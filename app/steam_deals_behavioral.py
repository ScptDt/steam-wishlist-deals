from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from app.steam_deals_tags import steam_tag_key


BEHAVIORAL_SIGNALS_SCHEMA = "behavioral_signals_v1"
BEHAVIORAL_EXPLANATIONS_SCHEMA = "behavioral_explanations_v1"
PLAYER_BEHAVIOR_PROFILE_SCHEMA = "player_behavior_profile_v1"
PLAYER_BEHAVIOR_FIT_SCHEMA = "player_behavior_fit_v1"
DECISION_SUPPORT_SCHEMA = "decision_support_v1"
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
_PROFILE_SOURCE_ORDER = (
    "manual_preferences",
    "local_activity",
    "library_summary",
    "wishlist_terms",
    "personalized_recommendations.profile",
)
_PROFILE_SOURCE_WEIGHTS = {
    "manual_preferences": 3.0,
    "local_activity": 2.0,
    "library_summary": 1.5,
    "wishlist_terms": 1.0,
    "personalized_recommendations.profile": 1.0,
}
_PROFILE_LIMITATIONS = ["local_snapshot", "not_purchase_advice", "ranking_impact_none"]
_DECISION_LIMITATIONS = ["local_snapshot", "not_purchase_advice", "ranking_impact_none"]
_DECISION_LABEL_ORDER = ("good_fit", "maybe", "weak_fit")
_DECISION_CAUTION_ORDER = ("partial_player_profile", "low_confidence", "limited_preference_match")
_PROFILE_ACTIVITY_FIELDS = (
    "playtime_2weeks",
    "playtime_forever",
    "hours_played",
    "hours",
    "recent_hours",
    "total_hours",
)
_PROFILE_PREFERRED_LIMIT = 5
_MANUAL_PREFERENCE_ID_FIELDS = {
    "preferred_families": "preferred_families",
    "families": "preferred_families",
    "preferred_loops": "preferred_loops",
    "behavioral_loops": "preferred_loops",
    "preferred_descriptors": "preferred_descriptors",
    "descriptors": "preferred_descriptors",
}
_MANUAL_PREFERENCE_TERM_FIELDS = {
    "preferred_terms": "preferred_terms",
    "terms": "preferred_terms",
    "tags": "tags",
    "genres": "genres",
}
_MANUAL_PREFERENCE_GAME_FIELDS = ("favorite_games", "comfort_games", "liked_games")
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


def _profile_source_order(values: Iterable[str]) -> list[str]:
    value_set = {value for value in values if value}
    ordered = [value for value in _PROFILE_SOURCE_ORDER if value in value_set]
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


def _empty_player_profile(status: str, reason: str, taxonomy: dict | None = None) -> dict:
    return {
        "schema": PLAYER_BEHAVIOR_PROFILE_SCHEMA,
        "status": status,
        "reason": reason,
        "reasons": [reason] if reason else [],
        "advisory_only": True,
        "ranking_impact": "none",
        "profile_scope": "local_run",
        "confidence": "unknown",
        "source_signals": [],
        "summary": {
            "families_count": 0,
            "loops_count": 0,
            "descriptors_count": 0,
            "opt_in_sources_count": 0,
            "advisory_only": True,
            "ranking_impact": "none",
            **_taxonomy_summary(taxonomy),
        },
        "preferred_families": [],
        "preferred_loops": [],
        "preferred_descriptors": [],
        "evidence_summary": {
            "manual_preferences_count": 0,
            "activity_terms_count": 0,
            "library_terms_count": 0,
            "wishlist_terms_count": 0,
            "personalized_profile_terms_count": 0,
        },
        "limitations": list(_PROFILE_LIMITATIONS),
    }


def _empty_player_fit(status: str, reason: str, taxonomy: dict | None = None) -> dict:
    return {
        "schema": PLAYER_BEHAVIOR_FIT_SCHEMA,
        "source_schemas": [PLAYER_BEHAVIOR_PROFILE_SCHEMA, BEHAVIORAL_SIGNALS_SCHEMA],
        "status": status,
        "reason": reason,
        "reasons": [reason] if reason else [],
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
        "limitations": list(_PROFILE_LIMITATIONS),
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


def _manual_preference_records(value: Any) -> list[dict]:
    records = []
    for record in _as_records(value):
        item = {
            field: _terms_from_value(record.get(field))
            for field in _TERM_FIELDS
            if _terms_from_value(record.get(field))
        }
        if item:
            records.append(item)
    return records


def normalize_player_manual_preferences(payload: Any) -> dict:
    """Normalize explicit local player preferences into allowed profile signals."""
    if payload in (None, ""):
        return {}
    if not isinstance(payload, dict):
        raise ValueError("debe ser un objeto JSON")
    source = payload.get("manual_preferences") if isinstance(payload.get("manual_preferences"), dict) else payload
    if not isinstance(source, dict):
        raise ValueError("manual_preferences debe ser un objeto JSON")
    normalized: dict[str, Any] = {}
    for field, target in _MANUAL_PREFERENCE_ID_FIELDS.items():
        values = _profile_terms_from_value(source.get(field))
        if values:
            normalized.setdefault(target, []).extend(values)
    for field, target in _MANUAL_PREFERENCE_TERM_FIELDS.items():
        values = _profile_terms_from_value(source.get(field))
        if values:
            normalized.setdefault(target, []).extend(values)
    for field in _MANUAL_PREFERENCE_GAME_FIELDS:
        records = _manual_preference_records(source.get(field))
        if records:
            normalized[field] = records
    return normalized


def load_player_manual_preferences(json_path: Path | str | None) -> dict:
    """Load explicit local player preference JSON without network access."""
    if json_path is None:
        return {}
    path = Path(json_path).expanduser()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"No se pudo leer JSON de preferencias del jugador ({path}): {exc}") from exc
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "JSON de preferencias del jugador inválido "
            f"({path}): {exc.msg} en línea {exc.lineno}, columna {exc.colno}"
        ) from exc
    try:
        return normalize_player_manual_preferences(payload)
    except ValueError as exc:
        raise ValueError(f"JSON de preferencias del jugador inválido ({path}): {exc}") from exc


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


def _profile_positive_number(value: Any) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _profile_terms_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        for key in ("term", *_LABEL_KEYS, "id"):
            label = _clean_text(value.get(key))
            if label:
                return [label]
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        terms: list[str] = []
        for item in value:
            terms.extend(_profile_terms_from_value(item))
        return terms
    text = _clean_text(value)
    return [text] if text else []


def _profile_terms_from_record(record: dict) -> list[str]:
    terms: list[str] = []
    for field in _TERM_FIELDS:
        terms.extend(_terms_from_value(record.get(field)))
    return terms


def _profile_terms_from_records(records: Any) -> list[str]:
    terms: list[str] = []
    for record in _as_records(records):
        terms.extend(_profile_terms_from_record(record))
    return terms


def _profile_terms_from_summary(summary: Any) -> list[str]:
    if not isinstance(summary, dict):
        return _profile_terms_from_value(summary)
    terms: list[str] = []
    for field in ("activity_terms", "library_terms", "top_terms", "genre_distribution"):
        terms.extend(_profile_terms_from_value(summary.get(field)))
    return terms


def _profile_active_records(records: Any) -> list[dict]:
    return [
        record
        for record in _as_records(records)
        if any(_profile_positive_number(record.get(field)) > 0 for field in _PROFILE_ACTIVITY_FIELDS)
    ]


def _profile_taxonomy_id(taxonomy: dict, section: str, value: Any) -> str:
    text = _clean_text(value)
    entries = taxonomy.get(section)
    if not text or not isinstance(entries, dict):
        return ""
    if text in entries:
        return text
    key = steam_tag_key(text)
    for entry_id, entry in entries.items():
        label = entry.get("label") if isinstance(entry, dict) else ""
        if key in {steam_tag_key(entry_id), steam_tag_key(label)}:
            return entry_id
    return ""


def _profile_add_entry(bucket: dict, entry_id: str, source: str, weight: float, confidence: str) -> None:
    if not entry_id:
        return
    current = bucket.setdefault(entry_id, {"weight": 0.0, "sources": set(), "confidences": []})
    current["weight"] = _profile_positive_number(current.get("weight")) + weight
    current["sources"].add(source)
    if confidence in _CONFIDENCE_RANK:
        current["confidences"].append(confidence)


def _profile_add_mapping(buckets: dict, mapping: dict, source: str, weight: float) -> int:
    confidence = mapping.get("base_confidence", "unknown") if isinstance(mapping, dict) else "unknown"
    matched = 0
    for mapping_key, bucket_key in (
        ("families", "families"),
        ("behavioral_loops", "behavioral_loops"),
        ("descriptors", "descriptors"),
    ):
        for entry_id in mapping.get(mapping_key, []) if isinstance(mapping, dict) else []:
            _profile_add_entry(buckets[bucket_key], _clean_text(entry_id), source, weight, confidence)
            matched += 1
    return matched


def _profile_add_terms(buckets: dict, terms: Iterable[str], mappings: dict[str, dict], source: str) -> int:
    matched = 0
    seen: set[str] = set()
    for term in terms:
        key = steam_tag_key(term)
        if not key or key in seen:
            continue
        seen.add(key)
        mapping = mappings.get(key)
        if mapping:
            matched += _profile_add_mapping(
                buckets,
                mapping,
                source,
                _PROFILE_SOURCE_WEIGHTS.get(source, 1.0),
            )
    return matched


def _profile_add_exact_ids(buckets: dict, taxonomy: dict, section: str, values: Any, source: str) -> int:
    bucket_key = "behavioral_loops" if section == "behavioral_loops" else section
    matched = 0
    for value in _profile_terms_from_value(values):
        entry_id = _profile_taxonomy_id(taxonomy, section, value)
        if entry_id:
            _profile_add_entry(
                buckets[bucket_key],
                entry_id,
                source,
                _PROFILE_SOURCE_WEIGHTS.get(source, 1.0),
                "high" if source == "manual_preferences" else "medium",
            )
            matched += 1
    return matched


def _profile_ingest_manual(buckets: dict, taxonomy: dict, mappings: dict[str, dict], manual: Any) -> int:
    source = "manual_preferences"
    if not manual:
        return 0
    if not isinstance(manual, dict):
        terms = _profile_terms_from_value(manual)
        exact = sum(
            _profile_add_exact_ids(buckets, taxonomy, section, terms, source)
            for section in ("families", "behavioral_loops", "descriptors")
        )
        return exact + _profile_add_terms(buckets, terms, mappings, source)
    exact = 0
    exact += _profile_add_exact_ids(buckets, taxonomy, "families", manual.get("preferred_families") or manual.get("families"), source)
    exact += _profile_add_exact_ids(buckets, taxonomy, "behavioral_loops", manual.get("preferred_loops") or manual.get("behavioral_loops"), source)
    exact += _profile_add_exact_ids(buckets, taxonomy, "descriptors", manual.get("preferred_descriptors") or manual.get("descriptors"), source)
    terms: list[str] = []
    for field in ("terms", "preferred_terms", "tags", "genres"):
        terms.extend(_profile_terms_from_value(manual.get(field)))
    for field in ("favorite_games", "comfort_games", "liked_games"):
        terms.extend(_profile_terms_from_records(manual.get(field)))
    return exact + _profile_add_terms(buckets, terms, mappings, source)


def _profile_ingest_terms(buckets: dict, mappings: dict[str, dict], terms: Iterable[str], source: str) -> int:
    return _profile_add_terms(buckets, terms, mappings, source)


def _profile_ingest_personalized_profile(buckets: dict, mappings: dict[str, dict], payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else payload
    if not isinstance(profile, dict):
        return 0
    terms = _profile_terms_from_summary(profile)
    terms.extend(_profile_terms_from_summary(profile.get("library_summary")))
    return _profile_ingest_terms(buckets, mappings, terms, "personalized_recommendations.profile")


def _profile_entry_confidence(info: dict) -> str:
    confidence = _confidence(info.get("confidences", []))
    source_count = len(info.get("sources", set()))
    if confidence == "unknown":
        return "medium" if source_count >= 2 else "low"
    if confidence == "low" and source_count >= 2:
        return "medium"
    return confidence


def _profile_strength(info: dict) -> str:
    weight = _profile_positive_number(info.get("weight"))
    source_count = len(info.get("sources", set()))
    if weight >= 4.0 or (source_count >= 2 and weight >= 2.5):
        return "strong"
    if weight >= 2.0 or source_count >= 2:
        return "medium"
    return "weak"


def _profile_preferred_records(bucket: dict, taxonomy: dict, section: str) -> list[dict]:
    order = {entry_id: index for index, entry_id in enumerate(taxonomy.get(section, {}).keys())}
    records = sorted(
        bucket.items(),
        key=lambda item: (
            -_profile_positive_number(item[1].get("weight")),
            -len(item[1].get("sources", set())),
            order.get(item[0], 9999),
            item[0],
        ),
    )
    return [
        {
            "id": entry_id,
            "label": _taxonomy_label(taxonomy, section, entry_id),
            "strength": _profile_strength(info),
            "confidence": _profile_entry_confidence(info),
        }
        for entry_id, info in records[:_PROFILE_PREFERRED_LIMIT]
    ]


def _profile_overall_confidence(status: str, sources: list[str], has_manual: bool, total_preferences: int) -> str:
    if status == "partial":
        return "low"
    if status != "available":
        return "unknown"
    if has_manual and len(sources) >= 2 and total_preferences >= 4:
        return "high"
    return "medium"


def _player_profile_gap_reasons(sources: list[str]) -> list[str]:
    reasons: list[str] = []
    if "manual_preferences" not in sources:
        reasons.append("manual_preferences_missing")
    if "local_activity" not in sources:
        reasons.append("local_activity_unavailable")
    if "library_summary" not in sources:
        reasons.append("library_summary_unavailable")
    return reasons or ["insufficient_personal_signals"]


def _player_profile_contract(
    buckets: dict,
    taxonomy: dict,
    source_signals: Iterable[str],
    evidence_summary: dict,
    manual_matches: int,
) -> dict:
    sources = _profile_source_order(source_signals)
    families = _profile_preferred_records(buckets["families"], taxonomy, "families")
    loops = _profile_preferred_records(buckets["behavioral_loops"], taxonomy, "behavioral_loops")
    descriptors = _profile_preferred_records(buckets["descriptors"], taxonomy, "descriptors")
    total_preferences = len(families) + len(loops) + len(descriptors)
    status = "available" if manual_matches > 0 or len(sources) >= 2 else "partial"
    confidence = _profile_overall_confidence(status, sources, manual_matches > 0, total_preferences)
    payload = {
        "schema": PLAYER_BEHAVIOR_PROFILE_SCHEMA,
        "status": status,
        "advisory_only": True,
        "ranking_impact": "none",
        "profile_scope": "local_run",
        "confidence": confidence,
        "source_signals": sources,
        "summary": {
            "families_count": len(families),
            "loops_count": len(loops),
            "descriptors_count": len(descriptors),
            "opt_in_sources_count": len(sources),
            "advisory_only": True,
            "ranking_impact": "none",
            **_taxonomy_summary(taxonomy),
        },
        "preferred_families": families,
        "preferred_loops": loops,
        "preferred_descriptors": descriptors,
        "evidence_summary": evidence_summary,
        "limitations": list(_PROFILE_LIMITATIONS),
    }
    if status == "partial":
        reasons = _player_profile_gap_reasons(sources)
        payload["reason"] = reasons[0]
        payload["reasons"] = reasons
    return payload


def build_player_behavior_profile(
    *,
    manual_preferences: Any = None,
    local_activity: Any = None,
    library_summary: Any = None,
    wishlist_terms: Any = None,
    personalized_recommendations: Any = None,
    taxonomy: dict | None = None,
    taxonomy_path: Path | str | None = None,
    enabled: bool = True,
) -> dict:
    """Build an advisory, local-run profile from allowed existing signals."""
    if not enabled:
        return _empty_player_profile("unavailable", "profile_opted_out", taxonomy)
    taxonomy, taxonomy_error = _resolve_taxonomy(taxonomy, taxonomy_path)
    if taxonomy_error:
        return _empty_player_profile("unavailable", taxonomy_error)
    assert taxonomy is not None
    mappings = _normalized_mappings(taxonomy)
    buckets: dict[str, dict] = {"families": {}, "behavioral_loops": {}, "descriptors": {}}
    evidence = {
        "manual_preferences_count": 0,
        "activity_terms_count": 0,
        "library_terms_count": 0,
        "wishlist_terms_count": 0,
        "personalized_profile_terms_count": 0,
    }
    source_signals: list[str] = []
    manual_matches = _profile_ingest_manual(buckets, taxonomy, mappings, manual_preferences)
    if manual_matches:
        evidence["manual_preferences_count"] = manual_matches
        source_signals.append("manual_preferences")
    activity_matches = _profile_ingest_terms(
        buckets,
        mappings,
        _profile_terms_from_records(_profile_active_records(local_activity)),
        "local_activity",
    )
    if activity_matches:
        evidence["activity_terms_count"] = activity_matches
        source_signals.append("local_activity")
    library_terms = _profile_terms_from_summary(library_summary) or _profile_terms_from_records(library_summary)
    library_matches = _profile_ingest_terms(buckets, mappings, library_terms, "library_summary")
    if library_matches:
        evidence["library_terms_count"] = library_matches
        source_signals.append("library_summary")
    wishlist_term_values = _profile_terms_from_records(wishlist_terms) or _profile_terms_from_value(wishlist_terms)
    wishlist_matches = _profile_ingest_terms(buckets, mappings, wishlist_term_values, "wishlist_terms")
    if wishlist_matches:
        evidence["wishlist_terms_count"] = wishlist_matches
        source_signals.append("wishlist_terms")
    profile_matches = _profile_ingest_personalized_profile(buckets, mappings, personalized_recommendations)
    if profile_matches:
        evidence["personalized_profile_terms_count"] = profile_matches
        source_signals.append("personalized_recommendations.profile")
    if not any(buckets[key] for key in buckets):
        return _empty_player_profile("insufficient_signals", "insufficient_personal_signals", taxonomy)
    return _player_profile_contract(buckets, taxonomy, source_signals, evidence, manual_matches)


def _fit_profile_records(profile: dict, key: str, taxonomy: dict, section: str) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for record in _as_records(profile.get(key)):
        entry_id = _profile_taxonomy_id(taxonomy, section, record.get("id"))
        if not entry_id or entry_id in records:
            continue
        strength = record.get("strength") if record.get("strength") in {"weak", "medium", "strong"} else "weak"
        confidence = record.get("confidence") if record.get("confidence") in _CONFIDENCE_RANK else "unknown"
        records[entry_id] = {
            "id": entry_id,
            "label": _taxonomy_label(taxonomy, section, entry_id),
            "strength": strength,
            "confidence": confidence,
        }
    return records


def _fit_profile_maps(profile: dict, taxonomy: dict) -> dict[str, dict[str, dict]]:
    return {
        "families": _fit_profile_records(profile, "preferred_families", taxonomy, "families"),
        "behavioral_loops": _fit_profile_records(profile, "preferred_loops", taxonomy, "behavioral_loops"),
        "descriptors": _fit_profile_records(profile, "preferred_descriptors", taxonomy, "descriptors"),
    }


def _fit_matched_records(ids: list[str], profile_records: dict[str, dict]) -> list[dict]:
    return [dict(profile_records[entry_id]) for entry_id in ids if entry_id in profile_records]


def _fit_level(families: list[dict], loops: list[dict], descriptors: list[dict]) -> str:
    matched_groups = sum(1 for values in (families, loops, descriptors) if values)
    matched_count = len(families) + len(loops) + len(descriptors)
    if matched_groups >= 2 and matched_count >= 3:
        return "strong"
    if matched_groups >= 2 or matched_count >= 2:
        return "medium"
    return "weak"


def _fit_confidence(signal_item: dict, matches: list[dict]) -> str:
    confidences = [signal_item.get("confidence")]
    confidences.extend(record.get("confidence") for record in matches)
    confidence = _confidence(confidences)
    return "low" if confidence == "unknown" else confidence


def _fit_item(signal_item: dict, profile_maps: dict[str, dict[str, dict]], taxonomy: dict) -> dict | None:
    appid = _record_appid(signal_item)
    if not appid:
        return None
    family_ids = _valid_signal_ids(signal_item, "families", taxonomy["families"].keys())
    loop_ids = _valid_signal_ids(signal_item, "behavioral_loops", taxonomy["behavioral_loops"].keys())
    descriptor_ids = _valid_signal_ids(signal_item, "descriptors", taxonomy["descriptors"].keys())
    families = _fit_matched_records(family_ids, profile_maps["families"])
    loops = _fit_matched_records(loop_ids, profile_maps["behavioral_loops"])
    descriptors = _fit_matched_records(descriptor_ids, profile_maps["descriptors"])
    if not (families or loops or descriptors):
        return None
    matches = [*families, *loops, *descriptors]
    item = {
        "appid": appid,
        "fit_level": _fit_level(families, loops, descriptors),
        "confidence": _fit_confidence(signal_item, matches),
        "matched_families": families,
        "matched_loops": loops,
        "matched_descriptors": descriptors,
        "reason_codes": _ordered(
            (
                code
                for code, values in (
                    ("profile_family_match", families),
                    ("profile_loop_match", loops),
                    ("profile_descriptor_match", descriptors),
                )
                if values
            ),
            ("profile_family_match", "profile_loop_match", "profile_descriptor_match"),
        ),
    }
    if name := _record_name(signal_item):
        item["name"] = name
    return item


def _player_fit_contract(items: list[dict], taxonomy: dict) -> dict:
    return {
        "schema": PLAYER_BEHAVIOR_FIT_SCHEMA,
        "source_schemas": [PLAYER_BEHAVIOR_PROFILE_SCHEMA, BEHAVIORAL_SIGNALS_SCHEMA],
        "status": "available",
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": {
            "items_count": len(items),
            "families_count": len({entry["id"] for item in items for entry in item.get("matched_families", [])}),
            "loops_count": len({entry["id"] for item in items for entry in item.get("matched_loops", [])}),
            "descriptors_count": len({entry["id"] for item in items for entry in item.get("matched_descriptors", [])}),
            "confidence": _summary_confidence(items),
            "advisory_only": True,
            "ranking_impact": "none",
            **_taxonomy_summary(taxonomy),
        },
        "items": items,
        "limitations": list(_PROFILE_LIMITATIONS),
    }


def _empty_decision_support(status: str, reason: str) -> dict:
    return {
        "schema": DECISION_SUPPORT_SCHEMA,
        "source_schemas": [PLAYER_BEHAVIOR_PROFILE_SCHEMA, PLAYER_BEHAVIOR_FIT_SCHEMA],
        "status": status,
        "reason": reason,
        "reasons": [reason],
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": {
            "items_count": 0,
            "good_fit_count": 0,
            "maybe_count": 0,
            "weak_fit_count": 0,
            "confidence": "unknown",
            "advisory_only": True,
            "ranking_impact": "none",
        },
        "items": [],
        "limitations": list(_DECISION_LIMITATIONS),
    }


def _decision_label(fit_level: str, confidence: str) -> str:
    if fit_level == "strong" and confidence in {"medium", "high"}:
        return "good_fit"
    if fit_level in {"medium", "strong"}:
        return "maybe"
    return "weak_fit"


def _decision_cautions(profile_status: str, fit_level: str, confidence: str) -> list[str]:
    cautions: list[str] = []
    if profile_status == "partial":
        cautions.append("partial_player_profile")
    if confidence in {"low", "unknown"}:
        cautions.append("low_confidence")
    if fit_level == "weak":
        cautions.append("limited_preference_match")
    return _ordered(cautions, _DECISION_CAUTION_ORDER)


def _decision_preferences(item: dict) -> list[dict]:
    preferences: list[dict] = []
    for kind, key in (
        ("family", "matched_families"),
        ("behavioral_loop", "matched_loops"),
        ("descriptor", "matched_descriptors"),
    ):
        for record in _as_records(item.get(key)):
            entry_id = _clean_text(record.get("id"))
            label = _clean_text(record.get("label"))
            if not entry_id or not label:
                continue
            preferences.append(
                {
                    "kind": kind,
                    "id": entry_id,
                    "label": label,
                    "strength": record.get("strength") if record.get("strength") in {"weak", "medium", "strong"} else "weak",
                    "confidence": record.get("confidence") if record.get("confidence") in _CONFIDENCE_RANK else "unknown",
                }
            )
    return preferences[:6]


def _decision_item(item: dict, profile_status: str) -> dict | None:
    appid = _record_appid(item)
    if not appid:
        return None
    preferences = _decision_preferences(item)
    if not preferences:
        return None
    fit_level = item.get("fit_level") if item.get("fit_level") in {"weak", "medium", "strong"} else "weak"
    confidence = item.get("confidence") if item.get("confidence") in _CONFIDENCE_RANK else "unknown"
    record = {
        "appid": appid,
        "decision_label": _decision_label(fit_level, confidence),
        "fit_level": fit_level,
        "confidence": "low" if confidence == "unknown" else confidence,
        "fit_reasons": _ordered(
            item.get("reason_codes", []),
            ("profile_family_match", "profile_loop_match", "profile_descriptor_match"),
        ),
        "caution_reasons": _decision_cautions(profile_status, fit_level, confidence),
        "matched_preferences": preferences,
    }
    if name := _record_name(item):
        record["name"] = name
    return record


def _decision_support_contract(items: list[dict]) -> dict:
    label_counts = {label: sum(1 for item in items if item.get("decision_label") == label) for label in _DECISION_LABEL_ORDER}
    return {
        "schema": DECISION_SUPPORT_SCHEMA,
        "source_schemas": [PLAYER_BEHAVIOR_PROFILE_SCHEMA, PLAYER_BEHAVIOR_FIT_SCHEMA],
        "status": "available",
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": {
            "items_count": len(items),
            "good_fit_count": label_counts["good_fit"],
            "maybe_count": label_counts["maybe"],
            "weak_fit_count": label_counts["weak_fit"],
            "confidence": _summary_confidence(items),
            "advisory_only": True,
            "ranking_impact": "none",
        },
        "items": items,
        "limitations": list(_DECISION_LIMITATIONS),
    }


def build_decision_support(player_behavior_profile: Any, player_behavior_fit: Any) -> dict:
    """Build qualitative JSON-only decision support from local player fit signals."""
    if not isinstance(player_behavior_profile, dict) or player_behavior_profile.get("schema") != PLAYER_BEHAVIOR_PROFILE_SCHEMA:
        return _empty_decision_support("unavailable", "player_profile_unavailable")
    profile_status = player_behavior_profile.get("status")
    if profile_status not in {"available", "partial"}:
        return _empty_decision_support("insufficient_signals", "player_profile_insufficient")
    if not isinstance(player_behavior_fit, dict) or player_behavior_fit.get("schema") != PLAYER_BEHAVIOR_FIT_SCHEMA:
        return _empty_decision_support("unavailable", "player_behavior_fit_unavailable")
    if player_behavior_fit.get("status") not in {"available", "partial"}:
        return _empty_decision_support("insufficient_signals", "player_behavior_fit_insufficient")
    items = [item for item in (_decision_item(fit_item, str(profile_status)) for fit_item in _as_records(player_behavior_fit.get("items"))) if item]
    if not items:
        return _empty_decision_support("insufficient_signals", "insufficient_decision_context")
    return _decision_support_contract(items)


def build_player_behavior_fit(
    player_behavior_profile: Any,
    behavioral_signals: Any,
    *,
    taxonomy: dict | None = None,
    taxonomy_path: Path | str | None = None,
) -> dict:
    """Build advisory item-level fit between a local player profile and game signals."""
    taxonomy, taxonomy_error = _resolve_taxonomy(taxonomy, taxonomy_path)
    if taxonomy_error:
        return _empty_player_fit("unavailable", taxonomy_error)
    assert taxonomy is not None
    if not isinstance(player_behavior_profile, dict) or player_behavior_profile.get("schema") != PLAYER_BEHAVIOR_PROFILE_SCHEMA:
        return _empty_player_fit("unavailable", "player_profile_unavailable", taxonomy)
    if player_behavior_profile.get("status") not in {"available", "partial"}:
        return _empty_player_fit("insufficient_signals", "player_profile_insufficient", taxonomy)
    if not isinstance(behavioral_signals, dict) or behavioral_signals.get("schema") != BEHAVIORAL_SIGNALS_SCHEMA:
        return _empty_player_fit("unavailable", "behavioral_signals_unavailable", taxonomy)
    if behavioral_signals.get("status") not in {"available", "partial"}:
        return _empty_player_fit("insufficient_signals", "behavioral_signals_insufficient", taxonomy)
    profile_maps = _fit_profile_maps(player_behavior_profile, taxonomy)
    if not any(profile_maps.values()):
        return _empty_player_fit("insufficient_signals", "player_profile_insufficient", taxonomy)
    items = [
        item
        for item in (_fit_item(signal, profile_maps, taxonomy) for signal in _signal_items(behavioral_signals))
        if item
    ]
    if not items:
        return _empty_player_fit("insufficient_signals", "insufficient_behavioral_fit_matches", taxonomy)
    return _player_fit_contract(items, taxonomy)


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
