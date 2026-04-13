# Task Context: Shared Web Infrastructure Refactor

Session ID: 2026-04-13-shared-web-infra
Created: 2026-04-13T11:00:52-07:00
Status: in_progress

## Current Request
Continuar con los pendientes después de completar la extracción de UI restante, siguiendo el siguiente paso natural: extraer infraestructura compartida para el server web local y reutilizarla entre Steam Deals Web y PAYDAY 2 Web.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/development/principles/clean-code.md
- /home/adolfo/Documents/Deals/.opencode/context/development/principles/api-design.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/steam_deals_web.py
- /home/adolfo/Documents/Deals/payday2_web.py
- /home/adolfo/Documents/Deals/steam_tools_desktop.py
- /home/adolfo/Documents/Deals/build_desktop.py
- /home/adolfo/Documents/Deals/web/steam_deals/index.html
- /home/adolfo/Documents/Deals/web/steam_deals/app.css
- /home/adolfo/Documents/Deals/web/steam_deals/app.js
- /home/adolfo/Documents/Deals/web/payday2/index.html
- /home/adolfo/Documents/Deals/web/payday2/app.css
- /home/adolfo/Documents/Deals/web/payday2/app.js

## External Docs Fetched
None.

## Components
- Shared HTTP response helpers for local web handlers
- Shared JSON body parsing and validation helpers
- Shared static asset loading / fallback helpers
- Shared subprocess / SSE support where safe to extract incrementally
- Thin per-app handlers for Steam Deals Web and PAYDAY 2 Web

## Constraints
- Mantener stdlib-first; no agregar frameworks o dependencias nuevas.
- No romper la UX compartida entre web local y desktop con pywebview.
- Mantener server local-only sobre 127.0.0.1 y validación defensiva.
- Reducir duplicación sin forzar una arquitectura más grande que el estado actual del repo.
- Trabajar de forma incremental y validar después de cada paso importante.

## Exit Criteria
- [ ] Existe infraestructura compartida reutilizable para al menos respuestas HTTP, parsing JSON o assets locales.
- [ ] `steam_deals_web.py` y `payday2_web.py` reutilizan esa base sin perder comportamiento actual.
- [ ] La sintaxis Python sigue pasando.
- [ ] Smoke tests mínimos de rutas clave siguen pasando.
