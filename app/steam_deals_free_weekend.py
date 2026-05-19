from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


FREE_WEEKEND_TEXT_RE = re.compile(r"\bfree\s+weekend\b", re.IGNORECASE)
FREE_TO_KEEP_TEXT_RE = re.compile(
    r"\bfree\s+(?:to\s+keep|to\s+own)\b|\bkeep\s+it\b",
    re.IGNORECASE,
)
DEMO_PLAYTEST_TEXT_RE = re.compile(r"\b(?:demo|playtest|prologue)\b", re.IGNORECASE)
CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}
SOURCE_POLICY = "fixture_or_cached_store_signals_v1"


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


def _iso_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _normalized_appid(value: Any) -> str:
    number = _numeric(value)
    return str(number) if number is not None and number > 0 else ""


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
) -> dict[str, Any]:
    """Build a cacheable Free Weekend payload from local Store JSON data."""
    items = build_free_weekend_candidate_items(
        featured_categories_payload,
        appdetails_payload,
        observed_at=observed_at,
        current_timestamp=current_timestamp,
        now=now,
    )
    return {
        "generated_at": _iso_datetime(observed_at),
        "source_policy": SOURCE_POLICY,
        "items": items,
        "summary": _summary(items),
    }
