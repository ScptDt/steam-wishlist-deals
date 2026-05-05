# Runbook Desktop Constraints

Guía mínima para mantener reproducibles las dependencias desktop sin mezclar upgrades con features.

## Modelo

- `requirements-desktop.txt`: intención humana de dependencias desktop.
- `constraints/desktop.txt`: resolución validada y versionada para CI/builds.
- CI y runbooks deben instalar con ambos archivos:

```bash
python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt
```

## Cuándo tocar constraints

Solo tocar `constraints/desktop.txt` cuando el objetivo explícito sea refrescar dependencias desktop, corregir una incompatibilidad de build/runtime o preparar release.

No hacer:
- no actualizar pins por opportunismo durante features
- no mezclar upgrade de PyInstaller/pywebview/Qt con cambios UX o seguridad
- no usar `latest` implícito en CI desktop

## Proceso de refresh controlado

1. Crear `.venv` limpio en la plataforma objetivo.
2. Instalar intención sin constraints solo para resolver candidatos:
   ```bash
   python -m pip install -r requirements-desktop.txt
   ```
3. Capturar pins relevantes de desktop y actualizar `constraints/desktop.txt`.
4. Reinstalar en `.venv` limpio usando constraints:
   ```bash
   python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt
   ```
5. Validar mínimo:
   ```bash
   python -m py_compile steam_tools_desktop.py steam_deals_web.py build_desktop.py desktop_doctor.py
   python -m unittest tests.test_web_assets tests.test_desktop_doctor tests.test_desktop_share
   python steam_tools_desktop.py --doctor
   ```
6. Si el cambio afecta empaquetado, ejecutar build/smoke dirigido según el runbook de la plataforma.
7. Registrar evidencia en `BITACORA.md` y resumir impacto en `PENDIENTES.md` si cambia el estado.

## Notas por plataforma

- Linux: `constraints/desktop.txt` fija el stack Qt/PyQt validado; las librerías nativas del sistema siguen siendo responsabilidad del host.
- Windows: WebView2 Runtime sigue siendo runtime externo a pip.
- macOS: host nativo sigue bloqueando cierre final; constraints no sustituyen validación de `.app`, Gatekeeper o codesign.
