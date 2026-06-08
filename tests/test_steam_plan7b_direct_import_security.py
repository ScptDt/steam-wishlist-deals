from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

import steam_deals_web
from shared_web_infra import LOCAL_CSRF_HEADER


PAIRING_START_PATH = "/api/steam-access/pairing/start"
PAIRING_REVOKE_PATH = "/api/steam-access/pairing/revoke"
PAIR_PATH = "/api/steam-access/pair"
IMPORT_PATH = "/api/steam-access/import"
EXTENSION_ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
EVIL_ORIGIN = "https://evil.example"
HOST = "127.0.0.1:8765"
SERVER_PORT = 8765


def _make_handler(
    path: str,
    *,
    host: str | None = HOST,
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    raw_body: bytes | None = None,
    content_type: str = "application/json",
):
    payload = raw_body if raw_body is not None else (json.dumps(body).encode("utf-8") if body is not None else b"")
    request_headers = dict(headers or {})
    if host is not None:
        request_headers.setdefault("Host", host)
    if payload or content_type:
        request_headers.setdefault("Content-Type", content_type)
    request_headers.setdefault("Content-Length", str(len(payload)))

    handler = steam_deals_web.Handler.__new__(steam_deals_web.Handler)
    handler.path = path
    handler.headers = request_headers
    handler.rfile = io.BytesIO(payload)
    handler.wfile = io.BytesIO()
    handler.server = type("FakeServer", (), {"server_port": SERVER_PORT})()
    handler.status = None
    handler.response_headers = []

    handler.send_response = lambda status: setattr(handler, "status", status)
    handler.send_header = lambda name, value: handler.response_headers.append((name, value))
    handler.end_headers = lambda: None
    handler.send_error = lambda status: setattr(handler, "status", status)
    return handler


def _response_json(handler) -> dict:
    body = handler.wfile.getvalue().decode("utf-8")
    return json.loads(body) if body else {}


def _headers(handler) -> dict[str, str]:
    return {name: value for name, value in handler.response_headers}


def _reset_plan7b_state() -> None:
    reset = getattr(steam_deals_web, "reset_steam_access_direct_import_state_for_tests", None)
    if callable(reset):
        reset()


def _valid_import_payload() -> dict:
    return {
        "schema": "steam_access_import_v1",
        "source": "steam_browser_helper_export",
        "generated_at": "2026-06-04T12:00:00Z",
        "provenance": "browser_helper_manual_export",
        "owned_appids": ["10", "20"],
        "family_shared_appids": ["30"],
        "wishlist_appids": [],
        "advisory_only": True,
        "ranking_impact": "none",
    }


def _start_pairing() -> str:
    original_token = steam_deals_web.LOCAL_SESSION_TOKEN
    steam_deals_web.LOCAL_SESSION_TOKEN = "LOCAL-UI-TOKEN"
    try:
        handler = _make_handler(
            PAIRING_START_PATH,
            headers={LOCAL_CSRF_HEADER: "LOCAL-UI-TOKEN"},
            body={},
        )
        steam_deals_web.Handler.do_POST(handler)
    finally:
        steam_deals_web.LOCAL_SESSION_TOKEN = original_token
    return _response_json(handler)["pairing_token"]


def _pair_extension(pairing_token: str, origin: str = EXTENSION_ORIGIN) -> str:
    handler = _make_handler(
        PAIR_PATH,
        headers={"Origin": origin, "X-Pairing-Token": pairing_token},
        body={"pairing_token": pairing_token},
    )
    steam_deals_web.Handler.do_POST(handler)
    return _response_json(handler)["session_token"]


class SteamPlan7BDirectImportSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_plan7b_state()

    def tearDown(self) -> None:
        _reset_plan7b_state()

    def test_pairing_routes_are_local_csrf_protected_without_exposing_token(self) -> None:
        self.assertIn(PAIRING_START_PATH, steam_deals_web.PROTECTED_POST_PATHS)
        self.assertIn(PAIRING_REVOKE_PATH, steam_deals_web.PROTECTED_POST_PATHS)
        original_token = steam_deals_web.LOCAL_SESSION_TOKEN
        steam_deals_web.LOCAL_SESSION_TOKEN = "LOCAL-UI-TOKEN"
        try:
            handler = _make_handler(PAIRING_START_PATH, body={})
            steam_deals_web.Handler.do_POST(handler)
        finally:
            steam_deals_web.LOCAL_SESSION_TOKEN = original_token
        self.assertEqual(handler.status, 403)
        self.assertNotIn("LOCAL-UI-TOKEN", handler.wfile.getvalue().decode("utf-8"))

    def test_import_rejects_invalid_host_before_auth_or_body_processing(self) -> None:
        handler = _make_handler(
            IMPORT_PATH,
            host="evil.example:8765",
            headers={"Origin": EXTENSION_ORIGIN, "Authorization": "Bearer SECRET-SESSION"},
            body={"raw_response": "SECRET-RAW"},
        )
        steam_deals_web.Handler.do_POST(handler)
        response = handler.wfile.getvalue().decode("utf-8")
        self.assertEqual(handler.status, 403)
        self.assertNotIn("SECRET-SESSION", response)
        self.assertNotIn("SECRET-RAW", response)

    def test_pairing_rejects_missing_or_unapproved_origin_safely(self) -> None:
        for origin in (None, "", EVIL_ORIGIN, "null"):
            with self.subTest(origin=origin):
                pairing_token = _start_pairing()
                headers = {"X-Pairing-Token": pairing_token}
                if origin is not None:
                    headers["Origin"] = origin
                handler = _make_handler(PAIR_PATH, headers=headers, body={"pairing_token": pairing_token})
                steam_deals_web.Handler.do_POST(handler)
                self.assertEqual(handler.status, 403)
                self.assertNotIn(pairing_token, handler.wfile.getvalue().decode("utf-8"))

    def test_pairing_requires_header_token_and_rejects_body_mismatch(self) -> None:
        pairing_token = _start_pairing()
        body_only = _make_handler(
            PAIR_PATH,
            headers={"Origin": EXTENSION_ORIGIN},
            body={"pairing_token": pairing_token},
        )
        steam_deals_web.Handler.do_POST(body_only)
        self.assertEqual(body_only.status, 401)
        self.assertNotIn(pairing_token, body_only.wfile.getvalue().decode("utf-8"))

        mismatch = _make_handler(
            PAIR_PATH,
            headers={"Origin": EXTENSION_ORIGIN, "X-Pairing-Token": pairing_token},
            body={"pairing_token": "DIFFERENT-PAIRING-TOKEN"},
        )
        steam_deals_web.Handler.do_POST(mismatch)
        serialized = mismatch.wfile.getvalue().decode("utf-8")
        self.assertEqual(mismatch.status, 401)
        self.assertNotIn(pairing_token, serialized)
        self.assertNotIn("DIFFERENT-PAIRING-TOKEN", serialized)

    def test_preflight_allows_only_extension_origin_expected_method_and_headers(self) -> None:
        _start_pairing()
        handler = _make_handler(
            PAIR_PATH,
            headers={
                "Origin": EXTENSION_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, X-Pairing-Token",
            },
        )
        steam_deals_web.Handler.do_OPTIONS(handler)
        headers = _headers(handler)
        self.assertIn(handler.status, {200, 204})
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), EXTENSION_ORIGIN)
        self.assertIn("Origin", headers.get("Vary", ""))
        self.assertNotEqual(headers.get("Access-Control-Allow-Origin"), "*")

        session_token = _pair_extension(_start_pairing())
        import_preflight = _make_handler(
            IMPORT_PATH,
            headers={
                "Origin": EXTENSION_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization",
            },
        )
        steam_deals_web.Handler.do_OPTIONS(import_preflight)
        import_headers = _headers(import_preflight)
        self.assertIn(import_preflight.status, {200, 204})
        self.assertEqual(import_headers.get("Access-Control-Allow-Origin"), EXTENSION_ORIGIN)
        self.assertNotIn(session_token, json.dumps(import_headers))

        evil = _make_handler(
            IMPORT_PATH,
            headers={
                "Origin": EVIL_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization",
            },
        )
        steam_deals_web.Handler.do_OPTIONS(evil)
        self.assertEqual(evil.status, 403)
        self.assertNotEqual(_headers(evil).get("Access-Control-Allow-Origin"), "*")

    def test_import_routes_reject_get_and_unsafe_mutation_methods(self) -> None:
        for method_name in ("do_GET", "do_PUT", "do_PATCH", "do_DELETE"):
            with self.subTest(method_name=method_name):
                handler = _make_handler(
                    IMPORT_PATH,
                    headers={"Origin": EXTENSION_ORIGIN},
                    body=None,
                )
                getattr(steam_deals_web.Handler, method_name)(handler)
                self.assertEqual(handler.status, 405)
                self.assertNotEqual(_headers(handler).get("Access-Control-Allow-Origin"), "*")

    def test_import_rejects_missing_invalid_revoked_or_expired_session_tokens(self) -> None:
        session_token = _pair_extension(_start_pairing())
        for auth_header in (None, "", "Bearer WRONG", f"Basic {session_token}"):
            with self.subTest(auth_header=auth_header):
                headers = {"Origin": EXTENSION_ORIGIN}
                if auth_header is not None:
                    headers["Authorization"] = auth_header
                handler = _make_handler(IMPORT_PATH, headers=headers, body=_valid_import_payload())
                steam_deals_web.Handler.do_POST(handler)
                response = handler.wfile.getvalue().decode("utf-8")
                self.assertEqual(handler.status, 401)
                self.assertNotIn(session_token, response)
                self.assertNotIn("WRONG", response)

        steam_deals_web.revoke_steam_access_direct_import_sessions_for_tests()
        handler = _make_handler(
            IMPORT_PATH,
            headers={"Origin": EXTENSION_ORIGIN, "Authorization": f"Bearer {session_token}"},
            body=_valid_import_payload(),
        )
        steam_deals_web.Handler.do_POST(handler)
        self.assertEqual(handler.status, 401)

    def test_pairing_and_import_reject_cookie_auth_even_with_valid_tokens(self) -> None:
        pairing_token = _start_pairing()
        pair = _make_handler(
            PAIR_PATH,
            headers={
                "Origin": EXTENSION_ORIGIN,
                "X-Pairing-Token": pairing_token,
                "Cookie": "local_session=SECRET",
            },
            body={"pairing_token": pairing_token},
        )
        steam_deals_web.Handler.do_POST(pair)
        self.assertEqual(pair.status, 401)

        session_token = _pair_extension(_start_pairing())
        imp = _make_handler(
            IMPORT_PATH,
            headers={
                "Origin": EXTENSION_ORIGIN,
                "Authorization": f"Bearer {session_token}",
                "Cookie": "local_session=SECRET",
            },
            body=_valid_import_payload(),
        )
        steam_deals_web.Handler.do_POST(imp)
        serialized = imp.wfile.getvalue().decode("utf-8")
        self.assertEqual(imp.status, 401)
        self.assertNotIn(session_token, serialized)
        self.assertNotIn("SECRET", serialized)

    def test_import_rejects_wrong_content_type_invalid_json_and_oversized_body(self) -> None:
        session_token = _pair_extension(_start_pairing())
        headers = {"Origin": EXTENSION_ORIGIN, "Authorization": f"Bearer {session_token}"}

        wrong_type = _make_handler(IMPORT_PATH, headers=headers, body=_valid_import_payload(), content_type="text/plain")
        steam_deals_web.Handler.do_POST(wrong_type)
        self.assertEqual(wrong_type.status, 415)

        invalid_json = _make_handler(IMPORT_PATH, headers=headers, raw_body=b"{not json")
        steam_deals_web.Handler.do_POST(invalid_json)
        self.assertEqual(invalid_json.status, 400)

        oversized = _make_handler(IMPORT_PATH, headers=headers, raw_body=b"{}")
        oversized.headers["Content-Length"] = str(steam_deals_web.STEAM_ACCESS_DIRECT_IMPORT_MAX_BODY_BYTES + 1)
        steam_deals_web.Handler.do_POST(oversized)
        self.assertEqual(oversized.status, 413)

    def test_invalid_schema_sensitive_keys_and_behavior_keys_do_not_save(self) -> None:
        session_token = _pair_extension(_start_pairing())
        saved_configs: list[dict] = []
        writes: list[dict] = []
        original_load_config = steam_deals_web.load_config
        original_save_config = steam_deals_web.save_config
        original_write_import = steam_deals_web.write_steam_access_direct_import
        steam_deals_web.load_config = lambda: {"vanity": "gaben"}
        steam_deals_web.save_config = lambda cfg: saved_configs.append(dict(cfg))
        steam_deals_web.write_steam_access_direct_import = lambda contract: writes.append(dict(contract)) or Path("/tmp/steam-access-direct-import.json")
        invalid_payloads = [
            {**_valid_import_payload(), "schema": "other_schema"},
            {**_valid_import_payload(), "raw_response": "SECRET-RAW"},
            {**_valid_import_payload(), "score": 999, "ranking": ["10"], "cache": {"ttl": 0}, "fetching": {"enabled": True}},
            {**_valid_import_payload(), "advisory_only": False},
            {**_valid_import_payload(), "ranking_impact": "score"},
        ]
        try:
            for payload in invalid_payloads:
                with self.subTest(payload_keys=sorted(payload)):
                    handler = _make_handler(
                        IMPORT_PATH,
                        headers={"Origin": EXTENSION_ORIGIN, "Authorization": f"Bearer {session_token}"},
                        body=payload,
                    )
                    steam_deals_web.Handler.do_POST(handler)
                    serialized = handler.wfile.getvalue().decode("utf-8")
                    self.assertEqual(handler.status, 400)
                    self.assertNotIn("SECRET-RAW", serialized)
        finally:
            steam_deals_web.load_config = original_load_config
            steam_deals_web.save_config = original_save_config
            steam_deals_web.write_steam_access_direct_import = original_write_import

        self.assertEqual(saved_configs, [])
        self.assertEqual(writes, [])

    def test_valid_import_returns_summary_only_and_updates_existing_import_config(self) -> None:
        session_token = _pair_extension(_start_pairing())
        saved_configs: list[dict] = []
        original_load_config = steam_deals_web.load_config
        original_save_config = steam_deals_web.save_config
        original_write_import = steam_deals_web.write_steam_access_direct_import
        steam_deals_web.load_config = lambda: {"vanity": "gaben", "key": "STEAM-SECRET"}
        steam_deals_web.save_config = lambda cfg: saved_configs.append(dict(cfg))
        steam_deals_web.write_steam_access_direct_import = lambda _contract: Path("/tmp/steam-access-direct-import.json")
        try:
            handler = _make_handler(
                IMPORT_PATH,
                headers={"Origin": EXTENSION_ORIGIN, "Authorization": f"Bearer {session_token}"},
                body=_valid_import_payload(),
            )
            steam_deals_web.Handler.do_POST(handler)
        finally:
            steam_deals_web.load_config = original_load_config
            steam_deals_web.save_config = original_save_config
            steam_deals_web.write_steam_access_direct_import = original_write_import

        payload = _response_json(handler)
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(handler.status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["owned_count"], 2)
        self.assertEqual(payload["summary"]["family_shared_count"], 1)
        self.assertEqual(payload["summary"]["ranking_impact"], "none")
        self.assertNotIn("STEAM-SECRET", serialized)
        self.assertNotIn(session_token, serialized)
        self.assertNotIn("owned_appids", payload)
        self.assertNotIn("family_shared_appids", payload)
        self.assertNotIn("wishlist_appids", payload)
        self.assertIn("steam_access_json", saved_configs[-1])

    def test_import_rate_limit_rejects_repeated_requests_without_extra_side_effects(self) -> None:
        session_token = _pair_extension(_start_pairing())
        statuses = []
        saved_configs: list[dict] = []
        original_load_config = steam_deals_web.load_config
        original_save_config = steam_deals_web.save_config
        original_write_import = steam_deals_web.write_steam_access_direct_import
        steam_deals_web.load_config = lambda: {"vanity": "gaben"}
        steam_deals_web.save_config = lambda cfg: saved_configs.append(dict(cfg))
        steam_deals_web.write_steam_access_direct_import = lambda _contract: Path("/tmp/steam-access-direct-import.json")
        try:
            for _ in range(steam_deals_web.STEAM_ACCESS_DIRECT_IMPORT_RATE_LIMIT + 1):
                handler = _make_handler(
                    IMPORT_PATH,
                    headers={"Origin": EXTENSION_ORIGIN, "Authorization": f"Bearer {session_token}"},
                    body=_valid_import_payload(),
                )
                steam_deals_web.Handler.do_POST(handler)
                statuses.append(handler.status)
        finally:
            steam_deals_web.load_config = original_load_config
            steam_deals_web.save_config = original_save_config
            steam_deals_web.write_steam_access_direct_import = original_write_import
        self.assertIn(429, statuses)
        self.assertLessEqual(len(saved_configs), steam_deals_web.STEAM_ACCESS_DIRECT_IMPORT_RATE_LIMIT)


if __name__ == "__main__":
    unittest.main()
