#!/usr/bin/env python3
"""Collect safe desktop readiness evidence with an explicit execution flag."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import desktop_readiness_plan


ROOT = Path(__file__).resolve().parent
FORBIDDEN_SAFE_COMMAND_PARTS = (
    "build_desktop.py",
    "--force-web-fallback",
    "BG00G",
    "--no-cache",
    "dist/",
    "dist\\",
    "open dist",
)


@dataclass(frozen=True)
class SafeCheck:
    title: str
    command: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommandExecution:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class CollectedCheck:
    title: str
    command: str
    status: str
    returncode: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CollectionReport:
    platform: str
    mode: str
    overall: str
    checks: tuple[CollectedCheck, ...]
    guardrails: tuple[str, ...]


Runner = Callable[[tuple[str, ...]], CommandExecution]


def command_to_args(command: str, platform: str) -> tuple[str, ...]:
    return tuple(shlex.split(command, posix=platform != "windows"))


def is_safe_collect_step(step: desktop_readiness_plan.ReadinessStep) -> bool:
    if step.manual or step.requires_approval or step.phase != "checks":
        return False
    command = step.command.strip()
    if not command:
        return False
    return not any(part in command for part in FORBIDDEN_SAFE_COMMAND_PARTS)


def build_safe_checks(platform: str | None = None) -> tuple[SafeCheck, ...]:
    plan = desktop_readiness_plan.build_readiness_plan(platform)
    return tuple(
        SafeCheck(step.title, step.command, step.notes)
        for step in plan.steps
        if is_safe_collect_step(step)
    )


def current_platform() -> str:
    return desktop_readiness_plan.normalize_platform(desktop_readiness_plan.current_platform())


def default_runner(args: tuple[str, ...]) -> CommandExecution:
    completed = subprocess.run(
        list(args),
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return CommandExecution(completed.returncode, completed.stdout or "", completed.stderr or "")


def tail_text(text: str, *, limit: int = 600) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return "..." + value[-limit:]


def collect_readiness(
    platform: str | None = None,
    *,
    execute: bool = False,
    runner: Runner = default_runner,
) -> CollectionReport:
    target = desktop_readiness_plan.normalize_platform(platform)
    if target == "all":
        raise ValueError("El collector ejecutable requiere una plataforma específica.")
    if execute and target != current_platform():
        raise ValueError(
            "La ejecución segura solo corre en la plataforma actual; usa dry-run para otros hosts."
        )

    checks = build_safe_checks(target)
    collected: list[CollectedCheck] = []
    for check in checks:
        if not execute:
            collected.append(
                CollectedCheck(
                    check.title,
                    check.command,
                    "planned",
                    notes=check.notes,
                )
            )
            continue
        result = runner(command_to_args(check.command, target))
        collected.append(
            CollectedCheck(
                check.title,
                check.command,
                "ok" if result.returncode == 0 else "fail",
                result.returncode,
                tail_text(result.stdout),
                tail_text(result.stderr),
                check.notes,
            )
        )

    overall = summarize_collected_checks(tuple(collected), execute=execute)
    return CollectionReport(
        target,
        "execute-safe-checks" if execute else "dry-run",
        overall,
        tuple(collected),
        desktop_readiness_plan.GLOBAL_GUARDRAILS,
    )


def summarize_collected_checks(
    checks: tuple[CollectedCheck, ...], *, execute: bool
) -> str:
    if not execute:
        return "PLANNED"
    if any(check.status == "fail" for check in checks):
        return "FAIL"
    return "OK"


def report_to_dict(report: CollectionReport) -> dict:
    return asdict(report)


def render_report(report: CollectionReport) -> str:
    lines = [
        f"# Desktop readiness collector: {report.platform}",
        "",
        f"Modo: {report.mode}",
        f"Resultado: {report.overall}",
        "",
        "## Guardrails",
        *[f"- {item}" for item in report.guardrails],
        "",
        "## Checks seguros",
    ]
    for check in report.checks:
        lines.append(f"- **{check.title}** — {check.status}")
        lines.append(f"  - `{check.command}`")
        if check.returncode is not None:
            lines.append(f"  - exit code: {check.returncode}")
        if check.stdout_tail:
            lines.append(f"  - stdout: `{check.stdout_tail}`")
        if check.stderr_tail:
            lines.append(f"  - stderr: `{check.stderr_tail}`")
        for note in check.notes:
            lines.append(f"  - {note}")
    if report.mode == "dry-run":
        lines.extend(
            [
                "",
                "Para ejecutar estos checks offline en la plataforma actual, relanza con `--execute-safe-checks`.",
            ]
        )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print or run safe desktop readiness checks."
    )
    parser.add_argument(
        "--platform",
        default=desktop_readiness_plan.current_platform(),
        help="Target platform for the collector plan (default: current).",
    )
    parser.add_argument(
        "--execute-safe-checks",
        action="store_true",
        help="Run only offline checks marked safe for the current platform.",
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
    try:
        report = collect_readiness(args.platform, execute=args.execute_safe_checks)
    except ValueError as exc:
        emit(f"Error: {exc}")
        return 2

    if args.format == "json":
        emit(json.dumps(report_to_dict(report), ensure_ascii=False, indent=2))
    else:
        emit(render_report(report))
    return 1 if report.overall == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
