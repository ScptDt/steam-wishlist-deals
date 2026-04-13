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


if __name__ == "__main__":
    unittest.main()
