from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

JSON_CONTENT_TYPE = "application/json; charset=utf-8"
HTML_CONTENT_TYPE = "text/html; charset=utf-8"
CSS_CONTENT_TYPE = "text/css; charset=utf-8"
JS_CONTENT_TYPE = "application/javascript; charset=utf-8"
SSE_CONTENT_TYPE = "text/event-stream"


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
) -> None:
    if proc.poll() is not None:
        return

    if getpgid is None:
        getpgid = os.getpgid
    if killpg is None:
        killpg = os.killpg

    process_group_id = None
    if os_name != "nt":
        try:
            process_group_id = getpgid(proc.pid)
            killpg(process_group_id, signal.SIGTERM)
        except (AttributeError, ProcessLookupError, OSError):
            proc.terminate()
    else:
        proc.terminate()

    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        if os_name != "nt" and process_group_id is not None:
            try:
                killpg(process_group_id, signal.SIGKILL)
            except (AttributeError, ProcessLookupError, OSError):
                proc.kill()
        else:
            proc.kill()
