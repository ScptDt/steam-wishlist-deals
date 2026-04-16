# Task Context: Cross-platform CI validation and fallback runbook

Session ID: 2026-04-15-cross-platform-ci-validation
Created: 2026-04-15T00:00:00Z
Status: in_progress

## Current Request
Revisar pendientes y continuar, priorizando validación cross-platform Linux/macOS, bitácora/checklist reproducible y verificación del fallback web desktop.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/core/standards/documentation.md
- .opencode/context/core/workflows/feature-breakdown.md
- .opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- PENDIENTES.md
- README.md
- build_desktop.py
- build_desktop.sh
- build_desktop.ps1
- steam_tools_desktop.py
- steam_deals_web.py
- requirements-desktop.txt

## External Docs Fetched
- Ninguna adicional en esta iteración.

## Components
- CI workflow Linux/macOS para build/validación desktop
- Runbook y bitácora cross-platform en README/PENDIENTES
- Verificación operativa de fallback web desktop

## Constraints
- Cambios incrementales y de bajo riesgo.
- Mantener compatibilidad actual de CLI/Web/Desktop.
- No depender de servicios remotos para smokes de readiness local.

## Exit Criteria
- [ ] Existe workflow CI para Linux/macOS con pasos reproducibles de validación desktop.
- [ ] README y PENDIENTES reflejan la ejecución por CI/runners y bitácora actualizada.
- [ ] Queda definido y verificable el flujo de fallback web para desktop cuando falla pywebview.
