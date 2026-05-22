from __future__ import annotations


def _record_appid(record) -> str:
    if isinstance(record, dict):
        return str(record.get("appid") or record.get("steam_appid") or "").strip()
    if record is not None and str(record).strip():
        return str(record).strip()
    return ""


def _record_name(record) -> str:
    if not isinstance(record, dict):
        return ""
    return str(record.get("name") or record.get("steam_name") or record.get("title") or "").strip()


def _records(records) -> list[dict]:
    if not records:
        return []
    if isinstance(records, dict):
        return [
            {"appid": str(appid), **(value if isinstance(value, dict) else {"name": value})}
            for appid, value in records.items()
        ]
    if isinstance(records, (str, int)):
        return [{"appid": str(records)}]
    result: list[dict] = []
    for record in records:
        if isinstance(record, dict):
            result.append(dict(record))
        elif record is not None and str(record).strip():
            result.append({"appid": str(record).strip()})
        else:
            result.append({})
    return result


def _appid_set(records) -> set[str]:
    return {_record_appid(record) for record in _records(records) if _record_appid(record)}


def _name_by_appid(*sources) -> dict[str, str]:
    names: dict[str, str] = {}
    for source in sources:
        for record in _records(source):
            appid = _record_appid(record)
            name = _record_name(record)
            if appid and name and appid not in names:
                names[appid] = name
    return names


def _access_item(appid: str, name: str, access_type: str, *, source: str, confidence: float, reasons: list[str]) -> dict:
    owned = access_type == "owned"
    family_shared = access_type in {"family_shared", "probable_family_shared"}
    return {
        "appid": appid,
        "name": name or f"AppID {appid}",
        "access_type": access_type,
        "owned": owned,
        "family_shared": family_shared,
        "playable_without_buying": owned or family_shared,
        "confidence": confidence,
        "source": source,
        "reasons": reasons,
        "advisory_only": True,
    }


def _owned_access(appid: str, name: str) -> dict:
    return _access_item(
        appid,
        name,
        "owned",
        source="owned_games",
        confidence=1.0,
        reasons=["aparece en tu biblioteca Steam"],
    )


def _family_access(appid: str, name: str) -> dict:
    return _access_item(
        appid,
        name,
        "family_shared",
        source="family_json",
        confidence=0.9,
        reasons=["aparece en biblioteca familiar declarada localmente"],
    )


def _probable_family_access(appid: str, name: str) -> dict:
    return _access_item(
        appid,
        name,
        "probable_family_shared",
        source="installed_or_playable_not_owned",
        confidence=0.75,
        reasons=["instalado o jugable localmente, pero no aparece como owned"],
    )


def _access_summary(items: list[dict], wishlist_count: int) -> dict:
    return {
        "total_wishlist_items": wishlist_count,
        "access_items_count": len(items),
        "owned_count": sum(1 for item in items if item["owned"]),
        "family_shared_count": sum(1 for item in items if item["family_shared"]),
        "probable_family_shared_count": sum(1 for item in items if item["access_type"] == "probable_family_shared"),
        "playable_without_buying_count": sum(1 for item in items if item["playable_without_buying"]),
        "advisory_only": True,
    }


def build_play_access_contract(
    wishlist,
    *,
    owned=None,
    family_appids=None,
    installed_or_playable_appids=None,
) -> dict:
    """Build local advisory play-access signals without claiming perfect ownership."""
    wishlist_records = _records(wishlist)
    owned_set = _appid_set(owned)
    family_set = _appid_set(family_appids)
    installed_set = _appid_set(installed_or_playable_appids)
    names = _name_by_appid(wishlist_records, owned, family_appids, installed_or_playable_appids)
    items: list[dict] = []
    for record in wishlist_records:
        appid = _record_appid(record)
        if not appid:
            continue
        name = _record_name(record) or names.get(appid, "")
        if appid in owned_set:
            items.append(_owned_access(appid, name))
        elif appid in family_set:
            items.append(_family_access(appid, name))
        elif appid in installed_set:
            items.append(_probable_family_access(appid, name))
    return {
        "schema": "play_access_v1",
        "source_signals": ["owned", "family", "installed_or_playable"],
        "items": items,
        "summary": _access_summary(items, len(wishlist_records)),
    }
