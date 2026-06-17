from __future__ import annotations

import base64
import hashlib
import re
import secrets
import urllib.parse
from copy import deepcopy
from typing import Any, Callable


ITAD_OAUTH_AUTHORIZE_URL = "https://isthereanydeal.com/oauth/authorize/"
ITAD_OAUTH_TOKEN_URL = "https://isthereanydeal.com/oauth/token/"
ITAD_OAUTH_CODE_CHALLENGE_METHOD = "S256"
ITAD_OAUTH_DEFAULT_SCOPES = ("user_info",)
ITAD_OAUTH_USER_SCOPES = frozenset(
    {
        "user_info",
        "notes_read",
        "notes_write",
        "profiles",
        "wait_read",
        "wait_write",
        "coll_read",
        "coll_write",
        "ignored_read",
        "ignored_write",
        "webhooks",
    }
)

ITAD_OAUTH_ENDPOINT_SUPPORT = {
    "user_info_v2": {
        "path": "/user/info/v2",
        "oauth": True,
        "scopes": ("user_info",),
        "note": "User-scoped endpoint documented as OAuth-only.",
    },
    "deals_v2": {
        "path": "/deals/v2",
        "oauth": True,
        "scopes": ("wait_read", "coll_read"),
        "note": "Docs allow API key or OAuth; OAuth enables user data filters.",
    },
    "games_lookup_v1": {
        "path": "/games/lookup/v1",
        "oauth": False,
        "scopes": (),
        "note": "Docs list API-key auth, not OAuth.",
    },
    "games_prices_v3": {
        "path": "/games/prices/v3",
        "oauth": False,
        "scopes": (),
        "note": "Docs list API-key auth, not OAuth.",
    },
    "games_search_v1": {
        "path": "/games/search/v1",
        "oauth": False,
        "scopes": (),
        "note": "Docs list API-key auth, not OAuth.",
    },
}

_CODE_VERIFIER_RE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
_SENSITIVE_OAUTH_KEYS = {
    "access_token",
    "refresh_token",
    "id_token",
    "client_secret",
    "code_verifier",
    "code",
    "authorization",
}


def generate_itad_oauth_code_verifier(token_factory: Callable[[int], str] = secrets.token_urlsafe) -> str:
    verifier = token_factory(64)
    if not _is_valid_code_verifier(verifier):
        raise ValueError("ITAD OAuth code_verifier inválido")
    return verifier


def build_itad_oauth_code_challenge(code_verifier: str) -> str:
    verifier = _clean_required_text(code_verifier, "code_verifier")
    if not _is_valid_code_verifier(verifier):
        raise ValueError("ITAD OAuth code_verifier inválido")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def build_itad_oauth_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
    scopes: tuple[str, ...] | list[str] = ITAD_OAUTH_DEFAULT_SCOPES,
) -> str:
    params = {
        "response_type": "code",
        "client_id": _clean_required_text(client_id, "client_id"),
        "redirect_uri": _clean_required_text(redirect_uri, "redirect_uri"),
        "scope": _scope_text(scopes),
        "state": _clean_required_text(state, "state"),
        "code_challenge": _clean_required_text(code_challenge, "code_challenge"),
        "code_challenge_method": ITAD_OAUTH_CODE_CHALLENGE_METHOD,
    }
    return f"{ITAD_OAUTH_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def build_itad_oauth_pkce_start(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: tuple[str, ...] | list[str] = ITAD_OAUTH_DEFAULT_SCOPES,
    state: str | None = None,
    code_verifier: str | None = None,
    token_factory: Callable[[int], str] = secrets.token_urlsafe,
) -> dict[str, Any]:
    verifier = code_verifier or generate_itad_oauth_code_verifier(token_factory)
    challenge = build_itad_oauth_code_challenge(verifier)
    safe_state = state or token_factory(32)
    return {
        "authorization_url": build_itad_oauth_authorization_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=challenge,
            state=safe_state,
            scopes=scopes,
        ),
        "state": safe_state,
        "code_verifier": verifier,
        "code_challenge": challenge,
        "code_challenge_method": ITAD_OAUTH_CODE_CHALLENGE_METHOD,
        "scopes": tuple(_valid_scopes(scopes)),
    }


def parse_itad_oauth_callback(query: str, *, expected_state: str) -> dict[str, str]:
    parsed = urllib.parse.parse_qs(query.lstrip("?"), keep_blank_values=True)
    state = _first_query_value(parsed, "state")
    if state != expected_state:
        raise ValueError("ITAD OAuth callback state inválido")
    error = _first_query_value(parsed, "error")
    if error:
        description = _first_query_value(parsed, "error_description") or error
        raise ValueError(f"ITAD OAuth callback error: {description}")
    code = _first_query_value(parsed, "code")
    if not code:
        raise ValueError("ITAD OAuth callback sin code")
    return {"code": code, "state": state}


def build_itad_oauth_token_request(
    *,
    client_id: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    client_secret: str | None = None,
) -> dict[str, Any]:
    body = {
        "grant_type": "authorization_code",
        "client_id": _clean_required_text(client_id, "client_id"),
        "redirect_uri": _clean_required_text(redirect_uri, "redirect_uri"),
        "code": _clean_required_text(code, "code"),
        "code_verifier": _clean_required_text(code_verifier, "code_verifier"),
    }
    if client_secret:
        body["client_secret"] = _clean_required_text(client_secret, "client_secret")
    return _token_request(body)


def build_itad_oauth_refresh_request(
    *,
    client_id: str,
    refresh_token: str,
    client_secret: str | None = None,
) -> dict[str, Any]:
    body = {
        "grant_type": "refresh_token",
        "client_id": _clean_required_text(client_id, "client_id"),
        "refresh_token": _clean_required_text(refresh_token, "refresh_token"),
    }
    if client_secret:
        body["client_secret"] = _clean_required_text(client_secret, "client_secret")
    return _token_request(body)


def exchange_itad_oauth_code(
    *,
    client_id: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    post_form,
    client_secret: str | None = None,
) -> dict[str, Any]:
    request = build_itad_oauth_token_request(
        client_id=client_id,
        redirect_uri=redirect_uri,
        code=code,
        code_verifier=code_verifier,
        client_secret=client_secret,
    )
    return normalize_itad_oauth_token_payload(
        post_form(request["url"], request["body"], headers=request["headers"])
    )


def refresh_itad_oauth_token(
    *,
    client_id: str,
    refresh_token: str,
    post_form,
    client_secret: str | None = None,
) -> dict[str, Any]:
    request = build_itad_oauth_refresh_request(
        client_id=client_id,
        refresh_token=refresh_token,
        client_secret=client_secret,
    )
    return normalize_itad_oauth_token_payload(
        post_form(request["url"], request["body"], headers=request["headers"])
    )


def normalize_itad_oauth_token_payload(payload) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("ITAD OAuth token response inválida")
    access_token = _clean_required_text(payload.get("access_token"), "access_token")
    token_type = str(payload.get("token_type") or "Bearer").strip()
    if token_type.lower() != "bearer":
        raise ValueError("ITAD OAuth token_type no soportado")
    normalized = {
        "access_token": access_token,
        "token_type": "Bearer",
    }
    for key in ("refresh_token", "expires_in", "scope"):
        if payload.get(key) not in (None, ""):
            normalized[key] = payload[key]
    return normalized


def itad_oauth_bearer_headers(access_token: str) -> dict[str, str]:
    token = _clean_required_text(access_token, "access_token")
    return {"Authorization": f"Bearer {token}"}


def itad_oauth_endpoint_support(endpoint_key: str) -> dict[str, Any]:
    support = ITAD_OAUTH_ENDPOINT_SUPPORT.get(endpoint_key)
    if not support:
        return {
            "path": endpoint_key,
            "oauth": False,
            "scopes": (),
            "note": "Endpoint no registrado en el spike OAuth ITAD.",
        }
    return {**support, "scopes": tuple(support.get("scopes") or ())}


def redact_itad_oauth_secrets(value):
    if isinstance(value, dict):
        return {
            key: "[redactado]" if str(key).lower() in _SENSITIVE_OAUTH_KEYS else redact_itad_oauth_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_itad_oauth_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_itad_oauth_secrets(item) for item in value)
    return deepcopy(value)


def _token_request(body: dict[str, str]) -> dict[str, Any]:
    return {
        "url": ITAD_OAUTH_TOKEN_URL,
        "body": body,
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
    }


def _clean_required_text(value, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"ITAD OAuth requiere {field}")
    return text


def _scope_text(scopes: tuple[str, ...] | list[str]) -> str:
    return " ".join(_valid_scopes(scopes))


def _valid_scopes(scopes: tuple[str, ...] | list[str]) -> list[str]:
    result = [str(scope).strip() for scope in scopes or () if str(scope).strip()]
    if not result:
        raise ValueError("ITAD OAuth requiere al menos un scope")
    invalid = [scope for scope in result if scope not in ITAD_OAUTH_USER_SCOPES]
    if invalid:
        raise ValueError(f"ITAD OAuth scope no soportado: {invalid[0]}")
    return result


def _is_valid_code_verifier(value: str) -> bool:
    return bool(_CODE_VERIFIER_RE.fullmatch(str(value or "")))


def _first_query_value(parsed: dict[str, list[str]], key: str) -> str:
    values = parsed.get(key) or []
    return values[0] if values else ""
