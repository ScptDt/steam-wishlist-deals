# Steam Access Export helper

Extensión MV3 local/dev para crear manualmente un JSON `steam_access_import_v1` a partir de AppIDs visibles en una pestaña Steam activa. Puede copiar/guardar el JSON o, si el usuario empareja primero la app local, enviarlo a Steam Tools en `127.0.0.1` como import-only.

## Uso

1. Carga `extension/steam-access-export/` como extensión desempaquetada en tu navegador.
2. Abre una página Steam Store/Community donde los AppIDs que quieres revisar sean visibles.
3. Abre el popup **Steam Access Export**.
4. Elige `owned_appids`, `family_shared_appids`, `wishlist_appids` o autodetección por URL.
5. Pulsa **Extract sanitized JSON from active Steam tab**.
6. Revisa el JSON y usa **Copy JSON** o **Save JSON**.
7. Para import manual, importa el archivo en Steam Tools con `--steam-access-json` o el campo Web `Steam Access local (JSON)`.
8. Para envío directo opcional, genera/obtén un pairing code desde la app local, pégalo en el popup, verifica `http://127.0.0.1:<puerto>`, pulsa **Pair with local app** y luego **Send sanitized JSON**. Si falla, Copy/Save sigue siendo el fallback seguro.

El pairing local usa `POST /api/steam-access/pair` con JSON, Origin de extensión y `X-Pairing-Token`. El import usa `POST /api/steam-access/import` con `Authorization: Bearer <sesión-local>`, `Content-Type: application/json`, `credentials: "omit"`, schema `steam_access_import_v1`, límite de tamaño/rate-limit y confirmación local previa en Steam Tools. El token de pairing/sesión local no es un token Steam y no autoriza nada fuera del import local.

## Guardrails

- Permisos mínimos de extracción: `activeTab` + `scripting`; permiso local estrecho: `host_permissions: ["http://127.0.0.1/*"]`.
- No declara `content_scripts`, `cookies`, `webRequest`, `nativeMessaging`, `localhost`, `0.0.0.0`, `<all_urls>` ni hosts Steam amplios.
- No pide password y no lee/exporta cookies Steam, tokens Steam, session IDs Steam, request headers Steam, raw responses, HTML, SteamID/perfil, names, friends, family members ni emails.
- El envío directo es import-only, opt-in, a `127.0.0.1`, desde el service worker y con `credentials: "omit"`; usa pairing/session token local, no cookies.
- No muta wishlist, Family, carrito, compras, settings ni estado Steam.
- El export es AppID-only, `advisory_only=true` y `ranking_impact="none"`.

## Limitaciones

- Solo extrae AppIDs presentes en links/atributos visibles del DOM de la página activa.
- La autodetección por URL es conservadora; si tienes duda, selecciona manualmente la colección.
- `family_shared_appids` significa “observado por el helper en esa página”, no prueba completitud ni acceso permanente.
- El envío directo requiere que Steam Tools esté corriendo en `127.0.0.1` y que el pairing code siga vigente; no usa `localhost`, `0.0.0.0`, LAN ni HTTPS.
- No hay validación live obligatoria; la evidencia del repo usa fixtures y checks estáticos.

## Validación local sugerida

```bash
node --check extension/steam-access-export/service_worker.js
node --check extension/steam-access-export/popup.js
node --check extension/steam-access-export/src/export-schema.js
node --check extension/steam-access-export/src/sanitize.js
node --test tests/steam_browser_helper_export.test.js
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_steam_browser_helper_import tests.test_steam_browser_helper_guardrails
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_steam_plan7b_direct_import_security
```
