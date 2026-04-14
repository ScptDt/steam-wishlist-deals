# Task Context: steam_deals_generator Watchlist Extraction

Session ID: 2026-04-14-generator-watchlist
Created: 2026-04-14T12:10:23-07:00
Status: completed

## Current Request
Continuar con los pendientes siguiendo el orden acordado. El siguiente corte chico aprobado es extraer el dominio de watchlist desde `steam_deals_generator.py`, idealmente reutilizable también desde `steam_deals_web.py`.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/steam_deals_web.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py
- /home/adolfo/Documents/Deals/renderers/markdown_renderer.py
- /home/adolfo/Documents/Deals/renderers/html_renderer.py

## External Docs Fetched
None.

## Components
- Watchlist file I/O
- CLI watchlist command handling
- Watchlist alert selection
- Shared watchlist boundary for generator/web

## Constraints
- Mantener el mismo path y schema de `~/.config/steam_deals_watchlist.json`.
- Mantener intacto el early-exit de `--watchlist`.
- Mantener el mismo shape de `watchlist_alerts` para renderers y budget flow.
- Preservar soft-fail en resolución de nombre al agregar desde CLI.
- Hacer un corte chico y mecánico, sin tocar orchestration fuera del seam compartido.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para watchlist reutilizable desde generator/web.
- [x] `steam_deals_generator.py` conserva wrappers compatibles para `load_watchlist`, `save_watchlist`, `handle_watchlist_command` y `check_watchlist_alerts`.
- [x] `steam_deals_web.py` reutiliza la nueva frontera compartida sin cambiar schema ni comportamiento observable.
- [x] Los tests/validaciones relevantes siguen pasando.
