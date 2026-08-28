/** Build browser capture payloads for POST /ingest. */
const JunoCapture = {
  /**
   * @param {chrome.tabs.Tab} tab
   * @returns {object}
   */
  buildPayload(tab) {
    const url = tab.url || "";
    const title = tab.title || url;
    const visitedAt = new Date().toISOString();
    return {
      source_type: "browser",
      uri: url,
      title,
      text: title,
      visited_at: visitedAt,
      raw_json: {
        visited_at: visitedAt,
        uri: url,
        title,
        tab_id: tab.id,
      },
    };
  },
};
