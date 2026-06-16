# Contrato: wishlist hygiene multi-store local

Contrato de decisión y uso para ampliar `wishlist_hygiene` con señales externas/multi-tienda y `play_access` local sin cambiar el comportamiento advisory-only.

## Readiness del slice

- Objetivo: documentar el contrato y uso actual de imports locales (`external_matches` y `play_access`) para `wishlist_hygiene`, dejando claro qué señales pueden alimentar revisiones manuales.
- Fuera de alcance permanente: APIs reales, scraping, credenciales, scoring, borrado, auto-exclusión, `BG00G`, `--no-cache`, builds y reportes generados.
- Archivos relacionados: `README.md`, `PENDIENTES.md`, `BITACORA.md`, este runbook, el índice de runbooks y los runbooks Windows.
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

## Cómo elegir el flujo correcto

- Usa `external_matches` cuando el archivo viene de una biblioteca, orden, compra o bundle propio y quieres revisar si algo de la wishlist quizá ya está cubierto.
- Usa `play_access` cuando el archivo lista juegos instalados o jugables localmente y quieres revisar acceso práctico sin compra nueva.
- Usa `steam_access` cuando el archivo lista AppIDs propios o disponibles por Steam Family desde una fuente local explícita/helper futuro; no implica login ni cookies en la app.
- Usa exports futuros de Playnite como collector local de **plataformas/launchers**, no como fuente de precios: biblioteca externa → `external_matches`; acceso instalado/jugable → `play_access`; juegos sin AppID claro → diagnóstico manual.
- Usa `external_offers`/ITAD solo para comparar precios externos; ese contrato vive en `docs/runbooks/multistore-price-comparison.md` y no alimenta ownership.
- Un precio, catálogo público o bundle público puede ser contexto, pero debe quedar fuera de `external_owned`/`external_bundle_owned` salvo que exista evidencia local explícita del usuario.

## Uso actual: import local JSON

El generator acepta un archivo local con matches externos:

```bash
python3 steam_deals_generator.py --vanity gaben \
  --wishlist-external-matches-json ./wishlist-external-matches.json
```

La Web UI usa el mismo flujo desde `Archivos opcionales` → `Matches externos wishlist (JSON)`. La ruta se valida en preflight y no se expone en el JSON de salida.

Shapes aceptadas por el import local:

1. Lista directa de registros.
2. Objeto `{ "external_matches": [...] }`.
3. Objeto `{ "matches": [...] }`.
4. Export manual simple con una lista en `games`, `items`, `library`, `orders`, `purchases` o `bundles`.

Ejemplo normalizado explícito:

```json
{
  "external_matches": [
    {
      "store_id": "gog",
      "store_name": "GOG",
      "store_type": "library",
      "source": "user_library_export",
      "external_id": "hades",
      "external_name": "Hades",
      "wishlist_appid": "1145360",
      "match_method": "steam_appid",
      "confidence": "high",
      "evidence": "owned_in_user_export",
      "observed_at": "2026-05-13"
    }
  ]
}
```

Ejemplo de export manual multi-store:

```json
{
  "store": "Fanatical",
  "source": "user_order_export",
  "orders": [
    {
      "title": "Bundle Game",
      "appid": "200",
      "bundle_owned": true,
      "external_id": "bundle-game-key"
    }
  ]
}
```

## Plantillas locales soportadas

Estas plantillas son **fixture-only/locales**: el usuario las arma desde un export propio o una lista manual. No implican API real, scraping, login ni verificación live.

Bibliotecas GOG/Epic:

```json
{
  "store": "GOG.com",
  "games": [{"title": "Hades", "steam_appid": "1145360"}]
}
```

```json
{
  "storefront": "Epic Games Store",
  "library": [{"name": "Celeste", "appid": "504230"}]
}
```

Órdenes/bundles Fanatical y compras/bundles Humble:

```json
{
  "store": "Fanatical",
  "orders": [{"title": "Bundle Game", "appid": "200"}]
}
```

```json
{
  "store": "Humble Bundle",
  "purchases": [{"title": "Humble Game", "steam_appid": "300"}]
}
```

Reglas de estas plantillas:

- `games` y `library` se normalizan como biblioteca local (`external_owned` si hay confianza alta).
- `orders`, `purchases` y `bundles` se normalizan como orden/bundle propio (`external_bundle_owned` si hay confianza alta).
- Tiendas comunes se canonicalizan de forma conservadora: `GOG.com` → `gog`, `Epic Games Store` → `epic`, `Humble Store`/`Humble Bundle` → `humble`.
- Si el registro solo representa precio, catálogo público o bundle público, usar `evidence=price_only`, `public_catalog` o `public_bundle`; no debe generar higiene por ownership.

Reglas de interpretación del import:

- `owned=true`, `store_type=library` o evidencia `owned_in_user_export` puede generar `external_owned` si la confianza queda alta.
- `bundle_owned=true`, `store_type=bundle_export` u órdenes/bundles propios pueden generar `external_bundle_owned`.
- `confidence=medium` o matches manuales sin ownership fuerte quedan como `external_review_needed`.
- `price_only`, `price`, catálogo público, bundle público, promociones o `confidence=low` no generan higiene por sí solos.
- Payload vacío (`null`, `{}`, `[]`) no genera ruido; JSON malformado o shapes incorrectas fallan con error accionable.

## Diagnóstico offline de imports

Para revisar un payload local antes de conectarlo a `wishlist_hygiene`, el helper puro `diagnose_wishlist_external_matches(payload)` clasifica cada registro sin leer archivos ni llamar APIs:

- `accepted` con `signal=external_owned`, `external_bundle_owned` o `external_review_needed`.
- `rejected` con razones como `context_only_evidence`, `context_only_store_type`, `low_confidence` o `missing_match_target`.
- `malformed` para entradas que no son objetos JSON.
- `status=error` si el shape top-level no es válido.

El diagnóstico conserva `advisory_only=true` y `ranking_impact=none`; no cambia score, ranking, wishlist, parsers, renderers ni salidas del reporte.

## Uso actual: import local `play_access`

El generator también acepta un archivo local explícito con juegos instalados o jugables:

```bash
python3 steam_deals_generator.py --vanity gaben \
  --play-access-json ./play-access-local.json
```

Este import alimenta `build_play_access_contract` y puede generar señales `owned`, `family_shared` o `probable_family_shared` para `wishlist_hygiene`, siempre como revisión manual. La ruta local no se expone en el JSON generado.

Shapes aceptadas:

1. Lista directa de registros o appids.
2. Mapa simple `{ "appid": "Nombre" }`.
3. Objeto con lista/mapa en `installed_or_playable`, `installed_or_playable_appids`, `installed`, `playable`, `games`, `items` o `library`.

Ejemplo explícito:

```json
{
  "source": "steam_local_library_export",
  "observed_at": "2026-05-22",
  "installed_or_playable": [
    {"appid": "30", "name": "Installed Only", "installed": true},
    {"steam_appid": "40", "title": "Playable Elsewhere", "playable": true},
    "50"
  ]
}
```

Reglas de interpretación:

- El import es **local y opt-in**: no hay auto-scan de carpetas Steam, launcher automation, SteamKit2, scraping, login ni red real.
- Entradas sin `appid`/`steam_appid` se ignoran para evitar matches ambiguos por nombre.
- Duplicados exactos por `appid` + `source` + `play_state` se deduplican.
- Payload vacío (`null`, `{}`, `[]`) no genera ruido; JSON malformado o shapes incorrectas fallan con error accionable.
- Si un juego aparece en el import local pero no en owned/family, la señal visible esperada es `probable_family_shared`, no ownership definitivo.
- No cambia score, ranking, filtros, defaults, wishlist deletion ni auto-exclusión.

## Uso actual: import local `steam_access`

El generator acepta un archivo local explícito con AppIDs propios o disponibles por Steam Family:

```bash
python3 steam_deals_generator.py --vanity gaben \
  --steam-access-json ./steam-access-local.json
```

La Web UI usa el mismo flujo desde `Archivos opcionales` → `Steam Access local (JSON)`. La ruta se valida en preflight y no se expone en el JSON generado.

Shape mínima:

```json
{
  "source": "steam_browser_helper_export",
  "steamid": "76561198000000000",
  "generated_at": "2026-06-03T12:00:00Z",
  "owned_appids": ["10", "20"],
  "family_shared_appids": ["30"],
  "wishlist_appids": ["40"]
}
```

Reglas de interpretación:

- El import es **local y opt-in**: no hay login directo, cookies, tokens, auto-scan, SteamKit2, scraping ni red real.
- Solo se conservan AppIDs y metadata segura (`source`, `steamid`, timestamps/provenance simples).
- Campos sensibles o sobredimensionados (`cookies`, tokens, raw responses, nombres de familiares) no forman parte del contrato público.
- AppIDs inválidos se ignoran; duplicados se deduplican preservando orden.
- `owned_appids` y `family_shared_appids` alimentan `play_access`/`wishlist_hygiene` como señales advisory-only; no cambian score, ranking, filtros, defaults, wishlist deletion ni auto-exclusión.

## Contrato futuro: export Playnite privacy-minimized

Este contrato queda como **docs-only/readiness** antes de implementar parser o add-on. Playnite puede funcionar como collector local de biblioteca multi-launcher, pero Steam Tools solo debe importar señales mínimas para revisar wishlist sin invadir privacidad.

Objetivo:

- decir “este juego ya aparece en GOG/Epic/Ubisoft/etc.”;
- distinguir plataformas/launchers de rutas locales;
- permitir revisión manual de duplicados de wishlist;
- evitar inferir precios, ownership por catálogo público o Steam Family con certeza.

### Export 1: biblioteca por plataforma

Archivo sugerido: `steamtools-playnite-library.json`.

Uso esperado: normalizar a `external_matches` cuando el juego aparece en una biblioteca/plataforma externa explícita.

```json
{
  "schema": "steamtools_playnite_library_v1",
  "source": "playnite",
  "exported_at": "2026-06-16T12:00:00Z",
  "items": [
    {
      "name": "Control Ultimate Edition",
      "steam_appid": "870780",
      "platforms": [
        {
          "store": "Epic Games Store",
          "source_type": "official_launcher",
          "provider_game_id": "epic-control",
          "evidence": "playnite_library"
        },
        {
          "store": "GOG",
          "source_type": "official_launcher",
          "provider_game_id": "gog-control",
          "evidence": "playnite_library"
        }
      ]
    }
  ]
}
```

Reglas:

- `platforms[*].store` es el launcher/plataforma visible, no una ubicación del disco.
- `source_type` puede ser `official_launcher`, `playnite_addon`, `manual` o `unknown`.
- `provider_game_id` es opcional y debe quedarse en un identificador de proveedor, no rutas ni IDs de cuenta personales.
- Si `store="Steam"`, no asumir `owned` vs `family_shared`; la señal Steam desde Playnite debe quedar como `ownership_status="unknown"` o revisión manual salvo evidencia más fuerte de `steam_access`.

### Export 2: acceso local sin rutas

Archivo sugerido: `steamtools-playnite-access.json`.

Uso esperado: normalizar a `play_access` para señalar que Playnite considera el juego instalado o jugable, sin revelar dónde está instalado.

```json
{
  "schema": "steamtools_playnite_access_v1",
  "source": "playnite",
  "exported_at": "2026-06-16T12:00:00Z",
  "items": [
    {
      "name": "Hades",
      "steam_appid": "1145360",
      "platforms": [
        {
          "store": "GOG",
          "installed": true,
          "playable_hint": true,
          "evidence": "playnite_access"
        }
      ]
    }
  ]
}
```

Reglas:

- `installed`/`playable_hint` son booleanos de alto nivel; no incluir `install_dir`, ejecutables, argumentos, saves, screenshots ni paths.
- `playtime_minutes` o `last_played` quedan como campos futuros opt-in; no son necesarios para el primer parser.
- Si solo hay acceso local pero no ownership externo claro, mostrar copy tipo “revisa antes de comprar”, no “ya es tuyo”.

### Export 3: diagnóstico de no vinculados

Archivo sugerido: `steamtools-playnite-unmatched.json`.

Uso esperado: revisión manual de juegos de Playnite sin AppID Steam confiable; no debe alimentar ownership automático.

```json
{
  "schema": "steamtools_playnite_unmatched_v1",
  "source": "playnite",
  "exported_at": "2026-06-16T12:00:00Z",
  "items": [
    {
      "name": "Some GOG Game",
      "store": "GOG",
      "provider_game_id": "gog-999",
      "reason": "steam_appid_missing"
    }
  ]
}
```

### Campos prohibidos en exports Playnite

No exportar:

- rutas locales (`install_dir`, `executable`, carpetas de usuario, working directories);
- nombres de usuario del sistema, paths de saves/screenshots/config;
- cookies, tokens, credenciales, headers, raw launcher metadata o logs;
- IDs de cuenta de launchers externos salvo que el usuario los escriba explícitamente en otro contrato;
- acciones de launch/play/install/uninstall.

### Steam Family queda fuera de Playnite

Playnite no debe usarse para afirmar Steam Family. La API pública de Steam/Playnite no da una señal fiable de “propio” vs “prestado por familia” para todos los casos.

Contrato futuro separado para perfiles Family opcionales:

```json
{
  "schema": "steamtools_family_profiles_v1",
  "members": [
    {
      "label": "Familia 1",
      "steam_profile": "https://steamcommunity.com/id/example-user"
    },
    {
      "label": "Familia 2",
      "steam_id": "76561198000000000"
    }
  ]
}
```

Reglas para este contrato futuro:

- `label` debe ser local y no tiene que ser nombre real.
- Consultar bibliotecas públicas por SteamID/custom URL solo puede producir `family_review_needed`, no certeza de acceso.
- Si la biblioteca no es pública, Steam rate-limitea o no hay coincidencia, no asumir “no lo tiene”.
- No login, cookies, tokens, scraping autenticado, friends/family names, mutaciones Steam ni auto-remoción de wishlist.

### Add-on Playnite futuro

Si se implementa, debe ser un add-on local tipo exporter que lea la biblioteca de Playnite y emita estos JSONs con acción explícita del usuario. La ruta de salida debe elegirse con diálogo de guardado; no escribir en carpetas de instalación ni enviar datos al server local por defecto.

Validación esperada antes de código:

1. Fixtures locales para los tres schemas válidos, vacíos y malformados.
2. Tests de parser que confirmen que `platforms[*].store` genera copy “lo tienes en X/Y” sin rutas.
3. Tests de denylist para campos prohibidos (`install_dir`, `path`, `executable`, `token`, `cookie`, `raw`).
4. Verificar que Steam desde Playnite no se convierte automáticamente en `family_shared`.

### Corte parser library cerrado 2026-06-16

- `steamtools_playnite_library_v1` ya puede entrar por el import existente `--wishlist-external-matches-json` sin flags/UI nuevos.
- El parser normaliza plataformas no-Steam a `external_matches` con `source=playnite_library`, `store_type=library`, `match_method=steam_appid` y evidencia local de Playnite.
- Entradas `store=Steam` se omiten para no inferir ownership ni Steam Family desde Playnite; Family sigue reservado para `steam_access` o el contrato futuro de perfiles con revisión manual.
- Campos sensibles o privados del export (`install_dir`, paths, ejecutables, tokens, cookies o raw metadata) no se copian al contrato normalizado.
- La salida sigue siendo advisory-only dentro de `wishlist_hygiene`: solo “revisar wishlist”, sin auto-quitar, auto-hide, score/ranking/defaults ni precios `external_offers`.

### Corte parser access cerrado 2026-06-16

- `steamtools_playnite_access_v1` ya puede entrar por el import existente `--play-access-json` sin flags/UI nuevos.
- El parser toma solo juegos con `platforms[*].installed=true` o `platforms[*].playable_hint=true` y los normaliza a registros locales de `play_access` con `source=playnite_access`.
- La señal resultante queda como acceso local/probable (`probable_family_shared` cuando no hay owned/family explícito), nunca como ownership ni Steam Family definitivo.
- Campos privados del export (`install_dir`, paths, ejecutables, tokens, cookies o raw metadata) no se copian al contrato normalizado.
- La salida sigue siendo advisory-only: ayuda a revisar antes de comprar, sin auto-quitar wishlist, score/ranking/defaults, precios `external_offers` ni Playnite add-on real.

## Plan 6A: contrato futuro del helper/browser extension Steam

Este corte es **docs-only** para dejar listo el threat model antes de implementar un helper real. El objetivo del helper futuro es producir un archivo manual compatible con `steam_access_import_v1`; la app Python/Web nunca debe manejar sesión Steam, cookies, tokens ni respuestas crudas.

### Threat model y límites

Activos sensibles que no deben salir del navegador:

- cookies de Steam, `steamLoginSecure`, session IDs, bearer tokens o cabeceras autenticadas;
- respuestas crudas de endpoints privados o payloads con datos personales;
- nombres de familiares, perfiles de miembros, emails, friends u otros datos que no sean AppIDs;
- password o prompts de credenciales.

Superficies permitidas:

- helper/extensión opcional, ejecutado por el usuario en su navegador ya autenticado;
- lectura puntual y explícita para armar un export local;
- descarga/copia manual de JSON AppID-only;
- import posterior vía `--steam-access-json` o campo Web `Steam Access local (JSON)`.

No permitido en Plan 6 ni en la app principal:

- login automatizado, scraping desde Python, SteamKit2 o captura de cookies/tokens;
- enviar raw responses al server local;
- mutar wishlist, ignore/follow, carrito, Family, settings o compras;
- endpoint local de recepción directa sin pairing/threat model separado;
- score/ranking/defaults/cache/fetching basados en estas señales.

### Permisos mínimos esperados para el helper futuro

El helper debe justificar cada permiso antes de implementarse:

| Permiso/superficie | Uso permitido | No usar para |
|---|---|---|
| Host Steam limitado | Leer endpoints estrictamente necesarios desde la sesión del navegador | Acceso amplio a cualquier dominio o scraping general |
| Acción manual/browser action | Botón `Exportar Steam Access JSON` | Ejecución automática en background |
| Descarga o clipboard opcional | Entregar JSON al usuario | Mandar datos a la app sin confirmación |
| Storage local mínimo opcional | Preferencias no sensibles del helper | Guardar cookies, tokens o raw responses |

Si la extensión necesita permisos más amplios, debe abrirse un nuevo threat model antes de código.

### Export JSON permitido

El export futuro debe ser un objeto JSON pequeño y AppID-only:

```json
{
  "schema": "steam_access_import_v1",
  "source": "steam_browser_helper_export",
  "generated_at": "2026-06-04T12:00:00Z",
  "provenance": "browser_helper_manual_export",
  "owned_appids": ["10", "20"],
  "family_shared_appids": ["30"],
  "wishlist_appids": ["40"],
  "advisory_only": true,
  "ranking_impact": "none"
}
```

Reglas de minimización:

- `owned_appids`, `family_shared_appids` y `wishlist_appids` son listas de strings numéricos.
- `wishlist_appids` es opcional y solo si el helper puede obtenerlo sin aumentar riesgos.
- El helper Plan 6B no infiere ni exporta SteamID/perfil; otros imports locales pueden traer `steamid` manual si el usuario lo aporta fuera del helper.
- Nombres de juegos no se exportan en Plan 6B; el contrato preferido sigue siendo AppID-only.
- No incluir campos de sesión, headers, cookies, tokens, family member names, raw endpoint payloads, HTML, URLs autenticadas ni debug logs.
- `family_shared_appids` significa “observado por helper con sesión de navegador”; sigue siendo advisory-only y puede quedar vacío si Steam cambia permisos/endpoints.

### Validación esperada para Plan 6B implementación

Antes de implementar la extensión real:

1. Consultar docs actuales de WebExtensions/MV3 y revisar permisos con ExternalScout.
2. Crear fixtures JSON locales para exports válidos, vacíos y malformados.
3. Probar que el helper filtra/deduplica AppIDs antes del export.
4. Probar que el export no contiene claves prohibidas (`cookies`, `token`, `raw_response`, `family_members`, headers).
5. Validar que el import existente acepta el JSON y mantiene `advisory_only=true` / `ranking_impact=none`.
6. Cierre sin live login obligatorio, sin red real como evidencia, sin endpoint local directo y sin mutaciones Steam.

### Plan 6B helper local/dev

El helper vive en `extension/steam-access-export/` y se carga como extensión desempaquetada durante desarrollo. Su flujo esperado es manual:

1. Abrir una página Steam Store/Community que muestre AppIDs.
2. Abrir el popup **Steam Access Export**.
3. Elegir si los AppIDs visibles deben tratarse como `owned_appids`, `family_shared_appids`, `wishlist_appids` o autodetección conservadora por URL.
4. Extraer, revisar y copiar/guardar `steam-access-import.json`.
5. Importar ese archivo en Steam Tools con `--steam-access-json` o el campo Web `Steam Access local (JSON)`.

Guardrails implementados en Plan 6B inicial:

- `manifest.json` usa MV3 con popup manual y permisos mínimos `activeTab` + `scripting`.
- No declara `host_permissions`, `content_scripts`, `cookies`, `webRequest`, `nativeMessaging`, permisos locales ni `<all_urls>`.
- El popup solo inyecta una función de extracción bajo acción explícita del usuario.
- El export se construye con sanitizer local y queda AppID-only; no exporta SteamID/perfil, cookies/tokens, respuestas crudas, HTML, nombres de familiares, friends ni emails.
- Copy/save son acciones manuales del usuario; no hay background scraping, persistencia de sesión ni envío a endpoint local/remoto.
- La evidencia de cierre usa fixtures y checks estáticos; no requiere live login, red real ni páginas Steam privadas.

Plan 7B amplía este helper con envío directo opcional, pero mantiene Copy/Save como fallback manual. Desde Plan 7B, el único `host_permissions` permitido es `"http://127.0.0.1/*"`, el fetch local vive en el service worker, y el endpoint sigue siendo import-only con pairing/session token local.

Plan 8B agrega un collector manual para reducir el trabajo de armar JSONs a mano: el usuario extrae AppIDs visibles en una página, los agrega explícitamente a un bucket (`owned_appids`, `family_shared_appids` o `wishlist_appids`), repite el proceso en otras páginas y exporta un JSON combinado `steam_access_import_v1`. El collector puede usar el permiso `storage`, pero solo para persistir AppIDs/metadata mínima local de la extensión; no puede guardar pairing/session tokens, cookies, request headers, raw responses, HTML, SteamID/perfil, family member names, friends ni emails. Direct-send queda reservado para el JSON combinado del collector y sigue usando el service worker, `127.0.0.1`, `credentials: "omit"`, pairing/auth explícitos y endpoint import-only. El collector no promete completitud: si Steam pagina, virtualiza, oculta o no expone todos los juegos, el helper solo observa lo visible bajo acción manual.

### Plan 8: UX de decisión para señales de acceso

El primer slice de Plan 8 puede mostrar notas de acceso en superficies de decisión, especialmente Top Picks, **solo** cuando el JSON ya contiene `wishlist_hygiene.items[*].access_decision` para el mismo AppID. La nota sirve para reforzar “revisar antes de comprar” cuando el juego parece `owned`, `family_shared`, `probable_family_shared` o `playable_without_buying`.

Contrato permitido:

- fuente única: `wishlist_hygiene`/`access_decision` ya calculado localmente;
- copy advisory-only: “Ya lo tienes”, “Disponible por Steam Family”, “Probable acceso local” o “Revisa el acceso local antes de comprar”;
- mantener `advisory_only=true`, `ranking_impact="none"`, acción `review` y badge/copy `Solo revisión`;
- mostrar la nota sin cambiar el score, orden, ranking ni selección de Top Picks.

No permitido en este slice:

- filtros, manual hide persistente, auto-hide o auto-exclusión;
- borrar wishlist, mutar ignore/follow/carrito/Family/settings/compras o abrir checkout;
- cambiar score, pesos, ranking, orden de Top Picks, defaults, cache policy o fetching;
- pedir login/password, leer cookies/tokens, guardar raw responses/HTML, SteamID-perfil desde helper, family member names, friends o emails;
- usar red real, `BG00G`, `--no-cache`, builds o reportes generados como validación automática.

Implementación dirigida del primer slice:

- HTML generado: cada card de Top Picks puede mostrar una nota `Acceso: ...` si el AppID del Top Pick coincide con `wishlist_hygiene.items[*].access_decision` explícito y seguro.
- Markdown generado: la tabla de Top Picks agrega la misma nota en la columna del juego, sin tocar score ni orden.
- Web `Último reporte`: las cards de “Compartir juegos destacados” muestran la nota cuando el último JSON local trae el mismo match por AppID.
- Los renderers/Web ignoran señales legacy sin `access_decision` explícito para evitar inferencias nuevas en la UI de Top Picks.
- La evidencia de cierre debe ser fixture/local: `py_compile`, `node --check`, tests dirigidos de renderers/Web assets y `git diff --check`; no requiere live login, red real ni reportes generados.

### Plan 7A: threat model endpoint directo helper → app local

Este corte es **docs-only**. Define el contrato mínimo antes de permitir que la extensión envíe un import directamente a la app local. Plan 7A no implementa endpoint, no cambia permisos de la extensión y no habilita envío directo todavía.

#### Objetivo y límites

Objetivo futuro de Plan 7B: permitir que el usuario, desde el popup del helper, envíe un JSON `steam_access_import_v1` AppID-only a un endpoint import-only de Steam Tools corriendo en `127.0.0.1`.

No permitido en Plan 7:

- endpoint de comandos generales o ejecución arbitraria;
- envío de cookies, tokens, passwords, headers autenticados, raw responses, HTML, SteamID/perfil, nombres de familiares, friends o emails;
- login automatizado, scraping desde Python, SteamKit2 o mutaciones Steam;
- cambios en score/ranking/defaults/cache/fetching;
- aceptar requests desde `0.0.0.0`, interfaces LAN o CORS wildcard.

#### Superficies y permisos futuros

Si se implementa Plan 7B, la extensión deberá usar el service worker o una página de extensión para llamar a la app local; no content-script fetch. Los permisos futuros deben ser explícitos y estrechos:

```json
{
  "host_permissions": ["http://127.0.0.1/*"]
}
```

`localhost` solo se agregaría si hay una razón documentada; operacionalmente se prefiere `127.0.0.1` para evitar sorpresas de resolución. La app debe seguir ligada a loopback y nunca a `0.0.0.0`.

#### Pairing y autenticación local

Diseño requerido para Plan 7B:

1. El usuario habilita explícitamente “recibir import desde helper” en la app local.
2. La app genera un pairing token/código corto, aleatorio, de un solo uso y con expiración breve.
3. El helper envía un request de pairing a `http://127.0.0.1:{port}/...` con `Content-Type: application/json` y `X-Pairing-Token` o `Authorization: Bearer ...`.
4. La app valida loopback, Origin permitido y token vigente; luego devuelve un token de sesión local de alcance import-only.
5. Cada import posterior debe enviar `Authorization: Bearer <local-session-token>` o header custom equivalente.
6. El usuario puede revocar/desconectar el pairing desde la app local.

No usar cookies para autenticar este flujo; token explícito en header reduce exposición CSRF y deja claro que no se reutiliza sesión Steam ni sesión web general.

#### Endpoint import-only futuro

Contrato preliminar de Plan 7B:

```http
POST /api/steam-access/import
Origin: chrome-extension://<extension-id>
Content-Type: application/json
Authorization: Bearer <local-session-token>
```

Payload permitido: el mismo contrato AppID-only `steam_access_import_v1` de Plan 6B. El server debe validar schema estricta, límites de tamaño, arrays de AppIDs numéricos, `advisory_only=true`, `ranking_impact="none"` y ausencia de claves prohibidas.

Respuesta exitosa sugerida:

```json
{
  "ok": true,
  "imported": true,
  "summary": {
    "owned_count": 2,
    "family_shared_count": 1,
    "wishlist_count": 0,
    "advisory_only": true,
    "ranking_impact": "none"
  }
}
```

Errores deben ser accionables pero no filtrar rutas locales, tokens, stack traces ni payloads crudos. Usar 400 para schema inválida, 401 para token faltante/inválido, 403 para Origin no permitido, 405 para método no permitido, 413 para payload demasiado grande y 429 para rate limit.

#### CORS, CSRF y checks obligatorios

Plan 7B debe probar con fixtures/mocks:

- server ligado a `127.0.0.1` y rechazo de hosts/origins no permitidos;
- CORS allowlist exacta para `chrome-extension://...` / `moz-extension://...` cuando exista Origin; nunca `Access-Control-Allow-Origin: *` para import;
- rechazo de `GET`, `PUT`, `PATCH`, `DELETE` para mutaciones/import;
- rechazo de POST sin token, con token expirado o con Origin web normal (`https://...`);
- request no simple: JSON + Authorization/custom header;
- límites de tamaño/rate limit por endpoint;
- no logging ni responses con tokens, cookies, raw responses, HTML, perfil, nombres de familiares o rutas locales;
- persistencia solo tras confirmación explícita del usuario y solo para el import local.

Plan 7B no puede avanzar sin tests de seguridad dedicados y stop-on-failure activo.

### Plan 7B: endpoint directo implementado helper → app local

Plan 7B habilita el flujo directo opt-in sin cambiar el contrato AppID-only:

1. La app local genera un pairing token one-time desde `/api/steam-access/pairing/start` protegido por el token local anti-CSRF.
2. El helper llama `POST /api/steam-access/pair` en `127.0.0.1` con JSON, Origin de extensión y `X-Pairing-Token` obligatorio; si el body incluye `pairing_token`, debe coincidir.
3. La app devuelve un `session_token` local import-only, corto, revocable y ligado al Origin de la extensión.
4. El helper llama `POST /api/steam-access/import` con `Authorization: Bearer <session_token>` y payload `steam_access_import_v1` sanitizado.
5. La app valida Host loopback, Origin/CORS sin wildcard, método, Content-Type, tamaño, rate-limit, schema, `advisory_only=true`, `ranking_impact="none"` y ausencia de campos sensibles antes de guardar el import como `steam_access_json` local.

Respuestas exitosas devuelven solo `ok`, `status`/`imported` y summary/counts. Errores no deben incluir tokens, rutas locales, payload crudo, cookies, raw responses, HTML, perfiles ni nombres de familiares.

La extensión Plan 7B puede declarar solo:

```json
{
  "host_permissions": ["http://127.0.0.1/*"]
}
```

El popup no hace `fetch` directo: envía un mensaje al service worker. El service worker usa endpoint fijo en `127.0.0.1`, `credentials: "omit"`, JSON y headers explícitos. No se agrega `localhost`, `<all_urls>`, `cookies`, `webRequest`, `nativeMessaging`, `content_scripts`, host Steam amplio ni endpoint de comandos generales.

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
        "access_decision": {
          "code": "owned",
          "label": "Ya lo tienes",
          "detail": "Comprar solo si quieres otra copia o soporte adicional.",
          "advisory_only": true,
          "ranking_impact": "none"
        },
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

Cualquier ampliación multi-store o `play_access` debe ser compatible hacia atrás: los consumidores que solo lean `signals`, `reasons`, `action` y `advisory_only` deben seguir funcionando. Cuando hay `play_access`, `source_signals` puede incluir `play_access` y cada item puede adjuntar metadata pública bajo `play_access` sin reemplazar `signals` ni `reasons`.

`access_decision` es opcional y solo resume copy visible para decidir compra. Códigos actuales:

- `owned` → “Ya lo tienes” / comprar solo si quieres otra copia o soporte adicional.
- `family` → “Disponible por Steam Family” / comprar solo si quieres copia propia.
- `probable_family_shared` → “Probable acceso local” / revisar acceso local antes de comprar.

La acción sigue siendo `review` y el badge operativo debe seguir diciendo `Solo revisión`; `access_decision` no borra, no oculta, no auto-excluye y no cambia score/ranking/defaults.

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
| Humble purchases/bundles/manual import | Señal de propiedad si el usuario provee export/lista local | Inferir ownership desde bundles públicos o catálogo |
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

## Próximos slices implementables

Primer corte seguro ya implementado:

> Parser local de export manual GOG/Epic/Fanatical/Humble → normaliza listas locales a `external_matches` → `build_wishlist_hygiene_signals` lo consume como señal opcional.

Siguiente corte solo si aparece un export concreto:

> Parser específico por formato real documentado/fixture local, manteniendo el mismo contrato y sin APIs reales.

Fuera de ese primer corte:

- login automático;
- scraping;
- ITAD live;
- cambios UI grandes;
- borrado/auto-exclusión;
- scoring o defaults.
