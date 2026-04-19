# Task Context: Continuar pendientes + sugerencia R1CK para título HTML

Session ID: 2026-04-18-r1ck-html-title-profile-name
Created: 2026-04-18T00:00:00Z
Status: in_progress

## Current Request
Continuar con los pendientes y agregar a pendientes una sugerencia del tester R1CK: "en el titulo de la pagina html cambiar el titulo de https://steamcommunity.com/profiles/76561198350398583/ al nombre de perfil de steam".

## Context Files (Standards to Follow)
- .opencode/context/navigation.md
- .opencode/context/core/navigation.md
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/task-management/navigation.md
- .opencode/context/core/task-management/guides/managing-tasks.md
- .opencode/context/core/workflows/component-planning.md
- .opencode/context/project-intelligence/navigation.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/development/navigation.md
- .opencode/context/development/ui-navigation.md
- .opencode/context/development/frontend/navigation.md

## Reference Files (Source Material to Look At)
- PENDIENTES.md
- steam_deals_generator.py
- app/steam_deals_steam_api.py
- renderers/html_renderer.py
- renderers/share_html_renderer.py
- renderers/json_renderer.py
- steam_deals_web.py
- web/steam_deals/app.js
- tests/test_generator_logic.py

## External Docs Fetched
- No aplica (sin librerías/dependencias nuevas)

## Components
- Gestión de backlog/pendientes
- Resolución de nombre visible de perfil Steam
- Renderizado de título HTML (reportes HTML/share)
- Metadata JSON consumida por Web UI

## Constraints
- Mantener compatibilidad con entradas de perfil existentes (vanity, URL completa, steamid)
- Cambios incrementales y con validación de tests relevantes
- Evitar mutaciones de comportamiento no relacionadas

## Exit Criteria
- [ ] `PENDIENTES.md` incluye el pendiente sugerido por R1CK
- [ ] El `<title>` de HTML/reportes usa nombre de perfil Steam cuando esté disponible
- [ ] Fallback seguro cuando no se pueda resolver nombre visible
- [ ] Tests relevantes pasan
