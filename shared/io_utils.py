from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Mapping


def json_file_fallback_diagnostic(path: Path, exc: BaseException) -> dict[str, str]:
    if isinstance(exc, json.JSONDecodeError):
        error = "invalid_json"
        message = "JSON local inválido; se usaron valores por defecto."
    elif isinstance(exc, UnicodeDecodeError):
        error = "decode_error"
        message = "JSON local ilegible; se usaron valores por defecto."
    else:
        error = "read_error"
        message = "No se pudo leer JSON local; se usaron valores por defecto."
    return {"error": error, "message": message, "file": Path(path).name}


def load_json_file(path: Path, default: Any, *, on_error=None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        if on_error is not None:
            on_error(json_file_fallback_diagnostic(path, exc))
        return default


def write_json_file(
    path: Path,
    data: Any,
    *,
    ensure_ascii: bool = False,
    indent: int | None = 2,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=ensure_ascii, indent=indent),
        encoding="utf-8",
    )


def http_get_json(
    url: str,
    headers: Mapping[str, str] | None = None,
    *,
    timeout: float = 15,
) -> Any:
    req = urllib.request.Request(url, headers=dict(headers or {}))
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def http_post_json(
    url: str,
    body: Any,
    headers: Mapping[str, str] | None = None,
    *,
    timeout: float = 30,
) -> Any:
    data = json.dumps(body).encode("utf-8")
    merged_headers = {"Content-Type": "application/json", **dict(headers or {})}
    req = urllib.request.Request(url, data=data, headers=merged_headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())
