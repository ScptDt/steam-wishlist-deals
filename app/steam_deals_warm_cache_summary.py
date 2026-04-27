from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
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
    batch_size: int | None = None
    batch_halving_limit: int | None = None
    deals_count: int | None = None
    min_discount: int | None = None
    wishlist_count: int | None = None
    elapsed_seconds: float | None = None
    cache_path: str | None = None


COMPARISON_COLUMNS = (
    ("Duración", "elapsed_seconds", "s"),
    ("Refresh candidates", "refresh_candidates", ""),
    ("Cooldown", "deferred_failure_count", ""),
    ("HTTP 400", "degraded_batch_count", ""),
    ("Fallback total", "individual_fallback_count", ""),
    ("Fallback sin datos", "individual_fallback_failed_count", ""),
)


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
            r"halving_limit=(?P<halving>\d+)",
            line,
        ):
            values["batch_size"] = _parse_int(match.group("batch"))
            values["batch_halving_limit"] = _parse_int(match.group("halving"))

        if match := re.search(r"Batches degradados por HTTP 400: (?P<count>[\d,]+)", line):
            values["degraded_batch_count"] = _parse_int(match.group("count"))

        if match := re.search(
            r"Fallback individual aplicado a (?P<total>[\d,]+) juegos en "
            r"(?P<batches>[\d,]+) tandas \((?P<resolved>[\d,]+) resueltos, "
            r"(?P<failed>[\d,]+) sin oferta/datos\)",
            line,
        ):
            values["individual_fallback_count"] = _parse_int(match.group("total"))
            values["individual_fallback_batches"] = _parse_int(match.group("batches"))
            values["individual_fallback_resolved_count"] = _parse_int(
                match.group("resolved")
            )
            values["individual_fallback_failed_count"] = _parse_int(match.group("failed"))

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
    if summary.batch_size is not None or summary.batch_halving_limit is not None:
        lines.append(
            f"- Tuning precios: batch_size={_format_value(summary.batch_size)} · "
            f"halving_limit={_format_value(summary.batch_halving_limit)}"
        )
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
    output.write("\n\n".join(sections))
    output.write("\n")
    return 0


__all__ = [
    "WarmCacheLogSummary",
    "build_parser",
    "format_warm_cache_comparison",
    "format_warm_cache_summary",
    "main",
    "parse_warm_cache_log_file",
    "parse_warm_cache_log_text",
]
