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
- **Core (CLI + Web):** sin dependencias externas (solo stdlib)
- **Desktop (pywebview):** requiere dependencias extra de `requirements-desktop.txt`

## Superficies del proyecto

Este repo se puede ejecutar en 3 superficies. **Recomendado para la mayoría de usuarios: Web UI**.

| Superficie | Objetivo | Dependencias | Entry point |
|------------|----------|--------------|-------------|
| Core CLI | Automatización por terminal y flags avanzados | Solo stdlib | `steam_deals_generator.py`, `payday2_dlc_tracker.py` |
| Web UI | Flujo guiado en navegador local | Solo stdlib | `steam_deals_web.py` (8080), `payday2_web.py` (8081) |
| Desktop | App en ventana nativa (empaquetable) | `requirements-desktop.txt` | `steam_tools_desktop.py`, `build_desktop.py` |

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
pip install -r requirements-desktop.txt
python steam_tools_desktop.py
```

## Uso rápido

> Nota: el flujo principal es el wizard web. El CLI sigue disponible como opción (con flags/config), y puedes usar `--interactive` si quieres prompts en terminal.

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

> Para el módulo PAYDAY 2 usa `python3 payday2_web.py` (puerto 8081).

## Desktop (Opción B: pywebview)

Baseline inicial para ejecutable de escritorio:

```bash
pip install -r requirements-desktop.txt
python steam_tools_desktop.py
```

Build unificado (todas las plataformas):

```bash
python build_desktop.py
```

Para generar un `.exe` en Windows (wrapper):

```powershell
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

Para Linux/macOS (wrapper):

```bash
chmod +x ./build_desktop.sh
./build_desktop.sh
```

Esto abre la misma app web dentro de una ventana nativa.

### Dependencias nativas por plataforma (pywebview)

`pywebview` usa backend nativo distinto por OS. En este repo, la base sigue siendo:

```bash
pip install -r requirements-desktop.txt
```

Dependencias/requisitos por plataforma:

- **Windows**
  - Backend esperado: WebView2 (Edge Chromium).
  - Requisito recomendado en máquina destino: **Microsoft Edge WebView2 Runtime**.
  - Si no hay backend nativo disponible, el launcher mantiene fallback al navegador (`steam_deals_web.py`).

- **Linux (Ubuntu LTS)**
  - Instalar deps del sistema para backend Qt o GTK/WebKit2.
  - Comandos de referencia (Ubuntu):

```bash
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtwebchannel libqt5webkit5-dev
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

- **macOS**
  - Backend nativo: Cocoa/WKWebView (PyObjC).
  - Si usas Python no-sistema, puede requerir paquetes `pyobjc-*` adicionales.
  - Para distribuir a terceros, preferir `.app` firmado/notarizado (evita fricción con Gatekeeper).

Referencias oficiales:
- https://pywebview.flowrl.com/guide/installation
- https://pywebview.flowrl.com/guide/web_engine
- https://pywebview.flowrl.com/guide/freezing
- https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing

### Checklist de validación desktop por OS

> Nota: desde entorno Windows no se puede validar backend nativo Linux/macOS de forma concluyente. Ejecutar en host nativo o runner CI del OS objetivo.

#### Linux (Ubuntu LTS)

1. `python3 -m pip install -r requirements-desktop.txt`
2. `python3 build_desktop.py`
3. Ejecutar artefacto en `dist/SteamToolsDesktop`.
4. Verificar: ventana nativa, preflight, run de prueba, outputs MD/HTML/CSV, cierre limpio.
5. Fallback mitigación: `python3 steam_deals_web.py --no-open --port 8080`.

#### macOS

1. `python3 -m pip install -r requirements-desktop.txt`
2. `python3 build_desktop.py`
3. Abrir app local: `open dist/SteamToolsDesktop.app`.
4. Verificar: ventana nativa, preflight, run de prueba, outputs MD/HTML/CSV, cierre limpio.
5. Si Gatekeeper bloquea artefacto local no firmado: `xattr -dr com.apple.quarantine dist/SteamToolsDesktop.app` y volver a abrir.
6. Fallback mitigación: `python3 steam_deals_web.py --no-open --port 8080`.

Planes y pendientes unificados: `PENDIENTES.md`.

## Módulos y entrypoints

### Steam Deals
- **CLI:** `steam_deals_generator.py`
- **Web:** `steam_deals_web.py` (http://127.0.0.1:8080)
- **Guía:** `steam_deals_guia.md`
- **Detalle en este README:** secciones `Watchlist`, `Budget Mode`, `Comparar Wishlists`, `Notificaciones`, `Scheduler`, `Todos los flags`.

### PAYDAY 2
- **CLI:** `payday2_dlc_tracker.py`
- **Web:** `payday2_web.py` (http://127.0.0.1:8081)
- **Guía:** `payday2_guia.md`
- **Outputs:** `PAYDAY2_Plan_de_Compra.md` y `.html`
- **Detalle en este README:** sección `PAYDAY 2 DLC Tracker`.

### Desktop Suite
- **Launcher:** `steam_tools_desktop.py`
- **Build unificado:** `build_desktop.py`
- **Wrappers:** `build_desktop.ps1`, `build_desktop.sh`

## Outputs por módulo

| Módulo | Output principal | Formatos |
|--------|------------------|----------|
| Steam Deals | Reporte de deals de wishlist | `.md`, `.html`, `.csv` |
| PAYDAY 2 | `PAYDAY2_Plan_de_Compra` | `.md`, `.html` |
| Desktop Build | Artefactos de distribución | `dist/` (binario/app según OS) |

Notas rápidas:
- Los datos intermedios y caché viven en `.cache/steam_deals/`.
- En desktop, los artefactos finales dependen de la plataforma (Windows/macOS/Linux).

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

## Todos los flags (Steam Deals CLI)

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

## PAYDAY 2 DLC Tracker (detalle)

Script y dashboard web para trackear DLCs de PAYDAY 2: cuáles te faltan, precios, ofertas, historial y recomendaciones de compra. Los DLCs se descubren dinámicamente desde la API de Steam.

> **Nota:** La API de Steam no detecta DLCs poseídos (solo juegos base). Marca tus DLCs como comprados vía checkboxes en el dashboard o con `--mark-owned` en CLI.

### Dashboard Web (recomendado)

```bash
python3 payday2_web.py
# Se abre http://127.0.0.1:8081 en tu navegador
```

Dashboard interactivo con:
- **Vista instantánea** — Carga datos del caché al abrir, sin esperas
- **Stats y donut** — Cuántos DLCs tienes, cuánto falta, ofertas activas
- **Tabla de DLCs** — Sorteable, filtrable por oferta, con imagenes
- **Marcar como comprado** — Click en el checkbox y se guarda al instante
- **Simulador de descuento** — Desliza para ver cuánto costaría con X% de descuento
- **Budget Planner** — "Tengo $500, ¿qué compro?" ordenado por mejor oferta
- **Próximas ofertas** — Estimación de costo en Summer/Autumn/Winter Sale
- **Actualizar datos** — Boton que ejecuta el tracker y muestra progreso en vivo
- **Config** — Cambia vanity/API keys desde la web

### CLI

```bash
python3 payday2_dlc_tracker.py --vanity TU_VANITY_URL
python3 payday2_dlc_tracker.py --budget 500
python3 payday2_dlc_tracker.py --min-deal 75          # umbral de descuento para recomendar
python3 payday2_dlc_tracker.py --itad-key TU_KEY      # mínimos históricos
python3 payday2_dlc_tracker.py --mark-owned 259381    # marcar DLC como comprado
```

Genera `PAYDAY2_Plan_de_Compra.md` y `.html` con el reporte completo.

## Caché

Los datos se cachean en `.cache/steam_deals/` (dentro del proyecto) para evitar requests innecesarios:

| Dato | TTL |
|------|-----|
| Precios | 24 horas |
| Reviews, Deck, ProtonDB, Anti-Cheat | 7 días |
| Tags (SteamSpy), Achievements | 30 días |

Usa `--no-cache` para forzar re-fetch.

## Config

La configuración se guarda en `~/.config/steam_deals.json` tras el primer run interactivo. La watchlist se guarda en `~/.config/steam_deals_watchlist.json`.
