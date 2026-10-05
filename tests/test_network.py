import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from stoletnika.network import DownloadError, Fetcher

CATALOG = '<html><div class="_products-list" data-product-id="1">' + 'x' * 600 + '</div></html>'
URL = 'https://stoletnika.eu/vendor/herbalkan'


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.fetcher = Fetcher(cache=root / 'cache', diagnostics=root / 'diagnostics.json', retries=1)

    def test_curl_reports_http_status_instead_of_exit_code(self):
        response = subprocess.CompletedProcess([], 0, b'Access denied\n__STOLETNIKA_HTTP_STATUS__:403', b'')
        with patch('stoletnika.network.subprocess.run', return_value=response):
            with self.assertRaises(DownloadError) as caught:
                self.fetcher._curl(URL)
        self.assertEqual(caught.exception.status, 403)
        self.assertIn('HTTP 403', str(caught.exception))

    def test_http_200_challenge_is_not_cached_as_catalog(self):
        self.fetcher._impersonated = Mock(return_value='<html>Checking your browser</html>' + 'x' * 600)
        self.fetcher._urllib = Mock(return_value=CATALOG)
        self.assertEqual(self.fetcher.get(URL), CATALOG)
        cached = next(self.fetcher.cache.glob('*.html')).read_text()
        self.assertEqual(cached, CATALOG)
        events = json.loads(self.fetcher.diagnostics.read_text())
        self.assertEqual(events[0]['status'], 200)
        self.assertIn('not the requested catalog', events[0]['error'])

    def test_http_refusals_use_browser_and_save_each_status(self):
        for name in ('_impersonated', '_urllib', '_curl'):
            setattr(self.fetcher, name, Mock(side_effect=DownloadError(name, 403, 'Forbidden')))
        self.fetcher._browser_get = Mock(return_value=CATALOG)
        self.assertEqual(self.fetcher.get(URL), CATALOG)
        self.fetcher._browser_get.assert_called_once_with(URL)
        events = json.loads(self.fetcher.diagnostics.read_text())
        self.assertEqual([event['status'] for event in events], [403, 403, 403])

    def test_refused_page_without_browser_returns_actionable_error(self):
        self.fetcher.browser_fallback = False
        for name in ('_impersonated', '_urllib', '_curl'):
            setattr(self.fetcher, name, Mock(side_effect=DownloadError(name, 429, 'Too many requests')))
        self.fetcher._browser_get = Mock()
        with self.assertRaisesRegex(RuntimeError, 'HTTP 429.*network_diagnostics.json'):
            self.fetcher.get(URL)
        self.fetcher._browser_get.assert_not_called()
        self.assertEqual(list(self.fetcher.cache.glob('*.html')), [])


if __name__ == '__main__':
    unittest.main()
