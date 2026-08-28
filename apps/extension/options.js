const apiBaseUrlEl = document.getElementById("apiBaseUrl");
const apiTokenEl = document.getElementById("apiToken");
const statusEl = document.getElementById("status");
const saveBtn = document.getElementById("save");

async function load() {
  const cfg = await JunoConfig.load();
  apiBaseUrlEl.value = cfg.apiBaseUrl;
  apiTokenEl.value = cfg.apiToken;
}

saveBtn.addEventListener("click", async () => {
  await JunoConfig.save({
    apiBaseUrl: apiBaseUrlEl.value,
    apiToken: apiTokenEl.value,
  });
  statusEl.textContent = "Saved.";
});

void load();
