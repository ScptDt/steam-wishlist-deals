# Task Context: steam_deals_generator Config Extraction

Session ID: 2026-04-14-generator-config
Created: 2026-04-14T12:10:23-07:00
Status: completed

## Current Request
Continuar con los pendientes siguiendo el orden acordado. El siguiente corte chico aprobado es extraer el dominio de config / CLI boundary desde `steam_deals_generator.py`.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/documentation.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/technical-domain.md
- /home/adolfo/Documents/Deals/.opencode/context/project-intelligence/navigation.md

## Reference Files (Source Material to Look At)
- /home/adolfo/Documents/Deals/PENDIENTES.md
- /home/adolfo/Documents/Deals/README.md
- /home/adolfo/Documents/Deals/steam_deals_generator.py
- /home/adolfo/Documents/Deals/tests/test_generator_logic.py

## External Docs Fetched
None.

## Components
- User config load/save
- CLI argument parsing
- Interactive fallback gating
- Config tuple assembly
- Compatibility wrapper in `steam_deals_generator.py`

## Constraints
- Mantener el mismo tuple de retorno de `get_config()`.
- Mantener intacto el early-exit de `--watchlist`.
- Preservar gating de prompts por `--web-run`, TTY y presencia de cache local.
- Mantener path/schema de `~/.config/steam_deals.json`.
- Hacer un corte chico y mecánico, sin tocar la orquestación principal.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para config / CLI boundary.
- [x] `steam_deals_generator.py` conserva wrappers compatibles para `load_user_config`, `save_user_config` y `get_config`.
- [x] Los tests/validaciones relevantes siguen pasando.
