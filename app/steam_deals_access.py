from __future__ import annotations

import json
from pathlib import Path


_LOCAL_PLAY_ACCESS_COLLECTION_KEYS = (
    "installed_or_playable",
    "installed_or_playable_appids",
    "installed",
    "playable",
    "games",
    "items",
    "library",
)
_LOCAL_PLAY_ACCESS_DEFAULT_SOURCE = "local_play_access_import"
_STEAM_ACCESS_IMPORT_DEFAULT_SOURCE = "steam_access_import"
_STEAM_ACCESS_COLLECTION_KEYS = ("owned_appids", "family_shared_appids", "wishlist_appids")
_STEAM_ACCESS_WRAPPER_KEYS = ("steam_access_import", "steam_access", "access")


def _clean_text(value) -> str:
    return str(value or "").strip()


def _metadata_text(value) -> str:
    if isinstance(value, (str, int, float)):
        return _clean_text(value)
    return ""


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


def _looks_like_appid_map(payload: dict) -> bool:
    return bool(payload) and all(str(key).strip().isdigit() for key in payload)


def _numeric_appid(value) -> str:
    appid = _clean_text(value)
    if not appid.isdigit():
        return ""
    if int(appid) <= 0:
        return ""
    return appid


def _dedupe_appids(values) -> list[str]:
    appids: list[str] = []
    seen: set[str] = set()
    for record in _records(values):
        appid = _numeric_appid(_record_appid(record))
        if not appid or appid in seen:
            continue
        seen.add(appid)
        appids.append(appid)
    return appids


def _steam_access_payload(payload) -> dict:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("import Steam Access debe ser un objeto JSON")
    for key in _STEAM_ACCESS_WRAPPER_KEYS:
        if key in payload:
            nested = payload[key]
            if nested is None:
                return {}
            if not isinstance(nested, dict):
                raise ValueError(f"{key} debe ser un objeto JSON")
            return nested
    return payload


def _empty_steam_access_contract() -> dict:
    return {
        "schema": "steam_access_import_v1",
        "source": _STEAM_ACCESS_IMPORT_DEFAULT_SOURCE,
        "owned_appids": [],
        "family_shared_appids": [],
        "wishlist_appids": [],
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": {
            "owned_count": 0,
            "family_shared_count": 0,
            "wishlist_count": 0,
            "advisory_only": True,
            "ranking_impact": "none",
        },
    }


def _has_steam_access_signal(payload: dict) -> bool:
    return any(key in payload for key in _STEAM_ACCESS_COLLECTION_KEYS)


def normalize_steam_access_import(payload) -> dict:
    """Normalize a local Steam access import into safe AppID-only signals."""
    data = _steam_access_payload(payload)
    contract = _empty_steam_access_contract()
    if not data:
        return contract
    if not _has_steam_access_signal(data):
        raise ValueError("import Steam Access debe incluir 'owned_appids', 'family_shared_appids' o 'wishlist_appids'")
    source = _metadata_text(data.get("source")) or _STEAM_ACCESS_IMPORT_DEFAULT_SOURCE
    owned_appids = _dedupe_appids(data.get("owned_appids"))
    family_shared_appids = _dedupe_appids(data.get("family_shared_appids"))
    wishlist_appids = _dedupe_appids(data.get("wishlist_appids"))
    contract.update(
        {
            "source": source,
            "owned_appids": owned_appids,
            "family_shared_appids": family_shared_appids,
            "wishlist_appids": wishlist_appids,
            "summary": {
                "owned_count": len(owned_appids),
                "family_shared_count": len(family_shared_appids),
                "wishlist_count": len(wishlist_appids),
                "advisory_only": True,
                "ranking_impact": "none",
            },
        }
    )
    for field in ("steamid", "generated_at", "observed_at", "imported_at", "provenance"):
        if value := _metadata_text(data.get(field)):
            contract[field] = value
    return contract


def load_steam_access_import(json_path: Path | str | None) -> dict:
    """Load a local Steam access JSON import without login, cookies, tokens, or network."""
    if json_path is None:
        return _empty_steam_access_contract()
    path = Path(json_path).expanduser()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"No se pudo leer JSON local Steam Access ({path}): {exc}") from exc
    if not raw.strip():
        return _empty_steam_access_contract()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "JSON local Steam Access inválido "
            f"({path}): {exc.msg} en línea {exc.lineno}, columna {exc.colno}"
        ) from exc
    try:
        return normalize_steam_access_import(payload)
    except ValueError as exc:
        raise ValueError(f"JSON local Steam Access inválido ({path}): {exc}") from exc


def _local_play_access_records(payload) -> tuple[list[dict], dict]:
    if payload is None:
        return [], {}
    if isinstance(payload, list):
        return _records(payload), {}
    if not isinstance(payload, dict):
        raise ValueError("import local play_access debe ser una lista o un objeto JSON")
    if not payload:
        return [], {}
    for key in _LOCAL_PLAY_ACCESS_COLLECTION_KEYS:
        if key in payload:
            records = payload[key]
            if records is None:
                return [], payload
            if not isinstance(records, (list, dict)):
                raise ValueError(f"{key} debe ser una lista u objeto de appids")
            return _records(records), {**payload, "_collection_key": key}
    if _looks_like_appid_map(payload):
        return _records(payload), {}
    raise ValueError(
        "import local play_access debe incluir una lista en 'installed_or_playable', "
        "'installed_or_playable_appids', 'installed', 'playable', 'games', 'items' o 'library'"
    )


def _local_play_state(record: dict, defaults: dict) -> str:
    if record.get("installed") is True:
        return "installed"
    if record.get("playable") is True or record.get("playable_without_buying") is True:
        return "playable"
    state = _clean_text(record.get("play_state") or record.get("status") or record.get("state")).lower()
    if state in {"installed", "playable", "installed_or_playable"}:
        return state
    collection_key = _clean_text(defaults.get("_collection_key"))
    if collection_key in {"installed", "playable", "installed_or_playable"}:
        return collection_key
    return "installed_or_playable"


def _local_play_access_record(record: dict, defaults: dict) -> dict | None:
    appid = _record_appid(record)
    if not appid:
        return None
    play_state = _local_play_state(record, defaults)
    normalized = {
        "appid": appid,
        "source": _clean_text(record.get("source") or defaults.get("source"))
        or _LOCAL_PLAY_ACCESS_DEFAULT_SOURCE,
        "play_state": play_state,
    }
    if name := _record_name(record):
        normalized["name"] = name
    if observed_at := _clean_text(record.get("observed_at") or record.get("imported_at") or defaults.get("observed_at")):
        normalized["observed_at"] = observed_at
    return normalized


def normalize_local_play_access_import(payload) -> list[dict]:
    """Normalize an explicit local installed/playable JSON payload into app records."""
    records, defaults = _local_play_access_records(payload)
    normalized: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        item = _local_play_access_record(record, defaults)
        if not item:
            continue
        fingerprint = (item["appid"], item["source"], item["play_state"])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        normalized.append(item)
    return normalized


def load_local_play_access_import(json_path: Path | str | None) -> list[dict]:
    """Load an explicit local installed/playable JSON import without network access."""
    if json_path is None:
        return []
    path = Path(json_path).expanduser()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"No se pudo leer JSON local de play_access ({path}): {exc}") from exc
    if not raw.strip():
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "JSON local de play_access inválido "
            f"({path}): {exc.msg} en línea {exc.lineno}, columna {exc.colno}"
        ) from exc
    try:
        return normalize_local_play_access_import(payload)
    except ValueError as exc:
        raise ValueError(f"JSON local de play_access inválido ({path}): {exc}") from exc


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
