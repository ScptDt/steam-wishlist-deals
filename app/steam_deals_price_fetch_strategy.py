from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


PLAN_SCHEMA = "proactive_price_fetch_plan_v1"
COMPARISON_SCHEMA = "proactive_price_fetch_plan_comparison_v1"
DEFAULT_REPEATED_HTTP_400_THRESHOLD = 3
FETCH_PLAN_BUCKETS = (
    "batch",
    "individual_planificado",
    "usar_stale",
    "defer",
    "cooldown",
    "fallback_reactivo",
)
_BUCKET_COPY_LABELS = {
    "batch": "batch",
    "individual_planificado": "individual planificado",
    "usar_stale": "usar stale útil",
    "defer": "diferidos",
    "cooldown": "cooldown",
    "fallback_reactivo": "fallback reactivo",
}

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
_REACTIVE_BASELINE_COUNT_KEYS = (
    "reactive_fallback_count",
    "fallback_reactivo_count",
    "fallback_individual_count",
    "fallback_total",
    "fallback_count",
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


def _bucket_count(plan: Mapping[str, Any], bucket: str) -> int:
    values = plan.get(bucket, [])
    return len(values) if isinstance(values, list) else 0


def _summarize_plan(plan: Mapping[str, Any]) -> dict[str, int | str]:
    counts = {f"{bucket}_count": len(plan.get(bucket, [])) for bucket in FETCH_PLAN_BUCKETS}
    return {
        "schema": PLAN_SCHEMA,
        "total_candidates": sum(counts.values()),
        "batch_fetch_count": counts["batch_count"],
        "planned_individual_count": counts["individual_planificado_count"],
        "reactive_fallback_count": counts["fallback_reactivo_count"],
        "planned_fetch_count": counts["batch_count"] + counts["individual_planificado_count"],
        "non_fetch_count": counts["usar_stale_count"] + counts["defer_count"] + counts["cooldown_count"],
        **counts,
    }


def _format_count_part(count: int, label: str) -> str:
    return f"{count:,} {label}"


def _planner_signal(plan: Mapping[str, Any], signal: str) -> bool:
    signals = plan.get("signals")
    return isinstance(signals, Mapping) and bool(signals.get(signal))


def _baseline_reactive_count(metrics: Mapping[str, Any] | None) -> int | None:
    if not isinstance(metrics, Mapping):
        return None
    for key in _REACTIVE_BASELINE_COUNT_KEYS:
        value = _safe_int(metrics.get(key))
        if value is not None and value >= 0:
            return value
    return None


def _percent_part(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((value / total) * 100, 1)


def format_proactive_price_fetch_plan_summary(plan: Mapping[str, Any]) -> str:
    """Format fixture-only planner metrics without changing runtime behavior."""
    counts = {bucket: _bucket_count(plan, bucket) for bucket in FETCH_PLAN_BUCKETS}
    total = sum(counts.values())
    lines = ["Plan proactivo de precios:"]
    if total <= 0:
        lines.append("- Sin candidatos para planificar.")
    else:
        lines.append(
            "- Fetch planificado: "
            + ", ".join(
                (
                    _format_count_part(counts["batch"], _BUCKET_COPY_LABELS["batch"]),
                    _format_count_part(
                        counts["individual_planificado"],
                        _BUCKET_COPY_LABELS["individual_planificado"],
                    ),
                )
            )
            + "."
        )
        lines.append(
            "- Sin fetch ahora: "
            + ", ".join(
                (
                    _format_count_part(counts["usar_stale"], _BUCKET_COPY_LABELS["usar_stale"]),
                    _format_count_part(counts["defer"], _BUCKET_COPY_LABELS["defer"]),
                    _format_count_part(counts["cooldown"], _BUCKET_COPY_LABELS["cooldown"]),
                )
            )
            + "."
        )

    if _planner_signal(plan, "repeated_http_400") and counts["individual_planificado"]:
        lines.append(
            "- Señal HTTP 400 repetido: se prioriza `individual_planificado` "
            f"para {counts['individual_planificado']:,} candidato(s) antes de llenar logs de splits."
        )

    fallback_count = counts["fallback_reactivo"]
    if fallback_count:
        lines.append(
            "- Fallback reactivo: "
            f"{_format_count_part(fallback_count, _BUCKET_COPY_LABELS['fallback_reactivo'])}; "
            "queda como safety net para fallos no previstos."
        )
    else:
        lines.append("- Fallback reactivo: 0 candidatos; se conserva solo como safety net.")
    lines.append("- Guardrail: no cambia defaults, score, ranking, cache policy ni fetching por sí solo.")
    return "\n".join(lines)


def build_proactive_price_fetch_plan_comparison(
    plan: Mapping[str, Any],
    *,
    reactive_baseline: Mapping[str, Any] | None = None,
) -> dict[str, int | float | str]:
    """Compare fixture-only proactive planning against reactive fallback counts."""
    counts = {bucket: _bucket_count(plan, bucket) for bucket in FETCH_PLAN_BUCKETS}
    planned_individual = counts["individual_planificado"]
    reactive_remaining = counts["fallback_reactivo"]
    internal_baseline = planned_individual + reactive_remaining
    external_baseline = _baseline_reactive_count(reactive_baseline)
    baseline_count = external_baseline if external_baseline is not None else internal_baseline
    baseline_source = "external" if external_baseline is not None else "plan"
    reactive_reduction = max(0, baseline_count - reactive_remaining)
    return {
        "schema": COMPARISON_SCHEMA,
        "baseline_source": baseline_source,
        "baseline_reactive_fallback_count": baseline_count,
        "planned_individual_count": planned_individual,
        "reactive_fallback_count": reactive_remaining,
        "batch_fetch_count": counts["batch"],
        "planned_fetch_count": counts["batch"] + planned_individual,
        "non_fetch_count": counts["usar_stale"] + counts["defer"] + counts["cooldown"],
        "reactive_dependency_reduction_count": reactive_reduction,
        "reactive_remaining_pct": _percent_part(reactive_remaining, baseline_count),
        "planned_individual_pct": _percent_part(planned_individual, baseline_count),
    }


def format_proactive_price_fetch_plan_comparison(
    comparison: Mapping[str, Any],
) -> str:
    baseline = _safe_int(comparison.get("baseline_reactive_fallback_count")) or 0
    planned_individual = _safe_int(comparison.get("planned_individual_count")) or 0
    reactive_remaining = _safe_int(comparison.get("reactive_fallback_count")) or 0
    reduction = _safe_int(comparison.get("reactive_dependency_reduction_count")) or 0
    batch_count = _safe_int(comparison.get("batch_fetch_count")) or 0
    baseline_label = "baseline externo" if comparison.get("baseline_source") == "external" else "baseline del plan"
    lines = ["Comparación offline planificado vs reactivo:"]
    lines.append(f"- Fallback reactivo base ({baseline_label}): {baseline:,} candidato(s).")
    lines.append(
        "- Plan actual: "
        f"{batch_count:,} batch, {planned_individual:,} individual_planificado, "
        f"{reactive_remaining:,} fallback_reactivo como safety net."
    )
    if reduction:
        lines.append(
            f"- Delta offline: {reduction:,} candidato(s) dejan de depender "
            "del fallback reactivo en este fixture."
        )
    else:
        lines.append("- Delta offline: no reduce dependencia del fallback reactivo en este fixture.")
    lines.append(
        "- Guardrail: resumen offline; no cambia runtime, defaults, score, "
        "ranking, cache policy ni fetching."
    )
    return "\n".join(lines)


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
    "COMPARISON_SCHEMA",
    "DEFAULT_REPEATED_HTTP_400_THRESHOLD",
    "PLAN_SCHEMA",
    "build_proactive_price_fetch_plan_comparison",
    "build_proactive_price_fetch_plan",
    "format_proactive_price_fetch_plan_comparison",
    "format_proactive_price_fetch_plan_summary",
]
