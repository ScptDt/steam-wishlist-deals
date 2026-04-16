# Task Context: Quick wins JSON export + score explanation

Session ID: 2026-04-16-quick-wins-json-score
Created: 2026-04-16T00:00:00Z
Status: in_progress

## Current Request
Este chat se usará para cositas cortas o rápidas. Empezar con quick win 1: export JSON; después quick win 2: mejorar explicación del score/recomendación.

## Context Files (Standards to Follow)
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/navigation.md
- .opencode/context/development/principles/api-design.md
- .opencode/context/core/workflows/task-delegation-basics.md
- .opencode/context/core/workflows/feature-breakdown.md

## Reference Files (Source Material to Look At)
- steam_deals_generator.py
- app/steam_deals_run_output.py
- app/steam_deals_recommendations.py
- renderers/markdown_renderer.py
- renderers/html_renderer.py
- web/steam_deals/index.html
- web/steam_deals/app.js
- steam_deals_web.py
- tests/test_generator_logic.py

## External Docs Fetched
- None.

## Components
- Generator/output pipeline for Steam Deals artifacts
- JSON report artifact surfaced in local web UI file list
- Score explanation follow-up for top picks/report rendering

## Constraints
- Quick wins only; avoid reopening large refactors.
- Mantener compatibilidad entre CLI, web y desktop reuse del mismo flujo.
- Preferir stdlib y helpers pequeños.
- Cambios incrementales: primero JSON export, luego score explanation.

## Exit Criteria
- [ ] Steam Deals genera un artifact JSON útil para automatización local.
- [ ] El artifact JSON aparece en el flujo actual de archivos generados.
- [ ] Hay tests puntuales cubriendo el contrato base del nuevo output.
