# Task Context: steam_deals_generator Presentation Helpers Extraction

Session ID: 2026-04-14-generator-presentation
Created: 2026-04-14T12:10:23-07:00
Status: completed

## Current Request
Continuar con los pendientes siguiendo el orden acordado. El siguiente corte chico aprobado es extraer presentation helpers / badges / grouping desde `steam_deals_generator.py`.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/renderers/markdown_renderer.py
- /home/adolfo/Documents/Deals/renderers/html_renderer.py
- /home/adolfo/Documents/Deals/renderers/csv_renderer.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py

## External Docs Fetched
None.

## Components
- Tier grouping helpers
- Deck / ProtonDB / Linux presentation badges
- Tags / grouping helpers
- Players / achievements badges
- Multiplayer badge helper
- Compatibility wrappers in `steam_deals_generator.py`

## Constraints
- Mantener exactamente los textos/salidas actuales porque los renderers ya dependen de ellos.
- Mantener wrappers compatibles en `steam_deals_generator.py`.
- No mezclar este corte con fetch/cache o network logic.
- Hacer un corte chico y mecánico, manteniendo la DI actual hacia renderers.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para presentation helpers / badges / grouping.
- [x] `steam_deals_generator.py` conserva wrappers compatibles para los helpers inyectados a los renderers.
- [x] Los tests/validaciones relevantes siguen pasando.
