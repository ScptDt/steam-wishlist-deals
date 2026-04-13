# Task Context: Desktop Cross-Platform Validation

Session ID: 2026-04-12-desktop-cross-platform-validation
Created: 2026-04-12T00:00:00Z
Status: in_progress

## Current Request
Continuar con los pendientes del proyecto, priorizando la validación cross-platform (Linux/macOS) y la documentación de dependencias nativas de pywebview.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/workflows/feature-breakdown.md

## Reference Files (Source Material to Look At)
- PENDIENTES.md
- README.md
- build_desktop.py
- build_desktop.ps1
- build_desktop.sh
- SteamToolsDesktop.spec
- steam_tools_desktop.py
- requirements-desktop.txt

## External Docs Fetched
- Ninguna aún (pendiente si se requiere confirmar prerequisitos nativos actualizados por OS).

## Components
- Validación de build desktop en Linux (Ubuntu LTS)
- Validación de build desktop en macOS (app bundle + apertura local)
- Documentación de dependencias nativas pywebview por plataforma

## Constraints
- Entorno actual: Windows local; validaciones Linux/macOS pueden requerir ejecución manual o CI en runners específicos.
- Mantener fallback web existente para minimizar riesgo de bloqueo por backend nativo.

## Exit Criteria
- [ ] Existe checklist de validación Linux completable y con criterios de éxito claros.
- [ ] Existe checklist de validación macOS completable y con criterios de éxito claros.
- [ ] README/PENDIENTES documentan dependencias nativas pywebview por plataforma.
- [ ] Queda registrada bitácora de estado y próximos pasos reproducibles.
