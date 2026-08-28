importScripts("lib/config.js", "lib/api.js", "lib/capture.js", "lib/tabs.js");

/**
 * POST page visit with optional engagement metrics.
 * @param {chrome.tabs.Tab} tab
 * @param {object | null} metrics
 */
async function captureTab(tab, metrics) {
  const url = tab.url || "";
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    return;
  }
  const { apiBaseUrl, apiToken } = await JunoConfig.load();
  if (!apiToken) {
    console.warn("Juno: set JUNO API token in extension options");
    return;
  }

  const payload = JunoCapture.buildPayload(tab, metrics);
  const { ok, status, body } = await JunoApi.postIngest(apiBaseUrl, apiToken, payload);
  if (!ok) {
    console.warn("Juno ingest failed", status, body);
    return;
  }
  console.log("Juno capture committed", body.capture_id, payload.title, metrics || {});
}

/** @param {number} tabId */
async function finalizeTab(tabId) {
  const row = JunoTabs.take(tabId);
  if (!row) {
    return;
  }
  await captureTab(row.tab, row.metrics);
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab?.url) {
    JunoTabs.track(tab);
  }
});

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  for (const tabId of JunoTabs.sessions.keys()) {
    if (tabId !== activeInfo.tabId) {
      await finalizeTab(tabId);
    }
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  void finalizeTab(tabId);
});

chrome.runtime.onMessage.addListener((message, sender) => {
  const tabId = sender.tab?.id;
  if (tabId == null) {
    return;
  }
  if (message.type === "juno-metrics" && message.metrics) {
    JunoTabs.setMetrics(tabId, message.metrics);
    return;
  }
  if (message.type === "juno-page-done") {
    if (message.metrics) {
      JunoTabs.setMetrics(tabId, message.metrics);
    }
    void finalizeTab(tabId);
  }
});

console.log("Juno extension service worker loaded");
