from __future__ import annotations

import re
import time
import urllib.parse
from collections.abc import Mapping, MutableMapping
from datetime import datetime, timezone


STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
STEAM_OPENID_NS = "http://specs.openid.net/auth/2.0"
STEAM_OPENID_IDENTIFIER_SELECT = "http://specs.openid.net/auth/2.0/identifier_select"
STEAM_OPENID_CLAIMED_ID_RE = re.compile(r"^https?://steamcommunity\.com/openid/id/(\d+)$")
STEAM_OPENID_STATE_TTL_SECONDS = 15 * 60
STEAM_OPENID_REQUIRED_SIGNED_FIELDS = frozenset(
    {"assoc_handle", "claimed_id", "identity", "op_endpoint", "response_nonce", "return_to"}
)


def _clean_text(value) -> str:
    return str(value or "").strip()


def _param(params: Mapping[str, object], key: str) -> str:
    value = params.get(key)
    if isinstance(value, (list, tuple)):
        return _clean_text(value[0] if value else "")
    return _clean_text(value)


def _signed_fields(params: Mapping[str, object]) -> set[str]:
    return {
        field.strip()
        for field in _param(params, "openid.signed").split(",")
        if field.strip()
    }


def _nonce_timestamp(value: str) -> float | None:
    nonce = _clean_text(value)
    if len(nonce) < 20:
        return None
    try:
        dt = datetime.strptime(nonce[:20], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc).timestamp()


def _prune_used_nonces(used_nonces: MutableMapping[str, float], now: float) -> None:
    cutoff = float(now) - STEAM_OPENID_STATE_TTL_SECONDS
    for nonce, seen_at in list(used_nonces.items()):
        try:
            if float(seen_at) < cutoff:
                used_nonces.pop(nonce, None)
        except (TypeError, ValueError):
            used_nonces.pop(nonce, None)


def _validate_response_nonce(
    nonce: str,
    *,
    now: float,
    used_nonces: Mapping[str, float] | None = None,
) -> None:
    clean_nonce = _clean_text(nonce)
    if not clean_nonce or len(clean_nonce) > 255:
        raise ValueError("nonce OpenID inválido")
    nonce_ts = _nonce_timestamp(clean_nonce)
    if nonce_ts is None:
        raise ValueError("nonce OpenID inválido")
    if abs(float(now) - nonce_ts) > STEAM_OPENID_STATE_TTL_SECONDS:
        raise ValueError("nonce OpenID expirado")
    if used_nonces is not None and clean_nonce in used_nonces:
        raise ValueError("nonce OpenID ya usado")


def steam_openid_base_url(port: int) -> str:
    return f"http://127.0.0.1:{int(port)}"


def build_steam_openid_return_to(base_url: str, state: str) -> str:
    return f"{base_url.rstrip('/')}/api/steam-openid/callback?state={urllib.parse.quote(state)}"


def build_steam_openid_login_url(return_to: str, realm: str) -> str:
    params = {
        "openid.ns": STEAM_OPENID_NS,
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.claimed_id": STEAM_OPENID_IDENTIFIER_SELECT,
        "openid.identity": STEAM_OPENID_IDENTIFIER_SELECT,
    }
    return f"{STEAM_OPENID_ENDPOINT}?{urllib.parse.urlencode(params)}"


def build_steam_openid_check_authentication_payload(params: Mapping[str, object]) -> dict[str, str]:
    payload: dict[str, str] = {}
    for key in params:
        if str(key).startswith("openid."):
            payload[str(key)] = _param(params, str(key))
    payload["openid.mode"] = "check_authentication"
    return payload


def is_steam_openid_check_authentication_valid(response_text: str) -> bool:
    values = {}
    for line in str(response_text or "").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values.get("is_valid") == "true"


def build_steam_openid_pending_state(state: str, *, base_url: str, now: float | None = None) -> dict:
    clean_state = _clean_text(state)
    realm = f"{base_url.rstrip('/')}/"
    return_to = build_steam_openid_return_to(base_url, clean_state)
    return {
        "state": clean_state,
        "return_to": return_to,
        "realm": realm,
        "created_at": float(time.time() if now is None else now),
    }


def build_steam_openid_start_response(state: str, *, base_url: str, now: float | None = None) -> tuple[dict, dict]:
    pending = build_steam_openid_pending_state(state, base_url=base_url, now=now)
    return {
        "login_url": build_steam_openid_login_url(pending["return_to"], pending["realm"]),
        "state": pending["state"],
        "expires_in_seconds": STEAM_OPENID_STATE_TTL_SECONDS,
        "notes": [
            "Steam OpenID solo identifica SteamID/perfil; no entrega Steam Family ni wishlist privada.",
            "La app no pide password, no lee cookies/tokens y no automatiza login.",
        ],
    }, pending


def extract_steamid_from_claimed_id(value: str) -> str:
    match = STEAM_OPENID_CLAIMED_ID_RE.match(_clean_text(value))
    return match.group(1) if match else ""


def steam_openid_profile(steamid: str, *, persona_name: str = "", avatar_url: str = "") -> dict:
    clean_steamid = _clean_text(steamid)
    if not clean_steamid.isdigit():
        raise ValueError("SteamID OpenID inválido")
    profile = {
        "schema": "steam_openid_profile_v1",
        "steamid": clean_steamid,
        "profile_url": f"https://steamcommunity.com/profiles/{clean_steamid}/",
        "source": "steam_openid",
        "family_access": "not_available_via_openid",
        "advisory_only": True,
        "ranking_impact": "none",
    }
    if value := _clean_text(persona_name):
        profile["persona_name"] = value
    if value := _clean_text(avatar_url):
        profile["avatar_url"] = value
    return profile


def public_steam_openid_profile(profile) -> dict | None:
    if not isinstance(profile, dict):
        return None
    steamid = _clean_text(profile.get("steamid"))
    if not steamid.isdigit():
        return None
    return {
        key: profile[key]
        for key in (
            "schema",
            "steamid",
            "profile_url",
            "persona_name",
            "avatar_url",
            "source",
            "family_access",
            "advisory_only",
            "ranking_impact",
        )
        if key in profile
    }


def validate_steam_openid_callback(
    params: Mapping[str, object],
    pending: Mapping[str, object],
    *,
    now: float | None = None,
    used_nonces: Mapping[str, float] | None = None,
) -> dict:
    current_time = float(time.time() if now is None else now)
    state = _param(params, "state")
    expected_state = _clean_text(pending.get("state"))
    if not state or state != expected_state:
        raise ValueError("state OpenID inválido o expirado")
    created_at = float(pending.get("created_at") or 0)
    if created_at and (current_time - created_at) > STEAM_OPENID_STATE_TTL_SECONDS:
        raise ValueError("state OpenID expirado")
    if _param(params, "openid.ns") != STEAM_OPENID_NS:
        raise ValueError("namespace OpenID inválido")
    if _param(params, "openid.mode") != "id_res":
        raise ValueError("respuesta OpenID no confirmada")
    if not _param(params, "openid.sig"):
        raise ValueError("firma OpenID ausente")
    if not STEAM_OPENID_REQUIRED_SIGNED_FIELDS.issubset(_signed_fields(params)):
        raise ValueError("campos firmados OpenID insuficientes")
    if _param(params, "openid.op_endpoint") != STEAM_OPENID_ENDPOINT:
        raise ValueError("proveedor OpenID inválido")
    if _param(params, "openid.return_to") != _clean_text(pending.get("return_to")):
        raise ValueError("return_to OpenID inválido")
    _validate_response_nonce(_param(params, "openid.response_nonce"), now=current_time, used_nonces=used_nonces)
    claimed_steamid = extract_steamid_from_claimed_id(_param(params, "openid.claimed_id"))
    identity_steamid = extract_steamid_from_claimed_id(_param(params, "openid.identity"))
    if not claimed_steamid or claimed_steamid != identity_steamid:
        raise ValueError("SteamID OpenID inválido")
    return steam_openid_profile(claimed_steamid)


def consume_steam_openid_callback(
    params: Mapping[str, object],
    pending_states: MutableMapping[str, Mapping[str, object]],
    *,
    now: float | None = None,
    used_nonces: MutableMapping[str, float] | None = None,
    verify_authentication=None,
) -> dict:
    current_time = float(time.time() if now is None else now)
    state = _param(params, "state")
    pending = pending_states.pop(state, None) if state else None
    if not pending:
        raise ValueError("state OpenID inválido o expirado")
    if used_nonces is not None:
        _prune_used_nonces(used_nonces, current_time)
    profile = validate_steam_openid_callback(
        params,
        pending,
        now=current_time,
        used_nonces=used_nonces,
    )
    if verify_authentication is not None and not verify_authentication(
        build_steam_openid_check_authentication_payload(params)
    ):
        raise ValueError("firma OpenID no validada por Steam")
    if used_nonces is not None:
        used_nonces[_param(params, "openid.response_nonce")] = current_time
    return profile
