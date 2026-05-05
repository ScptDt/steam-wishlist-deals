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
    degraded_batch_count: int = 0
    individual_fallback_count: int = 0
    individual_fallback_batches: int = 0
    individual_fallback_resolved_count: int = 0
    individual_fallback_failed_count: int = 0
    individual_attempts: int = 0
    individual_no_data: int = 0
    deferred_by_fallback_budget: int = 0
    fallback_budget_reason: str | None = None
    old_cache_used_count: int = 0
    http_400_direct_fallback_count: int = 0
    http_400_direct_fallback_batches: int = 0
    individual_fallback_worker_downgrade_count: int = 0
    individual_fallback_failure_reasons: dict[str, int] = field(default_factory=dict)
    batch_size: int | None = None
    batch_halving_limit: int | None = None
    individual_fallback_workers: int | None = None
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
    ("HTTP 400", "degraded_batch_count", ""),
    ("Fallback total", "individual_fallback_count", ""),
    ("Fallback sin datos", "individual_fallback_failed_count", ""),
    ("Budget diferidos", "deferred_by_fallback_budget", ""),
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


def _format_fallback_cooldown_action(summary: WarmCacheLogSummary) -> str:
    failed = summary.individual_fallback_failed_count
    total = summary.individual_fallback_count
    percent = round(_fallback_failed_ratio(summary) * 100)
    return (
        f"Mucho fallback sin datos: {failed}/{total} (~{percent}%) no resolvió; "
        f"espera al menos {PRICE_FAILURE_RETRY_HOURS}h de cooldown antes de forzar --no-cache."
    )


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
    has_fallback_no_data_cooldown = (
        latest.individual_fallback_count >= HIGH_FALLBACK_THRESHOLD
        and _fallback_failed_ratio(latest) >= HIGH_FAILED_FALLBACK_RATIO
    )

    if has_repeated_http_400:
        recommendations.append(
            WarmCacheRecommendation(
                "repeated-http-400",
                "warn",
                _format_http_400_action(latest, previous),
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
            f"- Batches degradados HTTP 400: {_format_value(summary.degraded_batch_count)}",
            "- Fallback individual: "
            f"{_format_value(summary.individual_fallback_count)} juegos en "
            f"{_format_value(summary.individual_fallback_batches)} tandas "
            f"({_format_value(summary.individual_fallback_resolved_count)} resueltos, "
            f"{_format_value(summary.individual_fallback_failed_count)} sin oferta/datos)",
        ]
    )
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
