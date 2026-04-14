# Task Context: steam_deals_generator HLTB Matching Extraction

Session ID: 2026-04-14-generator-hltb-matching
Created: 2026-04-14T11:10:51-07:00
Status: completed

## Current Request
Continuar con los pendientes siguiendo el orden acordado y hacer el siguiente corte chico de modularización de `steam_deals_generator.py`: extraer el dominio de HLTB / matching después de cerrar y validar `renderers/` y `scoring / recommendations`.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py
- /home/adolfo/Documents/Deals/renderers/markdown_renderer.py

## External Docs Fetched
None.

## Components
- HLTB hours parsing helpers
- Title normalization and fuzzy matching helpers
- HLTB × deals crosswalk
- Compatibility wrappers in `steam_deals_generator.py`

## Constraints
- Mantener compatibilidad con CLI, Web UI y desktop.
- Mantener intacto el shape de `backlog_on_sale` y `have_on_sale`.
- Hacer un corte chico y mecánico, sin tocar cache, adapters ni orchestration pesada.
- Reutilizar tests existentes y agregar solo validación puntual del dominio.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para HLTB / matching.
- [x] `steam_deals_generator.py` conserva wrappers compatibles para `parse_hltb`, `normalize`, `extract_numbers`, `significant_words`, `is_same_game`, `find_best_match` y `cross_hltb_with_deals`.
- [x] El shape de `backlog_on_sale` / `have_on_sale` no cambia.
- [x] Los tests de lógica pura relevantes siguen pasando.
