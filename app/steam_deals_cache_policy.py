from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Iterable


FAILED_AT_KEY = "_failed_at"
DEFAULT_FAILURE_RETRY_HOURS = 2.0


def _is_stale_entry(
    entry: dict | None,
    *,
    now_ts: float,
    ttl_hours: float,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
) -> bool:
    if not isinstance(entry, dict):
        return True
    fetched_at = entry.get("_fetched_at")
    if not isinstance(fetched_at, (int, float)):
        failed_at = entry.get(FAILED_AT_KEY)
        if isinstance(failed_at, (int, float)):
            age_hours = (float(now_ts) - float(failed_at)) / 3600.0
            return age_hours >= failure_retry_hours
        return True
    age_hours = (float(now_ts) - float(fetched_at)) / 3600.0
    return age_hours >= ttl_hours


def _refresh_ids(
    target_ids: list[str],
    cached: dict,
    *,
    now_ts: float,
    ttl_hours: float,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
) -> tuple[str, ...]:
    return tuple(
        appid
        for appid in target_ids
        if appid not in cached
        or _is_stale_entry(
            cached.get(appid),
            now_ts=now_ts,
            ttl_hours=ttl_hours,
            failure_retry_hours=failure_retry_hours,
        )
    )


def _deferred_failure_ids(
    target_ids: list[str],
    cached: dict,
    *,
    now_ts: float,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
) -> tuple[str, ...]:
    ids: list[str] = []
    for appid in target_ids:
        entry = cached.get(appid)
        if not isinstance(entry, dict):
            continue
        failed_at = entry.get(FAILED_AT_KEY)
        if not isinstance(failed_at, (int, float)):
            continue
        age_hours = (float(now_ts) - float(failed_at)) / 3600.0
        if age_hours < failure_retry_hours:
            ids.append(appid)
    return tuple(ids)


@dataclass(frozen=True)
class CacheDecision:
    status: str
    cache: dict
    missing_ids: tuple[str, ...] = ()
    refresh_ids: tuple[str, ...] = ()
    deferred_failure_ids: tuple[str, ...] = ()


def _clone_cache(cached: dict) -> dict:
    return dict(cached) if isinstance(cached, dict) else {}


def _missing_ids(target_ids: list[str], cached: dict) -> tuple[str, ...]:
    return tuple(appid for appid in target_ids if appid not in cached)


def _build_scoped_cache_decision(
    status: str,
    target_ids: list[str],
    cached: dict,
    *,
    now_ts: float,
    refresh_ttl: float,
    failure_retry_hours: float,
) -> CacheDecision:
    missing_ids = _missing_ids(target_ids, cached)
    refresh_ids = _refresh_ids(
        target_ids,
        cached,
        now_ts=now_ts,
        ttl_hours=refresh_ttl,
        failure_retry_hours=failure_retry_hours,
    )
    deferred_failure_ids = _deferred_failure_ids(
        target_ids,
        cached,
        now_ts=now_ts,
        failure_retry_hours=failure_retry_hours,
    )
    return CacheDecision(
        status,
        cached,
        missing_ids,
        refresh_ids,
        deferred_failure_ids,
    )


def select_scoped_cache(
    target_ids: list[str],
    cached: dict,
    cache_age: float,
    *,
    no_cache: bool,
    ttl_hours: float,
    current_time_fn=time.time,
    entry_ttl_hours: float | None = None,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
    preserve_expired_payload: bool = False,
) -> CacheDecision:
    target_ids = list(target_ids)
    if no_cache:
        return CacheDecision("bypass", {}, tuple(target_ids), tuple(target_ids))

    normalized_cache = _clone_cache(cached)
    if not normalized_cache:
        return CacheDecision("empty", {}, tuple(target_ids), tuple(target_ids))

    refresh_ttl = ttl_hours if entry_ttl_hours is None else entry_ttl_hours
    now_ts = float(current_time_fn())

    if cache_age >= ttl_hours:
        if not preserve_expired_payload:
            return CacheDecision("expired", {}, tuple(target_ids), tuple(target_ids))
        return _build_scoped_cache_decision(
            "expired",
            target_ids,
            normalized_cache,
            now_ts=now_ts,
            refresh_ttl=refresh_ttl,
            failure_retry_hours=failure_retry_hours,
        )

    return _build_scoped_cache_decision(
        "valid",
        target_ids,
        normalized_cache,
        now_ts=now_ts,
        refresh_ttl=refresh_ttl,
        failure_retry_hours=failure_retry_hours,
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
