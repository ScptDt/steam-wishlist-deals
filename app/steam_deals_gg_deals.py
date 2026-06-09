from __future__ import annotations

from pathlib import Path

from app.steam_deals_external_offers import normalize_external_offers


GG_DEALS_SOURCE = "gg_deals"
GG_DEALS_RETAIL_STORE_ID = "gg_deals"
GG_DEALS_KEYSHOPS_STORE_ID = "gg_deals_keyshops"


def gg_deals_prices_to_external_offers(
    payload,
    *,
    region: str = "us",
    include_keyshops: bool = True,
    include_marketplaces: bool = False,
) -> dict:
    """Normalize fixture/local GG.deals prices data into external_offers."""
    records = _gg_deals_price_records(
        payload,
        region=region,
        include_keyshops=include_keyshops,
    )
    return normalize_external_offers(
        {"offers": records},
        include_marketplaces=include_marketplaces,
    )


def gg_deals_external_offers_from_cache(
    cache_payload,
    *,
    appids: list[str] | set[str] | tuple[str, ...] | None = None,
    region: str = "us",
    include_keyshops: bool = True,
    include_marketplaces: bool = False,
) -> dict | None:
    """Return normalized external_offers from a local GG.deals cache payload."""
    if not isinstance(cache_payload, dict):
        return None
    offers = gg_deals_prices_to_external_offers(
        _gg_deals_cache_payload_for_appids(cache_payload, appids),
        region=region,
        include_keyshops=include_keyshops,
        include_marketplaces=include_marketplaces,
    )
    return offers if offers.get("items") else None


def load_gg_deals_external_offers_cache(
    cache_file: Path,
    *,
    load_json_file,
) -> dict:
    payload = load_json_file(Path(cache_file), {})
    return payload if isinstance(payload, dict) else {}


def _gg_deals_cache_payload_for_appids(cache_payload: dict, appids) -> dict:
    appid_filter = {str(appid) for appid in appids or [] if appid}
    if not appid_filter:
        return cache_payload
    data = cache_payload.get("data") if "data" in cache_payload else cache_payload
    if not isinstance(data, dict):
        return cache_payload
    filtered = {
        str(appid): item
        for appid, item in data.items()
        if str(appid) in appid_filter
    }
    if "data" in cache_payload:
        return {**cache_payload, "data": filtered}
    return filtered


def _gg_deals_price_records(payload, *, region: str, include_keyshops: bool) -> list[dict]:
    records: list[dict] = []
    for appid, item in _gg_deals_price_items(payload):
        prices = item.get("prices") if isinstance(item.get("prices"), dict) else {}
        currency = prices.get("currency")
        title = str(item.get("title") or item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        records.extend(
            _gg_deals_aggregate_records(
                appid,
                title=title,
                url=url,
                currency=currency,
                region=region,
                prices=prices,
                include_keyshops=include_keyshops,
            )
        )
    return records


def _gg_deals_price_items(payload) -> list[tuple[str, dict]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data") if "data" in payload else payload
    if not isinstance(data, dict):
        return []
    items: list[tuple[str, dict]] = []
    for appid, item in data.items():
        clean_appid = str(appid or "").strip()
        if clean_appid and isinstance(item, dict):
            items.append((clean_appid, item))
    return items


def _gg_deals_aggregate_records(
    appid: str,
    *,
    title: str,
    url: str,
    currency,
    region: str,
    prices: dict,
    include_keyshops: bool,
) -> list[dict]:
    records: list[dict] = []
    if _has_price_value(prices.get("currentRetail")):
        records.append(
            _gg_deals_offer_record(
                appid,
                title=title,
                store_id=GG_DEALS_RETAIL_STORE_ID,
                price=prices.get("currentRetail"),
                currency=currency,
                url=url,
                region=region,
                confidence="medium",
            )
        )
    if include_keyshops and _has_price_value(prices.get("currentKeyshops")):
        records.append(
            _gg_deals_offer_record(
                appid,
                title=title,
                store_id=GG_DEALS_KEYSHOPS_STORE_ID,
                price=prices.get("currentKeyshops"),
                currency=currency,
                url=url,
                region=region,
                confidence="medium",
            )
        )
    return records


def _has_price_value(value) -> bool:
    return value is not None and str(value).strip() != ""


def _gg_deals_offer_record(
    appid: str,
    *,
    title: str,
    store_id: str,
    price,
    currency,
    url: str,
    region: str,
    confidence: str,
) -> dict:
    return {
        "appid": appid,
        "name": title,
        "store_id": store_id,
        "store_name": store_id,
        "price": price,
        "currency": currency,
        "url": url,
        "drm": "unknown",
        "region": region,
        "source": GG_DEALS_SOURCE,
        "confidence": confidence,
    }
