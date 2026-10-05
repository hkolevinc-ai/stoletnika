"""Small access test: first listing pages and one product from each scope."""
from .catalog import SCOPES,listing,pagination,product
from .htmltree import parse


def check_access(fetcher):
    checks=[]
    for scope in SCOPES:
        tree=parse(fetcher.get(scope));items=listing(tree,scope)
        if not items:raise ValueError('No catalog found in '+scope)
        variant=product(fetcher.get(items[0]['url']),items[0])[0]
        checks.append({'scope':scope,'pages':pagination(tree,scope),'first_page_products':len(items),'sample_product':variant['url'],'sample_brand':variant['brand'],'sample_price_eur':variant['price_eur']})
    return {'access_test':'passed','requests_expected':6,'full_catalog_scraped':False,'checks':checks}
