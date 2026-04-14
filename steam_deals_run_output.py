from __future__ import annotations

import re
from datetime import date
from pathlib import Path


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


def write_artifact(path: Path, content: str, *, emit_event_fn=None, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)
    if emit_event_fn is not None:
        emit_event_fn("file", path=str(path))
    return path


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
