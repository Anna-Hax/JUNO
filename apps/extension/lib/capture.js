/** Build browser capture payloads for POST /ingest. */
const JunoCapture = {
  /**
   * @param {chrome.tabs.Tab} tab
   * @param {object | null} metrics
   * @param {object[] | null} highlights
   * @returns {object}
   */
  buildPayload(tab, metrics, highlights) {
    const url = tab.url || "";
    const title = tab.title || url;
    const visitedAt = new Date().toISOString();
    const list = Array.isArray(highlights) ? highlights : [];
    const raw = {
      visited_at: visitedAt,
      uri: url,
      title,
      tab_id: tab.id,
    };
    if (metrics) {
      raw.metrics = metrics;
    }
    if (list.length) {
      raw.highlights = list;
    }
    const highlightText = list.map((item) => item.text).filter(Boolean);
    const text =
      highlightText.length > 0 ? [title, ...highlightText].join("\n\n") : title;
    return {
      source_type: "browser",
      uri: url,
      title,
      text,
      visited_at: visitedAt,
      raw_json: raw,
    };
  },
};
