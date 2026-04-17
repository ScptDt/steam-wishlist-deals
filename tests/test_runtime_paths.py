from __future__ import annotations

import unittest
from pathlib import Path

from steam_deals_paths import resolve_cache_dir, resolve_logs_dir


class ResolveCacheDirTests(unittest.TestCase):
    def test_source_runs_keep_repo_local_cache_dir(self) -> None:
        cache_dir = resolve_cache_dir(
            Path("/workspace/deals"),
            env={},
            frozen=False,
        )

        self.assertEqual(cache_dir, Path("/workspace/deals/.cache/steam_deals"))

    def test_frozen_runs_use_home_cache_dir_by_default(self) -> None:
        cache_dir = resolve_cache_dir(
            Path("/tmp/_MEI123"),
            env={"HOME": "/home/tester"},
            frozen=True,
        )

        self.assertEqual(cache_dir, Path("/home/tester/.cache/steam_deals"))

    def test_frozen_runs_respect_xdg_cache_home(self) -> None:
        cache_dir = resolve_cache_dir(
            Path("/tmp/_MEI123"),
            env={"HOME": "/home/tester", "XDG_CACHE_HOME": "/var/cache/tester"},
            frozen=True,
        )

        self.assertEqual(cache_dir, Path("/var/cache/tester/steam_deals"))

    def test_override_env_wins_over_execution_mode(self) -> None:
        cache_dir = resolve_cache_dir(
            Path("/tmp/_MEI123"),
            env={"STEAM_DEALS_CACHE_DIR": "~/custom-cache"},
            frozen=True,
        )

        self.assertEqual(cache_dir, Path("~/custom-cache").expanduser())


class ResolveLogsDirTests(unittest.TestCase):
    def test_source_runs_default_to_project_logs_folder(self) -> None:
        logs_dir = resolve_logs_dir(
            Path("/workspace/deals"),
            env={},
            frozen=False,
        )

        self.assertEqual(logs_dir, Path("/workspace/deals/logs"))

    def test_cache_override_routes_logs_inside_cache_folder(self) -> None:
        logs_dir = resolve_logs_dir(
            Path("/workspace/deals"),
            env={"STEAM_DEALS_CACHE_DIR": "/var/tmp/steam-cache"},
            frozen=False,
        )

        self.assertEqual(logs_dir, Path("/var/tmp/steam-cache/logs"))

    def test_frozen_runs_use_persistent_cache_logs_folder(self) -> None:
        logs_dir = resolve_logs_dir(
            Path("/tmp/_MEI123"),
            env={"HOME": "/home/tester"},
            frozen=True,
        )

        self.assertEqual(logs_dir, Path("/home/tester/.cache/steam_deals/logs"))

    def test_logs_override_env_wins_over_execution_mode(self) -> None:
        logs_dir = resolve_logs_dir(
            Path("/tmp/_MEI123"),
            env={"STEAM_DEALS_LOG_DIR": "~/custom-logs"},
            frozen=True,
        )

        self.assertEqual(logs_dir, Path("~/custom-logs").expanduser())


if __name__ == "__main__":
    unittest.main()
