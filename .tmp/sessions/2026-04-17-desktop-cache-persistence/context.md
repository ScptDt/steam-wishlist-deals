# Task Context: Desktop cache persistence

Session ID: 2026-04-17-desktop-cache-persistence
Created: 2026-04-17T00:00:00Z
Status: in_progress

## Current Request
Hacer persistente el caché de Steam Deals desktop para que no se pierda entre ejecuciones del binario PyInstaller onefile y no vuelva a aparecer `Sin caché - fetch completo` tras cerrar/reabrir la app.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/workflows/component-planning.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/ui/web/ui-styling-standards.md

## Reference Files (Source Material to Look At)
- steam_deals_generator.py
- steam_deals_web.py
- steam_tools_desktop.py
- app/steam_deals_config.py
- tests/test_generator_logic.py

## External Docs Fetched
- None

## Components
- Shared runtime path resolution for cache storage
- Steam Deals generator cache path wiring
- Web UI cache detection wiring
- Targeted validation for source vs frozen path resolution

## Constraints
- Keep web + desktop aligned
- Avoid new dependencies
- Preserve current repo-local cache behavior for source runs if possible
- Ensure frozen desktop uses a persistent, non-temporary cache path

## Exit Criteria
- [ ] Frozen desktop no longer stores cache under `_MEI` temp paths
- [ ] Web UI and generator resolve the same persistent cache dir in frozen runs
- [ ] Source-mode behavior remains sensible and test-covered
