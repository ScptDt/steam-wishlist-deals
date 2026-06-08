# Steam Wishlist Deals Generator

Analiza tu wishlist de Steam y genera reportes detallados con deals, comparaciones de precios, compatibilidad, y mucho más.

## Features

### Datos y Análisis
- **Precios y descuentos** — Filtra deals por descuento mínimo, precio máximo, etc.
- **Reviews de Steam** — Porcentaje de reviews positivas y total de reviews
- **Metacritic Score** — Score de Metacritic integrado desde la API de Steam
- **Steam Deck / ProtonDB / Anti-Cheat** — Compatibilidad completa para Linux/Deck
- **Achievements** — Total de logros y porcentaje promedio de completion global
- **Multiplayer/Co-op** — Detección automática de modo de juego (Co-op, PvP, Single, Multi)
- **Etiquetas (SteamSpy)** — Categorización por etiquetas + estimación de jugadores
- **ITAD (IsThereAnyDeal)** — Mínimo histórico, precios multi-tienda, bundles activos
- **HLTB (HowLongToBeat)** — Cruce con tu backlog exportado de HLTB
- **Higiene de wishlist** — Sugerencias locales de revisión, incluyendo matches externos importados manualmente (`advisory-only`, sin borrar ni cambiar score)
- **Historial de precios** — Tendencias locales con sparklines SVG en el HTML
- **Top Picks** — Ranking por value score (reviews, descuento, prioridad, $/hora, Deck, Metacritic y antigüedad, medida como años desde lanzamiento) con recomendación rápida y razones visibles

### Herramientas
- **Watchlist Personal** — Alertas cuando un juego baja de tu precio objetivo
- **Tu Presupuesto Ideal** — "Tengo $500, ¿qué compro?" — optimizador greedy por eficiencia con contexto de recomendación en los picks sugeridos
- **Comparar Wishlists** — Overlap con amigos + gift ideas
- **Notificaciones** — Telegram y Discord webhook con resumen de cambios
- **Scheduler** — Ejecución automática cada N horas
- **Comparación entre runs** — Detecta deals nuevos, terminados y bajadas de precio; incluye quick compare de los últimos 2 runs, búsqueda/paginación de historial, filtros persistentes, deep links por URL y drilldown `Ver historial` por juego
- **Alertas inteligentes v2** — Umbrales configurables por subida (`--alert-rise-pct`), margen sobre mínimo global (`--alert-global-margin-pct`) y priorización por score mínimo (`--alert-score-min`); aparecen como resumen visible/JSON y no equivalen por defecto a notificaciones Telegram/Discord por juego

### Salida
- **Markdown** — Reporte completo con tablas, secciones, y badges
- **HTML interactivo** — Dashboard con gráficas, filtros en vivo, thumbnails con hover zoom, sparklines de precio
- **HTML compartible** — Versión ligera para enviar a amigos
- **Título de reporte con nombre de perfil** — El `<title>` de HTML/Share usa el nombre visible del perfil Steam cuando está disponible (con fallback al identificador original)
- **JSON** — Export estructurado para automatización local (`meta`, `inputs`, `summary`, `top_picks`, `deals`, `budget_result`, etc.)
- **CSV** — Exportación para Excel/Google Sheets (+ botón "Copiar para Sheets" en el HTML)
- **Resumen final inteligente** — Alertas clave por run: mejor precio local, subidas vs run anterior, mínimo histórico global y bundles activos, pensadas como revisión de volumen antes de automatizar notificaciones externas

## Requisitos

- Python 3.10+
- **Core (CLI + Web):** sin dependencias externas (solo stdlib)
- **Desktop (pywebview):** requiere dependencias extra de `requirements-desktop.txt`

## Superficies del proyecto

Este repo tiene **dos superficies de UX** y una superficie operativa por CLI:

- **Web UI**: flujo principal en navegador local
- **Desktop**: la misma UI web dentro de una ventana nativa con `pywebview`
- **CLI**: automatización, scripting y flags avanzados

**Recomendado para la mayoría de usuarios: Web UI**.

| Superficie | Objetivo | Dependencias | Entry point |
|------------|----------|--------------|-------------|
| Core CLI | Automatización por terminal y flags avanzados | Solo stdlib | `steam_deals_generator.py`, `payday2_dlc_tracker.py` |
| Web UI | Flujo guiado en navegador local | Solo stdlib | `steam_deals_web.py` (8080), `payday2_web.py` (8081) |
| Desktop | App en ventana nativa (empaquetable) | `requirements-desktop.txt` | `steam_tools_desktop.py`, `build_desktop.py` |

### Cómo se relacionan

- `steam_deals_web.py` es el entrypoint principal de UX para Steam Tools.
- `steam_tools_desktop.py` **no implementa otro frontend**: levanta el mismo server local y abre la misma UI en una ventana nativa.
- `payday2_web.py` sigue disponible como dashboard standalone para PAYDAY 2.
- La lógica pesada vive en los scripts CLI (`steam_deals_generator.py` y `payday2_dlc_tracker.py`); la capa web coordina ejecución, validación y progreso.
- Para trabajo operativo, roadmap y deuda técnica viva, la fuente de verdad sigue siendo `PENDIENTES.md`; la evidencia cronológica detallada y el historial operativo viven en `BITACORA.md`.

## Reglas de trabajo del repo

Resumen corto para mantener rumbo y evitar ruido en el repo:

- **`PENDIENTES.md` es la fuente única de verdad operativa**: backlog, prioridades, estado actual y pendientes vivos.
- **`BITACORA.md` guarda la evidencia cronológica detallada**: validaciones, workarounds, avances históricos y notas operativas largas.
- **La Web UI es la UX principal**; desktop debe seguir reutilizando la misma UI y no abrir otro frontend separado.
- **`CLI` es la superficie operativa** para automatización, flags avanzados y corridas reproducibles.
- **Artefactos temporales o generados no se versionan**: `.tmp/`, `.pytest_cache/`, `logs/`, `output/`, `.cache/`, `build/`, `dist/`, `*.spec`, reportes `Steam Deals*.md/.html/.json/.csv` y `PAYDAY2_Plan_de_Compra.*` son locales.
- **El caché local sí se conserva**: `./.cache/steam_deals` o la ruta persistente equivalente no se limpia por rutina porque acelera corridas reales.
- **Si necesitas un ejemplo o fixture**, guárdalo en `tests/fixtures/` o `docs/` con nombre intencional, no como salida cruda de una corrida real.

Reglas ampliadas y criterios de organización: `docs/project-rules.md` y `docs/runbooks/release-hygiene.md`.

### Ruta rápida recomendada
1. **Web UI (Steam Deals):** `python3 steam_deals_web.py`
2. **Web UI (PAYDAY 2):** `python3 payday2_web.py`
3. **Desktop:** `python steam_tools_desktop.py`
4. **CLI avanzado:** `steam_deals_generator.py` / `payday2_dlc_tracker.py`

## Instalación por superficie

### Core / Web (sin deps externas)

```bash
python3 --version
# listo: no necesitas pip install para flujo core/web
```

### Desktop (con deps extra)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt
python steam_tools_desktop.py
```

Desktop agrega dependencias solo para la ventana nativa / empaquetado. El flujo funcional sigue siendo el mismo server/UI local.

> En Debian/Ubuntu y otros entornos con Python marcado como `externally-managed` (PEP 668), usa `.venv` para instalar `requirements-desktop.txt` con `constraints/desktop.txt` en vez de `pip` global del sistema.

## Uso rápido

> Nota: el flujo principal es el wizard web. El CLI sigue disponible como opción (con flags/config), y puedes usar `--interactive` si quieres prompts en terminal.

```bash
# Básico (wishlist debe ser pública)
python3 steam_deals_generator.py --vanity gaben

# También acepta URL completa o Steam ID
python3 steam_deals_generator.py --vanity "https://steamcommunity.com/id/gaben/"
python3 steam_deals_generator.py --vanity 76561198012345678

# Con API key (habilita juegos propios + más datos)
python3 steam_deals_generator.py --vanity gaben --key TU_STEAM_API_KEY

# Con ITAD (mínimo histórico + multi-tienda)
python3 steam_deals_generator.py --vanity gaben --itad-key TU_ITAD_KEY

# Comparativa externa desde caché local ITAD (no hace red live por sí sola)
python3 steam_deals_generator.py --vanity gaben \
  --itad-external-offers-cache ./itad-external-offers.json

# Refrescar esa caché ITAD bajo opt-in explícito
STEAM_TOOLS_ITAD_API_KEY="tu-key-local" \
python3 steam_deals_generator.py --vanity gaben \
  --itad-external-offers-cache ./itad-external-offers.json \
  --itad-refresh-external-offers-cache

# Filtros
python3 steam_deals_generator.py --vanity gaben --discount 60 --max-price 300 --deck-only --sort score

# Wishlist grande (ajuste manual de paralelismo en enrichment)
python3 steam_deals_generator.py --vanity gaben --max-workers 16

# Precalentar caché de precios sin abrir Web/Desktop ni generar reportes
python3 steam_deals_generator.py --vanity gaben --warm-cache

# Export Markdown con frontmatter YAML (Obsidian/Notion)
python3 steam_deals_generator.py --vanity gaben --md-frontmatter
```

`gaben` es solo un ejemplo público. Reemplázalo por tu vanity real, la URL completa de tu perfil o tu Steam ID de 17 dígitos. No copies placeholders literales como `TU_VANITY_URL`.

En la Web UI puedes usar **Conectar Steam** para enlazar tu SteamID/perfil con OpenID oficial y evitar pegar el vanity manualmente. Ese flujo no pide password, no lee cookies/tokens, no automatiza login y no entrega Steam Family, wishlist privada ni biblioteca privada; para señales Family usa el import local `--steam-access-json`/`Steam Access local (JSON)`.

Con Steam API key, la app intenta importar tus juegos propios visibles vía Steam Web API para marcar “Ya lo tienes” de forma advisory-only. Si tu biblioteca/Game details está privada, la key falla o Steam rate-limitea, el reporte continúa con warning y no asume que tienes 0 juegos. Esta API tampoco entrega Steam Family.

`--max-workers` controla el paralelismo de fetch en enrichment. Recomendación práctica: dejar `16` (default actual), bajar a `12` o `8` si notas rate limits/red inestable, y evitar valores muy altos para reducir riesgo de fallos externos. Este ajuste ya está expuesto también en **Filtros avanzados** de la UI compartida (web + desktop), y los presets sugieren valores rápidos (`rapido=12`, `completo=16`, `ahorro=8`).

### Comparativa externa desde caché ITAD local

`--itad-external-offers-cache` permite sumar precios externos desde una caché JSON ITAD local. Leer esa caché no hace red live por sí solo y la comparativa es informativa: no prueba ownership, no abre carrito/checkout y no cambia score/ranking.

La Web UI expone el flujo en **Archivos opcionales** → `Caché ITAD external_offers (JSON)`. Si necesitas poblarla o actualizarla desde ITAD, marca explícitamente **Filtros avanzados** → `Refrescar caché ITAD external_offers en vivo (opt-in, solo precios)`; ese refresh requiere `ITAD key` y ruta de caché, y puede crear/actualizar el archivo indicado.

Este flujo es solo para **precios externos** (`external_offers`). No revisa bibliotecas ni órdenes, y nunca debe interpretarse como “ya tengo el juego”. Para ownership/revisión de wishlist usa el import local `external_matches` de la sección siguiente.

Para obtener una ITAD key, crea o usa tu cuenta regular de IsThereAnyDeal y registra una app en <https://isthereanydeal.com/apps/my/>. La documentación oficial vive en <https://docs.isthereanydeal.com/>. Guarda la key solo en tu entorno local, por ejemplo `STEAM_TOOLS_ITAD_API_KEY`, o en la config local de la Web UI si aceptas guardarla en tu máquina. No la pegues en issues, commits, reportes generados ni ejemplos compartidos.

Steam Tools envía la key de refresh ITAD como header `ITAD-API-Key` para evitar filtrarla en URLs/logs. Sin una key válida no se hace live smoke ni refresh real; sigue siendo posible usar una caché local ya descargada o fixtures sin red.

### Import local para revisar la wishlist

Puedes aportar un JSON local con matches externos para que `Revisar wishlist` sugiera juegos que quizá ya tienes en otra tienda. Es **solo revisión manual**: no borra juegos, no auto-excluye, no cambia score/ranking y no llama APIs externas.

Este flujo es para **ownership/import local** (`external_matches` → `wishlist_hygiene`). Es distinto de `external_offers`: un precio externo, catálogo público o bundle público puede servir como contexto, pero no prueba propiedad.

```bash
python3 steam_deals_generator.py --vanity gaben \
  --wishlist-external-matches-json ./mis-matches-wishlist.json
```

La Web UI expone el mismo flujo en **Archivos opcionales** → `Matches externos wishlist (JSON)`.

Shapes aceptadas:

```json
{
  "external_matches": [
    {
      "store": "GOG",
      "external_name": "Hades",
      "wishlist_appid": "1145360",
      "evidence": "owned_in_user_export",
      "confidence": "high"
    }
  ]
}
```

También acepta lista directa, `{ "matches": [...] }` y exports manuales simples con `games`, `library`, `orders`, `purchases` o `bundles`. Los imports de biblioteca/órdenes pueden generar `external_owned` o `external_bundle_owned`; matches medios quedan como `external_review_needed`; precio/catálogo público o `confidence=low` no cuentan como higiene.

Plantillas locales mínimas soportadas, siempre desde archivos que tú exportas/armas localmente:

- GOG/Epic biblioteca: `{ "store": "GOG.com", "games": [{"title": "Hades", "steam_appid": "1145360"}] }` o `{ "storefront": "Epic Games Store", "library": [...] }`.
- Fanatical órdenes/bundles: `{ "store": "Fanatical", "orders": [...] }` o `{ "store": "Fanatical", "bundles": [...] }`.
- Humble compras/bundles: `{ "store": "Humble Bundle", "purchases": [...] }` o `{ "store": "Humble Store", "bundles": [...] }`.

En esas plantillas, `orders`, `purchases` y `bundles` se tratan como evidencia local de orden/bundle propio. Si un registro representa solo precio, catálogo público o bundle público, marca `evidence` como `price_only`, `public_catalog` o `public_bundle`: seguirá siendo contexto y no sugerirá ownership.

Si quieres sumar señales locales de juegos instalados o jugables sin compra nueva, usa `--play-access-json`. Es otro import **local y explícito**: no escanea carpetas de Steam, no usa SteamKit2, no llama APIs externas y no cambia score/ranking.

```bash
python3 steam_deals_generator.py --vanity gaben \
  --play-access-json ./play-access-local.json
```

Shape mínima aceptada:

```json
{
  "installed_or_playable": [
    {"appid": "30", "name": "Installed Only", "installed": true},
    {"steam_appid": "40", "title": "Playable Elsewhere", "playable": true}
  ]
}
```

También acepta lista directa, mapas `{ "appid": "Nombre" }`, y listas bajo `installed`, `playable`, `games`, `items` o `library`. Cuando un juego de tu wishlist aparece en ese import local pero no como owned/family, `play_access` puede marcarlo como `probable_family_shared` para revisión manual.

Si ya tienes una lista explícita de AppIDs propios o disponibles por Steam Family, usa `--steam-access-json`. Este import también es **local y explícito**: no hace login, no lee cookies/tokens, no llama red y no escanea carpetas. Alimenta señales `owned`/`family_shared` para `play_access` y `wishlist_hygiene` sin cambiar score/ranking.

```bash
python3 steam_deals_generator.py --vanity gaben \
  --steam-access-json ./steam-access-local.json
```

Shape mínima aceptada:

```json
{
  "source": "steam_browser_helper_export",
  "generated_at": "2026-06-03T12:00:00Z",
  "provenance": "browser_helper_manual_export",
  "owned_appids": ["10", "20"],
  "family_shared_appids": ["30"],
  "wishlist_appids": ["40"],
  "advisory_only": true,
  "ranking_impact": "none"
}
```

La app solo conserva AppIDs y metadata segura. Campos como cookies, tokens Steam, request headers Steam, raw responses, HTML, SteamID/perfil, friends, emails o nombres de familiares se omiten.

Helper opcional para armar ese JSON: `extension/steam-access-export/`. Es una extensión MV3 local/dev, de uso explícito desde el popup, que intenta extraer AppIDs visibles en la pestaña Steam activa y permite copiarlos/guardarlos como JSON sanitizado. También puede acumular capturas manuales de varias páginas en un collector local AppID-only (`owned_appids`, `family_shared_appids`, `wishlist_appids`) y exportar un JSON combinado; esto reduce el trabajo manual, pero no promete completitud si Steam no muestra todos los juegos en esas páginas. El collector usa `storage` local de la extensión solo para AppIDs/metadata mínima, no para tokens. Si el usuario empareja primero la app local con un pairing code, puede enviar el JSON combinado a Steam Tools en `http://127.0.0.1:<puerto>`: el envío usa `X-Pairing-Token`/`Authorization`, Origin/CORS de extensión sin wildcard, schema `steam_access_import_v1`, límite de tamaño/rate-limit, permiso estrecho `host_permissions: ["http://127.0.0.1/*"]` y respuestas con summary/counts only. No se ejecuta automáticamente, no usa endpoint de comandos generales, no pide password, no solicita permisos de cookies/webRequest/`<all_urls>` y no exporta cookies/tokens Steam, request headers Steam, raw responses, HTML, SteamID/perfil, friends, emails ni nombres de familiares. Copy/Save sigue disponible como fallback y el import principal sigue siendo `--steam-access-json` o el campo Web `Steam Access local (JSON)`.

Contrato completo y ejemplos: `docs/runbooks/wishlist-hygiene-multistore-contract.md`.

### Preferencias manuales del jugador (JSON local opt-in)

Puedes aportar un JSON local de preferencias conductuales para que el export JSON incluya `player_behavior_profile` y, cuando haya matches con las señales del juego, `player_behavior_fit`. Es **advisory-only**: no cambia score, ranking, Top Picks, filtros, cache ni fetching.

```bash
python3 steam_deals_generator.py --vanity gaben \
  --player-preferences-json ./mis-preferencias-jugador.json
```

Shape mínima aceptada:

```json
{
  "manual_preferences": {
    "preferred_families": ["coop_teamwork"],
    "preferred_terms": ["online co-op", "loot"],
    "favorite_games": [{"tags": ["Horror", "Online Co-op"]}]
  }
}
```

También acepta un objeto directo sin wrapper `manual_preferences`. Campos soportados: `preferred_families`, `preferred_loops`, `preferred_descriptors`, `preferred_terms`, `tags`, `genres`, `favorite_games`, `comfort_games` y `liked_games`. En listas de juegos, las señales útiles son `tags`, `steam_tags`, `genres`, `steam_genres`, `categories` y `steam_categories`; nombres, rutas, AppIDs, playtime y campos debug se ignoran/sanitizan.

Plantilla editable: `docs/player-preferences.example.json`. Cópiala fuera del repo o renómbrala antes de poner preferencias personales. JSON inválido o shape no soportado falla localmente con un error accionable y no genera un reporte parcial.

### Warm cache headless

Si quieres dejar una corrida de preparación en segundo plano sin abrir la Web UI o Desktop, usa:

```bash
python3 steam_deals_generator.py --vanity gaben --warm-cache
```

Para intentar completar la cola resumible en varias pasadas conservando la misma caché, usa el modo opcional:

```bash
python3 steam_deals_generator.py --vanity gaben --warm-cache-full --warm-cache-full-max-passes 5
```

> Usa tu vanity real, la URL completa de tu perfil o tu Steam ID. Si copias el ejemplo, cambia `gaben` por tu dato real antes de ejecutar.

Este modo:

- resuelve tu `steam_id`
- baja la wishlist
- actualiza `prices_cache.json`
- guarda un log legible de la corrida headless
- sale sin generar `.md`, `.html`, `.json` ni `.csv`

`--warm-cache` hace una pasada. `--warm-cache-full` repite pasadas con la misma caché hasta que no queden pendientes importantes o hasta `--warm-cache-full-max-passes`; no borra caché, no fuerza `--no-cache` y no genera reportes automáticamente. Cuando termine, genera el reporte como una corrida normal separada para usar la caché ya actualizada.

En runs desde source, el caché queda en `./.cache/steam_deals`. En desktop empaquetado/frozen, el caché persistente vive en `~/.cache/steam_deals` (o `XDG_CACHE_HOME/steam_deals` si está definido).

Esto importa para desktop: el wrapper empaquetado ya no depende de rutas temporales `_MEI` para el caché, así que una corrida headless con `--warm-cache` puede precalentar datos que luego reutiliza la app nativa.

Los logs de `--warm-cache` se guardan automáticamente en una carpeta `logs/`:

- desde source: `./logs/warm-cache-YYYY-MM-DD_HH-MM-SS.log`
- si usas `STEAM_DEALS_CACHE_DIR` o un binario frozen: `<cache_dir>/logs/warm-cache-...log`

Si quieres forzar una ruta específica para logs, puedes usar:

```bash
STEAM_DEALS_LOG_DIR="$HOME/logs/steam-deals" python3 steam_deals_generator.py --vanity gaben --warm-cache
```

Si quieres forzar una ruta específica para compartir caché entre distintos modos, puedes usar:

```bash
STEAM_DEALS_CACHE_DIR="$HOME/.cache/steam_deals" python3 steam_deals_generator.py --vanity gaben --warm-cache
```

### Verificación larga recomendada para wishlists grandes

Si quieres validar rendimiento real y preparar un smoke largo Linux/desktop, usa este orden:

1. **Precalentar cache**

```bash
source .venv/bin/activate
STEAM_DEALS_CACHE_DIR="$HOME/.cache/steam_deals" python3 steam_deals_generator.py --vanity gaben --warm-cache
```

2. **Validar cobertura automatizada del frente de performance**

```bash
.venv/bin/python -m pytest tests/test_generator_logic.py -k "WarmCacheTests or PriceCacheTests"
```

3. **Correr un run largo real**
   - desde `python3 steam_deals_web.py` si quieres validar generator/web con una wishlist real grande
   - desde `./dist/SteamToolsDesktop` si quieres además cerrar evidencia desktop Linux

4. **Qué observar en el log/progreso**
   - `Refresh candidates: ...`
   - si hubo `stale` vs `nuevos`
   - si aparecen `fallos recientes en cooldown` (fallos/no-data recientes se reintentan después de una ventana corta en vez de forzar fallback lento inmediato)
   - si hubo `Batches degradados por HTTP 400`
   - si hubo `Fallback individual aplicado ...` y cuántos appids quedaron `resueltos` vs `sin oferta/datos`

5. **Evidencia mínima a guardar**
   - comando de warm-cache usado
   - ruta del log generado en `<cache>/logs/`
   - wishlist/deals del run largo real
   - artifacts generados (`.md`, `.html`, `share.html`, `.json`; y `.csv` cuando el smoke final sea desktop)

Para capturar la evidencia de forma comparable entre corridas, usa `docs/runbooks/performance-warm-cache.md` (índice general: `docs/runbooks/README.md`). Para resumir un log ya generado sin leerlo a mano:

```bash
python3 steam_deals_warm_cache_summary.py "$HOME/.cache/steam_deals/logs/warm-cache-YYYY-MM-DD_HH-MM-SS.log"
```

> Nota: una corrida larga desde Web UI/source sirve como evidencia funcional fuerte del generator y del Track Performance, pero el cierre de Linux desktop sigue requiriendo repetir la corrida dentro del binario y con `.csv` activado.

## Web UI

```bash
python3 steam_deals_web.py
# Se abre http://127.0.0.1:8080 en tu navegador
```

Interfaz visual para configurar y ejecutar el script sin usar la terminal.

> Para el módulo PAYDAY 2 usa `python3 payday2_web.py` (puerto 8081).

## Export JSON y API local

Cada corrida de Steam Deals genera artefactos `.md`, `.html`, `.json` y, si lo activas, `.csv`.

El JSON está pensado para scripting y automatización local. Incluye, entre otros:

- `meta` / `inputs` / `summary`
- `top_picks` con `recommendation` y `score_reasons`
- `deals`, `watchlist_alerts`, `wishlist_hygiene`, `budget_result`, `compare_data`
- señales advisory opcionales como `behavioral_signals`, `behavioral_explanations`, `player_behavior_profile`, `player_behavior_fit` y `decision_support` cuando hay datos locales suficientes

La Web UI también expone un endpoint local útil:

### `GET /api/latest-report`

Devuelve el último `Steam Deals*.json` generado en el directorio de salida actual.

```bash
curl http://127.0.0.1:8080/api/latest-report
```

Casos útiles:

- alimentar scripts locales
- inspeccionar el último run sin buscar archivos manualmente
- integrar Steam Deals con otras herramientas personales

Si todavía no existe un reporte JSON, responde `404`.

### Historial local

El dashboard histórico también usa estos endpoints locales:

#### `GET /api/history/runs?limit=50`

Devuelve las ejecuciones recientes disponibles para el comparador histórico.

- `limit` se normaliza a un rango seguro de `1..100`
- cada item resume `id`, `timestamp`, `date`, `sale_name`, `min_discount`, `deal_count`, `steam_id` y `vanity`

#### `GET /api/history/compare?left=...&right=...`

Compara dos runs guardados y devuelve un payload enriquecido para la UI histórica.

Parámetros opcionales:

- `include_same=1` para incluir filas sin cambio
- `status=all|changed|new|removed|same`
- `sort_delta=default|delta_desc|delta_asc|abs_desc`

Respuesta principal:

- `left` / `right`: resumen de cada run seleccionado
- `summary`: conteos de `changed`, `new`, `removed` y `same`
- `rows`: filas comparadas entre ambos runs
- `analytics`: `state_counts`, `top_price_drops`, `top_price_rises`, `history_runs` y `game_history` por appid

### Markdown con frontmatter (Obsidian/Notion)

Si quieres importar tu reporte Markdown en herramientas como Obsidian/Notion con metadatos estructurados, usa:

```bash
python3 steam_deals_generator.py --vanity gaben --md-frontmatter
```

Esto agrega un bloque YAML al inicio del `.md` con campos base como `title`, `profile`, `sale_name`, `generated_date`, `wishlist_count`, `deals_count` y `top_picks_count`.

#### Perfiles de frontmatter recomendados

Perfil base actual (compatible con ambos):

- `title`
- `profile`
- `sale_name`
- `generated_date`
- `min_discount`
- `wishlist_count`
- `deals_count`
- `top_picks_count`
- `tags`

Sugerencia práctica:

- **Obsidian**: usar `tags` + `generated_date` para vistas por fecha y filtros.
- **Notion**: importar como Markdown y mapear propiedades clave desde frontmatter (`title`, `sale_name`, `generated_date`, `deals_count`, `top_picks_count`).

Checklist manual de import: `docs/runbooks/features-validation.md` (índice general: `docs/runbooks/README.md`).

### Ejemplos mini de automatización

**Ver solo el resumen del último run**

```bash
curl -s http://127.0.0.1:8080/api/latest-report | jq '.summary'
```

**Sacar solo los nombres de los top picks**

```bash
curl -s http://127.0.0.1:8080/api/latest-report | jq -r '.top_picks[].name'
```

**Leer el endpoint desde Python (stdlib)**

```python
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8080/api/latest-report") as response:
    report = json.load(response)

print("Deals:", report["summary"]["deals_count"])
print("Top picks:", report["summary"]["top_picks_count"])
```

**Tip:** si usas otro puerto para la Web UI, reemplaza `8080` por el puerto real.

## Desktop (pywebview)

El desktop reutiliza la misma Web UI con `pywebview`; no hay frontend separado. Para uso diario, la ruta mínima es:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt
python steam_tools_desktop.py
```

Build unificado:

```bash
python build_desktop.py
```

El build usa PyInstaller desde `build_desktop.py` como fuente de verdad, instala `requirements-desktop.txt` con `constraints/desktop.txt` salvo que uses `--skip-install`, y deja artefactos locales en `dist/`. No versionar `dist/`, `build/` ni `*.spec`.

### Generar binario/app por plataforma

| Plataforma | Comandos base | Artefacto esperado | Ejecutar |
|---|---|---|---|
| Linux | `python3 -m venv .venv`<br>`source .venv/bin/activate`<br>`python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt`<br>`python build_desktop.py` | `dist/SteamToolsDesktop` | `./dist/SteamToolsDesktop` |
| Windows | `py -3 -m venv .venv`<br>`.\.venv\Scripts\Activate.ps1`<br>`python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt`<br>`python .\build_desktop.py` | `dist\SteamToolsDesktop.exe` | `.\dist\SteamToolsDesktop.exe` |
| macOS | `python3 -m venv .venv`<br>`source .venv/bin/activate`<br>`python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt`<br>`python build_desktop.py` | `dist/SteamToolsDesktop.app` | `open dist/SteamToolsDesktop.app` |

Atajos/wrappers disponibles:

- Windows: `powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1`
- Linux/macOS: `./build_desktop.sh`

Opciones útiles:

- `python build_desktop.py --skip-install`: rebuild rápido si ya instalaste deps.
- `python build_desktop.py --onedir`: genera modo directorio en vez de binario single-file.
- Fallback forzado: Linux/macOS `STEAM_TOOLS_FORCE_WEB_FALLBACK=1 ./dist/SteamToolsDesktop` (en macOS usar `dist/SteamToolsDesktop.app/Contents/MacOS/SteamToolsDesktop`); Windows `$env:STEAM_TOOLS_FORCE_WEB_FALLBACK = "1"` y luego `.\dist\SteamToolsDesktop.exe`.

Si `pywebview` o el backend nativo no arrancan, el launcher abre automáticamente la misma Web UI en el navegador por defecto y muestra un aviso visible de fallback.

### Doctor desktop y autofix seguro

```bash
python3 -m venv .venv
source .venv/bin/activate
python steam_tools_desktop.py --doctor
python steam_tools_desktop.py --doctor-fix
```

El doctor reporta `OK / WARN / FAIL` para readiness desktop:

- `.venv` / PEP 668 en Linux
- disponibilidad de `pywebview` y backend Qt esperado en Linux
- disponibilidad de `PyInstaller`
- checks específicos por OS: macOS (PyObjC/tooling local), Windows (WebView2/sesión) y Linux (Wayland/X11 + tooling host cuando aplica)
- presencia del artefacto desktop y warnings conocidos del último build

También está disponible desde la Web UI con los botones **Doctor desktop** y **Autofix desktop**. El autofix es opt-in y local: puede crear `.venv`, instalar `requirements-desktop.txt` con `constraints/desktop.txt` dentro del entorno y lanzar build local, pero no instala paquetes del sistema ni modifica configuración persistente.

La consola compartida (web + desktop) permite **Copiar log** y **Descargar log (.txt)** para conservar errores largos durante validación manual.

### Dependencias nativas por plataforma

`requirements-desktop.txt` declara la intención de dependencias Python del desktop y `constraints/desktop.txt` fija la resolución validada para builds reproducibles. Algunos backends nativos pueden requerir runtime o librerías del sistema:

- **Windows**: Microsoft Edge WebView2 Runtime.
- **Linux**: backend Qt/GTK/WebKit y librerías nativas según distro/sesión gráfica; usar `.venv` en Debian/Ubuntu con PEP 668.
- **macOS**: Cocoa/WKWebView vía PyObjC; para distribución a terceros puede requerir firma/notarización.

Referencias oficiales:
- https://pywebview.flowrl.com/guide/installation
- https://pywebview.flowrl.com/guide/web_engine
- https://pywebview.flowrl.com/guide/freezing
- https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing

### Validación desktop/cross-platform

README solo conserva la orientación rápida. Los checklists completos, comandos por OS, plantillas de evidencia y problemas comunes viven en `docs/runbooks/README.md`:

- Linux desktop: `docs/runbooks/desktop-linux.md`
- macOS desktop: `docs/runbooks/desktop-macos.md`
- Windows desktop: `docs/runbooks/desktop-windows.md`
- Constraints desktop: `docs/runbooks/desktop-constraints.md`
- Performance/warm-cache: `docs/runbooks/performance-warm-cache.md`
- Features específicas: `docs/runbooks/features-validation.md`

Regla de documentación:

- Estado vivo, bloqueos y siguiente paso: `PENDIENTES.md`.
- Evidencia detallada, comandos ejecutados y workarounds: `BITACORA.md`.
- Validación reproducible paso a paso: `docs/runbooks/README.md`.

El cierre formal P2 requiere evidencia manual Linux + macOS según `PENDIENTES.md`; Windows sirve como baseline de apoyo, no como sustituto.

## Mapa de módulos y entrypoints

### Superficies principales

| Superficie | Entry point | Notas |
|---|---|---|
| Steam Deals CLI | `steam_deals_generator.py` | Engine principal: análisis, scoring, exports y flags avanzados. |
| Steam Deals Web | `steam_deals_web.py` | UX principal en `http://127.0.0.1:8080`; coordina runs largos por SSE. |
| PAYDAY 2 CLI | `payday2_dlc_tracker.py` | Engine standalone para plan de compra de DLCs. |
| PAYDAY 2 Web | `payday2_web.py` | Dashboard en `http://127.0.0.1:8081`. |
| Desktop | `steam_tools_desktop.py` | Wrapper pywebview que reutiliza Steam Deals Web y cae a navegador si falla backend nativo. |
| Build desktop | `build_desktop.py` | Build unificado; wrappers: `build_desktop.ps1`, `build_desktop.sh`. |

### Organización interna resumida

- Dominio Steam Deals: módulos `steam_deals_*` para config, precios, enrichment, history, ITAD, recomendaciones, presentación, runtime reporting, output y adaptadores Steam.
- Web compartida: `shared_web_infra.py` + assets en `web/steam_deals/` y `web/payday2/`.
- Guías específicas: `steam_deals_guia.md`, `payday2_guia.md` y runbooks en `docs/runbooks/README.md`.

## Outputs por módulo

| Módulo | Output principal | Formatos |
|--------|------------------|----------|
| Steam Deals | Reporte de deals de wishlist | `.md`, `.html` interactivo, Share HTML, `.json`, `.csv` |
| PAYDAY 2 | `PAYDAY2_Plan_de_Compra` | `.md`, `.html`, `.csv` opcional |
| Desktop Build | Artefactos de distribución | `dist/` (binario/app según OS) |

Notas rápidas:
- Los datos intermedios y caché viven en `.cache/steam_deals/`.
- En desktop, los artefactos finales dependen de la plataforma (Windows/macOS/Linux).
- Para validación de outputs y evidencia reproducible, usar `docs/runbooks/README.md`.

## Watchlist

```bash
# Agregar un juego con precio objetivo
python3 steam_deals_generator.py --watchlist add 730 200
# → Counter-Strike 2 — objetivo $200 MXN

# Ver tu watchlist
python3 steam_deals_generator.py --watchlist list

# Quitar un juego
python3 steam_deals_generator.py --watchlist remove 730
```

## Tu Presupuesto Ideal

```bash
# ¿Qué compro con $500?
python3 steam_deals_generator.py --vanity gaben --budget 500
```

Muestra variantes de compra (`Lista chica`, `Lista media`, `Lista grande`) y permite reroll/reemplazos manteniendo el presupuesto. Checklist de validación UX/output: `docs/runbooks/features-validation.md` (índice general: `docs/runbooks/README.md`).

## Validación end-to-end de share

El flujo share debe funcionar desde Web UI, HTML interactivo y Share HTML, manteniendo payload compatible con desktop. Checklist E2E completo: `docs/runbooks/features-validation.md` (índice general: `docs/runbooks/README.md`).

## Comparar Wishlists

```bash
# Ver overlap y gift ideas con un amigo
python3 steam_deals_generator.py --vanity gaben --compare VANITY_AMIGO

# Comparar varios amigos y exponer regalos grupales en JSON
python3 steam_deals_generator.py --vanity gaben --compare "AMIGO_1,AMIGO_2"
```

En Web/Desktop, el campo **Comparar con** acepta un perfil por línea o separados por coma. Con varios perfiles, el JSON agrega `compare_profiles`, `gift_ideas_by_friend` y `shared_gift_ideas` sin cambiar el ranking ni abrir carrito/checkout.

## Notificaciones

```bash
# Telegram
python3 steam_deals_generator.py --vanity gaben \
  --telegram-token BOT_TOKEN --telegram-chat CHAT_ID

# Discord
python3 steam_deals_generator.py --vanity gaben \
  --discord-webhook WEBHOOK_URL
```

Las notificaciones Telegram/Discord actuales usan un resumen compacto de cambios notables (deals nuevos, bajadas, watchlist y top picks). **Alertas inteligentes v2** se calcula para el resumen final/JSON y no se envía como una notificación por juego por defecto; antes de conectarlas a canales externos conviene revisar una corrida natural con `price_changes` y definir un digest con límites anti-spam/preview.

## Scheduler

```bash
# Ejecutar cada 6 horas con notificaciones
python3 steam_deals_generator.py --vanity gaben \
  --telegram-token BOT_TOKEN --telegram-chat CHAT_ID \
  --schedule 6
```

## Flags comunes (Steam Deals CLI)

Para la lista completa y vigente, usa:

```bash
python3 steam_deals_generator.py --help
```

Flags más usados:

| Flag | Uso típico |
|------|------------|
| `--vanity` | Perfil Steam: vanity, Steam ID o URL completa |
| `--key` / `--itad-key` | API keys para más datos y mínimo histórico |
| `--itad-external-offers-cache` | Caché JSON local ITAD para `external_offers`, sin red live por defecto |
| `--itad-refresh-external-offers-cache` | Opt-in live para poblar esa caché ITAD; requiere `--itad-key` y ruta de caché |
| `--discount` / `--max-price` | Filtros principales de precio/oferta |
| `--deck-only` / `--deck-verified` | Filtros Steam Deck |
| `--top` / `--sort` | Cantidad y orden de picks destacados |
| `--budget` | Activar `Tu Presupuesto Ideal` |
| `--compare` | Comparar con otro perfil |
| `--watchlist` | `add/remove/list` de precio objetivo |
| `--csv` / `--md-frontmatter` | Exports extra para Sheets, Obsidian o Notion |
| `--wishlist-external-matches-json` | Import local advisory-only para sugerencias `Revisar wishlist` |
| `--play-access-json` / `--steam-access-json` | Imports locales para acceso jugable/Steam Family sin login/red |
| `--max-workers` | Paralelismo de enrichment; default actual: 16 |
| `--warm-cache` | Precalentar caché de precios sin generar reportes |
| `--warm-cache-full` | Repetir warm-cache en pasadas resumibles con la misma caché |
| `--warm-cache-full-max-passes` | Cap seguro de pasadas para `--warm-cache-full` |
| `--interactive` | Habilitar prompts de configuración en terminal |
| `--no-cache` | Forzar re-fetch cuando haga falta |

También existen flags avanzados para HLTB, familia, notificaciones, scheduler y alertas inteligentes; consulta `--help` antes de automatizar. Si combinas scheduler/notificaciones con Alertas inteligentes v2, primero valida el volumen en el resumen/JSON y evita enviar alertas por-juego sin límites explícitos.

## PAYDAY 2 DLC Tracker

Tracker standalone para DLCs de PAYDAY 2: faltantes, precios, ofertas, historial y recomendaciones de compra. Las sugerencias separan `Comprar ahora`, `Revisar antes de comprar` y `Esperar mejor oferta` con razones visibles, siempre advisory-only. Guía completa: `payday2_guia.md`.

> La API de Steam no detecta DLCs poseídos automáticamente. Márcalos manualmente con checkboxes en el dashboard o con `--mark-owned` / `--mark-unowned` en CLI; las recomendaciones no modifican ese estado.

### Dashboard Web

```bash
python3 payday2_web.py
# Se abre http://127.0.0.1:8081 en tu navegador
```

### CLI

```bash
python3 payday2_dlc_tracker.py --vanity gaben
python3 payday2_dlc_tracker.py --budget 500
python3 payday2_dlc_tracker.py --min-deal 75          # umbral para comprar/revisar/esperar
python3 payday2_dlc_tracker.py --itad-key TU_KEY      # mínimos históricos
python3 payday2_dlc_tracker.py --mark-owned 259381    # marcar DLC como comprado
python3 payday2_dlc_tracker.py --no-cache             # forzar catálogo/precios live
python3 payday2_dlc_tracker.py --diagnose-dlc 123456  # diagnosticar DLC esperado faltante
```

Genera `PAYDAY2_Plan_de_Compra.md` y `.html` con el reporte completo; con `--csv` también genera `.csv`.

Si un DLC nuevo no aparece, primero usa **Forzar catálogo** en `payday2_web.py` o `--no-cache`; si sigue ausente, usa `--diagnose-dlc APPID_O_NOMBRE`. Steam puede no exponer packages/bundles como DLCs del app base `218620`; detalles y estados de diagnóstico en `payday2_guia.md`.

## Datos locales, caché y config

- Config principal: `~/.config/steam_deals.json`.
- Watchlist: `~/.config/steam_deals_watchlist.json`.
- Caché source: `.cache/steam_deals/`.
- Caché desktop/frozen: ruta persistente de usuario (`~/.cache/steam_deals` o equivalente XDG).
- PAYDAY 2 usa subcarpeta propia bajo `.cache/steam_deals/payday2/`: catálogo/nombres/bundles hasta 7 días, precios 24h, ownership manual sin TTL e historial hasta 365 días.

Usa `--no-cache` solo cuando quieras forzar re-fetch. Para wishlists grandes, prefiere `--warm-cache` o `--warm-cache-full`; el flujo de medición y evidencia vive en `docs/runbooks/performance-warm-cache.md`.
