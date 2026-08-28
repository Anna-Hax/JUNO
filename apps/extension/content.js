/** Page engagement signals for Juno browser capture (#47). */
(() => {
  let activeMs = 0;
  let lastTick = Date.now();
  let visible = !document.hidden;
  let maxScroll = 0;

  function tick() {
    const now = Date.now();
    if (visible) {
      activeMs += now - lastTick;
    }
    lastTick = now;
  }

  function scrollDepth() {
    const root = document.documentElement;
    const scrollTop = window.scrollY || root.scrollTop || 0;
    const viewport = window.innerHeight || root.clientHeight || 1;
    const total = Math.max(root.scrollHeight - viewport, 1);
    return Math.min(1, scrollTop / total);
  }

  function snapshot() {
    tick();
    return {
      active_time_ms: Math.round(activeMs),
      scroll_depth: Math.round(maxScroll * 1000) / 1000,
    };
  }

  function report(finalize) {
    const metrics = snapshot();
    chrome.runtime
      .sendMessage({ type: finalize ? "juno-page-done" : "juno-metrics", metrics })
      .catch(() => {});
  }

  document.addEventListener("visibilitychange", () => {
    tick();
    visible = !document.hidden;
    if (!visible) {
      report(true);
    }
  });

  window.addEventListener(
    "scroll",
    () => {
      maxScroll = Math.max(maxScroll, scrollDepth());
    },
    { passive: true }
  );

  window.addEventListener("pagehide", () => report(true));

  setInterval(() => report(false), 5000);

  document.addEventListener("mouseup", () => {
    const selection = window.getSelection();
    const text = selection?.toString().trim();
    if (!text || text.length < 3) {
      return;
    }
    chrome.runtime
      .sendMessage({
        type: "juno-highlight",
        highlight: {
          text: text.slice(0, 2000),
          at: new Date().toISOString(),
        },
      })
      .catch(() => {});
  });
})();
