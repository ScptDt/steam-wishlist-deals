# Task Context: History reset filters UX

Session ID: 2026-04-17-history-reset-filters
Created: 2026-04-17T00:00:00Z
Status: in_progress

## Current Request
Agregar un refinamiento corto de UX al dashboard historico HTML: un boton para restablecer filtros/controles de comparacion sin tener que limpiar manualmente busqueda, estado, orden e include_same.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/ui/web/ui-styling-standards.md

## Reference Files (Source Material to Look At)
- web/steam_deals/index.html
- web/steam_deals/app.js
- web/steam_deals/app.css
- steam_deals_web.py

## External Docs Fetched
- None

## Components
- History toolbar button in shared UI
- Reset helper for filters/search/pagination/localStorage
- Small visual alignment update if needed

## Constraints
- Keep change short and low risk
- Shared web + desktop UI only (no separate frontend)
- Preserve existing history compare behavior
- Validate with syntax checks

## Exit Criteria
- [ ] Dashboard historico tiene boton de restablecer filtros
- [ ] Restablece busqueda, include_same, estado, orden y pagina
- [ ] Refresca selectores y limpia comparacion previa de forma coherente
