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
import urllib.request
import webbrowser
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8080
URL = f"http://{HOST}:{PORT}"


def _wait_server(url: str, timeout: float = 15.0) -> bool:
    start = time.monotonic()
    while (time.monotonic() - start) < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.5):
                return True
        except Exception:
            time.sleep(0.2)
    return False


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


def main() -> None:
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        print(
            "Uso: python steam_tools_desktop.py [--share=BASE64] "
            "[--internal-web] [--run-script <script> [args...]]"
        )
        print("\nOpciones:")
        print("  -h, --help            Muestra esta ayuda y sale")
        print("  --share=BASE64        Abre/parsea un deal compartido")
        print("  --internal-web        Ejecuta el servidor web embebido")
        print("  --run-script FILE ... Ejecuta script embebido con argumentos")
        return

    # Handle share URL scheme
    for arg in sys.argv[1:]:
        if arg.startswith("--share="):
            data_encoded = arg.split("=", 1)[1]
            try:
                import base64
                import json

                game_data = json.loads(base64.b64decode(data_encoded).decode("utf-8"))
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

    # If a local server is already alive, reuse it instead of spawning another one.
    if not _wait_server(URL, timeout=0.6):
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--internal-web", "--no-open", "--port", str(PORT)]
        else:
            web_script = ROOT / "steam_deals_web.py"
            cmd = [sys.executable, str(web_script), "--no-open", "--port", str(PORT)]
        proc = subprocess.Popen(cmd, cwd=str(ROOT))

    try:
        if not _wait_server(URL, timeout=25.0):
            raise RuntimeError("No se pudo iniciar Steam Deals Web UI para desktop.")

        try:
            import webview  # type: ignore[import-not-found]
        except Exception as exc:
            # If native webview is unavailable, continue in browser mode.
            webbrowser.open(URL)
            keep_server_alive = True
            return

        window_started = threading.Event()

        def _browser_fallback() -> None:
            # Fallback UX: if native webview is slow/fails, open default browser.
            if not window_started.is_set():
                webbrowser.open(URL)

        threading.Timer(4.0, _browser_fallback).start()

        webview.create_window(
            "Steam Tools",
            URL,
            width=1280,
            height=860,
            min_size=(1000, 700),
        )
        window_started.set()
        webview.start(debug=False)

    except Exception:
        webbrowser.open(URL)
        keep_server_alive = True

    finally:
        if proc and proc.poll() is None and not keep_server_alive:
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    main()
