# Task Context: steam_deals_generator Family Slice Extraction

Session ID: 2026-04-15-generator-family
Created: 2026-04-15T13:38:12-07:00
Status: in_progress

## Current Request
Continuar con la modularizacion de `steam_deals_generator.py` con el siguiente corte pequeno recomendado: `family`, aislando la carga y propagacion de `family_appids` con el mismo enfoque incremental y wrappers de compatibilidad.

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
- /home/adolfo/Documents/Deals/app/steam_deals_steam_api.py
- /home/adolfo/Documents/Deals/app/steam_deals_hltb.py
- /home/adolfo/Documents/Deals/app/steam_deals_config.py
- /home/adolfo/Documents/Deals/steam_deals_web.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py

## External Docs Fetched
None.

## Components
- Family library orchestration (`family_json` -> `family_appids`)
- Propagation boundary from generator to downstream HLTB/rendering consumers
- Compatibility wrappers in `steam_deals_generator.py`
- Regression coverage for family-related orchestration behavior

## Constraints
- Mantener compatibilidad con CLI, web y desktop.
- No mezclar todavia el refactor completo de HLTB, ITAD ni output final.
- Mantener intacto el comportamiento de `--family-json` y el shape de `family_appids`.
- Reutilizar modulos ya extraidos (`steam_deals_steam_api.py`, `steam_deals_hltb.py`, `steam_deals_config.py`) en vez de duplicar logica.
- Hacer un corte pequeno y mecanico con wrappers de compatibilidad.
- No hacer commit ni push.

## Exit Criteria
- [ ] Existe una frontera enfocada para la carga/uso de `family_appids`.
- [ ] `steam_deals_generator.py` conserva wrappers o boundary compatible para el flujo actual.
- [ ] El uso de `family_appids` en HLTB/rendering sigue siendo equivalente.
- [ ] Los tests relevantes siguen pasando.
