from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value)]
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _count_new_deals(deals: list[dict], previous_appids: set[str]) -> int:
    if not previous_appids:
        return 0
    return sum(1 for deal in deals if deal["appid"] not in previous_appids)


def _smart_alert_digest_total(digest: dict | None) -> int:
    if not isinstance(digest, dict):
        return 0
    try:
        return max(0, int(digest.get("total_count") or 0))
    except (TypeError, ValueError):
        return 0


def _free_weekend_now_total(payload: dict | None) -> int:
    if not isinstance(payload, dict):
        return 0
    summary = payload.get("summary")
    if isinstance(summary, dict):
        try:
            return max(0, int(summary.get("count") or 0))
        except (TypeError, ValueError):
            return 0
    items = payload.get("items")
    return len(items) if isinstance(items, list) else 0


def _external_offers_total(payload: dict | None) -> int:
    if not isinstance(payload, dict):
        return 0
    summary = payload.get("summary")
    if isinstance(summary, dict):
        try:
            return max(0, int(summary.get("items_count") or 0))
        except (TypeError, ValueError):
            return 0
    items = payload.get("items")
    return len(items) if isinstance(items, list) else 0


def _optional_dict_list(value) -> list[dict]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


TASTE_PRIORITY_CATEGORY_LABELS = {
    "compra_inmediata": "Prioridad alta para revisar",
    "espera_oferta": "Prioridad baja por gusto",
    "riesgo_abandono": "Riesgo de abandono",
    "reemplaza_varios": "Solapa con varios juegos",
    "no_comprar_aun": "No priorizar aún",
}


def _taste_priority_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return None
    items = [item for item in items if isinstance(item, dict)]
    if not items:
        return None
    category_labels = dict(TASTE_PRIORITY_CATEGORY_LABELS)
    if isinstance(payload.get("category_labels"), dict):
        category_labels.update(payload["category_labels"])
    category_labels["espera_oferta"] = TASTE_PRIORITY_CATEGORY_LABELS["espera_oferta"]
    summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
    summary.update(
        {
            "items_count": len(items),
            "advisory_only": True,
            "ranking_impact": "none",
        }
    )
    return {
        **payload,
        "items": items,
        "category_labels": category_labels,
        "summary": summary,
    }


def _taste_priority_total(payload: dict | None) -> int:
    normalized = _taste_priority_payload(payload)
    return len(normalized["items"]) if normalized else 0


def _promo_highlights_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return None
    normalized_sections = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        items = section.get("items")
        if not isinstance(items, list):
            continue
        items = [item for item in items if isinstance(item, dict)]
        if items:
            normalized_sections.append({**section, "items": items})
    sections = normalized_sections
    if not sections:
        return None
    items_count = sum(
        len(section.get("items"))
        for section in sections
        if isinstance(section.get("items"), list)
    )
    summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
    summary.update(
        {
            "promos_count": len(sections),
            "items_count": items_count,
            "advisory_only": True,
            "ranking_impact": "none",
        }
    )
    return {
        **payload,
        "sections": sections,
        "summary": summary,
    }


def _promo_highlights_total(payload: dict | None) -> int:
    normalized = _promo_highlights_payload(payload)
    return len(normalized["sections"]) if normalized else 0


def _play_access_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    items = [item for item in items if isinstance(item, dict)]
    if not items:
        return None
    summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
    summary.update(
        {
            "items_count": len(items),
            "advisory_only": True,
            "ranking_impact": "none",
        }
    )
    return {
        **payload,
        "items": items,
        "summary": summary,
        "advisory_only": True,
        "ranking_impact": "none",
    }


def _play_access_total(payload: dict | None) -> int:
    normalized = _play_access_payload(payload)
    return len(normalized["items"]) if normalized else 0


def _behavioral_signals_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != "behavioral_signals_v1":
        return None
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    items = [item for item in items if isinstance(item, dict)]
    if not items:
        return None
    summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
    summary.update(
        {
            "items_count": len(items),
            "advisory_only": True,
            "ranking_impact": "none",
        }
    )
    return {
        **payload,
        "items": items,
        "summary": summary,
        "advisory_only": True,
        "ranking_impact": "none",
    }


def _behavioral_signals_total(payload: dict | None) -> int:
    normalized = _behavioral_signals_payload(payload)
    return len(normalized["items"]) if normalized else 0


def _behavioral_explanations_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != "behavioral_explanations_v1":
        return None
    if payload.get("source_schema") != "behavioral_signals_v1":
        return None
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    items = [item for item in items if isinstance(item, dict)]
    if not items:
        return None
    explanations_count = sum(
        len(item.get("reasons"))
        for item in items
        if isinstance(item.get("reasons"), list)
    )
    summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
    summary.update(
        {
            "items_count": len(items),
            "explanations_count": explanations_count,
            "advisory_only": True,
            "ranking_impact": "none",
        }
    )
    return {
        **payload,
        "items": items,
        "summary": summary,
        "advisory_only": True,
        "ranking_impact": "none",
    }


def _behavioral_explanations_total(payload: dict | None) -> int:
    normalized = _behavioral_explanations_payload(payload)
    return len(normalized["items"]) if normalized else 0


def _profile_preferences(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    allowed_strengths = {"weak", "medium", "strong"}
    allowed_confidences = {"low", "medium", "high"}
    records = []
    for item in value:
        if not isinstance(item, dict):
            continue
        entry_id = str(item.get("id") or "").strip()
        label = str(item.get("label") or "").strip()
        if not entry_id or not label:
            continue
        record = {"id": entry_id, "label": label}
        record["strength"] = item.get("strength") if item.get("strength") in allowed_strengths else "weak"
        record["confidence"] = item.get("confidence") if item.get("confidence") in allowed_confidences else "low"
        records.append(record)
    return records


PLAYER_PROFILE_SOURCE_SIGNALS = {
    "manual_preferences",
    "local_activity",
    "library_summary",
    "wishlist_terms",
    "personalized_recommendations.profile",
}
PLAYER_PROFILE_REASONS = {
    "profile_opted_out",
    "insufficient_personal_signals",
    "manual_preferences_missing",
    "local_activity_unavailable",
    "library_summary_unavailable",
    "taxonomy_missing",
    "taxonomy_invalid",
}
PLAYER_PROFILE_LIMITATIONS = {
    "local_snapshot",
    "not_purchase_advice",
    "ranking_impact_none",
}
PLAYER_PROFILE_EVIDENCE_KEYS = (
    "manual_preferences_count",
    "activity_terms_count",
    "library_terms_count",
    "wishlist_terms_count",
    "personalized_profile_terms_count",
)


def _safe_profile_count(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _player_profile_strings(value, allowed: set[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = str(item or "").strip()
        if text in allowed and text not in result:
            result.append(text)
    return result


def _player_profile_summary(payload: dict, families: list[dict], loops: list[dict], descriptors: list[dict]) -> dict:
    raw = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    summary = {
        "families_count": len(families),
        "loops_count": len(loops),
        "descriptors_count": len(descriptors),
        "opt_in_sources_count": len(_player_profile_strings(payload.get("source_signals"), PLAYER_PROFILE_SOURCE_SIGNALS)),
        "advisory_only": True,
        "ranking_impact": "none",
    }
    taxonomy_schema = str(raw.get("taxonomy_schema") or "").strip()
    if taxonomy_schema == "behavioral_taxonomy_v1":
        summary["taxonomy_schema"] = taxonomy_schema
    taxonomy_version = str(raw.get("taxonomy_version") or "").strip()
    if taxonomy_version and len(taxonomy_version) <= 24 and "/" not in taxonomy_version and "\\" not in taxonomy_version:
        summary["taxonomy_version"] = taxonomy_version
    return summary


def _player_profile_evidence_summary(payload: dict) -> dict:
    raw = payload.get("evidence_summary") if isinstance(payload.get("evidence_summary"), dict) else {}
    return {key: _safe_profile_count(raw.get(key)) for key in PLAYER_PROFILE_EVIDENCE_KEYS}


def _player_behavior_profile_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != "player_behavior_profile_v1":
        return None
    if payload.get("status") not in {"available", "partial"}:
        return None
    families = _profile_preferences(payload.get("preferred_families"))
    loops = _profile_preferences(payload.get("preferred_loops"))
    descriptors = _profile_preferences(payload.get("preferred_descriptors"))
    if not (families or loops or descriptors):
        return None
    sources = _player_profile_strings(payload.get("source_signals"), PLAYER_PROFILE_SOURCE_SIGNALS)
    reasons = _player_profile_strings(payload.get("reasons"), PLAYER_PROFILE_REASONS)
    reason = str(payload.get("reason") or "").strip()
    if reason not in PLAYER_PROFILE_REASONS:
        reason = reasons[0] if reasons else ""
    result = {
        "schema": "player_behavior_profile_v1",
        "status": payload.get("status"),
        "advisory_only": True,
        "ranking_impact": "none",
        "profile_scope": payload.get("profile_scope") or "local_run",
        "confidence": payload.get("confidence") if payload.get("confidence") in {"low", "medium", "high"} else "unknown",
        "source_signals": sources,
        "summary": _player_profile_summary(payload, families, loops, descriptors),
        "preferred_families": families,
        "preferred_loops": loops,
        "preferred_descriptors": descriptors,
        "evidence_summary": _player_profile_evidence_summary(payload),
        "limitations": _player_profile_strings(payload.get("limitations"), PLAYER_PROFILE_LIMITATIONS),
    }
    if reason:
        result["reason"] = reason
    if reasons:
        result["reasons"] = reasons
    return result


PLAYER_BEHAVIOR_FIT_REASONS = {
    "taxonomy_missing",
    "taxonomy_invalid",
    "player_profile_unavailable",
    "player_profile_insufficient",
    "behavioral_signals_unavailable",
    "behavioral_signals_insufficient",
    "insufficient_behavioral_fit_matches",
}
PLAYER_BEHAVIOR_FIT_REASON_CODES = {
    "profile_family_match",
    "profile_loop_match",
    "profile_descriptor_match",
}
DECISION_SUPPORT_REASONS = {
    "taxonomy_invalid",
    "player_profile_unavailable",
    "player_profile_insufficient",
    "player_behavior_fit_unavailable",
    "player_behavior_fit_insufficient",
    "insufficient_decision_context",
}
DECISION_SUPPORT_LABELS = {"good_fit", "maybe", "weak_fit"}
DECISION_SUPPORT_CAUTIONS = {"partial_player_profile", "low_confidence", "limited_preference_match"}
DECISION_SUPPORT_PREFERENCE_KINDS = {"family", "behavioral_loop", "descriptor"}


def _fit_level(value) -> str:
    text = str(value or "").strip()
    return text if text in {"weak", "medium", "strong"} else "weak"


def _fit_confidence(value) -> str:
    text = str(value or "").strip()
    return text if text in {"low", "medium", "high"} else "unknown"


def _fit_reason_codes(value) -> list[str]:
    return _player_profile_strings(value, PLAYER_BEHAVIOR_FIT_REASON_CODES)


def _fit_items(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if not isinstance(item, dict):
            continue
        appid = str(item.get("appid") or "").strip()
        if not appid.isdigit():
            continue
        families = _profile_preferences(item.get("matched_families"))
        loops = _profile_preferences(item.get("matched_loops"))
        descriptors = _profile_preferences(item.get("matched_descriptors"))
        if not (families or loops or descriptors):
            continue
        record = {
            "appid": appid,
            "fit_level": _fit_level(item.get("fit_level")),
            "confidence": _fit_confidence(item.get("confidence")),
            "matched_families": families,
            "matched_loops": loops,
            "matched_descriptors": descriptors,
            "reason_codes": _fit_reason_codes(item.get("reason_codes")),
        }
        name = str(item.get("name") or "").strip()
        if name:
            record["name"] = name
        items.append(record)
    return items


def _player_behavior_fit_summary(payload: dict, items: list[dict]) -> dict:
    raw = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    summary = {
        "items_count": len(items),
        "families_count": len({entry["id"] for item in items for entry in item.get("matched_families", [])}),
        "loops_count": len({entry["id"] for item in items for entry in item.get("matched_loops", [])}),
        "descriptors_count": len({entry["id"] for item in items for entry in item.get("matched_descriptors", [])}),
        "confidence": _fit_confidence(raw.get("confidence")),
        "advisory_only": True,
        "ranking_impact": "none",
    }
    taxonomy_schema = str(raw.get("taxonomy_schema") or "").strip()
    if taxonomy_schema == "behavioral_taxonomy_v1":
        summary["taxonomy_schema"] = taxonomy_schema
    taxonomy_version = str(raw.get("taxonomy_version") or "").strip()
    if taxonomy_version and len(taxonomy_version) <= 24 and "/" not in taxonomy_version and "\\" not in taxonomy_version:
        summary["taxonomy_version"] = taxonomy_version
    return summary


def _player_behavior_fit_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != "player_behavior_fit_v1":
        return None
    if payload.get("status") not in {"available", "partial"}:
        return None
    source_schemas = payload.get("source_schemas")
    if source_schemas != ["player_behavior_profile_v1", "behavioral_signals_v1"]:
        return None
    items = _fit_items(payload.get("items"))
    if not items:
        return None
    reasons = _player_profile_strings(payload.get("reasons"), PLAYER_BEHAVIOR_FIT_REASONS)
    reason = str(payload.get("reason") or "").strip()
    if reason not in PLAYER_BEHAVIOR_FIT_REASONS:
        reason = reasons[0] if reasons else ""
    result = {
        "schema": "player_behavior_fit_v1",
        "source_schemas": ["player_behavior_profile_v1", "behavioral_signals_v1"],
        "status": payload.get("status"),
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": _player_behavior_fit_summary(payload, items),
        "items": items,
        "limitations": _player_profile_strings(payload.get("limitations"), PLAYER_PROFILE_LIMITATIONS),
    }
    if reason:
        result["reason"] = reason
    if reasons:
        result["reasons"] = reasons
    return result


def _decision_support_preferences(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    preferences = []
    for item in value:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        entry_id = str(item.get("id") or "").strip()
        label = str(item.get("label") or "").strip()
        if kind not in DECISION_SUPPORT_PREFERENCE_KINDS or not entry_id or not label:
            continue
        preferences.append(
            {
                "kind": kind,
                "id": entry_id,
                "label": label,
                "strength": item.get("strength") if item.get("strength") in {"weak", "medium", "strong"} else "weak",
                "confidence": _fit_confidence(item.get("confidence")),
            }
        )
    return preferences[:6]


def _decision_support_items(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if not isinstance(item, dict):
            continue
        appid = str(item.get("appid") or "").strip()
        label = str(item.get("decision_label") or "").strip()
        if not appid.isdigit() or label not in DECISION_SUPPORT_LABELS:
            continue
        preferences = _decision_support_preferences(item.get("matched_preferences"))
        if not preferences:
            continue
        record = {
            "appid": appid,
            "decision_label": label,
            "fit_level": _fit_level(item.get("fit_level")),
            "confidence": _fit_confidence(item.get("confidence")),
            "fit_reasons": _fit_reason_codes(item.get("fit_reasons")),
            "caution_reasons": _player_profile_strings(item.get("caution_reasons"), DECISION_SUPPORT_CAUTIONS),
            "matched_preferences": preferences,
        }
        name = str(item.get("name") or "").strip()
        if name:
            record["name"] = name
        items.append(record)
    return items


def _decision_support_summary(items: list[dict]) -> dict:
    confidence_rank = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
    confidence = max(
        (item.get("confidence") for item in items),
        default="unknown",
        key=lambda value: confidence_rank.get(value, 0),
    )
    return {
        "items_count": len(items),
        "good_fit_count": sum(1 for item in items if item.get("decision_label") == "good_fit"),
        "maybe_count": sum(1 for item in items if item.get("decision_label") == "maybe"),
        "weak_fit_count": sum(1 for item in items if item.get("decision_label") == "weak_fit"),
        "confidence": _fit_confidence(confidence),
        "advisory_only": True,
        "ranking_impact": "none",
    }


def _decision_support_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != "decision_support_v1":
        return None
    if payload.get("status") not in {"available", "partial"}:
        return None
    if payload.get("source_schemas") != ["player_behavior_profile_v1", "player_behavior_fit_v1"]:
        return None
    items = _decision_support_items(payload.get("items"))
    if not items:
        return None
    reasons = _player_profile_strings(payload.get("reasons"), DECISION_SUPPORT_REASONS)
    reason = str(payload.get("reason") or "").strip()
    if reason not in DECISION_SUPPORT_REASONS:
        reason = reasons[0] if reasons else ""
    result = {
        "schema": "decision_support_v1",
        "source_schemas": ["player_behavior_profile_v1", "player_behavior_fit_v1"],
        "status": payload.get("status"),
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": _decision_support_summary(items),
        "items": items,
        "limitations": _player_profile_strings(payload.get("limitations"), PLAYER_PROFILE_LIMITATIONS),
    }
    if reason:
        result["reason"] = reason
    if reasons:
        result["reasons"] = reasons
    return result


def _decision_support_total(payload: dict | None) -> int:
    normalized = _decision_support_payload(payload)
    return len(normalized["items"]) if normalized else 0


DECISION_ADVISOR_DECISIONS = {"comprar_ahora", "revisar", "esperar", "ignorar"}
DECISION_ADVISOR_PURCHASE_TYPES = {"comfort_pick", "stretch_pick", "aspirational_pick", "impulse_risk"}
DECISION_ADVISOR_PRIORITIES = {"alta", "media", "baja"}
DECISION_ADVISOR_CONFIDENCE = {"high", "medium", "low"}
DECISION_ADVISOR_ACCESS = {"requires_purchase", "available", "partially_available", "unknown"}


def _compact_strings(value, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    strings = []
    for item in value:
        text = str(item or "").strip()
        if "/" in text or "\\" in text:
            continue
        if text and text not in strings:
            strings.append(text[:120])
    return strings[:limit]


def _decision_advisor_items(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if not isinstance(item, dict):
            continue
        appid = str(item.get("appid") or "").strip()
        decision = str(item.get("decision") or "").strip()
        purchase_type = str(item.get("purchase_type") or "").strip()
        if not appid.isdigit() or decision not in DECISION_ADVISOR_DECISIONS:
            continue
        if purchase_type not in DECISION_ADVISOR_PURCHASE_TYPES:
            continue
        record = {
            "appid": appid,
            "decision": decision,
            "priority": item.get("priority") if item.get("priority") in DECISION_ADVISOR_PRIORITIES else "media",
            "purchase_type": purchase_type,
            "confidence": item.get("confidence") if item.get("confidence") in DECISION_ADVISOR_CONFIDENCE else "low",
            "access_status": item.get("access_status") if item.get("access_status") in DECISION_ADVISOR_ACCESS else "unknown",
            "reason": str(item.get("reason") or "limited_signals").strip()[:120],
            "positive_signals": _compact_strings(item.get("positive_signals")),
            "risks": _compact_strings(item.get("risks")),
            "source_signals": _compact_strings(item.get("source_signals")),
        }
        name = str(item.get("name") or "").strip()
        if name:
            record["name"] = name[:120]
        items.append(record)
    return items


def _decision_advisor_summary(payload: dict, items: list[dict]) -> dict:
    summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
    summary.update(
        {
            "items_count": len(items),
            "buy_now_count": sum(1 for item in items if item.get("decision") == "comprar_ahora"),
            "review_count": sum(1 for item in items if item.get("decision") == "revisar"),
            "wait_count": sum(1 for item in items if item.get("decision") == "esperar"),
            "ignore_count": sum(1 for item in items if item.get("decision") == "ignorar"),
            "impulse_risk_count": sum(1 for item in items if item.get("purchase_type") == "impulse_risk"),
            "advisory_only": True,
            "ranking_impact": "none",
        }
    )
    return summary


def _decision_advisor_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != "decision_advisor_v0":
        return None
    if payload.get("status") not in {"available", "partial"}:
        return None
    items = _decision_advisor_items(payload.get("items"))
    if not items:
        return None
    return {
        "schema": "decision_advisor_v0",
        "source_schemas": _compact_strings(payload.get("source_schemas"), limit=10),
        "status": payload.get("status"),
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": _decision_advisor_summary(payload, items),
        "items": items,
        "limitations": _compact_strings(payload.get("limitations"), limit=8),
    }


def _decision_advisor_total(payload: dict | None) -> int:
    normalized = _decision_advisor_payload(payload)
    return len(normalized["items"]) if normalized else 0


RECOMMENDATION_DIAGNOSTIC_MODES = {"behavioral", "mixed", "score_fallback"}


def _recommendation_diagnostics_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    mode = str(payload.get("recommendation_mode") or "").strip()
    if mode not in RECOMMENDATION_DIAGNOSTIC_MODES:
        return None
    return {
        **payload,
        "recommendation_mode": mode,
        "advisory_only": True,
        "ranking_impact": "none",
    }


def generate_json(
    deals: list[dict],
    backlog_on_sale: list[dict],
    have_on_sale: list[dict],
    vanity: str,
    owned: dict[str, str],
    wishlist_appids: list[str],
    min_discount: int,
    genres: list[str],
    hltb_used: bool = False,
    family_appids: set[str] | None = None,
    sale_name: str = "",
    priorities: dict[str, int] | None = None,
    historical_lows: dict[str, dict] | None = None,
    previous_appids: set[str] | None = None,
    reviews: dict[str, dict] | None = None,
    deck_compat: dict[str, int] | None = None,
    current_prices: dict[str, dict] | None = None,
    top_picks: list[dict] | None = None,
    comparison: dict | None = None,
    sort_field: str = "discount",
    tags_data: dict[str, dict] | None = None,
    local_trends: dict[str, dict] | None = None,
    active_bundles: dict[str, list[dict]] | None = None,
    protondb_data: dict[str, dict] | None = None,
    anticheat_data: dict[str, dict] | None = None,
    achievements_data: dict[str, dict] | None = None,
    watchlist_alerts: list[dict] | None = None,
    budget_result: dict | None = None,
    compare_data: dict | None = None,
    gift_ideas: list[dict] | None = None,
    compare_profiles: list[dict] | None = None,
    gift_ideas_by_friend: list[dict] | None = None,
    shared_gift_ideas: list[dict] | None = None,
    recommended_collections: list[dict] | None = None,
    personalized_recommendations: dict | None = None,
    wishlist_hygiene: dict | None = None,
    cache_coverage: dict | None = None,
    profile_display_name: str | None = None,
    active_promo_context: dict | None = None,
    smart_alert_digest: dict | None = None,
    free_weekend_now: dict | None = None,
    external_offers: dict | None = None,
    taste_priority: dict | None = None,
    recommendation_diagnostics: dict | None = None,
    promo_highlights: dict | None = None,
    play_access: dict | None = None,
    behavioral_signals: dict | None = None,
    behavioral_explanations: dict | None = None,
    player_behavior_profile: dict | None = None,
    player_behavior_fit: dict | None = None,
    decision_support: dict | None = None,
    decision_advisor: dict | None = None,
) -> str:
    previous_appids = previous_appids or set()
    family_appids = family_appids or set()
    priorities = priorities or {}
    historical_lows = historical_lows or {}
    reviews = reviews or {}
    deck_compat = deck_compat or {}
    current_prices = current_prices or {}
    top_picks = top_picks or []
    comparison = comparison or {}
    tags_data = tags_data or {}
    local_trends = local_trends or {}
    active_bundles = active_bundles or {}
    protondb_data = protondb_data or {}
    anticheat_data = anticheat_data or {}
    achievements_data = achievements_data or {}
    watchlist_alerts = watchlist_alerts or []
    gift_ideas = gift_ideas or []
    compare_profiles = _optional_dict_list(compare_profiles)
    gift_ideas_by_friend = _optional_dict_list(gift_ideas_by_friend)
    shared_gift_ideas = _optional_dict_list(shared_gift_ideas)
    recommended_collections = recommended_collections or []
    personalized_recommendations = personalized_recommendations or {"items": []}
    wishlist_hygiene = wishlist_hygiene or {"items": [], "summary": {}}
    smart_alert_digest = smart_alert_digest if isinstance(smart_alert_digest, dict) else None
    free_weekend_now = free_weekend_now if isinstance(free_weekend_now, dict) else None
    external_offers = external_offers if isinstance(external_offers, dict) else None
    taste_priority = _taste_priority_payload(taste_priority)
    recommendation_diagnostics = _recommendation_diagnostics_payload(recommendation_diagnostics)
    promo_highlights = _promo_highlights_payload(promo_highlights)
    play_access = _play_access_payload(play_access)
    behavioral_signals = _behavioral_signals_payload(behavioral_signals)
    behavioral_explanations = _behavioral_explanations_payload(behavioral_explanations)
    player_behavior_profile = _player_behavior_profile_payload(player_behavior_profile)
    player_behavior_fit = _player_behavior_fit_payload(player_behavior_fit)
    decision_support = _decision_support_payload(decision_support)
    decision_advisor = _decision_advisor_payload(decision_advisor)

    payload = {
        "meta": {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "profile": profile_display_name or vanity,
            "sale_name": sale_name or None,
        },
        "inputs": {
            "wishlist_count": len(wishlist_appids),
            "owned_count": len(owned),
            "family_count": len(family_appids),
            "min_discount": min_discount,
            "genres": genres,
            "sort_field": sort_field,
            "hltb_used": hltb_used,
        },
        "summary": {
            "deals_count": len(deals),
            "backlog_on_sale_count": len(backlog_on_sale),
            "have_on_sale_count": len(have_on_sale),
            "new_deals_count": _count_new_deals(deals, previous_appids),
            "top_picks_count": len(top_picks),
            "recommended_collections_count": len(recommended_collections),
            "personalized_recommendations_count": len(
                personalized_recommendations.get("items", [])
            ),
            "watchlist_alerts_count": len(watchlist_alerts),
            "smart_alerts_count": _smart_alert_digest_total(smart_alert_digest),
            "gift_ideas_count": len(gift_ideas),
            "wishlist_hygiene_count": len(wishlist_hygiene.get("items", [])),
            "free_weekend_now_count": _free_weekend_now_total(free_weekend_now),
            "external_offers_count": _external_offers_total(external_offers),
            "taste_priority_count": _taste_priority_total(taste_priority),
            "promo_highlights_count": _promo_highlights_total(promo_highlights),
            "play_access_count": _play_access_total(play_access),
            "behavioral_signals_count": _behavioral_signals_total(behavioral_signals),
            "behavioral_explanations_count": _behavioral_explanations_total(behavioral_explanations),
            "player_behavior_fit_count": len(player_behavior_fit.get("items", [])) if player_behavior_fit else 0,
            "decision_support_count": _decision_support_total(decision_support),
            "decision_advisor_count": _decision_advisor_total(decision_advisor),
        },
        "comparison": _json_safe(comparison),
        "top_picks": _json_safe(top_picks),
        "recommended_collections": _json_safe(recommended_collections),
        "personalized_recommendations": _json_safe(personalized_recommendations),
        "wishlist_hygiene": _json_safe(wishlist_hygiene),
        "watchlist_alerts": _json_safe(watchlist_alerts),
        "budget_result": _json_safe(budget_result),
        "compare_data": _json_safe(compare_data),
        "gift_ideas": _json_safe(gift_ideas),
        "deals": _json_safe(deals),
        "backlog_on_sale": _json_safe(backlog_on_sale),
        "have_on_sale": _json_safe(have_on_sale),
        "priorities": _json_safe(priorities),
        "reviews": _json_safe(reviews),
        "deck_compat": _json_safe(deck_compat),
        "historical_lows": _json_safe(historical_lows),
        "current_prices": _json_safe(current_prices),
        "tags_data": _json_safe(tags_data),
        "local_trends": _json_safe(local_trends),
        "active_bundles": _json_safe(active_bundles),
        "protondb_data": _json_safe(protondb_data),
        "anticheat_data": _json_safe(anticheat_data),
        "achievements_data": _json_safe(achievements_data),
    }
    if compare_profiles or gift_ideas_by_friend or shared_gift_ideas:
        payload["summary"].update(
            {
                "compare_profiles_count": len(compare_profiles),
                "gift_ideas_by_friend_count": len(gift_ideas_by_friend),
                "shared_gift_ideas_count": len(shared_gift_ideas),
            }
        )
    if compare_profiles:
        payload["compare_profiles"] = _json_safe(compare_profiles)
    if gift_ideas_by_friend:
        payload["gift_ideas_by_friend"] = _json_safe(gift_ideas_by_friend)
    if shared_gift_ideas:
        payload["shared_gift_ideas"] = _json_safe(shared_gift_ideas)
    if cache_coverage:
        payload["cache_coverage"] = _json_safe(cache_coverage)
    if active_promo_context:
        payload["meta"]["active_promo_context"] = _json_safe(active_promo_context)
    if smart_alert_digest:
        payload["smart_alert_digest"] = _json_safe(smart_alert_digest)
    if free_weekend_now:
        payload["free_weekend_now"] = _json_safe(free_weekend_now)
    if external_offers:
        payload["external_offers"] = _json_safe(external_offers)
    if taste_priority:
        payload["taste_priority"] = _json_safe(taste_priority)
    if recommendation_diagnostics:
        payload["recommendation_diagnostics"] = _json_safe(recommendation_diagnostics)
    if promo_highlights:
        payload["promo_highlights"] = _json_safe(promo_highlights)
    if play_access:
        payload["play_access"] = _json_safe(play_access)
    if behavioral_signals:
        payload["behavioral_signals"] = _json_safe(behavioral_signals)
    if behavioral_explanations:
        payload["behavioral_explanations"] = _json_safe(behavioral_explanations)
    if player_behavior_profile:
        payload["summary"].update(
            {
                "player_behavior_profile_status": player_behavior_profile.get("status"),
                "player_behavior_profile_sources_count": len(player_behavior_profile.get("source_signals", [])),
            }
        )
        payload["player_behavior_profile"] = _json_safe(player_behavior_profile)
    if player_behavior_fit:
        payload["player_behavior_fit"] = _json_safe(player_behavior_fit)
    if decision_support:
        payload["decision_support"] = _json_safe(decision_support)
    if decision_advisor:
        payload["decision_advisor"] = _json_safe(decision_advisor)
    return json.dumps(payload, ensure_ascii=False, indent=2)
