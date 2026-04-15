# Task Context: steam_deals_generator Engagement Post-Run Slice Extraction

Session ID: 2026-04-15-generator-engagement-post-run
Created: 2026-04-15T15:19:55-07:00
Status: in_progress

## Current Request
Continuar con los slices restantes de modularizacion de `steam_deals_generator.py` con el siguiente corte pequeno recomendado: engagement/post-run (`watchlist`, `budget`, `gift ideas` y notificaciones), manteniendo el mismo enfoque incremental y wrappers de compatibilidad.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/feature-breakdown.md
- /home/adolfo/Documents/Deals/.tmp/sessions/2026-04-15-generator-post-processing/context.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/app/steam_deals_watchlist.py
- /home/adolfo/Documents/Deals/app/steam_deals_notifications.py
- /home/adolfo/Documents/Deals/app/steam_deals_recommendations.py
- /home/adolfo/Documents/Deals/steam_deals_web.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py

## External Docs Fetched
None.

## Components
- Watchlist alerts orchestration
- Budget mode orchestration
- Gift ideas orchestration
- Notification orchestration boundary
- Compatibility wrappers in `steam_deals_generator.py`
- Regression coverage for engagement/post-run behavior

## Constraints
- Mantener compatibilidad con CLI, web y desktop.
- No mezclar renderers, output final ni closeout final.
- Reutilizar `steam_deals_watchlist.py`, `steam_deals_notifications.py` y `steam_deals_recommendations.py` como dependencias existentes, extrayendo solo la coordinacion restante.
- Mantener equivalentes los shapes de `watchlist_alerts`, `budget_result`, `gift_ideas` y el comportamiento visible de notificaciones.
- Hacer un corte pequeno y mecanico con wrappers de compatibilidad.
- No hacer commit ni push.

## Exit Criteria
- [ ] Existe una frontera enfocada para engagement/post-run.
- [ ] `steam_deals_generator.py` conserva wrappers o boundary compatible para el flujo actual.
- [ ] El comportamiento visible de watchlist, budget, gift ideas y notificaciones sigue siendo equivalente.
- [ ] Los tests relevantes siguen pasando.
