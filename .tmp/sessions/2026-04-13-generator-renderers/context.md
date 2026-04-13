# Task Context: steam_deals_generator Renderers Refactor

Session ID: 2026-04-13-generator-renderers
Created: 2026-04-13T13:45:34-07:00
Status: in_progress

## Current Request
Continuar con los pendientes y empezar la modularización de `steam_deals_generator.py` por dominios. El primer corte aprobado es extraer `renderers/` primero como paso inicial seguro.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/feature-breakdown.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/component-planning.md
- /home/adolfo/Documents/Deals/.opencode/context/development/principles/clean-code.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/steam_deals_web.py
- /home/adolfo/Documents/Deals/steam_tools_desktop.py

## External Docs Fetched
None.

## Components
- Renderer extraction plan for Markdown output
- Renderer extraction plan for HTML output
- Renderer extraction plan for share HTML output
- Renderer extraction plan for CSV output
- Compatibility layer so current generator entrypoints continue working during the refactor

## Constraints
- Hacer el primer corte por `renderers/`, no modularizar todo el generator de golpe.
- Mantener compatibilidad con CLI, Web UI y desktop.
- Evitar cambios de comportamiento; priorizar extracción mecánica y helpers pequeños.
- Validar incrementalmente después de cada corte.
- No hacer commit ni push.

## Exit Criteria
- [ ] Existe un plan de subtareas para extraer `renderers/` desde `steam_deals_generator.py`.
- [ ] El primer corte de ejecución puede hacerse en pasos pequeños y verificables.
- [ ] El refactor mantiene compatibilidad con los flujos actuales de CLI/web/desktop.
