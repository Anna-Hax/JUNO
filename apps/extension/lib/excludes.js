/** Domain / URL exclude matching for browser capture (#49). */
const JunoExcludes = {
  /**
   * @param {string} text
   * @returns {string[]}
   */
  parseList(text) {
    return String(text || "")
      .split(/[\n,]+/)
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean);
  },

  /**
   * @param {string} url
   * @param {string[]} patterns
   */
  isExcluded(url, patterns) {
    if (!patterns?.length) {
      return false;
    }
    let host = "";
    try {
      host = new URL(url).hostname.toLowerCase();
    } catch {
      return false;
    }
    return patterns.some((pattern) => {
      const p = pattern.toLowerCase();
      if (!p) {
        return false;
      }
      if (p.startsWith("http://") || p.startsWith("https://")) {
        try {
          return new URL(url).href.startsWith(p);
        } catch {
          return false;
        }
      }
      return host === p || host.endsWith(`.${p}`);
    });
  },
};
