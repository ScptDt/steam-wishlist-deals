from __future__ import annotations

from typing import Any


DECISION_ADVISOR_SCHEMA = "decision_advisor_v0"

DECISIONS = {"comprar_ahora", "revisar", "esperar", "ignorar"}
PURCHASE_TYPES = {"comfort_pick", "stretch_pick", "aspirational_pick", "impulse_risk"}
PRIORITIES = {"alta", "media", "baja"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
ACCESS_STATUSES = {"requires_purchase", "available", "partially_available", "unknown"}

_CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}
_BUYABLE_ACCESS = {"requires_purchase", "unknown"}
_PARTIAL_ACCESS_CODES = {"family", "probable_family_shared"}
_AVAILABLE_ACCESS_CODES = {"owned", "playable_without_buying"}
_WEAK_TASTE_CATEGORIES = {"espera_oferta", "riesgo_abandono", "no_comprar_aun"}


def _records(value: Any) -> list[dict]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _items(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        return _records(payload.get("items"))
    return []


def _appid(record: dict) -> str:
    value = record.get("appid") or record.get("steam_appid") or record.get("wishlist_appid")
    appid = str(value or "").strip()
    return appid if appid.isdigit() else ""


def _name(record: dict) -> str:
    return str(record.get("name") or record.get("title") or "").strip()


def _index_by_appid(records: list[dict]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for record in records:
        appid = _appid(record)
        if appid and appid not in indexed:
            indexed[appid] = record
    return indexed


def _candidate_records(*sources: Any) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    for source in sources:
        for record in _records(source) if not isinstance(source, dict) else _items(source):
            appid = _appid(record)
            if appid and appid not in seen:
                seen.add(appid)
                candidates.append({"appid": appid, "name": _name(record)})
    return candidates


def _safe_number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _confidence(value: Any) -> str:
    level = str(value or "").strip().lower()
    return level if level in CONFIDENCE_LEVELS else "low"


def _diagnostics_confidence(diagnostics: Any) -> str:
    if not isinstance(diagnostics, dict):
        return "low"
    confidence = diagnostics.get("recommendation_confidence")
    if isinstance(confidence, dict):
        return _confidence(confidence.get("level"))
    return "low"


def _recommendation_mode(diagnostics: Any) -> str:
    if not isinstance(diagnostics, dict):
        return "score_fallback"
    mode = str(diagnostics.get("recommendation_mode") or "").strip()
    return mode if mode in {"behavioral", "mixed", "score_fallback"} else "score_fallback"


def _lower_confidence(level: str) -> str:
    if level == "high":
        return "medium"
    if level == "medium":
        return "low"
    return "low"


def _cache_is_partial(cache_coverage: Any) -> bool:
    return isinstance(cache_coverage, dict) and (
        cache_coverage.get("status") == "partial" or bool(cache_coverage.get("is_partial"))
    )


def _access_status(hygiene_item: dict | None) -> tuple[str, list[str]]:
    if not isinstance(hygiene_item, dict):
        return "requires_purchase", []
    access = hygiene_item.get("access_decision")
    code = str(access.get("code") or "").strip() if isinstance(access, dict) else ""
    if code in _AVAILABLE_ACCESS_CODES:
        return "available", ["already_available"]
    if code in _PARTIAL_ACCESS_CODES:
        return "partially_available", ["access_requires_review"]
    return "requires_purchase", []


def _offer_signals(deal: dict | None, top_pick: dict | None) -> tuple[bool, list[str]]:
    record = deal if isinstance(deal, dict) else top_pick if isinstance(top_pick, dict) else {}
    discount = _safe_number(record.get("discount"))
    score = _safe_number(record.get("score"))
    signals: list[str] = []
    if discount >= 70:
        signals.append("strong_discount")
    if score >= 80:
        signals.append("high_score")
    return bool(signals), signals


def _fit_signals(decision_item: dict | None, taste_item: dict | None) -> tuple[str, list[str], list[str]]:
    positives: list[str] = []
    risks: list[str] = []
    decision_label = str((decision_item or {}).get("decision_label") or "").strip()
    taste_category = str((taste_item or {}).get("category") or "").strip()
    if decision_label == "good_fit" or taste_category == "compra_inmediata":
        positives.append("strong_personal_fit")
        return "strong", positives, risks
    if decision_label == "maybe":
        positives.append("partial_personal_fit")
        return "medium", positives, risks
    if decision_label == "weak_fit" or taste_category in _WEAK_TASTE_CATEGORIES:
        risks.append("weak_or_redundant_fit")
        return "weak", positives, risks
    risks.append("personal_fit_unknown")
    return "unknown", positives, risks


def _external_offer_signals(offers: list[dict]) -> tuple[list[str], list[str]]:
    positives: list[str] = []
    risks: list[str] = []
    for offer in offers:
        flags = offer.get("risk_flags") if isinstance(offer.get("risk_flags"), list) else []
        if offer.get("eligible_for_best_external_price") is True and not flags:
            positives.append("safe_external_offer")
        if flags:
            risks.append("external_offer_requires_review")
    return positives[:1], risks[:1]


def _item_confidence(mode: str, diagnostics_level: str, decision_item: dict | None, partial_cache: bool) -> str:
    if mode == "score_fallback":
        return "low"
    level = _confidence((decision_item or {}).get("confidence")) if decision_item else diagnostics_level
    if mode == "mixed" and _CONFIDENCE_RANK[level] > _CONFIDENCE_RANK["medium"]:
        level = "medium"
    return _lower_confidence(level) if partial_cache else level


def _purchase_type(fit_level: str, strong_offer: bool, risks: list[str]) -> str:
    if "weak_or_redundant_fit" in risks or (strong_offer and fit_level in {"weak", "unknown"}):
        return "impulse_risk"
    if fit_level == "strong":
        return "comfort_pick"
    if fit_level == "medium":
        return "stretch_pick"
    return "aspirational_pick"


def _decision(access_status: str, fit_level: str, strong_offer: bool, confidence: str) -> str:
    if access_status == "available":
        return "ignorar"
    if access_status == "partially_available":
        return "revisar"
    if fit_level == "strong" and strong_offer and confidence != "low":
        return "comprar_ahora"
    if fit_level == "strong":
        return "esperar"
    if strong_offer or fit_level == "medium":
        return "revisar"
    if fit_level == "weak":
        return "ignorar"
    return "esperar"


def _priority(decision: str) -> str:
    if decision == "comprar_ahora":
        return "alta"
    if decision in {"revisar", "esperar"}:
        return "media"
    return "baja"


def _advisor_item(
    candidate: dict,
    *,
    deals_by_appid: dict[str, dict],
    top_picks_by_appid: dict[str, dict],
    decision_by_appid: dict[str, dict],
    taste_by_appid: dict[str, dict],
    hygiene_by_appid: dict[str, dict],
    external_by_appid: dict[str, list[dict]],
    recommendation_mode: str,
    diagnostics_confidence: str,
    partial_cache: bool,
) -> dict:
    appid = candidate["appid"]
    strong_offer, positives = _offer_signals(deals_by_appid.get(appid), top_picks_by_appid.get(appid))
    fit_level, fit_positives, fit_risks = _fit_signals(decision_by_appid.get(appid), taste_by_appid.get(appid))
    access_status, access_risks = _access_status(hygiene_by_appid.get(appid))
    ext_positives, ext_risks = _external_offer_signals(external_by_appid.get(appid, []))
    risks = [*fit_risks, *access_risks, *ext_risks]
    if recommendation_mode == "score_fallback":
        risks.append("score_fallback_personalization")
    if partial_cache:
        risks.append("partial_cache_coverage")
    confidence = _item_confidence(recommendation_mode, diagnostics_confidence, decision_by_appid.get(appid), partial_cache)
    decision = _decision(access_status, fit_level, strong_offer, confidence)
    purchase_type = _purchase_type(fit_level, strong_offer, risks)
    positive_signals = [*positives, *fit_positives, *ext_positives]
    reason = positive_signals[0] if positive_signals else risks[0] if risks else "limited_signals"
    return {
        "appid": appid,
        "name": candidate.get("name") or _name(deals_by_appid.get(appid, {})) or _name(top_picks_by_appid.get(appid, {})),
        "decision": decision,
        "priority": _priority(decision),
        "purchase_type": purchase_type,
        "confidence": confidence,
        "access_status": access_status,
        "reason": reason,
        "positive_signals": positive_signals[:6],
        "risks": risks[:6],
        "source_signals": _source_signals(appid, deals_by_appid, top_picks_by_appid, decision_by_appid, taste_by_appid, hygiene_by_appid, external_by_appid),
    }


def _source_signals(appid: str, *indexes: Any) -> list[str]:
    names = ["deals", "top_picks", "decision_support", "taste_priority", "wishlist_hygiene", "external_offers"]
    sources: list[str] = []
    for name, index in zip(names, indexes):
        if isinstance(index, dict) and appid in index:
            sources.append(name)
    return sources


def _external_by_appid(external_offers: Any) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for offer in _items(external_offers):
        appid = _appid(offer)
        if appid:
            grouped.setdefault(appid, []).append(offer)
    return grouped


def _summary(items: list[dict], mode: str, partial_cache: bool) -> dict:
    confidence = max((item["confidence"] for item in items), default="low", key=lambda level: _CONFIDENCE_RANK[level])
    return {
        "items_count": len(items),
        "buy_now_count": sum(1 for item in items if item["decision"] == "comprar_ahora"),
        "review_count": sum(1 for item in items if item["decision"] == "revisar"),
        "wait_count": sum(1 for item in items if item["decision"] == "esperar"),
        "ignore_count": sum(1 for item in items if item["decision"] == "ignorar"),
        "impulse_risk_count": sum(1 for item in items if item["purchase_type"] == "impulse_risk"),
        "confidence": confidence,
        "recommendation_mode": mode,
        "cache_coverage_status": "partial" if partial_cache else "complete_or_not_provided",
        "advisory_only": True,
        "ranking_impact": "none",
    }


def _empty_contract(reason: str) -> dict:
    return {
        "schema": DECISION_ADVISOR_SCHEMA,
        "status": "insufficient_signals",
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": {"items_count": 0, "advisory_only": True, "ranking_impact": "none"},
        "items": [],
        "limitations": [reason, "advisory_only", "ranking_impact_none"],
    }


def build_decision_advisor(
    deals: Any,
    *,
    top_picks: Any = None,
    decision_support: Any = None,
    taste_priority: Any = None,
    wishlist_hygiene: Any = None,
    play_access: Any = None,
    external_offers: Any = None,
    recommendation_diagnostics: Any = None,
    cache_coverage: Any = None,
) -> dict:
    """Build JSON-only advisory purchase decisions from existing report signals."""
    del play_access  # Access is consumed after it feeds wishlist_hygiene.
    candidates = _candidate_records(deals, top_picks, decision_support, taste_priority, wishlist_hygiene)
    if not candidates:
        return _empty_contract("no_decision_candidates")
    mode = _recommendation_mode(recommendation_diagnostics)
    partial_cache = _cache_is_partial(cache_coverage)
    deals_by_appid = _index_by_appid(_records(deals))
    top_picks_by_appid = _index_by_appid(_records(top_picks))
    decision_by_appid = _index_by_appid(_items(decision_support))
    taste_by_appid = _index_by_appid(_items(taste_priority))
    hygiene_by_appid = _index_by_appid(_items(wishlist_hygiene))
    external_by_appid = _external_by_appid(external_offers)
    items = [
        _advisor_item(
            candidate,
            deals_by_appid=deals_by_appid,
            top_picks_by_appid=top_picks_by_appid,
            decision_by_appid=decision_by_appid,
            taste_by_appid=taste_by_appid,
            hygiene_by_appid=hygiene_by_appid,
            external_by_appid=external_by_appid,
            recommendation_mode=mode,
            diagnostics_confidence=_diagnostics_confidence(recommendation_diagnostics),
            partial_cache=partial_cache,
        )
        for candidate in candidates
    ]
    return {
        "schema": DECISION_ADVISOR_SCHEMA,
        "source_schemas": ["deals", "top_picks", "decision_support_v1", "taste_priority", "wishlist_hygiene"],
        "status": "partial" if partial_cache else "available",
        "advisory_only": True,
        "ranking_impact": "none",
        "summary": _summary(items, mode, partial_cache),
        "items": items,
        "limitations": ["advisory_only", "ranking_impact_none"],
    }
