# Runbook Desktop Linux

Runbook manual para validar el wrapper desktop de Steam Tools en Linux.

## Precondiciones

- Sesion grafica normal (no root) para la validacion final de ventana nativa.
- Python 3 disponible.
- Si Debian/Ubuntu marca PEP 668, usar `.venv` del repo.
- Este runbook no instala paquetes del sistema automaticamente.

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

## 5. Smoke funcional minimo

> Nota practica: con wishlists muy grandes (por ejemplo 2K+ juegos) este smoke deja de ser una validacion corta. Reservar una ventana amplia; con cache frio puede tardar bastante antes de generar outputs finales.

Dentro de la UI desktop:

1. correr **Doctor desktop** si quieres confirmar estado desde la UI
2. correr **Probar config**
3. lanzar un run real
4. esperar outputs `.md`, `.html`, `.csv`
5. cerrar la app

Esperado:
- preflight OK
- run sin crash
- outputs generados
- cierre limpio sin procesos colgados

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

### Validacion hecha como root

No cerrar el pendiente final de UX nativa con evidencia solo de root; repetir desde tu usuario grafico normal.
