# Runbook de Validación de Features

Checklists manuales para validar features específicas de Steam Deals sin cargar el README.

## Regla de registro

- Detalle de ejecución, comandos usados, errores y workarounds: `BITACORA.md`.
- Cambio de estado, prioridad o próximo paso: `PENDIENTES.md`.
- Uso rápido y comandos principales: `README.md`.

## Markdown con frontmatter (Obsidian/Notion)

### Comando base

```bash
python3 steam_deals_generator.py --vanity gaben --md-frontmatter
```

### Campos esperados en frontmatter

- `title`
- `profile`
- `sale_name`
- `generated_date`
- `min_discount`
- `wishlist_count`
- `deals_count`
- `top_picks_count`
- `tags`

### Checklist manual

1. Generar reporte con `--md-frontmatter`.
2. Abrir el `.md` y confirmar que inicia con bloque YAML (`---` ... `---`).
3. Importar en **Obsidian** y verificar:
   - título de nota correcto
   - metadatos visibles
   - tags detectables
4. Importar en **Notion** y verificar:
   - contenido renderiza sin romper tablas/listas
   - propiedades clave se pueden mapear desde frontmatter
5. Si la validación cierra el pendiente, actualizar `PENDIENTES.md`; si deja evidencia larga, registrarla en `BITACORA.md`.

## Tu Presupuesto Ideal

### Comando base

```bash
python3 steam_deals_generator.py --vanity gaben --budget 500
```

### Checklist manual

1. **Output principal**
   - Confirmar que el `.json` del último run preserve `budget_result.selected`, `selected_variant`, `variants` y `actions`.
   - Confirmar que `.md` y `.html` sigan mostrando la sección `Tu Presupuesto Ideal`.
2. **Variantes en Web UI**
   - Correr `python3 steam_deals_web.py`.
   - Ejecutar un run con presupuesto activo.
   - En la tarjeta **Último reporte**, cambiar entre `Lista chica`, `Lista media` y `Lista grande`.
   - Verificar que el techo activo siga igual al presupuesto del run y que cambien juegos/totales según la variante.
   - Si una variante muestra conteos/totales, verificar que también renderiza filas de juegos; no cerrar con tablas que solo tengan headers.
   - Si el payload no trae filas para una variante, debe haber fallback explícito o estado vacío claro, no una tabla vacía silenciosa.
3. **Cambio por juego**
   - Abrir `Cambiar este juego` en un pick que tenga reemplazos.
   - Verificar que el preview actualice `Total` y `Restante` sin exceder el mismo presupuesto.
   - Usar `Volver al original` y confirmar que la selección principal se restaura.
4. **Cobertura automatizada mínima**
   - `tests/test_generator_logic.py` valida variantes `small` / `balanced` / `large`.
   - También valida acciones de `probar otra lista` / `cambiar este juego`, totales, reemplazos y render en `.md`, `.html` y `.json`.

## Wishlist Comparison / Gift Ideas

### Objetivo

Validar que las secciones sociales no muestren solo títulos/headers cuando existen datos de comparación o regalos.

### Checklist manual

1. Generar un reporte con comparación de wishlist/friend que tenga al menos un juego en común/en oferta.
2. Abrir el HTML/Markdown generado y confirmar:
   - `Wishlist Comparison` muestra filas cuando el resumen indica juegos en común/en oferta.
   - `Gift Ideas` muestra filas con juego, precio/descuento y `Por qué` cuando `gift_ideas` trae items.
   - Si no hay items concretos, se muestra un estado vacío claro en vez de una tabla con headers solos.
3. Mantener el flujo advisory-only: no carrito, checkout, compras ni tiendas externas.
4. Para multi-perfil, usar el campo **Comparar con** con perfiles por línea o coma y confirmar en JSON:
    - `compare_profiles` lista perfiles válidos y perfiles no públicos/invalidos como estado no disponible sin tumbar el reporte.
    - `gift_ideas_by_friend` agrupa candidatos por amigo.
    - `shared_gift_ideas` muestra candidatos que quieren 2+ amigos y conserva `ranking_impact=none`.
5. En reportes Markdown/HTML generados con payload multi-perfil, confirmar:
   - `Ideas compartidas` muestra candidatos con amigos, precio/descuento y razones compactas cuando `shared_gift_ideas` trae items.
   - `Ideas para {amigo}` muestra candidatos por persona desde `gift_ideas_by_friend`.
   - Payloads vacíos o malformados muestran estado vacío claro o se omiten, sin tablas con headers solos.

### Cobertura automatizada mínima

- Fixtures de `tests/test_generator_logic.py` para comparación con una oferta común.
- Fixtures de `gift_ideas` con `social_reasons` y fallback de razón cuando falten razones.
- Regresión de caso vacío para evitar tablas sin filas.
- Fixtures multi-perfil con dedupe, perfil no disponible, JSON opcional backward-compatible y render Markdown/HTML de `Ideas compartidas` / `Ideas para {amigo}`.

## Share / Compartir deals

### Objetivo

Cerrar el flujo E2E de compartir desde Web UI, HTML interactivo y Share HTML, manteniendo payload compatible con desktop.

### Checklist manual

1. **Cobertura automatizada**
   - `tests/test_generator_logic.py` valida contrato del payload share en `generate_html(...)` y `generate_share_html(...)`.
   - `tests/test_desktop_share.py` valida compatibilidad del payload para desktop, alias legacy y payload URL-encoded.
2. **Web UI en vivo**
   - Correr `python3 steam_deals_web.py`.
   - Ejecutar un run que genere `.json`, `.html` y `Steam Deals Share <fecha>.html`.
   - En **Último reporte**, abrir share desde un **Top Pick** y, si existe presupuesto, desde un **budget pick**.
   - Confirmar que el modal muestra nombre, precio actual, precio original cuando aplique y mínimo histórico o fallback textual.
3. **HTML generado**
   - Abrir el `.html` interactivo generado.
   - Confirmar que botones share funcionan desde top picks y tabla principal.
   - Verificar cierre por botón, click fuera y `Esc`.
4. **Share HTML generado**
   - Abrir `Steam Deals Share <fecha>.html`.
   - Confirmar que top picks y filas de deals exponen botón share.
   - Si el JSON trae regalos multi-perfil, confirmar `Regalos grupales`, `Ideas compartidas` e `Ideas para {amigo}` sin cards vacías y con copy advisory-only/no carrito.
   - Verificar que `Copiar link steamtools://`, `Copiar link de Steam` y `Abrir en Steam` funcionan o caen al fallback esperado.
5. **Compatibilidad de payload**
    - Revisar que el mismo deal mantenga campos clave entre superficies: `appid`, `name` / `steam_name`, `price` / `price_final`, `price_original` / `original_price`, `min_hist` / `min_historical`, `discount` y `url`.
    - Confirmar que `steamtools://share?data=...` sigue siendo decodificable por `steam_tools_desktop.py`.

## Scheduler Web/Desktop

### Objetivo

Definir y validar el contrato para exponer `--schedule` en Web/Desktop. El soporte CLI corre en primer plano; la UI compartida solo puede activar ejecución recurrente como opt-in local/visible con tests de comando, validación y stop/lock.

### Contrato UX esperado

1. **Opt-in explícito**
   - El scheduler debe estar apagado por defecto.
   - No debe guardarse como auto-start silencioso ni arrancar al abrir Web/Desktop.
   - La UI debe explicar que solo funciona mientras Steam Tools siga abierto.
2. **Ejecución local y visible**
   - No crear daemon, servicio del sistema, tarea de cron/Task Scheduler ni proceso oculto.
   - Mostrar intervalo, estado actual, último run y próximo run cuando exista.
   - Validar intervalo como número positivo; `0`, vacío o inválido no deben iniciar loop desde Web/Desktop.
3. **Stop/lock**
   - `Detener` debe cancelar el run activo y evitar la siguiente repetición.
   - No permitir runs solapados: si ya hay una ejecución activa, conservar el lock/409 o estado equivalente.
   - Si el usuario cierra la ventana/app, no prometer continuidad.
4. **Notificaciones y anti-spam**
   - Telegram/Discord deben seguir enviando resumen agregado, no alertas por juego.
   - Smart Alerts v2 permanece como preview/dry-run salvo un slice separado con límites anti-spam, digest y evidencia real.
5. **No-go**
   - No cambiar defaults de filtros, ranking, score, cache ni fetching.
   - No usar red real, `BG00G`, `--no-cache`, builds ni reportes generados para cerrar la UI del scheduler.

### Cobertura automatizada mínima si se implementa

- `build_command(...)` pasa `--schedule HOURS` solo cuando el usuario lo activa explícitamente.
- Tests Web assets verifican copy de primer plano/local, sin daemon/autostart y sin notificaciones por juego.
- Validación JS rechaza intervalos vacíos/`0`/negativos/inválidos cuando el toggle está activo.
- Preflight o endpoint equivalente reporta estado claro si ya hay run activo.
- Tests de stop/lock confirman que no se programan runs solapados.

### Corte Web/Desktop cerrado 2026-06-10

- La UI compartida expone `Programación local` como opt-in desactivado por defecto y un intervalo positivo en horas.
- `build_command(...)` pasa `--schedule HOURS` solo si `schedule_enabled=true` y `schedule_hours` es finito y mayor que 0; valores vacíos, `0`, negativos, `nan`, `inf` o texto no se envían.
- `app.js` valida el intervalo antes de ejecutar, no guarda el scheduler como config persistente y resetea el opt-in como filtro transitorio.
- El copy conserva `Foreground/local-only`: sin daemon, servicio, cron, Task Scheduler, proceso oculto, autostart ni promesa de continuidad al cerrar Web/Desktop.
- Los tests de stop/lock verifican que un run programado usa el mismo `_running_proc`, rechaza solapamientos con 409 y que **Detener** limpia el lock cuando el proceso se detiene.
- Al cerrar Desktop, el wrapper pide `/api/stop` con token local antes de terminar el servidor lanzado para evitar dejar un run programado huérfano.
- No se usó red real, `BG00G`, `--no-cache`, builds ni reportes generados para cerrar el slice.

## Smart Alerts v2 — readiness de canales

### Objetivo

Definir el contrato mínimo antes de conectar Smart Alerts v2 a Telegram/Discord u otros canales externos. La base vigente sigue siendo preview/dry-run local: `smart_alert_digest` agrupa alertas, limita ítems visibles y mantiene `send_ready=false`, `external_send_enabled=false`, `channels=[]` y `per_game_notifications=false`.

### Prerrequisitos para abrir integración real

1. Contar con una decisión explícita de producto para activar canales como **digest agrupado**, no alertas por juego.
2. Tener evidencia de volumen suficiente:
   - una corrida natural futura con `price_changes`, o
   - fixtures representativas revisadas que cubran bajo/medio/alto volumen.
3. Mantener preview visible antes del envío: el usuario debe poder revisar qué se enviaría y cuántos ítems quedan ocultos por cap.
4. Exigir opt-in por canal en un slice separado; no habilitar canales por defecto ni por el solo hecho de tener token/webhook configurado.

### Contrato de integración futura

- Enviar como un único resumen agrupado por run, reutilizando `smart_alert_digest.sections` y `anti_spam`.
- Respetar caps visibles y `total_hidden_count`; si hay alto volumen, el mensaje debe decir que hay ítems ocultos y remitir al reporte completo.
- Incluir `volume_level`, `visible_items_count`, `total_hidden_count` y `max_items_per_section` en la decisión de envío.
- Preservar canales vacíos y `send_ready=false` hasta que el slice de integración cambie explícitamente esos campos con tests.
- Si no hay secciones o el payload está malformado, no enviar nada y mostrar estado vacío/preview local.
- El texto del canal debe conservar el tono advisory: no compra, no abre carrito/checkout, no modifica wishlist y no cambia score/ranking/defaults.

### Validación mínima si se implementan canales

- Tests puros del builder/policy que cubran:
  - volumen bajo/medio/alto;
  - caps y ocultos;
  - payload vacío/malformado;
  - opt-in de canal;
  - no envío por juego;
  - no envío cuando `send_ready=false` o falta revisión explícita.
- Tests de Web assets/command-builder si se agrega UI de opt-in o preview.
- Tests de notificaciones con fakes/mocks; no usar Telegram/Discord real para cerrar el slice.
- `git diff --check` y evidencia compacta en `BITACORA.md`.

### No-go

- No conectar Telegram/Discord real en readiness docs-only.
- No notificaciones por juego.
- No default-on, daemon, scheduler nuevo, auto-send oculto ni envío solo por tener credenciales.
- No cambiar score, ranking, Top Picks, defaults, cache, fetching ni thresholds por reacción a una corrida parcial.
- No red real, `BG00G`, `--no-cache`, builds ni reportes generados como validación automática.

### Corte policy helper cerrado 2026-06-16

- `decide_smart_alert_channel_readiness(...)` clasifica si un `smart_alert_digest` preview sería apto para un slice futuro de canales, sin enviar nada ni cambiar `send_ready=false`.
- Requiere canal soportado solicitado, opt-in del usuario, digest revisado, payload preview válido, digest agrupado y `per_game_notifications=false`.
- Volumen alto queda bloqueado hasta aprobación explícita (`allow_high_volume=True` en fixtures/policy), y los ítems ocultos deben comunicarse en el futuro mensaje.
- Payloads vacíos/malformados, ausencia de canales soportados, falta de review/opt-in, `external_send_enabled=true`, canales ya presentes o notificaciones por juego bloquean la readiness; canales no soportados se ignoran y se cuentan para diagnóstico.
- Sigue siendo fixture-only/policy-only: no conecta Telegram/Discord, no crea UI de opt-in y no cambia runtime de notificaciones.

### Corte preview builder cerrado 2026-06-16

- `build_smart_alert_channel_preview(...)` construye un mensaje fixture-only a partir de `smart_alert_digest` y reutiliza `decide_smart_alert_channel_readiness(...)` para exponer readiness, blockers y canales solicitados.
- La salida conserva `preview_only=true`, `send_ready=false`, `external_send_enabled=false` y `channels=[]`; sirve para revisión local/futura, no para envío real.
- El mensaje agrupa por secciones del digest, muestra canal soportado solicitado, `volume_level`, visibles/ocultas, caps por sección y copy advisory-only sin compras, score, ranking ni defaults.
- Payloads vacíos/malformados o readiness bloqueada devuelven preview bloqueado y estado vacío claro, sin fallback ni activación de Telegram/Discord.
- Validación mínima vigente: `py_compile`, `tests.test_generator_logic.SmartAlertsTests` y `git diff --check`; no red real, `BG00G`, `--no-cache`, builds ni reportes generados.

## PAYDAY 2 data/cache y diagnóstico

### Objetivo

Validar cambios alrededor del catálogo PAYDAY 2 sin hardcodear DLCs ni depender de red real para cerrar un slice.

### Checklist automático mínimo

```bash
.venv/bin/python -m unittest tests.test_payday2_diagnostics tests.test_web_assets tests.test_shared_web_infra tests.test_shared_cache_utils tests.test_runtime_paths
```

Agregar `tests.test_host_loopback_payday2` o `tests.test_config_security` si el cambio toca endpoints, CSRF/Host, secretos o subprocess.

### Checklist funcional

1. Confirmar que el flujo normal Web sigue siendo: `python3 payday2_web.py` → **Actualizar datos** → marcar ownership manual.
2. Confirmar que **Actualizar datos** respeta TTL/cache y que **Forzar catálogo** equivale a `--no-cache`.
3. Confirmar que `--no-cache` no borra `owned.json` ni cambia marcados manuales.
4. Para DLC faltante, usar fixtures/fakes de Steam/cache y validar que `--diagnose-dlc APPID_O_NOMBRE` clasifique al menos:
   - `listed_in_base_dlc`
   - `cache_stale`
   - `valid_app_not_linked_to_base`
   - `package_or_bundle_candidate`
   - `not_found_or_unreleased`
   - `name_mismatch`
5. Confirmar que la documentación explica los archivos de cache: `dlc_list.json`, `dlc_mapping.json`, `prices.json`, `bundles.json`, `owned.json` y `price_history.json`.
6. Confirmar que la salida pública no sugiere hardcodear DLCs ni promete que Steam expone todos los packages/bundles en `data.dlc` del app `218620`.

### Evidencia

- Registrar comandos y conteos en `BITACORA.md`.
- Actualizar `PENDIENTES.md` solo si cambia estado, prioridad o próximo paso.
- No pegar logs completos, respuestas Steam live ni reportes generados.
