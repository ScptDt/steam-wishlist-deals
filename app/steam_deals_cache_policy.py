from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CacheDecision:
    status: str
    cache: dict
    missing_ids: tuple[str, ...] = ()


def _clone_cache(cached: dict) -> dict:
    return dict(cached) if isinstance(cached, dict) else {}


def _missing_ids(target_ids: list[str], cached: dict) -> tuple[str, ...]:
    return tuple(appid for appid in target_ids if appid not in cached)


def select_scoped_cache(
    target_ids: list[str],
    cached: dict,
    cache_age: float,
    *,
    no_cache: bool,
    ttl_hours: float,
) -> CacheDecision:
    target_ids = list(target_ids)
    if no_cache:
        return CacheDecision("bypass", {}, tuple(target_ids))

    normalized_cache = _clone_cache(cached)
    if not normalized_cache:
        return CacheDecision("empty", {}, tuple(target_ids))

    if cache_age >= ttl_hours:
        return CacheDecision("expired", {}, tuple(target_ids))

    return CacheDecision(
        "valid",
        normalized_cache,
        _missing_ids(target_ids, normalized_cache),
    )


def select_global_cache(
    cached: dict,
    cache_age: float,
    *,
    no_cache: bool,
    ttl_hours: float,
) -> CacheDecision:
    if no_cache:
        return CacheDecision("bypass", {})

    normalized_cache = _clone_cache(cached)
    if not normalized_cache:
        return CacheDecision("empty", {})

    if cache_age >= ttl_hours:
        return CacheDecision("expired", {})

    return CacheDecision("valid", normalized_cache)


def clear_cache_files(
    cache_files: Iterable[Path],
    *,
    exists_fn=None,
    unlink_fn=None,
) -> tuple[Path, ...]:
    exists = exists_fn or (lambda path: path.exists())
    unlink = unlink_fn or (lambda path: path.unlink())
    cleared: list[Path] = []
    for cache_file in cache_files:
        if exists(cache_file):
            unlink(cache_file)
            cleared.append(cache_file)
    return tuple(cleared)
