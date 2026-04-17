# Task Context: UI max-workers exposure

Session ID: 2026-04-17-ui-max-workers
Created: 2026-04-17T00:00:00Z
Status: in_progress

## Current Request
Exponer `max_workers` de Steam Deals en la UI compartida (web + desktop) como un ajuste corto y no bloqueado, para que el paralelismo de enrichment no dependa solo del CLI.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/ui/web/ui-styling-standards.md

## Reference Files (Source Material to Look At)
- web/steam_deals/index.html
- web/steam_deals/app.js
- app/steam_deals_config.py
- app/steam_deals_enrichment.py
- steam_deals_generator.py
- README.md

## External Docs Fetched
- None

## Components
- Advanced filters UI field for `max_workers`
- Form serialization/hydration for saved `max_workers`
- Short documentation note about UI availability

## Constraints
- Keep web + desktop aligned via shared UI
- Preserve existing CLI behavior
- Avoid new dependencies and large UI reshuffles
- Validate with syntax checks after the change

## Exit Criteria
- [ ] UI shared form exposes `max_workers`
- [ ] Runs/preflight send `max_workers` through filters
- [ ] Saved config values can hydrate the field when present
- [ ] README notes UI availability
