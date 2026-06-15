# Steam Deals JSON export contract

Contrato vigente para exports JSON separados desde corridas normales de Steam Deals. El objetivo es permitir análisis externo o uso manual sin mezclar dos preguntas distintas:

1. **¿Qué ofertas detectó esta corrida?**
2. **¿Cuál es el estado de toda la wishlist conocida?**

Full warm-cache puede mejorar la cobertura, pero **no es requisito** para exportar. Si la corrida tiene cobertura parcial, los JSON deben decirlo explícitamente.

Estado actual: implementado en builders puros, escritura de artefactos, serving allowlist y Web/Desktop UI. Commits de referencia: `ebe768d` para builders/artefactos/serving/docs y `c90d107` para descargas Web/Desktop separadas.

## Readiness original del contrato

- Objetivo original: definir contrato, nombres, semántica de cobertura y fases de implementación para dos exports JSON separados.
- Fuera de alcance: código runtime, renderers, Web UI, file serving, score, ranking, defaults, cache policy, fetching, endpoints, builds, reportes generados, red real, `BG00G` y `--no-cache`.
- Archivos afectados en este slice: este runbook, índice de runbooks y `PENDIENTES.md`.
- Validación mínima: revisión documental + `git diff --check`.

## Principios

1. **Dos JSON, dos usos.** Ofertas y wishlist completa deben vivir en artefactos separados para no confundir “deal detectado” con “estado de todo lo que sigo”.
2. **Warm-cache mejora, no desbloquea.** Los exports aparecen después de una corrida normal de reporte. `--warm-cache`/`--warm-cache-full` siguen siendo cache-only y no generan reporte por sí mismos.
3. **Cobertura explícita.** Un export con cache parcial es válido si marca qué está confirmado, pendiente, stale, en cooldown o sin precio confirmado.
4. **Backward-compatible.** El JSON técnico existente del reporte no debe romperse ni migrarse por sorpresa; estos son artefactos adicionales.
5. **Local-first y seguro.** No exponer rutas locales, API keys, webhooks, cookies, tokens, raw responses ni exports privados completos.
6. **Advisory-only.** No borra wishlist, no auto-excluye, no compra, no abre carrito y no cambia score/ranking.

## Artefactos vigentes

Nombres finales generados junto al reporte normal:

- `Steam Deals Offers YYYY-MM-DD.json`
- `Steam Deals Wishlist YYYY-MM-DD.json`

Ambos deben incluir `schema`, `generated_at`, `source_report`, `advisory_only=true`, `ranking_impact="none"` y un bloque `coverage` compacto. No deben reemplazar el JSON técnico principal del reporte.

## Export 1: ofertas detectadas

### Semántica

`steam_deals_offers_export_v1` contiene únicamente ofertas/deals detectados con la cobertura disponible en esa corrida. Si la cache está parcial, el export no promete “todas las ofertas posibles”; promete “ofertas encontradas con la cobertura disponible”.

### Shape propuesto

```json
{
  "schema": "steam_deals_offers_export_v1",
  "generated_at": "2026-06-12T12:00:00Z",
  "source_report": {
    "schema": "steam_deals_report_json",
    "filename": "Steam Deals Example 2026-06-12.json",
    "vanity": "example-user",
    "sale_name": "Steam Sale"
  },
  "advisory_only": true,
  "ranking_impact": "none",
  "coverage": {
    "status": "partial",
    "wishlist_total": 120,
    "priced_or_cached_count": 95,
    "deals_count": 18,
    "deferred_count": 20,
    "failed_or_cooldown_count": 5,
    "notes": ["offers_with_available_coverage"]
  },
  "items": [
    {
      "appid": "123",
      "name": "Example Game",
      "discount_percent": 75,
      "price_final": "Mex$ 49.99",
      "price_original": "Mex$ 199.99",
      "price_raw": 4999,
      "score": 82.4,
      "score_label": "Muy buen deal",
      "score_reasons": ["reviews muy positivas", "descuento fuerte"],
      "cache_state": "fresh",
      "store_url": "https://store.steampowered.com/app/123/",
      "external_offers": [],
      "promo_context": {
        "matched": true,
        "label": "Steam Sale"
      }
    }
  ],
  "limitations": [
    "does_not_include_non_deal_wishlist_items",
    "coverage_may_be_partial",
    "not_purchase_advice"
  ]
}
```

### Campos mínimos por item

- `appid` string numérico.
- `name` si está disponible; si no, usar `null` o omitir, no inventar.
- precio/descuento solo si están confirmados por deal/cache disponible.
- `cache_state` con el vocabulario común de cobertura.
- `score`/`score_reasons` pueden explicar discovery/oferta, no recomendación personalizada.

## Export 2: wishlist completa

### Semántica

`steam_deals_wishlist_export_v1` contiene todos los AppIDs conocidos de la wishlist en la corrida, aunque no tengan oferta o no tengan precio confirmado. Su valor principal es separar “sin oferta” de “no confirmado todavía”.

### Shape propuesto

```json
{
  "schema": "steam_deals_wishlist_export_v1",
  "generated_at": "2026-06-12T12:00:00Z",
  "source_report": {
    "schema": "steam_deals_report_json",
    "filename": "Steam Deals Example 2026-06-12.json",
    "vanity": "example-user",
    "sale_name": "Steam Sale"
  },
  "advisory_only": true,
  "ranking_impact": "none",
  "coverage": {
    "status": "partial",
    "wishlist_total": 120,
    "items_exported": 120,
    "price_confirmed_count": 95,
    "deal_count": 18,
    "not_on_sale_confirmed_count": 77,
    "pending_or_unknown_count": 25
  },
  "items": [
    {
      "appid": "123",
      "name": "Example Game",
      "wishlist_priority": 4,
      "status": "deal_detected",
      "cache_state": "fresh",
      "price": {
        "known": true,
        "on_sale": true,
        "discount_percent": 75,
        "price_final": "Mex$ 49.99",
        "price_original": "Mex$ 199.99",
        "price_raw": 4999
      },
      "store_url": "https://store.steampowered.com/app/123/",
      "signals": {
        "owned": false,
        "family_shared": false,
        "external_access_possible": false
      },
      "limitations": []
    },
    {
      "appid": "456",
      "name": null,
      "wishlist_priority": null,
      "status": "pending_price_confirmation",
      "cache_state": "deferred",
      "price": {
        "known": false,
        "on_sale": null
      },
      "store_url": "https://store.steampowered.com/app/456/",
      "signals": {},
      "limitations": ["not_revalidated_in_this_run"]
    }
  ],
  "limitations": [
    "full_wishlist_does_not_mean_full_price_coverage",
    "cache_state_required_before_interpreting_status",
    "not_purchase_advice"
  ]
}
```

### Estados `status`

| Estado | Uso |
|---|---|
| `deal_detected` | Hay oferta detectada con precio/descuento disponible. |
| `not_on_sale_confirmed` | Precio conocido y sin descuento relevante en la corrida/cache vigente. |
| `pending_price_confirmation` | AppID conocido, pero no fue revalidado o quedó diferido. |
| `temporary_failure` | Fallo externo/rate limit/cooldown; no interpretar como ausencia de oferta. |
| `no_price_confirmed` | Steam/cache no entregó precio útil tras intento; puede ser unavailable/free/no-data. |
| `unknown` | Datos insuficientes para clasificar sin inventar. |

## Vocabulario común de cobertura

Los exports deben alinear `cache_state` con labels ya visibles en cache coverage:

| `cache_state` | Interpretación |
|---|---|
| `fresh` | Dato vigente por TTL/cache actual. |
| `stale_usable` | Dato viejo usado de forma explícita; no equivale a confirmación fresca. |
| `deferred` | Pendiente por presupuesto/resumible; no revalidado en esta corrida. |
| `cooldown` | Fallo reciente/rate limit en cooldown local. |
| `failed_no_data` | Se intentó resolver pero no hubo datos/precio útil. |
| `missing` | Sin dato local suficiente. |
| `unknown` | Estado no mapeado; consumidor debe degradar. |

`coverage.status` debe ser:

- `complete_or_not_required` cuando no hay pendientes relevantes conocidos.
- `partial` cuando hay `deferred`, `cooldown`, `failed_no_data`, `missing` o cobertura parcial del reporte.
- `unknown` si el builder no puede calcular cobertura sin inventar.

## Relación con warm-cache

- Corrida normal: puede generar ambos JSON con cobertura disponible.
- `--warm-cache`: no genera reportes ni exports; solo mejora cache para una corrida posterior.
- `--warm-cache-full`: tampoco genera reportes ni exports; repite pasadas resumibles y luego el usuario genera un reporte normal.
- Web/Desktop copy esperado: “Exporta con la información disponible en este reporte. Para mayor cobertura, continúa/completa warm-cache y vuelve a generar el reporte.”

No usar copy como “wishlist completa con precios completos” salvo que `coverage.status` lo justifique de forma explícita.

## Seguridad y privacidad

Los exports pueden incluir AppIDs de wishlist y nombres de juegos, pero no deben incluir:

- rutas locales de cache/output/imports;
- API keys, Telegram tokens, Discord webhooks, cookies o secretos;
- raw responses completas de Steam/Store/terceros;
- contenido privado no minimizado de imports locales;
- logs, traceback o paths de `_MEIPASS`/home/tmp.

Si una fuente local aporta ownership/acceso, exponer solo señales minimizadas (`owned`, `family_shared`, `external_access_possible`, `source_signal`) y no el archivo fuente ni evidencia cruda.

## Fases de implementación

1. **Builder puro** ✅ implementado
   - Crear helpers determinísticos para `offers_export` y `wishlist_export` desde datos ya disponibles del reporte/cache.
   - Tests con fixtures sin red: oferta confirmada, no oferta confirmada, stale usable, deferred, cooldown, failed/no-data y missing.

2. **Artefactos y serving** ✅ implementado
   - Escribir los dos JSON junto al reporte normal.
   - Actualizar allowlist de `/files` para nombres exactos esperados.
   - No servir `prices_cache.json` ni archivos arbitrarios.

3. **Web/Desktop UX** ✅ implementado
   - Mostrar dos acciones separadas: `Descargar ofertas JSON` y `Descargar wishlist JSON`.
   - Desktop queda cubierto si reutiliza la Web UI.
   - Copy debe mencionar cobertura parcial cuando aplique.

4. **Docs públicas** ✅ implementado en runbook/README/features/PENDIENTES
   - Actualizar `README.md`/`docs/features.md` solo cuando los artefactos existan realmente.
   - Mantener este runbook como contrato técnico y `PENDIENTES.md` como source-of-truth operativo.

## Validación mínima vigente

- `py_compile` de builders/render/output touched.
- Unit tests de builders puros con fixtures de cache state.
- Tests de `write_output_artifacts`/nombres de archivo.
- Tests de `/files` para permitir solo los nuevos JSON esperados.
- Tests Web assets para dos acciones separadas y copy de cobertura parcial.
- `git diff --check`.

No validar con red real, `BG00G`, `--no-cache`, builds ni reportes generados salvo aprobación explícita.
