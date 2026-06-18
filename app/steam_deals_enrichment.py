from __future__ import annotations

import inspect
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared.cache_utils import load_timestamped_cache as _default_load_timestamped_cache
from shared.cache_utils import save_timestamped_cache as _default_save_timestamped_cache


MAX_WORKERS = 16
RATE_LIMIT_INTERVAL = 0.15
ENRICHMENT_ERROR_SAMPLE_LIMIT = 5


def _default_bar(completed: int, total: int, width: int = 25) -> str:
    if total <= 0:
        return ""
    filled = int((completed / total) * width)
    return f"{'#' * filled}{'-' * (width - filled)}"


def _enrichment_error_reason(exc: Exception) -> str:
    reason = re.sub(r"[^a-z0-9_]+", "_", type(exc).__name__.lower()).strip("_")
    return reason or "error"


def _new_enrichment_error_stats() -> dict:
    return {"count": 0, "reasons": {}, "sample_appids": []}


def _record_enrichment_error(stats: dict | None, appid: str, exc: Exception) -> None:
    if stats is None:
        return
    reason = _enrichment_error_reason(exc)
    stats["count"] = int(stats.get("count", 0) or 0) + 1
    reasons = stats.setdefault("reasons", {})
    reasons[reason] = int(reasons.get(reason, 0) or 0) + 1
    sample_appids = stats.setdefault("sample_appids", [])
    appid_text = str(appid or "").strip()
    if appid_text and appid_text not in sample_appids and len(sample_appids) < ENRICHMENT_ERROR_SAMPLE_LIMIT:
        sample_appids.append(appid_text)


def _emit_enrichment_error_summary(label: str, stats: dict, on_error) -> None:
    count = int(stats.get("count", 0) or 0)
    if not count or on_error is None:
        return
    reasons = stats.get("reasons") if isinstance(stats.get("reasons"), dict) else {}
    reason_text = ", ".join(
        f"{reason}={amount}" for reason, amount in sorted(reasons.items())
    ) or "error"
    sample_appids = [str(appid) for appid in stats.get("sample_appids", []) if str(appid)]
    sample_text = f"; muestra appids: {', '.join(sample_appids)}" if sample_appids else ""
    on_error(
        f"{label}: {count} errores de fetch; señales omitidas "
        f"({reason_text}{sample_text})"
    )


def _supports_keyword(fn, keyword: str) -> bool:
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    return keyword in signature.parameters


def _run_fetch_parallel(
    fetch_parallel_fn,
    items: list[str],
    fetch_fn,
    label: str,
    *,
    rate_limit: float,
    on_error,
) -> dict:
    kwargs = {"rate_limit": rate_limit}
    if _supports_keyword(fetch_parallel_fn, "on_error"):
        kwargs["on_error"] = on_error
    return fetch_parallel_fn(items, fetch_fn, label, **kwargs)


def fetch_parallel(
    items: list[str],
    fetch_fn,
    label: str,
    rate_limit: float = RATE_LIMIT_INTERVAL,
    max_workers: int = MAX_WORKERS,
    *,
    monotonic_fn=time.monotonic,
    sleep_fn=time.sleep,
    emit_progress=print,
    build_bar=_default_bar,
    on_error=None,
) -> dict:
    """Execute fetch_fn(appid) in parallel with global rate limiting."""
    total = len(items)
    if total == 0:
        return {}

    results = {}
    start = monotonic_fn()
    completed = [0]
    result_lock = threading.Lock()
    throttle_lock = threading.Lock()
    last_request_at = [0.0]
    eta_str = f"~{total * rate_limit / max_workers / 60:.1f} min"
    emit_progress(f"  Fetching {label} de {total} juegos ({eta_str})...", flush=True)

    def throttled(appid: str):
        with throttle_lock:
            now = monotonic_fn()
            wait = rate_limit - (now - last_request_at[0])
            if wait > 0:
                sleep_fn(wait)
            last_request_at[0] = monotonic_fn()
        return appid, fetch_fn(appid)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(throttled, appid): appid for appid in items}
        for future in as_completed(futures):
            completed[0] += 1
            elapsed = monotonic_fn() - start
            if completed[0] > 1:
                eta_sec = elapsed / completed[0] * (total - completed[0])
                eta_str = f"{eta_sec / 60:.1f}m"
            bar = build_bar(completed[0], total)
            emit_progress(
                f"\r  {bar} {completed[0]}/{total} ETA {eta_str}  ", end="", flush=True
            )
            try:
                appid, result = future.result()
                if result is not None:
                    with result_lock:
                        results[appid] = result
            except Exception as exc:
                appid = futures.get(future, "")
                if on_error is not None:
                    on_error(appid, exc)
                else:
                    reason = _enrichment_error_reason(exc)
                    emit_progress(
                        f"\n  {label}: error fetch {appid}; señal omitida ({reason})",
                        flush=True,
                    )

    emit_progress(f"\r  {'':70}\r", end="", flush=True)
    return results


def fetch_single_review(appid: str, *, get_json, on_error=None) -> dict | None:
    url = f"https://store.steampowered.com/appreviews/{appid}?json=1&num_per_page=0&language=all"
    try:
        data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        summary = data.get("query_summary", {})
        total_reviews = summary.get("total_reviews", 0)
        if total_reviews > 0:
            positive = summary.get("total_positive", 0)
            return {
                "desc": summary.get("review_score_desc", ""),
                "pct": round(positive / total_reviews * 100),
                "total": total_reviews,
            }
    except Exception as exc:
        if on_error is not None:
            on_error(appid, exc)
    return None


def fetch_single_deck(appid: str, *, get_json, on_error=None) -> int | None:
    url = f"https://store.steampowered.com/saleaction/ajaxgetdeckappcompatibilityreport?nAppID={appid}"
    try:
        data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        return data.get("results", {}).get("resolved_category", 0)
    except Exception as exc:
        if on_error is not None:
            on_error(appid, exc)
    return None


def fetch_single_protondb(appid: str, *, get_json, on_error=None) -> dict | None:
    url = f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
    try:
        data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        tier = data.get("tier", "")
        if tier:
            return {
                "tier": tier,
                "score": data.get("score", 0),
                "total": data.get("total", 0),
            }
    except Exception as exc:
        if on_error is not None:
            on_error(appid, exc)
    return None


def fetch_single_achievement(appid: str, *, get_json, on_error=None) -> dict | None:
    url = f"https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={appid}"
    try:
        data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        achievements = data.get("achievementpercentages", {}).get("achievements", [])
        if not achievements:
            return None
        count = len(achievements)
        avg_completion = (
            sum(achievement.get("percent", 0) for achievement in achievements) / count
        )
        return {"count": count, "avg_completion": round(avg_completion, 1)}
    except Exception as exc:
        if on_error is not None:
            on_error(appid, exc)
        return None


def load_reviews_cache(
    cache_file, steam_id: str, *, load_timestamped_cache=_default_load_timestamped_cache
) -> tuple[dict, float]:
    return load_timestamped_cache(
        cache_file, "reviews", identity_key="steam_id", identity_value=steam_id
    )


def save_reviews_cache(
    cache_file,
    steam_id: str,
    reviews: dict,
    *,
    save_timestamped_cache=_default_save_timestamped_cache,
) -> None:
    save_timestamped_cache(
        cache_file,
        "reviews",
        reviews,
        identity_key="steam_id",
        identity_value=steam_id,
        ensure_ascii=False,
        indent=2,
    )


def fetch_reviews(
    appids: list[str],
    cached: dict,
    rate_limit: float = 0.15,
    *,
    fetch_parallel_fn=fetch_parallel,
    get_json,
    on_error=None,
) -> dict[str, dict]:
    to_fetch = [appid for appid in appids if appid not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    error_stats = _new_enrichment_error_stats()

    def record_error(appid: str, exc: Exception) -> None:
        _record_enrichment_error(error_stats, appid, exc)

    result.update(
        _run_fetch_parallel(
            fetch_parallel_fn,
            to_fetch,
            lambda appid: fetch_single_review(
                appid,
                get_json=get_json,
                on_error=record_error,
            ),
            "reviews",
            rate_limit=rate_limit,
            on_error=record_error,
        )
    )
    _emit_enrichment_error_summary("reviews", error_stats, on_error)
    return result


def load_deck_cache(
    cache_file, steam_id: str, *, load_timestamped_cache=_default_load_timestamped_cache
) -> tuple[dict, float]:
    return load_timestamped_cache(
        cache_file, "deck", identity_key="steam_id", identity_value=steam_id
    )


def save_deck_cache(
    cache_file,
    steam_id: str,
    deck: dict,
    *,
    save_timestamped_cache=_default_save_timestamped_cache,
) -> None:
    save_timestamped_cache(
        cache_file,
        "deck",
        deck,
        identity_key="steam_id",
        identity_value=steam_id,
        ensure_ascii=False,
        indent=2,
    )


def fetch_deck_compat(
    appids: list[str],
    cached: dict,
    rate_limit: float = 0.15,
    *,
    fetch_parallel_fn=fetch_parallel,
    get_json,
    on_error=None,
) -> dict[str, int]:
    to_fetch = [appid for appid in appids if appid not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    error_stats = _new_enrichment_error_stats()

    def record_error(appid: str, exc: Exception) -> None:
        _record_enrichment_error(error_stats, appid, exc)

    result.update(
        _run_fetch_parallel(
            fetch_parallel_fn,
            to_fetch,
            lambda appid: fetch_single_deck(
                appid,
                get_json=get_json,
                on_error=record_error,
            ),
            "Deck compat",
            rate_limit=rate_limit,
            on_error=record_error,
        )
    )
    _emit_enrichment_error_summary("Deck compat", error_stats, on_error)
    return result


def load_protondb_cache(
    cache_file, *, load_timestamped_cache=_default_load_timestamped_cache
) -> tuple[dict, float]:
    return load_timestamped_cache(cache_file, "protondb")


def save_protondb_cache(
    cache_file,
    protondb: dict,
    *,
    save_timestamped_cache=_default_save_timestamped_cache,
) -> None:
    save_timestamped_cache(
        cache_file, "protondb", protondb, ensure_ascii=False, indent=None
    )


def fetch_protondb(
    appids: list[str],
    cached: dict,
    rate_limit: float = 0.15,
    *,
    fetch_parallel_fn=fetch_parallel,
    get_json,
    on_error=None,
) -> dict[str, dict]:
    to_fetch = [appid for appid in appids if appid not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    error_stats = _new_enrichment_error_stats()

    def record_error(appid: str, exc: Exception) -> None:
        _record_enrichment_error(error_stats, appid, exc)

    result.update(
        _run_fetch_parallel(
            fetch_parallel_fn,
            to_fetch,
            lambda appid: fetch_single_protondb(
                appid,
                get_json=get_json,
                on_error=record_error,
            ),
            "ProtonDB",
            rate_limit=rate_limit,
            on_error=record_error,
        )
    )
    _emit_enrichment_error_summary("ProtonDB", error_stats, on_error)
    return result


def load_anticheat_cache(
    cache_file, *, load_timestamped_cache=_default_load_timestamped_cache
) -> tuple[dict, float]:
    return load_timestamped_cache(cache_file, "games")


def save_anticheat_cache(
    cache_file, games: dict, *, save_timestamped_cache=_default_save_timestamped_cache
) -> None:
    save_timestamped_cache(cache_file, "games", games, ensure_ascii=False, indent=None)


def fetch_anticheat_db(*, get_json, on_error=None) -> dict[str, dict]:
    url = "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/master/games.json"
    try:
        data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        result = {}
        if isinstance(data, list):
            for game in data:
                steam_id = game.get("storeIds", {}).get("steam")
                if steam_id:
                    result[str(steam_id)] = {
                        "status": game.get("status", ""),
                        "anticheats": game.get("anticheats", []),
                        "native": game.get("native", False),
                    }
        return result
    except Exception as exc:
        if on_error is not None:
            on_error(f"Anti-cheat DB error: {exc}")
        return {}


def load_tags_cache(
    cache_file, *, load_timestamped_cache=_default_load_timestamped_cache
) -> tuple[dict, float]:
    tags, age_hours = load_timestamped_cache(cache_file, "tags")
    for appid, value in tags.items():
        if isinstance(value, dict) and "tags" not in value:
            tags[appid] = {"tags": value, "players": {}}
    return tags, age_hours


def save_tags_cache(
    cache_file, tags: dict, *, save_timestamped_cache=_default_save_timestamped_cache
) -> None:
    save_timestamped_cache(cache_file, "tags", tags, ensure_ascii=False, indent=None)


def fetch_tags(
    appids: list[str],
    cached: dict,
    rate_limit: float = 1.1,
    *,
    get_json,
    sleep_fn=time.sleep,
    monotonic_fn=time.monotonic,
    emit_progress=print,
    build_bar=_default_bar,
) -> dict[str, dict]:
    to_fetch = [appid for appid in appids if appid not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    total = len(to_fetch)
    start = monotonic_fn()
    eta_str = f"~{total * rate_limit / 60:.1f} min"
    emit_progress(
        f"  Fetching tags de {total} juegos via SteamSpy ({eta_str})...", flush=True
    )
    for index, appid in enumerate(to_fetch):
        bar = build_bar(index, total)
        if index > 0:
            eta_sec = (monotonic_fn() - start) / index * (total - index)
            eta_str = f"{eta_sec / 60:.1f}m"
        emit_progress(f"\r  {bar} {index}/{total} ETA {eta_str}  ", end="", flush=True)
        url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
        try:
            data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
            tags = data.get("tags", {})
            if tags and isinstance(tags, dict):
                result[appid] = {
                    "tags": tags,
                    "players": {
                        "owners": data.get("owners", ""),
                        "ccu": data.get("ccu", 0),
                        "players_2weeks": data.get("players_2weeks", 0),
                    },
                }
        except Exception:
            pass
        sleep_fn(rate_limit)
    emit_progress(f"\r  {'':70}\r", end="", flush=True)
    return result


def load_achievements_cache(
    cache_file, steam_id: str, *, load_timestamped_cache=_default_load_timestamped_cache
) -> tuple[dict, float]:
    return load_timestamped_cache(
        cache_file, "achievements", identity_key="steam_id", identity_value=steam_id
    )


def save_achievements_cache(
    cache_file,
    steam_id: str,
    achievements: dict,
    *,
    save_timestamped_cache=_default_save_timestamped_cache,
) -> None:
    save_timestamped_cache(
        cache_file,
        "achievements",
        achievements,
        identity_key="steam_id",
        identity_value=steam_id,
        ensure_ascii=False,
        indent=2,
    )


def fetch_achievements(
    appids: list[str],
    cached: dict,
    rate_limit: float = 0.15,
    *,
    fetch_parallel_fn=fetch_parallel,
    get_json,
    on_error=None,
) -> dict[str, dict]:
    to_fetch = [appid for appid in appids if appid not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    error_stats = _new_enrichment_error_stats()

    def record_error(appid: str, exc: Exception) -> None:
        _record_enrichment_error(error_stats, appid, exc)

    result.update(
        _run_fetch_parallel(
            fetch_parallel_fn,
            to_fetch,
            lambda appid: fetch_single_achievement(
                appid,
                get_json=get_json,
                on_error=record_error,
            ),
            "achievements",
            rate_limit=rate_limit,
            on_error=record_error,
        )
    )
    _emit_enrichment_error_summary("achievements", error_stats, on_error)
    return result
