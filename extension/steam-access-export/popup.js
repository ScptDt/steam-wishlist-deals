"use strict";

const FILE_NAME = "steam-access-import.json";
const COLLECTION_KEYS = Object.freeze([
  "owned_appids",
  "family_shared_appids",
  "wishlist_appids",
]);

const dom = Object.freeze({
  collection_select: document.getElementById("collection_select"),
  extract_button: document.getElementById("extract_button"),
  copy_button: document.getElementById("copy_button"),
  save_button: document.getElementById("save_button"),
  export_text: document.getElementById("export_text"),
  appid_count: document.getElementById("appid_count"),
  status_message: document.getElementById("status_message"),
});

const set_status = (message, state = "info") => {
  dom.status_message.textContent = message;
  dom.status_message.dataset.state = state;
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

    set_export_text(text, appid_count);
    set_status(`Ready: ${appid_count} sanitized AppIDs in ${collection_key}. Review, copy, or save manually.`, "success");
  } catch (error) {
    set_status(error instanceof Error ? error.message : "Unable to extract AppIDs.", "error");
  } finally {
    set_busy(false);
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
dom.copy_button.addEventListener("click", copy_export);
dom.save_button.addEventListener("click", save_export);
