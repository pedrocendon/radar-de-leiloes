"""Security boundary checks using only temporary files and loopback servers."""
import http.client
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from collectors import Client, CollectError
from engine import safe_cell,connect_database
from friendly_ui import make_server,local_health


class LocalSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        root = Path(__file__).parent
        (base / 'config.json').write_bytes((root / 'config.example.json').read_bytes())
        (base / 'references.json').write_text('[]', encoding='utf-8')
        (base / 'ui').mkdir()
        (base / 'ui/index.html').write_text('<h1>Radar</h1>', encoding='utf-8')
        self.server = make_server(base)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.service.closed.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, method='GET', headers=None, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_api_requires_token_for_reads_and_writes(self):
        for path, method in [('/api/state', 'GET'), ('/api/excel', 'GET'), ('/api/close', 'POST')]:
            self.assertEqual(self.request(path, method)[0], 403)
        self.assertFalse(self.server.service.closed.is_set())

    def test_incorrect_token_is_rejected(self):
        self.assertEqual(self.request('/api/state', headers={'X-Radar-Token': 'invalid'})[0], 403)

    def test_foreign_origin_and_host_are_rejected(self):
        for extra in [{'Origin': 'https://untrusted.example'}, {'Host': 'untrusted.example'}]:
            headers = {'X-Radar-Token': self.server.token, **extra}
            self.assertEqual(self.request('/api/state', headers=headers)[0], 403)

    def test_static_page_security_headers(self):
        status, headers, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'Radar', body)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertIn("script-src 'self'", headers['Content-Security-Policy'])
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_files_outside_static_allowlist_are_not_served(self):
        for path in ['/config.json', '/data/sessao-interface.json', '/../config.json', '/%2e%2e/config.json']:
            self.assertEqual(self.request(path)[0], 404)

    def test_oversized_request_is_rejected_before_body_read(self):
        headers = {'X-Radar-Token': self.server.token, 'Content-Length': '1000001'}
        self.assertEqual(self.request('/api/import', 'POST', headers)[0], 413)

    def test_local_session_health_and_proxy_bypass(self):
        # A broken environment proxy must not see the local session token.
        with patch.dict(os.environ,{'http_proxy':'http://127.0.0.1:1','HTTP_PROXY':'http://127.0.0.1:1','no_proxy':'','NO_PROXY':''}):
            result=local_health(f'http://127.0.0.1:{self.server.server_port}/',self.server.token)
        self.assertEqual(result['base'],str(self.server.service.base))

    def test_local_session_rejects_ambiguous_urls_before_network(self):
        bad=['file:///etc/passwd','http://example.test/','http://localhost:1234/',
             'http://127.0.0.1:1234/elsewhere/','http://user@127.0.0.1:1234/',
             'http://127.0.0.1:1234/?next=','http://127.0.0.1:1234/#fragment',
             'http://127.0.0.1:0/','http://127.0.0.1:65536/','http://127.0.0.1:1234/\n']
        with patch('friendly_ui.urllib.request.build_opener') as opener:
            for url in bad:
                with self.subTest(url=url),self.assertRaises(ValueError):local_health(url,self.server.token)
            for token in ('short','a'*129,'a'*32+'\r\nHeader: injected',None):
                with self.subTest(token_type=type(token).__name__),self.assertRaises(ValueError):
                    local_health('http://127.0.0.1:1234/',token)
            opener.assert_not_called()


class DataSecurityTests(unittest.TestCase):
    def test_database_defensive_mode_blocks_schema_corruption(self):
        with closing(connect_database(':memory:')) as db:
            self.assertTrue(db.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE))
            self.assertFalse(db.getconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA))
            self.assertFalse(db.getconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION))
            db.execute('CREATE TABLE safe(value TEXT)')
            db.execute('PRAGMA writable_schema=ON')
            with self.assertRaises(sqlite3.DatabaseError):db.execute('DELETE FROM sqlite_master')
            hostile="'); DROP TABLE safe; --"
            db.execute('INSERT INTO safe VALUES(?)',(hostile,))
            self.assertEqual(db.execute('SELECT value FROM safe').fetchone()[0],hostile)

    def test_session_redirect_never_forwards_token(self):
        hits=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                hits.append(self.path)
                self.send_response(302);self.send_header('Location','/token-target');self.end_headers()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with self.assertRaises(urllib.error.HTTPError):
                local_health(f'http://127.0.0.1:{server.server_port}/','x'*43)
            self.assertEqual(hits,['/api/health'])
        finally:server.shutdown();server.server_close();thread.join()

    def test_session_response_size_is_bounded(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                raw=b' '*16385
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with self.assertRaisesRegex(ValueError,'muito grande'):
                local_health(f'http://127.0.0.1:{server.server_port}/','x'*43)
        finally:server.shutdown();server.server_close();thread.join()

    def test_csv_untrusted_formulas_are_neutralized(self):
        for text in ['=1+1', '+SUM(1)', '-1+2', '@SUM(1)', ' \t=HYPERLINK("https://example.test")', '\r\n=1+1']:
            self.assertTrue(safe_cell(text).startswith("'"))
        self.assertEqual(safe_cell('Apartamento'), 'Apartamento')
        self.assertEqual(safe_cell(123), 123)

    def test_collector_does_not_follow_redirects(self):
        hits = []

        class RedirectHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                hits.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/unexpected-target')
                self.end_headers()

        server = ThreadingHTTPServer(('127.0.0.1', 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(CollectError) as result:
                Client().raw(f'http://127.0.0.1:{server.server_port}/start')
            self.assertEqual(result.exception.status, 'redirecionado')
            self.assertEqual(hits, ['/start'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
