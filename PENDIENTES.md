# Pendientes (Fuente Unica)

Ultima actualizacion: 2026-04-21

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
- Item activo: relanzar el smoke largo Linux con cache ya precalentado, capturar evidencia final (`.md/.html/.csv` + cierre limpio) y seguir pendientes no bloqueados mientras macOS sigue en espera de host nativo.

## Pendientes Priorizados

### P0 - Estabilidad

- [x] Empaquetado con PyInstaller (build inicial) validado en Windows.
- [x] Checklist de release y smoke tests (primera version).
- [ ] Corregir botón `Detener` en Steam Deals desktop/web: hoy puede quedarse solo en "Solicitando detener ejecucion..." sin frenar el proceso de forma confiable; si el usuario hace varios clicks, el mensaje se duplica y aumenta la confusion.
- [ ] Revisar inconsistencia de caché/batches en precios Steam: el run puede reportar `Caché válida (...) — sin nuevos, skip fetch` y aun así lanzar `Fetching N juegos`, además de caer en `HTTP 400` por batch y degradarse a fallback individual muy lento. Decidir si se resuelve como quick win de mensajes/guardrails o como track más amplio de fetch batching/cache behavior.

### P1 - UX Ultra Friendly

- [x] Banner de modo: primer setup vs actualizacion.
- [x] Errores accionables por categoria (network/config/rate-limit/encoding).
- [x] Presets de ejecucion (rapido, completo, ahorro).
- [x] Renombrar "Budget Mode" a un nombre mas claro para usuarios no tecnicos.
- [x] Renombrar "Steam Tags" a "Etiquetas" en UI.
- [x] Cambiar la metrica "edad" por un termino mas claro (ej. "antiguedad") y explicar que mide.
- [ ] Corregir share (compartir deals): reportado primero en Top Picks y luego como falla general en todo el share. [Parcial avanzado: Web UI + HTML interactivo + Share HTML ya comparten payload normalizado, botones/modal de share y compatibilidad desktop validada por tests/artifacts; falta validacion manual E2E final desde superficies generadas y live UI.]
- [x] Modo Presupuesto (dinamica "Battle Royale" interna, no genero): permitir reemplazar sugerencias tanto de lista completa ("probar otra lista") como de juego individual ("cambiar este juego"), manteniendo presupuesto y priorizando valor/score. [Implementado base y evidenciado en artifacts HTML/JSON/MD; queda pendiente separado solo el refinamiento de diversidad real.]
- [x] Modo Presupuesto: ofrecer 3 variantes de seleccion para el mismo presupuesto (lista chica = pocos juegos/ticket alto, lista media = balanceada, lista grande = mas juegos/ticket bajo). [Implementado base y evidenciado en artifacts HTML/JSON/MD.]
- [ ] Modo Presupuesto: mejorar la diversidad real del reroll/reemplazos cuando varias opciones terminan sintiéndose demasiado parecidas o repiten casi los mismos juegos.
- [ ] Agregar acceso rapido (boton tipo flecha) a grafica/historico de precios junto al minimo historico; evaluar mostrar minimo global y minimo en ventana de tiempo.
- [ ] Revisar/replantear bloque de tendencia (trend): actualmente no se entiende y no aporta valor claro. [Parcial: copy/explicacion ahora aclaran que resume volumen general de ofertas y no precio individual; pendiente decidir si la señal actual se mantiene o se reemplaza por algo mas util.]
- [x] Renombrar/ajustar trend para lenguaje mas claro al usuario final (ej. "Tendencia de precios") y simplificar su interpretacion.
- [x] Dashboard historico: agregar notas/highlights breves a los botones debajo de los selectores de runs (`Comparar runs`, `Recargar runs`, `Restablecer filtros`) para que se entienda rapido cuando usar cada accion.
- [ ] Dashboard historico: ajustar el copy y la apariencia del botón `Comparar últimos 2 runs`, porque hoy se ve extraño visualmente y el texto se siente demasiado largo/apretado para un usuario normal.
- [ ] [Futuro] Agregar selector de moneda en UI para cambiar divisa de precios.
- [ ] Agregar hints explicativos de metricas/criterios usados en UI para que el usuario entienda que se esta utilizando en cada seccion. [Parcial: UI principal + reportes/share ya explican score, minimo historico, antiguedad y tendencia general; pendiente extenderlo de forma mas uniforme a otras secciones.]
- [ ] Filtros avanzados: agregar filtro por tipo de recomendacion/mensaje (ej. "vale la pena", "considerar", "esperar") aplicado sobre los mensajes de Top Picks.
- [ ] Agregar apartado "Shuffle 1 juego": recomendar un solo juego de la wishlist segun presupuesto + critica/score, con boton para rerollear ("dame otro").
- [ ] Definir estrategia de outputs para evitar archivos desperdigados: (A) guardar por defecto en estructura `output/YYYY-MM-DD/` o (B) generar archivos solo bajo accion explicita (boton/comando), a decidir en iteracion futura.
- [ ] Corregir UX de apertura de archivos generados (`/files/...`): hoy algunos botones/enlaces de reportes pueden dar la impresión de no hacer nada o abrir una página en blanco al intentar ver `.md/.html/.json`; aclarar el comportamiento esperado y evitar confusión para el usuario normal.
- [x] Cambiar etiqueta "Era" por termino mas claro en UI/reportes (ej. "Precio original").
- [x] Ajustar el `<title>` de los reportes HTML para mostrar el nombre visible del perfil de Steam (en lugar de URL/steamid cuando aplique). [Sugerencia tester R1CK]

### P2 - Cross-platform

- [ ] Validar build desktop en Linux (Ubuntu LTS). [Parcial alto: doctor READY en `.venv`, build local OK, ventana nativa + server local confirmados en sesion grafica KDE no-root, packaging PyInstaller corregido, primer evento `progress` validado dentro del binario congelado y corrida larga real avanzada hasta `[8/11]` con artifacts `.md/.html/share.html/.json` antes de un bug de closeout final ya corregido; la UI ahora permite copiar/descargar logs, el desktop usa cache persistente y existe `--warm-cache` headless con logs, y el precalentado manual ya quedo completado. Falta rerun final con outputs `.md/.html/.csv` completos y cierre limpio.]
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

- Linux ya tiene evidencia local fuerte: en Debian/Ubuntu con PEP 668 se requiere `.venv`, el build desktop local genera `dist/SteamToolsDesktop`, la ventana nativa abre en sesion grafica KDE no-root sin requerir `QT_QPA_PLATFORM=xcb` en la prueba mas reciente, y el binario congelado ya emite el primer evento `progress` del generator tras corregir packaging PyInstaller.
- Nueva mitigacion operativa Linux: el desktop ya guarda cache en ruta persistente fuera de `_MEI`, existe `--warm-cache` headless para precalentar `prices_cache.json` sin abrir UI y ese modo ahora guarda logs legibles en carpeta `logs/` (o `<cache>/logs` cuando aplica). El warm-cache local ya quedo completado.
- Validacion manual macOS queda **pospuesta intencionalmente** hasta contar con host nativo disponible.
- El runbook para cierre de P2 ya esta documentado en `README.md` y en `docs/runbooks/desktop-{linux,macos,windows}.md`; el criterio de evidencia queda definido en este archivo.
- El Track Performance ya documenta una ruta realista de verificacion: warm-cache previo, tests dirigidos (`WarmCacheTests` / `PriceCacheTests`) y luego corrida larga con observacion de `Refresh candidates`, degradacion por `HTTP 400` y fallback individual.
- Siguiente reactivacion: con `--warm-cache` ya completado, relanzar el smoke funcional largo de Linux con el binario actualizado para confirmar `.md/.html/.csv` + cierre limpio, y luego ejecutar checklist manual macOS cuando exista host nativo disponible.

## Plan inmediato (Windows / No bloqueado)

Mientras no haya host nativo Linux/macOS disponible para cierre manual de P2, la ejecucion recomendada es:

1. **Consolidar evidencia Windows desktop (runbook + smoke funcional manual)**
   - Repetir build + apertura local + smoke rapido + smoke funcional minimo y actualizar bitacora.
2. **Optimizacion de velocidad (P0) para wishlists grandes**
   - Cache mas agresivo (24h), mayor concurrencia de fetch y estrategia incremental por timestamps. [Parcial: cache policy ajustada para expirar en el borde del TTL (`>= 24h`), refresh incremental por entrada con `_fetched_at`, fallos/null ya no quedan marcados como frescos y la UI compartida expone `max_workers` (incluyendo presets `rapido=12`, `completo=16`, `ahorro=8`); validado con tests/syntax checks. Pendiente: subir concurrencia por default/global.]
3. **Output/Export de valor inmediato**
   - Export a Obsidian/Notion con frontmatter YAML. [Parcial avanzado: `--md-frontmatter` + guia de perfiles/checklist ya documentados en README; pendiente validacion manual final de importacion extremo a extremo en host real de Obsidian/Notion.]
4. **Dashboard historico HTML**
   - Navegacion entre runs + comparativa visual de precios. [Parcial implementado (MVP+3): selector Run A/Run B con paginado simple, busqueda de runs, quick compare de ultimos 2 runs, boton manual para `Recargar runs`, filtros por estado, orden por delta, persistencia local (`localStorage`), reset rapido de filtros, resumen visible de los runs autoseleccionados en quick compare, resumen por estado, Top Deltas (bajadas/subidas) y tendencia temporal simple (deals por run, ultimos 20 runs).]
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
| 2026-04-21 | Linux (entorno local) | pre-smoke final listo | `--warm-cache` headless completado con cache persistente y logs legibles en `~/.cache/steam_deals/logs/`; README y runbook Linux ya reflejan el flujo real y aclaran mejor `--vanity`. | Relanzar smoke largo del desktop con cache caliente y registrar `.md/.html/.csv` + cierre limpio. |
| 2026-04-17 | Linux (entorno local) | validacion manual avanzada | Sesion KDE nativa confirmada. `steam_tools_desktop.py --doctor` quedo READY en `.venv`; build local actualizado OK. Corrida larga real del desktop avanzo hasta `[8/11]` (`tags`) y ya habia escrito `.md`, `.html`, `share.html` y `.json`, pero detecto un bug real en el closeout final por mismatch de `smart_alerts`; el fix ya quedo validado con tests dirigidos. Se agregaron acciones UI para copiar/descargar logs, el desktop paso a usar cache persistente fuera de `_MEI` y se sumo `--warm-cache` headless con logs en carpeta `logs/`. | Dejar terminar warm-cache, rerun Linux final con cache caliente y confirmar `.csv` + cierre limpio sin procesos colgados. |
| 2026-04-16 | Decision operativa | Linux muy avanzado / macOS pospuesto | Se ejecuto validacion local fuerte en Linux durante esta iteracion; macOS sigue pendiente por no contar aun con host nativo disponible. CI cross-platform permanece OK como evidencia parcial base (`24487556896`). El smoke funcional Linux queda diferido porque la wishlist real supera 2K juegos y requiere una ventana amplia. | Ejecutar smoke funcional largo Linux cuando haya ventana suficiente; luego reactivar runbook macOS para cierre P2. |
| 2026-04-16 | Linux (entorno local) | validacion manual avanzada | `python3`/`pip` OK. `python3 -m pip install -r requirements-desktop.txt` fallo en system Python por PEP 668 (`externally-managed-environment`), por lo que se uso `.venv`. Build local OK con `dist/SteamToolsDesktop`. Primer arranque del artefacto: fallback web confirmado por falta de backend nativo (`qtpy`/`gi`). Tras instalar `pywebview[qt]` y rehacer build, se confirmo ventana nativa + server local en sesion grafica no-root usando `runuser` + `QT_QPA_PLATFORM=xcb`. El smoke funcional completo encontro un bug real de packaging (`ModuleNotFoundError: shared`) dentro del binario congelado; se corrigio `build_desktop.py`/spec agregando `--paths` + `collect_submodules(shared/renderers/app)` + hidden imports, y luego un check liviano del binario valido el primer evento `progress` (`Resolviendo Steam ID...`) del generator ya empaquetado. Warning actual a revisar: `libtiff.so.5` en empaquetado Qt. | Ejecutar run largo con wishlist real para confirmar outputs `.md/.html/.csv` y cierre limpio; decidir luego si `libtiff.so.5` requiere nota/paquete adicional. |
| 2026-04-16 | Linux (Ubuntu LTS) | validado en CI (parcial) | Workflow `Desktop Cross-Platform Validation` OK en `ubuntu-latest` (run `24487556896`): install deps, build desktop, `py_compile`, check fallback local y artifact `dist-ubuntu-latest` publicado. Falta validacion manual en host Linux nativo para ventana real, preflight funcional completo y cierre sin procesos colgados. | Ejecutar checklist manual Linux en host Ubuntu LTS y registrar incidencias/workarounds de backend nativo `pywebview`. |
| 2026-04-16 | macOS | validado en CI (parcial) | Workflow `Desktop Cross-Platform Validation` OK en `macos-latest` (run `24487556896`): install deps, build desktop, `py_compile`, check fallback local y artifact `dist-macos-latest` publicado. Falta validacion manual en host macOS para apertura de `.app`, quarantine/codesign/notarizacion segun distribucion. | Ejecutar checklist manual macOS (apertura local, quarantine, codesign) y registrar incidencias/workarounds. |

## Bitacora

- 2026-04-21: Quick win de UX en archivos generados: los enlaces finales ahora distinguen entre `Abrir` (HTML) y `Descargar` (Markdown/JSON/CSV), y explican que los archivos de texto se descargan para evitar la sensación de página en blanco al pasar por `/files/...`.
- 2026-04-21: Quick win de UX en presupuesto: `Tu Presupuesto Ideal` sale de `Filtros avanzados` y pasa a mostrarse en la configuración principal como feature visible, para que no se sienta escondido como si fuera solo otro filtro.
- 2026-04-21: Rerun real con cache caliente (`Steam Medieval Fest`) deja evidencia local de cierre parcial: artifacts `.md/.html/share.html/.json` generados correctamente, `Precio original` ya visible en reportes y `Tu Presupuesto Ideal` ya expone variantes/rerolls en HTML/JSON/MD. Quedan abiertos como follow-up el share E2E manual, la diversidad real de rerolls y la inconsistencia de batching/cache (`Caché válida ... sin nuevos` pero luego `Fetching 414 juegos` con `HTTP 400` por batch). También se observa desfase en el conteo visible de pasos (`[1/11]` ... `[12/11]`).
- 2026-04-21: `--warm-cache` local ya termino correctamente con cache persistente y logs en `~/.cache/steam_deals/logs/`; el siguiente paso operativo queda reducido al rerun largo Linux para capturar `.md/.html/.csv` + cierre limpio.
- 2026-04-21: La CLI headless ya maneja mejor errores de usuario en warm-cache (`TU_VANITY_URL`, vanity invalido, wishlist privada) con mensajes accionables en vez de traceback crudo, manteniendo exit code de error y cierre correcto del log.
- 2026-04-21: README, runbook Linux y ejemplos user-facing ahora usan `gaben` como vanity publico neutral para evitar exponer vanitys personales y reducir confusiones por copy/paste.
- 2026-04-21: El flujo de share queda mucho mas alineado entre Web UI, HTML interactivo y Share HTML: payload normalizado con aliases (`price_original`/`original_price`, `min_hist`/`min_historical`), botones/modal consistentes y validacion automatica reforzada; queda pendiente solo la verificacion manual E2E final.
- 2026-04-21: Se cierran los pendientes base de `Tu Presupuesto Ideal` para variantes chica/media/grande y cambios de lista/juego; queda abierto solo el refinamiento de diversidad real del reroll/reemplazos.
- 2026-04-21: Quick win de UX en histórico: el botón `Comparar últimos 2 runs` se acorta a `Últimos 2 runs`, mejora su spacing y deja un hint más directo para que se entienda sin verse apretado.
- 2026-04-20: Quick win de UX en tendencia/histórico: el bloque `Trend` ahora usa copy más claro para usuario normal (`Tendencia general de ofertas`, `Lectura rápida`, `Volumen similar al inicio`, etc.) para explicar que resume el volumen total de ofertas y no el precio de un juego individual.
- 2026-04-20: Se cierra el pendiente de la etiqueta `Era`: HTML/Markdown/reportes relevantes ahora usan `Precio original`, alineado con el resto de la UX para evitar lenguaje ambiguo.
- 2026-04-20: Quick win de UX en `Tu Presupuesto Ideal` dentro del HTML interactivo: las variantes ahora se presentan como botones de `Rerrollear todos` debajo de la barra del presupuesto, cada juego puede mostrar `Reroll` junto al número y el modal de share usa un botón `Cerrar` consistente con el resto. Sigue pendiente revisar la diversidad real de reemplazos cuando varias opciones se sienten demasiado parecidas.
- 2026-04-20: Quick win de UX en `Tu Presupuesto Ideal`: el campo de presupuesto en Filtros avanzados ahora explica mejor que genera una lista balanceada y que el reporte puede mostrar variantes chica/media/grande y cambios de juego dentro del tope.
- 2026-04-20: Avance en share/compartir deals: se corrige el contrato del payload entre Web UI y desktop (`price_original` vs `original_price`) y el parser de `steam_tools_desktop.py` ahora tolera payload base64 URL-encoded y alias legacy; falta validación manual E2E del flujo completo para cerrar el pendiente general de share.
- 2026-04-20: El dashboard historico suma `title` explicativos en `Comparar últimos 2 runs`, `Comparar runs`, `Recargar runs` y `Restablecer filtros`, reforzando la ayuda visible ya añadida en la sección.
- 2026-04-20: La UI principal de Steam Deals ahora muestra notas breves y `title` explicativos para los botones utilitarios (`Probar config`, `Doctor desktop`, `Autofix desktop`, `Limpiar cache`, `Abrir ultimo reporte`) para que un usuario normal entienda mejor qué hace cada acción.
- 2026-04-20: Se confirma que el repo ya cuenta con artifact Linux `dist/SteamToolsDesktop`; el `.exe` historico corresponde al flujo Windows y no sirve como validacion nativa en Linux.
- 2026-04-20: Sanitizacion base del repo aplicada para reducir ruido operativo: `.tmp/`, `.pytest_cache/`, `logs/` y reportes `Steam Deals*.json` pasan a tratarse como artefactos locales no versionados; el cache real se conserva fuera de esta limpieza para no penalizar wishlists grandes.
- 2026-04-20: Sugerencia de tester CH4VE5 implementada: Top Picks y Share HTML ya etiquetan explicitamente `Score` y `Metacritic`, para que no se vea solo un numero aislado.
- 2026-04-20: Sugerencia de tester J0HNNY implementada: el paso `[3/12] Comparando wishlists...` ya muestra el nombre visible del amigo cuando se puede resolver, con fallback seguro al vanity original.
- 2026-04-20: Sugerencia de tester R0CH4 verificada/cerrada: el dashboard historico ya incluye boton `Recargar runs` para refrescar manualmente el listado tras varias ejecuciones.
- 2026-04-18: Se agrega pendiente sugerido por tester R1CK para que el `<title>` de los reportes HTML use el nombre visible del perfil de Steam en lugar de URL/steamid cuando corresponda.
- 2026-04-18: Queda implementada la mejora sugerida por tester R1CK: los reportes HTML (`.html` y `Share HTML`) y `meta.profile` en JSON ya usan el nombre visible del perfil Steam cuando está disponible, con fallback seguro al identificador original si no se puede resolver.
- 2026-04-18: Se cierra el pendiente de claridad de scoring sobre "edad": se estandariza como "antigüedad" y se documenta explícitamente que mide años desde lanzamiento.
- 2026-04-18: Se renombra "Budget Mode" a "Tu Presupuesto Ideal" en documentación, UI y reportes para hacerlo más claro para usuarios no técnicos.
- 2026-04-18: Se renombra "Steam Tags" a "Etiquetas" en la UI/reportes relevantes y documentación para mantener lenguaje más claro para usuarios no técnicos.
- 2026-04-17: Se blindó el refresh incremental por `_fetched_at`: si un fetch de precios falla o devuelve `null`, esa entrada ya no queda marcada como fresca por 24h. El siguiente run la vuelve a tratar como retryable.
- 2026-04-17: La UI compartida ahora expone `max_workers` en Filtros avanzados y los presets de Steam Deals tambien ajustan workers sugeridos (`rapido=12`, `completo=16`, `ahorro=8`) sin cambiar todavia el default global.
- 2026-04-17: El dashboard historico gano un boton para restablecer filtros y un resumen visible de Run A / Run B al usar quick compare, para que la comparacion de los ultimos 2 runs sea mas clara.
- 2026-04-17: El smoke largo Linux del desktop detecto un bug real de closeout final: `steam_deals_run_output.py` ya pasaba `smart_alerts` al resumen corto pero el wrapper compatible en `steam_deals_generator.py` no aceptaba ese argumento. Se corrigio el boundary, quedaron tests dirigidos en verde y la proxima corrida larga debe validar el cierre E2E sin crash.
- 2026-04-17: La UI compartida Steam Deals ahora permite copiar y descargar el log visible de ejecucion; se hizo para no perder tracebacks largos durante validacion manual desktop/web.
- 2026-04-17: El cache del desktop ya no se pierde en `_MEI`: se movio a ruta persistente de usuario en modo frozen y se agrego `--warm-cache` headless para precalentar `prices_cache.json` sin abrir UI. La v2 del warm-cache guarda logs automaticamente en carpeta `logs/` (o `<cache>/logs` cuando se usa ruta persistente/override).
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
- [ ] Dashboard HTML historico con graficos de precios, comparativa entre runs y navegacion de historial. [Parcial implementado (MVP+3): comparativa Run A vs Run B con filtros/orden, persistencia local, resumen visual por estado, Top Deltas (bajadas/subidas), tendencia temporal simple (deals por run), busqueda de runs, quick compare de ultimos 2 runs, boton manual `Recargar runs` y paginado simple de selectores A/B; pendiente: graficos de tendencia mas ricos (series multipanel/zoom) y refinamiento UX.]
- [x] Exportar a JSON / API local para integracion con otras herramientas y automatizaciones. [Incluye artifact `.json`, endpoint local `GET /api/latest-report`, quick links UI para abrir/copiar el ultimo JSON, empty state cuando aun no existe reporte y tarjeta-resumen del ultimo run.]

### Social/Community

- [x] Generar link publica para compartir deals individuales (URL con data encodeada). [Implementado y alineado entre Web UI, HTML interactivo y Share HTML; payload share compatible con desktop validado por tests. Falta solo validacion manual E2E para cierre operativo del pendiente general de share.]
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

- [ ] Cache mas agresivo para wishlists grandes (24h stale time). [Parcial implementado: expiracion exacta al borde TTL, cobertura de tests y fallos/null ya no se congelan como fresh por `_fetched_at`.]
- [ ] Aumentar parallel fetching (de 5-10 a 50 concurrentes)
- [ ] Aumentar parallel fetching (de 5-10 a 50 concurrentes). [Parcial implementado: enrichment subio de `MAX_WORKERS 8 -> 12` en modo conservador, la UI compartida ya expone `max_workers` y los presets aplican valores recomendados (`12/16/8`) con validacion OK.]
- [ ] Usar batch API de Steam para multiples juegos (reducir requests)
- [ ] Fetch inteligente: solo actualizar precios que cambiaron (comparar timestamps). [Parcial implementado: timestamp por entrada `_fetched_at` para decidir stale/missing y refrescar selectivamente.]
