from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shared.cache_utils import load_timestamped_cache, save_timestamped_cache
from shared.io_utils import load_json_file, write_json_file


class JsonFileHelperTests(unittest.TestCase):
    def test_load_json_file_returns_default_for_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing.json"
            self.assertEqual(load_json_file(path, {"ok": True}), {"ok": True})

    def test_write_json_file_persists_and_load_json_file_restores(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "data.json"
            payload = {"name": "steam", "count": 2}

            write_json_file(path, payload, ensure_ascii=False, indent=2)

            self.assertEqual(load_json_file(path, {}), payload)

    def test_load_json_file_reports_invalid_json_without_leaking_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad-config.json"
            path.write_text("{bad", encoding="utf-8")
            diagnostics: list[dict] = []

            result = load_json_file(path, {"fallback": True}, on_error=diagnostics.append)

            self.assertEqual(result, {"fallback": True})
            self.assertEqual(diagnostics[0]["error"], "invalid_json")
            self.assertEqual(diagnostics[0]["file"], "bad-config.json")
            self.assertNotIn(tmpdir, str(diagnostics[0]))


class TimestampedCacheTests(unittest.TestCase):
    def test_save_and_load_timestamped_cache_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cache.json"
            payload = {"1": {"price": 1000}}

            save_timestamped_cache(
                path,
                "fetched",
                payload,
                identity_key="steam_id",
                identity_value="abc",
            )

            loaded, age_hours = load_timestamped_cache(
                path,
                "fetched",
                identity_key="steam_id",
                identity_value="abc",
            )

            self.assertEqual(loaded, payload)
            self.assertGreaterEqual(age_hours, 0)

    def test_load_timestamped_cache_returns_empty_when_identity_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cache.json"
            save_timestamped_cache(
                path,
                "reviews",
                {"1": {"pct": 90}},
                identity_key="steam_id",
                identity_value="expected",
            )

            loaded, age_hours = load_timestamped_cache(
                path,
                "reviews",
                identity_key="steam_id",
                identity_value="other",
            )

            self.assertEqual(loaded, {})
            self.assertEqual(age_hours, float("inf"))

    def test_load_timestamped_cache_reports_invalid_cache_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cache.json"
            path.write_text("[]", encoding="utf-8")
            diagnostics: list[dict] = []

            loaded, age_hours = load_timestamped_cache(
                path,
                "reviews",
                on_error=diagnostics.append,
            )

            self.assertEqual(loaded, {})
            self.assertEqual(age_hours, float("inf"))
            self.assertEqual(diagnostics[0]["error"], "invalid_cache_shape")
            self.assertEqual(diagnostics[0]["file"], "cache.json")
            self.assertNotIn(tmpdir, str(diagnostics[0]))


if __name__ == "__main__":
    unittest.main()
