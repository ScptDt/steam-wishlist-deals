# Runbooks

Índice de checklists manuales y validaciones reproducibles del proyecto.

## Regla de uso

- Usa `README.md` para instalación, uso rápido y comandos principales.
- Usa `PENDIENTES.md` para estado vivo, prioridades, bloqueos y próximo paso.
- Usa `BITACORA.md` para evidencia detallada, resultados de corridas, errores y workarounds.
- Usa estos runbooks para ejecutar validaciones paso a paso de forma repetible.

## Índice

| Runbook | Cuándo usarlo | Evidencia principal |
|---|---|---|
| `desktop-linux.md` | Cerrar o retestar deltas de Fase 1 — Linux desktop binario | Evidencia ya capturada, smoke mínimo no redundante, `.md/.html/.csv`, copiar log y cierre limpio |
| `desktop-macos.md` | Cerrar Fase 3 — macOS native-host closure cuando haya host | Build `.app`, apertura local, smoke funcional pequeño, cierre limpio |
| `desktop-windows.md` | Mantener baseline de apoyo en Windows | Build `.exe`, smoke rápido/manual, WebView2/fallback si aplica; no sustituye Linux/macOS |
| `desktop-readiness-plan.md` | Imprimir un plan reproducible por plataforma o recolectar checks offline seguros | `desktop_readiness_plan.py`, `desktop_readiness_collect.py`, blockers por host, guardrails y comandos no ejecutados por defecto |
| `desktop-constraints.md` | Refrescar o auditar dependencias desktop | Constraints versionados, comando de instalación, validación mínima |
| `release-hygiene.md` | Antes/después de builds, smokes o limpieza de repo | Qué se versiona, qué se ignora, cómo registrar evidencia |
| `evidence-template.md` | Cerrar quick wins sin duplicar evidencia | Plantilla `BITACORA.md`, resumen `PENDIENTES.md`, variantes por slice |
| `docs-alignment.md` | Antes de cerrar slices que tocan docs | Source-of-truth por tema y checklist anti-drift |
| `slice-readiness.md` | Antes de implementar cualquier quick win/slice | Mini-ficha de alcance, riesgos, validación, docs, evidencia y no-hacer |
| `validation-matrix.md` | Elegir validación proporcional por wave/slice | Qué validar, cuándo escalar y qué no repetir |
| `smoke-test-catalog.md` | Copiar comandos mínimos de test/smoke por wave | Comando, propósito, prerequisito y cuándo no usarlo |
| `stop-on-failure.md` | Cuando falla una validación, smoke o build | Detener, reportar, proponer, pedir aprobación y escalar |
| `performance-warm-cache.md` | Preparar o medir corridas grandes/wishlists grandes | Warm-cache, logs, fallback individual, duración y artifacts |
| `json-export-contract.md` | Diseñar exports JSON separados de ofertas detectadas y wishlist completa sin exigir full warm-cache | Contratos `steam_deals_offers_export_v1` y `steam_deals_wishlist_export_v1`, cobertura parcial y fases futuras |
| `free-weekend-source-strategy.md` | Operar y auditar `Free Weekend ahora` global | Fuentes Store/records/LootScraper, precedencia, schema local, confianza/vigencia y no-go contra scraping frágil |
| `features-validation.md` | Validar features específicas sin cargar el README | Frontmatter Obsidian/Notion, `Tu Presupuesto Ideal`, share E2E, contrato Scheduler Web/Desktop |
| `wishlist-hygiene-windows-validation.md` | Validar en Windows que `wishlist_hygiene` se vea en Web UI/reportes y que el import local opcional funcione como revisión | JSON `wishlist_hygiene.items`, sección `Revisar wishlist`, `external_matches` advisory-only |
| `playnite-exporter-at-home.md` | Probar en casa el add-on Playnite source-only/dev y sus imports locales en Steam Tools | Build/carga externa de Playnite, exports library/access JSON, import Web/CLI y troubleshooting |
| `wishlist-hygiene-multistore-contract.md` | Consultar contrato y uso local de señales multi-store/play_access/steam_access para `wishlist_hygiene` | `--wishlist-external-matches-json`, `--play-access-json`, `--steam-access-json`, shapes aceptadas, señales aceptables/rechazadas y guardrails advisory-only |
| `multistore-price-comparison.md` | Planificar la comparativa de precios multi-tienda separada de `wishlist_hygiene` | Contrato `external_offers`, taxonomía de tiendas, ITAD/Fanatical, keyshops opt-in y no-checkout |
| `behavioral-signals-contract.md` | Diseñar o auditar `behavioral_signals_v1`, `behavioral_explanations_v1`, consumidores visibles Plan F, `player_behavior_profile_v1`, `player_behavior_fit_v1` y `decision_support_v1` | Taxonomía `data/behavioral_taxonomy_v1.json`, contrato advisory-only, degraded states, perfil local/opt-in, fit y decision support JSON-only |
| `decision-advisor-v0.md` | Usar campos existentes del reporte como asesor de compra/revisión sin recalcular score ni ranking | Capas oferta/compatibilidad/acceso/confianza, política no-fallback recommendations, prompt externo recomendado y decisiones advisory-only |

## Selector rápido por wave/tipo

| Objetivo | Usa | Validación mínima | No repetir / blocker |
|---|---|---|---|
| P0 seguridad local | `PENDIENTES.md` + `evidence-template.md` | tests dirigidos de seguridad/web | no `BG00G`; parar si falla seguridad |
| P0 performance | `performance-warm-cache.md` | fixtures/fake tests o parser offline | `BG00G` solo si medir performance es objetivo explícito |
| PAYDAY 2 data/UX | `features-validation.md` + `evidence-template.md` | cache/fake/live según slice | no hardcodear DLCs sin diagnóstico |
| P2 desktop Linux | `desktop-linux.md` | smoke mínimo con `joseluis12351` si solo hay deltas | no repetir E2E largo salvo gate release/runtime |
| P2 desktop macOS | `desktop-macos.md` | `.app` en host macOS nativo | CI/Windows/source no sustituyen host nativo |
| Windows baseline | `desktop-windows.md` | build/smoke rápido/manual | apoyo solamente; no cierra Linux/macOS |
| Plan/collector desktop previo | `desktop-readiness-plan.md` | `.venv/bin/python desktop_readiness_plan.py --platform all`; collector solo con `--execute-safe-checks` | no ejecuta builds/smokes/red ni cierra OS |
| Constraints desktop | `desktop-constraints.md` | install con constraints + tests dirigidos | no upgrades oportunistas |
| Release hygiene/evidencia | `release-hygiene.md`, `evidence-template.md` | `git status`, `git diff --check`, revisión docs | no commitear outputs/logs/reportes generados |
| Alineación documental | `docs-alignment.md` | revisión docs + `git diff --check` | no duplicar README/runbooks/backlog |
| Readiness previa al slice | `slice-readiness.md` | mini-ficha proporcional al cambio | no convertirlo en plan largo ni bloquear docs-only triviales |
| Validación mínima | `validation-matrix.md` | validación proporcional por wave/slice | no ejecutar red/build/`BG00G` si el slice no lo pide |
| Catálogo de comandos | `smoke-test-catalog.md` | comando mínimo según wave | no copiar comandos largos como smoke rápido |
| Stop-on-failure | `stop-on-failure.md` | detener y pedir aprobación antes de fix/retry | no avanzar sobre base roja |
| P3 arquitectura/drift | `PENDIENTES.md` + `evidence-template.md` | tests puros/shape compatible por slice | no rediseño UI ni refactor amplio mezclado |

## Criterio de registro

- Si el resultado cambia estado/prioridad/próximo paso, actualizar `PENDIENTES.md`.
- Si cambia un riesgo, blocker, tradeoff o decisión activa, actualizar el registro compacto en `PENDIENTES.md`.
- Si solo deja evidencia cronológica o detalles de ejecución, registrar en `BITACORA.md`.
- Si cambia uso público o comandos principales, actualizar `README.md`.
- No repetir `BG00G`/cold-cache ni smokes largos salvo objetivo performance explícito o gate de release declarado.
