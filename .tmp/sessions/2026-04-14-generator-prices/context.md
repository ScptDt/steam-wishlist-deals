# Task Context: steam_deals_generator Price Cache Extraction

Session ID: 2026-04-14-generator-prices
Created: 2026-04-14T12:10:23-07:00
Status: completed

## Current Request
Continuar con los pendientes siguiendo el orden acordado. El siguiente corte chico aprobado es extraer el dominio de Steam price-fetch/cache desde `steam_deals_generator.py` y además ya se registró en backlog la integración futura con Fanatical/múltiples tiendas (official stores y keyshops).

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/shared/cache_utils.py
- /home/adolfo/Documents/Deals/shared/io_utils.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py

## External Docs Fetched
None.

## Components
- Price cache load/save
- Single-app fallback fetch
- Release year parsing
- Appdetails response processing
- Wishlist batch fetch with retry/fallback
- Compatibility wrappers in `steam_deals_generator.py`

## Constraints
- Mantener el schema de `prices_cache.json` y el identity check por `steam_id`.
- No cambiar el shape actual de `deals`.
- Preservar batch fetch + backoff por 429 + fallback individual.
- Mantener `--no-cache` alineado con el flujo actual de `main()`.
- Hacer un corte chico y mecánico, sin mezclar orquestación adicional.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para Steam price-fetch/cache.
- [x] `steam_deals_generator.py` conserva wrappers compatibles para cache/fetch/processing del dominio de precios.
- [x] Los tests/validaciones relevantes siguen pasando.
