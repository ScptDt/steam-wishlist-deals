# Guía técnica: Cómo funciona Steam Wishlist Deals

> Guía de arquitectura/funcionamiento interno. Para instalación, uso diario, desktop y comandos rápidos, usa `README.md`. Para validaciones paso a paso, usa `docs/runbooks/README.md`.

## Panorama general

El flujo base hace estos pasos en orden:

```
Steam API → Resolver vanity URL → Steam ID
Steam API → Lista de la wishlist (appids)
Steam API → Biblioteca propia (juegos comprados)
Steam API → Detectar oferta activa (marketing messages)
Steam Store API → Precios actuales (batching/paralelismo controlado)
Python → Cruce con HLTB + scoring + generación de reportes
```

---

## 1. Fuentes de datos

### Steam API (API Key opcional según el dato)

Base URL: `https://api.steampowered.com/`

Necesitas:
- **Perfil Steam**: vanity URL, URL completa o Steam ID de 17 dígitos.
- **API Key**: opcional para wishlist pública; recomendable para resolver datos privados como juegos propios y biblioteca familiar. Se obtiene en https://steamcommunity.com/dev/apikey

**Endpoints usados:**

| Endpoint | Qué devuelve | Requiere API Key |
|----------|-------------|-----------------|
| `ISteamUser/ResolveVanityURL/v1/?vanityurl=...` | Traduce vanity URL a Steam ID | Opcional; fallback a perfil público XML sin key |
| `IWishlistService/GetWishlist/v1/?steamid=...` | Lista de appids de la wishlist | Opcional si la wishlist es pública |
| `IPlayerService/GetOwnedGames/v1/?include_appinfo=1` | Juegos comprados con nombres | Sí |
| `IMarketingMessagesService/GetActiveMarketingMessages/v1/` | Ofertas/eventos activos de Steam | No |

### Vanity URL vs API Key

- **Vanity URL** (`gaben`): Es pública, solo identifica tu perfil. Con ella se resuelve tu Steam ID numérico.
- **API Key**: habilita datos privados/extra, especialmente juegos propios. Sin ella el flujo puede funcionar si tu wishlist es pública, pero tendrá menos señales.

### Steam Store API (precios, batching y fallback)

Base URL: `https://store.steampowered.com/api/`

```
GET /appdetails?appids=730,440,570,...&cc=mx&filters=price_overview,basic,genres
```

- `cc=mx` → precios en MXN
- `filters=price_overview,basic,genres` → nombre, tipo (game/dlc), precio y géneros
- **Batching**: acepta múltiples appids separados por coma, evitando una request por juego cuando Steam responde bien.
- **Paralelismo**: el enrichment usa `--max-workers` (default actual: 16) y puede bajarse a 12/8 si hay rate limits o red inestable.

**Rate limiting / errores externos**:
- Si Steam degrada batches (`HTTP 400`, `429` u otros fallos), el flujo puede caer a fallback individual para rescatar appids puntuales.
- Los fallos/no-data recientes entran en cooldown corto para no repetir trabajo lento innecesario.
- Para medir corridas grandes, usar `--warm-cache` y el runbook `docs/runbooks/performance-warm-cache.md`.

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
- El header del Markdown: `> 🏷️ **Steam Spring Sale** | 30 de marzo de 2026`
- El nombre del archivo: `Steam Deals Steam Spring Sale 2026-03-30.md`

### HLTB (HowLongToBeat)

Se exporta manualmente desde la web de HLTB: **Mi perfil → Exportar CSV**.

En Web/Desktop se puede pegar una ruta local al CSV. En Windows, las rutas con espacios deben conservarse completas, por ejemplo:

```text
C:/Users/Bryan Grijalva/Downloads/HLTB_Games_2026-05-15.csv
```

En la UI web no hace falta envolver la ruta en comillas; en CLI sí conviene usar comillas si la ruta tiene espacios. El preflight debe tratar la ruta como dato local sensible: confirmar si existe o no, pero sin filtrar la ruta completa en mensajes públicos/logs.

Plan de mejora pendiente: detectar de forma explícita y no intrusiva exports `HLTB*.csv` en `Documents/SteamTools/imports`, `Documents` o `Downloads` cuando el campo esté vacío, manteniendo la ruta redactada y sin subir archivos al navegador.

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

## 4. Reportes generados

### Nombre de archivos

- Con oferta detectada: `Steam Deals [Nombre de la oferta] [YYYY-MM-DD].*`
- Sin oferta: `Steam Deals [YYYY-MM-DD].*`
- Por defecto se generan en `output/` o en el directorio indicado con `--output`.
- Formatos vigentes: Markdown `.md`, HTML interactivo `.html`, Share HTML, JSON estructurado `.json` y CSV `.csv` cuando se activa.

### Secciones principales del Markdown

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
| `--output` | Directorio de salida para reportes |
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
9. Generar reportes (`.md`, `.html`, Share HTML, `.json` y `.csv` si aplica)
```
