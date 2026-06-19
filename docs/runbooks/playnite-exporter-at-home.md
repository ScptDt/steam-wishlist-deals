# Probar en casa: SteamTools Playnite Exporter

Guía práctica para probar el add-on local de Playnite y usar sus JSON en Steam Tools.

> Estado actual: **modo desarrollo/source-only**. Todavía no hay `.pext` publicado ni validación funcional cerrada en un host Windows + Playnite para prometer instalación final. Esta guía es para probarlo de forma local y reversible.

## Qué vas a probar

El add-on exporta inventario mínimo de Playnite a archivos JSON locales:

- `steamtools_playnite_library_v1`: juegos/fuentes/launchers visibles en Playnite.
- `steamtools_playnite_access_v1`: juegos que Playnite marca como instalados/jugables.

Steam Tools importa esos JSON para mostrar contexto en `Revisar wishlist`, siempre como revisión manual:

- No borra juegos de la wishlist.
- No auto-oculta ni auto-excluye.
- No prueba ownership definitivo.
- No confirma Steam Family.
- No exporta rutas, ejecutables, argumentos, scripts, `GameAction`, tokens, cookies, logs ni metadata cruda.
- No alimenta precios `external_offers`, score, ranking, filtros ni carrito.

## Requisitos

En la PC Windows donde tienes Playnite:

1. Playnite Desktop instalado.
2. Este repo descargado o clonado.
3. Visual Studio / Build Tools / MSBuild compatible con proyectos `.NET Framework 4.6.2`.
4. NuGet habilitado para restaurar `PlayniteSDK`.

Si `dotnet build` no compila `net462`, usa Visual Studio Developer PowerShell o Visual Studio directamente.

## 1. Compilar el add-on

Abre PowerShell en la raíz del repo:

```powershell
$plugin = ".\extension\playnite-steamtools-exporter"
dotnet restore "$plugin\SteamTools.PlayniteExporter.csproj"
dotnet build "$plugin\SteamTools.PlayniteExporter.csproj" -c Release
```

Si falla por targeting pack o .NET Framework:

1. Abre `SteamTools.PlayniteExporter.csproj` con Visual Studio.
2. Restaura paquetes NuGet si Visual Studio lo pide.
3. Compila en `Release`.

Salida esperada aproximada:

```text
extension\playnite-steamtools-exporter\bin\Release\net462\SteamTools.PlayniteExporter.dll
```

## 2. Preparar carpeta de extensión de desarrollo

Playnite necesita que `extension.yaml` y el `.dll` estén en la misma carpeta de extensión. Después de compilar:

```powershell
$plugin = ".\extension\playnite-steamtools-exporter"
$out = "$plugin\bin\Release\net462"
Copy-Item "$plugin\extension.yaml" "$out\extension.yaml" -Force
Get-ChildItem $out
```

Debe verse algo parecido a:

```text
extension.yaml
SteamTools.PlayniteExporter.dll
```

Si aparecen DLLs adicionales en la salida, déjalas en esa misma carpeta.

## 3. Cargar la extensión en Playnite

En Playnite Desktop:

1. Abre `Settings`.
2. Ve a `For developers`.
3. En `External extensions`, agrega la carpeta de build:

   ```text
   <repo>\extension\playnite-steamtools-exporter\bin\Release\net462
   ```

4. Reinicia Playnite.

Los plugins C# no se recargan bien en caliente: si recompilas, reinicia Playnite otra vez.

## 4. Exportar JSON desde Playnite

En Playnite, abre el menú de extensiones:

```text
Extensions → SteamTools
```

Usa estas acciones:

```text
Save SteamTools library JSON...
Save SteamTools access JSON...
```

Guarda los archivos en una carpeta que recuerdes, por ejemplo:

```text
Documents\SteamTools\imports\steamtools-playnite-library.json
Documents\SteamTools\imports\steamtools-playnite-access.json
```

También puedes usar las acciones `Show/copy...` si solo quieres inspeccionar el JSON primero.

## 5. Importarlos en Steam Tools Web

Arranca Steam Tools en la misma PC o en otra donde puedas acceder a esos archivos locales:

```powershell
.\.venv\Scripts\python.exe steam_deals_web.py
```

Abre:

```text
http://127.0.0.1:8080
```

En `Archivos opcionales`:

| Campo Web | Archivo de Playnite |
|---|---|
| `Matches externos wishlist (JSON)` | `steamtools-playnite-library.json` |
| `Play access local (JSON)` | `steamtools-playnite-access.json` |

Ejecuta Steam Deals normalmente.

## 6. Importarlos por CLI

Alternativa por terminal:

```powershell
.\.venv\Scripts\python.exe steam_deals_generator.py `
  --vanity TU_PERFIL `
  --wishlist-external-matches-json "C:\Users\TU_USUARIO\Documents\SteamTools\imports\steamtools-playnite-library.json" `
  --play-access-json "C:\Users\TU_USUARIO\Documents\SteamTools\imports\steamtools-playnite-access.json"
```

Puedes usar vanity, URL completa de perfil o Steam ID de 17 dígitos.

## 7. Qué revisar en el reporte

En la Web UI, después de terminar:

1. Abre `Resumen de tu última ejecución`.
2. Abre `Acciones y recomendaciones del último reporte`.
3. Busca `Revisar wishlist`.

También puedes revisar el JSON técnico generado y buscar:

```json
"wishlist_hygiene": {
  "items": []
}
```

Si `items` está vacío, la sección puede no aparecer. Eso es normal si no hubo señales relevantes o si tu wishlist no coincide con los datos exportados.

Señales esperadas cuando hay match:

- `external_owned`: aparece en otra biblioteca/import local con evidencia fuerte.
- `external_review_needed`: match por título o señal Playnite que requiere revisión manual.
- `probable_family_shared` / acceso local probable: Playnite lo marca instalado/jugable, pero no prueba ownership.

## 8. Si quieres probar sin depender de coincidencias reales

Puedes usar una wishlist pequeña y un juego que sabes que está en Playnite. Si el reporte no muestra `Revisar wishlist`, abre el JSON completo y verifica si hay `wishlist_hygiene.items`.

Si quieres probar el diagnóstico `steamtools_playnite_unmatched_v1`, hoy es helper interno fixture-only: no hay botón Playnite ni campo Web dedicado todavía. Puedes crear un JSON manual para revisión futura, pero no alimenta ownership ni acciones automáticas.

Ejemplo de fixture:

```json
{
  "schema": "steamtools_playnite_unmatched_v1",
  "source": "playnite",
  "exported_at": "2026-06-19T12:00:00Z",
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

## Troubleshooting

### No aparece `Extensions → SteamTools`

- Confirma que `extension.yaml` está en la misma carpeta que `SteamTools.PlayniteExporter.dll`.
- Confirma que agregaste la carpeta `bin\Release\net462` en `External extensions`.
- Reinicia Playnite.
- Revisa los logs de Playnite desde su menú de ayuda/logs.

### Compilación falla con `net462`

- Usa Visual Studio o Developer PowerShell en vez de `dotnet build` normal.
- Instala el Developer Pack de `.NET Framework 4.6.2` si Visual Studio lo pide.
- Restaura paquetes NuGet.

### Steam Tools no muestra `Revisar wishlist`

- Revisa que configuraste los archivos en los campos correctos.
- Confirma que el JSON no está vacío.
- Revisa el JSON técnico del reporte y busca `wishlist_hygiene`.
- Recuerda que Playnite no prueba Steam Family ni ownership; muchas señales quedan como revisión manual.

### El JSON exportado contiene rutas o metadata sensible

No lo importes directo. Este add-on debe emitir DTOs mínimos. Si pruebas otro exporter de Playnite y ves `installDirectory`, ejecutables, argumentos, scripts, `GameAction`, imágenes, notas, tokens, cookies o raw metadata, úsalo solo como staging manual/redactado.

## Cierre seguro de la prueba

Para desactivar el add-on:

1. Quita la carpeta de `External extensions` en Playnite.
2. Reinicia Playnite.
3. Borra los JSON temporales si no quieres conservarlos.

No commitees builds, logs, `.pext`, reportes generados ni exports reales con datos privados.
