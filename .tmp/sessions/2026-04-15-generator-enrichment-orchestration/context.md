# Task Context: steam_deals_generator Enrichment Orchestration Extraction

Session ID: 2026-04-15-generator-enrichment-orchestration
Created: 2026-04-15T12:25:20-07:00
Status: in_progress

## Current Request
Continuar con la modularizacion de `steam_deals_generator.py` despues de completar `cache policy / cache lifecycle`, identificando y ejecutando el siguiente corte pequeno de orchestration restante con el mismo enfoque incremental del repo.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-analysis.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/feature-breakdown.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/app/steam_deals_enrichment.py
- /home/adolfo/Documents/Deals/app/steam_deals_cache_policy.py
- /home/adolfo/Documents/Deals/app/steam_deals_run_output.py
- /home/adolfo/Documents/Deals/app/steam_deals_runtime_reporting.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py

## External Docs Fetched
None.

## Components
- Enrichment metadata orchestration slice for reviews, Steam Deck, ProtonDB, anti-cheat, tags y achievements
- Interface/wrapper compatibility in `steam_deals_generator.py`
- Incremental validation with existing logic tests and any targeted additions required

## Constraints
- Mantener compatibilidad con CLI, Web UI y desktop.
- Mantener el orden de pasos/progreso visible del flujo actual.
- No cambiar el shape de `reviews_data`, `deck_data`, `protondb_data`, `anticheat_data`, `tags_data` ni `achievements_data`.
- Reutilizar los modulos ya extraidos (`steam_deals_enrichment.py`, `steam_deals_cache_policy.py`, `steam_deals_runtime_reporting.py`) en vez de duplicar logica.
- Hacer un corte pequeno y mecanico, sin mezclar todavia HLTB/family/output final.
- No hacer commit ni push.

## Exit Criteria
- [ ] Existe un modulo enfocado para el orchestration de enrichment metadata.
- [ ] `steam_deals_generator.py` conserva una frontera compatible para el flujo actual.
- [ ] El orden de pasos y mensajes visibles se mantiene equivalente.
- [ ] Los tests relevantes siguen pasando.
