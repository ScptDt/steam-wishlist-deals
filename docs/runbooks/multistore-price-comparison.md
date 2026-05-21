# Plan: comparativa multi-tienda de precios

Track priorizado para ampliar la comparativa multi-tienda hacia Fanatical y más stores sin mezclarla con `wishlist_hygiene` ni con flujos de compra.

Estado actual: Fase 0/docs cerrada el 2026-05-21 y track reclasificado como listo para un primer slice fixture-only. El siguiente paso recomendado es crear el contrato/normalizador local `external_offers` sin red real.

Enfoque de ejecución: **feature-sliced + risk-gated**. La feature avanza por cortes pequeños, pero cada corte debe pasar gates de riesgo antes de exponerse al usuario, tocar ranking o usar fuentes live.

## Objetivo

Mostrar opciones externas de precio/disponibilidad para juegos de la wishlist, con confianza y tipo de tienda claros.

Esto es una comparativa informativa:

- no compra;
- no abre carrito;
- no procesa pagos;
- no borra ni auto-excluye juegos de la wishlist;
- no afirma ownership salvo import local explícito del usuario.

## Separación de contratos

La expansión multi-tienda debe mantener separados estos conceptos:

| Concepto | Contrato | Uso |
|---|---|---|
| Precio/disponibilidad externa | `external_offers` | Comparar ofertas fuera de Steam |
| Propiedad/import del usuario | `external_matches` | Alimentar `wishlist_hygiene` advisory-only |
| Mínimo histórico/global | ITAD/cache actual | Contexto de valor, no ownership |

Regla: un precio externo nunca equivale a “ya lo tienes”. Para ownership externo se requiere evidencia explícita del usuario, como export local de biblioteca/órdenes/bundles.

## Enfoque: feature-sliced + risk-gated

No se implementa como “feature-first y luego revisar riesgos”, porque eso podría exponer links, copy o ranking inseguros antes de tiempo. Tampoco se bloquea como “risk-first infinito”.

Regla de trabajo:

> Cada slice entrega una parte de la feature, pero solo avanza al siguiente nivel de visibilidad si pasa sus risk gates.

| Slice | Feature entregada | Risk gate antes de avanzar |
|---|---|---|
| Contrato/normalizador local | Existe `external_offers` normalizado desde fixtures | Clasificación de tienda, `risk_flags`, deny-by-default, sin side effects |
| JSON interno opcional | El reporte puede transportar ofertas externas | No ownership, no ranking, no checkout URLs, ausencia compatible |
| Render mínimo | Usuario ve comparativa externa | Solo official/authorized visibles, copy informativo, sin carrito |
| ITAD live | Precios reales multi-tienda | Errores seguros, cache/control, confidence y no ownership |
| Fanatical específico | Fanatical aparece como reseller autorizado | Fuente confiable/ITAD o import local; no scraping/login |
| Keyshops/marketplaces | Sección opt-in futura si se decide | Separado, warning, no “mejor precio oficial”, nunca por defecto |

## Minimización máxima de riesgos por slice

La implementación debe mantener gates conservadores: una oferta externa empieza como **no destacable** hasta pasar validaciones explícitas. El primer slice no debe renderizar links ni botones visibles; solo debe normalizar, clasificar y marcar riesgos con fixtures.

### Reglas duras

1. **Deny-by-default**: tiendas desconocidas, baja confianza, DRM/región desconocidos o marketplaces no opt-in no se destacan.
2. **Precio no es ownership**: `external_offers` nunca genera `external_owned`, `external_bundle_owned` ni señales de `wishlist_hygiene`.
3. **Sin exposición visible en el primer corte**: no UI, no botones y no links hasta que el contrato/risk flags estén probados.
4. **Risk flags obligatorios**: toda oferta riesgosa debe conservar señales de por qué no se destaca.
5. **Ranking intocable**: `score`, `top_picks`, filtros, defaults y recomendaciones no cambian por precio externo en las primeras fases.
6. **No checkout encubierto**: no aceptar copy ni URLs de carrito/checkout/add-to-cart/pago.
7. **Keyshops al final**: marketplaces/keyshops solo con opt-in futuro, sección separada y badge de riesgo; nunca mezclados con tiendas oficiales/autorizadas.

### Risk flags mínimos

```json
{
  "risk_flags": [
    "unknown_store",
    "marketplace_keyshop",
    "drm_unknown",
    "region_unknown",
    "low_confidence",
    "checkout_like_url",
    "ownership_not_proven"
  ]
}
```

Reglas de gating:

- `unknown_store` → ocultar/no destacar.
- `marketplace_keyshop` → ocultar por defecto; solo opt-in futuro.
- `low_confidence` → no destacar.
- `drm_unknown` o `region_unknown` → máximo “requiere revisión”, no “mejor oferta”.
- `checkout_like_url` → rechazar link.
- `ownership_not_proven` → no alimentar `wishlist_hygiene` como owned.

### Riesgos, mitigaciones y tests esperados

| Riesgo | Mitigación | Regla técnica | Test esperado |
|---|---|---|---|
| Confundir “lo venden barato” con “ya lo tienes” | Separar `external_offers` de `external_matches` | `price_only` nunca emite ownership/hygiene | Oferta con precio no produce `external_owned` |
| Mostrar keyshops grises sin contexto | Ocultos por defecto y opt-in futuro | `store_type=marketplace_keyshop` agrega flag y no destaca | Keyshop queda hidden/no-highlight |
| DRM/región incorrecta | Campos visibles y flags de incertidumbre | `drm/region=unknown` agrega flag y baja elegibilidad | Oferta unknown queda “requiere revisión” |
| Romper ranking por precio externo | Sección/contrato separado | Normalizador no toca `score`, `top_picks` ni defaults | Tests confirman ranking intacto/ausencia de side effects |
| Checkout encubierto | Copy y URL allowlist conservadora | URLs con `cart`, `checkout`, `add-to-cart` se rechazan | Link checkout-like queda removido o invalidado |
| Mezclar tiendas oficiales con marketplaces | Taxonomía obligatoria | UI futura agrupa por `store_type` y keyshops no compiten | Marketplace no cuenta como “mejor precio oficial” |

## Taxonomía de tiendas

| `store_type` | Ejemplos | Estado por defecto | Regla de UI |
|---|---|---|---|
| `steam` | Steam Store | visible | Base de comparación |
| `official_store` | GOG, Epic, Microsoft Store, Humble Store | visible | Tienda oficial/no keyshop |
| `authorized_key_reseller` | Fanatical, Green Man Gaming, Gamesplanet | visible si fuente confiable | Marcar como reseller autorizado |
| `aggregator` | ITAD | fuente, no tienda final | Mostrar la tienda final, no vender como ITAD |
| `marketplace_keyshop` | G2A, Kinguin, Eneba, marketplaces similares | oculto por defecto | Solo opt-in, con badge de riesgo |
| `manual_import` | JSON/export local del usuario | visible como señal local | No implica precio vigente salvo campo explícito |
| `unknown` | fuente no clasificada | no destacar | Requiere revisión/confianza antes de render prominente |

Decisión inicial: mostrar Steam + tiendas oficiales/autorizadas por defecto. Keyshops/marketplaces grises quedan fuera del “mejor precio” normal y requieren opt-in explícito.

## Contrato propuesto: `external_offers`

Campo top-level futuro del JSON:

```json
{
  "external_offers": {
    "items": [
      {
        "appid": "1145360",
        "name": "Hades",
        "store_id": "fanatical",
        "store_name": "Fanatical",
        "store_type": "authorized_key_reseller",
        "price": 8.99,
        "currency": "USD",
        "discount_pct": 65,
        "url": "https://example.invalid/deal",
        "drm": "steam",
        "region": "global",
        "source": "itad",
        "confidence": "high",
        "observed_at": "2026-05-21",
        "expires_at": null,
        "risk_flags": []
      }
    ],
    "summary": {
      "items_count": 1,
      "official_or_authorized_count": 1,
      "marketplace_count": 0,
      "best_external_price_count": 1
    }
  }
}
```

### Campos mínimos por oferta

| Campo | Regla |
|---|---|
| `appid` | AppID Steam si el match está resuelto; string |
| `store_id` / `store_name` | ID estable + nombre visible escapado al renderizar |
| `store_type` | Enum de la taxonomía anterior |
| `price` / `currency` | Precio normalizado; no renderizar como compra garantizada |
| `discount_pct` | Opcional; derivado o provisto por fuente confiable |
| `url` | Opcional; solo abrir tienda, no carrito/checkout |
| `drm` | `steam`, `gog`, `epic`, `unknown`, etc.; visible si cambia la expectativa del usuario |
| `region` | `global`, país/código o `unknown`; usar warning si no es global |
| `source` | `itad`, `manual_import`, `fixture`, etc. |
| `confidence` | `high`, `medium`, `low`; low no debe destacarse |
| `risk_flags` | Ej. `marketplace`, `region_locked`, `unknown_seller`, `drm_mismatch` |

## Fases recomendadas

### Fase 0 — contrato y docs — cerrada

- Crear/ajustar contrato `external_offers`.
- Definir taxonomía de tiendas y copy de riesgo.
- Mantener `external_matches` intacto para `wishlist_hygiene`.
- Validación: revisión documental + `git diff --check`.

### Fase 1 — parser/fixtures sin red — próximo slice ready

- Helper puro que normalice una lista local de ofertas a `external_offers`.
- Fixtures para Fanatical autorizado, GOG oficial, marketplace oculto, precio low-confidence y DRM mismatch.
- Validar escaping, duplicados, prioridades, `risk_flags` y gating deny-by-default.
- Sin Web UI todavía si el contrato no está estable.

Readiness del próximo slice:

- Objetivo: normalizar ofertas externas locales a `external_offers` con helper puro, fixtures, risk flags y gating conservador.
- Fuera de alcance: ITAD live, Fanatical live, scraping, credenciales, checkout, cambios de score/ranking/defaults y UI grande.
- Archivos probables: helper en `app/`, wrapper raíz si el patrón del repo lo pide, tests puros y este runbook si cambia el shape.
- Validación mínima: `py_compile`, tests puros del normalizador/shape/risk flags/gating, ausencia compatible de `external_offers`, ranking intacto y `git diff --check`.
- Evidencia esperada: cierre compacto en `BITACORA.md` y actualización de `PENDIENTES.md` si cambia el estado del track.

### Fase 2 — ITAD como proveedor preferido

- Usar ITAD para precios multi-tienda cuando haya `itad_key` configurada.
- Mapear Steam AppID → oferta externa sin asumir ownership.
- Clasificar tiendas finales (`official_store`, `authorized_key_reseller`, etc.).
- Si hay error de API, degradar con warning seguro y no romper el reporte.

### Fase 3 — render visible mínimo

Mostrar en JSON/Markdown/HTML/Web UI:

- “Mejor precio fuera de Steam”;
- “Tiendas oficiales/autorizadas”;
- “Steam sigue siendo mejor”;
- “Oferta externa con confianza media/baja”;
- “DRM/región requiere revisión”.

Copy recomendado:

> Comparativa informativa. Steam Tools no compra, no abre carrito y no verifica stock final.

### Fase 4 — Fanatical específico

Fanatical debe entrar primero por fuentes seguras:

1. Precio público vía ITAD o fuente documentada confiable.
2. Import local del usuario para órdenes/bundles propios, que sigue alimentando `external_matches`/`wishlist_hygiene`.

Evitar en el primer corte:

- scraping HTML de Fanatical;
- login automático;
- credenciales de tienda;
- parsing live frágil de páginas públicas.

### Fase 5 — marketplaces/keyshops opt-in

Solo después de tener estable official/authorized.

Reglas:

- desactivado por defecto;
- no mezclar con “mejor precio” oficial/autorizado;
- badge visible: `Marketplace externo / revisar riesgo`;
- warning de región, DRM, vendedor y políticas;
- nunca abrir checkout.

## Criterios de aceptación por slice

Antes de implementar cada fuente o renderer:

1. Readiness corta con objetivo, fuente, riesgos y no-hacer.
2. Fixtures locales para éxito, vacío, duplicado, baja confianza y error.
3. Tests que confirmen que `external_matches` y `wishlist_hygiene` no cambian semántica.
4. Copy visible de revisión manual y sin checkout.
5. Sin red real salvo smoke aprobado y acotado.
6. Sin cambios a score/ranking/defaults en el primer corte.

Checklist de handoff para otra IA antes de empezar implementación:

1. Leer este runbook completo.
2. Leer `docs/runbooks/wishlist-hygiene-multistore-contract.md` para preservar la separación `external_matches` vs `external_offers`.
3. Empezar solo por Fase 1: normalizador local fixture-only.
4. No tocar Web UI/renderers/live APIs en el primer PR/slice.
5. Detenerse si un test o validación falla; reportar antes de arreglar.

## Validación proporcional

| Tipo de cambio | Validación mínima |
|---|---|
| Docs/contrato | revisión documental + `git diff --check` |
| Parser local | `py_compile` + tests puros del parser |
| JSON contract | tests de shape + compatibilidad con ausencia de `external_offers` |
| Render HTML/Markdown/Web | tests renderer/assets + escaping |
| ITAD/API live | ExternalScout/docs actuales + fixtures fake; smoke live solo con aprobación |

## No hacer permanente

- No checkout/carrito/pagos.
- No scraping ni login automático.
- No credenciales de tiendas externas.
- No afirmar ownership por precio/catálogo público.
- No borrar, auto-excluir ni mutar wishlist.
- No recalibrar score/ranking/defaults en el primer corte.
- No mezclar keyshops con tiendas oficiales/autorizadas sin etiqueta y opt-in.
