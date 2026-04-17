from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from shared.io_utils import load_json_file as _default_load_json_file
from shared.io_utils import write_json_file as _default_write_json_file


def load_previous_deal_appids(output_dir: Path, current_filename: str) -> set[str]:
    """Busca el MD anterior más reciente y extrae los appids de deals."""
    markdown_files = sorted(
        output_dir.glob("Steam Deals*.md"),
        key=lambda file_path: file_path.stat().st_mtime,
        reverse=True,
    )
    for file_path in markdown_files:
        if file_path.name == current_filename:
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError:
            continue
        appids = set(re.findall(r"store\.steampowered\.com/app/(\d+)/", text))
        if appids:
            return appids
    return set()


def _run_entry(
    steam_id: str,
    vanity: str,
    sale_name: str,
    min_discount: int,
    deals: list[dict],
    *,
    now: datetime,
) -> dict:
    return {
        "steam_id": steam_id,
        "vanity": vanity,
        "date": date.today().isoformat(),
        "timestamp": now.isoformat(),
        "sale_name": sale_name,
        "min_discount": min_discount,
        "deals": {
            deal["appid"]: {
                "name": deal["name"],
                "discount": deal["discount"],
                "price_final": deal["price_final"],
                "price_raw": deal.get("price_raw", 0),
            }
            for deal in deals
        },
    }


def _prune_history(history_dir: Path, history_max_files: int) -> None:
    files = sorted(history_dir.glob("run_*.json"))
    excess = len(files) - history_max_files
    if excess <= 0:
        return
    for file_path in files[:excess]:
        file_path.unlink(missing_ok=True)


def save_run_history(
    steam_id: str,
    vanity: str,
    sale_name: str,
    min_discount: int,
    deals: list[dict],
    *,
    history_dir: Path,
    history_max_files: int,
    now: datetime | None = None,
) -> Path:
    """Guarda snapshot del run actual en historial JSON."""
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now or datetime.now()
    filename = f"run_{timestamp.strftime('%Y-%m-%d_%H%M%S')}.json"
    entry = _run_entry(steam_id, vanity, sale_name, min_discount, deals, now=timestamp)
    path = history_dir / filename
    path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
    _prune_history(history_dir, history_max_files)
    return path


def _load_history_file(file_path: Path) -> dict | None:
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_previous_run(steam_id: str, *, history_dir: Path) -> dict | None:
    """Carga el run anterior más reciente del historial."""
    if not history_dir.exists():
        return None
    for file_path in sorted(history_dir.glob("run_*.json"), reverse=True):
        data = _load_history_file(file_path)
        if data and data.get("steam_id") == steam_id:
            return data
    return None


def load_run_history(
    steam_id: str, *, history_dir: Path, max_runs: int = 30
) -> list[dict]:
    """Carga los últimos N runs para deal streak tracking."""
    if not history_dir.exists():
        return []
    runs = []
    for file_path in sorted(history_dir.glob("run_*.json"), reverse=True):
        if len(runs) >= max_runs:
            break
        data = _load_history_file(file_path)
        if data and data.get("steam_id") == steam_id:
            runs.append(data)
    return runs


def _delta_str(delta_raw: int) -> str:
    delta_pesos = abs(delta_raw) / 100
    return f"${delta_pesos:.0f}" if delta_pesos >= 1 else f"${delta_pesos:.2f}"


def compute_deal_comparison(
    current_deals: list[dict],
    previous_run: dict | None,
    run_history: list[dict],
) -> dict:
    """Compara deals actuales con run anterior y historial."""
    result = {
        "price_changes": {},
        "new_deals": set(),
        "disappeared": [],
        "deal_streak": {},
    }
    if not previous_run:
        return result

    previous_deals = previous_run.get("deals", {})
    current_appids = {deal["appid"] for deal in current_deals}
    previous_appids = set(previous_deals.keys())
    result["new_deals"] = current_appids - previous_appids

    for deal in current_deals:
        appid = deal["appid"]
        if appid not in previous_deals:
            continue
        previous = previous_deals[appid]
        current_price_raw = deal.get("price_raw", 0)
        previous_price_raw = previous.get("price_raw", 0)
        if (
            not current_price_raw
            or not previous_price_raw
            or current_price_raw == previous_price_raw
        ):
            continue
        delta = current_price_raw - previous_price_raw
        result["price_changes"][appid] = {
            "delta_raw": delta,
            "delta_str": _delta_str(delta),
            "prev_price": previous.get("price_final", "?"),
            "prev_price_raw": previous_price_raw,
            "change_pct": round((delta / previous_price_raw) * 100, 2),
            "direction": "down" if delta < 0 else "up",
        }

    previous_date = previous_run.get("date", "?")
    for appid in sorted(previous_appids - current_appids):
        info = previous_deals[appid]
        result["disappeared"].append(
            {
                "appid": appid,
                "name": info.get("name", "?"),
                "discount": info.get("discount", 0),
                "price_final": info.get("price_final", "?"),
                "last_seen": previous_date,
            }
        )

    for deal in current_deals:
        appid = deal["appid"]
        streak = 1
        for past_run in run_history:
            if appid in past_run.get("deals", {}):
                streak += 1
            else:
                break
        result["deal_streak"][appid] = streak

    return result


def _fmt_mxn(centavos: int) -> str:
    pesos = centavos / 100
    return f"${int(pesos)}" if pesos == int(pesos) else f"${pesos:.2f}"


def _empty_price_history(steam_id: str) -> dict:
    return {"version": 1, "steam_id": steam_id, "games": {}}


def load_price_history(
    steam_id: str,
    *,
    price_history_file: Path,
    load_json_file=_default_load_json_file,
) -> dict:
    data = load_json_file(price_history_file, None)
    if not isinstance(data, dict):
        return _empty_price_history(steam_id)
    if data.get("steam_id") != steam_id:
        return _empty_price_history(steam_id)
    return data


def save_price_history(
    history: dict,
    *,
    price_history_file: Path,
    write_json_file=_default_write_json_file,
) -> None:
    write_json_file(price_history_file, history, ensure_ascii=False, indent=None)


def log_price_snapshot(
    history: dict, deals: list[dict], *, today_iso: str | None = None
) -> None:
    """Register current run's prices into the history."""
    current_day = today_iso or date.today().isoformat()
    games = history.setdefault("games", {})
    for deal in deals:
        appid = deal["appid"]
        price_raw = deal.get("price_raw", 0)
        if not price_raw:
            continue
        game_entry = games.setdefault(appid, {"name": deal["name"], "snapshots": []})
        game_entry["name"] = deal["name"]
        snapshots = game_entry["snapshots"]
        snapshots[:] = [
            snapshot for snapshot in snapshots if snapshot["date"] != current_day
        ]
        snapshots.append(
            {"date": current_day, "discount": deal["discount"], "price_raw": price_raw}
        )
        if len(snapshots) > 60:
            snapshots[:] = snapshots[-60:]


def analyze_trends(
    history: dict, deals: list[dict], *, today_iso: str | None = None
) -> dict[str, dict]:
    """Analyze price trends for current deals. Returns {appid: trend_info}."""
    games = history.get("games", {})
    result = {}
    current_day = today_iso or date.today().isoformat()

    for deal in deals:
        appid = deal["appid"]
        price_raw = deal.get("price_raw", 0)
        game_entry = games.get(appid)
        if not game_entry or not price_raw:
            result[appid] = {"times_on_sale": 1, "is_first_time": True}
            continue

        previous_snapshots = [
            snapshot
            for snapshot in game_entry.get("snapshots", [])
            if snapshot["date"] != current_day
        ]
        if not previous_snapshots:
            result[appid] = {"times_on_sale": 1, "is_first_time": True}
            continue

        prices = [snapshot["price_raw"] for snapshot in previous_snapshots]
        lowest = min(prices)
        average = round(sum(prices) / len(prices))
        result[appid] = {
            "times_on_sale": len(previous_snapshots) + 1,
            "is_first_time": False,
            "is_best_local": price_raw <= lowest,
            "is_first_at_price": price_raw not in prices,
            "lowest_fmt": _fmt_mxn(lowest),
            "avg_fmt": _fmt_mxn(average),
            "avg_raw": average,
        }
    return result


def format_trend(trend: dict) -> str:
    if trend.get("is_first_time"):
        return "🆕 1ra vez"
    if trend.get("is_best_local") and trend.get("times_on_sale", 0) > 1:
        return "🔥 Mín. local"
    if trend.get("is_first_at_price"):
        return "💰 1ra vez a este precio"
    times = trend.get("times_on_sale", 0)
    average = trend.get("avg_fmt", "?")
    return f"📊 {times}x · prom {average}"
