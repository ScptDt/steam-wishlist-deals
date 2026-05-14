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

Experimento opt-in para cold-cache grande cuando el cuello ya sea fallback individual:

```bash
STEAM_DEALS_CACHE_DIR="$HOME/.cache/steam_deals-benchmark-large" \
STEAM_DEALS_INDIVIDUAL_FALLBACK_WORKERS=4 \
python3 steam_deals_generator.py --vanity BG00G --warm-cache
```

Usa `STEAM_DEALS_INDIVIDUAL_FALLBACK_WORKERS` con cautela: el default sigue siendo `1`, el máximo inicial es `4`, y cualquier mejora debe compararse contra un log cold-cache equivalente antes de subirlo a un flujo normal. Si la corrida detecta demasiados fallos con workers paralelos, el fallback adaptativo puede bajar a `1` worker y dejar evidencia como `Fallback individual adaptativo` y `Fallback individual fallos por razón`.

Diagnóstico opt-in para capturar muestras acotadas de batches/appids cuando Steam degrada con HTTP 400:

```bash
STEAM_DEALS_HTTP_400_DIAGNOSTIC_SAMPLE_LIMIT=5 \
STEAM_DEALS_CACHE_DIR="$HOME/.cache/steam_deals" \
python3 steam_deals_generator.py --vanity gaben --warm-cache
```

Mantén el límite bajo: las muestras exponen appids de la wishlist en el log local y solo sirven para diseñar el siguiente ajuste offline. El default es `0`, por lo que no se imprimen appids si no activas explícitamente la variable.

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
- [ ] `Stale-while-revalidate`, si aparece: `stale_used`, `stale_deferred` y buckets de jitter.
- [ ] `Refresh budget resumible`, si aparece: `processed`, `deferred`, `exhausted` y `next_resume_hint`; tratar `deferred` como juegos no revalidados en esa corrida.
- [ ] Cobertura parcial, si `deferred > 0`: registrar `processed/refresh_candidates`, pendientes, deals encontrados con la cobertura disponible y acción de continuación.
- [ ] `Batches degradados por HTTP 400`, si aparece.
- [ ] `HTTP 400 diagnostic samples`, solo si activaste `STEAM_DEALS_HTTP_400_DIAGNOSTIC_SAMPLE_LIMIT`.
- [ ] `Fallback individual aplicado a X juegos en Y tandas`.
- [ ] `Fallback individual directo por HTTP 400 repetido`, si aparece.
- [ ] `Fallback individual adaptativo` y `Fallback individual fallos por razón`, si aparecen.
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
| Stale usados/diferidos |  |  |  |
| Refresh budget procesados/diferidos |  |  |  |
| Batches degradados HTTP 400 |  |  |  |
| Fallback individual total |  |  |  |
| Fallback directo HTTP 400 |  |  |  |
| Fallback adaptativo |  |  |  |
| Razones de fallo fallback |  |  |  |
| Fallback resueltos |  |  |  |
| Fallback sin datos/oferta |  |  |  |

## Interpretación rápida

- Si la segunda corrida baja mucho `Refresh candidates`, el cache caliente está funcionando.
- Separa velocidad de completitud: el presupuesto evita corridas eternas o más rate-limit; si queda `deferred > 0`, el resultado es cobertura parcial aunque la corrida haya terminado correctamente.
- Lee estados de cobertura así: `processed` = revalidado en esta corrida; `deferred` = pendiente/no revalidado; `fresh cache` = dato confiable por TTL o fin de oferta; `stale cache` = dato viejo usado o pendiente; `failed/cooldown` = no confirmado por error/rate-limit.
- Si `Stale-while-revalidate` difiere stale no crítico, confirma que `missing` sigue en refresh y que los datos viejos útiles se conservan; no lo trates como error si baja el refresh masivo.
- Si `Refresh budget resumible` marca `exhausted=true`, conserva el mismo cache y repite warm-cache normal para continuar desde `next_resume_hint`; no fuerces `--no-cache` salvo benchmark explícito. Los deals de esa corrida son “deals encontrados con la cobertura disponible”, no cobertura completa si `deferred` es mayor que `0`.
- Evita copy como “deals actuales” o “caché actualizada” sin matiz cuando hay diferidos; usa “deals encontrados con la cobertura disponible” y “caché actualizada parcialmente”.
- Si `Fallback individual total` sigue alto con cache caliente, revisar primero batch sizing y distribución de fallos/no-data.
- Si aparece `Fallback individual directo por HTTP 400 repetido`, compara duración y `Batches degradados HTTP 400` contra una corrida previa: debe reducir splits fallidos, aunque el fallback individual siga siendo el costo dominante.
- Si un batch menor (`STEAM_DEALS_PRICE_BATCH_SIZE`) sube `Batches degradados HTTP 400` o activa esperas de rate-limit, vuelve al default/base y no sigas bajando el batch global; el siguiente paso debe ser analizar circuito/fallback directo o instrumentar appids/batches de forma acotada antes de otro benchmark.
- Si usas `STEAM_DEALS_HTTP_400_DIAGNOSTIC_SAMPLE_LIMIT`, trata las muestras como evidencia local temporal: appids repetidos en `split`/`fallback` ayudan a diseñar fixtures o un ajuste de circuit breaker, pero no justifican cambiar defaults sin tests. Si el resumen muestra degradación HTTP 400 sin muestras, conserva los logs y activa ese límite solo en un próximo benchmark aprobado.
- Si `Fallback individual total` cubre casi todos los candidatos y los HTTP 400 degradados ya son bajos, prueba una corrida aislada con `STEAM_DEALS_INDIVIDUAL_FALLBACK_WORKERS=4`; si mejora sin `429`, considerar hacerlo preset/configurable.
- Si `fallback_workers > 1` baja fuerte la duración pero también baja deals/resueltos, revisa `Fallback individual adaptativo` y las razones de fallo; no uses esa configuración como default hasta que conserve calidad.
- Si hay muchos `sin oferta/datos`, el cooldown debe evitar reintentos inmediatos; confirmar que aparecen como `fallos recientes en cooldown` en corridas posteriores.
- Si hay degradación repetida por HTTP 400, optimizar batching/fallback antes de diseñar cache por promo.
- Si una promo activa parece correlacionar con mejores oportunidades, documentarlo como observación; no invalidar cache por promo hasta tener evidencia suficiente.

## Interpretación de `Warm-cache next actions`

- `HTTP 400 repetido`: sigue el valor sugerido (`STEAM_DEALS_PRICE_BATCH_SIZE=N`, normalmente la mitad del batch actual/base) solo si no existe ya evidencia negativa de batch menor; no cambies cache por promo todavía.
- `Diagnóstico offline HTTP 400`: no hay appids de muestra en los logs actuales; antes de otro cambio de defaults, captura una corrida aprobada con `STEAM_DEALS_HTTP_400_DIAGNOSTIC_SAMPLE_LIMIT=5` o diseña fixtures con la evidencia existente de tamaño/saltos.
- `Muestras HTTP 400 disponibles`: no necesitas otro benchmark para analizarlas; convierte esos appids/orden/profundidad en fixture offline para probar circuit breaker o fallback directo. Si hay appids repetidos, prioriza esos casos; no cambies defaults ni captures más appids sin aprobación.
- `Fallback directo HTTP 400 activo`: el circuit breaker ya actuó y mandó batches completos a fallback individual; no captures más appids ni cambies defaults, usa el fixture offline existente para ajustar umbral/fallback directo si hace falta.
- `Batch menor no ayudó`: conserva o vuelve al default/base; no sigas bajando el batch global y prioriza circuito/fallback directo o instrumentación offline de appids/batches problemáticos.
- `Rate-limit observado`: espera cooldown y evita repetir benchmarks; si apareció junto con batch menor, trátalo como señal contra bajar más el batch global.
- `Mucho fallback sin datos`: usa el desglose `fallidos/total` y espera al menos el cooldown indicado (2h por defecto) antes de forzar `--no-cache` salvo que estés capturando evidencia explícita.
- `Cache efectivo`: la segunda corrida redujo fuerte los refresh candidates; conserva cache caliente antes de ampliar políticas de invalidación.
- `Fallback sigue alto`: prioriza batching/fallback antes de invalidar cache por promos.
- `Sin acción automática`: no hay una señal clara; captura otra corrida si cambia la promo o la wishlist.

## Pausa del frente HTTP 400 offline

Pausa este frente y no abras otro slice si ya están cubiertos estos cuatro puntos:

- hay samples o logs suficientes para explicar la degradación HTTP 400;
- existe un fixture offline grande que demuestra la entrada a fallback directo tras HTTP 400 repetidos;
- existe un fixture mixto que evita falsos positivos cuando hay batches exitosos entre fallos;
- el resumen warm-cache reconoce `http-400-direct-fallback-active` y deja de pedir más samples/batch menor.

Con esa evidencia, el siguiente cambio ya no debe ser “capturar más appids” ni bajar defaults. Reabre solo si aparece un log/samples nuevos, si se aprueba explícitamente ajustar umbral/circuit breaker con fixture offline, o si se planifica un benchmark aislado con alcance, cache y validación definidos de antemano.

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
- Cobertura refresh/parcial:
- Pendientes no revalidados:
- Continuación sugerida:
- Fallos recientes en cooldown:
- Stale-while-revalidate usados/diferidos/jitter:
- Refresh budget processed/deferred/exhausted/resume:
- Batches degradados HTTP 400:
- HTTP 400 diagnostic samples:
- Fallback individual total:
- Fallback directo HTTP 400:
- Fallback workers:
- Fallback adaptativo:
- Razones de fallo fallback:
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
