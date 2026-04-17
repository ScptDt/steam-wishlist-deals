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
- **Top Picks** — Ranking por value score (reviews, descuento, prioridad, $/hora, Deck, Metacritic, edad) con recomendación rápida y razones visibles

### Herramientas
- **Watchlist Personal** — Alertas cuando un juego baja de tu precio objetivo
- **Budget Mode** — "Tengo $500, ¿qué compro?" — optimizador greedy por eficiencia con contexto de recomendación en los picks sugeridos
- **Comparar Wishlists** — Overlap con amigos + gift ideas
- **Notificaciones** — Telegram y Discord webhook con resumen de cambios
- **Scheduler** — Ejecución automática cada N horas
- **Comparación entre runs** — Detecta deals nuevos, terminados, y bajadas de precio

### Salida
- **Markdown** — Reporte completo con tablas, secciones, y badges
- **HTML interactivo** — Dashboard con gráficas, filtros en vivo, thumbnails con hover zoom, sparklines de precio
- **HTML compartible** — Versión ligera para enviar a amigos
- **JSON** — Export estructurado para automatización local (`meta`, `inputs`, `summary`, `top_picks`, `deals`, `budget_result`, etc.)
- **CSV** — Exportación para Excel/Google Sheets (+ botón "Copiar para Sheets" en el HTML)

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
- Para trabajo operativo, roadmap y deuda técnica, la fuente de verdad sigue siendo `PENDIENTES.md`.

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
python -m pip install -r requirements-desktop.txt
python steam_tools_desktop.py
```

Desktop agrega dependencias solo para la ventana nativa / empaquetado. El flujo funcional sigue siendo el mismo server/UI local.

> En Debian/Ubuntu y otros entornos con Python marcado como `externally-managed` (PEP 668), usa `.venv` para instalar `requirements-desktop.txt` en vez de `pip` global del sistema.

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

# Wishlist grande (ajuste conservador de paralelismo en enrichment)
python3 steam_deals_generator.py --vanity TU_VANITY_URL --max-workers 16
```

`--max-workers` controla el paralelismo de fetch en enrichment. Recomendación práctica: empezar en `12` (default), probar `16` si tu red/API responde bien y evitar valores muy altos para reducir riesgo de rate limit.

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
- `deals`, `watchlist_alerts`, `budget_result`, `compare_data`

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

Baseline inicial para ejecutable de escritorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt
python steam_tools_desktop.py
```

Build unificado (todas las plataformas):

```bash
python build_desktop.py
```

### Doctor desktop + autofix seguro

```bash
python3 -m venv .venv
source .venv/bin/activate
python steam_tools_desktop.py --doctor
python steam_tools_desktop.py --doctor-fix
```

El doctor reporta `OK / WARN / FAIL` para checks utiles de readiness desktop, incluyendo:

- `.venv` / PEP 668 en Linux
- disponibilidad de `pywebview` y backend Qt esperado en Linux
- herramientas host de PyInstaller en Linux (`ldd`, `objdump`, `objcopy`) y heuristicas Wayland/X11 cuando aplica
- disponibilidad de `PyInstaller`
- guardrails de packaging conocidos del repo
- checks especificos por OS para macOS (PyObjC / tooling local) y Windows (WebView2 / sesion)
- presencia del artefacto desktop y warnings conocidos del ultimo build

Ademas, cuando encuentra `WARN`/`FAIL`, ahora agrega guidance mas profundo por plataforma, por ejemplo:

- **Linux**: separa deps Python vs deps nativas del sistema, orienta sobre Wayland/X11 y `QT_QPA_PLATFORM=xcb`, y recuerda validar el artefacto desde una sesion grafica normal.
- **macOS**: explica que backend/runtime espera PyObjC/Cocoa/WebKit, cuando conviene revisar `xcode-select` / `codesign` / `xattr`, y que la validacion final de la `.app` debe hacerse en una sesion local.
- **Windows**: explica el rol de WebView2, como validar manualmente el runtime y por que la validacion final del `.exe` debe ser en Console/RDP interactivo.

Tambien puedes ejecutarlo desde la Web UI con los botones **Doctor desktop** y **Autofix desktop**; reutilizan la misma logica y muestran el diagnostico en la consola local.

Autofix seguro (opt-in):

- crea `.venv` local si hace falta
- instala `requirements-desktop.txt` dentro de `.venv`
- puede lanzar `build_desktop.py --skip-install` cuando el artefacto falta

Limites actuales del autofix:

- no instala paquetes del sistema (`apt`, `brew`, `winget`, etc.)
- no toca shell profiles, registro de Windows ni variables persistentes
- no modifica archivos del repo para “arreglar” packaging
- requiere confirmacion explicita (`--yes` en CLI o confirmacion en Web UI)

Exit code:
- `0` = sin bloqueos reales (`FAIL`)
- `1` = hay al menos un bloqueo real a corregir antes de seguir

Para generar un `.exe` en Windows (wrapper):

```powershell
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

Para Linux/macOS (wrapper):

```bash
chmod +x ./build_desktop.sh
./build_desktop.sh
```

Esto abre la misma app web dentro de una ventana nativa. Si `pywebview` o el backend nativo no arrancan, el launcher abre automaticamente la misma Web UI en el navegador por defecto y muestra un aviso visible de fallback.

### Dependencias nativas por plataforma (pywebview)

`pywebview` usa backend nativo distinto por OS. En este repo, la base sigue siendo:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt
```

En Linux, `requirements-desktop.txt` instala `pywebview[qt]` automaticamente dentro del entorno Python del proyecto. Eso cubre `QtPy` + `PyQt6` + `PyQt6-WebEngine`, pero no reemplaza dependencias/librerias nativas del sistema cuando el backend Qt o GTK/WebKit las requiera.

Dependencias/requisitos por plataforma:

- **Windows**
  - Backend esperado: WebView2 (Edge Chromium).
  - Requisito recomendado en máquina destino: **Microsoft Edge WebView2 Runtime**.
  - Si no hay backend nativo disponible, el launcher mantiene fallback al navegador (`steam_deals_web.py`) y la UI indica que estas en modo web.

- **Linux (Ubuntu LTS)**
  - Hallazgo practico validado en este repo: instalar solo `pywebview` no alcanza siempre para levantar backend nativo; en Linux usa `requirements-desktop.txt` dentro de `.venv`.
  - Si el backend Qt del wheel no levanta o faltan librerias/plugins del sistema, instalar deps distro para Qt o GTK/WebKit2.
  - Comandos de referencia (Ubuntu, cuando hagan falta deps nativas adicionales):

```bash
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtwebchannel libqt5webkit5-dev
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

- **macOS**
  - Backend nativo: Cocoa/WKWebView (PyObjC).
  - Si usas Python no-sistema, puede requerir paquetes `pyobjc-*` adicionales.
  - Comando de referencia (cuando aplique): `python3 -m pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit`
  - Recomendado: tener Command Line Tools disponibles (`xcode-select --install`) para flujo de build/firma local.
  - Para distribuir a terceros, preferir `.app` firmado/notarizado (evita fricción con Gatekeeper).

Referencias oficiales:
- https://pywebview.flowrl.com/guide/installation
- https://pywebview.flowrl.com/guide/web_engine
- https://pywebview.flowrl.com/guide/freezing
- https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing

### Checklist de validación desktop por OS

> Nota: desde entorno Windows no se puede validar backend nativo Linux/macOS de forma concluyente. Ejecutar en host nativo o runner CI del OS objetivo.

Runbooks detallados por plataforma:

- Linux: `docs/runbooks/desktop-linux.md`
- macOS: `docs/runbooks/desktop-macos.md`
- Windows: `docs/runbooks/desktop-windows.md`

#### Linux (Ubuntu LTS)

1. Preparar entorno:
   - `python3 --version && python3 -m pip --version`
   - Esperado: Python/pip disponibles y funcionales.
2. Crear/activar entorno virtual local (recomendado; necesario en Debian/Ubuntu con PEP 668):
   - `python3 -m venv .venv && source .venv/bin/activate`
   - Esperado: shell usando el Python del proyecto.
3. Instalar dependencias desktop:
   - `python -m pip install -r requirements-desktop.txt`
   - Esperado: instalación sin errores; `pywebview[qt]` resuelto para Linux.
4. Build desktop:
   - `python build_desktop.py`
   - Esperado: artefacto generado en `dist/SteamToolsDesktop` (o `dist/SteamToolsDesktop/` según modo de build).
5. Ejecutar artefacto nativo:
   - `./dist/SteamToolsDesktop`
   - Esperado: ventana nativa abre y la UI responde.
6. Verificación funcional mínima:
   - Ejecutar preflight, correr run de prueba, generar MD/HTML/CSV y cerrar app.
   - Esperado: sin crash, outputs presentes, sin procesos colgados.
7. Fallback mitigación (si la ventana nativa no abre):
   - `python3 steam_deals_web.py --no-open --port 8080`
   - Esperado: servidor arriba en `http://127.0.0.1:8080`.

#### macOS

1. Preparar entorno:
   - `python3 --version && python3 -m pip --version`
   - Esperado: Python/pip disponibles y funcionales.
2. Instalar dependencias desktop:
   - `python3 -m pip install -r requirements-desktop.txt`
   - Esperado: instalación sin errores; `pywebview` instalado.
3. Build desktop:
   - `python3 build_desktop.py`
   - Esperado: artefacto `.app` generado en `dist/SteamToolsDesktop.app`.
4. Abrir app local:
   - `open dist/SteamToolsDesktop.app`
   - Esperado: app abre localmente y muestra UI.
5. Verificación funcional mínima:
   - Ejecutar preflight, correr run de prueba, generar MD/HTML/CSV y cerrar app.
   - Esperado: sin crash, outputs presentes, sin procesos colgados.
6. Quarantine/permisos (si aplica):
   - `xattr -dr com.apple.quarantine dist/SteamToolsDesktop.app`
   - Esperado: app vuelve a abrir cuando Gatekeeper bloquee artefacto local no firmado.
7. Verificación de codesign (si aplica distribución):
   - `codesign --verify --deep --strict --verbose=2 dist/SteamToolsDesktop.app`
   - Esperado: verificación exitosa del bundle (o error explícito a resolver antes de distribuir).
8. Fallback mitigación (si la ventana nativa no abre):
   - `python3 steam_deals_web.py --no-open --port 8080`
   - Esperado: servidor arriba en `http://127.0.0.1:8080`.

#### Repetición recomendada en CI/runners (fuera de Windows)

- Linux: ejecutar checklist de Linux en host nativo o runner `ubuntu-latest`.
- macOS: ejecutar checklist de macOS en host nativo o runner `macos-latest`.
- Registrar por plataforma: resultado por paso, error textual y workaround aplicado.
- Workflow incluido: `.github/workflows/desktop-cross-platform.yml`.
  - Ejecuta en `ubuntu-latest` y `macos-latest`.
  - Instala `requirements-desktop.txt`, corre `python build_desktop.py`, valida `py_compile` y sube `dist/` como artifact.
  - Validación de fallback: ejecuta `python steam_deals_web.py --no-open --help` para confirmar ruta local de mitigación disponible.
  - Evidencia inicial: run exitoso `24487556896` en `main` para Linux y macOS.

### Runbook rápido (manual) para cerrar P2

> Si necesitas el flujo completo paso a paso por plataforma, usa primero los runbooks en `docs/runbooks/`.

Usa esta secuencia en host nativo Linux y macOS. Copia/pega los resultados en `PENDIENTES.md` (Bitácora Cross-Platform por OS).

> Estado actual: este runbook queda **preparado para ejecución posterior**. En la iteración actual no se ejecutó validación manual en host nativo Linux/macOS por no contar con ese host; la evidencia disponible es CI parcial (run `24487556896`) y validación avanzada Linux en entorno local documentada en `PENDIENTES.md`.

> Nota de capacidad: si tu wishlist real es muy grande (por ejemplo 2K+ juegos), el smoke funcional Linux no debe tratarse como prueba corta; conviene reservar una ventana amplia antes de ejecutarlo.

#### Linux (Ubuntu LTS)

```bash
python3 --version && python3 -m pip --version
python3 -m pip install -r requirements-desktop.txt
python3 build_desktop.py
./dist/SteamToolsDesktop
python3 steam_deals_web.py --no-open --port 8080
```

Checklist de salida (esperado):
- build OK con artefacto en `dist/`
- ventana nativa abre
- preflight + run de prueba + generación de `.md/.html/.csv`
- cierre limpio (sin procesos colgados)
- fallback web accesible en `http://127.0.0.1:8080`

#### macOS

```bash
python3 --version && python3 -m pip --version
python3 -m pip install -r requirements-desktop.txt
python3 build_desktop.py
open dist/SteamToolsDesktop.app
python3 steam_deals_web.py --no-open --port 8080
```

Comandos de soporte (si aplica):

```bash
xattr -dr com.apple.quarantine dist/SteamToolsDesktop.app
codesign --verify --deep --strict --verbose=2 dist/SteamToolsDesktop.app
```

Checklist de salida (esperado):
- build OK con `.app` en `dist/`
- app abre localmente
- preflight + run de prueba + generación de `.md/.html/.csv`
- cierre limpio (sin procesos colgados)
- fallback web accesible en `http://127.0.0.1:8080`
- notas de quarantine/codesign registradas cuando apliquen

Planes y pendientes unificados: `PENDIENTES.md`.

## Mapa de módulos y entrypoints

### Núcleo y superficies

- `steam_deals_generator.py`
  - Engine principal de Steam Deals.
  - Orquesta analisis, exportaciones y flujo CLI.
- `steam_deals_config.py`
  - Boundary de config/CLI: carga/guardado de config, argparse y fallback interactivo reutilizable y testeable.
- `steam_deals_prices.py`
  - Dominio de precios Steam: cache por `steam_id`, fetch batch con fallback individual y normalizacion del shape de deals.
- `steam_deals_run_output.py`
  - Slice de salida/orquestacion: nombres de archivos, contexto previo, escritura de artefactos y resumen final del run.
- `steam_deals_runtime_reporting.py`
  - Contrato runtime compartido: symbols Unicode-safe, estilos ANSI, step/progress y eventos consumidos por web/SSE.
- `steam_deals_enrichment.py`
  - Fetchers/caches de enrichment: reviews, Steam Deck, ProtonDB, anti-cheat, tags y achievements con helpers reutilizables.
- `steam_deals_presentation.py`
  - Helpers puros de presentacion: badges, grouping por tier/tag y formateos reutilizados por los renderers.
- `steam_deals_scheduler.py`
  - Bucle programado CLI: parseo de `--schedule`, loop por intervalos y manejo suave de interrupciones/errores.
- `steam_deals_notifications.py`
  - Frontera de notificaciones: resumen notable del run y envios soft-fail para Telegram/Discord.
- `steam_deals_steam_api.py`
  - Adaptador de Steam account/profile/sale: resolucion de vanity/profile, wishlist, owned games, compare, family JSON y evento activo.
- `steam_deals_watchlist.py`
  - Frontera compartida de watchlist: I/O local, comando CLI y seleccion de alertas reutilizable desde generator/web.
- `steam_deals_itad.py`
  - Integracion/adaptador de IsThereAnyDeal: lookup, minimos historicos, mejores precios y bundles activos con soft-fail tolerante.
- `steam_deals_history.py`
  - Logica de historial/comparacion/tendencias: fallback al MD anterior, snapshots de runs y trend formatting local.
- `steam_deals_filters.py`
  - Logica pura de filtros/selection: filtros CLI y seleccion por genero para reutilizar sin tocar orchestration.
- `steam_deals_hltb.py`
  - Logica pura de HLTB/matching: parseo del CSV, normalizacion de titulos, fuzzy matching y cruce HLTB × deals.
- `steam_deals_recommendations.py`
  - Logica pura de scoring/recommendations: value score, top picks, budget picks y gift ideas.
- `steam_deals_web.py`
  - Entry point principal de UX para Steam Deals.
  - Sirve la UI local, valida requests y coordina ejecuciones largas por SSE.
- `payday2_dlc_tracker.py`
  - Engine/CLI de PAYDAY 2.
  - Genera el plan de compra y mantiene el flujo standalone del tracker.
- `payday2_web.py`
  - Dashboard web standalone para PAYDAY 2.
  - Sirve UI local y ejecuta refresh del tracker con progreso en vivo.
- `steam_tools_desktop.py`
  - Wrapper desktop con `pywebview`.
  - Reutiliza `steam_deals_web.py` y hace fallback al navegador con aviso visible en la UI si falta backend nativo o falla la ventana nativa.
- `build_desktop.py`
  - Build unificado para empaquetar la superficie desktop.

### Infraestructura compartida

- `shared_web_infra.py`
  - Helpers compartidos para server local: respuestas HTTP, JSON defensivo, assets de texto, subprocess y SSE.
  - Evita duplicación entre `steam_deals_web.py` y `payday2_web.py`.
- `web/steam_deals/`
  - Assets HTML/CSS/JS servidos por `steam_deals_web.py`.
- `web/payday2/`
  - Assets HTML/CSS/JS servidos por `payday2_web.py`.

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
| `--max-workers` | Workers de fetch paralelo para enrichment (default: 12; recomendado 12-16) |

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
