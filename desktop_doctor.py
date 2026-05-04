#!/usr/bin/env python3
"""Desktop readiness checks and safe autofix helpers for local builds."""

from __future__ import annotations

import importlib
import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path

from steam_deals_paths import resolve_cache_dir, resolve_logs_dir


ROOT = Path(__file__).resolve().parent
APP_NAME = "SteamToolsDesktop"
STATUS_PREFIXES = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}
REQUIRED_BUILD_PACKAGES = ("shared", "renderers", "app")
REQUIRED_HIDDEN_IMPORTS = ("steam_deals_generator", "payday2_dlc_tracker")
REQUIRED_DATA_FILES = (
    "assets/steam_tools_icon.svg",
    "web/payday2/favicon.svg",
    "web/payday2/masks/heist_mask_blue.svg",
    "web/payday2/masks/heist_mask_gold.svg",
    "web/payday2/masks/heist_mask_red.svg",
    "web/payday2/masks/heist_mask_shadow.svg",
)
LINUX_QT_MODULES = (
    ("qtpy", "QtPy"),
    ("PyQt6", "PyQt6"),
    ("PyQt6.QtWebEngineWidgets", "PyQt6-WebEngine"),
)
LINUX_BUILD_TOOLS = ("ldd", "objdump", "objcopy")
MACOS_PYOBJC_MODULES = (
    ("objc", "PyObjC core"),
    ("Cocoa", "Cocoa"),
    ("WebKit", "WebKit"),
)
MACOS_BUILD_TOOLS = ("xcode-select", "codesign", "xattr")
WINDOWS_WEBVIEW2_HINT = "Instala Microsoft Edge WebView2 Runtime en la máquina destino."
SAFE_FIX_PREFIXES = {"run": "[fix]", "ok": "[done]", "skip": "[skip]"}


@dataclass(frozen=True)
class DoctorCheck:
    status: str
    title: str
    summary: str
    actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DoctorFix:
    fix_id: str
    title: str
    summary: str
    commands: tuple[str, ...] = ()


def is_virtualenv() -> bool:
    return bool(
        getattr(sys, "real_prefix", None)
        or sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    )


def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_pep668_marker() -> Path | None:
    stdlib = sysconfig.get_path("stdlib")
    if not stdlib:
        return None
    marker = Path(stdlib) / "EXTERNALLY-MANAGED"
    return marker if marker.exists() else None


def module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError, ModuleNotFoundError):
        return False


def command_available(command_name: str) -> bool:
    return shutil.which(command_name) is not None


def get_local_venv_dir() -> Path:
    return ROOT / ".venv"


def get_local_venv_python() -> Path:
    if os.name == "nt":
        return get_local_venv_dir() / "Scripts" / "python.exe"
    return get_local_venv_dir() / "bin" / "python"


def is_local_venv_active() -> bool:
    try:
        return Path(sys.prefix).resolve() == get_local_venv_dir().resolve()
    except OSError:
        return False


def format_command(parts: tuple[str, ...]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def get_revalidate_action() -> str:
    return "Revalida con `python steam_tools_desktop.py --doctor`."


def get_manual_launch_action() -> str:
    if sys.platform == "win32":
        return "Valida manualmente `dist\\SteamToolsDesktop.exe` desde Console o RDP interactivo."
    if sys.platform == "darwin":
        return "Valida manualmente `open dist/SteamToolsDesktop.app` desde una sesión gráfica local."
    return "Valida manualmente `./dist/SteamToolsDesktop` desde una sesión gráfica normal."


def get_linux_python_vs_system_action() -> str:
    return "Deps Python van en `.venv`; deps nativas Qt/WebEngine se instalan manualmente con el gestor de paquetes de tu distro."


def get_linux_xcb_action() -> str:
    return "Prueba temporalmente `export QT_QPA_PLATFORM=xcb` antes de relanzar el desktop si Wayland/Qt da problemas."


def get_windows_webview2_action() -> str:
    return "Verifica en Apps instaladas que exista `Microsoft Edge WebView2 Runtime`; si falta, instálalo manualmente desde Microsoft."


def build_fix_command_strings(fix_id: str) -> tuple[str, ...]:
    local_python = str(get_local_venv_python())
    commands = {
        "create-local-venv": (
            format_command((sys.executable, "-m", "venv", str(get_local_venv_dir()))),
        ),
        "install-local-desktop-deps": (
            format_command((local_python, "-m", "pip", "install", "-r", str(ROOT / "requirements-desktop.txt"))),
        ),
        "build-desktop-artifact": (
            format_command((local_python, str(ROOT / "build_desktop.py"), "--skip-install")),
        ),
    }
    return commands.get(fix_id, ())


def get_check_status_map(checks: list[DoctorCheck]) -> dict[str, str]:
    return {check.title: check.status for check in checks}


def should_offer_local_venv_creation(check_statuses: dict[str, str]) -> bool:
    if is_frozen_runtime():
        return False
    if get_local_venv_python().exists() or is_local_venv_active():
        return False
    return check_statuses.get("Entorno Python") in {"warn", "fail"} or not is_virtualenv()


def should_offer_local_requirements_install(check_statuses: dict[str, str]) -> bool:
    relevant_titles = {
        "Entorno Python",
        "pywebview",
        "Backend nativo Linux (Qt)",
        "PyInstaller",
    }
    if not get_local_venv_python().exists():
        return should_offer_local_venv_creation(check_statuses)
    return any(check_statuses.get(title) in {"warn", "fail"} for title in relevant_titles)


def should_offer_desktop_build(check_statuses: dict[str, str]) -> bool:
    if get_platform_artifact().exists():
        return False
    if is_frozen_runtime():
        return False
    if check_statuses.get("Módulos locales críticos") == "fail":
        return False
    if check_statuses.get("Config build PyInstaller") == "fail":
        return False
    return True


def import_error(module_name: str) -> str | None:
    try:
        importlib.import_module(module_name)
        return None
    except Exception as exc:  # pragma: no cover - exercised via doctor runs
        return f"{exc.__class__.__name__}: {exc}"


def get_platform_artifact() -> Path:
    if sys.platform == "win32":
        return ROOT / "dist" / f"{APP_NAME}.exe"
    if sys.platform == "darwin":
        return ROOT / "dist" / f"{APP_NAME}.app"
    return ROOT / "dist" / APP_NAME


def check_python_environment() -> DoctorCheck:
    if is_frozen_runtime():
        return DoctorCheck(
            "ok",
            "Entorno Python",
            "Runtime Python embebido en el binario; los checks de .venv/PEP 668 no aplican.",
        )

    marker = get_pep668_marker()
    if sys.platform.startswith("linux") and marker and not is_virtualenv():
        return DoctorCheck(
            "warn",
            "Entorno Python",
            "Python del sistema con PEP 668 detectado fuera de .venv; pip global puede fallar para deps desktop.",
            (
                "python3 -m venv .venv",
                "source .venv/bin/activate",
                "python -m pip install -r requirements-desktop.txt",
                "Evita `--break-system-packages` salvo en entornos desechables.",
                get_revalidate_action(),
            ),
        )
    if is_virtualenv():
        return DoctorCheck(
            "ok",
            "Entorno Python",
            f"Entorno virtual activo: {sys.prefix}",
        )
    return DoctorCheck(
        "ok",
        "Entorno Python",
        "No se detecta bloqueo PEP 668 para este Python.",
    )


def check_local_modules() -> DoctorCheck:
    critical_modules = ("steam_deals_web", "steam_deals_generator")
    failures = []
    for module_name in critical_modules:
        error = import_error(module_name)
        if error:
            failures.append(f"{module_name}: {error}")
    if failures:
        return DoctorCheck(
            "fail",
            "Módulos locales críticos",
            "No se pudieron importar todos los módulos desktop/web requeridos.",
            tuple(failures),
        )
    return DoctorCheck(
        "ok",
        "Módulos locales críticos",
        "steam_deals_web.py y steam_deals_generator.py importan correctamente.",
    )


def check_pywebview_stack() -> DoctorCheck:
    if is_frozen_runtime():
        return DoctorCheck(
            "ok",
            "pywebview",
            "Chequeo de paquete source omitido: el binario frozen ya usa el runtime desktop empaquetado.",
        )

    if not module_available("webview"):
        actions = ["python -m pip install -r requirements-desktop.txt", get_revalidate_action()]
        if sys.platform.startswith("linux"):
            actions.insert(1, get_linux_python_vs_system_action())
        elif sys.platform == "darwin":
            actions.insert(1, "En macOS el backend nativo esperado es Cocoa/PyObjC; si falla el runtime, valida también `objc`, `Cocoa` y `WebKit`.")
            actions.append("Luego abre `dist/SteamToolsDesktop.app` desde Finder o con `open`.")
        elif sys.platform == "win32":
            actions.insert(1, get_windows_webview2_action())
        return DoctorCheck(
            "fail",
            "pywebview",
            "pywebview no está disponible en este entorno Python.",
            tuple(actions),
        )
    if not sys.platform.startswith("linux"):
        return DoctorCheck(
            "ok",
            "pywebview",
            "pywebview está disponible para runtime desktop.",
        )
    missing = [label for module_name, label in LINUX_QT_MODULES if not module_available(module_name)]
    if missing:
        return DoctorCheck(
            "fail",
            "Backend nativo Linux (Qt)",
            "Faltan módulos Python del backend Qt esperado para Linux.",
            (
                "python -m pip install -r requirements-desktop.txt",
                get_linux_python_vs_system_action(),
                f"Pendientes: {', '.join(missing)}",
                "Revalida imports con `python -c 'import qtpy, PyQt6, PyQt6.QtWebEngineWidgets'`.",
                get_manual_launch_action(),
                get_revalidate_action(),
            ),
        )
    return DoctorCheck(
        "ok",
        "Backend nativo Linux (Qt)",
        "QtPy + PyQt6 + PyQt6-WebEngine detectados.",
    )


def check_linux_build_host_tools() -> DoctorCheck | None:
    if not sys.platform.startswith("linux"):
        return None
    if is_frozen_runtime():
        return None
    missing = [tool for tool in LINUX_BUILD_TOOLS if not command_available(tool)]
    if missing:
        return DoctorCheck(
            "fail",
            "Host tools Linux para PyInstaller",
            "Faltan utilidades base que PyInstaller usa para analizar y empaquetar binarios en Linux.",
            (
                f"Pendientes: {', '.join(missing)}",
                "Instala manualmente los equivalentes de `binutils` / utilidades base de glibc en tu distro.",
                "Ejemplo Ubuntu/Debian: `sudo apt install binutils libc-bin`.",
                "Luego reintenta `python build_desktop.py`.",
                get_revalidate_action(),
            ),
        )
    return DoctorCheck(
        "ok",
        "Host tools Linux para PyInstaller",
        "ldd + objdump + objcopy detectados para builds Linux.",
    )


def check_linux_display_stack() -> DoctorCheck | None:
    if not sys.platform.startswith("linux"):
        return None
    session_type = (os.environ.get("XDG_SESSION_TYPE") or "").strip().lower()
    qt_qpa = (os.environ.get("QT_QPA_PLATFORM") or "").strip().lower()
    if session_type == "x11":
        return DoctorCheck(
            "ok",
            "Display stack Linux",
            "Sesión X11 detectada.",
        )
    if session_type == "wayland" and qt_qpa == "xcb":
        return DoctorCheck(
            "ok",
            "Display stack Linux",
            "Wayland detectado con `QT_QPA_PLATFORM=xcb`, workaround útil para Qt/pywebview en algunos entornos.",
        )
    if session_type == "wayland" and not qt_qpa:
        return DoctorCheck(
            "warn",
            "Display stack Linux",
            "Sesión Wayland detectada sin `QT_QPA_PLATFORM` explícito; algunos entornos Qt/pywebview abren mejor forzando X11/xcb.",
            (
                get_linux_xcb_action(),
                "Relanza `python steam_tools_desktop.py` desde tu usuario gráfico normal para validar la ventana nativa.",
                "Si sigue fallando, revisa paquetes Qt/WebEngine de tu distro o usa el fallback web en navegador.",
                get_revalidate_action(),
            ),
        )
    if session_type == "wayland":
        return DoctorCheck(
            "ok",
            "Display stack Linux",
            f"Wayland detectado con `QT_QPA_PLATFORM={qt_qpa}`.",
        )
    if (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and not session_type:
        return DoctorCheck(
            "warn",
            "Display stack Linux",
            "Hay señales de sesión gráfica, pero `XDG_SESSION_TYPE` no está definido; si Qt/pywebview falla, trata el entorno como Wayland/X11 ambiguo.",
            (
                get_linux_xcb_action(),
                "Valida el artefacto final desde una sesión gráfica normal con tu usuario real.",
                get_revalidate_action(),
            ),
        )
    return None


def check_pyinstaller_tool() -> DoctorCheck:
    if is_frozen_runtime():
        return DoctorCheck(
            "ok",
            "PyInstaller",
            "No se requiere tener PyInstaller instalado para ejecutar este binario empaquetado.",
        )

    if module_available("PyInstaller"):
        return DoctorCheck(
            "ok",
            "PyInstaller",
            "PyInstaller está disponible para builds desktop.",
        )
    return DoctorCheck(
        "warn",
        "PyInstaller",
        "PyInstaller no está disponible; podrás correr desktop source pero no empaquetar el binario.",
        (
            "python -m pip install -r requirements-desktop.txt",
            "Para builds reproducibles, usa siempre la `.venv` del proyecto en vez del Python global.",
            "Después ejecuta `python build_desktop.py`.",
            get_revalidate_action(),
        ),
    )


def check_build_configuration() -> DoctorCheck:
    if is_frozen_runtime():
        return DoctorCheck(
            "ok",
            "Config build PyInstaller",
            "Chequeo de fuente omitido dentro del artefacto empaquetado.",
        )
    try:
        import build_desktop
    except Exception as exc:
        return DoctorCheck(
            "fail",
            "Config build PyInstaller",
            f"No se pudo cargar build_desktop.py: {exc}",
            ("python -m py_compile build_desktop.py",),
        )

    missing_packages = [
        name
        for name in REQUIRED_BUILD_PACKAGES
        if name not in set(getattr(build_desktop, "COLLECT_SUBMODULE_PACKAGES", []))
    ]
    missing_hidden = [
        name
        for name in REQUIRED_HIDDEN_IMPORTS
        if name not in set(getattr(build_desktop, "HIDDEN_IMPORTS", []))
    ]
    data_sources = {src for src, _dest in getattr(build_desktop, "DATA_FILES", [])}
    missing_data = [name for name in REQUIRED_DATA_FILES if name not in data_sources]
    if missing_packages or missing_hidden or missing_data:
        details = []
        if missing_packages:
            details.append(f"collect-submodules faltantes: {', '.join(missing_packages)}")
        if missing_hidden:
            details.append(f"hidden imports faltantes: {', '.join(missing_hidden)}")
        if missing_data:
            details.append(f"assets web faltantes: {', '.join(missing_data)}")
        return DoctorCheck(
            "warn",
            "Config build PyInstaller",
            "La configuración de packaging no refleja todos los guardrails conocidos del repo.",
            tuple(details),
        )
    return DoctorCheck(
        "ok",
        "Config build PyInstaller",
        "build_desktop.py incluye paths, hidden imports y collect_submodules esperados.",
    )


def check_macos_backend_runtime() -> DoctorCheck | None:
    if sys.platform != "darwin":
        return None
    if is_frozen_runtime():
        return DoctorCheck(
            "ok",
            "Backend nativo macOS",
            "Chequeo source de PyObjC omitido dentro del binario frozen.",
        )
    missing = [label for module_name, label in MACOS_PYOBJC_MODULES if not module_available(module_name)]
    if missing:
        return DoctorCheck(
            "warn",
            "Backend nativo macOS",
            "No se detectan todos los módulos PyObjC esperados para Cocoa/WKWebView.",
            (
                "python -m pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit",
                "pywebview usa Cocoa/PyObjC como ruta nativa por defecto en macOS; esto es distinto al backend Qt de Linux.",
                f"Pendientes: {', '.join(missing)}",
                "Revalida imports con `python -c 'import objc, Cocoa, WebKit'`.",
                "Después abre `dist/SteamToolsDesktop.app` desde Finder o con `open`.",
                get_revalidate_action(),
            ),
        )
    return DoctorCheck(
        "ok",
        "Backend nativo macOS",
        "PyObjC/Cocoa/WebKit detectados para runtime nativo macOS.",
    )


def check_macos_build_tools() -> DoctorCheck | None:
    if sys.platform != "darwin":
        return None
    if is_frozen_runtime():
        return None
    missing = [tool for tool in MACOS_BUILD_TOOLS if not command_available(tool)]
    if missing:
        return DoctorCheck(
            "warn",
            "Tooling macOS local",
            "Faltan utilidades típicas de build/distribución local en macOS.",
            (
                f"Pendientes: {', '.join(missing)}",
                "xcode-select --install",
                "`codesign` y `xattr` ayudan a validar firma/cuarentena, pero el doctor no automatiza esos pasos.",
                get_manual_launch_action(),
                get_revalidate_action(),
            ),
        )
    return DoctorCheck(
        "ok",
        "Tooling macOS local",
        "xcode-select + codesign + xattr disponibles para validación local/distribución.",
    )


def check_macos_session_mode() -> DoctorCheck | None:
    if sys.platform != "darwin":
        return None
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        return DoctorCheck(
            "warn",
            "Sesión macOS",
            "macOS detectado por SSH/headless; el doctor sirve, pero la apertura real de la `.app` debe validarse desde una sesión gráfica local.",
            (
                "No tomes una sesión SSH como validación final de UX nativa.",
                "Abre la `.app` desde Finder o con `open dist/SteamToolsDesktop.app` en una sesión local.",
                "Si Gatekeeper bloquea la app, inspecciona atributos con `xattr -l dist/SteamToolsDesktop.app` antes de tocar cuarentena manualmente.",
                get_revalidate_action(),
            ),
        )
    return DoctorCheck(
        "ok",
        "Sesión macOS",
        "No se detecta una sesión macOS remota/headless obvia.",
    )


def check_session_environment() -> DoctorCheck:
    display = os.environ.get("DISPLAY")
    wayland = os.environ.get("WAYLAND_DISPLAY")
    if sys.platform.startswith("linux") and not display and not wayland:
        return DoctorCheck(
            "warn",
            "Sesión gráfica",
            "No se detecta DISPLAY/WAYLAND; este entorno sirve para build/doctor pero no para validar ventana nativa.",
            (
                "Abre una sesión gráfica normal para validar pywebview.",
                "Si solo quieres comprobar la UI web, usa `python steam_deals_web.py --no-open --port 8080` y abre el navegador manualmente.",
                get_manual_launch_action(),
                get_revalidate_action(),
            ),
        )
    if hasattr(os, "geteuid") and os.geteuid() == 0 and (display or wayland):
        return DoctorCheck(
            "warn",
            "Usuario/Sesión gráfica",
            "Estás validando desktop desde root con display activo; navegador, pywebview o PyInstaller pueden comportarse distinto.",
            (
                "Usa un usuario normal para validar ventana nativa.",
                "Si automatizas, prefiere runuser/su hacia tu usuario real.",
                "No cierres el pendiente de UX nativa basándote solo en una sesión root.",
                get_revalidate_action(),
            ),
        )
    return DoctorCheck(
        "ok",
        "Sesión gráfica",
        "No se detectan bloqueos obvios de usuario/display para validación local.",
    )


def check_windows_webview2_runtime() -> DoctorCheck | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg  # type: ignore[attr-defined]
    except Exception:
        return DoctorCheck(
            "warn",
            "Windows WebView2 Runtime",
            "No se pudo inspeccionar el registro de Windows para WebView2; valida manualmente el runtime nativo.",
            (
                WINDOWS_WEBVIEW2_HINT,
                get_windows_webview2_action(),
                r"Luego prueba `dist\SteamToolsDesktop.exe` en una sesión interactiva.",
                get_revalidate_action(),
            ),
        )

    registry_roots = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    try:
        for root_key, subkey in registry_roots:
            with winreg.OpenKey(root_key, subkey) as uninstall_root:
                for index in range(winreg.QueryInfoKey(uninstall_root)[0]):
                    child_name = winreg.EnumKey(uninstall_root, index)
                    with winreg.OpenKey(uninstall_root, child_name) as child_key:
                        try:
                            display_name = str(winreg.QueryValueEx(child_key, "DisplayName")[0])
                        except OSError:
                            continue
                        if "webview2" in display_name.lower():
                            return DoctorCheck(
                                "ok",
                                "Windows WebView2 Runtime",
                                f"Runtime detectado: {display_name}",
                            )
    except OSError:
        return DoctorCheck(
            "warn",
            "Windows WebView2 Runtime",
            "No se pudo completar la inspección del registro para WebView2.",
            (
                WINDOWS_WEBVIEW2_HINT,
                get_windows_webview2_action(),
                get_revalidate_action(),
            ),
        )

    return DoctorCheck(
        "warn",
        "Windows WebView2 Runtime",
        "No se detectó WebView2 Runtime en el registro; el launcher podría caer a navegador o no abrir backend nativo.",
        (
            WINDOWS_WEBVIEW2_HINT,
            get_windows_webview2_action(),
            "Si falta backend nativo, espera fallback a navegador como ruta temporal, no como validación final del desktop.",
            get_revalidate_action(),
        ),
    )


def check_windows_session_mode() -> DoctorCheck | None:
    if sys.platform != "win32":
        return None
    session_name = (os.environ.get("SESSIONNAME") or "").strip()
    if session_name.lower().startswith("service"):
        return DoctorCheck(
            "warn",
            "Sesión Windows",
            "Windows parece correr en una sesión de servicio/no interactiva; la ventana nativa debe validarse desde Console o RDP interactivo.",
            (
                r"Valida `dist\SteamToolsDesktop.exe` desde Console o RDP interactivo, no como servicio.",
                "Si solo necesitas comprobar fallback web, valida también la Web UI por separado.",
                get_revalidate_action(),
            ),
        )
    if session_name:
        return DoctorCheck(
            "ok",
            "Sesión Windows",
            f"Sesión Windows detectada: {session_name}",
        )
    return None


def check_artifact_presence() -> DoctorCheck:
    if is_frozen_runtime():
        return DoctorCheck(
            "ok",
            "Artefacto desktop",
            "Ejecutando desde el artefacto desktop empaquetado.",
        )

    artifact = get_platform_artifact()
    if artifact.exists():
        return DoctorCheck(
            "ok",
            "Artefacto desktop",
            f"Artefacto presente: {artifact}",
        )
    return DoctorCheck(
        "warn",
        "Artefacto desktop",
        "Aún no hay artefacto generado para esta plataforma.",
        (
            "python build_desktop.py",
            get_manual_launch_action(),
            get_revalidate_action(),
        ),
    )


def check_known_build_warnings() -> DoctorCheck:
    warning_file = ROOT / "build" / APP_NAME / f"warn-{APP_NAME}.txt"
    if not warning_file.exists():
        return DoctorCheck(
            "ok",
            "Warnings del último build",
            "No hay log de warnings de build para revisar todavía.",
        )
    warning_text = warning_file.read_text(encoding="utf-8", errors="replace")
    if "libtiff.so.5" in warning_text:
        return DoctorCheck(
            "warn",
            "Warnings del último build",
            "El último build reportó `libtiff.so.5` ausente en plugins Qt de PyInstaller.",
            (
                f"Revisa {warning_file}",
                "Si el runtime gráfico falla con plugins de imagen, instala/ajusta la librería TIFF de tu distro.",
                "Repite luego la validación manual del artefacto desktop desde tu sesión gráfica normal.",
                get_revalidate_action(),
            ),
        )
    return DoctorCheck(
        "ok",
        "Warnings del último build",
        "Sin warnings conocidos del último build en disco.",
    )


def _path_is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except (OSError, ValueError):
        return False


def check_frozen_runtime() -> DoctorCheck | None:
    if not is_frozen_runtime():
        return None
    if getattr(sys, "_MEIPASS", None):
        return DoctorCheck(
            "ok",
            "Runtime frozen",
            "PyInstaller frozen detectado; `_MEIPASS` se trata solo como raíz de recursos temporales.",
        )
    return DoctorCheck(
        "warn",
        "Runtime frozen",
        "`sys.frozen` está activo pero no se detecta `_MEIPASS`; valida manualmente el empaquetado.",
        (get_manual_launch_action(),),
    )


def check_frozen_runtime_storage() -> DoctorCheck | None:
    if not is_frozen_runtime():
        return None
    cache_dir = resolve_cache_dir(ROOT, frozen=True)
    logs_dir = resolve_logs_dir(ROOT, frozen=True)
    mei_root = getattr(sys, "_MEIPASS", None)
    if mei_root:
        mei_path = Path(mei_root)
        if _path_is_inside(cache_dir, mei_path) or _path_is_inside(logs_dir, mei_path):
            return DoctorCheck(
                "fail",
                "Cache/logs persistentes",
                "Cache o logs apuntan dentro de `_MEIPASS`; el binario perdería datos al cerrar.",
                (
                    "Quita overrides que apunten a `_MEIPASS`.",
                    "Usa una carpeta persistente de usuario para `STEAM_DEALS_CACHE_DIR` y `STEAM_DEALS_LOG_DIR`.",
                ),
            )
    return DoctorCheck(
        "ok",
        "Cache/logs persistentes",
        "Defaults frozen resuelven fuera de `_MEIPASS` en una ubicación persistente de usuario.",
    )


def get_platform_specific_checks() -> list[DoctorCheck]:
    maybe_checks = [
        check_linux_build_host_tools(),
        check_linux_display_stack(),
        check_macos_backend_runtime(),
        check_macos_build_tools(),
        check_macos_session_mode(),
        check_windows_webview2_runtime(),
        check_windows_session_mode(),
    ]
    return [check for check in maybe_checks if check is not None]


def get_desktop_doctor_fixes(checks: list[DoctorCheck] | None = None) -> list[DoctorFix]:
    current_checks = checks or get_desktop_doctor_checks()
    check_statuses = get_check_status_map(current_checks)
    fixes: list[DoctorFix] = []

    if should_offer_local_venv_creation(check_statuses):
        fixes.append(
            DoctorFix(
                "create-local-venv",
                "Crear `.venv` local del proyecto",
                "Prepara un entorno virtual aislado dentro del repo para evitar usar el Python global del sistema.",
                build_fix_command_strings("create-local-venv"),
            )
        )

    if should_offer_local_requirements_install(check_statuses):
        fixes.append(
            DoctorFix(
                "install-local-desktop-deps",
                "Instalar deps desktop en `.venv`",
                "Ejecuta `requirements-desktop.txt` dentro de la `.venv` local para dejar `pywebview` + `PyInstaller` listos sin tocar paquetes del sistema.",
                build_fix_command_strings("install-local-desktop-deps"),
            )
        )

    if should_offer_desktop_build(check_statuses):
        fixes.append(
            DoctorFix(
                "build-desktop-artifact",
                "Generar artefacto desktop",
                "Lanza `build_desktop.py` usando la `.venv` local preparada para dejar `dist/` listo.",
                build_fix_command_strings("build-desktop-artifact"),
            )
        )

    return fixes


def get_desktop_doctor_checks() -> list[DoctorCheck]:
    frozen_checks = [
        check
        for check in (check_frozen_runtime(), check_frozen_runtime_storage())
        if check is not None
    ]
    return [
        *frozen_checks,
        check_python_environment(),
        check_local_modules(),
        check_pywebview_stack(),
        check_pyinstaller_tool(),
        check_build_configuration(),
        check_session_environment(),
        check_artifact_presence(),
        check_known_build_warnings(),
        *get_platform_specific_checks(),
    ]


def render_check(check: DoctorCheck, emit) -> None:
    emit(f"{STATUS_PREFIXES[check.status]} {check.title}: {check.summary}")
    for action in check.actions:
        emit(f"       - {action}")


def summarize_checks(checks: list[DoctorCheck]) -> tuple[str, int]:
    fail_count = sum(1 for check in checks if check.status == "fail")
    warn_count = sum(1 for check in checks if check.status == "warn")
    if fail_count:
        return ("BLOCKED", 1)
    if warn_count:
        return ("ACTION_NEEDED", 0)
    return ("READY", 0)


def build_desktop_doctor_report() -> dict:
    checks = get_desktop_doctor_checks()
    overall, exit_code = summarize_checks(checks)
    fixes = get_desktop_doctor_fixes(checks)
    lines: list[str] = []

    def emit(line: str) -> None:
        lines.append(line)

    emit("=== Steam Tools Desktop Doctor ===")
    emit(
        f"Platform: {sys.platform} | Python: {sys.version.split()[0]} | Executable: {sys.executable}"
    )
    emit("")
    for check in checks:
        render_check(check, emit)
    emit("")
    emit(f"Resultado general: {overall}")
    emit("Exit code: 0 = sin FAIL, 1 = hay bloqueos reales.")

    return {
        "overall": overall,
        "exit_code": exit_code,
        "lines": lines,
        "fixes": [
            {
                "fix_id": fix.fix_id,
                "title": fix.title,
                "summary": fix.summary,
                "commands": list(fix.commands),
            }
            for fix in fixes
        ],
        "checks": [
            {
                "status": check.status,
                "title": check.title,
                "summary": check.summary,
                "actions": list(check.actions),
            }
            for check in checks
        ],
    }


def emit_fix_line(emit, prefix: str, message: str) -> None:
    emit(f"{SAFE_FIX_PREFIXES[prefix]} {message}")


def run_fix_command(parts: tuple[str, ...], *, emit) -> None:
    emit_fix_line(emit, "run", format_command(parts))
    subprocess.run(list(parts), check=True, cwd=str(ROOT))


def apply_desktop_doctor_fixes(*, confirm: bool = False, emit=print) -> dict:
    report = build_desktop_doctor_report()
    fixes = report["fixes"]
    result_lines: list[str] = []

    def capture(line: str) -> None:
        result_lines.append(line)
        emit(line)

    capture("=== Steam Tools Desktop Autofix ===")
    if not fixes:
        emit_fix_line(capture, "skip", "No hay autofixes seguros disponibles en este entorno.")
        return {
            "status": "noop",
            "applied_fixes": [],
            "lines": result_lines,
            "report": report,
        }

    for fix in fixes:
        emit_fix_line(capture, "skip", f"Plan: {fix['title']}")
        emit_fix_line(capture, "skip", fix["summary"])
        for command in fix["commands"]:
            emit_fix_line(capture, "skip", command)

    if not confirm:
        emit_fix_line(capture, "skip", "Autofix cancelado: falta confirmación explícita.")
        return {
            "status": "cancelled",
            "applied_fixes": [],
            "lines": result_lines,
            "report": report,
        }

    applied_fixes: list[dict[str, str]] = []
    fix_handlers = {
        "create-local-venv": lambda: run_fix_command(
            (sys.executable, "-m", "venv", str(get_local_venv_dir())), emit=capture
        ),
        "install-local-desktop-deps": lambda: run_fix_command(
            (
                str(get_local_venv_python()),
                "-m",
                "pip",
                "install",
                "-r",
                str(ROOT / "requirements-desktop.txt"),
            ),
            emit=capture,
        ),
        "build-desktop-artifact": lambda: run_fix_command(
            (str(get_local_venv_python()), str(ROOT / "build_desktop.py"), "--skip-install"),
            emit=capture,
        ),
    }

    try:
        for fix in fixes:
            handler = fix_handlers.get(fix["fix_id"])
            if handler is None:
                emit_fix_line(capture, "skip", f"Sin handler para {fix['fix_id']}")
                continue
            handler()
            applied_fixes.append({"fix_id": fix["fix_id"], "title": fix["title"]})
            emit_fix_line(capture, "ok", f"Aplicado: {fix['title']}")
    except subprocess.CalledProcessError as exc:
        emit_fix_line(capture, "skip", f"Autofix detenido por error en comando (exit {exc.returncode}).")
        return {
            "status": "failed",
            "applied_fixes": applied_fixes,
            "lines": result_lines,
            "report": build_desktop_doctor_report(),
            "error": f"command_failed:{exc.returncode}",
        }

    emit_fix_line(
        capture,
        "ok",
        "Autofix seguro completado. Si preparaste `.venv` desde otro Python, relanza la app usando esa `.venv` para que el doctor refleje el nuevo runtime.",
    )
    return {
        "status": "applied",
        "applied_fixes": applied_fixes,
        "lines": result_lines,
        "report": build_desktop_doctor_report(),
    }


def run_desktop_doctor(*, emit=print) -> int:
    report = build_desktop_doctor_report()
    for line in report["lines"]:
        emit(line)
    return int(report["exit_code"])


def run_desktop_doctor_autofix(*, assume_yes: bool = False, emit=print, prompt=input) -> int:
    report = build_desktop_doctor_report()
    fixes = report["fixes"]
    for line in report["lines"]:
        emit(line)
    if not fixes:
        emit("")
        emit("No hay autofixes seguros disponibles.")
        return 0

    emit("")
    emit("Autofixes seguros disponibles:")
    for index, fix in enumerate(fixes, start=1):
        emit(f"  {index}. {fix['title']} — {fix['summary']}")
        for command in fix["commands"]:
            emit(f"     - {command}")

    confirmed = assume_yes
    if not confirmed:
        if not sys.stdin.isatty():
            emit("Este autofix requiere confirmación interactiva o `--yes`.")
            return 1
        answer = prompt("\n¿Aplicar estos autofixes seguros? [y/N]: ").strip().lower()
        confirmed = answer in {"y", "yes", "s", "si"}

    emit("")
    result = apply_desktop_doctor_fixes(confirm=confirmed, emit=emit)
    return 0 if result["status"] in {"noop", "cancelled", "applied"} else 1
