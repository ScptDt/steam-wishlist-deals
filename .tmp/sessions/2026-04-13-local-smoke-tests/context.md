# Task Context: Local Smoke Tests

Session ID: 2026-04-13-local-smoke-tests
Created: 2026-04-13T13:01:30-07:00
Status: in_progress

## Current Request
Agregar smoke tests mínimos para web, desktop y PAYDAY 2. El usuario indicó explícitamente que estos tests no se subirán a GitHub.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/smoke_test_windows.ps1
- /home/adolfo/Documents/Deals/steam_deals_web.py
- /home/adolfo/Documents/Deals/payday2_web.py
- /home/adolfo/Documents/Deals/steam_tools_desktop.py
- /home/adolfo/Documents/Deals/shared_web_infra.py
- /home/adolfo/Documents/Deals/web/steam_deals/index.html
- /home/adolfo/Documents/Deals/web/steam_deals/app.js
- /home/adolfo/Documents/Deals/web/payday2/index.html
- /home/adolfo/Documents/Deals/web/payday2/app.js

## External Docs Fetched
None.

## Components
- Smoke test for Steam Deals Web
- Smoke test for PAYDAY 2 Web
- Smoke test for Desktop launcher or packaged desktop path
- Local-only placement strategy so tests do not get pushed by mistake

## Constraints
- Los smoke tests deben ser mínimos, reproducibles y stdlib-first cuando sea posible.
- Evitar dependencias de red externa o validaciones frágiles.
- Siempre cerrar procesos que se levanten durante los tests.
- Respetar la realidad actual: web local + wrapper desktop con pywebview.
- El usuario indicó que estos tests no se subirán a GitHub; preferir ubicación local/ignorada o confirmar estrategia final antes de ejecutar.
- No hacer commit ni push.

## Exit Criteria
- [ ] Existe una estrategia local para smoke tests que no termine en GitHub por accidente.
- [ ] Hay smoke test mínimo para Steam Deals Web.
- [ ] Hay smoke test mínimo para PAYDAY 2 Web.
- [ ] Hay smoke test mínimo para desktop o launcher desktop.
- [ ] Los smoke tests apagan limpio cualquier proceso que arranquen.
