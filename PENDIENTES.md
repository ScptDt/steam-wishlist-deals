# Pendientes (Fuente Unica)

Ultima actualizacion: 2026-04-16

## Regla de Oro

Este archivo es la fuente unica de verdad para:
- pendientes activos
- backlog de features
- plan cross-platform
- estado de ejecucion y bitacora

No se mantienen documentos paralelos de planificacion; este archivo es la unica fuente.

## Estado General

- Objetivo: llevar Steam Tools a una experiencia ultra user friendly y preparada para ejecutable desktop.
- Fase actual: P2 en validacion cross-platform (cierre manual pendiente por host nativo).
- Item activo: avanzar con pendientes no bloqueados desde Windows mientras Linux/macOS quedan en espera de host nativo.

## Pendientes Priorizados

### P0 - Estabilidad

- [x] Empaquetado con PyInstaller (build inicial) validado en Windows.
- [x] Checklist de release y smoke tests (primera version).

### P1 - UX Ultra Friendly

- [x] Banner de modo: primer setup vs actualizacion.
- [x] Errores accionables por categoria (network/config/rate-limit/encoding).
- [x] Presets de ejecucion (rapido, completo, ahorro).

### P2 - Cross-platform

- [ ] Validar build desktop en Linux (Ubuntu LTS). [Parcial alto: build local OK, ventana nativa + server local confirmados en sesion no-root, packaging PyInstaller corregido y primer evento `progress` validado dentro del binario congelado; falta smoke funcional completo con outputs `.md/.html/.csv` y cierre limpio.]
- [ ] Validar build desktop en macOS (app bundle + apertura local).
- [x] Documentar dependencias nativas por plataforma para pywebview.
- [ ] Validar cross-platform el fallback web: si `pywebview` no es compatible o no inicia backend nativo, abrir la Web UI en el navegador por defecto con aviso visible en la interfaz. [Linux parcial OK: fallback confirmado en primer intento sin backend, luego ventana nativa OK con Qt/X11; falta host nativo/macOS.]

### P3 - Base tecnica y mantenibilidad

- [x] Blindar handlers web: JSON invalido -> 400, validacion de boundaries y errores mas accionables.
- [x] Aclarar `README.md` por superficies: core stdlib, desktop con deps extra y posicionamiento de modulos.
- [x] Separar HTML/CSS/JS embebido de `steam_deals_web.py` y `payday2_web.py`.
- [x] Extraer infraestructura compartida para web local (JSON, SSE, subprocess, server utils).
- [x] Reutilizar la base compartida entre Steam Deals Web y PAYDAY 2 Web.
- [x] Modularizar `steam_deals_generator.py` por dominios (config, adapters, cache, scoring, renderers, orchestration) [cerrado: migracion estructural a `app/` en fases 1A-1D + cortes `cache policy / cache lifecycle`, `enrichment orchestration`, `family`, `output final`, `ITAD orchestration`, `post-processing` y `engagement/post-run` completados; limpieza final de residuos wrappers `empty_*` en el generador].
- [x] Hacer limpieza local del repo: depurar archivos, artefactos, scripts y restos de baja utilidad actual para reducir ruido y costo de mantenimiento.
- [x] Hacer limpieza de GitHub y documentacion: depurar README, docs y referencias/metadatos del repo para reflejar solo flujos y superficies vigentes.
- [x] Agregar smoke tests minimos para web, desktop y PAYDAY 2.
- [x] Agregar tests para logica pura critica (score, filtros, compare, budget, recomendaciones).
- [x] Crear capa shared entre Steam Deals y PAYDAY 2 para config/cache/helpers reutilizables.

Nota actual sobre la capa shared Steam Deals / PAYDAY 2:
- Completado en un primer corte pragmatico: `shared/io_utils.py` + `shared/cache_utils.py` centralizan config JSON, HTTP JSON y helpers genericos de cache reutilizados por `steam_deals_generator.py` y `payday2_dlc_tracker.py`.
- Los formatos de cache/historial siguen siendo propios de cada app cuando corresponde, pero ya sobre helpers compartidos.

Nota actual sobre `steam_deals_generator.py`:
- La modularizacion por dominios sigue en enfoque **incremental** por cortes pequenos para evitar elevar riesgo.
- Avance ya hecho: primer corte `renderers/` completado con extraccion de Markdown, HTML, Share HTML y CSV.
- Avance ya hecho adicional: barrido de integracion final del corte `renderers/` validado para CLI/web y la ruta desktop segura `--internal-web`.
- Avance ya hecho adicional: corte `scoring / recommendations` extraido a `steam_deals_recommendations.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `scoring / recommendations`: tests de logica pura OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `HLTB / matching` extraido a `steam_deals_hltb.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `HLTB / matching`: tests de logica pura OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `filters / selection` extraido a `steam_deals_filters.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `filters / selection`: tests de logica pura OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `history / comparison / local trends` extraido a `steam_deals_history.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `history / comparison / local trends`: tests de logica pura OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `ITAD adapter / integration` extraido a `steam_deals_itad.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `ITAD adapter / integration`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `watchlist` extraido a `steam_deals_watchlist.py` con wrappers de compatibilidad en `steam_deals_generator.py` y reuse desde `steam_deals_web.py`.
- Validacion del corte `watchlist`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `Steam account/profile/sale adapter` extraido a `steam_deals_steam_api.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `Steam account/profile/sale adapter`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `notifications` extraido a `steam_deals_notifications.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `notifications`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `scheduler` extraido a `steam_deals_scheduler.py` con wrapper compatible en `steam_deals_generator.py`.
- Validacion del corte `scheduler`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `config / CLI boundary` extraido a `steam_deals_config.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `config / CLI boundary`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `presentation helpers / badges / grouping` extraido a `steam_deals_presentation.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `presentation helpers / badges / grouping`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `metadata enrichment fetchers/caches` extraido a `steam_deals_enrichment.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `metadata enrichment fetchers/caches`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `Steam price-fetch/cache` extraido a `steam_deals_prices.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `Steam price-fetch/cache`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `run/output orchestration slice` extraido a `steam_deals_run_output.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `run/output orchestration slice`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `runtime progress / event reporting` extraido a `steam_deals_runtime_reporting.py` y alineado con `steam_deals_web.py`.
- Validacion del corte `runtime progress / event reporting`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py`.
- Avance ya hecho adicional: corte `cache policy / cache lifecycle` extraido a `steam_deals_cache_policy.py` con wrappers de compatibilidad en `steam_deals_generator.py`.
- Validacion del corte `cache policy / cache lifecycle`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py`.
- Avance ya hecho adicional: slice `enrichment orchestration` extraido a `steam_deals_enrichment_orchestration.py` con coordinacion de reviews, Steam Deck, ProtonDB, anti-cheat, tags y achievements; `steam_deals_generator.py` conserva wrappers de compatibilidad.
- Validacion del slice `enrichment orchestration`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py`.
- Avance ya hecho adicional: slice `family` extraido a `steam_deals_family.py` con boundary para carga de `family_appids`, passthrough hacia HLTB y kwargs para renderers; `steam_deals_generator.py` conserva wrappers de compatibilidad.
- Validacion del slice `family`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py`.
- Avance ya hecho adicional: slice `output final` consolidado en `steam_deals_run_output.py` con boundary para rutas de artifacts, fan-out de escritura y closeout final; `steam_deals_generator.py` conserva wrappers de compatibilidad.
- Validacion del slice `output final`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py`.
- Avance ya hecho adicional: slice `ITAD orchestration` extraido a `steam_deals_itad_orchestration.py` con coordinacion de lookup, historical lows, current prices y bundles; `steam_deals_generator.py` conserva wrappers de compatibilidad.
- Validacion del slice `ITAD orchestration`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py`.
- Avance ya hecho adicional: slice `post-processing` extraido a `steam_deals_post_processing.py` con boundary para `hltb_hours`, filtros y `top_picks`; `steam_deals_generator.py` conserva wrappers de compatibilidad.
- Validacion del slice `post-processing`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py`.
- Avance ya hecho adicional: slice `engagement/post-run` extraido a `steam_deals_engagement_post_run.py` con orquestacion de `watchlist_alerts`, `budget_result`, `gift_ideas` y notificaciones; `steam_deals_generator.py` conserva wrappers de compatibilidad.
- Validacion del slice `engagement/post-run`: tests de logica/reconfiguracion OK en `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py`.
- Cierre de modularizacion: auditoria final de residuos de orchestration completada; `steam_deals_generator.py` queda como frontera de compatibilidad con orquestacion delegada a modulos `app/*` y sin wrappers `empty_*` redundantes.
- Validacion de cierre: `python -m pytest tests/test_generator_logic.py tests/test_shared_cache_utils.py` OK (76 tests).

### Nota de trabajo futuro - orden sugerido de ejecucion

- 1. Cerrar base actual: cross-platform + README + handlers robustos. ✅
- 2. Separar HTML/CSS/JS embebido. ✅
- 3. Extraer infraestructura compartida para web local. ✅
- 4. Reutilizar la base compartida entre Steam Deals y PAYDAY 2. ✅
- 5. Agregar smoke tests minimos reproducibles para web, desktop y PAYDAY 2. ✅
- 6. Agregar tests de logica pura critica. ✅
- 7. Crear capa shared reutilizable para config/cache/helpers. ✅
- 8. Modularizar `steam_deals_generator.py`. ✅

Objetivo de esta secuencia: bajar costo de mantenimiento sin frenar el avance del producto.

## Backlog de Features (Estado)

### Core app

- [x] Eventos estructurados web-run (base: progress/file).
- [x] Preflight de configuracion antes de run.
- [x] Acciones rapidas UX (probar config, limpiar cache, abrir ultimo reporte).
- [x] Reduccion de dependencia parser ANSI en web.
- [x] Clasificacion avanzada de errores y sugerencias accionables.

### Wizard / UX

- [x] Wizard de primer uso y vista de actualizacion.
- [x] Banner persistente de modo (setup/actualizacion).
- [x] Presets y modo "1-click run".

### Desktop (Opcion B)

- [x] Launcher pywebview base (`steam_tools_desktop.py`).
- [x] Build unificado (`build_desktop.py`).
- [x] Wrappers por plataforma (`build_desktop.ps1`, `build_desktop.sh`).
- [x] Smoke tests de ejecutable en Windows.
- [ ] Validacion Linux/macOS.

## Plan Cross-Platform (Consolidado)

### Objetivo

Ejecutar de forma consistente en Windows, macOS y Linux.

### Riesgos

- Dependencias nativas de `pywebview` por OS.
- Diferencias de empaquetado/firma (especialmente macOS).
- Diferencias de encoding y terminal.
- Diferencias de permisos/rutas de salida/cache.

### Estrategia

1. Runtime parity:
- Mantener fallback universal web (`steam_deals_web.py`).
- Asegurar `--no-open` y arranque estable del servidor local.

2. Desktop packaging:
- Windows: PyInstaller + pywebview.
- macOS: app bundle + validacion de apertura.
- Linux: binario PyInstaller + validacion en Ubuntu LTS.

3. Calidad de release:
- Matriz de compatibilidad.
- Checklist QA previo release.
- Bitacora de incidencias por plataforma.

### Build Entry Points

- Unificado: `python build_desktop.py`
- Windows: `powershell -ExecutionPolicy Bypass -File .\\build_desktop.ps1`
- Linux/macOS: `./build_desktop.sh`

### Checklist de Validacion por OS

1. Arranca app desktop y muestra ventana nativa.
2. Ejecuta preflight sin errores.
3. Corre analisis de prueba completo.
4. Genera MD/HTML/CSV.
5. Cierra sin procesos colgados.

### Matriz de validacion reproducible (Linux/macOS)

> Restriccion actual: este repo se esta operando desde entorno Windows. La validacion de Linux/macOS debe correrse en host nativo o runner CI del OS objetivo.

#### Linux (Ubuntu LTS)

1. Preparar entorno
   - Comando: `python3 --version && python3 -m pip --version`
   - Esperado: Python/pip disponibles y funcionales.
2. Instalar dependencias desktop
   - Comando: `python3 -m pip install -r requirements-desktop.txt`
   - Esperado: instalacion sin errores; `pywebview` instalado.
3. Build desktop
   - Comando: `python3 build_desktop.py`
   - Esperado: artefacto generado en `dist/SteamToolsDesktop` (o `dist/SteamToolsDesktop/` en `--onedir`).
4. Ejecutar app y validar ventana nativa
   - Comando: `./dist/SteamToolsDesktop`
   - Esperado: abre ventana nativa; UI responde.
5. Verificacion funcional minima
   - Acciones: correr preflight, ejecutar run de prueba, generar MD/HTML/CSV, cerrar app.
   - Esperado: sin crash, outputs presentes, sin procesos colgados.
6. Fallback web (mitigacion)
   - Comando: `python3 steam_deals_web.py --no-open --port 8080`
   - Esperado: servidor arriba en `http://127.0.0.1:8080` si la ventana nativa falla.

#### macOS (app bundle + apertura local)

1. Preparar entorno
   - Comando: `python3 --version && python3 -m pip --version`
   - Esperado: Python/pip disponibles y funcionales.
2. Instalar dependencias desktop
   - Comando: `python3 -m pip install -r requirements-desktop.txt`
   - Esperado: instalacion sin errores; `pywebview` instalado.
3. Build desktop
   - Comando: `python3 build_desktop.py`
   - Esperado: artefacto generado en `dist/`.
4. Abrir app local
   - Comando: `open dist/SteamToolsDesktop.app`
   - Esperado: app abre localmente y muestra UI.
5. Verificacion funcional minima
   - Acciones: correr preflight, ejecutar run de prueba, generar MD/HTML/CSV, cerrar app.
   - Esperado: sin crash, outputs presentes, sin procesos colgados.
6. Quarantine/permisos (si aplica)
   - Comando: `xattr -dr com.apple.quarantine dist/SteamToolsDesktop.app`
   - Esperado: app vuelve a abrir cuando Gatekeeper bloquee artefacto local no firmado.
7. Fallback web (mitigacion)
   - Comando: `python3 steam_deals_web.py --no-open --port 8080`
   - Esperado: servidor arriba en `http://127.0.0.1:8080` si la ventana nativa falla.

#### Ejecucion recomendada en CI/runners

- Linux: `ubuntu-latest` (GitHub Actions u otro runner Ubuntu LTS).
- macOS: `macos-latest` (runner nativo para validar app bundle/apertura local).
- Guardar bitacora por OS: resultado por paso, error textual y workaround aplicado.

### Formato minimo de evidencia por OS (para cierre reproducible)

Registrar por plataforma (Linux/macOS) en la bitacora:

1. **Build**
   - Comando ejecutado
   - Resultado (OK/FAIL)
   - Ruta de artefacto generado en `dist/`
2. **Apertura nativa**
   - Comando de apertura/ejecucion (`./dist/SteamToolsDesktop` o `open dist/SteamToolsDesktop.app`)
   - Resultado (ventana abre/no abre)
   - Error textual exacto si falla
3. **Smoke funcional minimo**
   - Preflight
   - Run de prueba
   - Outputs generados (`.md`, `.html`, `.csv`)
   - Cierre limpio (sin procesos colgados)
4. **Fallback web (mitigacion)**
   - Comando: `python3 steam_deals_web.py --no-open --port 8080`
   - Resultado (server arriba + acceso local)
5. **Notas de plataforma**
   - Linux: backend nativo/deps usadas (`Qt` o `GTK/WebKit`)
   - macOS: quarantine/codesign/notarizacion (si aplica distribucion)

### Criterio de cierre P2 (Done)

P2 se considera **cerrado** cuando se cumpla TODO:

- [ ] Linux validado en host nativo: build, apertura nativa, smoke funcional, cierre limpio y fallback documentado.
- [ ] macOS validado en host nativo: build, apertura `.app`, smoke funcional, cierre limpio y fallback documentado.
- [ ] Bitacora Cross-Platform actualizada con evidencia por paso (comando, resultado y workaround si aplica).
- [ ] README y/o notas operativas alineadas con incidencias reales encontradas en validacion manual.

## Proximo Paso Operativo

- Linux ya tiene evidencia local fuerte: en Debian/Ubuntu con PEP 668 se requiere `.venv`, el build desktop local genera `dist/SteamToolsDesktop`, la ventana nativa abre en sesion grafica no-root (forzando `QT_QPA_PLATFORM=xcb`) y el binario congelado ya emite el primer evento `progress` del generator tras corregir packaging PyInstaller.
- Validacion manual macOS queda **pospuesta intencionalmente** hasta contar con host nativo disponible.
- El runbook para cierre de P2 ya esta documentado en `README.md` y en `docs/runbooks/desktop-{linux,macos,windows}.md`; el criterio de evidencia queda definido en este archivo.
- Siguiente reactivacion: correr el smoke funcional largo de Linux (wishlist real 2K+ juegos: preflight, run completo, outputs y cierre limpio) en una ventana amplia; luego ejecutar checklist manual macOS y despues pegar evidencia final en bitacora para cierre P2.

## Plan inmediato (Windows / No bloqueado)

Mientras no haya host nativo Linux/macOS disponible para cierre manual de P2, la ejecucion recomendada es:

1. **Consolidar evidencia Windows desktop (runbook + smoke funcional manual)**
   - Repetir build + apertura local + smoke rapido + smoke funcional minimo y actualizar bitacora.
2. **Optimizacion de velocidad (P0) para wishlists grandes**
   - Cache mas agresivo (24h), mayor concurrencia de fetch y estrategia incremental por timestamps. [Parcial: cache policy ajustada para expirar en el borde del TTL (`>= 24h`) y refresh incremental por entrada con `_fetched_at`; validado con tests. Pendiente: subir concurrencia de fetch.]
3. **Output/Export de valor inmediato**
   - Export a Obsidian/Notion con frontmatter YAML. [Parcial avanzado: `--md-frontmatter` + guia de perfiles/checklist ya documentados en README; pendiente validacion manual final de importacion extremo a extremo en host real de Obsidian/Notion.]
4. **Dashboard historico HTML**
   - Navegacion entre runs + comparativa visual de precios. [Parcial implementado (MVP+3): selector Run A/Run B con paginado simple, busqueda de runs, quick compare de ultimos 2 runs, filtros por estado, orden por delta, persistencia local (`localStorage`), resumen por estado, Top Deltas (bajadas/subidas) y tendencia temporal simple (deals por run, ultimos 20 runs).]
5. **Alertas inteligentes (v2)**
   - Implementacion base v2 completada (minimo historico global, bundles activos, subidas vs run anterior, nueva mejor oferta local y umbrales configurables).
   - **Pendiente por tiempo**: calibracion fina de umbrales y ejecucion/validacion manual completa en corrida larga real.
   - **Se retoma en la proxima corrida** para cierre operativo final del frente de Alertas v2.

Notas:
- Este plan no bloquea el cierre futuro de P2; solo evita tiempo muerto mientras falta host nativo.
- El cierre formal de P2 sigue condicionado a evidencia manual Linux + macOS segun criterio de Done.

## Bitacora Cross-Platform por OS

| Fecha | Plataforma | Estado | Incidencias | Proximo paso |
|---|---|---|---|---|
| 2026-04-16 | Decision operativa | Linux muy avanzado / macOS pospuesto | Se ejecuto validacion local fuerte en Linux durante esta iteracion; macOS sigue pendiente por no contar aun con host nativo disponible. CI cross-platform permanece OK como evidencia parcial base (`24487556896`). El smoke funcional Linux queda diferido porque la wishlist real supera 2K juegos y requiere una ventana amplia. | Ejecutar smoke funcional largo Linux cuando haya ventana suficiente; luego reactivar runbook macOS para cierre P2. |
| 2026-04-16 | Linux (entorno local) | validacion manual avanzada | `python3`/`pip` OK. `python3 -m pip install -r requirements-desktop.txt` fallo en system Python por PEP 668 (`externally-managed-environment`), por lo que se uso `.venv`. Build local OK con `dist/SteamToolsDesktop`. Primer arranque del artefacto: fallback web confirmado por falta de backend nativo (`qtpy`/`gi`). Tras instalar `pywebview[qt]` y rehacer build, se confirmo ventana nativa + server local en sesion grafica no-root usando `runuser` + `QT_QPA_PLATFORM=xcb`. El smoke funcional completo encontro un bug real de packaging (`ModuleNotFoundError: shared`) dentro del binario congelado; se corrigio `build_desktop.py`/spec agregando `--paths` + `collect_submodules(shared/renderers/app)` + hidden imports, y luego un check liviano del binario valido el primer evento `progress` (`Resolviendo Steam ID...`) del generator ya empaquetado. Warning actual a revisar: `libtiff.so.5` en empaquetado Qt. | Ejecutar run largo con wishlist real para confirmar outputs `.md/.html/.csv` y cierre limpio; decidir luego si `libtiff.so.5` requiere nota/paquete adicional. |
| 2026-04-16 | Linux (Ubuntu LTS) | validado en CI (parcial) | Workflow `Desktop Cross-Platform Validation` OK en `ubuntu-latest` (run `24487556896`): install deps, build desktop, `py_compile`, check fallback local y artifact `dist-ubuntu-latest` publicado. Falta validacion manual en host Linux nativo para ventana real, preflight funcional completo y cierre sin procesos colgados. | Ejecutar checklist manual Linux en host Ubuntu LTS y registrar incidencias/workarounds de backend nativo `pywebview`. |
| 2026-04-16 | macOS | validado en CI (parcial) | Workflow `Desktop Cross-Platform Validation` OK en `macos-latest` (run `24487556896`): install deps, build desktop, `py_compile`, check fallback local y artifact `dist-macos-latest` publicado. Falta validacion manual en host macOS para apertura de `.app`, quarantine/codesign/notarizacion segun distribucion. | Ejecutar checklist manual macOS (apertura local, quarantine, codesign) y registrar incidencias/workarounds. |

## Bitacora

- 2026-04-16: Alertas v2 queda en estado pendiente operativo por tiempo: aunque la implementacion v2 esta lista, falta calibracion/ejecucion manual en corrida larga real. Se agenda retomar en la proxima corrida para validar ajuste final y cerrar el item.
- 2026-04-16: Cierre Alertas v2: alertas inteligentes ahora soportan umbrales configurables de subida (`--alert-rise-pct`), margen sobre minimo global (`--alert-global-margin-pct`) y priorizacion por score minimo (`--alert-score-min`), manteniendo compatibilidad por default. Se conserva integracion en resumen final corto del run.
- 2026-04-16: Cierre documental del flujo Obsidian/Notion: README ahora incluye perfiles de frontmatter recomendados y checklist manual de validacion de import (Obsidian + Notion) para ejecucion reproducible. Queda pendiente solo la validacion E2E manual en host real para marcar cierre total del item.
- 2026-04-08: Se crea este archivo como consolidado unico de pendientes.
- 2026-04-08: Se implementan eventos estructurados base (progress/file).
- 2026-04-08: Se añade preflight y acciones rapidas de UX.
- 2026-04-08: Se fortalece parser de salida web (menos dependencia ANSI).
- 2026-04-08: Se crea base desktop opcion B (pywebview + build unificado).
- 2026-04-08: Build PyInstaller completado en Windows; generado `dist/SteamToolsDesktop.exe`.
- 2026-04-08: Smoke test basico del ejecutable Windows OK (arranca proceso y cierre controlado).
- 2026-04-08: Se agrega `smoke_test_windows.ps1` como smoke test reproducible (arranque, API local, cierre limpio).
- 2026-04-08: Smoke test Windows reproducible validado con resultado `SMOKE_OK`.
- 2026-04-08: Se agrega banner de modo (primer setup vs actualizacion) en la web UI.
- 2026-04-08: Se agregan presets de ejecucion (rapido/completo/ahorro) con aplicacion en formulario.
- 2026-04-08: Se agrega clasificacion de errores por categoria (network/config/rate-limit/encoding) con sugerencias accionables en consola UI.
- 2026-04-09: Se implementa feature Compartir Deals (URL scheme steamtools://) con modal en Web UI y HTML generado. Falta probar con datos reales (requiere VPN o config de red para Steam API).
- 2026-04-11: Se blindan handlers web en Steam Deals/PAYDAY 2 (JSON invalido -> 400, limites de payload, validacion de payload/action y errores mas accionables).
- 2026-04-11: PAYDAY 2 Web inicia separacion UI embebida: `web/payday2/index.html` externo con loader/fallback en `payday2_web.py`; spec desktop actualizado para incluir el HTML.
- 2026-04-11: Steam Deals Web migra HTML a `web/steam_deals/index.html` con loader/fallback en `steam_deals_web.py`; build desktop/spec incluyen ambos HTML externos.
- 2026-04-11: PAYDAY 2 Web extrae CSS a `web/payday2/app.css` y sirve `GET /app.css`; build desktop/spec incluyen nuevo asset.
- 2026-04-13: Se completa la extraccion de UI restante: `web/steam_deals/app.css`, `web/steam_deals/app.js` y `web/payday2/app.js`; ambos web servers sirven `/app.css` y `/app.js` con fallback a HTML inline.
- 2026-04-13: Se agrega `shared_web_infra.py` y se reutiliza en Steam Deals/PAYDAY 2 para respuestas HTTP, lectura defensiva de JSON, assets de texto, subprocess y SSE local.
- 2026-04-13: Se corrige shutdown de `payday2_web.py` para cerrar limpio con refresh activo, incluyendo terminacion del child process.
- 2026-04-13: README se actualiza para aclarar superficies, dependencias desktop y mapa de modulos/entrypoints.
- 2026-04-13: Se agregan smoke tests locales minimos en `.tmp/local-smoke-tests/` para Steam Deals Web, PAYDAY 2 Web y la ruta segura desktop `--internal-web`; quedan fuera del flujo normal de Git en este clon. `smoke_test_windows.ps1` se mantiene como smoke separado para Windows empaquetado.
- 2026-04-13: Se agregan tests unitarios puros en `tests/test_generator_logic.py` para score, filtros, matching/gift ideas y budget picks.
- 2026-04-13: Se completa el primer corte de capa shared con `shared/io_utils.py` y `shared/cache_utils.py`; Steam Deals y PAYDAY 2 ya comparten helpers de config JSON, HTTP JSON y cache reutilizable, con tests locales para los helpers shared.
- 2026-04-14: Se extrae CSV a `renderers/csv_renderer.py` manteniendo wrapper compatible en `steam_deals_generator.py`; validacion puntual OK con `py_compile`, `steam_deals_generator.py --help`, `steam_deals_web.py --help` e import seguro de `steam_tools_desktop.py`.
- 2026-04-14: Se agrega pendiente explicito para asegurar/validar fallback al navegador cuando `pywebview` no sea compatible o no pueda iniciar backend nativo.
- 2026-04-14: `steam_tools_desktop.py` ahora abre la Web UI con flag explicito de fallback y la UI compartida muestra banner/aviso cuando `pywebview` no esta disponible, se demora demasiado o falla al iniciar; falta validar este comportamiento en Linux/macOS nativos.
- 2026-04-14: Se completa el barrido de integracion del corte `renderers/` con `py_compile`, `steam_deals_generator.py --help`, `steam_deals_web.py --help`, `steam_web_smoke.py` y `desktop_smoke.py`; el primer corte de modularizacion de `renderers/` queda validado.
- 2026-04-14: Se extrae `steam_deals_recommendations.py` con `build_gift_ideas`, `compute_value_score`, `rank_top_picks` y `compute_budget_picks`; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (9 tests).
- 2026-04-14: Se extrae `steam_deals_hltb.py` con parseo HLTB, normalizacion/matching y cruce HLTB × deals; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (11 tests).
- 2026-04-14: Se extrae `steam_deals_filters.py` con `filter_by_genres` y `apply_filters`; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (12 tests).
- 2026-04-14: Se extrae `steam_deals_history.py` con fallback al MD anterior, historial de runs, comparacion de deals, historial local de precios y formateo de tendencias; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (15 tests).
- 2026-04-14: Se extrae `steam_deals_watchlist.py` con I/O, comando CLI y alertas de watchlist; `steam_deals_generator.py` conserva wrappers compatibles, `steam_deals_web.py` reutiliza la misma frontera shared y `tests/test_generator_logic.py` queda OK (22 tests).
- 2026-04-14: Se extrae `steam_deals_itad.py` con lookup, minimos historicos, mejores precios actuales y bundles activos de ITAD; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (19 tests).
- 2026-04-14: Se extrae `steam_deals_scheduler.py` con parseo de `--schedule` y loop programado con dependencias inyectables; `steam_deals_generator.py` conserva wrapper compatible y `tests/test_generator_logic.py` queda OK (38 tests).
- 2026-04-14: Se extrae `steam_deals_steam_api.py` con resolucion de perfil/Steam ID, wishlist, owned games, compare, family JSON y oferta activa; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (28 tests).
- 2026-04-14: Se extrae `steam_deals_notifications.py` con resumen, Telegram, Discord y dispatcher de notificaciones; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (33 tests).
- 2026-04-14: Se extrae `steam_deals_config.py` con carga/guardado de config y boundary CLI/interactivo; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (41 tests).
- 2026-04-14: Se extrae `steam_deals_presentation.py` con badges, grouping por tier/tag y helpers de presentacion compartidos por renderers; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (44 tests).
- 2026-04-14: Se extrae `steam_deals_enrichment.py` con fetch paralelo, reviews, Steam Deck, ProtonDB, anti-cheat, tags y achievements; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (48 tests).
- 2026-04-14: Se extrae `steam_deals_prices.py` con cache de precios, fetch batch con fallback individual y normalizacion de `deals`; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (51 tests).
- 2026-04-14: Se extrae `steam_deals_run_output.py` con nombre de archivos, fallback al MD anterior, escritura de artefactos y resumen final; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` queda OK (55 tests).
- 2026-04-14: Se extrae `steam_deals_runtime_reporting.py` con symbols Unicode-safe, estilos ANSI, contrato de eventos y step/progress reporting; `steam_deals_generator.py` conserva wrappers compatibles, `steam_deals_web.py` reutiliza el mismo `EVENT_PREFIX` y `tests/test_generator_logic.py` queda OK (58 tests).
- 2026-04-15: Se completa migracion estructural incremental a `app/` con wrappers de compatibilidad en raiz (fases 1A-1D): `steam_deals_filters.py`, `steam_deals_hltb.py`, `steam_deals_recommendations.py`, `steam_deals_runtime_reporting.py`, `steam_deals_scheduler.py`, `steam_deals_run_output.py`, `steam_deals_notifications.py`, `steam_deals_presentation.py`, `steam_deals_watchlist.py`, `steam_deals_history.py`, `steam_deals_config.py`, `steam_deals_itad.py`, `steam_deals_enrichment.py`, `steam_deals_prices.py`, `steam_deals_steam_api.py`; validacion OK con `python -m py_compile` y `python -m pytest tests/test_generator_logic.py tests/test_shared_cache_utils.py` (62 passed).
- 2026-04-15: Se extrae `steam_deals_cache_policy.py` con decisiones de TTL, bypass `--no-cache`, refresh parcial/full y limpieza de archivos de cache; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py` quedan OK (66 tests).
- 2026-04-15: Se extrae `steam_deals_enrichment_orchestration.py` con la coordinacion de reviews, Steam Deck, ProtonDB, anti-cheat, tags y achievements; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py` quedan OK (68 tests).
- 2026-04-15: Se extrae `steam_deals_family.py` con la carga de `family_appids`, su boundary hacia HLTB y kwargs para renderers; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py` quedan OK (70 tests).
- 2026-04-15: Se consolida `steam_deals_run_output.py` para el slice `output final` con rutas de artifacts, fan-out de escritura y closeout final; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py` quedan OK (73 tests).
- 2026-04-15: Se extrae `steam_deals_itad_orchestration.py` con la coordinacion opcional de lookup, historical lows, current prices y bundles; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py` quedan OK (74 tests).
- 2026-04-15: Se extrae `steam_deals_post_processing.py` con la coordinacion de `hltb_hours`, filtros y `top_picks`; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py` quedan OK (75 tests).
- 2026-04-15: Se extrae `steam_deals_engagement_post_run.py` con la orquestacion de watchlist alerts, budget mode, gift ideas y notificaciones; `steam_deals_generator.py` conserva wrappers compatibles y `tests/test_generator_logic.py` + `tests/test_shared_cache_utils.py` quedan OK (76 tests).
- 2026-04-16: Validacion Linux local parcial: `python3`/`pip` OK, pero `pip` global del sistema quedo bloqueado por PEP 668; se crea `.venv`, se instalan deps desktop y el build local genera `dist/SteamToolsDesktop`.
- 2026-04-16: Primer arranque Linux del artefacto confirma fallback web por falta de backend nativo (`qtpy`/`gi`). Tras instalar `pywebview[qt]` y rehacer build, el artefacto vuelve a levantar server local sin log de fallback; luego se confirma ventana nativa real en sesion grafica no-root usando `runuser` + `QT_QPA_PLATFORM=xcb`.
- 2026-04-16: El smoke funcional inicial del binario congelado detecta bug real de packaging PyInstaller (`ModuleNotFoundError: shared`) cuando `steam_tools_desktop.py` ejecuta `steam_deals_generator.py` via `runpy`; se corrige `build_desktop.py` para agregar `--paths` + `hidden imports` + `collect_submodules(shared/renderers/app)`.
- 2026-04-16: Check liviano post-fix del binario congelado OK: `steam_deals_generator.py` ya emite el primer evento `progress` (`Resolviendo Steam ID...`) dentro del desktop empaquetado. El smoke funcional largo queda diferido porque la wishlist real es grande y la corrida puede tardar bastante antes de generar outputs finales.
- 2026-04-16: Se implementa primer corte de Desktop Doctor read-only en `steam_tools_desktop.py --doctor`: valida `.venv`/PEP 668, imports criticos (`steam_deals_web.py` / `steam_deals_generator.py`), stack `pywebview`/Qt en Linux, disponibilidad de `PyInstaller`, guardrails actuales de `build_desktop.py`, presencia de artefacto y sesion grafica/root; queda pendiente extenderlo a UI/autofix y mayor cobertura por OS.
- 2026-04-16: Desktop Doctor se expone tambien en la Web UI con boton `Doctor desktop` y endpoint local `POST /api/desktop-doctor`; reutiliza `desktop_doctor.py` sin duplicar checks y muestra el diagnostico en la consola existente.
- 2026-04-16: Desktop Doctor suma checks read-only adicionales por OS sin tocar la UX: Linux ahora revisa tooling host de PyInstaller (`ldd`/`objdump`/`objcopy`) y heuristicas Wayland/X11 cuando hay señal suficiente; macOS revisa PyObjC/tooling local; Windows revisa WebView2 y sesion interactiva cuando corre en ese OS.
- 2026-04-16: Desktop Doctor suma primer corte de autofix liviano y opt-in: CLI `--doctor-fix` (con `--yes`) y endpoint `POST /api/desktop-doctor/fix` / boton `Autofix desktop`. Solo crea `.venv`, instala `requirements-desktop.txt` dentro del entorno local y/o lanza build local; no toca paquetes del sistema ni configuracion persistente.
- 2026-04-16: Desktop Doctor mejora guidance por OS sin cambiar la UX base: cada `WARN/FAIL` ahora explica mejor que revisar manualmente, como separar deps Python vs nativas, cuando validar Wayland/X11 o WebView2, y como revalidar el desktop por plataforma sin convertir el doctor en instalador.
- 2026-04-16: Se agregan runbooks manuales por plataforma en `docs/runbooks/desktop-linux.md`, `docs/runbooks/desktop-macos.md` y `docs/runbooks/desktop-windows.md`; consolidan precondiciones, doctor, build, smoke, fallback y evidencia reproducible sin convertir el flujo en instalador.
- 2026-04-16: Quick wins de salida/automatizacion completados en Steam Deals: nuevo artifact `.json`, endpoint local `GET /api/latest-report`, helper para localizar el ultimo artifact en `steam_deals_run_output.py` y soporte en Web UI/fallback para abrir/copiar el ultimo JSON, abrir el ultimo Share HTML, empty state sin JSON y tarjeta-resumen del ultimo run.
- 2026-04-16: Quick wins de recomendacion/documentacion completados: Top Picks y Budget Mode ahora muestran `recommendation` + `score_reasons`; `README.md` documenta export JSON, endpoint local y ejemplos mini de automatizacion (`curl`, `jq`, Python stdlib).
- 2026-04-16: Decision operativa actualizada: sin host nativo Linux/macOS disponible en esta iteracion, P2 queda en estado parcial documentado y se prioriza avance Windows/no bloqueado (documentacion + backlog ejecutable).
- 2026-04-16: Avance Windows/no bloqueado en optimizacion de velocidad: cache de precios ahora expira exactamente al TTL (24h) y se habilita refresh incremental por entrada via timestamp `_fetched_at` (solo re-fetch de appids stale o faltantes). Se robustecio fallback individual cuando un batch devuelve null (incluyendo batch unitario). Validacion OK con pruebas dirigidas (`4 passed`, `3 passed`) y barrido ampliado de cache/enrichment (`17 passed`).
- 2026-04-16: Ajuste conservador de parallel fetching en enrichment: `MAX_WORKERS` sube de `8` a `12` (sin cambiar `rate_limit`, backoff ni fallback). Validacion de regresion OK en `tests/test_generator_logic.py -k "EnrichmentTests or PriceCacheTests"` (`17 passed`).
- 2026-04-16: Dashboard historico web MVP completado en Steam Deals: backend con endpoints `GET /api/history/runs` y `GET /api/history/compare` (con validacion de params y lectura segura de `run_*.json`), UI con selector de runs A/B + tabla comparativa de precios, filtros por estado (`changed/new/removed/same`), orden por delta (`delta_desc/delta_asc/abs_desc`) y persistencia de controles en `localStorage`. Validacion de regresion OK en `tests/test_generator_logic.py -k "History or ConfigTests or PriceCacheTests"` (`17 passed`).
- 2026-04-16: Dashboard historico web avanza a MVP+1 en UI con visualizacion resumida por estado (`changed/new/removed/same`) y bloque Top Deltas (mayores bajadas/subidas) sobre los runs comparados; se integra sin cambiar contrato backend y manteniendo filtros/orden existentes. Validacion de regresion OK en `tests/test_generator_logic.py -k "History or ConfigTests or PriceCacheTests"` (`17 passed`).
- 2026-04-16: Dashboard historico web avanza a MVP+2 con tendencia temporal simple en UI usando `GET /api/history/runs` (linea + puntos de `deal_count` sobre ultimos runs, con resumen min/max y delta neto vs primer run). Se mantiene implementacion frontend-only (sin cambio de contrato backend) y convive con comparativa A/B, filtros y orden existentes. Validacion de regresion OK en `tests/test_generator_logic.py -k "History or ConfigTests or PriceCacheTests"` (`17 passed`).
- 2026-04-16: Dashboard historico web avanza a MVP+3 con navegacion historica avanzada en UI: busqueda de runs, quick compare de ultimos 2 runs y paginado simple en selectores Run A/Run B para mejorar usabilidad con historiales largos. Se mantiene el contrato backend y convive con comparativa A/B, filtros, orden, resumen por estado, Top Deltas y tendencia temporal simple. Validacion de regresion OK en `tests/test_generator_logic.py -k "History or ConfigTests or PriceCacheTests"` (`17 passed`).
- 2026-04-16: Avance parcial export Obsidian/Notion: Markdown ahora soporta frontmatter YAML base y activacion por CLI via `--md-frontmatter` (pipeline de output integrado y tests dirigidos de config/markdown en verde). Queda pendiente cerrar guia de uso/plantillas y validacion de importacion end-to-end en Obsidian/Notion.

## Backlog de Features (Propuestos - Planning)

### Output/Export

- [ ] Exportar a Obsidian/Notion (markdown con frontmatter YAML para importacion directa). [Parcial avanzado: `--md-frontmatter` implementado + perfiles/checklist documentados; falta validacion final E2E de import en host real (Obsidian/Notion).]
- [ ] Dashboard HTML historico con graficos de precios, comparativa entre runs y navegacion de historial
- [ ] Dashboard HTML historico con graficos de precios, comparativa entre runs y navegacion de historial. [Parcial implementado (MVP+3): comparativa Run A vs Run B con filtros/orden, persistencia local, resumen visual por estado, Top Deltas (bajadas/subidas), tendencia temporal simple (deals por run), busqueda de runs, quick compare de ultimos 2 runs y paginado simple de selectores A/B; pendiente: graficos de tendencia mas ricos (series multipanel/zoom) y refinamiento UX.]
- [x] Exportar a JSON / API local para integracion con otras herramientas y automatizaciones. [Incluye artifact `.json`, endpoint local `GET /api/latest-report`, quick links UI para abrir/copiar el ultimo JSON, empty state cuando aun no existe reporte y tarjeta-resumen del ultimo run.]

### Social/Community

- [x] Generar link publica para compartir deals individuales (URL con data encodeada) - implementado, falta probar
- [ ] Detectar bundles activos de juegos en wishlist (mejorar integracion ITAD)
- [ ] Mostrar recomendaciones sociales tipo "un amigo te recomendo esto" usando overlap, juegos compartidos y senales sociales simples

### Recomendaciones

- [ ] Sugerir juegos similares segun los ultimos juegos jugados del usuario (por generos o por relaciones marcadas por el usuario: "me gusta" / "similar a")
- [ ] Sugerir regalos para amigos de Steam segun sus juegos mas jugados, recientes y titulos similares
- [ ] Analisis de biblioteca: tiempo total (HLTB), distribucion por genero, precio promedio
- [x] Explicar score y recomendacion de compra (por que esta arriba, comprar ahora vs esperar). [Top Picks y Budget Mode ya muestran recomendacion corta + razones visibles en HTML/Markdown; `README.md` actualizado con export JSON, endpoint local y ejemplos mini de automatizacion.]
- [ ] Explicar recomendaciones sociales/regalos con contexto breve ("juega mucho X", "jugo Y recientemente", "se parece a Z")

### Producto / Plataforma

- [ ] Unificar Steam Deals, Watchlist, Compare y PAYDAY 2 bajo una UX de suite con modulos claros
- [ ] Doctor / instalador desktop por plataforma para validar dependencias nativas, setup y readiness. [Parcial: ya existe en CLI (`steam_tools_desktop.py --doctor` / `--doctor-fix`) y Web UI (`Doctor desktop` / `Autofix desktop`), con cobertura base Linux/macOS/Windows, autofix liviano local, guidance mas accionable por OS y runbooks externos por plataforma; falta instalador/autofix real de nivel sistema.]

### Alertas inteligentes

- [x] Alertar por minimo historico, bundles activos y cambios relevantes entre runs. [Implementado: minimo historico global, bundles activos, nueva mejor oferta local y subidas vs run anterior; incluido en resumen final corto del run.]
- [x] Alertar por minimo historico, bundles activos y cambios relevantes entre runs. [Implementado v2: minimo historico global, bundles activos, nueva mejor oferta local y subidas vs run anterior, con umbrales configurables (`--alert-rise-pct`, `--alert-global-margin-pct`) y priorizacion por score (`--alert-score-min`) en el resumen final corto del run.]

### Expansion de Datos

- [ ] Importar wishlists de otras plataformas (GOG, Epic - investigar APIs)
- [ ] Detectar juegos eliminados del catalogo Steam (alertas)
- [ ] Comparar wishlist con historial y mostrar delta (nuevos juegos, bajadas y ofertas terminadas)
- [ ] Ampliar la comparativa multi-tienda para soportar mejor Fanatical y sumar mas stores (tiendas oficiales y keyshops), con metadata normalizada por tienda, tipo de tienda y filtros de confianza.

### Optimizacion (Velocidad - P0)

- [ ] Cache mas agresivo para wishlists grandes (24h stale time). [Parcial implementado: expiracion exacta al borde TTL y cobertura de tests.]
- [ ] Aumentar parallel fetching (de 5-10 a 50 concurrentes)
- [ ] Aumentar parallel fetching (de 5-10 a 50 concurrentes). [Parcial implementado: enrichment subio de `MAX_WORKERS 8 -> 12` en modo conservador y con regresion de tests OK.]
- [ ] Usar batch API de Steam para multiples juegos (reducir requests)
- [ ] Fetch inteligente: solo actualizar precios que cambiaron (comparar timestamps). [Parcial implementado: timestamp por entrada `_fetched_at` para decidir stale/missing y refrescar selectivamente.]
