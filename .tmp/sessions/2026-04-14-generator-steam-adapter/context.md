# Task Context: steam_deals_generator Steam Adapter Extraction

Session ID: 2026-04-14-generator-steam-adapter
Created: 2026-04-14T12:10:23-07:00
Status: completed

## Current Request
Continuar con los pendientes siguiendo el orden acordado. El siguiente corte chico aprobado es extraer el dominio de Steam account/profile/sale adapter desde `steam_deals_generator.py`.

## Context Files (Standards to Follow)
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/code-quality.md
- /home/adolfo/Documents/Deals/.opencode/context/core/standards/test-coverage.md
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
- Steam vanity/profile resolution
- Wishlist loading
- Owned-games loading
- Wishlist comparison helper
- Family JSON loading
- Active sale detection
- Compatibility wrappers in `steam_deals_generator.py`

## Constraints
- Mantener compatibilidad con CLI, Web UI y desktop.
- Preservar fallback XML en `resolve_steam_id()`.
- Mantener el contrato de wishlist privada (`ValueError` en 401/403).
- Mantener shapes de salida para wishlist, owned, family y sale name.
- Hacer un corte chico y mecánico, sin mover orchestration al módulo nuevo.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para Steam account/profile/sale adapter.
- [x] `steam_deals_generator.py` conserva wrappers compatibles para `resolve_steam_id`, `get_wishlist`, `get_owned_games`, `compare_wishlists`, `load_family_games` y `get_active_sale`.
- [x] Los tests/validaciones relevantes siguen pasando.
