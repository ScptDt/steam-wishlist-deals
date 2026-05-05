from __future__ import annotations

import json
from pathlib import Path


VALID_STATUS_FILTERS = {"all", "changed", "new", "removed", "same"}
VALID_DELTA_SORTS = {"default", "delta_desc", "delta_asc", "abs_desc"}


def safe_history_filename(raw_name: str) -> str | None:
    name = (raw_name or "").strip()
    if not name:
        return None
    if not name.endswith(".json"):
        return None
    if not name.startswith("run_"):
        return None
    if ".." in name or "/" in name or "\\" in name:
        return None
    return name


def load_history_run(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("deals"), dict):
        return None
    return data


def build_history_run_summary(file_path: Path, run_data: dict) -> dict:
    deals = run_data.get("deals")
    deal_count = len(deals) if isinstance(deals, dict) else 0
    return {
        "id": file_path.name,
        "timestamp": run_data.get("timestamp", ""),
        "date": run_data.get("date", ""),
        "steam_id": run_data.get("steam_id", ""),
        "vanity": run_data.get("vanity", ""),
        "sale_name": run_data.get("sale_name", ""),
        "min_discount": run_data.get("min_discount", 0),
        "deal_count": deal_count,
    }


def list_history_runs(history_dir: Path, *, max_runs: int = 50) -> list[dict]:
    if not history_dir.exists():
        return []
    runs: list[dict] = []
    for file_path in sorted(history_dir.glob("run_*.json"), reverse=True):
        run_data = load_history_run(file_path)
        if run_data is None:
            continue
        runs.append(build_history_run_summary(file_path, run_data))
        if len(runs) >= max_runs:
            break
    return runs


def build_comparison_row(*, appid: str, left: dict | None, right: dict | None) -> dict:
    left_raw = (left or {}).get("price_raw", 0)
    right_raw = (right or {}).get("price_raw", 0)
    left_price = (left or {}).get("price_final", "?")
    right_price = (right or {}).get("price_final", "?")
    if left is None:
        status = "new"
        direction = "down"
        delta_raw = None
    elif right is None:
        status = "removed"
        direction = "up"
        delta_raw = None
    elif left_raw == right_raw:
        status = "same"
        direction = "same"
        delta_raw = 0
    else:
        status = "changed"
        delta_raw = int(right_raw) - int(left_raw)
        direction = "down" if delta_raw < 0 else "up"
    return {
        "appid": appid,
        "name": (right or left or {}).get("name", appid),
        "status": status,
        "direction": direction,
        "left_price": left_price,
        "right_price": right_price,
        "left_price_raw": left_raw,
        "right_price_raw": right_raw,
        "delta_raw": delta_raw,
        "left_discount": (left or {}).get("discount", 0),
        "right_discount": (right or {}).get("discount", 0),
    }


def row_delta_sort_value(row: dict, *, fallback: int) -> int:
    raw_delta = row.get("delta_raw")
    if isinstance(raw_delta, bool):
        return fallback
    if isinstance(raw_delta, (int, float)):
        return int(raw_delta)
    return fallback


def load_history_window(history_dir: Path, *, max_runs: int = 20) -> list[tuple[Path, dict]]:
    runs: list[tuple[Path, dict]] = []
    if not history_dir.exists():
        return runs
    for file_path in sorted(history_dir.glob("run_*.json"), reverse=True):
        run_data = load_history_run(file_path)
        if run_data is None:
            continue
        runs.append((file_path, run_data))
        if len(runs) >= max_runs:
            break
    runs.reverse()
    return runs


def build_game_history(
    appids: set[str], history_runs: list[tuple[Path, dict]]
) -> dict[str, list[dict]]:
    game_history: dict[str, list[dict]] = {appid: [] for appid in appids}
    for file_path, run_data in history_runs:
        deals = run_data.get("deals", {})
        for appid in appids:
            deal = deals.get(appid)
            if not isinstance(deal, dict):
                continue
            game_history[appid].append(
                {
                    "run_id": file_path.name,
                    "timestamp": run_data.get("timestamp", ""),
                    "date": run_data.get("date", ""),
                    "sale_name": run_data.get("sale_name", ""),
                    "price": deal.get("price_final", "?"),
                    "price_raw": deal.get("price_raw", 0),
                    "discount": deal.get("discount", 0),
                }
            )
    return {appid: snapshots for appid, snapshots in game_history.items() if snapshots}


def summarize_history_analytics(
    rows: list[dict], history_runs: list[tuple[Path, dict]]
) -> dict:
    state_counts = {"changed": 0, "new": 0, "removed": 0, "same": 0}
    for row in rows:
        status = row.get("status")
        if status in state_counts:
            state_counts[status] += 1

    changed_rows = [
        row
        for row in rows
        if row.get("status") == "changed" and isinstance(row.get("delta_raw"), (int, float))
    ]
    top_price_drops = sorted(
        [row for row in changed_rows if row.get("direction") == "down"],
        key=lambda row: row.get("delta_raw", 0),
    )[:5]
    top_price_rises = sorted(
        [row for row in changed_rows if row.get("direction") == "up"],
        key=lambda row: row.get("delta_raw", 0),
        reverse=True,
    )[:5]

    return {
        "state_counts": state_counts,
        "history_runs": [
            build_history_run_summary(file_path, run_data)
            for file_path, run_data in history_runs
        ],
        "game_history": build_game_history(
            {str(row.get("appid", "")) for row in rows if row.get("appid")},
            history_runs,
        ),
        "top_price_drops": top_price_drops,
        "top_price_rises": top_price_rises,
    }


def compare_history_runs(
    *,
    history_dir: Path,
    left_run_id: str,
    right_run_id: str,
    include_same: bool = False,
    status_filter: str = "all",
    sort_delta: str = "default",
) -> dict | None:
    left_name = safe_history_filename(left_run_id)
    right_name = safe_history_filename(right_run_id)
    if left_name is None or right_name is None:
        return None

    left_path = history_dir / left_name
    right_path = history_dir / right_name
    left_data = load_history_run(left_path)
    right_data = load_history_run(right_path)
    if left_data is None or right_data is None:
        return None

    left_deals = left_data.get("deals", {})
    right_deals = right_data.get("deals", {})
    left_ids = set(left_deals.keys())
    right_ids = set(right_deals.keys())
    all_ids = sorted(left_ids | right_ids)

    rows: list[dict] = []
    changed_count = 0
    new_count = 0
    removed_count = 0
    for appid in all_ids:
        row = build_comparison_row(
            appid=appid,
            left=left_deals.get(appid),
            right=right_deals.get(appid),
        )
        if row["status"] == "same" and not include_same:
            continue
        if status_filter != "all" and row["status"] != status_filter:
            continue
        if row["status"] == "changed":
            changed_count += 1
        elif row["status"] == "new":
            new_count += 1
        elif row["status"] == "removed":
            removed_count += 1
        rows.append(row)

    if sort_delta == "delta_desc":
        rows.sort(
            key=lambda row: row_delta_sort_value(row, fallback=-(10**12)),
            reverse=True,
        )
    elif sort_delta == "delta_asc":
        rows.sort(key=lambda row: row_delta_sort_value(row, fallback=10**12))
    elif sort_delta == "abs_desc":
        rows.sort(
            key=lambda row: abs(row_delta_sort_value(row, fallback=-1)),
            reverse=True,
        )

    same_count = sum(1 for row in rows if row.get("status") == "same")
    history_runs = load_history_window(history_dir, max_runs=20)

    return {
        "left": build_history_run_summary(left_path, left_data),
        "right": build_history_run_summary(right_path, right_data),
        "summary": {
            "left_total": len(left_ids),
            "right_total": len(right_ids),
            "changed": changed_count,
            "new": new_count,
            "removed": removed_count,
            "same": same_count,
        },
        "rows": rows,
        "analytics": summarize_history_analytics(rows, history_runs),
    }
