import json,re
from decimal import Decimal,ROUND_HALF_UP
from urllib.parse import urlsplit,urlunsplit,parse_qs,urlencode,urljoin
from concurrent.futures import ThreadPoolExecutor,as_completed
from .htmltree import parse

SCOPES=[
 'https://stoletnika.eu/vendor/bilka-chudodeyka',
 'https://stoletnika.eu/vendor/herbalkan',
 'https://stoletnika.eu/category/hranitelni-dobavki?vendors=natural-factors,webber-naturals'
]

def page_url(scope,page):
    u=urlsplit(scope); q=parse_qs(u.query)
    if page>1:q['page']=[str(page)]
    else:q.pop('page',None)
    return urlunsplit((u.scheme,u.netloc,u.path,urlencode(q,doseq=True),''))

def pagination(tree,scope):
    source=urlsplit(scope);q=parse_qs(source.query);wanted=q.get('vendors',[])
    nums={1}
    for a in tree.all('a'):
        u=urlsplit(urljoin(scope,a.get('href')))
        if u.netloc!=source.netloc or u.path!=source.path:continue
        query=parse_qs(u.query)
        # Restore the original vendor filter even if a theme omits it in a link.
        if wanted and query.get('vendors',wanted)!=wanted:continue
        p=query.get('page',['1'])[0]
        if p.isdigit() and 0<int(p)<=200: nums.add(int(p))
    return max(nums)

def listing(tree,scope):
    rows=[]
    for box in tree.all(cls='_product'):
        link=box.first(cls='_product-name-tag')
        a=link.first('a') if link else None
        if not a:continue
        u=urljoin(scope,a.get('href'))
        if urlsplit(u).netloc!='stoletnika.eu' or not urlsplit(u).path.startswith('/product/'):continue
        pricebox=box.first(cls='_product-price')
        rows.append({'url':urlunsplit((*urlsplit(u)[:3],'','')),'id':box.get('data-product-id'),'name':a.clean(),'scope':scope,'listing_price':pricebox.clean() if pricebox else ''})
    return rows

def discover(fetcher,workers=6):
    products={};stats=[];pages=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        first={pool.submit(fetcher.get,s):s for s in SCOPES}
        for future in as_completed(first):
            scope=first[future];tree=parse(future.result());n=pagination(tree,scope);found=listing(tree,scope)
            if not found:raise RuntimeError('No products found in required scope: '+scope)
            stats.append({'scope':scope,'pages':n,'listing_rows':len(found)})
            for p in found:products.setdefault(p['url'],p)
            pages.extend((scope,i) for i in range(2,n+1))
        more={pool.submit(fetcher.get,page_url(scope,p)):(scope,p) for scope,p in pages}
        for future in as_completed(more):
            scope,p=more[future];found=listing(parse(future.result()),scope)
            if not found:raise RuntimeError(f'Empty required listing page {p} in {scope}')
            stat=next(x for x in stats if x['scope']==scope);stat['listing_rows']+=len(found)
            for item in found:products.setdefault(item['url'],item)
    return sorted(products.values(),key=lambda p:(SCOPES.index(p['scope']),int(p['id'] or 0))),sorted(stats,key=lambda x:SCOPES.index(x['scope']))

def js_object(text,label):
    match=re.search(re.escape(label)+r'\s*=\s*',text)
    if not match:return {}
    try:return json.JSONDecoder().raw_decode(text[match.end():].lstrip())[0]
    except json.JSONDecodeError:return {}

def money(value):
    if value is None or str(value).strip()=='':return None
    value=str(value).replace('\u00a0','').replace(' ','').replace(',','.')
    try:return float(Decimal(value).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
    except Exception:return None

def flatten_variants(value):
    if isinstance(value,list):
        for x in value:
            if isinstance(x,dict) and 'id' in x and ('price' in x or 'price_input' in x):yield x
            else:yield from flatten_variants(x)
    elif isinstance(value,dict):
        for x in value.values():yield from flatten_variants(x)

def description_lines(node):
    if not node:return []
    lines=[]
    blocks=node.all('p')
    for p in blocks:
        text=p.clean()
        if text:lines.append(text)
    if not blocks:lines=[node.clean()]
    # Tables are retained, including dosage and nutrition units.
    for t in node.all('table'):
        for row in t.all('tr'):
            cells=[c.clean() for c in row.children if hasattr(c,'tag') and c.tag in ('td','th')]
            if cells:lines.append(' | '.join(cells))
    return list(dict.fromkeys(lines))

def product(html,item):
    tree=parse(html);data={};schema={}
    for s in tree.all('script'):
        text=s.text('')
        if 'window.cc_page_data' in text: data=js_object(text,'window.cc_page_data') or data
        if s.get('type')=='application/ld+json':
            try:
                obj=json.loads(text)
                if isinstance(obj,dict) and obj.get('@type')=='Product':schema=obj
            except ValueError:pass
    if data.get('type')!='product' or not data.get('id'):raise ValueError('CloudCart product payload missing')
    if str(data['id'])!=str(item['id']):raise ValueError('Product ID does not match the listing')
    brand_url=data.get('brand_details',{}).get('url','')
    allowed=('natural-factors','webber-naturals') if '/category/' in item['scope'] else (urlsplit(item['scope']).path.rsplit('/',1)[1],)
    if urlsplit(brand_url).path.rsplit('/',1)[-1] not in allowed:raise ValueError('Product brand falls outside requested scope')
    if data.get('currency')!='EUR':raise ValueError('Product price currency is not EUR')
    desc=next((n for n in tree.all() if n.get('id')=='product-details-description'),None)
    lines=description_lines(desc)
    images=[]
    def add_image(url):
        if not isinstance(url,str) or '/products/'+str(data['id'])+'/' not in url:return
        u=urlsplit(urljoin(item['url'],url));q=parse_qs(u.query);q.update({'width':['1920'],'height':['1920']})
        url=urlunsplit((u.scheme,u.netloc,u.path,urlencode(q,doseq=True),''))
        if url not in images:images.append(url)
    add_image(data.get('image_url'));add_image(schema.get('image'))
    for n in tree.all():
        if n.tag in ('a','img'):
            for attr in ('data-zoom-image','data-src','data-first-src','src','href'):add_image(n.get(attr))
    detail=next((n for n in tree.all(attr='data-variant-selection') if n.get('data-product-id')==str(data['id'])),None)
    variants=list(flatten_variants(json.loads(detail.get('data-variant-selection')))) if detail else []
    if not variants:variants=data.get('variants',[])
    summarized={str(v['id']):v for v in data.get('variants',[])}
    out=[]
    for v in variants:
        sv=summarized.get(str(v['id']),{})
        original=money(sv.get('price',v.get('price_input',data.get('price'))))
        discount=money(sv.get('discount_price',data.get('discount_price')))
        current=discount if discount is not None and discount>0 else original
        if current is None or current<=0:raise ValueError('No positive EUR price for variant '+str(v['id']))
        availability=v.get('stock_status_key',sv.get('availability','unknown'))
        available=availability in ('in_stock','limited_stock') and v.get('enable_sell',sv.get('enable_sell',True)) is not False
        qty=v.get('quantity_unit',v.get('quantity'))
        # Tracking-disabled stock is not a published exact quantity.
        exact=money(qty) if qty is not None and v.get('tracking')=='yes' else None
        weight=money(v.get('weight'))
        if weight is None:
            sw=schema.get('weight',{});weight=money(sw.get('value'))
            if weight is not None and sw.get('unitCode','').upper() in ('KG','KGM'):weight*=1000
        out.append({**item,'id':str(data['id']),'variant_id':str(v['id']),'name':data.get('name') or item.get('name',''),'brand':data.get('brand',''),'brand_slug':urlsplit(brand_url).path.rsplit('/',1)[-1],
           'site_category':data.get('category',''),'description_lines':lines,'description':'\n'.join(lines),'images':images,
           'sku':str(v.get('sku') or data.get('sku') or f'ST-{data["id"]}-{v["id"]}'),
           'barcode':str(v.get('barcode') or data.get('barcode') or ''),'price_eur':current,'list_price_eur':original if original and original>current else None,
           'available':available,'availability':availability,'stock':max(0,int(exact)) if available and exact is not None else (0 if not available else None),
           'weight_g':weight if weight and weight>0 else None,'variant_label':' / '.join(str(v.get(k) or '') for k in ('v1','v2','v3') if v.get(k)),
           'parameters':sv.get('parameters',[]),'has_variants':len(variants)>1})
    if not out:raise ValueError('No variants found')
    return out
