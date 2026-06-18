# SteamTools Playnite Exporter

Minimal Playnite Desktop add-on scaffold for exporting a privacy-safe local inventory that Steam Tools can import.

Status: early local/dev scaffold. No binaries are committed.

## Why this exists

Existing Playnite exporters are useful as manual staging tools, but most can export too much metadata: install paths, actions, launch commands, images, notes, raw fields, or write-back/import capabilities. This add-on intentionally emits only the fields needed by Steam Tools contracts.

## Contracts emitted

- `steamtools_playnite_library_v1` → import with Steam Tools `--wishlist-external-matches-json`.
- `steamtools_playnite_access_v1` → import with Steam Tools `--play-access-json`.

Both schemas are local-only and advisory-only. They never prove ownership, Steam Family, or whether a purchase should be removed.

## Guardrails

- User-initiated menu actions only; no background export.
- No network calls.
- No local server endpoint by default.
- Output only via a user-selected JSON file or a copyable/selectable dialog.
- No `InstallDirectory`, executables, arguments, scripts, working directories, ROM paths, screenshots, saves, notes, descriptions, images, raw metadata, cookies, tokens, logs, account IDs, prices, cart, checkout, wishlist mutation, or Steam Family inference.
- The code projects Playnite games into explicit DTOs; it never serializes full `Game` or `GameAction` objects.

## Playnite development install

Recommended workflow while private/local:

1. Create/build the plugin with Playnite Toolbox or MSBuild on a Windows machine with Playnite development prerequisites.
2. In Playnite Desktop, enable developer extension loading and add the build output folder as an external extension, or copy the built extension folder into Playnite's `Extensions` folder.
3. Restart Playnite.
4. Use `Extensions → SteamTools` menu entries.

PowerShell script extensions are avoided because Playnite 11 is expected to remove PowerShell extension support.

## Export workflow

Menu entries planned in this scaffold:

- `Extensions → SteamTools → Save SteamTools library JSON...`
- `Extensions → SteamTools → Show/copy SteamTools library JSON`
- `Extensions → SteamTools → Save SteamTools access JSON...`
- `Extensions → SteamTools → Show/copy SteamTools access JSON`

Save/copy flows are explicit. Canceling the save dialog does nothing.

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

## Development mode packaging

Until the exporter stabilizes, use Playnite development loading instead of publishing a `.pext`:

1. Build this project on Windows.
2. Add the build output folder in Playnite under `Settings → For developers → External extensions`.
3. Restart Playnite after every plugin build or source change.

Plugins do not hot-reload at runtime. A `.pext` package can be produced later with Playnite `Toolbox.exe pack` once the field mapping is stable.

## Validation from this repo

Without a Playnite host, local validation is static/text-only:

```bash
git diff --check -- extension/playnite-steamtools-exporter
```

Functional validation requires Playnite on Windows and should use a small test library first.

## Candidate exporter comparison

If testing existing Playnite add-ons, compare their output against this allowlist. Any export containing install paths, executable commands, GameActions, scripts, notes, raw metadata, images, tokens, cookies, or account identifiers should be treated as staging-only at best and should not be imported directly.
