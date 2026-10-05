import copy
import gzip
import json
import pathlib
import tempfile
import unittest
import contextlib
import io
import zipfile
from unittest.mock import patch
from stoletnika.browser_export import load_export
from stoletnika.catalog import SCOPES


class BrowserExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / 'export.json.gz'
        payload = {'type':'product','id':1,'name':'Vitamin D3','brand':'Natural Factors','brand_details':{'url':'https://stoletnika.eu/vendor/natural-factors'},'currency':'EUR','price':10.5,'variants':[{'id':10,'price':10.5,'availability':'in_stock'}]}
        self.data = {'format':'stoletnika-browser-export','version':1,'complete':True,'discovered_products':1,'scopes':[{'scope':s} for s in SCOPES],'items':[{'item':{'id':'1','url':'https://stoletnika.eu/product/test','scope':SCOPES[2],'name':'Vitamin D3'},'html':'<script>window.cc_page_data = '+json.dumps(payload)+';</script>','fetched_at':'2026-10-05T14:00:00Z'}]}

    def write(self):
        with gzip.open(self.path,'wt',encoding='utf-8') as stream:json.dump(self.data,stream)

    def test_gzip_export_retains_eur_and_source_time(self):
        self.write()
        products,stats,count,_=load_export(self.path)
        self.assertEqual((len(products),len(stats),count),(1,3,1))
        self.assertEqual(products[0]['price_eur'],10.5)
        self.assertEqual(products[0]['source_fetched_at'],'2026-10-05T14:00:00Z')

    def test_partial_export_is_rejected(self):
        self.data['complete']=False;self.write()
        with self.assertRaisesRegex(ValueError,'incomplete'):load_export(self.path)

    def test_missing_product_is_rejected(self):
        self.data['discovered_products']=2;self.write()
        with self.assertRaisesRegex(ValueError,'count'):load_export(self.path)

    def test_other_scope_and_url_are_rejected(self):
        original=copy.deepcopy(self.data)
        self.data['scopes'][0]['scope']='https://stoletnika.eu/category/other';self.write()
        with self.assertRaisesRegex(ValueError,'three requested scopes'):load_export(self.path)
        self.data=original
        self.data['items'][0]['item']['url']='https://example.com/product/test';self.write()
        with self.assertRaisesRegex(ValueError,'outside Stoletnika'):load_export(self.path)

    def test_excel_build_does_not_start_a_network_client(self):
        import scrape_stoletnika
        self.write()
        out=pathlib.Path(self.temp.name)/'output'
        argv=['scrape_stoletnika.py','--browser-export',str(self.path),'--out',str(out)]
        with patch('sys.argv',argv),patch.object(scrape_stoletnika,'Fetcher',side_effect=AssertionError('No network client is allowed')) as network,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(scrape_stoletnika.main(),0)
        network.assert_not_called()
        with zipfile.ZipFile(out/'TEMU_STOLETNIKA.xlsx') as workbook:
            self.assertIsNone(workbook.testzip())
        summary=json.loads((out/'summary.json').read_text())
        self.assertEqual((summary['source'],summary['currency'],summary['variant_rows']),('browser_export','EUR',1))
