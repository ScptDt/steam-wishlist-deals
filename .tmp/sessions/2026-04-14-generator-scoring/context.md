# Task Context: steam_deals_generator Scoring Extraction

Session ID: 2026-04-14-generator-scoring
Created: 2026-04-14T10:47:41-07:00
Status: completed

## Current Request
Continuar con los pendientes siguiendo el orden acordado y hacer el siguiente corte chico de modularización de `steam_deals_generator.py`: extraer scoring / recommendations después de cerrar y validar el corte `renderers/`.

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
- Gift ideas helper extraction
- Value score computation extraction
- Top picks ranking extraction
- Budget picks extraction
- Compatibility wrappers in `steam_deals_generator.py`

## Constraints
- Mantener compatibilidad con CLI, Web UI y desktop.
- Hacer un corte chico y mecánico, sin tocar adapters, cache ni orchestration.
- Reutilizar tests existentes antes de ampliar el refactor.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para scoring / recommendations.
- [x] `steam_deals_generator.py` conserva wrappers compatibles para `build_gift_ideas`, `compute_value_score`, `rank_top_picks` y `compute_budget_picks`.
- [x] Los tests existentes de lógica pura siguen pasando.
