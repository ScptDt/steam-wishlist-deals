from __future__ import annotations

import re
import time
import urllib.error

from shared.cache_utils import load_timestamped_cache as _default_load_timestamped_cache
from shared.cache_utils import save_timestamped_cache as _default_save_timestamped_cache


def load_price_cache(cache_file, steam_id: str, *, load_timestamped_cache=_default_load_timestamped_cache) -> tuple[dict, float]:
    return load_timestamped_cache(
        cache_file,
        "fetched",
        identity_key="steam_id",
        identity_value=steam_id,
    )


def save_price_cache(cache_file, steam_id: str, fetched: dict, *, save_timestamped_cache=_default_save_timestamped_cache) -> None:
    save_timestamped_cache(
        cache_file,
        "fetched",
        fetched,
        identity_key="steam_id",
        identity_value=steam_id,
        ensure_ascii=False,
        indent=2,
    )


def fetch_single(appid: str, country: str, delay: float, *, get_json, sleep_fn=time.sleep) -> dict | None:
    url = (
        f"https://store.steampowered.com/api/appdetails"
        f"?appids={appid}&cc={country}&filters=price_overview,basic,genres,platforms,release_date,metacritic,categories"
    )
    try:
        data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        sleep_fn(delay)
        return data
    except Exception:
        sleep_fn(delay)
        return None


def parse_release_year(date_str: str) -> int | None:
    if not date_str:
        return None
    match = re.search(r"((?:19|20)\d{2})", date_str)
    return int(match.group(1)) if match else None


def process_app_entry(appid: str, data: dict, *, parse_release_year_fn=parse_release_year) -> dict | None:
    app_entry = data.get(appid)
    if not app_entry or not isinstance(app_entry, dict) or not app_entry.get("success"):
        return None
    info = app_entry.get("data", {})
    price_info = info.get("price_overview")
    if not price_info:
        return None
    release_date = info.get("release_date", {})
    release_str = release_date.get("date", "") if not release_date.get("coming_soon") else ""
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


def _build_bar(completed: int, total: int, *, bar_fill: str, bar_empty: str, color_green: str, color_dim: str, color_reset: str, width: int = 25) -> str:
    filled = int((completed / total) * width) if total > 0 else 0
    return f"{color_green}{bar_fill * filled}{color_dim}{bar_empty * (width - filled)}{color_reset}"


def _emit(emit, message: str, **kwargs) -> None:
    try:
        emit(message, **kwargs)
    except TypeError:
        emit(message)


def _batch_url(batch: list[str], country: str) -> str:
    ids_str = ",".join(batch)
    return (
        f"https://store.steampowered.com/api/appdetails"
        f"?appids={ids_str}&cc={country}&filters=price_overview,basic,genres,platforms,release_date,metacritic,categories"
    )


def _build_deals(appids: list[str], fetched_cache: dict, min_discount: int) -> list[dict]:
    deals = [
        {
            "appid": appid,
            "name": info["name"],
            "type": info.get("type", "game"),
            "discount": info["discount_percent"],
            "price_final": info["price_final"],
            "price_original": info["price_original"],
            "price_raw": info.get("price_final_raw", 0),
            "genres": info["genres"],
            "release_year": info.get("release_year"),
            "description": info.get("description", ""),
            "linux_native": info.get("linux_native", False),
            "metacritic_score": info.get("metacritic_score"),
            "metacritic_url": info.get("metacritic_url", ""),
            "categories": info.get("categories", []),
        }
        for appid in appids
        if (info := fetched_cache.get(appid)) and info and info.get("discount_percent", 0) >= min_discount
    ]
    deals.sort(key=lambda deal: -deal["discount"])
    return deals


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
) -> tuple[list[dict], int]:
    to_fetch = [appid for appid in appids if appid not in fetched_cache]
    total = len(to_fetch)
    delay = rate_limit

    if total > 0:
        batches = [to_fetch[index:index + batch_size] for index in range(0, total, batch_size)]
        batch_count = len(batches)
        start = monotonic_fn()
        eta_str = f"~{batch_count * delay / 60:.1f} min"
        _emit(emit, f"  Fetching {total:,} juegos en {batch_count} batches ({eta_str})...", flush=True)

        fetched_count = 0
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
                eta_sec = (monotonic_fn() - start) / fetched_count * (total - fetched_count)
                eta_str = f"{eta_sec / 60:.1f}m"
            _emit(emit, f"\r  {bar} {fetched_count:,}/{total:,} ETA {eta_str}  ", end="", flush=True)

            url = _batch_url(batch, country)
            backoff = 30
            data = None
            for attempt in range(4):
                try:
                    data = get_json(url, headers={"User-Agent": "Mozilla/5.0"})
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code == 429:
                        _emit(emit, f"\n  {warn(f'Rate limit — esperando {backoff}s (intento {attempt + 1}/4)')}", flush=True)
                        sleep_fn(backoff)
                        backoff = min(backoff * 2, 120)
                        delay = min(delay * 1.5, 5.0)
                        _emit(emit, f"  {dim(f'Delay ajustado a {delay:.1f}s entre batches')}", flush=True)
                    else:
                        _emit(emit, f"\n  {warn(f'HTTP {exc.code} en batch {batch_index + 1}, saltando')}", flush=True)
                        sleep_fn(delay)
                        break
                except Exception as exc:
                    _emit(emit, f"\n  {warn(f'Error en batch {batch_index + 1}: {exc}')}", flush=True)
                    sleep_fn(delay * 3)
                    break

            if data is None:
                _emit(emit, f"\n  {dim('Batch falló, intentando individualmente...')}", flush=True)
                for appid in batch:
                    single = fetch_single_fn(appid, country, delay)
                    fetched_cache[appid] = process_app_entry_fn(appid, single) if single else None
                fetched_count += len(batch)
                continue

            null_count = sum(1 for appid in batch if not data.get(appid) or not isinstance(data.get(appid), dict))
            if null_count == len(batch) and len(batch) > 1:
                _emit(emit, f"\n  {dim('Batch devolvió todo null, reintentando individualmente...')}", flush=True)
                for appid in batch:
                    single = fetch_single_fn(appid, country, delay)
                    fetched_cache[appid] = process_app_entry_fn(appid, single) if single else None
                fetched_count += len(batch)
                continue

            for appid in batch:
                fetched_cache[appid] = process_app_entry_fn(appid, data)

            fetched_count += len(batch)
            if save_price_cache_fn is not None and batch_index > 0 and batch_index % 10 == 0:
                save_price_cache_fn(steam_id, fetched_cache)
            sleep_fn(delay)

        _emit(emit, f"\r  {'':70}\r", end="", flush=True)

    return _build_deals(appids, fetched_cache, min_discount), total
