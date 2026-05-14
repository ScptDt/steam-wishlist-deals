#!/usr/bin/env python3
"""Generate desktop readiness plans without executing validation commands."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass


PLATFORMS = ("linux", "windows", "macos")
PROFILE_SMOKE = "https://steamcommunity.com/id/joseluis12351"
DESKTOP_TESTS = (
    "tests.test_runtime_paths",
    "tests.test_desktop_share",
    "tests.test_desktop_doctor",
    "tests.test_web_assets",
)
GLOBAL_GUARDRAILS = (
    "Este helper solo imprime un plan; no ejecuta comandos, builds ni smokes.",
    "No usar BG00G, --no-cache, cold-cache largo ni red real salvo objetivo aprobado.",
    "No cerrar macOS sin host macOS nativo y .app validada localmente.",
    "No versionar output/, logs/, .cache/, build/, dist/, reportes generados ni *.spec.",
)


@dataclass(frozen=True)
class ReadinessStep:
    phase: str
    title: str
    command: str = ""
    notes: tuple[str, ...] = ()
    requires_approval: bool = False
    manual: bool = False


@dataclass(frozen=True)
class ReadinessPlan:
    platform: str
    runbook: str
    prerequisites: tuple[str, ...]
    blockers: tuple[str, ...]
    guardrails: tuple[str, ...]
    steps: tuple[ReadinessStep, ...]
    evidence: tuple[str, ...]


def normalize_platform(value: str | None = None) -> str:
    platform = (value or current_platform()).strip().lower()
    aliases = {
        "linux2": "linux",
        "win32": "windows",
        "win": "windows",
        "windows": "windows",
        "darwin": "macos",
        "mac": "macos",
        "macos": "macos",
    }
    platform = aliases.get(platform, platform)
    if platform not in PLATFORMS and platform != "all":
        raise ValueError(f"Plataforma no soportada: {value}")
    return platform


def current_platform() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return sys.platform


def platform_python(platform: str) -> str:
    return ".\\.venv\\Scripts\\python.exe" if platform == "windows" else ".venv/bin/python"


def desktop_test_command(platform: str) -> str:
    return " ".join((platform_python(platform), "-m", "unittest", *DESKTOP_TESTS))


def build_desktop_command(platform: str) -> str:
    return f"{platform_python(platform)} build_desktop.py --skip-install"


def doctor_command(platform: str) -> str:
    return f"{platform_python(platform)} steam_tools_desktop.py --doctor"


def fallback_command(platform: str) -> str:
    if platform == "windows":
        return f"{platform_python(platform)} steam_tools_desktop.py --force-web-fallback"
    if platform == "macos":
        return "STEAM_TOOLS_FORCE_WEB_FALLBACK=1 dist/SteamToolsDesktop.app/Contents/MacOS/SteamToolsDesktop"
    return "BROWSER=/bin/false .venv/bin/python steam_tools_desktop.py --force-web-fallback"


def artifact_launch_command(platform: str) -> str:
    if platform == "windows":
        return r"dist\SteamToolsDesktop.exe"
    if platform == "macos":
        return "open dist/SteamToolsDesktop.app"
    return "./dist/SteamToolsDesktop"


def build_readiness_plan(platform: str | None = None) -> ReadinessPlan:
    target = normalize_platform(platform)
    if target == "all":
        raise ValueError("Usa build_all_readiness_plans() para plataforma all.")
    plan_builders = {
        "linux": build_linux_plan,
        "windows": build_windows_plan,
        "macos": build_macos_plan,
    }
    return plan_builders[target]()


def common_steps(platform: str) -> tuple[ReadinessStep, ...]:
    return (
        ReadinessStep(
            "checks",
            "Tests desktop/readiness sin red",
            desktop_test_command(platform),
            ("Debe terminar en OK antes de abrir build/smoke manual.",),
        ),
        ReadinessStep(
            "checks",
            "Desktop Doctor source/frozen",
            doctor_command(platform),
            ("Si falla, detener y aplicar stop-on-failure antes de continuar.",),
        ),
        ReadinessStep(
            "fallback",
            "Fallback web dirigido",
            fallback_command(platform),
            ("Validación opcional del modo degradado; no sustituye host nativo.",),
            manual=True,
        ),
        ReadinessStep(
            "build",
            "Build desktop controlado",
            build_desktop_command(platform),
            ("Ejecutar solo si el objetivo del slice/release lo aprobó explícitamente.",),
            requires_approval=True,
            manual=True,
        ),
        ReadinessStep(
            "smoke",
            "Abrir artefacto desktop nativo",
            artifact_launch_command(platform),
            ("Requiere sesión gráfica interactiva del sistema objetivo.",),
            manual=True,
        ),
        ReadinessStep(
            "smoke",
            "Smoke funcional pequeño",
            "Usar perfil " + PROFILE_SMOKE + " desde la UI desktop",
            (
                "Confirmar Doctor/Probar config, outputs básicos, Copiar log y cierre limpio.",
                "No usar BG00G como smoke rápido.",
            ),
            manual=True,
        ),
    )


def build_linux_plan() -> ReadinessPlan:
    return ReadinessPlan(
        platform="linux",
        runbook="docs/runbooks/desktop-linux.md",
        prerequisites=(
            "Sesión gráfica normal no-root para cierre visual.",
            "Usar .venv; no instalar paquetes del sistema automáticamente.",
        ),
        blockers=(
            "No repetir E2E largo ni BG00G salvo cambio sustancial, gate release o performance explícita.",
            "Si aparece PermissionError en cache/log/output, revisar ownership antes de relanzar.",
        ),
        guardrails=GLOBAL_GUARDRAILS,
        steps=common_steps("linux"),
        evidence=(
            "Registrar solo deltas/incidencias en BITACORA.md.",
            "No sustituir macOS ni Windows con evidencia Linux.",
        ),
    )


def build_windows_plan() -> ReadinessPlan:
    return ReadinessPlan(
        platform="windows",
        runbook="docs/runbooks/desktop-windows.md",
        prerequisites=(
            "Sesión interactiva normal Console/RDP; no servicio.",
            "Python 3, PowerShell y WebView2 Runtime disponibles.",
        ),
        blockers=(
            "Windows es baseline de apoyo; no cierra Linux ni macOS.",
            "No usar BG00G ni build desktop salvo objetivo explícito.",
        ),
        guardrails=GLOBAL_GUARDRAILS,
        steps=common_steps("windows"),
        evidence=(
            "Registrar usuario/perfil, superficie Web/Desktop, outputs, incidencias y decisión.",
            "Mantener reportes/logs generados fuera de git.",
        ),
    )


def build_macos_plan() -> ReadinessPlan:
    return ReadinessPlan(
        platform="macos",
        runbook="docs/runbooks/desktop-macos.md",
        prerequisites=(
            "Host macOS nativo con sesión gráfica local.",
            "Python 3 y Command Line Tools disponibles.",
        ),
        blockers=(
            "Bloqueado sin host macOS nativo; CI/Windows/Linux/source no sustituyen .app local.",
            "No cerrar P2 macOS sin build .app, apertura local, smoke pequeño y cierre limpio.",
        ),
        guardrails=GLOBAL_GUARDRAILS,
        steps=common_steps("macos"),
        evidence=(
            "Registrar build .app, apertura, Gatekeeper/quarantine si aplica, outputs y cierre limpio.",
            "Usar smoke pequeño con joseluis12351; BG00G solo para performance/stress aprobado.",
        ),
    )


def build_all_readiness_plans() -> tuple[ReadinessPlan, ...]:
    return tuple(build_readiness_plan(platform) for platform in PLATFORMS)


def plan_to_dict(plan: ReadinessPlan) -> dict:
    return asdict(plan)


def render_plan(plan: ReadinessPlan) -> str:
    lines = [
        f"# Desktop readiness plan: {plan.platform}",
        "",
        f"Runbook: `{plan.runbook}`",
        "",
        "> Este comando solo imprime el plan; no ejecuta pasos.",
        "",
        "## Prerrequisitos",
        *[f"- {item}" for item in plan.prerequisites],
        "",
        "## Blockers / no sustituir",
        *[f"- {item}" for item in plan.blockers],
        "",
        "## Guardrails",
        *[f"- {item}" for item in plan.guardrails],
        "",
        "## Pasos propuestos",
    ]
    for step in plan.steps:
        flags = []
        if step.manual:
            flags.append("manual")
        if step.requires_approval:
            flags.append("requiere aprobación")
        suffix = f" ({', '.join(flags)})" if flags else ""
        lines.append(f"- **[{step.phase}] {step.title}{suffix}**")
        if step.command:
            lines.append(f"  - `{step.command}`")
        for note in step.notes:
            lines.append(f"  - {note}")
    lines.extend(["", "## Evidencia esperada", *[f"- {item}" for item in plan.evidence]])
    return "\n".join(lines)


def render_plans(plans: tuple[ReadinessPlan, ...]) -> str:
    return "\n\n---\n\n".join(render_plan(plan) for plan in plans)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a desktop readiness plan without executing commands."
    )
    parser.add_argument(
        "--platform",
        default=current_platform(),
        help="Target platform: linux, windows, macos or all (default: current).",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, emit=print) -> int:
    args = parse_args(argv)
    platform = normalize_platform(args.platform)
    plans = build_all_readiness_plans() if platform == "all" else (build_readiness_plan(platform),)
    if args.format == "json":
        emit(json.dumps([plan_to_dict(plan) for plan in plans], ensure_ascii=False, indent=2))
    else:
        emit(render_plans(plans))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
