from __future__ import annotations

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
