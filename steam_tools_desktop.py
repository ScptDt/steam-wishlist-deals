#!/usr/bin/env python3
"""Desktop launcher (Option B): Steam Tools in a native window via pywebview.

This is a first baseline for desktop packaging:
- Starts the local web server without opening an external browser
- Opens a native window using pywebview
- Stops the web server when the window closes
"""

from __future__ import annotations

import os
import subprocess
import socket
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import webbrowser
import runpy
from pathlib import Path
from urllib.parse import urlencode

from steam_deals_paths import build_persistent_runtime_env


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8080
PORT_SCAN_SIZE = 10
URL = f"http://{HOST}:{PORT}"
FORCE_WEB_FALLBACK_ENV = "STEAM_TOOLS_FORCE_WEB_FALLBACK"
FORCE_WEB_FALLBACK_FLAG = "--force-web-fallback"

FALLBACK_REASON_MESSAGES = {
    "forced-web-fallback": "Fallback web forzado para validacion. Abriendo Steam Tools en el navegador.",
    "missing-webview": "pywebview o su backend nativo no estan disponibles. Abriendo Steam Tools en el navegador.",
    "window-timeout": "La ventana nativa no respondio a tiempo. Abriendo Steam Tools en el navegador.",
    "window-error": "La ventana nativa fallo al iniciar. Abriendo Steam Tools en el navegador.",
}
ALLOWED_EMBEDDED_SCRIPTS = frozenset(
    {"steam_deals_generator.py", "payday2_dlc_tracker.py"}
)


def _fallback_url(reason: str | None = None, *, base_url: str = URL) -> str:
    if not reason:
        return base_url
    query = urlencode({"desktop_fallback": "1", "reason": reason})
    return f"{base_url}?{query}"


def _desktop_window_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["desktop_native"] = "1"
    return urllib.parse.urlunparse(parsed._replace(query=urlencode(query)))


def _is_truthy_flag(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _should_force_web_fallback(
    *,
    argv: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> bool:
    args = sys.argv[1:] if argv is None else list(argv)
    if FORCE_WEB_FALLBACK_FLAG in args:
        return True
    runtime_env = os.environ if env is None else env
    return _is_truthy_flag(runtime_env.get(FORCE_WEB_FALLBACK_ENV))


def _normalize_clipboard_text(text: object) -> str:
    value = str(text or "")
    if not value.strip():
        raise ValueError("No hay contenido de log para copiar.")
    return value


def copy_text_to_qt_clipboard(
    text: str,
    *,
    qapplication_cls=None,
) -> str:
    if qapplication_cls is None:
        try:
            from PyQt6.QtWidgets import QApplication as qapplication_cls  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError("Clipboard nativo Qt no disponible.") from exc

    app = qapplication_cls.instance()
    if app is None:
        raise RuntimeError("Clipboard nativo Qt no inicializado.")
    clipboard = app.clipboard()
    if clipboard is None:
        raise RuntimeError("Clipboard nativo Qt no disponible.")
    clipboard.setText(text)
    return "qt"


class DesktopClipboardApi:
    def __init__(self, *, copy_text_fn=copy_text_to_qt_clipboard):
        self._copy_text_fn = copy_text_fn

    def copy_text_to_clipboard(self, text: object) -> dict[str, str]:
        normalized = _normalize_clipboard_text(text)
        try:
            backend = self._copy_text_fn(normalized)
        except Exception as exc:
            raise RuntimeError(
                "Clipboard nativo no disponible. Usa Descargar log (.txt)."
            ) from exc
        return {"status": "copied", "backend": str(backend or "native")}


def _config_probe_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/config"


def _probe_steam_deals_server(
    base_url: str,
    *,
    timeout: float = 1.5,
    urlopen_fn=urllib.request.urlopen,
) -> bool:
    try:
        with urlopen_fn(_config_probe_url(base_url), timeout=timeout) as response:
            return int(getattr(response, "status", 200)) == 200
    except Exception:
        return False


def _candidate_urls(start_port: int, *, host: str = HOST) -> list[str]:
    return [
        f"http://{host}:{port}"
        for port in range(start_port, start_port + PORT_SCAN_SIZE)
    ]


def _find_free_port(
    start_port: int,
    *,
    host: str = HOST,
    socket_factory=socket.socket,
) -> int | None:
    for port in range(start_port, start_port + PORT_SCAN_SIZE):
        sock = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
        except OSError:
            sock.close()
            continue
        sock.close()
        return port
    return None


def _resolve_server_target(
    start_port: int,
    *,
    discover_live_url_fn=None,
    find_free_port_fn=None,
) -> dict[str, object]:
    if discover_live_url_fn is None:
        discover_live_url_fn = _discover_live_url
    if find_free_port_fn is None:
        find_free_port_fn = _find_free_port
    reused_url = discover_live_url_fn(start_port, timeout=0.6)
    if reused_url is not None:
        return {
            "reuse_existing": True,
            "active_url": reused_url,
            "launch_port": None,
            "discover_start_port": start_port,
        }

    launch_port = find_free_port_fn(start_port) or start_port
    return {
        "reuse_existing": False,
        "active_url": f"http://{HOST}:{launch_port}",
        "launch_port": launch_port,
        "discover_start_port": launch_port,
    }


def _wait_server(
    url: str,
    timeout: float = 15.0,
    *,
    urlopen_fn=urllib.request.urlopen,
    sleep_fn=time.sleep,
) -> bool:
    start = time.monotonic()
    while (time.monotonic() - start) < timeout:
        if _probe_steam_deals_server(url, timeout=1.5, urlopen_fn=urlopen_fn):
            return True
        sleep_fn(0.2)
    return False


def _discover_live_url(
    start_port: int,
    timeout: float = 15.0,
    *,
    urlopen_fn=urllib.request.urlopen,
    sleep_fn=time.sleep,
) -> str | None:
    start = time.monotonic()
    urls = _candidate_urls(start_port)
    while (time.monotonic() - start) < timeout:
        for base_url in urls:
            if _probe_steam_deals_server(
                base_url, timeout=1.5, urlopen_fn=urlopen_fn
            ):
                return base_url
        sleep_fn(0.2)
    return None


def _run_internal_web_server() -> None:
    from steam_deals_web import main as web_main

    args = [arg for arg in sys.argv[1:] if arg != "--internal-web"]
    if "--no-open" not in args:
        args.append("--no-open")

    prev_argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0], *args]
        web_main()
    finally:
        sys.argv = prev_argv


def _build_child_process_env(*, frozen: bool, base_env=None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    if frozen:
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        env = build_persistent_runtime_env(ROOT, env=env, frozen=True)
    return env


def validate_embedded_script_name(raw_name: str) -> str:
    script_name = str(raw_name or "").strip()
    if not script_name:
        raise ValueError("Script embebido no permitido.")
    if Path(script_name).is_absolute():
        raise ValueError("Script embebido no permitido.")
    if (
        ".." in script_name
        or "/" in script_name
        or "\\" in script_name
        or ":" in script_name
    ):
        raise ValueError("Script embebido no permitido.")
    if script_name not in ALLOWED_EMBEDDED_SCRIPTS:
        raise ValueError("Script embebido no permitido.")
    return script_name


def resolve_allowed_embedded_script(
    raw_name: str,
    *,
    base_dir: str | Path | None = None,
) -> Path:
    script_name = validate_embedded_script_name(raw_name)
    base = Path(base_dir) if base_dir is not None else Path(getattr(sys, "_MEIPASS", ROOT))
    try:
        resolved_base = base.resolve(strict=False)
        script_path = (resolved_base / script_name).resolve(strict=False)
    except OSError as exc:
        raise RuntimeError("Script embebido permitido no disponible.") from exc
    if script_path.parent != resolved_base:
        raise ValueError("Script embebido no permitido.")
    if not script_path.is_file() or script_path.is_symlink():
        raise RuntimeError("Script embebido permitido no disponible.")
    return script_path


def _run_embedded_script(
    script_name: str,
    script_args: list[str],
    *,
    base_dir: str | Path | None = None,
    run_path_fn=runpy.run_path,
) -> None:
    script_path = resolve_allowed_embedded_script(script_name, base_dir=base_dir)

    prev_argv = sys.argv[:]
    try:
        sys.argv = [str(script_path), *script_args]
        run_path_fn(str(script_path), run_name="__main__")
    finally:
        sys.argv = prev_argv


def decode_share_payload(data_encoded: str) -> dict:
    import base64
    import json

    normalized = urllib.parse.unquote(str(data_encoded or "").strip()).replace(" ", "+")
    if not normalized:
        raise ValueError("share payload vacío")
    padding = len(normalized) % 4
    if padding:
        normalized += "=" * (4 - padding)

    payload = json.loads(base64.b64decode(normalized).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("share payload inválido")
    if "price_original" not in payload and payload.get("original_price") is not None:
        payload["price_original"] = payload.get("original_price")
    return payload


def main() -> None:
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        print(
            "Uso: python steam_tools_desktop.py [--share=BASE64] "
            "[--internal-web] [--doctor] [--doctor-fix] [--yes] "
            "[--force-web-fallback] [--run-script <script> [args...]]"
        )
        print("\nOpciones:")
        print("  -h, --help            Muestra esta ayuda y sale")
        print("  --share=BASE64        Abre/parsea un deal compartido")
        print("  --internal-web        Ejecuta el servidor web embebido")
        print("  --doctor              Ejecuta checks read-only de readiness desktop")
        print("  --doctor-fix          Aplica autofixes seguros (con confirmacion)")
        print("  --yes                 Omite prompt interactivo para --doctor-fix")
        print("  --force-web-fallback  Fuerza abrir la UI en navegador para validar fallback")
        print("  --run-script FILE ... Ejecuta script embebido con argumentos")
        return

    if "--doctor" in sys.argv[1:]:
        from desktop_doctor import run_desktop_doctor

        raise SystemExit(run_desktop_doctor())

    if "--doctor-fix" in sys.argv[1:]:
        from desktop_doctor import run_desktop_doctor_autofix

        raise SystemExit(run_desktop_doctor_autofix(assume_yes="--yes" in sys.argv[1:]))

    # Handle share URL scheme
    for arg in sys.argv[1:]:
        if arg.startswith("--share="):
            data_encoded = arg.split("=", 1)[1]
            try:
                game_data = decode_share_payload(data_encoded)
                print(f"\n[C] Shared Deal: {game_data.get('name', 'Unknown')}")
                print(
                    f"    Price: {game_data.get('price', 'N/A')} (was {game_data.get('price_original', 'N/A')})"
                )
                print(f"    Discount: {game_data.get('discount', 'N/A')}%")
                if game_data.get("min_hist"):
                    print(f"    Historical Low: {game_data['min_hist']}")
                print(
                    f"    URL: https://store.steampowered.com/app/{game_data.get('appid', '')}/"
                )
                return
            except Exception as e:
                print(f"Error parsing shared deal: {e}")
                return

    if len(sys.argv) >= 3 and sys.argv[1] == "--run-script":
        try:
            _run_embedded_script(sys.argv[2], sys.argv[3:])
        except (ValueError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2) from exc
        return

    if "--internal-web" in sys.argv:
        _run_internal_web_server()
        return

    proc = None
    keep_server_alive = False
    browser_fallback_opened = threading.Event()
    active_url = URL

    def _open_browser_fallback(reason: str) -> None:
        nonlocal keep_server_alive
        if browser_fallback_opened.is_set():
            return
        browser_fallback_opened.set()
        keep_server_alive = True
        print(FALLBACK_REASON_MESSAGES.get(reason, FALLBACK_REASON_MESSAGES["window-error"]))
        fallback_target = _fallback_url(reason, base_url=active_url)
        print(f"URL fallback: {fallback_target}")
        opened = False
        try:
            opened = webbrowser.open(fallback_target)
        except Exception as exc:
            print(f"No se pudo abrir el navegador automáticamente: {exc}")
        if not opened:
            print(f"Abre manualmente: {fallback_target}")

    # If a local server is already alive, reuse it instead of spawning another one.
    target = _resolve_server_target(PORT)
    active_url = str(target["active_url"])
    launch_port = target["launch_port"]
    discover_start_port = int(target["discover_start_port"])
    if bool(target["reuse_existing"]):
        pass
    else:
        if getattr(sys, "frozen", False):
            cmd = [
                sys.executable,
                "--internal-web",
                "--no-open",
                "--port",
                str(launch_port),
            ]
        else:
            web_script = ROOT / "steam_deals_web.py"
            cmd = [
                sys.executable,
                str(web_script),
                "--no-open",
                "--port",
                str(launch_port),
            ]
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=_build_child_process_env(frozen=getattr(sys, "frozen", False)),
        )

    try:
        discovered_url = _discover_live_url(discover_start_port, timeout=25.0)
        if not discovered_url:
            raise RuntimeError("No se pudo iniciar Steam Deals Web UI para desktop.")
        active_url = discovered_url

        if _should_force_web_fallback():
            _open_browser_fallback("forced-web-fallback")
            return

        try:
            import webview  # type: ignore[import-not-found]
        except Exception:
            # If native webview is unavailable, continue in browser mode.
            print("Fallo al importar pywebview/backend nativo:", flush=True)
            traceback.print_exc(file=sys.stdout)
            _open_browser_fallback("missing-webview")
            return

        window_started = threading.Event()

        def _browser_fallback() -> None:
            # Fallback UX: if native webview is slow/fails, open default browser.
            if not window_started.is_set():
                _open_browser_fallback("window-timeout")

        threading.Timer(4.0, _browser_fallback).start()

        webview.create_window(
            "Steam Tools",
            _desktop_window_url(active_url),
            width=1280,
            height=860,
            min_size=(1000, 700),
            js_api=DesktopClipboardApi(),
        )
        window_started.set()
        webview.start(debug=False)

    except Exception:
        print("Detalle del fallo de ventana nativa:", flush=True)
        traceback.print_exc(file=sys.stdout)
        _open_browser_fallback("window-error")

    finally:
        if proc and proc.poll() is None and not keep_server_alive:
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    main()
