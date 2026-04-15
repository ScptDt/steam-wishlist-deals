# Task Context: steam_deals_generator ITAD Orchestration Slice Extraction

Session ID: 2026-04-15-generator-itad-orchestration
Created: 2026-04-15T14:24:48-07:00
Status: in_progress

## Current Request
Continuar con los slices restantes de modularizacion de `steam_deals_generator.py`, empezando por el siguiente corte pequeno recomendado: `ITAD orchestration`, para extraer la coordinacion opcional de lookup, historical lows, current prices y bundles con el mismo enfoque incremental y wrappers de compatibilidad.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/feature-breakdown.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/app/steam_deals_itad.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py

## External Docs Fetched
None.

## Components
- Optional ITAD orchestration boundary
- Coordination of lookup, lows, current prices and bundles
- Compatibility wrappers in `steam_deals_generator.py`
- Regression coverage for ITAD orchestration behavior

## Constraints
- Mantener compatibilidad con CLI, web y desktop.
- No mezclar aun el siguiente bloque de post-processing (filtros/top picks/watchlist/notificaciones).
- Reutilizar `steam_deals_itad.py` como adapter puro y extraer solo la coordinacion/orchestration restante.
- Mantener equivalentes mensajes visibles y shapes de `itad_ids`, `historical_lows`, `current_prices` y `active_bundles`.
- Hacer un corte pequeno y mecanico con wrappers de compatibilidad.
- No hacer commit ni push.

## Exit Criteria
- [ ] Existe una frontera enfocada para la coordinacion ITAD.
- [ ] `steam_deals_generator.py` conserva wrappers o boundary compatible para el flujo actual.
- [ ] El comportamiento visible de lookup/lows/prices/bundles sigue siendo equivalente.
- [ ] Los tests relevantes siguen pasando.
