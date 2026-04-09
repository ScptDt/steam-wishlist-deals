# Windows wrapper for unified desktop build
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1

$ErrorActionPreference = "Stop"

python .\build_desktop.py
