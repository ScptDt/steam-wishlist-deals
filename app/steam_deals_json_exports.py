from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.steam_deals_cache_policy import CACHE_STATE_COOLDOWN
from app.steam_deals_cache_policy import CACHE_STATE_FAILED_NO_DATA
from app.steam_deals_cache_policy import CACHE_STATE_FRESH
from app.steam_deals_cache_policy import CACHE_STATE_MISSING
from app.steam_deals_cache_policy import CACHE_STATE_PENDING_DEFERRED
from app.steam_deals_cache_policy import CACHE_STATE_STALE_USABLE


OFFERS_EXPORT_SCHEMA = "steam_deals_offers_export_v1"
WISHLIST_EXPORT_SCHEMA = "steam_deals_wishlist_export_v1"
REPORT_JSON_SCHEMA = "steam_deals_report_json"

EXPORT_CACHE_STATES = {
    "fresh",
    "stale_usable",
    "deferred",
    "cooldown",
    "failed_no_data",
    "missing",
    "unknown",
}
PARTIAL_CACHE_STATES = {"deferred", "cooldown", "failed_no_data", "missing"}
CONFIRMED_PRICE_STATES = {"fresh", "stale_usable"}
INTERNAL_CACHE_STATE_MAP = {
    CACHE_STATE_FRESH: "fresh",
    CACHE_STATE_STALE_USABLE: "stale_usable",
    CACHE_STATE_PENDING_DEFERRED: "deferred",
    CACHE_STATE_COOLDOWN: "cooldown",
    CACHE_STATE_FAILED_NO_DATA: "failed_no_data",
    CACHE_STATE_MISSING: "missing",
}
EXTERNAL_OFFER_EXPORT_KEYS = (
    "appid",
    "name",
    "store_id",
    "store_name",
    "store_type",
    "price",
    "currency",
    "discount_pct",
    "url",
    "link_allowed",
    "drm",
    "region",
    "source",
    "confidence",
    "observed_at",
    "expires_at",
    "visibility",
    "eligible_for_best_external_price",
    "risk_flags",
)


def normalize_export_cache_state(value) -> str:
    if isinstance(value, dict):
        value = value.get("cache_state") or value.get("state")
    state = str(value or "").strip()
    state = INTERNAL_CACHE_STATE_MAP.get(state, state)
    return state if state in EXPORT_CACHE_STATES else "unknown"


def build_offers_export(
    deals,
    *,
    generated_at: str,
    source_report: dict | None = None,
    wishlist_appids=None,
    cache_states: dict | None = None,
    cache_coverage: dict | None = None,
    top_picks=None,
    external_offers: dict | list | None = None,
    active_promo_context: dict | None = None,
) -> dict:
    deal_records = _dict_records(deals)
    wishlist_ids = _wishlist_appids(wishlist_appids)
    fallback_ids = [appid for appid in (_appid(deal) for deal in deal_records) if appid]
    coverage_ids = wishlist_ids or fallback_ids
    state_by_appid = _state_by_appid(cache_states, coverage_ids)
    top_pick_by_appid = _index_by_appid(_dict_records(top_picks))
    external_by_appid = _external_offers_by_appid(external_offers)
    source = _source_report(source_report)
    items = [
        _offer_item(
            deal,
            state_by_appid.get(_appid(deal), "unknown"),
            top_pick_by_appid.get(_appid(deal)),
            external_by_appid.get(_appid(deal), []),
            active_promo_context,
            source.get("sale_name"),
        )
        for deal in deal_records
        if _appid(deal)
    ]
    return {
        "schema": OFFERS_EXPORT_SCHEMA,
        "generated_at": str(generated_at),
        "source_report": source,
        "advisory_only": True,
        "ranking_impact": "none",
        "coverage": _offers_coverage(
            wishlist_ids=coverage_ids,
            items=items,
            state_by_appid=state_by_appid,
            cache_coverage=cache_coverage,
        ),
        "items": items,
        "limitations": [
            "does_not_include_non_deal_wishlist_items",
            "coverage_may_be_partial",
            "not_purchase_advice",
        ],
    }


def build_wishlist_export(
    wishlist_appids,
    *,
    generated_at: str,
    source_report: dict | None = None,
    deals=None,
    price_entries: dict | None = None,
    cache_states: dict | None = None,
    cache_coverage: dict | None = None,
    priorities: dict | None = None,
    owned=None,
    family_appids=None,
    wishlist_hygiene: dict | None = None,
) -> dict:
    wishlist_records = _wishlist_records(wishlist_appids)
    appids = [record["appid"] for record in wishlist_records]
    state_by_appid = _state_by_appid(cache_states, appids)
    deals_by_appid = _index_by_appid(_dict_records(deals))
    hygiene_by_appid = _index_by_appid(_dict_records((wishlist_hygiene or {}).get("items")))
    owned_set = _appid_set(owned)
    family_set = _appid_set(family_appids)
    items = [
        _wishlist_item(
            record,
            state_by_appid.get(record["appid"], "unknown"),
            deals_by_appid.get(record["appid"]),
            _price_entry(record["appid"], price_entries),
            priorities or {},
            record["appid"] in owned_set,
            record["appid"] in family_set,
            hygiene_by_appid.get(record["appid"]),
        )
        for record in wishlist_records
    ]
    return {
        "schema": WISHLIST_EXPORT_SCHEMA,
        "generated_at": str(generated_at),
        "source_report": _source_report(source_report),
        "advisory_only": True,
        "ranking_impact": "none",
        "coverage": _wishlist_coverage(
            wishlist_ids=appids,
            items=items,
            state_by_appid=state_by_appid,
            cache_coverage=cache_coverage,
        ),
        "items": items,
        "limitations": [
            "full_wishlist_does_not_mean_full_price_coverage",
            "cache_state_required_before_interpreting_status",
            "not_purchase_advice",
        ],
    }


def _offer_item(
    deal: dict,
    cache_state: str,
    top_pick: dict | None,
    external_offers: list[dict],
    active_promo_context: dict | None,
    sale_name: str | None,
) -> dict:
    appid = _appid(deal)
    score = _number(deal.get("score"), top_pick.get("score") if top_pick else None)
    item = {
        "appid": appid,
        "name": _name(deal),
        "discount_percent": _int_value(deal.get("discount"), deal.get("discount_percent")),
        "price_final": _text_or_none(deal.get("price_final")),
        "price_original": _text_or_none(deal.get("price_original")),
        "price_raw": _int_value(deal.get("price_raw"), deal.get("price_final_raw")),
        "score": score,
        "score_label": _text_or_none(
            deal.get("score_label")
            or deal.get("recommendation")
            or (top_pick or {}).get("recommendation")
        ),
        "score_reasons": _text_list(deal.get("score_reasons") or (top_pick or {}).get("score_reasons")),
        "cache_state": cache_state,
        "store_url": _store_url(appid),
        "external_offers": external_offers,
        "promo_context": _promo_context(active_promo_context, sale_name),
    }
    return {key: value for key, value in item.items() if value is not None}


def _wishlist_item(
    record: dict,
    cache_state: str,
    deal: dict | None,
    price_entry: dict | None,
    priorities: dict,
    owned: bool,
    family_shared: bool,
    hygiene_item: dict | None,
) -> dict:
    appid = record["appid"]
    price_source = deal if isinstance(deal, dict) else price_entry
    price = _price_payload(price_source, cache_state, is_deal=deal is not None)
    status = _wishlist_status(price, cache_state, is_deal=deal is not None)
    return {
        "appid": appid,
        "name": record.get("name") or _name(deal) or _name(price_entry),
        "wishlist_priority": _wishlist_priority(appid, record, priorities),
        "status": status,
        "cache_state": cache_state,
        "price": price,
        "store_url": _store_url(appid),
        "signals": _wishlist_signals(appid, owned, family_shared, hygiene_item),
        "limitations": _item_limitations(cache_state, status),
    }


def _source_report(source_report: dict | None) -> dict:
    source = source_report if isinstance(source_report, dict) else {}
    result = {"schema": REPORT_JSON_SCHEMA}
    filename = _filename(source.get("filename") or source.get("path") or source.get("output_json"))
    if filename:
        result["filename"] = filename
    vanity = _text_or_none(source.get("vanity") or source.get("profile"))
    if vanity:
        result["vanity"] = vanity
    sale_name = _text_or_none(source.get("sale_name"))
    if sale_name:
        result["sale_name"] = sale_name
    return result


def _offers_coverage(
    *,
    wishlist_ids: list[str],
    items: list[dict],
    state_by_appid: dict[str, str],
    cache_coverage: dict | None,
) -> dict:
    counts = _state_counts(state_by_appid, wishlist_ids)
    status = _coverage_status(counts, cache_coverage)
    coverage = {
        "status": status,
        "wishlist_total": len(wishlist_ids),
        "priced_or_cached_count": _count_states(counts, CONFIRMED_PRICE_STATES),
        "deals_count": len(items),
        "deferred_count": counts.get("deferred", 0),
        "failed_or_cooldown_count": counts.get("failed_no_data", 0) + counts.get("cooldown", 0),
        "notes": ["offers_with_available_coverage"],
    }
    if counts.get("missing", 0):
        coverage["missing_count"] = counts["missing"]
    if counts.get("unknown", 0):
        coverage["unknown_count"] = counts["unknown"]
    if status != "complete_or_not_required":
        coverage["notes"].append("coverage_may_be_partial")
    return coverage


def _wishlist_coverage(
    *,
    wishlist_ids: list[str],
    items: list[dict],
    state_by_appid: dict[str, str],
    cache_coverage: dict | None,
) -> dict:
    counts = _state_counts(state_by_appid, wishlist_ids)
    statuses = [item.get("status") for item in items]
    pending_or_unknown = sum(
        1
        for status in statuses
        if status in {"pending_price_confirmation", "temporary_failure", "no_price_confirmed", "unknown"}
    )
    return {
        "status": _coverage_status(counts, cache_coverage),
        "wishlist_total": len(wishlist_ids),
        "items_exported": len(items),
        "price_confirmed_count": sum(1 for item in items if item.get("price", {}).get("known") is True),
        "deal_count": statuses.count("deal_detected"),
        "not_on_sale_confirmed_count": statuses.count("not_on_sale_confirmed"),
        "pending_or_unknown_count": pending_or_unknown,
    }


def _coverage_status(counts: dict[str, int], cache_coverage: dict | None) -> str:
    if isinstance(cache_coverage, dict) and (
        cache_coverage.get("status") == "partial" or cache_coverage.get("is_partial") is True
    ):
        return "partial"
    if _count_states(counts, PARTIAL_CACHE_STATES):
        return "partial"
    if counts.get("unknown", 0):
        return "unknown"
    return "complete_or_not_required"


def _wishlist_status(price: dict, cache_state: str, *, is_deal: bool) -> str:
    if is_deal:
        return "deal_detected"
    if price.get("known") is True:
        return "not_on_sale_confirmed"
    if cache_state == "cooldown":
        return "temporary_failure"
    if cache_state == "failed_no_data":
        return "no_price_confirmed"
    if cache_state in {"deferred", "missing"}:
        return "pending_price_confirmation"
    return "unknown"


def _price_payload(record: dict | None, cache_state: str, *, is_deal: bool = False) -> dict:
    known = bool(is_deal or (cache_state in CONFIRMED_PRICE_STATES and _has_price_fields(record)))
    discount = _int_value((record or {}).get("discount"), (record or {}).get("discount_percent"))
    payload = {"known": known, "on_sale": (discount > 0 if known and discount is not None else None)}
    if not known:
        return payload
    for key, value in {
        "discount_percent": discount,
        "price_final": _text_or_none((record or {}).get("price_final")),
        "price_original": _text_or_none((record or {}).get("price_original")),
        "price_raw": _int_value((record or {}).get("price_raw"), (record or {}).get("price_final_raw")),
    }.items():
        if value is not None:
            payload[key] = value
    return payload


def _wishlist_signals(
    appid: str,
    owned: bool,
    family_shared: bool,
    hygiene_item: dict | None,
) -> dict:
    signals = list((hygiene_item or {}).get("signals") or [])
    return {
        "owned": owned or "owned" in signals,
        "family_shared": family_shared or "family" in signals,
        "external_access_possible": any(
            signal in {"external_owned", "external_bundle_owned", "external_review_needed"}
            for signal in signals
        ),
    }


def _item_limitations(cache_state: str, status: str) -> list[str]:
    limitations: list[str] = []
    if cache_state == "stale_usable":
        limitations.append("stale_price_data")
    if cache_state in {"deferred", "missing", "unknown"}:
        limitations.append("not_revalidated_in_this_run")
    if status == "temporary_failure":
        limitations.append("temporary_failure_cooldown")
    if status == "no_price_confirmed":
        limitations.append("no_price_confirmed")
    if status == "unknown":
        limitations.append("status_unknown")
    return limitations


def _state_by_appid(cache_states: dict | None, appids: Iterable[str]) -> dict[str, str]:
    explicit = cache_states if isinstance(cache_states, dict) else {}
    result = {
        str(appid): normalize_export_cache_state(explicit.get(str(appid)))
        for appid in appids
        if str(appid)
    }
    for appid, state in explicit.items():
        clean_appid = _appid(appid)
        if clean_appid and clean_appid not in result:
            result[clean_appid] = normalize_export_cache_state(state)
    return result


def _state_counts(state_by_appid: dict[str, str], appids: list[str]) -> dict[str, int]:
    counts = {state: 0 for state in EXPORT_CACHE_STATES}
    for appid in appids:
        counts[normalize_export_cache_state(state_by_appid.get(appid))] += 1
    return counts


def _count_states(counts: dict[str, int], states: set[str]) -> int:
    return sum(counts.get(state, 0) for state in states)


def _dict_records(value) -> list[dict]:
    if not value:
        return []
    if isinstance(value, dict):
        if isinstance(value.get("items"), list):
            return [dict(item) for item in value["items"] if isinstance(item, dict)]
        return [
            {"appid": str(appid), **(record if isinstance(record, dict) else {})}
            for appid, record in value.items()
        ]
    return [dict(item) for item in value if isinstance(item, dict)]


def _wishlist_records(value) -> list[dict]:
    records = _dict_records(value) if not isinstance(value, (str, int)) else [{"appid": value}]
    if not records and isinstance(value, (list, tuple, set)):
        records = [{"appid": item} for item in value]
    seen: set[str] = set()
    result: list[dict] = []
    for index, record in enumerate(records):
        appid = _appid(record)
        if not appid or appid in seen:
            continue
        seen.add(appid)
        result.append(
            {
                "appid": appid,
                "name": _name(record),
                "wishlist_priority": _int_value(record.get("wishlist_priority"), record.get("priority")),
                "wishlist_index": index,
            }
        )
    return result


def _wishlist_appids(value) -> list[str]:
    return [record["appid"] for record in _wishlist_records(value)]


def _index_by_appid(records: list[dict]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for record in records:
        appid = _appid(record)
        if appid and appid not in indexed:
            indexed[appid] = record
    return indexed


def _external_offers_by_appid(external_offers: dict | list | None) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in _dict_records(external_offers):
        appid = _appid(item)
        if appid:
            grouped.setdefault(appid, []).append(_safe_external_offer(item))
    return grouped


def _safe_external_offer(item: dict) -> dict:
    return {
        key: item[key]
        for key in EXTERNAL_OFFER_EXPORT_KEYS
        if key in item and not key.startswith("_")
    }


def _price_entry(appid: str, price_entries: dict | None) -> dict | None:
    if not isinstance(price_entries, dict):
        return None
    entry = price_entries.get(appid)
    return entry if isinstance(entry, dict) else None


def _has_price_fields(record: dict | None) -> bool:
    if not isinstance(record, dict):
        return False
    if record.get("_failed_at") is not None or record.get("_failure_reason") is not None:
        return False
    return any(
        record.get(key) not in (None, "")
        for key in ("price_final", "price_original", "price_raw", "price_final_raw")
    )


def _appid(record) -> str:
    if isinstance(record, dict):
        value = record.get("appid") or record.get("steam_appid") or record.get("wishlist_appid")
    else:
        value = record
    text = str(value or "").strip()
    return text if text.isdigit() else ""


def _appid_set(records) -> set[str]:
    if not records:
        return set()
    if isinstance(records, dict):
        return {appid for appid in (_appid(key) for key in records) if appid}
    if isinstance(records, (str, int)):
        return {_appid(records)} - {""}
    return {appid for appid in (_appid(record) for record in records) if appid}


def _name(record) -> str | None:
    if not isinstance(record, dict):
        return None
    return _text_or_none(record.get("name") or record.get("steam_name") or record.get("title"))


def _wishlist_priority(appid: str, record: dict, priorities: dict) -> int | None:
    return _int_value(record.get("wishlist_priority"), priorities.get(appid))


def _promo_context(active_promo_context: dict | None, sale_name: str | None) -> dict:
    label = _promo_label(active_promo_context) or _text_or_none(sale_name)
    return {"matched": bool(active_promo_context or label), "label": label}


def _promo_label(active_promo_context: dict | None) -> str | None:
    if not isinstance(active_promo_context, dict):
        return None
    primary = active_promo_context.get("primary")
    if isinstance(primary, dict):
        return _text_or_none(primary.get("label") or primary.get("name") or primary.get("title"))
    return _text_or_none(
        active_promo_context.get("label")
        or active_promo_context.get("name")
        or active_promo_context.get("sale_name")
    )


def _store_url(appid: str) -> str:
    return f"https://store.steampowered.com/app/{appid}/"


def _filename(value) -> str | None:
    text = _text_or_none(value)
    if not text:
        return None
    return Path(text.replace("\\", "/").split("/")[-1]).name or None


def _text_or_none(value, *, limit: int = 240) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text[:limit] if text else None


def _text_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _text_or_none(item)
        if text and text not in result:
            result.append(text)
    return result


def _int_value(*values) -> int | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _number(*values) -> float | int | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        return int(number) if number.is_integer() else round(number, 2)
    return None
