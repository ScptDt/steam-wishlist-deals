from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from app.steam_deals_tags import steam_tag_key


BEHAVIORAL_SIGNALS_SCHEMA = "behavioral_signals_v1"
BEHAVIORAL_EXPLANATIONS_SCHEMA = "behavioral_explanations_v1"
BEHAVIORAL_TAXONOMY_SCHEMA = "behavioral_taxonomy_v1"
DEFAULT_BEHAVIORAL_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "behavioral_taxonomy_v1.json"
)

_CONFIDENCE_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
_SOURCE_ORDER = (
    "manual_taxonomy",
    "known_appid_mapping",
    "steam_tags",
    "genre_mapping",
    "category_mapping",
    "title_pattern",
    "hltb_metadata",
    "user_override",
)
_TERM_FIELDS = {
    "tags": "steam_tags",
    "steam_tags": "steam_tags",
    "genres": "genre_mapping",
    "steam_genres": "genre_mapping",
    "categories": "category_mapping",
    "steam_categories": "category_mapping",
}
_LABEL_KEYS = ("description", "name", "label", "tag", "title")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _record_appid(record: Any) -> str:
    if not isinstance(record, dict):
        return ""
    return _clean_text(record.get("appid") or record.get("steam_appid"))


def _record_name(record: dict) -> str:
    return _clean_text(record.get("name") or record.get("title") or record.get("steam_name"))


def _as_records(records: Any) -> list[dict]:
    if not records:
        return []
    if isinstance(records, dict):
        return [dict(records)]
    result: list[dict] = []
    for record in records:
        if isinstance(record, dict):
            result.append(dict(record))
    return result


def _terms_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        for key in _LABEL_KEYS:
            label = _clean_text(value.get(key))
            if label:
                return [label]
        return [_clean_text(key) for key in value if _clean_text(key)]
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        terms: list[str] = []
        for item in value:
            terms.extend(_terms_from_value(item))
        return terms
    text = _clean_text(value)
    return [text] if text else []


def _record_terms(record: dict) -> list[tuple[str, str]]:
    terms: list[tuple[str, str]] = []
    for field, source in _TERM_FIELDS.items():
        for term in _terms_from_value(record.get(field)):
            key = steam_tag_key(term)
            if key:
                terms.append((key, source))
    return terms


def _ordered(values: Iterable[str], order: Iterable[str]) -> list[str]:
    value_set = {value for value in values if value}
    return [value for value in order if value in value_set]


def _source_order(values: Iterable[str]) -> list[str]:
    value_set = {value for value in values if value}
    ordered = [value for value in _SOURCE_ORDER if value in value_set]
    return ordered + sorted(value_set - set(ordered))


def _confidence(values: Iterable[str]) -> str:
    confidences = [value for value in values if value in _CONFIDENCE_RANK]
    if not confidences:
        return "unknown"
    if any(value == "high" for value in confidences):
        return "high"
    if any(value == "medium" for value in confidences):
        return "medium"
    return "medium" if len(confidences) >= 2 else "low"


def _summary_confidence(items: list[dict]) -> str:
    if not items:
        return "unknown"
    ranks = [_CONFIDENCE_RANK.get(item.get("confidence"), 0) for item in items]
    average = sum(ranks) / len(ranks)
    if average >= _CONFIDENCE_RANK["high"]:
        return "high"
    if average >= _CONFIDENCE_RANK["medium"]:
        return "medium"
    return "low" if average >= _CONFIDENCE_RANK["low"] else "unknown"


def _taxonomy_summary(taxonomy: dict | None) -> dict:
    if not isinstance(taxonomy, dict):
        return {"taxonomy_schema": BEHAVIORAL_TAXONOMY_SCHEMA}
    return {
        "taxonomy_schema": taxonomy.get("schema") or BEHAVIORAL_TAXONOMY_SCHEMA,
        "taxonomy_version": taxonomy.get("version") or "unknown",
    }


def _empty_contract(status: str, reason: str, taxonomy: dict | None = None) -> dict:
    return {
        "schema": BEHAVIORAL_SIGNALS_SCHEMA,
        "status": status,
        "reason": reason,
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": {
            "items_count": 0,
            "families_count": 0,
            "loops_count": 0,
            "descriptors_count": 0,
            "confidence": "unknown",
            "advisory_only": True,
            "ranking_impact": "none",
            **_taxonomy_summary(taxonomy),
        },
        "items": [],
    }


def _empty_explanations(status: str, reason: str, taxonomy: dict | None = None) -> dict:
    return {
        "schema": BEHAVIORAL_EXPLANATIONS_SCHEMA,
        "source_schema": BEHAVIORAL_SIGNALS_SCHEMA,
        "status": status,
        "reason": reason,
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": {
            "items_count": 0,
            "explanations_count": 0,
            "confidence": "unknown",
            "advisory_only": True,
            "ranking_impact": "none",
            **_taxonomy_summary(taxonomy),
        },
        "items": [],
    }


def validate_behavioral_taxonomy(taxonomy: Any) -> dict:
    """Validate the versioned behavioral taxonomy and return it unchanged."""
    if not isinstance(taxonomy, dict):
        raise ValueError("behavioral taxonomy debe ser un objeto JSON")
    if taxonomy.get("schema") != BEHAVIORAL_TAXONOMY_SCHEMA:
        raise ValueError("behavioral taxonomy schema inválido")
    families = taxonomy.get("families")
    loops = taxonomy.get("behavioral_loops")
    descriptor_groups = taxonomy.get("descriptor_groups")
    descriptors = taxonomy.get("descriptors")
    reason_codes = taxonomy.get("reason_codes")
    tag_mappings = taxonomy.get("tag_mappings")
    required = (families, loops, descriptor_groups, descriptors, reason_codes, tag_mappings)
    if not all(isinstance(section, dict) for section in required):
        raise ValueError("behavioral taxonomy debe incluir secciones de objetos JSON")
    family_ids = set(families)
    loop_ids = set(loops)
    descriptor_ids = set(descriptors)
    reason_ids = set(reason_codes)
    for family_id, family in families.items():
        missing = set(family.get("loops", [])) - loop_ids
        if missing:
            raise ValueError(f"familia {family_id} referencia loops desconocidos")
    for loop_id, loop in loops.items():
        if loop.get("family") not in family_ids:
            raise ValueError(f"loop {loop_id} referencia familia desconocida")
    for group_id, members in descriptor_groups.items():
        if not isinstance(members, list):
            raise ValueError(f"grupo descriptor {group_id} debe ser lista")
        if set(members) - descriptor_ids:
            raise ValueError(f"grupo descriptor {group_id} referencia descriptors desconocidos")
    for descriptor_id, descriptor in descriptors.items():
        if descriptor.get("group") not in descriptor_groups:
            raise ValueError(f"descriptor {descriptor_id} referencia grupo desconocido")
    for tag, mapping in tag_mappings.items():
        if mapping.get("base_confidence") not in _CONFIDENCE_RANK:
            raise ValueError(f"mapping {tag} tiene confidence inválida")
        checks = (
            ("families", family_ids),
            ("behavioral_loops", loop_ids),
            ("descriptors", descriptor_ids),
            ("reason_codes", reason_ids),
        )
        for key, known in checks:
            if set(mapping.get(key, [])) - known:
                raise ValueError(f"mapping {tag} referencia {key} desconocidos")
    return taxonomy


def load_behavioral_taxonomy(json_path: Path | str | None = None) -> dict:
    """Load and validate the versioned behavioral taxonomy without network access."""
    path = Path(json_path).expanduser() if json_path else DEFAULT_BEHAVIORAL_TAXONOMY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("behavioral taxonomy no encontrada") from exc
    except OSError as exc:
        raise ValueError(f"no se pudo leer behavioral taxonomy: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"behavioral taxonomy JSON inválido: {exc.msg} en línea {exc.lineno}, columna {exc.colno}"
        ) from exc
    return validate_behavioral_taxonomy(payload)


def _resolve_taxonomy(taxonomy: dict | None, taxonomy_path: Path | str | None) -> tuple[dict | None, str | None]:
    try:
        return validate_behavioral_taxonomy(taxonomy) if taxonomy is not None else load_behavioral_taxonomy(taxonomy_path), None
    except ValueError as exc:
        reason = "taxonomy_missing" if "no encontrada" in str(exc) else "taxonomy_invalid"
        return None, reason


def _normalized_mappings(taxonomy: dict) -> dict[str, dict]:
    return {steam_tag_key(tag): mapping for tag, mapping in taxonomy["tag_mappings"].items()}


def _classify_record(record: dict, taxonomy: dict, mappings: dict[str, dict]) -> dict | None:
    appid = _record_appid(record)
    if not appid:
        return None
    families: list[str] = []
    loops: list[str] = []
    descriptors: list[str] = []
    reason_codes: list[str] = []
    sources: list[str] = []
    confidences: list[str] = []
    for term, source in _record_terms(record):
        mapping = mappings.get(term)
        if not mapping:
            continue
        families.extend(mapping.get("families", []))
        loops.extend(mapping.get("behavioral_loops", []))
        descriptors.extend(mapping.get("descriptors", []))
        reason_codes.extend(mapping.get("reason_codes", []))
        sources.append(source)
        confidences.append(mapping.get("base_confidence", "unknown"))
    families = _ordered(families, taxonomy["families"].keys())
    loops = _ordered(loops, taxonomy["behavioral_loops"].keys())
    descriptors = _ordered(descriptors, taxonomy["descriptors"].keys())
    if not (families or loops or descriptors):
        return None
    item = {
        "appid": appid,
        "families": families,
        "behavioral_loops": loops,
        "descriptors": descriptors,
        "confidence": _confidence(confidences),
        "sources": _source_order(sources),
        "reason_codes": _ordered(reason_codes, taxonomy["reason_codes"].keys()),
    }
    if name := _record_name(record):
        item["name"] = name
    return item


def _contract(items: list[dict], taxonomy: dict) -> dict:
    confidence = _summary_confidence(items)
    status = "partial" if confidence == "low" else "available"
    return {
        "schema": BEHAVIORAL_SIGNALS_SCHEMA,
        "status": status,
        "advisory_only": True,
        "ranking_impact": "none",
        "source_signals": _source_order(source for item in items for source in item.get("sources", [])),
        "summary": {
            "items_count": len(items),
            "families_count": len({family for item in items for family in item.get("families", [])}),
            "loops_count": len({loop for item in items for loop in item.get("behavioral_loops", [])}),
            "descriptors_count": len({desc for item in items for desc in item.get("descriptors", [])}),
            "confidence": confidence,
            "advisory_only": True,
            "ranking_impact": "none",
            **_taxonomy_summary(taxonomy),
        },
        "items": items,
    }


def _signal_items(signals: Any) -> list[dict]:
    if isinstance(signals, dict):
        return _as_records(signals.get("items"))
    return _as_records(signals)


def _valid_signal_ids(item: dict, key: str, known_ids: Iterable[str]) -> list[str]:
    known = set(known_ids)
    values = item.get(key)
    if not isinstance(values, list):
        return []
    return _ordered((_clean_text(value) for value in values), known_ids) if known else []


def _taxonomy_entry(taxonomy: dict, section: str, entry_id: str) -> dict:
    entries = taxonomy.get(section)
    if not isinstance(entries, dict):
        return {}
    entry = entries.get(entry_id)
    return entry if isinstance(entry, dict) else {}


def _taxonomy_label(taxonomy: dict, section: str, entry_id: str) -> str:
    entry = _taxonomy_entry(taxonomy, section, entry_id)
    return _clean_text(entry.get("label")) or entry_id.replace("_", " ")


def _explanation_records(
    taxonomy: dict,
    ids: list[str],
    *,
    section: str,
    kind: str,
    include_description: bool = False,
) -> list[dict]:
    records: list[dict] = []
    for entry_id in ids:
        entry = _taxonomy_entry(taxonomy, section, entry_id)
        record = {
            "kind": kind,
            "id": entry_id,
            "label": _taxonomy_label(taxonomy, section, entry_id),
        }
        description = _clean_text(entry.get("description")) if include_description else ""
        if description:
            record["description"] = description
        records.append(record)
    return records


def _labels(records: list[dict], limit: int) -> list[str]:
    return [_clean_text(record.get("label")) for record in records[:limit] if _clean_text(record.get("label"))]


def _join_labels(labels: list[str]) -> str:
    if len(labels) <= 1:
        return labels[0] if labels else "Sin patrón principal"
    if len(labels) == 2:
        return f"{labels[0]} + {labels[1]}"
    return f"{', '.join(labels[:-1])} + {labels[-1]}"


def _explanation_reasons(primary: list[dict], loops: list[dict], descriptors: list[dict]) -> list[str]:
    reasons: list[str] = []
    if labels := _labels(primary, 3):
        reasons.append(f"Patrones principales: {_join_labels(labels)}")
    if labels := _labels(loops, 3):
        reasons.append(f"Loops detectados: {_join_labels(labels)}")
    if labels := _labels(descriptors, 3):
        reasons.append(f"Contexto de decisión: {_join_labels(labels)}")
    return reasons[:3]


def _explanation_item(item: dict, taxonomy: dict) -> dict | None:
    appid = _record_appid(item)
    if not appid:
        return None
    families = _valid_signal_ids(item, "families", taxonomy["families"].keys())
    loops = _valid_signal_ids(item, "behavioral_loops", taxonomy["behavioral_loops"].keys())
    descriptors = _valid_signal_ids(item, "descriptors", taxonomy["descriptors"].keys())
    if not (families or loops or descriptors):
        return None
    primary = _explanation_records(
        taxonomy,
        families,
        section="families",
        kind="family",
        include_description=True,
    )[:3]
    loop_records = _explanation_records(
        taxonomy,
        loops,
        section="behavioral_loops",
        kind="behavioral_loop",
    )[:3]
    descriptor_records = _explanation_records(
        taxonomy,
        descriptors,
        section="descriptors",
        kind="descriptor",
    )[:3]
    headline_labels = _labels(primary, 2) or _labels(loop_records, 2) or _labels(descriptor_records, 2)
    explanation = {
        "appid": appid,
        "headline": _join_labels(headline_labels),
        "confidence": item.get("confidence") if item.get("confidence") in _CONFIDENCE_RANK else "unknown",
        "reasons": _explanation_reasons(primary, loop_records, descriptor_records),
        "primary_patterns": primary,
        "supporting_cues": [*loop_records, *descriptor_records][:6],
        "source_signal_ids": {
            "families": families,
            "behavioral_loops": loops,
            "descriptors": descriptors,
        },
        "sources": _source_order(item.get("sources", [])),
        "reason_codes": _ordered(item.get("reason_codes", []), taxonomy["reason_codes"].keys()),
    }
    if name := _record_name(item):
        explanation["name"] = name
    return explanation


def _explanations_contract(items: list[dict], source_status: str, taxonomy: dict) -> dict:
    status = source_status if source_status in {"available", "partial"} else "available"
    explanations_count = sum(len(item.get("reasons", [])) for item in items)
    return {
        "schema": BEHAVIORAL_EXPLANATIONS_SCHEMA,
        "source_schema": BEHAVIORAL_SIGNALS_SCHEMA,
        "status": status,
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": {
            "items_count": len(items),
            "explanations_count": explanations_count,
            "confidence": _summary_confidence(items),
            "advisory_only": True,
            "ranking_impact": "none",
            **_taxonomy_summary(taxonomy),
        },
        "items": items,
    }


def build_behavioral_signals(
    games: Any,
    *,
    taxonomy: dict | None = None,
    taxonomy_path: Path | str | None = None,
) -> dict:
    """Build advisory behavioral signals for local game/deal records."""
    taxonomy, taxonomy_error = _resolve_taxonomy(taxonomy, taxonomy_path)
    if taxonomy_error:
        return _empty_contract("unavailable", taxonomy_error)
    assert taxonomy is not None
    mappings = _normalized_mappings(taxonomy)
    items = [
        item
        for item in (_classify_record(record, taxonomy, mappings) for record in _as_records(games))
        if item
    ]
    if not items:
        return _empty_contract("insufficient_signals", "insufficient_behavioral_matches", taxonomy)
    return _contract(items, taxonomy)


def build_behavioral_explanations(
    behavioral_signals: Any,
    *,
    taxonomy: dict | None = None,
    taxonomy_path: Path | str | None = None,
) -> dict:
    """Build compact JSON-only explanations from behavioral signal items."""
    taxonomy, taxonomy_error = _resolve_taxonomy(taxonomy, taxonomy_path)
    if taxonomy_error:
        return _empty_explanations("unavailable", taxonomy_error)
    assert taxonomy is not None
    if not isinstance(behavioral_signals, dict):
        return _empty_explanations("unavailable", "no_supported_game_metadata", taxonomy)
    source_status = str(behavioral_signals.get("status") or "available")
    items = [
        item
        for item in (_explanation_item(signal, taxonomy) for signal in _signal_items(behavioral_signals))
        if item
    ]
    if not items:
        return _empty_explanations("insufficient_signals", "insufficient_behavioral_matches", taxonomy)
    return _explanations_contract(items, source_status, taxonomy)
