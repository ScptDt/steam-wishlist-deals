from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TextIO


ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


@dataclass(frozen=True)
class WarmCacheLogSummary:
    source_path: str | None = None
    cache_status: str | None = None
    cache_age_hours: float | None = None
    refresh_candidates: int = 0
    missing_count: int = 0
    stale_count: int = 0
    deferred_failure_count: int = 0
    stale_used_count: int = 0
    stale_refresh_deferred_count: int = 0
    ttl_jitter_bucket_counts: dict[str, int] = field(default_factory=dict)
    degraded_batch_count: int = 0
    http_400_batch_size_counts: dict[str, int] = field(default_factory=dict)
    http_400_terminal_skip_count: int = 0
    http_400_batch_samples: list[dict] = field(default_factory=list)
    individual_fallback_count: int = 0
    individual_fallback_batches: int = 0
    individual_fallback_resolved_count: int = 0
    individual_fallback_failed_count: int = 0
    individual_attempts: int = 0
    individual_no_data: int = 0
    deferred_by_fallback_budget: int = 0
    fallback_budget_reason: str | None = None
    old_cache_used_count: int = 0
    processed_count: int = 0
    deferred_by_time_budget: int = 0
    time_budget_exhausted: bool = False
    next_resume_hint: str | None = None
    http_400_direct_fallback_count: int = 0
    http_400_direct_fallback_batches: int = 0
    individual_fallback_worker_downgrade_count: int = 0
    individual_fallback_failure_reasons: dict[str, int] = field(default_factory=dict)
    batch_size: int | None = None
    batch_halving_limit: int | None = None
    individual_fallback_workers: int | None = None
    rate_limit_wait_count: int = 0
    rate_limit_max_wait_seconds: int | None = None
    deals_count: int | None = None
    min_discount: int | None = None
    wishlist_count: int | None = None
    elapsed_seconds: float | None = None
    cache_path: str | None = None


@dataclass(frozen=True)
class WarmCacheRecommendation:
    code: str
    severity: str
    action: str


COMPARISON_COLUMNS = (
    ("Duración", "elapsed_seconds", "s"),
    ("Refresh candidates", "refresh_candidates", ""),
    ("Cooldown", "deferred_failure_count", ""),
    ("Stale diferidos", "stale_refresh_deferred_count", ""),
    ("HTTP 400", "degraded_batch_count", ""),
    ("Fallback total", "individual_fallback_count", ""),
    ("Fallback sin datos", "individual_fallback_failed_count", ""),
    ("Budget diferidos", "deferred_by_fallback_budget", ""),
    ("Refresh diferidos", "deferred_by_time_budget", ""),
)

HIGH_FALLBACK_THRESHOLD = 20
HIGH_FAILED_FALLBACK_RATIO = 0.5
CACHE_EFFECTIVE_DROP_RATIO = 0.25
DEFAULT_PRICE_BATCH_SIZE = 20
MIN_PRICE_BATCH_SIZE = 1
PRICE_FAILURE_RETRY_HOURS = 2


def _parse_int(raw_value: str) -> int:
    return int(raw_value.replace(",", ""))


def _parse_float(raw_value: str) -> float:
    return float(raw_value.replace(",", ""))


def _clean_log_text(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text).replace("\r", "\n")


def _cache_status_from_line(line: str) -> tuple[str | None, float | None]:
    if "--no-cache" in line:
        return "bypass", None
    if "Sin caché" in line:
        return "empty", None
    valid_match = re.search(r"Caché válida \((?P<age>[\d.]+)h\)", line)
    if valid_match:
        return "valid", _parse_float(valid_match.group("age"))
    expired_match = re.search(r"Caché expirada \((?P<age>[\d.]+)h\)", line)
    if expired_match:
        return "expired", _parse_float(expired_match.group("age"))
    return None, None


def _parse_reason_counts(raw_value: str) -> dict[str, int]:
    reasons: dict[str, int] = {}
    for part in raw_value.split(","):
        name, separator, count = part.strip().partition("=")
        if not separator or not name or not count:
            continue
        reasons[name] = _parse_int(count)
    return reasons


def _parse_ttl_jitter_bucket_counts(raw_value: str) -> dict[str, int]:
    buckets: dict[str, int] = {}
    if raw_value.strip() == "none":
        return buckets
    for part in raw_value.split(","):
        bucket, separator, count = part.strip().partition("=")
        if not separator or not bucket or not count:
            continue
        buckets[bucket] = _parse_int(count)
    return buckets


def _increment_count(values: dict, field_name: str, key: str) -> None:
    counts = values.get(field_name)
    if not isinstance(counts, dict):
        counts = {}
    counts[key] = int(counts.get(key, 0) or 0) + 1
    values[field_name] = counts


def _optional_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_http_400_batch_samples(raw_value: str) -> list[dict]:
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    samples: list[dict] = []
    for sample in payload:
        if not isinstance(sample, dict):
            continue
        normalized: dict = {}
        if stage := str(sample.get("stage") or "").strip():
            normalized["stage"] = stage
        for key in ("depth", "size"):
            if (value := _optional_int(sample.get(key))) is not None:
                normalized[key] = value
        appids = sample.get("appids")
        if isinstance(appids, list):
            normalized["appids"] = [str(appid)[:24] for appid in appids[:20]]
        if normalized:
            samples.append(normalized)
    return samples


def parse_warm_cache_log_text(
    text: str, *, source_path: str | None = None
) -> WarmCacheLogSummary:
    values = asdict(WarmCacheLogSummary(source_path=source_path))
    for line in _clean_log_text(text).splitlines():
        status, cache_age_hours = _cache_status_from_line(line)
        if status:
            values["cache_status"] = status
            values["cache_age_hours"] = cache_age_hours

        if match := re.search(
            r"Refresh candidates: (?P<total>[\d,]+) "
            r"\((?P<missing>[\d,]+) nuevos, (?P<stale>[\d,]+) stale\)",
            line,
        ):
            values["refresh_candidates"] = _parse_int(match.group("total"))
            values["missing_count"] = _parse_int(match.group("missing"))
            values["stale_count"] = _parse_int(match.group("stale"))

        if match := re.search(r"(?P<count>[\d,]+) fallos recientes en cooldown", line):
            values["deferred_failure_count"] = _parse_int(match.group("count"))

        if match := re.search(
            r"Stale-while-revalidate: stale_used=(?P<used>[\d,]+) · "
            r"stale_deferred=(?P<deferred>[\d,]+) · "
            r"ttl_jitter_buckets=(?P<buckets>.+)$",
            line,
        ):
            values["stale_used_count"] = _parse_int(match.group("used"))
            values["stale_refresh_deferred_count"] = _parse_int(
                match.group("deferred")
            )
            values["ttl_jitter_bucket_counts"] = _parse_ttl_jitter_bucket_counts(
                match.group("buckets")
            )

        if match := re.search(
            r"Tuning precios activo: batch_size=(?P<batch>\d+) · "
            r"halving_limit=(?P<halving>\d+)"
            r"(?: · fallback_workers=(?P<workers>\d+))?",
            line,
        ):
            values["batch_size"] = _parse_int(match.group("batch"))
            values["batch_halving_limit"] = _parse_int(match.group("halving"))
            if match.group("workers") is not None:
                values["individual_fallback_workers"] = _parse_int(match.group("workers"))

        if match := re.search(r"Batches degradados por HTTP 400: (?P<count>[\d,]+)", line):
            values["degraded_batch_count"] = _parse_int(match.group("count"))

        if match := re.search(
            r"HTTP 400 en batch de (?P<size>[\d,]+) juegos; reduciendo lote",
            line,
        ):
            _increment_count(
                values,
                "http_400_batch_size_counts",
                str(_parse_int(match.group("size"))),
            )

        if re.search(r"HTTP 400 en batch, saltando", line):
            values["http_400_terminal_skip_count"] += 1

        if match := re.search(r"HTTP 400 diagnostic samples: (?P<samples>\[.*\])", line):
            values["http_400_batch_samples"] = _parse_http_400_batch_samples(
                match.group("samples")
            )

        if match := re.search(
            r"Fallback individual aplicado a (?P<total>[\d,]+) juegos en "
            r"(?P<batches>[\d,]+) tandas \((?P<resolved>[\d,]+) resueltos, "
            r"(?P<failed>[\d,]+) sin oferta/datos\)",
            line,
        ):
            values["individual_fallback_count"] = _parse_int(match.group("total"))
            values["individual_attempts"] = values["individual_fallback_count"]
            values["individual_fallback_batches"] = _parse_int(match.group("batches"))
            values["individual_fallback_resolved_count"] = _parse_int(
                match.group("resolved")
            )
            values["individual_fallback_failed_count"] = _parse_int(match.group("failed"))

        if match := re.search(
            r"Fallback individual directo por HTTP 400 repetido: "
            r"(?P<total>[\d,]+) juegos en (?P<batches>[\d,]+) tandas",
            line,
        ):
            values["http_400_direct_fallback_count"] = _parse_int(match.group("total"))
            values["http_400_direct_fallback_batches"] = _parse_int(match.group("batches"))

        if match := re.search(
            r"Fallback individual adaptativo: (?P<count>[\d,]+) bajadas de workers",
            line,
        ):
            values["individual_fallback_worker_downgrade_count"] = _parse_int(
                match.group("count")
            )

        if match := re.search(
            r"Fallback individual fallos por razón: (?P<reasons>.+)$",
            line,
        ):
            values["individual_fallback_failure_reasons"] = _parse_reason_counts(
                match.group("reasons")
            )
            values["individual_no_data"] = values[
                "individual_fallback_failure_reasons"
            ].get("no_price_data", 0)

        if match := re.search(r"Rate limit.*esperando (?P<seconds>[\d,]+)s", line):
            wait_seconds = _parse_int(match.group("seconds"))
            values["rate_limit_wait_count"] += 1
            current_max = values["rate_limit_max_wait_seconds"] or 0
            values["rate_limit_max_wait_seconds"] = max(current_max, wait_seconds)

        if match := re.search(
            r"Fallback budget adaptativo: attempts=(?P<attempts>[\d,]+) · "
            r"no_data=(?P<no_data>[\d,]+) · deferred=(?P<deferred>[\d,]+) · "
            r"old_cache_used=(?P<old_cache>[\d,]+) · reason=(?P<reason>\S+)",
            line,
        ):
            values["individual_attempts"] = _parse_int(match.group("attempts"))
            values["individual_no_data"] = _parse_int(match.group("no_data"))
            values["deferred_by_fallback_budget"] = _parse_int(
                match.group("deferred")
            )
            values["old_cache_used_count"] = _parse_int(match.group("old_cache"))
            reason = match.group("reason")
            values["fallback_budget_reason"] = None if reason == "none" else reason

        if match := re.search(
            r"Refresh budget resumible: processed=(?P<processed>[\d,]+) · "
            r"deferred=(?P<deferred>[\d,]+) · "
            r"exhausted=(?P<exhausted>true|false) · "
            r"next_resume_hint=(?P<hint>\S+)",
            line,
        ):
            values["processed_count"] = _parse_int(match.group("processed"))
            values["deferred_by_time_budget"] = _parse_int(match.group("deferred"))
            values["time_budget_exhausted"] = match.group("exhausted") == "true"
            hint = match.group("hint")
            values["next_resume_hint"] = None if hint == "none" else hint

        if match := re.search(r"(?P<deals>[\d,]+) deals \(≥(?P<discount>\d+)%\)", line):
            values["deals_count"] = _parse_int(match.group("deals"))
            values["min_discount"] = _parse_int(match.group("discount"))

        if match := re.search(
            r"Warm cache listo en (?P<elapsed>[\d.]+)s", line
        ):
            values["elapsed_seconds"] = _parse_float(match.group("elapsed"))

        if match := re.search(
            r"Wishlist: (?P<wishlist>[\d,]+) juegos · Deals actuales: (?P<deals>[\d,]+)",
            line,
        ):
            values["wishlist_count"] = _parse_int(match.group("wishlist"))
            values["deals_count"] = _parse_int(match.group("deals"))

        if match := re.search(r"Caché objetivo: (?P<path>.+)$", line):
            values["cache_path"] = match.group("path").strip()

    return WarmCacheLogSummary(**values)


def parse_warm_cache_log_file(path: str | Path) -> WarmCacheLogSummary:
    log_path = Path(path)
    text = log_path.read_text(encoding="utf-8")
    return parse_warm_cache_log_text(text, source_path=str(log_path))


def _format_value(value, suffix: str = "") -> str:
    if value is None:
        return "n/d"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    if isinstance(value, int):
        return f"{value:,}{suffix}"
    return str(value)


def _format_delta(value, previous_value, suffix: str = "") -> str:
    if value is None or previous_value is None:
        return ""
    delta = value - previous_value
    if delta == 0:
        return " (sin cambio)"
    if isinstance(value, float) or isinstance(previous_value, float):
        return f" ({delta:+.1f}{suffix})"
    return f" ({delta:+,}{suffix})"


def _summary_label(summary: WarmCacheLogSummary, index: int) -> str:
    if not summary.source_path:
        return f"Log {index + 1}"
    return Path(summary.source_path).name


def _fallback_failed_ratio(summary: WarmCacheLogSummary) -> float:
    if summary.individual_fallback_count <= 0:
        return 0.0
    return summary.individual_fallback_failed_count / summary.individual_fallback_count


def _known_batch_size(
    latest: WarmCacheLogSummary, previous: WarmCacheLogSummary | None
) -> int:
    for summary in (latest, previous):
        value = getattr(summary, "batch_size", None) if summary else None
        if isinstance(value, int) and value > 0:
            return value
    return DEFAULT_PRICE_BATCH_SIZE


def _suggest_lower_batch_size(
    latest: WarmCacheLogSummary, previous: WarmCacheLogSummary | None
) -> int:
    current_batch_size = _known_batch_size(latest, previous)
    if current_batch_size <= MIN_PRICE_BATCH_SIZE:
        return MIN_PRICE_BATCH_SIZE
    return max(MIN_PRICE_BATCH_SIZE, current_batch_size // 2)


def _format_http_400_action(
    latest: WarmCacheLogSummary, previous: WarmCacheLogSummary | None
) -> str:
    current_batch_size = _known_batch_size(latest, previous)
    suggested_batch_size = _suggest_lower_batch_size(latest, previous)
    if suggested_batch_size >= current_batch_size:
        return (
            "HTTP 400 repetido: ya estás en batch_size=1; captura otro log antes "
            "de cambiar cache por promos."
        )
    return (
        "HTTP 400 repetido: prueba "
        f"STEAM_DEALS_PRICE_BATCH_SIZE={suggested_batch_size} "
        f"(actual/base {current_batch_size}) antes de otra wishlist grande."
    )


def _is_lower_batch_experiment_negative(
    latest: WarmCacheLogSummary, previous: WarmCacheLogSummary | None
) -> bool:
    if previous is None:
        return False
    if not latest.batch_size:
        return False
    baseline_batch_size = previous.batch_size or DEFAULT_PRICE_BATCH_SIZE
    return (
        latest.batch_size < baseline_batch_size
        and previous.degraded_batch_count > 0
        and latest.degraded_batch_count > previous.degraded_batch_count
    )


def _format_negative_batch_experiment_action(
    latest: WarmCacheLogSummary, previous: WarmCacheLogSummary
) -> str:
    baseline_batch_size = previous.batch_size or DEFAULT_PRICE_BATCH_SIZE
    return (
        "Batch menor no ayudó: "
        f"batch_size={latest.batch_size} generó {latest.degraded_batch_count:,} "
        f"HTTP 400 vs {previous.degraded_batch_count:,} con "
        f"batch_size={baseline_batch_size}; no bajes el default global, "
        "analiza offline appids/batches tóxicos o fallback directo antes de otro benchmark."
    )


def _format_rate_limit_action(summary: WarmCacheLogSummary) -> str:
    return (
        "Rate-limit observado: "
        f"{summary.rate_limit_wait_count:,} esperas"
        f" (máx {summary.rate_limit_max_wait_seconds}s); "
        "no repitas benchmarks ni bajes batch global sin aislar primero batches/appids problemáticos."
    )


def _format_http_400_diagnostic_action(summary: WarmCacheLogSummary) -> str:
    terminal = summary.http_400_terminal_skip_count
    terminal_hint = f"; {terminal:,} saltos terminales a fallback" if terminal else ""
    return (
        "Diagnóstico offline HTTP 400: faltan appids de muestra"
        f"{terminal_hint}; en el próximo benchmark aprobado usa "
        "STEAM_DEALS_HTTP_400_DIAGNOSTIC_SAMPLE_LIMIT=5 y compara logs "
        "antes de cambiar defaults."
    )


def _http_400_sample_appid_counts(summary: WarmCacheLogSummary) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in summary.http_400_batch_samples:
        appids = sample.get("appids")
        if not isinstance(appids, list):
            continue
        seen_in_sample: set[str] = set()
        for appid in appids:
            appid_text = str(appid).strip()
            if not appid_text or appid_text in seen_in_sample:
                continue
            seen_in_sample.add(appid_text)
            counts[appid_text] = counts.get(appid_text, 0) + 1
    return counts


def _format_http_400_sample_fixture_action(summary: WarmCacheLogSummary) -> str:
    sample_count = len(summary.http_400_batch_samples)
    fallback_count = sum(
        1
        for sample in summary.http_400_batch_samples
        if str(sample.get("stage") or "").strip() == "fallback"
    )
    fallback_label = ""
    if fallback_count == 1:
        fallback_label = "; 1 muestra terminal a fallback"
    elif fallback_count > 1:
        fallback_label = f"; {fallback_count:,} muestras terminales a fallback"

    repeated_appids = sorted(
        (
            (appid, count)
            for appid, count in _http_400_sample_appid_counts(summary).items()
            if count > 1
        ),
        key=lambda item: (-item[1], item[0]),
    )
    repeated_label = "; sin appids repetidos en la muestra acotada"
    if repeated_appids:
        repeated_text = ", ".join(
            f"{appid}×{count}" for appid, count in repeated_appids[:3]
        )
        if len(repeated_appids) > 3:
            repeated_text += f", +{len(repeated_appids) - 3} más"
        repeated_label = f"; appids repetidos en muestras: {repeated_text}"

    return (
        "Muestras HTTP 400 disponibles: "
        f"{sample_count:,} muestras{fallback_label}{repeated_label}; "
        "conviértelas en fixture offline para probar circuit breaker/fallback "
        "directo antes de otro benchmark; no cambies defaults ni captures "
        "más appids sin aprobación."
    )


def _format_fallback_cooldown_action(summary: WarmCacheLogSummary) -> str:
    failed = summary.individual_fallback_failed_count
    total = summary.individual_fallback_count
    percent = round(_fallback_failed_ratio(summary) * 100)
    return (
        f"Mucho fallback sin datos: {failed}/{total} (~{percent}%) no resolvió; "
        f"espera al menos {PRICE_FAILURE_RETRY_HOURS}h de cooldown antes de forzar --no-cache."
    )


def _refresh_budget_candidate_total(summary: WarmCacheLogSummary) -> int | None:
    if summary.refresh_candidates > 0:
        return summary.refresh_candidates
    total = summary.processed_count + summary.deferred_by_time_budget
    return total or None


def _format_coverage_state_legend(summary: WarmCacheLogSummary) -> str | None:
    has_coverage_state = any(
        (
            summary.processed_count,
            summary.deferred_by_time_budget,
            summary.stale_used_count,
            summary.stale_refresh_deferred_count,
            summary.deferred_failure_count,
        )
    )
    if not has_coverage_state:
        return None
    return (
        "- Estados de cobertura: processed=revalidado en esta corrida · "
        "deferred=pendiente/no revalidado · fresh cache=dato válido por TTL "
        "o fin de oferta · stale cache=dato viejo usado o pendiente · "
        "failed/cooldown=no confirmado por error/rate-limit"
    )


def _format_http_400_breakdown(summary: WarmCacheLogSummary) -> str | None:
    parts = [
        f"batch_size={size}: {_format_value(count)}"
        for size, count in sorted(
            summary.http_400_batch_size_counts.items(),
            key=lambda item: int(item[0]),
        )
    ]
    if summary.http_400_terminal_skip_count:
        parts.append(
            f"saltos a fallback={_format_value(summary.http_400_terminal_skip_count)}"
        )
    if not parts:
        return None
    return "- Desglose HTTP 400: " + " · ".join(parts)


def _format_http_400_sample(sample: dict) -> str:
    stage = sample.get("stage") or "unknown"
    details = [str(stage)]
    if "depth" in sample:
        details.append(f"depth={sample['depth']}")
    if "size" in sample:
        details.append(f"size={sample['size']}")
    appids = sample.get("appids")
    if isinstance(appids, list) and appids:
        appid_text = ",".join(str(appid) for appid in appids[:4])
        if len(appids) > 4:
            appid_text += ",…"
        details.append(f"appids={appid_text}")
    return " ".join(details)


def _format_http_400_samples(samples: list[dict]) -> str | None:
    if not samples:
        return None
    formatted = [_format_http_400_sample(sample) for sample in samples[:3]]
    if len(samples) > 3:
        formatted.append(f"+{len(samples) - 3} más")
    return "- HTTP 400 diagnostic samples: " + " | ".join(formatted)


def _format_refresh_budget_coverage_lines(
    summary: WarmCacheLogSummary,
) -> list[str]:
    has_refresh_budget = any(
        (
            summary.processed_count,
            summary.deferred_by_time_budget,
            summary.time_budget_exhausted,
        )
    )
    if not has_refresh_budget:
        return []

    total = _refresh_budget_candidate_total(summary)
    if total:
        coverage = f"{_format_value(summary.processed_count)}/{_format_value(total)}"
    else:
        coverage = _format_value(summary.processed_count)

    if summary.deferred_by_time_budget <= 0:
        return [
            "- Cobertura refresh: "
            f"{coverage} candidatos revalidados; sin pendientes por presupuesto."
        ]

    deferred = _format_value(summary.deferred_by_time_budget)
    lines = [
        "- Cobertura parcial: "
        f"se revalidaron {coverage} candidatos; quedan {deferred} "
        "pendientes/no revalidados en esta corrida."
    ]
    if summary.deals_count is not None:
        lines.append(
            "- Deals encontrados: "
            f"{_format_value(summary.deals_count)} con la cobertura disponible "
            "(cobertura parcial)."
        )
    lines.append(
        f"- Pendientes: no se sabe aún si los {deferred} pendientes tienen oferta."
    )
    if summary.next_resume_hint:
        lines.append(
            "- Continuación sugerida: conserva el mismo cache dir y repite una "
            "corrida normal con `--warm-cache` para seguir desde el candidato "
            f"{summary.next_resume_hint}; no uses `--no-cache` salvo benchmark aprobado."
        )
    if summary.time_budget_exhausted:
        lines.append(
            "- Completitud: se detuvo a propósito por presupuesto para evitar "
            "una corrida larga o más rate-limit; mejora velocidad, no garantiza "
            "cobertura total."
        )
    return lines


def analyze_warm_cache_recommendations(
    summaries: list[WarmCacheLogSummary],
) -> list[WarmCacheRecommendation]:
    if not summaries:
        return []

    latest = summaries[-1]
    previous = summaries[-2] if len(summaries) > 1 else None
    recommendations: list[WarmCacheRecommendation] = []

    has_repeated_http_400 = bool(
        previous and previous.degraded_batch_count > 0 and latest.degraded_batch_count > 0
    )
    has_negative_lower_batch = _is_lower_batch_experiment_negative(latest, previous)
    has_fallback_no_data_cooldown = (
        latest.individual_fallback_count >= HIGH_FALLBACK_THRESHOLD
        and _fallback_failed_ratio(latest) >= HIGH_FAILED_FALLBACK_RATIO
    )

    if has_negative_lower_batch and previous is not None:
        recommendations.append(
            WarmCacheRecommendation(
                "lower-batch-negative",
                "warn",
                _format_negative_batch_experiment_action(latest, previous),
            )
        )
    elif has_repeated_http_400:
        recommendations.append(
            WarmCacheRecommendation(
                "repeated-http-400",
                "warn",
                _format_http_400_action(latest, previous),
            )
        )

    if latest.rate_limit_wait_count > 0:
        recommendations.append(
            WarmCacheRecommendation(
                "rate-limit-waits",
                "warn",
                _format_rate_limit_action(latest),
            )
        )

    if latest.degraded_batch_count > 0 and latest.http_400_batch_samples:
        recommendations.append(
            WarmCacheRecommendation(
                "http-400-samples-fixture",
                "info",
                _format_http_400_sample_fixture_action(latest),
            )
        )
    elif latest.degraded_batch_count > 0:
        recommendations.append(
            WarmCacheRecommendation(
                "http-400-diagnostic-samples",
                "info",
                _format_http_400_diagnostic_action(latest),
            )
        )

    if has_fallback_no_data_cooldown:
        recommendations.append(
            WarmCacheRecommendation(
                "fallback-no-data-cooldown",
                "warn",
                _format_fallback_cooldown_action(latest),
            )
        )

    if previous and previous.refresh_candidates > 0:
        effective_limit = previous.refresh_candidates * CACHE_EFFECTIVE_DROP_RATIO
        if latest.refresh_candidates <= effective_limit:
            recommendations.append(
                WarmCacheRecommendation(
                    "cache-effective",
                    "info",
                    "Cache efectivo: los refresh candidates bajaron fuerte; conserva cache caliente antes de tocar promos.",
                )
            )

    if (
        previous
        and latest.individual_fallback_count >= HIGH_FALLBACK_THRESHOLD
        and latest.refresh_candidates <= previous.refresh_candidates
        and not has_repeated_http_400
        and not has_fallback_no_data_cooldown
    ):
        recommendations.append(
            WarmCacheRecommendation(
                "fallback-still-high",
                "warn",
                "Fallback sigue alto con cache caliente: prioriza batching/fallback antes de invalidar cache por promos.",
            )
        )

    if not recommendations:
        recommendations.append(
            WarmCacheRecommendation(
                "no-action",
                "info",
                "Sin acción automática: métricas warm-cache estables; captura otra corrida si cambia la promo o la wishlist.",
            )
        )

    return recommendations


def format_warm_cache_summary(summary: WarmCacheLogSummary) -> str:
    lines = ["## Warm-cache summary"]
    if summary.source_path:
        lines.append(f"- Log: `{summary.source_path}`")
    lines.extend(
        [
            f"- Duración: {_format_value(summary.elapsed_seconds, 's')}",
            f"- Wishlist/deals: {_format_value(summary.wishlist_count)} / {_format_value(summary.deals_count)}",
            f"- Cache: {summary.cache_status or 'n/d'} ({_format_value(summary.cache_age_hours, 'h')})",
            "- Refresh candidates: "
            f"{_format_value(summary.refresh_candidates)} "
            f"({_format_value(summary.missing_count)} nuevos, "
            f"{_format_value(summary.stale_count)} stale, "
            f"{_format_value(summary.deferred_failure_count)} cooldown)",
            "- Stale-while-revalidate: "
            f"{_format_value(summary.stale_used_count)} usados, "
            f"{_format_value(summary.stale_refresh_deferred_count)} diferidos",
            f"- Batches degradados HTTP 400: {_format_value(summary.degraded_batch_count)}",
            "- Fallback individual: "
            f"{_format_value(summary.individual_fallback_count)} juegos en "
            f"{_format_value(summary.individual_fallback_batches)} tandas "
            f"({_format_value(summary.individual_fallback_resolved_count)} resueltos, "
            f"{_format_value(summary.individual_fallback_failed_count)} sin oferta/datos)",
        ]
    )
    if http_400_breakdown := _format_http_400_breakdown(summary):
        lines.append(http_400_breakdown)
    if http_400_samples := _format_http_400_samples(summary.http_400_batch_samples):
        lines.append(http_400_samples)
    if summary.http_400_direct_fallback_count:
        lines.append(
            "- Fallback directo HTTP 400: "
            f"{_format_value(summary.http_400_direct_fallback_count)} juegos en "
            f"{_format_value(summary.http_400_direct_fallback_batches)} tandas"
        )
    if summary.individual_fallback_worker_downgrade_count:
        lines.append(
            "- Fallback adaptativo: "
            f"{_format_value(summary.individual_fallback_worker_downgrade_count)} bajadas de workers"
        )
    if summary.individual_fallback_failure_reasons:
        reason_parts = [
            f"{reason}={_format_value(count)}"
            for reason, count in sorted(
                summary.individual_fallback_failure_reasons.items()
            )
        ]
        lines.append("- Fallback razones: " + ", ".join(reason_parts))
    if summary.rate_limit_wait_count:
        lines.append(
            "- Rate-limit waits: "
            f"{_format_value(summary.rate_limit_wait_count)} esperas"
            f" (máx {_format_value(summary.rate_limit_max_wait_seconds, 's')})"
        )
    if (
        summary.individual_attempts
        or summary.deferred_by_fallback_budget
        or summary.old_cache_used_count
    ):
        reason = summary.fallback_budget_reason or "none"
        lines.append(
            "- Fallback budget: "
            f"attempts={_format_value(summary.individual_attempts)} · "
            f"no_data={_format_value(summary.individual_no_data)} · "
            f"deferred={_format_value(summary.deferred_by_fallback_budget)} · "
            f"old_cache_used={_format_value(summary.old_cache_used_count)} · "
            f"reason={reason}"
        )
    if (
        summary.processed_count
        or summary.deferred_by_time_budget
        or summary.time_budget_exhausted
    ):
        hint = summary.next_resume_hint or "none"
        exhausted = str(bool(summary.time_budget_exhausted)).lower()
        lines.append(
            "- Refresh budget: "
            f"processed={_format_value(summary.processed_count)} · "
            f"deferred={_format_value(summary.deferred_by_time_budget)} · "
            f"exhausted={exhausted} · "
            f"next_resume_hint={hint}"
        )
        lines.extend(_format_refresh_budget_coverage_lines(summary))
    if state_legend := _format_coverage_state_legend(summary):
        lines.append(state_legend)
    if summary.ttl_jitter_bucket_counts:
        bucket_parts = [
            f"{bucket}={_format_value(count)}"
            for bucket, count in sorted(summary.ttl_jitter_bucket_counts.items())
        ]
        lines.append("- TTL jitter buckets: " + ", ".join(bucket_parts))
    if (
        summary.batch_size is not None
        or summary.batch_halving_limit is not None
        or summary.individual_fallback_workers is not None
    ):
        tuning_parts = [
            f"batch_size={_format_value(summary.batch_size)}",
            f"halving_limit={_format_value(summary.batch_halving_limit)}",
        ]
        if summary.individual_fallback_workers is not None:
            tuning_parts.append(
                f"fallback_workers={_format_value(summary.individual_fallback_workers)}"
            )
        lines.append("- Tuning precios: " + " · ".join(tuning_parts))
    if summary.min_discount is not None:
        lines.append(f"- Descuento mínimo: {_format_value(summary.min_discount, '%')}")
    if summary.cache_path:
        lines.append(f"- Caché objetivo: `{summary.cache_path}`")
    return "\n".join(lines)


def format_warm_cache_comparison(summaries: list[WarmCacheLogSummary]) -> str:
    if len(summaries) < 2:
        return ""

    headers = ["Log", *(label for label, _field, _suffix in COMPARISON_COLUMNS)]
    lines = [
        "## Warm-cache comparison",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---", *("---:" for _ in COMPARISON_COLUMNS)]) + " |",
    ]
    previous: WarmCacheLogSummary | None = None
    for index, summary in enumerate(summaries):
        row = [_summary_label(summary, index)]
        for _label, field, suffix in COMPARISON_COLUMNS:
            value = getattr(summary, field)
            previous_value = getattr(previous, field) if previous else None
            row.append(_format_value(value, suffix) + _format_delta(value, previous_value, suffix))
        lines.append("| " + " | ".join(row) + " |")
        previous = summary
    return "\n".join(lines)


def format_warm_cache_recommendations(summaries: list[WarmCacheLogSummary]) -> str:
    if len(summaries) < 2:
        return ""

    lines = ["## Warm-cache next actions"]
    for recommendation in analyze_warm_cache_recommendations(summaries):
        lines.append(
            f"- [{recommendation.severity}] {recommendation.action}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resume logs offline de steam_deals_generator.py --warm-cache."
    )
    parser.add_argument("logs", nargs="+", help="Ruta(s) a warm-cache-*.log")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime el resumen como JSON en lugar de Markdown.",
    )
    return parser


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    summaries = [parse_warm_cache_log_file(path) for path in args.logs]
    if args.json:
        payload = [asdict(summary) for summary in summaries]
        if len(payload) == 1:
            payload = payload[0]
        output.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0
    sections = [format_warm_cache_summary(summary) for summary in summaries]
    comparison = format_warm_cache_comparison(summaries)
    if comparison:
        sections.append(comparison)
    recommendations = format_warm_cache_recommendations(summaries)
    if recommendations:
        sections.append(recommendations)
    output.write("\n\n".join(sections))
    output.write("\n")
    return 0


__all__ = [
    "WarmCacheLogSummary",
    "WarmCacheRecommendation",
    "analyze_warm_cache_recommendations",
    "build_parser",
    "format_warm_cache_comparison",
    "format_warm_cache_recommendations",
    "format_warm_cache_summary",
    "main",
    "parse_warm_cache_log_file",
    "parse_warm_cache_log_text",
]
