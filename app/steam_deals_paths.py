from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


APP_CACHE_DIRNAME = "steam_deals"
CACHE_DIR_ENV_VAR = "STEAM_DEALS_CACHE_DIR"
LOG_DIR_ENV_VAR = "STEAM_DEALS_LOG_DIR"
OUTPUT_DIR_ENV_VAR = "STEAM_DEALS_OUTPUT_DIR"
LOGS_DIRNAME = "logs"
DESKTOP_APP_DIRNAME = "SteamTools"
DESKTOP_CACHE_DIRNAME = "cache"
OUTPUT_DIRNAME = "output"
XDG_CACHE_HOME_ENV_VAR = "XDG_CACHE_HOME"


def _expand_path(raw_path: str) -> Path:
    return Path(raw_path).expanduser()


def _env_map(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _runtime_platform(platform: str | None) -> str:
    return (platform or sys.platform).lower()


def _resolve_home_dir(env: Mapping[str, str], home_dir: Path | None) -> Path:
    if home_dir is not None:
        return home_dir.expanduser()
    for env_var in ("HOME", "USERPROFILE"):
        raw_home = (env.get(env_var) or "").strip()
        if raw_home:
            return _expand_path(raw_home)
    return Path.home()


def resolve_user_cache_dir(
    *,
    env: Mapping[str, str] | None = None,
    home_dir: Path | None = None,
    platform: str | None = None,
) -> Path:
    env_map = _env_map(env)
    current_platform = _runtime_platform(platform)

    if current_platform.startswith("win"):
        local_app_data = (env_map.get("LOCALAPPDATA") or "").strip()
        if local_app_data:
            return _expand_path(local_app_data) / DESKTOP_APP_DIRNAME / DESKTOP_CACHE_DIRNAME
        return (
            _resolve_home_dir(env_map, home_dir)
            / "AppData"
            / "Local"
            / DESKTOP_APP_DIRNAME
            / DESKTOP_CACHE_DIRNAME
        )

    if current_platform == "darwin":
        return _resolve_home_dir(env_map, home_dir) / "Library" / "Caches" / DESKTOP_APP_DIRNAME

    xdg_cache_home = (env_map.get(XDG_CACHE_HOME_ENV_VAR) or "").strip()
    if xdg_cache_home:
        return _expand_path(xdg_cache_home) / APP_CACHE_DIRNAME

    return _resolve_home_dir(env_map, home_dir) / ".cache" / APP_CACHE_DIRNAME


def resolve_cache_dir(
    project_dir: Path,
    *,
    env: Mapping[str, str] | None = None,
    frozen: bool = False,
    platform: str | None = None,
) -> Path:
    env_map = _env_map(env)
    override_dir = (env_map.get(CACHE_DIR_ENV_VAR) or "").strip()
    if override_dir:
        return _expand_path(override_dir)

    if frozen:
        return resolve_user_cache_dir(env=env_map, platform=platform)

    return project_dir.resolve() / ".cache" / APP_CACHE_DIRNAME


def resolve_user_output_dir(
    *,
    env: Mapping[str, str] | None = None,
    home_dir: Path | None = None,
) -> Path:
    return _resolve_home_dir(_env_map(env), home_dir) / DESKTOP_APP_DIRNAME / OUTPUT_DIRNAME


def resolve_reports_output_dir(
    project_dir: Path,
    *,
    env: Mapping[str, str] | None = None,
    frozen: bool = False,
) -> Path:
    env_map = _env_map(env)
    override_dir = (env_map.get(OUTPUT_DIR_ENV_VAR) or "").strip()
    if override_dir:
        return _expand_path(override_dir)

    if frozen:
        return resolve_user_output_dir(env=env_map)

    return project_dir.resolve() / OUTPUT_DIRNAME


def resolve_logs_dir(
    project_dir: Path,
    *,
    env: Mapping[str, str] | None = None,
    frozen: bool = False,
    platform: str | None = None,
) -> Path:
    env_map = _env_map(env)
    override_dir = (env_map.get(LOG_DIR_ENV_VAR) or "").strip()
    if override_dir:
        return _expand_path(override_dir)

    cache_override = (env_map.get(CACHE_DIR_ENV_VAR) or "").strip()
    if cache_override or frozen:
        return resolve_cache_dir(
            project_dir,
            env=env_map,
            frozen=frozen,
            platform=platform,
        ) / LOGS_DIRNAME

    return project_dir.resolve() / LOGS_DIRNAME


def _has_path_override(env: Mapping[str, str], name: str) -> bool:
    return bool((env.get(name) or "").strip())


def build_persistent_runtime_env(
    project_dir: Path,
    *,
    env: Mapping[str, str] | None = None,
    frozen: bool = False,
    platform: str | None = None,
) -> dict[str, str]:
    runtime_env = dict(_env_map(env))
    if not frozen:
        return runtime_env

    if not _has_path_override(runtime_env, CACHE_DIR_ENV_VAR):
        runtime_env[CACHE_DIR_ENV_VAR] = str(
            resolve_cache_dir(
                project_dir,
                env=runtime_env,
                frozen=True,
                platform=platform,
            )
        )
    if not _has_path_override(runtime_env, LOG_DIR_ENV_VAR):
        runtime_env[LOG_DIR_ENV_VAR] = str(
            resolve_logs_dir(
                project_dir,
                env=runtime_env,
                frozen=True,
                platform=platform,
            )
        )
    if not _has_path_override(runtime_env, OUTPUT_DIR_ENV_VAR):
        runtime_env[OUTPUT_DIR_ENV_VAR] = str(
            resolve_reports_output_dir(
                project_dir,
                env=runtime_env,
                frozen=True,
            )
        )
    return runtime_env
