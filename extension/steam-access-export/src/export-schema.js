"use strict";

const STEAM_ACCESS_SCHEMA = "steam_access_import_v1";
const STEAM_ACCESS_SOURCE = "steam_browser_helper_export";
const ADVISORY_ONLY = true;
const RANKING_IMPACT = "none";

const COLLECTION_KEYS = Object.freeze([
  "owned_appids",
  "family_shared_appids",
  "wishlist_appids",
]);

const empty_summary = (owned_appids, family_shared_appids, wishlist_appids) => ({
  owned_count: owned_appids.length,
  family_shared_count: family_shared_appids.length,
  wishlist_count: wishlist_appids.length,
  advisory_only: ADVISORY_ONLY,
  ranking_impact: RANKING_IMPACT,
});

const appid_array = (values) => (Array.isArray(values) ? values.map(String) : []);

const build_steam_access_export = (collections = {}, metadata = {}) => {
  const owned_appids = appid_array(collections.owned_appids);
  const family_shared_appids = appid_array(collections.family_shared_appids);
  const wishlist_appids = appid_array(collections.wishlist_appids);
  const generated_at = typeof metadata.generated_at === "string" ? metadata.generated_at.trim() : "";

  return {
    schema: STEAM_ACCESS_SCHEMA,
    source: STEAM_ACCESS_SOURCE,
    owned_appids,
    family_shared_appids,
    wishlist_appids,
    advisory_only: ADVISORY_ONLY,
    ranking_impact: RANKING_IMPACT,
    ...(generated_at ? { generated_at } : {}),
    provenance: "browser_helper_manual_export",
    summary: empty_summary(owned_appids, family_shared_appids, wishlist_appids),
  };
};

const export_schema_api = Object.freeze({
  STEAM_ACCESS_SCHEMA,
  STEAM_ACCESS_SOURCE,
  ADVISORY_ONLY,
  RANKING_IMPACT,
  COLLECTION_KEYS,
  build_steam_access_export,
});

if (typeof module !== "undefined" && module.exports) {
  module.exports = export_schema_api;
}

if (typeof globalThis !== "undefined") {
  globalThis.SteamAccessExportSchema = export_schema_api;
}
