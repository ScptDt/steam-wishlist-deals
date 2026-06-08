"use strict";

const FILE_NAME = "steam-access-import.json";
const LOCAL_DIRECT_MESSAGE_TYPES = Object.freeze({
  PAIR: "steam_access_pair_local_app",
  IMPORT: "steam_access_import_local_app",
});
const COLLECTION_KEYS = Object.freeze([
  "owned_appids",
  "family_shared_appids",
  "wishlist_appids",
]);

const dom = Object.freeze({
  collection_select: document.getElementById("collection_select"),
  extract_button: document.getElementById("extract_button"),
  collector_add_button: document.getElementById("collector_add_button"),
  collector_export_button: document.getElementById("collector_export_button"),
  collector_clear_button: document.getElementById("collector_clear_button"),
  collector_counts: document.getElementById("collector_counts"),
  collector_status: document.getElementById("collector_status"),
  pair_button: document.getElementById("pair_button"),
  send_button: document.getElementById("send_button"),
  copy_button: document.getElementById("copy_button"),
  save_button: document.getElementById("save_button"),
  export_text: document.getElementById("export_text"),
  appid_count: document.getElementById("appid_count"),
  local_base_url: document.getElementById("local_base_url"),
  pairing_token: document.getElementById("pairing_token"),
  direct_status: document.getElementById("direct_status"),
  status_message: document.getElementById("status_message"),
});

let current_export_data = null;
let current_collection_key = "";
let current_export_source = "";
let local_session_token = "";

const set_status = (message, state = "info") => {
  dom.status_message.textContent = message;
  dom.status_message.dataset.state = state;
};

const set_direct_status = (message, state = "info") => {
  dom.direct_status.textContent = message;
  dom.direct_status.dataset.state = state;
};

const has_appids = (export_data) => count_appids(export_data || {}) > 0;

const set_collector_status = (message, state = "info") => {
  dom.collector_status.textContent = message;
  dom.collector_status.dataset.state = state;
};

const update_direct_send_state = () => {
  dom.send_button.disabled = current_export_source !== "collector" || !has_appids(current_export_data) || !local_session_token;
};

const update_collector_add_state = () => {
  dom.collector_add_button.disabled = !current_export_data || !current_collection_key;
};

const reset_current_export = () => {
  current_export_data = null;
  current_collection_key = "";
  current_export_source = "";
  set_export_text("", 0);
};

const set_busy = (is_busy) => {
  dom.extract_button.disabled = is_busy;
  dom.extract_button.textContent = is_busy
    ? "Extracting visible AppIDs..."
    : "Extract sanitized JSON from active Steam tab";
};

const set_export_text = (text, appid_count) => {
  dom.export_text.value = text;
  dom.appid_count.textContent = `${appid_count} AppID${appid_count === 1 ? "" : "s"}`;
  dom.copy_button.disabled = !text;
  dom.save_button.disabled = !text;
  update_collector_add_state();
  update_direct_send_state();
};

const collector_api = () => {
  if (!globalThis.SteamAccessCollector) {
    throw new Error("Collector helpers are not available in this extension context.");
  }
  return globalThis.SteamAccessCollector;
};

const render_collector_counts = (state = {}) => {
  const counts = collector_api().collector_counts(state);
  dom.collector_counts.textContent = [
    `Collector: ${counts.owned_count || 0} owned`,
    `${counts.family_shared_count || 0} family`,
    `${counts.wishlist_count || 0} wishlist`,
    `${counts.total_count || 0} total`,
  ].join(" · ");
};

const refresh_collector_state = async () => {
  const state = await collector_api().read_collector_state();
  render_collector_counts(state);
  return state;
};

const send_local_app_message = async (message) => {
  const response = await chrome.runtime.sendMessage({
    ...message,
    base_url: dom.local_base_url.value,
  });
  if (!response?.ok) {
    throw new Error(response?.message || "The local app rejected direct send.");
  }
  return response.data || {};
};

const get_active_tab = async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || typeof tab.id !== "number") {
    throw new Error("No active browser tab was found.");
  }
  return tab;
};

const extract_visible_steam_appids = () => {
  const MAX_APPIDS = 50000;
  const APPID_PATTERNS = [
    /\/app\/(\d+)/gi,
    /(?:^|[_-])app[_-]?(\d+)(?:\D|$)/gi,
    /(?:^|[?&#_=-])appid(?:=|_|-)?(\d+)(?:\D|$)/gi,
    /(?:^|[?&#_=-])appids(?:=|_|-)?(\d+)(?:\D|$)/gi,
    /(?:^|[?&#_=-])gameid(?:=|_|-)?(\d+)(?:\D|$)/gi,
  ];

  const is_steam_page = /(^|\.)steam(?:community|powered)\.com$/i.test(location.hostname);
  const page_path = `${location.pathname}${location.search}`.toLowerCase();
  const values = [];
  if (!is_steam_page) {
    return { appids: [], is_steam_page: false, page_path };
  }

  const push_matches = (value) => {
    const text = typeof value === "string" ? value : "";
    if (!text) {
      return;
    }
    if (/^\d+(?:\s*,\s*\d+)*$/.test(text)) {
      text.split(",").forEach((appid) => {
        if (values.length < MAX_APPIDS) {
          values.push(appid.trim());
        }
      });
      return;
    }
    for (const pattern of APPID_PATTERNS) {
      pattern.lastIndex = 0;
      let match = pattern.exec(text);
      while (match && values.length < MAX_APPIDS) {
        values.push(match[1]);
        match = pattern.exec(text);
      }
    }
  };

  document.querySelectorAll("a[href], [data-ds-appid], [data-appid], [data-gameid], [id]").forEach((node) => {
    push_matches(node.getAttribute("href"));
    push_matches(node.getAttribute("data-ds-appid"));
    push_matches(node.getAttribute("data-appid"));
    push_matches(node.getAttribute("data-gameid"));
    push_matches(node.getAttribute("id"));
  });

  return { appids: values, is_steam_page: true, page_path };
};

const detect_collection_key = (page_path, selected_key) => {
  if (COLLECTION_KEYS.includes(selected_key)) {
    return selected_key;
  }
  if (page_path.includes("wishlist")) {
    return "wishlist_appids";
  }
  if (page_path.includes("family")) {
    return "family_shared_appids";
  }
  return "owned_appids";
};

const build_payload = (appids, collection_key) => ({
  owned_appids: collection_key === "owned_appids" ? appids : [],
  family_shared_appids: collection_key === "family_shared_appids" ? appids : [],
  wishlist_appids: collection_key === "wishlist_appids" ? appids : [],
});

const build_export = (extraction_result, selected_key) => {
  if (!extraction_result?.is_steam_page) {
    throw new Error("The active tab is not a Steam Store or Steam Community page.");
  }

  const collection_key = detect_collection_key(extraction_result.page_path || "", selected_key);
  const payload = build_payload(extraction_result.appids || [], collection_key);
  const export_data = globalThis.SteamAccessSanitize.build_sanitized_steam_access_export(payload, {
    generated_at: new Date().toISOString(),
  });

  return { collection_key, export_data };
};

const count_appids = (export_data) => COLLECTION_KEYS.reduce(
  (total, key) => total + (Array.isArray(export_data[key]) ? export_data[key].length : 0),
  0,
);

const extract_export = async () => {
  set_busy(true);
  try {
    const tab = await get_active_tab();
    if (tab.url && !/^https?:\/\//i.test(tab.url)) {
      throw new Error("Open a regular Steam web page before extracting AppIDs.");
    }

    const [execution] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extract_visible_steam_appids,
    });
    const { collection_key, export_data } = build_export(execution?.result, dom.collection_select.value);
    const text = JSON.stringify(export_data, null, 2);
    const appid_count = count_appids(export_data);

    current_export_data = export_data;
    current_collection_key = collection_key;
    current_export_source = "single_capture";
    set_export_text(text, appid_count);
    set_status(`Ready: ${appid_count} sanitized AppIDs in ${collection_key}. Review, copy, save, or add to the manual collector.`, "success");
    set_direct_status("Direct send uses combined collector JSON. Add this capture to the collector and export combined JSON, or use Copy/Save.", "info");
  } catch (error) {
    reset_current_export();
    set_status(error instanceof Error ? error.message : "Unable to extract AppIDs.", "error");
  } finally {
    set_busy(false);
  }
};

const export_collector_json = async () => {
  try {
    const api = collector_api();
    const state = await api.read_collector_state();
    const export_data = api.build_collector_export(state, {
      generated_at: new Date().toISOString(),
    });
    const appid_count = count_appids(export_data);
    current_export_data = export_data;
    current_collection_key = "";
    current_export_source = "collector";
    set_export_text(JSON.stringify(export_data, null, 2), appid_count);
    render_collector_counts(state);
    set_collector_status(
      `Combined collector JSON ready with ${appid_count} AppIDs. Copy/Save is manual; direct send remains optional after pairing.`,
      "success",
    );
    set_direct_status(
      appid_count > 0
        ? "Combined collector JSON is ready. Pair with the local app if you want direct send."
        : "Collector export is empty. Add visible AppIDs before direct send.",
      appid_count > 0 ? "info" : "error",
    );
    set_status("Combined collector JSON is displayed. Use Copy JSON or Save JSON if you want manual import.", "success");
  } catch (error) {
    set_collector_status(error instanceof Error ? error.message : "Unable to export collector JSON.", "error");
  }
};

const clear_collector = async () => {
  try {
    const api = collector_api();
    const cleared_state = await api.clear_collector_storage(undefined, {
      updated_at: new Date().toISOString(),
    });
    render_collector_counts(cleared_state);
    if (current_export_source === "collector") {
      reset_current_export();
      set_status("Collector state cleared. The combined JSON display was cleared to avoid sending stale data.", "info");
    }
    set_collector_status("Collector cleared. Only local AppID collector state was reset.", "success");
  } catch (error) {
    set_collector_status(error instanceof Error ? error.message : "Unable to clear collector.", "error");
  }
};

const add_current_capture_to_collector = async () => {
  try {
    if (!current_export_data || !current_collection_key) {
      throw new Error("Extract visible AppIDs before adding to the collector.");
    }
    dom.collector_add_button.disabled = true;
    const api = collector_api();
    const previous_state = await api.read_collector_state();
    const previous_count = (previous_state[current_collection_key] || []).length;
    const next_state = api.add_appids_to_collector(
      previous_state,
      current_collection_key,
      current_export_data[current_collection_key] || [],
      { updated_at: new Date().toISOString() },
    );
    const saved_state = await api.write_collector_state(next_state);
    const next_count = (saved_state[current_collection_key] || []).length;
    render_collector_counts(saved_state);
    set_collector_status(
      `Added ${Math.max(0, next_count - previous_count)} new AppIDs to ${current_collection_key}. Capture pages manually; completeness is not guaranteed.`,
      "success",
    );
  } catch (error) {
    set_collector_status(error instanceof Error ? error.message : "Unable to update collector.", "error");
  } finally {
    update_collector_add_state();
  }
};

const pair_local_app = async () => {
  const pairing_token = dom.pairing_token.value.trim();
  try {
    dom.pair_button.disabled = true;
    local_session_token = "";
    update_direct_send_state();
    const response = await send_local_app_message({
      type: LOCAL_DIRECT_MESSAGE_TYPES.PAIR,
      pairing_token,
    });
    local_session_token = typeof response.session_token === "string" ? response.session_token : "";
    if (!local_session_token) {
      throw new Error("The local app did not return a direct-send session.");
    }
    dom.pairing_token.value = "";
    set_direct_status("Paired with local app. Session is held in popup memory only.", "success");
  } catch (error) {
    set_direct_status(
      `${error instanceof Error ? error.message : "Unable to pair with local app."} Copy/Save remains available.`,
      "error",
    );
  } finally {
    dom.pair_button.disabled = false;
    update_direct_send_state();
  }
};

const send_direct_import = async () => {
  try {
    if (current_export_source !== "collector") {
      throw new Error("Export combined collector JSON before direct send.");
    }
    if (!has_appids(current_export_data)) {
      throw new Error("Combined collector JSON has no AppIDs to send.");
    }
    dom.send_button.disabled = true;
    await send_local_app_message({
      type: LOCAL_DIRECT_MESSAGE_TYPES.IMPORT,
      payload: current_export_data,
      session_token: local_session_token,
    });
    set_direct_status("Combined AppID-only collector JSON sent to local app. Review the local confirmation/result.", "success");
  } catch (error) {
    set_direct_status(
      `${error instanceof Error ? error.message : "Unable to send to local app."} Copy/Save remains available.`,
      "error",
    );
  } finally {
    update_direct_send_state();
  }
};

const copy_export = async () => {
  try {
    await navigator.clipboard.writeText(dom.export_text.value);
    set_status("Sanitized JSON copied. Paste it manually into your chosen local import path.", "success");
  } catch (error) {
    dom.export_text.focus();
    dom.export_text.select();
    set_status("Clipboard permission was denied. Select the JSON text and copy it manually.", "error");
  }
};

const save_export = () => {
  const blob = new Blob([dom.export_text.value], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = FILE_NAME;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  set_status("Save started through the browser. No data was sent to any endpoint.", "success");
};

dom.extract_button.addEventListener("click", extract_export);
dom.collector_add_button.addEventListener("click", add_current_capture_to_collector);
dom.collector_export_button.addEventListener("click", export_collector_json);
dom.collector_clear_button.addEventListener("click", clear_collector);
dom.pair_button.addEventListener("click", pair_local_app);
dom.send_button.addEventListener("click", send_direct_import);
dom.copy_button.addEventListener("click", copy_export);
dom.save_button.addEventListener("click", save_export);

refresh_collector_state().catch((error) => {
  set_collector_status(error instanceof Error ? error.message : "Unable to load collector state.", "error");
});
