from __future__ import annotations

import io
import unittest

import payday2_dlc_tracker
import payday2_web
import steam_deals_web
from shared_web_infra import (
    CONFIG_SECRET_ENV_VARS,
    LOCAL_CSRF_HEADER,
    build_secret_subprocess_env,
    config_without_secrets,
    extract_secret_env,
    hydrate_config_secrets,
    merge_config_preserving_secrets,
    public_config,
)


class _FakeSteamConfigHandler:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.status = None
        self.json = None
        self.headers = []
        self.wfile = io.BytesIO()

    def _read_json_body(self):
        return self.body

    def _send_json(self, data, status=200):
        self.status = status
        self.json = data

    def _json(self, data, status=200):
        self.status = status
        self.json = data

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.headers.append((name, value))

    def end_headers(self):
        pass

    def body_text(self) -> str:
        return self.wfile.getvalue().decode("utf-8")


class _FakeStreamProcess:
    def __init__(self, lines: list[str]) -> None:
        self.stdout = iter(lines)
        self.returncode = 0

    def poll(self):
        return None

    def wait(self, timeout=None):
        self.returncode = 0
        return 0


def _make_steam_route_handler(path: str, headers: dict[str, str] | None = None):
    handler = steam_deals_web.Handler.__new__(steam_deals_web.Handler)
    handler.path = path
    handler.headers = {"Host": "127.0.0.1:8765", **(headers or {})}
    handler.server = type("FakeServer", (), {"server_port": 8765})()
    handler.status = None
    handler.json = None
    handler.calls = []

    def fake_send_json(data, status=200):
        handler.status = status
        handler.json = data

    handler._send_json = fake_send_json
    return handler


def _make_payday2_route_handler(path: str, headers: dict[str, str] | None = None):
    handler = payday2_web.Handler.__new__(payday2_web.Handler)
    handler.path = path
    handler.headers = {"Host": "127.0.0.1:8765", **(headers or {})}
    handler.server = type("FakeServer", (), {"server_port": 8765})()
    handler.status = None
    handler.json = None
    handler.calls = []

    def fake_json(data, status=200):
        handler.status = status
        handler.json = data

    handler._json = fake_json
    return handler


class ConfigSecretRedactionTests(unittest.TestCase):
    def test_public_config_exposes_presence_flags_without_raw_secrets(self) -> None:
        cfg = {
            "vanity": "gaben",
            "output_dir": "output",
            "key": "STEAM-SECRET",
            "itad_key": "ITAD-SECRET",
            "telegram_token": "TELEGRAM-SECRET",
            "discord_webhook": "DISCORD-SECRET",
        }

        result = public_config(cfg)

        self.assertEqual(result["vanity"], "gaben")
        self.assertEqual(result["output_dir"], "output")
        for secret in ("STEAM-SECRET", "ITAD-SECRET", "TELEGRAM-SECRET", "DISCORD-SECRET"):
            self.assertNotIn(secret, result.values())
        self.assertNotIn("key", result)
        self.assertNotIn("itad_key", result)
        self.assertNotIn("telegram_token", result)
        self.assertNotIn("discord_webhook", result)
        self.assertTrue(result["has_key"])
        self.assertTrue(result["has_itad_key"])
        self.assertTrue(result["has_telegram_token"])
        self.assertTrue(result["has_discord_webhook"])

    def test_public_config_flags_empty_secrets_as_absent(self) -> None:
        result = public_config({"key": "", "itad_key": "   ", "telegram_token": None})

        self.assertFalse(result["has_key"])
        self.assertFalse(result["has_itad_key"])
        self.assertFalse(result["has_telegram_token"])

    def test_merge_config_preserving_secrets_keeps_existing_blank_or_redacted(self) -> None:
        existing = {
            "vanity": "old-profile",
            "key": "OLD-STEAM",
            "itad_key": "OLD-ITAD",
            "telegram_token": "OLD-TELEGRAM",
            "discord_webhook": "OLD-DISCORD",
        }
        incoming = {
            "vanity": "new-profile",
            "key": "",
            "itad_key": None,
            "telegram_token": "********",
            "discord_webhook": "__redacted__",
            "has_key": False,
        }

        result = merge_config_preserving_secrets(existing, incoming)

        self.assertEqual(result["vanity"], "new-profile")
        self.assertEqual(result["key"], "OLD-STEAM")
        self.assertEqual(result["itad_key"], "OLD-ITAD")
        self.assertEqual(result["telegram_token"], "OLD-TELEGRAM")
        self.assertEqual(result["discord_webhook"], "OLD-DISCORD")
        self.assertNotIn("has_key", result)

    def test_merge_config_preserving_secrets_accepts_explicit_new_secret(self) -> None:
        result = merge_config_preserving_secrets(
            {"key": "OLD-STEAM", "vanity": "gaben"},
            {"key": "NEW-STEAM"},
        )

        self.assertEqual(result["key"], "NEW-STEAM")
        self.assertEqual(result["vanity"], "gaben")

    def test_hydrate_config_secrets_restores_saved_runtime_secrets(self) -> None:
        result = hydrate_config_secrets(
            {"vanity": "gaben", "key": "", "itad_key": "NEW-ITAD"},
            {"key": "SAVED-STEAM", "itad_key": "SAVED-ITAD"},
        )

        self.assertEqual(result["key"], "SAVED-STEAM")
        self.assertEqual(result["itad_key"], "NEW-ITAD")

    def test_steam_deals_public_config_response_keeps_defaults_and_redacts(self) -> None:
        result = steam_deals_web.build_public_config_response(
            {"vanity": "gaben", "key": "STEAM-SECRET", "discount": 50}
        )

        self.assertEqual(result["vanity"], "gaben")
        self.assertEqual(result["discount"], 50)
        self.assertIn("default_output_dir", result)
        self.assertEqual(result["default_output_dir"], "output")
        self.assertNotIn("/home/", str(result))
        self.assertTrue(result["has_key"])
        self.assertNotIn("STEAM-SECRET", result.values())
        self.assertNotIn("key", result)

    def test_steam_deals_html_injects_local_token_only_in_root_ui(self) -> None:
        original_token = steam_deals_web.LOCAL_SESSION_TOKEN
        steam_deals_web.LOCAL_SESSION_TOKEN = "LOCAL-UI-TOKEN"
        try:
            html = steam_deals_web.load_steam_deals_html()
            config_response = steam_deals_web.build_public_config_response(
                {"vanity": "gaben", "key": "STEAM-SECRET"}
            )
        finally:
            steam_deals_web.LOCAL_SESSION_TOKEN = original_token

        self.assertIn('meta name="steam-tools-local-token"', html)
        self.assertIn('content="LOCAL-UI-TOKEN"', html)
        self.assertNotIn("LOCAL-UI-TOKEN", str(config_response))

    def test_steam_deals_do_post_rejects_missing_local_token_before_side_effects(self) -> None:
        original_token = steam_deals_web.LOCAL_SESSION_TOKEN
        steam_deals_web.LOCAL_SESSION_TOKEN = "EXPECTED-TOKEN"
        handler = _make_steam_route_handler("/api/config")
        handler._serve_config_save = lambda: handler.calls.append("config")
        try:
            steam_deals_web.Handler.do_POST(handler)
        finally:
            steam_deals_web.LOCAL_SESSION_TOKEN = original_token

        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.json["error"], "forbidden")
        self.assertEqual(handler.calls, [])
        self.assertNotIn("EXPECTED-TOKEN", str(handler.json))

    def test_steam_deals_protects_all_mutable_post_routes(self) -> None:
        expected = {
            "/api/run",
            "/api/run-pd2",
            "/api/preflight",
            "/api/desktop-doctor",
            "/api/desktop-doctor/fix",
            "/api/cache/clear",
            "/api/stop",
            "/api/open-output-folder",
            "/api/config",
            "/api/watchlist",
            "/api/watchlist/delete",
            "/api/log/export",
        }

        self.assertLessEqual(expected, steam_deals_web.PROTECTED_POST_PATHS)

    def test_steam_deals_do_post_rejects_external_origin_with_valid_token(self) -> None:
        original_token = steam_deals_web.LOCAL_SESSION_TOKEN
        steam_deals_web.LOCAL_SESSION_TOKEN = "EXPECTED-TOKEN"
        handler = _make_steam_route_handler(
            "/api/config",
            {
                LOCAL_CSRF_HEADER: "EXPECTED-TOKEN",
                "Origin": "http://evil.example:8765",
            },
        )
        handler._serve_config_save = lambda: handler.calls.append("config")
        try:
            steam_deals_web.Handler.do_POST(handler)
        finally:
            steam_deals_web.LOCAL_SESSION_TOKEN = original_token

        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.calls, [])

    def test_steam_deals_do_post_allows_valid_token_without_origin_for_desktop(self) -> None:
        original_token = steam_deals_web.LOCAL_SESSION_TOKEN
        steam_deals_web.LOCAL_SESSION_TOKEN = "EXPECTED-TOKEN"
        handler = _make_steam_route_handler(
            "/api/config",
            {LOCAL_CSRF_HEADER: "EXPECTED-TOKEN"},
        )
        handler._serve_config_save = lambda: handler.calls.append("config")
        try:
            steam_deals_web.Handler.do_POST(handler)
        finally:
            steam_deals_web.LOCAL_SESSION_TOKEN = original_token

        self.assertIsNone(handler.status)
        self.assertEqual(handler.calls, ["config"])

    def test_steam_deals_get_config_does_not_require_or_expose_local_token(self) -> None:
        original_token = steam_deals_web.LOCAL_SESSION_TOKEN
        original_load_config = steam_deals_web.load_config
        steam_deals_web.LOCAL_SESSION_TOKEN = "EXPECTED-TOKEN"
        steam_deals_web.load_config = lambda: {"vanity": "gaben", "key": "STEAM-SECRET"}
        handler = _make_steam_route_handler("/api/config")
        try:
            steam_deals_web.Handler.do_GET(handler)
        finally:
            steam_deals_web.LOCAL_SESSION_TOKEN = original_token
            steam_deals_web.load_config = original_load_config

        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.json["vanity"], "gaben")
        self.assertNotIn("EXPECTED-TOKEN", str(handler.json))

    def test_payday2_public_config_response_redacts_secrets(self) -> None:
        result = payday2_web.build_public_config_response(
            {"vanity": "wolf", "key": "STEAM-SECRET", "itad_key": "ITAD-SECRET"}
        )

        self.assertEqual(result["vanity"], "wolf")
        self.assertTrue(result["has_key"])
        self.assertTrue(result["has_itad_key"])
        self.assertNotIn("STEAM-SECRET", result.values())
        self.assertNotIn("ITAD-SECRET", result.values())
        self.assertNotIn("key", result)
        self.assertNotIn("itad_key", result)

    def test_payday2_html_injects_local_token_only_in_root_ui(self) -> None:
        original_token = payday2_web.LOCAL_SESSION_TOKEN
        payday2_web.LOCAL_SESSION_TOKEN = "PD2-LOCAL-UI-TOKEN"
        try:
            html = payday2_web.load_payday2_html()
            config_response = payday2_web.build_public_config_response(
                {"vanity": "wolf", "key": "STEAM-SECRET"}
            )
        finally:
            payday2_web.LOCAL_SESSION_TOKEN = original_token

        self.assertIn('meta name="steam-tools-local-token"', html)
        self.assertIn('content="PD2-LOCAL-UI-TOKEN"', html)
        self.assertNotIn("PD2-LOCAL-UI-TOKEN", str(config_response))

    def test_payday2_do_post_rejects_missing_local_token_before_side_effects(self) -> None:
        original_token = payday2_web.LOCAL_SESSION_TOKEN
        payday2_web.LOCAL_SESSION_TOKEN = "EXPECTED-PD2-TOKEN"
        handler = _make_payday2_route_handler("/api/refresh")
        handler._serve_refresh = lambda: handler.calls.append("refresh")
        try:
            payday2_web.Handler.do_POST(handler)
        finally:
            payday2_web.LOCAL_SESSION_TOKEN = original_token

        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.json["error"], "forbidden")
        self.assertEqual(handler.calls, [])
        self.assertNotIn("EXPECTED-PD2-TOKEN", str(handler.json))

    def test_payday2_protects_all_mutable_post_routes(self) -> None:
        expected = {
            "/api/toggle",
            "/api/toggle-bundle",
            "/api/refresh",
            "/api/config",
        }

        self.assertLessEqual(expected, payday2_web.PROTECTED_POST_PATHS)

    def test_payday2_do_post_rejects_external_origin_with_valid_token(self) -> None:
        original_token = payday2_web.LOCAL_SESSION_TOKEN
        payday2_web.LOCAL_SESSION_TOKEN = "EXPECTED-PD2-TOKEN"
        handler = _make_payday2_route_handler(
            "/api/refresh",
            {
                LOCAL_CSRF_HEADER: "EXPECTED-PD2-TOKEN",
                "Origin": "http://evil.example:8765",
            },
        )
        handler._serve_refresh = lambda: handler.calls.append("refresh")
        try:
            payday2_web.Handler.do_POST(handler)
        finally:
            payday2_web.LOCAL_SESSION_TOKEN = original_token

        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.calls, [])

    def test_payday2_do_post_allows_valid_token_without_origin_for_desktop(self) -> None:
        original_token = payday2_web.LOCAL_SESSION_TOKEN
        payday2_web.LOCAL_SESSION_TOKEN = "EXPECTED-PD2-TOKEN"
        handler = _make_payday2_route_handler(
            "/api/refresh",
            {LOCAL_CSRF_HEADER: "EXPECTED-PD2-TOKEN"},
        )
        handler._serve_refresh = lambda: handler.calls.append("refresh")
        try:
            payday2_web.Handler.do_POST(handler)
        finally:
            payday2_web.LOCAL_SESSION_TOKEN = original_token

        self.assertIsNone(handler.status)
        self.assertEqual(handler.calls, ["refresh"])

    def test_payday2_get_config_does_not_require_or_expose_local_token(self) -> None:
        original_token = payday2_web.LOCAL_SESSION_TOKEN
        original_load_user_config = payday2_web.pd2.load_user_config
        payday2_web.LOCAL_SESSION_TOKEN = "EXPECTED-PD2-TOKEN"
        payday2_web.pd2.load_user_config = lambda: {
            "vanity": "wolf",
            "key": "STEAM-SECRET",
        }
        handler = _make_payday2_route_handler("/api/config")
        try:
            payday2_web.Handler.do_GET(handler)
        finally:
            payday2_web.LOCAL_SESSION_TOKEN = original_token
            payday2_web.pd2.load_user_config = original_load_user_config

        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.json["vanity"], "wolf")
        self.assertNotIn("EXPECTED-PD2-TOKEN", str(handler.json))

    def test_steam_deals_config_save_preserves_existing_secrets(self) -> None:
        saved_configs: list[dict] = []
        original_load_config = steam_deals_web.load_config
        original_save_config = steam_deals_web.save_config
        steam_deals_web.load_config = lambda: {
            "vanity": "old-profile",
            "key": "OLD-STEAM",
            "itad_key": "OLD-ITAD",
        }
        steam_deals_web.save_config = lambda cfg: saved_configs.append(cfg)

        try:
            handler = _FakeSteamConfigHandler(
                {"vanity": "new-profile", "key": "", "itad_key": "********"}
            )
            steam_deals_web.Handler._serve_config_save(handler)
        finally:
            steam_deals_web.load_config = original_load_config
            steam_deals_web.save_config = original_save_config

        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.json, {"status": "saved"})
        self.assertEqual(saved_configs[0]["vanity"], "new-profile")
        self.assertEqual(saved_configs[0]["key"], "OLD-STEAM")
        self.assertEqual(saved_configs[0]["itad_key"], "OLD-ITAD")

    def test_extract_secret_env_maps_only_real_secret_values(self) -> None:
        result = extract_secret_env(
            {
                "key": "STEAM-SECRET",
                "itad_key": "ITAD-SECRET",
                "telegram_token": "",
                "discord_webhook": "__redacted__",
                "vanity": "gaben",
            }
        )

        self.assertEqual(result[CONFIG_SECRET_ENV_VARS["key"]], "STEAM-SECRET")
        self.assertEqual(result[CONFIG_SECRET_ENV_VARS["itad_key"]], "ITAD-SECRET")
        self.assertNotIn(CONFIG_SECRET_ENV_VARS["telegram_token"], result)
        self.assertNotIn(CONFIG_SECRET_ENV_VARS["discord_webhook"], result)

    def test_build_secret_subprocess_env_preserves_base_env_and_adds_secrets(self) -> None:
        result = build_secret_subprocess_env(
            {"key": "STEAM-SECRET"},
            base_env={"PATH": "/usr/bin", "KEEP": "1"},
        )

        self.assertEqual(result["PATH"], "/usr/bin")
        self.assertEqual(result["KEEP"], "1")
        self.assertEqual(result[CONFIG_SECRET_ENV_VARS["key"]], "STEAM-SECRET")

    def test_config_without_secrets_removes_sensitive_keys_only(self) -> None:
        result = config_without_secrets(
            {
                "vanity": "gaben",
                "key": "STEAM-SECRET",
                "telegram_chat": "123",
                "discord_webhook": "DISCORD-SECRET",
            }
        )

        self.assertEqual(result, {"vanity": "gaben", "telegram_chat": "123"})

    def test_steam_deals_runtime_command_moves_secrets_to_env(self) -> None:
        cmd, env = steam_deals_web.build_runtime_command_and_env(
            {
                "vanity": "gaben",
                "key": "STEAM-SECRET",
                "itad_key": "ITAD-SECRET",
                "telegram_token": "TELEGRAM-SECRET",
                "telegram_chat": "12345",
                "discord_webhook": "DISCORD-SECRET",
            },
            {},
        )
        command_text = " ".join(cmd)

        for secret in ("STEAM-SECRET", "ITAD-SECRET", "TELEGRAM-SECRET", "DISCORD-SECRET"):
            self.assertNotIn(secret, command_text)
        for flag in ("--key", "--itad-key", "--telegram-token", "--discord-webhook"):
            self.assertNotIn(flag, cmd)
        self.assertIn("--telegram-chat", cmd)
        self.assertEqual(env[CONFIG_SECRET_ENV_VARS["key"]], "STEAM-SECRET")
        self.assertEqual(env[CONFIG_SECRET_ENV_VARS["itad_key"]], "ITAD-SECRET")
        self.assertEqual(env[CONFIG_SECRET_ENV_VARS["telegram_token"]], "TELEGRAM-SECRET")
        self.assertEqual(env[CONFIG_SECRET_ENV_VARS["discord_webhook"]], "DISCORD-SECRET")

    def test_payday2_runtime_command_moves_secrets_to_env(self) -> None:
        cmd, env = payday2_web.build_refresh_command_and_env(
            {"vanity": "wolf", "key": "STEAM-SECRET", "itad_key": "ITAD-SECRET"}
        )
        command_text = " ".join(cmd)

        self.assertIn("--vanity", cmd)
        self.assertNotIn("STEAM-SECRET", command_text)
        self.assertNotIn("ITAD-SECRET", command_text)
        self.assertNotIn("--key", cmd)
        self.assertNotIn("--itad-key", cmd)
        self.assertEqual(env[CONFIG_SECRET_ENV_VARS["key"]], "STEAM-SECRET")
        self.assertEqual(env[CONFIG_SECRET_ENV_VARS["itad_key"]], "ITAD-SECRET")

    def test_payday2_config_resolves_env_before_saved_config(self) -> None:
        result = payday2_dlc_tracker.get_config(
            argv=[],
            environ={
                CONFIG_SECRET_ENV_VARS["key"]: "ENV-STEAM",
                CONFIG_SECRET_ENV_VARS["itad_key"]: "ENV-ITAD",
            },
            load_user_config_fn=lambda: {
                "key": "CONFIG-STEAM",
                "itad_key": "CONFIG-ITAD",
                "vanity": "wolf",
            },
        )

        self.assertEqual(result["key"], "ENV-STEAM")
        self.assertEqual(result["itad_key"], "ENV-ITAD")
        self.assertEqual(result["vanity"], "wolf")

    def test_payday2_config_keeps_cli_secret_priority_over_env(self) -> None:
        result = payday2_dlc_tracker.get_config(
            argv=["--key", "CLI-STEAM", "--itad-key", "CLI-ITAD"],
            environ={
                CONFIG_SECRET_ENV_VARS["key"]: "ENV-STEAM",
                CONFIG_SECRET_ENV_VARS["itad_key"]: "ENV-ITAD",
            },
            load_user_config_fn=lambda: {},
        )

        self.assertEqual(result["key"], "CLI-STEAM")
        self.assertEqual(result["itad_key"], "CLI-ITAD")

    def test_payday2_refresh_start_error_sanitizes_public_detail(self) -> None:
        original_load_user_config = payday2_web.pd2.load_user_config
        original_start_text_subprocess = payday2_web.start_text_subprocess
        secret_path = "/tmp/pd2-secret"
        secret_webhook = "https://discord.com/api/webhooks/2/secret"

        payday2_web.pd2.load_user_config = lambda: {"vanity": "wolf", "key": "SAVED-SECRET"}

        def fake_start_text_subprocess(_cmd, env=None):
            raise RuntimeError(f"Traceback failed at {secret_path} webhook={secret_webhook}")

        payday2_web.start_text_subprocess = fake_start_text_subprocess
        handler = _FakeSteamConfigHandler({})
        try:
            payday2_web.Handler._serve_refresh(handler)
        finally:
            payday2_web.pd2.load_user_config = original_load_user_config
            payday2_web.start_text_subprocess = original_start_text_subprocess

        payload = str(handler.json)
        self.assertEqual(handler.status, 500)
        self.assertEqual(handler.json["error"], "process_start_failed")
        self.assertEqual(handler.json["message"], "No se pudo iniciar proceso.")
        self.assertNotIn(secret_path, payload)
        self.assertNotIn("discord.com/api/webhooks", payload)
        self.assertNotIn("Traceback", payload)

    def test_payday2_refresh_runtime_sse_sanitizes_public_text(self) -> None:
        original_load_user_config = payday2_web.pd2.load_user_config
        original_start_text_subprocess = payday2_web.start_text_subprocess
        original_load_from_cache = payday2_web.load_from_cache
        original_refresh_proc = payday2_web._refresh_proc
        secret_path = "/etc/steamtools-secret.conf"
        secret_webhook = "https://discord.com/api/webhooks/2/secret"
        secret_token = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabc"

        payday2_web.pd2.load_user_config = lambda: {
            "vanity": "wolf",
            "key": "PD2-SAVED-SECRET",
        }
        payday2_web.load_from_cache = lambda: None
        payday2_web._refresh_proc = None

        def fake_start_text_subprocess(_cmd, env=None):
            return _FakeStreamProcess(
                [
                    "Bare PD2 secret PD2-SAVED-SECRET must be hidden\n",
                    f"Traceback failed at {secret_path} webhook={secret_webhook}\n",
                    f"[1/2] Leyendo token={secret_token} desde /private/tmp/pd2.log\n",
                ]
            )

        payday2_web.start_text_subprocess = fake_start_text_subprocess
        handler = _FakeSteamConfigHandler({})
        try:
            payday2_web.Handler._serve_refresh(handler)
        finally:
            payday2_web.pd2.load_user_config = original_load_user_config
            payday2_web.start_text_subprocess = original_start_text_subprocess
            payday2_web.load_from_cache = original_load_from_cache
            payday2_web._refresh_proc = original_refresh_proc

        payload = handler.body_text()
        self.assertNotIn("Traceback", payload)
        self.assertNotIn(secret_path, payload)
        self.assertNotIn("discord.com/api/webhooks", payload)
        self.assertNotIn(secret_token, payload)
        self.assertNotIn("PD2-SAVED-SECRET", payload)
        self.assertNotIn("/private/tmp/pd2.log", payload)
        self.assertIn("[ruta]", payload)


if __name__ == "__main__":
    unittest.main()
