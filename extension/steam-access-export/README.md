# Steam Access Export helper

Extensión MV3 local/dev para crear manualmente un JSON `steam_access_import_v1` a partir de AppIDs visibles en una pestaña Steam activa.

## Uso

1. Carga `extension/steam-access-export/` como extensión desempaquetada en tu navegador.
2. Abre una página Steam Store/Community donde los AppIDs que quieres revisar sean visibles.
3. Abre el popup **Steam Access Export**.
4. Elige `owned_appids`, `family_shared_appids`, `wishlist_appids` o autodetección por URL.
5. Pulsa **Extract sanitized JSON from active Steam tab**.
6. Revisa el JSON y usa **Copy JSON** o **Save JSON**.
7. Importa el archivo en Steam Tools con `--steam-access-json` o el campo Web `Steam Access local (JSON)`.

## Guardrails

- Permisos mínimos: `activeTab` + `scripting`.
- No declara `host_permissions`, `content_scripts`, `cookies`, `webRequest`, `nativeMessaging`, permisos locales ni `<all_urls>`.
- No pide password y no lee/exporta cookies, tokens, session IDs, request headers, raw responses, HTML, SteamID/perfil, names, friends, family members ni emails.
- No hace envío directo a endpoint local/remoto; copy/save son acciones manuales del usuario.
- No muta wishlist, Family, carrito, compras, settings ni estado Steam.
- El export es AppID-only, `advisory_only=true` y `ranking_impact="none"`.

## Limitaciones

- Solo extrae AppIDs presentes en links/atributos visibles del DOM de la página activa.
- La autodetección por URL es conservadora; si tienes duda, selecciona manualmente la colección.
- `family_shared_appids` significa “observado por el helper en esa página”, no prueba completitud ni acceso permanente.
- No hay validación live obligatoria; la evidencia del repo usa fixtures y checks estáticos.

## Validación local sugerida

```bash
node --check extension/steam-access-export/service_worker.js
node --check extension/steam-access-export/popup.js
node --check extension/steam-access-export/src/export-schema.js
node --check extension/steam-access-export/src/sanitize.js
node --test tests/steam_browser_helper_export.test.js
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_steam_browser_helper_import tests.test_steam_browser_helper_guardrails
```
