# Features actuales

Catálogo compacto de capacidades implementadas. El README se mantiene breve; los contratos, validaciones y detalles largos viven en los runbooks enlazados.

## Steam Deals

- **Web UI local**: wizard principal en `steam_deals_web.py` para configurar, ejecutar y revisar resultados desde `127.0.0.1`.
- **CLI**: `steam_deals_generator.py` para automatización, scripting, filtros avanzados y warm-cache.
- **Desktop wrapper**: `steam_tools_desktop.py` reutiliza la misma Web UI con `pywebview` y fallback a navegador.
- **Reportes**: Markdown, HTML interactivo, Share HTML, JSON técnico, exports JSON separados de ofertas/wishlist y CSV opcional.
- **Top Picks y recomendaciones**: ranking/discovery, razones visibles, señales advisory y soporte para Decision Advisor JSON-only; score no se presenta como recomendación personalizada si faltan señales conductuales.
- **Tu Presupuesto Ideal**: selección greedy por presupuesto con contexto de recomendación.
- **Watchlist personal**: precio objetivo por juego y alertas de cambios relevantes.
- **Comparar wishlists**: overlap, ideas de regalo y regalos grupales para múltiples perfiles.
- **Historial entre runs**: comparación local de deals nuevos, terminados, subidas/bajadas y drilldown por juego.

## Datos y enriquecimiento

- Precios/descuentos de Steam Store con caché local.
- Reviews de Steam, Metacritic y metadata básica de juegos.
- Compatibilidad Steam Deck, ProtonDB y anti-cheat.
- Achievements y completitud global.
- Tags/géneros/categorías y señales de modo de juego.
- ITAD para mínimos históricos, multi-tienda y bundles cuando hay key/caché válida.
- GG.deals/ITAD `external_offers` desde caché local, sin checkout ni ownership.
- HLTB mediante import local.
- Free Weekend como fuente live/cache separada y opt-in.

## Imports locales advisory-only

- `wishlist_external_matches_json`: revisar si quizá ya tienes juegos en otra tienda.
- `play_access_json`: juegos instalados/jugables sin compra nueva.
- `steam_access_json`: AppIDs owned/family/wishlist exportados localmente, sin login directo.
- `player_preferences_json`: preferencias manuales para perfil conductual local.
- `behavioral_signals` / `behavioral_explanations`: señales de estilo de juego y razones visibles.
- `player_behavior_fit` / `decision_support`: ajuste conductual y soporte de decisión JSON-only.
- `decision_advisor`: payload advisory para compra/revisión/espera/ignorar usando señales existentes.

## Caché, performance y automatización

- `--warm-cache`: precalienta precios sin generar reportes.
- `--warm-cache-full`: completa pendientes en pasadas resumibles con la misma caché.
- Stale-while-revalidate, cooldown de fallos temporales y presupuesto resumible por corrida.
- Planner de fetching de precios con métricas separadas `individual_planificado` vs `fallback_reactivo`.
- Scheduler foreground/local-only vía CLI/Web/Desktop, sin daemon ni autostart.
- Notificaciones Telegram/Discord con resumen agregado; Smart Alerts v2 se mantiene como preview/dry-run salvo integración aprobada.

## PAYDAY 2 DLC Tracker

- Dashboard Web local en `payday2_web.py`.
- CLI standalone `payday2_dlc_tracker.py`.
- Plan de compra por presupuesto, umbral de oferta y ownership manual.
- Caché de catálogo/precios, historial local y diagnóstico de DLC faltante.
- Outputs Markdown, HTML y CSV opcional.

## Guardrails de producto

- Local-first: server en loopback, config/cache/reportes en la máquina del usuario.
- Imports locales son advisory-only: no cambian score/ranking por sí mismos.
- No checkout, carrito, pagos, auto-buy, auto-hide, auto-remove ni mutaciones Steam.
- No manejar passwords, cookies/tokens Steam ni raw responses privados.
- No versionar caches, logs, builds ni reportes generados.

## Referencias

- Runbooks: `docs/runbooks/README.md`
- Guía Steam Deals: `steam_deals_guia.md`
- Guía PAYDAY 2: `payday2_guia.md`
- Performance/warm-cache: `docs/runbooks/performance-warm-cache.md`
- Behavioral/Decision Advisor: `docs/runbooks/behavioral-signals-contract.md`, `docs/runbooks/decision-advisor-v0.md`
