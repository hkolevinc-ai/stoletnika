import asyncio
import contextlib
import io
import json
import pathlib
import tempfile
import time
import unittest
import zipfile
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock,Mock,patch
from stoletnika.chrome import ChromeSession,ChromeFetcher,requested_url
from stoletnika.catalog import SCOPES
from stoletnika.network import DownloadError
from stoletnika.template import N,Template

CATALOG='<div class="_products-list" data-product-id="1">'+'x'*600+'</div>'

class ChromePageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.session=ChromeSession.__new__(ChromeSession)
        self.session.lock=asyncio.Lock();self.session.timeout=.02;self.session.delay=0
        self.session.folder=pathlib.Path(self.temp.name)
        self.session.last_navigation=0;self.session.failure=None;self.session.status=403
        self.session.tab=Mock(get=AsyncMock(),evaluate=AsyncMock(return_value=SCOPES[0]),get_content=AsyncMock(return_value=CATALOG),save_screenshot=AsyncMock())

    async def test_one_tab_is_reused_for_catalog_navigation(self):
        self.assertEqual(await self.session._get(SCOPES[0]),CATALOG)
        self.session.tab.evaluate.return_value=SCOPES[1]
        self.assertEqual(await self.session._get(SCOPES[1]),CATALOG)
        self.assertEqual(self.session.tab.get.await_count,2)

    async def test_refusal_saves_page_and_stops_further_navigation(self):
        self.session.tab.get_content.return_value='<html>Access denied, code 1010</html>'
        with self.assertRaises(DownloadError):await self.session._get(SCOPES[0])
        with self.assertRaisesRegex(DownloadError,'Scanning stopped'):await self.session._get(SCOPES[1])
        self.assertEqual(self.session.tab.get.await_count,1)
        self.assertIn('1010',(self.session.folder/'blocked_page.html').read_text())
        self.assertEqual((self.session.folder/'blocked_url.txt').read_text(),SCOPES[0])

    async def test_old_page_content_is_not_returned_for_new_navigation(self):
        self.session.tab.evaluate.return_value=SCOPES[1]
        with self.assertRaises(DownloadError):await self.session._get(SCOPES[0])

    async def test_outside_scope_fails_before_browser_navigation(self):
        for url in ['https://example.com/product/x','https://stoletnika.eu/category/other','https://stoletnika.eu/category/hranitelni-dobavki']:
            self.assertFalse(requested_url(url))
            with self.assertRaises(DownloadError):await self.session._get(url)
        self.session.tab.get.assert_not_awaited()

class ChromeWorkflowTests(unittest.TestCase):
    def test_default_scan_writes_three_eur_rows_without_key_or_export(self):
        import scrape_stoletnika
        with tempfile.TemporaryDirectory() as folder:
            out=pathlib.Path(folder)/'output'
            slugs=['bilka-chudodeyka','herbalkan','natural-factors'];calls=[]
            def get(url):
                calls.append(url)
                if url in SCOPES:
                    i=SCOPES.index(url)
                    return f'<div class="_products-list"><div class="_product" data-product-id="{i+1}"><div class="_product-name-tag"><a href="/product/p{i+1}">Vitamin D3</a></div></div></div>'+' '*600
                i=int(url[-1])-1
                data={'type':'product','id':i+1,'name':'Vitamin D3','brand':slugs[i],'currency':'EUR','brand_details':{'url':'https://stoletnika.eu/vendor/'+slugs[i]},'variants':[{'id':100+i,'price':9.5+i,'availability':'in_stock'}]}
                return f'<div data-product-id="{i+1}"></div><script>window.cc_page_data = '+json.dumps(data)+';</script>'+' '*600
            browser=Mock(get=get)
            argv=['scrape_stoletnika.py','--out',str(out),'--refresh']
            with patch('sys.argv',argv),patch('stoletnika.chrome.ChromeSession',return_value=browser),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(scrape_stoletnika.main(),0)
            self.assertEqual(set(calls),set(SCOPES)|{'https://stoletnika.eu/product/p1','https://stoletnika.eu/product/p2','https://stoletnika.eu/product/p3'})
            self.assertEqual(len(calls),6)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual((summary['source'],summary['currency'],summary['variant_rows']),('chrome','EUR',3))
            with zipfile.ZipFile(out/'TEMU_STOLETNIKA.xlsx') as book:
                self.assertIsNone(book.testzip())
                sheet=ET.fromstring(book.read(Template('templates/temu_template.xlsx').sheets['Template']))
            self.assertEqual([sheet.find(f"m:sheetData/m:row[@r='{r}']/m:c[@r='LB{r}']/m:v",N).text for r in range(5,8)],['9.5','10.5','11.5'])
            browser.close.assert_called_once()
