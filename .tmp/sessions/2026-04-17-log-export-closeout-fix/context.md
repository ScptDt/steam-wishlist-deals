# Task Context: Steam Deals log export + closeout fix

Session ID: 2026-04-17-log-export-closeout-fix
Created: 2026-04-17T00:00:00Z
Status: in_progress

## Current Request
Corregir el crash final detectado en la corrida larga de Steam Deals desktop y agregar una manera práctica de copiar o descargar logs/traceback desde la UI para no perder errores largos.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/core/standards/documentation.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/ui/web/ui-styling-standards.md

## Reference Files (Source Material to Look At)
- steam_deals_generator.py
- app/steam_deals_run_output.py
- web/steam_deals/index.html
- web/steam_deals/app.js
- web/steam_deals/app.css
- tests/test_generator_logic.py

## External Docs Fetched
- pytest + Python venv guidance: usar `./.venv/bin/python -m pytest` en lugar de `python3 -m pytest` en Debian/Linux.

## Components
- Fix de compatibilidad entre generator y run-output para el resumen final
- Acciones de UI para copiar/descargar logs de ejecución
- Validación dirigida por tests

## Constraints
- Mantener alineados web + desktop porque comparten la misma UI
- Evitar dependencias nuevas
- Cambios pequeños y directos en la UI existente
- No romper el flujo SSE actual ni los accesos rápidos de reportes

## Exit Criteria
- [ ] El resumen final no vuelve a crashear por `smart_alerts`
- [ ] La UI permite copiar o descargar el log visible de ejecución
- [ ] La validación dirigida pasa en `.venv`
