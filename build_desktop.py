#!/usr/bin/env python3
"""Unified desktop build entrypoint (Windows/macOS/Linux).

This script centralizes PyInstaller invocation so platform wrappers only call this file.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP_NAME = "SteamToolsDesktop"
DATA_FILES = [
    ("steam_deals_web.py", "."),
    ("steam_deals_generator.py", "."),
    ("payday2_web.py", "."),
    ("payday2_dlc_tracker.py", "."),
    ("web/payday2/index.html", "web/payday2"),
    ("web/payday2/app.css", "web/payday2"),
    ("web/payday2/app.js", "web/payday2"),
    ("web/steam_deals/index.html", "web/steam_deals"),
    ("web/steam_deals/app.css", "web/steam_deals"),
    ("web/steam_deals/app.js", "web/steam_deals"),
]
HIDDEN_IMPORTS = [
    "steam_deals_generator",
    "payday2_dlc_tracker",
]
COLLECT_SUBMODULE_PACKAGES = ["shared", "renderers", "app"]


def run(cmd: list[str]) -> None:
    print("[build]", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def add_data_arg(src: str, dest: str = ".") -> str:
    # PyInstaller uses ';' on Windows and ':' on Unix-like systems.
    sep = ";" if os.name == "nt" else ":"
    return f"{src}{sep}{dest}"


def append_repeated_flag(cmd: list[str], flag: str, values: list[str]) -> None:
    for value in values:
        cmd.extend([flag, value])


def append_data_files(cmd: list[str]) -> None:
    for src, dest in DATA_FILES:
        cmd.extend(["--add-data", add_data_arg(src, dest)])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build desktop executable for Steam Tools"
    )
    parser.add_argument(
        "--skip-install", action="store_true", help="Skip pip install step"
    )
    parser.add_argument(
        "--onedir", action="store_true", help="Build as one-dir instead of one-file"
    )
    args = parser.parse_args()

    if not args.skip_install:
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(ROOT / "requirements-desktop.txt"),
            ]
        )

    mode_flag = "--onedir" if args.onedir else "--onefile"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--windowed",
        mode_flag,
        "--paths",
        str(ROOT),
        str(ROOT / "steam_tools_desktop.py"),
    ]
    append_data_files(cmd)
    append_repeated_flag(cmd, "--hidden-import", HIDDEN_IMPORTS)
    append_repeated_flag(cmd, "--collect-submodules", COLLECT_SUBMODULE_PACKAGES)
    run(cmd)

    output_hint = ROOT / "dist" / APP_NAME
    if os.name == "nt" and not args.onedir:
        output_hint = output_hint.with_suffix(".exe")
    print(f"[build] Complete. Output: {output_hint}")


if __name__ == "__main__":
    main()
