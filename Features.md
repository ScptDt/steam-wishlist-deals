# Features

Inventario de features del proyecto y del enfoque Playnite. Este archivo enumera capacidades; los detalles operativos, evidencia y pendientes viven en `PENDIENTES.md`, `BITACORA.md` y `docs/runbooks/`.

## Steam Tools

- Web UI local en `127.0.0.1` para configurar, ejecutar y revisar reportes.
- CLI para automatización, filtros avanzados, warm-cache y corridas reproducibles.
- Desktop wrapper con pywebview reutilizando la Web UI y fallback a navegador.
- Reportes Markdown, HTML interactivo, Share HTML, JSON técnico y CSV opcional.
- Top Picks con razones visibles, ranking local y señales advisory.
- Decision Advisor JSON-only para sugerir comprar, revisar, esperar o ignorar usando señales existentes.
- Presupuesto ideal para armar una selección de compra por presupuesto.
- Watchlist personal con precio objetivo por juego.
- Comparación de wishlists, ideas de regalo y regalos grupales.
- Historial local entre runs para detectar ofertas nuevas, terminadas, subidas y bajadas.

## Datos y enriquecimiento

- Precios/descuentos de Steam Store con caché local.
- Reviews de Steam, Metacritic y metadata básica.
- Compatibilidad Steam Deck, ProtonDB y anti-cheat.
- Achievements y completitud global.
- Tags, géneros, categorías y señales de modo de juego.
- ITAD para mínimos históricos, bundles y comparativa multi-tienda cuando hay key/caché válida.
- GG.deals e ITAD `external_offers` desde caché local, sin checkout ni ownership.
- HLTB mediante import local.
- Free Weekend como fuente live/cache separada y opt-in.

## Imports locales advisory-only

- `wishlist_external_matches_json` para revisar juegos de la wishlist que quizá ya están cubiertos en otra tienda.
- `play_access_json` para juegos instalados o jugables localmente sin compra nueva.
- `steam_access_json` para AppIDs owned/family/wishlist exportados localmente sin login directo.
- `player_preferences_json` para preferencias manuales del perfil conductual.
- `behavioral_signals` y `behavioral_explanations` para señales de estilo de juego y razones visibles.
- `player_behavior_fit` y `decision_support` para ajuste conductual y soporte de decisión.
- `decision_advisor` como payload advisory de compra/revisión/espera/ignorar.

## Wishlist hygiene multi-store

- Sugerencias no destructivas para revisar wishlist.
- Matches externos por AppID, external ID, título normalizado o revisión manual.
- Detección de juegos que aparecen en GOG, Epic, Amazon, Xbox, Ubisoft u otras fuentes locales.
- Diferenciación entre biblioteca/import local (`external_matches`) y precios externos (`external_offers`).
- Soporte para matches de confianza alta por AppID y confianza media por título normalizado.
- Salida siempre `advisory_only`: revisar antes de comprar o quitar manualmente.

## Playnite actual

- Contrato `steamtools_playnite_library_v1` para exportar presencia de juegos por launcher/plataforma.
- Parser de `steamtools_playnite_library_v1` vía `--wishlist-external-matches-json`.
- Contrato `steamtools_playnite_access_v1` para exportar instalado/jugable sin rutas locales.
- Parser de `steamtools_playnite_access_v1` vía `--play-access-json`.
- Contrato `steamtools_playnite_unmatched_v1` como helper/fixture local de diagnóstico para juegos sin AppID o match confiable; todavía no es botón del add-on ni campo Web dedicado.
- Separación explícita entre Playnite y Steam Family: Playnite no prueba ownership ni Family.

## Playnite add-on MVP

- Add-on local de Playnite como C# `GenericPlugin`.
- Exportación iniciada manualmente desde menú de Playnite.
- Exportar inventario seguro de juegos con nombre, launcher/source, provider ID sanitizado, AppID Steam si existe y estado instalado/jugable.
- Exportar `steamtools_playnite_library_v1` para wishlist hygiene.
- Exportar `steamtools_playnite_access_v1` para acceso local/jugable.
- Base para diagnóstico de juegos sin AppID o match confiable; el export desde el add-on queda pendiente de un slice posterior.
- Guardar JSON mediante diálogo elegido por el usuario.
- Mostrar JSON en diálogo seleccionable/copiable como alternativa.
- No usar red, endpoint local, background sync ni auto-export.
- No serializar objetos completos de Playnite ni `GameAction`.

## Features habilitadas por Playnite

- Inventario multi-launcher local: saber en qué launcher aparece cada juego.
- Wishlist hygiene por otra plataforma: detectar juegos de Steam wishlist que ya aparecen en Epic, GOG, Amazon, Xbox, Ubisoft u otros launchers.
- Revisión por título normalizado cuando no existe AppID Steam confiable.
- Señal de acceso local: marcar juegos instalados o jugables para revisar antes de comprar.
- Diagnóstico de duplicados entre launchers.
- Diagnóstico de juegos sin AppID Steam confiable.
- Base futura para vista de biblioteca multi-store local.
- Base futura para dedupe manual de wishlist sin acciones destructivas.

## Smart Alerts y automatización

- Digest/preview local de Smart Alerts agrupado y anti-spam.
- Readiness policy fixture-only para canales futuros.
- Preview builder de mensajes de canal sin envío externo.
- Fake delivery plan y fake sender boundary para pruebas sin Telegram/Discord real.
- Opt-in preview de canales Smart Alerts en CLI/Web/reportes, default-off y dry-run.
- Scheduler foreground/local-only vía CLI/Web/Desktop, sin daemon ni autostart.

## PAYDAY 2 DLC Tracker

- Dashboard Web local.
- CLI standalone.
- Plan de compra por presupuesto, umbral de oferta y ownership manual.
- Caché de catálogo/precios, historial local y diagnóstico de DLC faltante.
- Outputs Markdown, HTML y CSV opcional.

## Guardrails de producto

- Local-first: datos, cachés, imports y reportes permanecen en la máquina del usuario.
- Advisory-only: imports locales no cambian score/ranking/defaults por sí mismos.
- Sin auto-buy, checkout, carrito, pagos, auto-hide, auto-remove ni mutaciones Steam.
- Sin passwords, cookies/tokens Steam, raw responses privados ni scraping autenticado.
- Sin rutas locales, ejecutables, argumentos, scripts, notas, imágenes ni metadata cruda en exports Playnite.
- Sin inferir ownership, Steam Family o propiedad definitiva desde Playnite.
