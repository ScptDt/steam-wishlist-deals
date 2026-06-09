from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


PLAN_SCHEMA = "proactive_price_fetch_plan_v1"
DEFAULT_REPEATED_HTTP_400_THRESHOLD = 3
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
_REPEATED_HTTP_400_FLAG_KEYS = (
    "repeated_http_400",
    "http_400_repeated",
    "use_planned_individual_after_http_400",
)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = _safe_text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return _safe_text(value).lower() in {"1", "true", "yes", "on"}


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


def _planner_context_value(context: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in context:
            return context.get(key)
    return None


def _has_repeated_http_400_signal(context: Mapping[str, Any] | None) -> bool:
    if not isinstance(context, Mapping):
        return False
    if any(_safe_bool(context.get(key)) for key in _REPEATED_HTTP_400_FLAG_KEYS):
        return True

    direct_fallback_count = _safe_int(context.get("http_400_direct_fallback_count"))
    if direct_fallback_count is not None and direct_fallback_count > 0:
        return True

    streak = _safe_int(
        _planner_context_value(
            context,
            ("http_400_degradation_streak", "degraded_batch_streak"),
        )
    )
    threshold = _safe_int(context.get("http_400_circuit_breaker_threshold"))
    if threshold is None:
        threshold = DEFAULT_REPEATED_HTTP_400_THRESHOLD
    return bool(streak is not None and threshold > 0 and streak >= threshold)


def _planner_signals(context: Mapping[str, Any] | None) -> dict[str, bool]:
    return {
        "repeated_http_400": _has_repeated_http_400_signal(context),
    }


def _planned_bucket(bucket: str, signals: Mapping[str, bool]) -> str:
    if bucket == "batch" and signals.get("repeated_http_400"):
        return "individual_planificado"
    return bucket


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


def build_proactive_price_fetch_plan(
    candidates: Iterable[Any],
    *,
    planner_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a pure, non-runtime fetch plan scaffold for price candidates.

    Plain AppID inputs mirror today's behavior by going to ``batch``. Rich candidate
    mappings can opt into future buckets without changing the active fetch path yet.
    When the provided planner context shows repeated HTTP 400 degradation, default
    batch candidates move to ``individual_planificado`` for fixture-only planning.
    """
    signals = _planner_signals(planner_context)
    plan = _empty_plan()
    for candidate in candidates:
        appid = _candidate_appid(candidate)
        if not appid:
            continue
        bucket = _planned_bucket(_candidate_state(candidate), signals)
        plan[bucket].append(appid)
    plan["signals"] = signals
    plan["summary"] = _summarize_plan(plan)
    return plan


__all__ = [
    "FETCH_PLAN_BUCKETS",
    "DEFAULT_REPEATED_HTTP_400_THRESHOLD",
    "PLAN_SCHEMA",
    "build_proactive_price_fetch_plan",
]
