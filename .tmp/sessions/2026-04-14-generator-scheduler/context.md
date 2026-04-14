# Task Context: steam_deals_generator Scheduler Extraction

Session ID: 2026-04-14-generator-scheduler
Created: 2026-04-14T12:10:23-07:00
Status: completed

## Current Request
Continuar con los pendientes siguiendo el orden acordado. El siguiente corte chico aprobado fue extraer el dominio de scheduler desde `steam_deals_generator.py`.

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
- Schedule flag parsing
- Programmed run loop
- Soft stop on KeyboardInterrupt
- Compatibility wrapper in `steam_deals_generator.py`

## Constraints
- Mantener compatibilidad con CLI, Web UI y desktop.
- Preservar semantica actual: sin `--schedule` o valor invalido/falsy => run unico.
- Preservar mensajes y soft-stop por `KeyboardInterrupt`.
- Hacer un corte chico y mecánico, sin mover responsabilidades web/desktop al scheduler.
- No hacer commit ni push.

## Exit Criteria
- [x] Existe un módulo enfocado para scheduler.
- [x] `steam_deals_generator.py` conserva wrapper compatible para `run_scheduled`.
- [x] Los tests/validaciones relevantes siguen pasando.
