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
   - Verificar que `Copiar link steamtools://`, `Copiar link de Steam` y `Abrir en Steam` funcionan o caen al fallback esperado.
5. **Compatibilidad de payload**
    - Revisar que el mismo deal mantenga campos clave entre superficies: `appid`, `name` / `steam_name`, `price` / `price_final`, `price_original` / `original_price`, `min_hist` / `min_historical`, `discount` y `url`.
    - Confirmar que `steamtools://share?data=...` sigue siendo decodificable por `steam_tools_desktop.py`.

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
