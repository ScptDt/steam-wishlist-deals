from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.cache_utils import load_timestamped_cache, save_timestamped_cache
from shared.io_utils import http_get_json


FREE_WEEKEND_TEXT_RE = re.compile(r"\bfree\s+weekend\b", re.IGNORECASE)
FREE_TO_KEEP_TEXT_RE = re.compile(
    r"\bfree\s+(?:to\s+keep|to\s+own)\b|\bkeep\s+it\b",
    re.IGNORECASE,
)
DEMO_PLAYTEST_TEXT_RE = re.compile(r"\b(?:demo|playtest|prologue)\b", re.IGNORECASE)
CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}
SOURCE_POLICY = "fixture_or_cached_store_signals_v1"
FREE_WEEKEND_CACHE_PAYLOAD_KEY = "free_weekend_now"
FREE_WEEKEND_CACHE_TTL_HOURS = 12
FEATURED_CATEGORIES_URL = "https://store.steampowered.com/api/featuredcategories"
APPDETAILS_URL = (
    "https://store.steampowered.com/api/appdetails"
    "?appids={appids}&filters=basic,price_overview,packages,package_groups"
)
STORE_JSON_HEADERS = {"User-Agent": "Mozilla/5.0"}
APPDETAILS_BATCH_SIZE = 1
CROSS_SIGNAL_REASONS = {
    "in_wishlist": "en tu wishlist",
    "owned": "ya en biblioteca",
    "family": "disponible en biblioteca familiar",
    "taste_match": "similar a tus gustos",
}


def _compact_text(value: Any, *, limit: int = 160) -> str:
    if not isinstance(value, str):
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", without_tags).strip()
    return text[:limit]


def _numeric(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _timestamp(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    number = _numeric(value)
    return float(number) if number is not None else None


def _timestamp_from_iso(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return _timestamp(value)
    raw = value.strip()
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return _timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _reference_timestamp(
    *,
    current_timestamp: int | float | None = None,
    now: Any = None,
) -> float:
    if current_timestamp is not None:
        return float(current_timestamp)
    timestamp = _timestamp(now)
    if timestamp is not None:
        return float(timestamp)
    return datetime.now(timezone.utc).timestamp()


def _iso_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _normalized_appid(value: Any) -> str:
    number = _numeric(value)
    return str(number) if number is not None and number > 0 else ""


def _collection_appid(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("appid", "steam_appid", "id", "app_id"):
            appid = _normalized_appid(value.get(key))
            if appid:
                return appid
        return ""
    return _normalized_appid(value)


def _normalize_appid_set(values: Any) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, dict):
        return {_collection_appid(key) for key in values.keys() if _collection_appid(key)}
    if isinstance(values, (list, set, tuple)):
        return {_collection_appid(value) for value in values if _collection_appid(value)}
    appid = _collection_appid(values)
    return {appid} if appid else set()


def _payload_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        raw_items = value.get("items")
    else:
        raw_items = value
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def _preference_reasons_for_appid(appid: str, preference_relations: Any) -> list[str]:
    if not isinstance(preference_relations, dict):
        return []
    raw = preference_relations.get(appid) or preference_relations.get(str(appid))
    if isinstance(raw, str):
        text = _compact_text(raw, limit=120)
        return [text] if text else []
    if isinstance(raw, list):
        return [_compact_text(reason, limit=120) for reason in raw if _compact_text(reason, limit=120)]
    return []


def _personalized_reason_for_appid(appid: str, personalized_recommendations: Any) -> str:
    for item in _payload_items(personalized_recommendations):
        if _collection_appid(item) != appid:
            continue
        reasons = item.get("reasons") if isinstance(item.get("reasons"), list) else []
        for reason in reasons:
            text = _compact_text(reason, limit=120)
            if text and text != "score base del reporte":
                return text
        affinity = item.get("affinity_score")
        if affinity not in (None, ""):
            return f"afinidad positiva {affinity}"
    return ""


def _taste_match_reason(
    appid: str,
    *,
    personalized_recommendations: Any = None,
    liked_appids: Any = None,
    preference_relations: Any = None,
) -> str:
    preference_reasons = _preference_reasons_for_appid(appid, preference_relations)
    if preference_reasons:
        return preference_reasons[0]
    personalized_reason = _personalized_reason_for_appid(appid, personalized_recommendations)
    if personalized_reason:
        return personalized_reason
    if appid in _normalize_appid_set(liked_appids):
        return CROSS_SIGNAL_REASONS["taste_match"]
    return ""


def _append_unique(values: list[str], value: str) -> None:
    text = _compact_text(value, limit=140)
    if text and text not in values:
        values.append(text)


def _extract_appdetails_info(appdetails: dict[str, Any] | None) -> tuple[dict[str, Any] | None, bool]:
    if not isinstance(appdetails, dict):
        return None, False
    if "success" in appdetails:
        info = appdetails.get("data")
        return (info if isinstance(info, dict) else None), appdetails.get("success") is True
    return appdetails, True


def _appdetails_entry_for_appid(
    appid: str,
    appdetails_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(appdetails_payload, dict):
        return None
    entry = appdetails_payload.get(appid)
    return entry if isinstance(entry, dict) else None


def _featured_item_appid(item: dict[str, Any]) -> str:
    for key in ("id", "appid", "app_id"):
        appid = _normalized_appid(item.get(key))
        if appid:
            return appid
    return ""


def _item_title(item: dict[str, Any], info: dict[str, Any] | None) -> str:
    for source in (item, info or {}):
        for key in ("name", "title"):
            text = _compact_text(source.get(key), limit=120)
            if text:
                return text
    return ""


def _text_signals(item: dict[str, Any], info: dict[str, Any] | None) -> list[str]:
    values: list[str] = []
    for source in (item, info or {}):
        for key in ("name", "title", "headline", "short_description", "detailed_description"):
            text = _compact_text(source.get(key))
            if text:
                values.append(text)
    return values


def _first_matching_text(texts: list[str], pattern: re.Pattern[str]) -> str | None:
    for text in texts:
        if pattern.search(text):
            return text
    return None


def _is_demo_or_playtest(item: dict[str, Any], info: dict[str, Any] | None) -> bool:
    if isinstance(info, dict) and str(info.get("type") or "").lower() in {"demo", "playtest"}:
        return True
    title = _item_title(item, info)
    return bool(DEMO_PLAYTEST_TEXT_RE.search(title))


def _price_overview(info: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(info, dict):
        return {}
    price = info.get("price_overview")
    return price if isinstance(price, dict) else {}


def _discount_percent(item: dict[str, Any], price: dict[str, Any]) -> int | None:
    values = [
        _numeric(item.get("discount_percent")),
        _numeric(price.get("discount_percent")),
    ]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _final_price(item: dict[str, Any], price: dict[str, Any]) -> int | None:
    values = []
    for value in (item.get("final_price"), item.get("final"), price.get("final")):
        number = _numeric(value)
        if number is not None:
            values.append(number)
    return min(values) if values else None


def _original_price(item: dict[str, Any], price: dict[str, Any]) -> int | None:
    values = []
    for value in (item.get("original_price"), item.get("initial"), price.get("initial")):
        number = _numeric(value)
        if number is not None:
            values.append(number)
    return max(values) if values else None


def _discount_expiration(item: dict[str, Any], price: dict[str, Any]) -> int | None:
    for value in (item.get("discount_expiration"), price.get("discount_expiration")):
        number = _numeric(value)
        if number is not None and number > 0:
            return number
    return None


def _iso_from_timestamp(timestamp: int | None) -> str | None:
    if timestamp is None or timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _is_future_expiration(expiration: int | None, current_timestamp: int | float | None) -> bool:
    if expiration is None:
        return False
    if current_timestamp is None:
        return True
    return expiration > float(current_timestamp)


def _package_ids(info: dict[str, Any] | None) -> list[str]:
    ids: list[str] = []
    if not isinstance(info, dict):
        return ids
    for value in info.get("packages") or []:
        number = _numeric(value)
        if number is not None and str(number) not in ids:
            ids.append(str(number))
    for group in info.get("package_groups") or []:
        if not isinstance(group, dict):
            continue
        for sub in group.get("subs") or []:
            if not isinstance(sub, dict):
                continue
            number = _numeric(sub.get("packageid"))
            if number is not None and str(number) not in ids:
                ids.append(str(number))
    return ids


def _candidate_reason(confidence: str) -> str:
    if confidence == "high":
        return "Explicit Free Weekend text corroborated by Store price and expiration signals."
    return "Store signals show 100% discount/final price 0 with expiration on a paid-looking app."


def _external_candidate_reason(confidence: str) -> str:
    if confidence == "high":
        return "Local external source marks this as a Free Weekend with a future validity window."
    return "Local external/cache signal marks a future-valid Free Weekend candidate; verify on Steam before acting."


def _iso_from_any_timestamp(value: Any) -> str | None:
    timestamp = _timestamp_from_iso(value)
    if timestamp is None or timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _first_field(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _external_record_title(record: dict[str, Any]) -> str:
    for key in ("title", "name", "game_title", "game_name"):
        title = _compact_text(record.get(key), limit=120)
        if title:
            return title
    return ""


def _external_signal_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _compact_text(value.replace("_", " ").replace("-", " "))


def _external_record_texts(record: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in (
        "title",
        "name",
        "game_title",
        "game_name",
        "headline",
        "description",
        "summary",
        "status",
        "type",
        "category",
        "offer_type",
        "source",
        "provider",
    ):
        text = _external_signal_text(record.get(key))
        if text:
            texts.append(text)
    for key in ("sources", "providers"):
        raw_values = record.get(key)
        if isinstance(raw_values, list):
            for value in raw_values:
                text = _external_signal_text(value)
                if text:
                    texts.append(text)
    return texts


def _external_record_sources(record: dict[str, Any]) -> list[str]:
    sources: list[str] = []

    def append_source(value: Any) -> None:
        text = _compact_text(value, limit=80)
        if text and text not in sources:
            sources.append(text)

    for key in ("source", "provider", "origin"):
        append_source(record.get(key))
    for key in ("sources", "providers"):
        values = record.get(key)
        if isinstance(values, list):
            for value in values:
                append_source(value)
    return sources[:4]


def _safe_external_url(record: dict[str, Any]) -> str | None:
    value = _first_field(record, ("source_url", "url", "offer_url", "details_url"))
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return None
    return url[:300]


def _external_record_confidence(record: dict[str, Any], matched_text: str | None) -> str:
    raw = str(record.get("confidence") or "").strip().lower()
    if raw in CONFIDENCE_RANK:
        return raw
    return "high" if matched_text else "medium"


def _compact_external_signal(value: Any, *, limit: int = 120) -> str | None:
    text = _compact_text(value, limit=limit)
    return text or None


def classify_external_free_weekend_record(
    record: dict[str, Any] | None,
    *,
    observed_at: Any,
    current_timestamp: int | float | None = None,
    now: Any = None,
) -> dict[str, Any] | None:
    """Normalize one local external/cache Free Weekend record into the shared contract."""
    if not isinstance(record, dict):
        return None

    appid = _collection_appid(record)
    title = _external_record_title(record)
    sources = _external_record_sources(record)
    if not appid or not title or not sources:
        return None

    texts = _external_record_texts(record)
    matched_text = _first_matching_text(texts, FREE_WEEKEND_TEXT_RE)
    if _first_matching_text(texts, FREE_TO_KEEP_TEXT_RE):
        return None
    if _first_matching_text(texts, DEMO_PLAYTEST_TEXT_RE):
        return None
    if record.get("is_free") is True and not matched_text:
        return None

    reference_timestamp = _reference_timestamp(
        current_timestamp=current_timestamp,
        now=now,
    )
    starts_at = _first_field(record, ("starts_at", "start_at", "start", "from", "begins_at"))
    valid_until_raw = _first_field(
        record,
        ("valid_until", "ends_at", "end_at", "end", "until", "expires_at", "free_until"),
    )
    start_timestamp = _timestamp_from_iso(starts_at)
    valid_until_timestamp = _timestamp_from_iso(valid_until_raw)
    if start_timestamp is not None and start_timestamp > reference_timestamp:
        return None
    if valid_until_timestamp is None or valid_until_timestamp <= reference_timestamp:
        return None

    confidence = _external_record_confidence(record, matched_text)
    source_url = _safe_external_url(record)
    signals = {
        "matched_text": matched_text,
        "starts_at": _iso_from_any_timestamp(starts_at),
        "source_url": source_url,
        "external_status": _compact_external_signal(record.get("status")),
        "external_offer_type": _compact_external_signal(record.get("offer_type") or record.get("type")),
        "is_free": record.get("is_free") if isinstance(record.get("is_free"), bool) else None,
        "package_ids": [],
    }

    return {
        "appid": appid,
        "title": title,
        "observed_at": _iso_datetime(observed_at),
        "valid_until": _iso_from_any_timestamp(valid_until_raw),
        "store_url": f"https://store.steampowered.com/app/{appid}/",
        "sources": sources,
        "confidence": confidence,
        "reason": _external_candidate_reason(confidence),
        "signals": {
            key: value
            for key, value in signals.items()
            if value not in (None, "")
        },
    }


def _candidate_rank(candidate: dict[str, Any]) -> tuple[int, str]:
    return (
        CONFIDENCE_RANK.get(str(candidate.get("confidence") or "low"), 9),
        str(candidate.get("valid_until") or ""),
    )


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    confidence_counts: dict[str, int] = {}
    for item in items:
        confidence = str(item.get("confidence") or "unknown")
        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
    return {"count": len(items), "confidence_counts": confidence_counts}


def build_free_weekend_candidates_from_external_records(
    records_payload: dict[str, Any] | list[Any] | None,
    *,
    observed_at: Any,
    current_timestamp: int | float | None = None,
    now: Any = None,
    wishlist_appids: Any = None,
    owned: Any = None,
    family_appids: Any = None,
    personalized_recommendations: Any = None,
    liked_appids: Any = None,
    preference_relations: Any = None,
) -> dict[str, Any]:
    """Build `free_weekend_now` from local external records without network access."""
    by_appid: dict[str, dict[str, Any]] = {}
    for record in _payload_items(records_payload):
        candidate = classify_external_free_weekend_record(
            record,
            observed_at=observed_at,
            current_timestamp=current_timestamp,
            now=now,
        )
        if not candidate:
            continue
        previous = by_appid.get(candidate["appid"])
        if previous is None or _candidate_rank(candidate) < _candidate_rank(previous):
            by_appid[candidate["appid"]] = candidate

    items = list(by_appid.values())
    payload = {
        "generated_at": _iso_datetime(observed_at),
        "source_policy": SOURCE_POLICY,
        "items": items,
        "summary": _summary(items),
    }
    if any(
        context is not None
        for context in (
            wishlist_appids,
            owned,
            family_appids,
            personalized_recommendations,
            liked_appids,
            preference_relations,
        )
    ):
        return enrich_free_weekend_cross_signals(
            payload,
            wishlist_appids=wishlist_appids,
            owned=owned,
            family_appids=family_appids,
            personalized_recommendations=personalized_recommendations,
            liked_appids=liked_appids,
            preference_relations=preference_relations,
        )
    return payload


def _candidate_is_current(item: dict[str, Any], reference_timestamp: float) -> bool:
    if not isinstance(item, dict):
        return False
    if not _collection_appid(item) or not _compact_text(item.get("title"), limit=120):
        return False
    valid_until = _timestamp_from_iso(item.get("valid_until"))
    return valid_until is not None and valid_until > reference_timestamp


def filter_current_free_weekend_payload(
    payload: dict[str, Any] | None,
    *,
    current_timestamp: int | float | None = None,
    now: Any = None,
) -> dict[str, Any] | None:
    """Return only non-expired Free Weekend candidates from a cached/live payload."""
    if not isinstance(payload, dict):
        return None
    reference_timestamp = _reference_timestamp(
        current_timestamp=current_timestamp,
        now=now,
    )
    items = [
        dict(item)
        for item in payload.get("items", [])
        if isinstance(item, dict) and _candidate_is_current(item, reference_timestamp)
    ]
    return {
        **payload,
        "generated_at": payload.get("generated_at") or _iso_datetime(now or datetime.now(timezone.utc)),
        "source_policy": payload.get("source_policy") or SOURCE_POLICY,
        "items": items,
        "summary": _summary(items),
    }


def enrich_free_weekend_candidate_cross_signals(
    candidate: dict[str, Any],
    *,
    wishlist_appids: Any = None,
    owned: Any = None,
    family_appids: Any = None,
    personalized_recommendations: Any = None,
    liked_appids: Any = None,
    preference_relations: Any = None,
) -> dict[str, Any]:
    """Add advisory local cross-signals to a Free Weekend candidate."""
    if not isinstance(candidate, dict):
        return {}
    appid = _collection_appid(candidate)
    existing_cross_signals = candidate.get("cross_signals") if isinstance(candidate.get("cross_signals"), dict) else {}
    existing_reasons = candidate.get("cross_reasons") if isinstance(candidate.get("cross_reasons"), list) else []
    wishlist_set = _normalize_appid_set(wishlist_appids)
    owned_set = _normalize_appid_set(owned)
    family_set = _normalize_appid_set(family_appids)

    owned_or_family = None
    if appid and appid in owned_set:
        owned_or_family = "owned"
    elif appid and appid in family_set:
        owned_or_family = "family"

    existing_owned_or_family = str(existing_cross_signals.get("owned_or_family") or "").strip()
    if owned_or_family == "owned" or existing_owned_or_family == "owned":
        owned_or_family = "owned"
    elif owned_or_family == "family" or existing_owned_or_family == "family":
        owned_or_family = "family"
    else:
        owned_or_family = None

    taste_reason = _taste_match_reason(
        appid,
        personalized_recommendations=personalized_recommendations,
        liked_appids=liked_appids,
        preference_relations=preference_relations,
    ) if appid else ""

    cross_signals = {
        "in_wishlist": bool(existing_cross_signals.get("in_wishlist") is True or (appid and appid in wishlist_set)),
        "owned_or_family": owned_or_family,
        "similar_to_profile": bool(existing_cross_signals.get("similar_to_profile") is True or taste_reason),
    }
    cross_reasons: list[str] = []
    for reason in existing_reasons:
        _append_unique(cross_reasons, str(reason or ""))
    if cross_signals["in_wishlist"]:
        _append_unique(cross_reasons, CROSS_SIGNAL_REASONS["in_wishlist"])
    if owned_or_family == "owned":
        _append_unique(cross_reasons, CROSS_SIGNAL_REASONS["owned"])
    elif owned_or_family == "family":
        _append_unique(cross_reasons, CROSS_SIGNAL_REASONS["family"])
    if taste_reason:
        label = CROSS_SIGNAL_REASONS["taste_match"]
        reason = taste_reason if taste_reason == label else f"{label}: {taste_reason}"
        _append_unique(cross_reasons, reason)
    elif cross_signals["similar_to_profile"] and not any(
        reason.startswith(CROSS_SIGNAL_REASONS["taste_match"])
        for reason in cross_reasons
    ):
        _append_unique(cross_reasons, CROSS_SIGNAL_REASONS["taste_match"])

    enriched = dict(candidate)
    enriched["cross_signals"] = cross_signals
    enriched["cross_reasons"] = cross_reasons
    return enriched


def enrich_free_weekend_cross_signals(
    payload: dict[str, Any] | None,
    *,
    wishlist_appids: Any = None,
    owned: Any = None,
    family_appids: Any = None,
    personalized_recommendations: Any = None,
    liked_appids: Any = None,
    preference_relations: Any = None,
) -> dict[str, Any] | None:
    """Return a Free Weekend payload enriched with advisory local cross-signals."""
    if not isinstance(payload, dict):
        return payload
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    return {
        **payload,
        "items": [
            enrich_free_weekend_candidate_cross_signals(
                item,
                wishlist_appids=wishlist_appids,
                owned=owned,
                family_appids=family_appids,
                personalized_recommendations=personalized_recommendations,
                liked_appids=liked_appids,
                preference_relations=preference_relations,
            )
            for item in items
        ],
    }


def extract_featured_category_items(payload: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
    """Return Store featured-category item dicts from cached JSON payloads."""
    items: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            raw_items = value.get("items")
            if isinstance(raw_items, list):
                for item in raw_items:
                    if isinstance(item, dict):
                        items.append(item)
            for key, child in value.items():
                if key == "items":
                    continue
                if isinstance(child, (dict, list)):
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, (dict, list)):
                    visit(child)

    visit(payload)
    return items


def classify_free_weekend_candidate(
    featured_item: dict[str, Any] | None,
    appdetails: dict[str, Any] | None,
    *,
    observed_at: Any,
    current_timestamp: int | float | None = None,
    now: Any = None,
) -> dict[str, Any] | None:
    """Classify one cached Store candidate without live network access."""
    if not isinstance(featured_item, dict):
        return None

    appid = _featured_item_appid(featured_item)
    info, success = _extract_appdetails_info(appdetails)
    title = _item_title(featured_item, info)
    if not appid or not title or not success or not isinstance(info, dict):
        return None

    texts = _text_signals(featured_item, info)
    if _first_matching_text(texts, FREE_TO_KEEP_TEXT_RE):
        return None
    if _is_demo_or_playtest(featured_item, info):
        return None

    price = _price_overview(info)
    discount_percent = _discount_percent(featured_item, price)
    final_price = _final_price(featured_item, price)
    original_price = _original_price(featured_item, price)
    expiration = _discount_expiration(featured_item, price)
    has_price_signal = final_price == 0 or (discount_percent is not None and discount_percent >= 100)
    reference_timestamp = current_timestamp if current_timestamp is not None else _timestamp(now)
    has_future_expiration = _is_future_expiration(expiration, reference_timestamp)
    matched_text = _first_matching_text(texts, FREE_WEEKEND_TEXT_RE)

    if not has_price_signal or not has_future_expiration:
        return None

    paid_looking = info.get("is_free") is not True or original_price not in (None, 0)
    if not paid_looking and not matched_text:
        return None

    confidence = "high" if matched_text else "medium"
    sources = ["featuredcategories", "appdetails"]
    signals = {
        "discount_percent": discount_percent,
        "final_price": final_price,
        "original_price": original_price,
        "is_free": info.get("is_free") if isinstance(info.get("is_free"), bool) else None,
        "matched_text": matched_text,
        "package_ids": _package_ids(info),
    }

    return {
        "appid": appid,
        "title": title,
        "observed_at": _iso_datetime(observed_at),
        "valid_until": _iso_from_timestamp(expiration),
        "store_url": f"https://store.steampowered.com/app/{appid}/",
        "sources": sources,
        "confidence": confidence,
        "reason": _candidate_reason(confidence),
        "signals": signals,
    }


def build_free_weekend_candidate_items(
    featured_categories_payload: dict[str, Any] | list[Any] | None,
    appdetails_payload: dict[str, Any] | None,
    *,
    observed_at: Any,
    current_timestamp: int | float | None = None,
    now: Any = None,
) -> list[dict[str, Any]]:
    """Build deduped Free Weekend candidates from cached Store JSON fixtures."""
    by_appid: dict[str, dict[str, Any]] = {}
    reference_timestamp = current_timestamp if current_timestamp is not None else _timestamp(now)
    for item in extract_featured_category_items(featured_categories_payload):
        appid = _featured_item_appid(item)
        candidate = classify_free_weekend_candidate(
            item,
            _appdetails_entry_for_appid(appid, appdetails_payload),
            observed_at=observed_at,
            current_timestamp=reference_timestamp,
        )
        if not candidate:
            continue
        previous = by_appid.get(candidate["appid"])
        if previous is None or _candidate_rank(candidate) < _candidate_rank(previous):
            by_appid[candidate["appid"]] = candidate
    return list(by_appid.values())


def build_free_weekend_candidates(
    featured_categories_payload: dict[str, Any] | list[Any] | None,
    appdetails_payload: dict[str, Any] | None,
    *,
    observed_at: Any,
    current_timestamp: int | float | None = None,
    now: Any = None,
    wishlist_appids: Any = None,
    owned: Any = None,
    family_appids: Any = None,
    personalized_recommendations: Any = None,
    liked_appids: Any = None,
    preference_relations: Any = None,
) -> dict[str, Any]:
    """Build a cacheable Free Weekend payload from local Store JSON data."""
    items = build_free_weekend_candidate_items(
        featured_categories_payload,
        appdetails_payload,
        observed_at=observed_at,
        current_timestamp=current_timestamp,
        now=now,
    )
    payload = {
        "generated_at": _iso_datetime(observed_at),
        "source_policy": SOURCE_POLICY,
        "items": items,
        "summary": _summary(items),
    }
    if any(
        context is not None
        for context in (
            wishlist_appids,
            owned,
            family_appids,
            personalized_recommendations,
            liked_appids,
            preference_relations,
        )
    ):
        return enrich_free_weekend_cross_signals(
            payload,
            wishlist_appids=wishlist_appids,
            owned=owned,
            family_appids=family_appids,
            personalized_recommendations=personalized_recommendations,
            liked_appids=liked_appids,
            preference_relations=preference_relations,
        )
    return payload


def load_free_weekend_candidate_cache(
    cache_file: Path,
    *,
    ttl_hours: int | float = FREE_WEEKEND_CACHE_TTL_HOURS,
    current_timestamp: int | float | None = None,
    now: Any = None,
    load_cache_fn=load_timestamped_cache,
) -> dict[str, Any] | None:
    """Load a fresh, current Free Weekend payload from the dedicated cache."""
    payload, age_hours = load_cache_fn(
        cache_file,
        FREE_WEEKEND_CACHE_PAYLOAD_KEY,
        default={},
    )
    if age_hours > float(ttl_hours):
        return None
    return filter_current_free_weekend_payload(
        payload,
        current_timestamp=current_timestamp,
        now=now,
    )


def save_free_weekend_candidate_cache(
    cache_file: Path,
    payload: dict[str, Any],
    *,
    save_cache_fn=save_timestamped_cache,
) -> None:
    """Persist Free Weekend candidates without touching the price cache."""
    if not isinstance(payload, dict):
        return
    save_cache_fn(
        cache_file,
        FREE_WEEKEND_CACHE_PAYLOAD_KEY,
        payload,
        ensure_ascii=False,
        indent=2,
    )


def _fetch_json(fetch_json, url: str) -> Any:
    return fetch_json(url, headers=STORE_JSON_HEADERS, timeout=15)


def _chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _featured_appids(featured_categories_payload: dict[str, Any] | list[Any] | None) -> list[str]:
    appids = {
        _featured_item_appid(item)
        for item in extract_featured_category_items(featured_categories_payload)
    }
    return sorted((appid for appid in appids if appid), key=lambda value: int(value))


def _merge_appdetails_payload(
    target: dict[str, Any],
    payload: Any,
) -> None:
    if not isinstance(payload, dict):
        return
    target.update(
        {
            str(appid): entry
            for appid, entry in payload.items()
            if isinstance(entry, dict)
        }
    )


def fetch_free_weekend_store_payloads(
    *,
    fetch_json=http_get_json,
) -> tuple[dict[str, Any] | list[Any] | None, dict[str, Any]]:
    """Fetch Store JSON used to build opt-in Free Weekend candidates."""
    featured_categories_payload = _fetch_json(fetch_json, FEATURED_CATEGORIES_URL)
    appdetails_payload: dict[str, Any] = {}
    for appid_batch in _chunked(
        _featured_appids(featured_categories_payload),
        APPDETAILS_BATCH_SIZE,
    ):
        if not appid_batch:
            continue
        url = APPDETAILS_URL.format(appids=",".join(appid_batch))
        try:
            _merge_appdetails_payload(appdetails_payload, _fetch_json(fetch_json, url))
        except Exception:
            continue
    return featured_categories_payload, appdetails_payload


def build_live_free_weekend_candidates(
    *,
    fetch_json=http_get_json,
    observed_at: Any = None,
    current_timestamp: int | float | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Build Free Weekend candidates from opt-in live Store JSON fetches."""
    observed = observed_at or now or datetime.now(timezone.utc)
    reference_timestamp = current_timestamp if current_timestamp is not None else _timestamp(observed)
    featured_categories_payload, appdetails_payload = fetch_free_weekend_store_payloads(
        fetch_json=fetch_json,
    )
    return build_free_weekend_candidates(
        featured_categories_payload,
        appdetails_payload,
        observed_at=observed,
        current_timestamp=reference_timestamp,
    )


def resolve_free_weekend_now_payload(
    cache_file: Path,
    *,
    live_enabled: bool = False,
    ttl_hours: int | float = FREE_WEEKEND_CACHE_TTL_HOURS,
    fetch_json=http_get_json,
    current_timestamp: int | float | None = None,
    now: Any = None,
) -> dict[str, Any] | None:
    """Resolve optional `free_weekend_now` from fresh cache or opt-in live fetch."""
    cached_payload = load_free_weekend_candidate_cache(
        cache_file,
        ttl_hours=ttl_hours,
        current_timestamp=current_timestamp,
        now=now,
    )
    if cached_payload is not None:
        return cached_payload
    if not live_enabled:
        return None

    try:
        live_payload = build_live_free_weekend_candidates(
            fetch_json=fetch_json,
            current_timestamp=current_timestamp,
            now=now,
        )
    except Exception:
        return None

    current_payload = filter_current_free_weekend_payload(
        live_payload,
        current_timestamp=current_timestamp,
        now=now,
    )
    if current_payload is not None:
        save_free_weekend_candidate_cache(cache_file, current_payload)
    return current_payload
