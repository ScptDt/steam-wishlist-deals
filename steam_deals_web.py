#!/usr/bin/env python3
"""
Steam Deals Web UI — Interfaz web para steam_deals_generator.py
Ejecuta: python3 steam_deals_web.py
Abre: http://127.0.0.1:8080
"""

import html
import hmac
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Iterable
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
from steam_deals_paths import (
    build_persistent_runtime_env,
    resolve_cache_dir,
    resolve_logs_dir,
    resolve_reports_output_dir,
)
from desktop_doctor import apply_desktop_doctor_fixes, build_desktop_doctor_report
from app.steam_deals_history_dashboard import compare_history_runs, list_history_runs
from app.steam_deals_openid import (
    STEAM_OPENID_ENDPOINT,
    build_steam_openid_start_response,
    consume_steam_openid_callback,
    is_steam_openid_check_authentication_valid,
    public_steam_openid_profile,
    steam_openid_base_url,
    verify_steam_openid_check_authentication,
)
from app.steam_deals_access import validate_steam_access_direct_import
from app.steam_deals_recommendations import build_selection_review
from shared.tool_modules import PAYDAY2_TOOL_ID, get_tool_entrypoint

from shared_web_infra import (
    build_steam_access_import_session_record,
    build_steam_access_pairing_record,
    build_missing_assets_html,
    build_secret_subprocess_env,
    CONFIG_SECRET_ENV_VARS,
    config_without_secrets,
    create_local_session_token,
    CSS_CONTENT_TYPE,
    hydrate_config_secrets,
    has_steam_access_cookie_auth,
    is_steam_access_body_within_limit,
    is_steam_access_direct_import_confirmed,
    is_steam_access_json_content_type,
    is_steam_access_pairing_active,
    is_steam_access_rate_limited,
    is_valid_local_anti_csrf_request,
    is_valid_loopback_host_header,
    is_redacted_config_secret,
    is_valid_steam_access_extension_origin,
    is_valid_steam_access_preflight,
    JS_CONTENT_TYPE,
    load_html_with_fallback,
    local_anti_csrf_forbidden_payload,
    local_host_forbidden_payload,
    LOCAL_CSRF_HEADER,
    merge_config_preserving_secrets,
    normalize_steam_access_extension_origin,
    ProcessStreamUnavailable,
    public_config,
    read_json_body,
    redact_sensitive_text,
    safe_public_error_payload,
    send_html,
    send_json,
    send_sse_event,
    serve_text_asset,
    start_text_subprocess,
    steam_access_local_import_contract,
    steam_access_local_status_payload,
    steam_access_timestamp_iso,
    steam_access_auth_required_payload,
    steam_access_bearer_token,
    steam_access_content_length,
    steam_access_cookie_auth_forbidden_payload,
    steam_access_cors_forbidden_payload,
    steam_access_cors_headers,
    steam_access_import_session_for_token,
    steam_access_method_not_allowed_payload,
    steam_access_origin_forbidden_payload,
    steam_access_pairing_required_payload,
    steam_access_pairing_token,
    steam_access_rate_limited_payload,
    STEAM_ACCESS_LOCAL_IMPORT_ROUTE,
    STEAM_ACCESS_LOCAL_IMPORT_MAX_BODY_BYTES,
    STEAM_ACCESS_LOCAL_IMPORT_RATE_LIMIT,
    STEAM_ACCESS_LOCAL_IMPORT_SESSION_TOKEN_BYTES,
    STEAM_ACCESS_LOCAL_IMPORT_SECURITY_INVARIANTS,
    STEAM_ACCESS_LOCAL_PAIRING_TOKEN_BYTES,
    STEAM_ACCESS_LOCAL_PAIRING_TTL_SECONDS,
    STEAM_ACCESS_LOCAL_PAIR_ROUTE,
    STEAM_ACCESS_LOCAL_PAIR_STATUS_ROUTE,
    stop_process,
    stream_process_as_sse,
)

PROJECT_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = PROJECT_DIR / "steam_deals_generator.py"
PD2_ENTRYPOINT = get_tool_entrypoint(PAYDAY2_TOOL_ID)
PD2_SCRIPT_PATH = PROJECT_DIR / PD2_ENTRYPOINT
CONFIG_FILE = Path.home() / ".config" / "steam_deals.json"
DEFAULT_PORT = 8080
WEB_DIR = PROJECT_DIR / "web" / "steam_deals"
STEAM_DEALS_HTML_FILE = WEB_DIR / "index.html"
STEAM_DEALS_CSS_FILE = WEB_DIR / "app.css"
STEAM_DEALS_JS_FILE = WEB_DIR / "app.js"
STEAM_DEALS_MISSING_ASSETS_HTML = build_missing_assets_html(
    "Steam Tools",
    "web/steam_deals/index.html + app.css + app.js",
)
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output"
HLTB_AUTODETECT_PATTERN = "HLTB*.csv"
HLTB_AUTODETECT_RELATIVE_DIRS = (
    Path("Documents") / "SteamTools" / "imports",
    Path("Documents"),
    Path("Downloads"),
)
LOCAL_SESSION_TOKEN = create_local_session_token()
STEAM_ACCESS_LOCAL_ENDPOINT_CONTRACT = steam_access_local_import_contract()
STEAM_ACCESS_LOCAL_ENDPOINT_ROUTES = frozenset(
    {
        STEAM_ACCESS_LOCAL_PAIR_ROUTE,
        STEAM_ACCESS_LOCAL_PAIR_STATUS_ROUTE,
        STEAM_ACCESS_LOCAL_IMPORT_ROUTE,
    }
)
STEAM_ACCESS_LOCAL_ENDPOINT_SECURITY_INVARIANTS = STEAM_ACCESS_LOCAL_IMPORT_SECURITY_INVARIANTS
STEAM_ACCESS_PAIRING_START_PATH = "/api/steam-access/pairing/start"
STEAM_ACCESS_PAIRING_REVOKE_PATH = "/api/steam-access/pairing/revoke"
STEAM_ACCESS_PAIRING_TTL_SECONDS = STEAM_ACCESS_LOCAL_PAIRING_TTL_SECONDS
STEAM_ACCESS_DIRECT_IMPORT_MAX_BODY_BYTES = STEAM_ACCESS_LOCAL_IMPORT_MAX_BODY_BYTES
STEAM_ACCESS_DIRECT_IMPORT_RATE_LIMIT = STEAM_ACCESS_LOCAL_IMPORT_RATE_LIMIT
PROTECTED_POST_PATHS = frozenset(
    {
        "/api/run",
        "/api/run-pd2",
        "/api/preflight",
        "/api/desktop-doctor",
        "/api/desktop-doctor/fix",
        "/api/cache/clear",
        "/api/stop",
        "/api/open-output-folder",
        "/api/config",
        "/api/steam-openid/start",
        "/api/steam-openid/disconnect",
        STEAM_ACCESS_PAIRING_START_PATH,
        STEAM_ACCESS_PAIRING_REVOKE_PATH,
        "/api/watchlist",
        "/api/watchlist/delete",
        "/api/selection-review",
        "/api/log/export",
    }
)

_running_proc = None
_proc_lock = threading.Lock()
_steam_openid_pending_states: dict[str, dict] = {}
_steam_openid_used_nonces: dict[str, float] = {}
_steam_access_pairings: dict[str, dict] = {}
_steam_access_import_sessions: dict[str, dict] = {}


def _now_seconds() -> float:
    return time.time()


def _same_local_token(left: str, right: str) -> bool:
    try:
        return hmac.compare_digest(str(left), str(right))
    except TypeError:
        return False


def _prune_steam_access_direct_import_state() -> None:
    now = _now_seconds()
    for token, pending in list(_steam_access_pairings.items()):
        expires_at = pending.get("expires_at", 0)
        if expires_at <= now or pending.get("used"):
            _steam_access_pairings.pop(token, None)
    for token, session in list(_steam_access_import_sessions.items()):
        expires_at = session.get("expires_at", 0)
        if expires_at <= now or session.get("revoked"):
            _steam_access_import_sessions.pop(token, None)


def reset_steam_access_direct_import_state_for_tests() -> None:
    _steam_access_pairings.clear()
    _steam_access_import_sessions.clear()


def revoke_steam_access_direct_import_sessions_for_tests() -> None:
    for session in _steam_access_import_sessions.values():
        session["revoked"] = True


def _build_stop_response(status: str, message: str) -> dict[str, str]:
    return {"status": status, "message": message}

LOCAL_CACHE_DIR = resolve_cache_dir(
    PROJECT_DIR,
    frozen=getattr(sys, "frozen", False),
)
DEFAULT_ITAD_EXTERNAL_OFFERS_CACHE_FILE = "itad-external-offers.json"
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
GENERATED_HTML_CSP = (
    "sandbox allow-scripts allow-popups allow-downloads; "
    "default-src 'none'; "
    "script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; "
    "img-src https: data:; "
    "connect-src 'none'; "
    "form-action 'none'; "
    "base-uri 'none'; "
    "object-src 'none'; "
    "frame-ancestors 'none'"
)
PAYDAY2_GENERATED_FILES = frozenset(
    {
        "PAYDAY2_Plan_de_Compra.html",
        "PAYDAY2_Plan_de_Compra.md",
        "PAYDAY2_Plan_de_Compra.csv",
    }
)
STEAM_DEALS_PRIMARY_ARTIFACT_RE = re.compile(
    r"^Steam Deals(?: [A-Z0-9][^<>:\"/\\|?*]*?)? \d{4}-\d{2}-\d{2}\.(?:html|md|json|csv)$"
)
STEAM_DEALS_SHARE_ARTIFACT_RE = re.compile(
    r"^Steam Deals Share \d{4}-\d{2}-\d{2}\.html$"
)
STEAM_DEALS_JSON_EXPORT_ARTIFACT_RE = re.compile(
    r"^Steam Deals (?:Offers|Wishlist) (\d{4}-\d{2}-\d{2})\.json$"
)


def _safe_content_disposition_filename(name: str) -> str:
    return re.sub(r'[\r\n"]+', "_", name)


def generated_file_content_disposition(name: str, suffix: str) -> str:
    disposition = "inline" if suffix.lower() == ".html" else "attachment"
    safe_name = _safe_content_disposition_filename(name)
    encoded_name = urllib.parse.quote(name)
    return f"{disposition}; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}"


def generated_file_content_type(suffix: str) -> str:
    return GENERATED_FILE_CONTENT_TYPES.get(suffix.lower(), "application/octet-stream")


def generated_html_security_headers(suffix: str) -> dict[str, str]:
    if suffix.lower() != ".html":
        return {}
    return {
        "Content-Security-Policy": GENERATED_HTML_CSP,
        "Referrer-Policy": "no-referrer",
    }


def resolve_output_dir(
    value: str | None,
    *,
    env: dict[str, str] | None = None,
    frozen: bool | None = None,
    project_dir: Path = PROJECT_DIR,
) -> Path:
    raw = str(value or "").strip()
    if not raw:
        return resolve_reports_output_dir(
            project_dir,
            env=env,
            frozen=getattr(sys, "frozen", False) if frozen is None else frozen,
        )
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project_dir / path
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


def is_expected_generated_artifact_name(name: str) -> bool:
    if not is_safe_generated_file_name(name):
        return False

    suffix = Path(name).suffix.lower()
    if suffix not in GENERATED_FILE_CONTENT_TYPES:
        return False
    if name.startswith(("Steam Deals Offers ", "Steam Deals Wishlist ")):
        return bool(STEAM_DEALS_JSON_EXPORT_ARTIFACT_RE.match(name))
    if name.startswith("Steam Deals Share "):
        return bool(STEAM_DEALS_SHARE_ARTIFACT_RE.match(name))
    if name.startswith("Steam Deals "):
        return bool(STEAM_DEALS_PRIMARY_ARTIFACT_RE.match(name))
    return name in PAYDAY2_GENERATED_FILES


def public_generated_file_name(path_value: str) -> str:
    raw = str(path_value or "").strip().strip('"')
    name = re.split(r"[\\/]", raw)[-1]
    if is_expected_generated_artifact_name(name):
        return name
    return redact_sensitive_text(raw)


def _appid_from_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    app_match = re.search(r"(?:store\.steampowered\.com/app/|\bapp/)(\d{1,12})", text)
    if app_match:
        return app_match.group(1)
    plain_match = re.search(r"(?<!\d)(\d{1,12})(?!\d)", text)
    return plain_match.group(1) if plain_match else ""


def _selection_review_records_from_text(text: str, *, limit: int) -> list[dict]:
    records: list[dict] = []
    seen_appids: set[str] = set()
    for line in str(text or "").splitlines():
        appid = _appid_from_text(line)
        if not appid or appid in seen_appids:
            continue
        seen_appids.add(appid)
        records.append({"appid": appid})
        if len(records) >= limit:
            break
    return records


def _selection_review_records(selection, *, limit: int = 50) -> list[dict]:
    if isinstance(selection, str):
        return _selection_review_records_from_text(selection, limit=limit)
    if isinstance(selection, dict):
        raw_records = selection.get("items") if isinstance(selection.get("items"), list) else [selection]
    elif isinstance(selection, list):
        raw_records = selection
    elif selection is None:
        raw_records = []
    else:
        raw_records = [selection]

    records: list[dict] = []
    for raw in raw_records:
        if len(records) >= limit:
            break
        if isinstance(raw, dict):
            appid = _appid_from_text(raw.get("appid") or raw.get("steam_appid"))
            name = str(raw.get("name") or raw.get("steam_name") or "").strip()[:160]
        else:
            appid = _appid_from_text(raw)
            name = ""
        if not appid and not name:
            records.append({})
            continue
        record = {"appid": appid}
        if name:
            record["name"] = name
        records.append(record)
    return records


def selection_review_records_from_body(body: dict, *, limit: int = 50) -> list[dict]:
    for key in ("selection", "items", "appids", "text"):
        if key in body:
            return _selection_review_records(body.get(key), limit=limit)
    return []


def _first_non_empty_report_value(report: dict, keys: tuple[str, ...], allowed_types: tuple[type, ...], default=None):
    for key in keys:
        value = report.get(key)
        if isinstance(value, allowed_types) and value:
            return value
    return default


def _nested_report_value(report: dict, parent_keys: tuple[str, ...], keys: tuple[str, ...], allowed_types: tuple[type, ...], default=None):
    for parent_key in parent_keys:
        parent = report.get(parent_key)
        if isinstance(parent, dict):
            value = _first_non_empty_report_value(parent, keys, allowed_types)
            if value:
                return value
    return default


def _personalized_recommendations_from_report(report: dict):
    recommendations = report.get("personalized_recommendations")
    if isinstance(recommendations, dict):
        return recommendations if recommendations.get("items") else None
    if isinstance(recommendations, list):
        return recommendations or None
    return None


def selection_review_context_from_report(report: dict) -> dict:
    have_on_sale = _first_non_empty_report_value(report, ("have_on_sale",), (list,), default=[])
    liked_appids = _first_non_empty_report_value(report, ("liked_appids", "liked"), (list, dict))
    if liked_appids is None:
        liked_appids = _nested_report_value(
            report,
            ("preferences", "user_preferences"),
            ("liked_appids", "liked"),
            (list, dict),
            default=[],
        )
    preference_relations = _first_non_empty_report_value(
        report,
        ("preference_relations", "relationships"),
        (dict,),
    )
    if preference_relations is None:
        preference_relations = _nested_report_value(
            report,
            ("preferences", "user_preferences"),
            ("preference_relations", "relationships", "relations"),
            (dict,),
            default={},
        )
    return {
        "deals": _first_non_empty_report_value(report, ("deals",), (list,), default=[]),
        "top_picks": _first_non_empty_report_value(report, ("top_picks",), (list,), default=[]),
        "personalized_recommendations": _personalized_recommendations_from_report(report),
        "recommended_collections": _first_non_empty_report_value(report, ("recommended_collections",), (list,), default=[]),
        "activity_games": _first_non_empty_report_value(
            report,
            ("activity_games", "recent_activity", "recently_played"),
            (list, dict),
            default=[],
        ),
        "library_games": _first_non_empty_report_value(
            report,
            ("library_games", "library", "owned_games"),
            (list, dict),
            default=have_on_sale,
        ),
        "owned": _first_non_empty_report_value(
            report,
            ("owned", "owned_appids"),
            (list, dict),
            default=have_on_sale,
        ),
        "family_appids": _first_non_empty_report_value(report, ("family_appids", "family"), (list, dict), default=[]),
        "liked_appids": liked_appids or [],
        "preference_relations": preference_relations or {},
        "hltb_hours": _first_non_empty_report_value(report, ("hltb_hours", "hltb"), (dict,), default={}),
    }


def load_latest_report_payload(output_dir: str | Path) -> tuple[Path | None, dict | None]:
    latest_report = find_latest_primary_report_artifact(output_dir)
    if latest_report is None:
        return None, None
    try:
        payload = json.loads(latest_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return latest_report, None
    return latest_report, payload if isinstance(payload, dict) else None


def is_primary_steam_deals_artifact_name(name: str) -> bool:
    if STEAM_DEALS_SHARE_ARTIFACT_RE.match(name):
        return False
    if STEAM_DEALS_JSON_EXPORT_ARTIFACT_RE.match(name):
        return False
    return bool(STEAM_DEALS_PRIMARY_ARTIFACT_RE.match(name))


def is_json_export_artifact_name(name: str) -> bool:
    return bool(STEAM_DEALS_JSON_EXPORT_ARTIFACT_RE.match(name))


def _has_complete_primary_artifact_group(path: Path, output_dir: Path) -> bool:
    required_suffixes = (".md", ".html", ".json")
    try:
        resolved_output_dir = output_dir.resolve()
    except OSError:
        return False

    for suffix in required_suffixes:
        sibling = path.with_suffix(suffix)
        if sibling.is_symlink() or not sibling.is_file():
            return False
        try:
            if sibling.resolve().parent != resolved_output_dir:
                return False
        except OSError:
            return False
    return True


def _json_export_report_date(name: str) -> str:
    match = STEAM_DEALS_JSON_EXPORT_ARTIFACT_RE.match(name)
    return match.group(1) if match else ""


def _has_primary_report_for_export(path: Path, output_dir: Path) -> bool:
    report_date = _json_export_report_date(path.name)
    if not report_date:
        return False
    try:
        candidates = list(output_dir.glob(f"Steam Deals* {report_date}.json"))
    except OSError:
        return False
    return any(
        is_primary_steam_deals_artifact_name(candidate.name)
        and _has_complete_primary_artifact_group(candidate, output_dir)
        for candidate in candidates
    )


def is_allowed_generated_file_path(path: Path, output_dir: Path) -> bool:
    if not is_expected_generated_artifact_name(path.name):
        return False
    if path.is_symlink() or not path.is_file():
        return False
    try:
        if path.resolve().parent != output_dir.resolve():
            return False
    except OSError:
        return False
    if is_primary_steam_deals_artifact_name(path.name):
        return _has_complete_primary_artifact_group(path, output_dir)
    if is_json_export_artifact_name(path.name):
        return _has_primary_report_for_export(path, output_dir)
    return True


def find_latest_primary_report_artifact(output_dir: str | Path) -> Path | None:
    out_dir = Path(output_dir)
    try:
        candidates = [
            path
            for path in out_dir.iterdir()
            if path.suffix.lower() == ".json"
            if is_primary_steam_deals_artifact_name(path.name)
            and is_allowed_generated_file_path(path, out_dir)
        ]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def list_allowed_generated_files(output_dir: str | Path) -> list[Path]:
    out_dir = Path(output_dir)
    try:
        candidates = [
            path
            for path in out_dir.iterdir()
            if is_allowed_generated_file_path(path, out_dir)
        ]
    except OSError:
        return []
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


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
    data = generated_file_error_page(
        status_code,
        title,
        redact_sensitive_text(message),
    ).encode("utf-8")
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


def write_steam_access_direct_import(contract: dict) -> Path:
    """Persist a sanitized Steam Access helper import for the existing import flow."""
    import_path = CONFIG_FILE.parent / "steam-access-direct-import.json"
    tmp_path = import_path.with_suffix(f"{import_path.suffix}.tmp")
    import_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(import_path)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise
    return import_path


def build_public_config_response(config: dict) -> dict:
    default_output_dir = resolve_output_dir(None)
    default_output_label = redact_sensitive_text(
        output_folder_display_name(default_output_dir),
        extra_values=[default_output_dir],
    )
    return {
        **public_config(config),
        "default_output_dir": default_output_label,
        "default_output_label": default_output_label,
    }


def default_itad_external_offers_cache_path() -> str:
    return str(LOCAL_CACHE_DIR / DEFAULT_ITAD_EXTERNAL_OFFERS_CACHE_FILE)


def resolve_itad_external_offers_cache_path(config: dict, filters: dict) -> str:
    configured = normalize_optional_local_path_value(
        config.get("itad_external_offers_cache")
    )
    if configured:
        return configured
    if filters.get("itad_refresh_external_offers_cache"):
        return default_itad_external_offers_cache_path()
    return ""


def steam_openid_status_payload(config: dict) -> dict:
    return {
        "profile": public_steam_openid_profile(config.get("steam_openid_profile")),
        "family_available": False,
        "message": "Steam Sign-in solo identifica tu perfil; no entrega Steam Family ni wishlist privada.",
    }


def steam_openid_result_page(title: str, message: str, *, status: str) -> str:
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    safe_status = html.escape(status)
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #1b2838; color: #f5f5f5; margin: 0; padding: 2rem; }}
    main {{ max-width: 680px; margin: 10vh auto; background: #16202d; border: 1px solid rgba(102,192,244,.25); border-radius: 12px; padding: 1.25rem; }}
    a {{ color: #66c0f4; }}
    .badge {{ display: inline-block; margin-bottom: .75rem; color: #66c0f4; font-weight: 700; text-transform: uppercase; font-size: .75rem; letter-spacing: .08em; }}
  </style>
</head>
<body>
  <main data-steam-openid-result="{safe_status}">
    <span class="badge">Steam Sign-in</span>
    <h1>{safe_title}</h1>
    <p>{safe_message}</p>
    <p>Este flujo no da acceso a Steam Family, wishlist privada, cookies ni tokens.</p>
    <a href="/">Volver a Steam Tools</a>
  </main>
</body>
</html>"""


def verify_steam_openid_check_authentication(payload: dict[str, str], *, timeout: int = 8) -> bool:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        STEAM_OPENID_ENDPOINT,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read(4096).decode("utf-8", errors="replace")
    except OSError:
        return False
    return is_steam_openid_check_authentication_valid(text)


def _config_redaction_values(config: dict, env: dict[str, str] | None = None) -> list[str]:
    values: list[str] = []
    for config_key, env_name in CONFIG_SECRET_ENV_VARS.items():
        config_value = config.get(config_key)
        if not is_redacted_config_secret(config_value):
            values.append(str(config_value))
        if env is not None:
            env_value = env.get(env_name)
            if not is_redacted_config_secret(env_value):
                values.append(str(env_value))
    return values


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
    def valid_generated_artifact(candidate: str) -> str | None:
        value = candidate.strip()
        name = re.split(r"[\\/]", value)[-1]
        if is_expected_generated_artifact_name(name):
            return value
        return None

    stripped = text.strip()
    m = re.search(
        r"(?:✓|OK)\s+(.+\.(?:md|html|csv|json))$", stripped, flags=re.IGNORECASE
    )
    if m:
        return valid_generated_artifact(m.group(1))
    if re.search(r"\.(?:md|html|csv|json)$", stripped, flags=re.IGNORECASE) and (
        "\\" in stripped or "/" in stripped
    ):
        return valid_generated_artifact(stripped)
    return None


def inject_local_session_token(html_text: str, token: str) -> str:
    token_meta = (
        '<meta name="steam-tools-local-token" '
        f'content="{html.escape(token, quote=True)}">'
    )
    if "</head>" in html_text:
        return html_text.replace("</head>", f"{token_meta}\n</head>", 1)
    return token_meta + "\n" + html_text


def load_steam_deals_html() -> str:
    html_text = load_html_with_fallback(
        STEAM_DEALS_HTML_FILE,
        [STEAM_DEALS_CSS_FILE, STEAM_DEALS_JS_FILE],
        STEAM_DEALS_MISSING_ASSETS_HTML,
    )
    return inject_local_session_token(html_text, LOCAL_SESSION_TOKEN)


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


def normalize_optional_local_path_value(raw: object) -> str:
    """Trim UI path input while preserving spaces inside the path."""
    value = str(raw or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def hltb_autodetect_search_dirs(home: Path | None = None) -> list[Path]:
    root = Path.home() if home is None else Path(home).expanduser()
    return [root / relative_dir for relative_dir in HLTB_AUTODETECT_RELATIVE_DIRS]


def find_hltb_csv_candidates(
    *,
    home: Path | None = None,
    search_dirs: Iterable[Path | str] | None = None,
) -> list[Path]:
    directories = (
        [Path(path).expanduser() for path in search_dirs]
        if search_dirs is not None
        else hltb_autodetect_search_dirs(home)
    )
    candidates: list[tuple[float, int, str, Path]] = []
    for priority, directory in enumerate(directories):
        try:
            if not directory.is_dir():
                continue
            matches = list(directory.glob(HLTB_AUTODETECT_PATTERN))
        except OSError:
            continue
        for candidate in matches:
            try:
                if not candidate.is_file():
                    continue
                modified_at = candidate.stat().st_mtime
            except OSError:
                continue
            candidates.append((modified_at, priority, candidate.name.lower(), candidate))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [candidate for _, _, _, candidate in candidates]


def build_hltb_autodetect_public_suggestion(candidate: Path | None) -> dict | None:
    if candidate is None:
        return None
    expanded = candidate.expanduser()
    label = redact_sensitive_text(str(expanded), extra_values=[candidate, expanded])
    if label == str(expanded):
        label = "[ruta]"
    message = (
        f"Se detectó un posible export HLTB CSV local en {label}. "
        "No se usará automáticamente; confirma explícitamente pegando la ruta completa "
        "en el campo HLTB si quieres incluirlo."
    )
    return {
        "found": True,
        "label": label,
        "message": message,
        "requires_confirmation": True,
    }


# ─── Build CLI command ───────────────────────────


def web_schedule_hours_from_filters(filters: dict) -> str | None:
    if not _is_truthy_filter_flag(filters.get("schedule_enabled")):
        return None
    raw_value = str(filters.get("schedule_hours") or "").strip()
    if not raw_value:
        return None
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return raw_value


def _is_truthy_filter_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def web_smart_alert_preview_channels_from_filters(filters: dict) -> list[str]:
    raw_channels = filters.get("smart_alert_preview_channels")
    if isinstance(raw_channels, str):
        values = [raw_channels]
    elif isinstance(raw_channels, (list, tuple, set)):
        values = list(raw_channels)
    else:
        values = []
    channels: list[str] = []
    for value in values:
        for channel in str(value or "").split(","):
            channel = channel.strip().lower()
            if channel:
                channels.append(channel)
    return channels


def build_command(config: dict, filters: dict) -> list[str]:
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--run-script", "steam_deals_generator.py", "--web-run"]
    else:
        cmd = [sys.executable, str(SCRIPT_PATH), "--web-run"]

    vanity = normalize_steam_profile_value(config.get("vanity"))
    if vanity:
        cmd += ["--vanity", vanity]
    hltb_path = normalize_optional_local_path_value(config.get("hltb"))
    if hltb_path:
        cmd += ["--hltb", hltb_path]
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
    if config.get("wishlist_external_matches_json"):
        cmd += [
            "--wishlist-external-matches-json",
            config["wishlist_external_matches_json"],
        ]
    play_access_json = normalize_optional_local_path_value(config.get("play_access_json"))
    if play_access_json:
        cmd += ["--play-access-json", play_access_json]
    steam_access_json = normalize_optional_local_path_value(config.get("steam_access_json"))
    if steam_access_json:
        cmd += ["--steam-access-json", steam_access_json]
    player_preferences_json = normalize_optional_local_path_value(
        config.get("player_preferences_json")
    )
    if player_preferences_json:
        cmd += ["--player-preferences-json", player_preferences_json]
    itad_external_offers_cache = resolve_itad_external_offers_cache_path(config, filters)
    if itad_external_offers_cache:
        cmd += ["--itad-external-offers-cache", itad_external_offers_cache]
    gg_deals_external_offers_cache = normalize_optional_local_path_value(
        config.get("gg_deals_external_offers_cache")
    )
    if gg_deals_external_offers_cache:
        cmd += ["--gg-deals-external-offers-cache", gg_deals_external_offers_cache]
    warm_cache_full = bool(filters.get("warm_cache_full"))
    warm_cache = bool(filters.get("warm_cache"))
    if warm_cache_full:
        cmd.append("--warm-cache-full")
        if filters.get("warm_cache_full_max_passes"):
            cmd += ["--warm-cache-full-max-passes", str(filters["warm_cache_full_max_passes"])]
    elif warm_cache:
        cmd.append("--warm-cache")
    if filters.get("no_cache") and not (warm_cache or warm_cache_full):
        cmd.append("--no-cache")
    if filters.get("free_weekend_live"):
        cmd.append("--free-weekend-live")
    if filters.get("free_weekend_lootscraper_live"):
        cmd.append("--free-weekend-lootscraper-live")
    if filters.get("itad_refresh_external_offers_cache"):
        cmd.append("--itad-refresh-external-offers-cache")
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
    if filters.get("md_frontmatter"):
        cmd.append("--md-frontmatter")
    if filters.get("budget"):
        cmd += ["--budget", str(filters["budget"])]
    if "alert_rise_pct" in filters and filters["alert_rise_pct"] is not None:
        cmd += ["--alert-rise-pct", str(filters["alert_rise_pct"])]
    if (
        "alert_global_margin_pct" in filters
        and filters["alert_global_margin_pct"] is not None
    ):
        cmd += ["--alert-global-margin-pct", str(filters["alert_global_margin_pct"])]
    if "alert_score_min" in filters and filters["alert_score_min"] is not None:
        cmd += ["--alert-score-min", str(filters["alert_score_min"])]
    if _is_truthy_filter_flag(filters.get("smart_alert_opt_in_preview")):
        cmd.append("--smart-alert-opt-in-preview")
        for channel in web_smart_alert_preview_channels_from_filters(filters):
            cmd += ["--smart-alert-preview-channel", channel]
        if _is_truthy_filter_flag(filters.get("smart_alert_preview_reviewed")):
            cmd.append("--smart-alert-preview-reviewed")
        if _is_truthy_filter_flag(filters.get("smart_alert_preview_allow_high_volume")):
            cmd.append("--smart-alert-preview-allow-high-volume")
    schedule_hours = web_schedule_hours_from_filters(filters)
    if schedule_hours:
        cmd += ["--schedule", schedule_hours]
    if config.get("compare"):
        cmd += ["--compare", config["compare"]]
    if config.get("telegram_chat"):
        cmd += ["--telegram-chat", config["telegram_chat"]]
    return cmd


def build_pd2_command(config: dict, filters: dict) -> list[str]:
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--run-script", PD2_ENTRYPOINT]
    else:
        cmd = [sys.executable, str(PD2_SCRIPT_PATH)]

    vanity = normalize_steam_profile_value(config.get("vanity"))
    if vanity:
        cmd += ["--vanity", vanity]
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


def build_runtime_command_and_env(
    config: dict,
    filters: dict,
    *,
    pd2: bool = False,
) -> tuple[list[str], dict[str, str]]:
    command_config = config_without_secrets(config)
    cmd = (
        build_pd2_command(command_config, filters)
        if pd2
        else build_command(command_config, filters)
    )
    env = build_secret_subprocess_env(config)
    return cmd, build_persistent_runtime_env(
        PROJECT_DIR,
        env=env,
        frozen=getattr(sys, "frozen", False),
    )


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

    def _server_port(self) -> int:
        server = getattr(self, "server", None)
        port = getattr(server, "server_port", None)
        if isinstance(port, int):
            return port
        server_address = getattr(server, "server_address", None)
        if isinstance(server_address, tuple) and len(server_address) >= 2:
            try:
                return int(server_address[1])
            except (TypeError, ValueError):
                pass
        return DEFAULT_PORT

    def _require_local_anti_csrf(self) -> bool:
        if is_valid_local_anti_csrf_request(
            self.headers,
            LOCAL_SESSION_TOKEN,
            self._server_port(),
        ):
            return True
        self._send_json(local_anti_csrf_forbidden_payload(), status=403)
        return False

    def _require_loopback_host(self) -> bool:
        if is_valid_loopback_host_header(self.headers, self._server_port()):
            return True
        self._send_json(local_host_forbidden_payload(), status=403)
        return False

    def _send_steam_access_cors_headers(self, origin: str) -> None:
        for header, value in steam_access_cors_headers(origin).items():
            self.send_header(header, value)

    def _send_steam_access_json(self, data, *, status=200, origin: str | None = None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if normalized_origin := normalize_steam_access_extension_origin(origin):
            self._send_steam_access_cors_headers(normalized_origin)
        self.end_headers()
        self.wfile.write(body)

    def _has_active_steam_access_pairing(self) -> bool:
        _prune_steam_access_direct_import_state()
        now = _now_seconds()
        return any(
            is_steam_access_pairing_active(record, now=now)
            for record in _steam_access_pairings.values()
        )

    def _active_steam_access_session_origins(self) -> frozenset[str]:
        _prune_steam_access_direct_import_state()
        return frozenset(
            normalize_steam_access_extension_origin(record.get("origin"))
            for record in _steam_access_import_sessions.values()
            if record.get("origin")
        ) - {""}

    def _steam_access_origin_for_route(self, path: str) -> str:
        origin = normalize_steam_access_extension_origin(self.headers.get("Origin"))
        if not origin:
            return ""
        if path in {STEAM_ACCESS_LOCAL_PAIR_ROUTE, STEAM_ACCESS_LOCAL_IMPORT_ROUTE}:
            return origin
        if origin in self._active_steam_access_session_origins():
            return origin
        return ""

    def _serve_steam_access_options(self) -> None:
        if not self._require_loopback_host():
            return
        path = urllib.parse.urlparse(self.path).path
        origin = self._steam_access_origin_for_route(path)
        if not origin:
            self._send_steam_access_json(steam_access_origin_forbidden_payload(), status=403)
            return
        if not is_valid_steam_access_preflight(self.headers, allowed_origins={origin}):
            self._send_steam_access_json(
                steam_access_cors_forbidden_payload(),
                status=403,
                origin=origin,
            )
            return
        self.send_response(204)
        self._send_steam_access_cors_headers(origin)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _steam_access_extension_origin(self) -> str:
        path = urllib.parse.urlparse(self.path).path
        return self._steam_access_origin_for_route(path)

    def _serve_steam_access_method_not_allowed(self) -> None:
        if not self._require_loopback_host():
            return
        origin = self._steam_access_extension_origin()
        self._send_steam_access_json(
            steam_access_method_not_allowed_payload(),
            status=405,
            origin=origin or None,
        )

    def _require_steam_access_origin(self) -> str:
        origin = self._steam_access_extension_origin()
        if not origin:
            self._send_steam_access_json(steam_access_origin_forbidden_payload(), status=403)
        return origin

    def _require_steam_access_json_envelope(self, origin: str) -> bool:
        if not is_steam_access_json_content_type(self.headers):
            self._send_steam_access_json(
                {
                    "error": "unsupported_media_type",
                    "message": "Content-Type debe ser application/json.",
                },
                status=415,
                origin=origin,
            )
            return False
        if steam_access_content_length(self.headers) is None:
            self._send_steam_access_json(
                {"error": "invalid_content_length", "message": "Content-Length invalido."},
                status=400,
                origin=origin,
            )
            return False
        if not is_steam_access_body_within_limit(
            self.headers,
            max_bytes=STEAM_ACCESS_DIRECT_IMPORT_MAX_BODY_BYTES,
        ):
            self._send_steam_access_json(
                {
                    "error": "payload_too_large",
                    "message": f"Payload excede {STEAM_ACCESS_DIRECT_IMPORT_MAX_BODY_BYTES} bytes.",
                },
                status=413,
                origin=origin,
            )
            return False
        return True

    def _read_steam_access_json_body(self, origin: str) -> dict | None:
        length = steam_access_content_length(self.headers)
        if length is None:
            self._send_steam_access_json(
                {"error": "invalid_content_length", "message": "Content-Length invalido."},
                status=400,
                origin=origin,
            )
            return None
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_steam_access_json(
                {"error": "invalid_json", "message": "JSON invalido en el body."},
                status=400,
                origin=origin,
            )
            return None
        if not isinstance(payload, dict):
            self._send_steam_access_json(
                {"error": "invalid_payload", "message": "Se esperaba un objeto JSON."},
                status=400,
                origin=origin,
            )
            return None
        return payload

    def _steam_access_pairing_record(self, pairing_token: str) -> tuple[str, dict] | tuple[str, None]:
        _prune_steam_access_direct_import_state()
        now = _now_seconds()
        for stored_token, record in _steam_access_pairings.items():
            if _same_local_token(stored_token, pairing_token) and record.get("expires_at", 0) > now:
                if not record.get("used"):
                    return stored_token, record
        return "", None

    def _steam_access_import_session_record(self, token: str) -> dict | None:
        _prune_steam_access_direct_import_state()
        stored_token, record = steam_access_import_session_for_token(
            _steam_access_import_sessions,
            token,
            now=_now_seconds(),
        )
        if stored_token and record is None:
            _steam_access_import_sessions.pop(stored_token, None)
        return record if isinstance(record, dict) else None

    def _require_steam_access_import_session(self, origin: str) -> dict | None:
        if has_steam_access_cookie_auth(self.headers):
            self._send_steam_access_json(
                steam_access_cookie_auth_forbidden_payload(),
                status=401,
                origin=origin,
            )
            return None
        session = self._steam_access_import_session_record(
            steam_access_bearer_token(self.headers)
        )
        if not session or session.get("origin") != origin:
            self._send_steam_access_json(
                steam_access_auth_required_payload(),
                status=401,
                origin=origin,
            )
            return None
        if not is_steam_access_direct_import_confirmed(session):
            self._send_steam_access_json(
                {
                    "error": "user_confirmation_required",
                    "message": "Import directo requiere confirmación local previa.",
                },
                status=403,
                origin=origin,
            )
            return None
        if is_steam_access_rate_limited(
            session,
            max_imports=STEAM_ACCESS_DIRECT_IMPORT_RATE_LIMIT,
        ):
            self._send_steam_access_json(
                steam_access_rate_limited_payload(),
                status=429,
                origin=origin,
            )
            return None
        return session

    # ── GET routes ──

    def do_OPTIONS(self):
        path = urllib.parse.urlparse(self.path).path
        if path in {STEAM_ACCESS_LOCAL_PAIR_ROUTE, STEAM_ACCESS_LOCAL_IMPORT_ROUTE}:
            self._serve_steam_access_options()
        else:
            self.send_error(404)

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        if path in STEAM_ACCESS_LOCAL_ENDPOINT_ROUTES:
            self._serve_steam_access_method_not_allowed()
        else:
            self.send_error(404)

    def do_PATCH(self):
        self.do_PUT()

    def do_DELETE(self):
        self.do_PUT()

    def do_GET(self):
        if not self._require_loopback_host():
            return
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send_html(load_steam_deals_html())
        elif path == "/app.css":
            serve_text_asset(self, STEAM_DEALS_CSS_FILE, CSS_CONTENT_TYPE)
        elif path == "/app.js":
            serve_text_asset(self, STEAM_DEALS_JS_FILE, JS_CONTENT_TYPE)
        elif path == "/api/config":
            self._send_json(build_public_config_response(load_config()))
        elif path == "/api/steam-openid/status":
            self._send_json(steam_openid_status_payload(load_config()))
        elif path == STEAM_ACCESS_LOCAL_PAIR_STATUS_ROUTE:
            self._serve_steam_access_pairing_status()
        elif path in {STEAM_ACCESS_LOCAL_PAIR_ROUTE, STEAM_ACCESS_LOCAL_IMPORT_ROUTE}:
            self._serve_steam_access_method_not_allowed()
        elif path == "/api/steam-openid/callback":
            self._serve_steam_openid_callback()
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
        if not self._require_loopback_host():
            return
        path = urllib.parse.urlparse(self.path).path
        if path in PROTECTED_POST_PATHS and not self._require_local_anti_csrf():
            return
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
        elif path == "/api/steam-openid/start":
            self._serve_steam_openid_start()
        elif path == "/api/steam-openid/disconnect":
            self._serve_steam_openid_disconnect()
        elif path == STEAM_ACCESS_PAIRING_START_PATH:
            self._serve_steam_access_pairing_start()
        elif path == STEAM_ACCESS_PAIRING_REVOKE_PATH:
            self._serve_steam_access_pairing_revoke()
        elif path == STEAM_ACCESS_LOCAL_PAIR_ROUTE:
            self._serve_steam_access_pair_guard()
        elif path == STEAM_ACCESS_LOCAL_IMPORT_ROUTE:
            self._serve_steam_access_import_guard()
        elif path == "/api/watchlist":
            self._serve_watchlist_add()
        elif path == "/api/watchlist/delete":
            self._serve_watchlist_delete()
        elif path == "/api/selection-review":
            self._serve_selection_review()
        elif path == "/api/log/export":
            self._serve_log_export()
        else:
            self.send_error(404)

    # ── Config save ──

    def _serve_config_save(self):
        body = self._read_json_body()
        if body is None:
            return
        cfg = merge_config_preserving_secrets(load_config(), body)
        save_config(cfg)
        self._send_json({"status": "saved"})

    def _serve_steam_openid_start(self):
        state = create_local_session_token(24)
        payload, pending = build_steam_openid_start_response(
            state,
            base_url=steam_openid_base_url(self._server_port()),
        )
        _steam_openid_pending_states[state] = pending
        self._send_json(payload)

    def _serve_steam_openid_disconnect(self):
        cfg = dict(load_config())
        cfg.pop("steam_openid_profile", None)
        save_config(cfg)
        self._send_json({"status": "disconnected", **steam_openid_status_payload(cfg)})

    def _serve_steam_access_pairing_start(self):
        _prune_steam_access_direct_import_state()
        pairing_token = create_local_session_token(STEAM_ACCESS_LOCAL_PAIRING_TOKEN_BYTES)
        pairing_record = build_steam_access_pairing_record(now=_now_seconds())
        _steam_access_pairings[pairing_token] = pairing_record
        expires_at = pairing_record["expires_at"]
        self._send_json(
            {
                "status": "pairing_started",
                "pairing_token": pairing_token,
                "expires_at": steam_access_timestamp_iso(expires_at),
                "expires_in_seconds": STEAM_ACCESS_PAIRING_TTL_SECONDS,
                "pair_url": f"http://127.0.0.1:{self._server_port()}{STEAM_ACCESS_LOCAL_PAIR_ROUTE}",
                "import_url": f"http://127.0.0.1:{self._server_port()}{STEAM_ACCESS_LOCAL_IMPORT_ROUTE}",
                "requires_user_confirmation": True,
                "accepts_payload": False,
                "advisory_only": True,
                "ranking_impact": "none",
            }
        )

    def _serve_steam_access_pairing_status(self):
        if not is_valid_local_anti_csrf_request(
            self.headers,
            LOCAL_SESSION_TOKEN,
            self._server_port(),
        ):
            self._send_json(local_anti_csrf_forbidden_payload(), status=403)
            return
        _prune_steam_access_direct_import_state()
        self._send_json(
            steam_access_local_status_payload(
                _steam_access_pairings,
                _steam_access_import_sessions,
                now=_now_seconds(),
            )
        )

    def _serve_steam_access_pairing_revoke(self):
        reset_steam_access_direct_import_state_for_tests()
        self._send_json({"status": "revoked"})

    def _serve_steam_access_pair_guard(self):
        origin = self._require_steam_access_origin()
        if not origin:
            return
        if has_steam_access_cookie_auth(self.headers):
            self._send_steam_access_json(
                steam_access_cookie_auth_forbidden_payload(),
                status=401,
                origin=origin,
            )
            return
        if not self._require_steam_access_json_envelope(origin):
            return
        body = self._read_steam_access_json_body(origin)
        if body is None:
            return
        header_pairing_token = steam_access_pairing_token(self.headers)
        body_pairing_token = str(body.get("pairing_token") or "").strip()
        if not header_pairing_token or (
            body_pairing_token and not _same_local_token(header_pairing_token, body_pairing_token)
        ):
            self._send_steam_access_json(
                steam_access_pairing_required_payload(),
                status=401,
                origin=origin,
            )
            return
        stored_token, pairing_record = self._steam_access_pairing_record(header_pairing_token)
        if not pairing_record:
            self._send_steam_access_json(
                steam_access_pairing_required_payload(),
                status=401,
                origin=origin,
            )
            return

        pairing_record["used"] = True
        session_token = create_local_session_token(
            STEAM_ACCESS_LOCAL_IMPORT_SESSION_TOKEN_BYTES
        )
        session_record = build_steam_access_import_session_record(
            origin,
            now=_now_seconds(),
        )
        session_record["direct_import_confirmed_by_local_ui"] = True
        _steam_access_pairings.pop(stored_token, None)
        _steam_access_import_sessions[session_token] = session_record
        self._send_steam_access_json(
            {
                "ok": True,
                "status": "paired",
                "session_token": session_token,
                "expires_at": steam_access_timestamp_iso(session_record["expires_at"]),
                "import_url": f"http://127.0.0.1:{self._server_port()}{STEAM_ACCESS_LOCAL_IMPORT_ROUTE}",
                "advisory_only": True,
                "ranking_impact": "none",
            },
            origin=origin,
        )

    def _serve_steam_access_import_guard(self):
        origin = self._require_steam_access_origin()
        if not origin:
            return
        session = self._require_steam_access_import_session(origin)
        if not session:
            return
        if not self._require_steam_access_json_envelope(origin):
            return
        body = self._read_steam_access_json_body(origin)
        if body is None:
            return
        try:
            contract = validate_steam_access_direct_import(body)
        except ValueError as exc:
            self._send_steam_access_json(
                safe_public_error_payload("invalid_steam_access_import", str(exc)),
                status=400,
                origin=origin,
            )
            return
        try:
            import_path = write_steam_access_direct_import(contract)
            cfg = dict(load_config())
            cfg["steam_access_json"] = str(import_path)
            save_config(cfg)
        except OSError as exc:
            self._send_steam_access_json(
                safe_public_error_payload(
                    "steam_access_import_save_failed",
                    "No se pudo guardar el import Steam Access local.",
                    exc=exc,
                    extra_values=[CONFIG_FILE],
                ),
                status=500,
                origin=origin,
            )
            return

        session["import_count"] = int(session.get("import_count", 0)) + 1
        session["last_import_at"] = _now_seconds()
        self._send_steam_access_json(
            {
                "ok": True,
                "imported": True,
                "status": "imported",
                "summary": {
                    "owned_count": len(contract.get("owned_appids") or []),
                    "family_shared_count": len(contract.get("family_shared_appids") or []),
                    "wishlist_count": len(contract.get("wishlist_appids") or []),
                    "advisory_only": True,
                    "ranking_impact": "none",
                },
            },
            origin=origin,
        )

    def _serve_steam_openid_callback(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        try:
            profile = consume_steam_openid_callback(
                params,
                _steam_openid_pending_states,
                used_nonces=_steam_openid_used_nonces,
                verify_authentication=verify_steam_openid_check_authentication,
            )
        except ValueError as exc:
            self._send_html(
                steam_openid_result_page(
                    "No se pudo conectar Steam",
                    str(exc),
                    status="error",
                ),
                status=400,
            )
            return
        cfg = dict(load_config())
        cfg["steam_openid_profile"] = profile
        cfg["vanity"] = profile["profile_url"]
        save_config(cfg)
        self._send_html(
            steam_openid_result_page(
                "Steam conectado",
                f"Perfil enlazado localmente: SteamID {profile['steamid']}. Ya puedes volver y generar reportes con esa identidad.",
                status="ok",
            )
        )

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
        filters = body.get("filters", {}) or {}
        if not isinstance(filters, dict):
            self._send_json(
                {"error": "invalid_payload", "message": "filters debe ser objeto."},
                status=400,
            )
            return
        runtime_config = hydrate_config_secrets(config, load_config())
        issues = []
        warnings = []

        vanity = (config.get("vanity") or "").strip()
        if not vanity:
            issues.append(
                "Falta el perfil de Steam (vanity, Steam ID o URL de perfil)."
            )

        hltb_autodetect = None
        hltb = normalize_optional_local_path_value(config.get("hltb"))
        if hltb and not Path(hltb).expanduser().exists():
            issues.append(
                "No se encontró HLTB CSV local. En Web/Desktop pega la ruta completa sin comillas; "
                "las rutas Windows con espacios se conservan como un solo argumento: "
                + redact_sensitive_text(hltb, extra_values=[Path(hltb).expanduser()])
            )
        elif not hltb:
            hltb_candidates = find_hltb_csv_candidates()
            hltb_autodetect = build_hltb_autodetect_public_suggestion(
                hltb_candidates[0] if hltb_candidates else None
            )
            if hltb_autodetect:
                warnings.append(hltb_autodetect["message"])

        family_json = (config.get("family_json") or "").strip()
        if family_json and not Path(family_json).expanduser().exists():
            issues.append(
                "No se encontró Family JSON: "
                + redact_sensitive_text(
                    family_json,
                    extra_values=[Path(family_json).expanduser()],
                )
            )

        external_matches_json = (config.get("wishlist_external_matches_json") or "").strip()
        if external_matches_json and not Path(external_matches_json).expanduser().exists():
            issues.append(
                "No se encontró JSON de matches externos wishlist: "
                + redact_sensitive_text(
                    external_matches_json,
                    extra_values=[Path(external_matches_json).expanduser()],
                )
            )

        play_access_json = normalize_optional_local_path_value(
            config.get("play_access_json")
        )
        if play_access_json and not Path(play_access_json).expanduser().exists():
            issues.append(
                "No se encontró JSON local de play_access: "
                + redact_sensitive_text(
                    play_access_json,
                    extra_values=[Path(play_access_json).expanduser()],
                )
            )

        steam_access_json = normalize_optional_local_path_value(
            config.get("steam_access_json")
        )
        if steam_access_json and not Path(steam_access_json).expanduser().exists():
            issues.append(
                "No se encontró JSON local Steam Access: "
                + redact_sensitive_text(
                    steam_access_json,
                    extra_values=[Path(steam_access_json).expanduser()],
                )
            )

        player_preferences_json = normalize_optional_local_path_value(
            config.get("player_preferences_json")
        )
        if player_preferences_json and not Path(player_preferences_json).expanduser().exists():
            issues.append(
                "No se encontró JSON local de preferencias del jugador: "
                + redact_sensitive_text(
                    player_preferences_json,
                    extra_values=[Path(player_preferences_json).expanduser()],
                )
            )

        itad_refresh_external_offers_cache = bool(
            filters.get("itad_refresh_external_offers_cache")
        )
        itad_external_offers_cache = resolve_itad_external_offers_cache_path(
            config,
            filters,
        )
        if itad_refresh_external_offers_cache:
            if not (runtime_config.get("itad_key") or "").strip():
                issues.append(
                    "Refresh ITAD external_offers requiere ITAD API Key."
                )
        if itad_external_offers_cache and not Path(itad_external_offers_cache).expanduser().exists():
            cache_label = redact_sensitive_text(
                itad_external_offers_cache,
                extra_values=[Path(itad_external_offers_cache).expanduser()],
            )
            if itad_refresh_external_offers_cache:
                warnings.append(
                    "La caché ITAD external_offers local se creará o actualizará al refrescar: "
                    + cache_label
                )
            else:
                issues.append(
                    "No se encontró caché ITAD external_offers local: "
                    + cache_label
                )

        gg_deals_external_offers_cache = normalize_optional_local_path_value(
            config.get("gg_deals_external_offers_cache")
        )
        if gg_deals_external_offers_cache and not Path(gg_deals_external_offers_cache).expanduser().exists():
            cache_label = redact_sensitive_text(
                gg_deals_external_offers_cache,
                extra_values=[Path(gg_deals_external_offers_cache).expanduser()],
            )
            issues.append(
                "No se encontró caché GG.deals external_offers local: "
                + cache_label
            )

        output_dir = resolve_output_dir(config.get("output"))
        output_label = redact_sensitive_text(
            output_folder_display_name(output_dir),
            extra_values=[output_dir],
        )
        if not output_dir.exists():
            warnings.append(
                f"La carpeta de salida se creará al generar: {output_label}"
            )
        elif not output_dir.is_dir():
            issues.append(
                f"La ruta de salida no es una carpeta: {output_label}"
            )

        if not (runtime_config.get("key") or "").strip():
            warnings.append(
                "Sin Steam API Key: se usará modo público (wishlist debe ser pública)."
            )

        self._send_json(
            {
                "ok": len(issues) == 0,
                "issues": issues,
                "warnings": warnings,
                "hltb_autodetect": hltb_autodetect,
                "output_dir": redact_sensitive_text(str(output_dir), extra_values=[output_dir]),
                "output_label": output_label,
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
                    **safe_public_error_payload(
                        "open_output_folder_failed",
                        "No se pudo abrir la carpeta de salida.",
                        exc=e,
                        extra_values=[output_dir],
                    ),
                    "output_dir": redact_sensitive_text(output_folder_display_name(output_dir), extra_values=[output_dir]),
                    "output_label": redact_sensitive_text(output_folder_display_name(output_dir), extra_values=[output_dir]),
                },
                status=500,
            )
            return

        Handler.output_dir = str(opened_dir)
        public_opened_path = redact_sensitive_text(str(opened_dir), extra_values=[opened_dir])
        public_opened_label = redact_sensitive_text(
            output_folder_display_name(opened_dir),
            extra_values=[opened_dir],
        )
        self._send_json(
            {
                "status": "opened",
                "path": public_opened_path,
                "label": public_opened_label,
            }
        )

    def _serve_desktop_doctor(self):
        try:
            self._send_json(build_desktop_doctor_report())
        except Exception as e:
            self._send_json(
                safe_public_error_payload(
                    "desktop_doctor_failed",
                    "No se pudo ejecutar Desktop Doctor.",
                    exc=e,
                ),
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
                safe_public_error_payload(
                    "desktop_doctor_fix_failed",
                    "No se pudo ejecutar Desktop Autofix.",
                    exc=e,
                ),
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
                safe_public_error_payload(
                    "log_export_failed",
                    "No se pudo guardar el log.",
                    exc=e,
                    extra_values=[filename or ""],
                ),
                status=500,
            )
            return
        self._send_json(
            {
                "status": "saved",
                "path": redact_sensitive_text(str(saved_path), extra_values=[saved_path]),
                "name": saved_path.name,
            }
        )

    # ── Serve generated files ──

    def _serve_files_list(self):
        out_dir = Path(Handler.output_dir)
        files = [
            {
                "name": path.name,
                "size": path.stat().st_size,
                "mtime": path.stat().st_mtime,
            }
            for path in list_allowed_generated_files(out_dir)
        ]
        self._send_json(files[:20])

    def _serve_latest_report(self):
        latest_report = find_latest_primary_report_artifact(Handler.output_dir)
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

    def _serve_selection_review(self):
        body = self._read_json_body()
        if body is None:
            return
        if not isinstance(body, dict):
            self._send_json(
                {"error": "invalid_payload", "message": "El payload debe ser un objeto JSON."},
                status=400,
            )
            return

        _latest_report, report = load_latest_report_payload(Handler.output_dir)
        if report is None:
            self._send_json(
                {
                    "error": "latest_report_not_found",
                    "message": "No se encontró un reporte JSON válido para evaluar la selección.",
                },
                status=404,
            )
            return

        selection = selection_review_records_from_body(body)
        review_context = selection_review_context_from_report(report)
        review = build_selection_review(
            selection,
            **review_context,
        )
        self._send_json({"status": "ok", "review": review})

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
        if not is_expected_generated_artifact_name(name):
            send_generated_file_error(
                self,
                403,
                "Archivo no disponible",
                "Por seguridad solo se pueden abrir archivos generados por nombre. Vuelve al panel y usa los enlaces del último run.",
            )
            return
        out_dir = Path(Handler.output_dir)
        fpath = out_dir / name
        if not fpath.exists():
            send_generated_file_error(
                self,
                404,
                "Archivo no encontrado",
                "El archivo generado ya no está disponible en la carpeta de salida. Ejecuta de nuevo el reporte o revisa la ruta configurada.",
            )
            return
        if not is_allowed_generated_file_path(fpath, out_dir):
            send_generated_file_error(
                self,
                403,
                "Archivo no disponible",
                "Por seguridad solo se pueden abrir reportes generados válidos desde la carpeta de salida.",
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
        for header_name, header_value in generated_html_security_headers(fpath.suffix).items():
            self.send_header(header_name, header_value)
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
        saved_config = load_config()
        runtime_config = hydrate_config_secrets(config, saved_config)

        # Save config for future sessions
        save_cfg = {}
        for k in (
            "vanity",
            "key",
            "hltb",
            "family_json",
            "wishlist_external_matches_json",
            "play_access_json",
            "steam_access_json",
            "player_preferences_json",
            "itad_external_offers_cache",
            "gg_deals_external_offers_cache",
            "itad_key",
        ):
            if config.get(k) and not is_redacted_config_secret(config.get(k)):
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
            save_config({**saved_config, **save_cfg})
        except Exception:
            pass

        # Update output_dir for file serving
        Handler.output_dir = str(resolve_output_dir(runtime_config.get("output")))

        cmd, proc_env = build_runtime_command_and_env(runtime_config, filters, pd2=pd2)
        public_redaction_values = [
            *cmd,
            *_config_redaction_values(runtime_config, proc_env),
        ]

        try:
            proc = start_text_subprocess(cmd, env=proc_env)
        except Exception as e:
            self._send_json(
                safe_public_error_payload(
                    "process_start_failed",
                    "No se pudo iniciar proceso.",
                    exc=e,
                    extra_values=public_redaction_values,
                ),
                status=500,
            )
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
                                "label": redact_sensitive_text(
                                    event.get("label", ""),
                                    extra_values=public_redaction_values,
                                ),
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
                        "label": redact_sensitive_text(
                            prog[2],
                            extra_values=public_redaction_values,
                        ),
                    }
                )

            fpath = detect_file_path(text)
            if fpath:
                generated_files.append(fpath)

            emit_sse(
                {
                    "type": "line",
                    "text": redact_sensitive_text(
                        text,
                        extra_values=public_redaction_values,
                    ),
                    "cls": cls,
                }
            )

        def handle_process_done(done_proc, emit_sse):
            clear_running_proc()
            emit_sse(
                {
                    "type": "done",
                    "exit_code": done_proc.returncode,
                    "files": [
                        public_generated_file_name(path)
                        for path in generated_files
                    ],
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
