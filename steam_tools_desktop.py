#!/usr/bin/env python3
"""Desktop launcher (Option B): Steam Tools in a native window via pywebview.

This is a first baseline for desktop packaging:
- Starts the local web server without opening an external browser
- Opens a native window using pywebview
- Stops the web server when the window closes
"""

from __future__ import annotations

from html.parser import HTMLParser
import os
import shlex
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

from share_payload import decode_share_payload as _decode_share_payload
from steam_deals_paths import build_persistent_runtime_env


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8080
PORT_SCAN_SIZE = 10
URL = f"http://{HOST}:{PORT}"
FORCE_WEB_FALLBACK_ENV = "STEAM_TOOLS_FORCE_WEB_FALLBACK"
FORCE_WEB_FALLBACK_FLAG = "--force-web-fallback"
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
LOCAL_TOKEN_META_NAME = "steam-tools-local-token"
LOCAL_CSRF_HEADER_NAME = "X-Steam-Tools-Local-Token"
STOP_REQUEST_TIMEOUT_SECONDS = 1.5

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


class _LocalSessionTokenParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.token = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        if self.token or tag.lower() != "meta":
            return
        attr_map = {
            str(name).lower(): str(value or "")
            for name, value in attrs
        }
        if attr_map.get("name", "").lower() == LOCAL_TOKEN_META_NAME:
            self.token = attr_map.get("content", "")


def _extract_local_session_token(html_text: object) -> str:
    parser = _LocalSessionTokenParser()
    try:
        parser.feed(str(html_text or ""))
    except Exception:
        return ""
    return parser.token.strip()


def _read_response_text(response: object) -> str:
    try:
        body = response.read()
    except Exception:
        return ""
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body or "")


def _desktop_server_origin(base_url: str) -> str:
    parsed = urllib.parse.urlparse(str(base_url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _request_stop_active_run(
    base_url: str,
    *,
    timeout: float = STOP_REQUEST_TIMEOUT_SECONDS,
    urlopen_fn=None,
    request_cls=urllib.request.Request,
) -> bool:
    origin = _desktop_server_origin(base_url)
    if not origin:
        return False

    urlopen = urllib.request.urlopen if urlopen_fn is None else urlopen_fn
    root_url = f"{origin}/"
    stop_url = f"{origin}/api/stop"
    parsed = urllib.parse.urlparse(origin)

    try:
        with urlopen(root_url, timeout=timeout) as response:
            token = _extract_local_session_token(_read_response_text(response))
        if not token:
            return False

        request = request_cls(
            stop_url,
            data=b"{}",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                LOCAL_CSRF_HEADER_NAME: token,
                "Origin": origin,
                "Referer": root_url,
                "Host": parsed.netloc,
            },
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is None and hasattr(response, "getcode"):
                status = response.getcode()
            return 200 <= int(status or 200) < 500
    except Exception:
        return False


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


def _is_linux_root_graphical_session(
    *,
    env: dict[str, str] | None = None,
    platform: str | None = None,
    geteuid_fn=None,
) -> bool:
    platform_name = sys.platform if platform is None else str(platform)
    if not platform_name.startswith("linux"):
        return False
    if geteuid_fn is None:
        geteuid_fn = getattr(os, "geteuid", lambda: -1)
    try:
        is_root = int(geteuid_fn()) == 0
    except Exception:
        is_root = False
    if not is_root:
        return False
    runtime_env = os.environ if env is None else env
    return any(runtime_env.get(name) for name in ("DISPLAY", "WAYLAND_DISPLAY"))


def _xauthority_owner_name(
    *,
    env: dict[str, str] | None = None,
    stat_fn=None,
    getpwuid_fn=None,
) -> str:
    runtime_env = os.environ if env is None else env
    xauthority = str(runtime_env.get("XAUTHORITY") or "").strip()
    if xauthority:
        stat_fn = os.stat if stat_fn is None else stat_fn
        try:
            xauthority_uid = int(stat_fn(xauthority).st_uid)
        except Exception:
            xauthority_uid = None
        if xauthority_uid is not None and xauthority_uid != 0:
            try:
                if getpwuid_fn is None:
                    import pwd

                    getpwuid_fn = pwd.getpwuid
                return str(getpwuid_fn(xauthority_uid).pw_name or "").strip()
            except Exception:
                return ""
    sudo_user = str(runtime_env.get("SUDO_USER") or "").strip()
    if sudo_user and sudo_user != "root":
        return sudo_user
    return ""


def _linux_root_graphical_session_warning(
    *,
    env: dict[str, str] | None = None,
    platform: str | None = None,
    geteuid_fn=None,
    stat_fn=None,
) -> str:
    runtime_env = os.environ if env is None else env
    if not _is_linux_root_graphical_session(
        env=runtime_env,
        platform=platform,
        geteuid_fn=geteuid_fn,
    ):
        return ""

    lines = [
        "Aviso: Steam Tools Desktop se esta ejecutando como root en una sesion grafica.",
        "El navegador fallback/Qt puede fallar si la sesion grafica pertenece al usuario normal.",
        "Ejecuta la UI como usuario grafico no-root, por ejemplo: .venv/bin/python steam_tools_desktop.py",
    ]
    xauthority = str(runtime_env.get("XAUTHORITY") or "").strip()
    if xauthority:
        stat_fn = os.stat if stat_fn is None else stat_fn
        try:
            xauthority_uid = int(stat_fn(xauthority).st_uid)
        except Exception:
            xauthority_uid = None
        if xauthority_uid is not None and xauthority_uid != 0:
            lines.append(
                "$XAUTHORITY pertenece a otro usuario; evita sudo/root para abrir la UI desktop."
            )
    return "\n".join(lines)


def _linux_root_browser_manual_hint(
    fallback_target: str,
    *,
    env: dict[str, str] | None = None,
    platform: str | None = None,
    geteuid_fn=None,
    stat_fn=None,
    getpwuid_fn=None,
) -> str:
    runtime_env = os.environ if env is None else env
    if not _is_linux_root_graphical_session(
        env=runtime_env,
        platform=platform,
        geteuid_fn=geteuid_fn,
    ):
        return ""
    lines = [
        "No se intento abrir el navegador automaticamente porque el launcher corre como root en una sesion grafica.",
        f"Abre manualmente: {fallback_target}",
    ]
    owner_name = _xauthority_owner_name(
        env=runtime_env,
        stat_fn=stat_fn,
        getpwuid_fn=getpwuid_fn,
    )
    if owner_name:
        lines.append(
            "Opcional desde root: "
            f"runuser -u {shlex.quote(owner_name)} -- xdg-open {shlex.quote(fallback_target)}"
        )
    return "\n".join(lines)


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


def _set_ctypes_signature(function, *, restype=None, argtypes=None) -> None:
    try:
        if restype is not None:
            function.restype = restype
        if argtypes is not None:
            function.argtypes = argtypes
    except Exception:
        return


def copy_text_to_windows_clipboard(
    text: str,
    *,
    ctypes_module=None,
    platform: str | None = None,
) -> str:
    platform_name = sys.platform if platform is None else str(platform)
    if not platform_name.startswith("win"):
        raise RuntimeError("Clipboard nativo Windows no disponible.")
    if ctypes_module is None:
        import ctypes as ctypes_module

    user32 = ctypes_module.windll.user32
    kernel32 = ctypes_module.windll.kernel32
    _set_ctypes_signature(
        user32.OpenClipboard,
        restype=getattr(ctypes_module, "c_bool", None),
        argtypes=[getattr(ctypes_module, "c_void_p", object)],
    )
    _set_ctypes_signature(user32.EmptyClipboard, restype=getattr(ctypes_module, "c_bool", None))
    _set_ctypes_signature(
        user32.SetClipboardData,
        restype=getattr(ctypes_module, "c_void_p", None),
        argtypes=[getattr(ctypes_module, "c_uint", object), getattr(ctypes_module, "c_void_p", object)],
    )
    _set_ctypes_signature(user32.CloseClipboard, restype=getattr(ctypes_module, "c_bool", None))
    _set_ctypes_signature(
        kernel32.GlobalAlloc,
        restype=getattr(ctypes_module, "c_void_p", None),
        argtypes=[getattr(ctypes_module, "c_uint", object), getattr(ctypes_module, "c_size_t", object)],
    )
    _set_ctypes_signature(
        kernel32.GlobalLock,
        restype=getattr(ctypes_module, "c_void_p", None),
        argtypes=[getattr(ctypes_module, "c_void_p", object)],
    )
    _set_ctypes_signature(
        kernel32.GlobalUnlock,
        restype=getattr(ctypes_module, "c_bool", None),
        argtypes=[getattr(ctypes_module, "c_void_p", object)],
    )
    _set_ctypes_signature(
        kernel32.GlobalFree,
        restype=getattr(ctypes_module, "c_void_p", None),
        argtypes=[getattr(ctypes_module, "c_void_p", object)],
    )

    payload = (str(text) + "\0").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
    if not handle:
        raise RuntimeError("Clipboard nativo Windows no disponible.")
    try:
        locked = kernel32.GlobalLock(handle)
        if not locked:
            raise RuntimeError("Clipboard nativo Windows no disponible.")
        try:
            ctypes_module.memmove(locked, payload, len(payload))
        finally:
            kernel32.GlobalUnlock(handle)

        if not user32.OpenClipboard(None):
            raise RuntimeError("Clipboard nativo Windows no disponible.")
        try:
            if not user32.EmptyClipboard():
                raise RuntimeError("Clipboard nativo Windows no disponible.")
            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                raise RuntimeError("Clipboard nativo Windows no disponible.")
            handle = None
        finally:
            user32.CloseClipboard()
    finally:
        if handle:
            kernel32.GlobalFree(handle)
    return "windows"


def copy_text_to_native_clipboard(
    text: str,
    *,
    platform: str | None = None,
    windows_copy_fn=copy_text_to_windows_clipboard,
    qt_copy_fn=copy_text_to_qt_clipboard,
) -> str:
    platform_name = sys.platform if platform is None else str(platform)
    if platform_name.startswith("win"):
        return windows_copy_fn(text)
    return qt_copy_fn(text)


class DesktopClipboardApi:
    def __init__(self, *, copy_text_fn=copy_text_to_native_clipboard):
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
    return _decode_share_payload(data_encoded)


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
                steam_url = game_data.get("steam_url") or game_data.get("url")
                if not steam_url:
                    steam_url = f"https://store.steampowered.com/app/{game_data.get('appid', '')}/"
                print(f"    URL: {steam_url}")
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
        root_warning = _linux_root_graphical_session_warning()
        if root_warning:
            print(root_warning)
        fallback_target = _fallback_url(reason, base_url=active_url)
        print(f"URL fallback: {fallback_target}")
        manual_hint = _linux_root_browser_manual_hint(fallback_target)
        if manual_hint:
            print(manual_hint)
            return
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
            _request_stop_active_run(active_url)
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    main()
