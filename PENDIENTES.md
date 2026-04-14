# Pendientes (Fuente Unica)

Ultima actualizacion: 2026-04-14

## Regla de Oro

Este archivo es la fuente unica de verdad para:
- pendientes activos
- backlog de features
- plan cross-platform
- estado de ejecucion y bitacora

No se mantienen documentos paralelos de planificacion; este archivo es la unica fuente.

## Estado General

- Objetivo: llevar Steam Tools a una experiencia ultra user friendly y preparada para ejecutable desktop.
- Fase actual: P2 en validacion cross-platform.
- Item activo: validacion build desktop en Linux/macOS.

## Pendientes Priorizados

### P0 - Estabilidad

- [x] Empaquetado con PyInstaller (build inicial) validado en Windows.
- [x] Checklist de release y smoke tests (primera version).

### P1 - UX Ultra Friendly

- [x] Banner de modo: primer setup vs actualizacion.
- [x] Errores accionables por categoria (network/config/rate-limit/encoding).
- [x] Presets de ejecucion (rapido, completo, ahorro).

### P2 - Cross-platform

- [~] Validar build desktop en Linux (Ubuntu LTS). (runbook/checklist reproducible documentado; falta ejecución en host Linux)
- [~] Validar build desktop en macOS (app bundle + apertura local). (runbook/checklist reproducible documentado; falta ejecución en host macOS)
- [x] Documentar dependencias nativas por plataforma para pywebview.

### P3 - Base tecnica y mantenibilidad

- [x] Blindar handlers web: JSON invalido -> 400, validacion de boundaries y errores mas accionables.
- [x] Aclarar `README.md` por superficies: core stdlib, desktop con deps extra y posicionamiento de modulos.
- [x] Separar HTML/CSS/JS embebido de `steam_deals_web.py` y `payday2_web.py`.
- [x] Extraer infraestructura compartida para web local (JSON, SSE, subprocess, server utils).
- [x] Reutilizar la base compartida entre Steam Deals Web y PAYDAY 2 Web.
- [~] Modularizar `steam_deals_generator.py` por dominios (config, adapters, cache, scoring, renderers, orchestration). (fase renderers completada; faltan dominios restantes)
- [x] Agregar smoke tests minimos para web, desktop y PAYDAY 2.
- [x] Agregar tests para logica pura critica (score, filtros, compare, budget, recomendaciones).
- [x] Crear capa shared entre Steam Deals y PAYDAY 2 para config/cache/helpers reutilizables.

Nota actual sobre la capa shared Steam Deals / PAYDAY 2:
- Completado en un primer corte pragmatico: `shared/io_utils.py` + `shared/cache_utils.py` centralizan config JSON, HTTP JSON y helpers genericos de cache reutilizados por `steam_deals_generator.py` y `payday2_dlc_tracker.py`.
- Los formatos de cache/historial siguen siendo propios de cada app cuando corresponde, pero ya sobre helpers compartidos.

Nota actual sobre `steam_deals_generator.py`:
- Estado: modularizacion en progreso por cortes pequeños.
- Avance completado: paquete `renderers/` con extraccion de Markdown, HTML, Share HTML y CSV.
- Integracion completada: barrido CLI/web/desktop validado (imports/renderers/entrypoints).
- Ajuste de robustez: `steam_tools_desktop.py --help` ahora sale de forma inmediata (sin iniciar server/UI).
- Siguiente paso recomendado: continuar extraccion por dominios no-renderer (p. ej. scoring u orchestration) en subtareas atomicas.

### Nota de trabajo futuro - orden sugerido de ejecucion

- 1. Cerrar base actual: cross-platform + README + handlers robustos. ✅
- 2. Separar HTML/CSS/JS embebido. ✅
- 3. Extraer infraestructura compartida para web local. ✅
- 4. Reutilizar la base compartida entre Steam Deals y PAYDAY 2. ✅
- 5. Agregar smoke tests minimos reproducibles para web, desktop y PAYDAY 2. ✅
- 6. Agregar tests de logica pura critica. ✅
- 7. Crear capa shared reutilizable para config/cache/helpers. ✅
- 8. Modularizar `steam_deals_generator.py`. [~ en progreso: renderers completado]

Objetivo de esta secuencia: bajar costo de mantenimiento sin frenar el avance del producto.

## Backlog de Features (Estado)

### Core app

- [x] Eventos estructurados web-run (base: progress/file).
- [x] Preflight de configuracion antes de run.
- [x] Acciones rapidas UX (probar config, limpiar cache, abrir ultimo reporte).
- [x] Reduccion de dependencia parser ANSI en web.
- [x] Clasificacion avanzada de errores y sugerencias accionables.

### Wizard / UX

- [x] Wizard de primer uso y vista de actualizacion.
- [x] Banner persistente de modo (setup/actualizacion).
- [x] Presets y modo "1-click run".

### Desktop (Opcion B)

- [x] Launcher pywebview base (`steam_tools_desktop.py`).
- [x] Build unificado (`build_desktop.py`).
- [x] Wrappers por plataforma (`build_desktop.ps1`, `build_desktop.sh`).
- [x] Smoke tests de ejecutable en Windows.
- [ ] Validacion Linux/macOS.

## Plan Cross-Platform (Consolidado)

### Objetivo

Ejecutar de forma consistente en Windows, macOS y Linux.

### Riesgos

- Dependencias nativas de `pywebview` por OS.
- Diferencias de empaquetado/firma (especialmente macOS).
- Diferencias de encoding y terminal.
- Diferencias de permisos/rutas de salida/cache.

### Estrategia

1. Runtime parity:
- Mantener fallback universal web (`steam_deals_web.py`).
- Asegurar `--no-open` y arranque estable del servidor local.

2. Desktop packaging:
- Windows: PyInstaller + pywebview.
- macOS: app bundle + validacion de apertura.
- Linux: binario PyInstaller + validacion en Ubuntu LTS.

3. Calidad de release:
- Matriz de compatibilidad.
- Checklist QA previo release.
- Bitacora de incidencias por plataforma.

### Build Entry Points

- Unificado: `python build_desktop.py`
- Windows: `powershell -ExecutionPolicy Bypass -File .\\build_desktop.ps1`
- Linux/macOS: `./build_desktop.sh`

### Checklist de Validacion por OS

1. Arranca app desktop y muestra ventana nativa.
2. Ejecuta preflight sin errores.
3. Corre analisis de prueba completo.
4. Genera MD/HTML/CSV.
5. Cierra sin procesos colgados.

### Matriz de validacion reproducible (Linux/macOS)

> Restriccion actual: este repo se esta operando desde entorno Windows. La validacion de Linux/macOS debe correrse en host nativo o runner CI del OS objetivo.

#### Linux (Ubuntu LTS)

1. Preparar entorno
   - Comando: `python3 --version && python3 -m pip --version`
   - Esperado: Python/pip disponibles y funcionales.
2. Instalar dependencias desktop
   - Comando: `python3 -m pip install -r requirements-desktop.txt`
   - Esperado: instalacion sin errores; `pywebview` instalado.
3. Build desktop
   - Comando: `python3 build_desktop.py`
   - Esperado: artefacto generado en `dist/SteamToolsDesktop` (o `dist/SteamToolsDesktop/` en `--onedir`).
4. Ejecutar app y validar ventana nativa
   - Comando: `./dist/SteamToolsDesktop`
   - Esperado: abre ventana nativa; UI responde.
5. Verificacion funcional minima
   - Acciones: correr preflight, ejecutar run de prueba, generar MD/HTML/CSV, cerrar app.
   - Esperado: sin crash, outputs presentes, sin procesos colgados.
6. Fallback web (mitigacion)
   - Comando: `python3 steam_deals_web.py --no-open --port 8080`
   - Esperado: servidor arriba en `http://127.0.0.1:8080` si la ventana nativa falla.

#### macOS (app bundle + apertura local)

1. Preparar entorno
   - Comando: `python3 --version && python3 -m pip --version`
   - Esperado: Python/pip disponibles y funcionales.
2. Instalar dependencias desktop
   - Comando: `python3 -m pip install -r requirements-desktop.txt`
   - Esperado: instalacion sin errores; `pywebview` instalado.
3. Build desktop
   - Comando: `python3 build_desktop.py`
   - Esperado: artefacto generado en `dist/`.
4. Abrir app local
   - Comando: `open dist/SteamToolsDesktop.app`
   - Esperado: app abre localmente y muestra UI.
5. Verificacion funcional minima
   - Acciones: correr preflight, ejecutar run de prueba, generar MD/HTML/CSV, cerrar app.
   - Esperado: sin crash, outputs presentes, sin procesos colgados.
6. Quarantine/permisos (si aplica)
   - Comando: `xattr -dr com.apple.quarantine dist/SteamToolsDesktop.app`
   - Esperado: app vuelve a abrir cuando Gatekeeper bloquee artefacto local no firmado.
7. Fallback web (mitigacion)
   - Comando: `python3 steam_deals_web.py --no-open --port 8080`
   - Esperado: servidor arriba en `http://127.0.0.1:8080` si la ventana nativa falla.

#### Ejecucion recomendada en CI/runners

- Linux: `ubuntu-latest` (GitHub Actions u otro runner Ubuntu LTS).
- macOS: `macos-latest` (runner nativo para validar app bundle/apertura local).
- Guardar bitacora por OS: resultado por paso, error textual y workaround aplicado.

## Proximo Paso Operativo

- Ejecutar validacion Linux en host nativo/runner `ubuntu-latest` y validacion macOS en host nativo/runner `macos-latest`, con bitacora por paso (build, apertura app/binario, preflight, run de prueba, outputs, cierre, quarantine/codesign cuando aplique) y documentar incidencias/workarounds.

## Bitacora Cross-Platform por OS

| Fecha | Plataforma | Estado | Incidencias | Proximo paso |
|---|---|---|---|---|
| 2026-04-14 | Linux (Ubuntu LTS) | en progreso | Sin ejecucion nativa aun en este entorno Windows. | Correr checklist en `ubuntu-latest`/host Ubuntu y registrar resultados por paso. |
| 2026-04-14 | macOS | en progreso | Sin ejecucion nativa aun en este entorno Windows. | Correr checklist en `macos-latest`/host macOS y registrar resultados por paso, incluyendo quarantine/codesign. |

## Bitacora

- 2026-04-08: Se crea este archivo como consolidado unico de pendientes.
- 2026-04-08: Se implementan eventos estructurados base (progress/file).
- 2026-04-08: Se añade preflight y acciones rapidas de UX.
- 2026-04-08: Se fortalece parser de salida web (menos dependencia ANSI).
- 2026-04-08: Se crea base desktop opcion B (pywebview + build unificado).
- 2026-04-08: Build PyInstaller completado en Windows; generado `dist/SteamToolsDesktop.exe`.
- 2026-04-08: Smoke test basico del ejecutable Windows OK (arranca proceso y cierre controlado).
- 2026-04-08: Se agrega `smoke_test_windows.ps1` como smoke test reproducible (arranque, API local, cierre limpio).
- 2026-04-08: Smoke test Windows reproducible validado con resultado `SMOKE_OK`.
- 2026-04-08: Se agrega banner de modo (primer setup vs actualizacion) en la web UI.
- 2026-04-08: Se agregan presets de ejecucion (rapido/completo/ahorro) con aplicacion en formulario.
- 2026-04-08: Se agrega clasificacion de errores por categoria (network/config/rate-limit/encoding) con sugerencias accionables en consola UI.
- 2026-04-09: Se implementa feature Compartir Deals (URL scheme steamtools://) con modal en Web UI y HTML generado. Falta probar con datos reales (requiere VPN o config de red para Steam API).
- 2026-04-11: Se blindan handlers web en Steam Deals/PAYDAY 2 (JSON invalido -> 400, limites de payload, validacion de payload/action y errores mas accionables).
- 2026-04-11: PAYDAY 2 Web inicia separacion UI embebida: `web/payday2/index.html` externo con loader/fallback en `payday2_web.py`; spec desktop actualizado para incluir el HTML.
- 2026-04-11: Steam Deals Web migra HTML a `web/steam_deals/index.html` con loader/fallback en `steam_deals_web.py`; build desktop/spec incluyen ambos HTML externos.
- 2026-04-11: PAYDAY 2 Web extrae CSS a `web/payday2/app.css` y sirve `GET /app.css`; build desktop/spec incluyen nuevo asset.
- 2026-04-13: Se completa la extraccion de UI restante: `web/steam_deals/app.css`, `web/steam_deals/app.js` y `web/payday2/app.js`; ambos web servers sirven `/app.css` y `/app.js` con fallback a HTML inline.
- 2026-04-13: Se agrega `shared_web_infra.py` y se reutiliza en Steam Deals/PAYDAY 2 para respuestas HTTP, lectura defensiva de JSON, assets de texto, subprocess y SSE local.
- 2026-04-13: Se corrige shutdown de `payday2_web.py` para cerrar limpio con refresh activo, incluyendo terminacion del child process.
- 2026-04-13: README se actualiza para aclarar superficies, dependencias desktop y mapa de modulos/entrypoints.
- 2026-04-13: Se agregan smoke tests locales minimos en `.tmp/local-smoke-tests/` para Steam Deals Web, PAYDAY 2 Web y la ruta segura desktop `--internal-web`; quedan fuera del flujo normal de Git en este clon. `smoke_test_windows.ps1` se mantiene como smoke separado para Windows empaquetado.
- 2026-04-13: Se agregan tests unitarios puros en `tests/test_generator_logic.py` para score, filtros, matching/gift ideas y budget picks.
- 2026-04-13: Se completa el primer corte de capa shared con `shared/io_utils.py` y `shared/cache_utils.py`; Steam Deals y PAYDAY 2 ya comparten helpers de config JSON, HTTP JSON y cache reutilizable, con tests locales para los helpers shared.
- 2026-04-14: Linux desktop validation documentado como runbook reproducible en `README.md` (preparación, instalación, build, ejecución del artefacto, verificación funcional y fallback web). Estado Linux pasa a en progreso; pendiente ejecutar en host Linux/runner `ubuntu-latest` y registrar incidencias/resultados.
- 2026-04-14: macOS desktop validation documentado como runbook reproducible en `README.md` (preparación, instalación, build, apertura `.app`, verificación funcional, quarantine y verificación de codesign). Estado macOS pasa a en progreso; pendiente ejecutar en host macOS/runner `macos-latest` y registrar incidencias/resultados.
- 2026-04-14: Se consolidan dependencias nativas pywebview por plataforma en `README.md` (Windows/Linux/macOS) con referencias/comandos verificables y se agrega bitacora cross-platform por OS en este archivo para seguimiento accionable.
- 2026-04-14: Se completa `generator-renderers`: extracción de renderers (Markdown/HTML/Share HTML/CSV) desde `steam_deals_generator.py` con wrappers de compatibilidad y barrido de integración final para CLI/web/desktop (`py_compile` + `--help` en entrypoints).

## Backlog de Features (Propuestos - Planning)

### Output/Export

- [ ] Exportar a Obsidian/Notion (markdown con frontmatter YAML para importacion directa)
- [ ] Dashboard HTML historico con graficos de precios, comparativa entre runs y navegacion de historial
- [ ] Exportar a JSON / API local para integracion con otras herramientas y automatizaciones

### Social/Community

- [x] Generar link publica para compartir deals individuales (URL con data encodeada) - implementado, falta probar
- [ ] Detectar bundles activos de juegos en wishlist (mejorar integracion ITAD)

### Recomendaciones

- [ ] Sugerir juegos similares basados en generos de la biblioteca del usuario
- [ ] Analisis de biblioteca: tiempo total (HLTB), distribucion por genero, precio promedio
- [ ] Explicar score y recomendacion de compra (por que esta arriba, comprar ahora vs esperar)

### Producto / Plataforma

- [ ] Unificar Steam Deals, Watchlist, Compare y PAYDAY 2 bajo una UX de suite con modulos claros
- [ ] Doctor / instalador desktop por plataforma para validar dependencias nativas, setup y readiness

### Alertas inteligentes

- [ ] Alertar por minimo historico, bundles activos y cambios relevantes entre runs

### Expansion de Datos

- [ ] Importar wishlists de otras plataformas (GOG, Epic - investigar APIs)
- [ ] Detectar juegos eliminados del catalogo Steam (alertas)
- [ ] Comparar wishlist con historial y mostrar delta (nuevos juegos, bajadas y ofertas terminadas)

### Optimizacion (Velocidad - P0)

- [ ] Cache mas agresivo para wishlists grandes (24h stale time)
- [ ] Aumentar parallel fetching (de 5-10 a 50 concurrentes)
- [ ] Usar batch API de Steam para multiples juegos (reducir requests)
- [ ] Fetch inteligente: solo actualizar precios que cambiaron (comparar timestamps)
