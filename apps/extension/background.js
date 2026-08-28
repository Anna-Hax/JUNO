const DEFAULT_API_BASE = "http://127.0.0.1:8787";

/** @typedef {{ apiBaseUrl: string; apiToken: string }} JunoConfig */

/** @returns {Promise<JunoConfig>} */
async function loadConfig() {
  const stored = await chrome.storage.sync.get({
    apiBaseUrl: DEFAULT_API_BASE,
    apiToken: "",
  });
  return {
    apiBaseUrl: String(stored.apiBaseUrl || DEFAULT_API_BASE).replace(/\/$/, ""),
    apiToken: String(stored.apiToken || ""),
  };
}

/**
 * Spike S2: POST one page visit to loopback /ingest (Bearer token).
 * @param {chrome.tabs.Tab} tab
 */
async function captureTab(tab) {
  const url = tab.url || "";
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    return;
  }
  const { apiBaseUrl, apiToken } = await loadConfig();
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

  try {
    const resp = await fetch(`${apiBaseUrl}/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiToken}`,
      },
      body: JSON.stringify(payload),
    });
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      console.warn("Juno ingest failed", resp.status, body);
      return;
    }
    console.log("Juno capture committed", body.capture_id, title);
  } catch (err) {
    console.warn("Juno ingest error", err);
  }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete" || !tab?.url) {
    return;
  }
  void captureTab(tab);
});

console.log("Juno extension service worker loaded (Spike S2)");
