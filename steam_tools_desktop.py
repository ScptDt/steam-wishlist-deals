#!/usr/bin/env python3
"""Desktop launcher (Option B): Steam Tools in a native window via pywebview.

This is a first baseline for desktop packaging:
- Starts the local web server without opening an external browser
- Opens a native window using pywebview
- Stops the web server when the window closes
"""

from __future__ import annotations

import subprocess
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


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8080
PORT_SCAN_SIZE = 10
URL = f"http://{HOST}:{PORT}"

FALLBACK_REASON_MESSAGES = {
    "missing-webview": "pywebview o su backend nativo no estan disponibles. Abriendo Steam Tools en el navegador.",
    "window-timeout": "La ventana nativa no respondio a tiempo. Abriendo Steam Tools en el navegador.",
    "window-error": "La ventana nativa fallo al iniciar. Abriendo Steam Tools en el navegador.",
}


def _fallback_url(reason: str | None = None, *, base_url: str = URL) -> str:
    if not reason:
        return base_url
    query = urlencode({"desktop_fallback": "1", "reason": reason})
    return f"{base_url}?{query}"


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


def _run_embedded_script(script_name: str, script_args: list[str]) -> None:
    base = Path(getattr(sys, "_MEIPASS", ROOT))
    script_path = base / script_name
    if not script_path.exists():
        raise RuntimeError(f"No se encontró script embebido: {script_name}")

    prev_argv = sys.argv[:]
    try:
        sys.argv = [str(script_path), *script_args]
        runpy.run_path(str(script_path), run_name="__main__")
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
            "[--internal-web] [--doctor] [--doctor-fix] [--yes] [--run-script <script> [args...]]"
        )
        print("\nOpciones:")
        print("  -h, --help            Muestra esta ayuda y sale")
        print("  --share=BASE64        Abre/parsea un deal compartido")
        print("  --internal-web        Ejecuta el servidor web embebido")
        print("  --doctor              Ejecuta checks read-only de readiness desktop")
        print("  --doctor-fix          Aplica autofixes seguros (con confirmacion)")
        print("  --yes                 Omite prompt interactivo para --doctor-fix")
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
        _run_embedded_script(sys.argv[2], sys.argv[3:])
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
        opened = False
        try:
            opened = webbrowser.open(fallback_target)
        except Exception as exc:
            print(f"No se pudo abrir el navegador automáticamente: {exc}")
        if not opened:
            print(f"Abre manualmente: {fallback_target}")

    # If a local server is already alive, reuse it instead of spawning another one.
    reused_url = _discover_live_url(PORT, timeout=0.6)
    if reused_url is not None:
        active_url = reused_url
    else:
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--internal-web", "--no-open", "--port", str(PORT)]
        else:
            web_script = ROOT / "steam_deals_web.py"
            cmd = [sys.executable, str(web_script), "--no-open", "--port", str(PORT)]
        proc = subprocess.Popen(cmd, cwd=str(ROOT))

    try:
        discovered_url = _discover_live_url(PORT, timeout=25.0)
        if not discovered_url:
            raise RuntimeError("No se pudo iniciar Steam Deals Web UI para desktop.")
        active_url = discovered_url

        try:
            import webview  # type: ignore[import-not-found]
        except Exception:
            # If native webview is unavailable, continue in browser mode.
            print("Fallo al importar pywebview/backend nativo:")
            traceback.print_exc()
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
            active_url,
            width=1280,
            height=860,
            min_size=(1000, 700),
        )
        window_started.set()
        webview.start(debug=False)

    except Exception:
        print("Detalle del fallo de ventana nativa:")
        traceback.print_exc()
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
