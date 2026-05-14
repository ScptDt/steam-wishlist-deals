# PAYDAY 2 DLC Tracker

Herramienta para trackear todos los DLCs de PAYDAY 2: cuáles te faltan, precios en tiempo real, ofertas, historial de precios, y recomendaciones de compra.

Los DLCs se descubren dinámicamente desde la API de Steam — no hay base de datos hardcodeada.

## Features

### Datos y Análisis
- **Descubrimiento dinámico** — Detecta todos los DLCs de PAYDAY 2 automáticamente desde Steam
- **Precios en tiempo real** — Fetch de precios actuales en MXN desde la API de Steam
- **Detección de ofertas** — Identifica DLCs en descuento y calcula ahorro potencial
- **ITAD (IsThereAnyDeal)** — Mínimo histórico y precios en otras tiendas
- **Historial de precios** — Snapshots diarios con análisis de tendencia (hasta 365 días)
- **Comparación entre runs** — Detecta nuevas ofertas, ofertas terminadas, y bajadas de precio
- **Estimación de próximas ofertas** — Proyección de costos en Summer/Autumn/Winter Sale

### Herramientas
- **Umbral configurable (`--min-deal`)** — Define el descuento mínimo para clasificar recomendaciones (default: 50%)
- **Tu Presupuesto Ideal** — "Tengo $500, ¿qué compro?" priorizando importancia jugable y valor, no solo descuento/precio
- **Recomendaciones advisory-only** — Separa DLCs en `Comprar ahora`, `Revisar antes de comprar` y `Esperar mejor oferta` con razones visibles; no marca DLCs como comprados ni cambia tus checkboxes manuales
- **Alert Price** — Alertar cuando un DLC baja de N MXN
- **Mark Owned/Unowned** — Marcar DLCs como comprados o no desde CLI o desde la web (checkboxes)

> **Nota:** La API de Steam no permite detectar DLCs poseídos automáticamente (solo juegos base). Los DLCs se marcan manualmente vía checkboxes en el dashboard o con `--mark-owned` en CLI.

### Salida
- **Markdown** — Reporte completo con tablas, recomendaciones, y ofertas
- **HTML interactivo** — Dashboard con donut chart, filtros, imágenes, sparklines de precio
- **CSV** — Exportación para Excel/Google Sheets

## Requisitos

- Python 3.10+
- Sin dependencias externas (solo stdlib)

## Dashboard Web (recomendado)

```bash
python3 payday2_web.py
# Se abre http://127.0.0.1:8081 en tu navegador
```

Dashboard interactivo con:
- **Vista instantánea** — Carga datos del caché al abrir, sin esperas
- **Stats y donut** — Cuántos DLCs tienes, cuánto falta, ofertas activas
- **Tabla de DLCs** — Sorteable, filtrable por oferta, con imágenes
- **Marcar como comprado** — Click en el checkbox y se guarda al instante
- **Simulador de descuento** — Desliza para ver cuánto costaría con X% de descuento
- **Tu Presupuesto Ideal** — "Tengo $500, ¿qué compro?" priorizando importancia/valor del DLC antes que solo el descuento más alto
- **Recomendaciones de compra** — Banners compactos para `Comprar ahora`, `Revisar antes de comprar` y `Esperar mejor oferta`, siempre como sugerencias locales/advisory-only
- **Próximas ofertas** — Estimación de costo en Summer/Autumn/Winter Sale
- **Actualizar datos** — Botón que ejecuta el tracker y muestra progreso en vivo
- **Forzar catálogo** — Acción secundaria que ejecuta el tracker con `--no-cache` cuando esperas DLCs nuevos o sospechas caché viejo
- **Estado de caché/fuente** — Muestra edad y conteo del catálogo, nombres, precios y bundles cargados desde caché
- **Config** — Cambia vanity/API keys desde la web

También disponible como tab integrado en `steam_deals_web.py`.

### Flujo recomendado

1. Abre `python3 payday2_web.py`.
2. Configura tu perfil/API key si hace falta.
3. Usa **Actualizar datos** para el refresh normal: respeta caché/TTL y es el camino recomendado.
4. Revisa los banners de recomendación: `Comprar ahora` prioriza ofertas fuertes/jugables, `Revisar` pide contexto manual, y `Esperar` indica que no cumple el umbral actual o la oferta no es convincente.
5. Marca DLCs propios manualmente con los checkboxes; Steam no reporta ownership de DLCs de forma fiable y las recomendaciones no cambian ese estado.
6. Usa **Forzar catálogo** solo si esperas DLCs nuevos o sospechas caché viejo. Esa acción equivale a `python3 payday2_dlc_tracker.py --no-cache`.
7. Si el DLC esperado sigue sin aparecer, usa `--diagnose-dlc APPID_O_NOMBRE` para saber si Steam lo expone como DLC del app base `218620` o si parece app/package/bundle separado.

## CLI

```bash
# Básico (usa config compartida de Steam Deals)
python3 payday2_dlc_tracker.py --vanity TU_VANITY_URL

# Con API key/config compartida (ownership de DLCs sigue siendo manual)
python3 payday2_dlc_tracker.py --key TU_KEY --vanity TU_VANITY_URL

# Con ITAD (mínimos históricos + multi-tienda)
python3 payday2_dlc_tracker.py --itad-key TU_KEY

# Tu Presupuesto Ideal
python3 payday2_dlc_tracker.py --budget 500

# Alert price
python3 payday2_dlc_tracker.py --alert-price 30

# Umbral de descuento para clasificar compra/revisar/esperar (default: 50%)
python3 payday2_dlc_tracker.py --min-deal 75

# Marcar DLC como comprado
python3 payday2_dlc_tracker.py --mark-owned 12345

# Desmarcar DLC
python3 payday2_dlc_tracker.py --mark-unowned 12345

# Generar CSV
python3 payday2_dlc_tracker.py --csv

# Ignorar caché / forzar catálogo live
python3 payday2_dlc_tracker.py --no-cache

# Diagnosticar un DLC esperado que no aparece
python3 payday2_dlc_tracker.py --diagnose-dlc 123456
python3 payday2_dlc_tracker.py --diagnose-dlc "Nombre del DLC"
```

Genera `PAYDAY2_Plan_de_Compra.md` y `.html` con el reporte completo; si usas `--csv`, también genera `.csv`.

## Todos los flags

| Flag | Descripción |
|------|-------------|
| `--vanity` | Vanity URL, Steam ID, o link de perfil |
| `--key` | Steam API Key (resuelve perfil/juegos base; ownership de DLCs sigue siendo manual) |
| `--itad-key` | IsThereAnyDeal API Key (mínimos históricos) |
| `--output` | Directorio de salida |
| `--no-cache` | Ignorar caché existente |
| `--diagnose-dlc` | Diagnosticar por appid/nombre si un DLC esperado no aparece en el catálogo |
| `--budget` | Presupuesto en MXN |
| `--alert-price` | Alertar si DLC baja de N MXN |
| `--min-deal` | Descuento mínimo % para clasificar recomendaciones `comprar/revisar/esperar` (default: 50) |
| `--mark-owned` | Marcar appids como poseídos |
| `--mark-unowned` | Desmarcar appids |
| `--csv` | Generar CSV |

## Config

Reutiliza la config de Steam Deals en `~/.config/steam_deals.json`. Los campos `payday2_budget`, `payday2_alert_price`, y `payday2_min_deal` se guardan ahí también.

## Caché

Los datos se cachean en `.cache/steam_deals/payday2/` (dentro del proyecto):

| Archivo | Dato | TTL / uso |
|------|------|-----|
| `dlc_list.json` | AppIDs publicados por Steam en `data.dlc` del app base `218620` | 7 días |
| `dlc_mapping.json` | Nombres cacheados por appid | 7 días / se refresca junto con catálogo |
| `prices.json` | Precio, descuento y nombre básico por DLC | 24 horas |
| `bundles.json` | Bundles detectados desde la tienda de PAYDAY 2 | 7 días |
| `owned.json` | DLCs marcados manualmente como propios | Sin TTL; no se borra por refresh |
| `price_history.json` | Snapshots de precios | Permanente, últimos 365 días |

### Refresh normal vs forzado

- **Actualizar datos** en la Web y el CLI normal usan caché si está dentro del TTL.
- **Forzar catálogo** en la Web y `--no-cache` ignoran caché de catálogo/precios para pedir datos live a Steam.
- `--no-cache` no debería borrar tus marcados manuales (`owned.json`); solo fuerza re-fetch de datos de Steam.
- Si Steam no devuelve un appid en `data.dlc`, forzar caché no puede inventarlo de forma segura.

## DLC nuevo no aparece

Usa:

```bash
python3 payday2_dlc_tracker.py --diagnose-dlc APPID_O_NOMBRE
```

El diagnóstico clasifica el caso y sugiere una acción:

| Estado | Significado | Acción típica |
|---|---|---|
| `listed_in_base_dlc` | Steam live sí lo lista en `data.dlc` del app `218620` | Recarga la UI/revisa filtros; debería entrar al catálogo |
| `cache_stale` | Steam live lo lista, pero tu cache local aún no | Usa **Forzar catálogo** o `--no-cache` |
| `valid_app_not_linked_to_base` | El app existe en Steam, pero no está enlazado como DLC de PAYDAY 2 | No hardcodearlo; esperar/confirmar fuente Steam |
| `package_or_bundle_candidate` | La URL/ID parece bundle/package/sub, no appid de DLC | Revisar como bundle; el tracker solo cataloga appids DLC |
| `not_found_or_unreleased` | Steam no lo devuelve como app pública | Verificar appid/nombre o esperar publicación |
| `name_mismatch` | El nombre buscado no coincide de forma segura con el candidato | Confirmar appid exacto |

Steam puede publicar contenido como package/bundle separado o no exponerlo aún en `data.dlc` del app base `218620`. No se recomienda hardcodear DLCs manualmente sin confirmación de Steam.
