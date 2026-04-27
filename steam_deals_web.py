#!/usr/bin/env python3
"""
Steam Deals Web UI — Interfaz web para steam_deals_generator.py
Ejecuta: python3 steam_deals_web.py
Abre: http://127.0.0.1:8080
"""

import html
import json
import os
import re
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from steam_deals_runtime_reporting import EVENT_PREFIX
except Exception:
    EVENT_PREFIX = "__STEAM_EVENT__"
from steam_deals_watchlist import (
    add_watchlist_item,
    load_watchlist,
    remove_watchlist_item,
    save_watchlist,
)
from steam_deals_run_output import find_latest_artifact
from steam_deals_paths import resolve_cache_dir, resolve_logs_dir
from desktop_doctor import apply_desktop_doctor_fixes, build_desktop_doctor_report

from shared_web_infra import (
    CSS_CONTENT_TYPE,
    JS_CONTENT_TYPE,
    load_html_with_fallback,
    ProcessStreamUnavailable,
    read_json_body,
    send_html,
    send_json,
    send_sse_event,
    serve_text_asset,
    start_text_subprocess,
    stop_process,
    stream_process_as_sse,
)

SCRIPT_PATH = Path(__file__).resolve().parent / "steam_deals_generator.py"
PD2_SCRIPT_PATH = Path(__file__).resolve().parent / "payday2_dlc_tracker.py"
PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = Path.home() / ".config" / "steam_deals.json"
DEFAULT_PORT = 8080
WEB_DIR = PROJECT_DIR / "web" / "steam_deals"
STEAM_DEALS_HTML_FILE = WEB_DIR / "index.html"
STEAM_DEALS_CSS_FILE = WEB_DIR / "app.css"
STEAM_DEALS_JS_FILE = WEB_DIR / "app.js"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output"

_running_proc = None
_proc_lock = threading.Lock()


def _build_stop_response(status: str, message: str) -> dict[str, str]:
    return {"status": status, "message": message}

LOCAL_CACHE_DIR = resolve_cache_dir(
    PROJECT_DIR,
    frozen=getattr(sys, "frozen", False),
)
LOCAL_LOGS_DIR = resolve_logs_dir(
    PROJECT_DIR,
    frozen=getattr(sys, "frozen", False),
)
HISTORY_DIR = LOCAL_CACHE_DIR / "history"

GENERATED_FILE_CONTENT_TYPES = {
    ".html": "text/html",
    ".md": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
}


def _safe_content_disposition_filename(name: str) -> str:
    return re.sub(r'[\r\n"]+', "_", name)


def generated_file_content_disposition(name: str, suffix: str) -> str:
    disposition = "inline" if suffix.lower() == ".html" else "attachment"
    safe_name = _safe_content_disposition_filename(name)
    encoded_name = urllib.parse.quote(name)
    return f"{disposition}; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}"


def generated_file_content_type(suffix: str) -> str:
    return GENERATED_FILE_CONTENT_TYPES.get(suffix.lower(), "application/octet-stream")


def resolve_output_dir(value: str | None) -> Path:
    raw = str(value or "").strip()
    path = Path(raw).expanduser() if raw else DEFAULT_OUTPUT_DIR
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path


def output_folder_display_name(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_DIR)) or path.name
    except ValueError:
        return str(path)


def open_output_folder(
    output_dir: Path,
    *,
    platform: str | None = None,
    startfile_fn=None,
    popen_fn=None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    platform_name = platform or sys.platform
    if platform_name.startswith("win"):
        opener = startfile_fn or os.startfile  # type: ignore[attr-defined]
        opener(str(output_dir))
        return output_dir

    command = (
        ["open", str(output_dir)]
        if platform_name == "darwin"
        else ["xdg-open", str(output_dir)]
    )
    launcher = popen_fn or subprocess.Popen
    launcher(command)
    return output_dir


def is_safe_generated_file_name(name: str) -> bool:
    return bool(name) and ".." not in name and "/" not in name and "\\" not in name


def generated_file_error_page(status_code: int, title: str, message: str) -> str:
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{status_code} — {safe_title}</title>
  <style>
    :root {{ --bg:#1b2838; --card:#16202d; --border:#2a475e; --text:#c7d5e0; --muted:#8f98a0; --accent:#66c0f4; --warn:#f0b232; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:1.5rem; font-family:system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); }}
    main {{ width:min(680px,100%); background:var(--card); border:1px solid var(--border); border-radius:12px; padding:1.5rem; box-shadow:0 16px 40px rgba(0,0,0,.24); }}
    .code {{ color:var(--warn); font-weight:700; font-size:.85rem; margin-bottom:.35rem; }}
    h1 {{ margin:.1rem 0 .7rem; font-size:1.35rem; }}
    p {{ color:var(--muted); line-height:1.55; margin:.4rem 0 1rem; }}
    a {{ display:inline-block; color:#000; background:var(--accent); border-radius:8px; padding:.55rem .85rem; text-decoration:none; font-weight:700; }}
  </style>
</head>
<body>
  <main>
    <div class="code">Error {status_code}</div>
    <h1>{safe_title}</h1>
    <p>{safe_message}</p>
    <a href="/">Volver a Steam Tools</a>
  </main>
</body>
</html>"""


def send_generated_file_error(handler, status_code: int, title: str, message: str) -> None:
    data = generated_file_error_page(status_code, title, message).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)

# ─── Config I/O ──────────────────────────────────


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def has_local_cache() -> bool:
    try:
        return LOCAL_CACHE_DIR.exists() and any(LOCAL_CACHE_DIR.iterdir())
    except OSError:
        return False


def build_execution_log_filename(*, now_fn=datetime.now) -> str:
    return f"steam-deals-log-{now_fn().strftime('%Y-%m-%d_%H-%M-%S')}.txt"


def save_execution_log_text(
    text: str,
    *,
    filename: str | None = None,
    logs_dir: Path = LOCAL_LOGS_DIR,
    now_fn=datetime.now,
) -> Path:
    raw_name = (filename or build_execution_log_filename(now_fn=now_fn)).strip()
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "-", Path(raw_name).name) or build_execution_log_filename(now_fn=now_fn)
    if not safe_name.endswith(".txt"):
        safe_name += ".txt"

    normalized_text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    output_text = normalized_text.rstrip("\n") + "\n"

    logs_dir.mkdir(parents=True, exist_ok=True)
    output_path = logs_dir / safe_name
    output_path.write_text(output_text, encoding="utf-8")
    return output_path


def _safe_history_filename(raw_name: str) -> str | None:
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


def _load_history_run(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    deals = data.get("deals")
    if not isinstance(deals, dict):
        return None
    return data


def _build_history_run_summary(file_path: Path, run_data: dict) -> dict:
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
        run_data = _load_history_run(file_path)
        if run_data is None:
            continue
        runs.append(_build_history_run_summary(file_path, run_data))
        if len(runs) >= max_runs:
            break
    return runs


def _build_comparison_row(
    *,
    appid: str,
    left: dict | None,
    right: dict | None,
) -> dict:
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


def _row_delta_sort_value(row: dict, *, fallback: int) -> int:
    raw_delta = row.get("delta_raw")
    if isinstance(raw_delta, bool):
        return fallback
    if isinstance(raw_delta, (int, float)):
        return int(raw_delta)
    return fallback


def _load_history_window(history_dir: Path, *, max_runs: int = 20) -> list[tuple[Path, dict]]:
    runs: list[tuple[Path, dict]] = []
    if not history_dir.exists():
        return runs
    for file_path in sorted(history_dir.glob("run_*.json"), reverse=True):
        run_data = _load_history_run(file_path)
        if run_data is None:
            continue
        runs.append((file_path, run_data))
        if len(runs) >= max_runs:
            break
    runs.reverse()
    return runs


def _build_game_history(appids: set[str], history_runs: list[tuple[Path, dict]]) -> dict[str, list[dict]]:
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


def _summarize_history_analytics(rows: list[dict], history_runs: list[tuple[Path, dict]]) -> dict:
    state_counts = {"changed": 0, "new": 0, "removed": 0, "same": 0}
    for row in rows:
        status = row.get("status")
        if status in state_counts:
            state_counts[status] += 1

    changed_rows = [
        row for row in rows if row.get("status") == "changed" and isinstance(row.get("delta_raw"), (int, float))
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
            _build_history_run_summary(file_path, run_data)
            for file_path, run_data in history_runs
        ],
        "game_history": _build_game_history(
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
    left_name = _safe_history_filename(left_run_id)
    right_name = _safe_history_filename(right_run_id)
    if left_name is None or right_name is None:
        return None

    left_path = history_dir / left_name
    right_path = history_dir / right_name
    left_data = _load_history_run(left_path)
    right_data = _load_history_run(right_path)
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
        row = _build_comparison_row(
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
            key=lambda row: _row_delta_sort_value(row, fallback=-(10**12)),
            reverse=True,
        )
    elif sort_delta == "delta_asc":
        rows.sort(key=lambda row: _row_delta_sort_value(row, fallback=10**12))
    elif sort_delta == "abs_desc":
        rows.sort(
            key=lambda row: abs(_row_delta_sort_value(row, fallback=-1)),
            reverse=True,
        )

    same_count = sum(1 for row in rows if row.get("status") == "same")
    history_runs = _load_history_window(history_dir, max_runs=20)

    return {
        "left": _build_history_run_summary(left_path, left_data),
        "right": _build_history_run_summary(right_path, right_data),
        "summary": {
            "left_total": len(left_ids),
            "right_total": len(right_ids),
            "changed": changed_count,
            "new": new_count,
            "removed": removed_count,
            "same": same_count,
        },
        "rows": rows,
        "analytics": _summarize_history_analytics(rows, history_runs),
    }


# ─── ANSI helpers ────────────────────────────────

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
_STEP_RE = re.compile(r"\[(\d+)/(\d+)\]\s*(.*)")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def classify_line(raw: str) -> tuple[str, str]:
    """Return (cleaned_text, css_class)."""
    text = strip_ansi(raw).rstrip()
    lower = text.lower()
    if not text:
        return text, "dim"
    if "✓" in raw or "✓" in text or lower.startswith("ok ") or lower.startswith("ok\t"):
        return text, "ok"
    if (
        "⚠" in raw
        or "⚠" in text
        or lower.startswith("warn:")
        or lower.startswith("warning")
    ):
        return text, "warn"
    if "✗" in raw or "✗" in text or lower.startswith("error") or "traceback" in lower:
        return text, "err"
    if "\033[36m" in raw:  # cyan = step header
        return text, "step"
    if _STEP_RE.search(text):
        return text, "step"
    if "\033[2m" in raw:  # dim
        return text, "dim"
    if "───" in text or "===" in text:
        return text, "bold"
    return text, "normal"


def extract_progress(text: str) -> tuple[int, int, str] | None:
    m = _STEP_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2)), m.group(3).strip()
    return None


def detect_file_path(text: str) -> str | None:
    """Detect generated file paths from ✓ output lines."""
    stripped = text.strip()
    m = re.search(
        r"(?:✓|OK)\s+(.+\.(?:md|html|csv|json))$", stripped, flags=re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    if re.search(r"\.(?:md|html|csv|json)$", stripped, flags=re.IGNORECASE) and (
        "\\" in stripped or "/" in stripped
    ):
        return stripped
    return None


def load_steam_deals_html() -> str:
    return load_html_with_fallback(
        STEAM_DEALS_HTML_FILE,
        [STEAM_DEALS_CSS_FILE, STEAM_DEALS_JS_FILE],
        PAGE_HTML,
    )


def normalize_steam_profile_value(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.isdigit() and len(value) >= 16:
        return f"https://steamcommunity.com/profiles/{value}/"
    if value.startswith("id/"):
        value = value[3:]
    if value.startswith("profiles/"):
        value = value[9:]
        if value.isdigit():
            return f"https://steamcommunity.com/profiles/{value}/"
    return f"https://steamcommunity.com/id/{value}/"


# ─── Build CLI command ───────────────────────────


def build_command(config: dict, filters: dict) -> list[str]:
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--run-script", "steam_deals_generator.py", "--web-run"]
    else:
        cmd = [sys.executable, str(SCRIPT_PATH), "--web-run"]

    vanity = normalize_steam_profile_value(config.get("vanity"))
    if vanity:
        cmd += ["--vanity", vanity]
    if config.get("key"):
        cmd += ["--key", config["key"]]
    if config.get("hltb"):
        cmd += ["--hltb", config["hltb"]]
    cmd += ["--output", str(resolve_output_dir(config.get("output")))]
    if config.get("discount") is not None:
        cmd += ["--discount", str(config["discount"])]
    if config.get("genres"):
        genres = config["genres"]
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(",") if g.strip()]
        if genres:
            cmd += ["--genre"] + genres
    if config.get("family_json"):
        cmd += ["--family-json", config["family_json"]]
    if config.get("itad_key"):
        cmd += ["--itad-key", config["itad_key"]]
    if filters.get("no_cache"):
        cmd.append("--no-cache")
    if filters.get("max_price"):
        cmd += ["--max-price", str(filters["max_price"])]
    if filters.get("deck_only"):
        cmd.append("--deck-only")
    if filters.get("deck_verified"):
        cmd.append("--deck-verified")
    if filters.get("min_reviews"):
        cmd += ["--min-reviews", str(filters["min_reviews"])]
    if filters.get("min_review_count"):
        cmd += ["--min-review-count", str(filters["min_review_count"])]
    if filters.get("max_hours"):
        cmd += ["--max-hours", str(filters["max_hours"])]
    if filters.get("top"):
        cmd += ["--top", str(filters["top"])]
    if filters.get("sort") and filters["sort"] != "discount":
        cmd += ["--sort", filters["sort"]]
    if filters.get("new_only"):
        cmd.append("--new-only")
    if filters.get("csv"):
        cmd.append("--csv")
    if filters.get("budget"):
        cmd += ["--budget", str(filters["budget"])]
    if config.get("compare"):
        cmd += ["--compare", config["compare"]]
    if config.get("telegram_token"):
        cmd += ["--telegram-token", config["telegram_token"]]
    if config.get("telegram_chat"):
        cmd += ["--telegram-chat", config["telegram_chat"]]
    if config.get("discord_webhook"):
        cmd += ["--discord-webhook", config["discord_webhook"]]
    return cmd


def build_pd2_command(config: dict, filters: dict) -> list[str]:
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--run-script", "payday2_dlc_tracker.py"]
    else:
        cmd = [sys.executable, str(PD2_SCRIPT_PATH)]

    vanity = normalize_steam_profile_value(config.get("vanity"))
    if vanity:
        cmd += ["--vanity", vanity]
    if config.get("key"):
        cmd += ["--key", config["key"]]
    if config.get("itad_key"):
        cmd += ["--itad-key", config["itad_key"]]
    cmd += ["--output", str(resolve_output_dir(config.get("output")))]
    if filters.get("no_cache"):
        cmd.append("--no-cache")
    if filters.get("budget"):
        cmd += ["--budget", str(filters["budget"])]
    if filters.get("alert_price"):
        cmd += ["--alert-price", str(filters["alert_price"])]
    if filters.get("csv"):
        cmd.append("--csv")
    if filters.get("min_deal"):
        cmd += ["--min-deal", str(filters["min_deal"])]
    return cmd


# ─── HTML page ───────────────────────────────────

PAGE_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Steam Tools</title>
<style>
:root {
  --bg: #1b2838; --bg2: #2a475e; --card: #16202d; --card-border: #2a475e;
  --accent: #66c0f4; --accent-hover: #4db8e8; --text: #c7d5e0; --text2: #8f98a0;
  --green: #6cc644; --yellow: #f0b232; --red: #c7322e; --console-bg: #0e1a26;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Header */
.header {
  background: linear-gradient(135deg, #171a21, #1b2838);
  border-bottom: 1px solid var(--card-border);
  padding: 1.2rem 0; text-align: center;
}
.header h1 { font-size: 1.5rem; font-weight: 600; letter-spacing: 0.02em; }
.header h1 span { color: var(--accent); }

/* Container */
.container { max-width: 720px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }

/* Cards */
.card {
  background: var(--card); border: 1px solid var(--card-border);
  border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem;
}
.card h2 { font-size: 1rem; color: var(--accent); margin-bottom: 1rem; font-weight: 600; }

/* Form fields */
.field { margin-bottom: 1rem; }
.field label {
  display: block; font-size: 0.85rem; color: var(--text2);
  margin-bottom: 0.3rem; font-weight: 500;
}
.field .hint { font-size: 0.75rem; color: var(--text2); margin-top: 0.25rem; opacity: 0.7; }
.optional { color: var(--text2); font-weight: 400; font-size: 0.75rem; }
input[type="text"], input[type="number"], input[type="password"], select {
  width: 100%; padding: 0.55rem 0.75rem; font-size: 0.9rem;
  background: var(--bg); border: 1px solid var(--card-border); border-radius: 6px;
  color: var(--text); outline: none; transition: border-color 0.2s;
}
input:focus, select:focus { border-color: var(--accent); }
input::placeholder { color: var(--text2); opacity: 0.5; }

/* Password toggle */
.pw-wrap { position: relative; }
.pw-wrap input { padding-right: 2.5rem; }
.pw-toggle {
  position: absolute; right: 0.5rem; top: 50%; transform: translateY(-50%);
  background: none; border: none; color: var(--text2); cursor: pointer;
  font-size: 1.1rem; padding: 0.25rem;
}
.pw-toggle:hover { color: var(--text); }

/* Row (multi-column) */
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 500px) { .row { grid-template-columns: 1fr; } }

/* Range slider */
.range-wrap { display: flex; align-items: center; gap: 0.75rem; }
.range-wrap input[type="range"] {
  flex: 1; -webkit-appearance: none; height: 6px; background: var(--bg2);
  border-radius: 3px; outline: none;
}
.range-wrap input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none; width: 18px; height: 18px; border-radius: 50%;
  background: var(--accent); cursor: pointer; border: 2px solid var(--card);
}
.range-wrap .range-val {
  min-width: 3rem; text-align: center; font-weight: 600;
  font-size: 0.95rem; color: var(--accent);
}

/* Details / collapsible */
details { margin-bottom: 1rem; }
details summary {
  cursor: pointer; font-size: 0.9rem; color: var(--text2); padding: 0.4rem 0;
  font-weight: 500; user-select: none; list-style: none;
}
details summary::before { content: '▸ '; transition: transform 0.2s; }
details[open] summary::before { content: '▾ '; }
details summary:hover { color: var(--text); }
details .details-body { padding-top: 0.75rem; }

/* Checkboxes */
.checks {
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem 1rem;
}
@media (max-width: 500px) { .checks { grid-template-columns: 1fr; } }
.checks label {
  display: flex; align-items: center; gap: 0.5rem;
  font-size: 0.85rem; color: var(--text2); cursor: pointer;
}
.checks input[type="checkbox"] {
  accent-color: var(--accent); width: 16px; height: 16px;
}

/* Genres autocomplete */
.genre-autocomplete { position: relative; }
.genre-suggestions {
  position: absolute; top: calc(100% + 6px); left: 0; right: 0;
  background: var(--card); border: 1px solid var(--card-border); border-radius: 8px;
  box-shadow: 0 10px 24px rgba(0,0,0,.35); z-index: 60; max-height: 220px; overflow-y: auto;
}
.genre-suggestion {
  display: block; width: 100%; text-align: left; padding: .55rem .75rem;
  background: transparent; border: 0; color: var(--text); font-size: .86rem; cursor: pointer;
}
.genre-suggestion + .genre-suggestion { border-top: 1px solid rgba(255,255,255,.04); }
.genre-suggestion:hover, .genre-suggestion.active { background: var(--bg2); color: var(--accent); }

/* Mode banner + presets */
.mode-banner {
  margin-bottom: .9rem; padding: .65rem .8rem; border-radius: 8px;
  border: 1px solid var(--card-border); background: var(--card);
  display: flex; align-items: center; justify-content: space-between; gap: .8rem;
}
.mode-banner strong { color: var(--accent); font-size: .9rem; }
.mode-banner .hint-inline { color: var(--text2); font-size: .82rem; }
.preset-row {
  display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .55rem;
}
.preset-btn {
  border: 1px solid var(--card-border); background: var(--bg2); color: var(--text);
  padding: .35rem .65rem; border-radius: 999px; font-size: .78rem; font-weight: 600; cursor: pointer;
}
.preset-btn:hover { border-color: var(--accent); color: var(--accent); }
.preset-btn.active { border-color: var(--accent); background: rgba(102,192,244,.12); color: var(--accent); }

/* Buttons */
.actions { display: flex; gap: 0.75rem; margin-top: 0.5rem; }
.btn {
  padding: 0.7rem 1.5rem; border: none; border-radius: 6px;
  font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent), #4b9cd3);
  color: #fff; flex: 1;
}
.btn-primary:hover:not(:disabled) { background: linear-gradient(135deg, var(--accent-hover), #3d8bc2); }
.btn-danger {
  background: var(--bg2); color: var(--red); border: 1px solid var(--red);
}
.btn-danger:hover:not(:disabled) { background: var(--red); color: #fff; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Progress bar */
.progress-container {
  background: var(--bg); border-radius: 4px; height: 28px; position: relative;
  overflow: hidden; margin-bottom: 0.75rem;
}
.progress-bar {
  height: 100%; background: linear-gradient(90deg, var(--accent), #4b9cd3);
  border-radius: 4px; transition: width 0.4s ease; width: 0%;
}
.progress-text {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.8rem; font-weight: 600; color: var(--text);
  text-shadow: 0 1px 2px rgba(0,0,0,0.5);
}

/* Console */
.console {
  background: var(--console-bg); border: 1px solid var(--card-border);
  border-radius: 6px; padding: 0.75rem; font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.8rem; line-height: 1.5; max-height: 55vh; overflow-y: auto;
  min-height: 120px;
}
.console:empty::before {
  content: 'Listo para ejecutar...'; color: var(--text2); opacity: 0.5;
}
.console .line { white-space: pre-wrap; word-break: break-all; }
.console .line-ok { color: var(--green); }
.console .line-warn { color: var(--yellow); }
.console .line-err { color: var(--red); }
.console .line-step { color: var(--accent); font-weight: 600; }
.console .line-dim { color: var(--text2); opacity: 0.7; }
.console .line-bold { color: var(--text); font-weight: 700; }

/* File links */
.file-links {
  display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem;
}
.file-link {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.5rem 1rem; background: var(--bg2); border: 1px solid var(--card-border);
  border-radius: 6px; color: var(--accent); font-size: 0.85rem;
  font-weight: 500; transition: all 0.2s;
}
.file-link:hover { background: var(--accent); color: #fff; text-decoration: none; border-color: var(--accent); }
.latest-report-empty-state {
  margin-top: 0.75rem; padding: 0.85rem 1rem; border-radius: 8px;
  border: 1px dashed var(--card-border); background: var(--bg2);
  color: var(--text2); font-size: 0.85rem; display: flex; flex-direction: column; gap: 0.25rem;
}
.latest-report-empty-state strong { color: var(--text); font-size: 0.9rem; }
.latest-report-card {
  margin-top: 0.75rem; padding: 1rem; border-radius: 10px;
  border: 1px solid var(--card-border); background: linear-gradient(180deg, var(--bg2), var(--card));
}
.latest-report-head { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: flex-start; justify-content: space-between; margin-bottom: 0.85rem; }
.latest-report-title { font-size: 1rem; font-weight: 700; color: var(--text); }
.latest-report-subtitle { margin-top: 0.2rem; color: var(--text2); font-size: 0.82rem; }
.latest-report-badge {
  display: inline-flex; align-items: center; padding: 0.28rem 0.6rem; border-radius: 999px;
  background: rgba(255,255,255,0.05); border: 1px solid var(--card-border); color: var(--accent);
  font-size: 0.75rem; font-weight: 600;
}
.latest-report-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.6rem; }
.latest-report-stat {
  padding: 0.75rem 0.8rem; border-radius: 8px; background: var(--bg);
  border: 1px solid var(--card-border); min-height: 72px;
}
.latest-report-stat-label { color: var(--text2); font-size: 0.78rem; margin-bottom: 0.25rem; }
.latest-report-stat-value { color: var(--text); font-size: 1.1rem; font-weight: 700; }
.hidden { display: none !important; }

/* Wizard */
.wizard-overlay { display: none; position: fixed; inset: 0; background: var(--bg); z-index: 1000; overflow-y: auto; }
.wizard { max-width: 560px; margin: 0 auto; padding: 2rem 1rem 3rem; }
.wizard h1 { font-size: 1.6rem; text-align: center; margin-bottom: 0.3rem; }
.wizard .subtitle { text-align: center; color: var(--text2); font-size: 0.9rem; margin-bottom: 2rem; }
.wizard .step { display: none; }
.wizard .step.active { display: block; }
.wizard .step-card { background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1rem; }
.wizard .step-num { display: inline-block; background: var(--accent); color: #000; font-weight: 700; font-size: 0.8rem; padding: 0.15rem 0.6rem; border-radius: 10px; margin-bottom: 0.6rem; }
.wizard .step-card h2 { font-size: 1.1rem; margin-bottom: 0.6rem; }
.wizard .step-card p { font-size: 0.88rem; color: var(--text2); line-height: 1.6; margin-bottom: 0.8rem; }
.wizard .step-card .example { background: var(--bg); border: 1px solid var(--card-border); border-radius: 6px; padding: 0.6rem 0.8rem; font-family: monospace; font-size: 0.85rem; color: var(--accent); margin: 0.5rem 0; word-break: break-all; }
.wizard .step-card .tip { background: #1a2a1a; border: 1px solid #2a4a2a; border-radius: 6px; padding: 0.5rem 0.8rem; font-size: 0.82rem; color: var(--green); margin-top: 0.5rem; }
.wizard .step-card .optional-tag { display: inline-block; background: var(--bg2); color: var(--text2); font-size: 0.7rem; padding: 0.1rem 0.4rem; border-radius: 4px; margin-left: 0.3rem; font-weight: 400; }
.wizard .nav { display: flex; gap: 0.75rem; margin-top: 1rem; }
.wizard .nav .btn { flex: 1; }
.wizard .btn-secondary { background: var(--bg2); color: var(--text); border: 1px solid var(--card-border); }
.wizard .btn-secondary:hover { border-color: var(--accent); }
.wizard .dots { display: flex; justify-content: center; gap: 0.5rem; margin-bottom: 1.5rem; }
.wizard .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--bg2); border: 1px solid var(--card-border); transition: all 0.3s; }
.wizard .dot.active { background: var(--accent); border-color: var(--accent); }
.wizard .dot.done { background: var(--green); border-color: var(--green); }

/* Share Modal */
.share-modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center; }
.share-modal.active { display: flex; }
.share-modal-content { background: var(--card); border: 1px solid var(--card-border); border-radius: 12px; padding: 1.5rem; max-width: 420px; width: 90%; }
.share-modal h3 { color: var(--accent); margin-bottom: 1rem; font-size: 1.1rem; }
.share-game-info { background: var(--bg); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
.share-game-name { font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem; }
.share-game-price { color: var(--green); font-size: 1.2rem; font-weight: 700; }
.share-game-price span { text-decoration: line-through; color: var(--text2); font-weight: 400; font-size: 0.9rem; }
.share-game-minhist { font-size: 0.8rem; color: var(--text2); margin-top: 0.3rem; }
.share-game-minhist span { color: var(--yellow); }
.share-actions { display: flex; flex-direction: column; gap: 0.6rem; }
.share-btn { padding: 0.6rem 1rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer; text-align: center; }
.share-btn-copy-app { background: var(--accent); color: #fff; border: none; }
.share-btn-copy-app:hover { background: var(--accent-hover); }
.share-btn-copy-steam { background: var(--bg2); color: var(--text); border: 1px solid var(--card-border); }
.share-btn-copy-steam:hover { border-color: var(--accent); }
.share-btn-open { background: var(--bg); color: var(--text2); border: 1px solid var(--card-border); }
.share-close { margin-top: 0.8rem; text-align: center; color: var(--text2); font-size: 0.85rem; cursor: pointer; }
.share-close:hover { color: var(--text); }
</style>
</head>
<body>

<!-- ══ Share Modal ══ -->
<div class="share-modal" id="share-modal">
  <div class="share-modal-content">
    <h3>Compartir oferta</h3>
    <div class="share-game-info">
      <div class="share-game-name" id="share-name"></div>
      <div class="share-game-price" id="share-price"></div>
      <div class="share-game-minhist" id="share-minhist"></div>
    </div>
    <div class="share-actions">
      <button class="share-btn share-btn-copy-app" id="btn-copy-app" onclick="copyShareLink()">Copiar link steamtools://</button>
      <button class="share-btn share-btn-copy-steam" onclick="copySteamLink()">Copiar link de Steam</button>
      <button class="share-btn share-btn-open" onclick="openInSteam()">Abrir en Steam</button>
    </div>
    <div class="share-close" onclick="closeShareModal()">Cerrar</div>
  </div>
</div>

<!-- ══ Setup Wizard ══ -->
<div class="wizard-overlay" id="wizard-overlay">
<div class="wizard">
  <h1>&#127918; Steam Deals Generator</h1>
  <p class="subtitle">Configura tu perfil en unos pasos</p>
  <div class="dots">
    <div class="dot active" id="dot-0"></div>
    <div class="dot" id="dot-1"></div>
    <div class="dot" id="dot-2"></div>
    <div class="dot" id="dot-3"></div>
  </div>

  <!-- Step 0: Vanity URL -->
  <div class="step active" id="wiz-step-0">
    <div class="step-card">
      <span class="step-num">Paso 1 de 4</span>
      <h2>&#128100; Tu perfil de Steam</h2>
      <p>Necesitamos tu <strong>Vanity URL</strong> o <strong>Steam ID</strong> para encontrar tu wishlist.</p>
      <p>Lo encuentras en tu perfil de Steam &rarr; la parte final de la URL:</p>
      <div class="example">https://steamcommunity.com/id/<strong>TU_VANITY_URL</strong>/</div>
      <p>Tambien puede ser tu Steam ID (17 digitos):</p>
      <div class="example">https://steamcommunity.com/profiles/<strong>76561198012345678</strong>/</div>
      <div class="field" style="margin-top:1rem">
        <label>Tu perfil de Steam</label>
        <input type="text" id="wiz-vanity" placeholder="tu_vanity_url, Steam ID, o URL completa">
      </div>
      <div class="tip">&#128161; Si pegas la URL completa del perfil, se extrae automaticamente.</div>
    </div>
    <div class="nav">
      <button class="btn btn-primary" onclick="wizNext()">Siguiente &#8594;</button>
    </div>
  </div>

  <!-- Step 1: Steam API Key -->
  <div class="step" id="wiz-step-1">
    <div class="step-card">
      <span class="step-num">Paso 2 de 4</span>
      <h2>&#128273; Steam API Key <span class="optional-tag">opcional</span></h2>
      <p>Con una API Key obtienes datos extra:</p>
      <ul style="font-size:.88rem;color:var(--text2);margin:0.3rem 0 0.8rem 1.2rem;line-height:1.8">
        <li>Ver juegos que ya tienes (para limpiar la wishlist)</li>
        <li>Mejor deteccion de biblioteca familiar</li>
        <li>Nota: la API de Steam no detecta DLCs poseidos, solo juegos</li>
      </ul>
      <p><strong>Sin key tambien funciona</strong> para wishlist &mdash; solo necesitas que sea publica.</p>
      <p>Para obtenerla:</p>
      <ol style="font-size:.85rem;color:var(--text2);margin:0.3rem 0 0.8rem 1.2rem;line-height:1.8">
        <li>Ve a <a href="https://steamcommunity.com/dev/apikey" target="_blank">steamcommunity.com/dev/apikey</a></li>
        <li>Pon cualquier nombre de dominio (ej: <code>localhost</code>)</li>
        <li>Copia la key que te da</li>
      </ol>
      <div class="field">
        <label>Steam API Key</label>
        <div class="pw-wrap">
          <input type="password" id="wiz-key" placeholder="Dejalo vacio si no tienes">
          <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
        </div>
      </div>
    </div>
    <div class="nav">
      <button class="btn btn-secondary" onclick="wizPrev()">&#8592; Atras</button>
      <button class="btn btn-primary" onclick="wizNext()">Siguiente &#8594;</button>
    </div>
  </div>

  <!-- Step 2: ITAD Key -->
  <div class="step" id="wiz-step-2">
    <div class="step-card">
      <span class="step-num">Paso 3 de 4</span>
      <h2>&#128176; IsThereAnyDeal API Key <span class="optional-tag">opcional</span></h2>
      <p>ITAD agrega datos de otras tiendas:</p>
      <ul style="font-size:.88rem;color:var(--text2);margin:0.3rem 0 0.8rem 1.2rem;line-height:1.8">
        <li><strong>Minimo historico</strong> &mdash; el precio mas bajo que ha tenido en Steam</li>
        <li><strong>Precios multi-tienda</strong> &mdash; si otra tienda lo tiene mas barato ahora</li>
        <li><strong>Bundles activos</strong> &mdash; si el juego esta en algun bundle</li>
      </ul>
      <p>Para obtenerla:</p>
      <ol style="font-size:.85rem;color:var(--text2);margin:0.3rem 0 0.8rem 1.2rem;line-height:1.8">
        <li>Crea cuenta en <a href="https://isthereanydeal.com/" target="_blank">isthereanydeal.com</a></li>
        <li>Ve a <a href="https://isthereanydeal.com/dev/app/" target="_blank">isthereanydeal.com/dev/app/</a></li>
        <li>Crea una app y copia la API key</li>
      </ol>
      <div class="field">
        <label>ITAD API Key</label>
        <div class="pw-wrap">
          <input type="password" id="wiz-itad" placeholder="Dejalo vacio si no tienes">
          <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
        </div>
      </div>
    </div>
    <div class="nav">
      <button class="btn btn-secondary" onclick="wizPrev()">&#8592; Atras</button>
      <button class="btn btn-primary" onclick="wizNext()">Siguiente &#8594;</button>
    </div>
  </div>

  <!-- Step 3: Confirm -->
  <div class="step" id="wiz-step-3">
    <div class="step-card">
      <span class="step-num">Paso 4 de 4</span>
      <h2>&#9989; Listo!</h2>
      <p>Tu configuracion:</p>
      <div style="background:var(--bg);border-radius:6px;padding:0.8rem;margin:0.8rem 0;font-size:0.88rem">
        <div style="margin-bottom:0.3rem"><strong>Perfil:</strong> <span id="wiz-summary-vanity" style="color:var(--accent)"></span></div>
        <div style="margin-bottom:0.3rem"><strong>Steam API Key:</strong> <span id="wiz-summary-key" style="color:var(--text2)"></span></div>
        <div><strong>ITAD Key:</strong> <span id="wiz-summary-itad" style="color:var(--text2)"></span></div>
      </div>
      <p>Puedes cambiar esto cuando quieras desde el formulario principal.</p>
      <div class="tip">&#128161; La configuracion se guarda automaticamente. No tendras que hacer esto de nuevo.</div>
    </div>
    <div class="nav">
      <button class="btn btn-secondary" onclick="wizPrev()">&#8592; Atras</button>
      <button class="btn btn-primary" onclick="wizFinish()">&#128640; Empezar</button>
    </div>
  </div>
</div>
</div>

<div class="header">
  <h1><span>&#127918;</span> Steam <span>Tools</span></h1>
</div>

<div class="container">
  <div class="mode-banner" id="mode-banner">
    <div>
      <strong id="mode-title">Modo: Cargando...</strong>
      <div class="hint-inline" id="mode-hint">Revisando cache y configuracion local.</div>
    </div>
    <button class="preset-btn" type="button" onclick="openWizard()">Configurar</button>
  </div>

  <!-- Tab navigation -->
  <div class="tabs" style="display:flex;gap:0;margin-bottom:1rem">
    <button class="tab-btn active" id="tab-deals" onclick="switchTab('deals')" style="flex:1;padding:.7rem;border:1px solid var(--card-border);border-radius:8px 0 0 8px;background:var(--accent);color:#fff;font-weight:600;font-size:.95rem;cursor:pointer;transition:all .2s">&#128640; Steam Deals</button>
    <button class="tab-btn" id="tab-pd2" onclick="switchTab('pd2')" style="flex:1;padding:.7rem;border:1px solid var(--card-border);border-left:none;border-radius:0 8px 8px 0;background:var(--card);color:var(--text2);font-weight:600;font-size:.95rem;cursor:pointer;transition:all .2s">&#127918; PAYDAY 2</button>
  </div>

  <!-- Shared config -->
  <div class="card">
      <h2 style="display:flex;align-items:center;justify-content:space-between;gap:.6rem">
        <span>Cuenta de Steam</span>
        <button type="button" class="btn" onclick="openWizard()" style="padding:.35rem .75rem;font-size:.8rem;background:var(--bg2);color:var(--text);border:1px solid var(--card-border)">
          Abrir wizard
        </button>
      </h2>
    <div class="field">
      <label>Perfil de Steam</label>
      <input type="text" id="vanity" placeholder="tu_vanity_url, Steam ID, o URL del perfil">
      <div class="hint">Vanity URL, Steam ID (17 digitos), o link completo del perfil</div>
    </div>
    <div class="row">
      <div class="field">
        <label>Steam API Key <span class="optional">(opcional)</span></label>
        <div class="pw-wrap">
          <input type="password" id="key" placeholder="Tu Steam API Key">
          <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
        </div>
        <div style="font-size:.72rem;color:var(--text2);margin-top:.3rem">Obtenla en <a href="https://steamcommunity.com/dev/apikey" target="_blank">steamcommunity.com/dev/apikey</a> — habilita juegos propios y biblioteca familiar</div>
      </div>
      <div class="field">
        <label>ITAD API Key <span class="optional">(opcional)</span></label>
        <div class="pw-wrap">
          <input type="password" id="itad_key" placeholder="IsThereAnyDeal Key">
          <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ═══ TAB: Steam Deals ═══ -->
  <div id="panel-deals">
  <div class="card">
    <h2>Configuracion</h2>
    <div class="field" style="margin-bottom:.4rem">
      <label>Presets de ejecucion</label>
      <div class="preset-row" id="preset-row">
        <button type="button" class="preset-btn" data-preset="rapido" onclick="applyPreset('rapido')">Rapido</button>
        <button type="button" class="preset-btn" data-preset="completo" onclick="applyPreset('completo')">Completo</button>
        <button type="button" class="preset-btn" data-preset="ahorro" onclick="applyPreset('ahorro')">Ahorro</button>
      </div>
      <div class="hint">Ajusta automaticamente filtros comunes; puedes modificar cualquier campo despues.</div>
    </div>
    <div class="field">
      <label>Descuento minimo</label>
      <div class="range-wrap">
        <input type="range" id="discount" min="10" max="95" step="5" value="50" oninput="document.getElementById('disc-val').textContent=this.value+'%'">
        <span class="range-val" id="disc-val">50%</span>
      </div>
    </div>
    <div class="row">
      <div class="field">
        <label>Top picks</label>
        <input type="number" id="top" value="10" min="1" max="50">
      </div>
      <div class="field">
        <label>Ordenar por</label>
        <select id="sort">
          <option value="discount">Descuento</option>
          <option value="price">Precio</option>
          <option value="reviews">Reviews</option>
          <option value="priority">Prioridad wishlist</option>
          <option value="score">Score (recomendación compuesta)</option>
        </select>
        <div class="hint">Score combina reviews, descuento, prioridad, $/hora HLTB, Deck, Metacritic y antigüedad (años desde lanzamiento).</div>
      </div>
    </div>
    <div class="field">
      <label>Generos <span class="optional">(opcional, separados por coma)</span></label>
      <div class="genre-autocomplete">
        <input type="text" id="genres" autocomplete="off" placeholder="roguelike, indie, rpg">
        <div id="genres-suggestions" class="genre-suggestions hidden"></div>
      </div>
    </div>
  </div>

  <div class="card">
    <details>
      <summary>Fuentes de datos</summary>
      <div class="details-body">
        <div class="field">
          <label>HLTB CSV <span class="optional">(opcional)</span></label>
          <input type="text" id="hltb" placeholder="~/hltb-export.csv">
          <div class="hint">Exporta desde tu perfil de HowLongToBeat</div>
        </div>
        <div class="field">
          <label>Family JSON <span class="optional">(opcional)</span></label>
          <input type="text" id="family_json" placeholder="~/familia.json">
        </div>
        <div class="field">
          <label>Directorio de salida</label>
          <input type="text" id="output" placeholder="(mismo directorio del script)">
        </div>
      </div>
    </details>

    <details>
      <summary>Filtros avanzados</summary>
      <div class="details-body">
        <div class="row">
          <div class="field">
            <label>Precio maximo (MXN)</label>
            <input type="number" id="max_price" min="0" placeholder="Sin limite">
          </div>
          <div class="field">
            <label>Min reviews %</label>
            <input type="number" id="min_reviews" min="0" max="100" placeholder="Cualquiera">
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Min # de reviews</label>
            <input type="number" id="min_review_count" min="0" placeholder="Cualquiera">
          </div>
          <div class="field">
            <label>Max HLTB horas</label>
            <input type="number" id="max_hours" min="0" placeholder="Sin limite">
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Presupuesto (MXN) <span class="optional">(Tu Presupuesto Ideal)</span></label>
            <input type="number" id="budget" min="0" step="50" placeholder="Sin limite">
            <div class="hint">Recomienda la mejor combinacion de juegos</div>
          </div>
          <div class="field">
            <label>Comparar con <span class="optional">(opcional)</span></label>
            <input type="text" id="compare" placeholder="Vanity URL del amigo">
            <div class="hint">Wishlist del amigo debe ser publica</div>
          </div>
        </div>
        <div class="checks" style="margin-top:0.5rem">
          <label><input type="checkbox" id="deck_only"> Solo Deck compatible</label>
          <label><input type="checkbox" id="deck_verified"> Solo Deck Verified</label>
          <label><input type="checkbox" id="new_only"> Solo deals nuevos</label>
          <label><input type="checkbox" id="csv"> Generar CSV</label>
          <label><input type="checkbox" id="no_cache"> Ignorar cache</label>
        </div>
      </div>
    </details>

    <details>
      <summary>Notificaciones</summary>
      <div class="details-body">
        <div class="field">
          <label>Telegram Bot Token <span class="optional">(opcional)</span></label>
          <div class="pw-wrap">
            <input type="password" id="telegram_token" placeholder="123456:ABC-DEF...">
            <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Telegram Chat ID</label>
            <input type="text" id="telegram_chat" placeholder="-100123456789">
          </div>
          <div class="field">
            <label>Discord Webhook</label>
            <div class="pw-wrap">
              <input type="password" id="discord_webhook" placeholder="https://discord.com/api/webhooks/...">
              <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
            </div>
          </div>
        </div>
        <div class="hint">Envia un resumen cuando hay deals nuevos o price drops</div>
      </div>
    </details>
  </div>

  <!-- Watchlist -->
  <div class="card">
    <h2>&#127919; Watchlist (Price Alerts)</h2>
    <div class="field">
      <div class="row">
        <div class="field"><label>AppID</label><input type="text" id="wl-appid" placeholder="730"></div>
        <div class="field"><label>Nombre</label><input type="text" id="wl-name" placeholder="Counter-Strike 2"></div>
        <div class="field"><label>Precio objetivo (MXN)</label><input type="number" id="wl-price" placeholder="200" min="0"></div>
      </div>
      <button class="btn btn-primary" style="margin-top:.5rem;padding:.4rem 1rem;font-size:.85rem" onclick="addWatchlist()">+ Agregar</button>
    </div>
    <div id="wl-list" style="margin-top:.75rem"></div>
  </div>

  </div><!-- /panel-deals -->

  <!-- ═══ TAB: PAYDAY 2 ═══ -->
  <div id="panel-pd2" style="display:none">
  <div class="card">
    <h2>&#127918; PAYDAY 2 DLC Tracker</h2>
    <div class="row">
      <div class="field">
        <label>Presupuesto MXN <span class="optional">(opcional)</span></label>
        <div class="range-wrap">
          <input type="range" id="pd2_budget" min="0" max="5000" step="50" value="0" oninput="document.getElementById('pd2-bval').textContent=this.value>0?('$'+this.value):'Sin limite'">
          <span class="range-val" id="pd2-bval">Sin limite</span>
        </div>
      </div>
      <div class="field">
        <label>Alerta de precio <span class="optional">(MXN)</span></label>
        <input type="number" id="pd2_alert" min="0" placeholder="Alertar si DLC baja de este precio">
      </div>
    </div>
    <div class="row">
      <div class="field">
        <label>Min. descuento para recomendar <span class="optional">(%)</span></label>
        <input type="number" id="pd2_min_deal" min="0" max="100" value="50" placeholder="50">
      </div>
      <div class="field">
        <label>Directorio de salida</label>
        <input type="text" id="pd2_output" placeholder="(mismo directorio del script)">
      </div>
    </div>
    <div class="checks" style="margin-top:0.5rem">
      <label><input type="checkbox" id="pd2_csv"> Generar CSV</label>
      <label><input type="checkbox" id="pd2_no_cache"> Ignorar cache</label>
    </div>
  </div>
  </div><!-- /panel-pd2 -->

  <div class="actions" style="margin-bottom:.6rem">
    <button class="btn" id="btn-preflight" style="background:var(--bg2);color:var(--text);border:1px solid var(--card-border)">&#129514; Probar config</button>
    <button class="btn" id="btn-desktop-doctor" style="background:var(--bg2);color:var(--text);border:1px solid var(--card-border)">&#129658; Doctor desktop</button>
    <button class="btn" id="btn-desktop-autofix" style="background:var(--bg2);color:var(--text);border:1px solid var(--card-border)">&#128295; Autofix desktop</button>
    <button class="btn" id="btn-clear-cache" style="background:var(--bg2);color:var(--text);border:1px solid var(--card-border)">&#128465; Limpiar cache</button>
    <button class="btn" id="btn-open-last" style="background:var(--bg2);color:var(--text);border:1px solid var(--card-border)">&#128194; Abrir ultimo reporte</button>
  </div>

  <div class="actions" style="margin-bottom:1rem">
    <button class="btn btn-primary" id="btn-run">&#128640; Ejecutar</button>
    <button class="btn btn-danger" id="btn-stop" disabled>&#9209; Detener</button>
  </div>

  <!-- Output panel -->
  <div class="card" id="output-card">
    <h2>Ejecucion</h2>
    <div class="progress-container">
      <div class="progress-bar" id="progress-bar"></div>
      <div class="progress-text" id="progress-text">Listo</div>
    </div>
    <div class="console" id="console"></div>
    <div class="file-links hidden" id="file-links"></div>
  </div>
</div>

<script>
// ── Helpers ──
function $(id) { return document.getElementById(id); }
function togglePw(btn) {
  const inp = btn.previousElementSibling;
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

// ── Config fields (saveable) ──
const CONFIG_FIELDS = ['vanity','key','hltb','output','discount','genres','family_json','itad_key','compare','telegram_token','telegram_chat','discord_webhook'];
const FILTER_FIELDS = ['max_price','min_reviews','min_review_count','max_hours','top','sort','budget'];
const CHECK_FIELDS  = ['deck_only','deck_verified','new_only','csv','no_cache'];
const GENRE_SUGGESTIONS = [
  'action', 'adventure', 'indie', 'rpg', 'strategy', 'simulation', 'casual', 'sports',
  'racing', 'puzzle', 'platformer', 'metroidvania', 'roguelike', 'roguelite', 'soulslike',
  'survival', 'horror', 'open world', 'sandbox', 'crafting', 'city builder', '4x', 'turn-based',
  'real-time strategy', 'deckbuilder', 'card game', 'tactical', 'shooter', 'fps', 'third-person',
  'co-op', 'multiplayer', 'singleplayer', 'visual novel', 'rhythm', 'bullet hell', 'tower defense'
];

function getConfig() {
  const c = {};
  CONFIG_FIELDS.forEach(f => {
    const el = $(f);
    if (!el) return;
    if (f === 'discount') c[f] = parseInt(el.value);
    else c[f] = el.value.trim() || null;
  });
  c.vanity = normalizeVanity(c.vanity);
  return c;
}

function normalizeVanity(value) {
  const v = (value || '').trim();
  if (!v) return '';
  if (v.startsWith('http://') || v.startsWith('https://')) return v;
  if (/^\d{16,}$/.test(v)) return `https://steamcommunity.com/profiles/${v}/`;
  if (v.startsWith('id/')) return `https://steamcommunity.com/${v.endsWith('/') ? v : v + '/'}`;
  if (v.startsWith('profiles/')) return `https://steamcommunity.com/${v.endsWith('/') ? v : v + '/'}`;
  return `https://steamcommunity.com/id/${v}/`;
}

function getFilters() {
  const f = {};
  FILTER_FIELDS.forEach(k => {
    const el = $(k);
    if (!el) return;
    const v = el.value.trim();
    if (k === 'sort') f[k] = v;
    else if (v) f[k] = parseFloat(v);
  });
  CHECK_FIELDS.forEach(k => {
    const el = $(k);
    if (el) f[k] = el.checked;
  });
  return f;
}

function fillForm(cfg) {
  if (!cfg) return;
  CONFIG_FIELDS.forEach(f => {
    const el = $(f);
    if (!el || cfg[f] == null) return;
    if (f === 'discount') {
      el.value = cfg[f];
      $('disc-val').textContent = cfg[f] + '%';
    } else if (f === 'genres') {
      el.value = Array.isArray(cfg[f]) ? cfg[f].join(', ') : (cfg[f] || '');
    } else if (f === 'output') {
      el.value = cfg.output_dir || cfg.output || '';
    } else {
      el.value = cfg[f] || '';
    }
  });
}

const genresInput = $('genres');
const genresSuggestions = $('genres-suggestions');
let genresActiveIndex = -1;

function _genresSelectedSet() {
  const set = new Set();
  const parts = (genresInput.value || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
  parts.forEach(p => set.add(p));
  return set;
}

function _genresCurrentToken() {
  const raw = genresInput.value || '';
  const lastComma = raw.lastIndexOf(',');
  const tokenStartBase = lastComma === -1 ? 0 : lastComma + 1;
  const leadingSpaces = (raw.slice(tokenStartBase).match(/^\s*/) || [''])[0].length;
  const start = tokenStartBase + leadingSpaces;
  return {
    raw,
    start,
    token: raw.slice(start).trim().toLowerCase(),
  };
}

function hideGenreSuggestions() {
  genresActiveIndex = -1;
  genresSuggestions.classList.add('hidden');
  genresSuggestions.innerHTML = '';
}

function applyGenreSuggestion(genre) {
  const ctx = _genresCurrentToken();
  const before = ctx.raw.slice(0, ctx.start);
  genresInput.value = `${before}${genre}, `;
  hideGenreSuggestions();
  genresInput.focus();
}

function renderGenreSuggestions() {
  const ctx = _genresCurrentToken();
  if (!ctx.token) {
    hideGenreSuggestions();
    return;
  }
  const selected = _genresSelectedSet();
  const items = GENRE_SUGGESTIONS
    .filter(g => g.includes(ctx.token) && !selected.has(g.toLowerCase()))
    .slice(0, 8);

  if (!items.length) {
    hideGenreSuggestions();
    return;
  }

  genresSuggestions.innerHTML = items.map((g, i) =>
    `<button type="button" class="genre-suggestion${i === genresActiveIndex ? ' active' : ''}" data-genre="${g}">${g}</button>`
  ).join('');
  genresSuggestions.classList.remove('hidden');

  genresSuggestions.querySelectorAll('.genre-suggestion').forEach(btn => {
    btn.addEventListener('mousedown', (e) => {
      e.preventDefault();
      applyGenreSuggestion(btn.dataset.genre || '');
    });
  });
}

genresInput.addEventListener('input', renderGenreSuggestions);
genresInput.addEventListener('focus', renderGenreSuggestions);
genresInput.addEventListener('blur', () => setTimeout(hideGenreSuggestions, 120));
genresInput.addEventListener('keydown', (e) => {
  const buttons = Array.from(genresSuggestions.querySelectorAll('.genre-suggestion'));
  if (!buttons.length || genresSuggestions.classList.contains('hidden')) return;

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    genresActiveIndex = (genresActiveIndex + 1) % buttons.length;
    renderGenreSuggestions();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    genresActiveIndex = genresActiveIndex <= 0 ? buttons.length - 1 : genresActiveIndex - 1;
    renderGenreSuggestions();
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    if (genresActiveIndex >= 0 && genresActiveIndex < buttons.length) {
      e.preventDefault();
      applyGenreSuggestion(buttons[genresActiveIndex].dataset.genre || '');
    }
  } else if (e.key === 'Escape') {
    hideGenreSuggestions();
  }
});

// ── Wizard ──
let wizStep = 0;
const WIZ_TOTAL = 4;

function wizUpdateDots() {
  for (let i = 0; i < WIZ_TOTAL; i++) {
    const d = document.getElementById('dot-' + i);
    d.className = 'dot' + (i === wizStep ? ' active' : i < wizStep ? ' done' : '');
  }
}

function wizShowStep(n) {
  for (let i = 0; i < WIZ_TOTAL; i++) {
    document.getElementById('wiz-step-' + i).classList.toggle('active', i === n);
  }
  wizStep = n;
  wizUpdateDots();
  if (n === 3) {
    // Update summary
    document.getElementById('wiz-summary-vanity').textContent = document.getElementById('wiz-vanity').value.trim() || '(no configurado)';
    document.getElementById('wiz-summary-key').textContent = document.getElementById('wiz-key').value.trim() ? 'Configurada' : 'No (modo publico)';
    document.getElementById('wiz-summary-itad').textContent = document.getElementById('wiz-itad').value.trim() ? 'Configurada' : 'No';
  }
}

function wizNext() {
  if (wizStep === 0 && !document.getElementById('wiz-vanity').value.trim()) {
    const inp = document.getElementById('wiz-vanity');
    inp.style.borderColor = 'var(--red)';
    inp.focus();
    setTimeout(() => inp.style.borderColor = '', 2000);
    return;
  }
  if (wizStep < WIZ_TOTAL - 1) wizShowStep(wizStep + 1);
}

function wizPrev() {
  if (wizStep > 0) wizShowStep(wizStep - 1);
}

function wizFinish() {
  const vanity = document.getElementById('wiz-vanity').value.trim();
  const key = document.getElementById('wiz-key').value.trim();
  const itad = document.getElementById('wiz-itad').value.trim();
  // Fill main form
  document.getElementById('vanity').value = vanity;
  if (key) document.getElementById('key').value = key;
  if (itad) document.getElementById('itad_key').value = itad;
  // Save config
  const cfg = {vanity};
  if (key) cfg.key = key;
  if (itad) cfg.itad_key = itad;
  fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(cfg)}).catch(() => {});
  closeWizard();
}

function prefillWizard(cfg, keepVanity=false) {
  const vanityInp = document.getElementById('wiz-vanity');
  vanityInp.value = '';
  vanityInp.placeholder = 'Ejemplo: https://steamcommunity.com/id/tu_usuario/';
  if (!cfg) return;
  if (keepVanity && cfg.vanity) vanityInp.value = cfg.vanity;
  if (cfg.key) document.getElementById('wiz-key').value = cfg.key;
  if (cfg.itad_key) document.getElementById('wiz-itad').value = cfg.itad_key;
}

function openWizard() {
  prefillWizard(getConfig(), false);
  wizShowStep(0);
  document.getElementById('wizard-overlay').style.display = 'block';
}

function closeWizard() {
  document.getElementById('wizard-overlay').style.display = 'none';
}

// ── Load config on startup ──
Promise.all([
  fetch('/api/config').then(r => r.json()),
  fetch('/api/ui-state').then(r => r.json()),
]).then(([cfg, state]) => {
  fillForm(cfg);
  prefillWizard(cfg, false);
  if (state) {
    setModeBanner(!!state.has_cache, !!state.has_config);
  }
  setActivePreset('rapido');
  if (state && state.has_cache) {
    closeWizard();
  } else {
    openWizard();
  }
}).catch(() => {
  fetch('/api/config').then(r => r.json()).then(cfg => {
    fillForm(cfg);
    prefillWizard(cfg, false);
    setModeBanner(false, !!(cfg && cfg.vanity));
    setActivePreset('rapido');
    if (cfg && cfg.vanity) closeWizard();
    else openWizard();
  }).catch(() => {});
});

// ── Run ──
const btnRun = $('btn-run');
const btnStop = $('btn-stop');
const btnPreflight = $('btn-preflight');
const btnDesktopDoctor = $('btn-desktop-doctor');
const btnDesktopAutofix = $('btn-desktop-autofix');
const btnClearCache = $('btn-clear-cache');
const btnOpenLast = $('btn-open-last');
const consoleEl = $('console');
const progressBar = $('progress-bar');
const progressText = $('progress-text');
const fileLinks = $('file-links');
let abortCtrl = null;
let shownErrorHints = new Set();
let stopRequestInFlight = false;
let stopMessageShown = false;

function resetStopUiState() {
  stopRequestInFlight = false;
  stopMessageShown = false;
  if (btnStop) btnStop.disabled = true;
}

function beginStopUiState() {
  stopRequestInFlight = true;
  if (btnStop) btnStop.disabled = true;
  if (!stopMessageShown) {
    appendLine('Solicitando detener ejecucion...', 'warn');
    stopMessageShown = true;
  }
}

function completeStopUiState() {
  stopRequestInFlight = false;
}

function setModeBanner(hasCache, hasConfig) {
  const title = $('mode-title');
  const hint = $('mode-hint');
  if (hasCache) {
    title.textContent = 'Modo: Actualizacion rapida';
    hint.textContent = hasConfig
      ? 'Se detecto cache local. Puedes ejecutar directo o ajustar presets.'
      : 'Hay cache local disponible. Revisa tu perfil y ejecuta cuando quieras.';
  } else {
    title.textContent = 'Modo: Primer setup';
    hint.textContent = 'No se detecto cache local. Usa el wizard y ejecuta tu primer analisis.';
  }
}

function setActivePreset(name) {
  document.querySelectorAll('#preset-row .preset-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.preset === name);
  });
}

function applyPreset(name) {
  if (name === 'rapido') {
    $('top').value = 10;
    $('discount').value = 60;
    $('disc-val').textContent = '60%';
    $('deck_only').checked = false;
    $('deck_verified').checked = false;
    $('new_only').checked = true;
    $('no_cache').checked = false;
  } else if (name === 'completo') {
    $('top').value = 20;
    $('discount').value = 45;
    $('disc-val').textContent = '45%';
    $('deck_only').checked = false;
    $('deck_verified').checked = false;
    $('new_only').checked = false;
    $('no_cache').checked = true;
  } else if (name === 'ahorro') {
    $('top').value = 12;
    $('discount').value = 70;
    $('disc-val').textContent = '70%';
    $('deck_only').checked = false;
    $('deck_verified').checked = false;
    $('new_only').checked = true;
    $('no_cache').checked = false;
    if (!$('budget').value) $('budget').value = '500';
    if (!$('max_price').value) $('max_price').value = '250';
  }
  setActivePreset(name);
  appendLine('Preset aplicado: ' + name + '.', 'step');
}

function detectErrorCategory(text) {
  const t = (text || '').toLowerCase();
  if (!t) return null;
  if (t.includes('429') || t.includes('rate limit') || t.includes('too many requests')) return 'rate-limit';
  if (t.includes('unicodeencodeerror') || t.includes('cp1252') || t.includes('codec can\'t encode') || t.includes('encoding')) return 'encoding';
  if (t.includes('failed to fetch') || t.includes('timeout') || t.includes('timed out') || t.includes('connection') || t.includes('dns') || t.includes('name or service not known')) return 'network';
  if (t.includes('vanity') || t.includes('steam id') || t.includes('config invalida') || t.includes('falta el perfil') || t.includes('no se encontr') || t.includes('api key') || t.includes('invalid')) return 'config';
  return null;
}

function errorHintForCategory(category) {
  if (category === 'network') {
    return 'SUGERENCIA [network]: revisa internet/VPN/firewall y vuelve a intentar en unos segundos.';
  }
  if (category === 'config') {
    return 'SUGERENCIA [config]: valida perfil Steam, rutas opcionales y API keys; usa "Probar config" antes de ejecutar.';
  }
  if (category === 'rate-limit') {
    return 'SUGERENCIA [rate-limit]: Steam/servicios limitaron solicitudes; espera 1-3 minutos y reintenta.';
  }
  if (category === 'encoding') {
    return 'SUGERENCIA [encoding]: se detecto problema de codificacion de salida; reinicia app y usa la version mas reciente del ejecutable.';
  }
  return null;
}

function maybeShowActionableHint(text, cls) {
  if (cls !== 'err' && cls !== 'warn') return;
  const category = detectErrorCategory(text);
  if (!category || shownErrorHints.has(category)) return;
  shownErrorHints.add(category);
  const hint = errorHintForCategory(category);
  if (hint) appendLine(hint, 'warn');
}

async function runPreflightUI() {
  const pre = await fetch('/api/preflight', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({config: getConfig(), filters: getFilters()}),
  });
  const preData = await pre.json();
  appendLine('Preflight ejecutado.', preData.ok ? 'ok' : 'warn');
  (preData.warnings || []).forEach(w => appendLine('WARN: ' + w, 'warn'));
  (preData.issues || []).forEach(i => appendLine('ISSUE: ' + i, 'err'));
  return preData;
}

function doctorLineClass(text, overall) {
  if (!text) return 'dim';
  if (text.startsWith('[OK]')) return 'ok';
  if (text.startsWith('[WARN]')) return 'warn';
  if (text.startsWith('[FAIL]')) return 'err';
  if (text.startsWith('[fix]')) return 'step';
  if (text.startsWith('[done]')) return 'ok';
  if (text.startsWith('[skip]')) return 'dim';
  if (text.startsWith('Resultado general:')) {
    if (overall === 'READY') return 'ok';
    if (overall === 'BLOCKED') return 'err';
    return 'warn';
  }
  if (text.startsWith('===') || text.startsWith('Platform:')) return 'step';
  if (text.trim().startsWith('-')) return 'dim';
  return 'normal';
}

function appendDoctorReport(data, introText='Desktop Doctor ejecutado.') {
  appendLine(introText, data.exit_code === 1 ? 'err' : data.overall === 'READY' ? 'ok' : 'warn');
  (data.lines || []).forEach(line => {
    if (!line) return;
    appendLine(line, doctorLineClass(line, data.overall));
  });
}

function renderDoctorFixPlan(fixes) {
  if (!fixes || !fixes.length) {
    appendLine('No hay autofixes seguros disponibles para este entorno.', 'ok');
    return;
  }
  appendLine('Autofixes seguros disponibles:', 'step');
  fixes.forEach((fix, index) => {
    appendLine(`${index + 1}. ${fix.title} — ${fix.summary}`, 'dim');
    (fix.commands || []).forEach(command => appendLine('  - ' + command, 'dim'));
  });
}

async function fetchDesktopDoctorReport() {
  const resp = await fetch('/api/desktop-doctor', {method: 'POST'});
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.message || data.error || ('HTTP ' + resp.status));
  }
  return data;
}

async function runDesktopDoctorUI() {
  const data = await fetchDesktopDoctorReport();
  appendDoctorReport(data);
  return data;
}

async function runDesktopDoctorAutofixUI() {
  const report = await fetchDesktopDoctorReport();
  appendDoctorReport(report, 'Desktop Doctor ejecutado antes del autofix.');
  renderDoctorFixPlan(report.fixes || []);
  if (!report.fixes || !report.fixes.length) {
    return {status: 'noop', report};
  }

  const accepted = window.confirm('Se aplicarán solo autofixes seguros del proyecto (.venv local, deps desktop en .venv y/o build local). ¿Continuar?');
  if (!accepted) {
    appendLine('Autofix desktop cancelado por el usuario.', 'warn');
    return {status: 'cancelled', report};
  }

  const resp = await fetch('/api/desktop-doctor/fix', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({confirm: true}),
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.message || data.error || ('HTTP ' + resp.status));
  }

  appendLine('Autofix desktop ejecutado.', data.status === 'failed' ? 'err' : data.status === 'applied' ? 'ok' : 'warn');
  (data.lines || []).forEach(line => {
    if (!line) return;
    appendLine(line, doctorLineClass(line, data.report && data.report.overall));
  });
  if (data.report) {
    appendDoctorReport(data.report, 'Doctor desktop tras autofix.');
  }
  return data;
}

btnPreflight.addEventListener('click', async () => {
  try {
    await runPreflightUI();
  } catch(e) {
    appendLine('No se pudo ejecutar preflight: ' + e.message, 'err');
  }
});

btnDesktopDoctor.addEventListener('click', async () => {
  btnDesktopDoctor.disabled = true;
  try {
    await runDesktopDoctorUI();
  } catch(e) {
    appendLine('No se pudo ejecutar Desktop Doctor: ' + e.message, 'err');
  } finally {
    btnDesktopDoctor.disabled = false;
  }
});

if (btnDesktopAutofix) btnDesktopAutofix.addEventListener('click', async () => {
  btnDesktopAutofix.disabled = true;
  if (btnDesktopDoctor) btnDesktopDoctor.disabled = true;
  try {
    await runDesktopDoctorAutofixUI();
  } catch(e) {
    appendLine('No se pudo ejecutar Autofix desktop: ' + e.message, 'err');
  } finally {
    btnDesktopAutofix.disabled = false;
    if (btnDesktopDoctor) btnDesktopDoctor.disabled = false;
  }
});

btnClearCache.addEventListener('click', async () => {
  try {
    const r = await fetch('/api/cache/clear', {method: 'POST'});
    const d = await r.json();
    appendLine('Cache limpiada: ' + (d.removed || 0) + ' archivo(s).', 'ok');
  } catch(e) {
    appendLine('No se pudo limpiar cache: ' + e.message, 'err');
  }
});

btnOpenLast.addEventListener('click', async () => {
  try {
    const r = await fetch('/api/files');
    const files = await r.json();
    if (!files || !files.length) {
      appendLine('No hay reportes generados todavia.', 'warn');
      return;
    }
    const name = files[0].name;
    window.open('/files/' + encodeURIComponent(name), '_blank');
    appendLine('Abriendo reporte: ' + name, 'ok');
  } catch(e) {
    appendLine('No se pudo abrir ultimo reporte: ' + e.message, 'err');
  }
});

function appendLine(text, cls) {
  const div = document.createElement('div');
  div.className = 'line line-' + cls;
  div.textContent = text;
  consoleEl.appendChild(div);
  consoleEl.scrollTop = consoleEl.scrollHeight;
  maybeShowActionableHint(text, cls);
}

btnRun.addEventListener('click', async () => {
  if (!$('vanity').value.trim()) {
    $('vanity').focus();
    $('vanity').style.borderColor = 'var(--red)';
    setTimeout(() => $('vanity').style.borderColor = '', 2000);
    return;
  }

  // Reset UI
  shownErrorHints = new Set();
  consoleEl.innerHTML = '';
  progressBar.style.width = '0%';
  progressText.textContent = 'Iniciando...';
  fileLinks.innerHTML = '';
  fileLinks.classList.add('hidden');
  btnRun.disabled = true;
  resetStopUiState();
  btnStop.disabled = false;

  // Preflight
  try {
    const preData = await runPreflightUI();
    if (!preData.ok) {
      appendLine('Validacion previa fallida. Corrige lo siguiente:', 'err');
      btnRun.disabled = false;
      btnStop.disabled = true;
      progressText.textContent = 'Config invalida';
      progressBar.style.width = '0%';
      return;
    }
  } catch(e) {
    appendLine('No se pudo ejecutar preflight: ' + e.message, 'warn');
  }

  abortCtrl = new AbortController();

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: getConfig(), filters: getFilters()}),
      signal: abortCtrl.signal,
    });

    if (!resp.ok && resp.status !== 409) {
      let msg = 'HTTP ' + resp.status;
      try {
        const body = await resp.json();
        if (body && body.error) msg = body.error;
      } catch(e) {}
      appendLine('Error del servidor: ' + msg, 'err');
      return;
    }

    if (resp.status === 409) {
      appendLine('Ya hay una ejecucion en curso.', 'warn');
      btnRun.disabled = false;
      resetStopUiState();
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});

      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of block.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const ev = JSON.parse(line.slice(6));
              handleEvent(ev);
            } catch(e) {}
          }
        }
      }
    }
  } catch(e) {
    if (e.name !== 'AbortError') {
      appendLine('Error de conexion: ' + e.message, 'err');
    }
  }

  btnRun.disabled = false;
  resetStopUiState();
  abortCtrl = null;
});

btnStop.addEventListener('click', async () => {
  if (stopRequestInFlight) return;
  beginStopUiState();
  try {
    const resp = await fetch('/api/stop', {method: 'POST'});
    let payload = {};
    try {
      payload = await resp.json();
    } catch (e) {}
    if (!resp.ok) {
      appendLine((payload && payload.message) || ('No se pudo detener la ejecucion: HTTP ' + resp.status), 'err');
    } else if (payload && payload.status === 'stopped') {
      appendLine(payload.message || '--- Cancelado por el usuario ---', 'warn');
      if (abortCtrl) abortCtrl.abort();
    } else if (payload && payload.status === 'not_running') {
      appendLine(payload.message || 'No habia una ejecucion activa para detener.', 'dim');
      if (abortCtrl) abortCtrl.abort();
    } else {
      appendLine((payload && payload.message) || 'Estado de detener desconocido.', 'warn');
    }
  } catch(e) {
    appendLine('No se pudo detener la ejecucion: ' + e.message, 'err');
  } finally {
    completeStopUiState();
  }
});

// PD2 Tracker button
$('btn-run-pd2').addEventListener('click', async () => {
  if (!$('vanity').value.trim()) { $('vanity').focus(); return; }
  shownErrorHints = new Set();
  consoleEl.innerHTML = '';
  progressBar.style.width = '0%';
  progressBar.style.background = 'linear-gradient(90deg, #d4a84b, #b8922e)';
  progressText.textContent = 'PAYDAY 2 Tracker...';
  fileLinks.innerHTML = '';
  fileLinks.classList.add('hidden');
  btnRun.disabled = true;
  $('btn-run-pd2').disabled = true;
  resetStopUiState();
  btnStop.disabled = false;
  abortCtrl = new AbortController();
  try {
    const resp = await fetch('/api/run-pd2', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        config: getConfig(),
        filters: {
          no_cache: $('pd2_no_cache').checked,
          csv: $('pd2_csv').checked,
          budget: $('pd2_budget').value ? parseFloat($('pd2_budget').value) : null,
          alert_price: $('pd2_alert').value ? parseFloat($('pd2_alert').value) : null,
          min_deal: $('pd2_min_deal').value ? parseInt($('pd2_min_deal').value) : null,
        }
      }),
      signal: abortCtrl.signal,
    });
    if (resp.status === 409) { appendLine('Ya hay una ejecucion en curso.', 'warn'); }
    else {
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          for (const line of block.split('\n')) {
            if (line.startsWith('data: ')) {
              try { handleEvent(JSON.parse(line.slice(6))); } catch(e) {}
            }
          }
        }
      }
    }
  } catch(e) { if (e.name !== 'AbortError') appendLine('Error: ' + e.message, 'err'); }
  btnRun.disabled = false;
  $('btn-run-pd2').disabled = false;
  resetStopUiState();
  abortCtrl = null;
});

function handleEvent(ev) {
  if (ev.type === 'line') {
    appendLine(ev.text, ev.cls || 'normal');
  }
  else if (ev.type === 'progress') {
    const pct = Math.round(ev.current / ev.total * 100);
    progressBar.style.width = pct + '%';
    progressText.textContent = '[' + ev.current + '/' + ev.total + '] ' + ev.label;
  }
  else if (ev.type === 'done') {
    resetStopUiState();
    progressBar.style.width = '100%';
    if (ev.exit_code === 0) {
      progressText.textContent = 'Completado';
      progressBar.style.background = 'linear-gradient(90deg, var(--green), #4eaa5a)';
    } else {
      progressText.textContent = 'Error (codigo ' + ev.exit_code + ')';
      progressBar.style.background = 'linear-gradient(90deg, var(--red), #a02020)';
    }
    if (ev.files && ev.files.length) {
      showFiles(ev.files);
      appendQuickOpenButtons(ev.files);
    }
    syncLatestReportEmptyState(ev.files);
    syncLatestReportCard(ev.files);
  }
}

function showFiles(files) {
  fileLinks.innerHTML = '';
  const icons = {'.html': '&#128202;', '.md': '&#128196;', '.csv': '&#128203;', '.json': '&#123;&#125;'};
  files.forEach(f => {
    const name = f.split('/').pop();
    const ext = name.slice(name.lastIndexOf('.'));
    const icon = icons[ext] || '&#128196;';
    const a = document.createElement('a');
    a.className = 'file-link';
    a.href = '/files/' + encodeURIComponent(name);
    a.target = '_blank';
    a.innerHTML = icon + ' ' + name;
    fileLinks.appendChild(a);
  });
  fileLinks.classList.remove('hidden');
}

function latestReportUrl() {
  return new URL('/api/latest-report', window.location.origin).href;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatLatestReportTimestamp(value) {
  if (!value) return 'Fecha desconocida';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function latestReportCardEl() {
  let el = $('latest-report-card');
  if (el) return el;
  const card = $('output-card');
  if (!card) return null;
  el = document.createElement('div');
  el.id = 'latest-report-card';
  el.className = 'latest-report-card hidden';
  card.insertBefore(el, fileLinks);
  return el;
}

function hideLatestReportCard() {
  const el = latestReportCardEl();
  if (!el) return;
  el.classList.add('hidden');
  el.innerHTML = '';
}

function renderLatestReportCard(report) {
  const el = latestReportCardEl();
  if (!el) return;
  const meta = report && typeof report === 'object' ? (report.meta || {}) : {};
  const summary = report && typeof report === 'object' ? (report.summary || {}) : {};
  const subtitleParts = [];
  if (meta.profile) subtitleParts.push(`Perfil: ${escapeHtml(meta.profile)}`);
  subtitleParts.push(escapeHtml(formatLatestReportTimestamp(meta.generated_at)));
  const saleBadge = meta.sale_name ? `<span class="latest-report-badge">${escapeHtml(meta.sale_name)}</span>` : '';
  const stats = [
    ['Deals', summary.deals_count ?? 0],
    ['Top picks', summary.top_picks_count ?? 0],
    ['Alerts', summary.watchlist_alerts_count ?? 0],
    ['Regalos', summary.gift_ideas_count ?? 0],
  ];
  el.innerHTML = `
    <div class="latest-report-head">
      <div>
        <div class="latest-report-title">Ultimo reporte</div>
        <div class="latest-report-subtitle">${subtitleParts.join(' · ')}</div>
      </div>
      ${saleBadge}
    </div>
    <div class="latest-report-stats">
      ${stats.map(([label, value]) => `
        <div class="latest-report-stat">
          <div class="latest-report-stat-label">${escapeHtml(label)}</div>
          <div class="latest-report-stat-value">${escapeHtml(value)}</div>
        </div>
      `).join('')}
    </div>
  `;
  el.classList.remove('hidden');
}

async function syncLatestReportCard(files = null) {
  if (Array.isArray(files) && !hasJsonArtifact(files)) {
    hideLatestReportCard();
    return;
  }
  try {
    const resp = await fetch('/api/latest-report');
    if (!resp.ok) {
      hideLatestReportCard();
      return;
    }
    renderLatestReportCard(await resp.json());
  } catch (e) {
    hideLatestReportCard();
  }
}

function latestReportEmptyStateEl() {
  let el = $('latest-report-empty-state');
  if (el) return el;
  const card = $('output-card');
  if (!card) return null;
  el = document.createElement('div');
  el.id = 'latest-report-empty-state';
  el.className = 'latest-report-empty-state hidden';
  card.appendChild(el);
  return el;
}

function hasJsonArtifact(files) {
  return Array.isArray(files) && files.some(file => {
    const name = typeof file === 'string' ? file.split('/').pop() : (file && file.name) || '';
    return /\.json$/i.test(name || '');
  });
}

function showLatestReportEmptyState(message) {
  const el = latestReportEmptyStateEl();
  if (!el) return;
  el.innerHTML = `<strong>Sin reporte JSON todavia.</strong><span>${message}</span>`;
  el.classList.remove('hidden');
}

function hideLatestReportEmptyState() {
  const el = latestReportEmptyStateEl();
  if (!el) return;
  el.classList.add('hidden');
  el.innerHTML = '';
}

async function syncLatestReportEmptyState(files = null) {
  if (hasJsonArtifact(files)) {
    hideLatestReportEmptyState();
    return;
  }
  if (Array.isArray(files)) {
    showLatestReportEmptyState('Corre Steam Deals una vez en este directorio para habilitar Abrir/Copiar JSON.');
    return;
  }
  try {
    const resp = await fetch('/api/files');
    const listedFiles = await resp.json();
    if (hasJsonArtifact(listedFiles)) {
      hideLatestReportEmptyState();
      return;
    }
  } catch (e) {}
  showLatestReportEmptyState('Corre Steam Deals una vez en este directorio para habilitar Abrir/Copiar JSON.');
}

function isShareHtmlFile(filePath) {
  return /steam deals share .*\.html$/i.test((filePath || '').split('/').pop() || '');
}

function copyLatestReportUrl(btn) {
  const url = latestReportUrl();
  const resetLabel = btn.innerHTML;
  const showCopied = () => {
    btn.textContent = '¡Copiado!';
    setTimeout(() => { btn.innerHTML = resetLabel; }, 2000);
  };

  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    navigator.clipboard.writeText(url).then(showCopied).catch(() => {
      window.prompt('Copia esta URL:', url);
    });
    return;
  }

  window.prompt('Copia esta URL:', url);
}

function appendQuickOpenButtons(files) {
  const htmlFile = files ? files.find(f => f.endsWith('.html') && !isShareHtmlFile(f)) : null;
  const shareHtmlFile = files ? files.find(isShareHtmlFile) : null;
  const jsonFile = files ? files.find(f => f.endsWith('.json')) : null;
  if (!htmlFile && !shareHtmlFile && !jsonFile) return;

  const btnContainer = document.createElement('div');
  btnContainer.style.cssText = 'margin-top:0.75rem;display:flex;gap:0.5rem;flex-wrap:wrap';

  if (htmlFile) {
    const openHtmlBtn = document.createElement('a');
    openHtmlBtn.href = '/files/' + encodeURIComponent(htmlFile.split('/').pop());
    openHtmlBtn.target = '_blank';
    openHtmlBtn.className = 'file-link';
    openHtmlBtn.innerHTML = '&#128202; Abrir reporte interactivo (con botones compartir)';
    btnContainer.appendChild(openHtmlBtn);
  }

  if (shareHtmlFile) {
    const openShareBtn = document.createElement('a');
    openShareBtn.href = '/files/' + encodeURIComponent(shareHtmlFile.split('/').pop());
    openShareBtn.target = '_blank';
    openShareBtn.className = 'file-link';
    openShareBtn.innerHTML = '&#128279; Abrir ultimo Share HTML';
    btnContainer.appendChild(openShareBtn);
  }

  if (jsonFile) {
    const openJsonBtn = document.createElement('a');
    openJsonBtn.href = '/api/latest-report';
    openJsonBtn.target = '_blank';
    openJsonBtn.className = 'file-link';
    openJsonBtn.innerHTML = '&#123;&#125; Abrir ultimo JSON';
    btnContainer.appendChild(openJsonBtn);

    const copyJsonBtn = document.createElement('button');
    copyJsonBtn.type = 'button';
    copyJsonBtn.className = 'file-link';
    copyJsonBtn.style.cursor = 'pointer';
    copyJsonBtn.style.fontFamily = 'inherit';
    copyJsonBtn.innerHTML = '&#128203; Copiar URL del ultimo JSON';
    copyJsonBtn.addEventListener('click', () => copyLatestReportUrl(copyJsonBtn));
    btnContainer.appendChild(copyJsonBtn);
  }

  fileLinks.appendChild(btnContainer);
  fileLinks.classList.remove('hidden');
}

// ── Watchlist ──
function renderWatchlist(items) {
  const el = document.getElementById('wl-list');
  if (!items.length) { el.innerHTML = '<div style="color:var(--text2);font-size:.85rem">Watchlist vacia</div>'; return; }
  el.innerHTML = '<div style="font-size:.85rem;color:var(--text2);margin-bottom:.3rem">' + items.length + ' juegos en watchlist</div>' +
    items.map(w => '<div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0;border-bottom:1px solid var(--card-border)">' +
      '<span style="flex:1;font-size:.85rem">' + w.name + ' <span style="color:var(--text2)">(AppID ' + w.appid + ')</span></span>' +
      '<span style="font-size:.85rem;color:var(--accent)">$' + w.target_price + '</span>' +
      '<button onclick="removeWatchlist(\'' + w.appid + '\')" style="background:none;border:none;color:var(--red);cursor:pointer;font-size:1rem">&times;</button>' +
    '</div>').join('');
}
async function loadWatchlist() {
  try { const r = await fetch('/api/watchlist'); renderWatchlist(await r.json()); } catch(e) {}
}
async function addWatchlist() {
  const appid = document.getElementById('wl-appid').value.trim();
  const name = document.getElementById('wl-name').value.trim() || appid;
  const price = parseFloat(document.getElementById('wl-price').value);
  if (!appid || !price) return;
  try {
    const r = await fetch('/api/watchlist', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({appid, name, target_price:price})});
    const d = await r.json(); renderWatchlist(d.items);
    document.getElementById('wl-appid').value = '';
    document.getElementById('wl-name').value = '';
    document.getElementById('wl-price').value = '';
  } catch(e) {}
}
async function removeWatchlist(appid) {
  try {
    const r = await fetch('/api/watchlist/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({appid})});
    const d = await r.json(); renderWatchlist(d.items);
  } catch(e) {}
}

let currentShareData = null;
let currentSteamUrl = '';

function encodeSharePayload(data) {
  const json = JSON.stringify(data || {});
  try {
    return btoa(unescape(encodeURIComponent(json)));
  } catch (e) {
    try {
      return btoa(json);
    } catch (e2) {
      return '';
    }
  }
}

function copyTextWithFallback(text) {
  if (!text) return Promise.reject(new Error('empty-text'));
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      const ok = document.execCommand('copy');
      textarea.remove();
      if (ok) resolve();
      else reject(new Error('copy-failed'));
    } catch (err) {
      textarea.remove();
      reject(err);
    }
  });
}

function flashShareButton(button, successLabel, defaultLabel) {
  if (!button) return;
  button.textContent = successLabel;
  setTimeout(() => {
    button.textContent = defaultLabel;
  }, 2000);
}

function openShareModal(game) {
  const name = game.name || game.steam_name || 'Unknown';
  const price = game.price || 0;
  const original = game.price_original || price;
  const discount = game.discount || 0;
  const minHist = game.min_hist || game.min_historical || null;
  const appid = game.appid;
  
  currentShareData = {
    name: name,
    appid: appid,
    price: price,
    price_original: original,
    original_price: original,
    discount: discount,
    min_hist: minHist,
    url: 'https://store.steampowered.com/app/' + appid + '/'
  };
  
  currentSteamUrl = 'https://store.steampowered.com/app/' + appid + '/';
  
  document.getElementById('share-name').textContent = name;
  document.getElementById('share-price').innerHTML = (original > price ? `<span>$${original} MXN </span>` : '') + `$${price} MXN (${discount}% OFF)`;
  document.getElementById('share-minhist').innerHTML = minHist ? `Minimo historico: <span>$${minHist} MXN</span>` : '';
  
  document.getElementById('share-modal').classList.add('active');
}

function closeShareModal() {
  document.getElementById('share-modal').classList.remove('active');
  currentShareData = null;
}

function copyShareLink() {
  if (!currentShareData) return;
  const encoded = encodeSharePayload(currentShareData);
  if (!encoded) {
    appendLine('No se pudo generar link para compartir.', 'err');
    return;
  }
  const shareUrl = 'steamtools://share?data=' + encoded;
  copyTextWithFallback(shareUrl).then(() => {
    const btn = document.getElementById('btn-copy-app');
    flashShareButton(btn, '¡Copiado!', 'Copiar link steamtools://');
  }).catch(() => {
    window.prompt('Copia este link:', shareUrl);
  });
}

function copySteamLink() {
  if (!currentSteamUrl) return;
  copyTextWithFallback(currentSteamUrl).then(() => {
    const btn = document.querySelector('.share-btn-copy-steam');
    flashShareButton(btn, '¡Copiado!', 'Copiar link de Steam');
  }).catch(() => {
    window.prompt('Copia este link de Steam:', currentSteamUrl);
  });
}

function openInSteam() {
  if (currentSteamUrl) {
    window.open(currentSteamUrl, '_blank');
  }
}

loadWatchlist();
syncLatestReportEmptyState();
syncLatestReportCard();
</script>
</body>
</html>"""


# ─── HTTP Handler ────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    output_dir = str(DEFAULT_OUTPUT_DIR)
    max_json_body_bytes = 64 * 1024

    def log_message(self, format, *args):
        pass  # Silenciar logs del server

    def end_headers(self):
        path = urllib.parse.urlparse(getattr(self, "path", "")).path
        if path in {"/", "/app.js", "/app.css"}:
            self.send_header(
                "Cache-Control",
                "no-store, no-cache, must-revalidate, max-age=0",
            )
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def _send_json(self, data, status=200):
        send_json(self, data, status=status)

    def _send_html(self, html, status=200):
        send_html(self, html, status=status)

    def _read_json_body(self) -> dict | None:
        return read_json_body(self, max_json_body_bytes=self.max_json_body_bytes)

    # ── GET routes ──

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send_html(load_steam_deals_html())
        elif path == "/app.css":
            serve_text_asset(self, STEAM_DEALS_CSS_FILE, CSS_CONTENT_TYPE)
        elif path == "/app.js":
            serve_text_asset(self, STEAM_DEALS_JS_FILE, JS_CONTENT_TYPE)
        elif path == "/api/config":
            self._send_json(
                {
                    **load_config(),
                    "default_output_dir": str(DEFAULT_OUTPUT_DIR),
                    "default_output_label": output_folder_display_name(DEFAULT_OUTPUT_DIR),
                }
            )
        elif path == "/api/ui-state":
            self._send_json(
                {
                    "has_cache": has_local_cache(),
                    "has_config": bool(load_config().get("vanity")),
                }
            )
        elif path == "/api/watchlist":
            self._send_json(load_watchlist())
        elif path == "/api/files":
            self._serve_files_list()
        elif path == "/api/latest-report":
            self._serve_latest_report()
        elif path == "/api/history/runs":
            self._serve_history_runs()
        elif path == "/api/history/compare":
            self._serve_history_compare()
        elif path.startswith("/files/"):
            self._serve_file(path[7:])
        else:
            self.send_error(404)

    # ── POST routes ──

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/run":
            self._serve_run_sse()
        elif path == "/api/run-pd2":
            self._serve_run_sse(pd2=True)
        elif path == "/api/preflight":
            self._serve_preflight()
        elif path == "/api/desktop-doctor":
            self._serve_desktop_doctor()
        elif path == "/api/desktop-doctor/fix":
            self._serve_desktop_doctor_fix()
        elif path == "/api/cache/clear":
            self._serve_clear_cache()
        elif path == "/api/stop":
            self._serve_stop()
        elif path == "/api/open-output-folder":
            self._serve_open_output_folder()
        elif path == "/api/config":
            self._serve_config_save()
        elif path == "/api/watchlist":
            self._serve_watchlist_add()
        elif path == "/api/watchlist/delete":
            self._serve_watchlist_delete()
        elif path == "/api/log/export":
            self._serve_log_export()
        else:
            self.send_error(404)

    # ── Config save ──

    def _serve_config_save(self):
        body = self._read_json_body()
        if body is None:
            return
        cfg = load_config()
        cfg.update(body)
        save_config(cfg)
        self._send_json({"status": "saved"})

    def _serve_preflight(self):
        body = self._read_json_body()
        if body is None:
            return
        config = body.get("config", {}) or {}
        if not isinstance(config, dict):
            self._send_json(
                {"error": "invalid_payload", "message": "config debe ser objeto."},
                status=400,
            )
            return
        issues = []
        warnings = []

        vanity = (config.get("vanity") or "").strip()
        if not vanity:
            issues.append(
                "Falta el perfil de Steam (vanity, Steam ID o URL de perfil)."
            )

        hltb = (config.get("hltb") or "").strip()
        if hltb and not Path(hltb).expanduser().exists():
            issues.append(f"No se encontró HLTB CSV: {hltb}")

        family_json = (config.get("family_json") or "").strip()
        if family_json and not Path(family_json).expanduser().exists():
            issues.append(f"No se encontró Family JSON: {family_json}")

        output_dir = resolve_output_dir(config.get("output"))
        if not output_dir.exists():
            warnings.append(
                f"La carpeta de salida se creará al generar: {output_folder_display_name(output_dir)}"
            )
        elif not output_dir.is_dir():
            issues.append(
                f"La ruta de salida no es una carpeta: {output_folder_display_name(output_dir)}"
            )

        if not (config.get("key") or "").strip():
            warnings.append(
                "Sin Steam API Key: se usará modo público (wishlist debe ser pública)."
            )

        self._send_json(
            {
                "ok": len(issues) == 0,
                "issues": issues,
                "warnings": warnings,
                "output_dir": str(output_dir),
                "output_label": output_folder_display_name(output_dir),
            }
        )

    def _serve_open_output_folder(self):
        body = self._read_json_body()
        if body is None:
            return
        config = body.get("config", {}) or {}
        if not isinstance(config, dict):
            self._send_json(
                {"error": "invalid_payload", "message": "config debe ser objeto."},
                status=400,
            )
            return

        output_dir = resolve_output_dir(config.get("output"))
        try:
            opened_dir = open_output_folder(output_dir)
        except Exception as e:
            self._send_json(
                {
                    "error": "open_output_folder_failed",
                    "message": f"No se pudo abrir la carpeta de salida: {e}",
                    "output_dir": str(output_dir),
                    "output_label": output_folder_display_name(output_dir),
                },
                status=500,
            )
            return

        Handler.output_dir = str(opened_dir)
        self._send_json(
            {
                "status": "opened",
                "path": str(opened_dir),
                "label": output_folder_display_name(opened_dir),
            }
        )

    def _serve_desktop_doctor(self):
        try:
            self._send_json(build_desktop_doctor_report())
        except Exception as e:
            self._send_json(
                {
                    "error": "desktop_doctor_failed",
                    "message": f"No se pudo ejecutar Desktop Doctor: {e}",
                },
                status=500,
            )

    def _serve_desktop_doctor_fix(self):
        body = self._read_json_body()
        if body is None:
            return
        if not isinstance(body, dict) or body.get("confirm") is not True:
            self._send_json(
                {
                    "error": "confirmation_required",
                    "message": "Desktop autofix requiere `confirm: true`.",
                },
                status=400,
            )
            return
        try:
            result = apply_desktop_doctor_fixes(confirm=True, emit=lambda _line: None)
            status_code = 500 if result.get("status") == "failed" else 200
            self._send_json(result, status=status_code)
        except Exception as e:
            self._send_json(
                {
                    "error": "desktop_doctor_fix_failed",
                    "message": f"No se pudo ejecutar Desktop Autofix: {e}",
                },
                status=500,
            )

    def _serve_clear_cache(self):
        removed = 0
        if LOCAL_CACHE_DIR.exists():
            for p in LOCAL_CACHE_DIR.rglob("*"):
                try:
                    if p.is_file():
                        p.unlink()
                        removed += 1
                except OSError:
                    pass
        self._send_json({"status": "ok", "removed": removed})

    # ── Watchlist CRUD ──

    def _serve_watchlist_add(self):
        body = self._read_json_body()
        if body is None:
            return
        appid = str(body.get("appid", "")).strip()
        target = body.get("target_price")
        name = str(body.get("name", appid)).strip() or appid
        if not appid or target is None:
            self._send_json({"error": "appid and target_price required"}, status=400)
            return
        try:
            target_value = float(target)
        except (TypeError, ValueError):
            self._send_json(
                {
                    "error": "invalid_target_price",
                    "message": "target_price debe ser numerico.",
                },
                status=400,
            )
            return
        if target_value < 0:
            self._send_json(
                {
                    "error": "invalid_target_price",
                    "message": "target_price debe ser >= 0.",
                },
                status=400,
            )
            return
        items = add_watchlist_item(load_watchlist(), appid, target_value, name)
        save_watchlist(items)
        self._send_json({"status": "added", "items": items})

    def _serve_watchlist_delete(self):
        body = self._read_json_body()
        if body is None:
            return
        appid = str(body.get("appid", "")).strip()
        if not appid:
            self._send_json({"error": "appid required"}, status=400)
            return
        items, _removed = remove_watchlist_item(load_watchlist(), appid)
        save_watchlist(items)
        self._send_json({"status": "deleted", "items": items})

    def _serve_log_export(self):
        body = self._read_json_body()
        if body is None:
            return
        text = str(body.get("text", ""))
        filename = str(body.get("filename", "")).strip() or None
        if not text.strip():
            self._send_json(
                {
                    "error": "empty_log",
                    "message": "No hay contenido de log para exportar.",
                },
                status=400,
            )
            return
        try:
            saved_path = save_execution_log_text(text, filename=filename)
        except Exception as e:
            self._send_json(
                {
                    "error": "log_export_failed",
                    "message": f"No se pudo guardar el log: {e}",
                },
                status=500,
            )
            return
        self._send_json(
            {
                "status": "saved",
                "path": str(saved_path),
                "name": saved_path.name,
            }
        )

    # ── Serve generated files ──

    def _serve_files_list(self):
        out_dir = Path(Handler.output_dir)
        files = []
        for ext in ("*.md", "*.html", "*.csv", "*.json"):
            for f in out_dir.glob(f"Steam Deals*{ext[1:]}"):
                files.append(
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "mtime": f.stat().st_mtime,
                    }
                )
        files.sort(key=lambda x: -x["mtime"])
        self._send_json(files[:20])

    def _serve_latest_report(self):
        latest_report = find_latest_artifact(Handler.output_dir, "Steam Deals*.json")
        if latest_report is None:
            self._send_json(
                {
                    "error": "latest_report_not_found",
                    "message": "No se encontró ningún reporte JSON generado.",
                },
                status=404,
            )
            return
        self._serve_file(latest_report.name)

    def _serve_history_runs(self):
        max_runs = 50
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "limit" in query:
                max_runs = max(1, min(100, int(query["limit"][0])))
        except Exception:
            max_runs = 50
        self._send_json({"runs": list_history_runs(HISTORY_DIR, max_runs=max_runs)})

    def _serve_history_compare(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        left = (query.get("left") or [""])[0]
        right = (query.get("right") or [""])[0]
        include_same_raw = (query.get("include_same") or ["false"])[0].lower()
        include_same = include_same_raw in {"1", "true", "yes", "on"}
        status_filter = (query.get("status") or ["all"])[0].lower()
        if status_filter not in {"all", "changed", "new", "removed", "same"}:
            status_filter = "all"
        sort_delta = (query.get("sort_delta") or ["default"])[0].lower()
        if sort_delta not in {"default", "delta_desc", "delta_asc", "abs_desc"}:
            sort_delta = "default"

        if not left or not right:
            self._send_json(
                {"error": "invalid_params", "message": "left y right son requeridos."},
                status=400,
            )
            return

        comparison = compare_history_runs(
            history_dir=HISTORY_DIR,
            left_run_id=left,
            right_run_id=right,
            include_same=include_same,
            status_filter=status_filter,
            sort_delta=sort_delta,
        )
        if comparison is None:
            self._send_json(
                {
                    "error": "comparison_not_available",
                    "message": "No se pudieron cargar los runs solicitados.",
                },
                status=404,
            )
            return

        self._send_json(comparison)

    def _serve_file(self, encoded_name: str):
        name = urllib.parse.unquote(encoded_name)
        if not is_safe_generated_file_name(name):
            send_generated_file_error(
                self,
                403,
                "Archivo no disponible",
                "Por seguridad solo se pueden abrir archivos generados por nombre. Vuelve al panel y usa los enlaces del último run.",
            )
            return
        fpath = Path(Handler.output_dir) / name
        if not fpath.exists():
            send_generated_file_error(
                self,
                404,
                "Archivo no encontrado",
                "El archivo generado ya no está disponible en la carpeta de salida. Ejecuta de nuevo el reporte o revisa la ruta configurada.",
            )
            return
        ct = generated_file_content_type(fpath.suffix)
        try:
            data = fpath.read_bytes()
        except OSError:
            send_generated_file_error(
                self,
                500,
                "No se pudo leer el archivo",
                "El archivo existe, pero no se pudo leer en este momento. Reintenta o vuelve a generar el reporte.",
            )
            return
        self.send_response(200)
        self.send_header("Content-Type", f"{ct}; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            generated_file_content_disposition(fpath.name, fpath.suffix),
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── Run (SSE stream) ──

    def _serve_run_sse(self, pd2: bool = False):
        global _running_proc

        def clear_running_proc() -> None:
            global _running_proc
            with _proc_lock:
                _running_proc = None

        with _proc_lock:
            if _running_proc and _running_proc.poll() is None:
                self._send_json({"error": "Already running"}, status=409)
                return

        body = self._read_json_body()
        if body is None:
            return
        config = body.get("config", {})
        filters = body.get("filters", {})
        if not isinstance(config, dict):
            self._send_json(
                {"error": "invalid_payload", "message": "config debe ser objeto."},
                status=400,
            )
            return
        if not isinstance(filters, dict):
            self._send_json(
                {"error": "invalid_payload", "message": "filters debe ser objeto."},
                status=400,
            )
            return

        # Save config for future sessions
        save_cfg = {}
        for k in ("vanity", "key", "hltb", "family_json", "itad_key"):
            if config.get(k):
                save_cfg[k] = config[k]
        if config.get("output"):
            save_cfg["output_dir"] = config["output"]
        if not pd2:
            if config.get("discount") is not None:
                save_cfg["discount"] = config["discount"]
            if config.get("genres"):
                g = config["genres"]
                if isinstance(g, str):
                    g = [x.strip() for x in g.split(",") if x.strip()]
                save_cfg["genres"] = g
        try:
            save_config({**load_config(), **save_cfg})
        except Exception:
            pass

        # Update output_dir for file serving
        Handler.output_dir = str(resolve_output_dir(config.get("output")))

        cmd = (
            build_pd2_command(config, filters)
            if pd2
            else build_command(config, filters)
        )

        try:
            proc = start_text_subprocess(cmd)
        except Exception as e:
            self._send_json({"error": f"No se pudo iniciar proceso: {e}"}, status=500)
            return

        with _proc_lock:
            _running_proc = proc

        generated_files = []

        def handle_process_line(raw_line: str, emit_sse):
            raw_text = raw_line.strip()
            if raw_text.startswith(EVENT_PREFIX):
                try:
                    event = json.loads(raw_text[len(EVENT_PREFIX) :])
                    if event.get("type") == "file" and event.get("path"):
                        generated_files.append(event["path"])
                    elif event.get("type") == "progress":
                        emit_sse(
                            {
                                "type": "progress",
                                "current": event.get("current", 0),
                                "total": event.get("total", 0),
                                "label": event.get("label", ""),
                            }
                        )
                    return
                except Exception:
                    pass

            text, cls = classify_line(raw_line)
            if not text and not raw_line.strip():
                return

            prog = extract_progress(text)
            if prog:
                emit_sse(
                    {
                        "type": "progress",
                        "current": prog[0],
                        "total": prog[1],
                        "label": prog[2],
                    }
                )

            fpath = detect_file_path(text)
            if fpath:
                generated_files.append(fpath)

            emit_sse({"type": "line", "text": text, "cls": cls})

        def handle_process_done(done_proc, emit_sse):
            clear_running_proc()
            emit_sse(
                {
                    "type": "done",
                    "exit_code": done_proc.returncode,
                    "files": generated_files,
                }
            )

        try:
            stream_process_as_sse(self, proc, handle_process_line, handle_process_done)
        except ProcessStreamUnavailable:
            clear_running_proc()
            self._send_json({"error": "No se pudo leer salida del proceso"}, status=500)
        finally:
            clear_running_proc()

    # ── Stop ──

    def _serve_stop(self):
        global _running_proc
        with _proc_lock:
            proc = _running_proc
            if proc is None:
                self._send_json(
                    _build_stop_response(
                        "not_running", "No había una ejecución activa para detener."
                    )
                )
                return

            if proc.poll() is not None:
                _running_proc = None
                self._send_json(
                    _build_stop_response(
                        "not_running", "La ejecución ya había terminado."
                    )
                )
                return

            stop_process(proc)
            if proc.poll() is None:
                self._send_json(
                    _build_stop_response(
                        "stop_timeout",
                        "Se intentó detener la ejecución, pero el proceso sigue activo.",
                    ),
                    status=500,
                )
                return

            _running_proc = None
            self._send_json(
                _build_stop_response(
                    "stopped", "La ejecución se detuvo correctamente."
                )
            )


# ─── Main ────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Steam Deals Web UI")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Puerto inicial a intentar"
    )
    parser.add_argument(
        "--no-open", action="store_true", help="No abrir navegador automáticamente"
    )
    args = parser.parse_args()

    port = args.port
    server = None
    for p in range(port, port + 10):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            continue

    if not server:
        print(
            f"Error: no se pudo abrir ningún puerto ({DEFAULT_PORT}-{DEFAULT_PORT + 9})"
        )
        sys.exit(1)

    url = f"http://127.0.0.1:{port}"
    print(f"\n  \033[36mSteam Deals Web UI\033[0m")
    print(f"  \033[1m{url}\033[0m")
    print(f"  Ctrl+C para cerrar\n")

    if not args.no_open:
        threading.Timer(0.5, webbrowser.open, args=[url]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        with _proc_lock:
            if _running_proc and _running_proc.poll() is None:
                stop_process(_running_proc)
        server.server_close()
        print("\n  Cerrado.")


if __name__ == "__main__":
    main()
