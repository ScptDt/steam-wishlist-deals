from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence
from urllib.parse import urlparse

JSON_CONTENT_TYPE = "application/json; charset=utf-8"
HTML_CONTENT_TYPE = "text/html; charset=utf-8"
CSS_CONTENT_TYPE = "text/css; charset=utf-8"
JS_CONTENT_TYPE = "application/javascript; charset=utf-8"
SSE_CONTENT_TYPE = "text/event-stream"
LOCAL_CSRF_HEADER = "X-Steam-Tools-Local-Token"
LOCAL_CSRF_TOKEN_BYTES = 32
LOCAL_CSRF_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
SENSITIVE_CONFIG_KEYS = frozenset(
    {"key", "itad_key", "telegram_token", "discord_webhook"}
)
CONFIG_SECRET_ENV_VARS = {
    "key": "STEAM_TOOLS_STEAM_API_KEY",
    "itad_key": "STEAM_TOOLS_ITAD_API_KEY",
    "telegram_token": "STEAM_TOOLS_TELEGRAM_TOKEN",
    "discord_webhook": "STEAM_TOOLS_DISCORD_WEBHOOK",
}
REDACTED_SECRET_MARKERS = frozenset(
    {
        "__redacted__",
        "<redacted>",
        "redacted",
        "(redacted)",
        "configured",
        "configured (hidden)",
        "configurada",
        "configurada (oculta)",
    }
)
PUBLIC_REDACTION_MARKER = "[redactado]"
PATH_REDACTION_MARKER = "[ruta]"
TRACEBACK_REDACTION_MARKER = "[traceback]"
TOKEN_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(key|token|webhook|secret)(\s*[=:]\s*)([^\s&;,]+)"
)
DISCORD_WEBHOOK_RE = re.compile(
    r"https://(?:discord(?:app)?\.com)/api/webhooks/[^\s)\]}\"']+",
    re.IGNORECASE,
)
TELEGRAM_TOKEN_RE = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"\b[A-Za-z]:\\[^\s)\]}\"']+")
POSIX_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![:/\w])/(?:[^\s)\]}\"']+)"
)


class LocalWebHandlerProtocol(Protocol):
    headers: Any
    rfile: Any
    wfile: Any

    def send_response(self, code: int) -> None: ...

    def send_header(self, keyword: str, value: str) -> None: ...

    def end_headers(self) -> None: ...

    def send_error(self, code: int) -> None: ...


class ProcessStreamUnavailable(RuntimeError):
    pass


SSEEmitter = Callable[[dict[str, Any]], bool]
SSELineHandler = Callable[[str, SSEEmitter], None]
SSEDoneHandler = Callable[[subprocess.Popen[str], SSEEmitter], None]


def secret_presence_flag_name(secret_key: str) -> str:
    return f"has_{secret_key}"


def create_local_session_token(byte_count: int = LOCAL_CSRF_TOKEN_BYTES) -> str:
    return secrets.token_urlsafe(byte_count)


def is_valid_local_token_header(
    headers: Mapping[str, str],
    expected_token: str,
    *,
    header_name: str = LOCAL_CSRF_HEADER,
) -> bool:
    supplied_token = headers.get(header_name)
    if not supplied_token or not expected_token:
        return False
    return hmac.compare_digest(str(supplied_token), str(expected_token))


def is_local_request_url(value: str, server_port: int) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.hostname not in LOCAL_CSRF_HOSTS:
        return False
    try:
        return parsed.port == server_port
    except ValueError:
        return False


def is_valid_loopback_host(host_header: str | None, server_port: int) -> bool:
    if not host_header:
        return False
    host_value = str(host_header).strip()
    if not host_value or any(ch.isspace() for ch in host_value):
        return False
    try:
        parsed = urlparse(f"//{host_value}")
    except ValueError:
        return False

    if parsed.username or parsed.password or parsed.path or parsed.params or parsed.query or parsed.fragment:
        return False
    if parsed.hostname not in LOCAL_CSRF_HOSTS:
        return False
    try:
        return parsed.port == server_port
    except ValueError:
        return False


def is_valid_loopback_host_header(headers: Mapping[str, str], server_port: int) -> bool:
    return is_valid_loopback_host(headers.get("Host"), server_port)


def local_host_forbidden_payload() -> dict[str, str]:
    return {
        "error": "forbidden_host",
        "message": "Host local no autorizado.",
    }


def has_valid_local_origin_or_referer(
    headers: Mapping[str, str],
    server_port: int,
) -> bool:
    origin = headers.get("Origin")
    if origin:
        return is_local_request_url(origin, server_port)

    referer = headers.get("Referer")
    if referer:
        return is_local_request_url(referer, server_port)
    return True


def is_valid_local_anti_csrf_request(
    headers: Mapping[str, str],
    expected_token: str,
    server_port: int,
) -> bool:
    return is_valid_local_token_header(
        headers,
        expected_token,
    ) and has_valid_local_origin_or_referer(headers, server_port)


def local_anti_csrf_forbidden_payload() -> dict[str, str]:
    return {
        "error": "forbidden",
        "message": "Solicitud local no autorizada.",
    }


def is_redacted_config_secret(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False

    normalized = value.strip()
    if not normalized:
        return True
    if set(normalized) <= {"*"} or set(normalized) <= {"•"}:
        return True
    return normalized.lower() in REDACTED_SECRET_MARKERS


def has_config_secret(config: Mapping[str, Any], secret_key: str) -> bool:
    return not is_redacted_config_secret(config.get(secret_key))


def public_config(
    config: Mapping[str, Any],
    *,
    sensitive_keys: Iterable[str] = SENSITIVE_CONFIG_KEYS,
) -> dict[str, Any]:
    sensitive = frozenset(sensitive_keys)
    public = {key: value for key, value in config.items() if key not in sensitive}
    for secret_key in sorted(sensitive):
        public[secret_presence_flag_name(secret_key)] = has_config_secret(config, secret_key)
    return public


def merge_config_preserving_secrets(
    existing_config: Mapping[str, Any],
    incoming_config: Mapping[str, Any],
    *,
    sensitive_keys: Iterable[str] = SENSITIVE_CONFIG_KEYS,
) -> dict[str, Any]:
    sensitive = frozenset(sensitive_keys)
    secret_flags = {secret_presence_flag_name(secret_key) for secret_key in sensitive}
    merged = dict(existing_config)

    for key, value in incoming_config.items():
        if key in secret_flags:
            continue
        if key in sensitive and is_redacted_config_secret(value):
            continue
        merged[key] = value
    return merged


def hydrate_config_secrets(
    public_or_partial_config: Mapping[str, Any],
    saved_config: Mapping[str, Any],
    *,
    sensitive_keys: Iterable[str] = SENSITIVE_CONFIG_KEYS,
) -> dict[str, Any]:
    hydrated = dict(public_or_partial_config)
    for secret_key in sensitive_keys:
        if not is_redacted_config_secret(hydrated.get(secret_key)):
            continue
        saved_value = saved_config.get(secret_key)
        if not is_redacted_config_secret(saved_value):
            hydrated[secret_key] = saved_value
    return hydrated


def config_without_secrets(
    config: Mapping[str, Any],
    *,
    sensitive_keys: Iterable[str] = SENSITIVE_CONFIG_KEYS,
) -> dict[str, Any]:
    sensitive = frozenset(sensitive_keys)
    return {key: value for key, value in config.items() if key not in sensitive}


def extract_secret_env(
    config: Mapping[str, Any],
    *,
    env_var_names: Mapping[str, str] = CONFIG_SECRET_ENV_VARS,
) -> dict[str, str]:
    env: dict[str, str] = {}
    for config_key, env_name in env_var_names.items():
        value = config.get(config_key)
        if is_redacted_config_secret(value):
            continue
        env[env_name] = str(value)
    return env


def build_secret_subprocess_env(
    config: Mapping[str, Any],
    *,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.update(extract_secret_env(config))
    return env


def resolve_config_secret(
    cli_value: Any,
    config: Mapping[str, Any],
    config_key: str,
    *,
    environ: Mapping[str, str] | None = None,
    env_var_names: Mapping[str, str] = CONFIG_SECRET_ENV_VARS,
) -> Any:
    if cli_value is not None:
        return cli_value
    env_name = env_var_names.get(config_key)
    env = os.environ if environ is None else environ
    if env_name:
        env_value = env.get(env_name)
        if not is_redacted_config_secret(env_value):
            return env_value
    return config.get(config_key)


def _known_sensitive_values(extra_values: Iterable[Any] = ()) -> list[str]:
    values: list[str] = []
    for env_name in CONFIG_SECRET_ENV_VARS.values():
        env_value = os.environ.get(env_name)
        if env_value:
            values.append(env_value)
    for path_value in (Path.home(), Path.cwd(), getattr(sys, "_MEIPASS", None)):
        if path_value:
            values.append(str(path_value))
    for value in extra_values:
        if value:
            values.append(str(value))
    return sorted(set(values), key=len, reverse=True)


def redact_sensitive_text(text: Any, *, extra_values: Iterable[Any] = ()) -> str:
    redacted = str(text or "")
    for value in _known_sensitive_values(extra_values):
        if value:
            marker = PATH_REDACTION_MARKER if any(sep in value for sep in ("/", "\\")) else PUBLIC_REDACTION_MARKER
            redacted = redacted.replace(value, marker)
    redacted = DISCORD_WEBHOOK_RE.sub(PUBLIC_REDACTION_MARKER, redacted)
    redacted = TELEGRAM_TOKEN_RE.sub(PUBLIC_REDACTION_MARKER, redacted)
    redacted = TOKEN_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{PUBLIC_REDACTION_MARKER}",
        redacted,
    )
    redacted = WINDOWS_ABSOLUTE_PATH_RE.sub(PATH_REDACTION_MARKER, redacted)
    redacted = POSIX_ABSOLUTE_PATH_RE.sub(PATH_REDACTION_MARKER, redacted)
    redacted = redacted.replace("_MEIPASS", PATH_REDACTION_MARKER)
    redacted = re.sub(r"Traceback(?: \(most recent call last\))?:?", TRACEBACK_REDACTION_MARKER, redacted, flags=re.IGNORECASE)
    return redacted


def safe_public_error_payload(
    error: str,
    message: str,
    *,
    exc: BaseException | None = None,
    extra_values: Iterable[Any] = (),
) -> dict[str, str]:
    payload = {"error": error, "message": redact_sensitive_text(message, extra_values=extra_values)}
    if exc is not None:
        detail = redact_sensitive_text(str(exc), extra_values=extra_values).strip()
        if detail:
            payload["detail"] = detail
    return payload


def send_text(
    handler: LocalWebHandlerProtocol,
    text: str,
    content_type: str,
    status: int = 200,
) -> None:
    body = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_json(
    handler: LocalWebHandlerProtocol,
    data: Any,
    status: int = 200,
) -> None:
    send_text(
        handler,
        json.dumps(data, ensure_ascii=False),
        JSON_CONTENT_TYPE,
        status=status,
    )


def send_html(
    handler: LocalWebHandlerProtocol,
    html: str,
    status: int = 200,
) -> None:
    send_text(handler, html, HTML_CONTENT_TYPE, status=status)


def read_json_body(
    handler: LocalWebHandlerProtocol,
    max_json_body_bytes: int = 64 * 1024,
) -> dict[str, Any] | None:
    raw_length = handler.headers.get("Content-Length", "0")

    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        send_json(
            handler,
            {
                "error": "invalid_content_length",
                "message": "Content-Length invalido.",
            },
            status=400,
        )
        return None

    if length <= 0:
        return {}

    if length > max_json_body_bytes:
        send_json(
            handler,
            {
                "error": "payload_too_large",
                "message": f"Payload excede {max_json_body_bytes} bytes.",
            },
            status=413,
        )
        return None

    content_type = (handler.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if content_type and content_type != "application/json":
        send_json(
            handler,
            {
                "error": "unsupported_media_type",
                "message": "Content-Type debe ser application/json.",
            },
            status=415,
        )
        return None

    try:
        payload = json.loads(handler.rfile.read(length))
    except (json.JSONDecodeError, UnicodeDecodeError):
        send_json(
            handler,
            {
                "error": "invalid_json",
                "message": "JSON invalido en el body.",
            },
            status=400,
        )
        return None

    if not isinstance(payload, dict):
        send_json(
            handler,
            {
                "error": "invalid_payload",
                "message": "Se esperaba un objeto JSON.",
            },
            status=400,
        )
        return None

    return payload


def load_text_asset(asset_file: Path) -> str | None:
    try:
        if asset_file.exists():
            return asset_file.read_text(encoding="utf-8")
    except OSError:
        return None
    return None


def load_html_with_fallback(
    html_file: Path,
    required_assets: Iterable[Path],
    fallback_html: str,
) -> str:
    try:
        if html_file.exists() and all(asset.exists() for asset in required_assets):
            return html_file.read_text(encoding="utf-8")
    except OSError:
        pass
    return fallback_html


def build_missing_assets_html(app_name: str, asset_hint: str) -> str:
    safe_app_name = app_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_asset_hint = asset_hint.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_app_name} - assets faltantes</title>
<style>
body {{ font-family: system-ui, sans-serif; background: #1b2838; color: #c7d5e0; margin: 0; padding: 2rem; }}
main {{ max-width: 680px; margin: 8vh auto; background: #16202d; border: 1px solid #2a475e; border-radius: 12px; padding: 1.5rem; }}
h1 {{ color: #66c0f4; margin-top: 0; }}
code {{ background: #0e1a26; border-radius: 4px; padding: .1rem .3rem; }}
</style>
</head>
<body>
<main>
<h1>{safe_app_name}</h1>
<p>No se encontraron los assets web necesarios para cargar la interfaz completa.</p>
<p>Revisa que <code>{safe_asset_hint}</code> esté incluido junto al ejecutable o vuelve a generar el build desktop.</p>
</main>
</body>
</html>"""


def serve_text_asset(
    handler: LocalWebHandlerProtocol,
    asset_file: Path,
    content_type: str,
) -> bool:
    asset = load_text_asset(asset_file)
    if asset is None:
        handler.send_error(404)
        return False
    send_text(handler, asset, content_type)
    return True


def build_unbuffered_process_env(
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )
    return env


def start_text_subprocess(
    command: Sequence[str],
    env: Mapping[str, str] | None = None,
) -> subprocess.Popen[str]:
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creation_flag = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if creation_flag:
            popen_kwargs["creationflags"] = creation_flag
    else:
        popen_kwargs["start_new_session"] = True

    return subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=build_unbuffered_process_env(env),
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **popen_kwargs,
    )


def send_sse_headers(handler: LocalWebHandlerProtocol) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", SSE_CONTENT_TYPE)
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()


def send_sse_event(handler: LocalWebHandlerProtocol, data: dict[str, Any]) -> bool:
    try:
        handler.wfile.write(
            f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")
        )
        handler.wfile.flush()
        return True
    except BrokenPipeError:
        return False


def stream_process_as_sse(
    handler: LocalWebHandlerProtocol,
    proc: subprocess.Popen[str],
    on_stdout_line: SSELineHandler,
    on_done: SSEDoneHandler | None = None,
) -> None:
    stream = proc.stdout
    if stream is None:
        raise ProcessStreamUnavailable("No se pudo leer salida del proceso")

    send_sse_headers(handler)
    emitter = lambda data: send_sse_event(handler, data)

    try:
        for raw_line in stream:
            on_stdout_line(raw_line, emitter)
        proc.wait()
    except Exception:
        stop_process(proc, timeout_seconds=1.0)

    if on_done is not None:
        on_done(proc, emitter)


def stop_process(
    proc: subprocess.Popen[str],
    timeout_seconds: float = 3.0,
    *,
    os_name: str = os.name,
    getpgid=None,
    killpg=None,
    terminate_fn=None,
    kill_fn=None,
    wait_fn=None,
) -> None:
    if proc.poll() is not None:
        return

    if getpgid is None:
        getpgid = os.getpgid
    if killpg is None:
        killpg = os.killpg
    if terminate_fn is None:
        terminate_fn = proc.terminate
    if kill_fn is None:
        kill_fn = proc.kill
    if wait_fn is None:
        wait_fn = proc.wait

    process_group_id = None
    if os_name != "nt":
        try:
            process_group_id = getpgid(proc.pid)
            killpg(process_group_id, signal.SIGTERM)
        except (AttributeError, ProcessLookupError, OSError):
            terminate_fn()
    else:
        terminate_fn()

    try:
        wait_fn(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        if os_name != "nt" and process_group_id is not None:
            try:
                killpg(process_group_id, signal.SIGKILL)
            except (AttributeError, ProcessLookupError, OSError):
                kill_fn()
        else:
            kill_fn()
