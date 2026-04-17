# Task Context: Preset max_workers tuning

Session ID: 2026-04-17-preset-max-workers
Created: 2026-04-17T00:00:00Z
Status: in_progress

## Current Request
Ajustar la opcion corta 1: que los presets de Steam Deals en la UI compartida asignen valores utiles de `max_workers` sin cambiar todavia el default global.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/ui/web/ui-styling-standards.md

## Reference Files (Source Material to Look At)
- web/steam_deals/app.js
- web/steam_deals/index.html
- README.md
- app/steam_deals_config.py
- steam_deals_generator.py

## External Docs Fetched
- None

## Components
- Preset-to-max_workers mapping in shared UI
- Small user-visible feedback in preset application

## Constraints
- Keep change short and low risk
- No default global change yet
- Shared web + desktop UI only
- Validate with JS syntax check

## Exit Criteria
- [ ] Rapido / Completo / Ahorro asignan `max_workers` en la UI
- [ ] No se rompe la aplicacion de presets existente
- [ ] La validacion JS pasa
