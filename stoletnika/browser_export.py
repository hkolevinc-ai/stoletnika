"""Import a local browser export. This path never makes network requests."""
import gzip
import json
from urllib.parse import urlsplit
from .catalog import SCOPES, product


def load_export(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        data = json.load(stream)
    if data.get('format') != 'stoletnika-browser-export' or data.get('version') != 1:
        raise ValueError('This is not a Stoletnika browser export')
    if not data.get('complete'):
        raise ValueError('The browser export is incomplete. Continue scanning in Chrome and export the completed catalog.')
    stats = data.get('scopes', [])
    if {s.get('scope') for s in stats} != set(SCOPES):
        raise ValueError('Browser export must contain exactly the three requested scopes')
    entries = data.get('items', [])
    discovered = int(data.get('discovered_products', 0))
    if not entries or len(entries) != discovered:
        raise ValueError('Exported product count does not match the discovered catalog')
    products = []
    seen = set()
    for entry in entries:
        item = entry['item']
        url = urlsplit(item['url'])
        if url.scheme != 'https' or url.netloc != 'stoletnika.eu' or not url.path.startswith('/product/'):
            raise ValueError('Product URL outside Stoletnika')
        if item.get('scope') not in SCOPES:
            raise ValueError('Product scope outside the requested catalog')
        if item['url'] in seen:
            raise ValueError('Duplicate product page in browser export')
        seen.add(item['url'])
        variants = product(entry['html'], item)
        for variant in variants:
            variant['source_fetched_at'] = entry.get('fetched_at', '')
        products.extend(variants)
    return products, stats, discovered, data.get('started_at', '')
