# Task Context: steam_deals_generator Post-Processing Slice Extraction

Session ID: 2026-04-15-generator-post-processing
Created: 2026-04-15T14:39:24-07:00
Status: in_progress

## Current Request
Continuar con los slices restantes de modularizacion de `steam_deals_generator.py` con el siguiente corte pequeno recomendado: post-processing de deals (`hltb_hours`, filtros y `top_picks`), manteniendo el mismo enfoque incremental y wrappers de compatibilidad.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/feature-breakdown.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/app/steam_deals_hltb.py
- /home/adolfo/Documents/Deals/app/steam_deals_filters.py
- /home/adolfo/Documents/Deals/app/steam_deals_recommendations.py
- /home/adolfo/Documents/Deals/app/steam_deals_itad_orchestration.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py

## External Docs Fetched
None.

## Components
- Post-processing orchestration boundary
- `hltb_hours` derivation from crossed HLTB deals
- Filtering orchestration
- `top_picks` orchestration
- Compatibility wrappers in `steam_deals_generator.py`
- Regression coverage for post-processing behavior

## Constraints
- Mantener compatibilidad con CLI, web y desktop.
- No mezclar aun watchlist, budget, gift ideas ni notificaciones.
- Reutilizar `steam_deals_hltb.py`, `steam_deals_filters.py` y `steam_deals_recommendations.py` como dependencias puras, extrayendo solo la coordinacion restante.
- Mantener equivalentes los shapes de `hltb_hours`, `deals` filtrados y `top_picks`.
- Hacer un corte pequeno y mecanico con wrappers de compatibilidad.
- No hacer commit ni push.

## Exit Criteria
- [ ] Existe una frontera enfocada para el post-processing de deals.
- [ ] `steam_deals_generator.py` conserva wrappers o boundary compatible para el flujo actual.
- [ ] El comportamiento visible de `hltb_hours`, filtros y `top_picks` sigue siendo equivalente.
- [ ] Los tests relevantes siguen pasando.
