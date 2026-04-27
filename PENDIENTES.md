# Pendientes (Fuente Unica)

Ultima actualizacion: 2026-04-27

## Regla de Oro

Este archivo es la fuente unica de verdad para:
- pendientes activos
- backlog de features
- plan cross-platform
- estado de ejecución y bitácora reciente

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
- [ ] [Quick Win] Corregir botón `Detener` en Steam Deals desktop/web. [Estado: Web UI validada sin duplicar `Solicitando detener ejecucion...` y `/api/stop` ya usa estados veraces. Falta: confirmar la misma experiencia visible en desktop. Evidencia: prueba manual desde binario sin mensajes duplicados ni procesos colgados.]
- [ ] [Track] Hacer robusta y clara la apertura/descarga de reportes y archivos generados. [Estado: cortes cerrados para acciones HTML/MD/JSON/CSV, errores claros en `/files/...` (`403` inválido, `404` faltante, `500` lectura), default explícito `output/`, endpoint local `Ver carpeta` y artefactos agrupados por tipo en Web UI. Falta: validación manual web/desktop desde superficie real/binario. Evidencia: HTML/Share HTML abren, MD/JSON/CSV descargan y la carpeta `output/` se abre/crea consistentemente.]
- [ ] [Track] Reducir el tiempo total de fetching en wishlists grandes. [Estado: ya hay `max_workers=16`, observabilidad de fallback individual, cooldown para fallos/no-data, parser offline de logs warm-cache y tabla comparativa de múltiples logs con deltas. Falta: medir corrida larga real, ajustar cache/batches/invalidación por promos y reducir fallback individual lento. Evidencia: run grande con progreso estable, menor duración y artifacts completos.]
- [x] [Quick Win] Corregir el cálculo de estadísticas visibles en el HTML interactivo: hoy `Promedio` y `Precio medio` pueden renderizar `NaN`; blindar el cálculo cuando no haya deals visibles o entren valores no numéricos, y mostrar un fallback claro. [Cerrado 2026-04-24: fallback `sin datos` y cálculo defensivo para promedios visibles.]

### P1 - UX Ultra Friendly

- [x] Banner de modo: primer setup vs actualizacion.
- [x] Errores accionables por categoria (network/config/rate-limit/encoding).
- [x] Presets de ejecucion (rapido, completo, ahorro).
- [x] Renombrar "Budget Mode" a un nombre mas claro para usuarios no tecnicos.
- [x] Renombrar "Steam Tags" a "Etiquetas" en UI.
- [x] Cambiar la metrica "edad" por un termino mas claro (ej. "antiguedad") y explicar que mide.
- [ ] [Track] Corregir share (compartir deals) en todas las superficies. [Estado: Web UI + HTML interactivo + Share HTML ya comparten payload normalizado, botones/modal y compatibilidad desktop validada por tests/artifacts. Falta: validación manual E2E final desde superficies generadas y live UI. Evidencia: compartir desde Top Picks/reportes/Share HTML sin payload roto.]
- [ ] [Track] Mejorar la jerarquía visual y la escaneabilidad de la UX principal. [Estado: varios quick wins de copy/layout ya cerrados. Falta: reducir ruido general, simplificar `Último reporte`, revisar hints de métricas/criterios y evaluar controles más naturales para archivos/rutas. Evidencia: revisión visual/manual con menos bloques compitiendo y acciones más claras.]
- [x] Modo Presupuesto (dinamica "Battle Royale" interna, no genero): permitir reemplazar sugerencias tanto de lista completa ("probar otra lista") como de juego individual ("cambiar este juego"), manteniendo presupuesto y priorizando valor/score. [Implementado base y evidenciado en artifacts HTML/JSON/MD; queda pendiente separado solo el refinamiento de diversidad real.]
- [x] Modo Presupuesto: ofrecer 3 variantes de seleccion para el mismo presupuesto (lista chica = pocos juegos/ticket alto, lista media = balanceada, lista grande = mas juegos/ticket bajo). [Implementado base y evidenciado en artifacts HTML/JSON/MD.]
- [x] Modo Presupuesto: mejorar la diversidad real del reroll/reemplazos cuando varias opciones terminan sintiéndose demasiado parecidas o repiten casi los mismos juegos. [Cerrado 2026-04-24: diversidad suave y determinística para variantes no principales y primeras sugerencias de reemplazo, con fallback cuando faltan alternativas.]
- [x] Corregir el reroll/reemplazo en `Tu Presupuesto Ideal`: al cambiar un juego se actualizan texto/precio pero la imagen puede quedarse en la opción anterior. [Cerrado 2026-04-24: los payloads de reroll incluyen `image_url` y `applyBudgetOption` actualiza la cápsula visible.]
- [x] [Quick Win] Agregar acceso rápido a gráfica/histórico de precios junto al mínimo histórico. [Cerrado 2026-04-24: el HTML interactivo muestra `Ver historial` junto a `Mín. histórico` cuando hay historial local suficiente y el fallback legacy quedó alineado.]
- [ ] [Track] Revisar/replantear bloque de tendencia (`trend`). [Parcial 2026-04-24: el reporte demota señales débiles; Markdown solo muestra `Historial local` con señales útiles y HTML solo muestra columna/salto si hay snapshots suficientes, con copy de “no es predicción”. Falta: validación manual final y decidir si se reemplaza por una señal más accionable.]
- [x] Renombrar/ajustar trend para lenguaje mas claro al usuario final (ej. "Tendencia de precios") y simplificar su interpretacion.
- [x] Dashboard historico: agregar notas/highlights breves a los botones debajo de los selectores de runs (`Comparar runs`, `Recargar runs`, `Restablecer filtros`) para que se entienda rapido cuando usar cada accion.
- [ ] [Track] Dashboard histórico HTML. [Estado: MVP+ con cobertura automática reforzada para analytics/filtros/orden/parsing. Falta: validación manual final en browser, gráficos/tendencias más ricos, comparativa entre runs, deltas de wishlist y refinamiento visual. Evidencia: navegación manual fluida entre runs y comparación clara en browser.]
- [x] [Quick Win] Dashboard historico: ajustar el copy, spacing y alineación del bloque de búsqueda y del CTA rápido (`Comparar 2 recientes`), porque hoy se ve desbalanceado visualmente y no queda al mismo nivel para un usuario normal. [Cerrado 2026-04-24: copy y layout del bloque de búsqueda/atajo rápido refinados.]
- [ ] [Track] Mejorar detección, contexto y picks por promo activa de Steam. [Estado: clasificador y `active_promo_context` ya persisten en JSON/historial/reportes con razones conservadoras en Top Picks. Falta: usar esos datos para picks/cache por promo, naming de promos simultáneas y contexto de comprar ahora vs esperar. Evidencia: reportes con picks por fest/oferta temática/launch/`Weeklong`/`Midweek`/`Weekend Deals`.]
- [ ] [Futuro] Agregar selector de moneda en UI para cambiar divisa de precios. [Estado: no priorizado. Falta: definir alcance de conversión/formato y fuentes de precio por moneda. Evidencia: UI permite cambiar divisa sin romper reportes.]
- [x] [Quick Win] Filtros avanzados: agregar filtro por tipo de recomendación/mensaje en Top Picks. [Cerrado 2026-04-24: el HTML interactivo agrega controles por recomendación (`Comprar ahora`, `Muy buena oferta`, `Vale la pena`, `Solo si ya lo traías en radar`) con contador y estado vacío.]
- [ ] [Track] Agregar apartado `Shuffle 1 juego`. [Parcial 2026-04-24: primer corte en HTML interactivo recomienda 1 juego desde Top Picks o deals y permite rotar con `Dame otro` entre candidatos serializados; fallback legacy alineado. Falta: calibrar mejor por presupuesto/actividad y validar manualmente en reporte real. Evidencia: bloque funcional en reporte/UI con reroll estable.]
- [x] [Quick Win] Como primer corte del track de outputs/reportes, aclarar todavía más el comportamiento esperado al abrir o descargar archivos generados (`/files/...`) para que HTML/MD/JSON/CSV se sientan consistentes y no den impresión de página en blanco o de que no pasó nada. [Cerrado 2026-04-24: `Ver último HTML` abre el reporte interactivo; enlaces finales distinguen `Abrir reporte interactivo` vs `Descargar Markdown/JSON/CSV`; `/files/...` usa inline para HTML y attachment para datos.]
- [x] Cambiar etiqueta "Era" por termino mas claro en UI/reportes (ej. "Precio original").
- [x] Ajustar el `<title>` de los reportes HTML para mostrar el nombre visible del perfil de Steam (en lugar de URL/steamid cuando aplique). [Sugerencia tester R1CK]
- [x] [Quick Win] Hacer que el encabezado visible del HTML interactivo use el nombre visible del perfil de Steam en lugar de vanity URL o URL completa cuando exista `profile_display_name`. [Cerrado 2026-04-24: el `<h1>` visible usa `profile_display_name` con fallback a `vanity`.]

### P2 - Cross-platform

- [ ] [Track] Validar build desktop en Linux (Ubuntu LTS). [Estado: doctor READY en `.venv`, build local OK, ventana nativa KDE no-root confirmada, packaging PyInstaller corregido, primer `progress` validado en binario congelado y warm-cache completado. Falta: rerun largo final desde el binario con outputs `.md/.html/.csv` y cierre limpio. Evidencia: entrada en `BITACORA.md` + runbook Linux completo.]
- [ ] [Track] Validar build desktop en macOS (app bundle + apertura local). [Estado: pendiente por falta de host nativo. Falta: ejecutar runbook macOS con `.app`, smoke funcional y cierre limpio. Evidencia: entrada en `BITACORA.md` con build/apertura/outputs/cierre.]
- [x] Documentar dependencias nativas por plataforma para pywebview.
- [ ] [Track] Validar cross-platform el fallback web. [Estado: Linux parcial OK con fallback en primer intento sin backend y luego ventana nativa Qt/X11. Falta: validar aviso visible y apertura en navegador por defecto en desktop/macOS/host nativo. Evidencia: runbooks con fallback documentado por plataforma.]
- [ ] [Track] Automatizar y reforzar readiness desktop/cross-platform. [Estado: CLI `--doctor`/`--doctor-fix`, Web UI `Doctor desktop`/`Autofix desktop`, cobertura base Linux/macOS/Windows y runbooks ya existen. Falta: script de flujo repetitivo (doctor, warm-cache, build, run/smoke, logs/evidencia) e instalador/autofix real de nivel sistema. Evidencia: comando reproducible que recolecte evidencia sin pasos manuales repetidos.]

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
- Modularización por dominios cerrada: `steam_deals_generator.py` queda como frontera de compatibilidad y la orquestación vive delegada en módulos `app/*`, `renderers/*` y helpers compartidos.
- El detalle histórico de cortes intermedios (`renderers`, scoring, HLTB, filtros, history, ITAD, watchlist, config, runtime reporting, cache policy, enrichment/orchestration, output final, post-processing y engagement/post-run) vive en `BITACORA.md`.
- Validación histórica de cierre: `python -m pytest tests/test_generator_logic.py tests/test_shared_cache_utils.py` OK (76 tests).
- Cualquier cambio futuro en este frente debe seguir el mismo enfoque incremental: cortes pequeños, wrappers compatibles cuando haga falta y validación dirigida.

### Nota de cierre P3

- La secuencia base técnica ya quedó cerrada: cross-platform/readiness inicial, README, handlers robustos, separación UI, infraestructura web compartida, smoke tests mínimos, tests de lógica pura, capa shared y modularización del generator.
- Objetivo cumplido: bajar costo de mantenimiento sin frenar el avance del producto.

## Backlog de Features (Estado)

- Base funcional cerrada: eventos estructurados, preflight, acciones rápidas UX, JSON/API local, parser web más robusto y errores accionables.
- Onboarding/UX base cerrado: wizard, banner de modo, presets/1-click run, share base y explicación visible de score/recomendación.
- Desktop base cerrado: launcher pywebview, build unificado, wrappers por plataforma y smoke Windows.
- El detalle histórico vive en `BITACORA.md`; los pendientes activos siguen en `Pendientes Priorizados`.

## Plan Cross-Platform (Consolidado)

### Objetivo

Ejecutar de forma consistente en Windows, macOS y Linux, manteniendo la Web UI como superficie compartida y el wrapper desktop como una capa nativa sin divergencias innecesarias.

### Estado actual

- **Windows**: build y smoke inicial validados; sigue como baseline de apoyo para launcher, doctor, outputs y fallback, pero no cierra P2 por sí solo.
- **Linux**: evidencia local avanzada con `.venv`, build local, ventana nativa KDE no-root, primer evento `progress` del binario congelado y warm-cache persistente completado; falta rerun largo final desde el binario para confirmar `.md/.html/.csv` + cierre limpio.
- **macOS**: validación manual pospuesta hasta contar con host nativo; CI/runner sirve solo como evidencia parcial base.
- **Fallback web**: mitigación requerida para cualquier plataforma donde `pywebview` no inicie backend nativo; ya tiene evidencia parcial Linux y falta cierre cross-platform/manual.

Riesgos vigentes: dependencias nativas de `pywebview`, diferencias de empaquetado/firma, encoding/terminal, permisos/rutas de salida/cache y comportamiento de ventana nativa por OS.

### Criterio de cierre P2 (Done)

P2 se considera **cerrado** cuando se cumpla TODO:

- [ ] Linux validado en host nativo: build, apertura nativa, smoke funcional, cierre limpio y fallback documentado.
- [ ] macOS validado en host nativo: build, apertura `.app`, smoke funcional, cierre limpio y fallback documentado.
- [ ] `BITACORA.md` actualizada con evidencia por paso (comando, resultado, incidencia y workaround si aplica).
- [ ] README y/o runbooks alineados con incidencias reales encontradas en validación manual.

### Orden del Track Desktop

1. **Fase 1 — Linux desktop binario (cierre prioritario)**
   - build local
   - apertura de ventana nativa
   - smoke funcional largo desde el binario
   - `.md/.html/.csv`
   - cierre limpio sin procesos colgados
   - evidencia detallada en `BITACORA.md`
2. **Fase 2 — Paridad compartida y readiness**
   - fallback web
   - Desktop Doctor / Autofix / instalador futuro
   - temas compartidos web/desktop: stop, share, reportes
   - evidencia Windows como baseline de apoyo
3. **Fase 3 — macOS native-host closure**
   - host macOS nativo disponible
   - build `.app`
   - apertura local
   - smoke funcional y cierre limpio

### Modelo de evidencia

- **Web UI/source** cuenta como evidencia funcional del generator, performance y UX compartida.
- **Desktop binario** cuenta como evidencia de cierre desktop real.
- La evidencia web/source **no sustituye** la evidencia nativa del binario para cerrar Linux/macOS.
- Los comandos, checklists detallados y plantillas de evidencia viven en:
  - `docs/runbooks/desktop-linux.md`
  - `docs/runbooks/desktop-macos.md`
  - `docs/runbooks/desktop-windows.md`
- La evidencia larga, comandos ejecutados, incidencias y workarounds se registran en `BITACORA.md`; en `PENDIENTES.md` solo queda el resumen que cambie estado, prioridad o próximo paso.

## Proximo Paso Operativo

- Acción inmediata: relanzar el smoke funcional largo de Linux con cache caliente desde el binario desktop y confirmar `.md/.html/.csv` + cierre limpio.
- Bloqueo actual: la validación manual macOS queda pospuesta hasta contar con host nativo disponible.
- Registro: pasos/checklists en `docs/runbooks/desktop-*.md`, evidencia larga en `BITACORA.md`, y este archivo solo se actualiza si cambia estado, prioridad o próximo paso.

## Trabajo no bloqueado

Mientras Linux/macOS manual sigan pendientes por host nativo o ventana larga de validación, avanzar solo en frentes que no sustituyen el cierre formal de P2:

1. Consolidar evidencia Windows desktop si hay host disponible, usando `docs/runbooks/desktop-windows.md`.
2. Seguir slices del Track Performance P0 para wishlists grandes.
3. Cerrar validación E2E de Obsidian/Notion.
4. Cerrar validación manual/refinamiento del Dashboard histórico.
5. Cerrar calibración y validación larga de Alertas inteligentes v2.

Notas:
- Cada frente debe actualizar su track activo correspondiente en este archivo.
- La evidencia larga, comandos y workarounds van a `BITACORA.md`.
- El cierre formal de P2 sigue condicionado a evidencia manual Linux + macOS según criterio de Done.

## Bitacora reciente

- 2026-04-27: Track outputs/reportes suma carpeta default `output/`, `POST /api/open-output-folder`, botón `Ver carpeta`, botón principal `Generar reportes` y acciones finales agrupadas por HTML interactivo/Share HTML/Markdown/JSON/CSV; validado con `tests/test_generated_files_serving.py tests/test_web_assets.py` (18 tests OK).
- 2026-04-27: Track Performance agrega comparación offline de múltiples logs warm-cache con tabla de deltas para duración, refresh candidates, cooldown, HTTP 400 y fallback; el runbook documenta el uso con 2+ logs. Validado con `tests/test_warm_cache_summary.py` (8 tests OK) y subset performance/cache (`tests/test_generator_logic.py -k "warm_cache or price_cache or fallback or cooldown" tests/test_runtime_paths.py tests/test_shared_cache_utils.py`, 17 selected OK).
- 2026-04-24: Quick wins HTML/histórico cerrados: estadísticas visibles del HTML interactivo usan fallback `sin datos` en vez de `NaN`, el encabezado visible del reporte usa `profile_display_name` cuando existe y el dashboard histórico mejora copy/alineación de búsqueda + `Comparar 2 recientes`; validado con tests focales de renderer y `tests/test_web_assets.py tests/test_track_history_flow.py` (13 tests OK).
- 2026-04-24: Quick win outputs/reportes cierra el primer corte de claridad para `/files/...`: `Ver último HTML` prioriza el reporte interactivo, MD/JSON/CSV descargan explícitamente y el server usa `Content-Disposition` consistente; validado con `tests/test_web_assets.py tests/test_generated_files_serving.py tests/test_shared_web_infra.py` (10 tests OK).
- 2026-04-24: Track outputs/reportes suma errores claros para `/files/...`: nombres inválidos/path traversal devuelven página 403 accionable, faltantes 404 y fallos de lectura 500 sin exponer detalles internos; validado con `tests/test_generated_files_serving.py tests/test_web_assets.py` (13 tests OK).
- 2026-04-24: Quick win de `Tu Presupuesto Ideal` corrige imagen stale en reroll/reemplazo: las opciones serializan `image_url` y el HTML interactivo actualiza la cápsula junto con texto/precio; validado con `tests/test_generator_logic.py -k "budget"` (8 tests OK).
- 2026-04-24: Quick win de diversidad en Modo Presupuesto agrega depriorización suave de juegos ya usados por la variante balanceada y diversifica la primera sugerencia de reemplazo cuando hay alternativas, manteniendo fallback determinístico; validado con `tests/test_generator_logic.py -k "budget"` (10 tests OK).
- 2026-04-24: Quick win del bloque `trend` lo replantea como `Historial local`: se ocultan columnas sin señal útil/snapshots suficientes y el copy aclara que no es predicción; validado con `tests/test_generator_logic.py -k "trend or local_history"` (8 tests OK).
- 2026-04-24: Quick win de filtros avanzados en Top Picks agrega controles por tipo de recomendación, contador visible y estado vacío en el HTML interactivo, manteniendo el fallback legacy alineado; validado con `tests/test_generator_logic.py -k "top_picks or top_pick"` (9 tests OK).
- 2026-04-24: Quick win de acceso rápido a histórico junto a `Mín. histórico` queda cerrado: botón `Ver historial`, foco visual y fallback HTML legacy alineado; validado con `tests/test_generator_logic.py -k "min_historical_trend_jump or local_history"` (3 tests OK).
- 2026-04-24: Track `Shuffle 1 juego` abre primer corte automatizable: bloque HTML determinístico con `Dame otro` que rota entre candidatos de Top Picks/deals y fallback legacy alineado; validado con `tests/test_generator_logic.py -k "shuffle_one_game or top_picks or top_pick"` (12 tests OK).
- 2026-04-24: Track Promos / Active Steam Events avanza con clasificador puro, persistencia de `active_promo_context` en JSON/historial, contexto visible en reportes Markdown/HTML y razones conservadoras en Top Picks; falta decidir si habrá cache policy por promo activa.
- 2026-04-24: Track Alertas inteligentes v2 extrae el conteo a un helper puro y agrega fixtures determinísticas para mínimo global, bundles, subidas, mejor local y `alert_score_min`; validado con `tests/test_generator_logic.py -k "smart_alerts or deal_comparison or trends or itad_orchestration"` (9 tests OK). Falta corrida real/larga para calibración operativa.
- 2026-04-24: Track Performance avanza con observabilidad de fallback individual, cooldown corto para fallos/no-data, runbook `docs/runbooks/performance-warm-cache.md` y parser offline `steam_deals_warm_cache_summary.py` para resumir logs warm-cache; siguen pendientes medición en corrida larga y ajustes finales para wishlists grandes.
- 2026-04-23: Track History amplía cobertura automática de analytics, filtros/orden/límites y parsing defensivo; queda pendiente validación manual final en browser.
- 2026-04-22: Track Stop queda casi cerrado en Web UI; falta validar la misma experiencia visible en desktop.
- 2026-04-21: El warm-cache Linux ya quedó completado y el siguiente paso operativo sigue siendo relanzar el smoke largo del desktop para confirmar `.md/.html/.csv` + cierre limpio.

## Archivo historico

La bitácora cronológica detallada, evidencia operativa y entradas antiguas viven en `BITACORA.md`.

`PENDIENTES.md` sigue siendo la fuente única de verdad para pendientes activos, prioridades, estado actual y próximo paso operativo.

## Backlog de Features (Propuestos - Planning)

### Output/Export

- [ ] [Quick Win] Exportar a Obsidian/Notion (markdown con frontmatter YAML para importación directa). [Estado: `--md-frontmatter` implementado y perfiles/checklist documentados. Falta: validación final E2E de import en host real Obsidian/Notion. Evidencia: import manual exitoso documentado en `BITACORA.md`.]

### Social/Community

- [ ] [Track] Recomendaciones sociales y regalos. [Estado: propuesto. Falta: usar overlap, juegos compartidos, actividad reciente/horas y señales sociales simples para explicar por qué un juego conviene para un amigo o como regalo. Evidencia: recomendaciones con explicación contextual por amigo.]
  - Evitar que regalos repitan exactamente los juegos ya mostrados en overlap/en común, o mezclar ambos grupos de forma más útil para que no se sienta redundante.
  - Explicar cada recomendación con contexto breve (ej. `juega mucho X`, `jugó Y recientemente`, `se parece a Z`).

### Recomendaciones

- [ ] [Track] Recomendaciones personalizadas por actividad y biblioteca. [Estado: propuesto. Falta: sugerir juegos similares y mejores deals según últimos juegos jugados, más jugados, horas, géneros y relaciones marcadas (`me gusta` / `similar a`). Evidencia: ranking personalizado con razones visibles.]
  - Incluir análisis de biblioteca: tiempo total (HLTB), distribución por género y precio promedio.
  - Reutilizar la lógica social cuando aplique, pero adaptada al propio perfil del usuario.

### Producto / Plataforma

- [ ] [Futuro] [Track] Unificar Steam Deals, Watchlist, Compare y PAYDAY 2 bajo una UX de suite con módulos claros. [Estado: no priorizado. Falta: definir navegación, límites entre módulos y estrategia de migración. Evidencia: propuesta de UX/suite antes de implementar.]

### PAYDAY 2 DLC Tracker

- [ ] [Quick Win] Probar el dashboard PAYDAY 2 con datos reales antes de expandir alcance. [Estado: propuesto; branding, favicon y máscaras originales ya quedaron como corte visual. Falta: corrida manual con `python3 payday2_web.py`, actualizar datos, marcar/desmarcar DLCs y revisar cache/precios. Evidencia: sesión real sin errores visibles y experiencia cómoda en `http://127.0.0.1:8081`.]
- [ ] [Track] Pulir UX del dashboard PAYDAY 2 solo si el uso real muestra fricción. [Estado: propuesto. Falta: revisar jerarquía visual, estados vacíos, mensajes de actualización, filtros y acciones de marcado tras una sesión real. Evidencia: lista corta de ajustes validada visualmente sin mezclar la UI de Steam Tools.]
- [ ] [Track] Mejorar recomendaciones de compra de DLCs. [Estado: propuesto. Falta: calibrar reglas de `comprar ahora` vs `esperar`, considerar descuento mínimo, precio final, presupuesto, histórico local/ITAD y bundles. Evidencia: recomendaciones útiles en una corrida real y explicaciones claras por DLC.]
- [ ] [Track] Revisar bundles y marcado manual de propiedad. [Estado: propuesto. Falta: validar bundles reales, deshacer marcado por bundle, manejo de DLCs ya poseídos y limitación de Steam API para detectar ownership de DLCs. Evidencia: checkboxes/bundles actualizan faltantes sin inconsistencias.]
- [ ] [Futuro] [Track] Agregar export/compartir específico para PAYDAY 2 si hace falta. [Estado: no priorizado. Falta: decidir si conviene exportar lista de faltantes/recomendados a Markdown/HTML/share o si el dashboard basta. Evidencia: output PAYDAY 2 útil sin duplicar lógica innecesaria.]
- [ ] [Futuro] [Track] Evaluar convertir PAYDAY 2 en base para un Steam DLC Tracker genérico. [Estado: no priorizado. Falta: extraer configuración por juego (`base_appid`, nombre, namespace de cache, copy/branding) y mantener PAYDAY 2 como perfil especial, sin mezclarlo todavía con Steam Tools. Evidencia: propuesta técnica antes de implementar y prueba con al menos otro juego con DLCs.]

### Alertas inteligentes

- [ ] [Track] Cerrar Alertas inteligentes v2. [Estado: base implementada y conteo extraído a helper puro con fixtures para mínimo histórico global, bundles activos, nueva mejor oferta local, subidas vs run anterior y `--alert-score-min`. Falta: calibrar umbrales con corrida real/larga y cerrar criterios operativos. Evidencia: alertas útiles en run real y criterios claros.]

### Expansion de Datos

- [ ] [Track] Enriquecer y depurar la wishlist con señales externas. [Estado: propuesto. Falta: detectar juegos cubiertos por `HLTB CSV`, `Family JSON`, biblioteca propia, catálogo Steam eliminado u otras plataformas; empezar como sugerencia/filtro/exclusión opcional, no borrado automático. Evidencia: apartado de higiene con import/investigación de GOG/Epic/etc.]
- [ ] [Futuro] [Track] Ampliar la comparativa multi-tienda para Fanatical y más stores. [Estado: no priorizado. Falta: metadata normalizada por tienda, tipo de tienda, bundles activos/ITAD y filtros de confianza. Evidencia: comparativa multi-tienda coherente sin mezclar tiendas oficiales/keyshops.]
