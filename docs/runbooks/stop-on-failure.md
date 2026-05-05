# Stop-on-failure y escalación

Política compacta para no avanzar sobre una base roja. Aplica a cualquier slice con validación mínima, smoke manual, build, benchmark o revisión documental.

## Regla base

Si falla una validación mínima:

1. **Detener** el slice/wave actual; no pasar al siguiente slice.
2. **Reportar** el fallo con comando, salida resumida, archivo/ruta afectada y riesgo.
3. **Proponer** una opción de manejo.
4. **Pedir aprobación** antes de corregir, repetir comandos largos, hacer rebuild, smoke manual o benchmark.
5. **Registrar** en `BITACORA.md` si deja evidencia/incidencia; actualizar `PENDIENTES.md` solo si cambia estado, prioridad, blocker o decisión.

## Decisiones permitidas

| Decisión | Cuándo usarla | Qué hacer |
|---|---|---|
| `fix-forward` | Fallo acotado, causa clara y fix pequeño | Pedir aprobación, corregir el mismo slice y repetir validación mínima |
| `revert/pause` | El fix crece, cambia alcance o rompe contrato | Pausar, proponer revertir o dejar el slice abierto |
| `blocked por host/red` | Falta macOS nativo, host gráfico, red real o ventana larga | Marcar blocker y no sustituir con evidencia parcial |
| `downgrade a backlog` | El problema no es requisito del slice actual | Registrar follow-up en `PENDIENTES.md` y cerrar solo si el slice sigue válido |
| `alinear docs` | La falla es contradicción documental o evidencia incompleta | Corregir docs fuente de verdad y registrar decisión compacta |

## Stop conditions por wave

| Wave/slice | Detener si aparece | Escalación típica |
|---|---|---|
| Docs-only / release hygiene | `git diff --check` falla, docs se contradicen, se intenta commitear output/log/spec generado | Alinear docs o pausar hasta limpiar repo |
| P0 seguridad local | Se exponen secretos/rutas/tracebacks, `/files` sale de allowlist, CSRF permite POST sin token, Host acepta externo o bloquea localhost válido | `fix-forward` solo con test dirigido; si no, `revert/pause` |
| P0 performance | Hot-cache empieza a fetch, cache vieja útil se pierde, `--no-cache` queda ambiguo, parser no lee logs viejos, aparece red/`BG00G` no planificado | Pausar; no lanzar benchmark como reacción improvisada |
| PAYDAY 2 | Ownership manual se pierde, force refresh filtra secretos en `argv`, cache normal/force se confunden, diagnóstico intenta hardcodear DLC sin Steam | `fix-forward` con fixtures fake o `downgrade` a diagnóstico separado |
| P2 desktop | Source/frozen divergen, Doctor oculta fallos reales o suma falsos FAIL, fallback web muere, cache/log/output apuntan a `_MEI`, macOS se quiere cerrar sin host nativo | Bloquear por host o repetir solo smoke mínimo aprobado |
| P3 arquitectura/drift | Response shape cambia sin migración, links Share legacy fallan, import guardrail se rompe, refactor se vuelve rediseño UI | `revert/pause` o dividir slice antes de seguir |
| Outputs/reportes/Share | HTML/MD/JSON/CSV cambian contrato, Share pierde `steamtools://`/link Steam, CSP/allowlist se debilita, se generan artefactos versionados | Fix dirigido + tests de serving/payload; limpiar artefactos locales |

## Reanudar después de un fallo

- Reanudar solo cuando la validación mínima original pase de nuevo o el usuario apruebe cambiar el criterio.
- Si el fallo se acepta como blocker, actualizar el registro compacto de riesgos/decisiones en `PENDIENTES.md`.
- Si se repite una validación larga, documentar por qué se repite y qué cambió.
- Si se agrega un follow-up, debe tener alcance y no-hacer claros; no ocultar fallos como “pendiente menor” si bloquean el slice actual.

## Relación con otros runbooks

- `slice-readiness.md`: declara riesgos, validación mínima y no-hacer antes de ejecutar.
- `validation-matrix.md`: decide qué validación es proporcional.
- `smoke-test-catalog.md`: provee comandos concretos.
- `evidence-template.md`: registra el resultado sin logs largos ni secretos.
