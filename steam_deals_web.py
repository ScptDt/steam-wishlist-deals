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
from steam_deals_paths import (
    build_persistent_runtime_env,
    resolve_cache_dir,
    resolve_logs_dir,
    resolve_reports_output_dir,
)
from desktop_doctor import apply_desktop_doctor_fixes, build_desktop_doctor_report
from app.steam_deals_history_dashboard import compare_history_runs, list_history_runs
from shared.tool_modules import PAYDAY2_TOOL_ID, get_tool_entrypoint

from shared_web_infra import (
    build_missing_assets_html,
    build_secret_subprocess_env,
    CONFIG_SECRET_ENV_VARS,
    config_without_secrets,
    create_local_session_token,
    CSS_CONTENT_TYPE,
    hydrate_config_secrets,
    is_valid_local_anti_csrf_request,
    is_valid_loopback_host_header,
    is_redacted_config_secret,
    JS_CONTENT_TYPE,
    load_html_with_fallback,
    local_anti_csrf_forbidden_payload,
    local_host_forbidden_payload,
    LOCAL_CSRF_HEADER,
    merge_config_preserving_secrets,
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
LOCAL_SESSION_TOKEN = create_local_session_token()
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
        "/api/watchlist",
        "/api/watchlist/delete",
        "/api/log/export",
    }
)

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
    if name.startswith("Steam Deals Share "):
        return bool(STEAM_DEALS_SHARE_ARTIFACT_RE.match(name))
    if name.startswith("Steam Deals "):
        return bool(STEAM_DEALS_PRIMARY_ARTIFACT_RE.match(name))
    return name in PAYDAY2_GENERATED_FILES


def is_primary_steam_deals_artifact_name(name: str) -> bool:
    if STEAM_DEALS_SHARE_ARTIFACT_RE.match(name):
        return False
    return bool(STEAM_DEALS_PRIMARY_ARTIFACT_RE.match(name))


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
    return True


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


# ─── Build CLI command ───────────────────────────


def build_command(config: dict, filters: dict) -> list[str]:
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--run-script", "steam_deals_generator.py", "--web-run"]
    else:
        cmd = [sys.executable, str(SCRIPT_PATH), "--web-run"]

    vanity = normalize_steam_profile_value(config.get("vanity"))
    if vanity:
        cmd += ["--vanity", vanity]
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

    # ── GET routes ──

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
        cfg = merge_config_preserving_secrets(load_config(), body)
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
        runtime_config = hydrate_config_secrets(config, load_config())
        issues = []
        warnings = []

        vanity = (config.get("vanity") or "").strip()
        if not vanity:
            issues.append(
                "Falta el perfil de Steam (vanity, Steam ID o URL de perfil)."
            )

        hltb = (config.get("hltb") or "").strip()
        if hltb and not Path(hltb).expanduser().exists():
            issues.append(
                "No se encontró HLTB CSV: "
                + redact_sensitive_text(hltb, extra_values=[Path(hltb).expanduser()])
            )

        family_json = (config.get("family_json") or "").strip()
        if family_json and not Path(family_json).expanduser().exists():
            issues.append(
                "No se encontró Family JSON: "
                + redact_sensitive_text(
                    family_json,
                    extra_values=[Path(family_json).expanduser()],
                )
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
        for k in ("vanity", "key", "hltb", "family_json", "itad_key"):
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
                        redact_sensitive_text(path, extra_values=public_redaction_values)
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
