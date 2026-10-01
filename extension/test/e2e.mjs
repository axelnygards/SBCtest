// End-to-end: real Chromium + this extension + a mock of EA's Web App + the real backend.
//
//   node test/e2e.mjs <path-to-seeded-sqlite-db>
//
// The mock Web App mimics the parts page.js relies on (window.services.Club.search,
// UTSearchCriteriaDTO) and serves club / market JSON from a fake utas host. The test checks
// that the extension imports the whole club, shares observed prices, and makes NO requests to
// EA on its own (every utas request must come from the mock app's own code).
import { spawn } from "node:child_process";
import { copyFileSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const extDir = resolve(here, "..");
const backendDir = resolve(here, "../../backend");
const seedDb = process.argv[2];
const API = "http://localhost:8765";
const UTAS = "https://utas.mob.v5.prd.futc-ext.gcp.ea.com";
const WEB_APP = "https://www.ea.com/ea-sports-fc/ultimate-team/web-app/";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitFor(fn, what, ms = 30000) {
  const end = Date.now() + ms;
  for (;;) {
    const v = await fn().catch(() => undefined);
    if (v) return v;
    if (Date.now() > end) throw new Error(`timeout waiting for ${what}`);
    await sleep(250);
  }
}

// --- backend ------------------------------------------------------------------------------
const tmp = mkdtempSync(join(tmpdir(), "futsbc-e2e-"));
copyFileSync(seedDb, join(tmp, "db.sqlite"));
const backend = spawn(resolve(backendDir, "../.venv/bin/python"),
  ["-m", "uvicorn", "app.main:app", "--port", "8765"],
  { cwd: backendDir, env: { ...process.env, DATABASE_URL: `sqlite:///${tmp}/db.sqlite`, DISABLE_SCHEDULER: "1" }, stdio: "inherit" });
process.on("exit", () => backend.kill());
await waitFor(() => fetch(`${API}/api/health`).then((r) => r.ok), "backend");
const { token } = await (await fetch(`${API}/api/users`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })).json();
const auth = { Authorization: `Bearer ${token}` };

// club fixture: 200 real FC 27 base cards from the seeded DB (via sync)
const sync = await (await fetch(`${API}/api/sync?since=0&limit=20000`)).json();
const clubCards = sync.players.filter((p) => p.rating >= 75).slice(0, 200);
const clubItems = clubCards.map((p, i) => ({
  id: 9000000 + i, resourceId: Number(p.id), assetId: p.baseId, rating: p.rating,
  rareflag: i % 2, preferredPosition: p.positions[0], possiblePositions: p.positions,
  nation: p.nation, leagueId: p.league, teamid: p.club, untradeable: i % 3 === 0, loans: 0,
  itemType: "player",
}));
const marketCard = sync.players.find((p) => p.rating === 84);

// --- browser ------------------------------------------------------------------------------
const ctx = await chromium.launchPersistentContext(mkdtempSync(join(tmpdir(), "futsbc-prof-")), {
  executablePath: "/opt/pw-browsers/chromium",
  headless: true,
  args: [`--disable-extensions-except=${extDir}`, `--load-extension=${extDir}`],
});
const utasRequests = [];
await ctx.route(`${UTAS}/**`, async (route) => {
  const req = route.request();
  const url = new URL(req.url());
  utasRequests.push(`${req.method()} ${url.pathname}`);
  if (url.pathname === "/ut/game/fc27/club") {
    const { start, count } = JSON.parse(req.postData() || "{}");
    return route.fulfill({ json: { itemData: clubItems.slice(start, start + count) },
      headers: { "Access-Control-Allow-Origin": "*" } });
  }
  if (url.pathname === "/ut/game/fc27/transfermarket") {
    const item = { id: 1, resourceId: Number(marketCard.id), assetId: marketCard.baseId,
      rating: 84, rareflag: 1, itemType: "player", preferredPosition: "ST" };
    return route.fulfill({ json: { auctionInfo: [
      { buyNowPrice: 2400, itemData: { ...item, id: 11 } },
      { buyNowPrice: 2100, itemData: { ...item, id: 12 } },
    ] }, headers: { "Access-Control-Allow-Origin": "*" } });
  }
  return route.fulfill({ status: 404 });
});
await ctx.route("https://www.ea.com/**", (route) => route.fulfill({
  contentType: "text/html",
  body: `<!doctype html><title>Mock Web App</title><script>
    // minimal imitation of the Web App globals page.js uses
    window.SearchType = { PLAYER: "player" };
    window.UTSearchCriteriaDTO = function () { this.type = ""; this.offset = 0; this.count = 21; };
    window.services = { Club: { search(c) {
      return { observe(scope, cb) {
        const x = new XMLHttpRequest();
        x.open("POST", "${UTAS}/ut/game/fc27/club");
        x.onload = () => { const b = JSON.parse(x.responseText);
          cb(null, { success: true, response: { items: b.itemData } }); };
        x.send(JSON.stringify({ type: c.type, start: c.offset, count: c.count }));
      } };
    } } };
  </script>`,
}));

const page = await ctx.newPage();
await page.goto(WEB_APP);
const sw = ctx.serviceWorkers()[0] || await ctx.waitForEvent("serviceworker");
const extId = new URL(sw.url()).host;
await sw.evaluate(({ token, api }) => chrome.storage.local.set(
  { accepted: true, token, backendUrl: api, platform: "console", sharePrices: true }), { token, api: API });

// 1) club import, started from the popup like a user would
const popup = await ctx.newPage();
await popup.goto(`chrome-extension://${extId}/src/popup.html`);
const tabId = await sw.evaluate(async () => {
  for (const t of await chrome.tabs.query({})) {
    try { await chrome.tabs.sendMessage(t.id, { kind: "probe" }); return t.id; } catch (_) {}
  }
  return null;
});
assert.ok(tabId, "web app tab with content script found");
const r = await popup.evaluate((tabId) => chrome.runtime.sendMessage({ kind: "popup-import", tabId }), tabId);
assert.equal(r.ok, true);
const status = await waitFor(async () => {
  const { status } = await sw.evaluate(() => chrome.storage.session.get("status"));
  if (status?.phase === "error") throw new Error(status.message);
  return status?.phase === "done" ? status : null;
}, "import done", 60000);
assert.equal(status.imported, 200);
const me = await (await fetch(`${API}/api/me`, { headers: auth })).json();
assert.equal(me.club_size, 200);
console.log(`club import ok: ${me.club_size} players in ${utasRequests.length} club pages`);

// 2) the user searches the market in the Web App -> price shared
await page.evaluate((u) => fetch(`${u}/ut/game/fc27/transfermarket?num=21&start=0&type=player`), UTAS);
const price = await waitFor(async () => {
  const s = await (await fetch(`${API}/api/sync?since=0&limit=20000`)).json();
  const p = s.prices.find((x) => x.id === marketCard.id && x.source === "live");
  return p;
}, "live price");
assert.equal(price.price, 2100);
console.log(`price sharing ok: ${marketCard.name} live ${price.price}`);

// 3) the extension made no EA requests of its own
assert.deepEqual(utasRequests, [
  "POST /ut/game/fc27/club", "POST /ut/game/fc27/club", "POST /ut/game/fc27/club",
  "GET /ut/game/fc27/transfermarket",
]);
console.log("no extra EA requests: ok");

// 4) solve with the imported club
const sol = (await (await fetch(`${API}/api/solve`, { method: "POST",
  headers: { ...auth, "Content-Type": "application/json" },
  body: JSON.stringify({ requirements: [{ type: "team_rating", value: 80 }], time_limit_s: 15 }) })).json())[0];
assert.equal(sol.status, "OPTIMAL");
console.log(`solve ok: rating ${sol.team_rating}, ${sol.slots.filter((s) => s.owned).length}/11 from club, ${sol.total_cost} coins to buy`);

await ctx.close();
backend.kill();
console.log("E2E PASSED");
process.exit(0);
