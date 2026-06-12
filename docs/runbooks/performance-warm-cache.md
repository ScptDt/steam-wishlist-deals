# Runbook Performance Warm Cache

Plantilla para capturar evidencia real del Track Performance en wishlists grandes sin cambiar todavía la política de cache por promos.

## Objetivo

Medir si el cache caliente realmente reduce fetches lentos y fallback individual antes de tocar reglas más agresivas como invalidación por promo activa.

## No hacer en esta fase

- No correr `--no-cache` en una wishlist grande salvo que se reserve una ventana larga explícita.
- No invalidar cache por promo activa todavía.
- No subir `--max-workers` por encima del default solo para “probar suerte”.
- No cerrar el Track Performance con una sola corrida si hubo fallos externos/rate limits.

## Rate limits: Web API vs Store `appdetails`

No mezcles límites oficiales de la Steam Web API con el comportamiento práctico del Store JSON:

- `api.steampowered.com` / Web API oficial: Steam documenta un límite general de `100,000` llamadas por día por API key. Ese número sirve como referencia para endpoints oficiales con key, pero no describe ráfagas ni endpoints Store.
- `store.steampowered.com/api/appdetails`: es el endpoint Store usado para precios/metadatos y puede devolver `HTTP 400`/`HTTP 429` bajo patrones de batch o refresh grandes. Sus límites prácticos no están documentados públicamente como el cupo diario de Web API, así que trátalos como throttling externo/IP/endpoint y no como “sin oferta” o “juego no disponible”.
- El comportamiento actual del fetch de precios usa backoff interno ante `429` durante el batch (`30s`, `60s`, hasta `120s`) y, si un appid queda con `http_429`, guarda `_next_retry_after` con el cooldown local (`2h` por defecto). Hoy no se interpreta un header `Retry-After`; si eso cambia, debe cubrirse con fixture offline antes de otro benchmark real.
- Si aparece rate-limit en logs, conserva la caché, espera cooldown y continúa con warm-cache normal. No fuerces `--no-cache`, no bajes más el batch global y no repitas `BG00G` salvo benchmark aprobado.

## Comandos base

Usa `gaben` solo como ejemplo público; reemplázalo por tu vanity real, URL completa o Steam ID.

```bash
source .venv/bin/activate
STEAM_DEALS_CACHE_DIR="$HOME/.cache/steam_deals" python3 steam_deals_generator.py --vanity gaben --warm-cache
```

Para completar pendientes importantes con pasadas resumibles y cap seguro:

```bash
STEAM_DEALS_CACHE_DIR="$HOME/.cache/steam_deals" \
python3 steam_deals_generator.py --vanity gaben --warm-cache-full --warm-cache-full-max-passes 5
```

`--warm-cache-full` reutiliza la misma caché, ignora `--no-cache` si se combinan por error, se detiene con advisory si solo quedan cooldown/fallidos finales/sin oferta-datos y no genera reportes; genera el reporte después con una corrida normal.

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
- Contrato `--warm-cache-full`: repetir pasadas solo mientras queden señales importantes (`deferred_by_time_budget`, `next_resume_hint`, stale refresh diferido o fallback diferido por presupuesto) y no se alcance el cap de seguridad. Si solo quedan cooldown/fallidos finales/sin oferta-datos, detener con advisory; el reporte final se genera después como corrida normal separada, no dentro del warm-cache.
- Si `Fallback individual total` sigue alto con cache caliente, revisar primero batch sizing y distribución de fallos/no-data.
- Si aparece `Fallback individual directo por HTTP 400 repetido`, compara duración y `Batches degradados HTTP 400` contra una corrida previa: debe reducir splits fallidos, aunque el fallback individual siga siendo el costo dominante.
- Si un batch menor (`STEAM_DEALS_PRICE_BATCH_SIZE`) sube `Batches degradados HTTP 400` o activa esperas de rate-limit, vuelve al default/base y no sigas bajando el batch global; el siguiente paso debe ser analizar circuito/fallback directo o instrumentar appids/batches de forma acotada antes de otro benchmark.
- Si usas `STEAM_DEALS_HTTP_400_DIAGNOSTIC_SAMPLE_LIMIT`, trata las muestras como evidencia local temporal: appids repetidos en `split`/`fallback` ayudan a diseñar fixtures o un ajuste de circuit breaker, pero no justifican cambiar defaults sin tests. Si el resumen muestra degradación HTTP 400 sin muestras, conserva los logs y activa ese límite solo en un próximo benchmark aprobado.
- Si `Fallback individual total` cubre casi todos los candidatos y los HTTP 400 degradados ya son bajos, prueba una corrida aislada con `STEAM_DEALS_INDIVIDUAL_FALLBACK_WORKERS=4`; si mejora sin `429`, considerar hacerlo preset/configurable.
- Si `fallback_workers > 1` baja fuerte la duración pero también baja deals/resueltos, revisa `Fallback individual adaptativo` y las razones de fallo; no uses esa configuración como default hasta que conserve calidad.
- Si hay muchos `sin oferta/datos`, el cooldown debe evitar reintentos inmediatos; confirmar que aparecen como `fallos recientes en cooldown` en corridas posteriores.
- Si hay degradación repetida por HTTP 400, optimizar batching/fallback antes de diseñar cache por promo.
- Si una promo activa parece correlacionar con mejores oportunidades, documentarlo como observación; no invalidar cache por promo hasta tener evidencia suficiente.

## Proactive price fetch planner

Motivación: los logs reales muestran que, cuando Steam degrada batches con HTTP 400, el flujo actual puede imprimir muchos splits fallidos (`20 -> 10 -> 5 -> fallback`) antes de llegar al comportamiento útil. El objetivo futuro no es eliminar el fallback, sino convertirlo en red de seguridad y mover la decisión principal a un planner proactivo.

Contrato deseado del planner:

- Entrada: candidatos priorizados, estado de caché/fallos, tuning vigente y métricas de la corrida.
- Salida: buckets explícitos `batch`, `individual_planificado`, `usar_stale`, `defer`, `cooldown` y `fallback_reactivo` solo para fallos no previstos.
- Invariante: `missing` sigue siendo más crítico que stale no crítico; `http_429` y fallos recientes respetan cooldown; datos viejos útiles se preservan si Steam falla.
- Métricas nuevas esperadas: batches planificados, individuales planificados, batches evitados, stale reutilizado proactivamente, diferidos proactivos y fallback reactivo restante.

Orden de implementación recomendado:

1. Docs/contrato: definir buckets, no-go y fixtures mínimas antes de tocar runtime.
2. Helper puro sin cambio de comportamiento, idealmente en `app/steam_deals_price_fetch_strategy.py` o una sección aislada de `app/steam_deals_prices.py`.
3. Primera regla real: si los fixtures existentes demuestran HTTP 400 repetido, rutear los siguientes grupos como `individual_planificado` antes de llenar logs de splits.
4. Copy/métricas: diferenciar “individual planificado” de “fallback reactivo” en logs, JSON/resumen y runbook.
5. Benchmark aislado solo si fixtures pasan y se aprueba explícitamente cache/log/objetivo.

Corte offline 2026-06-10:

- `build_proactive_price_fetch_plan_comparison(...)` resume, sin tocar runtime, la diferencia entre fallback reactivo base, `individual_planificado`, `fallback_reactivo` restante, batch y buckets sin fetch.
- `format_proactive_price_fetch_plan_comparison(...)` produce copy offline para comparar planificado vs reactivo, siempre con guardrail explícito de que no cambia runtime, defaults, score, ranking, cache policy ni fetching.
- Este resumen sirve para fixtures/logs ya convertidos a métricas; la integración runtime del planner sigue siendo un slice separado con aprobación explícita.

Corte runtime fixture-only 2026-06-10:

- Cuando el circuit breaker por HTTP 400 repetido ya está activo, el runtime construye el plan proactivo para el batch pendiente y ejecuta esos appids como `individual_planificado` antes de seguir acumulando splits.
- Los fallbacks que ocurren dentro del flujo batch/splits siguen contándose como `fallback_reactivo`; las métricas legacy (`individual_fallback_count`, `http_400_direct_fallback_count`) se preservan para compatibilidad.
- `run_price_cache_stage(...)` y el resumen offline separan `individual_planificado` de `fallback_reactivo` en logs/resultados, sin cambiar batch default, cache policy, score/ranking, cooldown, fallback budget ni stale-while-revalidate.

Corte benchmark real parcial 2026-06-10:

- `BG00G` con caché aislada y `--warm-cache` completó OK en 607.4s, sin `--no-cache`, sin tuning de batch/workers y sin diagnostic samples.
- Resultado parcial esperado por presupuesto resumible: 2,953 candidatos, `processed=360`, `deferred=2,593`, `exhausted=true`, `next_resume_hint=477740`, 38 deals con la cobertura disponible, 21 batches HTTP 400 degradados y planner runtime `individual_planificado=300` / `fallback_reactivo=60`.
- Interpretación: el planner proactivo se activó en caso grande real y redujo splits posteriores, pero no cierra cobertura completa ni justifica cambiar defaults. Si se continúa, debe ser con la misma caché y `--warm-cache` bajo aprobación explícita; no usar `--no-cache` como reacción.

Corte benchmark real multipasada 2026-06-11:

- Se completó `BG00G` con la misma caché aislada y `--warm-cache`, sin `--no-cache`, sin tuning de batch/workers y sin diagnostic samples. Evidencia larga: `BITACORA.md`; logs locales no versionados en `/tmp/opencode/steam-deals-benchmarks/proactive-bg00g-2026-06-10/cache/logs/` desde `warm-cache-2026-06-11_10-04-50.log` hasta `warm-cache-2026-06-11_13-36-02.log`.
- La caché resumible funcionó: tras el primer log disponible con `Sin caché`, las pasadas siguientes detectaron `Caché válida`; la cola principal bajó de `deferred=2,593` a `deferred=0`, `exhausted=false`, `next_resume_hint=none`.
- Los deals subieron de 53 a 365 al cerrar la cola principal, y a 372 tras dos reconciliaciones cortas de cooldown/fallos. Tiempo activo total registrado: ~90 min.
- Patrón estable: las pasadas grandes mantuvieron 21 batches HTTP 400 degradados y alto uso de fallback individual; el planner separó `individual_planificado` de `fallback_reactivo`, pero el costo dominante siguió siendo fallback individual bajo degradación de Steam.
- Interpretación: `deferred=0` significa cola resumible cerrada, no cobertura perfecta; todavía pueden quedar `failed/cooldown` y `no_price_data`. Las reconciliaciones inmediatas aportaron rendimiento marginal bajo (`365 -> 369 -> 372`), por lo que conviene pausar corridas y analizar logs offline antes de tocar umbral/circuit breaker/planner.
- Decisión operativa: no crear una caché nueva, no usar `--no-cache` como reacción y no cambiar defaults por este benchmark. Reabrir solo con análisis offline, muestras/appids o benchmark aislado aprobado.

No hacer: no bajar `STEAM_DEALS_PRICE_BATCH_SIZE` global, no forzar `--no-cache`, no invalidar cache por promo, no tratar `HTTP 400` como ausencia definitiva de oferta, no borrar protecciones de cooldown/fallback budget/stale-while-revalidate y no usar `BG00G` o red real para cerrar los primeros slices.

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
