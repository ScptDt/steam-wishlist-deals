from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Mapping


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
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
