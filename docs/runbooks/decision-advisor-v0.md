# Decision Advisor v0

Contrato docs-only para usar los campos existentes del reporte Steam Deals como asesor de decisión. El objetivo no es encontrar más descuentos, sino responder una pregunta más útil:

> ¿Vale la pena comprar este juego para este usuario, considerando oferta, compatibilidad, acceso ya disponible y confianza de las señales?

## Readiness del slice

- Objetivo: definir un mapa de decisión sobre payloads ya existentes, sin crear runtime nuevo.
- Fuera de alcance: score, ranking, Top Picks, filtros, defaults, cache, fetching, UI, renderers, endpoints y schema nuevo.
- Archivos afectados: este runbook, índice de runbooks, `PENDIENTES.md` y `BITACORA.md`.
- Validación mínima: revisión documental + `git diff --check`.
- No hacer: checkout/carrito/pagos, auto-buy, auto-hide, auto-remove, borrar wishlist, mutaciones Steam, red real, `BG00G`, `--no-cache`, builds o reportes generados.

## Principios

1. **Buen descuento no equivale a buena compra.** Un juego puede ser barato y aun así redundante, poco compatible o ya accesible.
2. **Separar capas antes de decidir.** Oferta, compatibilidad, accesibilidad/necesidad y confianza deben evaluarse por separado.
3. **Advisory-only.** Toda salida es ayuda para revisión manual; no cambia ranking ni ejecuta acciones.
4. **No inventar señales.** Si falta perfil, cache, propiedad externa o diagnóstico, la conclusión debe marcarse como tentativa o degradarse.
5. **Precio no es ownership.** `external_offers` compara precios; solo imports explícitos (`external_matches`, `play_access`, `steam_access`) pueden alimentar acceso/propiedad advisory.

## Capas de decisión

| Capa | Pregunta | Señales existentes | Lectura esperada | Degradación |
|---|---|---|---|---|
| Oferta | ¿Es buen momento de precio? | `deals`, `top_picks`, precio final/descuento, mínimos históricos/locales, `active_promo_context`, `smart_alert_digest`, `external_offers` | Distinguir precio atractivo, precio normal, promo simultánea y oferta externa segura/review | Si cache/precios son parciales, marcar “tentativo”; no usar oferta externa como propiedad |
| Compatibilidad | ¿Encaja con el usuario? | `personalized_recommendations`, `recommendation_diagnostics`, `taste_priority`, `behavioral_signals`, `behavioral_explanations`, `player_behavior_profile`, `player_behavior_fit`, `decision_support`, tags/géneros, Deck/Proton/anti-cheat | Explicar por qué podría gustar, qué loop/commitment implica y si hay señales personales reales | Si `mode=score_fallback`, baja confianza o `affinity_zero_rate` alto, no sobreprometer afinidad |
| Accesibilidad/necesidad | ¿Hace falta comprarlo? | `wishlist_hygiene`, `access_decision`, `play_access`, `steam_access`, `external_matches`, owned/family/shared, backlog/HLTB cuando exista | Detectar ya owned, Family/shared, probable acceso local, otra tienda o redundancia con backlog | Si la fuente es import local parcial, pedir revisión; nunca afirmar completitud de Family/externos |
| Confianza | ¿Qué tan fuerte es la conclusión? | `recommendation_diagnostics`, estados `available`/`partial`, `cache_coverage`, warm-cache summary, `ranking_impact`, `advisory_only`, source schemas | Separar recomendaciones conductuales de score fallback y conclusiones fuertes de tentativas | Si falta payload opcional, omitir esa base y explicitar limitación |

## Vocabulario de decisión

Estas etiquetas son una guía de producto para consumidores humanos o futuros renders; no son un nuevo payload obligatorio.

| Decisión | Usar cuando | Advertencias típicas |
|---|---|---|
| `comprar_ahora` / Compra inmediata | Oferta fuerte + compatibilidad alta + no parece accesible ya + confianza suficiente | Mantener copy manual/advisory; no enlazar checkout ni prometer “óptimo” |
| `revisar` / Revisar antes de comprar | Buen candidato con señales mixtas, acceso posible, cache parcial, riesgo externo o compatibilidad no concluyente | Pedir mirar Steam page/reviews/backlog antes de decidir |
| `esperar` / Compra futura | Compatibilidad buena pero precio flojo, descuento no urgente, backlog saturado o cobertura insuficiente | No presentarlo como predicción de precio salvo señal explícita de histórico/alerta |
| `ignorar` / Limpiar wishlist | Compatibilidad débil, alta redundancia, riesgo de abandono o ya accesible por otro medio | No borrar ni ocultar automáticamente; solo sugerir revisión manual |

## Tipo de compra / postura

Estas etiquetas son prosa advisory para análisis humano o prompts externos. No son enums de producto ni deben convertirse en score/ranking sin un slice separado.

| Tipo | Usar cuando | Riesgo que comunica |
|---|---|---|
| Comfort Pick | Coincide con patrones observados, loops preferidos o preferencias manuales/locales | Compra segura si también pasa oferta/acceso |
| Stretch Pick | Sale de la zona habitual, pero tiene señales positivas suficientes para investigar | Puede gustar, pero requiere revisar reviews/commitment |
| Aspirational Pick | Atrae conceptualmente, pero tiene pocas señales reales de que el usuario lo jugará | “Me gusta la idea” más que “lo voy a jugar” |
| Impulse Risk | Descuento llamativo con baja afinidad, alta redundancia o evidencia débil | Compra impulsiva probable; bajar prioridad |

## Reglas de interpretación

### Oferta

- Priorizar el contexto de valor sobre el porcentaje bruto: un `-90%` puede ser menos útil que un descuento menor en un juego que el usuario sí jugaría.
- `top_picks` y score final sirven como señales de ranking existente, pero Decision Advisor no debe recalcularlos.
- `external_offers` puede mejorar la lectura de precio/disponibilidad, pero debe conservar risk gates: tienda desconocida, keyshop/marketplace, DRM/región incierta o baja confianza pasan a revisión, no a compra inmediata.

### Compatibilidad

- `decision_support_v1` y `player_behavior_fit_v1` son las señales más directas cuando existen, porque cruzan perfil local/opt-in con señales del juego.
- `recommendation_diagnostics` debe modular el tono. Con `score_fallback` alto, afinidad `0.0` o baja fuerza conductual, explicar que la recomendación viene más del score/oferta que del comportamiento del usuario.
- `taste_priority` aporta redundancia, clusters/core loop y riesgo de abandono, útil para detectar “me gusta la idea” versus “probablemente lo jugaré”.
- Deck/Proton/anti-cheat son compatibilidad técnica, no gusto personal.

### Accesibilidad y necesidad

- `wishlist_hygiene.items[*].access_decision` es la señal visible principal para “ya lo tienes”, “Steam Family” o “probable acceso local”.
- `play_access` y `steam_access` son imports/locales advisory-only; si son parciales, recomendar revisar antes de comprar.
- `external_matches` puede indicar propiedad externa solo si viene de biblioteca/orden/bundle propio. Catálogo público, precio externo o bundle público son contexto, no ownership.
- Si el usuario ya puede jugarlo, la decisión normal debe ser “no comprar ahora” o “comprar solo si quieres copia propia”.

### Confianza y cobertura

- Si la cache de precios o warm-cache cubre solo parte de la wishlist, todas las conclusiones de oferta deben marcarse como tentativas.
- Si faltan señales personales, diferenciar “recomendación por score fallback” de “recomendación por comportamiento”.
- Los estados `partial`, `insufficient_signals` y `unavailable` deben aparecer como limitaciones, no como fallos.

## Payload JSON vigente

El primer slice implementado expone `decision_advisor` como payload top-level opcional en el JSON final cuando existen candidatos válidos. Es un agregador advisory-only, no un recalibrador:

```json
{
  "decision_advisor": {
    "schema": "decision_advisor_v0",
    "status": "available",
    "advisory_only": true,
    "ranking_impact": "none",
    "summary": {
      "items_count": 1,
      "buy_now_count": 1,
      "review_count": 0,
      "wait_count": 0,
      "ignore_count": 0,
      "impulse_risk_count": 0,
      "confidence": "high",
      "recommendation_mode": "behavioral",
      "cache_coverage_status": "complete_or_not_provided",
      "advisory_only": true,
      "ranking_impact": "none"
    },
    "items": [
      {
        "appid": "123",
        "name": "Example Game",
        "decision": "comprar_ahora",
        "priority": "alta",
        "purchase_type": "comfort_pick",
        "confidence": "high",
        "access_status": "requires_purchase",
        "reason": "strong_discount",
        "positive_signals": ["strong_discount", "strong_personal_fit"],
        "risks": [],
        "source_signals": ["deals", "top_picks", "decision_support"]
      }
    ],
    "limitations": ["advisory_only", "ranking_impact_none"]
  }
}
```

Reglas vigentes:

- Se construye solo desde señales ya disponibles (`deals`, `top_picks`, `decision_support`, `taste_priority`, `wishlist_hygiene`, `external_offers`, `recommendation_diagnostics`, `cache_coverage`).
- Se omite si queda vacío, inválido o sin candidatos seguros para serializar.
- `status="partial"` marca conclusiones tentativas si `cache_coverage` es parcial.
- No cambia `score`, `top_picks`, orden, filtros, defaults, cache ni fetching.

## Prompt recomendado para análisis externo

```text
Analiza este reporte de Steam Deals como un asesor de compras de videojuegos.

Objetivo principal:
Ayudar a decidir qué comprar, qué ignorar, qué revisar más a fondo y qué eliminar de la wishlist.

No asumas que el score final es correcto. Evalúa críticamente la calidad de las señales disponibles antes de confiar en cualquier recomendación.

## Paso 1: Diagnóstico de confianza

Determina primero la calidad de la personalización.

Revisa estos campos si existen:

- recommendation_mode
- recommendation_confidence
- affinity_score
- owned_count
- family_count
- activity_records_count
- activity_terms_count
- library_terms_count
- affinity_zero_rate
- profile_depth
- signal_sources
- cache_coverage / cobertura warm-cache

Clasifica el análisis como:

- Behavioral: alta personalización.
- Mixed: personalización parcial.
- Score Fallback: principalmente score/descuento.

Si la personalización, cache o cobertura de señales es débil, indica claramente que las conclusiones son tentativas.

## Paso 2: Analizar cada juego relevante

Para cada juego indica:

### Prioridad

- Alta
- Media
- Baja

### Razón principal

Explica brevemente por qué destaca.

### Señales positivas

Ejemplos:

- gran descuento
- afinidad alta
- coincide con patrones del usuario
- baja saturación
- alta valoración
- buena oportunidad histórica
- disponible en tienda confiable con mejor precio

### Riesgos

Ejemplos:

- afinidad desconocida
- posible redundancia
- backlog elevado
- compromiso excesivo
- señales insuficientes
- posible compra impulsiva
- riesgo externo de tienda/DRM/región
- posible acceso ya cubierto por owned/family/external import

### Recomendación

Clasifica como:

- Comprar ahora
- Revisar más a fondo
- Esperar oferta mejor
- Ignorar por ahora

## Paso 3: Detectar redundancia

Busca señales de:

- juegos similares ya comprados
- juegos similares en Family Sharing
- juegos similares en otras plataformas/imports locales
- exceso de juegos del mismo loop

Ejemplos de loops saturables:

- survival crafting
- colony sim
- farming/life sim
- roguelite
- automation
- grand strategy
- social co-op chaos
- city builder
- management

Explica cuando un juego parece competir directamente contra otros ya disponibles.

## Paso 4: Detectar saturación

Genera un análisis de backlog por loop/género cuando existan señales suficientes.

Ejemplos:

- Saturación alta en survival crafting.
- Saturación media en roguelites.
- Saturación baja en social co-op.

Explica cómo esa saturación afecta la recomendación.

## Paso 5: Evaluar accesibilidad/necesidad de compra

Considera:

- owned
- family shared / probable family shared
- external store/import local
- subscription si aparece en el reporte
- wishlist only

Determina si realmente existe necesidad de compra.

Distingue entre:

- disponible
- disponible parcialmente / requiere revisión
- requiere compra

No trates precio externo o catálogo público como ownership.

## Paso 6: Clasificar tipo de compra

Etiqueta cada juego como:

- Comfort Pick
- Stretch Pick
- Aspirational Pick
- Impulse Risk

Definiciones:

Comfort Pick:
Coincide con patrones de juego observados.

Stretch Pick:
Sale de la zona habitual, pero tiene señales positivas.

Aspirational Pick:
Parece atractivo conceptualmente, pero tiene pocas señales reales.

Impulse Risk:
Descuento atractivo con baja evidencia de interés real.

## Paso 7: Resumen ejecutivo

Genera:

### Top 5 compras recomendadas

Ordenadas por prioridad.

### Top 5 juegos para revisar

Necesitan más investigación.

### Juegos que podrían eliminarse o bajar de prioridad en la wishlist

Explica por qué.

### Juegos probablemente cubiertos por biblioteca existente

Owned, shared, external import o equivalentes claros.

### Conclusión final

Responde:

"Si solo pudiera comprar 3 juegos hoy, compraría estos."

Justifica cada elección.

Recordatorios:
- Diferencia recomendaciones basadas en comportamiento de recomendaciones basadas en score fallback.
- No confundas buen descuento con buena compra.
- No sugieras checkout/carrito/compra automática; todo es advisory-only.
- Marca como tentativas las conclusiones basadas en señales parciales.
```

## Prompt compacto para análisis externo

```text
Analiza este reporte de Steam Deals.

Objetivos:
1. Prioriza qué juegos conviene revisar o comprar ahora.
2. Identifica juegos que parecen buenas ofertas pero probablemente no valen la pena para este usuario.
3. Detecta redundancias con biblioteca, Family Sharing, otras plataformas o backlog existente.
4. Señala riesgos de compra impulsiva.
5. Explica claramente por qué cada juego aparece recomendado.

Ten en cuenta:
- Descuentos y precio histórico.
- Top Picks y score final.
- Afinidad del usuario si existe.
- Cobertura y calidad de señales disponibles.
- Saturación por género/core loop.
- Commitment class: short session, campaign, lifestyle, etc.
- Disponibilidad: owned, family/shared, external store, subscription/import local.
- Recommendation diagnostics.

Si la cobertura de caché o señales es parcial:
- Indica explícitamente qué conclusiones son tentativas.
- Diferencia recomendaciones basadas en comportamiento de recomendaciones basadas en score fallback.
- No confundas buen descuento con buena compra.

Para cada juego indica:
- Prioridad: Alta / Media / Baja.
- Motivo principal.
- Riesgos o advertencias.
- Si parece compra inmediata, compra futura, revisión manual o algo que puede ignorarse.

Al final genera:
- Top 5 compras/revisiones recomendadas.
- Juegos que conviene eliminar o bajar de prioridad en la wishlist.
- Juegos que conviene revisar porque podrían estar disponibles por otros medios.
- Resumen de confianza del análisis.
```

## Slices futuros posibles

1. **Web/Markdown/HTML consumer**: mostrar una tarjeta compacta “Comprar / Revisar / Esperar / Ignorar” usando solo el payload ya aprobado.
2. **Source-policy de accesibilidad de juego**: definir fuentes permitidas para accessibility options reales; no mezclar con compatibilidad técnica Deck/Proton.
3. **Backlog/redundancy stronger fixtures**: mejorar clusters/redundancia solo con fixtures locales y sin ML pesado.

Cualquier slice futuro que toque score, ranking, filtros, defaults, cache, fetching o acciones sobre Steam requiere aprobación explícita separada.
