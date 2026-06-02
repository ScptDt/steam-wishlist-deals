# Plan: comparativa multi-tienda de precios

Track priorizado para ampliar la comparativa multi-tienda hacia Fanatical y más stores sin mezclarla con `wishlist_hygiene` ni con flujos de compra.

Estado actual: Fase 0/docs, Fase 1 normalizador fixture-only, Fase 1B JSON interno opcional, Fase 1C diagnóstico JSON-consumer, primer render visible mínimo risk-gated, Share HTML, adaptador ITAD fixture-only, lectura de caché ITAD local por flag, configuración Web de esa caché, refresh live opt-in/acotado, trigger Web explícito, pulido UX no-checkout y diagnóstico offline de caché ITAD cerrados entre 2026-05-21 y 2026-06-02. El siguiente paso requiere elegir explícitamente si hacer un live smoke acotado/aprobado con key oficial o ampliar otra superficie local bajo los mismos gates.

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

## Cómo elegir el flujo correcto

- Usa `external_offers` para comparar precio/disponibilidad fuera de Steam. Puede venir de caché ITAD local o de refresh ITAD opt-in, y nunca cambia score/ranking ni prueba ownership.
- Usa `external_matches` cuando el usuario aporta una biblioteca, orden, compra o bundle propio para que `wishlist_hygiene` sugiera revisión manual.
- Usa `play_access` cuando el usuario aporta juegos instalados/jugables localmente para revisar acceso práctico sin compra nueva.
- Trabajar los tres frentes es válido, pero deben avanzar como slices separados: primero UX/contrato claro, luego parsers locales con exports concretos, y solo después live smoke ITAD si hay key oficial y aprobación explícita.

## Enfoque: feature-sliced + risk-gated

No se implementa como “feature-first y luego revisar riesgos”, porque eso podría exponer links, copy o ranking inseguros antes de tiempo. Tampoco se bloquea como “risk-first infinito”.

Regla de trabajo:

> Cada slice entrega una parte de la feature, pero solo avanza al siguiente nivel de visibilidad si pasa sus risk gates.

| Slice | Feature entregada | Risk gate antes de avanzar |
|---|---|---|
| Contrato/normalizador local | Existe `external_offers` normalizado desde fixtures | Clasificación de tienda, `risk_flags`, deny-by-default, sin side effects |
| JSON interno opcional | Cerrado 2026-05-21: el reporte puede transportar ofertas externas explícitas | No ownership, no ranking, no checkout URLs, ausencia compatible |
| Diagnóstico JSON-consumer | Cerrado 2026-05-21: consumidor offline valida el contrato transportado | Detecta drift/riesgos sin UI, sin ranking, sin ownership y sin red |
| Render mínimo | Cerrado 2026-05-21: usuario ve comparativa externa desde JSON local | Solo official/authorized visibles, copy informativo, sin carrito |
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
    "appid_missing",
    "unknown_store",
    "marketplace_keyshop",
    "aggregator_source",
    "drm_unknown",
    "region_unknown",
    "low_confidence",
    "checkout_like_url",
    "unsafe_url_scheme",
    "invalid_price",
    "currency_missing",
    "invalid_currency",
    "ownership_not_proven"
  ]
}
```

Reglas de gating:

- `unknown_store` → ocultar/no destacar.
- `marketplace_keyshop` → ocultar por defecto; solo opt-in futuro.
- `appid_missing` → ocultar/no destacar; no puede competir como oferta externa segura.
- `aggregator_source` → ocultar como tienda final; ITAD es fuente, no tienda destino.
- `low_confidence` → no destacar.
- `drm_unknown` o `region_unknown` → máximo “requiere revisión”, no “mejor oferta”.
- `checkout_like_url` → rechazar link.
- `unsafe_url_scheme` → rechazar link; solo `http`/`https` podrán ser linkeables en fases visibles.
- `invalid_price`, `currency_missing` o `invalid_currency` → ocultar/no destacar.
- `ownership_not_proven` → no alimentar `wishlist_hygiene` como owned.

### Riesgos, mitigaciones y tests esperados

| Riesgo | Mitigación | Regla técnica | Test esperado |
|---|---|---|---|
| Confundir “lo venden barato” con “ya lo tienes” | Separar `external_offers` de `external_matches` | `price_only` nunca emite ownership/hygiene | Oferta con precio no produce `external_owned` |
| Mostrar keyshops grises sin contexto | Ocultos por defecto y opt-in futuro | `store_type=marketplace_keyshop` agrega flag y no destaca | Keyshop queda hidden/no-highlight |
| DRM/región/AppID/moneda incorrecta | Campos visibles y flags de incertidumbre | `drm/region=unknown`, AppID faltante o moneda inválida agregan flags y bajan elegibilidad | Oferta incierta queda review/hidden según riesgo |
| Romper ranking por precio externo | Sección/contrato separado | Normalizador no toca `score`, `top_picks` ni defaults | Tests confirman ranking intacto/ausencia de side effects |
| Checkout encubierto | Copy y URL allowlist conservadora | URLs con `cart`, `checkout`, `add-to-cart` o scheme no `http/https` se rechazan | Link checkout-like/unsafe queda removido o invalidado |
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

## Contrato exacto del normalizador local

Primer slice de implementación: módulo puro `app/steam_deals_external_offers.py` y wrapper raíz `steam_deals_external_offers.py` si se sigue el patrón de `steam_deals_wishlist_hygiene.py`.

### API pública propuesta

```python
def normalize_external_offers(payload, *, include_marketplaces: bool = False) -> dict:
    """Normaliza ofertas externas locales a un payload external_offers seguro."""

def diagnose_external_offers_contract(payload) -> dict:
    """Inspecciona un reporte JSON o payload external_offers sin mutar ranking/ownership."""
```

El helper debe ser puro: sin red, sin filesystem, sin config global, sin tocar ranking, sin leer cache y sin modificar `external_matches`.

### Inputs aceptados en Fase 1

Shapes permitidas:

1. Lista directa de ofertas: `[{...}, {...}]`.
2. Objeto `{ "external_offers": [...] }`.
3. Objeto `{ "offers": [...] }`.
4. Objeto `{ "items": [...] }` solo si representa ofertas, no biblioteca/ownership.

Cada registro puede usar aliases conservadores:

| Campo canónico | Aliases aceptados |
|---|---|
| `appid` | `appid`, `steam_appid`, `wishlist_appid` |
| `name` | `name`, `title`, `steam_name` |
| `store_id` | `store_id`, `store`, `storefront`, `shop` |
| `store_name` | `store_name`, `store`, `storefront`, `shop` |
| `price` | `price`, `final_price`, `amount` |
| `currency` | `currency`, `currency_code` |
| `discount_pct` | `discount_pct`, `discount`, `discount_percent` |
| `url` | `url`, `link` |
| `drm` | `drm`, `platform` |
| `region` | `region`, `country` |
| `source` | `source` |
| `confidence` | `confidence` |
| `observed_at` | `observed_at`, `seen_at` |
| `expires_at` | `expires_at`, `valid_until` |

Payloads vacíos (`None`, `{}`, `[]`) devuelven `{ "items": [], "summary": ... }` sin ruido. Shapes malformadas deben fallar con `ValueError` accionable en tests, sin tracebacks públicos en futuros callers.

### Store registry inicial

El normalizador debe clasificar tiendas por allowlist local, no por texto visible arbitrario:

| `store_id` normalizado | `store_name` | `store_type` | Default |
|---|---|---|---|
| `steam` | Steam | `steam` | visible/base |
| `gog` | GOG | `official_store` | permitido |
| `epic` | Epic Games Store | `official_store` | permitido |
| `microsoft` | Microsoft Store | `official_store` | permitido |
| `humble` | Humble Store | `official_store` | permitido |
| `fanatical` | Fanatical | `authorized_key_reseller` | permitido si fuente confiable |
| `greenmangaming` / `gmg` | Green Man Gaming | `authorized_key_reseller` | permitido si fuente confiable |
| `gamesplanet` | Gamesplanet | `authorized_key_reseller` | permitido si fuente confiable |
| `itad` | IsThereAnyDeal | `aggregator` | fuente, no tienda final |
| `g2a`, `kinguin`, `eneba`, `cdkeys` | nombre visible correspondiente | `marketplace_keyshop` | oculto por defecto |
| cualquier otro | nombre escapado o `Unknown` | `unknown` | oculto/no destacar |

El registry debe ser pequeño y explícito en el primer corte. Agregar una tienda nueva requiere fixture y decisión de `store_type`.

### Output canónico por item

Cada item normalizado debe incluir campos de decisión, no solo datos crudos:

```json
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
  "link_allowed": true,
  "drm": "steam",
  "region": "global",
  "source": "fixture",
  "confidence": "high",
  "observed_at": "2026-05-21",
  "expires_at": null,
  "visibility": "highlight",
  "eligible_for_best_external_price": true,
  "risk_flags": ["ownership_not_proven"]
}
```

`visibility` enum:

| Valor | Uso |
|---|---|
| `highlight` | Puede competir como oferta externa visible futura |
| `review` | Puede mostrarse solo como “requiere revisión” |
| `hidden` | No se muestra por defecto |

Reglas iniciales:

- `highlight`: tienda `official_store` o `authorized_key_reseller`, `confidence=high`, precio/currency válidos, link no checkout-like, DRM y región conocidos.
- `review`: tienda permitida pero `confidence=medium`, DRM desconocido o región desconocida.
- `hidden`: tienda `unknown`, `marketplace_keyshop` sin opt-in, `confidence=low`, precio inválido o URL checkout-like.

`ownership_not_proven` debe estar presente por defecto en ofertas de precio, incluso si la oferta es `highlight`, para reforzar que no alimenta `wishlist_hygiene`.

### Summary canónico

```json
{
  "items_count": 3,
  "highlight_count": 1,
  "review_count": 1,
  "hidden_count": 1,
  "official_or_authorized_count": 2,
  "marketplace_count": 1,
  "best_external_price_count": 1,
  "risk_counts": {
    "ownership_not_proven": 3,
    "marketplace_keyshop": 1
  },
  "advisory_only": true,
  "ranking_impact": "none"
}
```

`best_external_price_count` solo cuenta items `highlight` de tiendas oficiales/autorizadas, nunca marketplaces.

### Dedupe y orden

- Fingerprint recomendado: `(appid, store_id, drm, region, url_normalizada)`.
- Si hay duplicado exacto, conservar determinísticamente:
  1. precio válido más bajo;
  2. mayor confianza (`high` > `medium` > `low`);
  3. primer registro en orden de entrada.
- Orden final recomendado: `highlight` → `review` → `hidden`; dentro de cada grupo, precio ascendente y luego nombre/tienda.

### URLs y checkout-like

El primer slice no renderiza links, pero debe marcar o bloquear URLs riesgosas:

- `link_allowed=false` si la URL contiene segmentos o query obvios de `cart`, `checkout`, `add-to-cart`, `payment`, `purchase`.
- `checkout_like_url` en `risk_flags` cuando se bloquee.
- `link_allowed=false` y `unsafe_url_scheme` si la URL no usa `http`/`https`.
- No intentar resolver redirects ni hacer requests de red.

### Tests mínimos del primer slice

1. Fanatical autorizado, confianza alta, DRM/región conocidos → `highlight`, eligible, `ownership_not_proven`.
2. GOG oficial con región desconocida → `review`, no eligible.
3. G2A/Eneba/Kinguin/CDKeys → `hidden`, `marketplace_keyshop`, no eligible.
4. Store desconocida → `hidden`, `unknown_store`.
5. URL checkout-like → `link_allowed=false`, `checkout_like_url`, no eligible.
6. URL con scheme inseguro (`javascript:`, `data:`) → `link_allowed=false`, `unsafe_url_scheme`, no eligible.
7. `confidence=low` → `hidden`, `low_confidence`.
8. Precio `0` con currency válida cuenta como precio válido.
9. Precio inválido, currency faltante/inválida o AppID ausente → `hidden` con risk flag correspondiente.
10. Dedupe conserva el precio válido más bajo para la misma oferta.
11. Payload vacío devuelve items vacíos + summary segura.
12. No aparece ningún campo `external_matches`, `wishlist_hygiene`, `score`, `top_picks` ni mutation de ranking en el output.

## Fases recomendadas

### Fase 0 — contrato y docs — cerrada

- Crear/ajustar contrato `external_offers`.
- Definir taxonomía de tiendas y copy de riesgo.
- Mantener `external_matches` intacto para `wishlist_hygiene`.
- Validación: revisión documental + `git diff --check`.

### Fase 1 — parser/fixtures sin red — cerrada

- `normalize_external_offers(payload, include_marketplaces=False)` normaliza fixtures/local imports a `external_offers`.
- Cubre Fanatical autorizado, GOG oficial, marketplaces/keyshops ocultos por defecto, low-confidence, URLs checkout-like/unsafe, precio/currency inválidos, dedupe y payload vacío.
- Mantiene `ownership_not_proven`, `advisory_only=true`, `ranking_impact=none` y ausencia de campos prohibidos (`external_matches`, `wishlist_hygiene`, `score`, `top_picks`).
- No hace red, no lee filesystem/config, no renderiza UI por sí mismo y no toca ranking/defaults.

Cierre 2026-05-21:

- Helper y wrapper raíz implementados en `app/steam_deals_external_offers.py` / `steam_deals_external_offers.py`.
- Evidencia y detalle operativo viven en `PENDIENTES.md`/`BITACORA.md`; este bloque queda como referencia histórica de contrato, no como siguiente acción.
- Siguiente acción vigente: usar el selector actual de `PENDIENTES.md` y el estado al inicio de este runbook, no reiniciar en Fase 1.

### Fase 1B — JSON interno opcional — cerrada

- `generate_json` acepta `external_offers` explícito y lo pasa al renderer JSON.
- `renderers/json_renderer.py` serializa `external_offers` solo si es `dict`.
- `summary.external_offers_count` usa `summary.items_count` o fallback a `len(items)`.
- Payloads inválidos/ausentes se omiten con count `0`.
- No normaliza ofertas automáticamente, no llama APIs, no toca UI/renderers HTML/Markdown/Web, no cambia ranking/defaults.

### Fase 1C — diagnóstico JSON-consumer offline — cerrada

- `diagnose_external_offers_contract` acepta un reporte JSON/string JSON o un payload `external_offers` directo.
- Si el contrato está ausente, devuelve estado `absent` sin ruido.
- Si está presente, verifica `items`, `summary`, conteos, `advisory_only=true`, `ranking_impact=none`, risk gates, links bloqueados, separación de ownership/ranking y keyshops no elegibles.
- Devuelve estado `ok`, `warning` o `error` con issues accionables; no muta payloads, no renderiza UI, no llama APIs y no cambia ranking/defaults.

### Fase 2 — ITAD como proveedor preferido

- Usar ITAD para precios multi-tienda cuando haya `itad_key` configurada.
- Mapear Steam AppID → oferta externa sin asumir ownership.
- Clasificar tiendas finales (`official_store`, `authorized_key_reseller`, etc.).
- Si hay error de API, degradar con warning seguro y no romper el reporte.

Corte fixture-only cerrado 2026-05-21:

- Se consultaron docs externas actuales de ITAD API 2.10.0 y Fanatical.
- `itad_prices_to_external_offers` adapta payloads tipo ITAD `prices/v3` ya obtenidos/fixtureados a `external_offers`, reutilizando `normalize_external_offers`.
- Fanatical entra como `authorized_key_reseller` solo cuando ITAD lo reporta como tienda final; Steam se omite como oferta externa.
- URLs checkout-like siguen bloqueadas por el normalizador; tiendas desconocidas quedan ocultas.
- No hay red live nueva, cache, flags CLI/Web, generator wiring ni credenciales en este corte.
- Fanatical no tiene API pública de precios documentada para este uso; no scraping/login/private endpoints.

Corte generator/cache/flag local cerrado 2026-05-21:

- `--itad-external-offers-cache` habilita lectura de una caché JSON local ITAD y la convierte a `external_offers` para Markdown, HTML, Share HTML y JSON.
- El flag no hace red live por sí solo; si la caché falta, está vacía o no mapea los deals actuales, el reporte continúa sin `external_offers`.
- La caché conserva `appid_to_itad_id`, país, timestamp y payloads tipo `prices/v3`; el normalizador mantiene gates de tienda/DRM/región/checkout y `ranking_impact=none`.
- Se agregó helper explícito para payload `prices/v3` con header `ITAD-API-Key`, pensado para un refresh futuro opt-in; no se conectó a un flujo live por defecto.
- No se agregó Web UI, refresh live automático, scraping, credenciales Fanatical, checkout/carrito, ownership, ranking ni defaults.

Corte Web UI local-cache cerrado 2026-05-22:

- `Archivos opcionales` expone `Caché ITAD external_offers (JSON)` para configurar la ruta local sin escribir comandos CLI.
- La Web UI persiste la ruta, `/api/preflight` valida existencia con mensajes públicos redactados y `/api/run` pasa `--itad-external-offers-cache` al generator solo cuando el usuario configuró el archivo.
- El copy conserva que es import local de precios ITAD ya descargados: no hace red live por sí solo, no prueba ownership y no cambia score/ranking/wishlist hygiene.
- No se agregó refresh live, selección automática, scraping, credenciales Fanatical, checkout/carrito, ownership, ranking ni defaults.

Corte refresh live opt-in cerrado 2026-05-22:

- `--itad-refresh-external-offers-cache` refresca en vivo solo bajo opt-in explícito y requiere `--itad-key` + `--itad-external-offers-cache`.
- Reutiliza IDs ITAD ya resueltos por el flujo existente o hace lookup por Steam appid con `ITAD-API-Key` en header; no pone la key en URLs nuevas.
- Obtiene `/games/prices/v3` con header auth, `deals=true` y `capacity=3`, y guarda una caché local con país, timestamp, opciones, `appid_to_itad_id` y payloads tipo `prices/v3`.
- Si falta key/ruta, no hay IDs ITAD o falla fetch/429, no sobreescribe la caché existente y el reporte continúa usando lo local disponible.
- No se agregó live smoke real, scraping, credenciales Fanatical, checkout/carrito, ownership, ranking ni defaults.

Credenciales ITAD seguras:

- Obtener key oficial requiere cuenta regular de IsThereAnyDeal y registrar una app en <https://isthereanydeal.com/apps/my/>; docs oficiales: <https://docs.isthereanydeal.com/>.
- Preferir `STEAM_TOOLS_ITAD_API_KEY` o config local de Web/Desktop; nunca versionar keys ni copiarlas a ejemplos, logs, reportes o issues.
- Aunque algunos endpoints aceptan `key=...`, este proyecto usa `ITAD-API-Key` header en los helpers nuevos para evitar filtrado por URL.
- Sin key válida no hay live smoke ni refresh real; no probar keys random. Mantener fixtures/caché local como alternativa offline.

Corte Web trigger refresh live cerrado 2026-05-22:

- `Filtros avanzados` expone `Refrescar caché ITAD external_offers en vivo (opt-in)` como acción separada del uso normal de caché local.
- `/api/run` pasa `--itad-refresh-external-offers-cache` solo cuando el usuario marca el checkbox; no se guarda como default automático.
- `/api/preflight` exige ITAD key y ruta de caché cuando el refresh está marcado; si el archivo de caché aún no existe, avisa que se creará/actualizará con la ruta pública redactada.
- El copy conserva que es live opt-in, requiere key + caché, no prueba ownership y no cambia score/ranking/wishlist hygiene.
- No se ejecutó live smoke real, no se agregó refresh automático, scraping, credenciales Fanatical, checkout/carrito, ownership, ranking ni defaults.

Corte diagnóstico offline de caché ITAD cerrado 2026-06-02:

- `diagnose_itad_external_offers_cache(cache_payload, appids=None)` inspecciona payloads locales de caché sin leer archivos ni hacer red.
- Reporta caché vacía/malformada, cobertura de mappings AppID→ITAD, appids mapeados sin payload de precios, ofertas normalizables, ofertas ocultas/riesgosas, conteos por risk flag y coverage básico.
- El summary conserva `advisory_only=true` y `ranking_impact=none`; el helper no toca CLI/Web, renderers, score, ranking, ownership ni `wishlist_hygiene`.
- El diagnóstico usa fixtures/caché local únicamente; live smoke ITAD sigue bloqueado sin key oficial configurada y aprobación explícita.

### Fase 3 — render visible mínimo — primer cierre 2026-05-21

Mostrar en JSON/Markdown/HTML/Web UI:

- “Mejor precio fuera de Steam”;
- “Tiendas oficiales/autorizadas”;
- “Steam sigue siendo mejor”;
- “Oferta externa con confianza media/baja”;
- “DRM/región requiere revisión”.

Copy recomendado:

> Comparativa informativa. Steam Tools no compra, no abre carrito y no verifica stock final.

Cierre 2026-05-21:

- Markdown principal, HTML interactivo generado, Share HTML y Web UI del último reporte renderizan `external_offers` solo desde payload local ya transportado en JSON.
- Solo se muestran tiendas `official_store` o `authorized_key_reseller` con `visibility=highlight`/`review`.
- `hidden`, marketplaces/keyshops, tiendas desconocidas, aggregators y ofertas con riesgos bloqueantes quedan fuera del render visible por defecto.
- Los links visibles requieren `link_allowed=true`, URL `http/https` y no checkout/cart/add-to-cart/payment.
- El copy conserva “Comparativa informativa”, “no compra/no abre carrito/no verifica stock final”, “no prueba ownership” y “no cambia score/ranking/wishlist hygiene”.
- No se agregó ITAD/Fanatical live, ranking/defaults ni integración con `wishlist_hygiene`.

Pulido UX/copy 2026-05-22:

- Web UI del último reporte, HTML generado, Markdown y Share HTML cambian la acción externa a `Ver tienda (sin carrito)` para evitar lectura de checkout/carrito.
- El copy visible agrega `sin checkout` y conserva `Comparativa informativa`, `no compra/no abre carrito`, `no verifica stock final`, `no prueba ownership` y `no cambia score/ranking/wishlist hygiene`.
- La Web UI refuerza el link como pill accesible con foco visible sin cambiar payload, backend, endpoints, ranking ni providers.
- No se agregó live smoke real, refresh automático, scraping, credenciales Fanatical, checkout/carrito, ownership, ranking ni defaults.

Chips UX fixture-only 2026-05-22:

- Markdown, HTML generado, Share HTML y Web UI del último reporte agregan chips locales como `Mejor fuera de Steam`, `Tienda autorizada` y `Revisar DRM/región` solo para ofertas ya visibles por los gates existentes.
- Los chips no cambian payload, providers, score, ranking, defaults, ownership ni `wishlist_hygiene`; keyshops, ofertas hidden y links checkout-like siguen fuera del render visible.
- No requiere ITAD key ni red live.

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

Checklist de handoff para otra IA antes de continuar implementación:

1. Leer este runbook completo.
2. Leer `docs/runbooks/wishlist-hygiene-multistore-contract.md` para preservar la separación `external_matches` vs `external_offers`.
3. Confirmar el estado vigente en `PENDIENTES.md` y en el encabezado de este runbook antes de elegir slice.
4. Si el slice es nuevo proveedor, renderer o live smoke, partir de las fases ya cerradas como contrato y no reabrir Fase 1 salvo cambio explícito de shape.
5. No tocar Web UI/renderers/live APIs ni hacer red real fuera del slice aprobado.
6. Detenerse si un test o validación falla; reportar antes de arreglar.

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
