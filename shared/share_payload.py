from __future__ import annotations

import base64
import json
import urllib.parse
from collections.abc import Mapping
from typing import Any


SHARE_PAYLOAD_VERSION = 1
SHARE_URL_PREFIX = "steamtools://share?data="


def normalize_share_payload(
    raw: Mapping[str, Any] | None,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return _invalid_payload(strict)

    appid = _clean_text(_first_value(raw, "appid", "steam_appid", "app_id"))
    name = _clean_text(_first_value(raw, "name", "steam_name"))
    if not appid or not name:
        return _invalid_payload(strict)

    price = _clean_text(_first_value(raw, "price", "price_final"))
    price_final = _clean_text(_first_value(raw, "price_final", "price"))
    price_original = _clean_text(
        _first_value(raw, "price_original", "original_price")
    )
    min_hist = _clean_text(
        _first_value(raw, "min_hist", "historical_low", "min_historical")
    )
    steam_url = _steam_store_url(appid)

    return {
        "v": SHARE_PAYLOAD_VERSION,
        "name": name,
        "steam_name": _clean_text(raw.get("steam_name")) or name,
        "appid": appid,
        "steam_appid": appid,
        "price": price,
        "price_final": price_final or price,
        "price_original": price_original or price_final or price,
        "original_price": price_original or price_final or price,
        "discount": _normalize_discount(raw.get("discount")),
        "min_hist": min_hist,
        "min_historical": min_hist,
        "historical_low": min_hist,
        "steam_url": steam_url,
        "url": steam_url,
    }


def encode_share_payload(payload: Mapping[str, Any] | None) -> str:
    normalized = normalize_share_payload(payload)
    if not normalized:
        return ""

    json_payload = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return base64.b64encode(json_payload.encode("utf-8")).decode("ascii")


def decode_share_payload(data: str, *, strict: bool = True) -> dict[str, Any]:
    try:
        decoded = _decode_json_payload(data)
    except Exception as exc:
        if strict:
            raise ValueError("share payload inválido") from exc
        return {}

    normalized = normalize_share_payload(decoded, strict=strict)
    if normalized:
        return normalized
    if strict:
        raise ValueError("share payload inválido")
    return {}


def build_steamtools_share_url(payload: Mapping[str, Any] | None) -> str:
    encoded = encode_share_payload(payload)
    return f"{SHARE_URL_PREFIX}{encoded}" if encoded else ""


def _decode_json_payload(data: str) -> Any:
    encoded = _normalize_encoded_data(data)
    if not encoded:
        raise ValueError("share payload vacío")

    decoded_bytes = _base64_decode(encoded)
    return json.loads(decoded_bytes.decode("utf-8"))


def _invalid_payload(strict: bool) -> dict[str, Any]:
    if strict:
        raise ValueError("share payload inválido")
    return {}


def _normalize_encoded_data(data: str) -> str:
    raw = str(data or "").strip()
    if raw.startswith(SHARE_URL_PREFIX):
        raw = raw[len(SHARE_URL_PREFIX) :]
    elif "data=" in raw:
        raw = _extract_data_query_value(raw)

    normalized = urllib.parse.unquote(raw).replace(" ", "+")
    padding = len(normalized) % 4
    if padding:
        normalized += "=" * (4 - padding)
    return normalized


def _extract_data_query_value(raw: str) -> str:
    query = urllib.parse.urlparse(raw).query or raw
    for part in query.split("&"):
        if part.startswith("data="):
            return part.split("=", 1)[1]
    return raw


def _base64_decode(encoded: str) -> bytes:
    try:
        return base64.b64decode(encoded)
    except Exception:
        return base64.urlsafe_b64decode(encoded)


def _first_value(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None and value != "":
            return value
    return None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_discount(value: Any) -> int | float:
    if isinstance(value, bool):
        return 0
    try:
        discount = float(value)
    except (TypeError, ValueError):
        return 0
    if not discount.is_integer():
        return discount
    return int(discount)


def _steam_store_url(appid: str) -> str:
    return f"https://store.steampowered.com/app/{appid}/"
