# Task Context: steam_deals_generator Filters Extraction

Session ID: 2026-04-14-generator-filters
Created: 2026-04-14T12:08:30-07:00
Status: completed

## Current Request
Actualizar la documentación y continuar con los pendientes siguiendo el orden acordado. El siguiente corte chico aprobado es extraer el dominio de filters / selection de `steam_deals_generator.py`.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/documentation.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/feature-breakdown.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py
- /home/adolfo/Documents/Deals/renderers/markdown_renderer.py
- /home/adolfo/Documents/Deals/renderers/html_renderer.py
- /home/adolfo/Documents/Deals/renderers/csv_renderer.py

## External Docs Fetched
None.

## Components
- Genre selection helper extraction
- CLI filters helper extraction
- Compatibility wrappers in `steam_deals_generator.py`

## Constraints
- Mantener compatibilidad con CLI, Web UI y desktop.
- No romper la inyección de helpers hacia renderers.
- Mantener el orden actual del pipeline: `hltb_hours` -> `apply_filters()` -> `rank_top_picks()`.
- Hacer un corte chico y mecánico, sin tocar fetch, cache ni orchestration.
- Reutilizar tests existentes y agregar validación puntual para `filter_by_genres()`.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para filters / selection.
- [x] `steam_deals_generator.py` conserva wrappers compatibles para `filter_by_genres` y `apply_filters`.
- [x] Los tests de lógica pura relevantes siguen pasando.
