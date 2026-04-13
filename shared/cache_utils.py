from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .io_utils import load_json_file, write_json_file


def load_timestamped_cache(
    path: Path,
    payload_key: str,
    *,
    identity_key: str | None = None,
    identity_value: str | None = None,
    default: dict | None = None,
) -> tuple[dict, float]:
    empty = dict(default or {})
    data = load_json_file(path, None)
    if not isinstance(data, dict):
        return empty, float("inf")

    if identity_key is not None and data.get(identity_key) != identity_value:
        return empty, float("inf")

    saved_at = data.get("saved_at")
    if not isinstance(saved_at, str):
        return empty, float("inf")

    try:
        age_hours = (datetime.now() - datetime.fromisoformat(saved_at)).total_seconds() / 3600
    except (TypeError, ValueError):
        return empty, float("inf")

    payload = data.get(payload_key, empty)
    if not isinstance(payload, dict):
        payload = empty

    return payload, age_hours


def save_timestamped_cache(
    path: Path,
    payload_key: str,
    payload: dict,
    *,
    identity_key: str | None = None,
    identity_value: str | None = None,
    ensure_ascii: bool = False,
    indent: int | None = 2,
) -> None:
    data: dict[str, object] = {
        "saved_at": datetime.now().isoformat(),
        payload_key: payload,
    }
    if identity_key is not None:
        data[identity_key] = identity_value

    write_json_file(path, data, ensure_ascii=ensure_ascii, indent=indent)
