import hashlib,pathlib,subprocess,time,urllib.request,urllib.error

class Fetcher:
    def __init__(self,cache='.cache/html',refresh=False,timeout=30,retries=3,transport='auto'):
        self.cache=pathlib.Path(cache); self.cache.mkdir(parents=True,exist_ok=True)
        self.refresh,self.timeout,self.retries,self.transport=refresh,timeout,retries,transport
    def get(self,url):
        p=self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.html')
        if p.exists() and not self.refresh: return p.read_text(encoding='utf-8')
        error=None
        for attempt in range(self.retries):
            try:
                if self.transport=='curl':
                    result=subprocess.run(['curl','--fail','--silent','--show-error','--location','--max-time',str(self.timeout),'--user-agent','Mozilla/5.0 StoletnikaCatalog/1.0',url],capture_output=True,check=True)
                    raw=result.stdout
                else:
                    try:
                        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 StoletnikaCatalog/1.0','Accept':'text/html','Accept-Encoding':'identity'})
                        with urllib.request.urlopen(req,timeout=self.timeout) as response: raw=response.read()
                    except (urllib.error.URLError,TimeoutError):
                        if self.transport!='auto': raise
                        result=subprocess.run(['curl','--fail','--silent','--show-error','--location','--max-time',str(self.timeout),url],capture_output=True,check=True)
                        raw=result.stdout
                text=raw.decode('utf-8')
                if len(text)<500 or ('<html' not in text.lower() and 'data-product-id' not in text): raise ValueError('Response is not a catalog HTML page')
                temp=p.with_suffix('.tmp');temp.write_text(text,encoding='utf-8');temp.replace(p)
                return text
            except Exception as exc:
                error=exc
                if attempt+1<self.retries: time.sleep(min(2**attempt,4))
        raise RuntimeError(f'Cannot download {url}: {error}')
