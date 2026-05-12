# Contrato futuro: wishlist hygiene multi-store

Contrato de decisión para ampliar `wishlist_hygiene` con señales externas/multi-tienda sin cambiar el comportamiento actual.

## Readiness del slice

- Objetivo: definir qué señales externas pueden alimentar `wishlist_hygiene` en un futuro y cómo normalizarlas sin implementar integraciones.
- Fuera de alcance: APIs reales, scraping, credenciales, UI, renderers, scoring, borrado, auto-exclusión, `BG00G`, `--no-cache`, builds y reportes generados.
- Archivos afectados por este slice: `PENDIENTES.md`, `BITACORA.md`, este runbook y el índice de runbooks.
- Validación mínima: revisión documental + `git diff --check`.
- Evidencia esperada: cierre compacto en `BITACORA.md` y resumen corto en `PENDIENTES.md`.
- No hacer permanente: convertir señales externas en acción destructiva o en ajuste de score/ranking.

## Principios

1. `wishlist_hygiene` sigue siendo **advisory-only**.
2. Toda sugerencia requiere revisión manual del usuario.
3. Una señal externa puede explicar “revisar este juego”, pero no puede:
   - borrar juegos;
   - auto-excluir juegos;
   - cambiar score/ranking/filtros;
   - cambiar defaults;
   - abrir carrito o compra.
4. Precio disponible en otra tienda **no equivale** a que el usuario ya tenga el juego.
5. Las señales de propiedad externa deben venir de fuentes explícitas del usuario o registros locales confiables, no de disponibilidad pública.

## Contrato actual que se debe preservar

El payload visible sigue esta semántica base:

```json
{
  "wishlist_hygiene": {
    "source_signals": ["owned", "family", "library", "hltb", "catalog"],
    "items": [
      {
        "appid": "10",
        "name": "Game",
        "signals": ["owned"],
        "reasons": ["ya está en tu biblioteca"],
        "action": "review",
        "advisory_only": true,
        "wishlist_index": 0
      }
    ],
    "summary": {
      "total_wishlist_items": 1,
      "review_items_count": 1,
      "signal_counts": {"owned": 1},
      "advisory_only": true
    }
  }
}
```

Cualquier ampliación multi-store debe ser compatible hacia atrás: los consumidores que solo lean `signals`, `reasons`, `action` y `advisory_only` deben seguir funcionando.

## Extensión propuesta por item

Agregar metadata opcional bajo cada item, sin reemplazar `signals` ni `reasons`:

```json
{
  "appid": "10",
  "name": "Game",
  "signals": ["external_owned"],
  "reasons": ["aparece en una biblioteca externa importada: GOG"],
  "action": "review",
  "advisory_only": true,
  "external_matches": [
    {
      "store_id": "gog",
      "store_name": "GOG",
      "store_type": "library",
      "source": "user_library_export",
      "external_id": "game-slug-or-id",
      "external_name": "Game",
      "match_method": "normalized_title",
      "confidence": "high",
      "evidence": "owned_in_user_export",
      "reason": "Coincidencia en export local de biblioteca GOG",
      "observed_at": "2026-05-12"
    }
  ]
}
```

Campos normalizados:

| Campo | Tipo | Regla |
|---|---|---|
| `store_id` | string estable | `gog`, `epic`, `fanatical`, `itad`, `steam`, `unknown` |
| `store_name` | string visible | Nombre para UI/reportes; escapar al renderizar |
| `store_type` | enum | `library`, `order_export`, `bundle_export`, `price_index`, `catalog`, `manual` |
| `source` | string | Fuente técnica: `user_library_export`, `user_order_export`, `hltb`, `itad_lookup`, etc. |
| `external_id` | string opcional | ID/slug externo si existe |
| `external_name` | string | Nombre externo normalizado solo para explicar el match |
| `match_method` | enum | `steam_appid`, `external_id`, `normalized_title`, `manual` |
| `confidence` | enum | `high`, `medium`, `low` |
| `evidence` | enum/string | Qué prueba la señal: `owned_in_user_export`, `in_hltb_other_store`, `price_only`, etc. |
| `reason` | string | Razón visible compacta |
| `observed_at` | string opcional | Fecha local de la observación/importación |

## Señales aceptables

| Señal | Cuándo usarla | Confianza mínima | Render/copy |
|---|---|---|---|
| `external_owned` | El usuario importó una biblioteca/order export donde el juego figura como propio | `high` | “aparece en biblioteca externa importada” |
| `external_bundle_owned` | El usuario importó una compra/bundle propio donde figura el juego | `high` | “aparece en bundle/orden externa importada” |
| `external_hltb_other_store` | HLTB local indica storefront externo para un registro del usuario | `medium` | “figura en HLTB para otra tienda” |
| `external_review_needed` | Hay match externo útil pero no suficiente para afirmar ownership | `medium` | “revisar match externo antes de limpiar” |

Todas estas señales deben mantener `action="review"` y `advisory_only=true`.

## Señales rechazadas o solo contexto

No deben generar higiene por sí solas:

- Precio disponible en GOG/Epic/Fanatical/ITAD.
- Mínimo histórico en otra tienda.
- Bundle activo público si no hay evidencia de compra del usuario.
- Catálogo público con nombre parecido.
- Match fuzzy de título con `confidence=low`.
- Promoción, publisher sale o marketing message.

Estas señales pueden usarse en otra feature de comparación/precio, pero no como “depurar wishlist”.

## Fuentes candidatas por tienda

| Fuente | Uso permitido en `wishlist_hygiene` | No usar para |
|---|---|---|
| GOG library export/manual import | Señal de propiedad si el usuario provee export local | Scraping o login automático |
| Epic library export/manual import | Señal de propiedad si el usuario provee export local | Credenciales, scraping o launcher automation |
| Fanatical order/bundle export | Señal de propiedad si el usuario provee order/bundle export | Inferir ownership desde bundles públicos |
| ITAD lookup/prices | Contexto de tienda/precio o IDs cruzados en feature separada | Afirmar que el usuario posee el juego |
| HLTB local | Señal secundaria si ya existe en datos locales del usuario | Fuente única para borrar o auto-excluir |

## Criterios de aceptación para un slice de implementación futuro

Antes de implementar una fuente externa:

1. Definir parser puro con fixtures locales, sin red real como requisito de cierre.
2. Validar entradas malformadas, duplicados, nombres ambiguos y caracteres especiales.
3. Normalizar a `external_matches` sin romper el payload actual.
4. Agregar tests determinísticos para:
   - match positivo de alta confianza;
   - match medio que queda como revisión;
   - match bajo rechazado;
   - price-only no cuenta como hygiene;
   - payload vacío no renderiza ruido.
5. Renderizar siempre con copy de revisión manual.
6. Mantener sin cambios score, ranking, defaults y acciones destructivas.

## Validación proporcional futura

| Tipo de cambio futuro | Validación mínima |
|---|---|
| Parser/import local | `py_compile` + tests puros del parser + `WishlistHygieneTests` |
| JSON contract | tests de `generate_json` + shape backward-compatible |
| Markdown/HTML/Web UI visible | tests de renderer/assets + escaping |
| Fuente con red/API real | primero `ExternalScout`/docs actuales, fixtures fake, luego smoke aprobado y acotado |

## Próximo slice implementable recomendado

Primer corte seguro si se prioriza implementación:

> Parser local de export manual GOG/Epic/Fanatical → normaliza una lista de juegos externos a `external_matches` → `build_wishlist_hygiene_signals` lo consume como señal opcional.

Fuera de ese primer corte:

- login automático;
- scraping;
- ITAD live;
- cambios UI grandes;
- borrado/auto-exclusión;
- scoring o defaults.
