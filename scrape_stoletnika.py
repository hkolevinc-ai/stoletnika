#!/usr/bin/env python3
"""Automatically scan Stoletnika and fill the supplied Temu template."""
import argparse,concurrent.futures,csv,json,pathlib,sys,datetime,collections,traceback,os
from stoletnika.browser_export import load_export
from stoletnika.catalog import discover,product,SCOPES
from stoletnika.network import Fetcher
from stoletnika.template import Template
from stoletnika.mapping import map_row

def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def make_fetcher(args,cfg,out):
    if args.backend=='chrome':
        from stoletnika.chrome import ChromeFetcher
        return ChromeFetcher(refresh=args.refresh,diagnostics=out/'network_diagnostics.json',timeout=cfg.get('browser_timeout',45),delay=cfg.get('request_delay',1))
    return Fetcher(refresh=args.refresh,transport='urllib',retries=1,browser_fallback=False,diagnostics=out/'network_diagnostics.json',access_token=os.environ.get('STOLETNIKA_ACCESS_TOKEN',''))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--template',default='templates/temu_template.xlsx')
    ap.add_argument('--config',default='config.json')
    ap.add_argument('--out',default='output')
    ap.add_argument('--workers',type=int)
    ap.add_argument('--limit',type=int,default=0,help='Test only; 0 = full catalog')
    ap.add_argument('--refresh',action='store_true',help='Ignore cached pages')
    ap.add_argument('--offline-json',help='Rebuild only from a previously saved products.json')
    ap.add_argument('--browser-export',help='Import the .json.gz catalog downloaded from your Chrome')
    ap.add_argument('--online',action='store_true',help='Compatibility flag; online scanning is now the default')
    ap.add_argument('--backend',choices=['chrome','direct'],default='chrome')
    ap.add_argument('--check-access',action='store_true',help='Six-page access test; no full scan and no Excel')
    ap.add_argument('--no-xlsx',action='store_true',help='Extraction and validation only')
    args=ap.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(pathlib.Path(args.config).read_text(encoding='utf-8'))
    if args.check_access:
        from stoletnika.probe import check_access
        fetcher=make_fetcher(args,cfg,out)
        try:
            result=check_access(fetcher);write_json(out/'access_test.json',result)
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        except Exception as exc:
            write_json(out/'errors.json',[{'phase':'access_test','error':str(exc)}]);raise
        finally:
            if hasattr(fetcher,'usage'):write_json(out/'api_usage.json',fetcher.usage())
            fetcher.close()
        return 0
    workers=max(1,min(args.workers or cfg.get('workers',6),12))
    t=Template(args.template);errors=[];products=[];scope_stats=[];links=[];discovered_count=None;source_started_at=None
    if args.browser_export:
        products,scope_stats,discovered_count,source_started_at=load_export(args.browser_export)
        print(f'Imported {discovered_count} product pages from Chrome; no website requests.',flush=True)
    elif args.offline_json:
        products=json.loads(pathlib.Path(args.offline_json).read_text(encoding='utf-8'))
    else:
        fetcher=make_fetcher(args,cfg,out)
        print('Scanning exactly the 3 requested scopes...',flush=True)
        try:links,scope_stats=discover(fetcher,workers)
        except Exception as exc:
            write_json(out/'errors.json',[{'phase':'discovery','error':str(exc)}])
            if hasattr(fetcher,'usage'):write_json(out/'api_usage.json',fetcher.usage())
            fetcher.close()
            raise
        write_json(out/'discovery.json',{'scopes':scope_stats,'products':links})
        discovered_count=len(links)
        print(f'Found {discovered_count} unique products.',flush=True)
        if args.limit:links=links[:args.limit]
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            jobs={pool.submit(lambda item:product(fetcher.get(item['url']),item),item):item for item in links}
            for i,future in enumerate(concurrent.futures.as_completed(jobs),1):
                item=jobs[future]
                try:products.extend(future.result())
                except Exception as exc:errors.append({'phase':'product','id':item['id'],'url':item['url'],'error':str(exc)})
                if i%25==0 or i==len(jobs):
                    print(f'{i}/{len(jobs)} pages, {len(products)} variants, {len(errors)} download errors',flush=True)
                    write_json(out/'products.json',products)
        fetcher.close()
        if hasattr(fetcher,'usage'):write_json(out/'api_usage.json',fetcher.usage())
    products.sort(key=lambda p:(SCOPES.index(p['scope']),int(p['id']),int(p['variant_id'])))
    # Deduplicate by the actual CloudCart variant identifier.
    dedup={}
    for p in products:dedup.setdefault((p['id'],p['variant_id']),p)
    products=list(dedup.values());write_json(out/'products.json',products)
    mapped=[];reviews=[]
    for p in products:
        try:
            row,review=map_row(p,t,cfg);i=len(mapped)+5;mapped.append(row)
            reviews.append({'excel_row':i,'id':p['id'],'variant_id':p['variant_id'],'sku':p['sku'],'name':p['name'],'brand':p['brand'],'url':p['url'],**review})
        except Exception as exc:
            errors.append({'phase':'mapping','id':p['id'],'url':p['url'],'error':str(exc)})
    write_json(out/'mapped_rows.json',mapped);write_json(out/'review.json',reviews);write_json(out/'errors.json',errors)
    with (out/'review.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['excel_row','id','variant_id','sku','name','brand','category_id','category_reason','missing_fields','warnings','url']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in reviews:w.writerow({k:'; '.join(r[k]) if isinstance(r[k],list) else r[k] for k in fields})
    if mapped and not args.no_xlsx:t.write(out/'TEMU_STOLETNIKA.xlsx',mapped)
    summary={'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'version':'1.4.0','currency':'EUR',
      'source':'browser_export' if args.browser_export else ('saved_products' if args.offline_json else args.backend),'source_started_at':source_started_at,
      'scopes':scope_stats,'discovered_products':discovered_count,'scraped_products':len({p['id'] for p in products}),
      'variant_rows':len(mapped),'rows_without_category':sum(not r.get('E') for r in mapped),
      'rows_with_missing_required_fields':sum(bool(r['missing_fields']) for r in reviews),'rows_with_warnings':sum(bool(r['warnings']) for r in reviews),
      'unavailable_variants':sum(not p['available'] for p in products),'download_or_mapping_errors':len(errors),'limited_test':bool(args.limit),
      'brand_counts':dict(collections.Counter(p['brand'] for p in products))}
    write_json(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    if errors:return 2
    if not mapped:raise RuntimeError('No rows exported; inspect errors.json')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:print('ERROR:',exc,file=sys.stderr);sys.exit(1)
