importScripts("lib/config.js", "lib/api.js");

/**
 * Spike S2+: POST page visit to loopback /ingest (Bearer token).
 * @param {chrome.tabs.Tab} tab
 */
async function captureTab(tab) {
  const url = tab.url || "";
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    return;
  }
  const { apiBaseUrl, apiToken } = await JunoConfig.load();
  if (!apiToken) {
    console.warn("Juno: set JUNO API token in extension options");
    return;
  }

  const title = tab.title || url;
  const payload = {
    source_type: "browser",
    uri: url,
    title,
    text: title,
  };

  const { ok, status, body } = await JunoApi.postIngest(apiBaseUrl, apiToken, payload);
  if (!ok) {
    console.warn("Juno ingest failed", status, body);
    return;
  }
  console.log("Juno capture committed", body.capture_id, title);
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete" || !tab?.url) {
    return;
  }
  void captureTab(tab);
});

console.log("Juno extension service worker loaded");
