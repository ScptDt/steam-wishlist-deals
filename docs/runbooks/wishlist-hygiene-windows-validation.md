# Validación Windows: Wishlist hygiene visible

Checklist para probar en Windows que las señales `wishlist_hygiene` aparecen donde corresponde, incluyendo el import local opcional de `external_matches`:

- Web UI: `Último reporte` → `Acciones y recomendaciones del último reporte` → `Revisar wishlist`.
- Reporte Markdown generado: sección `## 🧹 Revisar wishlist`.
- Reporte HTML generado: sección `Revisar wishlist`.
- JSON generado: campo `wishlist_hygiene.items`.
- Import local opcional: `--wishlist-external-matches-json` o Web UI → `Archivos opcionales` → `Matches externos wishlist (JSON)`.

> Importante: la sección se oculta a propósito si `wishlist_hygiene.items` viene vacío o no existe. Si no ves nada, primero revisa el JSON.

## Objetivo

Confirmar que la higiene de wishlist se muestra como sugerencia local de revisión, no como acción destructiva.

Debe quedar claro que:

- No borra juegos.
- No auto-excluye juegos.
- No cambia score, ranking ni filtros.
- Solo muestra señales locales para revisar manualmente.
- Si se importan `external_matches`, siguen siendo señales de revisión manual.
- En Web UI muestra máximo 3 items.
- En reportes generados muestra una sección compacta solo cuando hay items.

## No hacer en esta validación

- No usar `BG00G` salvo que el objetivo explícito sea performance.
- No usar `--no-cache`.
- No hacer cold-cache largo.
- No hacer builds desktop.
- No llamar APIs externas, hacer scraping ni usar credenciales para forzar señales externas.
- No versionar archivos de `output/`, logs ni reportes generados.
- No probar borrado real ni limpieza automática de wishlist, porque no existe esa acción.

## 1. Confirmar que estás en la versión correcta

En PowerShell, desde la raíz del repo:

```powershell
git pull
git log --oneline -5
Select-String -Path README.md -Pattern "--wishlist-external-matches-json"
Select-String -Path docs\runbooks\wishlist-hygiene-multistore-contract.md -Pattern "Uso actual: import local JSON"
```

Debes confirmar:

- `git log --oneline -5` muestra commits recientes de `main` después de hacer `git pull`.
- `README.md` menciona `--wishlist-external-matches-json`.
- El contrato multi-store menciona `Uso actual: import local JSON`.

Si esos marcadores no aparecen, no estás probando la documentación/versión correcta.

## 2. Smoke recomendado desde Web UI

Usa un perfil chico para prueba rápida. Ejemplo recomendado:

```text
https://steamcommunity.com/id/joseluis12351
```

Arranca la Web UI:

```powershell
.\.venv\Scripts\python.exe steam_deals_web.py
```

En la Web UI:

1. Configura el perfil chico.
2. Ejecuta Steam Deals normalmente.
3. Espera a que termine.
4. Ve a `Resumen de tu última ejecución`.
5. Abre el desplegable `Acciones y recomendaciones del último reporte`.
6. Busca la sección `Revisar wishlist`.

Si también quieres validar import local, configura antes de ejecutar `Archivos opcionales` → `Matches externos wishlist (JSON)` con un JSON local temporal. No uses APIs externas ni scraping.

### Resultado esperado si hay señales

Debe aparecer una sección `Revisar wishlist` con:

- Badge/copy `Solo revisión`.
- Máximo 3 juegos visibles.
- Señales como biblioteca, Family, HLTB, otra tienda, catálogo local o AppID inválido, según aplique.
- Links a Steam solo si el AppID es numérico.
- Texto tipo `N más en el JSON completo` si hay más de 3 items.

### Resultado esperado si NO hay señales

La sección `Revisar wishlist` no aparece. Eso es correcto si el JSON trae:

```json
"wishlist_hygiene": {
  "items": []
}
```

o si el campo no existe en un reporte viejo.

## 3. Si no ves nada, revisar primero el JSON

Desde la tarjeta de último reporte:

1. Abre `Acciones y recomendaciones del último reporte`.
2. Clic en `Abrir JSON técnico` o `Ver JSON completo`.
3. Busca `wishlist_hygiene`.

Revisa este campo:

```json
"wishlist_hygiene": {
  "items": [
    {
      "appid": "...",
      "name": "...",
      "signals": ["owned"],
      "reasons": ["ya está en tu biblioteca"],
      "action": "review",
      "advisory_only": true
    }
  ]
}
```

Interpretación:

| JSON | Qué debería pasar |
|---|---|
| `items` tiene 1+ elementos | Debe verse `Revisar wishlist` en Web UI y reportes generados. |
| `items: []` | No debe aparecer la sección. |
| No existe `wishlist_hygiene` | Probablemente abriste un reporte viejo o no estás en la versión correcta. |

Si usaste import local, revisa además que el item conserve `external_matches` como metadata explicativa y que las señales sean `external_owned`, `external_bundle_owned` o `external_review_needed` según la evidencia.

## 4. Import local `external_matches` opcional

Para forzar una señal visible sin depender de datos reales, crea un JSON temporal desde un juego del reporte chico ya generado:

```powershell
$reportJson = Read-Host "Ruta del JSON del reporte chico"
$data = Get-Content $reportJson -Raw | ConvertFrom-Json
$firstDeal = $data.deals | Select-Object -First 1

if (-not $firstDeal) {
  Write-Host "No hay deals en el reporte chico; omite este bloque opcional."
} else {
  $matches = Join-Path $env:TEMP "wishlist-external-matches.json"
  @{
    external_matches = @(
      @{
        store = "GOG"
        store_type = "library"
        source = "user_library_export"
        external_name = $firstDeal.name
        wishlist_appid = [string]$firstDeal.appid
        evidence = "owned_in_user_export"
        confidence = "high"
      }
    )
  } | ConvertTo-Json -Depth 5 | Set-Content $matches -Encoding UTF8
}
```

Luego úsalo por CLI con `--wishlist-external-matches-json $matches` o desde Web UI en `Matches externos wishlist (JSON)`.

Comprobar:

- La corrida termina sin traceback.
- El JSON nuevo contiene una señal externa esperada.
- El item mantiene `action=review` y `advisory_only=true`.
- La ruta local del JSON no queda expuesta en el JSON de salida.
- No aparecen acciones para borrar, auto-excluir, comprar ni cambiar score/ranking.

## 5. Validar reportes generados

Después de una corrida que sí tenga `wishlist_hygiene.items`:

### Markdown

Abre el `.md` generado y busca:

```markdown
## 🧹 Revisar wishlist
```

Debe incluir copy de revisión manual/advisory-only y una tabla compacta de juegos/señales/razones.

Si `items` está vacío, esta sección no debe aparecer.

### HTML interactivo

Abre el HTML interactivo generado y busca una sección titulada:

```text
Revisar wishlist
```

Debe mostrar tarjetas/lista compacta con señales y razones.

Verifica:

- No hay botón para borrar.
- No hay botón para auto-excluir.
- No hay cambio de carrito/compra.
- El texto indica revisión manual.
- Nombres raros o caracteres especiales no rompen el HTML.

### JSON

Abre el `.json` generado y confirma:

```json
"summary": {
  "wishlist_hygiene_count": 0
}
```

o un número mayor que cero si hubo items.

## 6. Validación determinística opcional sin depender de datos reales

Si la wishlist real no produce señales y quieres confirmar que el código sí está funcionando, corre tests locales:

```powershell
.\.venv\Scripts\python.exe -m py_compile app\steam_deals_wishlist_hygiene.py steam_deals_wishlist_hygiene.py steam_deals_generator.py tests\test_generator_logic.py tests\test_web_assets.py tests\test_generated_files_serving.py
.\.venv\Scripts\python.exe -m unittest tests.test_generator_logic.WishlistHygieneTests tests.test_web_assets.WebAssetsTests tests.test_generated_files_serving.GeneratedFilesServingTests
```

Resultado esperado:

```text
OK
```

Puede aparecer un warning benigno parecido a:

```text
Steam rechazó la API key al resolver el perfil (HTTP 403). Intentando fallback público sin key...
```

Ese warning ya es conocido y no invalida esta prueba si los tests terminan en `OK`.

## 7. Qué reportar si algo no coincide

Pásame esto:

1. `git log --oneline -5`.
2. Si en Web UI viste o no `Revisar wishlist`.
3. El valor de `wishlist_hygiene.items` en el JSON:
   - vacío,
   - con datos,
   - o ausente.
4. Si apareció en Markdown (`## 🧹 Revisar wishlist`).
5. Si apareció en HTML (`Revisar wishlist`).
6. Si usaste import local, qué señal generó (`external_owned`, `external_bundle_owned`, `external_review_needed` o ninguna) y si quedó advisory-only.
7. Screenshot si se ve mal o si debería aparecer y no aparece.
8. Cualquier error de PowerShell o consola del browser.

## Checklist rápido

- [ ] `git pull` completó y `git log` muestra commits recientes de `main`.
- [ ] README/contrato documentan `--wishlist-external-matches-json` e import local JSON.
- [ ] Corrida normal con perfil chico termina.
- [ ] JSON revisado: `wishlist_hygiene.items` está claro.
- [ ] Si se usó import local `external_matches`, la señal queda advisory-only y sin ruta local filtrada.
- [ ] Si `items` tiene datos, Web UI muestra `Revisar wishlist`.
- [ ] Si `items` tiene datos, Markdown muestra `## 🧹 Revisar wishlist`.
- [ ] Si `items` tiene datos, HTML muestra `Revisar wishlist`.
- [ ] Si `items` está vacío, las secciones se ocultan sin ruido.
- [ ] No hay botones destructivos ni auto-exclusión.
- [ ] No se versionaron reportes, logs ni outputs generados.
