from __future__ import annotations

import re
from decimal import Decimal
from decimal import InvalidOperation
from urllib.parse import unquote
from urllib.parse import urlsplit


_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
_HIGHLIGHT_STORE_TYPES = {"official_store", "authorized_key_reseller"}
_REVIEWABLE_STORE_TYPES = _HIGHLIGHT_STORE_TYPES | {"steam", "manual_import"}
_CHECKOUT_LIKE_PATTERN = re.compile(
    r"(^|[/?#&=._-])(cart|checkout|add-to-cart|addtocart|payment|purchase)s?([/?#&=._-]|$)"
)
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_RISK_ORDER = (
    "appid_missing",
    "unknown_store",
    "marketplace_keyshop",
    "aggregator_source",
    "drm_unknown",
    "region_unknown",
    "low_confidence",
    "checkout_like_url",
    "unsafe_url_scheme",
    "invalid_price",
    "currency_missing",
    "invalid_currency",
    "ownership_not_proven",
)
_STORE_REGISTRY = {
    "steam": {"store_name": "Steam", "store_type": "steam"},
    "gog": {"store_name": "GOG", "store_type": "official_store"},
    "epic": {"store_name": "Epic Games Store", "store_type": "official_store"},
    "microsoft": {"store_name": "Microsoft Store", "store_type": "official_store"},
    "humble": {"store_name": "Humble Store", "store_type": "official_store"},
    "fanatical": {"store_name": "Fanatical", "store_type": "authorized_key_reseller"},
    "greenmangaming": {"store_name": "Green Man Gaming", "store_type": "authorized_key_reseller"},
    "gamesplanet": {"store_name": "Gamesplanet", "store_type": "authorized_key_reseller"},
    "itad": {"store_name": "IsThereAnyDeal", "store_type": "aggregator"},
    "g2a": {"store_name": "G2A", "store_type": "marketplace_keyshop"},
    "kinguin": {"store_name": "Kinguin", "store_type": "marketplace_keyshop"},
    "eneba": {"store_name": "Eneba", "store_type": "marketplace_keyshop"},
    "cdkeys": {"store_name": "CDKeys", "store_type": "marketplace_keyshop"},
}
_STORE_ALIASES = {
    "steamstore": "steam",
    "gogcom": "gog",
    "epicgames": "epic",
    "epicgamesstore": "epic",
    "microsoftstore": "microsoft",
    "xboxstore": "microsoft",
    "humblestore": "humble",
    "humblebundle": "humble",
    "greenmangaming": "greenmangaming",
    "gmg": "greenmangaming",
    "isthereanydeal": "itad",
    "itad": "itad",
    "manual": "manual_import",
    "manualimport": "manual_import",
}
_STORE_REGISTRY["manual_import"] = {"store_name": "Manual import", "store_type": "manual_import"}


def normalize_external_offers(payload, *, include_marketplaces: bool = False) -> dict:
    """Normalize local fixture-only store offers into a safe external_offers contract."""
    records = _offer_records(payload)
    offers = [
        offer
        for index, record in enumerate(records)
        if (offer := _normalize_offer(record, index, include_marketplaces=include_marketplaces))
    ]
    items = [_public_offer(offer) for offer in _sort_offers(_dedupe_offers(offers))]
    return {"items": items, "summary": _summary(items)}


def _offer_records(payload) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return _copy_offer_records(payload, context="external_offers")
    if isinstance(payload, dict):
        if not payload:
            return []
        for key in ("external_offers", "offers", "items"):
            if key in payload:
                value = payload[key]
                if isinstance(value, dict) and key == "external_offers" and "items" in value:
                    value = value["items"]
                return _copy_offer_records(value, context=key)
        raise ValueError(
            "debe ser una lista o un objeto con clave 'external_offers', 'offers' o 'items'"
        )
    raise ValueError("debe ser una lista o un objeto JSON")


def _copy_offer_records(records, *, context: str) -> list[dict]:
    if records is None:
        return []
    if not isinstance(records, list):
        raise ValueError(f"{context} debe ser una lista")
    copied: list[dict] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"{context}[{index}] debe ser un objeto JSON")
        copied.append(dict(record))
    return copied


def _normalize_offer(record: dict, index: int, *, include_marketplaces: bool) -> dict | None:
    if not any(_clean_text(value) for value in record.values()):
        return None
    appid = _clean_text(_first(record, "appid", "steam_appid", "wishlist_appid"))
    store_id, store_name, store_type = _store_metadata(record)
    price = _price(record)
    currency = _currency(record)
    drm = _slug(_first(record, "drm", "platform")) or "unknown"
    region = _slug(_first(record, "region", "country")) or "unknown"
    confidence = _confidence(record)
    raw_url = _clean_text(_first(record, "url", "link"))
    checkout_like = _is_checkout_like_url(raw_url)
    unsafe_url_scheme = _is_unsafe_url_scheme(raw_url)
    risk_flags = _risk_flags(
        appid,
        store_type,
        confidence,
        price,
        currency,
        drm,
        region,
        checkout_like,
        unsafe_url_scheme,
    )
    visibility = _visibility(
        appid,
        store_type,
        confidence,
        price,
        currency,
        drm,
        region,
        checkout_like,
        unsafe_url_scheme,
        include_marketplaces=include_marketplaces,
    )
    return {
        "appid": appid,
        "name": _clean_text(_first(record, "name", "title", "steam_name")),
        "store_id": store_id,
        "store_name": store_name,
        "store_type": store_type,
        "price": price,
        "currency": currency,
        "discount_pct": _discount_pct(record),
        "url": "" if checkout_like or unsafe_url_scheme else raw_url,
        "link_allowed": bool(raw_url) and not checkout_like and not unsafe_url_scheme,
        "drm": drm,
        "region": region,
        "source": _clean_text(record.get("source")) or "fixture",
        "confidence": confidence,
        "observed_at": _clean_text(_first(record, "observed_at", "seen_at")),
        "expires_at": _clean_text(_first(record, "expires_at", "valid_until")) or None,
        "visibility": visibility,
        "eligible_for_best_external_price": visibility == "highlight"
        and store_type in _HIGHLIGHT_STORE_TYPES,
        "risk_flags": risk_flags,
        "_index": index,
    }


def _store_metadata(record: dict) -> tuple[str, str, str]:
    raw_store = _first(record, "store_id", "store", "storefront", "shop", "store_name")
    lookup_key = _store_lookup_key(raw_store)
    canonical_id = _STORE_ALIASES.get(lookup_key, lookup_key)
    if canonical_id in _STORE_REGISTRY:
        info = _STORE_REGISTRY[canonical_id]
        return canonical_id, info["store_name"], info["store_type"]
    store_id = _slug(raw_store) or "unknown"
    raw_name = _clean_text(_first(record, "store_name", "store", "storefront", "shop"))
    return store_id, raw_name or "Unknown", "unknown"


def _risk_flags(
    appid: str,
    store_type: str,
    confidence: str,
    price: float | None,
    currency: str,
    drm: str,
    region: str,
    checkout_like: bool,
    unsafe_url_scheme: bool,
) -> list[str]:
    flags = {"ownership_not_proven"}
    if not appid:
        flags.add("appid_missing")
    if store_type == "unknown":
        flags.add("unknown_store")
    if store_type == "marketplace_keyshop":
        flags.add("marketplace_keyshop")
    if store_type == "aggregator":
        flags.add("aggregator_source")
    if drm == "unknown":
        flags.add("drm_unknown")
    if region == "unknown":
        flags.add("region_unknown")
    if confidence == "low":
        flags.add("low_confidence")
    if checkout_like:
        flags.add("checkout_like_url")
    if unsafe_url_scheme:
        flags.add("unsafe_url_scheme")
    if price is None:
        flags.add("invalid_price")
    if not currency:
        flags.add("currency_missing")
    elif not _valid_currency(currency):
        flags.add("invalid_currency")
    return [flag for flag in _RISK_ORDER if flag in flags]


def _visibility(
    appid: str,
    store_type: str,
    confidence: str,
    price: float | None,
    currency: str,
    drm: str,
    region: str,
    checkout_like: bool,
    unsafe_url_scheme: bool,
    *,
    include_marketplaces: bool,
) -> str:
    if not appid or price is None or not _valid_currency(currency) or checkout_like or unsafe_url_scheme or confidence == "low":
        return "hidden"
    if store_type in {"unknown", "aggregator"}:
        return "hidden"
    if store_type == "marketplace_keyshop":
        return "review" if include_marketplaces else "hidden"
    if store_type not in _REVIEWABLE_STORE_TYPES:
        return "hidden"
    if confidence == "medium" or drm == "unknown" or region == "unknown":
        return "review"
    return "highlight"


def _dedupe_offers(offers: list[dict]) -> list[dict]:
    deduped: dict[tuple[str, str, str, str, str], dict] = {}
    for offer in offers:
        fingerprint = _fingerprint(offer)
        current = deduped.get(fingerprint)
        if current is None or _is_better_duplicate(offer, current):
            deduped[fingerprint] = offer
    return list(deduped.values())


def _is_better_duplicate(candidate: dict, current: dict) -> bool:
    candidate_valid = _has_valid_price(candidate)
    current_valid = _has_valid_price(current)
    if candidate_valid != current_valid:
        return candidate_valid
    if candidate_valid and candidate["price"] != current["price"]:
        return candidate["price"] < current["price"]
    if _CONFIDENCE_RANK[candidate["confidence"]] != _CONFIDENCE_RANK[current["confidence"]]:
        return _CONFIDENCE_RANK[candidate["confidence"]] > _CONFIDENCE_RANK[current["confidence"]]
    return candidate["_index"] < current["_index"]


def _sort_offers(offers: list[dict]) -> list[dict]:
    visibility_rank = {"highlight": 0, "review": 1, "hidden": 2}
    return sorted(
        offers,
        key=lambda offer: (
            visibility_rank[offer["visibility"]],
            _price_sort_value(offer["price"]),
            offer["name"].lower(),
            offer["store_name"].lower(),
            offer["_index"],
        ),
    )


def _summary(items: list[dict]) -> dict:
    risk_counts: dict[str, int] = {}
    for item in items:
        for flag in item["risk_flags"]:
            risk_counts[flag] = risk_counts.get(flag, 0) + 1
    return {
        "items_count": len(items),
        "highlight_count": sum(1 for item in items if item["visibility"] == "highlight"),
        "review_count": sum(1 for item in items if item["visibility"] == "review"),
        "hidden_count": sum(1 for item in items if item["visibility"] == "hidden"),
        "official_or_authorized_count": sum(
            1 for item in items if item["store_type"] in _HIGHLIGHT_STORE_TYPES
        ),
        "marketplace_count": sum(1 for item in items if item["store_type"] == "marketplace_keyshop"),
        "best_external_price_count": sum(
            1 for item in items if item["eligible_for_best_external_price"]
        ),
        "risk_counts": risk_counts,
        "advisory_only": True,
        "ranking_impact": "none",
    }


def _public_offer(offer: dict) -> dict:
    return {key: value for key, value in offer.items() if not key.startswith("_")}


def _fingerprint(offer: dict) -> tuple[str, str, str, str, str]:
    return (
        offer["appid"],
        offer["store_id"],
        offer["drm"],
        offer["region"],
        _normalized_url_key(offer["url"]),
    )


def _price(record: dict) -> float | None:
    return _decimal_to_float(_parse_decimal(_first(record, "price", "final_price", "amount")))


def _discount_pct(record: dict) -> int | None:
    value = _parse_decimal(_first(record, "discount_pct", "discount", "discount_percent"))
    if value is None or value < 0 or value > 100:
        return None
    return int(value)


def _parse_decimal(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = _clean_text(value)
    if not text:
        return None
    cleaned = re.sub(r"[^0-9,.-]+", "", text)
    if cleaned.count(",") == 1 and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        parsed = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed >= 0 and parsed.is_finite() else None


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.01")))


def _currency(record: dict) -> str:
    return _clean_text(_first(record, "currency", "currency_code")).upper()


def _confidence(record: dict) -> str:
    candidate = _slug(record.get("confidence"))
    return candidate if candidate in _CONFIDENCE_RANK else "low"


def _has_valid_price(offer: dict) -> bool:
    return offer["price"] is not None and _valid_currency(offer["currency"])


def _valid_currency(currency: str) -> bool:
    return bool(_CURRENCY_PATTERN.fullmatch(currency))


def _price_sort_value(value: float | None) -> float:
    return value if value is not None else float("inf")


def _is_checkout_like_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlsplit(url)
    candidate = unquote(" ".join((parsed.path, parsed.query, parsed.fragment))).lower()
    candidate = re.sub(r"[\s_]+", "-", candidate)
    return bool(_CHECKOUT_LIKE_PATTERN.search(candidate))


def _is_unsafe_url_scheme(url: str) -> bool:
    if not url:
        return False
    scheme = urlsplit(url).scheme.lower()
    return scheme not in {"http", "https"}


def _normalized_url_key(url: str) -> str:
    if not url:
        return ""
    parsed = urlsplit(url)
    path = unquote(parsed.path).rstrip("/").lower()
    query = unquote(parsed.query).lower()
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}?{query}"


def _store_lookup_key(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_text(value).lower())


def _slug(value) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _clean_text(value).lower()).strip("_")


def _clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first(record: dict, *keys: str):
    for key in keys:
        value = record.get(key)
        if _clean_text(value):
            return value
    return ""
