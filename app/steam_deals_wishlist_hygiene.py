from __future__ import annotations

import re


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
) -> dict:
    """Build advisory-only hygiene hints from local wishlist signals."""
    wishlist_records = _records(wishlist)
    owned_set = _normalize_appids(owned)
    family_set = _normalize_appids(family_appids)
    catalog_set = _normalize_appids(known_catalog_appids) if known_catalog_appids is not None else None
    removed_set = _normalize_appids(removed_appids)
    library_by_appid, library_by_name = _index_records(library_games)
    hltb_by_appid, hltb_by_name = _index_records(_flatten_hltb_records(hltb_records))
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
        if not signals:
            continue
        for signal in signals:
            signal_counts[signal] = signal_counts.get(signal, 0) + 1
        items.append(
            {
                "appid": appid,
                "name": name,
                "signals": signals,
                "reasons": reasons,
                "action": "review",
                "advisory_only": True,
                "wishlist_index": index,
            }
        )
    return {
        "source_signals": ["owned", "family", "library", "hltb", "catalog"],
        "items": items,
        "summary": {
            "total_wishlist_items": len(wishlist_records),
            "review_items_count": len(items),
            "signal_counts": signal_counts,
            "advisory_only": True,
        },
    }
