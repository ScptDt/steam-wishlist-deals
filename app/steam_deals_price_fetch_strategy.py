from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


PLAN_SCHEMA = "proactive_price_fetch_plan_v1"
FETCH_PLAN_BUCKETS = (
    "batch",
    "individual_planificado",
    "usar_stale",
    "defer",
    "cooldown",
    "fallback_reactivo",
)

_DEFAULT_BUCKET = "batch"
_STATE_ALIASES = {
    "batch": "batch",
    "planned_batch": "batch",
    "individual": "individual_planificado",
    "single": "individual_planificado",
    "planned_individual": "individual_planificado",
    "individual_planificado": "individual_planificado",
    "use_stale": "usar_stale",
    "stale_usable": "usar_stale",
    "usar_stale": "usar_stale",
    "defer": "defer",
    "deferred": "defer",
    "time_budget_deferred": "defer",
    "fallback_budget_deferred": "defer",
    "cooldown": "cooldown",
    "failed_cooldown": "cooldown",
    "recent_failure": "cooldown",
    "http_429": "cooldown",
    "reactive_fallback": "fallback_reactivo",
    "fallback_reactivo": "fallback_reactivo",
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _candidate_appid(candidate: Any) -> str:
    if not isinstance(candidate, Mapping):
        return _safe_text(candidate)
    for key in ("appid", "app_id", "id"):
        appid = _safe_text(candidate.get(key))
        if appid:
            return appid
    return ""


def _candidate_state(candidate: Any) -> str:
    if not isinstance(candidate, Mapping):
        return _DEFAULT_BUCKET
    failure_reason = _safe_text(candidate.get("failure_reason")).lower()
    if failure_reason == "http_429":
        return "cooldown"
    if candidate.get("use_stale") is True or candidate.get("has_useful_stale") is True:
        return "usar_stale"
    if candidate.get("deferred") is True:
        return "defer"
    raw_state = _safe_text(
        candidate.get("bucket")
        or candidate.get("strategy")
        or candidate.get("state")
        or _DEFAULT_BUCKET
    ).lower()
    return _STATE_ALIASES.get(raw_state, _DEFAULT_BUCKET)


def _empty_plan() -> dict[str, Any]:
    return {
        "schema": PLAN_SCHEMA,
        **{bucket: [] for bucket in FETCH_PLAN_BUCKETS},
    }


def _summarize_plan(plan: Mapping[str, Any]) -> dict[str, int | str]:
    counts = {f"{bucket}_count": len(plan.get(bucket, [])) for bucket in FETCH_PLAN_BUCKETS}
    return {
        "schema": PLAN_SCHEMA,
        "total_candidates": sum(counts.values()),
        "planned_fetch_count": counts["batch_count"] + counts["individual_planificado_count"],
        "non_fetch_count": counts["usar_stale_count"] + counts["defer_count"] + counts["cooldown_count"],
        **counts,
    }


def build_proactive_price_fetch_plan(candidates: Iterable[Any]) -> dict[str, Any]:
    """Build a pure, non-runtime fetch plan scaffold for price candidates.

    Plain AppID inputs mirror today's behavior by going to ``batch``. Rich candidate
    mappings can opt into future buckets without changing the active fetch path yet.
    """
    plan = _empty_plan()
    for candidate in candidates:
        appid = _candidate_appid(candidate)
        if not appid:
            continue
        bucket = _candidate_state(candidate)
        plan[bucket].append(appid)
    plan["summary"] = _summarize_plan(plan)
    return plan


__all__ = [
    "FETCH_PLAN_BUCKETS",
    "PLAN_SCHEMA",
    "build_proactive_price_fetch_plan",
]
