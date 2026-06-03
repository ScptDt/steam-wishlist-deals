from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.parse
from pathlib import Path
from tempfile import TemporaryDirectory

import steam_deals_web as web
from steam_deals_paths import OUTPUT_DIR_ENV_VAR
from steam_deals_web import (
    DEFAULT_OUTPUT_DIR,
    Handler,
    build_hltb_autodetect_public_suggestion,
    build_command,
    build_pd2_command,
    detect_file_path,
    find_hltb_csv_candidates,
    generated_file_error_page,
    generated_file_content_disposition,
    generated_file_content_type,
    generated_html_security_headers,
    is_allowed_generated_file_path,
    is_expected_generated_artifact_name,
    is_safe_generated_file_name,
    list_allowed_generated_files,
    open_output_folder,
    public_generated_file_name,
    resolve_output_dir,
    selection_review_context_from_report,
    selection_review_records_from_body,
)


class _FakeFileHandler:
    def __init__(self) -> None:
        self.status = None
        self.headers = []
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.headers.append((name, value))

    def end_headers(self):
        pass

    def header(self, name: str) -> str | None:
        for header_name, value in self.headers:
            if header_name.lower() == name.lower():
                return value
        return None

    def body_text(self) -> str:
        return self.wfile.getvalue().decode("utf-8")


class _FakeJsonHandler:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.status = None
        self.json = None

    def _read_json_body(self):
        return self.body

    def _send_json(self, data, status=200):
        self.status = status
        self.json = data

class _FakeRunHandler(_FakeJsonHandler):
    max_json_body_bytes = 64 * 1024

    def __init__(self, body: dict) -> None:
        super().__init__(body)
        self.headers = []
        self.wfile = io.BytesIO()

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


class GeneratedFilesServingTests(unittest.TestCase):
    def test_empty_output_resolves_to_project_output_folder(self) -> None:
        self.assertEqual(resolve_output_dir(None), DEFAULT_OUTPUT_DIR)
        self.assertEqual(resolve_output_dir(""), DEFAULT_OUTPUT_DIR)
        self.assertEqual(resolve_output_dir("custom-reports"), web.PROJECT_DIR / "custom-reports")

    def test_frozen_empty_output_resolves_to_persistent_user_output_folder(self) -> None:
        output_dir = resolve_output_dir(
            None,
            env={"HOME": "/home/tester"},
            frozen=True,
            project_dir=Path("/tmp/_MEI123"),
        )

        self.assertEqual(output_dir, Path("/home/tester/SteamTools/output"))

    def test_frozen_build_commands_use_persistent_output_override(self) -> None:
        original_output = os.environ.get(OUTPUT_DIR_ENV_VAR)
        had_frozen = hasattr(sys, "frozen")
        original_frozen = getattr(sys, "frozen", None)
        try:
            setattr(sys, "frozen", True)
            os.environ[OUTPUT_DIR_ENV_VAR] = "/var/tmp/steam-output"
            deals_cmd = build_command({"vanity": "gaben"}, {})
            pd2_cmd = build_pd2_command({"vanity": "gaben"}, {})
        finally:
            if original_output is None:
                os.environ.pop(OUTPUT_DIR_ENV_VAR, None)
            else:
                os.environ[OUTPUT_DIR_ENV_VAR] = original_output
            if had_frozen:
                setattr(sys, "frozen", original_frozen)
            elif hasattr(sys, "frozen"):
                delattr(sys, "frozen")

        self.assertEqual(Path(deals_cmd[deals_cmd.index("--output") + 1]), Path("/var/tmp/steam-output"))
        self.assertEqual(Path(pd2_cmd[pd2_cmd.index("--output") + 1]), Path("/var/tmp/steam-output"))

    def test_build_commands_always_pass_resolved_output_dir(self) -> None:
        deals_cmd = build_command({"vanity": "gaben"}, {})
        pd2_cmd = build_pd2_command({"vanity": "gaben"}, {})

        self.assertEqual(Path(deals_cmd[deals_cmd.index("--output") + 1]), DEFAULT_OUTPUT_DIR)
        self.assertEqual(Path(pd2_cmd[pd2_cmd.index("--output") + 1]), DEFAULT_OUTPUT_DIR)

    def test_build_command_warm_cache_reuses_cache_without_no_cache(self) -> None:
        cmd = build_command(
            {"vanity": "gaben"},
            {"warm_cache": True, "no_cache": True},
        )

        self.assertIn("--warm-cache", cmd)
        self.assertEqual(cmd.count("--warm-cache"), 1)
        self.assertNotIn("--no-cache", cmd)

    def test_build_command_full_warm_cache_reuses_cache_without_no_cache(self) -> None:
        cmd = build_command(
            {"vanity": "gaben"},
            {"warm_cache_full": True, "warm_cache_full_max_passes": 4, "no_cache": True},
        )

        self.assertIn("--warm-cache-full", cmd)
        self.assertNotIn("--warm-cache", cmd)
        self.assertEqual(cmd[cmd.index("--warm-cache-full-max-passes") + 1], "4")
        self.assertNotIn("--no-cache", cmd)

    def test_build_command_explicit_no_cache_still_requires_non_warm_cache_run(self) -> None:
        normal_cmd = build_command({"vanity": "gaben"}, {"no_cache": True})
        warm_cmd = build_command(
            {"vanity": "gaben"},
            {"warm_cache": True, "no_cache": True},
        )

        self.assertIn("--no-cache", normal_cmd)
        self.assertNotIn("--warm-cache", normal_cmd)
        self.assertIn("--warm-cache", warm_cmd)
        self.assertNotIn("--no-cache", warm_cmd)

    def test_build_command_passes_free_weekend_live_only_when_requested(self) -> None:
        default_cmd = build_command({"vanity": "gaben"}, {})
        opt_in_cmd = build_command({"vanity": "gaben"}, {"free_weekend_live": True})

        self.assertNotIn("--free-weekend-live", default_cmd)
        self.assertIn("--free-weekend-live", opt_in_cmd)
        self.assertEqual(opt_in_cmd.count("--free-weekend-live"), 1)

    def test_build_command_passes_itad_refresh_external_offers_only_when_requested(self) -> None:
        config = {
            "vanity": "gaben",
            "itad_external_offers_cache": "/tmp/itad-external-offers.json",
        }
        default_cmd = build_command(config, {})
        opt_in_cmd = build_command(
            config,
            {"itad_refresh_external_offers_cache": True},
        )

        self.assertNotIn("--itad-refresh-external-offers-cache", default_cmd)
        self.assertIn("--itad-refresh-external-offers-cache", opt_in_cmd)
        self.assertEqual(opt_in_cmd.count("--itad-refresh-external-offers-cache"), 1)

    def test_build_command_does_not_enable_itad_refresh_from_saved_config(self) -> None:
        config = {
            "vanity": "gaben",
            "itad_external_offers_cache": "/tmp/itad-external-offers.json",
            "itad_refresh_external_offers_cache": True,
        }

        cmd = build_command(config, {})

        self.assertNotIn("--itad-refresh-external-offers-cache", cmd)

    def test_build_command_passes_wishlist_external_matches_json(self) -> None:
        cmd = build_command(
            {
                "vanity": "gaben",
                "wishlist_external_matches_json": "/tmp/wishlist-external.json",
            },
            {},
        )

        self.assertIn("--wishlist-external-matches-json", cmd)
        self.assertEqual(
            cmd[cmd.index("--wishlist-external-matches-json") + 1],
            "/tmp/wishlist-external.json",
        )

    def test_build_command_passes_play_access_json(self) -> None:
        cmd = build_command(
            {
                "vanity": "gaben",
                "play_access_json": " /tmp/play-access.json ",
            },
            {},
        )

        self.assertIn("--play-access-json", cmd)
        self.assertEqual(
            cmd[cmd.index("--play-access-json") + 1],
            "/tmp/play-access.json",
        )

    def test_build_command_passes_steam_access_json(self) -> None:
        cmd = build_command(
            {
                "vanity": "gaben",
                "steam_access_json": " /tmp/steam-access.json ",
            },
            {},
        )

        self.assertIn("--steam-access-json", cmd)
        self.assertEqual(
            cmd[cmd.index("--steam-access-json") + 1],
            "/tmp/steam-access.json",
        )

    def test_build_command_passes_itad_external_offers_cache(self) -> None:
        cmd = build_command(
            {
                "vanity": "gaben",
                "itad_external_offers_cache": " /tmp/itad-external-offers.json ",
            },
            {},
        )

        self.assertIn("--itad-external-offers-cache", cmd)
        self.assertEqual(
            cmd[cmd.index("--itad-external-offers-cache") + 1],
            "/tmp/itad-external-offers.json",
        )

    def test_build_command_preserves_hltb_windows_paths_with_spaces(self) -> None:
        path_with_slashes = "C:/Users/Bryan Grijalva/Downloads/HLTB_Games_2026-05-15.csv"
        path_with_backslashes = r"C:\Users\Bryan Grijalva\Downloads\HLTB_Games_2026-05-15.csv"

        for hltb_path in (path_with_slashes, path_with_backslashes):
            cmd = build_command({"vanity": "gaben", "hltb": f'  "{hltb_path}"  '}, {})

            self.assertIn("--hltb", cmd)
            self.assertEqual(cmd[cmd.index("--hltb") + 1], hltb_path)
            self.assertEqual(cmd.count(hltb_path), 1)

    def test_find_hltb_csv_candidates_prefers_newest_matching_export(self) -> None:
        with TemporaryDirectory() as temp_dir:
            imports_dir = Path(temp_dir) / "Documents" / "SteamTools" / "imports"
            documents_dir = Path(temp_dir) / "Documents"
            downloads_dir = Path(temp_dir) / "Downloads"
            imports_dir.mkdir(parents=True)
            documents_dir.mkdir(exist_ok=True)
            downloads_dir.mkdir()
            old_export = imports_dir / "HLTB_Games_2026-05-14.csv"
            newest_export = downloads_dir / "HLTB_Games_2026-05-15.csv"
            ignored_lowercase = downloads_dir / "hltb_games_2026-05-16.csv"
            old_export.write_text("Title\nOld", encoding="utf-8")
            newest_export.write_text("Title\nNew", encoding="utf-8")
            ignored_lowercase.write_text("Title\nIgnored", encoding="utf-8")
            os.utime(old_export, (1_700_000_000, 1_700_000_000))
            os.utime(newest_export, (1_700_100_000, 1_700_100_000))
            os.utime(ignored_lowercase, (1_700_200_000, 1_700_200_000))

            candidates = find_hltb_csv_candidates(home=Path(temp_dir))

        self.assertEqual(candidates[0], newest_export)
        self.assertIn(old_export, candidates)
        self.assertNotIn(ignored_lowercase, candidates)

    def test_find_hltb_csv_candidates_uses_directory_priority_for_ties(self) -> None:
        with TemporaryDirectory() as temp_dir:
            imports_dir = Path(temp_dir) / "imports"
            documents_dir = Path(temp_dir) / "documents"
            downloads_dir = Path(temp_dir) / "downloads"
            for directory in (imports_dir, documents_dir, downloads_dir):
                directory.mkdir()
            imports_export = imports_dir / "HLTB_imports.csv"
            documents_export = documents_dir / "HLTB_documents.csv"
            downloads_export = downloads_dir / "HLTB_downloads.csv"
            for path in (imports_export, documents_export, downloads_export):
                path.write_text("Title\nGame", encoding="utf-8")
                os.utime(path, (1_700_000_000, 1_700_000_000))

            candidates = find_hltb_csv_candidates(
                search_dirs=[imports_dir, documents_dir, downloads_dir]
            )

        self.assertEqual(candidates[:3], [imports_export, documents_export, downloads_export])

    def test_hltb_autodetect_public_suggestion_redacts_path_and_requires_confirmation(self) -> None:
        private_path = Path("/private/home/user/Downloads/HLTB_Games_2026-05-15.csv")

        suggestion = build_hltb_autodetect_public_suggestion(private_path)

        self.assertIsNotNone(suggestion)
        payload = json.dumps(suggestion, ensure_ascii=False)
        self.assertIn("[ruta]", payload)
        self.assertIn("No se usará automáticamente", payload)
        self.assertTrue(suggestion["requires_confirmation"])
        self.assertNotIn(str(private_path), payload)
        self.assertNotIn("HLTB_Games_2026-05-15.csv", payload)

    def test_open_output_folder_creates_directory_and_uses_platform_opener(self) -> None:
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "reports"
            commands = []

            opened = open_output_folder(
                target,
                platform="linux",
                popen_fn=lambda command: commands.append(command),
            )

            self.assertEqual(opened, target)
            self.assertTrue(target.is_dir())
            self.assertEqual(commands, [["xdg-open", str(target)]])

    def test_open_output_folder_endpoint_uses_resolved_output_and_returns_json(self) -> None:
        original_open_output_folder = web.open_output_folder
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "reports"
            opened_paths = []

            def fake_open_output_folder(path):
                opened_paths.append(path)
                path.mkdir(parents=True, exist_ok=True)
                return path

            web.open_output_folder = fake_open_output_folder
            handler = _FakeJsonHandler({"config": {"output": str(target)}})
            try:
                Handler._serve_open_output_folder(handler)
            finally:
                web.open_output_folder = original_open_output_folder
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.json["status"], "opened")
        self.assertEqual(handler.json["path"], "[ruta]")
        self.assertEqual(handler.json["label"], "[ruta]")
        self.assertEqual(opened_paths, [target])

    def test_open_output_folder_error_sanitizes_public_detail(self) -> None:
        original_open_output_folder = web.open_output_folder
        original_output_dir = Handler.output_dir
        secret_path = "/tmp/private-folder"
        secret_token = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabc"

        def fake_open_output_folder(_path):
            raise RuntimeError(f"Traceback key={secret_token} failed at {secret_path} _MEIPASS")

        web.open_output_folder = fake_open_output_folder
        handler = _FakeJsonHandler({"config": {"output": secret_path}})
        try:
            Handler._serve_open_output_folder(handler)
        finally:
            web.open_output_folder = original_open_output_folder
            Handler.output_dir = original_output_dir

        payload = str(handler.json)
        self.assertEqual(handler.status, 500)
        self.assertEqual(handler.json["message"], "No se pudo abrir la carpeta de salida.")
        self.assertNotIn(secret_path, payload)
        self.assertNotIn(secret_token, payload)
        self.assertNotIn("Traceback", payload)
        self.assertNotIn("_MEIPASS", payload)

    def test_preflight_sanitizes_public_path_fields_and_messages(self) -> None:
        original_load_config = web.load_config
        hltb_path = "C:/Users/Bryan Grijalva/Downloads/HLTB_Games_2026-05-15.csv"
        family_path = "/private/tmp/steamtools-family-missing.json"
        wishlist_matches_path = "/private/tmp/wishlist-external-missing.json"
        play_access_path = "/private/tmp/play-access-missing.json"
        steam_access_path = "/private/tmp/steam-access-missing.json"
        itad_external_offers_cache_path = "/private/tmp/itad-external-offers-missing.json"
        output_path = "/srv/app/steamtools-output-secret"

        web.load_config = lambda: {"key": "SAVED-SECRET"}
        handler = _FakeJsonHandler(
            {
                "config": {
                    "vanity": "gaben",
                    "hltb": hltb_path,
                    "family_json": family_path,
                    "wishlist_external_matches_json": wishlist_matches_path,
                    "play_access_json": play_access_path,
                    "steam_access_json": steam_access_path,
                    "itad_external_offers_cache": itad_external_offers_cache_path,
                    "output": output_path,
                }
            }
        )
        try:
            Handler._serve_preflight(handler)
        finally:
            web.load_config = original_load_config

        payload = str(handler.json)
        self.assertEqual(handler.status, 200)
        self.assertNotIn(hltb_path, payload)
        self.assertNotIn("Bryan Grijalva", payload)
        self.assertNotIn("HLTB_Games_2026-05-15.csv", payload)
        self.assertNotIn(family_path, payload)
        self.assertNotIn(wishlist_matches_path, payload)
        self.assertNotIn(play_access_path, payload)
        self.assertNotIn(steam_access_path, payload)
        self.assertNotIn(itad_external_offers_cache_path, payload)
        self.assertNotIn(output_path, payload)
        self.assertIn("[ruta]", payload)
        self.assertIn("ruta completa sin comillas", payload)
        self.assertIn("JSON de matches externos wishlist", payload)
        self.assertIn("JSON local de play_access", payload)
        self.assertIn("JSON local Steam Access", payload)
        self.assertIn("caché ITAD external_offers local", payload)

    def test_preflight_reports_missing_play_access_json_redacted(self) -> None:
        original_load_config = web.load_config
        original_find_hltb_csv_candidates = web.find_hltb_csv_candidates
        play_access_path = "/private/tmp/play-access-missing.json"
        web.load_config = lambda: {}
        web.find_hltb_csv_candidates = lambda: []
        handler = _FakeJsonHandler(
            {
                "config": {
                    "vanity": "gaben",
                    "play_access_json": play_access_path,
                }
            }
        )
        try:
            Handler._serve_preflight(handler)
        finally:
            web.load_config = original_load_config
            web.find_hltb_csv_candidates = original_find_hltb_csv_candidates

        payload = str(handler.json)
        self.assertEqual(handler.status, 200)
        self.assertFalse(handler.json["ok"])
        self.assertNotIn(play_access_path, payload)
        self.assertIn("JSON local de play_access", payload)

    def test_preflight_reports_missing_steam_access_json_redacted(self) -> None:
        original_load_config = web.load_config
        original_find_hltb_csv_candidates = web.find_hltb_csv_candidates
        steam_access_path = "/private/tmp/steam-access-missing.json"
        web.load_config = lambda: {}
        web.find_hltb_csv_candidates = lambda: []
        handler = _FakeJsonHandler(
            {
                "config": {
                    "vanity": "gaben",
                    "steam_access_json": steam_access_path,
                }
            }
        )
        try:
            Handler._serve_preflight(handler)
        finally:
            web.load_config = original_load_config
            web.find_hltb_csv_candidates = original_find_hltb_csv_candidates

        payload = str(handler.json)
        self.assertEqual(handler.status, 200)
        self.assertFalse(handler.json["ok"])
        self.assertNotIn(steam_access_path, payload)
        self.assertIn("JSON local Steam Access", payload)
        self.assertIn("[ruta]", payload)

    def test_preflight_requires_itad_key_and_cache_path_for_itad_refresh(self) -> None:
        original_load_config = web.load_config
        web.load_config = lambda: {}
        handler = _FakeJsonHandler(
            {
                "config": {"vanity": "gaben"},
                "filters": {"itad_refresh_external_offers_cache": True},
            }
        )
        try:
            Handler._serve_preflight(handler)
        finally:
            web.load_config = original_load_config

        payload = str(handler.json)
        self.assertEqual(handler.status, 200)
        self.assertFalse(handler.json["ok"])
        self.assertIn("Refresh ITAD external_offers requiere ITAD API Key", payload)
        self.assertIn("Caché ITAD external_offers (JSON)", payload)

    def test_preflight_does_not_require_itad_key_when_itad_refresh_is_unchecked(self) -> None:
        original_load_config = web.load_config
        original_find_hltb_csv_candidates = web.find_hltb_csv_candidates
        web.load_config = lambda: {}
        web.find_hltb_csv_candidates = lambda: []
        handler = _FakeJsonHandler(
            {
                "config": {"vanity": "gaben"},
                "filters": {"itad_refresh_external_offers_cache": False},
            }
        )
        try:
            Handler._serve_preflight(handler)
        finally:
            web.load_config = original_load_config
            web.find_hltb_csv_candidates = original_find_hltb_csv_candidates

        payload = str(handler.json)
        self.assertEqual(handler.status, 200)
        self.assertTrue(handler.json["ok"])
        self.assertNotIn("ITAD API Key", payload)
        self.assertNotIn("Caché ITAD external_offers (JSON)", payload)

    def test_preflight_uses_saved_itad_key_for_redacted_refresh_config(self) -> None:
        original_load_config = web.load_config
        original_find_hltb_csv_candidates = web.find_hltb_csv_candidates
        web.load_config = lambda: {"itad_key": "SAVED-ITAD"}
        web.find_hltb_csv_candidates = lambda: []
        with TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "itad-external-offers.json"
            cache_path.write_text("{}", encoding="utf-8")
            handler = _FakeJsonHandler(
                {
                    "config": {
                        "vanity": "gaben",
                        "itad_key": "********",
                        "itad_external_offers_cache": str(cache_path),
                    },
                    "filters": {"itad_refresh_external_offers_cache": True},
                }
            )
            try:
                Handler._serve_preflight(handler)
            finally:
                web.load_config = original_load_config
                web.find_hltb_csv_candidates = original_find_hltb_csv_candidates

        payload = str(handler.json)
        self.assertEqual(handler.status, 200)
        self.assertTrue(handler.json["ok"])
        self.assertNotIn("SAVED-ITAD", payload)
        self.assertNotIn("requiere ITAD API Key", payload)
        self.assertNotIn("Caché ITAD external_offers (JSON)", payload)

    def test_preflight_allows_missing_itad_cache_target_when_refreshing(self) -> None:
        original_load_config = web.load_config
        cache_path = "/private/tmp/new-itad-external-offers.json"
        web.load_config = lambda: {"itad_key": "SAVED-ITAD"}
        handler = _FakeJsonHandler(
            {
                "config": {
                    "vanity": "gaben",
                    "itad_external_offers_cache": cache_path,
                },
                "filters": {"itad_refresh_external_offers_cache": True},
            }
        )
        try:
            Handler._serve_preflight(handler)
        finally:
            web.load_config = original_load_config

        payload = str(handler.json)
        self.assertEqual(handler.status, 200)
        self.assertTrue(handler.json["ok"])
        self.assertNotIn(cache_path, payload)
        self.assertIn("se creará o actualizará", payload)
        self.assertIn("[ruta]", payload)

    def test_preflight_suggests_redacted_hltb_autodetect_only_when_field_empty(self) -> None:
        original_find_hltb_csv_candidates = web.find_hltb_csv_candidates
        original_load_config = web.load_config
        detected_path = Path("/private/home/user/Downloads/HLTB_Games_2026-05-15.csv")
        calls = []

        def fake_find_hltb_csv_candidates():
            calls.append("called")
            return [detected_path]

        web.find_hltb_csv_candidates = fake_find_hltb_csv_candidates
        web.load_config = lambda: {"key": "SAVED-SECRET"}
        try:
            empty_handler = _FakeJsonHandler(
                {"config": {"vanity": "gaben", "hltb": ""}}
            )
            Handler._serve_preflight(empty_handler)

            with TemporaryDirectory() as temp_dir:
                existing_hltb = Path(temp_dir) / "HLTB_Games.csv"
                existing_hltb.write_text("Title\nGame", encoding="utf-8")
                filled_handler = _FakeJsonHandler(
                    {"config": {"vanity": "gaben", "hltb": str(existing_hltb)}}
                )
                Handler._serve_preflight(filled_handler)
        finally:
            web.find_hltb_csv_candidates = original_find_hltb_csv_candidates
            web.load_config = original_load_config

        payload = json.dumps(empty_handler.json, ensure_ascii=False)
        self.assertEqual(empty_handler.status, 200)
        self.assertEqual(calls, ["called"])
        self.assertIn("hltb_autodetect", empty_handler.json)
        self.assertIn("[ruta]", payload)
        self.assertIn("No se usará automáticamente", payload)
        self.assertNotIn(str(detected_path), payload)
        self.assertNotIn("HLTB_Games_2026-05-15.csv", payload)
        self.assertIsNone(filled_handler.json["hltb_autodetect"])

    def test_generated_file_content_type_matches_report_extensions(self) -> None:
        self.assertEqual(generated_file_content_type(".html"), "text/html")
        self.assertEqual(generated_file_content_type(".md"), "text/plain")
        self.assertEqual(generated_file_content_type(".csv"), "text/csv")
        self.assertEqual(generated_file_content_type(".json"), "application/json")
        self.assertEqual(generated_file_content_type(".bin"), "application/octet-stream")

    def test_generated_file_content_disposition_opens_html_and_downloads_data_files(self) -> None:
        html = generated_file_content_disposition("Steam Deals 2026-04-24.html", ".html")
        csv = generated_file_content_disposition("Steam Deals 2026-04-24.csv", ".csv")
        json = generated_file_content_disposition("Steam Deals 2026-04-24.json", ".json")

        self.assertTrue(html.startswith("inline;"))
        self.assertTrue(csv.startswith("attachment;"))
        self.assertTrue(json.startswith("attachment;"))
        self.assertIn("filename*=UTF-8''Steam%20Deals%202026-04-24.csv", csv)

    def test_generated_file_content_disposition_sanitizes_header_filename(self) -> None:
        disposition = generated_file_content_disposition('Steam Deals "sale".json', ".json")

        self.assertIn('filename="Steam Deals _sale_.json"', disposition)
        self.assertNotIn('filename="Steam Deals "sale".json"', disposition)

    def test_generated_html_security_headers_apply_only_to_html(self) -> None:
        html_headers = generated_html_security_headers(".html")

        self.assertIn("Content-Security-Policy", html_headers)
        self.assertIn("sandbox", html_headers["Content-Security-Policy"])
        self.assertIn("allow-scripts", html_headers["Content-Security-Policy"])
        self.assertIn("allow-popups", html_headers["Content-Security-Policy"])
        self.assertIn("allow-downloads", html_headers["Content-Security-Policy"])
        self.assertIn("connect-src 'none'", html_headers["Content-Security-Policy"])
        self.assertIn("form-action 'none'", html_headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", html_headers["Content-Security-Policy"])
        self.assertNotIn("allow-same-origin", html_headers["Content-Security-Policy"])
        self.assertEqual(html_headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(generated_html_security_headers(".json"), {})

    def test_generated_file_name_validation_blocks_path_traversal(self) -> None:
        self.assertTrue(is_safe_generated_file_name("Steam Deals 2026-04-24.html"))
        self.assertFalse(is_safe_generated_file_name("../secrets.json"))
        self.assertFalse(is_safe_generated_file_name("nested/report.html"))
        self.assertFalse(is_safe_generated_file_name("nested\\report.html"))
        self.assertFalse(is_safe_generated_file_name(""))

    def test_expected_generated_artifact_name_validation_uses_allowlist(self) -> None:
        self.assertTrue(is_expected_generated_artifact_name("Steam Deals 2026-04-24.html"))
        self.assertTrue(is_expected_generated_artifact_name("Steam Deals Now Available - Far Far West 2026-04-24.html"))
        self.assertTrue(is_expected_generated_artifact_name("Steam Deals Share 2026-04-24.html"))
        self.assertTrue(is_expected_generated_artifact_name("Steam Deals 2026-04-24.md"))
        self.assertTrue(is_expected_generated_artifact_name("Steam Deals 2026-04-24.json"))
        self.assertTrue(is_expected_generated_artifact_name("Steam Deals 2026-04-24.csv"))
        self.assertTrue(is_expected_generated_artifact_name("PAYDAY2_Plan_de_Compra.html"))
        self.assertTrue(is_expected_generated_artifact_name("PAYDAY2_Plan_de_Compra.md"))
        self.assertTrue(is_expected_generated_artifact_name("PAYDAY2_Plan_de_Compra.csv"))
        self.assertFalse(is_expected_generated_artifact_name("report.html"))
        self.assertFalse(is_expected_generated_artifact_name("Steam Deals secrets.json"))
        self.assertFalse(is_expected_generated_artifact_name("Steam Deals secrets 2026-04-24.json"))
        self.assertFalse(is_expected_generated_artifact_name("Steam Deals random.csv"))
        self.assertFalse(is_expected_generated_artifact_name("Steam Deals Share 2026-04-24.json"))
        self.assertFalse(is_expected_generated_artifact_name("Steam Deals 2026-04-24.backup.html"))
        self.assertFalse(is_expected_generated_artifact_name("PAYDAY2_Plan_de_Compra.json"))
        self.assertFalse(is_expected_generated_artifact_name("Steam Deals 2026-04-24.exe"))
        self.assertFalse(is_expected_generated_artifact_name("../Steam Deals 2026-04-24.html"))

    def test_public_generated_file_name_uses_safe_basename_for_links(self) -> None:
        self.assertEqual(
            public_generated_file_name(
                "/home/user/output/Steam Deals Now Available - Far Far West 2026-04-24.html"
            ),
            "Steam Deals Now Available - Far Far West 2026-04-24.html",
        )
        self.assertEqual(
            public_generated_file_name(
                r"C:\Users\tester\output\Steam Deals 2026-04-24.json"
            ),
            "Steam Deals 2026-04-24.json",
        )

    def test_public_generated_file_name_keeps_invalid_paths_redacted(self) -> None:
        public_name = public_generated_file_name("/home/user/secrets.json")

        self.assertNotIn("/home/user", public_name)
        self.assertNotEqual(public_name, "secrets.json")

    def test_detect_file_path_only_accepts_expected_generated_artifacts(self) -> None:
        self.assertEqual(
            detect_file_path("✓ /tmp/output/Steam Deals 2026-04-24.json"),
            "/tmp/output/Steam Deals 2026-04-24.json",
        )
        self.assertEqual(
            detect_file_path(r"OK C:\\Users\\tester\\output\\Steam Deals 2026-04-24.html"),
            r"C:\\Users\\tester\\output\\Steam Deals 2026-04-24.html",
        )
        self.assertIsNone(
            detect_file_path("Caché objetivo: /home/user/.cache/steam_deals/prices_cache.json")
        )
        self.assertIsNone(detect_file_path("✓ /home/user/.cache/steam_deals/prices_cache.json"))
        self.assertIsNone(detect_file_path("✓ /home/user/output/secrets.json"))

    def test_allowed_generated_file_path_rejects_directories_and_symlinks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            valid = output_dir / "Steam Deals 2026-04-24.html"
            valid.with_suffix(".md").write_text("md", encoding="utf-8")
            valid.with_suffix(".json").write_text("{}", encoding="utf-8")
            directory = output_dir / "Steam Deals Directory 2026-04-24.html"
            symlink = output_dir / "Steam Deals Link 2026-04-24.html"
            target = output_dir / "target.html"
            valid.write_text("ok", encoding="utf-8")
            directory.mkdir()
            target.write_text("secret", encoding="utf-8")

            self.assertTrue(is_allowed_generated_file_path(valid, output_dir))
            self.assertFalse(is_allowed_generated_file_path(directory, output_dir))
            try:
                symlink.symlink_to(target)
            except (NotImplementedError, OSError):
                self.skipTest("symlink creation is not available on this platform")
            self.assertFalse(is_allowed_generated_file_path(symlink, output_dir))

    def test_list_allowed_generated_files_filters_output_dir_contents(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            valid_html = output_dir / "Steam Deals 2026-04-24.html"
            valid_md = output_dir / "Steam Deals 2026-04-24.md"
            valid_json = output_dir / "Steam Deals 2026-04-24.json"
            valid_share = output_dir / "Steam Deals Share 2026-04-24.html"
            valid_pd2 = output_dir / "PAYDAY2_Plan_de_Compra.csv"
            invalid_basename = output_dir / "secrets.json"
            invalid_extension = output_dir / "Steam Deals 2026-04-24.exe"
            invalid_generated_looking = output_dir / "Steam Deals secrets.json"
            invalid_share_json = output_dir / "Steam Deals Share 2026-04-24.json"
            invalid_backup = output_dir / "Steam Deals 2026-04-24.backup.html"
            invalid_directory = output_dir / "Steam Deals Directory 2026-04-24.html"
            for path in (
                valid_html,
                valid_md,
                valid_json,
                valid_share,
                valid_pd2,
                invalid_basename,
                invalid_extension,
                invalid_generated_looking,
                invalid_share_json,
                invalid_backup,
            ):
                path.write_text(path.name, encoding="utf-8")
            invalid_directory.mkdir()

            result = {path.name for path in list_allowed_generated_files(output_dir)}

        self.assertEqual(
            result,
            {
                "Steam Deals 2026-04-24.html",
                "Steam Deals 2026-04-24.md",
                "Steam Deals 2026-04-24.json",
                "Steam Deals Share 2026-04-24.html",
                "PAYDAY2_Plan_de_Compra.csv",
            },
        )

    def test_generated_file_error_page_is_clear_and_escapes_content(self) -> None:
        page = generated_file_error_page(404, "Archivo <faltante>", "No usar <path>")

        self.assertIn("Error 404", page)
        self.assertIn("Archivo &lt;faltante&gt;", page)
        self.assertIn("No usar &lt;path&gt;", page)
        self.assertIn("Volver a Steam Tools", page)

    def test_serve_file_returns_clear_403_for_invalid_names(self) -> None:
        handler = _FakeFileHandler()

        Handler._serve_file(handler, urllib.parse.quote("../secrets.json", safe=""))

        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.header("Content-Type"), "text/html; charset=utf-8")
        self.assertEqual(handler.header("X-Content-Type-Options"), "nosniff")
        self.assertIn("Archivo no disponible", handler.body_text())

    def test_serve_file_returns_clear_404_for_missing_files(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            Handler.output_dir = temp_dir
            try:
                Handler._serve_file(
                    handler,
                    urllib.parse.quote("Steam Deals Missing 2026-04-24.html", safe=""),
                )
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 404)
        self.assertIn("Archivo no encontrado", handler.body_text())

    def test_serve_file_returns_clear_500_for_read_failures(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        original_read_bytes = Path.read_bytes
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "Steam Deals 2026-04-24.html"
            target.write_text("ok", encoding="utf-8")
            target.with_suffix(".md").write_text("md", encoding="utf-8")
            target.with_suffix(".json").write_text("{}", encoding="utf-8")
            Handler.output_dir = temp_dir
            Path.read_bytes = lambda _path: (_ for _ in ()).throw(OSError("boom"))
            try:
                Handler._serve_file(
                    handler,
                    urllib.parse.quote("Steam Deals 2026-04-24.html", safe=""),
                )
            finally:
                Path.read_bytes = original_read_bytes
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 500)
        self.assertIn("No se pudo leer el archivo", handler.body_text())

    def test_serve_file_error_page_sanitizes_sensitive_message(self) -> None:
        handler = _FakeFileHandler()

        web.send_generated_file_error(
            handler,
            500,
            "Fallo",
            "Traceback key=SECRET123 en /tmp/private _MEIPASS",
        )

        body = handler.body_text()
        self.assertNotIn("Traceback", body)
        self.assertNotIn("SECRET123", body)
        self.assertNotIn("/tmp/private", body)
        self.assertNotIn("_MEIPASS", body)

    def test_serve_file_keeps_successful_html_inline(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "Steam Deals 2026-04-24.html"
            target.write_text("<h1>OK</h1>", encoding="utf-8")
            target.with_suffix(".md").write_text("md", encoding="utf-8")
            target.with_suffix(".json").write_text("{}", encoding="utf-8")
            Handler.output_dir = temp_dir
            try:
                Handler._serve_file(
                    handler,
                    urllib.parse.quote("Steam Deals 2026-04-24.html", safe=""),
                )
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 200)
        self.assertIn("text/html", handler.header("Content-Type"))
        self.assertTrue(handler.header("Content-Disposition").startswith("inline;"))
        self.assertIn("sandbox", handler.header("Content-Security-Policy"))
        self.assertNotIn("allow-same-origin", handler.header("Content-Security-Policy"))
        self.assertEqual(handler.header("Referrer-Policy"), "no-referrer")
        self.assertEqual(handler.header("X-Content-Type-Options"), "nosniff")
        self.assertEqual(handler.body_text(), "<h1>OK</h1>")

    def test_serve_file_does_not_add_sandbox_to_data_downloads(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "Steam Deals 2026-04-24.json"
            target.write_text("{}", encoding="utf-8")
            target.with_suffix(".md").write_text("md", encoding="utf-8")
            target.with_suffix(".html").write_text("html", encoding="utf-8")
            Handler.output_dir = temp_dir
            try:
                Handler._serve_file(
                    handler,
                    urllib.parse.quote("Steam Deals 2026-04-24.json", safe=""),
                )
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 200)
        self.assertTrue(handler.header("Content-Disposition").startswith("attachment;"))
        self.assertEqual(handler.header("Content-Security-Policy"), None)
        self.assertEqual(handler.header("Referrer-Policy"), None)
        self.assertEqual(handler.header("X-Content-Type-Options"), "nosniff")

    def test_serve_file_rejects_non_generated_basename(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "report.html").write_text("<h1>OK</h1>", encoding="utf-8")
            Handler.output_dir = temp_dir
            try:
                Handler._serve_file(handler, urllib.parse.quote("report.html", safe=""))
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 403)
        self.assertIn("Archivo no disponible", handler.body_text())

    def test_serve_file_rejects_generated_looking_non_artifact_name(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "Steam Deals secrets.json").write_text("{}", encoding="utf-8")
            Handler.output_dir = temp_dir
            try:
                Handler._serve_file(handler, urllib.parse.quote("Steam Deals secrets.json", safe=""))
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 403)
        self.assertIn("Archivo no disponible", handler.body_text())

    def test_serve_file_rejects_directory_named_like_generated_report(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "Steam Deals Directory 2026-04-24.html").mkdir()
            Handler.output_dir = temp_dir
            try:
                Handler._serve_file(
                    handler,
                    urllib.parse.quote("Steam Deals Directory 2026-04-24.html", safe=""),
                )
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 403)
        self.assertIn("reportes generados válidos", handler.body_text())

    def test_files_list_only_returns_allowed_generated_artifacts(self) -> None:
        handler = _FakeJsonHandler({})
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "Steam Deals 2026-04-24.html").write_text("html", encoding="utf-8")
            (output_dir / "Steam Deals 2026-04-24.md").write_text("md", encoding="utf-8")
            (output_dir / "Steam Deals 2026-04-24.json").write_text("{}", encoding="utf-8")
            (output_dir / "PAYDAY2_Plan_de_Compra.md").write_text("md", encoding="utf-8")
            (output_dir / "secret.json").write_text("{}", encoding="utf-8")
            (output_dir / "Steam Deals secrets.json").write_text("{}", encoding="utf-8")
            (output_dir / "Steam Deals Share 2026-04-24.json").write_text("{}", encoding="utf-8")
            Handler.output_dir = temp_dir
            try:
                Handler._serve_files_list(handler)
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 200)
        self.assertEqual(
            {item["name"] for item in handler.json},
            {
                "Steam Deals 2026-04-24.html",
                "Steam Deals 2026-04-24.md",
                "Steam Deals 2026-04-24.json",
                "PAYDAY2_Plan_de_Compra.md",
            },
        )

    def test_selection_review_records_from_body_sanitizes_urls_and_limits(self) -> None:
        records = selection_review_records_from_body(
            {
                "selection": "https://store.steampowered.com/app/10/Game\nnot-an-app\napp/20\n30",
            },
            limit=2,
        )

        self.assertEqual(records, [{"appid": "10"}, {"appid": "20"}])

    def test_selection_review_endpoint_uses_latest_report_without_running_generator(self) -> None:
        handler = _FakeJsonHandler({"selection": ["10", "20"]})
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            stem = "Steam Deals 2026-05-07"
            (output_dir / f"{stem}.html").write_text("html", encoding="utf-8")
            (output_dir / f"{stem}.md").write_text("md", encoding="utf-8")
            (output_dir / f"{stem}.json").write_text(
                json.dumps(
                    {
                        "deals": [
                            {"appid": "10", "name": "Deep Action", "score": 70, "discount": 60},
                            {"appid": "20", "name": "Weak Deal", "score": 40, "discount": 10},
                        ],
                        "top_picks": [],
                        "personalized_recommendations": {
                            "items": [
                                {
                                    "appid": "10",
                                    "name": "Deep Action",
                                    "base_score": 70,
                                    "affinity_score": 40,
                                    "personalized_score": 100,
                                    "reasons": ["similar a Hades"],
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            Handler.output_dir = temp_dir
            try:
                Handler._serve_selection_review(handler)
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.json["status"], "ok")
        items = handler.json["review"]["items"]
        self.assertEqual([item["appid"] for item in items], ["10", "20"])
        self.assertEqual([item["decision"] for item in items], ["conservar", "quitar"])
        self.assertIn("personalized_score", items[0]["signals"])
        self.assertIn("report_score", items[1]["signals"])
        self.assertIn("similar a Hades", items[0]["reasons"])

    def test_selection_review_endpoint_uses_local_report_signals_when_personalized_is_empty(self) -> None:
        handler = _FakeJsonHandler({"selection": ["10", "30", "40"]})
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            stem = "Steam Deals 2026-05-08"
            (output_dir / f"{stem}.html").write_text("html", encoding="utf-8")
            (output_dir / f"{stem}.md").write_text("md", encoding="utf-8")
            (output_dir / f"{stem}.json").write_text(
                json.dumps(
                    {
                        "deals": [
                            {
                                "appid": "10",
                                "name": "Deep Action",
                                "score": 60,
                                "discount": 40,
                                "genres": ["Action", "Roguelike"],
                            },
                            {"appid": "30", "name": "Owned Hit", "score": 95, "genres": ["Action"]},
                            {"appid": "40", "name": "Family Hit", "score": 95, "genres": ["Action"]},
                        ],
                        "activity_games": [
                            {
                                "appid": "90",
                                "name": "Hades",
                                "playtime_2weeks": 180,
                                "genres": ["Action", "Roguelike"],
                            }
                        ],
                        "library_games": [{"appid": "91", "name": "Dead Cells", "genres": ["Action"]}],
                        "have_on_sale": [{"appid": "30", "name": "Owned Hit"}],
                        "family_appids": ["40"],
                        "user_preferences": {
                            "liked_appids": ["10"],
                            "relationships": {"10": ["similar a Hades"]},
                        },
                        "recommended_collections": [
                            {
                                "id": "steam_deck",
                                "label": "Steam Deck",
                                "items": [{"appid": "10", "reason": "Steam Deck Verified"}],
                            }
                        ],
                        "personalized_recommendations": {"items": []},
                    }
                ),
                encoding="utf-8",
            )
            Handler.output_dir = temp_dir
            try:
                Handler._serve_selection_review(handler)
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 200)
        items = handler.json["review"]["items"]
        by_appid = {item["appid"]: item for item in items}
        self.assertEqual(by_appid["10"]["decision"], "conservar")
        self.assertIn("personalized_score", by_appid["10"]["signals"])
        self.assertIn("affinity", by_appid["10"]["signals"])
        self.assertIn("recommended_collection", by_appid["10"]["signals"])
        self.assertEqual(by_appid["30"]["decision"], "quitar")
        self.assertIn("owned", by_appid["30"]["signals"])
        self.assertEqual(by_appid["40"]["decision"], "quitar")
        self.assertIn("family", by_appid["40"]["signals"])

    def test_selection_review_context_from_report_extracts_nested_preferences(self) -> None:
        context = selection_review_context_from_report(
            {
                "have_on_sale": [{"appid": "30", "name": "Owned Hit"}],
                "activity_games": [{"appid": "90", "genres": ["Action"]}],
                "user_preferences": {
                    "liked_appids": ["10"],
                    "relations": {"10": ["similar a Hades"]},
                },
                "recommended_collections": [
                    {"id": "steam_deck", "label": "Steam Deck", "items": [{"appid": "10"}]}
                ],
                "personalized_recommendations": {"items": []},
            }
        )

        self.assertEqual(context["owned"], [{"appid": "30", "name": "Owned Hit"}])
        self.assertEqual(context["library_games"], [{"appid": "30", "name": "Owned Hit"}])
        self.assertEqual(context["liked_appids"], ["10"])
        self.assertEqual(context["preference_relations"], {"10": ["similar a Hades"]})
        self.assertEqual(
            context["recommended_collections"],
            [{"id": "steam_deck", "label": "Steam Deck", "items": [{"appid": "10"}]}],
        )
        self.assertIsNone(context["personalized_recommendations"])

    def test_run_sse_start_error_sanitizes_public_detail(self) -> None:
        original_start_text_subprocess = web.start_text_subprocess
        original_load_config = web.load_config
        secret_path = "/tmp/secret-process"
        secret_webhook = "https://discord.com/api/webhooks/1/secret"

        def fake_start_text_subprocess(_cmd, env=None):
            raise RuntimeError(f"failed {secret_path} webhook={secret_webhook}")

        web.start_text_subprocess = fake_start_text_subprocess
        web.load_config = lambda: {"key": "SAVED-SECRET"}
        handler = _FakeRunHandler({"config": {"vanity": "gaben"}, "filters": {}})
        try:
            Handler._serve_run_sse(handler)
        finally:
            web.start_text_subprocess = original_start_text_subprocess
            web.load_config = original_load_config

        payload = str(handler.json)
        self.assertEqual(handler.status, 500)
        self.assertEqual(handler.json["error"], "process_start_failed")
        self.assertEqual(handler.json["message"], "No se pudo iniciar proceso.")
        self.assertNotIn(secret_path, payload)
        self.assertNotIn("discord.com/api/webhooks", payload)

    def test_run_sse_returns_conflict_when_process_is_already_running(self) -> None:
        original_running_proc = web._running_proc
        web._running_proc = _FakeStreamProcess([])
        handler = _FakeRunHandler(
            {"config": {"vanity": "gaben"}, "filters": {"warm_cache": True}}
        )
        try:
            Handler._serve_run_sse(handler)
        finally:
            web._running_proc = original_running_proc

        self.assertEqual(handler.status, 409)
        self.assertEqual(handler.json, {"error": "Already running"})

    def test_run_sse_runtime_lines_sanitize_public_text(self) -> None:
        original_start_text_subprocess = web.start_text_subprocess
        original_load_config = web.load_config
        original_save_config = web.save_config
        original_running_proc = web._running_proc
        secret_path = "/usr/bin/python3"
        secret_webhook = "https://discord.com/api/webhooks/1/secret"
        secret_token = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabc"

        def fake_start_text_subprocess(_cmd, env=None):
            return _FakeStreamProcess(
                [
                    "Bare saved secret SAVED-SECRET must be hidden\n",
                    f"Traceback failed {secret_path} webhook={secret_webhook} _MEIPASS\n",
                    f"[1/2] Token {secret_token} en /srv/app/config.json\n",
                ]
            )

        web.start_text_subprocess = fake_start_text_subprocess
        web.load_config = lambda: {"key": "SAVED-SECRET"}
        web.save_config = lambda _cfg: None
        web._running_proc = None
        handler = _FakeRunHandler({"config": {"vanity": "gaben"}, "filters": {}})
        try:
            Handler._serve_run_sse(handler)
        finally:
            web.start_text_subprocess = original_start_text_subprocess
            web.load_config = original_load_config
            web.save_config = original_save_config
            web._running_proc = original_running_proc

        payload = handler.body_text()
        self.assertNotIn("Traceback", payload)
        self.assertNotIn(secret_path, payload)
        self.assertNotIn("discord.com/api/webhooks", payload)
        self.assertNotIn(secret_token, payload)
        self.assertNotIn("SAVED-SECRET", payload)
        self.assertNotIn("_MEIPASS", payload)
        self.assertNotIn("/srv/app/config.json", payload)
        self.assertIn('"files"', payload)
        self.assertIn("[ruta]", payload)

    def test_log_export_success_sanitizes_public_path(self) -> None:
        original_save_execution_log_text = web.save_execution_log_text
        secret_path = Path("/private/tmp/steamtools-secret-log.txt")

        web.save_execution_log_text = lambda _text, filename=None: secret_path
        handler = _FakeJsonHandler({"text": "hello", "filename": "log.txt"})
        try:
            Handler._serve_log_export(handler)
        finally:
            web.save_execution_log_text = original_save_execution_log_text

        payload = str(handler.json)
        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.json["status"], "saved")
        self.assertEqual(handler.json["path"], "[ruta]")
        self.assertEqual(handler.json["name"], secret_path.name)
        self.assertNotIn(str(secret_path), payload)


if __name__ == "__main__":
    unittest.main()
