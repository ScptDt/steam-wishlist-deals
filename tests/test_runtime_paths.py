from __future__ import annotations

import unittest
from pathlib import Path

from steam_deals_paths import (
    CACHE_DIR_ENV_VAR,
    LOG_DIR_ENV_VAR,
    OUTPUT_DIR_ENV_VAR,
    build_persistent_runtime_env,
    resolve_cache_dir,
    resolve_logs_dir,
    resolve_reports_output_dir,
)


class DesktopPersistenceContractTests(unittest.TestCase):
    def test_frozen_runs_share_same_root_for_cache_and_logs(self) -> None:
        project_dir = Path("/tmp/_MEI123")
        env = {"HOME": "/home/tester"}

        cache_dir = resolve_cache_dir(project_dir, env=env, frozen=True, platform="linux")
        logs_dir = resolve_logs_dir(project_dir, env=env, frozen=True, platform="linux")

        self.assertEqual(cache_dir, Path("/home/tester/.cache/steam_deals"))
        self.assertEqual(logs_dir, cache_dir / "logs")

    def test_cache_override_keeps_logs_nested_inside_same_persistent_root(self) -> None:
        project_dir = Path("/tmp/_MEI123")
        env = {"STEAM_DEALS_CACHE_DIR": "/var/tmp/steam-cache"}

        cache_dir = resolve_cache_dir(project_dir, env=env, frozen=True)
        logs_dir = resolve_logs_dir(project_dir, env=env, frozen=True)

        self.assertEqual(cache_dir, Path("/var/tmp/steam-cache"))
        self.assertEqual(logs_dir, Path("/var/tmp/steam-cache/logs"))

    def test_frozen_windows_uses_local_app_data_cache_root(self) -> None:
        cache_dir = resolve_cache_dir(
            Path("C:/Temp/_MEI123"),
            env={"LOCALAPPDATA": "C:/Users/tester/AppData/Local"},
            frozen=True,
            platform="win32",
        )

        self.assertEqual(
            cache_dir,
            Path("C:/Users/tester/AppData/Local/SteamTools/cache"),
        )

    def test_frozen_macos_uses_library_caches_root(self) -> None:
        cache_dir = resolve_cache_dir(
            Path("/var/folders/_MEI123"),
            env={"HOME": "/Users/tester"},
            frozen=True,
            platform="darwin",
        )

        self.assertEqual(cache_dir, Path("/Users/tester/Library/Caches/SteamTools"))

    def test_frozen_runtime_env_sets_persistent_cache_logs_and_output_defaults(self) -> None:
        runtime_env = build_persistent_runtime_env(
            Path("/tmp/_MEI123"),
            env={"HOME": "/home/tester", "KEEP": "1"},
            frozen=True,
            platform="linux",
        )

        self.assertEqual(runtime_env["KEEP"], "1")
        self.assertEqual(runtime_env[CACHE_DIR_ENV_VAR], "/home/tester/.cache/steam_deals")
        self.assertEqual(runtime_env[LOG_DIR_ENV_VAR], "/home/tester/.cache/steam_deals/logs")
        self.assertEqual(runtime_env[OUTPUT_DIR_ENV_VAR], "/home/tester/SteamTools/output")

    def test_frozen_runtime_env_preserves_existing_path_overrides(self) -> None:
        runtime_env = build_persistent_runtime_env(
            Path("/tmp/_MEI123"),
            env={
                CACHE_DIR_ENV_VAR: "/var/tmp/steam-cache",
                LOG_DIR_ENV_VAR: "/var/tmp/steam-logs",
                OUTPUT_DIR_ENV_VAR: "/var/tmp/steam-output",
            },
            frozen=True,
            platform="linux",
        )

        self.assertEqual(runtime_env[CACHE_DIR_ENV_VAR], "/var/tmp/steam-cache")
        self.assertEqual(runtime_env[LOG_DIR_ENV_VAR], "/var/tmp/steam-logs")
        self.assertEqual(runtime_env[OUTPUT_DIR_ENV_VAR], "/var/tmp/steam-output")

    def test_source_runtime_env_does_not_set_cache_or_logs_defaults(self) -> None:
        runtime_env = build_persistent_runtime_env(
            Path("/workspace/deals"),
            env={"HOME": "/home/tester"},
            frozen=False,
            platform="linux",
        )

        self.assertNotIn(CACHE_DIR_ENV_VAR, runtime_env)
        self.assertNotIn(LOG_DIR_ENV_VAR, runtime_env)
        self.assertNotIn(OUTPUT_DIR_ENV_VAR, runtime_env)

    def test_frozen_default_output_uses_persistent_user_folder(self) -> None:
        output_dir = resolve_reports_output_dir(
            Path("/tmp/_MEI123"),
            env={"HOME": "/home/tester"},
            frozen=True,
        )

        self.assertEqual(output_dir, Path("/home/tester/SteamTools/output"))

    def test_source_default_output_stays_project_local(self) -> None:
        output_dir = resolve_reports_output_dir(
            Path("/workspace/deals"),
            env={},
            frozen=False,
        )

        self.assertEqual(output_dir, Path("/workspace/deals/output"))

    def test_output_override_wins_over_execution_mode(self) -> None:
        output_dir = resolve_reports_output_dir(
            Path("/tmp/_MEI123"),
            env={OUTPUT_DIR_ENV_VAR: "~/custom-output"},
            frozen=True,
        )

        self.assertEqual(output_dir, Path("~/custom-output").expanduser())


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
            platform="linux",
        )

        self.assertEqual(cache_dir, Path("/home/tester/.cache/steam_deals"))

    def test_frozen_runs_respect_xdg_cache_home(self) -> None:
        cache_dir = resolve_cache_dir(
            Path("/tmp/_MEI123"),
            env={"HOME": "/home/tester", "XDG_CACHE_HOME": "/var/cache/tester"},
            frozen=True,
            platform="linux",
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
        project_dir = Path("/workspace/deals")
        logs_dir = resolve_logs_dir(
            project_dir,
            env={},
            frozen=False,
        )

        self.assertEqual(logs_dir, project_dir.resolve() / "logs")

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
            platform="linux",
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
