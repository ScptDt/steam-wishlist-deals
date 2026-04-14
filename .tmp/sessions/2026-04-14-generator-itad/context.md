# Task Context: steam_deals_generator ITAD Extraction

Session ID: 2026-04-14-generator-itad
Created: 2026-04-14T12:10:23-07:00
Status: completed

## Current Request
Continuar con los pendientes siguiendo el orden acordado. El siguiente corte chico aprobado es extraer el dominio de ITAD adapter / integration de `steam_deals_generator.py`.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md

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
- ITAD lookup by Steam appid
- ITAD historical lows loader
- ITAD current prices loader
- ITAD active bundles loader
- Compatibility wrappers in `steam_deals_generator.py`

## Constraints
- Mantener compatibilidad con CLI, Web UI y desktop.
- Mantener los mismos shapes de `historical_lows`, `current_prices` y `active_bundles`.
- Preservar defaults de país y soft-fail behavior actuales.
- Hacer un corte chico y mecánico, sin tocar orchestration fuera del seam de wrappers.
- Agregar validación puntual sin depender de red real.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para ITAD adapter / integration.
- [x] `steam_deals_generator.py` conserva wrappers compatibles para `itad_lookup_games`, `itad_get_store_lows`, `itad_get_current_prices` y `itad_get_active_bundles`.
- [x] Los tests de lógica pura/reconfigurada relevantes siguen pasando.
