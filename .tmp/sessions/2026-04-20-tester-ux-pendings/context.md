# Task Context: Pendientes UX sugeridos por testers

Session ID: 2026-04-20-tester-ux-pendings
Created: 2026-04-20T10:09:08-07:00
Status: in_progress

## Current Request
Continuar con los pendientes y agregar sugerencias de testers: hacer mas claro que el numero en Top Picks es de Metacritic, permitir/confirmar recarga del listado de runs tras varias ejecuciones, y en la seccion 3/12 del generador mostrar el nombre del amigo en vez de la etiqueta generica "Friend".

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/ui/web/ui-styling-standards.md
- .opencode/context/ui/web/animation-loading.md
- .opencode/context/ui/terminal/navigation.md
- .opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- steam_deals_generator.py
- app/steam_deals_steam_api.py
- renderers/html_renderer.py
- renderers/share_html_renderer.py
- web/steam_deals/index.html
- web/steam_deals/app.js
- tests/test_generator_logic.py
- PENDIENTES.md

## External Docs Fetched
- Ninguna.

## Components
- Reportes HTML / Top Picks: aclarar visualmente el badge o score de Metacritic.
- CLI / progreso de comparacion de wishlists: mostrar el nombre real del amigo en la salida 3/12.
- Dashboard historico web: verificar el flujo de recarga del listado de runs y cerrar el pendiente/reportarlo.
- Tracking operativo: registrar notas relevantes en PENDIENTES.md.

## Constraints
- Mantener compatibilidad web + desktop (pywebview reutiliza la misma UI web).
- Preferir helpers pequenos y cambios localizados.
- No introducir dependencias nuevas.
- No romper wrappers compatibles existentes en `steam_deals_generator.py`.
- Si falla validacion, detenerse y reportar antes de corregir.

## Exit Criteria
- [ ] Top Picks deja claro que el numero corresponde a Metacritic en los reportes HTML relevantes.
- [ ] La salida de comparacion de wishlists usa el nombre del amigo cuando este disponible.
- [ ] El dashboard historico ofrece una forma clara de recargar el listado de runs o queda confirmado/documentado que ya existe.
- [ ] `PENDIENTES.md` refleja las sugerencias/estado de estos pendientes.
- [ ] Hay validacion dirigida sin regresiones en las areas tocadas.
