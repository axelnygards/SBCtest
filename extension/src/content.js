// Isolated-world bridge: page.js <-> background service worker. Holds no data itself.
(() => {
  "use strict";
  window.addEventListener("message", (e) => {
    if (e.source !== window || !e.data || e.data.source !== "futsbc-page") return;
    chrome.runtime.sendMessage({ kind: "page", payload: e.data }).catch(() => {});
  });

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg && (msg.kind === "start-import" || msg.kind === "probe")) {
      window.postMessage({ source: "futsbc-content", type: msg.kind === "probe" ? "probe" : "import" },
        location.origin);
    }
  });
})();
