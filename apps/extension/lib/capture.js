/** Build browser capture payloads for POST /ingest. */
const JunoCapture = {
  /**
   * @param {chrome.tabs.Tab} tab
   * @param {object | null} metrics
   * @returns {object}
   */
  buildPayload(tab, metrics) {
    const url = tab.url || "";
    const title = tab.title || url;
    const visitedAt = new Date().toISOString();
    const raw = {
      visited_at: visitedAt,
      uri: url,
      title,
      tab_id: tab.id,
    };
    if (metrics) {
      raw.metrics = metrics;
    }
    return {
      source_type: "browser",
      uri: url,
      title,
      text: title,
      visited_at: visitedAt,
      raw_json: raw,
    };
  },
};
