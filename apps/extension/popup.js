const statusEl = document.getElementById("status");
const openOptions = document.getElementById("openOptions");

async function refresh() {
  statusEl.textContent = "Checking…";
  const { apiBaseUrl, apiToken } = await JunoConfig.load();
  if (!apiToken) {
    statusEl.textContent = "Set API token in Options.";
    return;
  }
  try {
    const { ok, status, body } = await JunoApi.getStatus(apiBaseUrl, apiToken);
    if (!ok) {
      statusEl.textContent = `API error ${status}. Is juno serve running?`;
      return;
    }
    const paused = body.capture_paused ? "paused" : "running";
    statusEl.textContent = `Connected — capture ${paused}.`;
  } catch {
    statusEl.textContent = "Cannot reach Juno API. Start juno serve.";
  }
}

openOptions.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

void refresh();
