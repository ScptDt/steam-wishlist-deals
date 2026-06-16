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
_PLAYNITE_ACCESS_SCHEMA = "steamtools_playnite_access_v1"
_PLAYNITE_ACCESS_SOURCE = "playnite_access"
_STEAM_ACCESS_IMPORT_DEFAULT_SOURCE = "steam_access_import"
_STEAM_ACCESS_COLLECTION_KEYS = ("owned_appids", "family_shared_appids", "wishlist_appids")
_STEAM_ACCESS_WRAPPER_KEYS = ("steam_access_import", "steam_access", "access")
_STEAM_ACCESS_DIRECT_ALLOWED_KEYS = frozenset(
    {
        "schema",
        "source",
        "generated_at",
        "observed_at",
        "imported_at",
        "provenance",
        "owned_appids",
        "family_shared_appids",
        "wishlist_appids",
        "advisory_only",
        "ranking_impact",
        "summary",
    }
)
_STEAM_ACCESS_DIRECT_FORBIDDEN_KEYS = frozenset(
    {
        "cookie",
        "cookies",
        "steamloginsecure",
        "token",
        "tokens",
        "session",
        "session_id",
        "sessionid",
        "headers",
        "request_headers",
        "raw_response",
        "raw_html",
        "html",
        "password",
        "steamid",
        "steam_id",
        "profile",
        "profile_url",
        "family_member",
        "family_members",
        "family_member_name",
        "friend",
        "friends",
        "email",
        "emails",
        "command",
        "commands",
        "action",
        "mutation",
        "method",
    }
)


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


def _iter_json_keys(value) -> list[str]:
    if isinstance(value, dict):
        keys: list[str] = []
        for key, nested in value.items():
            keys.append(str(key))
            keys.extend(_iter_json_keys(nested))
        return keys
    if isinstance(value, list):
        keys: list[str] = []
        for nested in value:
            keys.extend(_iter_json_keys(nested))
        return keys
    return []


def _contains_forbidden_direct_key(key: str) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    if normalized in _STEAM_ACCESS_COLLECTION_KEYS:
        return False
    return normalized in _STEAM_ACCESS_DIRECT_FORBIDDEN_KEYS


def _strict_direct_appids(values, field: str) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{field} debe ser una lista de AppIDs numéricos")
    appids: list[str] = []
    seen: set[str] = set()
    for raw in values:
        appid = _numeric_appid(raw)
        if not appid:
            raise ValueError(f"{field} incluye un AppID inválido")
        if appid in seen:
            continue
        seen.add(appid)
        appids.append(appid)
    return appids


def validate_steam_access_direct_import(payload) -> dict:
    """Validate a direct helper import before any persistence side effect."""
    if not isinstance(payload, dict):
        raise ValueError("import directo Steam Access debe ser un objeto JSON")
    unknown_keys = set(payload) - _STEAM_ACCESS_DIRECT_ALLOWED_KEYS
    if unknown_keys:
        raise ValueError("import directo Steam Access incluye campos no permitidos")
    forbidden_keys = [key for key in _iter_json_keys(payload) if _contains_forbidden_direct_key(key)]
    if forbidden_keys:
        raise ValueError("import directo Steam Access incluye campos sensibles o acciones no permitidas")
    if payload.get("schema") != "steam_access_import_v1":
        raise ValueError("import directo Steam Access debe usar schema steam_access_import_v1")
    if payload.get("advisory_only") is not True:
        raise ValueError("import directo Steam Access debe declarar advisory_only=true")
    if payload.get("ranking_impact") != "none":
        raise ValueError("import directo Steam Access debe declarar ranking_impact=none")
    if not _has_steam_access_signal(payload):
        raise ValueError("import directo Steam Access debe incluir AppIDs")
    safe_payload = {
        "schema": "steam_access_import_v1",
        "source": _metadata_text(payload.get("source")) or "steam_browser_helper_export",
        "owned_appids": _strict_direct_appids(payload.get("owned_appids"), "owned_appids"),
        "family_shared_appids": _strict_direct_appids(
            payload.get("family_shared_appids"),
            "family_shared_appids",
        ),
        "wishlist_appids": _strict_direct_appids(payload.get("wishlist_appids"), "wishlist_appids"),
        "advisory_only": True,
        "ranking_impact": "none",
    }
    for field in ("generated_at", "observed_at", "imported_at", "provenance"):
        if value := _metadata_text(payload.get(field)):
            safe_payload[field] = value
    return normalize_steam_access_import(safe_payload)


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


def _playnite_access_items(payload: dict) -> list[dict]:
    items = payload.get("items")
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError("items debe ser una lista")
    copied: list[dict] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"items[{index}] debe ser un objeto JSON")
        copied.append(dict(item))
    return copied


def _playnite_access_platforms(item: dict, index: int) -> list[dict]:
    platforms = item.get("platforms")
    if platforms is None:
        return []
    if not isinstance(platforms, list):
        raise ValueError(f"items[{index}].platforms debe ser una lista")
    copied: list[dict] = []
    for platform_index, platform in enumerate(platforms):
        if not isinstance(platform, dict):
            raise ValueError(
                f"items[{index}].platforms[{platform_index}] debe ser un objeto JSON"
            )
        copied.append(dict(platform))
    return copied


def _playnite_access_play_state(platforms: list[dict]) -> str:
    if any(platform.get("installed") is True for platform in platforms):
        return "installed"
    if any(
        platform.get("playable_hint") is True or platform.get("playable") is True
        for platform in platforms
    ):
        return "playable"
    return ""


def _playnite_access_record(item: dict, index: int, defaults: dict) -> dict | None:
    platforms = _playnite_access_platforms(item, index)
    appid = _numeric_appid(_record_appid(item))
    if not appid:
        return None
    play_state = _playnite_access_play_state(platforms)
    if not play_state:
        return None
    normalized = {
        "appid": appid,
        "source": _PLAYNITE_ACCESS_SOURCE,
        "play_state": play_state,
    }
    if name := _record_name(item):
        normalized["name"] = name
    if observed_at := _clean_text(item.get("observed_at") or defaults.get("exported_at")):
        normalized["observed_at"] = observed_at
    return normalized


def normalize_playnite_access_export(payload) -> list[dict]:
    """Normalize a privacy-minimized Playnite access export into local play-access records."""
    if not isinstance(payload, dict):
        raise ValueError("export Playnite access debe ser un objeto JSON")
    if payload.get("schema") != _PLAYNITE_ACCESS_SCHEMA:
        schema = payload.get("schema") or "missing"
        raise ValueError(f"schema Playnite access no soportado: {schema}")
    normalized: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    defaults = {"exported_at": payload.get("exported_at")}
    for index, item in enumerate(_playnite_access_items(payload)):
        record = _playnite_access_record(item, index, defaults)
        if not record:
            continue
        fingerprint = (record["appid"], record["source"], record["play_state"])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        normalized.append(record)
    return normalized


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
    if isinstance(payload, dict) and payload.get("schema") == _PLAYNITE_ACCESS_SCHEMA:
        return normalize_playnite_access_export(payload)
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
