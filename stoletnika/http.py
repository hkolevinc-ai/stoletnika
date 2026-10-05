"""Read public CloudCart catalog responses with ordinary HTTP, without a browser."""
import hashlib
import datetime
import json
import pathlib
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit

from .catalog import SCOPES

HEADERS = {
    'User-Agent': 'StoletnikaCatalog/1.5',
    'Accept': 'text/html, application/xhtml+xml;q=0.9, */*;q=0.8',
    'Accept-Encoding': 'identity',
}


class DownloadError(RuntimeError):
    def __init__(self, status, detail):
        self.status = status
        super().__init__(f'HTTP {status if status is not None else "unknown"}: {detail}')


def allowed_url(url):
    u = urlsplit(url)
    if u.scheme != 'https' or u.netloc != 'stoletnika.eu' or u.fragment:
        return False
    q = parse_qs(u.query, keep_blank_values=True)
    if u.path.startswith('/product/') and len(u.path.split('/')) == 3:
        return bool(u.path.rsplit('/', 1)[-1]) and not q
    for scope in SCOPES:
        s = urlsplit(scope)
        if u.path != s.path:
            continue
        expected = parse_qs(s.query)
        if set(q) - set(expected) - {'page'}:
            return False
        if any(q.get(k) != value for k, value in expected.items()):
            return False
        if 'page' in q and (len(q['page']) != 1 or not q['page'][0].isdigit()
                            or not 1 <= int(q['page'][0]) <= 200):
            return False
        return True
    return False


def catalog_html(text, url):
    """Normalize the public HTML or quick-view JSON envelope; never execute JS."""
    stripped = text.lstrip()
    if stripped.startswith('{'):
        try:
            data = json.loads(stripped)
        except ValueError as exc:
            raise DownloadError(200, 'Invalid catalog JSON') from exc
        if data.get('status') not in (None, 'success'):
            raise DownloadError(200, 'Catalog JSON reports an error')
        text = data.get('body') or data.get('html')
        if not isinstance(text, str):
            raise DownloadError(200, 'Catalog JSON has no HTML body')
    lower = text.lower()
    if ('/cdn-cgi/challenge-platform/' in lower or '<title>just a moment' in lower
            or 'cf-chl-' in lower):
        raise DownloadError(200, 'Site returned a human verification page')
    if len(text) < 500 or 'window.cc_page_data' not in text:
        raise DownloadError(200, 'Structured CloudCart catalog data missing')
    if '/product/' in url:
        valid = 'data-product-id' in text
    else:
        valid = 'data-product-id' in text and ('_products-list' in text or 'js-products-container' in text)
    if not valid:
        raise DownloadError(200, 'Response is not the requested catalog page')
    return text


class CatalogRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise DownloadError(code, 'Redirect outside the requested catalog')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    def __init__(self, cache='.cache/http-v15', refresh=False, timeout=35,
                 delay=1.0, diagnostics='output/network_diagnostics.json'):
        self.cache = pathlib.Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.refresh, self.timeout, self.delay = refresh, timeout, max(0, delay)
        self.diagnostics = pathlib.Path(diagnostics) if diagnostics else None
        self.events = []
        self._lock = threading.RLock()
        self._next_request = 0.0
        self._blocked = None
        self._local = threading.local()

    def _reserve_request(self):
        with self._lock:
            if self._blocked:
                raise DownloadError(None, self._blocked)
            pause = max(0, self._next_request - time.monotonic())
            self._next_request = max(self._next_request, time.monotonic()) + self.delay
        if pause:
            time.sleep(pause)
        with self._lock:
            if self._blocked:
                raise DownloadError(None, self._blocked)

    def _record(self, url, status, size, error=None):
        event = {'url': url, 'method': 'http', 'status': status, 'bytes': size,
                 'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'error': str(error)[:500] if error else None}
        with self._lock:
            self.events.append(event)
            if self.diagnostics:
                self.diagnostics.parent.mkdir(parents=True, exist_ok=True)
                self.diagnostics.write_text(json.dumps(self.events, ensure_ascii=False, indent=2), encoding='utf-8')

    def _save_block(self, url, text):
        with self._lock:
            self._blocked = 'Site refused catalog access; no further website requests will be sent'
            if self.diagnostics:
                folder = self.diagnostics.parent
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'blocked_page.html').write_text(text, encoding='utf-8')
                (folder / 'blocked_url.txt').write_text(url, encoding='utf-8')

    def get(self, url):
        if not allowed_url(url):
            raise ValueError('URL outside the three requested catalog scopes: ' + url)
        p = self.cache / (hashlib.sha256(url.encode()).hexdigest() + '.html')
        if p.exists() and not self.refresh:
            try:
                return catalog_html(p.read_text(encoding='utf-8'), url)
            except DownloadError:
                pass
        if not hasattr(self._local, 'opener'):
            self._local.opener = urllib.request.build_opener(CatalogRedirectHandler())
        for attempt in range(3):
            self._reserve_request()
            response, text, status = None, '', None
            try:
                try:
                    response = self._local.opener.open(urllib.request.Request(url, headers=HEADERS), timeout=self.timeout)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    status = response.status
                    text = response.read().decode('utf-8', errors='replace')
                if not allowed_url(response.geturl()):
                    raise DownloadError(status, 'Response URL outside the requested catalog')
                if status in (401, 403):
                    self._save_block(url, text)
                    raise DownloadError(status, 'Site refused this HTTP request')
                if status == 429 or 500 <= status < 600:
                    raise DownloadError(status, 'Temporary server error or request rate limit')
                if status != 200:
                    raise DownloadError(status, 'Catalog page unavailable')
                try:
                    normalized = catalog_html(text, url)
                except DownloadError:
                    self._save_block(url, text)
                    raise
                temp = p.with_suffix('.' + str(threading.get_ident()) + '.tmp')
                temp.write_text(normalized, encoding='utf-8')
                temp.replace(p)
                self._record(url, status, len(text.encode()))
                return normalized
            except Exception as exc:
                self._record(url, status, len(text.encode()), exc)
                retry = isinstance(exc, (urllib.error.URLError, TimeoutError)) or status == 429 or (status is not None and 500 <= status < 600)
                if not retry or attempt == 2 or self._blocked:
                    raise
                retry_after = response.headers.get('Retry-After', '') if response else ''
                pause = min(30, max(3 * (attempt + 1), int(retry_after) if retry_after.isdigit() else 0))
                time.sleep(pause)
        raise RuntimeError('Catalog download failed')

    def close(self):
        pass
