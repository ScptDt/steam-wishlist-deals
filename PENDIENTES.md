# Pendientes (Fuente Unica)

Ultima actualizacion: 2026-04-09

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

- [ ] Validar build desktop en Linux (Ubuntu LTS).
- [ ] Validar build desktop en macOS (app bundle + apertura local).
- [ ] Documentar dependencias nativas por plataforma para pywebview.

### P3 - Base tecnica y mantenibilidad

- [ ] Blindar handlers web: JSON invalido -> 400, validacion de boundaries y errores mas accionables.
- [ ] Aclarar `README.md` por superficies: core stdlib, desktop con deps extra y posicionamiento de modulos.
- [ ] Separar HTML/CSS/JS embebido de `steam_deals_web.py` y `payday2_web.py`.
- [ ] Extraer infraestructura compartida para web local (JSON, SSE, subprocess, server utils).
- [ ] Reutilizar la base compartida entre Steam Deals Web y PAYDAY 2 Web.
- [ ] Modularizar `steam_deals_generator.py` por dominios (config, adapters, cache, scoring, renderers, orchestration).
- [ ] Crear capa shared entre Steam Deals y PAYDAY 2 para config/cache/helpers reutilizables.
- [ ] Agregar smoke tests minimos para web, desktop y PAYDAY 2.
- [ ] Agregar tests para logica pura critica (score, filtros, compare, budget, recomendaciones).

### Nota de trabajo futuro - orden sugerido de ejecucion

- 1. Cerrar base actual: cross-platform + README + handlers robustos.
- 2. Separar HTML/CSS/JS embebido.
- 3. Extraer infraestructura compartida para web local.
- 4. Reutilizar la base compartida entre Steam Deals y PAYDAY 2.
- 5. Modularizar `steam_deals_generator.py`.
- 6. Crear capa shared reutilizable.
- 7. Agregar smoke tests y tests de logica pura.
- 8. Implementar features nuevas sobre una base mas sana.

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

## Proximo Paso Operativo

- Validar build desktop en Linux y macOS y documentar incidencias por plataforma.

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
