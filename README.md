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
- **Tags de SteamSpy** — Categorización por tags + estimación de jugadores
- **ITAD (IsThereAnyDeal)** — Mínimo histórico, precios multi-tienda, bundles activos
- **HLTB (HowLongToBeat)** — Cruce con tu backlog exportado de HLTB
- **Historial de precios** — Tendencias locales con sparklines SVG en el HTML
- **Top Picks** — Ranking por value score (reviews, descuento, prioridad, $/hora, Deck, Metacritic, edad)

### Herramientas
- **Watchlist Personal** — Alertas cuando un juego baja de tu precio objetivo
- **Budget Mode** — "Tengo $500, ¿qué compro?" — optimizador greedy por eficiencia
- **Comparar Wishlists** — Overlap con amigos + gift ideas
- **Notificaciones** — Telegram y Discord webhook con resumen de cambios
- **Scheduler** — Ejecución automática cada N horas
- **Comparación entre runs** — Detecta deals nuevos, terminados, y bajadas de precio

### Salida
- **Markdown** — Reporte completo con tablas, secciones, y badges
- **HTML interactivo** — Dashboard con gráficas, filtros en vivo, thumbnails con hover zoom, sparklines de precio
- **HTML compartible** — Versión ligera para enviar a amigos
- **CSV** — Exportación para Excel/Google Sheets (+ botón "Copiar para Sheets" en el HTML)

## Requisitos

- Python 3.10+
- Sin dependencias externas (solo stdlib)

## Uso rápido

```bash
# Básico (wishlist debe ser pública)
python3 steam_deals_generator.py --vanity TU_VANITY_URL

# Con API key (habilita juegos propios + más datos)
python3 steam_deals_generator.py --vanity TU_VANITY_URL --key TU_STEAM_API_KEY

# Con ITAD (mínimo histórico + multi-tienda)
python3 steam_deals_generator.py --vanity TU_VANITY_URL --itad-key TU_ITAD_KEY

# Filtros
python3 steam_deals_generator.py --vanity TU_VANITY_URL --discount 60 --max-price 300 --deck-only --sort score
```

## Web UI

```bash
python3 steam_deals_web.py
# Se abre http://127.0.0.1:8080 en tu navegador
```

Interfaz visual para configurar y ejecutar el script sin usar la terminal.

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

## Budget Mode

```bash
# ¿Qué compro con $500?
python3 steam_deals_generator.py --vanity TU_VANITY_URL --budget 500
```

## Comparar Wishlists

```bash
# Ver overlap y gift ideas con un amigo
python3 steam_deals_generator.py --vanity TU_VANITY_URL --compare VANITY_AMIGO
```

## Notificaciones

```bash
# Telegram
python3 steam_deals_generator.py --vanity TU_VANITY_URL \
  --telegram-token BOT_TOKEN --telegram-chat CHAT_ID

# Discord
python3 steam_deals_generator.py --vanity TU_VANITY_URL \
  --discord-webhook WEBHOOK_URL
```

## Scheduler

```bash
# Ejecutar cada 6 horas con notificaciones
python3 steam_deals_generator.py --vanity TU_VANITY_URL \
  --telegram-token BOT_TOKEN --telegram-chat CHAT_ID \
  --schedule 6
```

## Todos los flags

| Flag | Descripción |
|------|-------------|
| `--vanity` | Vanity URL, Steam ID, o link de perfil |
| `--key` | Steam API Key (opcional) |
| `--itad-key` | IsThereAnyDeal API Key (opcional) |
| `--hltb` | Ruta al CSV exportado de HLTB |
| `--discount` | Descuento mínimo % (default: 50) |
| `--genre` | Filtrar por géneros |
| `--output` | Directorio de salida |
| `--no-cache` | Ignorar caché existente |
| `--max-price` | Precio máximo en MXN |
| `--deck-only` | Solo Deck Verified o Playable |
| `--deck-verified` | Solo Deck Verified |
| `--min-reviews` | Mínimo % de reviews positivas |
| `--min-review-count` | Mínimo total de reviews |
| `--max-hours` | Máximo horas HLTB |
| `--top` | Top N picks (default: 10) |
| `--sort` | Ordenar por: discount, price, reviews, priority, score |
| `--new-only` | Solo deals nuevos vs run anterior |
| `--csv` | Generar CSV |
| `--watchlist` | add/remove/list precio objetivo |
| `--budget` | Presupuesto en MXN |
| `--compare` | Comparar con otro perfil |
| `--telegram-token` | Token del bot de Telegram |
| `--telegram-chat` | Chat ID de Telegram |
| `--discord-webhook` | URL del webhook de Discord |
| `--schedule` | Ejecutar cada N horas |
| `--family-json` | JSON de biblioteca familiar |

## PAYDAY 2 DLC Tracker

Incluye un script separado para trackear DLCs de PAYDAY 2:

```bash
python3 payday2_dlc_tracker.py --vanity TU_VANITY_URL
```

## Caché

Los datos se cachean en `~/.cache/steam_deals/` para evitar requests innecesarios:

| Dato | TTL |
|------|-----|
| Precios | 24 horas |
| Reviews, Deck, ProtonDB, Anti-Cheat | 7 días |
| Tags (SteamSpy), Achievements | 30 días |

Usa `--no-cache` para forzar re-fetch.

## Config

La configuración se guarda en `~/.config/steam_deals.json` tras el primer run interactivo. La watchlist se guarda en `~/.config/steam_deals_watchlist.json`.
