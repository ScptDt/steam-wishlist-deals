from __future__ import annotations

import re
import time
from pathlib import Path

from app.steam_deals_external_offers import normalize_external_offers


ITAD_BATCH = 50
ITAD_PRICES_BATCH = 200
ITAD_EXTERNAL_OFFERS_CACHE_VERSION = 1
ITAD_EXTERNAL_OFFERS_DEFAULT_CAPACITY = 3
ITAD_AUTH_HTTP_CODES = {401, 403}
_STEAM_SHOP_KEYS = {"steam", "steamstore"}


def itad_prices_to_external_offers(
    price_payload,
    appid_to_itad_id: dict[str, str],
    *,
    country: str = "MX",
    include_marketplaces: bool = False,
) -> dict:
    """Normalize ITAD prices/v3-shaped data into the safe external_offers contract."""
    records = _itad_price_records(price_payload, appid_to_itad_id, country=country)
    return normalize_external_offers(
        {"offers": records}, include_marketplaces=include_marketplaces
    )


def itad_deals_v2_to_external_offers(
    payload,
    *,
    itad_id_to_appid: dict[str, str] | None = None,
    country: str = "MX",
    include_marketplaces: bool = False,
) -> dict:
    """Normalize ITAD deals/v2-shaped data into the safe external_offers contract."""
    records = _itad_deals_v2_records(
        payload,
        itad_id_to_appid=itad_id_to_appid,
        country=country,
    )
    return normalize_external_offers(
        {"offers": records}, include_marketplaces=include_marketplaces
    )


def build_itad_external_offers_cache(
    price_payload,
    appid_to_itad_id: dict[str, str],
    *,
    country: str = "MX",
    fetched_at: str = "",
    deals_only: bool = True,
    capacity: int = ITAD_EXTERNAL_OFFERS_DEFAULT_CAPACITY,
) -> dict:
    """Build a small local cache payload for ITAD external_offers data."""
    return {
        "version": ITAD_EXTERNAL_OFFERS_CACHE_VERSION,
        "source": "itad",
        "country": country,
        "fetched_at": _itad_date_text(fetched_at),
        "options": {
            "deals_only": bool(deals_only),
            "capacity": _non_negative_int(capacity),
        },
        "appid_to_itad_id": {
            str(appid): str(itad_id)
            for appid, itad_id in (appid_to_itad_id or {}).items()
            if appid and itad_id
        },
        "prices": _itad_price_items(price_payload),
    }


def itad_external_offers_from_cache(
    cache_payload,
    *,
    appids: list[str] | set[str] | tuple[str, ...] | None = None,
    include_marketplaces: bool = False,
) -> dict | None:
    """Return normalized external_offers from a local ITAD cache payload."""
    if not isinstance(cache_payload, dict):
        return None
    mapping = cache_payload.get("appid_to_itad_id")
    if not isinstance(mapping, dict):
        return None
    appid_filter = {str(appid) for appid in appids or [] if appid}
    appid_to_itad_id = {
        str(appid): str(itad_id)
        for appid, itad_id in mapping.items()
        if appid and itad_id and (not appid_filter or str(appid) in appid_filter)
    }
    if not appid_to_itad_id:
        return None
    price_payload = cache_payload.get("prices")
    if price_payload is None:
        price_payload = cache_payload.get("items") or cache_payload.get("data")
    offers = itad_prices_to_external_offers(
        price_payload,
        appid_to_itad_id,
        country=str(cache_payload.get("country") or "MX"),
        include_marketplaces=include_marketplaces,
    )
    return offers if offers.get("items") else None


def diagnose_itad_external_offers_cache(
    cache_payload,
    *,
    appids: list[str] | set[str] | tuple[str, ...] | None = None,
    include_marketplaces: bool = False,
) -> dict:
    """Diagnose a local ITAD external_offers cache without I/O or ranking changes."""
    issues: list[dict] = []
    if cache_payload is None:
        cache_payload = {}
        issues.append(_itad_cache_issue("warning", "cache_empty", "caché ITAD external_offers vacía"))
    elif not isinstance(cache_payload, dict):
        issue = _itad_cache_issue(
            "error",
            "invalid_itad_external_offers_cache",
            "la caché ITAD external_offers debe ser un objeto JSON",
        )
        summary = _itad_cache_diagnostic_summary([], price_payload_items_count=0)
        return {"status": "error", "items": [], "issues": [issue], "summary": summary}
    elif not cache_payload:
        issues.append(_itad_cache_issue("warning", "cache_empty", "caché ITAD external_offers vacía"))

    mapping_value = cache_payload.get("appid_to_itad_id")
    mapping = _itad_cache_mapping(mapping_value)
    issues.extend(_itad_cache_mapping_issues(mapping_value, mapping, cache_empty=not cache_payload))

    price_payload, price_source = _itad_cache_price_payload(cache_payload)
    price_items = _itad_price_items(price_payload)
    issues.extend(
        _itad_cache_price_payload_issues(
            price_payload,
            price_source,
            price_items_count=len(price_items),
            cache_empty=not cache_payload,
        )
    )

    price_items_by_id = _itad_cache_price_items_by_id(price_items)
    checked_appids = _itad_cache_checked_appids(mapping, appids)
    country = str(cache_payload.get("country") or "MX")
    items = [
        _itad_cache_diagnostic_item(
            appid,
            mapping,
            price_items_by_id,
            country=country,
            include_marketplaces=include_marketplaces,
        )
        for appid in checked_appids
    ]
    summary = _itad_cache_diagnostic_summary(items, price_payload_items_count=len(price_items))
    return {
        "status": _itad_cache_diagnostic_status(issues, items),
        "items": items,
        "issues": issues,
        "summary": summary,
    }


def load_itad_external_offers_cache(
    cache_file: Path,
    *,
    load_json_file,
) -> dict:
    payload = load_json_file(Path(cache_file), {})
    return payload if isinstance(payload, dict) else {}


def save_itad_external_offers_cache(
    cache_file: Path,
    payload: dict,
    *,
    write_json_file,
) -> None:
    write_json_file(Path(cache_file), payload, ensure_ascii=False, indent=2)


def _itad_price_records(price_payload, appid_to_itad_id: dict[str, str], *, country: str) -> list[dict]:
    id_to_appid = {str(itad_id): str(appid) for appid, itad_id in appid_to_itad_id.items()}
    records: list[dict] = []
    for item in _itad_price_items(price_payload):
        appid = id_to_appid.get(str(item.get("id") or ""))
        if not appid:
            continue
        for deal in item.get("deals", []):
            if isinstance(deal, dict) and not _itad_is_steam_deal(deal):
                records.append(_itad_deal_record(item, deal, appid, country=country))
    return records


def _itad_deals_v2_records(payload, *, itad_id_to_appid: dict[str, str] | None, country: str) -> list[dict]:
    id_to_appid = {
        str(itad_id): str(appid)
        for itad_id, appid in (itad_id_to_appid or {}).items()
        if itad_id and appid
    }
    records: list[dict] = []
    for item in _itad_deals_v2_items(payload):
        deal = item.get("deal") if isinstance(item.get("deal"), dict) else None
        if not deal or _itad_is_steam_deal(deal):
            continue
        records.append(
            _itad_deal_record(
                item,
                deal,
                _itad_deals_v2_appid(item, id_to_appid),
                country=country,
            )
        )
    return records


def _itad_deals_v2_items(payload) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("list", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _itad_deals_v2_appid(item: dict, id_to_appid: dict[str, str]) -> str:
    direct = str(item.get("appid") or item.get("steam_appid") or "").strip()
    if direct:
        return direct
    return id_to_appid.get(str(item.get("id") or "").strip(), "")


def _itad_price_items(price_payload) -> list[dict]:
    if isinstance(price_payload, list):
        return [item for item in price_payload if isinstance(item, dict)]
    if not isinstance(price_payload, dict):
        return []
    for key in ("items", "prices", "data"):
        value = price_payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _itad_cache_mapping(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(appid).strip(): str(itad_id).strip()
        for appid, itad_id in value.items()
        if str(appid).strip() and str(itad_id).strip()
    }


def _itad_cache_mapping_issues(mapping_value, mapping: dict[str, str], *, cache_empty: bool) -> list[dict]:
    if cache_empty:
        return []
    if mapping_value is None:
        return [
            _itad_cache_issue(
                "warning",
                "missing_appid_mapping",
                "la caché no incluye appid_to_itad_id",
            )
        ]
    if not isinstance(mapping_value, dict):
        return [
            _itad_cache_issue(
                "error",
                "invalid_appid_mapping",
                "appid_to_itad_id debe ser un objeto",
            )
        ]
    if not mapping:
        return [
            _itad_cache_issue(
                "warning",
                "appid_mapping_empty",
                "appid_to_itad_id no contiene mappings válidos",
            )
        ]
    return []


def _itad_cache_price_payload(cache_payload: dict) -> tuple[object | None, str]:
    for key in ("prices", "items", "data"):
        if key in cache_payload:
            return cache_payload.get(key), key
    return None, ""


def _itad_cache_price_payload_issues(
    price_payload,
    price_source: str,
    *,
    price_items_count: int,
    cache_empty: bool,
) -> list[dict]:
    if cache_empty:
        return []
    if not price_source:
        return [
            _itad_cache_issue(
                "warning",
                "missing_price_payload",
                "la caché no incluye prices/items/data",
            )
        ]
    if isinstance(price_payload, list):
        malformed_count = sum(1 for item in price_payload if not isinstance(item, dict))
        if malformed_count:
            return [
                _itad_cache_issue(
                    "warning",
                    "malformed_price_items",
                    f"{malformed_count} entradas de precios ITAD no son objetos",
                )
            ]
        return []
    if isinstance(price_payload, dict):
        has_collection = any(isinstance(price_payload.get(key), list) for key in ("items", "prices", "data"))
        if has_collection or price_items_count:
            return []
    return [
        _itad_cache_issue(
            "error",
            "invalid_price_payload",
            f"{price_source} debe ser una lista o contener items/prices/data como lista",
        )
    ]


def _itad_cache_price_items_by_id(price_items: list[dict]) -> dict[str, dict]:
    items_by_id: dict[str, dict] = {}
    for item in price_items:
        itad_id = str(item.get("id") or "").strip()
        if itad_id and itad_id not in items_by_id:
            items_by_id[itad_id] = item
    return items_by_id


def _itad_cache_checked_appids(mapping: dict[str, str], appids) -> list[str]:
    candidates = list(appids or mapping.keys())
    checked: list[str] = []
    seen: set[str] = set()
    for appid in candidates:
        value = str(appid).strip()
        if value and value not in seen:
            checked.append(value)
            seen.add(value)
    return checked


def _itad_cache_diagnostic_item(
    appid: str,
    mapping: dict[str, str],
    price_items_by_id: dict[str, dict],
    *,
    country: str,
    include_marketplaces: bool,
) -> dict:
    itad_id = mapping.get(appid, "")
    if not itad_id:
        return _itad_cache_appid_item(appid, "warning", "missing_itad_mapping", "appid sin mapping ITAD")
    price_item = price_items_by_id.get(itad_id)
    if price_item is None:
        return _itad_cache_appid_item(
            appid,
            "warning",
            "missing_price_payload",
            "appid con mapping ITAD pero sin payload de precios",
            itad_id=itad_id,
        )
    try:
        offers = itad_prices_to_external_offers(
            [price_item], {appid: itad_id}, country=country, include_marketplaces=include_marketplaces
        )
    except Exception as exc:
        return _itad_cache_appid_item(
            appid,
            "malformed",
            "price_payload_malformed",
            f"payload de precios ITAD inválido: {exc}",
            itad_id=itad_id,
            has_price_payload=True,
        )
    return _itad_cache_offer_item(appid, itad_id, offers)


def _itad_cache_appid_item(
    appid: str,
    status: str,
    code: str,
    message: str,
    *,
    itad_id: str = "",
    has_price_payload: bool = False,
) -> dict:
    item = {
        "appid": appid,
        "status": status,
        "code": code,
        "message": message,
        "has_price_payload": has_price_payload,
        "has_external_offers": False,
        "offers_count": 0,
        "highlight_count": 0,
        "review_count": 0,
        "hidden_count": 0,
        "visible_count": 0,
        "risky_offer_count": 0,
        "risk_counts": {},
    }
    if itad_id:
        item["itad_id"] = itad_id
    return item


def _itad_cache_offer_item(appid: str, itad_id: str, offers: dict) -> dict:
    offer_items = offers.get("items") if isinstance(offers, dict) else []
    offer_items = offer_items if isinstance(offer_items, list) else []
    summary = offers.get("summary") if isinstance(offers, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    visible_count = int(summary.get("highlight_count") or 0) + int(summary.get("review_count") or 0)
    hidden_count = int(summary.get("hidden_count") or 0)
    offers_count = len(offer_items)
    if not offers_count:
        status, code, message = "warning", "no_external_offers", "payload ITAD sin ofertas externas normalizables"
    elif not visible_count:
        status, code, message = "warning", "hidden_offers_only", "solo hay ofertas ocultas por risk gates"
    elif hidden_count:
        status, code, message = "warning", "offers_available_with_hidden_risks", "hay ofertas visibles y otras ocultas por risk gates"
    else:
        status, code, message = "ok", "offers_available", "ofertas externas normalizadas disponibles"
    item = _itad_cache_appid_item(
        appid,
        status,
        code,
        message,
        itad_id=itad_id,
        has_price_payload=True,
    )
    item.update(
        {
            "has_external_offers": bool(offers_count),
            "offers_count": offers_count,
            "highlight_count": int(summary.get("highlight_count") or 0),
            "review_count": int(summary.get("review_count") or 0),
            "hidden_count": hidden_count,
            "visible_count": visible_count,
            "risky_offer_count": _itad_cache_risky_offer_count(offer_items),
            "risk_counts": _itad_cache_risk_counts(offer_items),
        }
    )
    return item


def _itad_cache_diagnostic_summary(items: list[dict], *, price_payload_items_count: int) -> dict:
    appids_count = len(items)
    mapped_count = sum(1 for item in items if item.get("itad_id"))
    price_payload_appids_count = sum(1 for item in items if item.get("has_price_payload"))
    external_offer_appids_count = sum(1 for item in items if item.get("has_external_offers"))
    return {
        "appids_count": appids_count,
        "mapped_appids_count": mapped_count,
        "missing_mapping_count": sum(1 for item in items if item.get("code") == "missing_itad_mapping"),
        "appids_with_price_payload_count": price_payload_appids_count,
        "missing_price_payload_count": sum(1 for item in items if item.get("code") == "missing_price_payload"),
        "appids_with_external_offers_count": external_offer_appids_count,
        "visible_appids_count": sum(1 for item in items if item.get("visible_count", 0) > 0),
        "hidden_only_appids_count": sum(1 for item in items if item.get("code") == "hidden_offers_only"),
        "malformed_count": sum(1 for item in items if item.get("status") == "malformed"),
        "price_payload_items_count": price_payload_items_count,
        "offers_count": sum(int(item.get("offers_count") or 0) for item in items),
        "highlight_count": sum(int(item.get("highlight_count") or 0) for item in items),
        "review_count": sum(int(item.get("review_count") or 0) for item in items),
        "hidden_count": sum(int(item.get("hidden_count") or 0) for item in items),
        "risky_offer_count": sum(int(item.get("risky_offer_count") or 0) for item in items),
        "risk_counts": _itad_cache_merged_risk_counts(items),
        "coverage": {
            "mapping": _itad_cache_ratio(mapped_count, appids_count),
            "price_payload": _itad_cache_ratio(price_payload_appids_count, appids_count),
            "external_offers": _itad_cache_ratio(external_offer_appids_count, appids_count),
        },
        "advisory_only": True,
        "ranking_impact": "none",
    }


def _itad_cache_diagnostic_status(issues: list[dict], items: list[dict]) -> str:
    if any(issue.get("severity") == "error" for issue in issues):
        return "error"
    if issues or any(item.get("status") != "ok" for item in items):
        return "warning"
    return "ok"


def _itad_cache_risky_offer_count(offer_items: list[dict]) -> int:
    return sum(
        1
        for item in offer_items
        if set(item.get("risk_flags") or []) - {"ownership_not_proven"}
    )


def _itad_cache_risk_counts(offer_items: list[dict]) -> dict[str, int]:
    risk_counts: dict[str, int] = {}
    for item in offer_items:
        for risk in item.get("risk_flags") or []:
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
    return risk_counts


def _itad_cache_merged_risk_counts(items: list[dict]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for item in items:
        risk_counts = item.get("risk_counts") or {}
        for risk, count in risk_counts.items():
            merged[risk] = merged.get(risk, 0) + int(count)
    return merged


def _itad_cache_ratio(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0


def _itad_cache_issue(severity: str, code: str, message: str) -> dict:
    return {"severity": severity, "code": code, "message": message}


def _itad_deal_record(item: dict, deal: dict, appid: str, *, country: str) -> dict:
    price = deal.get("price") if isinstance(deal.get("price"), dict) else {}
    regular = deal.get("regular") if isinstance(deal.get("regular"), dict) else {}
    shop = deal.get("shop") if isinstance(deal.get("shop"), dict) else {}
    shop_name = _itad_shop_name(shop)
    return {
        "appid": appid,
        "name": _itad_game_title(item),
        "store": shop_name,
        "store_name": shop_name,
        "price": _itad_price_amount(price),
        "currency": _itad_price_currency(price, regular),
        "discount_pct": deal.get("cut"),
        "url": deal.get("url"),
        "drm": _itad_drm(deal.get("drm")),
        "region": country,
        "source": "itad",
        "confidence": "high",
        "observed_at": _itad_date_text(deal.get("timestamp")),
        "expires_at": _itad_date_text(deal.get("expiry")),
    }


def _itad_is_steam_deal(deal: dict) -> bool:
    shop = deal.get("shop") if isinstance(deal.get("shop"), dict) else {}
    return _itad_slug(_itad_shop_name(shop)) in _STEAM_SHOP_KEYS


def _itad_shop_name(shop: dict) -> str:
    return str(shop.get("name") or shop.get("title") or shop.get("shop") or "").strip()


def _itad_game_title(item: dict) -> str:
    game = item.get("game") if isinstance(item.get("game"), dict) else {}
    return str(item.get("title") or item.get("name") or game.get("title") or "").strip()


def _itad_price_amount(price: dict):
    amount = price.get("amount")
    if amount not in (None, ""):
        return amount
    try:
        return int(price.get("amountInt")) / 100
    except (TypeError, ValueError):
        return None


def _itad_price_currency(price: dict, regular: dict) -> str:
    return str(price.get("currency") or regular.get("currency") or "").strip().upper()


def _itad_drm(value) -> str:
    labels = [_itad_slug(label) for label in _itad_labels(value)]
    labels = [label for label in labels if label]
    if "steam" in labels:
        return "steam"
    return labels[0] if labels else "unknown"


def _itad_labels(value) -> list[str]:
    if isinstance(value, list):
        labels: list[str] = []
        for item in value:
            if isinstance(item, dict):
                labels.append(str(item.get("name") or item.get("title") or item.get("id") or ""))
            else:
                labels.append(str(item or ""))
        return labels
    if isinstance(value, dict):
        return [str(value.get("name") or value.get("title") or value.get("id") or "")]
    return [str(value or "")]


def _itad_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _itad_date_text(value) -> str:
    return str(value or "").strip()


def _non_negative_int(value) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _itad_lookup_appids(appids: list[str]) -> list[str]:
    return [str(appid).strip() for appid in appids if str(appid).strip().isdigit()]


def _chunked(items: list[str], size: int = ITAD_BATCH):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _sleep_after_batch(sleep_fn, seconds: float = 0.5) -> None:
    sleep_fn(seconds)


def _emit_error(on_error, message: str) -> None:
    if on_error is not None:
        on_error(message)


def _http_status_code(exc) -> int | None:
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(exc, "status", None)
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def _is_itad_auth_error(exc) -> bool:
    return _http_status_code(exc) in ITAD_AUTH_HTTP_CODES


def _itad_auth_error_message(operation: str, exc) -> str:
    code = _http_status_code(exc)
    status = f"HTTP {code}" if code is not None else "HTTP auth"
    return (
        f"{operation}: {status} "
        "(ITAD rechazó la API key; rota/regenera STEAM_TOOLS_ITAD_API_KEY "
        "o revisa la config local)"
    )


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
            if _is_itad_auth_error(exc):
                _emit_error(on_error, _itad_auth_error_message("ITAD lookup auth error", exc))
                break
            _emit_error(on_error, f"ITAD lookup error: {exc}")
        _sleep_after_batch(sleep_fn)
    return result


def itad_lookup_games_by_appid(
    appids: list[str],
    itad_key: str,
    *,
    get_json,
    sleep_fn=time.sleep,
    on_error=None,
) -> dict[str, str]:
    """Resolve Steam appids to ITAD IDs using header-auth GET lookups."""
    result: dict[str, str] = {}
    for appid in _itad_lookup_appids(appids):
        try:
            data = get_json(
                f"https://api.isthereanydeal.com/games/lookup/v1?appid={appid}",
                headers={"ITAD-API-Key": itad_key},
            )
            game = data.get("game") if isinstance(data, dict) else None
            if isinstance(game, dict) and data.get("found") and game.get("id"):
                result[appid] = str(game["id"])
        except Exception as exc:
            if _is_itad_auth_error(exc):
                _emit_error(on_error, _itad_auth_error_message("ITAD appid lookup auth error", exc))
                break
            _emit_error(on_error, f"ITAD appid lookup error: {exc}")
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
            if _is_itad_auth_error(exc):
                _emit_error(on_error, _itad_auth_error_message("ITAD storelow auth error", exc))
                break
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
            if _is_itad_auth_error(exc):
                _emit_error(on_error, _itad_auth_error_message("ITAD prices auth error", exc))
                break
            _emit_error(on_error, f"ITAD prices error: {exc}")
        _sleep_after_batch(sleep_fn)
    return result


def itad_get_prices_payload(
    itad_ids: dict[str, str],
    itad_key: str,
    country: str = "MX",
    *,
    post_json,
    sleep_fn=time.sleep,
    on_error=None,
    deals_only: bool = True,
    capacity: int = ITAD_EXTERNAL_OFFERS_DEFAULT_CAPACITY,
) -> list[dict]:
    """Fetch raw ITAD prices/v3 items for explicit external_offers cache refresh."""
    _id_to_appid, all_ids = _id_map(itad_ids)
    items: list[dict] = []
    errors: list[str] = []
    deals_param = str(bool(deals_only)).lower()
    capacity_param = _non_negative_int(capacity)
    for batch in _chunked(all_ids, ITAD_PRICES_BATCH):
        try:
            data = post_json(
                "https://api.isthereanydeal.com/games/prices/v3"
                f"?country={country}&deals={deals_param}&capacity={capacity_param}",
                batch,
                headers={"ITAD-API-Key": itad_key},
            )
            items.extend(_itad_price_items(data))
        except TypeError:
            message = "ITAD external offers prices error: post_json no acepta headers"
            errors.append(message)
            _emit_error(on_error, message)
        except Exception as exc:
            if _is_itad_auth_error(exc):
                message = _itad_auth_error_message(
                    "ITAD external offers prices auth error",
                    exc,
                )
                errors.append(message)
                _emit_error(on_error, message)
                break
            message = f"ITAD external offers prices error: {exc}"
            errors.append(message)
            _emit_error(on_error, message)
        _sleep_after_batch(sleep_fn)
    if errors:
        raise RuntimeError("; ".join(errors))
    return items


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
            if _is_itad_auth_error(exc):
                _emit_error(on_error, _itad_auth_error_message("ITAD bundles auth error", exc))
                break
            _emit_error(on_error, f"ITAD bundles error: {exc}")
        _sleep_after_batch(sleep_fn)
    return result
