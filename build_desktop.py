#!/usr/bin/env python3
"""Unified desktop build entrypoint (Windows/macOS/Linux).

This script centralizes PyInstaller invocation so platform wrappers only call this file.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import struct
from pathlib import Path
import zlib


ROOT = Path(__file__).resolve().parent
APP_NAME = "SteamToolsDesktop"
ICON_SOURCE_FILE = ROOT / "assets" / "steam_tools_icon.svg"
GENERATED_WINDOWS_ICON_FILE = ROOT / ".tmp" / "desktop-icon" / "steam_tools_icon.ico"
DESKTOP_REQUIREMENTS_FILE = ROOT / "requirements-desktop.txt"
DESKTOP_CONSTRAINTS_FILE = ROOT / "constraints" / "desktop.txt"
DATA_FILES = [
    ("assets/steam_tools_icon.svg", "assets"),
    ("steam_deals_web.py", "."),
    ("steam_deals_generator.py", "."),
    ("payday2_web.py", "."),
    ("payday2_dlc_tracker.py", "."),
    ("web/payday2/index.html", "web/payday2"),
    ("web/payday2/app.css", "web/payday2"),
    ("web/payday2/app.js", "web/payday2"),
    ("web/payday2/favicon.svg", "web/payday2"),
    ("web/payday2/masks/heist_mask_blue.svg", "web/payday2/masks"),
    ("web/payday2/masks/heist_mask_gold.svg", "web/payday2/masks"),
    ("web/payday2/masks/heist_mask_red.svg", "web/payday2/masks"),
    ("web/payday2/masks/heist_mask_shadow.svg", "web/payday2/masks"),
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


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def build_windows_icon_bytes(size: int = 32) -> bytes:
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            in_badge = (x - 24) ** 2 + (y - 8) ** 2 <= 9
            in_t = 7 <= y <= 11 and 7 <= x <= 24 or 14 <= x <= 17 and 7 <= y <= 25
            in_s_top = 7 <= y <= 10 and 8 <= x <= 22
            in_s_mid = 14 <= y <= 17 and 8 <= x <= 22
            in_s_bot = 21 <= y <= 24 and 8 <= x <= 22
            in_s_left = 10 <= y <= 14 and 8 <= x <= 11
            in_s_right = 17 <= y <= 21 and 19 <= x <= 22
            if in_badge:
                row.extend((95, 224, 122, 255))
            elif in_t:
                row.extend((245, 197, 66, 255))
            elif in_s_top or in_s_mid or in_s_bot or in_s_left or in_s_right:
                row.extend((231, 238, 247, 255))
            else:
                blue = 24 + int(56 * (x + y) / (size * 2))
                row.extend((7, blue, 74 + int(88 * y / size), 255))
        rows.append(bytes(row))
    raw = b"".join(rows)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(raw, 9))
    png += _png_chunk(b"IEND", b"")
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(png), 22)
    return header + entry + png


def ensure_windows_icon(path: Path = GENERATED_WINDOWS_ICON_FILE) -> Path:
    icon_bytes = build_windows_icon_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != icon_bytes:
        path.write_bytes(icon_bytes)
    return path


def append_icon_arg(
    cmd: list[str], os_name: str = os.name, icon_path: Path | None = None
) -> None:
    if os_name != "nt":
        return
    cmd.extend(["--icon", str(icon_path or ensure_windows_icon())])


def build_dependency_install_command() -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(DESKTOP_REQUIREMENTS_FILE),
    ]
    if DESKTOP_CONSTRAINTS_FILE.exists():
        cmd.extend(["-c", str(DESKTOP_CONSTRAINTS_FILE)])
    return cmd


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
        run(build_dependency_install_command())

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
    append_icon_arg(cmd)
    append_repeated_flag(cmd, "--hidden-import", HIDDEN_IMPORTS)
    append_repeated_flag(cmd, "--collect-submodules", COLLECT_SUBMODULE_PACKAGES)
    run(cmd)

    output_hint = ROOT / "dist" / APP_NAME
    if os.name == "nt" and not args.onedir:
        output_hint = output_hint.with_suffix(".exe")
    print(f"[build] Complete. Output: {output_hint}")


if __name__ == "__main__":
    main()
