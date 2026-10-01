// Service worker: receives captured Web App responses from content.js and forwards the
// relevant parts to the FUT SBC Solver backend (only that backend, only with the pairing token).
import { classify, clubItems, limitObservations, marketObservations } from "./parse.js";

const DEFAULTS = { backendUrl: "http://localhost:8000", token: "", platform: "console", sharePrices: true };
const CHUNK = 5000;

async function settings() {
  return { ...DEFAULTS, ...(await chrome.storage.local.get(Object.keys(DEFAULTS))) };
}

async function setStatus(patch) {
  const { status = {} } = await chrome.storage.session.get("status");
  await chrome.storage.session.set({ status: { ...status, ...patch, at: Date.now() } });
}

async function post(path, body) {
  const s = await settings();
  if (!s.token) throw new Error("Inte kopplad – klistra in koden från appen.");
  const res = await fetch(`${s.backendUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${s.token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Servern svarade ${res.status}`);
  return res.json();
}

// item id -> definition id, needed to map EA's price limits (keyed by item id)
async function rememberItems(items) {
  const { defOfItem = {} } = await chrome.storage.local.get("defOfItem");
  for (const it of items) if (it.id) defOfItem[it.id] = it.resourceId || it.definitionId;
  await chrome.storage.local.set({ defOfItem });
}

async function onClubPage(body) {
  const items = clubItems(body);
  await rememberItems(items);
  const { importing, buffer = [] } = await chrome.storage.session.get(["importing", "buffer"]);
  if (importing) {
    await chrome.storage.session.set({ buffer: buffer.concat(items) });
    await setStatus({ phase: "importing", collected: buffer.length + items.length });
  } else if (items.length) {
    // the user is just browsing their club: add what they see, replace nothing
    await post("/api/ext/club", { items, replace: false });
  }
}

async function finishImport() {
  const { buffer = [] } = await chrome.storage.session.get("buffer");
  await chrome.storage.session.set({ importing: false, buffer: [] });
  const unique = [...new Map(buffer.map((it) => [it.id, it])).values()];
  let sent = 0;
  for (let i = 0; i < unique.length; i += CHUNK) {
    const r = await post("/api/ext/club", { items: unique.slice(i, i + CHUNK), replace: i === 0 });
    sent += r.imported;
  }
  await setStatus({ phase: "done", imported: sent });
}

async function onMarket(body) {
  const s = await settings();
  if (!s.sharePrices) return;
  const { items, prices } = marketObservations(body);
  if (prices.length) {
    const r = await post("/api/ext/observations", { platform: s.platform, items, prices });
    const { shared = 0 } = await chrome.storage.local.get("shared");
    await chrome.storage.local.set({ shared: shared + r.accepted });
  }
}

async function onLimits(body) {
  const s = await settings();
  if (!s.sharePrices) return;
  const { defOfItem = {} } = await chrome.storage.local.get("defOfItem");
  const prices = limitObservations(body, new Map(Object.entries(defOfItem)));
  if (prices.length) await post("/api/ext/observations", { platform: s.platform, prices });
}

async function handlePage(p) {
  if (p.type === "import-status") {
    if (p.phase === "done") return finishImport();
    if (p.phase === "error") {
      await chrome.storage.session.set({ importing: false, buffer: [] });
      return setStatus({ phase: "error", message: p.message });
    }
    if (p.phase === "probe") return setStatus({ supported: p.supported });
    return setStatus({ phase: p.phase, page: p.page });
  }
  if (p.type !== "response") return;
  const kind = classify(p.path);
  if (kind === "club") return onClubPage(p.body);
  if (kind === "market") return onMarket(p.body);
  if (kind === "limits") return onLimits(p.body);
}

// Page events are processed strictly in arrival order: the import buffer is read-modify-write
// state, and "done" must never be handled before the last club page has been stored.
let queue = Promise.resolve();

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (msg.kind === "page") {
    queue = queue
      .then(() => handlePage(msg.payload))
      .catch((e) => setStatus({ phase: "error", message: String(e.message || e) }));
    return false;
  }
  if (msg.kind === "popup-import") {
    (async () => {
      await chrome.storage.session.set({ importing: true, buffer: [] });
      await setStatus({ phase: "start", message: "" });
      await chrome.tabs.sendMessage(msg.tabId, { kind: "start-import" });
      reply({ ok: true });
    })().catch((e) => reply({ ok: false, error: String(e.message || e) }));
    return true;
  }
  return false;
});
