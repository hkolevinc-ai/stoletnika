"""One browser event loop, shared cookies, bounded concurrent tabs."""
import asyncio,concurrent.futures,os,threading

class BrowserTransport:
    def __init__(self,timeout=35):
        self.timeout=timeout;self.ready=concurrent.futures.Future();self.loop=asyncio.new_event_loop()
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
        self.ready.result(timeout=60)
    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:self.loop.run_until_complete(self._start());self.ready.set_result(True)
        except Exception as exc:self.ready.set_exception(exc);self.loop.close();return
        self.loop.run_forever();self.loop.close()
    async def _start(self):
        from playwright.async_api import async_playwright
        self.playwright=await async_playwright().start()
        self.browser=await self.playwright.chromium.launch(headless=not bool(os.environ.get('DISPLAY')))
        self.context=await self.browser.new_context(locale='bg-BG',viewport={'width':1366,'height':900})
        self.semaphore=asyncio.Semaphore(3)
    async def _get(self,url):
        from .network import DownloadError
        async with self.semaphore:
            page=await self.context.new_page();response=None
            try:
                response=await page.goto(url,wait_until='domcontentloaded',timeout=self.timeout*1000)
                await page.wait_for_selector('[data-product-id]',state='attached',timeout=self.timeout*1000)
                html=await page.content();status=response.status if response else None
                if status and status>=400 and 'window.cc_page_data' not in html and '_products-list' not in html:raise DownloadError('browser',status,'Browser navigation returned an error page')
                return html
            except Exception as exc:
                raise DownloadError('browser',response.status if response else None,str(exc)[:300]) from exc
            finally:await page.close()
    def get(self,url):
        return asyncio.run_coroutine_threadsafe(self._get(url),self.loop).result(timeout=self.timeout*3+10)
    async def _stop(self):
        await self.context.close();await self.browser.close();await self.playwright.stop()
    def close(self):
        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._stop(),self.loop).result(timeout=20)
            self.loop.call_soon_threadsafe(self.loop.stop);self.thread.join(timeout=10)
