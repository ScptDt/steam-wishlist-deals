from __future__ import annotations

import json
import re
from pathlib import Path


_STORE_NAMES = {
    "amazon_games": "Amazon Games",
    "battle_net": "Battle.net",
    "ea": "EA app",
    "epic": "Epic",
    "fanatical": "Fanatical",
    "gog": "GOG",
    "humble": "Humble Store",
    "itch": "itch.io",
    "itad": "ITAD",
    "steam": "Steam",
    "ubisoft": "Ubisoft Connect",
    "unknown": "Unknown",
    "xbox": "Xbox app",
}
_STORE_ID_ALIASES = {
    "amazon": "amazon_games",
    "amazon_games_app": "amazon_games",
    "battle_net": "battle_net",
    "battlenet": "battle_net",
    "ea_app": "ea",
    "epic_games": "epic",
    "epic_games_store": "epic",
    "fanatical_com": "fanatical",
    "gog_com": "gog",
    "humble_bundle": "humble",
    "humble_bundle_store": "humble",
    "humble_store": "humble",
    "isthereanydeal": "itad",
    "is_there_any_deal": "itad",
    "itch_io": "itch",
    "microsoft_store": "xbox",
    "origin": "ea",
    "steam_store": "steam",
    "ubisoft_connect": "ubisoft",
    "uplay": "ubisoft",
    "xbox_app": "xbox",
}
_STORE_TYPES = {"library", "order_export", "bundle_export", "price_index", "catalog", "manual"}
_MATCH_METHODS = {"steam_appid", "external_id", "normalized_title", "manual"}
_CONFIDENCES = {"high", "medium", "low"}
_PLAYNITE_LIBRARY_SCHEMA = "steamtools_playnite_library_v1"
_PLAYNITE_UNMATCHED_SCHEMA = "steamtools_playnite_unmatched_v1"
_PLAYNITE_UNMATCHED_SOURCE = "playnite_unmatched"
_PLAYNITE_UNMATCHED_SIGNAL = "playnite_unmatched_review_needed"
_PLAYNITE_SOURCE_TYPES = {"official_launcher", "playnite_addon", "manual", "unknown"}
_PLAYNITE_FORBIDDEN_FIELD_IDS = {
    "accountid",
    "args",
    "arguments",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "executable",
    "game",
    "gameaction",
    "headers",
    "installdir",
    "installdirectory",
    "installpath",
    "launchargs",
    "launchcommand",
    "log",
    "logs",
    "path",
    "paths",
    "raw",
    "rawmetadata",
    "savepath",
    "saves",
    "screenshotpath",
    "screenshots",
    "script",
    "scripts",
    "token",
    "tokens",
    "username",
    "workingdir",
    "workingdirectory",
}
_OWNERSHIP_EVIDENCE = {"owned_in_user_export", "owned_in_library_export", "in_user_library", "owned"}
_BUNDLE_EVIDENCE = {"owned_in_bundle_export", "owned_in_order_export", "bundle_owned", "in_user_order"}
_CONTEXT_ONLY_EVIDENCE = {"price_only", "catalog_match", "public_bundle", "public_catalog", "discount_only", "promo_only"}
_MANUAL_EXPORT_COLLECTION_KEYS = (
    "games",
    "items",
    "library",
    "orders",
    "purchases",
    "bundles",
)
_ACCESS_DECISION_COPY = {
    "owned": {
        "label": "Ya lo tienes",
        "detail": "Comprar solo si quieres otra copia o soporte adicional.",
    },
    "family": {
        "label": "Disponible por Steam Family",
        "detail": "Comprar solo si quieres copia propia.",
    },
    "probable_family_shared": {
        "label": "Probable acceso local",
        "detail": "Revisa el acceso local antes de comprar.",
    },
    "playable_without_buying": {
        "label": "Jugable sin compra local",
        "detail": "Revisa el acceso local antes de comprar.",
    },
}
_ACCESS_DECISION_PRIORITY = ("owned", "family", "probable_family_shared", "playable_without_buying")


def _appid(record) -> str:
    if isinstance(record, dict):
        return str(record.get("appid") or record.get("steam_appid") or "").strip()
    if record is not None and str(record).strip():
        return str(record).strip()
    return ""


def _name(record) -> str:
    if not isinstance(record, dict):
        return ""
    return str(record.get("name") or record.get("steam_name") or record.get("title") or "").strip()


def _name_key(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]+", " ", value.lower())).strip()


def _clean_text(value) -> str:
    return str(value or "").strip()


def _slug(value) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", _clean_text(value).lower()).strip("_")
    return normalized or "unknown"


def _truthy(value) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "si", "sí"}
    return False


def _store_id(value) -> str:
    slug = _slug(value)
    return _STORE_ID_ALIASES.get(slug, slug)


def _enum(value, allowed: set[str], default: str) -> str:
    candidate = _slug(value)
    return candidate if candidate in allowed else default


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


def _copy_external_match_records(records, *, context: str) -> list[dict]:
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


def _manual_export_records(payload) -> tuple[list[dict], dict]:
    if isinstance(payload, list):
        return _records(payload), {}
    if not isinstance(payload, dict):
        raise ValueError("export manual debe ser una lista o un objeto JSON")
    for key in _MANUAL_EXPORT_COLLECTION_KEYS:
        if key in payload:
            records = payload[key]
            if records is None:
                return [], {**payload, "_collection_key": key}
            if not isinstance(records, list):
                raise ValueError(f"{key} debe ser una lista")
            return _records(records), {**payload, "_collection_key": key}
    raise ValueError(
        "export manual debe incluir una lista en 'games', 'items', 'library', "
        "'orders', 'purchases' o 'bundles'"
    )


def _manual_export_store_type(record: dict, defaults: dict) -> str:
    if record.get("bundle_owned") is True or record.get("bundle") is True:
        return "bundle_export"
    raw_type = record.get("store_type") or record.get("type") or defaults.get("store_type")
    source = _slug(record.get("source") or defaults.get("source"))
    collection_key = _clean_text(defaults.get("_collection_key"))
    if not raw_type and any(token in source for token in ("order", "purchase", "bundle")):
        if "bundle" in source:
            return "bundle_export"
        return "order_export"
    if not raw_type and collection_key == "bundles":
        return "bundle_export"
    if not raw_type and collection_key in {"orders", "purchases"}:
        return "order_export"
    return _enum(raw_type, _STORE_TYPES, "library")


def _manual_export_evidence(record: dict, store_type: str) -> str:
    if record.get("price_only") is True or record.get("price") is not None:
        return "price_only"
    if record.get("bundle_owned") is True or record.get("bundle") is True:
        return "owned_in_bundle_export"
    if store_type == "bundle_export":
        return "owned_in_bundle_export"
    if store_type == "order_export":
        return "owned_in_order_export"
    if record.get("owned") is False:
        return "manual_match"
    if record.get("owned") is True or store_type == "library":
        return "owned_in_user_export"
    return "manual_match"


def _manual_export_record_to_external_match(record: dict, defaults: dict) -> dict | None:
    if not isinstance(record, dict):
        return None
    external_name = _external_name(record)
    appid = _external_target_appid(record)
    if not external_name and not appid:
        return None
    store_id = _store_id(
        record.get("store_id")
        or record.get("store")
        or record.get("storefront")
        or defaults.get("store_id")
        or defaults.get("store")
        or defaults.get("storefront")
    )
    store_type = _manual_export_store_type(record, defaults)
    evidence = _clean_text(record.get("evidence")) or _manual_export_evidence(record, store_type)
    confidence = _clean_text(record.get("confidence")) or _external_confidence(record, evidence)
    normalized = {
        "store_id": store_id,
        "store_name": _store_name(
            store_id,
            record.get("store_name")
            or record.get("store")
            or record.get("storefront")
            or defaults.get("store_name")
            or defaults.get("store")
            or defaults.get("storefront"),
        ),
        "store_type": store_type,
        "source": _clean_text(record.get("source") or defaults.get("source"))
        or "manual_external_export",
        "external_name": external_name or _clean_text(record.get("steam_name")),
        "match_method": _external_match_method(record, appid),
        "confidence": _enum(confidence, _CONFIDENCES, "low"),
        "evidence": _slug(evidence),
    }
    if appid:
        normalized["wishlist_appid"] = appid
    if external_id := _clean_text(record.get("external_id") or record.get("id") or record.get("slug")):
        normalized["external_id"] = external_id
    if reason := _clean_text(record.get("reason")):
        normalized["reason"] = reason
    if observed_at := _clean_text(record.get("observed_at") or record.get("imported_at") or defaults.get("observed_at")):
        normalized["observed_at"] = observed_at
    return normalized


def normalize_manual_external_library_export(payload) -> list[dict]:
    """Normalize a user-provided local store export into external_matches records."""
    records, defaults = _manual_export_records(payload)
    normalized: list[dict] = []
    seen: set[tuple[str, ...]] = set()
    for record in records:
        match = _manual_export_record_to_external_match(record, defaults)
        if not match:
            continue
        fingerprint = (
            match["store_id"],
            match["store_type"],
            _clean_text(match.get("external_id")),
            _name_key(match["external_name"]),
            _clean_text(match.get("wishlist_appid")),
            match["evidence"],
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        normalized.append(match)
    return normalized


def _playnite_items(payload: dict) -> list[dict]:
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


def _playnite_platforms(item: dict, index: int) -> list[dict]:
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


def _safe_playnite_provider_id(value) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    if "://" in text or "/" in text or "\\" in text or re.match(r"^[a-zA-Z]:", text):
        return ""
    return text


def _looks_like_path_or_url(value) -> bool:
    text = _clean_text(value)
    if not text:
        return False
    return bool("://" in text or "\\" in text or re.search(r"(^|\s)(/|[a-zA-Z]:[\\/])", text))


def _playnite_field_id(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_text(value).lower())


def _is_forbidden_playnite_field(key) -> bool:
    key_id = _playnite_field_id(key)
    if key_id in _PLAYNITE_FORBIDDEN_FIELD_IDS:
        return True
    return key_id.startswith("raw") or key_id.endswith("path")


def _first_forbidden_playnite_field(value) -> str:
    if isinstance(value, dict):
        for key, child in value.items():
            if _is_forbidden_playnite_field(key):
                return _clean_text(key)
            nested = _first_forbidden_playnite_field(child)
            if nested:
                return nested
    if isinstance(value, list):
        for child in value:
            nested = _first_forbidden_playnite_field(child)
            if nested:
                return nested
    return ""


def _playnite_safe_identifier(value, *, field: str, index: int) -> str:
    text = _clean_text(value)
    safe = _safe_playnite_provider_id(text)
    if text and not safe:
        raise ValueError(f"items[{index}].{field} contiene ruta o URL no permitida")
    return safe


def _playnite_unmatched_items(payload: dict) -> list:
    items = payload.get("items")
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError("items debe ser una lista")
    return list(items)


def _playnite_unmatched_record(item: dict, index: int, defaults: dict) -> dict:
    if forbidden_field := _first_forbidden_playnite_field(item):
        raise ValueError(f"items[{index}] contiene campo no permitido: {forbidden_field}")
    name = _external_name(item)
    if not name:
        raise ValueError(f"items[{index}] debe incluir name")
    if _looks_like_path_or_url(name):
        raise ValueError(f"items[{index}].name contiene ruta o URL no permitida")
    store_raw = item.get("store") or item.get("store_name") or item.get("source")
    if not _clean_text(store_raw):
        raise ValueError(f"items[{index}] debe incluir store")
    if _looks_like_path_or_url(store_raw):
        raise ValueError(f"items[{index}].store contiene ruta o URL no permitida")
    store_id = _store_id(store_raw)
    reason = _clean_text(item.get("reason")) or "steam_appid_missing"
    if _looks_like_path_or_url(reason):
        reason = "manual_review"
    record = {
        "source": _PLAYNITE_UNMATCHED_SOURCE,
        "name": name,
        "store_id": store_id,
        "store_name": _store_name(store_id, store_raw),
        "reason": reason,
        "signal": _PLAYNITE_UNMATCHED_SIGNAL,
        "confidence": "low",
        "match_method": "unmatched_title",
        "advisory_only": True,
        "ranking_impact": "none",
    }
    if source_type := _enum(item.get("source_type"), _PLAYNITE_SOURCE_TYPES, "unknown"):
        record["source_type"] = source_type
    if provider_game_id := _playnite_safe_identifier(
        item.get("provider_game_id") or item.get("external_id"),
        field="provider_game_id",
        index=index,
    ):
        record["provider_game_id"] = provider_game_id
    if playnite_id := _playnite_safe_identifier(item.get("playnite_id"), field="playnite_id", index=index):
        record["playnite_id"] = playnite_id
    if observed_at := _clean_text(item.get("observed_at") or defaults.get("exported_at")):
        record["observed_at"] = observed_at
    return record


def _add_unmatched_duplicate_flags(records: list[dict]) -> list[dict]:
    title_counts: dict[str, int] = {}
    source_counts: dict[tuple[str, str], int] = {}
    for record in records:
        title_key = _name_key(record["name"])
        title_counts[title_key] = title_counts.get(title_key, 0) + 1
        source_key = (title_key, record["store_id"])
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
    flagged: list[dict] = []
    for record in records:
        title_key = _name_key(record["name"])
        flags: list[str] = []
        if title_counts.get(title_key, 0) > 1:
            flags.append("duplicate_title")
        if source_counts.get((title_key, record["store_id"]), 0) > 1:
            flags.append("duplicate_source")
        flagged.append({**record, **({"review_flags": flags} if flags else {})})
    return flagged


def normalize_playnite_unmatched_export(payload) -> list[dict]:
    """Normalize a Playnite unmatched export into safe manual-review diagnostics."""
    if not isinstance(payload, dict):
        raise ValueError("export Playnite unmatched debe ser un objeto JSON")
    if payload.get("schema") != _PLAYNITE_UNMATCHED_SCHEMA:
        raise ValueError(f"schema Playnite unmatched no soportado: {payload.get('schema') or 'missing'}")
    records: list[dict] = []
    defaults = {"exported_at": payload.get("exported_at")}
    for index, item in enumerate(_playnite_unmatched_items(payload)):
        if not isinstance(item, dict):
            raise ValueError(f"items[{index}] debe ser un objeto JSON")
        records.append(_playnite_unmatched_record(dict(item), index, defaults))
    return _add_unmatched_duplicate_flags(records)


def _playnite_confidence(platform: dict, store_id: str, source_type: str, evidence: str) -> str:
    if confidence := _clean_text(platform.get("confidence")):
        return _enum(confidence, _CONFIDENCES, "low")
    if _slug(evidence) in _CONTEXT_ONLY_EVIDENCE:
        return "low"
    if store_id != "unknown" and source_type in {"official_launcher", "playnite_addon"}:
        return "high"
    return "medium"


def _playnite_family_hint(platform: dict, store_raw) -> bool:
    store_name = _clean_text(store_raw)
    return _truthy(platform.get("family_hint")) or "steam family" in store_name.lower()


def _playnite_platform_match(item: dict, platform: dict, defaults: dict) -> dict | None:
    appid = _external_target_appid(item)
    external_name = _external_name(item)
    if appid and not appid.isdigit():
        appid = ""
    if not appid and not external_name:
        return None
    store_raw = platform.get("store") or platform.get("source") or platform.get("name")
    store_id = _store_id(store_raw)
    if not _clean_text(store_raw):
        return None
    family_hint = _playnite_family_hint(platform, store_raw)
    if store_id.startswith("steam") and not family_hint:
        return None
    source_type = _enum(platform.get("source_type"), _PLAYNITE_SOURCE_TYPES, "unknown")
    evidence = _clean_text(platform.get("evidence")) or ("family_hint" if family_hint else "playnite_library")
    store_name = _store_name(store_id, store_raw)
    match = {
        "store_id": store_id,
        "store_name": store_name,
        "store_type": "manual" if family_hint else "library",
        "source": "playnite_library",
        "external_name": external_name,
        "match_method": "steam_appid" if appid else "normalized_title",
        "confidence": "medium" if family_hint else (
            _playnite_confidence(platform, store_id, source_type, evidence)
            if appid
            else "medium"
        ),
        "evidence": _slug(evidence),
        "reason": (
            f"aparece en Playnite como {store_name}; revisar acceso/Family manualmente"
            if family_hint
            else f"aparece en Playnite: {store_name}"
        ),
    }
    if family_hint:
        match["family_hint"] = True
    if playnite_id := _safe_playnite_provider_id(item.get("playnite_id")):
        match["playnite_id"] = playnite_id
    if appid:
        match["wishlist_appid"] = appid
    if external_id := _safe_playnite_provider_id(platform.get("provider_game_id")):
        match["external_id"] = external_id
    if observed_at := _clean_text(platform.get("observed_at") or item.get("observed_at") or defaults.get("exported_at")):
        match["observed_at"] = observed_at
    return match


def normalize_playnite_library_export(payload) -> list[dict]:
    """Normalize a privacy-minimized Playnite library export into external_matches."""
    if not isinstance(payload, dict):
        raise ValueError("export Playnite debe ser un objeto JSON")
    if payload.get("schema") != _PLAYNITE_LIBRARY_SCHEMA:
        raise ValueError(f"schema Playnite no soportado: {payload.get('schema') or 'missing'}")
    normalized: list[dict] = []
    seen: set[tuple[str, ...]] = set()
    defaults = {"exported_at": payload.get("exported_at")}
    for index, item in enumerate(_playnite_items(payload)):
        for platform in _playnite_platforms(item, index):
            match = _playnite_platform_match(item, platform, defaults)
            if not match:
                continue
            fingerprint = (
                match["store_id"],
                _clean_text(match.get("external_id")),
                _clean_text(match.get("wishlist_appid")),
                _name_key(match["external_name"]),
                match["match_method"],
                "family_hint" if match.get("family_hint") is True else "",
            )
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            normalized.append(match)
    return normalized


def _external_matches_from_payload(payload) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return _copy_external_match_records(payload, context="external_matches")
    if isinstance(payload, dict):
        if not payload:
            return []
        if payload.get("schema") == _PLAYNITE_LIBRARY_SCHEMA:
            return normalize_playnite_library_export(payload)
        for key in ("external_matches", "matches"):
            if key in payload:
                return _copy_external_match_records(payload[key], context=key)
        if any(key in payload for key in _MANUAL_EXPORT_COLLECTION_KEYS):
            return normalize_manual_external_library_export(payload)
        raise ValueError(
            "debe ser una lista o un objeto con clave 'external_matches' o 'matches'"
        )
    raise ValueError("debe ser una lista o un objeto JSON")


def load_wishlist_external_matches(json_path: Path | str | None) -> list[dict]:
    """Load user-provided local external matches for wishlist hygiene."""
    if json_path is None:
        return []
    path = Path(json_path).expanduser()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            f"No se pudo leer JSON de matches externos wishlist ({path}): {exc}"
        ) from exc
    if not raw.strip():
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "JSON de matches externos wishlist inválido "
            f"({path}): {exc.msg} en línea {exc.lineno}, columna {exc.colno}"
        ) from exc
    try:
        return _external_matches_from_payload(payload)
    except ValueError as exc:
        raise ValueError(f"JSON de matches externos wishlist inválido ({path}): {exc}") from exc


def _normalize_appids(values) -> set[str]:
    return {_appid(record) for record in _records(values) if _appid(record)}


def _flatten_hltb_records(hltb_records) -> list[dict]:
    if not isinstance(hltb_records, dict):
        return _records(hltb_records)
    if any(isinstance(value, list) for value in hltb_records.values()):
        flattened: list[dict] = []
        for status, records in hltb_records.items():
            for record in _records(records):
                flattened.append({"hltb_status": str(status), **record})
        return flattened
    return _records(hltb_records)


def _index_records(records) -> tuple[dict[str, dict], dict[str, dict]]:
    by_appid: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for record in _records(records):
        if appid := _appid(record):
            by_appid[appid] = record
        if name_key := _name_key(_name(record)):
            by_name[name_key] = record
    return by_appid, by_name


def _lookup(record: dict, by_appid: dict[str, dict], by_name: dict[str, dict]) -> dict | None:
    appid = _appid(record)
    if appid and appid in by_appid:
        return by_appid[appid]
    name_key = _name_key(_name(record))
    if name_key:
        return by_name.get(name_key)
    return None


def _external_target_appid(record: dict) -> str:
    for key in ("appid", "steam_appid", "wishlist_appid"):
        value = _clean_text(record.get(key))
        if value:
            return value
    return ""


def _external_name(record: dict) -> str:
    for key in ("external_name", "name", "title", "steam_name", "wishlist_name"):
        value = _clean_text(record.get(key))
        if value:
            return value
    return ""


def _store_name(store_id: str, raw_value) -> str:
    raw_name = _clean_text(raw_value)
    if raw_name:
        return raw_name
    return _STORE_NAMES.get(store_id, store_id.replace("_", " ").title())


def _external_evidence(record: dict, store_type: str) -> str:
    evidence = _slug(record.get("evidence") or record.get("status") or record.get("ownership"))
    if evidence != "unknown":
        return evidence
    if record.get("owned") is True:
        return "owned_in_user_export"
    if record.get("bundle_owned") is True or store_type == "bundle_export":
        return "owned_in_bundle_export"
    if store_type in {"price_index", "catalog"}:
        return "price_only"
    return "manual_match"


def _external_confidence(record: dict, evidence: str) -> str:
    if confidence := _clean_text(record.get("confidence")):
        return _enum(confidence, _CONFIDENCES, "low")
    if evidence in _OWNERSHIP_EVIDENCE | _BUNDLE_EVIDENCE:
        return "high"
    return "low"


def _external_match_method(record: dict, appid: str) -> str:
    if method := _clean_text(record.get("match_method")):
        return _enum(method, _MATCH_METHODS, "normalized_title")
    if appid:
        return "steam_appid"
    if _clean_text(record.get("external_id")):
        return "external_id"
    return "normalized_title"


def _normalized_external_match(record: dict) -> dict | None:
    if not isinstance(record, dict):
        return None
    appid = _external_target_appid(record)
    external_name = _external_name(record)
    if not appid and not external_name:
        return None
    store_id = _store_id(record.get("store_id") or record.get("store") or record.get("storefront"))
    store_type = _enum(record.get("store_type") or record.get("type"), _STORE_TYPES, "manual")
    evidence = _external_evidence(record, store_type)
    normalized = {
        "store_id": store_id,
        "store_name": _store_name(store_id, record.get("store_name") or record.get("store") or record.get("storefront")),
        "store_type": store_type,
        "source": _clean_text(record.get("source")) or "manual_import",
        "external_name": external_name,
        "match_method": _external_match_method(record, appid),
        "confidence": _external_confidence(record, evidence),
        "evidence": evidence,
        "reason": _clean_text(record.get("reason")),
        "_target_appid": appid,
        "_target_name": _clean_text(record.get("wishlist_name") or record.get("steam_name")) or external_name,
    }
    if external_id := _clean_text(record.get("external_id") or record.get("id") or record.get("slug")):
        normalized["external_id"] = external_id
    if observed_at := _clean_text(record.get("observed_at") or record.get("imported_at")):
        normalized["observed_at"] = observed_at
    if _truthy(record.get("family_hint")):
        normalized["family_hint"] = True
    if playnite_id := _clean_text(record.get("playnite_id")):
        normalized["playnite_id"] = playnite_id
    for key in ("installed", "playable_hint"):
        if _truthy(record.get(key)):
            normalized[key] = True
    return normalized


def _external_signal(match: dict) -> str:
    if match["confidence"] == "low":
        return ""
    if match["evidence"] in _CONTEXT_ONLY_EVIDENCE or match["store_type"] in {"price_index", "catalog"}:
        return ""
    if match.get("family_hint") is True:
        return "external_review_needed"
    if match["confidence"] == "high":
        if match["store_type"] == "bundle_export" or match["evidence"] in _BUNDLE_EVIDENCE:
            return "external_bundle_owned"
        if match["store_type"] in {"library", "order_export", "manual"} or match["evidence"] in _OWNERSHIP_EVIDENCE:
            return "external_owned"
    return "external_review_needed"


def _external_rejection(match: dict) -> tuple[str, str]:
    if match["evidence"] in _CONTEXT_ONLY_EVIDENCE:
        return "context_only_evidence", "evidencia contextual; no prueba ownership"
    if match["store_type"] in {"price_index", "catalog"}:
        return "context_only_store_type", "precio o catálogo público; no prueba ownership"
    if match["confidence"] == "low":
        return "low_confidence", "confianza baja; no genera sugerencia de wishlist"
    return "no_actionable_signal", "sin evidencia suficiente para sugerir revisión"


def _external_diagnostic_item(index: int, status: str, code: str, message: str, match: dict | None = None) -> dict:
    item = {"index": index, "status": status, "code": code, "message": message}
    if not match:
        return item
    for key in ("store_id", "store_name", "store_type", "source", "external_name", "confidence", "evidence"):
        if value := match.get(key):
            item[key] = value
    if target_appid := _clean_text(match.get("_target_appid")):
        item["wishlist_appid"] = target_appid
    if external_id := _clean_text(match.get("external_id")):
        item["external_id"] = external_id
    return item


def _diagnose_normalized_external_match(index: int, match: dict | None) -> dict:
    if not match:
        return _external_diagnostic_item(
            index,
            "rejected",
            "missing_match_target",
            "registro sin AppID/nombre para asociar a la wishlist",
        )
    signal = _external_signal(match)
    if signal:
        item = _external_diagnostic_item(index, "accepted", signal, _external_reason(match, signal), match)
        item["signal"] = signal
        return item
    code, message = _external_rejection(match)
    return _external_diagnostic_item(index, "rejected", code, message, match)


def _diagnose_external_records(records: list, *, defaults: dict | None = None) -> list[dict]:
    items: list[dict] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            items.append(
                _external_diagnostic_item(index, "malformed", "record_not_object", "registro no es un objeto JSON")
            )
            continue
        normalized = (
            _manual_export_record_to_external_match(record, defaults)
            if defaults is not None
            else record
        )
        items.append(_diagnose_normalized_external_match(index, _normalized_external_match(normalized or {})))
    return items


def _external_diagnostic_summary(items: list[dict]) -> dict:
    signal_counts: dict[str, int] = {}
    for item in items:
        if item.get("status") != "accepted":
            continue
        signal = item.get("signal") or item.get("code")
        signal_counts[signal] = signal_counts.get(signal, 0) + 1
    return {
        "records_count": len(items),
        "accepted_count": sum(1 for item in items if item.get("status") == "accepted"),
        "rejected_count": sum(1 for item in items if item.get("status") == "rejected"),
        "malformed_count": sum(1 for item in items if item.get("status") == "malformed"),
        "signal_counts": signal_counts,
        "advisory_only": True,
        "ranking_impact": "none",
    }


def _playnite_unmatched_error_code(error_message: str) -> str:
    if "campo no permitido" in error_message:
        return "forbidden_field"
    if "ruta o URL" in error_message:
        return "unsafe_identifier"
    if "debe incluir name" in error_message:
        return "missing_name"
    if "debe incluir store" in error_message:
        return "missing_store"
    return "invalid_unmatched_record"


def _playnite_unmatched_diagnostic_item(
    index: int,
    status: str,
    code: str,
    message: str,
    record: dict | None = None,
) -> dict:
    item = {"index": index, "status": status, "code": code, "message": message}
    if not record:
        return item
    allowed = {
        "source",
        "name",
        "store_id",
        "store_name",
        "reason",
        "signal",
        "confidence",
        "match_method",
        "source_type",
        "provider_game_id",
        "playnite_id",
        "observed_at",
        "review_flags",
        "advisory_only",
        "ranking_impact",
    }
    return {**item, **{key: value for key, value in record.items() if key in allowed}}


def _playnite_unmatched_diagnostic_summary(items: list[dict]) -> dict:
    signal_counts: dict[str, int] = {}
    for item in items:
        if item.get("status") != "accepted":
            continue
        signal = item.get("signal") or item.get("code")
        signal_counts[signal] = signal_counts.get(signal, 0) + 1
    duplicate_title_count = sum(
        1
        for item in items
        if item.get("status") == "accepted" and "duplicate_title" in item.get("review_flags", [])
    )
    return {
        "records_count": len(items),
        "accepted_count": sum(1 for item in items if item.get("status") == "accepted"),
        "review_count": sum(1 for item in items if item.get("status") == "accepted"),
        "rejected_count": sum(1 for item in items if item.get("status") == "rejected"),
        "malformed_count": sum(1 for item in items if item.get("status") == "malformed"),
        "duplicate_title_count": duplicate_title_count,
        "signal_counts": signal_counts,
        "advisory_only": True,
        "ranking_impact": "none",
    }


def diagnose_playnite_unmatched_export(payload) -> dict:
    """Diagnose Playnite unmatched records without feeding ownership or ranking."""
    try:
        if payload is None or payload == [] or payload == {}:
            raw_items: list = []
            defaults: dict = {}
        elif not isinstance(payload, dict):
            raise ValueError("export Playnite unmatched debe ser un objeto JSON")
        else:
            if payload.get("schema") != _PLAYNITE_UNMATCHED_SCHEMA:
                raise ValueError(
                    f"schema Playnite unmatched no soportado: {payload.get('schema') or 'missing'}"
                )
            raw_items = _playnite_unmatched_items(payload)
            defaults = {"exported_at": payload.get("exported_at")}
    except ValueError as exc:
        summary = _playnite_unmatched_diagnostic_summary([])
        return {
            "schema": "steamtools_playnite_unmatched_diagnostic_v1",
            "status": "error",
            "items": [],
            "issues": [{"code": "invalid_playnite_unmatched_payload", "message": str(exc)}],
            "summary": summary,
        }

    records_by_index: dict[int, dict] = {}
    items: list[dict] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            items.append(
                _playnite_unmatched_diagnostic_item(
                    index,
                    "malformed",
                    "record_not_object",
                    "registro no es un objeto JSON",
                )
            )
            continue
        try:
            records_by_index[index] = _playnite_unmatched_record(dict(item), index, defaults)
        except ValueError as exc:
            message = str(exc)
            items.append(
                _playnite_unmatched_diagnostic_item(
                    index,
                    "rejected",
                    _playnite_unmatched_error_code(message),
                    message,
                )
            )

    flagged_records = _add_unmatched_duplicate_flags(list(records_by_index.values()))
    flagged_by_index = dict(zip(records_by_index, flagged_records))
    for index, record in flagged_by_index.items():
        items.append(
            _playnite_unmatched_diagnostic_item(
                index,
                "accepted",
                _PLAYNITE_UNMATCHED_SIGNAL,
                "sin AppID Steam confiable; revisión manual",
                record,
            )
        )
    items.sort(key=lambda entry: entry["index"])
    summary = _playnite_unmatched_diagnostic_summary(items)
    status = "warning" if summary["review_count"] or summary["rejected_count"] or summary["malformed_count"] else "ok"
    return {
        "schema": "steamtools_playnite_unmatched_diagnostic_v1",
        "status": status,
        "items": items,
        "issues": [],
        "summary": summary,
    }


def diagnose_wishlist_external_matches(payload) -> dict:
    """Diagnose local external_matches payloads without reading files or mutating ranking."""
    try:
        if payload is None or payload == [] or payload == {}:
            items: list[dict] = []
        elif isinstance(payload, list):
            items = _diagnose_external_records(payload)
        elif isinstance(payload, dict):
            if "external_matches" in payload or "matches" in payload:
                key = "external_matches" if "external_matches" in payload else "matches"
                records = payload.get(key)
                if records is None:
                    items = []
                elif not isinstance(records, list):
                    raise ValueError(f"{key} debe ser una lista")
                else:
                    items = _diagnose_external_records(records)
            elif payload.get("schema") == _PLAYNITE_UNMATCHED_SCHEMA:
                return diagnose_playnite_unmatched_export(payload)
            elif any(key in payload for key in _MANUAL_EXPORT_COLLECTION_KEYS):
                records, defaults = _manual_export_records(payload)
                items = _diagnose_external_records(records, defaults=defaults)
            else:
                raise ValueError("debe incluir 'external_matches', 'matches' o un export manual soportado")
        else:
            raise ValueError("debe ser una lista o un objeto JSON")
    except ValueError as exc:
        summary = _external_diagnostic_summary([])
        return {
            "status": "error",
            "items": [],
            "issues": [{"code": "invalid_external_matches_payload", "message": str(exc)}],
            "summary": summary,
        }
    summary = _external_diagnostic_summary(items)
    status = "warning" if summary["rejected_count"] or summary["malformed_count"] else "ok"
    return {"status": status, "items": items, "issues": [], "summary": summary}


def _external_reason(match: dict, signal: str) -> str:
    if match.get("reason"):
        return match["reason"]
    if signal == "external_owned":
        return f"aparece en una biblioteca externa importada: {match['store_name']}"
    if signal == "external_bundle_owned":
        return f"aparece en bundle/orden externa importada: {match['store_name']}"
    return f"revisar match externo antes de limpiar: {match['store_name']}"


def _external_public_match(match: dict) -> dict:
    return {key: value for key, value in match.items() if not key.startswith("_") and value != ""}


def _external_fingerprint(match: dict) -> tuple[str, ...]:
    return (
        match["store_id"],
        match["store_type"],
        _clean_text(match.get("external_id")),
        _name_key(match["external_name"]),
        match["evidence"],
        match["confidence"],
        _clean_text(match.get("playnite_id")),
        "family_hint" if match.get("family_hint") is True else "",
    )


def _append_external_index(index: dict[str, list[dict]], key: str, match: dict) -> None:
    if key:
        index.setdefault(key, []).append(match)


def _index_external_matches(external_matches) -> tuple[dict[str, list[dict]], dict[str, list[dict]], bool]:
    by_appid: dict[str, list[dict]] = {}
    by_name: dict[str, list[dict]] = {}
    has_external_records = False
    for record in _records(external_matches):
        match = _normalized_external_match(record)
        if not match:
            continue
        has_external_records = True
        _append_external_index(by_appid, match["_target_appid"], match)
        _append_external_index(by_name, _name_key(match["_target_name"]), match)
    return by_appid, by_name, has_external_records


def _lookup_external_matches(record: dict, by_appid: dict[str, list[dict]], by_name: dict[str, list[dict]]) -> list[dict]:
    matches = by_appid.get(_appid(record), []) + by_name.get(_name_key(_name(record)), [])
    seen: set[tuple[str, ...]] = set()
    unique: list[dict] = []
    for match in matches:
        fingerprint = _external_fingerprint(match)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(match)
    return unique


def _play_access_items(play_access) -> list[dict]:
    if not play_access:
        return []
    if isinstance(play_access, dict):
        if isinstance(play_access.get("items"), list):
            return _records(play_access["items"])
        if _appid(play_access):
            return [dict(play_access)]
        return []
    return _records(play_access)


def _index_play_access(play_access) -> tuple[dict[str, dict], dict[str, dict], bool]:
    by_appid: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    items = _play_access_items(play_access)
    for item in items:
        if appid := _appid(item):
            by_appid[appid] = item
        if name_key := _name_key(_name(item)):
            by_name[name_key] = item
    return by_appid, by_name, bool(items)


def _lookup_play_access(record: dict, by_appid: dict[str, dict], by_name: dict[str, dict]) -> dict | None:
    if appid := _appid(record):
        if appid in by_appid:
            return by_appid[appid]
    if name_key := _name_key(_name(record)):
        return by_name.get(name_key)
    return None


def _play_access_signal(access: dict) -> str:
    if not access.get("playable_without_buying"):
        return ""
    access_type = _slug(access.get("access_type"))
    if access.get("owned") is True or access_type == "owned":
        return "owned"
    if access_type == "family_shared":
        return "family"
    if access_type == "probable_family_shared" or access.get("family_shared") is True:
        return "probable_family_shared"
    return "playable_without_buying"


def _play_access_reason(access: dict, signal: str) -> str:
    if signal == "owned":
        return "ya está en tu biblioteca"
    if signal == "family":
        return "ya disponible en biblioteca familiar"
    if signal == "probable_family_shared":
        return "probablemente ya puedes jugarlo sin comprarlo"
    return "ya aparece como jugable sin compra localmente"


def _play_access_public(access: dict) -> dict:
    allowed = {
        "access_type",
        "owned",
        "family_shared",
        "playable_without_buying",
        "confidence",
        "source",
        "play_state",
        "family_hint",
        "source_details",
        "reasons",
        "advisory_only",
    }
    return {key: value for key, value in access.items() if key in allowed}


def _unique_clean_text(values) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def _review_source_from_external(match: dict) -> dict:
    source = {
        "kind": "external_match",
        "store_id": match.get("store_id"),
        "store_name": match.get("store_name"),
        "source": match.get("source"),
        "match_method": match.get("match_method"),
        "confidence": match.get("confidence"),
        "evidence": match.get("evidence"),
    }
    for key in ("external_id", "playnite_id", "reason", "observed_at"):
        if value := _clean_text(match.get(key)):
            source[key] = value
    if match.get("family_hint") is True:
        source["family_hint"] = True
    return {key: value for key, value in source.items() if value not in (None, "")}


def _review_sources_from_play_access(access: dict | None) -> list[dict]:
    if not isinstance(access, dict):
        return []
    details = access.get("source_details")
    if isinstance(details, dict):
        details = [details]
    sources: list[dict] = []
    if isinstance(details, list):
        for detail in details:
            if not isinstance(detail, dict):
                continue
            source = {
                "kind": "play_access",
                "store_name": detail.get("store_name") or access.get("source"),
                "source": detail.get("source") or access.get("source"),
            }
            for key in ("evidence", "observed_at"):
                if value := _clean_text(detail.get(key)):
                    source[key] = value
            for key in ("installed", "playable_hint", "family_hint"):
                if detail.get(key) is True:
                    source[key] = True
            sources.append({key: value for key, value in source.items() if value not in (None, "")})
    if not sources:
        source_name = _clean_text(access.get("source")) or "play_access"
        source = {"kind": "play_access", "store_name": source_name, "source": source_name}
        if access.get("family_hint") is True:
            source["family_hint"] = True
        sources.append(source)
    return sources


def _wishlist_review_context(
    external_matches: list[dict],
    play_access_match: dict | None,
) -> dict | None:
    sources = [_review_source_from_external(match) for match in external_matches]
    sources.extend(_review_sources_from_play_access(play_access_match))
    if not sources:
        return None
    source_names = _unique_clean_text(source.get("store_name") for source in sources)
    match_methods = _unique_clean_text(source.get("match_method") for source in sources)
    confidences = _unique_clean_text(source.get("confidence") for source in sources)
    has_family_hint = any(source.get("family_hint") is True for source in sources)
    installed_or_playable = bool(
        isinstance(play_access_match, dict)
        and (
            play_access_match.get("playable_without_buying") is True
            or _clean_text(play_access_match.get("play_state")) in {"installed", "playable", "installed_or_playable"}
        )
    )
    review_reasons: list[str] = []
    if len(source_names) > 1:
        review_reasons.append("multiple_launchers")
    if has_family_hint:
        review_reasons.append("family_hint")
    if installed_or_playable:
        review_reasons.append("installed_or_playable")
    if "normalized_title" in match_methods:
        review_reasons.append("normalized_title_match")
    if any(confidence != "high" for confidence in confidences):
        review_reasons.append("manual_confidence_review")
    context = {
        "sources": sources,
        "source_names": source_names,
        "source_count": len(sources),
        "multiple_sources": len(source_names) > 1,
        "family_hint": has_family_hint,
        "installed_or_playable": installed_or_playable,
        "match_methods": match_methods,
        "confidences": confidences,
        "review_reasons": review_reasons,
        "advisory_only": True,
        "ranking_impact": "none",
    }
    return {key: value for key, value in context.items() if value not in (None, [], "")}


def _append_signal(signals: list[str], reasons: list[str], signal: str, reason: str) -> None:
    if signal not in signals:
        signals.append(signal)
        reasons.append(reason)


def _access_decision(signals: list[str]) -> dict | None:
    for code in _ACCESS_DECISION_PRIORITY:
        if code not in signals:
            continue
        copy = _ACCESS_DECISION_COPY[code]
        return {
            "code": code,
            "label": copy["label"],
            "detail": copy["detail"],
            "advisory_only": True,
            "ranking_impact": "none",
        }
    return None


def _missing_local_name_reason() -> str:
    return "No tenemos nombre local para este AppID; revisa si quieres mantenerlo en wishlist"


def _appid_only_label(appid: str) -> str:
    return f"AppID {appid}" if appid else "Entrada sin appid"


def _hltb_status(record: dict) -> str:
    return str(record.get("hltb_status") or record.get("status") or "registrado").strip().lower()


def _hltb_reason(record: dict) -> str:
    status = _hltb_status(record)
    storefront = str(record.get("storefront") or record.get("store") or "").strip()
    if storefront:
        return f"aparece en HLTB local ({status}) para {storefront}"
    return f"aparece en HLTB local ({status})"


def build_wishlist_hygiene_signals(
    wishlist,
    *,
    owned=None,
    family_appids=None,
    library_games=None,
    hltb_records=None,
    known_catalog_appids=None,
    removed_appids=None,
    external_matches=None,
    play_access=None,
) -> dict:
    """Build advisory-only hygiene hints from local wishlist signals."""
    wishlist_records = _records(wishlist)
    owned_by_appid, _owned_by_name = _index_records(owned)
    owned_set = _normalize_appids(owned)
    family_set = _normalize_appids(family_appids)
    catalog_set = _normalize_appids(known_catalog_appids) if known_catalog_appids is not None else None
    removed_set = _normalize_appids(removed_appids)
    library_by_appid, library_by_name = _index_records(library_games)
    hltb_by_appid, hltb_by_name = _index_records(_flatten_hltb_records(hltb_records))
    external_by_appid, external_by_name, has_external_records = _index_external_matches(external_matches)
    access_by_appid, access_by_name, has_play_access_records = _index_play_access(play_access)
    items: list[dict] = []
    signal_counts: dict[str, int] = {}

    for index, record in enumerate(wishlist_records):
        appid = _appid(record)
        name = _name(record)
        if not name and appid and appid in owned_by_appid:
            name = _name(owned_by_appid[appid])
        signals: list[str] = []
        reasons: list[str] = []
        if not appid:
            _append_signal(signals, reasons, "invalid_appid", "entrada sin appid válido")
        if appid in owned_set:
            _append_signal(signals, reasons, "owned", "ya está en tu biblioteca")
        if appid in family_set:
            _append_signal(signals, reasons, "family", "ya disponible en biblioteca familiar")
        play_access_match = _lookup_play_access(record, access_by_appid, access_by_name)
        if play_access_match:
            access_signal = _play_access_signal(play_access_match)
            if access_signal:
                _append_signal(
                    signals,
                    reasons,
                    access_signal,
                    _play_access_reason(play_access_match, access_signal),
                )
                if not appid:
                    appid = _appid(play_access_match)
                if not name:
                    name = _name(play_access_match)
        if library_record := _lookup(record, library_by_appid, library_by_name):
            _append_signal(signals, reasons, "library_match", "aparece en biblioteca local")
            if not appid:
                appid = _appid(library_record)
            if not name:
                name = _name(library_record)
        if hltb_record := _lookup(record, hltb_by_appid, hltb_by_name):
            _append_signal(signals, reasons, "hltb_match", _hltb_reason(hltb_record))
            if not name:
                name = _name(hltb_record)
            storefront = str(hltb_record.get("storefront") or hltb_record.get("store") or "").strip().lower()
            if storefront and storefront != "steam":
                _append_signal(signals, reasons, "other_store", f"ya figura en otra tienda: {hltb_record.get('storefront') or hltb_record.get('store')}")
        if appid and appid in removed_set:
            _append_signal(signals, reasons, "catalog_removed", "marcado localmente como retirado del catálogo")
        elif catalog_set is not None and appid and appid not in catalog_set:
            _append_signal(signals, reasons, "catalog_missing", "no aparece en el catálogo local conocido")
        accepted_external_matches: list[dict] = []
        for external_match in _lookup_external_matches(record, external_by_appid, external_by_name):
            external_signal = _external_signal(external_match)
            if not external_signal:
                continue
            _append_signal(signals, reasons, external_signal, _external_reason(external_match, external_signal))
            accepted_external_matches.append(_external_public_match(external_match))
            if not appid:
                appid = external_match["_target_appid"]
        if not signals:
            continue
        missing_local_name = bool(appid and not name)
        if missing_local_name:
            reasons.insert(0, _missing_local_name_reason())
        display_name = name or _appid_only_label(appid)
        for signal in signals:
            signal_counts[signal] = signal_counts.get(signal, 0) + 1
        item = {
            "appid": appid,
            "name": display_name,
            "signals": signals,
            "reasons": reasons,
            "action": "review",
            "advisory_only": True,
            "wishlist_index": index,
        }
        if access_decision := _access_decision(signals):
            item["access_decision"] = access_decision
        if missing_local_name:
            item["missing_local_name"] = True
        if accepted_external_matches:
            item["external_matches"] = accepted_external_matches
        if play_access_match:
            item["play_access"] = _play_access_public(play_access_match)
        if review_context := _wishlist_review_context(accepted_external_matches, play_access_match):
            item["review_context"] = review_context
        items.append(item)
    source_signals = ["owned", "family", "library", "hltb", "catalog"]
    if has_play_access_records:
        source_signals.append("play_access")
    if has_external_records:
        source_signals.append("external")
    return {
        "source_signals": source_signals,
        "items": items,
        "summary": {
            "total_wishlist_items": len(wishlist_records),
            "review_items_count": len(items),
            "signal_counts": signal_counts,
            "advisory_only": True,
        },
    }
