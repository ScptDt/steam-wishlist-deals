# Runbook Desktop Windows

Runbook manual para validar el wrapper desktop de Steam Tools en Windows.

## Precondiciones

- Sesion interactiva normal (Console o RDP), no servicio.
- Python 3 disponible.
- PowerShell funcional.
- Microsoft Edge WebView2 Runtime instalado o validable manualmente.

## Modelo de evidencia y fase del track

- Este runbook aporta evidencia de apoyo dentro de la **Fase 2 — Paridad compartida y readiness**.
- Windows sirve como baseline util para launcher, doctor, outputs y fallback, pero **no sustituye** el cierre Linux/macOS exigido por P2.
- La **Fase 1** sigue siendo Linux desktop binario; la **Fase 3** sigue siendo macOS native-host closure.
- No usar un smoke Windows exitoso para cerrar macOS ni para repetir evidencia Linux ya capturada; registra solo deltas/incidencias.

## Checklist visible para prueba Windows

Usa esta checklist como guía principal. Incluye lo nuevo de `wishlist_hygiene` y las validaciones previas de Windows/Desktop/Web/Share. Las secciones históricas del runbook siguen abajo como referencia resumida.

### A. Confirmar versión y preparar entorno

```powershell
git pull
git log -1 --oneline
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt
```

Comprobar:
- [ ] `git log -1 --oneline` muestra `2f3069c feat: surface wishlist hygiene in reports` o un commit posterior que lo incluya.
- [ ] `git log --oneline -5` contiene también `f5cceed feat: surface wishlist hygiene in web ui` y `c1c128d feat: expose wishlist hygiene in json`.
- [ ] Python 3 funciona desde PowerShell.
- [ ] `.venv` activa sin errores.
- [ ] Dependencias desktop instalan sin errores bloqueantes.
- [ ] La sesión es interactiva normal (Console/RDP), no servicio.
- [ ] WebView2 Runtime está instalado o se puede validar manualmente en Apps instaladas.

### B. Tests rápidos sin red

```powershell
.\.venv\Scripts\python.exe -m py_compile renderers\markdown_renderer.py renderers\html_renderer.py steam_deals_generator.py tests\test_generator_logic.py
.\.venv\Scripts\python.exe -m unittest tests.test_generator_logic.WishlistHygieneTests tests.test_generator_logic.RunOutputTests
```

Esperado:

```text
Ran 8 tests
OK
```

Regresión opcional para reportes/Share/Web/Desktop helpers:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_generated_files_serving tests.test_web_assets tests.test_desktop_share
```

Comprobar:
- [ ] Tests terminan en `OK`.
- [ ] Si aparece warning benigno de Steam 403/fallback público pero los tests pasan, no invalida esta validación.

### C. Smoke CLI chico de reportes generados

No usar `BG00G` ni `--no-cache` para este smoke normal.

```powershell
$out = "$env:TEMP\steam-deals-hygiene-test"
New-Item -ItemType Directory -Force $out | Out-Null

.\.venv\Scripts\python.exe steam_deals_generator.py `
  --vanity "https://steamcommunity.com/id/joseluis12351" `
  --output $out `
  --discount 0 `
  --top 10

Get-ChildItem $out
```

Comprobar:
- [ ] La corrida termina sin traceback.
- [ ] Se generan `.md`, `.html`, `.json` y `share.html`.
- [ ] Si se pidió CSV en otra prueba, también aparece `.csv`.
- [ ] No se versionan los reportes generados.

### D. Revisar `wishlist_hygiene` en JSON

```powershell
$json = Get-ChildItem $out -Filter *.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$data = Get-Content $json.FullName -Raw | ConvertFrom-Json

$data.summary.wishlist_hygiene_count
$data.wishlist_hygiene.items | Select-Object appid,name,signals,action,advisory_only
```

Comprobar:
- [ ] Existe `wishlist_hygiene` en el JSON nuevo.
- [ ] Existe `summary.wishlist_hygiene_count`.
- [ ] Si hay items, `action` es `review` y `advisory_only` es `True`.
- [ ] Si `items` está vacío, Markdown/HTML/Web UI deben ocultar la sección. Eso es correcto.
- [ ] Si `wishlist_hygiene` no existe, probablemente se abrió un reporte viejo o falta actualizar con `git pull`.

### E. Revisar Markdown generado

Abre el `.md` generado desde `$out`.

Si `wishlist_hygiene.items` tiene elementos, comprobar:
- [ ] Aparece `## 🧹 Revisar wishlist`.
- [ ] Aparece `advisory-only`.
- [ ] Aparece `Solo revisión`.
- [ ] El texto deja claro que no borra, no auto-excluye y no cambia el score.
- [ ] La tabla muestra juego, señales, motivos y acción.

Si `wishlist_hygiene.items` está vacío:
- [ ] No aparece sección vacía ni ruido de `Revisar wishlist`.

Regresión visible en Markdown:
- [ ] Top Picks siguen renderizando.
- [ ] Colecciones recomendadas siguen renderizando si hay datos.
- [ ] Recomendaciones personalizadas siguen renderizando si hay datos.
- [ ] Watchlist Alerts siguen renderizando si hay datos.
- [ ] Presupuesto sigue renderizando si se corre con `--budget`.
- [ ] Tablas de descuentos no se rompen.

### F. Revisar HTML generado

Abre el `.html` generado en Edge/Chrome.

Si `wishlist_hygiene.items` tiene elementos, comprobar:
- [ ] Aparece sección `Revisar wishlist`.
- [ ] Aparece badge/copy `Solo revisión`.
- [ ] Muestra señales como biblioteca, Family, HLTB, otra tienda, catálogo local o AppID inválido según aplique.
- [ ] Links a Steam aparecen solo para AppID numérico.
- [ ] No hay botones para borrar, quitar, auto-excluir, comprar ni abrir carrito.
- [ ] Textos raros con `<`, `>`, `&` se ven escapados y no se ejecutan como HTML.

Si `wishlist_hygiene.items` está vacío:
- [ ] No aparece sección vacía de `Revisar wishlist`.

Regresión visible en HTML:
- [ ] Filtro de búsqueda funciona.
- [ ] Filtro de precio/descuento funciona.
- [ ] Ordenar columnas funciona.
- [ ] Top Picks se ven y sus filtros de recomendación funcionan.
- [ ] Botones Share abren modal.
- [ ] Modal Share cierra por botón, click fuera y `Esc`.
- [ ] `Copiar link steamtools://`, `Copiar link de Steam` y `Abrir en Steam` funcionan o muestran fallback claro.

### G. Revisar `share.html`

Abre `Steam Deals Share <fecha>.html` o el `share.html` generado.

Comprobar:
- [ ] Abre sin errores visuales.
- [ ] Top Picks o filas de deals muestran botón Share cuando aplica.
- [ ] `Copiar link steamtools://` funciona o muestra fallback claro.
- [ ] `Copiar link de Steam` funciona o muestra fallback claro.
- [ ] `Abrir en Steam` abre link/fallback esperado.
- [ ] Payload mantiene campos clave: `appid`, `name`, `price`, `price_original`, `discount`, `url`.

### H. Web UI directa

```powershell
.\.venv\Scripts\python.exe steam_deals_web.py
```

En navegador:
- [ ] Ejecutar preflight / Probar config.
- [ ] Ejecutar Steam Deals con `https://steamcommunity.com/id/joseluis12351`.
- [ ] Ver progreso sin congelamiento de SSE/log.
- [ ] Al terminar, revisar `Resumen de tu última ejecución`.
- [ ] Abrir `Acciones y recomendaciones del último reporte`.
- [ ] Abrir links a MD/HTML/JSON/share.
- [ ] Top Picks, Share, historial/dashboard y acciones técnicas siguen funcionando si hay datos.

Wishlist hygiene en Web UI:
- [ ] Si el JSON trae `wishlist_hygiene.items` con datos, aparece `Revisar wishlist`.
- [ ] Muestra máximo 3 sugerencias.
- [ ] Si hay más, muestra texto tipo `N más en el JSON completo`.
- [ ] Badge/copy `Solo revisión` visible.
- [ ] No hay acción destructiva ni auto-exclusión.
- [ ] Si `items` está vacío, la sección se oculta.

### I. Desktop Doctor en source mode

```powershell
.\.venv\Scripts\python.exe steam_tools_desktop.py --doctor
```

Comprobar:
- [ ] Reporta Windows/sesión usable.
- [ ] Reporta WebView2 o da instrucción clara para instalar/validar.
- [ ] Reporta PyInstaller/build tools de forma entendible.
- [ ] No oculta `FAIL` reales ni termina con traceback.
- [ ] No aparecen secretos, rutas sensibles o tracebacks largos en UI/salida pública.

### J. Desktop source mode

```powershell
.\.venv\Scripts\python.exe steam_tools_desktop.py
```

Comprobar:
- [ ] Abre ventana nativa o fallback navegador claro.
- [ ] UI no queda en blanco.
- [ ] App no se cierra sola.
- [ ] Server/API local responde en `127.0.0.1`.
- [ ] Ejecutar **Doctor desktop** desde la UI.
- [ ] Ejecutar **Probar config**.
- [ ] Correr Steam Deals con `joseluis12351`.
- [ ] Outputs se generan y los links abren.
- [ ] HTML interactivo y Share HTML abren.
- [ ] `Copiar log` funciona o muestra fallback accionable sin crash.
- [ ] `Carpeta de reportes` funciona si aparece.
- [ ] Cerrar app termina limpio, sin procesos rotos visibles.

### K. Build desktop opcional / `.exe`

Solo si quieres validar binario Windows.

```powershell
.\.venv\Scripts\python.exe build_desktop.py
```

Alternativa:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

Comprobar:
- [ ] Build termina OK.
- [ ] Existe `dist\SteamToolsDesktop.exe`.
- [ ] No versionar `build/`, `dist/`, `*.spec` ni artefactos generados.

Abrir:

```powershell
.\dist\SteamToolsDesktop.exe
```

Repetir checks clave:
- [ ] Abre UI nativa o fallback claro.
- [ ] Genera reporte chico.
- [ ] Outputs abren.
- [ ] Share funciona.
- [ ] Wishlist hygiene se comporta igual que en Web UI/MD/HTML si hay items.
- [ ] Cierra limpio.

### L. Smoke script Windows opcional

```powershell
powershell -ExecutionPolicy Bypass -File .\smoke_test_windows.ps1
```

Comprobar:
- [ ] Resultado `SMOKE_OK`.
- [ ] Si sale `SMOKE_FAIL` o se cuelga, detener y registrar salida corta.

### M. Fallback web forzado

Con binario:

```powershell
$env:STEAM_TOOLS_FORCE_WEB_FALLBACK = "1"
.\dist\SteamToolsDesktop.exe
Remove-Item Env:\STEAM_TOOLS_FORCE_WEB_FALLBACK
```

Alternativa en source mode:

```powershell
.\.venv\Scripts\python.exe steam_tools_desktop.py --force-web-fallback
```

Comprobar:
- [ ] Abre navegador local.
- [ ] URL incluye `?desktop_fallback=1&reason=forced-web-fallback`.
- [ ] La UI muestra aviso de fallback desktop.
- [ ] Server queda en `127.0.0.1`.
- [ ] No intenta abrir ventana nativa cuando el fallback es forzado.

### N. Web UI directa si el desktop falla

```powershell
.\.venv\Scripts\python.exe steam_deals_web.py --no-open --port 8080
```

Comprobar:
- [ ] Abrir `http://127.0.0.1:8080` manualmente.
- [ ] UI usable como fallback temporal.
- [ ] Registrar que es fallback, no cierre completo del desktop nativo.

### O. PAYDAY 2 opcional si quieres revisar la app completa

```powershell
.\.venv\Scripts\python.exe payday2_web.py
```

Comprobar:
- [ ] UI abre.
- [ ] **Actualizar datos** normal respeta TTL/cache.
- [ ] No usar `--no-cache` salvo que pruebes explícitamente **Forzar catálogo**.
- [ ] Marcado manual de owned no se pierde.
- [ ] Steam Deals y PAYDAY 2 no se mezclan ni rompen navegación.

### P. No hacer en esta prueba

- [ ] No usar `BG00G` como smoke rápido.
- [ ] No usar `--no-cache` ni cold-cache largo.
- [ ] No hacer benchmark/performance salvo aprobación explícita y cache/logs aislados.
- [ ] No commitear `output/`, `logs/`, `.cache/`, `build/`, `dist/`, reportes `Steam Deals*`, `PAYDAY2_Plan_de_Compra.*` ni `*.spec`.
- [ ] No cerrar macOS ni Linux con evidencia Windows.
- [ ] No continuar si aparece seguridad rota: secretos, paths sensibles, traceback público, server no-local o POST sin protección.
- [ ] No repetir muchas corridas si falla algo; detener y reportar.

### Q. Evidencia que debes mandar

Manda resumen corto, no logs completos:
- [ ] Windows version y si fue Console/RDP.
- [ ] Resultado de `py -3 --version`.
- [ ] Último commit probado (`git log -1 --oneline`).
- [ ] WebView2 OK/FAIL/no claro.
- [ ] Resultado de tests rápidos (`8 OK` o error corto).
- [ ] Resultado de `python .\steam_tools_desktop.py --doctor`.
- [ ] Build OK/FAIL y si existe `dist\SteamToolsDesktop.exe` si hiciste build.
- [ ] Resultado de `smoke_test_windows.ps1` (`SMOKE_OK`/`SMOKE_FAIL`) si lo corriste.
- [ ] Perfil usado (`joseluis12351` para smoke rápido).
- [ ] Tiempo aproximado del run y si completó.
- [ ] Outputs generados: `.md`, `.html`, `.csv`, `.json`, `share.html`.
- [ ] Wishlist hygiene: indicar si `wishlist_hygiene.items` estaba vacío, ausente o con datos.
- [ ] Wishlist hygiene: indicar si apareció `Revisar wishlist` en Web UI, Markdown y HTML.
- [ ] HTML interactivo OK/FAIL.
- [ ] Share HTML/modal/link OK/FAIL/no probado.
- [ ] `Copiar log` OK/FAIL/no probado.
- [ ] Fallback web forzado OK/FAIL si lo probaste.
- [ ] Cierre limpio OK/FAIL.
- [ ] Errores cortos o screenshot si falla.

### R. Criterio rápido de PASS/FAIL

PASS si:
- Doctor no bloquea el entorno.
- Si hiciste build, genera `dist\SteamToolsDesktop.exe`.
- App source o exe abre y corre `joseluis12351` hasta generar outputs.
- HTML/Share/log/fallback principal funcionan o fallan con mensaje accionable.
- `wishlist_hygiene` aparece/oculta correctamente según el JSON en Web UI, Markdown y HTML.
- Cierra limpio.

FAIL si:
- Build no genera exe cuando el objetivo era validar binario.
- App crashea, queda en blanco o no levanta server local.
- Preflight/run no inicia o el progreso se congela.
- Outputs esperados faltan.
- `wishlist_hygiene.items` tiene datos pero no aparece `Revisar wishlist` en Web UI/Markdown/HTML.
- `wishlist_hygiene.items` está vacío pero aparece una sección vacía o ruidosa.
- Fallback web no abre o no muestra aviso.
- Se filtran secretos/rutas sensibles/tracebacks largos.
- Quedan procesos rotos o la app no cierra.

## 1. Preparar entorno

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-desktop.txt -c constraints/desktop.txt
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
3. ejecutar Steam Deals con ambos perfiles según objetivo:
   - baseline rápido: `https://steamcommunity.com/id/joseluis12351` para validar flujo corto, Share, colecciones recomendadas y outputs básicos
   - validación larga/stress: `BG00G` solo si el objetivo explícito es performance, stress de outputs, Shuffle con variedad o desktop/binario largo
4. no usar `BG00G` como quick smoke ni con cold-cache accidental; si se usa, aislar cache/logs y registrarlo como medición larga
5. durante un run suficientemente largo, probar **Detener** una vez solo si ese comportamiento cambió o falta evidencia de la build actual
6. verificar `.md`, `.html`, `.csv` y, si aplican, `.json`/`share.html`
7. probar **Copiar log** o confirmar fallback accionable sin crash
8. cerrar la app

## 7. Fallback web (mitigacion)

Para validar el modo degradado sin romper WebView2, fuerza el fallback desde el launcher desktop:

```powershell
$env:STEAM_TOOLS_FORCE_WEB_FALLBACK = "1"
.\dist\SteamToolsDesktop.exe
Remove-Item Env:\STEAM_TOOLS_FORCE_WEB_FALLBACK
```

Alternativa equivalente en source mode:

```powershell
python .\steam_tools_desktop.py --force-web-fallback
```

Esperado:
- server local en `127.0.0.1`
- navegador abierto con `?desktop_fallback=1&reason=forced-web-fallback`
- aviso de fallback desktop visible en la UI
- no se intenta abrir ventana nativa en este modo forzado

Si el backend nativo no abre correctamente de forma no forzada, esperar fallback a navegador o levantar manualmente la UI web:

```powershell
python .\steam_deals_web.py --no-open --port 8080
```

## 8. Evidencia minima a registrar

- build OK/FAIL
- `dist\SteamToolsDesktop.exe` presente o no
- apertura local OK/FAIL
- resultado del smoke script (`SMOKE_OK` / `SMOKE_FAIL`)
- outputs `.md`, `.html`, `.csv`
- perfil usado: `joseluis12351` para smoke rápido y/o `BG00G` para validación larga/stress explícita
- **Copiar log** OK/FAIL/no probado si se valida la UX desktop
- cierre limpio
- notas de WebView2 o fallback browser

## 9. Siguiente ejecucion prioritaria (si estas solo en Windows)

Cuando no hay host nativo Linux/macOS disponible, usa este runbook para mantener avance sin bloqueo:

1. Ejecutar `--doctor` y guardar resultado.
2. Correr build desktop y confirmar `dist\\SteamToolsDesktop.exe`.
3. Ejecutar `smoke_test_windows.ps1` y guardar `SMOKE_OK`/`SMOKE_FAIL`.
4. Hacer smoke funcional minimo manual en UI (preflight + run + outputs + cierre limpio).
5. Registrar evidencia detallada en `BITACORA.md` con fecha, resultado y siguiente paso; si cambia prioridad/estado actual, resumirlo también en `PENDIENTES.md`.

Esto mantiene el proyecto en movimiento mientras la validacion manual Linux/macOS queda en espera de host nativo.

## Problemas comunes

### Falta WebView2

Validar manualmente `Microsoft Edge WebView2 Runtime` en Apps instaladas. Sin eso, el backend nativo puede fallar o caer a navegador.

### Sesion no interactiva

No tomar una ejecucion como servicio como validacion final del desktop. Repetir en Console o RDP interactivo.

### Solo smoke rapido disponible

`smoke_test_windows.ps1` es evidencia util de arranque/API/cierre limpio, pero no reemplaza el smoke funcional completo dentro de la UI.
