import unittest,json,copy,tempfile,pathlib,zipfile,xml.etree.ElementTree as E
from stoletnika.catalog import page_url,pagination,product,SCOPES
from stoletnika.htmltree import parse
from stoletnika.mapping import map_row,pick_category
from stoletnika.template import Template,N,colnum

class ScraperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template=Template('templates/temu_template.xlsx')
        cls.cfg=json.loads(pathlib.Path('config.json').read_text())
        cls.example={'id':'1','variant_id':'10','sku':'000123','barcode':'0123456789012','name':'Витамин D3, 30 капсули','brand':'Natural Factors',
            'brand_slug':'natural-factors','description_lines':['Производител: Natural Factors, Canada','Състав: Витамин D3 (холекалциферол).'],
            'description':'','images':['https://stoletnika.eu/cdn/img/products/1/bottle.jpg'],'price_eur':10.5,'list_price_eur':None,'stock':7,
            'weight_g':100,'variant_label':'','available':True,'has_variants':False,'site_category':'Витамини','url':'https://stoletnika.eu/product/test','scope':SCOPES[2]}
    def test_all_page_urls_keep_exact_vendor_filter(self):
        from urllib.parse import parse_qs,urlsplit
        for i in [1,2,15]:
            q=parse_qs(urlsplit(page_url(SCOPES[2],i)).query)
            self.assertEqual(q['vendors'],['natural-factors,webber-naturals'])
    def test_pagination_cannot_follow_other_category(self):
        html='<a href="/category/else?page=100">100</a><a href="/category/hranitelni-dobavki?page=15">Last</a>'
        self.assertEqual(pagination(parse(html),SCOPES[2]),15)
    def test_current_eur_sale_and_reference_price(self):
        data={'type':'product','id':1,'name':'Витамин D3','brand':'Natural Factors','brand_details':{'url':'https://stoletnika.eu/vendor/natural-factors'},'currency':'EUR','price':25,'discount_price':20,'variants':[{'id':10,'price':'25','discount_price':20,'availability':'in_stock'}]}
        html='<html><script>window.cc_page_data = '+json.dumps(data)+';</script></html>'
        p=product(html,{'id':'1','scope':SCOPES[2],'url':'https://stoletnika.eu/product/test','name':''})[0]
        self.assertEqual((p['price_eur'],p['list_price_eur']),(20,25))
        data['currency']='BGN'
        with self.assertRaisesRegex(ValueError,'not EUR'):product('<html><script>window.cc_page_data = '+json.dumps(data)+';</script></html>',{'id':'1','scope':SCOPES[2],'url':'https://stoletnika.eu/product/test','name':''})
    def test_wrong_vendor_rejected(self):
        data={'type':'product','id':1,'brand_details':{'url':'https://stoletnika.eu/vendor/other-brand'}}
        with self.assertRaisesRegex(ValueError,'outside'):product('<html><script>window.cc_page_data = '+json.dumps(data)+';</script></html>',{'id':'1','scope':SCOPES[2],'url':'https://stoletnika.eu/product/test'})
    def test_reference_not_invented_missing_dimensions_reported(self):
        row,review=map_row(self.example,self.template,self.cfg)
        self.assertEqual(row['LE'],'N/A');self.assertIsNone(row['LD'])
        self.assertTrue(any(x.startswith('LG ') for x in review['missing_fields']))
        self.assertEqual(row['LF'],100)
        self.assertEqual(row['LY'],'Canada')
        self.assertEqual(row['LT'],'0123456789012')
    def test_same_product_two_bottle_bundle_retains_unit_count(self):
        p=copy.deepcopy(self.example);p['name']='ПРОМО ПАКЕТ Витамин D3 80 таблетки - 2 броя'
        row,_=map_row(p,self.template,self.cfg)
        self.assertEqual(row['LL'],2);self.assertEqual(row['LP'],80);self.assertEqual(row['LQ'],160)
        self.assertEqual(row['LJ'],'Multi-piece set')
    def test_closest_category_for_unsupported_product(self):
        p=copy.deepcopy(self.example);p['name']='Билков спрей за крака';p['brand_slug']='herbalkan';p['description_lines']=[]
        cid,reason=pick_category(p,self.template)
        self.assertIn(cid,self.template.category_names);self.assertTrue(reason.startswith('nearest:'))
        p['name']='Витамин K2';self.assertEqual(pick_category(p,self.template)[0],'17710')
    def test_missing_plant_category_and_mixed_bundle_have_valid_nearest_leaf(self):
        p=copy.deepcopy(self.example);p.update(name='Билкова Тинктура Турта',brand_slug='bilka-chudodeyka',description_lines=[])
        self.assertEqual(pick_category(p,self.template)[0],'17509')
        p['name']='ПРОМО ПАКЕТ Витамин C + Билков чай'
        self.assertEqual(pick_category(p,self.template)[0],'17707')
        row,review=map_row(p,self.template,self.cfg)
        self.assertTrue(row['E']);self.assertTrue(review['category_reason'].startswith('nearest:'))
        self.assertNotIn('E Category',review['missing_fields'])
    def test_capsule_additives_do_not_determine_nearest_category(self):
        p=copy.deepcopy(self.example);p.update(name='Комплекс Example',description_lines=[
            'Съставки: (в 1 капсула)', 'Ехинацея 300 mg',
            'Други съставки: микрокристална целулоза, силициев диоксид.'])
        self.assertEqual(pick_category(p,self.template)[0],'17512')
        p.update(name='Билков спрей за гърло с Лавандула',brand_slug='bilka-chudodeyka')
        self.assertEqual(pick_category(p,self.template)[0],'17509')
    def test_configured_unknown_dropdown_reports_problem(self):
        cfg=copy.deepcopy(self.cfg);cfg['brands']['natural-factors']['manufacturer']='Unknown fake company'
        row,review=map_row(self.example,self.template,cfg)
        self.assertNotIn('NY',row);self.assertTrue(any('Manufacturer' in x for x in review['warnings']))
    def test_native_metadata_and_typed_values_survive(self):
        rows=[map_row(self.example,self.template,self.cfg)[0]]
        with tempfile.TemporaryDirectory() as folder:
            dest=pathlib.Path(folder)/'filled.xlsx';self.template.write(dest,rows)
            with zipfile.ZipFile(dest) as z:
                self.assertIsNone(z.testzip())
                for name in self.template.zip.namelist():
                    if name!=self.template.sheets['Template']:self.assertEqual(z.read(name),self.template.zip.read(name))
                new=E.fromstring(z.read(self.template.sheets['Template']))
                old=E.fromstring(self.template.sheet_xml)
                for tag in ('dataValidations','conditionalFormatting','cols','sheetViews','mergeCells'):
                    self.assertEqual([E.tostring(x) for x in new.findall('m:'+tag,N)],[E.tostring(x) for x in old.findall('m:'+tag,N)])
                self.assertEqual(new.find("m:sheetData/m:row[@r='5']/m:c[@r='LB5']/m:v",N).text,'10.5')
                self.assertEqual(new.find("m:sheetData/m:row[@r='5']/m:c[@r='LT5']/m:is/m:t",N).text,'0123456789012')
    def test_blank_category_retains_formula_and_ordered_native_cells(self):
        import re
        row={'E':'','G':'Unsupported category product','LB':9.5}
        with tempfile.TemporaryDirectory() as folder:
            dest=pathlib.Path(folder)/'filled.xlsx';self.template.write(dest,[row])
            with zipfile.ZipFile(dest) as z:
                root=E.fromstring(z.read(self.template.sheets['Template']))
            cells=root.find("m:sheetData/m:row[@r='5']",N)
            columns=[colnum(re.match(r'[A-Z]+',c.get('r'))[0]) for c in cells]
            self.assertEqual(columns,sorted(columns))
            self.assertIn('VLOOKUP(E5',cells.find("m:c[@r='F5']/m:f",N).text)
            self.assertEqual(cells.find("m:c[@r='F5']",N).get('s',''),self.template.styles.get('F',''))

if __name__=='__main__':unittest.main()
