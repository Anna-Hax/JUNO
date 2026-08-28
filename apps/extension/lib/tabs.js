/** Tab session state for deferred browser capture with metrics. */
const JunoTabs = {
  /** @type {Map<number, { tab: chrome.tabs.Tab; metrics: object | null }>} */
  sessions: new Map(),

  /** @param {chrome.tabs.Tab} tab */
  track(tab) {
    if (!tab.id || !tab.url?.startsWith("http")) {
      return;
    }
    this.sessions.set(tab.id, { tab, metrics: null });
  },

  /** @param {number} tabId @param {object} metrics */
  setMetrics(tabId, metrics) {
    const row = this.sessions.get(tabId);
    if (row) {
      row.metrics = metrics;
    }
  },

  /** @param {number} tabId */
  take(tabId) {
    const row = this.sessions.get(tabId);
    this.sessions.delete(tabId);
    return row;
  },
};
