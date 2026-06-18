using Playnite.SDK;
using Playnite.SDK.Data;
using Playnite.SDK.Models;
using Playnite.SDK.Plugins;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace SteamTools.PlayniteExporter
{
    public sealed class SteamToolsExporterPlugin : GenericPlugin
    {
        private const string LibrarySchema = "steamtools_playnite_library_v1";
        private const string AccessSchema = "steamtools_playnite_access_v1";
        private readonly IPlayniteAPI api;

        public override Guid Id { get; } = Guid.Parse("5e8b6a3c-76bb-4d48-94d3-a1d6f97db7c1");

        public SteamToolsExporterPlugin(IPlayniteAPI api) : base(api)
        {
            this.api = api;
        }

        public override IEnumerable<MainMenuItem> GetMainMenuItems(GetMainMenuItemsArgs args)
        {
            yield return new MainMenuItem
            {
                Description = "Save SteamTools library JSON...",
                MenuSection = "@SteamTools",
                Action = _ => SaveJson(BuildLibraryPayload(), "steamtools-playnite-library.json")
            };

            yield return new MainMenuItem
            {
                Description = "Show/copy SteamTools library JSON",
                MenuSection = "@SteamTools",
                Action = _ => ShowJson(BuildLibraryPayload(), "SteamTools Playnite library JSON")
            };

            yield return new MainMenuItem
            {
                Description = "Save SteamTools access JSON...",
                MenuSection = "@SteamTools",
                Action = _ => SaveJson(BuildAccessPayload(), "steamtools-playnite-access.json")
            };

            yield return new MainMenuItem
            {
                Description = "Show/copy SteamTools access JSON",
                MenuSection = "@SteamTools",
                Action = _ => ShowJson(BuildAccessPayload(), "SteamTools Playnite access JSON")
            };
        }

        private object BuildLibraryPayload()
        {
            var exportedAt = DateTime.UtcNow.ToString("o");
            var items = api.Database.Games
                .Select(game => BuildLibraryItem(game, exportedAt))
                .Where(item => item != null)
                .ToList();

            return new
            {
                schema = LibrarySchema,
                source = "playnite",
                exported_at = exportedAt,
                items
            };
        }

        private object BuildAccessPayload()
        {
            var exportedAt = DateTime.UtcNow.ToString("o");
            var items = api.Database.Games
                .Select(game => BuildAccessItem(game, exportedAt))
                .Where(item => item != null)
                .ToList();

            return new
            {
                schema = AccessSchema,
                source = "playnite",
                exported_at = exportedAt,
                items
            };
        }

        private object? BuildLibraryItem(Game game, string exportedAt)
        {
            var platform = BuildLibraryPlatform(game, exportedAt);
            if (platform == null)
            {
                return null;
            }

            return new
            {
                playnite_id = game.Id.ToString(),
                name = CleanText(game.Name),
                steam_appid = TrustedSteamAppId(game),
                observed_at = exportedAt,
                platforms = new[] { platform }
            };
        }

        private object? BuildAccessItem(Game game, string exportedAt)
        {
            var installed = IsInstalled(game);
            var platform = BuildAccessPlatform(game, installed, exportedAt);
            if (platform == null)
            {
                return null;
            }

            return new
            {
                playnite_id = game.Id.ToString(),
                name = CleanText(game.Name),
                steam_appid = TrustedSteamAppId(game),
                observed_at = exportedAt,
                platforms = new[] { platform }
            };
        }

        private object? BuildLibraryPlatform(Game game, string exportedAt)
        {
            var store = StoreName(game);
            if (string.IsNullOrWhiteSpace(store))
            {
                return null;
            }

            return new
            {
                store,
                source_type = SourceType(game),
                provider_game_id = SafeProviderGameId(game.GameId),
                family_hint = IsSteamFamilySource(store),
                evidence = "playnite_library",
                observed_at = exportedAt
            };
        }

        private object? BuildAccessPlatform(Game game, bool installed, string exportedAt)
        {
            var store = StoreName(game);
            if (string.IsNullOrWhiteSpace(store))
            {
                return null;
            }

            return new
            {
                store,
                installed,
                playable_hint = installed,
                family_hint = IsSteamFamilySource(store),
                evidence = "playnite_access",
                observed_at = exportedAt
            };
        }

        private string? StoreName(Game game)
        {
            var sourceName = CleanText(game.Source?.Name);
            if (!string.IsNullOrWhiteSpace(sourceName))
            {
                return sourceName;
            }

            return CleanText(ProviderName(game));
        }

        private string? ProviderName(Game game)
        {
            var plugin = api.Addons.Plugins
                .OfType<LibraryPlugin>()
                .FirstOrDefault(item => item.Id == game.PluginId);
            return plugin?.Name;
        }

        private string SourceType(Game game)
        {
            var store = StoreName(game)?.ToLowerInvariant() ?? string.Empty;
            if (IsSteamFamilySource(store))
            {
                return "playnite_addon";
            }

            if (store.Contains("steam") || store.Contains("gog") || store.Contains("epic") || store.Contains("ubisoft") || store.Contains("xbox"))
            {
                return "official_launcher";
            }

            return string.IsNullOrWhiteSpace(store) ? "unknown" : "playnite_addon";
        }

        private static bool IsSteamFamilySource(string? store)
        {
            return CleanText(store)?.ToLowerInvariant().Contains("steam family") == true;
        }

        private string? TrustedSteamAppId(Game game)
        {
            var gameId = SafeProviderGameId(game.GameId);
            if (string.IsNullOrWhiteSpace(gameId) || !gameId.All(char.IsDigit))
            {
                return null;
            }

            var source = StoreName(game)?.ToLowerInvariant() ?? string.Empty;
            return source.Contains("steam") ? gameId : null;
        }

        private static bool IsInstalled(Game game)
        {
            return game.IsInstalled || game.InstallationStatus == InstallationStatus.Installed;
        }

        private static string? SafeProviderGameId(string? value)
        {
            var cleaned = CleanText(value);
            if (string.IsNullOrWhiteSpace(cleaned))
            {
                return null;
            }

            if (cleaned.Contains("/") || cleaned.Contains("\\") || cleaned.Contains(":") || cleaned.Contains(".."))
            {
                return null;
            }

            return cleaned.Length > 128 ? cleaned.Substring(0, 128) : cleaned;
        }

        private static string? CleanText(string? value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return null;
            }

            return value.Trim();
        }

        private void SaveJson(object payload, string defaultFileName)
        {
            var json = Serialization.ToJson(payload, true);
            var path = api.Dialogs.SaveFile("JSON files|*.json", true);
            if (string.IsNullOrWhiteSpace(path))
            {
                return;
            }

            File.WriteAllText(path, json, Encoding.UTF8);
            api.Dialogs.ShowMessage($"SteamTools export saved. Suggested name: {defaultFileName}", "SteamTools Playnite Exporter");
        }

        private void ShowJson(object payload, string caption)
        {
            var json = Serialization.ToJson(payload, true);
            api.Dialogs.ShowSelectableString("Select/copy the generated JSON:", caption, json);
        }
    }
}
