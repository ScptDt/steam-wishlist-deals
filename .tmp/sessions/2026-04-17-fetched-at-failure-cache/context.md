# Task Context: _fetched_at failure cache fix

Session ID: 2026-04-17-fetched-at-failure-cache
Created: 2026-04-17T00:00:00Z
Status: in_progress

## Current Request
Hacer un ajuste corto al fetch inteligente por `_fetched_at` para que fallos transitorios o respuestas nulas de precios no queden marcadas como frescas por 24 horas, evitando que un error puntual congele reintentos futuros.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/project-intelligence/technical-domain.md

## Reference Files (Source Material to Look At)
- app/steam_deals_prices.py
- app/steam_deals_cache_policy.py
- steam_deals_generator.py
- tests/test_generator_logic.py

## External Docs Fetched
- None

## Components
- Cache entry stamping for price fetch results
- Retry semantics for failed/null results
- Targeted regression tests for timestamp refresh behavior

## Constraints
- Cambio pequeño y de bajo riesgo
- Mantener compatibilidad web/desktop/CLI
- No introducir dependencias nuevas
- Validar con tests dirigidos

## Exit Criteria
- [ ] Un fetch fallido/null ya no deja `_fetched_at` fresco por 24h
- [ ] El siguiente run vuelve a considerar ese appid como stale/reintentable
- [ ] Hay tests dirigidos cubriendo el caso
