"use strict";

const ACTION_READY_TITLE = "Steam Access Export ready. Open the popup to extract AppID-only JSON manually.";

chrome.runtime.onInstalled.addListener(() => {
  chrome.action.setBadgeText({ text: "" });
  chrome.action.setTitle({ title: ACTION_READY_TITLE });
});
