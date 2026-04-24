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
3. **Cambio por juego**
   - Abrir `Cambiar este juego` en un pick que tenga reemplazos.
   - Verificar que el preview actualice `Total` y `Restante` sin exceder el mismo presupuesto.
   - Usar `Volver al original` y confirmar que la selección principal se restaura.
4. **Cobertura automatizada mínima**
   - `tests/test_generator_logic.py` valida variantes `small` / `balanced` / `large`.
   - También valida acciones de `probar otra lista` / `cambiar este juego`, totales, reemplazos y render en `.md`, `.html` y `.json`.

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
