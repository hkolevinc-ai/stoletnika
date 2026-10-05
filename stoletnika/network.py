"""HTTP transport with browser fallback and useful failure diagnostics."""
import hashlib,json,pathlib,subprocess,threading,time,urllib.request,urllib.error

USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
HEADERS={'User-Agent':USER_AGENT,'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Accept-Language':'bg-BG,bg;q=0.9,en;q=0.7','Referer':'https://stoletnika.eu/'}

class DownloadError(RuntimeError):
    def __init__(self,method,status,detail):
        self.method,self.status=method,status
        super().__init__(f'{method}: HTTP {status if status is not None else "unknown"}: {detail}')

def valid_catalog(text,url):
    if len(text)<500:return False
    if '/product/' in url:return 'window.cc_page_data' in text and 'data-product-id' in text
    return 'data-product-id' in text and ('_products-list' in text or 'js-products-container' in text)

class Fetcher:
    def __init__(self,cache='.cache/html',refresh=False,timeout=35,retries=2,transport='auto',browser_fallback=True,diagnostics='output/network_diagnostics.json',access_token=''):
        self.cache=pathlib.Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
        self.refresh,self.timeout,self.retries,self.transport=refresh,timeout,retries,transport
        self.browser_fallback=browser_fallback;self.diagnostics=pathlib.Path(diagnostics) if diagnostics else None
        self.events=[];self.local=threading.local();self.lock=threading.RLock();self.browser=None;self.browser_active=False
        self.access_token=access_token
    def _record(self,url,method,status,error):
        with self.lock:
            self.events.append({'url':url,'method':method,'status':status,'error':str(error)[:500]})
            if self.diagnostics:
                self.diagnostics.parent.mkdir(parents=True,exist_ok=True)
                self.diagnostics.write_text(json.dumps(self.events,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'NETWORK {method}, HTTP {status if status is not None else "unknown"}: {url}',flush=True)
    def _impersonated(self,url):
        try:from curl_cffi import requests
        except ImportError:raise DownloadError('chrome-http',None,'curl_cffi is not installed')
        if not hasattr(self.local,'session'):self.local.session=requests.Session(impersonate='chrome')
        r=self.local.session.get(url,timeout=self.timeout,allow_redirects=True,headers={'Accept-Language':HEADERS['Accept-Language'],'Referer':HEADERS['Referer']})
        if r.status_code>=400:raise DownloadError('chrome-http',r.status_code,r.reason)
        return r.text
    def _urllib(self,url):
        try:
            headers={**HEADERS,'Accept-Encoding':'identity'}
            if self.access_token:headers.update({'X-Stoletnika-Catalog-Token':self.access_token,'User-Agent':'StoletnikaTemuCatalog/1.4.0'})
            req=urllib.request.Request(url,headers=headers)
            with urllib.request.urlopen(req,timeout=self.timeout) as r:return r.read().decode('utf-8')
        except urllib.error.HTTPError as e:raise DownloadError('urllib',e.code,e.reason) from e
    def _curl(self,url):
        args=['curl','--silent','--show-error','--location','--max-time',str(self.timeout),'--user-agent',USER_AGENT,'--header','Accept-Language: '+HEADERS['Accept-Language'],'--referer','https://stoletnika.eu/','--write-out','\n__STOLETNIKA_HTTP_STATUS__:%{http_code}',url]
        r=subprocess.run(args,capture_output=True,timeout=self.timeout+5)
        body,_,tail=r.stdout.rpartition(b'\n__STOLETNIKA_HTTP_STATUS__:')
        status=int(tail.strip()) if tail.strip().isdigit() else None
        if r.returncode or status is None or status>=400:
            detail=r.stderr.decode('utf-8',errors='replace').strip() or f'HTTP response status {status}'
            raise DownloadError('curl',status,detail)
        return body.decode('utf-8')
    def _browser_get(self,url):
        with self.lock:
            if self.browser is None:
                from .browser import BrowserTransport
                self.browser=BrowserTransport(timeout=self.timeout)
                print('Starting Chrome browser fallback...',flush=True)
            browser=self.browser
        text=browser.get(url)
        with self.lock:self.browser_active=True
        return text
    def get(self,url):
        p=self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.html')
        if p.exists() and not self.refresh:
            text=p.read_text(encoding='utf-8')
            if valid_catalog(text,url):return text
        errors=[]
        methods=[('chrome-http',self._impersonated),('urllib',self._urllib),('curl',self._curl)] if self.transport=='auto' else [(self.transport,{'curl':self._curl,'urllib':self._urllib,'chrome-http':self._impersonated,'browser':self._browser_get}[self.transport])]
        if self.browser_active:methods=[('browser',self._browser_get)]
        for attempt in range(self.retries):
            for name,method in methods:
                try:
                    text=method(url)
                    if not valid_catalog(text,url):raise DownloadError(name,200,'The response is not the requested catalog page (possibly a challenge or error page)')
                    temp=p.with_suffix('.'+str(threading.get_ident())+'.tmp');temp.write_text(text,encoding='utf-8');temp.replace(p)
                    return text
                except Exception as exc:
                    errors.append(str(exc));self._record(url,name,getattr(exc,'status',None),exc)
            if self.browser_fallback and not any(name=='browser' for name,_ in methods):
                try:
                    text=self._browser_get(url)
                    if not valid_catalog(text,url):raise DownloadError('browser',None,'Catalog did not load')
                    p.write_text(text,encoding='utf-8');return text
                except Exception as exc:
                    errors.append(str(exc));self._record(url,'browser',getattr(exc,'status',None),exc)
            if attempt+1<self.retries:time.sleep(min(2**attempt,4))
        raise RuntimeError('Cannot download '+url+'; '+' | '.join(dict.fromkeys(errors))+'; see network_diagnostics.json and blocked_page.html when present.')
    def close(self):
        if self.browser:self.browser.close()
