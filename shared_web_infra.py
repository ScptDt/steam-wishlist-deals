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
STEAM_ACCESS_IMPORT_SCHEMA = "steam_access_import_v1"
STEAM_ACCESS_IMPORT_ADVISORY_ONLY = True
STEAM_ACCESS_IMPORT_RANKING_IMPACT = "none"
STEAM_ACCESS_IMPORT_COLLECTION_KEYS = (
    "owned_appids",
    "family_shared_appids",
    "wishlist_appids",
)
STEAM_ACCESS_LOCAL_LOOPBACK_HOST = "127.0.0.1"
STEAM_ACCESS_LOCAL_PAIR_ROUTE = "/api/steam-access/pair"
STEAM_ACCESS_LOCAL_PAIR_STATUS_ROUTE = "/api/steam-access/pair/status"
STEAM_ACCESS_LOCAL_IMPORT_ROUTE = "/api/steam-access/import"
STEAM_ACCESS_LOCAL_AUTH_HEADER = "Authorization"
STEAM_ACCESS_LOCAL_PAIRING_TOKEN_HEADER = "X-Pairing-Token"
STEAM_ACCESS_LOCAL_PAIRING_TOKEN_BYTES = 18
STEAM_ACCESS_LOCAL_IMPORT_SESSION_TOKEN_BYTES = 24
STEAM_ACCESS_LOCAL_PAIRING_TTL_SECONDS = 5 * 60
STEAM_ACCESS_LOCAL_IMPORT_SESSION_TTL_SECONDS = 30 * 60
STEAM_ACCESS_LOCAL_ALLOWED_EXTENSION_ORIGINS = frozenset()
STEAM_ACCESS_LOCAL_ALLOWED_ORIGIN_SCHEMES = frozenset(
    {"chrome-extension", "moz-extension"}
)
STEAM_ACCESS_LOCAL_IMPORT_ALLOWED_METHODS = ("POST", "OPTIONS")
STEAM_ACCESS_LOCAL_IMPORT_CORS_ALLOW_HEADERS = (
    STEAM_ACCESS_LOCAL_AUTH_HEADER,
    "Content-Type",
    STEAM_ACCESS_LOCAL_PAIRING_TOKEN_HEADER,
)
STEAM_ACCESS_LOCAL_IMPORT_CORS_ALLOW_METHODS = ("POST", "OPTIONS")
STEAM_ACCESS_LOCAL_IMPORT_CONTENT_TYPE = "application/json"
STEAM_ACCESS_LOCAL_IMPORT_MAX_BODY_BYTES = 64 * 1024
STEAM_ACCESS_LOCAL_IMPORT_RATE_LIMIT = 3
STEAM_ACCESS_LOCAL_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "cookie",
        "cookies",
        "steam_token",
        "steam_tokens",
        "token",
        "tokens",
        "session",
        "session_id",
        "sessionid",
        "headers",
        "request_headers",
        "raw_response",
        "raw_html",
        "html",
        "password",
        "steamid",
        "steam_id",
        "profile",
        "profile_url",
        "family_member",
        "family_members",
        "family_member_names",
        "friend",
        "friends",
        "email",
        "emails",
    }
)
STEAM_ACCESS_LOCAL_IMPORT_SECURITY_INVARIANTS = (
    "import_only_no_general_command_endpoint",
    "bind_and_call_127_0_0_1_loopback_only",
    "token_auth_required_no_cookies",
    "strict_extension_origin_allowlist",
    "post_json_import_only",
    "narrow_options_preflight_only",
    "appid_only_payload_no_steam_secrets_or_identity",
    "advisory_only_true_ranking_impact_none",
    "no_score_ranking_default_cache_or_fetching_changes",
    "no_live_steam_login_network_or_mutations",
)
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
SAFE_PUBLIC_METRIC_PATH_FRAGMENTS = frozenset(
    {
        "cache",
        "caché",
        "cooldown",
        "deals",
        "deferred",
        "fallback",
        "historial",
        "history",
        "juegos",
        "ofertas",
        "pendientes",
        "prices",
        "precios",
        "processed",
        "procesados",
        "progress",
        "progreso",
        "reviews",
        "reseñas",
        "total",
    }
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


def steam_access_origin_forbidden_payload() -> dict[str, str]:
    return {
        "error": "forbidden_origin",
        "message": "Origin de extensión no autorizado.",
    }


def steam_access_cors_forbidden_payload() -> dict[str, str]:
    return {
        "error": "forbidden_cors",
        "message": "Preflight Steam Access no autorizado.",
    }


def steam_access_method_not_allowed_payload() -> dict[str, str]:
    return {
        "error": "method_not_allowed",
        "message": "Steam Access directo acepta solo POST JSON y OPTIONS preflight.",
    }


def steam_access_auth_required_payload() -> dict[str, str]:
    return {
        "error": "invalid_session",
        "message": "Sesión local de import inválida o expirada.",
    }


def steam_access_pairing_required_payload() -> dict[str, str]:
    return {
        "error": "invalid_pairing",
        "message": "Pairing token local inválido o expirado.",
    }


def steam_access_cookie_auth_forbidden_payload() -> dict[str, str]:
    return {
        "error": "cookie_auth_forbidden",
        "message": "Steam Access directo no acepta autenticación por cookies.",
    }


def steam_access_rate_limited_payload() -> dict[str, str]:
    return {
        "error": "rate_limited",
        "message": "Límite de imports directos alcanzado.",
    }


def steam_access_local_import_contract() -> dict[str, Any]:
    """Return the Plan 7B import-only local endpoint contract."""
    return {
        "schema": STEAM_ACCESS_IMPORT_SCHEMA,
        "routes": {
            "pair": STEAM_ACCESS_LOCAL_PAIR_ROUTE,
            "pair_status": STEAM_ACCESS_LOCAL_PAIR_STATUS_ROUTE,
            "import": STEAM_ACCESS_LOCAL_IMPORT_ROUTE,
        },
        "loopback_host": STEAM_ACCESS_LOCAL_LOOPBACK_HOST,
        "auth_header": STEAM_ACCESS_LOCAL_AUTH_HEADER,
        "pairing_token_header": STEAM_ACCESS_LOCAL_PAIRING_TOKEN_HEADER,
        "allowed_extension_origins": sorted(
            STEAM_ACCESS_LOCAL_ALLOWED_EXTENSION_ORIGINS
        ),
        "allowed_origin_schemes": sorted(STEAM_ACCESS_LOCAL_ALLOWED_ORIGIN_SCHEMES),
        "allowed_methods": list(STEAM_ACCESS_LOCAL_IMPORT_ALLOWED_METHODS),
        "allowed_headers": list(STEAM_ACCESS_LOCAL_IMPORT_CORS_ALLOW_HEADERS),
        "content_type": STEAM_ACCESS_LOCAL_IMPORT_CONTENT_TYPE,
        "max_body_bytes": STEAM_ACCESS_LOCAL_IMPORT_MAX_BODY_BYTES,
        "rate_limit_per_session": STEAM_ACCESS_LOCAL_IMPORT_RATE_LIMIT,
        "collection_keys": list(STEAM_ACCESS_IMPORT_COLLECTION_KEYS),
        "advisory_only": STEAM_ACCESS_IMPORT_ADVISORY_ONLY,
        "ranking_impact": STEAM_ACCESS_IMPORT_RANKING_IMPACT,
        "forbidden_payload_keys": sorted(STEAM_ACCESS_LOCAL_FORBIDDEN_PAYLOAD_KEYS),
        "security_invariants": list(STEAM_ACCESS_LOCAL_IMPORT_SECURITY_INVARIANTS),
    }


def normalize_steam_access_extension_origin(origin: str | None) -> str:
    raw = str(origin or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    if parsed.scheme not in STEAM_ACCESS_LOCAL_ALLOWED_ORIGIN_SCHEMES:
        return ""
    if not parsed.netloc or parsed.username or parsed.password:
        return ""
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def is_valid_steam_access_extension_origin(
    origin: str | None,
    *,
    allowed_origins: Iterable[str] = STEAM_ACCESS_LOCAL_ALLOWED_EXTENSION_ORIGINS,
) -> bool:
    normalized = normalize_steam_access_extension_origin(origin)
    if not normalized:
        return False
    allowed = frozenset(normalize_steam_access_extension_origin(value) for value in allowed_origins)
    allowed = frozenset(value for value in allowed if value)
    if not allowed:
        return True
    return normalized in allowed


def steam_access_cors_headers(origin: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": ", ".join(STEAM_ACCESS_LOCAL_IMPORT_CORS_ALLOW_METHODS),
        "Access-Control-Allow-Headers": ", ".join(STEAM_ACCESS_LOCAL_IMPORT_CORS_ALLOW_HEADERS),
        "Vary": "Origin",
    }


def _requested_header_names(value: str | None) -> set[str]:
    return {part.strip().lower() for part in str(value or "").split(",") if part.strip()}


def is_valid_steam_access_preflight(
    headers: Mapping[str, str],
    *,
    allowed_origins: Iterable[str] = STEAM_ACCESS_LOCAL_ALLOWED_EXTENSION_ORIGINS,
) -> bool:
    if not is_valid_steam_access_extension_origin(
        headers.get("Origin"),
        allowed_origins=allowed_origins,
    ):
        return False
    method = str(headers.get("Access-Control-Request-Method") or "").strip().upper()
    if method != "POST":
        return False
    requested_headers = _requested_header_names(headers.get("Access-Control-Request-Headers"))
    allowed_headers = {header.lower() for header in STEAM_ACCESS_LOCAL_IMPORT_CORS_ALLOW_HEADERS}
    if not requested_headers or not requested_headers <= allowed_headers:
        return False
    return "content-type" in requested_headers and (
        "authorization" in requested_headers
        or STEAM_ACCESS_LOCAL_PAIRING_TOKEN_HEADER.lower() in requested_headers
    )


def steam_access_bearer_token(headers: Mapping[str, str]) -> str:
    auth = str(headers.get(STEAM_ACCESS_LOCAL_AUTH_HEADER) or "").strip()
    prefix = "Bearer "
    if not auth.startswith(prefix):
        return ""
    return auth[len(prefix) :].strip()


def steam_access_pairing_token(headers: Mapping[str, str]) -> str:
    return str(headers.get(STEAM_ACCESS_LOCAL_PAIRING_TOKEN_HEADER) or "").strip()


def has_steam_access_cookie_auth(headers: Mapping[str, str]) -> bool:
    return bool(str(headers.get("Cookie") or "").strip())


def is_steam_access_json_content_type(headers: Mapping[str, str]) -> bool:
    content_type = str(headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return content_type == STEAM_ACCESS_LOCAL_IMPORT_CONTENT_TYPE


def steam_access_content_length(headers: Mapping[str, str]) -> int | None:
    try:
        return int(headers.get("Content-Length", "0"))
    except (TypeError, ValueError):
        return None


def is_steam_access_body_within_limit(
    headers: Mapping[str, str],
    *,
    max_bytes: int = STEAM_ACCESS_LOCAL_IMPORT_MAX_BODY_BYTES,
) -> bool:
    length = steam_access_content_length(headers)
    return length is not None and 0 <= length <= max_bytes


def steam_access_timestamp_iso(timestamp: float) -> str:
    from datetime import datetime, timezone

    return (
        datetime.fromtimestamp(timestamp, timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_steam_access_pairing_record(
    *,
    now: float,
    ttl_seconds: int = STEAM_ACCESS_LOCAL_PAIRING_TTL_SECONDS,
) -> dict[str, Any]:
    return {
        "created_at": now,
        "expires_at": now + ttl_seconds,
        "used": False,
        "pairing_confirmed_by_local_ui": True,
    }


def build_steam_access_import_session_record(
    origin: str,
    *,
    now: float,
    ttl_seconds: int = STEAM_ACCESS_LOCAL_IMPORT_SESSION_TTL_SECONDS,
) -> dict[str, Any]:
    return {
        "origin": origin,
        "created_at": now,
        "expires_at": now + ttl_seconds,
        "import_count": 0,
        "revoked": False,
        "paired": True,
        "pairing_confirmed_by_local_ui": True,
        "direct_import_confirmed_by_local_ui": False,
    }


def is_steam_access_pairing_active(record: Mapping[str, Any], *, now: float) -> bool:
    return bool(record.get("expires_at", 0) > now and not record.get("used"))


def is_steam_access_import_session_active(
    record: Mapping[str, Any],
    *,
    now: float,
) -> bool:
    return bool(record.get("expires_at", 0) > now and not record.get("revoked"))


def steam_access_import_session_for_token(
    sessions: Mapping[str, Mapping[str, Any]],
    token: str,
    *,
    now: float,
) -> tuple[str, Mapping[str, Any] | None]:
    if not token:
        return "", None
    for stored_token, record in sessions.items():
        if hmac.compare_digest(str(stored_token), str(token)):
            if is_steam_access_import_session_active(record, now=now):
                return stored_token, record
            return stored_token, None
    return "", None


def is_steam_access_rate_limited(
    session_record: Mapping[str, Any],
    *,
    max_imports: int = STEAM_ACCESS_LOCAL_IMPORT_RATE_LIMIT,
) -> bool:
    try:
        import_count = int(session_record.get("import_count") or 0)
    except (TypeError, ValueError):
        import_count = max_imports
    return import_count >= max_imports


def is_steam_access_direct_import_confirmed(record: Mapping[str, Any]) -> bool:
    return bool(
        record.get("paired")
        and record.get("pairing_confirmed_by_local_ui")
        and record.get("direct_import_confirmed_by_local_ui")
    )


def steam_access_local_status_payload(
    pairings: Mapping[str, Mapping[str, Any]],
    sessions: Mapping[str, Mapping[str, Any]],
    *,
    now: float,
) -> dict[str, Any]:
    active_pairings = [
        record
        for record in pairings.values()
        if is_steam_access_pairing_active(record, now=now)
    ]
    active_sessions = [
        record
        for record in sessions.values()
        if is_steam_access_import_session_active(record, now=now)
    ]
    import_ready = any(
        is_steam_access_direct_import_confirmed(record) for record in active_sessions
    )
    next_pairing_expiry = min(
        (record["expires_at"] for record in active_pairings),
        default=None,
    )
    next_session_expiry = min(
        (record["expires_at"] for record in active_sessions),
        default=None,
    )
    return {
        "status": "ready_for_confirmation" if active_pairings or active_sessions else "idle",
        "loopback_host": STEAM_ACCESS_LOCAL_LOOPBACK_HOST,
        "pairing": {
            "active": bool(active_pairings),
            "active_count": len(active_pairings),
            "expires_at": steam_access_timestamp_iso(next_pairing_expiry)
            if next_pairing_expiry
            else None,
        },
        "session": {
            "active": bool(active_sessions),
            "active_count": len(active_sessions),
            "expires_at": steam_access_timestamp_iso(next_session_expiry)
            if next_session_expiry
            else None,
        },
        "direct_import": {
            "ready": import_ready,
            "requires_pairing": not bool(active_sessions),
            "requires_user_confirmation": not import_ready,
            "accepts_payload": False,
        },
        "advisory_only": STEAM_ACCESS_IMPORT_ADVISORY_ONLY,
        "ranking_impact": STEAM_ACCESS_IMPORT_RANKING_IMPACT,
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
    path_values: list[Any] = []
    for path_getter in (Path.home, Path.cwd):
        try:
            path_values.append(path_getter())
        except OSError:
            continue
    path_values.append(getattr(sys, "_MEIPASS", None))
    for path_value in path_values:
        if path_value:
            values.append(str(path_value))
    for value in extra_values:
        if value:
            values.append(str(value))
    return sorted(set(values), key=len, reverse=True)


def _previous_metric_word(source: str, start: int) -> str:
    before = source[:start].rstrip()
    match = re.search(r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)$", before)
    return match.group(1).lower() if match else ""


def _is_safe_public_metric_path_fragment(value: str, source: str, start: int) -> bool:
    fragment = value[1:] if value.startswith("/") else value
    if not fragment or "/" in fragment or "\\" in fragment:
        return False
    normalized = fragment.strip(".,;:").lower()
    previous_text = source[:start].rstrip()
    previous_char = previous_text[-1:] if previous_text else ""
    previous_word = _previous_metric_word(source, start)
    if re.fullmatch(r"\d[\d.,]*%?", normalized):
        return bool(previous_char and (previous_char.isdigit() or previous_word in SAFE_PUBLIC_METRIC_PATH_FRAGMENTS))
    return normalized in SAFE_PUBLIC_METRIC_PATH_FRAGMENTS and previous_word in SAFE_PUBLIC_METRIC_PATH_FRAGMENTS


def _redact_posix_absolute_path_match(match: re.Match[str]) -> str:
    value = match.group(0)
    if _is_safe_public_metric_path_fragment(value, match.string, match.start()):
        return value
    return PATH_REDACTION_MARKER


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
    redacted = POSIX_ABSOLUTE_PATH_RE.sub(_redact_posix_absolute_path_match, redacted)
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
