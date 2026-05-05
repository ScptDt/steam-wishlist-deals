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
| `desktop-linux.md` | Cerrar Fase 1 — Linux desktop binario | Build, apertura nativa, smoke largo desde binario, `.md/.html/.csv`, cierre limpio |
| `desktop-macos.md` | Cerrar Fase 3 — macOS native-host closure | Build `.app`, apertura local, smoke funcional, cierre limpio |
| `desktop-windows.md` | Mantener baseline de apoyo en Windows | Build `.exe`, smoke rápido/manual, WebView2/fallback si aplica |
| `desktop-constraints.md` | Refrescar o auditar dependencias desktop | Constraints versionados, comando de instalación, validación mínima |
| `performance-warm-cache.md` | Preparar o medir corridas grandes/wishlists grandes | Warm-cache, logs, fallback individual, duración y artifacts |
| `features-validation.md` | Validar features específicas sin cargar el README | Frontmatter Obsidian/Notion, `Tu Presupuesto Ideal`, share E2E |

## Criterio de registro

- Si el resultado cambia estado/prioridad/próximo paso, actualizar `PENDIENTES.md`.
- Si solo deja evidencia cronológica o detalles de ejecución, registrar en `BITACORA.md`.
- Si cambia uso público o comandos principales, actualizar `README.md`.
