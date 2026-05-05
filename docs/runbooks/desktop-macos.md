# Runbook Desktop macOS

Runbook manual para validar el wrapper desktop de Steam Tools en macOS.

## Precondiciones

- Host macOS nativo con sesion grafica local.
- Python 3 funcional.
- Command Line Tools disponibles o instalables con `xcode-select --install`.
- Este runbook no automatiza firma, notarizacion ni cambios persistentes del sistema.

## Modelo de evidencia y fase del track

- Este runbook cubre la **Fase 3 — macOS native-host closure**.
- La fase macOS solo debe tomarse como cierre cuando exista **host nativo** y se valide desde la `.app` local.
- La evidencia de Web UI/source o incluso la evidencia Linux/Windows **no sustituye** la evidencia nativa de macOS.
- La **Fase 1** (Linux desktop binario) va primero; la **Fase 2** (paridad compartida/readiness) prepara el terreno antes del cierre final en macOS.

## Estado actual del checklist P2

- Estado: bloqueado hasta contar con host macOS nativo en sesion grafica local.
- No usar CI, Linux, Windows, source mode ni fallback web como sustituto de la `.app`.
- Cuando haya host, ejecutar solo el smoke mínimo con `https://steamcommunity.com/id/joseluis12351`; no usar `BG00G` salvo objetivo explícito de performance/stress.
- Registrar solo deltas/incidencias en `BITACORA.md`; mantener en `PENDIENTES.md` el resumen de estado.

## 1. Preparar entorno

```bash
python3 --version && python3 -m pip --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt
```

## 2. Ejecutar Desktop Doctor

```bash
python steam_tools_desktop.py --doctor
```

Buscar especialmente:
- `Backend nativo macOS`
- `Tooling macOS local`
- `Sesion macOS`
- `Artefacto desktop`

Si faltan modulos PyObjC, instalar manualmente en `.venv`:

```bash
python -m pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit
```

## 3. Build desktop

```bash
python build_desktop.py
```

Esperado:
- `dist/SteamToolsDesktop.app`

## 4. Abrir la app localmente

```bash
open dist/SteamToolsDesktop.app
```

Esperado:
- la app abre localmente
- UI visible
- sin crash inmediato

## 5. Smoke funcional minimo

Dentro de la app:

1. correr **Doctor desktop** si quieres una segunda validacion desde la UI
2. correr **Probar config**
3. lanzar un run pequeño con `https://steamcommunity.com/id/joseluis12351`
4. durante un run suficientemente largo, probar **Detener** una vez solo si ese comportamiento cambió o falta evidencia de la build actual
5. verificar `.md`, `.html`, `.csv` y, si aplican, `.json`/`share.html`
6. probar **Copiar log** o confirmar fallback accionable sin crash
7. cerrar la app

Esperado:
- preflight OK
- run OK
- outputs generados
- cierre limpio

## 6. Gatekeeper / quarantine / codesign

Si la app local no abre por cuarentena:

```bash
xattr -l dist/SteamToolsDesktop.app
```

Solo si corresponde a una prueba local controlada:

```bash
xattr -dr com.apple.quarantine dist/SteamToolsDesktop.app
```

Si necesitas validar firma local:

```bash
codesign --verify --deep --strict --verbose=2 dist/SteamToolsDesktop.app
```

## 7. Fallback web (mitigacion)

Para validar el modo degradado sin romper la app nativa, fuerza el fallback desde el launcher desktop:

```bash
STEAM_TOOLS_FORCE_WEB_FALLBACK=1 dist/SteamToolsDesktop.app/Contents/MacOS/SteamToolsDesktop
```

Alternativa equivalente en source mode:

```bash
python steam_tools_desktop.py --force-web-fallback
```

Esperado:
- server local en `127.0.0.1`
- navegador abierto con `?desktop_fallback=1&reason=forced-web-fallback`
- aviso de fallback desktop visible en la UI
- no se intenta abrir ventana nativa en este modo forzado

Si la ventana nativa no abre de forma no forzada:

```bash
python steam_deals_web.py --no-open --port 8080
```

## 8. Evidencia minima a registrar

- host macOS y tipo de sesion grafica
- build OK/FAIL
- `.app` generado o no
- apertura local OK/FAIL
- texto exacto del error si Gatekeeper o runtime bloquean
- Doctor/Probar config OK/FAIL
- outputs `.md`, `.html`, `.csv` y evidencia adicional `.json`/`share.html` si aplica
- **Copiar log** OK/FAIL/no probado
- fallback web forzado o no forzado si aplica
- cierre limpio
- procesos colgados sí/no
- notas de cuarentena/codesign/notarizacion si aplican

## Problemas comunes

### SSH/headless

No cerrar validacion nativa desde una sesion SSH. La `.app` debe probarse en sesion grafica local.

### Faltan modulos Cocoa/WebKit

Revalidar con:

```bash
python -c 'import objc, Cocoa, WebKit'
```

### Gatekeeper

Primero inspeccionar con `xattr -l`; no automatizar remocion de cuarentena como paso por defecto.
