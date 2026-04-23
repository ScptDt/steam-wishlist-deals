# Runbook Desktop Linux

Runbook manual para validar el wrapper desktop de Steam Tools en Linux.

## Precondiciones

- Sesion grafica normal (no root) para la validacion final de ventana nativa.
- Python 3 disponible.
- Si Debian/Ubuntu marca PEP 668, usar `.venv` del repo.
- Este runbook no instala paquetes del sistema automaticamente.

## Modelo de evidencia y fase del track

- Este runbook cubre la **Fase 1 — Linux desktop binario (cierre prioritario)**.
- La evidencia que cierra esta fase debe salir del **binario desktop** en sesion grafica normal.
- Una corrida desde Web UI/source ayuda a validar generator, performance y UX compartida, pero **no sustituye** la evidencia del binario para cerrar Linux desktop.
- La **Fase 2** (paridad compartida/readiness) y la **Fase 3** (macOS native-host closure) van despues de este cierre Linux.

## Flujo recomendado

### 1. Preparar entorno local

```bash
python3 --version && python3 -m pip --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt
```

Esperado:
- `.venv` activa
- `pywebview[qt]`, `PyInstaller`, `QtPy`, `PyQt6` y `PyQt6-WebEngine` instalados

## 2. Ejecutar Desktop Doctor

```bash
python steam_tools_desktop.py --doctor
```

Buscar especialmente:
- `Entorno Python`
- `Backend nativo Linux (Qt)`
- `Display stack Linux`
- `Host tools Linux para PyInstaller`
- `Usuario/Sesion grafica`

Si hay Wayland y problemas de Qt/pywebview, probar temporalmente:

```bash
export QT_QPA_PLATFORM=xcb
```

## 3. Build desktop

```bash
python build_desktop.py
```

Esperado:
- artefacto en `dist/SteamToolsDesktop`
- sin errores fatales de PyInstaller

Si el doctor o el log del build mencionan plugins Qt / `libtiff.so.5`, revisar primero el warning antes de seguir cerrando validacion.

## 4. Abrir el artefacto nativo

```bash
./dist/SteamToolsDesktop
```

Esperado:
- ventana nativa visible
- server local arriba
- sin fallback inmediato al navegador

> En la validacion local mas reciente, una sesion grafica KDE normal (no root) abrio la ventana nativa sin necesitar `QT_QPA_PLATFORM=xcb`. Si tu stack Wayland/Qt falla, manten `xcb` solo como workaround puntual, no como requisito por defecto.

## 5. Smoke funcional minimo

> Nota practica: con wishlists muy grandes (por ejemplo 2K+ juegos) este smoke deja de ser una validacion corta. Reservar una ventana amplia; con cache frio puede tardar bastante antes de generar outputs finales.

> Mitigacion recomendada para wishlists grandes: antes del run largo, calienta `prices_cache.json` desde terminal con `--warm-cache`. Esto evita perder tiempo en una ventana desktop abierta solo esperando fetch inicial.

```bash
source .venv/bin/activate
STEAM_DEALS_CACHE_DIR="$HOME/.cache/steam_deals" python3 steam_deals_generator.py --vanity gaben --warm-cache
```

> `gaben` es solo un ejemplo público. Reemplázalo por tu vanity real, la URL completa de tu perfil o tu Steam ID de 17 dígitos. No copies placeholders literales como `TU_VANITY_URL`.

Esperado:
- se actualiza `prices_cache.json` sin abrir la UI
- se crea un log legible en `<cache>/logs/` (por ejemplo `~/.cache/steam_deals/logs/` cuando usas `STEAM_DEALS_CACHE_DIR`)
- sale sin generar `.md`, `.html`, `.json` ni `.csv`
- el siguiente run desktop reutiliza el cache persistente y no depende de rutas temporales `_MEI`

Dentro de la UI desktop:

1. correr **Doctor desktop** si quieres confirmar estado desde la UI
2. correr **Probar config**
3. lanzar un run real
4. durante un run suficientemente largo, probar **Detener** una vez para confirmar que no duplica mensajes y que no deja procesos colgados
5. esperar outputs `.md`, `.html`, `.csv`
6. cerrar la app

Esperado:
- preflight OK
- run sin crash
- si usas **Detener**, solo aparece una vez `Solicitando detener ejecucion...` y luego un estado veraz de parada
- outputs generados
- cierre limpio sin procesos colgados

> Nota actual del Track Stop: la validación manual en browser ya confirmó que `Detener` deja de duplicar mensajes y sí para el run. La confirmación equivalente dentro del desktop binario queda pendiente mientras el launcher/fallback sigue estabilizándose.

Tip operativo:
- si aparece un traceback largo o warning dificil de copiar, usa los botones **Copiar log** / **Descargar log (.txt)** dentro de la UI antes de cerrar la app

### Señales a observar en un run largo real

Durante un caso grande (wishlist real / smoke largo), conviene guardar evidencia de:

- `Refresh candidates: X (N nuevos, M stale)`
- `Batches degradados por HTTP 400: ...` si aparece degradacion del batching
- `Fallback individual aplicado a ... juegos en ... tandas`
- artifacts generados al final (`.md`, `.html`, `.csv` para cierre desktop; `share.html/.json` como evidencia adicional)

### Checklist de cierre Linux desktop binario

Usa esta lista solo para la evidencia que realmente cierra la **Fase 1**:

- [ ] `python steam_tools_desktop.py --doctor` en `.venv` sin FAIL reales
- [ ] Build local del desktop ejecutado (`python build_desktop.py`) y artefacto `dist/SteamToolsDesktop` presente
- [ ] Binario abierto en sesion grafica normal (no root)
- [ ] Ventana nativa visible sin crash inmediato
- [ ] **Probar config** ejecutado desde la UI
- [ ] Run largo completado desde el binario desktop (no desde Web UI/source)
- [ ] Artefacts confirmados: `.md`, `.html`, `.csv`
- [ ] `share.html` / `.json` guardados como evidencia adicional si aplican (no sustituyen `.csv` ni cierran Linux por sí solos)
- [ ] Sin fallback no deseado al navegador (o fallback documentado si ocurrio)
- [ ] Cierre limpio de la app
- [ ] Sin procesos colgados despues del cierre
- [ ] Evidencia detallada registrada en `BITACORA.md` con comando, resultado y workaround si hizo falta; dejar en `PENDIENTES.md` solo el resumen que afecte estado o próximo paso

> `--warm-cache` y una corrida larga desde Web UI/source cuentan como preparación y evidencia funcional del generator/Track Performance, pero no sustituyen el cierre final del desktop Linux: para cerrar P2 sigue haciendo falta repetir la corrida dentro del binario y confirmar `.csv` + cierre limpio.

### Plantilla sugerida para la entrada final de bitácora

- Host/sesión gráfica:
- Comandos ejecutados:
- Doctor desktop: OK/FAIL
- Build desktop: OK/FAIL
- Apertura nativa: OK/FAIL
- `Probar config`: OK/FAIL
- Run largo desde binario: OK/FAIL
- Artefactos confirmados: `.md` / `.html` / `.csv`
- Evidencia adicional: `share.html` / `.json`
- Fallback al navegador: sí/no
- Cierre limpio: sí/no
- Procesos colgados: sí/no
- Workarounds usados:
- Incidencias observadas:

## 6. Fallback web (mitigacion)

Si la ventana nativa no abre o cae el backend Qt:

```bash
python steam_deals_web.py --no-open --port 8080
```

Esperado:
- Web UI disponible en `http://127.0.0.1:8080`
- banner/modo fallback visible si vienes desde desktop

## 7. Evidencia minima a registrar

- comando ejecutado
- resultado (OK/FAIL)
- ruta del artefacto
- si la ventana nativa abrio o no
- si hubo fallback al navegador
- si se generaron `.md`, `.html`, `.csv`
- si quedaron procesos colgados
- workaround usado (`.venv`, `QT_QPA_PLATFORM=xcb`, paquetes distro, etc.)

## Problemas comunes

### PEP 668 / externally-managed-environment

Usar `.venv`; no usar `--break-system-packages` como ruta normal.

### Falta backend Qt

Confirmar primero deps Python del repo:

```bash
python -c 'import qtpy, PyQt6, PyQt6.QtWebEngineWidgets'
```

Si eso falla, reinstalar `requirements-desktop.txt` dentro de `.venv`.

### Qt falla en Wayland

Reintentar con:

```bash
export QT_QPA_PLATFORM=xcb
```

Si en KDE/X11 o en una sesion grafica normal el artefacto ya abre sin ese flag, no lo fuerces en la evidencia final.

### Validacion hecha como root

No cerrar el pendiente final de UX nativa con evidencia solo de root; repetir desde tu usuario grafico normal.

### Cache / logs no persisten entre lanzadas

El desktop actualizado ya no debe guardar cache dentro de `_MEI`. Si quieres calentar cache o dejar evidencia de un run largo fuera de la UI:

```bash
source .venv/bin/activate
STEAM_DEALS_CACHE_DIR="$HOME/.cache/steam_deals" python3 steam_deals_generator.py --vanity gaben --warm-cache
```

Opcionalmente puedes separar logs con:

```bash
STEAM_DEALS_LOG_DIR="$HOME/logs/steam-deals" python3 steam_deals_generator.py --vanity gaben --warm-cache
```
