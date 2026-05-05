# Runbook Evidence Template

Plantilla compacta para cerrar slices sin cargar `PENDIENTES.md` ni pegar logs largos.

## Regla base

- `BITACORA.md`: evidencia cronológica resumida, comandos, resultados, incidencias y decisión.
- `PENDIENTES.md`: estado vivo; solo resumen corto si cambia prioridad, bloqueo o próximo paso.
- No pegar logs completos, reportes HTML/JSON/CSV, tracebacks largos ni secretos; referenciar ruta/métrica/error relevante.

## Plantilla BITACORA

```markdown
- YYYY-MM-DD: Quick win <area/slice> <estado>. <Objetivo en 1 frase>. Evidencia: `<comando>` (<resultado>), `<comando>` (<resultado>), artefactos/logs: <ruta o resumen>. Incidencias: <ninguna o breve>. Impacto/decisión: <qué destraba o cambia>. Siguiente seguimiento: <ninguno o próximo slice>.
```

Campos mínimos:

| Campo | Incluir | Evitar |
|---|---|---|
| Objetivo | Qué se cerró y por qué importa | Repetir todo el plan |
| Evidencia | Comandos/tests/smoke + resultado | Logs completos |
| Artefactos | Rutas o nombres relevantes | Archivos generados enteros |
| Incidencias | Error breve y decisión | Traceback largo |
| Seguimiento | Próximo paso o `ninguno` | Nuevo backlog duplicado |

## Resumen PENDIENTES

Usar una sola frase dentro del item:

```markdown
[Cerrado YYYY-MM-DD: <impacto>; validado con <tests/smoke/revisión>; queda <bloqueo o ninguno>. Evidencia detallada en BITACORA.]
```

## Variantes rápidas

- Docs-only: `Evidencia: revisión documental + git diff --check OK; no builds/smokes.`
- Tests-only: listar comando exacto, suite y conteo (`59 OK`, `32 selected OK`).
- Desktop manual: host/sesión, build/binario, acción UI, outputs, cierre/procesos y fallback si aplica.
- Performance: fixture/cache, duración, candidates, HTTP/fallback/deferred; ruta del log, no log completo.
- PAYDAY 2/data-cache: fuente (`cache`, `fake Steam`, `live`), cambios de ownership/cache y validación sin secretos.
