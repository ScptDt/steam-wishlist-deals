# Steam Wishlist Deals Generator

Herramienta local para analizar tu wishlist de Steam, encontrar ofertas útiles y generar reportes Markdown, HTML, JSON y CSV. La experiencia principal es la **Web UI local**; también hay CLI para automatización y wrapper desktop con `pywebview`.

## Quick start

```bash
# Web UI principal: http://127.0.0.1:8080
python3 steam_deals_web.py

# CLI básico: wishlist pública por vanity, URL o Steam ID
python3 steam_deals_generator.py --vanity gaben

# Desktop: misma Web UI dentro de ventana nativa
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt
python steam_tools_desktop.py
```

`gaben` es solo un ejemplo público. Reemplázalo por tu vanity, URL completa de perfil o Steam ID de 17 dígitos.

## Qué hace

- Detecta deals de tu wishlist con filtros por descuento, precio, Deck/ProtonDB, reviews y más.
- Genera Top Picks, presupuesto ideal, watchlist de precios, comparativa entre runs y comparación con amigos.
- Soporta imports locales advisory-only: wishlist externa, acceso jugable/Steam Family, preferencias del jugador y cachés ITAD/GG.deals.
- Produce reportes `.md`, HTML interactivo, Share HTML, `.json` y `.csv`.
- Incluye warm-cache para wishlists grandes sin forzar `--no-cache`.
- Tiene módulo standalone para PAYDAY 2 DLC Tracker.

## Superficies

| Superficie | Entry point | Uso principal |
|---|---|---|
| Steam Deals Web | `steam_deals_web.py` | Flujo guiado local en navegador |
| Steam Deals CLI | `steam_deals_generator.py` | Automatización, flags avanzados, warm-cache |
| Desktop | `steam_tools_desktop.py` | La misma Web UI en ventana nativa |
| PAYDAY 2 Web | `payday2_web.py` | Dashboard local de DLCs |
| PAYDAY 2 CLI | `payday2_dlc_tracker.py` | Plan de compra por terminal |

La app es local-first: el server escucha en loopback, los reportes/cache/config viven en tu máquina y los artefactos generados no se versionan.

## Comandos frecuentes

```bash
# Filtros principales
python3 steam_deals_generator.py --vanity gaben --discount 60 --max-price 300 --deck-only

# Presupuesto ideal
python3 steam_deals_generator.py --vanity gaben --budget 500

# Comparar wishlists
python3 steam_deals_generator.py --vanity gaben --compare otro_usuario

# Precalentar caché de precios sin generar reportes
python3 steam_deals_generator.py --vanity gaben --warm-cache

# Completar caché en pasadas resumibles con la misma caché
python3 steam_deals_generator.py --vanity gaben --warm-cache-full --warm-cache-full-max-passes 5

# Ver todos los flags vigentes
python3 steam_deals_generator.py --help
```

Para wishlists grandes, conserva la misma caché y usa `--warm-cache` / `--warm-cache-full`; no uses `--no-cache` como reacción automática. El procedimiento completo está en `docs/runbooks/performance-warm-cache.md`.

## Free Weekend opt-in

El reporte puede incluir `Free Weekend ahora` como señal advisory separada de descuentos, score/ranking, Top Picks y caché de precios. Por defecto no hace fetch live; solo reutiliza el caché dedicado si existe y sigue vigente.

```bash
# Consultar Store JSON con TTL/cache dedicado free_weekend_candidates.json
python3 steam_deals_generator.py --vanity gaben --free-weekend-live

# Usar registros locales ya corroborados, sin red live
python3 steam_deals_generator.py --vanity gaben --free-weekend-records-json data/free_weekend_records.json

# Señal experimental desde el feed Atom de LootScraper, opt-in y cacheada aparte de precios
python3 steam_deals_generator.py --vanity gaben --free-weekend-lootscraper-live
```

`--free-weekend-records-json` tiene prioridad sobre fuentes live. LootScraper es una señal candidata de terceros: revisa confianza/vigencia antes de asumir disponibilidad. Detalles de fuentes, precedencia y validación: `docs/runbooks/free-weekend-source-strategy.md`.

## Desktop y builds

```bash
python build_desktop.py
```

Artefactos locales esperados: `dist/SteamToolsDesktop` en Linux, `dist\SteamToolsDesktop.exe` en Windows y `dist/SteamToolsDesktop.app` en macOS. No versionar `dist/`, `build/` ni `*.spec`.

Checklists completos: `docs/runbooks/desktop-linux.md`, `docs/runbooks/desktop-windows.md`, `docs/runbooks/desktop-macos.md` y `docs/runbooks/desktop-constraints.md`.

## PAYDAY 2 DLC Tracker

Web: `python3 payday2_web.py` (`http://127.0.0.1:8081`). CLI: `python3 payday2_dlc_tracker.py --vanity gaben` o `--budget 500`. Guía completa: `payday2_guia.md`.

## Documentación

La documentación canónica vive en el repo para versionarse junto con el código. La Wiki de GitHub puede usarse como versión navegable/pulida para tutoriales largos, FAQ o capturas, enlazando de vuelta a estos archivos.

- Índice de runbooks: `docs/runbooks/README.md`
- Guías principales: `steam_deals_guia.md`, `payday2_guia.md`
- Performance/warm-cache: `docs/runbooks/performance-warm-cache.md`
- Features, imports locales y multi-tienda: `docs/runbooks/features-validation.md`, `docs/runbooks/wishlist-hygiene-multistore-contract.md`, `docs/runbooks/multistore-price-comparison.md`
- Behavioral / Decision Advisor: `docs/runbooks/behavioral-signals-contract.md`, `docs/runbooks/decision-advisor-v0.md`
- Reglas del repo: `docs/project-rules.md`

## Datos locales

- Config/watchlist: `~/.config/steam_deals.json`, `~/.config/steam_deals_watchlist.json`
- Caché: `.cache/steam_deals/` desde source; ruta persistente de usuario en desktop/frozen (`~/.cache/steam_deals` o equivalente XDG)
- Outputs generados: `output/` o carpeta elegida en la UI/CLI

No commitear caches, logs, builds ni reportes generados (`Steam Deals*.md/.html/.json/.csv`, `PAYDAY2_Plan_de_Compra.*`).

## Desarrollo

- `PENDIENTES.md`: fuente única de estado, prioridades y bloqueos.
- `BITACORA.md`: evidencia histórica, validaciones y decisiones operativas.
- `docs/runbooks/README.md`: checklists reproducibles y validación por área.
- `docs/project-rules.md`: reglas de arquitectura, seguridad local e higiene del repo.
