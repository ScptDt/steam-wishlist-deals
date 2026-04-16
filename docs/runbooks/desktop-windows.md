# Runbook Desktop Windows

Runbook manual para validar el wrapper desktop de Steam Tools en Windows.

## Precondiciones

- Sesion interactiva normal (Console o RDP), no servicio.
- Python 3 disponible.
- PowerShell funcional.
- Microsoft Edge WebView2 Runtime instalado o validable manualmente.

## 1. Preparar entorno

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-desktop.txt
```

## 2. Ejecutar Desktop Doctor

```powershell
python .\steam_tools_desktop.py --doctor
```

Buscar especialmente:
- `Windows WebView2 Runtime`
- `Sesion Windows`
- `PyInstaller`
- `Artefacto desktop`

Si el doctor avisa sobre WebView2, validarlo manualmente en Apps instaladas antes de seguir.

## 3. Build desktop

Opcion directa:

```powershell
python .\build_desktop.py
```

Opcion wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

Esperado:
- `dist\SteamToolsDesktop.exe`

## 4. Abrir el ejecutable

```powershell
.\dist\SteamToolsDesktop.exe
```

Esperado:
- UI visible
- API local respondiendo
- sin cierre inmediato

## 5. Smoke reproducible rapido

```powershell
powershell -ExecutionPolicy Bypass -File .\smoke_test_windows.ps1
```

Esperado:
- `SMOKE_OK`

## 6. Smoke funcional minimo manual

Dentro de la UI desktop:

1. correr **Doctor desktop**
2. correr **Probar config**
3. ejecutar un run real
4. verificar `.md`, `.html`, `.csv`
5. cerrar la app

## 7. Fallback web (mitigacion)

Si el backend nativo no abre correctamente, esperar fallback a navegador o levantar manualmente la UI web:

```powershell
python .\steam_deals_web.py --no-open --port 8080
```

## 8. Evidencia minima a registrar

- build OK/FAIL
- `dist\SteamToolsDesktop.exe` presente o no
- apertura local OK/FAIL
- resultado del smoke script (`SMOKE_OK` / `SMOKE_FAIL`)
- outputs `.md`, `.html`, `.csv`
- cierre limpio
- notas de WebView2 o fallback browser

## Problemas comunes

### Falta WebView2

Validar manualmente `Microsoft Edge WebView2 Runtime` en Apps instaladas. Sin eso, el backend nativo puede fallar o caer a navegador.

### Sesion no interactiva

No tomar una ejecucion como servicio como validacion final del desktop. Repetir en Console o RDP interactivo.

### Solo smoke rapido disponible

`smoke_test_windows.ps1` es evidencia util de arranque/API/cierre limpio, pero no reemplaza el smoke funcional completo dentro de la UI.
