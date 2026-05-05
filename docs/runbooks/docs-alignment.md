# Runbook Docs Alignment

Matriz compacta para evitar drift entre README, runbooks, backlog, bitácora y contexto técnico.

## Source-of-truth por información

| Información | Vive en | No duplicar en |
|---|---|---|
| Estado, prioridades, blockers, próximo paso | `PENDIENTES.md` | README/runbooks |
| Evidencia, comandos ejecutados, incidencias | `BITACORA.md` | `PENDIENTES.md` largo |
| Uso público, instalación, comandos principales | `README.md` | backlog/bitácora |
| Procedimientos, checklists, smokes | `docs/runbooks/*.md` | README largo |
| Reglas del repo y source-of-truth | `docs/project-rules.md` | entradas históricas |
| Realidad técnica/arquitectura | `.opencode/context/project-intelligence/technical-domain.md` | runbooks operativos |

## Temas activos y docs que tocar

| Tema | Actualizar juntos |
|---|---|
| P0 seguridad local | `PENDIENTES.md`, `BITACORA.md`, tests/evidencia; README solo si cambia uso público |
| Performance cache/BG00G | `PENDIENTES.md`, `BITACORA.md`, `performance-warm-cache.md` |
| PAYDAY 2 data/cache | `PENDIENTES.md`, `BITACORA.md`, `features-validation.md`, `README.md` si cambia uso |
| P2 desktop/runtime/fallback/constraints | `PENDIENTES.md`, `BITACORA.md`, `desktop-*.md`, `desktop-constraints.md` |
| Release hygiene/evidencia | `release-hygiene.md`, `evidence-template.md`, `docs/project-rules.md` |
| P3 arquitectura/drift | `PENDIENTES.md`, `BITACORA.md`, contexto técnico si cambia frontera/stack |

## Antes de cerrar un slice

1. ¿Cambió estado/prioridad/bloqueo? → actualizar `PENDIENTES.md`.
2. ¿Hay comandos/tests/smokes/incidencias? → registrar en `BITACORA.md` usando `evidence-template.md`.
3. ¿Cambió uso/comando público? → actualizar `README.md`.
4. ¿Cambió procedimiento repetible? → actualizar runbook específico.
5. ¿Cambió arquitectura, stack o frontera permanente? → actualizar contexto técnico o reglas del repo.

Regla: documentar una vez, enlazar desde el resto. Si dudas, poner estado en `PENDIENTES.md` y evidencia en `BITACORA.md`.
