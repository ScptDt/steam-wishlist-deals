from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from steam_deals_config import get_config
from steam_deals_generator import (
    build_free_weekend_now_from_records_json,
    resolve_free_weekend_now,
)


class _FakeStdin:
    def isatty(self):
        return False


class FreeWeekendRecordsWiringTests(unittest.TestCase):
    def test_get_config_exposes_local_free_weekend_records_json_flag(self) -> None:
        result = get_config(
            script_path=Path("/tmp/fake_script.py"),
            load_user_config_fn=lambda: {},
            save_user_config_fn=lambda _cfg: None,
            handle_watchlist_command_fn=lambda _args: None,
            input_fn=lambda _prompt: "",
            stdin=_FakeStdin(),
            exit_fn=lambda _code: None,
            argv=[
                "--vanity",
                "gaben",
                "--free-weekend-records-json",
                "/tmp/free-weekend-records.json",
            ],
        )

        self.assertEqual(
            result[11]["free_weekend_records_json"],
            Path("/tmp/free-weekend-records.json"),
        )

    def test_get_config_exposes_lootscraper_live_opt_in_flag(self) -> None:
        result = get_config(
            script_path=Path("/tmp/fake_script.py"),
            load_user_config_fn=lambda: {},
            save_user_config_fn=lambda _cfg: None,
            handle_watchlist_command_fn=lambda _args: None,
            input_fn=lambda _prompt: "",
            stdin=_FakeStdin(),
            exit_fn=lambda _code: None,
            argv=["--vanity", "gaben", "--free-weekend-lootscraper-live"],
        )

        self.assertTrue(result[11]["free_weekend_lootscraper_live"])

    def test_resolve_free_weekend_now_uses_local_records_without_fetch(self) -> None:
        now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
        records = {
            "items": [
                {
                    "appid": 1843840,
                    "title": "Rogue Point",
                    "starts_at": "2026-06-11T18:00:00Z",
                    "ends_at": "2026-06-15T18:00:00Z",
                    "sources": ["FreeToKeep", "LootScraper"],
                    "category": "free_weekend",
                }
            ]
        }

        with TemporaryDirectory() as temp_dir:
            records_path = Path(temp_dir) / "free-weekend-records.json"
            records_path.write_text(json.dumps(records), encoding="utf-8")
            resolved = resolve_free_weekend_now(
                records_json_file=records_path,
                live_enabled=True,
                lootscraper_live_enabled=True,
                now=now,
                fetch_json=lambda *_args, **_kwargs: self.fail("local records should not fetch"),
                fetch_text=lambda *_args, **_kwargs: self.fail("local records should not fetch"),
            )

        self.assertEqual(resolved["source_policy"], "fixture_or_cached_store_signals_v1")
        self.assertEqual(resolved["summary"], {"count": 1, "confidence_counts": {"high": 1}})
        self.assertEqual(resolved["items"][0]["appid"], "1843840")
        self.assertEqual(resolved["items"][0]["sources"], ["FreeToKeep", "LootScraper"])

    def test_resolve_free_weekend_now_uses_lootscraper_live_when_requested(self) -> None:
        now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
        atom_xml = (
            Path(__file__).parent
            / "fixtures"
            / "free_weekend"
            / "lootscraper_steam_game_atom.xml"
        ).read_text(encoding="utf-8")

        with TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "free_weekend_candidates.json"
            resolved = resolve_free_weekend_now(
                cache_file=cache_path,
                lootscraper_live_enabled=True,
                now=now,
                fetch_text=lambda *_args, **_kwargs: atom_xml,
                fetch_json=lambda *_args, **_kwargs: self.fail("LootScraper live should not fetch Store JSON"),
            )

        self.assertEqual(resolved["items"][0]["appid"], "1843840")
        self.assertEqual(resolved["items"][0]["sources"], ["LootScraper"])

    def test_build_free_weekend_now_from_records_json_reports_invalid_local_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            records_path = Path(temp_dir) / "free-weekend-records.json"
            records_path.write_text("{not-json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Free Weekend records inválido"):
                build_free_weekend_now_from_records_json(records_path)


if __name__ == "__main__":
    unittest.main()
