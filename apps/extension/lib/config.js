/** Shared Juno extension settings (chrome.storage.sync). */
const JunoConfig = {
  DEFAULT_API_BASE: "http://127.0.0.1:8787",
  DEFAULT_EXCLUDES: "chase.com\npaypal.com\nbankofamerica.com",

  /** @returns {Promise<{ apiBaseUrl: string; apiToken: string; excludedDomains: string[] }>} */
  async load() {
    const stored = await chrome.storage.sync.get({
      apiBaseUrl: JunoConfig.DEFAULT_API_BASE,
      apiToken: "",
      excludedDomainsText: JunoConfig.DEFAULT_EXCLUDES,
    });
    const excludedDomains = JunoExcludes.parseList(stored.excludedDomainsText);
    return {
      apiBaseUrl: String(stored.apiBaseUrl || JunoConfig.DEFAULT_API_BASE).replace(/\/$/, ""),
      apiToken: String(stored.apiToken || ""),
      excludedDomains,
    };
  },

  /** @param {{ apiBaseUrl?: string; apiToken?: string; excludedDomainsText?: string }} values */
  async save(values) {
    const patch = {};
    if (values.apiBaseUrl !== undefined) {
      patch.apiBaseUrl = values.apiBaseUrl.trim() || JunoConfig.DEFAULT_API_BASE;
    }
    if (values.apiToken !== undefined) {
      patch.apiToken = values.apiToken.trim();
    }
    if (values.excludedDomainsText !== undefined) {
      patch.excludedDomainsText = values.excludedDomainsText;
    }
    await chrome.storage.sync.set(patch);
  },
};
