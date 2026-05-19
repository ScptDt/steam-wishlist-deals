# Runbook Free Weekend Source Strategy

Estrategia inicial para agregar una sección global `Free Weekend ahora` sin depender de scraping frágil ni mezclar todavía UI/backend/reportes.

## Objetivo

Definir cómo detectar y cachear candidatos globales de Free Weekend independientes de la wishlist, con vigencia, fuente y confianza explícitas. La primera implementación debe ser fixture/local-cache first; el fetch live queda para un slice posterior aprobado.

## Decisión de fuente

No hay un feed público oficial y estable que liste todos los Free Weekends globales actuales con appid y ventana de vigencia. Por eso la estrategia será conservadora y basada en señales corroboradas.

| Fuente | Uso permitido | Datos útiles | Limitaciones |
|---|---|---|---|
| Steamworks Free Weekends docs | Semántica y copy de producto | Define que Free Weekend es acceso temporal al juego base vía paquete temporal; ventana típica jueves-lunes | No lista eventos actuales ni appids |
| `IStoreService/GetAppList` | Universo de apps y cambios para cache | `appid`, nombre, `last_modified`, `price_change_number` | No detecta Free Weekend por sí solo; requiere key/API oficial |
| `featuredcategories` Store JSON | Descubrimiento acotado de candidatos en especiales/curados | `id`, nombre, precio/descuento, posible `discount_expiration` | No exhaustivo; Storefront no documentado/estable como feed Free Weekend |
| `appdetails` Store JSON | Enriquecimiento por appid | `is_free`, `price_overview`, paquetes/grupos, metadata | Storefront no documentado/estable; no garantiza campo Free Weekend |
| `packagedetails` Store JSON | Corroborar paquetes cuando `appdetails` los expone | contenido/precio del paquete | Storefront no documentado/estable; no sirve como descubrimiento global |
| Store search / news | Señal opcional/corroboración | Texto `Free Weekend`, `100%`, appid/título, fechas si aparecen | Más frágil o no estructurado; no usar como única fuente |

Referencias consultadas para esta decisión:

- Steamworks Free Weekends: https://partner.steamgames.com/doc/marketing/discounts/freeweekends
- `ISteamApps::BIsSubscribedFromFreeWeekend`: https://partner.steamgames.com/doc/api/ISteamApps#BIsSubscribedFromFreeWeekend
- `IStoreService/GetAppList`: https://partner.steamgames.com/doc/webapi/IStoreService#GetAppList

## Modelo local propuesto

El contrato futuro puede exponerse como `free_weekend_now` en JSON, pero este slice solo define la forma.

```json
{
  "free_weekend_now": {
    "generated_at": "2026-05-19T00:00:00Z",
    "source_policy": "fixture_or_cached_store_signals_v1",
    "items": [
      {
        "appid": "123456",
        "title": "Example Game",
        "observed_at": "2026-05-19T00:00:00Z",
        "valid_until": "2026-05-20T17:00:00Z",
        "sources": ["featuredcategories", "appdetails"],
        "confidence": "medium",
        "reason": "Store signals show 100% discount/final price 0 with expiration on a normally paid app.",
        "signals": {
          "discount_percent": 100,
          "final_price": 0,
          "is_free": false,
          "matched_text": null,
          "package_ids": []
        },
        "cross_signals": {
          "in_wishlist": false,
          "owned_or_family": null,
          "similar_to_profile": null
        },
        "cross_reasons": []
      }
    ]
  }
}
```

### Campos mínimos

- `appid` y `title`: obligatorios, normalizados como string/nombre visible.
- `observed_at`: cuándo se vio la señal localmente.
- `valid_until`: solo si la fuente trae expiración; si falta, no prometer disponibilidad.
- `sources`: lista de fuentes usadas para esa decisión.
- `confidence`: `high`, `medium` o `low`.
- `reason`: copy técnico corto para debugging/reportes.
- `signals`: datos crudos reducidos necesarios para explicar la clasificación.
- `cross_signals`/`cross_reasons`: señales locales advisory (`en tu wishlist`, `ya en biblioteca`/familia, `similar a tus gustos`); no cambian score ni ranking y deben preservarse si el payload ya las trae.

## Reglas de confianza

| Confianza | Regla inicial |
|---|---|
| `high` | Señal explícita de `Free Weekend` en texto/package/news más corroboración actual por `appdetails`/paquete o vigencia estructurada. |
| `medium` | App normalmente paga con `final_price=0` o `discount_percent=100` y `discount_expiration` futuro desde Store JSON. |
| `low` | Texto o búsqueda sugiere Free Weekend, pero falta expiración o corroboración estructurada. No mostrar como “ahora” sin copy de baja confianza. |

### Exclusiones para evitar falsos positivos

- Juegos permanently free-to-play (`is_free=true` sin señal temporal).
- Demos, playtests, prologues o packages que no den acceso al juego base.
- Free-to-keep/giveaways: son otra categoría, no Free Weekend.
- Descuentos normales sin precio final cero o sin texto de Free Weekend.
- Señales vencidas (`valid_until` pasado) salvo evidencia nueva.

## Cache y TTL

- Guardar respuestas/candidatos en cache local separada de precios, por ejemplo `free_weekend_candidates.json`.
- TTL corto recomendado para fetch live futuro: 6-12 horas, con `observed_at` y `valid_until` por item.
- Si `valid_until` existe y ya pasó, ocultar o marcar `expired` sin borrar evidencia local inmediatamente.
- No invalidar `prices_cache.json` por Free Weekend en este track inicial; el runbook performance mantiene esa puerta cerrada hasta nueva evidencia.

## Implementación futura por slices

1. [x] Parser/clasificador fixture-only para `featuredcategories` + `appdetails` con tests determinísticos (`app/steam_deals_free_weekend.py`, `tests/test_free_weekend_parser.py`).
2. [x] Contrato JSON `free_weekend_now` en el output del generator, sin UI todavía (`renderers/json_renderer.py`, `tests.test_generator_logic`).
3. [x] Secciones Web/HTML/Markdown `Free Weekend ahora` con copy de confianza/vigencia (`renderers/markdown_renderer.py`, `renderers/html_renderer.py`, `web/steam_deals/app.js`).
4. [x] Señales cruzadas (`en tu wishlist`, `ya en biblioteca`, `similar a tus gustos`) sin recalibrar score (`app/steam_deals_free_weekend.py` + renderers/Web existentes).
5. [ ] Fetch live opt-in con TTL/cache, solo después de que fixtures y contrato estén estables.

## No hacer

- No scrape/render de páginas Store como fuente primaria.
- No hardcodear listas largas de appids/eventos.
- No prometer “gratis ahora” si falta vigencia o confianza.
- No mezclar con score, ranking, Top Picks o invalidación de cache de precios.
- No usar red real, `BG00G`, builds ni reportes generados como validación de este slice docs-only.

## Validación mínima para este slice

- Revisión documental contra `PENDIENTES.md`, `BITACORA.md`, `docs/runbooks/README.md` y `performance-warm-cache.md`.
- `git diff --check`.
