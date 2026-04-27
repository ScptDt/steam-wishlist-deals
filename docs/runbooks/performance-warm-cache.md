# Runbook Performance Warm Cache

Plantilla para capturar evidencia real del Track Performance en wishlists grandes sin cambiar todavía la política de cache por promos.

## Objetivo

Medir si el cache caliente realmente reduce fetches lentos y fallback individual antes de tocar reglas más agresivas como invalidación por promo activa.

## No hacer en esta fase

- No correr `--no-cache` en una wishlist grande salvo que se reserve una ventana larga explícita.
- No invalidar cache por promo activa todavía.
- No subir `--max-workers` por encima del default solo para “probar suerte”.
- No cerrar el Track Performance con una sola corrida si hubo fallos externos/rate limits.

## Comandos base

Usa `gaben` solo como ejemplo público; reemplázalo por tu vanity real, URL completa o Steam ID.

```bash
source .venv/bin/activate
STEAM_DEALS_CACHE_DIR="$HOME/.cache/steam_deals" python3 steam_deals_generator.py --vanity gaben --warm-cache
```

Validación automática corta del frente performance:

```bash
.venv/bin/python -m pytest tests/test_warm_cache_summary.py
.venv/bin/python -m pytest tests/test_generator_logic.py -k "warm_cache or price_cache or fallback or cooldown"
.venv/bin/python -m pytest tests/test_runtime_paths.py tests/test_shared_cache_utils.py
```

Resumen offline de un log ya generado:

```bash
python3 steam_deals_warm_cache_summary.py "$HOME/.cache/steam_deals/logs/warm-cache-YYYY-MM-DD_HH-MM-SS.log"
```

Si quieres guardar salida estructurada para comparar después:

```bash
python3 steam_deals_warm_cache_summary.py "$HOME/.cache/steam_deals/logs/warm-cache-YYYY-MM-DD_HH-MM-SS.log" --json
```

Para comparar dos o más corridas en Markdown, pasa todos los logs en orden cronológico; el resumen agrega una tabla con deltas contra el log anterior y un bloque `Warm-cache next actions` con recomendaciones automáticas:

```bash
python3 steam_deals_warm_cache_summary.py \
  "$HOME/.cache/steam_deals/logs/warm-cache-PRIMERA.log" \
  "$HOME/.cache/steam_deals/logs/warm-cache-SEGUNDA.log"
```

## Checklist de evidencia warm-cache

- [ ] Comando exacto usado para warm-cache.
- [ ] Ruta del cache (`STEAM_DEALS_CACHE_DIR` o default).
- [ ] Ruta del log generado (`logs/warm-cache-...log`).
- [ ] Duración total (`Warm cache listo en ...s`).
- [ ] Tamaño aproximado de wishlist.
- [ ] `Refresh candidates: X (N nuevos, M stale)`.
- [ ] `fallos recientes en cooldown`, si aparece.
- [ ] `Batches degradados por HTTP 400`, si aparece.
- [ ] `Fallback individual aplicado a X juegos en Y tandas`.
- [ ] Desglose de fallback: `resueltos` vs `sin oferta/datos`.
- [ ] Si se hizo segunda corrida warm-cache, comparar contra la primera.
- [ ] Resumen offline generado con `steam_deals_warm_cache_summary.py` y pegado en `BITACORA.md` si aporta evidencia; si hay 2+ logs, incluir la tabla `Warm-cache comparison`.

## Plantilla de comparación

| Métrica | Warm-cache 1 | Warm-cache 2 | Nota |
| --- | ---: | ---: | --- |
| Duración total |  |  |  |
| Wishlist entries |  |  |  |
| Refresh candidates |  |  |  |
| Nuevos |  |  |  |
| Stale |  |  |  |
| Fallos en cooldown |  |  |  |
| Batches degradados HTTP 400 |  |  |  |
| Fallback individual total |  |  |  |
| Fallback resueltos |  |  |  |
| Fallback sin datos/oferta |  |  |  |

## Interpretación rápida

- Si la segunda corrida baja mucho `Refresh candidates`, el cache caliente está funcionando.
- Si `Fallback individual total` sigue alto con cache caliente, revisar primero batch sizing y distribución de fallos/no-data.
- Si hay muchos `sin oferta/datos`, el cooldown debe evitar reintentos inmediatos; confirmar que aparecen como `fallos recientes en cooldown` en corridas posteriores.
- Si hay degradación repetida por HTTP 400, optimizar batching/fallback antes de diseñar cache por promo.
- Si una promo activa parece correlacionar con mejores oportunidades, documentarlo como observación; no invalidar cache por promo hasta tener evidencia suficiente.

## Interpretación de `Warm-cache next actions`

- `HTTP 400 repetido`: sigue el valor sugerido (`STEAM_DEALS_PRICE_BATCH_SIZE=N`, normalmente la mitad del batch actual/base) antes de repetir una wishlist grande; no cambies cache por promo todavía.
- `Mucho fallback sin datos`: usa el desglose `fallidos/total` y espera al menos el cooldown indicado (2h por defecto) antes de forzar `--no-cache` salvo que estés capturando evidencia explícita.
- `Cache efectivo`: la segunda corrida redujo fuerte los refresh candidates; conserva cache caliente antes de ampliar políticas de invalidación.
- `Fallback sigue alto`: prioriza batching/fallback antes de invalidar cache por promos.
- `Sin acción automática`: no hay una señal clara; captura otra corrida si cambia la promo o la wishlist.

## Plantilla para BITACORA.md

```markdown
- Fecha/host:
- Comando warm-cache:
- Cache dir:
- Log generado:
- Duración:
- Wishlist/deals:
- Refresh candidates:
- Nuevos/stale:
- Fallos recientes en cooldown:
- Batches degradados HTTP 400:
- Fallback individual total:
- Fallback resueltos/sin datos:
- Segunda corrida comparativa: sí/no
- Resultado de tests focales:
- Observaciones:
- Decisión: mantener / ajustar batching / investigar fallos / evaluar promo-cache después
```

## Gate antes de cambiar cache por promos

Solo considerar una política promo-aware si:

1. hay evidencia de que warm-cache normal deja oportunidades relevantes sin refrescar;
2. el costo de fallback individual ya está controlado;
3. la regla puede limitarse a juegos tuyos afectados por promo activa;
4. respeta cooldown para fallos/no-data recientes;
5. tiene tests determinísticos antes de correrla en una wishlist grande.
