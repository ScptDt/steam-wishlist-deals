from __future__ import annotations

import re
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor

from shared.cache_utils import load_timestamped_cache as _default_load_timestamped_cache
from shared.cache_utils import save_timestamped_cache as _default_save_timestamped_cache


ENTRY_FETCHED_AT_KEY = "_fetched_at"
ENTRY_FAILED_AT_KEY = "_failed_at"
ENTRY_FAILURE_REASON_KEY = "_failure_reason"
FETCH_ERROR_KEY = "_steam_deals_fetch_error"
PRICE_DATA_FAILURE_REASON = "no_price_data"
DEFAULT_FAILURE_RETRY_HOURS = 2.0
DEFAULT_HTTP_400_CIRCUIT_BREAKER_THRESHOLD = 3
DEFAULT_INDIVIDUAL_FALLBACK_WORKERS = 1
MAX_INDIVIDUAL_FALLBACK_WORKERS = 4
ADAPTIVE_FALLBACK_FAILURE_RATIO = 0.5
ADAPTIVE_FALLBACK_MIN_BATCH_SIZE = 4


def load_price_cache(
    cache_file, steam_id: str, *, load_timestamped_cache=_default_load_timestamped_cache
) -> tuple[dict, float]:
    return load_timestamped_cache(
        cache_file,
        "fetched",
        identity_key="steam_id",
        identity_value=steam_id,
    )


def save_price_cache(
    cache_file,
    steam_id: str,
    fetched: dict,
    *,
    save_timestamped_cache=_default_save_timestamped_cache,
) -> None:
    save_timestamped_cache(
        cache_file,
        "fetched",
        fetched,
        identity_key="steam_id",
        identity_value=steam_id,
        ensure_ascii=False,
        indent=2,
    )


def fetch_single(
    appid: str, country: str, delay: float, *, get_json, sleep_fn=time.sleep
) -> dict | None:
    url = (
        f"https://store.steampowered.com/api/appdetails"
        f"?appids={appid}&cc={country}&filters=price_overview,basic,genres,platforms,release_date,metacritic,categories"
    )
    try:
        data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        sleep_fn(delay)
        return data
    except urllib.error.HTTPError as exc:
        sleep_fn(delay)
        return {FETCH_ERROR_KEY: f"http_{exc.code}"}
    except Exception as exc:
        sleep_fn(delay)
        reason = re.sub(r"[^a-z0-9_]+", "_", type(exc).__name__.lower())
        return {FETCH_ERROR_KEY: f"error_{reason}"}


def parse_release_year(date_str: str) -> int | None:
    if not date_str:
        return None
    match = re.search(r"((?:19|20)\d{2})", date_str)
    return int(match.group(1)) if match else None


def process_app_entry(
    appid: str, data: dict, *, parse_release_year_fn=parse_release_year
) -> dict | None:
    app_entry = data.get(appid)
    if not app_entry or not isinstance(app_entry, dict) or not app_entry.get("success"):
        return None
    info = app_entry.get("data", {})
    price_info = info.get("price_overview")
    if not price_info:
        return None
    release_date = info.get("release_date", {})
    release_str = (
        release_date.get("date", "") if not release_date.get("coming_soon") else ""
    )
    raw_desc = info.get("short_description", "")
    clean_desc = re.sub(r"<[^>]+>", "", raw_desc).strip()[:120] if raw_desc else ""
    return {
        "name": info.get("name", ""),
        "type": info.get("type", "game"),
        "discount_percent": price_info.get("discount_percent", 0),
        "price_final": price_info.get("final_formatted", ""),
        "price_original": price_info.get("initial_formatted", ""),
        "price_final_raw": price_info.get("final", 0),
        "genres": [genre["description"].lower() for genre in info.get("genres", [])],
        "release_year": parse_release_year_fn(release_str),
        "description": clean_desc,
        "linux_native": info.get("platforms", {}).get("linux", False),
        "metacritic_score": info.get("metacritic", {}).get("score"),
        "metacritic_url": info.get("metacritic", {}).get("url", ""),
        "categories": [category["id"] for category in info.get("categories", [])],
    }


def _build_bar(
    completed: int,
    total: int,
    *,
    bar_fill: str,
    bar_empty: str,
    color_green: str,
    color_dim: str,
    color_reset: str,
    width: int = 25,
) -> str:
    filled = int((completed / total) * width) if total > 0 else 0
    return f"{color_green}{bar_fill * filled}{color_dim}{bar_empty * (width - filled)}{color_reset}"


def _emit(emit, message: str, **kwargs) -> None:
    try:
        emit(message, **kwargs)
    except TypeError:
        emit(message)


def _bounded_individual_fallback_workers(worker_count: int | None) -> int:
    if not isinstance(worker_count, int):
        return DEFAULT_INDIVIDUAL_FALLBACK_WORKERS
    return min(
        MAX_INDIVIDUAL_FALLBACK_WORKERS,
        max(DEFAULT_INDIVIDUAL_FALLBACK_WORKERS, worker_count),
    )


def _fetch_failure_reason(single: dict | None) -> str | None:
    if not isinstance(single, dict):
        return None
    reason = single.get(FETCH_ERROR_KEY)
    return reason if isinstance(reason, str) and reason else None


def _increment_failure_reason(stats_out: dict | None, reason: str | None) -> None:
    if not isinstance(stats_out, dict):
        return
    safe_reason = reason or PRICE_DATA_FAILURE_REASON
    reason_counts = stats_out.setdefault("individual_fallback_failure_reasons", {})
    if isinstance(reason_counts, dict):
        reason_counts[safe_reason] = int(reason_counts.get(safe_reason, 0) or 0) + 1


def _should_downgrade_individual_fallback_workers(
    *, workers: int, batch_stats: dict[str, int]
) -> bool:
    total = int(batch_stats.get("total", 0) or 0)
    failed = int(batch_stats.get("failed", 0) or 0)
    if workers <= 1 or total < ADAPTIVE_FALLBACK_MIN_BATCH_SIZE:
        return False
    return (failed / total) >= ADAPTIVE_FALLBACK_FAILURE_RATIO


def _downgrade_individual_fallback_workers_if_needed(
    workers: int,
    batch_stats: dict[str, int],
    *,
    stats_out: dict | None,
    emit,
    dim,
) -> int:
    if not _should_downgrade_individual_fallback_workers(
        workers=workers,
        batch_stats=batch_stats,
    ):
        return workers
    if isinstance(stats_out, dict):
        stats_out["individual_fallback_worker_downgrade_count"] = (
            int(stats_out.get("individual_fallback_worker_downgrade_count", 0) or 0)
            + 1
        )
    failed = int(batch_stats.get("failed", 0) or 0)
    total = int(batch_stats.get("total", 0) or 0)
    _emit(
        emit,
        "\n  "
        + dim(
            f"Fallback individual adaptativo: {failed}/{total} fallaron con "
            f"workers={workers}; bajando a 1 worker."
        ),
        flush=True,
    )
    return DEFAULT_INDIVIDUAL_FALLBACK_WORKERS


def _build_empty_fallback_stats() -> dict[str, int]:
    return {"total": 0, "resolved": 0, "failed": 0}


def _merge_fallback_stats(target: dict[str, int], source: dict[str, int]) -> None:
    for key in ("total", "resolved", "failed"):
        target[key] = int(target.get(key, 0) or 0) + int(source.get(key, 0) or 0)


def _fetch_individual_fallback_entry(
    appid: str,
    *,
    country: str,
    delay: float,
    fetch_single_fn,
    process_app_entry_fn,
) -> tuple[str, dict | None, str | None]:
    single = fetch_single_fn(appid, country, delay)
    fetch_error_reason = _fetch_failure_reason(single)
    parsed = None
    if single and not fetch_error_reason:
        parsed = process_app_entry_fn(appid, single)
    failure_reason = None if parsed else (fetch_error_reason or PRICE_DATA_FAILURE_REASON)
    return appid, parsed, failure_reason


def _handle_individual_fallback(
    batch: list[str],
    fetched_cache: dict,
    *,
    country: str,
    delay: float,
    now_ts: float,
    fetch_single_fn,
    process_app_entry_fn,
    individual_fallback_workers: int = DEFAULT_INDIVIDUAL_FALLBACK_WORKERS,
    stats_out: dict | None = None,
) -> dict[str, int]:
    batch_stats = _build_empty_fallback_stats()
    if isinstance(stats_out, dict):
        stats_out["individual_fallback_batches"] = (
            int(stats_out.get("individual_fallback_batches", 0) or 0) + 1
        )
        stats_out["individual_fallback_count"] = (
            int(stats_out.get("individual_fallback_count", 0) or 0) + len(batch)
        )
    workers = _bounded_individual_fallback_workers(individual_fallback_workers)
    if workers <= 1 or len(batch) <= 1:
        results = [
            _fetch_individual_fallback_entry(
                appid,
                country=country,
                delay=delay,
                fetch_single_fn=fetch_single_fn,
                process_app_entry_fn=process_app_entry_fn,
            )
            for appid in batch
        ]
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(batch))) as executor:
            results = list(
                executor.map(
                    lambda appid: _fetch_individual_fallback_entry(
                        appid,
                        country=country,
                        delay=delay,
                        fetch_single_fn=fetch_single_fn,
                        process_app_entry_fn=process_app_entry_fn,
                    ),
                    batch,
                )
            )

    for appid, parsed, failure_reason in results:
        batch_stats["total"] += 1
        if isinstance(stats_out, dict):
            counter_key = (
                "individual_fallback_resolved_count"
                if isinstance(parsed, dict) and parsed
                else "individual_fallback_failed_count"
            )
            stats_out[counter_key] = int(stats_out.get(counter_key, 0) or 0) + 1
        if isinstance(parsed, dict) and parsed:
            batch_stats["resolved"] += 1
        else:
            batch_stats["failed"] += 1
            _increment_failure_reason(stats_out, failure_reason)
        fetched_cache[appid] = _cache_result_entry(
            parsed,
            now_ts=now_ts,
            failure_reason=failure_reason or PRICE_DATA_FAILURE_REASON,
        )
    return batch_stats


def _split_batch(batch: list[str]) -> tuple[list[str], list[str]]:
    midpoint = max(1, len(batch) // 2)
    return batch[:midpoint], batch[midpoint:]


def _resolve_batch_with_guardrails(
    batch: list[str],
    fetched_cache: dict,
    *,
    country: str,
    delay: float,
    now_ts: float,
    get_json,
    sleep_fn,
    fetch_single_fn,
    process_app_entry_fn,
    emit,
    warn,
    dim,
    max_batch_halving: int = 3,
    individual_fallback_workers: int = DEFAULT_INDIVIDUAL_FALLBACK_WORKERS,
    stats_out: dict | None = None,
) -> dict[str, int]:
    aggregate_fallback_stats = _build_empty_fallback_stats()
    pending_batches: list[tuple[list[str], int]] = [(list(batch), 0)]
    while pending_batches:
        current_batch, depth = pending_batches.pop(0)
        if not current_batch:
            continue

        url = _batch_url(current_batch, country)
        data = None
        should_split = False
        backoff = 30

        for attempt in range(4):
            try:
                data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    _emit(
                        emit,
                        f"\n  {warn(f'Rate limit — esperando {backoff}s (intento {attempt + 1}/4)')}",
                        flush=True,
                    )
                    sleep_fn(backoff)
                    backoff = min(backoff * 2, 120)
                    delay = min(delay * 1.5, 5.0)
                    _emit(
                        emit,
                        f"  {dim(f'Delay ajustado a {delay:.1f}s entre batches')}",
                        flush=True,
                    )
                    continue
                if exc.code == 400 and len(current_batch) > 1 and depth < max_batch_halving:
                    if isinstance(stats_out, dict):
                        stats_out["degraded_batch_count"] = (
                            int(stats_out.get("degraded_batch_count", 0) or 0) + 1
                        )
                    _emit(
                        emit,
                        f"\n  {warn(f'HTTP 400 en batch de {len(current_batch)} juegos; reduciendo lote')}",
                        flush=True,
                    )
                    should_split = True
                    break
                _emit(
                    emit,
                    f"\n  {warn(f'HTTP {exc.code} en batch, saltando')}",
                    flush=True,
                )
                if exc.code != 400:
                    sleep_fn(delay)
                break
            except Exception as exc:
                _emit(
                    emit,
                    f"\n  {warn(f'Error en batch: {exc}')}",
                    flush=True,
                )
                sleep_fn(delay * 3)
                break

        if should_split:
            left, right = _split_batch(current_batch)
            pending_batches = [(left, depth + 1), (right, depth + 1), *pending_batches]
            continue

        if data is None:
            _emit(
                emit,
                f"\n  {dim('Batch falló, intentando individualmente...')}",
                flush=True,
            )
            batch_fallback_stats = _handle_individual_fallback(
                current_batch,
                fetched_cache,
                country=country,
                delay=delay,
                now_ts=now_ts,
                fetch_single_fn=fetch_single_fn,
                process_app_entry_fn=process_app_entry_fn,
                individual_fallback_workers=individual_fallback_workers,
                stats_out=stats_out,
            )
            _merge_fallback_stats(aggregate_fallback_stats, batch_fallback_stats)
            continue

        null_count = sum(
            1
            for appid in current_batch
            if not data.get(appid) or not isinstance(data.get(appid), dict)
        )
        if null_count == len(current_batch):
            if isinstance(stats_out, dict):
                stats_out["null_batch_count"] = (
                    int(stats_out.get("null_batch_count", 0) or 0) + 1
                )
            _emit(
                emit,
                f"\n  {dim('Batch devolvió todo null, reintentando individualmente...')}",
                flush=True,
            )
            batch_fallback_stats = _handle_individual_fallback(
                current_batch,
                fetched_cache,
                country=country,
                delay=delay,
                now_ts=now_ts,
                fetch_single_fn=fetch_single_fn,
                process_app_entry_fn=process_app_entry_fn,
                individual_fallback_workers=individual_fallback_workers,
                stats_out=stats_out,
            )
            _merge_fallback_stats(aggregate_fallback_stats, batch_fallback_stats)
            continue

        for appid in current_batch:
            fetched_cache[appid] = _cache_result_entry(
                process_app_entry_fn(appid, data),
                now_ts=now_ts,
            )
        sleep_fn(delay)

    return aggregate_fallback_stats


def _batch_url(batch: list[str], country: str) -> str:
    ids_str = ",".join(batch)
    return (
        f"https://store.steampowered.com/api/appdetails"
        f"?appids={ids_str}&cc={country}&filters=price_overview,basic,genres,platforms,release_date,metacritic,categories"
    )


def _build_deals(
    appids: list[str], fetched_cache: dict, min_discount: int
) -> list[dict]:
    deals = []
    for appid in appids:
        info = fetched_cache.get(appid)
        if not _is_deal_cache_entry(info, min_discount):
            continue
        deals.append(
            {
                "appid": appid,
                "name": info.get("name", ""),
                "type": info.get("type", "game"),
                "discount": info.get("discount_percent", 0),
                "price_final": info.get("price_final", ""),
                "price_original": info.get("price_original", ""),
                "price_raw": info.get("price_final_raw", 0),
                "genres": info.get("genres", []),
                "release_year": info.get("release_year"),
                "description": info.get("description", ""),
                "linux_native": info.get("linux_native", False),
                "metacritic_score": info.get("metacritic_score"),
                "metacritic_url": info.get("metacritic_url", ""),
                "categories": info.get("categories", []),
            }
        )
    deals.sort(key=lambda deal: -deal["discount"])
    return deals


def _is_deal_cache_entry(entry: dict | None, min_discount: int) -> bool:
    if not isinstance(entry, dict) or not entry:
        return False
    if ENTRY_FAILED_AT_KEY in entry or ENTRY_FAILURE_REASON_KEY in entry:
        return False
    discount_percent = entry.get("discount_percent")
    if not isinstance(discount_percent, (int, float)):
        return False
    if discount_percent < min_discount:
        return False
    return all(key in entry for key in ("name", "price_final", "price_original"))


def _is_recent_failed_entry(
    entry: dict | None,
    now_ts: float,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
) -> bool:
    if not isinstance(entry, dict):
        return False
    failed_at = entry.get(ENTRY_FAILED_AT_KEY)
    if not isinstance(failed_at, (int, float)):
        return False
    age_hours = (now_ts - float(failed_at)) / 3600.0
    return age_hours < failure_retry_hours


def _is_stale_entry(
    entry: dict | None,
    now_ts: float,
    ttl_hours: float,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
) -> bool:
    if not isinstance(entry, dict):
        return True
    fetched_at = entry.get(ENTRY_FETCHED_AT_KEY)
    if not isinstance(fetched_at, (int, float)):
        failed_at = entry.get(ENTRY_FAILED_AT_KEY)
        if isinstance(failed_at, (int, float)):
            return not _is_recent_failed_entry(
                entry,
                now_ts,
                failure_retry_hours=failure_retry_hours,
            )
        return True
    age_hours = (now_ts - float(fetched_at)) / 3600.0
    return age_hours >= ttl_hours


def count_refresh_candidates(
    appids: list[str],
    fetched_cache: dict,
    *,
    now_ts: float,
    entry_ttl_hours: float,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
) -> tuple[int, int]:
    missing = 0
    stale = 0
    for appid in appids:
        if appid not in fetched_cache:
            missing += 1
            continue
        if _is_stale_entry(
            fetched_cache.get(appid),
            now_ts,
            entry_ttl_hours,
            failure_retry_hours=failure_retry_hours,
        ):
            stale += 1
    return missing, stale


def _stamp_entry(entry: dict | None, *, now_ts: float) -> dict:
    if isinstance(entry, dict):
        stamped = dict(entry)
    else:
        stamped = {}
    stamped[ENTRY_FETCHED_AT_KEY] = now_ts
    return stamped


def _cache_result_entry(
    entry: dict | None,
    *,
    now_ts: float,
    failure_reason: str = PRICE_DATA_FAILURE_REASON,
) -> dict:
    if not isinstance(entry, dict) or not entry:
        return {
            ENTRY_FAILED_AT_KEY: now_ts,
            ENTRY_FAILURE_REASON_KEY: failure_reason or PRICE_DATA_FAILURE_REASON,
        }
    return _stamp_entry(entry, now_ts=now_ts)


def get_deals_from_wishlist(
    appids: list[str],
    fetched_cache: dict,
    steam_id: str,
    country: str = "mx",
    min_discount: int = 50,
    rate_limit: float = 1.5,
    *,
    get_json,
    sleep_fn=time.sleep,
    monotonic_fn=time.monotonic,
    save_price_cache_fn=None,
    fetch_single_fn=fetch_single,
    process_app_entry_fn=process_app_entry,
    emit=print,
    warn=lambda text: text,
    dim=lambda text: text,
    bar_fill: str = "#",
    bar_empty: str = "-",
    color_green: str = "",
    color_dim: str = "",
    color_reset: str = "",
    batch_size: int = 20,
    entry_ttl_hours: float = 24.0,
    current_time_fn=time.time,
    refresh_ids: list[str] | tuple[str, ...] | None = None,
    max_batch_halving: int = 3,
    failure_retry_hours: float = DEFAULT_FAILURE_RETRY_HOURS,
    http_400_circuit_breaker_threshold: int = DEFAULT_HTTP_400_CIRCUIT_BREAKER_THRESHOLD,
    individual_fallback_workers: int = DEFAULT_INDIVIDUAL_FALLBACK_WORKERS,
    stats_out: dict | None = None,
) -> tuple[list[dict], int]:
    now_ts = float(current_time_fn())
    to_fetch = (
        list(refresh_ids)
        if refresh_ids is not None
        else [
            appid
            for appid in appids
            if appid not in fetched_cache
            or _is_stale_entry(
                fetched_cache.get(appid),
                now_ts,
                entry_ttl_hours,
                failure_retry_hours=failure_retry_hours,
            )
        ]
    )
    total = len(to_fetch)
    delay = rate_limit
    tracking_stats = stats_out if isinstance(stats_out, dict) else {}
    tracking_stats.setdefault("refresh_candidate_count", total)
    tracking_stats.setdefault(
        "deferred_failure_count",
        sum(
            1
            for appid in appids
            if appid in fetched_cache
            and _is_recent_failed_entry(
                fetched_cache.get(appid),
                now_ts,
                failure_retry_hours=failure_retry_hours,
            )
        ),
    )
    tracking_stats.setdefault("degraded_batch_count", 0)
    tracking_stats.setdefault("individual_fallback_count", 0)
    tracking_stats.setdefault("individual_fallback_batches", 0)
    tracking_stats.setdefault("individual_fallback_resolved_count", 0)
    tracking_stats.setdefault("individual_fallback_failed_count", 0)
    tracking_stats.setdefault("http_400_direct_fallback_count", 0)
    tracking_stats.setdefault("http_400_direct_fallback_batches", 0)
    tracking_stats.setdefault("individual_fallback_worker_downgrade_count", 0)
    tracking_stats.setdefault("individual_fallback_failure_reasons", {})
    tracking_stats.setdefault(
        "individual_fallback_worker_count",
        _bounded_individual_fallback_workers(individual_fallback_workers),
    )
    tracking_stats.setdefault("null_batch_count", 0)

    if total > 0:
        batches = [
            to_fetch[index : index + batch_size]
            for index in range(0, total, batch_size)
        ]
        batch_count = len(batches)
        start = monotonic_fn()
        eta_str = f"~{batch_count * delay / 60:.1f} min"
        _emit(
            emit,
            f"  Fetching {total:,} juegos en {batch_count} batches ({eta_str})...",
            flush=True,
        )

        fetched_count = 0
        http_400_degradation_streak = 0
        use_direct_http_400_fallback = False
        direct_fallback_notice_emitted = False
        current_fallback_workers = _bounded_individual_fallback_workers(
            individual_fallback_workers
        )
        for batch_index, batch in enumerate(batches):
            bar = _build_bar(
                fetched_count,
                total,
                bar_fill=bar_fill,
                bar_empty=bar_empty,
                color_green=color_green,
                color_dim=color_dim,
                color_reset=color_reset,
            )
            if fetched_count > 0:
                eta_sec = (
                    (monotonic_fn() - start) / fetched_count * (total - fetched_count)
                )
                eta_str = f"{eta_sec / 60:.1f}m"
            _emit(
                emit,
                f"\r  {bar} {fetched_count:,}/{total:,} ETA {eta_str}  ",
                end="",
                flush=True,
            )

            batch_now_ts = float(current_time_fn())
            if use_direct_http_400_fallback:
                if not direct_fallback_notice_emitted:
                    _emit(
                        emit,
                        "\n  "
                        + dim(
                            "HTTP 400 repetido; usando fallback individual directo para evitar splits lentos..."
                        ),
                        flush=True,
                    )
                    direct_fallback_notice_emitted = True
                tracking_stats["http_400_direct_fallback_batches"] = (
                    int(tracking_stats.get("http_400_direct_fallback_batches", 0) or 0)
                    + 1
                )
                tracking_stats["http_400_direct_fallback_count"] = (
                    int(tracking_stats.get("http_400_direct_fallback_count", 0) or 0)
                    + len(batch)
                )
                batch_fallback_stats = _handle_individual_fallback(
                    batch,
                    fetched_cache,
                    country=country,
                    delay=delay,
                    now_ts=batch_now_ts,
                    fetch_single_fn=fetch_single_fn,
                    process_app_entry_fn=process_app_entry_fn,
                    individual_fallback_workers=current_fallback_workers,
                    stats_out=tracking_stats,
                )
                current_fallback_workers = _downgrade_individual_fallback_workers_if_needed(
                    current_fallback_workers,
                    batch_fallback_stats,
                    stats_out=tracking_stats,
                    emit=emit,
                    dim=dim,
                )
                fetched_count += len(batch)
                if (
                    save_price_cache_fn is not None
                    and batch_index > 0
                    and batch_index % 10 == 0
                ):
                    save_price_cache_fn(steam_id, fetched_cache)
                continue

            degraded_before = int(tracking_stats.get("degraded_batch_count", 0) or 0)
            fallback_before = int(tracking_stats.get("individual_fallback_count", 0) or 0)

            batch_fallback_stats = _resolve_batch_with_guardrails(
                batch,
                fetched_cache,
                country=country,
                delay=delay,
                now_ts=batch_now_ts,
                get_json=get_json,
                sleep_fn=sleep_fn,
                fetch_single_fn=fetch_single_fn,
                process_app_entry_fn=process_app_entry_fn,
                emit=emit,
                warn=warn,
                dim=dim,
                max_batch_halving=max_batch_halving,
                individual_fallback_workers=current_fallback_workers,
                stats_out=tracking_stats,
            )

            current_fallback_workers = _downgrade_individual_fallback_workers_if_needed(
                current_fallback_workers,
                batch_fallback_stats,
                stats_out=tracking_stats,
                emit=emit,
                dim=dim,
            )

            degraded_delta = (
                int(tracking_stats.get("degraded_batch_count", 0) or 0)
                - degraded_before
            )
            fallback_delta = (
                int(tracking_stats.get("individual_fallback_count", 0) or 0)
                - fallback_before
            )
            if degraded_delta > 0 and fallback_delta >= len(batch):
                http_400_degradation_streak += 1
            else:
                http_400_degradation_streak = 0
            if (
                http_400_circuit_breaker_threshold > 0
                and http_400_degradation_streak >= http_400_circuit_breaker_threshold
            ):
                use_direct_http_400_fallback = True

            fetched_count += len(batch)
            if (
                save_price_cache_fn is not None
                and batch_index > 0
                and batch_index % 10 == 0
            ):
                save_price_cache_fn(steam_id, fetched_cache)

        _emit(emit, f"\r  {'':70}\r", end="", flush=True)

    return _build_deals(appids, fetched_cache, min_discount), total
