# Runbook Release Hygiene

Política compacta para que builds, smokes y corridas reales dejen evidencia útil sin ensuciar el repo.

## Regla base

- Versionar solo source-of-truth: código, `web/*`, `assets/*`, tests, docs/runbooks, requirements/constraints y workflows.
- Mantener locales los artefactos generados: `output/`, `logs/`, `.cache/`, `build/`, `dist/`, reportes `Steam Deals*`, `PAYDAY2_Plan_de_Compra.*` y `*.spec`.
- Registrar evidencia por resumen/ruta en `BITACORA.md`; no pegar reportes completos, logs largos ni HTML/JSON generados.
- Si un output se vuelve fixture/documentación, moverlo a `tests/fixtures/` o `docs/` con nombre estable y contexto.

## Clasificación rápida

| Tipo | Política | Notas |
|---|---|---|
| Código, assets, UI web, tests | Versionar | Source-of-truth del producto. |
| README, runbooks, `PENDIENTES.md`, `BITACORA.md` | Versionar | Estado y evidencia compacta. |
| `requirements-desktop.txt`, `constraints/desktop.txt`, CI | Versionar | Resolución desktop reproducible. |
| `output/`, `logs/`, `.cache/` | No versionar | Evidencia local; conservar cache útil. |
| `build/`, `dist/` | No versionar | Artefactos de PyInstaller/CI. |
| `Steam Deals*.md/.html/.json/.csv`, `PAYDAY2_Plan_de_Compra.*` | No versionar | Reportes generados por corridas reales. |
| `SteamToolsDesktop.spec` / `*.spec` | No versionar | Spec generado/local con rutas absolutas; `build_desktop.py` es la fuente operativa. |

## Antes y después de smokes/builds

1. Antes: revisar `git status --short` para separar cambios source de ruido local.
2. Ejecutar smoke/build con rutas esperadas por runbook.
3. Guardar en `BITACORA.md` con `docs/runbooks/evidence-template.md`: comando, resultado, ruta de log/artefacto, incidencia y decisión.
4. Después: revisar `git status --short`; si aparece output generado, ajustar `.gitignore` o moverlo a fixture/docs con intención explícita.

## Decisión sobre `SteamToolsDesktop.spec`

Por ahora `SteamToolsDesktop.spec` es artefacto generado/local: está ignorado como `*.spec` y puede contener rutas absolutas del host. No editarlo ni usarlo como requisito de repo limpio. Si una release necesita spec estable versionado, abrir un slice separado para limpiar rutas, quitar el ignore, alinear con `build_desktop.py` y agregar validación.
