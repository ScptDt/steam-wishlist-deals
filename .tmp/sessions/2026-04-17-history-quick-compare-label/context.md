# Task Context: History quick compare clarity

Session ID: 2026-04-17-history-quick-compare-label
Created: 2026-04-17T00:00:00Z
Status: in_progress

## Current Request
Hacer mas claro el quick compare del dashboard historico mostrando de forma visible que Run A y Run B fueron autoseleccionados al usar "Comparar ultimos 2 runs".

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md

## Reference Files (Source Material to Look At)
- web/steam_deals/index.html
- web/steam_deals/app.js
- web/steam_deals/app.css
- app/steam_deals_history.py

## External Docs Fetched
- None

## Components
- Small summary/banner element for selected runs
- Quick compare label update logic
- Shared styling for web + desktop UI

## Constraints
- Keep UX change short and low risk
- Reuse existing run-label formatting
- No backend changes required
- Validate with syntax check

## Exit Criteria
- [ ] Quick compare leaves visible context for Run A / Run B
- [ ] Manual compare can also refresh the same summary coherently
- [ ] Shared UI remains clean and compact
