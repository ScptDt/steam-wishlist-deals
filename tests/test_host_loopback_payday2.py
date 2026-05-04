from __future__ import annotations

import unittest

import payday2_web
from shared_web_infra import LOCAL_CSRF_HEADER


def _make_handler(path: str, host: str | None = "127.0.0.1:8765"):
    handler = payday2_web.Handler.__new__(payday2_web.Handler)
    handler.path = path
    handler.headers = {}
    if host is not None:
        handler.headers["Host"] = host
    handler.server = type("FakeServer", (), {"server_port": 8765})()
    handler.status = None
    handler.json = None
    handler.html = None
    handler.text = None
    handler.calls = []

    def fake_json(data, status=200):
        handler.status = status
        handler.json = data

    def fake_html(html):
        handler.status = 200
        handler.html = html

    def fake_css(css):
        handler.status = 200
        handler.text = css

    def fake_js(script):
        handler.status = 200
        handler.text = script

    def fake_svg(svg):
        handler.status = 200
        handler.text = svg

    handler._json = fake_json
    handler._html = fake_html
    handler._css = fake_css
    handler._js = fake_js
    handler._svg = fake_svg
    return handler


class Payday2HostLoopbackTests(unittest.TestCase):
    def test_get_rejects_invalid_host_before_route_side_effects(self) -> None:
        for host in (None, "", "evil.example:8765", "192.168.1.9:8765", "0.0.0.0:8765", "127.0.0.1:9999"):
            with self.subTest(host=host):
                handler = _make_handler("/api/data", host)

                payday2_web.Handler.do_GET(handler)

                self.assertEqual(handler.status, 403)
                self.assertEqual(handler.json["error"], "forbidden_host")
                if host:
                    self.assertNotIn(str(host), str(handler.json))

    def test_post_rejects_invalid_host_before_csrf_and_side_effects(self) -> None:
        original_token = payday2_web.LOCAL_SESSION_TOKEN
        payday2_web.LOCAL_SESSION_TOKEN = "EXPECTED-PD2-TOKEN"
        try:
            handler = _make_handler("/api/refresh", "evil.example:8765")
            handler.headers[LOCAL_CSRF_HEADER] = "EXPECTED-PD2-TOKEN"
            handler._serve_refresh = lambda: handler.calls.append("refresh")

            payday2_web.Handler.do_POST(handler)
        finally:
            payday2_web.LOCAL_SESSION_TOKEN = original_token

        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.json["error"], "forbidden_host")
        self.assertEqual(handler.calls, [])
        self.assertNotIn("EXPECTED-PD2-TOKEN", str(handler.json))

    def test_get_accepts_loopback_hosts_for_safe_config_route(self) -> None:
        original_load_user_config = payday2_web.pd2.load_user_config
        payday2_web.pd2.load_user_config = lambda: {"vanity": "wolf", "key": "SECRET"}
        try:
            for host in ("localhost:8765", "127.0.0.1:8765", "[::1]:8765"):
                with self.subTest(host=host):
                    handler = _make_handler("/api/config", host)

                    payday2_web.Handler.do_GET(handler)

                    self.assertEqual(handler.status, 200)
                    self.assertEqual(handler.json["vanity"], "wolf")
                    self.assertNotIn("SECRET", str(handler.json))
        finally:
            payday2_web.pd2.load_user_config = original_load_user_config

    def test_valid_host_preserves_root_data_and_asset_routes(self) -> None:
        root_handler = _make_handler("/", "localhost:8765")
        payday2_web.Handler.do_GET(root_handler)
        self.assertEqual(root_handler.status, 200)
        self.assertIn("steam-tools-local-token", root_handler.html)

        data_handler = _make_handler("/api/data", "localhost:8765")
        payday2_web.Handler.do_GET(data_handler)
        self.assertEqual(data_handler.status, 200)
        self.assertIsInstance(data_handler.json, dict)

        js_handler = _make_handler("/app.js", "localhost:8765")
        payday2_web.Handler.do_GET(js_handler)
        self.assertEqual(js_handler.status, 200)
        self.assertIn("localMutableFetch", js_handler.text)

        mask_handler = _make_handler("/masks/heist_mask_blue.svg", "localhost:8765")
        payday2_web.Handler.do_GET(mask_handler)
        self.assertEqual(mask_handler.status, 200)
        self.assertIn("<svg", mask_handler.text)

    def test_valid_host_and_csrf_preserve_mutable_post_dispatch(self) -> None:
        original_token = payday2_web.LOCAL_SESSION_TOKEN
        payday2_web.LOCAL_SESSION_TOKEN = "EXPECTED-PD2-TOKEN"
        try:
            handler = _make_handler("/api/refresh", "localhost:8765")
            handler.headers[LOCAL_CSRF_HEADER] = "EXPECTED-PD2-TOKEN"
            handler._serve_refresh = lambda: handler.calls.append("refresh")

            payday2_web.Handler.do_POST(handler)
        finally:
            payday2_web.LOCAL_SESSION_TOKEN = original_token

        self.assertEqual(handler.calls, ["refresh"])


if __name__ == "__main__":
    unittest.main()
