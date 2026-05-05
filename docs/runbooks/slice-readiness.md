# Slice readiness

Checklist compacto para arrancar quick wins sin mezclar alcance, validación y evidencia. No reemplaza a `PENDIENTES.md`: solo deja claro qué se va a tocar antes de implementar.

## Cuándo usarlo

- Antes de cualquier slice que toque código, tests, packaging, UI, cache, seguridad o docs permanentes.
- En docs-only triviales puede ser una mini-ficha de 3-5 líneas; no hace falta crear un plan largo.
- Si aparece un blocker real (`macOS` sin host nativo, red real, `BG00G` cold-cache, build largo), declararlo aquí antes de ejecutar.

## Mini-ficha

```markdown
### Readiness: <slice>

- Objetivo: <resultado verificable en una frase>
- Fuera de alcance: <qué NO se va a mezclar>
- Archivos probables: <rutas o áreas>
- Dependencias/prerrequisitos: <host, red, cache, build, fixtures, contexto>
- Riesgos/blockers: <compatibilidad, seguridad, performance, host nativo>
- Validación mínima: <tests/smoke/revisión proporcional al cambio>
- Docs afectados: <README, runbooks, PENDIENTES, BITACORA, ninguno>
- Evidencia esperada: <qué se registra y dónde>
- Rollback/compatibilidad: <cómo revertir o preservar comportamiento>
- No hacer: <límites explícitos del slice>
```

## Variantes ligeras por tipo

| Tipo de slice | Énfasis de readiness | Validación mínima típica | No hacer |
|---|---|---|---|
| Docs-only | Source-of-truth y enlaces afectados | Revisión documental + `git diff --check` | Builds, smokes largos o repetir evidencia |
| P0 seguridad local | Endpoints, secretos, errores públicos, Web/Desktop/PAYDAY 2 | Tests dirigidos de seguridad/web | `BG00G`, cambios UX amplios, continuar si falla seguridad |
| P0 performance | Fixtures fake/cache/time, métricas nuevas, hot-cache intacto | Tests determinísticos sin red real | Cold-cache largo salvo objetivo explícito |
| PAYDAY 2 data/UX | Cache, `--no-cache`, Steam API, ownership manual | Tests fake/cache + assets si cambia UI | Hardcodear DLCs sin diagnóstico |
| P2 desktop | Source vs frozen vs host nativo, fallback web, outputs/cache/logs | Tests dirigidos + smoke manual solo si aplica | Cerrar macOS sin `.app` en host nativo |
| P3 arquitectura | Fronteras, response shape, compatibilidad legacy | Tests puros + shape compatible | Rediseño UI o refactor amplio mezclado |
| Release hygiene | Artefactos, logs, ignore, evidencia | `git status`, `git diff --check`, revisión docs | Versionar outputs/logs/reportes generados |

## Ejemplo aplicado: PAYDAY 2 force refresh

- Objetivo: agregar una acción Web secundaria para forzar refresh live usando `--no-cache`.
- Fuera de alcance: no diagnosticar DLC faltante por appid/nombre y no cambiar TTLs.
- Archivos probables: `payday2_web.py`, `web/payday2/*`, tests PAYDAY 2, docs PAYDAY 2 si cambia copy.
- Dependencias/prerrequisitos: usar fixtures fake/cache; red real no es requisito de cierre.
- Riesgos/blockers: filtrar secretos en `argv`, perder ownership manual, bloquear si ya hay refresh corriendo.
- Validación mínima: command builder normal/force, acción UI visible, 409/lock existente respetado.
- Docs afectados: runbook o guía PAYDAY 2 si cambia el flujo recomendado.
- Evidencia esperada: comandos/resultados compactos en `BITACORA.md`; cierre corto en `PENDIENTES.md`.
- Rollback/compatibilidad: refresh normal conserva cache y comportamiento actual; force queda opt-in.
- No hacer: no hardcodear DLCs, no prometer que Steam expone todos los packages/bundles.

## Cierre

Al terminar el slice, usar `docs/runbooks/evidence-template.md` para registrar evidencia y `docs/runbooks/docs-alignment.md` para verificar que README/runbooks/backlog/bitácora no se contradicen.
