from __future__ import annotations

import json
import re
from pathlib import Path


_STORE_NAMES = {
    "epic": "Epic",
    "fanatical": "Fanatical",
    "gog": "GOG",
    "itad": "ITAD",
    "steam": "Steam",
    "unknown": "Unknown",
}
_STORE_TYPES = {"library", "order_export", "bundle_export", "price_index", "catalog", "manual"}
_MATCH_METHODS = {"steam_appid", "external_id", "normalized_title", "manual"}
_CONFIDENCES = {"high", "medium", "low"}
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
                return [], payload
            if not isinstance(records, list):
                raise ValueError(f"{key} debe ser una lista")
            return _records(records), payload
    raise ValueError(
        "export manual debe incluir una lista en 'games', 'items', 'library', "
        "'orders', 'purchases' o 'bundles'"
    )


def _manual_export_store_type(record: dict, defaults: dict) -> str:
    if record.get("bundle_owned") is True or record.get("bundle") is True:
        return "bundle_export"
    raw_type = record.get("store_type") or record.get("type") or defaults.get("store_type")
    source = _slug(record.get("source") or defaults.get("source"))
    if not raw_type and any(token in source for token in ("order", "purchase", "bundle")):
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
    store_id = _slug(
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


def _external_matches_from_payload(payload) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return _copy_external_match_records(payload, context="external_matches")
    if isinstance(payload, dict):
        if not payload:
            return []
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
    store_id = _slug(record.get("store_id") or record.get("store") or record.get("storefront"))
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


def _append_signal(signals: list[str], reasons: list[str], signal: str, reason: str) -> None:
    if signal not in signals:
        signals.append(signal)
        reasons.append(reason)


def _hltb_status(record: dict) -> str:
    return str(record.get("hltb_status") or record.get("status") or "registrado").strip().lower()


def _hltb_reason(record: dict) -> str:
    status = _hltb_status(record)
    storefront = str(record.get("storefront") or record.get("store") or "").strip()
    if storefront:
        return f"aparece en HLTB ({status}) para {storefront}"
    return f"aparece en HLTB ({status})"


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
) -> dict:
    """Build advisory-only hygiene hints from local wishlist signals."""
    wishlist_records = _records(wishlist)
    owned_set = _normalize_appids(owned)
    family_set = _normalize_appids(family_appids)
    catalog_set = _normalize_appids(known_catalog_appids) if known_catalog_appids is not None else None
    removed_set = _normalize_appids(removed_appids)
    library_by_appid, library_by_name = _index_records(library_games)
    hltb_by_appid, hltb_by_name = _index_records(_flatten_hltb_records(hltb_records))
    external_by_appid, external_by_name, has_external_records = _index_external_matches(external_matches)
    items: list[dict] = []
    signal_counts: dict[str, int] = {}

    for index, record in enumerate(wishlist_records):
        appid = _appid(record)
        name = _name(record) or (f"App {appid}" if appid else "Entrada sin appid")
        signals: list[str] = []
        reasons: list[str] = []
        if not appid:
            _append_signal(signals, reasons, "invalid_appid", "entrada sin appid válido")
        if appid in owned_set:
            _append_signal(signals, reasons, "owned", "ya está en tu biblioteca")
        if appid in family_set:
            _append_signal(signals, reasons, "family", "ya disponible en biblioteca familiar")
        if library_record := _lookup(record, library_by_appid, library_by_name):
            _append_signal(signals, reasons, "library_match", "aparece en datos locales de biblioteca")
            if not appid:
                appid = _appid(library_record)
        if hltb_record := _lookup(record, hltb_by_appid, hltb_by_name):
            _append_signal(signals, reasons, "hltb_match", _hltb_reason(hltb_record))
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
        for signal in signals:
            signal_counts[signal] = signal_counts.get(signal, 0) + 1
        item = {
            "appid": appid,
            "name": name,
            "signals": signals,
            "reasons": reasons,
            "action": "review",
            "advisory_only": True,
            "wishlist_index": index,
        }
        if accepted_external_matches:
            item["external_matches"] = accepted_external_matches
        items.append(item)
    source_signals = ["owned", "family", "library", "hltb", "catalog"]
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
