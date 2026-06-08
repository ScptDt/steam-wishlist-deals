"use strict";

const ACTION_READY_TITLE = "Steam Access Export ready. Open the popup to extract AppID-only JSON manually.";
const DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:8080";
const LOCAL_PAIR_PATH = "/api/steam-access/pair";
const LOCAL_IMPORT_PATH = "/api/steam-access/import";
const LOCAL_DIRECT_MESSAGE_TYPES = Object.freeze({
  PAIR: "steam_access_pair_local_app",
  IMPORT: "steam_access_import_local_app",
});

const normalize_local_base_url = (value = DEFAULT_LOCAL_BASE_URL) => {
  let url;
  try {
    url = new URL(value || DEFAULT_LOCAL_BASE_URL);
  } catch (_error) {
    throw new Error("Local Steam Tools URL inválida.");
  }
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1") {
    throw new Error("El envío directo solo permite http://127.0.0.1.");
  }
  url.pathname = "";
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/$/, "");
};

const local_endpoint_url = (path, base_url = DEFAULT_LOCAL_BASE_URL) => {
  const normalized_base = normalize_local_base_url(base_url);
  return `${normalized_base}${path}`;
};

const build_local_json_request = (payload, token, { pairing = false } = {}) => {
  const clean_token = typeof token === "string" ? token.trim() : "";
  if (!clean_token) {
    throw new Error("Token local requerido para envío directo.");
  }
  return {
    method: "POST",
    credentials: "omit",
    headers: {
      "Content-Type": "application/json",
      ...(pairing ? { "X-Pairing-Token": clean_token } : { Authorization: `Bearer ${clean_token}` }),
    },
    body: JSON.stringify(payload),
  };
};

const post_local_json = async (path, payload, token, options = {}) => {
  const url = local_endpoint_url(path, options.base_url);
  const request = build_local_json_request(payload, token, { pairing: options.pairing });
  const response = await fetch(url, request);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || "La app local rechazó el envío directo.");
  }
  return data;
};

const pair_with_local_app = (pairing_token, options = {}) => (
  post_local_json(LOCAL_PAIR_PATH, { pairing_token }, pairing_token, { ...options, pairing: true })
);

const send_steam_access_import = (export_data, session_token, options = {}) => (
  post_local_json(LOCAL_IMPORT_PATH, export_data, session_token, options)
);

const handle_local_direct_message = async (message = {}) => {
  if (message.type === LOCAL_DIRECT_MESSAGE_TYPES.PAIR) {
    return pair_with_local_app(message.pairing_token, { base_url: message.base_url });
  }
  if (message.type === LOCAL_DIRECT_MESSAGE_TYPES.IMPORT) {
    return send_steam_access_import(message.payload, message.session_token, { base_url: message.base_url });
  }
  throw new Error("Solicitud local no soportada.");
};

const direct_error_message = (error) => (
  error instanceof Error && error.message ? error.message : "La app local rechazó el envío directo."
);

if (typeof chrome !== "undefined" && chrome.runtime?.onInstalled) {
  chrome.runtime.onInstalled.addListener(() => {
    chrome.action.setBadgeText({ text: "" });
    chrome.action.setTitle({ title: ACTION_READY_TITLE });
  });
}

if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    const message_type = message && typeof message === "object" ? message.type : "";
    if (!Object.values(LOCAL_DIRECT_MESSAGE_TYPES).includes(message_type)) {
      return false;
    }
    handle_local_direct_message(message)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((error) => sendResponse({ ok: false, message: direct_error_message(error) }));
    return true;
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    DEFAULT_LOCAL_BASE_URL,
    LOCAL_PAIR_PATH,
    LOCAL_IMPORT_PATH,
    LOCAL_DIRECT_MESSAGE_TYPES,
    normalize_local_base_url,
    local_endpoint_url,
    build_local_json_request,
    pair_with_local_app,
    send_steam_access_import,
    handle_local_direct_message,
  };
}
