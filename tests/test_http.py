import io
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch, Mock
from email.message import Message
from urllib.error import HTTPError

from stoletnika.catalog import SCOPES
from stoletnika.http import Fetcher, DownloadError, allowed_url, catalog_html, CatalogRedirectHandler

PRODUCT = 'https://stoletnika.eu/product/example'
HTML = '<div data-product-id="1"></div><script>window.cc_page_data = {};</script>' + (' ' * 600)
LISTING = '<div class="js-products-container">' + HTML + '</div>'


class Response(io.BytesIO):
    def __init__(self, text, status=200, url=PRODUCT):
        super().__init__(text.encode())
        self.status, self.url = status, url
        self.headers = Message()

    def geturl(self):
        return self.url


class HttpTests(unittest.TestCase):
    def test_exact_catalog_boundaries_and_filter(self):
        for url in [*SCOPES, PRODUCT, SCOPES[2] + '&page=15']:
            self.assertTrue(allowed_url(url), url)
        for url in ['http://stoletnika.eu/product/example', 'https://other.eu/product/example',
                    'https://stoletnika.eu/category/hranitelni-dobavki',
                    SCOPES[2].replace('natural-factors,webber-naturals', 'other'),
                    SCOPES[0] + '?page=0', SCOPES[0] + '?page=201',
                    'https://stoletnika.eu/cart', PRODUCT + '?login=1']:
            self.assertFalse(allowed_url(url), url)

    def test_html_and_public_json_envelopes(self):
        self.assertEqual(catalog_html(HTML, PRODUCT), HTML)
        for field in ['body', 'html']:
            self.assertEqual(catalog_html(json.dumps({'status': 'success', field: HTML}), PRODUCT), HTML)
        with self.assertRaises(DownloadError):
            catalog_html(json.dumps({'status': 'error', 'body': HTML}), PRODUCT)
        with self.assertRaises(DownloadError):
            catalog_html(json.dumps({'status': 'success', 'body': {}}), PRODUCT)

    def test_challenge_with_status_200_is_not_catalog(self):
        with self.assertRaisesRegex(DownloadError, 'human verification'):
            catalog_html('<title>Just a moment...</title>' + HTML, PRODUCT)

    def test_successful_http_and_cache_without_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            opener = Mock()
            opener.open.return_value = Response(HTML)
            with patch('stoletnika.http.urllib.request.build_opener', return_value=opener):
                fetcher = Fetcher(cache=folder, delay=0, diagnostics=None)
                self.assertEqual(fetcher.get(PRODUCT), HTML)
                self.assertEqual(fetcher.get(PRODUCT), HTML)
            self.assertEqual(opener.open.call_count, 1)
            self.assertEqual(fetcher.events[0]['status'], 200)
            headers = dict(opener.open.call_args.args[0].header_items())
            self.assertEqual(headers['User-agent'], 'StoletnikaCatalog/1.5')

    def test_403_stops_subsequent_requests_and_saves_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            opener = Mock()
            opener.open.side_effect = HTTPError(PRODUCT, 403, 'Forbidden', Message(), io.BytesIO(b'error code: 1010'))
            with patch('stoletnika.http.urllib.request.build_opener', return_value=opener):
                fetcher = Fetcher(cache=pathlib.Path(folder) / 'cache', delay=0,
                                  diagnostics=pathlib.Path(folder) / 'network.json')
                with self.assertRaisesRegex(DownloadError, '403'):
                    fetcher.get(PRODUCT)
                with self.assertRaisesRegex(DownloadError, 'no further'):
                    fetcher.get(SCOPES[0])
            self.assertEqual(opener.open.call_count, 1)
            self.assertEqual((pathlib.Path(folder) / 'blocked_url.txt').read_text(), PRODUCT)
            self.assertEqual(json.loads((pathlib.Path(folder) / 'network.json').read_text())[0]['status'], 403)

    def test_redirect_cannot_leave_catalog(self):
        with self.assertRaisesRegex(DownloadError, 'Redirect outside'):
            CatalogRedirectHandler().redirect_request(Mock(), None, 302, 'Found', {}, 'https://stoletnika.eu/login')

    def test_temporary_error_retries_same_http_request(self):
        with tempfile.TemporaryDirectory() as folder:
            opener = Mock()
            opener.open.side_effect = [Response('Unavailable', 503), Response(HTML)]
            with patch('stoletnika.http.urllib.request.build_opener', return_value=opener), patch('stoletnika.http.time.sleep'):
                fetcher = Fetcher(cache=folder, delay=0, diagnostics=None)
                self.assertEqual(fetcher.get(PRODUCT), HTML)
            self.assertEqual([x['status'] for x in fetcher.events], [503, 200])


if __name__ == '__main__':
    unittest.main()
