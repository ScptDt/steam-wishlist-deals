from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


APP_CACHE_DIRNAME = "steam_deals"
CACHE_DIR_ENV_VAR = "STEAM_DEALS_CACHE_DIR"
LOG_DIR_ENV_VAR = "STEAM_DEALS_LOG_DIR"
LOGS_DIRNAME = "logs"
XDG_CACHE_HOME_ENV_VAR = "XDG_CACHE_HOME"


def _expand_path(raw_path: str) -> Path:
    return Path(raw_path).expanduser()


def resolve_user_cache_dir(
    *,
    env: Mapping[str, str] | None = None,
    home_dir: Path | None = None,
) -> Path:
    env_map = env or os.environ
    xdg_cache_home = (env_map.get(XDG_CACHE_HOME_ENV_VAR) or "").strip()
    if xdg_cache_home:
        return _expand_path(xdg_cache_home) / APP_CACHE_DIRNAME

    if home_dir is not None:
        return home_dir.expanduser() / ".cache" / APP_CACHE_DIRNAME

    home_from_env = (env_map.get("HOME") or "").strip()
    if home_from_env:
        return _expand_path(home_from_env) / ".cache" / APP_CACHE_DIRNAME

    return Path.home() / ".cache" / APP_CACHE_DIRNAME


def resolve_cache_dir(
    project_dir: Path,
    *,
    env: Mapping[str, str] | None = None,
    frozen: bool = False,
) -> Path:
    env_map = env or os.environ
    override_dir = (env_map.get(CACHE_DIR_ENV_VAR) or "").strip()
    if override_dir:
        return _expand_path(override_dir)

    if frozen:
        return resolve_user_cache_dir(env=env_map)

    return project_dir.resolve() / ".cache" / APP_CACHE_DIRNAME


def resolve_logs_dir(
    project_dir: Path,
    *,
    env: Mapping[str, str] | None = None,
    frozen: bool = False,
) -> Path:
    env_map = env or os.environ
    override_dir = (env_map.get(LOG_DIR_ENV_VAR) or "").strip()
    if override_dir:
        return _expand_path(override_dir)

    cache_override = (env_map.get(CACHE_DIR_ENV_VAR) or "").strip()
    if cache_override or frozen:
        return resolve_cache_dir(project_dir, env=env_map, frozen=frozen) / LOGS_DIRNAME

    return project_dir.resolve() / LOGS_DIRNAME
