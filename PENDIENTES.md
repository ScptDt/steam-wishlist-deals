# Pendientes (Fuente Unica)

Ultima actualizacion: 2026-04-23

## Regla de Oro

Este archivo es la fuente unica de verdad para:
- pendientes activos
- backlog de features
- plan cross-platform
- estado de ejecucion y bitacora

No se mantienen documentos paralelos de planificacion; este archivo es la unica fuente.
`BITACORA.md` solo guarda historial cronologico detallado y no reemplaza este archivo.

## Estado General

- Objetivo: llevar Steam Tools a una experiencia ultra user friendly y preparada para ejecutable desktop.
- Fase actual: P2 en validacion cross-platform (cierre manual pendiente por host nativo).
- Item activo: relanzar el smoke largo Linux con cache ya precalentado, capturar evidencia final (`.md/.html/.csv` + cierre limpio) y seguir pendientes no bloqueados mientras macOS sigue en espera de host nativo.

## Pendientes Priorizados

### P0 - Estabilidad

- [x] Empaquetado con PyInstaller (build inicial) validado en Windows.
- [x] Checklist de release y smoke tests (primera version).
- [ ] Corregir botón `Detener` en Steam Deals desktop/web. [Parcial avanzado: en Web UI ya no duplica `Solicitando detener ejecucion...`, `/api/stop` usa estados veraces (`stopped`, `not_running`, `stop_timeout`) y una validación manual en browser confirmó que el run sí se detiene. Queda pendiente confirmar la misma experiencia visible en desktop cuando el launcher esté más estable.]
- [ ] [Track] Hacer robusta y clara la apertura/descarga de reportes y archivos generados: hoy el flujo de `/files/...` puede disparar `403`, abrir rutas codificadas problemáticas o resultar confuso según el tipo de archivo y la superficie. Consolidar aquí el frente de outputs/reportes para unificar apertura/descarga de HTML/MD/JSON/CSV, aclarar `Abrir` vs `Descargar` y definir mejor la estrategia de guardado de outputs.
- [ ] [Track] Reducir el tiempo total de fetching en wishlists grandes: hoy el run puede tardar demasiado y varios procesos de precios/enrichment se sienten muy largos para el usuario. Consolidar este frente de performance para bajar la duración real del run, hacer el progreso más estable/predecible y atacar en un solo track los subfrentes de caché/batches, invalidación por Weeklong/Midweek/Weekend Deals, mayor concurrencia, batch API de Steam, fetch incremental por timestamps y reducción del fallback individual lento.
- [ ] [Quick Win] Corregir el cálculo de estadísticas visibles en el HTML interactivo: hoy `Promedio` y `Precio medio` pueden renderizar `NaN`; blindar el cálculo cuando no haya deals visibles o entren valores no numéricos, y mostrar un fallback claro.

### P1 - UX Ultra Friendly

- [x] Banner de modo: primer setup vs actualizacion.
- [x] Errores accionables por categoria (network/config/rate-limit/encoding).
- [x] Presets de ejecucion (rapido, completo, ahorro).
- [x] Renombrar "Budget Mode" a un nombre mas claro para usuarios no tecnicos.
- [x] Renombrar "Steam Tags" a "Etiquetas" en UI.
- [x] Cambiar la metrica "edad" por un termino mas claro (ej. "antiguedad") y explicar que mide.
- [ ] Corregir share (compartir deals): reportado primero en Top Picks y luego como falla general en todo el share. [Parcial avanzado: Web UI + HTML interactivo + Share HTML ya comparten payload normalizado, botones/modal de share y compatibilidad desktop validada por tests/artifacts; falta validacion manual E2E final desde superficies generadas y live UI.]
- [ ] [Track] Mejorar la jerarquía visual y la escaneabilidad de la UX principal: hoy hay demasiada información compitiendo al mismo tiempo en la UI principal y reportes, y algunos bloques/hints se sienten pesados o raros visualmente. Consolidar aquí el frente de UX visual para reducir ruido general, simplificar `Último reporte`, revisar hints de métricas/criterios y evaluar controles más naturales para archivos/rutas cuando realmente aporten claridad.
- [x] Modo Presupuesto (dinamica "Battle Royale" interna, no genero): permitir reemplazar sugerencias tanto de lista completa ("probar otra lista") como de juego individual ("cambiar este juego"), manteniendo presupuesto y priorizando valor/score. [Implementado base y evidenciado en artifacts HTML/JSON/MD; queda pendiente separado solo el refinamiento de diversidad real.]
- [x] Modo Presupuesto: ofrecer 3 variantes de seleccion para el mismo presupuesto (lista chica = pocos juegos/ticket alto, lista media = balanceada, lista grande = mas juegos/ticket bajo). [Implementado base y evidenciado en artifacts HTML/JSON/MD.]
- [ ] Modo Presupuesto: mejorar la diversidad real del reroll/reemplazos cuando varias opciones terminan sintiéndose demasiado parecidas o repiten casi los mismos juegos.
- [ ] Corregir el reroll/reemplazo en `Tu Presupuesto Ideal`: al cambiar un juego se actualizan texto/precio pero la imagen puede quedarse en la opción anterior.
- [ ] Agregar acceso rapido (boton tipo flecha) a grafica/historico de precios junto al minimo historico; evaluar mostrar minimo global y minimo en ventana de tiempo.
- [ ] Revisar/replantear bloque de tendencia (trend): actualmente no se entiende y no aporta valor claro. [Parcial: copy/explicacion ahora aclaran que resume volumen general de ofertas y no precio individual; pendiente decidir si la señal actual se mantiene o se reemplaza por algo mas util.]
- [x] Renombrar/ajustar trend para lenguaje mas claro al usuario final (ej. "Tendencia de precios") y simplificar su interpretacion.
- [x] Dashboard historico: agregar notas/highlights breves a los botones debajo de los selectores de runs (`Comparar runs`, `Recargar runs`, `Restablecer filtros`) para que se entienda rapido cuando usar cada accion.
- [ ] [Quick Win] Dashboard historico: ajustar el copy, spacing y alineación del bloque de búsqueda y del CTA rápido (`Comparar 2 recientes`), porque hoy se ve desbalanceado visualmente y no queda al mismo nivel para un usuario normal.
- [ ] [Track] Mejorar detección, contexto y picks por promo activa de Steam: hoy el reporte se queda corto cuando coinciden varias promos o cuando falta contexto de si conviene comprar ahora o esperar. Consolidar aquí la detección/naming de promos simultáneas y la selección de picks por fest, oferta temática, launch day y `Weeklong`/`Midweek`/`Weekend Deals`, además de mostrar próximas ofertas grandes y pequeñas para dar contexto temporal.
- [ ] [Futuro] Agregar selector de moneda en UI para cambiar divisa de precios.
- [ ] Filtros avanzados: agregar filtro por tipo de recomendacion/mensaje (ej. "vale la pena", "considerar", "esperar") aplicado sobre los mensajes de Top Picks.
- [ ] Agregar apartado "Shuffle 1 juego": recomendar un solo juego de la wishlist segun presupuesto + critica/score, con boton para rerollear ("dame otro").
- [ ] [Quick Win] Como primer corte del track de outputs/reportes, aclarar todavía más el comportamiento esperado al abrir o descargar archivos generados (`/files/...`) para que HTML/MD/JSON/CSV se sientan consistentes y no den impresión de página en blanco o de que no pasó nada.
- [x] Cambiar etiqueta "Era" por termino mas claro en UI/reportes (ej. "Precio original").
- [x] Ajustar el `<title>` de los reportes HTML para mostrar el nombre visible del perfil de Steam (en lugar de URL/steamid cuando aplique). [Sugerencia tester R1CK]
- [ ] [Quick Win] Hacer que el encabezado visible del HTML interactivo use el nombre visible del perfil de Steam en lugar de vanity URL o URL completa cuando exista `profile_display_name`. [Follow-up del ajuste previo del `<title>` en reportes HTML.]

### P2 - Cross-platform

- [ ] Validar build desktop en Linux (Ubuntu LTS). [Parcial alto: doctor READY en `.venv`, build local OK, ventana nativa + server local confirmados en sesion grafica KDE no-root, packaging PyInstaller corregido, primer evento `progress` validado dentro del binario congelado y corrida larga real avanzada hasta `[8/11]` con artifacts `.md/.html/share.html/.json` antes de un bug de closeout final ya corregido; la UI ahora permite copiar/descargar logs, el desktop usa cache persistente y existe `--warm-cache` headless con logs, y el precalentado manual ya quedo completado. Falta rerun final con outputs `.md/.html/.csv` completos y cierre limpio.]
- [ ] Validar build desktop en macOS (app bundle + apertura local).
- [x] Documentar dependencias nativas por plataforma para pywebview.
- [ ] Validar cross-platform el fallback web: si `pywebview` no es compatible o no inicia backend nativo, abrir la Web UI en el navegador por defecto con aviso visible en la interfaz. [Linux parcial OK: fallback confirmado en primer intento sin backend, luego ventana nativa OK con Qt/X11; falta host nativo/macOS.]
- [ ] Automatizar con un script el flujo repetitivo de validación desktop/cross-platform y arranque/depuración/launch (doctor, warm-cache, build, run/smoke y recolección de logs/evidencia) para no ejecutar manualmente siempre los mismos pasos. [Tratarlo como Track operativo/técnico, no como quick win.]

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

### Modelo de evidencia y orden del Track Desktop

Orden actual del track:

1. **Fase 1 — Linux desktop binario (cierre prioritario)**
    - build local
    - apertura de ventana nativa
    - smoke funcional largo
    - `.md/.html/.csv`
    - cierre limpio sin procesos colgados
    - bitacora actualizada con evidencia binaria
2. **Fase 2 — Paridad compartida y readiness**
   - fallback web
   - Desktop Doctor / Autofix
   - temas compartidos web/desktop (stop/share/reportes)
   - evidencia Windows como baseline de apoyo, no como cierre de P2
3. **Fase 3 — macOS native-host closure**
   - host macOS nativo disponible
   - build `.app`
   - apertura local
   - smoke funcional y cierre limpio

Modelo de evidencia:

- **Web UI/source** cuenta como evidencia funcional del generator, performance y UX compartida.
- **Desktop binario** cuenta como evidencia de cierre desktop real.
- La evidencia web/source **no sustituye** la evidencia nativa del binario para cerrar Linux/macOS.

Checklist resumido para cerrar **Fase 1 — Linux desktop binario**:

- [ ] `python steam_tools_desktop.py --doctor` sin FAIL reales
- [ ] `python build_desktop.py` OK + `dist/SteamToolsDesktop` presente
- [ ] Binario abierto en sesión gráfica normal (no root)
- [ ] `Probar config` ejecutado desde la UI
- [ ] Run largo completado **desde el binario desktop**
- [ ] Artefactos finales confirmados: `.md`, `.html`, `.csv`
- [ ] `share.html` / `.json` guardados solo como evidencia adicional (si aplica)
- [ ] Fallback al navegador documentado si ocurrió
- [ ] Cierre limpio confirmado
- [ ] Sin procesos colgados tras cerrar

Plantilla mínima para la entrada final de bitácora Linux:

- Host/sesión gráfica:
- Comandos ejecutados:
- Doctor desktop:
- Build desktop:
- Apertura nativa:
- `Probar config`:
- Run largo desde binario:
- Artefactos: `.md` / `.html` / `.csv`
- Evidencia adicional: `share.html` / `.json`
- Fallback al navegador: sí/no
- Cierre limpio: sí/no
- Procesos colgados: sí/no
- Workarounds usados:
- Incidencias observadas:

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
   - Navegacion entre runs + comparativa visual de precios. [Parcial implementado (MVP+3): selector Run A/Run B con paginado simple, busqueda de runs, quick compare de ultimos 2 runs, boton manual para `Recargar runs`, filtros por estado, orden por delta, persistencia local (`localStorage`) + restauracion por URL params, reset rapido de filtros, resumen visible de los runs autoseleccionados en quick compare, resumen por estado, Top Deltas (bajadas/subidas), drilldown por juego con `Ver historial` y tendencia temporal simple (deals por run, ultimos 20 runs). Cobertura automatizada reforzada en `tests/test_track_history_flow.py`; pendiente validacion manual final en browser y refinamiento UX.]
5. **Alertas inteligentes (v2)**
   - Implementacion base v2 completada (minimo historico global, bundles activos, subidas vs run anterior, nueva mejor oferta local y umbrales configurables).
   - **Pendiente por tiempo**: calibracion fina de umbrales y ejecucion/validacion manual completa en corrida larga real.
   - **Se retoma en la proxima corrida** para cierre operativo final del frente de Alertas v2.

Notas:
- Este plan no bloquea el cierre futuro de P2; solo evita tiempo muerto mientras falta host nativo.
- El cierre formal de P2 sigue condicionado a evidencia manual Linux + macOS segun criterio de Done.

## Bitacora reciente

- 2026-04-23: Track History amplía la cobertura automática en `tests/test_track_history_flow.py` para el contrato enriquecido de analytics, filtros/orden/límites y parsing defensivo de `/api/history/runs` + `/api/history/compare`; queda pendiente la validación manual final en browser para cerrar el frente.
- 2026-04-23: Quick win de consistencia UX en configuración: `Steam API Key` e `ITAD API Key` se humanizan a `Clave de Steam API` y `Clave de ITAD`, manteniendo claridad pero reduciendo mezcla innecesaria de inglés y español.
- 2026-04-23: Quick win de UX en el asistente inicial: el wizard alinea su lenguaje con la UI principal (`perfil de Steam`, `Clave de Steam API`, `Clave de ITAD`) para reducir jerga técnica innecesaria desde el primer uso.
- 2026-04-23: Quick win de UX en el asistente inicial: el primer paso cambia su título a `Tu cuenta de Steam`, buscando un tono todavía más natural para usuario normal.
- 2026-04-23: Quick win de lenguaje UX: `Abrir wizard` se renombra a `Abrir asistente`, evitando un anglicismo innecesario en una acción muy visible.
- 2026-04-23: Quick win de pulido de copy: placeholders y textos visibles que seguían sin acento (`Sin limite`) ahora quedan como `Sin límite`, reduciendo detalles visuales descuidados en la UI.
- 2026-04-23: Quick win de UX en onboarding/configuración: el hint de `Perfil de Steam` se reescribe para sonar más guiado y menos técnico, manteniendo los mismos formatos admitidos.
- 2026-04-23: Quick win de UX en comparación social: el placeholder de `Comparar con` deja la referencia técnica a `vanity URL` y pasa a pedir de forma más directa el perfil del amigo.
- 2026-04-23: `PENDIENTES.md` se limpia para consolidar tracks paraguas de performance/fetching, outputs/reportes, UX visual, promos/eventos Steam y wishlist hygiene, y la bitácora cronológica detallada se migra a `BITACORA.md`.
- 2026-04-22: Track Stop queda casi cerrado en Web UI; falta validar la misma experiencia visible en desktop.
- 2026-04-21: El warm-cache Linux ya quedó completado y el siguiente paso operativo sigue siendo relanzar el smoke largo del desktop para confirmar `.md/.html/.csv` + cierre limpio.

## Archivo historico

La bitácora cronológica detallada, evidencia operativa y entradas antiguas viven en `BITACORA.md`.

`PENDIENTES.md` sigue siendo la fuente única de verdad para pendientes activos, prioridades, estado actual y próximo paso operativo.

## Backlog de Features (Propuestos - Planning)

### Output/Export

- [ ] Exportar a Obsidian/Notion (markdown con frontmatter YAML para importacion directa). [Parcial avanzado: `--md-frontmatter` implementado + perfiles/checklist documentados; falta validacion final E2E de import en host real (Obsidian/Notion).]
- [ ] Dashboard HTML historico con graficos de precios, comparativa entre runs y navegacion de historial. [Parcial implementado (MVP+3): comparativa Run A vs Run B con filtros/orden, persistencia local + restauracion por URL params, resumen visual por estado, Top Deltas (bajadas/subidas), tendencia temporal simple (deals por run), busqueda de runs, quick compare de ultimos 2 runs, boton manual `Recargar runs`, paginado simple de selectores A/B y drilldown por juego con `Ver historial`; cobertura automatizada reforzada en `tests/test_track_history_flow.py`. Pendiente: validacion manual final en browser, graficos de tendencia mas ricos (series multipanel/zoom) y refinamiento UX.]
- [x] Exportar a JSON / API local para integracion con otras herramientas y automatizaciones. [Incluye artifact `.json`, endpoint local `GET /api/latest-report`, quick links UI para abrir/copiar el ultimo JSON, empty state cuando aun no existe reporte y tarjeta-resumen del ultimo run.]

### Social/Community

- [x] Generar link publica para compartir deals individuales (URL con data encodeada). [Implementado y alineado entre Web UI, HTML interactivo y Share HTML; payload share compatible con desktop validado por tests. Falta solo validacion manual E2E para cierre operativo del pendiente general de share.]
- [ ] Detectar bundles activos de juegos en wishlist (mejorar integracion ITAD)
- [ ] Mostrar recomendaciones sociales tipo "un amigo te recomendo esto" usando overlap, juegos compartidos y senales sociales simples
- [ ] Al sugerir regalos para un amigo, priorizar opciones que no sean exactamente los mismos juegos ya mostrados en la sección de overlap/en común, o al menos mezclar ambos grupos de forma más útil para no sentirse redundante.

### Recomendaciones

- [ ] Sugerir juegos similares segun los ultimos juegos jugados del usuario (por generos o por relaciones marcadas por el usuario: "me gusta" / "similar a")
- [ ] Sugerir regalos para amigos de Steam segun sus juegos mas jugados, recientes y titulos similares
- [ ] Recomendar mejores deals para ti segun tu actividad en Steam, considerando no solo lo jugado recientemente sino tambien lo mas jugado / los juegos con mas horas, usando una lógica parecida a la de recomendaciones para amigos pero aplicada a tu propio perfil.
- [ ] Analisis de biblioteca: tiempo total (HLTB), distribucion por genero, precio promedio
- [x] Explicar score y recomendacion de compra (por que esta arriba, comprar ahora vs esperar). [Top Picks y Budget Mode ya muestran recomendacion corta + razones visibles en HTML/Markdown; `README.md` actualizado con export JSON, endpoint local y ejemplos mini de automatizacion.]
- [ ] Explicar recomendaciones sociales/regalos con contexto breve ("juega mucho X", "jugo Y recientemente", "se parece a Z")

### Producto / Plataforma

- [ ] Unificar Steam Deals, Watchlist, Compare y PAYDAY 2 bajo una UX de suite con modulos claros
- [ ] Doctor / instalador desktop por plataforma para validar dependencias nativas, setup y readiness. [Parcial: ya existe en CLI (`steam_tools_desktop.py --doctor` / `--doctor-fix`) y Web UI (`Doctor desktop` / `Autofix desktop`), con cobertura base Linux/macOS/Windows, autofix liviano local, guidance mas accionable por OS y runbooks externos por plataforma; falta instalador/autofix real de nivel sistema.]

### Alertas inteligentes

- [x] Alertar por minimo historico, bundles activos y cambios relevantes entre runs. [Implementado v2: minimo historico global, bundles activos, nueva mejor oferta local y subidas vs run anterior, con umbrales configurables (`--alert-rise-pct`, `--alert-global-margin-pct`) y priorizacion por score (`--alert-score-min`) en el resumen final corto del run.]

### Expansion de Datos

- [ ] [Track] Enriquecer y depurar la wishlist con señales externas: evaluar un apartado/opción que ayude a detectar juegos ya cubiertos por `HLTB CSV`, `Family JSON`, biblioteca propia u otras plataformas. Empezar como sugerencia/filtro/exclusión opcional, no como borrado automático, e incluir la investigación/import de wishlists externas (GOG, Epic, etc.) dentro del mismo frente.
- [ ] Detectar juegos eliminados del catalogo Steam (alertas)
- [ ] Comparar wishlist con historial y mostrar delta (nuevos juegos, bajadas y ofertas terminadas)
- [ ] Ampliar la comparativa multi-tienda para soportar mejor Fanatical y sumar mas stores (tiendas oficiales y keyshops), con metadata normalizada por tienda, tipo de tienda y filtros de confianza.
