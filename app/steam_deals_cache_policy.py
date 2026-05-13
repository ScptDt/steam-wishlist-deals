from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import time
from typing import Iterable


FAILED_AT_KEY = "_failed_at"
FETCHED_AT_KEY = "_fetched_at"
FAILURE_REASON_KEY = "_failure_reason"
DEFERRED_REASON_KEY = "_deferred_reason"
NEXT_RETRY_AFTER_KEY = "_next_retry_after"
TIME_BUDGET_DEFERRED_REASON = "time_budget_deferred"
FALLBACK_BUDGET_FAILURE_REASON = "fallback_budget_deferred"
DEFAULT_FAILURE_RETRY_HOURS = 2.0
DEFAULT_STALE_GRACE_HOURS = 72.0
DEFAULT_TTL_JITTER_HOURS = 6
DEFAULT_MAX_STALE_REFRESH_PER_RUN = 200
CACHE_STATE_FRESH = "fresh"
CACHE_STATE_STALE_USABLE = "stale_usable"
CACHE_STATE_PENDING_DEFERRED = "pending_deferred"
CACHE_STATE_COOLDOWN = "cooldown"
CACHE_STATE_FAILED_NO_DATA = "failed_no_data"
CACHE_STATE_MISSING = "missing"
CACHE_STATE_ORDER = (
    CACHE_STATE_FRESH,
    CACHE_STATE_STALE_USABLE,
    CACHE_STATE_PENDING_DEFERRED,
    CACHE_STATE_COOLDOWN,
    CACHE_STATE_FAILED_NO_DATA,
    CACHE_STATE_MISSING,
)
CACHE_STATE_LABELS = {
    CACHE_STATE_FRESH: "fresh cache",
    CACHE_STATE_STALE_USABLE: "stale usable",
    CACHE_STATE_PENDING_DEFERRED: "pending/deferred",
    CACHE_STATE_COOLDOWN: "failed/cooldown",
    CACHE_STATE_FAILED_NO_DATA: "failed/no data",
    CACHE_STATE_MISSING: "missing",
}


def stable_ttl_jitter_hours(appid: str, max_jitter_hours: int | float) -> int:
    max_bucket = int(max(0, max_jitter_hours or 0))
    if max_bucket <= 0:
        return 0
    digest = hashlib.sha256(str(appid).encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") % (max_bucket + 1)


def _is_stale_entry(
    entry: dict | None,
    *,
    now_ts: float,
    ttl_hours: float,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
) -> bool:
    if not isinstance(entry, dict):
        return True
    fetched_at = entry.get(FETCHED_AT_KEY)
    if not isinstance(fetched_at, (int, float)):
        if _is_recent_failed_entry(
            entry,
            now_ts=now_ts,
            failure_retry_hours=failure_retry_hours,
        ):
            return False
        if _is_retryable_failure_entry(
            entry,
            now_ts=now_ts,
            failure_retry_hours=failure_retry_hours,
        ):
            return True
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
        if _is_recent_failed_entry(
            entry,
            now_ts=now_ts,
            failure_retry_hours=failure_retry_hours,
        ):
            ids.append(appid)
    return tuple(ids)


@dataclass(frozen=True)
class CacheDecision:
    status: str
    cache: dict
    missing_ids: tuple[str, ...] = ()
    refresh_ids: tuple[str, ...] = ()
    deferred_failure_ids: tuple[str, ...] = ()
    fresh_ids: tuple[str, ...] = ()
    stale_usable_ids: tuple[str, ...] = ()
    stale_expired_ids: tuple[str, ...] = ()
    stale_used_ids: tuple[str, ...] = ()
    stale_refresh_deferred_ids: tuple[str, ...] = ()
    ttl_jitter_buckets: dict[str, int] = field(default_factory=dict)


def _clone_cache(cached: dict) -> dict:
    return dict(cached) if isinstance(cached, dict) else {}


def _missing_ids(target_ids: list[str], cached: dict) -> tuple[str, ...]:
    return tuple(appid for appid in target_ids if appid not in cached)


def _entry_age_hours(entry: dict | None, *, now_ts: float) -> float | None:
    if not isinstance(entry, dict):
        return None
    fetched_at = entry.get(FETCHED_AT_KEY)
    if not isinstance(fetched_at, (int, float)):
        return None
    return (float(now_ts) - float(fetched_at)) / 3600.0


def _is_pending_deferred_entry(entry: dict | None) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get(DEFERRED_REASON_KEY) == TIME_BUDGET_DEFERRED_REASON:
        return True
    return entry.get(FAILURE_REASON_KEY) == FALLBACK_BUDGET_FAILURE_REASON


def classify_cache_entry_state(
    appid: str,
    cached: dict,
    *,
    now_ts: float,
    ttl_hours: float,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
    stale_grace_hours: float = DEFAULT_STALE_GRACE_HOURS,
    ttl_jitter_hours: int | float = DEFAULT_TTL_JITTER_HOURS,
) -> str:
    if appid not in cached:
        return CACHE_STATE_MISSING
    entry = cached.get(appid)
    if not isinstance(entry, dict):
        return CACHE_STATE_MISSING
    if _is_pending_deferred_entry(entry):
        return CACHE_STATE_PENDING_DEFERRED
    if _is_recent_failed_entry(
        entry,
        now_ts=now_ts,
        failure_retry_hours=failure_retry_hours,
    ):
        return CACHE_STATE_COOLDOWN
    if _is_retryable_failure_entry(
        entry,
        now_ts=now_ts,
        failure_retry_hours=failure_retry_hours,
    ):
        return CACHE_STATE_FAILED_NO_DATA

    age_hours = _entry_age_hours(entry, now_ts=now_ts)
    if age_hours is None:
        return CACHE_STATE_MISSING

    effective_ttl = float(ttl_hours) + stable_ttl_jitter_hours(appid, ttl_jitter_hours)
    if age_hours < effective_ttl:
        return CACHE_STATE_FRESH
    if stale_grace_hours > 0 and age_hours < effective_ttl + float(stale_grace_hours):
        return CACHE_STATE_STALE_USABLE
    return CACHE_STATE_PENDING_DEFERRED


def build_cache_state_summary(
    target_ids: list[str] | tuple[str, ...],
    cached: dict,
    *,
    now_ts: float,
    ttl_hours: float,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
    stale_grace_hours: float = DEFAULT_STALE_GRACE_HOURS,
    ttl_jitter_hours: int | float = DEFAULT_TTL_JITTER_HOURS,
) -> dict:
    counts = {state: 0 for state in CACHE_STATE_ORDER}
    for appid in target_ids:
        state = classify_cache_entry_state(
            str(appid),
            cached,
            now_ts=now_ts,
            ttl_hours=ttl_hours,
            failure_retry_hours=failure_retry_hours,
            stale_grace_hours=stale_grace_hours,
            ttl_jitter_hours=ttl_jitter_hours,
        )
        counts[state] += 1
    return {
        "total": len(tuple(target_ids)),
        "counts": counts,
        "states": [
            {
                "state": state,
                "label": CACHE_STATE_LABELS[state],
                "count": counts[state],
            }
            for state in CACHE_STATE_ORDER
            if counts[state] > 0
        ],
    }


def _is_recent_failed_entry(
    entry: dict | None,
    *,
    now_ts: float,
    failure_retry_hours: float,
) -> bool:
    if not isinstance(entry, dict):
        return False
    next_retry_after = entry.get(NEXT_RETRY_AFTER_KEY)
    if isinstance(next_retry_after, (int, float)):
        return float(now_ts) < float(next_retry_after)
    failed_at = entry.get(FAILED_AT_KEY)
    if not isinstance(failed_at, (int, float)):
        return False
    age_hours = (float(now_ts) - float(failed_at)) / 3600.0
    return age_hours < failure_retry_hours


def _is_retryable_failure_entry(
    entry: dict | None,
    *,
    now_ts: float,
    failure_retry_hours: float,
) -> bool:
    if not isinstance(entry, dict):
        return False
    failed_at = entry.get(FAILED_AT_KEY)
    if not isinstance(failed_at, (int, float)):
        return False
    return not _is_recent_failed_entry(
        entry,
        now_ts=now_ts,
        failure_retry_hours=failure_retry_hours,
    )


def _is_useful_price_entry(entry: dict | None, min_discount: int) -> bool:
    if not isinstance(entry, dict) or FAILED_AT_KEY in entry:
        return False
    discount_percent = entry.get("discount_percent")
    if not isinstance(discount_percent, (int, float)):
        return False
    if discount_percent < min_discount:
        return False
    return all(key in entry for key in ("name", "price_final", "price_original"))


def _stale_priority(
    appid: str,
    cached: dict,
    *,
    now_ts: float,
    min_discount: int,
) -> tuple[int, float, str]:
    entry = cached.get(appid)
    useful_rank = 0 if _is_useful_price_entry(entry, min_discount) else 1
    age_hours = _entry_age_hours(entry, now_ts=now_ts) or 0.0
    return useful_rank, -age_hours, appid


def _prioritize_stale_ids(
    stale_ids: list[str],
    cached: dict,
    *,
    now_ts: float,
    min_discount: int,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            stale_ids,
            key=lambda appid: _stale_priority(
                appid,
                cached,
                now_ts=now_ts,
                min_discount=min_discount,
            ),
        )
    )


def _select_stale_usable_refresh_ids(
    stale_usable_ids: list[str],
    cached: dict,
    *,
    now_ts: float,
    min_discount: int,
    max_stale_refresh_per_run: int | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    prioritized = _prioritize_stale_ids(
        stale_usable_ids,
        cached,
        now_ts=now_ts,
        min_discount=min_discount,
    )
    if max_stale_refresh_per_run is None:
        return prioritized, ()
    max_refresh = max(0, int(max_stale_refresh_per_run))
    return prioritized[:max_refresh], prioritized[max_refresh:]


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


def _build_stale_revalidate_cache_decision(
    status: str,
    target_ids: list[str],
    cached: dict,
    *,
    now_ts: float,
    refresh_ttl: float,
    failure_retry_hours: float,
    ttl_jitter_hours: int | float,
    stale_grace_hours: float,
    max_stale_refresh_per_run: int | None,
    min_discount: int,
) -> CacheDecision:
    missing_ids: list[str] = []
    fresh_ids: list[str] = []
    stale_usable_ids: list[str] = []
    stale_expired_ids: list[str] = []
    failure_retry_ids: list[str] = []
    deferred_failure_ids: list[str] = []
    ttl_jitter_buckets: dict[str, int] = {}

    for appid in target_ids:
        if appid not in cached:
            missing_ids.append(appid)
            continue

        entry = cached.get(appid)
        if _is_recent_failed_entry(
            entry,
            now_ts=now_ts,
            failure_retry_hours=failure_retry_hours,
        ):
            deferred_failure_ids.append(appid)
            continue
        if _is_retryable_failure_entry(
            entry,
            now_ts=now_ts,
            failure_retry_hours=failure_retry_hours,
        ):
            failure_retry_ids.append(appid)
            stale_expired_ids.append(appid)
            continue

        age_hours = _entry_age_hours(entry, now_ts=now_ts)
        if age_hours is None:
            stale_expired_ids.append(appid)
            continue

        jitter_bucket = stable_ttl_jitter_hours(appid, ttl_jitter_hours)
        ttl_jitter_buckets[appid] = jitter_bucket
        effective_ttl = refresh_ttl + jitter_bucket
        if age_hours < effective_ttl:
            fresh_ids.append(appid)
            continue
        if stale_grace_hours > 0 and age_hours < effective_ttl + stale_grace_hours:
            stale_usable_ids.append(appid)
            continue
        stale_expired_ids.append(appid)

    stale_usable_refresh_ids, stale_deferred_ids = _select_stale_usable_refresh_ids(
        stale_usable_ids,
        cached,
        now_ts=now_ts,
        min_discount=min_discount,
        max_stale_refresh_per_run=max_stale_refresh_per_run,
    )
    stale_expired_refresh_ids = tuple(
        appid for appid in stale_expired_ids if appid not in failure_retry_ids
    )
    prioritized_expired = _prioritize_stale_ids(
        list(stale_expired_refresh_ids),
        cached,
        now_ts=now_ts,
        min_discount=min_discount,
    )
    refresh_ids = (
        tuple(missing_ids)
        + prioritized_expired
        + stale_usable_refresh_ids
        + tuple(failure_retry_ids)
    )
    return CacheDecision(
        status=status,
        cache=cached,
        missing_ids=tuple(missing_ids),
        refresh_ids=refresh_ids,
        deferred_failure_ids=tuple(deferred_failure_ids),
        fresh_ids=tuple(fresh_ids),
        stale_usable_ids=tuple(stale_usable_ids),
        stale_expired_ids=tuple(stale_expired_ids),
        stale_used_ids=stale_deferred_ids,
        stale_refresh_deferred_ids=stale_deferred_ids,
        ttl_jitter_buckets=ttl_jitter_buckets,
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
    stale_grace_hours: float = 0.0,
    ttl_jitter_hours: int | float = 0,
    max_stale_refresh_per_run: int | None = None,
    min_discount: int = 0,
) -> CacheDecision:
    target_ids = list(target_ids)
    if no_cache:
        return CacheDecision("bypass", {}, tuple(target_ids), tuple(target_ids))

    normalized_cache = _clone_cache(cached)
    if not normalized_cache:
        return CacheDecision("empty", {}, tuple(target_ids), tuple(target_ids))

    refresh_ttl = ttl_hours if entry_ttl_hours is None else entry_ttl_hours
    now_ts = float(current_time_fn())
    stale_revalidate_enabled = (
        stale_grace_hours > 0
        or ttl_jitter_hours > 0
        or max_stale_refresh_per_run is not None
    )

    if cache_age >= ttl_hours:
        if not preserve_expired_payload:
            return CacheDecision("expired", {}, tuple(target_ids), tuple(target_ids))
        if stale_revalidate_enabled:
            return _build_stale_revalidate_cache_decision(
                "expired",
                target_ids,
                normalized_cache,
                now_ts=now_ts,
                refresh_ttl=refresh_ttl,
                failure_retry_hours=failure_retry_hours,
                ttl_jitter_hours=ttl_jitter_hours,
                stale_grace_hours=stale_grace_hours,
                max_stale_refresh_per_run=max_stale_refresh_per_run,
                min_discount=min_discount,
            )
        return _build_scoped_cache_decision(
            "expired",
            target_ids,
            normalized_cache,
            now_ts=now_ts,
            refresh_ttl=refresh_ttl,
            failure_retry_hours=failure_retry_hours,
        )

    if stale_revalidate_enabled:
        return _build_stale_revalidate_cache_decision(
            "valid",
            target_ids,
            normalized_cache,
            now_ts=now_ts,
            refresh_ttl=refresh_ttl,
            failure_retry_hours=failure_retry_hours,
            ttl_jitter_hours=ttl_jitter_hours,
            stale_grace_hours=stale_grace_hours,
            max_stale_refresh_per_run=max_stale_refresh_per_run,
            min_discount=min_discount,
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
