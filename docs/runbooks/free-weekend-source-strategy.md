# Runbook Free Weekend Source Strategy

Estrategia y operación actual para la sección global `Free Weekend ahora` sin depender de scraping frágil ni mezclar la señal con score/ranking, Top Picks o caché de precios.

## Objetivo

Definir cómo detectar, normalizar y cachear candidatos globales de Free Weekend independientes de la wishlist, con vigencia, fuente y confianza explícitas. La política vigente es fixture/local-cache first; las fuentes live existen solo como opt-in y deben seguir siendo advisory-only.

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
| Registros JSON locales | Fuente offline/manual prioritaria | `appid`, título, vigencia, fuente, confianza o campos equivalentes normalizables | Requiere que el operador ya haya corroborado los datos; no hace fetch live |
| LootScraper Atom Steam | Señal candidata opt-in experimental | Links Store, categorías/texto, hints de fechas | Fuente de terceros, no autoritativa; tratar como candidato y revisar vigencia/confianza |
| FreeToKeep | Investigación/corroboración manual | Puede señalar campañas gratis/temporales | No hay API pública limpia/documentada; no usar como dependencia directa ni como Free Weekend autoritativo |

Referencias consultadas para esta decisión:

- Steamworks Free Weekends: https://partner.steamgames.com/doc/marketing/discounts/freeweekends
- `ISteamApps::BIsSubscribedFromFreeWeekend`: https://partner.steamgames.com/doc/api/ISteamApps#BIsSubscribedFromFreeWeekend
- `IStoreService/GetAppList`: https://partner.steamgames.com/doc/webapi/IStoreService#GetAppList
- LootScraper Steam Atom: https://feed.eikowagenknecht.com/lootscraper_steam_game.xml

## Uso actual

| Entrada | Flag/UI | Red live | Precedencia | Notas |
|---|---|---:|---:|---|
| Caché dedicado vigente | automático | No | 2 | Reutiliza `free_weekend_candidates.json` si existe y no expiró. |
| Store JSON | `--free-weekend-live` / checkbox Web `Buscar Free Weekend ahora` | Sí, opt-in | 3 | Consulta `featuredcategories` + `appdetails` por appid; guarda caché dedicado. |
| Registros locales | `--free-weekend-records-json PATH` | No | 1 | Normaliza registros externos ya corroborados y evita cualquier fuente live. |
| LootScraper Atom | `--free-weekend-lootscraper-live` / checkbox Web experimental | Sí, opt-in | 2 antes de Store live | Usa el feed Atom como señal candidata; si no produce payload y también está Store live activo, puede continuar con Store. |

Reglas operativas:

- `--free-weekend-records-json` gana sobre LootScraper y Store live.
- LootScraper y Store comparten el caché dedicado `free_weekend_candidates.json`, separado de `prices_cache.json`.
- Activar cualquier live source requiere acción explícita del usuario; no cambiar defaults para hacerlo automático.
- La sección `Free Weekend ahora` no reordena deals, no recalibra score y no invalida cache de precios.

## Modelo local

El contrato se expone como `free_weekend_now` en JSON cuando existe payload válido de caché, registros locales o fuente live opt-in.

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

- Guardar respuestas/candidatos en cache local separada de precios: `free_weekend_candidates.json`.
- TTL vigente del fetch live: 12 horas, con `observed_at` y `valid_until` por item cuando la fuente lo permita.
- Si `valid_until` existe y ya pasó, ocultar o marcar `expired` sin borrar evidencia local inmediatamente.
- No invalidar `prices_cache.json` por Free Weekend en este track inicial; el runbook performance mantiene esa puerta cerrada hasta nueva evidencia.

## Implementación futura por slices

1. [x] Parser/clasificador fixture-only para `featuredcategories` + `appdetails` con tests determinísticos (`app/steam_deals_free_weekend.py`, `tests/test_free_weekend_parser.py`).
2. [x] Contrato JSON `free_weekend_now` en el output del generator, sin UI todavía (`renderers/json_renderer.py`, `tests.test_generator_logic`).
3. [x] Secciones Web/HTML/Markdown `Free Weekend ahora` con copy de confianza/vigencia (`renderers/markdown_renderer.py`, `renderers/html_renderer.py`, `web/steam_deals/app.js`).
4. [x] Señales cruzadas (`en tu wishlist`, `ya en biblioteca`, `similar a tus gustos`) sin recalibrar score (`app/steam_deals_free_weekend.py` + renderers/Web existentes).
5. [x] Fetch live Store opt-in con TTL/cache dedicado, validado offline con fake fetch/cache y sin red real.
6. [x] Entrada `--free-weekend-records-json` para registros locales ya corroborados, sin red live.
7. [x] Parser offline de LootScraper Atom a registros externos con fixture determinística.
8. [x] Resolución LootScraper live opt-in con cache-first y fallback conservador.
9. [x] Web/Desktop exponen el checkbox experimental de LootScraper Atom sin cambiar defaults.

## No hacer

- No scrape/render de páginas Store como fuente primaria.
- No depender de FreeToKeep/RSC ni páginas renderizadas como integración directa.
- No hardcodear listas largas de appids/eventos.
- No prometer “gratis ahora” si falta vigencia o confianza.
- No mezclar con score, ranking, Top Picks o invalidación de cache de precios.
- No tratar LootScraper como fuente autoritativa; es señal candidata opt-in.
- No usar red real, `BG00G`, builds ni reportes generados como validación automática; el live real requiere aprobación explícita.

## Validación mínima para cambios de este track

- Revisión documental contra `PENDIENTES.md`, `BITACORA.md`, `docs/runbooks/README.md` y `performance-warm-cache.md` si cambia el estado operativo.
- Tests offline con fixtures/fake fetch/cache/time si cambia parser, resolver, TTL/cache o wiring opt-in.
- Tests dirigidos de `build_command` y assets web si cambia un checkbox/flag Web/Desktop.
- Smoke live real solo con aprobación explícita, cache/log/output aislados y sin `--no-cache`; `appdetails` debe consultarse por appid o con fallback conservador si Store rechaza batches multi-appid.
- `git diff --check`.
