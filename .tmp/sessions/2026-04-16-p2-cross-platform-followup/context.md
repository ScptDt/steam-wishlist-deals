# Task Context: Retomar pendientes P2 cross-platform

Session ID: 2026-04-16-p2-cross-platform-followup
Created: 2026-04-16T09:52:27-07:00
Status: in_progress

## Current Request
Continuemos con los pendientes.

## Context Files (Standards to Follow)
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/navigation.md
- .opencode/context/core/navigation.md
- .opencode/context/core/task-management/navigation.md
- .opencode/context/core/task-management/guides/managing-tasks.md
- .opencode/context/core/workflows/feature-breakdown.md
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/core/workflows/session-management.md

## Reference Files (Source Material to Look At)
- PENDIENTES.md
- README.md
- steam_tools_desktop.py
- build_desktop.py
- requirements-desktop.txt
- .github/workflows/desktop-cross-platform.yml
- .tmp/tasks/desktop-cross-platform-validation/task.json
- .tmp/tasks/desktop-cross-platform-validation/subtask_01.json
- .tmp/tasks/desktop-cross-platform-validation/subtask_02.json
- .tmp/tasks/desktop-cross-platform-validation/subtask_03.json
- .tmp/tasks/desktop-cross-platform-validation/subtask_04.json

## External Docs Fetched
- pywebview: Linux/macOS native deps, backend requirements (GTK/Qt/PyObjC), packaging notes and recommended browser fallback pattern for local web UI wrappers. Source snapshot: `.tmp/external-context/pywebview/linux-macos-deps-packaging-fallback.md`.
- PyInstaller: Linux/macOS packaging caveats, `--onedir` recommendation, macOS `.app` notes and validation concerns. Source snapshot: `.tmp/external-context/pyinstaller/linux-macos-desktop-packaging.md`.

## Components
- Estado operativo P2 en `PENDIENTES.md`
- Documentación y runbook en `README.md`
- Desktop wrapper `steam_tools_desktop.py`
- Build desktop `build_desktop.py`
- Validación parcial CI en `.github/workflows/desktop-cross-platform.yml`

## Constraints
- `PENDIENTES.md` es la fuente única de verdad para pendientes y bitácora operativa.
- El repo opera actualmente desde entorno Linux local, pero la validación nativa concluyente de Linux/macOS debe tratarse con evidencia reproducible y sin inventar resultados no ejecutados.
- Web UI y desktop deben seguir alineados; `steam_tools_desktop.py` reutiliza el mismo server/UI local.
- Si `pywebview` o su backend nativo no levantan, el fallback a navegador debe seguir siendo una ruta válida y visible.
- Cualquier cambio debe ser incremental y validado paso a paso.

## Exit Criteria
- [ ] Queda documentada la brecha real entre `PENDIENTES.md`, `README.md`, CI cross-platform y la tarea histórica `desktop-cross-platform-validation`.
- [ ] Se identifica el pendiente activo mínimo y se acuerda el siguiente cambio útil para avanzar P2.
- [ ] Cualquier archivo actualizado queda alineado con el estado real y sin duplicar fuentes de verdad.
