"use strict";

const schema_api = (() => {
  if (typeof require === "function") {
    try {
      return require("./export-schema.js");
    } catch (_error) {
      // Browser extension contexts can load this file without CommonJS.
    }
  }
  return typeof globalThis !== "undefined" ? globalThis.SteamAccessExportSchema : undefined;
})();

const sanitize_api = (() => {
  if (typeof require === "function") {
    try {
      return require("./sanitize.js");
    } catch (_error) {
      // Browser extension contexts can load this file without CommonJS.
    }
  }
  return typeof globalThis !== "undefined" ? globalThis.SteamAccessSanitize : undefined;
})();

const COLLECTION_KEYS = schema_api?.COLLECTION_KEYS ?? Object.freeze([
  "owned_appids",
  "family_shared_appids",
  "wishlist_appids",
]);
const COLLECTOR_SCHEMA = "steam_access_collector_v1";
const COLLECTOR_STORAGE_KEY = "steam_access_collector_state";

const is_plain_object = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);

const appid_array = (values) => {
  if (sanitize_api?.sanitize_appids) {
    return sanitize_api.sanitize_appids(values);
  }
  return Array.isArray(values) ? values.map(String).filter((value) => /^\d+$/.test(value)) : [];
};

const valid_collection_key = (collection_key) => (
  COLLECTION_KEYS.includes(collection_key) ? collection_key : "owned_appids"
);

const merge_appids = (...collections) => {
  const seen = new Set();
  const merged = [];

  for (const collection of collections) {
    for (const appid of appid_array(collection)) {
      if (seen.has(appid)) {
        continue;
      }
      seen.add(appid);
      merged.push(appid);
    }
  }

  return merged;
};

const collector_counts = (state = {}) => COLLECTION_KEYS.reduce(
  (counts, key) => ({
    ...counts,
    [`${key.replace(/_appids$/, "")}_count`]: appid_array(state[key]).length,
  }),
  {
    total_count: COLLECTION_KEYS.reduce((total, key) => total + appid_array(state[key]).length, 0),
  },
);

const safe_timestamp = (value) => (typeof value === "string" ? value.trim() : "");

const collector_metadata = (state = {}, updates = {}) => {
  const current = is_plain_object(state.metadata) ? state.metadata : {};
  const capture_count = Number.isSafeInteger(current.capture_count) && current.capture_count > 0
    ? current.capture_count
    : 0;
  const next_capture_count = Number.isSafeInteger(updates.capture_count)
    ? Math.max(0, updates.capture_count)
    : capture_count;
  const updated_at = safe_timestamp(updates.updated_at) || safe_timestamp(current.updated_at);

  return {
    capture_count: next_capture_count,
    ...(updated_at ? { updated_at } : {}),
  };
};

const empty_collector_state = (metadata = {}) => ({
  schema: COLLECTOR_SCHEMA,
  owned_appids: [],
  family_shared_appids: [],
  wishlist_appids: [],
  metadata: collector_metadata({}, metadata),
});

const normalize_collector_state = (state = {}) => {
  const data = is_plain_object(state) ? state : {};
  return {
    schema: COLLECTOR_SCHEMA,
    owned_appids: merge_appids(data.owned_appids),
    family_shared_appids: merge_appids(data.family_shared_appids),
    wishlist_appids: merge_appids(data.wishlist_appids),
    metadata: collector_metadata(data),
  };
};

const add_appids_to_collector = (state = {}, collection_key = "owned_appids", appids = [], metadata = {}) => {
  const normalized = normalize_collector_state(state);
  const key = valid_collection_key(collection_key);
  const updated_at = safe_timestamp(metadata.updated_at) || new Date().toISOString();

  return normalize_collector_state({
    ...normalized,
    [key]: merge_appids(normalized[key], appids),
    metadata: collector_metadata(normalized, {
      capture_count: (normalized.metadata.capture_count || 0) + 1,
      updated_at,
    }),
  });
};

const collector_collections = (state = {}) => {
  const normalized = normalize_collector_state(state);
  return COLLECTION_KEYS.reduce(
    (collections, key) => ({ ...collections, [key]: normalized[key] }),
    {},
  );
};

const build_collector_export = (state = {}, metadata = {}) => {
  if (!schema_api?.build_steam_access_export) {
    throw new Error("SteamAccessExportSchema must be loaded before building collector exports");
  }
  const generated_at = safe_timestamp(metadata.generated_at) || new Date().toISOString();
  return schema_api.build_steam_access_export(collector_collections(state), { generated_at });
};

const clear_collector_state = (metadata = {}) => empty_collector_state(metadata);

const extension_storage_area = () => {
  if (typeof chrome !== "undefined" && chrome.storage?.local) {
    return chrome.storage.local;
  }
  if (typeof browser !== "undefined" && browser.storage?.local) {
    return browser.storage.local;
  }
  return null;
};

const storage_get = async (storage_area, key) => {
  if (!storage_area?.get) {
    return {};
  }
  return storage_area.get(key);
};

const storage_set = async (storage_area, record) => {
  if (!storage_area?.set) {
    return;
  }
  await storage_area.set(record);
};

const read_collector_state = async (storage_area = extension_storage_area()) => {
  const result = await storage_get(storage_area, COLLECTOR_STORAGE_KEY);
  const stored_state = is_plain_object(result)
    ? result[COLLECTOR_STORAGE_KEY]
    : null;
  return normalize_collector_state(stored_state);
};

const write_collector_state = async (state = {}, storage_area = extension_storage_area()) => {
  const normalized = normalize_collector_state(state);
  await storage_set(storage_area, { [COLLECTOR_STORAGE_KEY]: normalized });
  return normalized;
};

const clear_collector_storage = async (storage_area = extension_storage_area(), metadata = {}) => (
  write_collector_state(clear_collector_state(metadata), storage_area)
);

const collector_api = Object.freeze({
  COLLECTOR_SCHEMA,
  COLLECTOR_STORAGE_KEY,
  COLLECTION_KEYS,
  empty_collector_state,
  normalize_collector_state,
  add_appids_to_collector,
  collector_collections,
  collector_counts,
  build_collector_export,
  clear_collector_state,
  read_collector_state,
  write_collector_state,
  clear_collector_storage,
});

if (typeof module !== "undefined" && module.exports) {
  module.exports = collector_api;
}

if (typeof globalThis !== "undefined") {
  globalThis.SteamAccessCollector = collector_api;
}
