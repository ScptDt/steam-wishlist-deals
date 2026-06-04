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

const COLLECTION_KEYS = schema_api?.COLLECTION_KEYS ?? Object.freeze([
  "owned_appids",
  "family_shared_appids",
  "wishlist_appids",
]);
const MAX_APPID = Number.MAX_SAFE_INTEGER;
const MAX_APPIDS_PER_COLLECTION = 50000;
const SENSITIVE_KEY_PATTERN = /(?:password|passcode|cookie|steamloginsecure|loginsecure|token|session|header|raw[_-]?(?:response|html)?|html|email|friend|family(?!_shared_appids)|profile|member)/i;

const is_plain_object = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);

const normalize_appid = (value) => {
  if (typeof value === "number" && Number.isInteger(value) && value > 0 && value <= MAX_APPID) {
    return String(value);
  }
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  const appid = Number(trimmed);
  return Number.isSafeInteger(appid) && appid > 0 ? String(appid) : null;
};

const appid_from_record = (record, fallback_key = null) => {
  if (is_plain_object(record)) {
    return normalize_appid(record.appid ?? record.steam_appid ?? record.app_id ?? fallback_key);
  }
  return normalize_appid(record) ?? normalize_appid(fallback_key);
};

const records_from_collection = (collection) => {
  if (Array.isArray(collection)) {
    return collection.map((record) => [record, null]);
  }
  if (is_plain_object(collection)) {
    return Object.entries(collection).map(([key, value]) => [value, key]);
  }
  return [[collection, null]];
};

const sanitize_appids = (collection) => {
  const seen = new Set();
  const appids = [];

  for (const [record, fallback_key] of records_from_collection(collection)) {
    const appid = appid_from_record(record, fallback_key);
    if (appid === null || seen.has(appid)) {
      continue;
    }
    seen.add(appid);
    appids.push(appid);
    if (appids.length >= MAX_APPIDS_PER_COLLECTION) {
      break;
    }
  }

  return appids;
};

const has_sensitive_key = (key) => SENSITIVE_KEY_PATTERN.test(String(key || ""));

const sanitize_steam_access_input = (payload = {}) => {
  const data = is_plain_object(payload) ? payload : {};
  return COLLECTION_KEYS.reduce(
    (collections, key) => ({
      ...collections,
      [key]: has_sensitive_key(key) ? [] : sanitize_appids(data[key]),
    }),
    {},
  );
};

const build_sanitized_steam_access_export = (payload = {}, metadata = {}) => {
  if (!schema_api?.build_steam_access_export) {
    throw new Error("SteamAccessExportSchema must be loaded before building exports");
  }
  return schema_api.build_steam_access_export(sanitize_steam_access_input(payload), metadata);
};

const sanitize_api = Object.freeze({
  MAX_APPIDS_PER_COLLECTION,
  has_sensitive_key,
  normalize_appid,
  sanitize_appids,
  sanitize_steam_access_input,
  build_sanitized_steam_access_export,
});

if (typeof module !== "undefined" && module.exports) {
  module.exports = sanitize_api;
}

if (typeof globalThis !== "undefined") {
  globalThis.SteamAccessSanitize = sanitize_api;
}
