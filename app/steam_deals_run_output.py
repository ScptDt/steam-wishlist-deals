from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class OutputArtifactPaths:
    output_md: Path
    output_html: Path
    output_share: Path
    output_json: Path
    output_csv: Path | None = None


@dataclass(frozen=True)
class OutputArtifactPayloads:
    markdown: str
    html: str
    share_html: str
    json_content: str
    csv_content: str | None = None


def _sanitize_sale_name(sale_name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', sale_name).strip()


def build_output_md_path(output_dir: str | Path, sale_name: str, *, today_obj: date | None = None) -> Path:
    today = today_obj or date.today()
    date_str = today.strftime("%Y-%m-%d")
    if sale_name:
        filename = f"Steam Deals {_sanitize_sale_name(sale_name)} {date_str}.md"
    else:
        filename = f"Steam Deals {date_str}.md"
    return Path(output_dir) / filename


def resolve_previous_context(
    output_dir: str | Path,
    current_filename: str,
    steam_id: str,
    *,
    load_previous_run_fn,
    load_run_history_fn,
    load_previous_deal_appids_fn,
) -> dict:
    previous_run = load_previous_run_fn(steam_id)
    run_history = load_run_history_fn(steam_id) if previous_run else []
    previous_appids: set[str] = set()
    if not previous_run:
        previous_appids = load_previous_deal_appids_fn(Path(output_dir), current_filename)
    return {
        "previous_run": previous_run,
        "run_history": run_history,
        "previous_appids": previous_appids,
    }


def build_share_output_path(output_dir: str | Path, *, today_obj: date | None = None) -> Path:
    today = today_obj or date.today()
    return Path(output_dir) / f"Steam Deals Share {today.strftime('%Y-%m-%d')}.html"


def build_output_artifact_paths(
    output_md: Path,
    *,
    today_obj: date | None = None,
    include_csv: bool = False,
) -> OutputArtifactPaths:
    return OutputArtifactPaths(
        output_md=output_md,
        output_html=output_md.with_suffix(".html"),
        output_share=build_share_output_path(output_md.parent, today_obj=today_obj),
        output_json=output_md.with_suffix(".json"),
        output_csv=output_md.with_suffix(".csv") if include_csv else None,
    )


def find_latest_artifact(output_dir: str | Path, pattern: str) -> Path | None:
    try:
        candidates = [path for path in Path(output_dir).glob(pattern) if path.is_file()]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def write_artifact(path: Path, content: str, *, emit_event_fn=None, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)
    if emit_event_fn is not None:
        emit_event_fn("file", path=str(path))
    return path


def write_output_artifacts(
    paths: OutputArtifactPaths,
    payloads: OutputArtifactPayloads,
    *,
    write_artifact_fn,
) -> dict[str, Path]:
    written = {
        "markdown": write_artifact_fn(paths.output_md, payloads.markdown),
        "html": write_artifact_fn(paths.output_html, payloads.html),
        "share_html": write_artifact_fn(paths.output_share, payloads.share_html),
        "json": write_artifact_fn(paths.output_json, payloads.json_content),
    }
    if payloads.csv_content is not None and paths.output_csv is not None:
        written["csv"] = write_artifact_fn(paths.output_csv, payloads.csv_content)
    return written


def build_final_summary(
    elapsed: float,
    deals: list[dict],
    backlog_on_sale: list[dict],
    previous_appids: set[str],
    top_picks: list[dict] | None,
    output_md: Path,
) -> tuple[int, str]:
    new_count = sum(1 for deal in deals if previous_appids and deal["appid"] not in previous_appids) if previous_appids else 0
    summary = f"  {len(deals):,} deals · {len(backlog_on_sale)} backlog"
    if new_count:
        summary += f" · {new_count} nuevos"
    if top_picks:
        summary += f" · Top pick: {top_picks[0]['name']} ({top_picks[0]['score']})"
    summary += f" · {output_md.name}"
    return new_count, summary


def emit_final_closeout(
    elapsed: float,
    deals: list[dict],
    backlog_on_sale: list[dict],
    previous_appids: set[str],
    top_picks: list[dict] | None,
    output_md: Path,
    *,
    build_final_summary_fn,
    emit_fn,
    bold_fn,
    color_green: str,
    color_reset: str,
    divider_width: int = 42,
) -> tuple[int, str]:
    new_count, summary = build_final_summary_fn(
        elapsed,
        deals,
        backlog_on_sale,
        previous_appids,
        top_picks,
        output_md,
    )
    divider = f"{color_green}{'─' * divider_width}{color_reset}"
    emit_fn(f"\n{divider}")
    emit_fn(f"  {bold_fn('Listo')} en {elapsed:.1f}s")
    emit_fn(summary)
    emit_fn(f"{divider}\n")
    return new_count, summary
