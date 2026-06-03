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
| `behavioral_explanations_v1` | JSON interno + consumidores Plan F | Consume `behavioral_signals_v1` para exponer headlines, razones y cues compactos reutilizables. |
| `player_behavior_profile_v1` | JSON interno opcional | Perfila preferencias conductuales del usuario con señales locales/opt-in; se expone solo si hay preferencias útiles. |
| `player_behavior_fit_v1` | JSON interno opcional | Cruza perfil del jugador con señales de juego por item, sin score numérico ni impacto en ranking. |
| `decision_support_v1` | JSON interno opcional | Traduce fit cualitativo en etiquetas de revisión (`good_fit`, `maybe`, `weak_fit`) sin compra automática ni impacto en ranking. |

## Contrato JSON

El reporte JSON expone `behavioral_signals` como payload top-level opcional cuando hay items válidos:

```json
{
  "summary": {
    "behavioral_signals_count": 1,
    "behavioral_explanations_count": 1,
    "player_behavior_profile_status": "available",
    "player_behavior_profile_sources_count": 3
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
  },
  "player_behavior_profile": {
    "schema": "player_behavior_profile_v1",
    "status": "available",
    "advisory_only": true,
    "ranking_impact": "none",
    "profile_scope": "local_run",
    "confidence": "medium",
    "source_signals": ["manual_preferences", "local_activity", "wishlist_terms"],
    "summary": {
      "families_count": 2,
      "loops_count": 2,
      "descriptors_count": 2,
      "opt_in_sources_count": 3,
      "taxonomy_schema": "behavioral_taxonomy_v1"
    },
    "preferred_families": [
      {"id": "coop_teamwork", "label": "Co-op / teamwork", "strength": "strong", "confidence": "medium"}
    ],
    "preferred_loops": [
      {"id": "shared_objective_pressure", "label": "Shared objective pressure", "strength": "medium", "confidence": "medium"}
    ],
    "preferred_descriptors": [
      {"id": "short_session", "label": "Short session", "strength": "weak", "confidence": "low"}
    ],
    "evidence_summary": {
      "manual_preferences_count": 2,
      "activity_terms_count": 3,
      "library_terms_count": 0,
      "wishlist_terms_count": 3,
      "personalized_profile_terms_count": 0
    },
    "limitations": ["local_snapshot", "not_purchase_advice", "ranking_impact_none"]
  }
}
```

Si no hay items válidos, los payloads top-level `behavioral_signals` y `behavioral_explanations` deben omitirse o exponerse solo en diagnósticos internos con `status` no disponible. Si `player_behavior_profile_v1` no tiene preferencias útiles o queda en `insufficient_signals`/`unavailable`, también debe omitirse del JSON público final y conservar solo el estado interno si un consumidor lo necesita. No deben romper consumidores existentes.

## Explicaciones y consumidores visibles

`behavioral_explanations_v1` nació como consumidor interno para traducir IDs estables de la taxonomía a material compacto. Plan F lo consume de forma visible en `Recomendaciones personalizadas` del HTML generado, Web UI del último reporte, Markdown principal y Share HTML, sin cambiar el contrato JSON:

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

Plan F define consumidores visibles sin cambiar el contrato JSON. El objetivo no es decidir compras ni recalibrar el ranking, sino explicar de forma compacta **por qué un juego podría valer la pena revisar** usando señales ya calculadas.

### Consumidores visibles cerrados

- **Superficies**: HTML interactivo generado, Web UI del último reporte, Markdown principal y Share HTML, siempre dentro de `Recomendaciones personalizadas`, un juego por card/item cuando exista match por `appid`/`steam_appid`.
- **Título/copy base**: `Por qué podría gustarte` para confianza `medium`/`high`; usar `Señales de estilo del juego` si la confianza es `low` para no prometer afinidad personal.
- **Fuente única**: `behavioral_explanations.items` existente. No leer red, no recalcular preferencias y no crear payloads nuevos.
- **Campos permitidos**: `headline`, hasta 2 frases de `reasons`, y hasta 3 labels de `supporting_cues` si aportan claridad.
- **Fallback**: si el payload falta, está inválido, no tiene appid numérico o no matchea la recomendación visible, omitir el bloque sin empty state.
- **Nota obligatoria**: indicar cerca del bloque que es advisory-only y que no cambia score/ranking.

### No objetivos de Plan F v1

- No construir ni consumir `player_behavior_profile_v1` dentro de Plan F; ese perfil vive en un slice separado y no altera estas explicaciones visibles.
- No inferir gustos personales sin señales explícitas.
- No cambiar Top Picks, score, ranking, defaults, cache, fetching ni orden de recomendaciones.
- No mover la señal a otra superficie sin slice separado.
- No mostrar behavioral signals crudos si no pasan por `behavioral_explanations_v1`.

### Validación requerida para consumidores visibles

- Fixture con recomendación personalizada que sí tenga explicación behavioral y renderice el bloque compacto.
- Fixture con recomendación sin explicación/mismatch que omita el bloque sin romper la card.
- Fixture con payload malformado o appid inválido que degrade sin excepción.
- Validación dirigida de renderer y `git diff --check`; sin reportes generados, red real, `BG00G`, `--no-cache` ni builds.

## Player behavior profile v1 (JSON interno opcional)

`player_behavior_profile_v1` perfila **preferencias conductuales del usuario**, no juegos. Su objetivo es dar contexto para Discovery/Decision Support, por ejemplo: “parece que prefieres co-op corto y progresión por colección”. No decide compras, no recalibra recomendaciones y no altera score/ranking.

### Principios de producto y privacidad

- Local-first y opt-in defensivo: solo usar señales ya disponibles en la corrida o importadas explícitamente por el usuario.
- Advisory-only: `advisory_only=true` y `ranking_impact=none` obligatorios.
- Sin perfil público obligatorio: si Steam/actividad/biblioteca no están disponibles, degradar con estado y razón accionable.
- Minimización de datos: preferir agregados, labels y conteos; no exponer rutas locales, secretos, IDs privados innecesarios ni listas crudas de playtime.
- No usar ML/embeddings, scraping, login, SteamKit2, endpoints nuevos ni red extra en v1.
- No mezclar ownership/import local (`external_matches`, `play_access`) ni precios externos (`external_offers`) como fuentes de gusto; podrían ser consumidores futuros, no señales de perfil.

### Fuentes permitidas en v1

Usar solo si existen y el usuario no las deshabilitó:

- `manual_preferences`: juegos favoritos, comfort games, disliked/avoid o relaciones `similar_to` agregadas explícitamente. En CLI puede entrar como JSON local opt-in mediante `--player-preferences-json`.
- `local_activity`: actividad reciente/local ya importada o disponible en el reporte, preferentemente agregada por tags/families/loops.
- `library_summary`: biblioteca/owned/family ya usada por el reporte, agregada por géneros/tags/families; no afirmar ownership externo por precios.
- `wishlist_terms`: señales de la wishlist/deals actuales ya cargados, sin fetch adicional.
- `personalized_recommendations.profile`: resumen ya existente de actividad/biblioteca como señal secundaria, no como verdad absoluta.

### Shape vigente

El payload es top-level opcional y debe omitirse si no hay información útil. Shape vigente:

```json
{
  "schema": "player_behavior_profile_v1",
  "status": "available",
  "advisory_only": true,
  "ranking_impact": "none",
  "profile_scope": "local_run",
  "confidence": "medium",
  "source_signals": ["manual_preferences", "local_activity", "library_summary"],
  "summary": {
    "families_count": 3,
    "loops_count": 4,
    "descriptors_count": 5,
    "opt_in_sources_count": 2
  },
  "preferred_families": [
    {"id": "coop_teamwork", "label": "Co-op / teamwork", "strength": "strong", "confidence": "medium"}
  ],
  "preferred_loops": [
    {"id": "shared_objective_pressure", "label": "Shared objective pressure", "strength": "medium", "confidence": "low"}
  ],
  "preferred_descriptors": [
    {"id": "short_session", "label": "Short session", "strength": "medium", "confidence": "medium"}
  ],
  "evidence_summary": {
    "manual_preferences_count": 2,
    "activity_terms_count": 3,
    "library_terms_count": 5
  },
  "limitations": ["local_snapshot", "not_purchase_advice", "ranking_impact_none"]
}
```

Reglas de shape:

- `strength` es una etiqueta cualitativa (`weak`, `medium`, `strong`), no score numérico.
- `confidence` describe calidad/cobertura de señales, no certeza psicológica.
- `evidence_summary` debe usar conteos/agregados; no incluir rutas, secretos ni listas crudas largas.
- `preferred_*` debe usar IDs existentes en `behavioral_taxonomy_v1` y labels derivados de la taxonomía.

### Estados y degradación del perfil

- `available`: hay al menos dos fuentes útiles o una fuente manual explícita fuerte.
- `partial`: hay señales, pero con cobertura limitada, genérica o sin opt-in manual.
- `insufficient_signals`: no hay señales suficientes para preferencias conductuales.
- `unavailable`: el usuario deshabilitó señales personales, falta input local o la taxonomía no está disponible.

Razones sugeridas: `profile_opted_out`, `insufficient_personal_signals`, `manual_preferences_missing`, `local_activity_unavailable`, `library_summary_unavailable`, `taxonomy_missing`, `taxonomy_invalid`.

### Primer slice implementado

El primer slice **JSON-only** quedó implementado el 2026-06-02:

1. helper puro con fixtures locales;
2. payload top-level opcional en JSON;
3. resumen `summary.player_behavior_profile_status` y `summary.player_behavior_profile_sources_count` solo cuando el payload se serializa;
4. sin UI visible, sin score/ranking, sin cambios de Top Picks y sin red extra.

Siguientes slices posibles deben mantenerse separados: documentación/plantillas de ejemplo para preferencias manuales, decision-support JSON-only sobre disponibilidad/backlog, y solo después un consumidor visible con decisión explícita de UX/privacidad.

### Entrada local opt-in de preferencias manuales

El primer input explícito de usuario para el perfil es `--player-preferences-json <ruta>`. Reglas:

- lee solo un archivo JSON local proporcionado por el usuario; no hace red ni persistencia automática;
- acepta un objeto directo o `{ "manual_preferences": { ... } }`;
- normaliza solo campos permitidos (`preferred_families`, `preferred_loops`, `preferred_descriptors`, `preferred_terms`, `tags`, `genres`, `favorite_games`, `comfort_games`, `liked_games`);
- descarta campos extra/debug antes de entrar al perfil y el JSON final sigue usando solo agregados/labels/conteos;
- JSON inválido o shape top-level no soportado falla con error local accionable y no genera reporte parcial.

Ejemplo de uso CLI:

```bash
python3 steam_deals_generator.py --vanity gaben \
  --player-preferences-json ./mis-preferencias-jugador.json
```

Shape mínima:

```json
{
  "manual_preferences": {
    "preferred_families": ["coop_teamwork"],
    "preferred_terms": ["online co-op", "loot"],
    "favorite_games": [{"tags": ["Horror", "Online Co-op"]}]
  }
}
```

La plantilla editable versionada vive en `docs/player-preferences.example.json`. Copiarla a un archivo local personal antes de usarla; no versionar preferencias privadas. En `favorite_games`, `comfort_games` y `liked_games` solo se consumen señales agregables (`tags`, `steam_tags`, `genres`, `steam_genres`, `categories`, `steam_categories`); rutas locales, AppIDs, playtime, nombres y campos debug no entran al perfil final.

### Fit JSON-only entre perfil y señales de juego

`player_behavior_fit_v1` es un payload top-level opcional que cruza `player_behavior_profile_v1` con `behavioral_signals_v1` por IDs de taxonomía. Reglas:

- `advisory_only=true` y `ranking_impact=none` obligatorios;
- no produce score numérico, no modifica `score`, `personalized_score`, Top Picks, orden ni filtros;
- usa labels/IDs de taxonomía para `matched_families`, `matched_loops` y `matched_descriptors`;
- `fit_level` es cualitativo (`weak`, `medium`, `strong`);
- se omite si no hay perfil útil, señales de juego útiles o matches entre ambos;
- no expone rutas locales, playtime crudo, AppIDs personales ni campos debug del perfil.

### Decision support JSON-only

`decision_support_v1` es un payload top-level opcional que consume `player_behavior_profile_v1` + `player_behavior_fit_v1` y genera ayuda cualitativa para revisar juegos. Reglas:

- `advisory_only=true` y `ranking_impact=none` obligatorios;
- no produce score numérico, no modifica `score`, `personalized_score`, Top Picks, orden ni filtros;
- `decision_label` permitido por item: `good_fit`, `maybe`, `weak_fit`;
- `fit_reasons` reutiliza reason codes del fit (`profile_family_match`, `profile_loop_match`, `profile_descriptor_match`);
- `caution_reasons` puede incluir `partial_player_profile`, `low_confidence` o `limited_preference_match`;
- `matched_preferences` expone solo IDs/labels/strength/confidence de taxonomía, sin rutas locales, playtime crudo, AppIDs personales del perfil ni campos debug;
- se omite si no hay profile/fit útil o contexto suficiente.

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

## Player profile implementado JSON-only

`player_behavior_profile_v1` ya está implementado como payload JSON-only, top-level opcional, local/opt-in y con degradación explícita (`unavailable` o `insufficient_signals`) si faltan señales personales. `player_behavior_fit_v1` también está implementado como cruce cualitativo entre perfil y `behavioral_signals_v1`. `decision_support_v1` queda como primer consumidor JSON-only cualitativo, sin UI visible. Cualquier consumidor visible futuro debe aprobarse como slice separado y mantener `advisory_only=true` + `ranking_impact=none`.

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
4. **Explicaciones JSON-only**: `behavioral_explanations` traduce IDs a headlines/razones/cues compactos.
5. **Plan F consumidores visibles**: explicación compacta en `Recomendaciones personalizadas` del HTML generado, Web UI, Markdown y Share HTML, usando solo `behavioral_explanations_v1` y con `ranking_impact=none`.
6. **Player profile docs-only**: cerrado; define `player_behavior_profile_v1` local/opt-in, sin UI visible.
7. **Player profile JSON-only**: cerrado; helper puro + payload opcional top-level, con `--player-preferences-json` para input manual explícito.
8. **Player behavior fit JSON-only**: cerrado; cruza perfil + señales de juego con `fit_level` cualitativo y sin impacto en ranking.
9. **Decision support JSON-only**: cerrado; expone etiquetas cualitativas de revisión desde profile+fit, sin UI visible ni impacto en ranking.
10. **Consumidores futuros visibles**: usar `decision_support_v1` o señales existentes en slices aprobados, sin score/ranking impact.
