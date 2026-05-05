# Catálogo de smokes/tests por wave

Comandos copiables para validar slices sin buscar en la bitácora. Este catálogo complementa `validation-matrix.md`: primero decide **qué tipo de validación** aplica, luego copia el comando mínimo.

## Regla base

- Usa `.venv/bin/python` si existe; si no hay venv, reemplaza por `python3`.
- Si un comando falla, sigue `stop-on-failure.md`: detén el avance, reporta el fallo, propone fix y pide aprobación antes de corregir.
- No ejecutes build, smoke manual, red real, `BG00G` ni cold-cache salvo que el slice lo pida explícitamente.
- Mantén los comandos largos fuera del cierre docs-only.

## Comandos rápidos

| Área | Comando mínimo | Cuándo usar | No usar cuando |
|---|---|---|---|
| Docs-only / release hygiene | `git diff --check` | Cambios solo docs/runbooks/backlog/bitácora | No sustituye tests si tocaste código |
| Estado de repo | `git status --short` | Antes de cerrar o preparar commit | No como evidencia funcional |
| P0 seguridad base | `.venv/bin/python -m unittest tests.test_config_security tests.test_generated_files_serving tests.test_shared_web_infra tests.test_web_assets` | Config pública, `/files`, errores, assets, helpers web | No cubre por sí solo Host ni desktop |
| P0 seguridad Host/desktop | `.venv/bin/python -m unittest tests.test_host_loopback_steam_deals tests.test_host_loopback_payday2 tests.test_desktop_share` | Host loopback, DNS rebinding, desktop/share relacionado | No usar si no tocaste esos frentes |
| P0 performance parser | `.venv/bin/python -m unittest tests.test_warm_cache_summary` | Cambios en resumen offline/log parser | No valida cache policy completa |
| P0 performance cache/policy | `.venv/bin/python -m unittest tests.test_generator_logic tests.test_warm_cache_summary` | Cache, fallback, stale/jitter, métricas | No lanzar red real ni `BG00G` por defecto |
| PAYDAY 2 data/UX | `.venv/bin/python -m unittest tests.test_web_assets tests.test_shared_web_infra tests.test_shared_cache_utils tests.test_runtime_paths` | Copy/UI PAYDAY 2, cache/shared infra, runtime helpers | No diagnostica Steam live ni DLC faltante real |
| P2 desktop/readiness | `.venv/bin/python -m unittest tests.test_runtime_paths tests.test_desktop_share tests.test_desktop_doctor tests.test_web_assets` | Paths frozen/source, Doctor, desktop bridge/assets | No cierra macOS ni reemplaza host nativo |
| Outputs/reportes/Share | `.venv/bin/python -m unittest tests.test_generated_files_serving tests.test_web_assets tests.test_desktop_share` | Serving de reportes, acciones finales, Share | No commitear reportes generados |
| P3 arquitectura/drift | `.venv/bin/python -m unittest tests.test_web_assets tests.test_shared_web_infra tests.test_desktop_share` | Fronteras web/shared/desktop sin módulo nuevo | Agrega tests puros específicos si extraes módulo |

## Comandos opcionales por contexto

| Contexto | Comando | Requisito | Nota |
|---|---|---|---|
| Performance selectivo con `pytest` disponible | `.venv/bin/python -m pytest tests/test_generator_logic.py -k "price_cache or fallback or cooldown or http_400" tests/test_warm_cache_summary.py` | `pytest` instalado en venv | Úsalo solo si ya es el patrón del slice; no lo vuelvas requisito global |
| Py compile dirigido | `.venv/bin/python -m py_compile <archivo1.py> <archivo2.py>` | Código Python tocado | Complementa tests; no reemplaza behavior tests |
| Desktop rebuild | `.venv/bin/python build_desktop.py --skip-install` | Cambio en build/frozen/launcher y aprobación explícita | Puede tardar; registrar warnings no fatales por resumen |
| Fallback web dirigido | `BROWSER=/bin/false .venv/bin/python steam_tools_desktop.py --force-web-fallback` | Slice fallback web o cierre manual | No requiere run largo; validar URL/mensaje/hint |
| Smoke pequeño Steam Deals | perfil `https://steamcommunity.com/id/joseluis12351` | Validación funcional explícita con red | Usar cache controlado y evidencia compacta |
| Benchmark grande | perfil `BG00G` | Objetivo performance explícito y ventana larga | Nunca usar como smoke rápido |

## Evidencia mínima

Registra en `BITACORA.md` solo comando, resultado resumido, duración si importa, rutas de artefactos/logs si aplica, incidencias y decisión. En `PENDIENTES.md` deja solo el cierre que cambie estado/prioridad/próximo paso.
