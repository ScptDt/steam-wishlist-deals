# Guía: Cómo funciona el generador de Steam Wishlist Deals

## Panorama general

El programa hace 6 pasos en orden:

```
Steam API → Resolver vanity URL → Steam ID
Steam API → Lista de la wishlist (appids)
Steam API → Biblioteca propia (juegos comprados)
Steam API → Detectar oferta activa (marketing messages)
Steam Store API → Precios actuales (en batches de 20)
Python → Cruce con HLTB + generación del MD
```

---

## 1. Fuentes de datos

### Steam API (requiere API Key)

Base URL: `https://api.steampowered.com/`

Necesitas:
- **API Key**: de https://steamcommunity.com/dev/apikey
- **Steam ID** (64-bit numérico): si tienes vanity URL (ej. `gaben`), primero lo resuelves

**Endpoints usados:**

| Endpoint | Qué devuelve | Requiere API Key |
|----------|-------------|-----------------|
| `ISteamUser/ResolveVanityURL/v1/?vanityurl=...` | Traduce vanity URL a Steam ID | Sí |
| `IWishlistService/GetWishlist/v1/?steamid=...` | Lista de appids de la wishlist | Sí |
| `IPlayerService/GetOwnedGames/v1/?include_appinfo=1` | Juegos comprados con nombres | Sí |
| `IMarketingMessagesService/GetActiveMarketingMessages/v1/` | Ofertas/eventos activos de Steam | No |

### Vanity URL vs API Key

- **Vanity URL** (`gaben`): Es pública, solo identifica tu perfil. Con ella se resuelve tu Steam ID numérico.
- **API Key**: Da acceso a datos privados (wishlist, biblioteca, juegos jugados). Sin ella no funciona el script.

### Steam Store API (precios, en batches)

Base URL: `https://store.steampowered.com/api/`

```
GET /appdetails?appids=730,440,570,...&cc=mx&filters=price_overview,basic,genres
```

- `cc=mx` → precios en MXN
- `filters=price_overview,basic,genres` → nombre, tipo (game/dlc), precio y géneros
- **Batching**: acepta múltiples appids separados por coma (hasta ~20 por request)
- Con ~2,900 juegos → ~146 batches en vez de 2,900 requests individuales

**Rate limiting**:
- Delay base: 1.5s entre batches
- Si Steam devuelve 429 (rate limit), el delay sube dinámicamente (x1.5, máx 5s)
- Tiempo estimado para fetch completo: ~4 minutos (vs ~80 min sin batching)

La respuesta incluye un campo `type` que indica si es `"game"`, `"dlc"`, `"demo"`, etc. Esto se usa para filtrar soundtracks y DLCs del matching con HLTB.

### Detección de oferta activa

```
GET /IMarketingMessagesService/GetActiveMarketingMessages/v1/
```

No requiere API key. Devuelve los eventos/ofertas activas de Steam. El script busca:
1. `type == 1` → Ofertas principales (Spring Sale, Summer Sale, fests)
2. `type == 11` → Weeklong Deals, Midweek Deals, Weekend Deals
3. Fallback: primer mensaje con título

El nombre de la oferta se usa para:
- El header del MD: `> 🏷️ **Steam Spring Sale** | 30 de marzo de 2026`
- El nombre del archivo: `Steam Deals Steam Spring Sale 2026-03-30.md`

### HLTB (HowLongToBeat)

Se exporta manualmente desde la web de HLTB: **Mi perfil → Exportar CSV**.

En la implementación actual, este dominio ya vive en `steam_deals_hltb.py`, mientras `steam_deals_generator.py` mantiene wrappers compatibles durante la modularización incremental.

El CSV tiene columnas relevantes:
- `Title` — nombre del juego
- `Backlog` — "X" si está en backlog
- `Completed` — "X" si está completado
- `Playing` — "X" si está jugando
- `Retired` — "X" si lo abandonaste
- `Storefront` — dónde lo tienes (Steam, Epic Games, GOG, Amazon Game App...)

---

## 2. Sistema de caché

Los precios se guardan en `.cache/steam_deals/prices_cache.json` (dentro del proyecto).

- **Expiración**: 24 horas
- **Smart refresh**: solo fetchea appids nuevos que no estén en caché
- **Guardado incremental**: guarda cada 10 batches para no perder progreso si crashea
- **Ctrl+C**: si interrumpes, guarda lo que lleve y la próxima vez continúa donde quedó
- **`--no-cache`**: fuerza re-fetch completo ignorando caché existente

Estructura del caché:
```json
{
  "steam_id": "76561198245393934",
  "saved_at": "2026-03-30T11:02:00",
  "fetched": {
    "730": {
      "name": "Counter-Strike 2",
      "type": "game",
      "discount_percent": 0,
      "price_final": "Free to Play",
      "price_original": "",
      "genres": ["action", "free to play"]
    },
    "12345": null
  }
}
```

`null` = appid consultado pero sin precio (gratis, no disponible en región, etc.)

---

## 3. Algoritmo de cruce (fuzzy matching)

### Filtro de DLC/Soundtracks

Antes de matchear, se filtran los deals que no sean `type == "game"`. Esto evita falsos positivos como:
- "Hotline Miami 2: Wrong Number" → matcheaba con "Hotline Miami 2: Wrong Number - Soundtrack"
- DLCs que comparten nombre con el juego base

### Normalización

Antes de comparar, ambos nombres se normalizan:
1. Minúsculas
2. Quitar ®™©
3. Solo letras, números y espacios
4. Romanos → arábigos (VI → 6, III → 3, etc.)

### Similitud

Se usa `difflib.SequenceMatcher` con threshold de **0.75** (75%).

### Validaciones extra (is_same_game)

1. **Números deben coincidir**: "Battlefield 1" vs "Battlefield 4" → rechazar
2. **Word overlap ≥ 70%**: las palabras del nombre más corto deben aparecer en el largo
3. **Palabras únicas en ambos lados** → son juegos distintos (excepto edition words como "remastered", "deluxe", etc.)

La implementación de parseo HLTB, normalización, `is_same_game`, `find_best_match` y `cross_hltb_with_deals` vive en `steam_deals_hltb.py` para mantener ese algoritmo aislado y testeable; `steam_deals_generator.py` actúa como frontera de compatibilidad/orquestación.

---

## 4. Estructura del MD generado

### Nombre del archivo

- Con oferta detectada: `Steam Deals [Nombre de la oferta] [YYYY-MM-DD].md`
- Sin oferta: `Steam Deals [YYYY-MM-DD].md`
- Se genera en el mismo directorio del script

### Secciones

```
# Steam Wishlist Deals — [vanity]
> 🏷️ [Oferta activa] | [fecha] | Precios en MXN

## Backlog en Oferta — Ya los Tienes en HLTB
  → 🟡 Confirmado en Familia de Steam
  → 🟢 Sin plataforma registrada en HLTB

## Genre Deals (si se pasaron --genre)

## Quitar de la Wishlist
  → Ya comprados en Steam (no se quitaron automáticamente)
  → 🔴 Otra plataforma (GOG, Epic, Amazon…)
  → ⚠️ Steam en HLTB — no localizado en familia
  → Completados / Retirados en HLTB

## Deals por tier (90%+, 80-89%, 70-79%, 60-69%, 50-59%)
```

La sección "Quitar de la Wishlist" agrupa todo lo que deberías remover:
- Juegos ya comprados en Steam que siguen en la wishlist (Steam no siempre los quita automáticamente)
- Juegos que ya tienes en otra plataforma según HLTB
- Juegos marcados como Steam en HLTB pero no aparecen en tu biblioteca familiar
- Juegos completados o retirados que siguen en la wishlist

---

## 5. Configuración

### Archivo de config

`~/.config/steam_deals.json` — se crea tras el primer run interactivo si eliges guardar.

```json
{
  "key": "TU_API_KEY",
  "vanity": "gaben",
  "hltb": null,
  "output_dir": "/home/usuario/Documents/Deals",
  "discount": 50,
  "genres": [],
  "family_json": null
}
```

### Flags de línea de comandos

| Flag | Descripción |
|------|-------------|
| `--key` | Steam API Key |
| `--vanity` | Vanity URL o Steam ID numérico |
| `--hltb` | Ruta al CSV de HLTB (opcional) |
| `--output` | Directorio de salida para los MD |
| `--discount` | Descuento mínimo % (default: 50) |
| `--genre` | Géneros de interés (puede repetirse) |
| `--no-cache` | Ignorar caché y re-fetchear todo |
| `--family-json` | Ruta al JSON de biblioteca familiar |

Prioridad: flag CLI > config file > prompt interactivo.

---

## 6. Flujo completo resumido

```
1. Resolver vanity URL → Steam ID numérico
2. GET wishlist → lista de ~2,900 appids
3. GET biblioteca → juegos ya comprados
4. GET marketing messages → oferta activa de Steam
5. Construir nombre del archivo (oferta + fecha)
6. Para cada batch de 20 appids:
   a. GET store/appdetails?appids=id1,id2,...&cc=mx
   b. Guardar en caché (nombre, tipo, precio, descuento, géneros)
   c. Cada 10 batches → guardado incremental
7. Filtrar deals con descuento >= mínimo
8. Si hay HLTB CSV:
   a. Parsear CSV → backlog[], completed[], playing[], retired[]
   b. Para cada juego, buscar match en deals[] (solo type=game)
   c. Clasificar por storefront y estado
9. Generar MD con todas las secciones
```
