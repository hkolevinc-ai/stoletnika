"""Load public catalog pages in one Chrome session, with bounded navigation."""
import asyncio
import concurrent.futures
import os
import pathlib
import shutil
import threading
import time
from urllib.parse import urlsplit,parse_qs
from .catalog import SCOPES
from .network import DownloadError,Fetcher,valid_catalog

def requested_url(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.netloc!='stoletnika.eu':return False
    if parsed.path.startswith('/product/'):return True
    for scope in SCOPES:
        wanted=urlsplit(scope)
        if parsed.path==wanted.path:
            return parse_qs(parsed.query).get('vendors',[])==parse_qs(wanted.query).get('vendors',[])
    return False

def same_page(actual,wanted):
    a,b=urlsplit(actual),urlsplit(wanted)
    return (a.netloc,a.path,parse_qs(a.query))==(b.netloc,b.path,parse_qs(b.query))

class ChromeSession:
    def __init__(self,timeout=45,delay=1,diagnostics_dir='output'):
        self.timeout=timeout;self.delay=delay;self.folder=pathlib.Path(diagnostics_dir)
        self.ready=concurrent.futures.Future();self.loop=asyncio.new_event_loop()
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
        self.ready.result(timeout=60)

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._start());self.ready.set_result(True)
        except Exception as exc:
            if getattr(self,"browser",None):
                try:self.loop.run_until_complete(self._stop())
                except Exception:pass
            self.ready.set_exception(exc);self.loop.close();return
        self.loop.run_forever();self.loop.close()

    async def _start(self):
        import nodriver as uc
        executable=os.environ.get('CHROME_BIN') or next((p for name in ('google-chrome','google-chrome-stable','chromium','chromium-browser') if (p:=shutil.which(name))),None)
        if not executable:raise RuntimeError('Chrome is missing. Run the supplied GitHub workflow on ubuntu-24.04.')
        self.browser=await uc.start(browser_executable_path=executable,headless=not bool(os.environ.get('DISPLAY')),browser_args=['--window-size=1366,900','--blink-settings=imagesEnabled=false'])
        self.tab=await self.browser.get('about:blank')
        self.lock=asyncio.Lock();self.last_navigation=0;self.failure=None;self.status=None;self.target=''
        await self.tab.send(uc.cdp.network.enable())
        self.tab.add_handler(uc.cdp.network.ResponseReceived,self._response)

    def _response(self,event):
        if getattr(event.type_,'value','')=='Document' and same_page(event.response.url,self.target):
            self.status=int(event.response.status)

    async def _diagnostics(self,html,url):
        self.folder.mkdir(parents=True,exist_ok=True)
        (self.folder/'blocked_page.html').write_text(html,encoding='utf-8')
        (self.folder/'blocked_url.txt').write_text(url,encoding='utf-8')
        try:await self.tab.save_screenshot(str(self.folder/'blocked_page.png'),format='png')
        except Exception:pass

    async def _get(self,url):
        if not requested_url(url):raise DownloadError('chrome',None,'URL outside the three requested catalog scopes')
        async with self.lock:
            if self.failure:raise DownloadError('chrome',self.failure.status,'Scanning stopped after a refused page; no further pages requested')
            await asyncio.sleep(max(0,self.delay-(time.monotonic()-self.last_navigation)))
            self.target=url;self.status=None;html='';last_error=None
            try:
                await asyncio.wait_for(self.tab.get(url),timeout=self.timeout)
                deadline=time.monotonic()+self.timeout
                while time.monotonic()<deadline:
                    try:
                        actual=await self.tab.evaluate('location.href')
                        html=await self.tab.get_content()
                        if same_page(actual,url) and valid_catalog(html,url):
                            self.last_navigation=time.monotonic();return html
                    except Exception as exc:last_error=exc
                    await asyncio.sleep(.5)
                detail='Chrome did not load the requested catalog page'
                if last_error:detail+=': '+str(last_error)[:200]
                self.failure=DownloadError('chrome',self.status,detail)
                await self._diagnostics(html,url)
                raise self.failure
            except Exception as exc:
                if not self.failure:
                    self.failure=DownloadError('chrome',self.status,str(exc)[:300])
                    await self._diagnostics(html,url)
                raise self.failure from None

    def get(self,url):
        return asyncio.run_coroutine_threadsafe(self._get(url),self.loop).result(timeout=self.timeout*3+20)

    async def _stop(self):
        await self.browser.aclose()
        self.browser.stop()
        await asyncio.sleep(.1)

    def close(self):
        if self.loop.is_running():
            try:asyncio.run_coroutine_threadsafe(self._stop(),self.loop).result(timeout=15)
            finally:
                self.loop.call_soon_threadsafe(self.loop.stop);self.thread.join(timeout=10)

class ChromeFetcher(Fetcher):
    def __init__(self,*,delay=1,timeout=45,**kwargs):
        self.delay=delay;self.session=None;self.startup_error=None
        super().__init__(cache='.cache/chrome',transport='urllib',browser_fallback=False,retries=1,timeout=timeout,**kwargs)

    def _urllib(self,url):
        with self.lock:
            if self.startup_error:raise self.startup_error
            if self.session is None:
                try:self.session=ChromeSession(self.timeout,self.delay,self.diagnostics.parent if self.diagnostics else 'output')
                except Exception as exc:
                    self.startup_error=DownloadError('chrome',None,str(exc));raise self.startup_error from None
        return self.session.get(url)

    def _record(self,url,method,status,error):super()._record(url,'chrome',status,error)

    def close(self):
        if self.session:self.session.close()
