/// <reference lib="webworker" />
/**
 * Runs the IndexedDB sync off the main thread (JSON parsing of a full ~17k-player sync and
 * the bulk write would otherwise freeze the UI on a phone). Started via runWorker() with a
 * timeout, e.g.:
 *   runWorker(() => new Worker(new URL("./sync.worker.ts", import.meta.url), { type: "module" }),
 *             { baseUrl }, 60_000)
 */
import { openCache, syncFromServer } from "./playerCache";

self.onmessage = async (e: MessageEvent<{ baseUrl: string }>) => {
  try {
    const db = await openCache();
    const result = await syncFromServer(db, e.data.baseUrl);
    db.close();
    self.postMessage({ ok: true, result });
  } catch (err) {
    self.postMessage({ ok: false, error: String(err) });
  }
};
