# Behavioral signals contract

Contrato inicial para modelar patrones de engagement en Steam Deals sin depender de ML, red extra ni perfil público. Este runbook documenta el lenguaje común; la taxonomía versionada vive en `data/behavioral_taxonomy_v1.json`.

## Objetivo

Mover el producto hacia un sistema de **Discovery + Decision Support**:

- **Discovery**: explicar por qué un juego podría gustarle al usuario.
- **Decision**: preparar señales futuras para decidir si conviene comprar, jugar, esperar o ignorar ahora.

`behavioral_signals_v1` clasifica **juegos**, no personas. El perfil de jugador queda explícitamente fuera de este primer contrato.

## Principios

- Advisory-only: nunca borra, auto-excluye ni compra nada.
- `ranking_impact` siempre es `none` en v1.
- No cambia score, ranking, defaults, cache, fetching ni Top Picks.
- No requiere perfil público, wishlist pública, playtime, juegos instalados ni red nueva.
- No usa ML, embeddings, scraping, login ni endpoints nuevos.
- Si faltan señales personales, los consumidores futuros deben degradar con `partial`, `unavailable` o `insufficient_signals`, no fallar ni inventar.
- La taxonomía debe ser amplia para distintos tipos de jugador, no solo para el perfil actual del autor.

## Relación con otras capas

| Capa | Estado | Rol |
|---|---|---|
| `behavioral_taxonomy_v1` | Este slice | Lenguaje versionado: families, loops, descriptors, mappings y reason codes. |
| `behavioral_signals_v1` | Helper puro + JSON interno | Clasifica juegos/deals usando la taxonomía y se expone como payload JSON opcional. |
| `behavioral_explanations_v1` | JSON interno | Consume `behavioral_signals_v1` para exponer headlines, razones y cues compactos reutilizables. |
| `player_behavior_profile_v1` | Futuro | Perfila gustos del usuario cuando existan señales suficientes y opt-in/privacy claros. |
| Decision support | Futuro | Consume señales de juego + perfil + availability/backlog para sugerir comprar/esperar/revisar. |

## Contrato JSON

El reporte JSON expone `behavioral_signals` como payload top-level opcional cuando hay items válidos:

```json
{
  "summary": {
    "behavioral_signals_count": 1,
    "behavioral_explanations_count": 1
  },
  "behavioral_signals": {
    "schema": "behavioral_signals_v1",
    "status": "available",
    "advisory_only": true,
    "ranking_impact": "none",
    "summary": {
      "items_count": 1,
      "families_count": 4,
      "loops_count": 5,
      "descriptors_count": 7,
      "confidence": "medium",
      "taxonomy_schema": "behavioral_taxonomy_v1"
    },
    "items": [
      {
        "appid": "548430",
        "name": "Deep Rock Galactic",
        "families": ["social", "coop_teamwork", "comfort_cozy", "collection_progression"],
        "behavioral_loops": ["emergent_social_chaos", "high_execution_coop", "shared_objective_pressure"],
        "descriptors": ["friends_recommended", "matchmaking_friendly", "mission_based", "short_session"],
        "confidence": "medium",
        "sources": ["steam_tags", "genre_mapping"],
        "reason_codes": ["coop_tags_detected", "social_tags_detected", "mission_structure_detected"]
      }
    ]
  },
  "behavioral_explanations": {
    "schema": "behavioral_explanations_v1",
    "source_schema": "behavioral_signals_v1",
    "status": "available",
    "advisory_only": true,
    "ranking_impact": "none",
    "summary": {
      "items_count": 1,
      "explanations_count": 3,
      "confidence": "medium"
    },
    "items": [
      {
        "appid": "548430",
        "name": "Deep Rock Galactic",
        "headline": "Social + Co-op / teamwork",
        "confidence": "medium",
        "reasons": [
          "Patrones principales: Social + Co-op / teamwork",
          "Loops detectados: Emergent social chaos, High-execution co-op + Shared objective pressure",
          "Contexto de decisión: Friends recommended, Matchmaking friendly + Mission based"
        ],
        "primary_patterns": [
          {"kind": "family", "id": "social", "label": "Social"},
          {"kind": "family", "id": "coop_teamwork", "label": "Co-op / teamwork"}
        ],
        "supporting_cues": [
          {"kind": "behavioral_loop", "id": "emergent_social_chaos", "label": "Emergent social chaos"},
          {"kind": "descriptor", "id": "friends_recommended", "label": "Friends recommended"}
        ],
        "source_signal_ids": {
          "families": ["social", "coop_teamwork"],
          "behavioral_loops": ["emergent_social_chaos", "high_execution_coop", "shared_objective_pressure"],
          "descriptors": ["friends_recommended", "matchmaking_friendly", "mission_based"]
        }
      }
    ]
  }
}
```

Si no hay items válidos, los payloads top-level `behavioral_signals` y `behavioral_explanations` deben omitirse o exponerse solo en diagnósticos internos con `status` no disponible. No deben romper consumidores existentes.

## Explicaciones JSON-only

`behavioral_explanations_v1` es un consumidor interno, no una UI visible. Su rol es traducir IDs estables de la taxonomía a material compacto para futuros consumidores de Discovery/Decision:

- `headline`: resumen corto con 1-2 patrones principales.
- `reasons`: frases compactas derivadas de families, loops y descriptors.
- `primary_patterns`: labels/descripciones de families principales.
- `supporting_cues`: loops/descriptors etiquetados para futuros renders o decision support.
- `source_signal_ids`: IDs originales para trazabilidad y pruebas.

Reglas:

- no inventar afinidad personal ni perfil de jugador;
- omitir payload si `behavioral_signals` no tiene items válidos;
- conservar `advisory_only=true` y `ranking_impact=none`;
- no cambiar score, ranking, defaults, cache ni fetching.

## Plan F — definición de producto para consumidor visible

Plan F desbloquea un consumidor visible futuro sin cambiar el contrato JSON. El objetivo no es decidir compras ni recalibrar el ranking, sino explicar de forma compacta **por qué un juego podría valer la pena revisar** usando señales ya calculadas.

### Primer slice implementable aprobado para planificar

- **Superficie**: HTML interactivo generado, dentro de `Recomendaciones personalizadas`, un juego por card cuando exista match por `appid`/`steam_appid`.
- **Título/copy base**: `Por qué podría gustarte` para confianza `medium`/`high`; usar `Señales de estilo del juego` si la confianza es `low` para no prometer afinidad personal.
- **Fuente única**: `behavioral_explanations.items` existente. No leer red, no recalcular preferencias y no crear payloads nuevos.
- **Campos permitidos**: `headline`, hasta 2 frases de `reasons`, y hasta 3 labels de `supporting_cues` si aportan claridad.
- **Fallback**: si el payload falta, está inválido, no tiene appid numérico o no matchea la recomendación visible, omitir el bloque sin empty state.
- **Nota obligatoria**: indicar cerca del bloque que es advisory-only y que no cambia score/ranking.

### No objetivos de Plan F v1

- No construir `player_behavior_profile_v1`.
- No inferir gustos personales sin señales explícitas.
- No cambiar Top Picks, score, ranking, defaults, cache, fetching ni orden de recomendaciones.
- No mover la señal a Web UI, Markdown o Share HTML en el mismo slice; esas superficies requieren slices separados.
- No mostrar behavioral signals crudos si no pasan por `behavioral_explanations_v1`.

### Validación requerida para el primer slice visible

- Fixture con recomendación personalizada que sí tenga explicación behavioral y renderice el bloque compacto.
- Fixture con recomendación sin explicación/mismatch que omita el bloque sin romper la card.
- Fixture con payload malformado o appid inválido que degrade sin excepción.
- Validación dirigida de renderer y `git diff --check`; sin reportes generados, red real, `BG00G`, `--no-cache` ni builds.

## Estados y degradación

Estados permitidos:

- `available`: hay señales suficientes para al menos un item.
- `partial`: hay señales, pero faltan fuentes relevantes o la confianza es baja.
- `unavailable`: no se puede construir la señal por taxonomía faltante/inválida u otra causa controlada.
- `insufficient_signals`: las entradas no tienen tags/géneros/mapping suficiente.

Razones permitidas iniciales:

- `profile_private_or_unavailable`
- `wishlist_private_or_unavailable`
- `owned_games_unavailable`
- `insufficient_behavioral_matches`
- `taxonomy_missing`
- `taxonomy_invalid`
- `no_supported_game_metadata`

Regla: `behavioral_signals_v1` debe funcionar sin perfil/wishlist públicos. Esas razones existen para consumidores personalizados futuros.

## Confidence

Niveles:

- `high`: mapping manual/known-appid o combinación fuerte de tags específicos.
- `medium`: varias señales coherentes de tags/géneros.
- `low`: una señal débil o género genérico.
- `unknown`: no hay evidencia suficiente.

La confianza describe la clasificación del juego, no afinidad del usuario.

## Taxonomía v1.1

La lista exhaustiva versionada está en `data/behavioral_taxonomy_v1.json`. Resumen:

### Families

```text
social
coop_teamwork
competition
mastery_skill
action_arcade
optimization
strategy_planning
management_simulation
exploration_discovery
narrative
creativity_sandbox
collection_progression
survival_pressure
horror_tension
comfort_cozy
puzzle_problem_solving
immersion_roleplay
sports_racing
simulation_realism
rhythm_music
```

### Descriptor groups

```text
session_time
social_requirement
online_availability_friction
commitment
replay_structure
mental_load
skill_difficulty
content_style
pace_intensity
risk_friction
```

## Mapping v1

El mapping convierte tags/géneros conocidos a families, loops, descriptors y reason codes. Debe ser conservador:

- Un tag genérico aporta confianza baja.
- Tags específicos o combinaciones coherentes suben a confianza media.
- Mappings manuales o appids conocidos pueden subir a alta confianza en slices futuros.

Ejemplo:

```json
{
  "online co-op": {
    "families": ["coop_teamwork"],
    "behavioral_loops": ["shared_objective_pressure", "tactical_coop"],
    "descriptors": ["friends_recommended", "online_required", "matchmaking_friendly"],
    "reason_codes": ["coop_tags_detected"],
    "base_confidence": "medium"
  }
}
```

## Normalización esperada

El helper debe:

- normalizar tags/géneros a minúsculas, espacios simples y sin guiones irrelevantes;
- deduplicar families, loops, descriptors, sources y reason codes;
- ignorar valores que no existan en la taxonomía;
- omitir items sin `appid` o sin señales válidas;
- ordenar de forma estable;
- no incluir rutas locales, playtime crudo sensible, secretos ni datos personales no necesarios.

## Player profile queda futuro

`player_behavior_profile_v1` sí es deseable, pero no se implementa hasta que `behavioral_signals_v1` esté estable. Futuras fuentes posibles:

- wishlist pública si está disponible;
- owned/library ya utilizados por el reporte;
- favoritos o comfort games seleccionados manualmente;
- import local explícito;
- playtime/installed/recent activity solo con opt-in claro.

Si faltan señales personales, el perfil futuro debe usar `status=unavailable` o `insufficient_signals` con razón accionable, no fallback silencioso.

## No-hacer v1

- No recalibrar score/ranking/defaults.
- No usar red extra, scraping, login, SteamKit2 ni endpoints nuevos.
- No inferir preferencias personales sin señales.
- No inferir ownership/play access desde precio/catálogo público.
- No mezclar con `wishlist_hygiene`, `external_offers` ni `play_access` salvo como consumidor futuro explícito.
- No generar UI visible en los slices de contrato/JSON-only; cualquier consumidor visible debe seguir la definición Plan F y aprobarse como slice separado.
- No ejecutar `BG00G`, `--no-cache`, builds, smokes live ni reportes generados para validar este contrato.

## Slices recomendados

1. **Docs/taxonomy**: este runbook + `data/behavioral_taxonomy_v1.json`.
2. **Helper puro**: `app/steam_deals_behavioral.py` carga/valida taxonomía y clasifica fixtures locales.
3. **JSON-only**: `generate_json` serializa `behavioral_signals` top-level y `summary.behavioral_signals_count`.
4. **Explicaciones JSON-only**: `behavioral_explanations` traduce IDs a headlines/razones/cues compactos sin UI visible.
5. **Plan F definición**: documentar copy, fuente única, superficies y no-objetivos antes de cualquier UI visible.
6. **Plan F primer consumidor visible**: explicación compacta en `Recomendaciones personalizadas` del HTML generado, usando solo `behavioral_explanations_v1` y con `ranking_impact=none`.
7. **Consumidores futuros**: discovery/decision reasons en otras superficies aprobadas por slice y eventualmente `player_behavior_profile_v1`.
