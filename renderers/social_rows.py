from __future__ import annotations


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except (TypeError, ValueError):
        return default


def item_appid(item: dict) -> str:
    return str(item.get("appid") or item.get("steam_appid") or "").strip()


def is_numeric_appid(appid: str) -> bool:
    return str(appid or "").isdigit()


def item_name(item: dict) -> str:
    appid = item_appid(item)
    name = str(
        item.get("name")
        or item.get("steam_name")
        or item.get("title")
        or (f"AppID {appid}" if appid else "")
    ).strip()
    return name or "Juego sin nombre"


def item_price(item: dict) -> str:
    for key in ("price_final", "price", "current_price", "final_price"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    raw = item.get("price_raw")
    try:
        amount = float(raw) / 100
    except (TypeError, ValueError):
        return "—"
    return f"${amount:.0f}" if amount.is_integer() else f"${amount:.2f}"


def item_discount(item: dict) -> int:
    return safe_int(item.get("discount", item.get("discount_percent", 0)))


def compact_social_reasons(item: dict, *, limit: int = 2) -> str:
    reasons = item.get("social_reasons")
    if not isinstance(reasons, list):
        reasons = item.get("reasons")
    if not isinstance(reasons, list):
        return ""
    compact: list[str] = []
    for reason in reasons:
        text = str(reason or "").strip()
        if text and text not in compact:
            compact.append(text)
        if len(compact) >= limit:
            break
    return " · ".join(compact)


def _record_list(value: object) -> list[dict]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if isinstance(item, dict)]
    return []


def _collect_appids(value: object) -> list[str]:
    appids: list[str] = []
    if isinstance(value, dict):
        appid = item_appid(value) or str(value.get("id") or "").strip()
        return [appid] if appid else []
    if isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, dict):
                appids.extend(_collect_appids(item))
                continue
            appid = str(item or "").strip()
            if appid:
                appids.append(appid)
    elif value is not None:
        appid = str(value).strip()
        if appid:
            appids.append(appid)
    return appids


def compare_overlap_appids(compare_data: dict | None) -> list[str]:
    if not isinstance(compare_data, dict):
        return []
    appids: list[str] = []
    for key in ("overlap", "overlap_appids", "shared_appids", "common_appids"):
        appids.extend(_collect_appids(compare_data.get(key)))
    seen: set[str] = set()
    unique: list[str] = []
    for appid in appids:
        if appid and appid not in seen:
            seen.add(appid)
            unique.append(appid)
    return unique


def compare_overlap_count(compare_data: dict | None) -> int:
    appids = compare_overlap_appids(compare_data)
    if appids:
        return len(appids)
    if not isinstance(compare_data, dict):
        return 0
    for key in ("overlap_count", "common_count"):
        value = compare_data.get(key)
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return 0


def _has_offer_data(item: dict) -> bool:
    return (
        any(
            item.get(key) not in (None, "")
            for key in ("price_final", "price", "price_raw")
        )
        or item_discount(item) > 0
    )


def _normalized_social_row(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    appid = item_appid(item)
    explicit_name = str(
        item.get("name") or item.get("steam_name") or item.get("title") or ""
    ).strip()
    name = item_name(item)
    if not appid and not explicit_name:
        return None
    return {
        "appid": appid,
        "name": name,
        "discount": item_discount(item),
        "price_final": item_price(item),
        "reason": compact_social_reasons(item),
        "raw": item,
    }


def normalize_gift_idea_rows(
    gift_ideas: list[dict] | None, *, limit: int = 20
) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for item in gift_ideas or []:
        if not isinstance(item, dict):
            continue
        row = _normalized_social_row(item)
        if not row:
            continue
        key = row["appid"] or row["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def normalize_overlap_deal_rows(
    deals: list[dict], compare_data: dict | None, *, limit: int = 20
) -> list[dict]:
    if not isinstance(compare_data, dict):
        return []
    deals_by_appid = {
        item_appid(deal): deal
        for deal in deals or []
        if isinstance(deal, dict) and item_appid(deal)
    }
    candidates: list[dict] = []
    for appid in compare_overlap_appids(compare_data):
        deal = deals_by_appid.get(str(appid))
        if deal:
            candidates.append(deal)
    for key in ("overlap_deals", "common_deals", "shared_deals"):
        candidates.extend(_record_list(compare_data.get(key)))
    for item in _record_list(compare_data.get("overlap")):
        if _has_offer_data(item):
            candidates.append(item)

    rows: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        row = _normalized_social_row(item)
        if not row:
            continue
        key = row["appid"] or row["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return sorted(rows, key=lambda row: (-row["discount"], row["name"].lower()))[:limit]
