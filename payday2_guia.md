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
- **Umbral configurable (`--min-deal`)** — Define el descuento mínimo para recomendar compra (default: 50%)
- **Tu Presupuesto Ideal** — "Tengo $500, ¿qué compro?" ordenado por mejor oferta
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
- **Tu Presupuesto Ideal** — "Tengo $500, ¿qué compro?" ordenado por mejor oferta
- **Próximas ofertas** — Estimación de costo en Summer/Autumn/Winter Sale
- **Actualizar datos** — Botón que ejecuta el tracker y muestra progreso en vivo
- **Config** — Cambia vanity/API keys desde la web

También disponible como tab integrado en `steam_deals_web.py`.

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

# Umbral de descuento para recomendar compra (default: 50%)
python3 payday2_dlc_tracker.py --min-deal 75

# Marcar DLC como comprado
python3 payday2_dlc_tracker.py --mark-owned 12345

# Desmarcar DLC
python3 payday2_dlc_tracker.py --mark-unowned 12345

# Generar CSV
python3 payday2_dlc_tracker.py --csv

# Ignorar caché
python3 payday2_dlc_tracker.py --no-cache
```

Genera `PAYDAY2_Plan_de_Compra.md` y `.html` con el reporte completo.

## Todos los flags

| Flag | Descripción |
|------|-------------|
| `--vanity` | Vanity URL, Steam ID, o link de perfil |
| `--key` | Steam API Key (detecta DLCs propios) |
| `--itad-key` | IsThereAnyDeal API Key (mínimos históricos) |
| `--output` | Directorio de salida |
| `--no-cache` | Ignorar caché existente |
| `--budget` | Presupuesto en MXN |
| `--alert-price` | Alertar si DLC baja de N MXN |
| `--min-deal` | Descuento mínimo % para recomendar compra (default: 50) |
| `--mark-owned` | Marcar appids como poseídos |
| `--mark-unowned` | Desmarcar appids |
| `--csv` | Generar CSV |

## Config

Reutiliza la config de Steam Deals en `~/.config/steam_deals.json`. Los campos `payday2_budget`, `payday2_alert_price`, y `payday2_min_deal` se guardan ahí también.

## Caché

Los datos se cachean en `.cache/steam_deals/payday2/` (dentro del proyecto):

| Dato | TTL |
|------|-----|
| Lista de DLCs | 7 días |
| Precios | 24 horas |
| Historial de precios | Permanente (últimos 365 días) |

Usa `--no-cache` para forzar re-fetch.
