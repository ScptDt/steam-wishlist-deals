# Task Context: steam_deals_generator Cache Lifecycle Extraction

Session ID: 2026-04-15-generator-cache-lifecycle
Created: 2026-04-15T09:48:47-07:00
Status: in_progress

## Current Request
Continuar con la modularizacion de `steam_deals_generator.py` retomando el siguiente corte pequeno acordado. El usuario recuerda las fases tipo 1A/1B/1C/1D y quiere seguir con la modularizacion incremental en el punto pendiente actual.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/feature-breakdown.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py
- /home/adolfo/Documents/Deals/app/steam_deals_prices.py
- /home/adolfo/Documents/Deals/app/steam_deals_enrichment.py
- /home/adolfo/Documents/Deals/shared/cache_utils.py

## External Docs Fetched
None.

## Components
- Cache policy extraction for price and enrichment flows
- Cache lifecycle decisions (`--no-cache`, TTL, partial refresh, full refresh)
- Compatibility wrappers in `steam_deals_generator.py`
- Incremental validation with existing logic tests

## Constraints
- Mantener compatibilidad con CLI, Web UI y desktop.
- Hacer un corte chico y mecanico, sin tocar adapters ni orchestration pesada fuera del dominio de cache.
- Reutilizar tests existentes antes de expandir cobertura.
- No hacer commit ni push.
- Actualizar `PENDIENTES.md` solo si el corte queda efectivamente completado.

## Exit Criteria
- [ ] Existe un modulo enfocado para `cache policy / cache lifecycle`.
- [ ] `steam_deals_generator.py` conserva wrappers o fronteras compatibles para el flujo actual.
- [ ] La logica de `--no-cache`, TTL y refresh parcial/full queda centralizada sin cambiar comportamiento observable.
- [ ] Los tests relevantes siguen pasando.
