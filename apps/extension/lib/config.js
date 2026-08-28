/** Shared Juno extension settings (chrome.storage.sync). */
const JunoConfig = {
  DEFAULT_API_BASE: "http://127.0.0.1:8787",

  /** @returns {Promise<{ apiBaseUrl: string; apiToken: string }>} */
  async load() {
    const stored = await chrome.storage.sync.get({
      apiBaseUrl: JunoConfig.DEFAULT_API_BASE,
      apiToken: "",
    });
    return {
      apiBaseUrl: String(stored.apiBaseUrl || JunoConfig.DEFAULT_API_BASE).replace(/\/$/, ""),
      apiToken: String(stored.apiToken || ""),
    };
  },

  /** @param {{ apiBaseUrl?: string; apiToken?: string }} values */
  async save(values) {
    const patch = {};
    if (values.apiBaseUrl !== undefined) {
      patch.apiBaseUrl = values.apiBaseUrl.trim() || JunoConfig.DEFAULT_API_BASE;
    }
    if (values.apiToken !== undefined) {
      patch.apiToken = values.apiToken.trim();
    }
    await chrome.storage.sync.set(patch);
  },
};
