# Task Context: Shared Web Infra - Paso 1

Session ID: 2026-04-14-shared-web-infra-step1
Created: 2026-04-15T00:53:44.573703+00:00
Status: in_progress

## Current Request
"Empieza el plan" para ejecutar el Paso 1: implementar/asegurar el módulo base web compartido reutilizable para `steam_deals_web.py` y `payday2_web.py`, sin cambiar comportamiento funcional.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/development/principles/clean-code.md
- .opencode/context/project-intelligence/navigation.md
- .opencode/context/core/standards/security-patterns.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/development/principles/api-design.md
- .opencode/context/core/workflows/feature-breakdown.md
- .opencode/context/core/workflows/component-planning.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/living-notes.md

## Reference Files (Source Material to Look At)
- .tmp/tasks/shared-web-infra/task.json
- .tmp/tasks/shared-web-infra/subtask_01.json
- shared_web_infra.py
- steam_deals_web.py
- payday2_web.py

## External Docs Fetched
- Ninguna (no requerida para este paso)

## Components
- Módulo base compartido de infraestructura web local
- Helpers de respuesta HTTP/JSON/HTML/CSS/JS
- Parsing seguro de JSON de request
- Helpers de lectura de assets locales
- Helpers de subprocess/SSE reutilizables

## Constraints
- No cambiar rutas ni comportamiento visible de los handlers actuales.
- Mantener compatibilidad con ejecución local/desktop.
- Trabajo incremental por pasos con validación en cada paso.

## Exit Criteria
- [ ] Existe módulo base compartido reutilizable para infraestructura web local.
- [ ] El módulo cubre helpers de respuesta HTTP, parsing JSON y assets de texto.
- [ ] `python -m py_compile shared_web_infra.py` termina sin errores.
