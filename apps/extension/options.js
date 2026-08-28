const apiBaseUrlEl = document.getElementById("apiBaseUrl");
const apiTokenEl = document.getElementById("apiToken");
const excludedDomainsEl = document.getElementById("excludedDomains");
const statusEl = document.getElementById("status");
const saveBtn = document.getElementById("save");

async function load() {
  const stored = await chrome.storage.sync.get({
    apiBaseUrl: JunoConfig.DEFAULT_API_BASE,
    apiToken: "",
    excludedDomainsText: JunoConfig.DEFAULT_EXCLUDES,
  });
  apiBaseUrlEl.value = stored.apiBaseUrl;
  apiTokenEl.value = stored.apiToken;
  excludedDomainsEl.value = stored.excludedDomainsText;
}

saveBtn.addEventListener("click", async () => {
  await JunoConfig.save({
    apiBaseUrl: apiBaseUrlEl.value,
    apiToken: apiTokenEl.value,
    excludedDomainsText: excludedDomainsEl.value,
  });
  statusEl.textContent = "Saved.";
});

void load();
