# SteamTools Playnite Exporter

Minimal Playnite Desktop add-on scaffold for exporting a privacy-safe local inventory that Steam Tools can import.

Status: early local/dev scaffold. No binaries are committed.

At-home tutorial: `../../docs/runbooks/playnite-exporter-at-home.md`.

## Why this exists

Existing Playnite exporters are useful as manual staging tools, but most can export too much metadata: install paths, actions, launch commands, images, notes, raw fields, or write-back/import capabilities. This add-on intentionally emits only the fields needed by Steam Tools contracts.

## Contracts emitted

- `steamtools_playnite_library_v1` → import with Steam Tools `--wishlist-external-matches-json`.
- `steamtools_playnite_access_v1` → import with Steam Tools `--play-access-json`.

Both schemas are local-only and advisory-only. They never prove ownership, Steam Family, or whether a purchase should be removed.

See `docs/runbooks/wishlist-hygiene-multistore-contract.md` for the canonical import contract. This exporter only produces privacy-minimized source data; Steam Tools decides later whether a record becomes `external_matches`, `play_access`, or manual-review context.

## Guardrails

- User-initiated menu actions only; no background export.
- No network calls.
- No local server endpoint by default.
- Output only via a user-selected JSON file or a copyable/selectable dialog.
- No `InstallDirectory`, executables, arguments, scripts, working directories, ROM paths, screenshots, saves, notes, descriptions, images, raw metadata, cookies, tokens, logs, account IDs, prices, cart, checkout, wishlist mutation, or Steam Family inference.
- The code projects Playnite games into explicit DTOs; it never serializes full `Game` or `GameAction` objects.

## Playnite development install

There is no installer or published `.pext` yet. The current supported path is a development install on Windows.

Prerequisites:

- Playnite Desktop.
- .NET SDK/MSBuild or Visual Studio Build Tools.
- This repository checked out locally.

From PowerShell at the repository root:

```powershell
dotnet build .\extension\playnite-steamtools-exporter\SteamTools.PlayniteExporter.csproj -c Debug
```

Create a local extension folder and copy the two files Playnite needs:

```powershell
$PluginDir = "$env:USERPROFILE\Documents\SteamTools.PlayniteExporter"
New-Item -ItemType Directory -Force $PluginDir | Out-Null
Copy-Item .\extension\playnite-steamtools-exporter\extension.yaml $PluginDir\
Copy-Item .\extension\playnite-steamtools-exporter\bin\Debug\net462\SteamTools.PlayniteExporter.dll $PluginDir\
```

The folder loaded by Playnite must contain:

- `extension.yaml`
- `SteamTools.PlayniteExporter.dll`

Then load it in Playnite:

1. Open Playnite Desktop.
2. Go to `Settings → For developers → External extensions`.
3. Add the folder created above.
4. Restart Playnite.
5. Use `Extensions → SteamTools` menu entries.

PowerShell script extensions are avoided because Playnite 11 is expected to remove PowerShell extension support.

## Export workflow

Menu entries planned in this scaffold:

- `Extensions → SteamTools → Save SteamTools library JSON...`
- `Extensions → SteamTools → Show/copy SteamTools library JSON`
- `Extensions → SteamTools → Save SteamTools access JSON...`
- `Extensions → SteamTools → Show/copy SteamTools access JSON`

Save/copy flows are explicit. Canceling the save dialog does nothing.

Suggested filenames:

- `steamtools-playnite-library.json` for the library export.
- `steamtools-playnite-access.json` for the installed/playable access export.

## Field mapping

The exporter treats Playnite `Source` / library plugin as the launcher/store signal. It does **not** export Playnite hardware platforms as Steam Tools `platforms[*]` because that contract field means launcher/source, not OS/hardware.

For each game:

- `name`: Playnite game name.
- `playnite_id`: local Playnite GUID for grouping/debugging only; it is not an account ID and does not prove ownership.
- `steam_appid`: emitted only when a trusted numeric Steam AppID is available. Initial scaffold trusts numeric `Game.GameId` only for Steam-source games.
- `platforms[*].store`: safe launcher/source display name.
- `platforms[*].source_type`: `official_launcher` for known library sources, otherwise `playnite_addon`/`unknown`.
- `platforms[*].provider_game_id`: sanitized provider id, never a path.
- `platforms[*].installed`: high-level Playnite install flag.
- `platforms[*].playable_hint`: high-level boolean derived from install status only; no launch actions are inspected or exported.
- `platforms[*].family_hint`: `true` only when Playnite source text is `Steam Family Sharing` or equivalent. This is a review hint, not ownership or confirmed Family access.

Games without a trusted Steam AppID still appear in the safe inventory. Steam Tools can use exact title matches as `normalized_title` review signals, not as automatic ownership proof.

Duplicate titles across launchers are preserved. If the same title appears in Epic, GOG, Amazon, Xbox, Steam, or Steam Family Sharing, each source remains visible so Steam Tools can help with manual review instead of hiding potentially useful context.

The library export can include all safe games with a launcher/source. The access export is narrower: it only includes games Playnite reports as installed/playable, because Steam Tools treats that file as access context rather than full inventory.

## Steam Tools import mapping

- Library JSON (`steamtools_playnite_library_v1`) is meant for `--wishlist-external-matches-json` and can become `external_matches` only as review/advisory context.
- Access JSON (`steamtools_playnite_access_v1`) is meant for `--play-access-json` and can become `play_access` only when Playnite reports a high-level installed/playable signal.
- Steam and Steam Family entries from Playnite remain review hints. Confirmed ownership/family access belongs to separate `steam_access` imports, not this exporter.
- Playnite output is not a price source and must not feed `external_offers`, score, ranking, filters, defaults, cart, checkout, or wishlist mutation.

Example CLI imports from Steam Tools:

```powershell
python steam_deals_generator.py --vanity gaben --wishlist-external-matches-json "C:\path\steamtools-playnite-library.json"
python steam_deals_generator.py --vanity gaben --play-access-json "C:\path\steamtools-playnite-access.json"
```

Use your own Steam vanity/profile input and the actual file paths you selected in Playnite. The Web UI can also use these JSONs through the optional file fields for external wishlist matches and local play access.

For a full home testing checklist, including build folder layout and troubleshooting, see `../../docs/runbooks/playnite-exporter-at-home.md`.

## Development mode packaging

Until the exporter stabilizes, use Playnite development loading instead of publishing a `.pext`:

1. Build this project on Windows.
2. Add the build output folder in Playnite under `Settings → For developers → External extensions`.
3. Restart Playnite after every plugin build or source change.

Plugins do not hot-reload at runtime. A `.pext` package can be produced later with Playnite `Toolbox.exe pack` once the field mapping is stable.

Do not commit generated `bin/`, `obj/`, `.pext`, zip files, logs, or exported JSONs.

## Troubleshooting

- Menu missing: confirm Playnite loaded the folder that contains both `extension.yaml` and `SteamTools.PlayniteExporter.dll`, then restart Playnite.
- Build succeeds but Playnite does not load it: rebuild, recopy the DLL, verify the `Module` in `extension.yaml` still matches `SteamTools.PlayniteExporter.dll`, and restart Playnite.
- JSON has fewer items than expected: the access export intentionally includes only games Playnite reports as installed/playable; use the library export for broader inventory review.
- Need a real install package: wait for a Windows + Playnite smoke first; `.pext` packaging is intentionally deferred until the source/dev flow is validated.

## Validation from this repo

Without a Playnite host, local validation is static/text-only:

```bash
git diff --check -- extension/playnite-steamtools-exporter
```

Functional validation requires Playnite on Windows and should use a small test library first.

## Candidate exporter comparison

If testing existing Playnite add-ons, compare their output against this allowlist. Any export containing install paths, executable commands, GameActions, scripts, notes, raw metadata, images, tokens, cookies, or account identifiers should be treated as staging-only at best and should not be imported directly.
