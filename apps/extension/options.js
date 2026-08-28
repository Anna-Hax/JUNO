const DEFAULT_API_BASE = "http://127.0.0.1:8787";

const apiBaseUrlEl = document.getElementById("apiBaseUrl");
const apiTokenEl = document.getElementById("apiToken");
const statusEl = document.getElementById("status");
const saveBtn = document.getElementById("save");

async function load() {
  const stored = await chrome.storage.sync.get({
    apiBaseUrl: DEFAULT_API_BASE,
    apiToken: "",
  });
  apiBaseUrlEl.value = stored.apiBaseUrl;
  apiTokenEl.value = stored.apiToken;
}

saveBtn.addEventListener("click", async () => {
  await chrome.storage.sync.set({
    apiBaseUrl: apiBaseUrlEl.value.trim() || DEFAULT_API_BASE,
    apiToken: apiTokenEl.value.trim(),
  });
  statusEl.textContent = "Saved.";
});

void load();
