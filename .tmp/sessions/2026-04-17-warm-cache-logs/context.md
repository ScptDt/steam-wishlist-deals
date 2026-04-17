# Task Context: Warm-cache logs folder

Session ID: 2026-04-17-warm-cache-logs
Created: 2026-04-17T00:00:00Z
Status: in_progress

## Current Request
Extender la v2 del modo headless `--warm-cache` para poder guardar logs de la corrida en una carpeta llamada `logs`, útil para runs largos en segundo plano.

## Context Files (Standards to Follow)
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/security-patterns.md
- .opencode/context/core/standards/documentation.md

## Reference Files (Source Material to Look At)
- steam_deals_generator.py
- steam_deals_paths.py
- app/steam_deals_paths.py
- app/steam_deals_config.py
- tests/test_generator_logic.py
- tests/test_runtime_paths.py
- README.md

## External Docs Fetched
- None

## Components
- CLI/config flag wiring for warm-cache log behavior
- Runtime path resolution for a persistent `logs/` directory
- Headless warm-cache stream tee into terminal + file
- Tests and README updates

## Constraints
- Mantener compatibilidad CLI/web/desktop
- Evitar dependencias nuevas
- No exponer secretos en logs más de lo que ya imprime el CLI actual
- Preferir helpers pequeños y reusables

## Exit Criteria
- [ ] `--warm-cache` puede dejar un log en una carpeta `logs/`
- [ ] La ruta de logs no depende de `_MEI` temporal en modo frozen
- [ ] Hay tests dirigidos para config/rutas/comportamiento
- [ ] README documenta el uso
