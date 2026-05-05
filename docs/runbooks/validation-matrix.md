# Matriz de validación mínima

Guía compacta para escoger validación proporcional por wave/slice. La matriz define **qué tipo de evidencia mínima** se espera; los comandos concretos viven en `smoke-test-catalog.md`.

## Regla base

1. Completa la mini-ficha de `slice-readiness.md` antes de implementar.
2. Usa la validación más pequeña que cubra el riesgo real del cambio.
3. Si falla una validación mínima, detén la wave: registra el fallo, propone fix y no avances a otro slice sobre base roja.
4. No ejecutes red real, build, smoke manual, `BG00G` ni cold-cache largo salvo que el objetivo del slice lo pida explícitamente.

## Matriz por wave/slice

| Wave/slice | Validación mínima | Manual/smoke permitido | Prerrequisitos/blockers | Evidencia esperada |
|---|---|---|---|---|
| Docs-only / release hygiene | Revisión documental, enlaces coherentes y `git diff --check` | No | Ninguno; no requiere runtime | Entrada compacta en `BITACORA.md` y cierre corto en `PENDIENTES.md` |
| P0 seguridad local | Tests dirigidos de helpers/web/assets y casos error/edge; revisar secretos, rutas, Host, tokens y serving | Solo smoke local pequeño si cambia flujo visible | No usar `BG00G`; parar si falla seguridad | Tests OK, endpoint/guardrail cubierto y sin secretos/rutas/tracebacks públicos |
| P0 performance determinística | Tests con fixtures fake cache/fetch/time; parser offline si cambia resumen/log | `BG00G` solo para benchmark aprobado | Sin red real por defecto; hot-cache debe seguir fast path | Métricas nuevas parseadas, cache vieja útil preservada y no cold-cache accidental |
| PAYDAY 2 data/UX | Tests fake/cache y assets/copy si cambia UI; validar ownership manual y secretos fuera de `argv` | Red live solo para diagnóstico aprobado | No hardcodear DLCs; Steam puede no exponer packages/bundles | Cache/force/diagnóstico explicados, flujo Web/CLI compatible |
| P2 desktop source/frozen/fallback | Tests dirigidos de runtime paths, Doctor, desktop share/assets y fallback según área tocada | Smoke pequeño con `joseluis12351` si cambia launcher/build/runtime | macOS requiere host nativo; Windows es apoyo; no repetir Linux E2E largo | Source/frozen no divergen, cache/log/output persistentes y cierre limpio si hubo smoke |
| P3 arquitectura/drift | Tests puros del módulo extraído + regresión de response shape/contratos legacy | Manual solo si cambia UX visible | No rediseñar UI ni mover múltiples fronteras en un slice | Formato compatible, imports/fronteras saneadas y links/payloads legacy conservados |
| Outputs/reportes/Share | Tests de serving/renderer/payload y marcadores estables; revisar allowlist y CSP si aplica | Smoke pequeño si se valida UX final | No commitear reportes generados; no comparar documentos completos byte-for-byte | HTML/MD/JSON/CSV o Share conservan acciones principales y evidencia por ruta/resumen |
| Cross-platform manual | Runbook de OS correspondiente + smoke mínimo definido | Sí, solo cuando hay host gráfico/nativo disponible | macOS `.app` no se cierra con CI/source; Linux E2E largo no se repite sin gate | Comando, resultado, incidencia, workaround y cierre en `BITACORA.md` |

## Escalación

- **Sube de docs-only a tests** si el cambio toca copy que habilita/deshabilita flujo, comandos o contrato esperado.
- **Sube de tests a smoke manual** si cambia comportamiento visible, launcher, build/frozen runtime, clipboard, fallback web o archivos generados.
- **Sube a benchmark/cold-cache** solo si el objetivo declarado es performance real con cache controlado.
- **Bloquea cierre** si falta host nativo macOS, falla seguridad, cambia response shape sin migración o aparece evidencia contradictoria entre `PENDIENTES.md`, `BITACORA.md` y runbooks.

## Relación con otros runbooks

- `slice-readiness.md`: define alcance, riesgos y validación mínima antes de tocar archivos.
- `smoke-test-catalog.md`: lista comandos copiables para ejecutar la validación elegida.
- `stop-on-failure.md`: define qué hacer si la validación elegida falla.
- `evidence-template.md`: define cómo registrar el resultado sin pegar logs largos.
- `docs-alignment.md`: evita drift entre README, runbooks, backlog y bitácora.
- `release-hygiene.md`: define qué artefactos/logs/specs no se versionan después de validar.
