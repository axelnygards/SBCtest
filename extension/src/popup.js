const $ = (id) => document.getElementById(id);
const WEB_APP = /^https:\/\/www\.ea\.com\/.*ea-sports-fc\/ultimate-team\/web-app\//;

const MESSAGES = {
  start: "Startar import…",
  importing: (s) => `Importerar… ${s.collected ?? 0} spelare hittills`,
  page: (s) => `Läser sida ${s.page}…`,
  done: (s) => `Klart: ${s.imported} spelare importerade.`,
  error: (s) => s.message === "unsupported"
    ? "Web App-versionen stöds inte för automatisk import. Bläddra igenom klubben manuellt – tillägget läser med medan du bläddrar."
    : `Fel: ${s.message}`,
};

async function load() {
  const s = await chrome.storage.local.get(["accepted", "token", "platform", "sharePrices", "backendUrl", "shared"]);
  $("accept").checked = !!s.accepted;
  $("main").hidden = !s.accepted;
  $("token").value = s.token || "";
  $("platform").value = s.platform || "console";
  $("sharePrices").checked = s.sharePrices !== false;
  $("backendUrl").value = s.backendUrl || "http://localhost:8000";
  renderStatus();
}

async function renderStatus() {
  const { status = {} } = await chrome.storage.session.get("status");
  const { shared = 0 } = await chrome.storage.local.get("shared");
  const f = MESSAGES[status.phase];
  const line = typeof f === "function" ? f(status) : f || "Öppna din klubb i EA FC Web App och tryck Importera klubb.";
  $("status").textContent = `${line}${shared ? ` · ${shared} priser delade` : ""}`;
}

$("accept").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ accepted: e.target.checked });
  $("main").hidden = !e.target.checked;
});

$("save").addEventListener("click", async () => {
  const backendUrl = $("backendUrl").value.trim().replace(/\/$/, "");
  if (!/^https?:\/\/localhost(:\d+)?$/.test(backendUrl)) {
    // only ask for access to the one server the user configured
    const ok = await chrome.permissions.request({ origins: [`${backendUrl}/*`] });
    if (!ok) return ($("status").textContent = "Behörighet till servern nekades.");
  }
  await chrome.storage.local.set({
    token: $("token").value.trim(),
    platform: $("platform").value,
    sharePrices: $("sharePrices").checked,
    backendUrl,
  });
  $("status").textContent = "Sparat.";
});

$("import").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !WEB_APP.test(tab.url || "")) {
    $("status").textContent = "Öppna EA FC Web App i den här fliken och logga in först.";
    return;
  }
  $("import").disabled = true;
  const r = await chrome.runtime.sendMessage({ kind: "popup-import", tabId: tab.id });
  if (!r || !r.ok) $("status").textContent = `Fel: ${r && r.error}`;
  setTimeout(() => ($("import").disabled = false), 3000);
});

chrome.storage.session.onChanged.addListener(renderStatus);
load();
