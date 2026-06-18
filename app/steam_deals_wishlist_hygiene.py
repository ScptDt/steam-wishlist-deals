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
_PLAYNITE_SOURCE_TYPES = {"official_launcher", "playnite_addon", "manual", "unknown"}
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


def _playnite_confidence(platform: dict, store_id: str, source_type: str, evidence: str) -> str:
    if confidence := _clean_text(platform.get("confidence")):
        return _enum(confidence, _CONFIDENCES, "low")
    if _slug(evidence) in _CONTEXT_ONLY_EVIDENCE:
        return "low"
    if store_id != "unknown" and source_type in {"official_launcher", "playnite_addon"}:
        return "high"
    return "medium"


def _playnite_platform_match(item: dict, platform: dict, defaults: dict) -> dict | None:
    appid = _external_target_appid(item)
    external_name = _external_name(item)
    if appid and not appid.isdigit():
        appid = ""
    if not appid and not external_name:
        return None
    store_raw = platform.get("store") or platform.get("source") or platform.get("name")
    store_id = _store_id(store_raw)
    if store_id.startswith("steam") or not _clean_text(store_raw):
        return None
    source_type = _enum(platform.get("source_type"), _PLAYNITE_SOURCE_TYPES, "unknown")
    evidence = _clean_text(platform.get("evidence")) or "playnite_library"
    store_name = _store_name(store_id, store_raw)
    match = {
        "store_id": store_id,
        "store_name": store_name,
        "store_type": "library",
        "source": "playnite_library",
        "external_name": external_name,
        "match_method": "steam_appid" if appid else "normalized_title",
        "confidence": _playnite_confidence(platform, store_id, source_type, evidence)
        if appid
        else "medium",
        "evidence": _slug(evidence),
        "reason": f"aparece en Playnite: {store_name}",
    }
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
    return normalized


def _external_signal(match: dict) -> str:
    if match["confidence"] == "low":
        return ""
    if match["evidence"] in _CONTEXT_ONLY_EVIDENCE or match["store_type"] in {"price_index", "catalog"}:
        return ""
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
        "reasons",
        "advisory_only",
    }
    return {key: value for key, value in access.items() if key in allowed}


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
