importScripts("lib/excludes.js", "lib/config.js", "lib/api.js", "lib/capture.js", "lib/tabs.js");

/** When true, API returned 423 — stop ingesting until /status says running. */
let remoteCapturePaused = false;

/**
 * POST page visit with optional engagement metrics.
 * @param {chrome.tabs.Tab} tab
 * @param {object | null} metrics
 * @param {object[] | null} highlights
 */
async function captureTab(tab, metrics, highlights) {
  const url = tab.url || "";
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    return;
  }
  if (remoteCapturePaused) {
    return;
  }
  const { apiBaseUrl, apiToken, excludedDomains } = await JunoConfig.load();
  if (JunoExcludes.isExcluded(url, excludedDomains)) {
    console.log("Juno: skipped excluded domain", url);
    return;
  }
  if (!apiToken) {
    console.warn("Juno: set JUNO API token in extension options");
    return;
  }

  const payload = JunoCapture.buildPayload(tab, metrics, highlights);
  const { ok, status, body } = await JunoApi.postIngest(apiBaseUrl, apiToken, payload);
  if (status === 423) {
    remoteCapturePaused = true;
    console.warn("Juno: capture paused via API");
    return;
  }
  if (!ok) {
    console.warn("Juno ingest failed", status, body);
    return;
  }
  remoteCapturePaused = false;
  console.log("Juno capture committed", body.capture_id, payload.title, metrics || {});
}

async function syncPauseFromStatus() {
  const { apiBaseUrl, apiToken } = await JunoConfig.load();
  if (!apiToken) {
    return;
  }
  try {
    const { ok, body } = await JunoApi.getStatus(apiBaseUrl, apiToken);
    if (ok) {
      remoteCapturePaused = Boolean(body.capture_paused);
    }
  } catch {
    /* serve may be down */
  }
}

void syncPauseFromStatus();
setInterval(() => void syncPauseFromStatus(), 60_000);

/** @param {number} tabId */
async function finalizeTab(tabId) {
  const row = JunoTabs.take(tabId);
  if (!row) {
    return;
  }
  await captureTab(row.tab, row.metrics, row.highlights);
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
  if (message.type === "juno-highlight" && message.highlight) {
    JunoTabs.addHighlight(tabId, message.highlight);
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
