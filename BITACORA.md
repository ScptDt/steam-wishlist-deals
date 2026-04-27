# Bitácora Operativa

Ultima actualizacion: 2026-04-24

## Proposito

Este archivo concentra el historial cronológico de avances, validaciones, hallazgos,
workarounds y evidencia operativa del proyecto.

`PENDIENTES.md` sigue siendo la fuente única de verdad para:
- pendientes activos
- prioridades
- estado actual
- proximo paso operativo

`BITACORA.md` NO reemplaza `PENDIENTES.md`.
Su función es servir como historial detallado y referencia operativa.

## Regla de uso

Mover aquí:
- avances cerrados o parciales que ya no cambian la prioridad del backlog
- evidencia cronológica por fecha
- workarounds, validaciones y notas históricas
- entradas largas que cargan demasiado `PENDIENTES.md`

Mantener en `PENDIENTES.md`:
- tracks activos
- quick wins activos
- bloqueos vigentes
- estado general
- siguiente paso operativo
- una bitácora reciente corta si todavía afecta decisiones actuales

## Formato de entrada

### YYYY-MM-DD
- [Area] Resumen corto del cambio/avance
- Evidencia:
  - comando / prueba / artefacto / resultado
- Impacto:
  - qué pendiente afecta o qué frente destraba
- Siguiente seguimiento:
  - si ya no aplica, poner `ninguno`

## Bitacora reciente de migracion

- 2026-04-24: `README.md` compacta el tail de referencia: flags comunes reemplazan la tabla completa, PAYDAY 2 queda como resumen con link a `payday2_guia.md`, y caché/config se condensan en notas de datos locales.
- 2026-04-24: `README.md` compacta `Mapa de módulos y entrypoints` hacia una tabla de superficies + resumen interno; `docs/project-rules.md` enlaza explícitamente el índice `docs/runbooks/README.md`.
- 2026-04-24: Se crea `docs/runbooks/README.md` como índice central de runbooks y `README.md` pasa a enlazar ese índice para desktop, performance y validaciones de features.
- 2026-04-24: Se crea `docs/runbooks/features-validation.md` para mover checklists de frontmatter Obsidian/Notion, `Tu Presupuesto Ideal` y share E2E fuera del README; `README.md` queda con resúmenes y links.
- 2026-04-24: `README.md` se alinea con la separación documental: compacta desktop/cross-platform hacia resumen + links a runbooks, corrige `Budget Mode` a `Tu Presupuesto Ideal` y actualiza formatos de salida Steam Deals.
- 2026-04-24: `PENDIENTES.md` normaliza pendientes abiertos con etiquetas `[Track]`, `[Quick Win]` o `[Futuro]` y notas compactas de Estado/Falta/Evidencia para facilitar cierre futuro.
- 2026-04-24: `PENDIENTES.md` compacta `Backlog de Features (Estado)` porque sus elementos estaban cerrados; queda un resumen de capacidades base y el detalle histórico permanece en esta bitácora.
- 2026-04-24: `PENDIENTES.md` compacta `Proximo Paso Operativo` a acción inmediata, bloqueo actual y regla de registro, evitando repetir estado P2/runbooks.
- 2026-04-24: `PENDIENTES.md` compacta `Bitacora reciente` a un resumen corto de entradas que aún afectan decisiones actuales; el detalle cronológico cerrado permanece en esta bitácora.
- 2026-04-24: `PENDIENTES.md` reemplaza `Plan inmediato (Windows / No bloqueado)` por `Trabajo no bloqueado`, dejando solo orientación y referencias a tracks activos para evitar duplicar backlog.
- 2026-04-24: `PENDIENTES.md` compacta `Plan Cross-Platform (Consolidado)` para dejar solo estado, criterio de cierre, fases y referencias; los comandos/checklists detallados permanecen en `docs/runbooks/desktop-*.md` y la evidencia larga en esta bitácora.
- 2026-04-24: `PENDIENTES.md` compacta la nota extensa de P3/modularización; la evidencia histórica de cortes, validaciones y comandos permanece en esta bitácora para no cargar el backlog vivo.
- 2026-04-23: Se crea `BITACORA.md` para sacar del backlog vivo la bitácora cronológica detallada y dejar `PENDIENTES.md` más enfocado en pendientes activos, prioridades y próximo paso operativo.

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

- 2026-04-27: Quick win de UX en Share/Compartir: el modal y reportes usan `Compartir oferta`, `Compartir juegos destacados`, texto sin jerga de `payload` y feedback `¡Copiado!`; se mantiene compatibilidad `steamtools://share`. Validado con `tests/test_generator_logic.py -k "share"` (6 tests OK) y `tests/test_desktop_share.py tests/test_web_assets.py` (22 tests OK).
- 2026-04-27: Quick win de copy en Dashboard histórico: se corrigen acentos visibles (`Página`, `Salió`, `Cambió`, `histórico`) y se reemplaza copy técnico de `include_same`/`run` por lenguaje de usuario. Validado con `tests/test_track_history_flow.py tests/test_web_assets.py` (17 tests OK).
- 2026-04-22: Track Stop queda casi cerrado: la Web UI ya no duplica `Solicitando detener ejecucion...`, `/api/stop` usa estados veraces y una prueba manual en browser confirmó que el run sí se detiene. La validación equivalente en desktop se difiere al Track Desktop mientras el launcher/fallback sigue estabilizándose.
- 2026-04-22: Quick win de UX en reportes HTML: el encabezado visible pasa de `Steam Deals` a `Ofertas de Steam`, para sonar menos como nombre interno de script y más como pantalla orientada al usuario.
- 2026-04-22: Quick win de UX en la tarjeta final: `Último reporte` se renombra a `Resumen de tu última ejecución`, alineado con el lenguaje más claro del historial y la UI principal.
- 2026-04-22: Quick win de consistencia UX en histórico/resumen: se eliminan restos de inglés como `Quick compare activo`, `deals` y `Top cambios`, sustituyéndolos por copy más natural (`Comparación rápida activa`, `ofertas`, `cambios destacados`).
- 2026-04-22: Quick win de UX en histórico: cuando una ejecución no trae nombre de promo/festival, el resumen deja de mostrar `Steam Deals` y usa `Sin evento detectado`, que comunica mejor lo que pasó.
- 2026-04-21: Quick win de UX en archivos opcionales: `HLTB CSV` y `Family JSON` se humanizan a `Export de HowLongToBeat (CSV)` y `Biblioteca familiar (JSON)`, para que el usuario entienda mejor qué archivo espera cada campo.
- 2026-04-21: Quick win de UX en archivos opcionales: `Directorio de salida` pasa a `Dónde guardar los reportes` y su placeholder se vuelve más claro (`Usar carpeta actual`).
- 2026-04-21: Quick win de UX en notificaciones automáticas: los placeholders de Telegram y Discord ahora se vuelven más guiados (`Pega aquí el token del bot`, `Pega aquí el webhook del canal`) en vez de dejar ejemplos crudos poco explicativos.
- 2026-04-21: Quick win de UX en notificaciones automáticas: el placeholder de `ID del chat de Telegram` deja el ejemplo crudo y pasa a pedir la acción directamente (`Pega aquí el ID del chat o canal`).
- 2026-04-21: Quick win de UX en notificaciones automáticas: los labels de Telegram/Discord se humanizan (`Token del bot de Telegram`, `ID del chat de Telegram`, `Webhook de Discord`) para depender menos de jerga técnica cruda.
- 2026-04-21: Quick win de UX en notificaciones automáticas: `Telegram Bot Token`, `Telegram Chat ID` y `Discord Webhook` ahora explican mejor para qué sirve cada campo y dónde impacta el aviso.
- 2026-04-21: Quick win de consistencia UX: `Solo deals nuevos` se renombra a `Solo ofertas nuevas`, manteniendo el mismo comportamiento pero con lenguaje más natural para usuario normal.
- 2026-04-21: Quick win de consistencia UX en Steam Deck: estados visibles como `Verified`, `Playable` y `Unsupported` se traducen a `Verificado`, `Jugable` y `No compatible` en reportes/labels visibles.
- 2026-04-21: Quick win de UX en la antigua `Watchlist`: la sección ahora se presenta como `Alertas de precio`, aclara para qué sirve y cambia `AppID` por `ID del juego` para sonar menos técnica.
- 2026-04-21: Quick win de UX en configuración: `Fuentes de datos` pasa a `Archivos opcionales` y ahora explica mejor para qué sirven `HLTB CSV`, `Family JSON` y el `Directorio de salida`.
- 2026-04-21: Quick win de UX en configuración: `Notificaciones` pasa a `Notificaciones automáticas` y su hint ahora explica mejor que te avisa sobre ofertas nuevas o cambios de precio importantes.
- 2026-04-21: Quick win de UX en histórico: se elimina `(MVP)` del título porque era jerga interna que no aportaba nada al usuario final.
- 2026-04-21: Quick win de consistencia UX en histórico: el resumen de cada ejecución deja de mostrar `deals` y pasa a `ofertas`, manteniendo el evento/festival visible con wording más natural.
- 2026-04-21: Quick win de consistencia UX en resúmenes: el pill `nuevos` se aclara a `ofertas nuevas`, alineado con el wording de `Solo ofertas nuevas` para evitar términos demasiado ambiguos.
- 2026-04-21: Quick win de consistencia UX en resúmenes: el pill `Deck Verified` se humaniza a `verificados para Steam Deck`, alineado con el resto del lenguaje ya traducido.
- 2026-04-21: Quick win de consistencia UX en reportes/tablas: `Steam Deck / Linux` y `Steam Deck` se simplifican hacia `Compatibilidad`, y el dashboard resume mejor la sección como `Compatibilidad Steam Deck y Linux`.
- 2026-04-21: Quick win de UX en reportes: `Tipo de juego` ahora se acompaña de una nota breve para aclarar que resume si el juego es solo, cooperativo, PvP o multijugador.
- 2026-04-21: Quick win de consistencia UX en reportes/tablas: `Deck`/`Deck/Linux` y `Modo` se humanizan hacia `Steam Deck` / `Steam Deck / Linux` y `Tipo de juego`, para que los headers suenen menos técnicos y más claros.
- 2026-04-21: Quick win de consistencia UX: `MC` pasa a mostrarse como `Metacritic` en tablas/reportes visibles, evitando abreviaturas poco claras para usuario normal.
- 2026-04-21: Quick win de consistencia UX: labels visibles de `Reviews` pasan a `Reseñas` en UI/reportes principales, reduciendo la mezcla innecesaria de inglés y español.
- 2026-04-21: Quick win de lenguaje UX en histórico: `Run` se humaniza a `Ejecución` en labels, hints, títulos y mensajes visibles para que la sección suene menos técnica.
- 2026-04-21: Quick win de consistencia UX: `Top Picks` pasa a mostrarse como `Juegos destacados` también en HTML interactivo y Share HTML, alineado con la UI principal.
- 2026-04-21: Quick win de UX en configuración principal: `Top picks` se renombra a `Juegos destacados`, para sonar menos técnico y más natural para usuario normal.
- 2026-04-21: Quick win de UX en histórico: `Buscar runs` ahora añade ejemplos concretos (`2026-04-21`, `Medieval Fest`, `gaben`) para que el usuario entienda más rápido qué puede escribir ahí.
- 2026-04-21: Quick win de UX en histórico: `Filtrar estado` ahora explica mejor qué significa `Nuevo`, `Salieron` e `Iguales`, para que el usuario no tenga que deducirlo por contexto.
- 2026-04-21: Quick win de UX en filtros avanzados: los checks de Steam Deck también se humanizan en el texto (`Solo juegos que corren en Steam Deck`, `Solo juegos verificados para Steam Deck`), para que se entiendan incluso sin leer el hint adicional.
- 2026-04-21: Quick win de UX en filtros avanzados: `Precio máximo (MXN)` ahora aclara que deja fuera juegos por arriba de ese tope, para que el usuario entienda mejor cuándo conviene usarlo.
- 2026-04-21: Quick win de UX en configuración principal: `Ordenar por` ahora explica mejor que cambia el criterio de acomodo del reporte y sugiere dejar `Score` si no sabes cuál usar.
- 2026-04-21: Quick win de UX en configuración principal: `Descuento mínimo` ahora aclara que subirlo deja fuera ofertas pequeñas y concentra el reporte en descuentos más fuertes.
- 2026-04-21: Quick win de UX en filtros avanzados: `Generar CSV` ahora aclara que sirve para llevar resultados a Excel o Google Sheets, en vez de quedar como una opción técnica sin contexto.
- 2026-04-21: Quick win de UX en filtros avanzados: `Solo deals nuevos` ahora aclara que compara contra el run anterior y que, sin historial previo, puede aportar poco o nada.
- 2026-04-21: Quick win de UX en filtros avanzados: los checks de Steam Deck ahora explican mejor la diferencia entre `compatible` y `Verified`, para que el usuario normal entienda qué tanto quiere restringir los resultados.
- 2026-04-21: Quick win de UX en filtros avanzados: `Max HLTB horas` se humaniza a `Duración máxima (horas)` y ahora aclara que sirve para priorizar juegos más cortos o evitar experiencias demasiado largas.
- 2026-04-21: Quick win de UX en filtros avanzados: los filtros de reviews ahora usan labels más claros (`Reviews positivas mín.`, `Cantidad mínima de reviews`) y explican mejor qué estás filtrando y por qué puede ayudarte.
- 2026-04-21: Quick win de UX en `Top picks`: el campo ahora aclara que solo controla cuántos juegos se destacan arriba y que no cambia el total de deals del reporte.
- 2026-04-21: Quick win de UX en histórico: `Buscar runs` deja de usar términos técnicos en el placeholder (`steam_id`/`vanity`) y ahora se apoya en un hint más claro (`fecha, evento o perfil`).
- 2026-04-21: Quick win de UX en histórico: `Orden delta` ahora tiene un hint más claro para explicar cuándo conviene ver primero subidas, bajadas o cambios fuertes entre runs.
- 2026-04-21: Quick win de UX en histórico: `Incluir precios sin cambio` ahora lleva un hint directo para explicar que agrega juegos cuyo precio quedó igual entre ambos runs.
- 2026-04-21: Quick win de UX en histórico: `Run A (base)` y `Run B (comparar)` se renombran a `Run inicial` y `Run a comparar`, para que el selector suene menos técnico y más claro para usuario normal.
- 2026-04-21: Quick win de UX en histórico: la opción `Default` dentro de `Orden delta` se renombra a `Orden normal`, para que el usuario entienda mejor que no está priorizando subidas o bajadas especiales.
- 2026-04-21: Quick win de UX en `Workers de enrichment`: el hint ahora explica en lenguaje más práctico cuándo dejar `12`, cuándo probar `16` y cuándo bajar a `8`, en vez de quedarse en wording demasiado técnico.
- 2026-04-21: Quick win de UX en `Comparar con`: el hint ahora explica mejor que sirve para ver juegos en común e ideas de regalo, además de recordar que la wishlist del amigo debe ser pública.
- 2026-04-21: Quick win de UX en Top Picks: se agrega una guía breve para interpretar `Comprar ahora`, `Vale la pena` y `Solo si ya lo traías en radar`, reduciendo la ambigüedad de esas recomendaciones rápidas para usuario normal.
- 2026-04-21: Quick win de UX en reportes HTML: `Mín. histórico` ahora puede mostrar un acceso rápido `Ver tendencia` cuando existe sparkline local, para saltar visualmente al movimiento de precio del mismo juego sin buscarlo a mano.
- 2026-04-21: Quick win de UX en histórico: el botón de comparación rápida ahora se muestra apilado con su hint y cambia su copy a `Comparar 2 recientes`, evitando el look apretado/extraño que tenía al competir visualmente con el texto explicativo.
- 2026-04-21: Quick win de UX/estado en cache: la UI ahora refuerza que `Ignorar cache` arranque desmarcado incluso al recargar o volver a la página (`pageshow`), para evitar que el navegador reviva un estado visual viejo y confunda al usuario.
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
