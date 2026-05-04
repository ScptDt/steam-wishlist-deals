from __future__ import annotations

import unittest

import steam_deals_web
from shared_web_infra import LOCAL_CSRF_HEADER


def _make_handler(path: str, host: str | None = "127.0.0.1:8765"):
    handler = steam_deals_web.Handler.__new__(steam_deals_web.Handler)
    handler.path = path
    handler.headers = {}
    if host is not None:
        handler.headers["Host"] = host
    handler.server = type("FakeServer", (), {"server_port": 8765})()
    handler.status = None
    handler.json = None
    handler.html = None
    handler.calls = []

    def fake_send_json(data, status=200):
        handler.status = status
        handler.json = data

    def fake_send_html(html, status=200):
        handler.status = status
        handler.html = html

    handler._send_json = fake_send_json
    handler._send_html = fake_send_html
    return handler


class SteamDealsHostLoopbackTests(unittest.TestCase):
    def test_get_rejects_invalid_host_before_route_side_effects(self) -> None:
        for host in (None, "", "evil.example:8765", "192.168.1.9:8765", "0.0.0.0:8765", "127.0.0.1:9999"):
            with self.subTest(host=host):
                handler = _make_handler("/api/files", host)
                handler._serve_files_list = lambda: handler.calls.append("files")

                steam_deals_web.Handler.do_GET(handler)

                self.assertEqual(handler.status, 403)
                self.assertEqual(handler.json["error"], "forbidden_host")
                self.assertEqual(handler.calls, [])
                if host:
                    self.assertNotIn(str(host), str(handler.json))

    def test_post_rejects_invalid_host_before_csrf_and_side_effects(self) -> None:
        original_token = steam_deals_web.LOCAL_SESSION_TOKEN
        steam_deals_web.LOCAL_SESSION_TOKEN = "EXPECTED-TOKEN"
        try:
            handler = _make_handler("/api/config", "evil.example:8765")
            handler.headers[LOCAL_CSRF_HEADER] = "EXPECTED-TOKEN"
            handler._serve_config_save = lambda: handler.calls.append("config")

            steam_deals_web.Handler.do_POST(handler)
        finally:
            steam_deals_web.LOCAL_SESSION_TOKEN = original_token

        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.json["error"], "forbidden_host")
        self.assertEqual(handler.calls, [])
        self.assertNotIn("EXPECTED-TOKEN", str(handler.json))

    def test_get_accepts_loopback_hosts_for_safe_routes(self) -> None:
        original_load_config = steam_deals_web.load_config
        steam_deals_web.load_config = lambda: {"vanity": "gaben", "key": "SECRET"}
        try:
            for host in ("localhost:8765", "127.0.0.1:8765", "[::1]:8765"):
                with self.subTest(host=host):
                    handler = _make_handler("/api/config", host)

                    steam_deals_web.Handler.do_GET(handler)

                    self.assertEqual(handler.status, 200)
                    self.assertEqual(handler.json["vanity"], "gaben")
                    self.assertNotIn("SECRET", str(handler.json))
        finally:
            steam_deals_web.load_config = original_load_config

    def test_valid_host_preserves_root_files_and_generated_file_dispatch(self) -> None:
        root_handler = _make_handler("/", "localhost:8765")
        steam_deals_web.Handler.do_GET(root_handler)
        self.assertEqual(root_handler.status, 200)
        self.assertIn("steam-tools-local-token", root_handler.html)

        files_handler = _make_handler("/api/files", "localhost:8765")
        files_handler._serve_files_list = lambda: files_handler.calls.append("files")
        steam_deals_web.Handler.do_GET(files_handler)
        self.assertEqual(files_handler.calls, ["files"])

        file_handler = _make_handler("/files/report.html", "localhost:8765")
        file_handler._serve_file = lambda name: file_handler.calls.append(name)
        steam_deals_web.Handler.do_GET(file_handler)
        self.assertEqual(file_handler.calls, ["report.html"])

    def test_valid_host_and_csrf_preserve_mutable_post_dispatch(self) -> None:
        original_token = steam_deals_web.LOCAL_SESSION_TOKEN
        steam_deals_web.LOCAL_SESSION_TOKEN = "EXPECTED-TOKEN"
        try:
            handler = _make_handler("/api/config", "localhost:8765")
            handler.headers[LOCAL_CSRF_HEADER] = "EXPECTED-TOKEN"
            handler._serve_config_save = lambda: handler.calls.append("config")

            steam_deals_web.Handler.do_POST(handler)
        finally:
            steam_deals_web.LOCAL_SESSION_TOKEN = original_token

        self.assertEqual(handler.calls, ["config"])


if __name__ == "__main__":
    unittest.main()
