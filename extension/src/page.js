// Runs in the Web App's own page context (MAIN world).
//
// What it does:
//   1. Copies the BODY of responses the Web App itself receives for a few read-only
//      endpoints (club, transfer market search results, price limits) and hands them to
//      content.js. It never reads request headers, cookies or the session token.
//   2. On "Importera klubb" it asks the Web App's own club search to load the next page,
//      one page at a time with a pause, so the responses flow through (1). It never builds
//      its own requests to EA and never buys, lists, bids or searches the market.
(() => {
  "use strict";
  if (window.__futsbcInstalled) return;
  window.__futsbcInstalled = true;

  const SOURCE = "futsbc-page";
  const WATCH = [
    /\/ut\/game\/fc\d+\/club(\?|$)/,
    /\/ut\/game\/fc\d+\/transfermarket(\?|$)/,
    /\/ut\/game\/fc\d+\/marketdata\/item\/pricelimits(\?|$)/,
  ];
  const watched = (url) => typeof url === "string" && url.includes(".ea.com/") && WATCH.some((r) => r.test(url));

  function emit(url, body) {
    try {
      const path = new URL(url, location.href).pathname;
      window.postMessage({ source: SOURCE, type: "response", path, body }, location.origin);
    } catch (_) { /* never break the Web App */ }
  }

  // --- passive capture: fetch ---------------------------------------------------------
  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    const p = origFetch.apply(this, arguments);
    const url = typeof input === "string" ? input : input && input.url;
    if (watched(url)) {
      p.then((res) => res.clone().json().then((b) => emit(url, b)).catch(() => {})).catch(() => {});
    }
    return p;
  };

  // --- passive capture: XMLHttpRequest --------------------------------------------------
  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    if (watched(String(url))) {
      this.addEventListener("load", () => {
        try {
          if (this.status !== 200) return;
          const body = this.responseType === "json" ? this.response : JSON.parse(this.responseText);
          emit(String(url), body);
        } catch (_) { /* ignore non-JSON */ }
      });
    }
    return origOpen.apply(this, arguments);
  };

  // --- active import: drive the Web App's own club search ----------------------------
  const PAGE_SIZE = 91;          // the Web App's own page size for club searches
  const PAUSE_MS = 1500;         // steady, modest pace; not randomised to look human
  const MAX_PAGES = 70;          // circuit breaker (~6 300 cards)
  let importing = false;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function webAppApi() {
    const s = window.services;
    if (!s || !s.Club || typeof s.Club.search !== "function") return null;
    if (typeof window.UTSearchCriteriaDTO !== "function") return null;
    return s;
  }

  function searchPage(services, offset) {
    return new Promise((resolve, reject) => {
      const c = new window.UTSearchCriteriaDTO();
      c.type = (window.SearchType && window.SearchType.PLAYER) || "player";
      c.offset = offset;
      c.count = PAGE_SIZE;
      const timer = setTimeout(() => reject(new Error("timeout")), 20000);
      services.Club.search(c).observe(window, (_sender, res) => {
        clearTimeout(timer);
        if (!res || !res.success) return reject(new Error("search failed"));
        const items = (res.response && res.response.items) || [];
        resolve(items.length);
      });
    });
  }

  async function runImport() {
    if (importing) return;
    const services = webAppApi();
    if (!services) {
      status({ phase: "error", message: "unsupported" });
      return;
    }
    importing = true;
    let page = 0;
    try {
      status({ phase: "start" });
      for (; page < MAX_PAGES; page++) {
        const n = await searchPage(services, page * PAGE_SIZE);
        status({ phase: "page", page: page + 1, count: n });
        if (n < PAGE_SIZE) break;
        await sleep(PAUSE_MS);
      }
      status({ phase: "done", pages: page + 1 });
    } catch (e) {
      status({ phase: "error", message: String(e && e.message || e), pages: page });
    } finally {
      importing = false;
    }
  }

  function status(s) {
    window.postMessage({ source: SOURCE, type: "import-status", ...s }, location.origin);
  }

  window.addEventListener("message", (e) => {
    if (e.source !== window || !e.data || e.data.source !== "futsbc-content") return;
    if (e.data.type === "import") runImport();
    if (e.data.type === "probe") status({ phase: "probe", supported: !!webAppApi() });
  });
})();
