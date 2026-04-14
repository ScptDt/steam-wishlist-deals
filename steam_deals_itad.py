from __future__ import annotations

import time


ITAD_BATCH = 50


def _chunked(items: list[str], size: int = ITAD_BATCH):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _sleep_after_batch(sleep_fn, seconds: float = 0.5) -> None:
    sleep_fn(seconds)


def _emit_error(on_error, message: str) -> None:
    if on_error is not None:
        on_error(message)


def _id_map(itad_ids: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    return {itad_id: appid for appid, itad_id in itad_ids.items()}, list(itad_ids.values())


def itad_lookup_games(
    appids: list[str],
    itad_key: str,
    *,
    post_json,
    sleep_fn=time.sleep,
    on_error=None,
) -> dict[str, str]:
    """Resuelve Steam appids → ITAD game IDs. Devuelve {appid: itad_id}."""
    result: dict[str, str] = {}
    for batch in _chunked(appids):
        body = [{"type": "steam", "id": f"app/{appid}"} for appid in batch]
        try:
            data = post_json(f"https://api.isthereanydeal.com/games/lookup/v1?key={itad_key}", body)
            if isinstance(data, list):
                for item, appid in zip(data, batch):
                    if item and isinstance(item, dict) and item.get("found"):
                        result[appid] = item["game"]["id"]
        except Exception as exc:
            _emit_error(on_error, f"ITAD lookup error: {exc}")
        _sleep_after_batch(sleep_fn)
    return result


def itad_get_store_lows(
    itad_ids: dict[str, str],
    itad_key: str,
    country: str = "MX",
    *,
    post_json,
    sleep_fn=time.sleep,
    on_error=None,
) -> dict[str, dict]:
    """Obtiene mínimo histórico en Steam. Devuelve {appid: {price, cut, date}}."""
    id_to_appid, all_ids = _id_map(itad_ids)
    result: dict[str, dict] = {}
    for batch in _chunked(all_ids):
        try:
            data = post_json(
                f"https://api.isthereanydeal.com/games/storelow/v2?key={itad_key}&country={country}&shops=61",
                batch,
            )
            if isinstance(data, list):
                for item in data:
                    itad_id = item.get("id", "")
                    appid = id_to_appid.get(itad_id)
                    lows = item.get("lows", [])
                    if appid and lows:
                        low = lows[0]
                        price = low.get("price", {})
                        result[appid] = {
                            "price": price.get("amount", 0),
                            "currency": price.get("currency", ""),
                            "cut": low.get("cut", 0),
                            "date": (low.get("timestamp") or "")[:10],
                        }
        except Exception as exc:
            _emit_error(on_error, f"ITAD storelow error: {exc}")
        _sleep_after_batch(sleep_fn)
    return result


def _best_other_price(price_deals: list[dict]) -> tuple[float | None, dict | None]:
    steam_price = None
    best_other = None
    for price_deal in price_deals:
        shop = price_deal.get("shop", {})
        shop_id = shop.get("id", 0)
        price = price_deal.get("price", {}).get("amount", 0)
        if shop_id == 61:
            steam_price = price
        elif best_other is None or price < best_other["price"]:
            best_other = {
                "store": shop.get("name", "?"),
                "price": price,
                "url": price_deal.get("url", ""),
            }
    return steam_price, best_other


def itad_get_current_prices(
    itad_ids: dict[str, str],
    itad_key: str,
    country: str = "MX",
    *,
    post_json,
    sleep_fn=time.sleep,
    on_error=None,
) -> dict[str, dict]:
    """Current best prices across stores. Returns {appid: {store, price, url}} only when another store beats Steam."""
    id_to_appid, all_ids = _id_map(itad_ids)
    result: dict[str, dict] = {}
    for batch in _chunked(all_ids):
        try:
            data = post_json(
                f"https://api.isthereanydeal.com/games/prices/v3?key={itad_key}&country={country}",
                batch,
            )
            if isinstance(data, list):
                for item in data:
                    appid = id_to_appid.get(item.get("id", ""))
                    if not appid:
                        continue
                    steam_price, best_other = _best_other_price(item.get("deals", []))
                    if best_other and steam_price is not None and best_other["price"] < steam_price:
                        result[appid] = best_other
        except Exception as exc:
            _emit_error(on_error, f"ITAD prices error: {exc}")
        _sleep_after_batch(sleep_fn)
    return result


def itad_get_active_bundles(
    itad_ids: dict[str, str],
    itad_key: str,
    country: str = "US",
    *,
    post_json,
    sleep_fn=time.sleep,
    on_error=None,
) -> dict[str, list[dict]]:
    """Active bundles containing deal games. Returns {appid: [{title, store, price, currency, url}]}."""
    id_to_appid, all_ids = _id_map(itad_ids)
    result: dict[str, list[dict]] = {}
    for batch in _chunked(all_ids):
        try:
            data = post_json(
                f"https://api.isthereanydeal.com/games/overview/v2?key={itad_key}&country={country}",
                batch,
            )
            bundles = data.get("bundles", []) if isinstance(data, dict) else []
            for bundle in bundles:
                title = bundle.get("title", "")
                page = bundle.get("page", {})
                store = page.get("name", "")
                url = bundle.get("url", "")
                for tier in bundle.get("tiers", []):
                    price = tier.get("price") or {}
                    entry = {
                        "title": title,
                        "store": store,
                        "price": price.get("amount", 0),
                        "currency": price.get("currency", "USD"),
                        "url": url,
                    }
                    for game in tier.get("games", []):
                        appid = id_to_appid.get(game.get("id", ""))
                        if not appid:
                            continue
                        result.setdefault(appid, [])
                        if not any(bundle_entry["title"] == title for bundle_entry in result[appid]):
                            result[appid].append(entry)
        except Exception as exc:
            _emit_error(on_error, f"ITAD bundles error: {exc}")
        _sleep_after_batch(sleep_fn)
    return result
