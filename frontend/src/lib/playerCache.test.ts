import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";

import { fetchWithTimeout, TimeoutError } from "./guard";
import {
  applySync,
  getSyncVersion,
  openCache,
  PlayerIndex,
  playersInLeague,
  replaceClub,
  syncFromServer,
  type PlayerRow,
  type SyncPayload,
} from "./playerCache";

function players(n: number): PlayerRow[] {
  return Array.from({ length: n }, (_, i) => ({
    id: String(i),
    baseId: i,
    name: `Player ${i}`,
    rating: 50 + (i % 45),
    positions: ["ST"],
    nation: i % 60,
    league: i % 40,
    club: i % 600,
    rarity: i % 2 ? "rare" : "common",
    kind: "normal" as const,
  }));
}

const full = (n: number): SyncPayload => ({
  version: 1,
  full: true,
  players: players(n),
  prices: players(n).map((p) => ({ id: p.id, price: 200 + p.rating * 10, updatedAt: 0 })),
  deleted: [],
});

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory(); // fresh database per test
});

test("full sync of 20k players in one transaction, then delta", async () => {
  const db = await openCache();
  const t = performance.now();
  await applySync(db, full(20_000));
  const ms = performance.now() - t;
  expect(await db.count("players")).toBe(20_000);
  expect(await getSyncVersion(db)).toBe(1);
  console.info(`full sync 20k rows: ${ms.toFixed(0)} ms (fake-indexeddb, real browsers are faster)`);

  await applySync(db, {
    version: 2,
    full: false,
    players: [],
    prices: [{ id: "5", price: 999, updatedAt: 1 }],
    deleted: ["6"],
  });
  expect((await db.get("prices", "5"))?.price).toBe(999);
  expect(await db.get("players", "6")).toBeUndefined();
  expect(await db.count("players")).toBe(19_999);
  expect(await getSyncVersion(db)).toBe(2);
});

test("compound index range query", async () => {
  const db = await openCache();
  await applySync(db, full(5_000));
  const rows = await playersInLeague(db, 3, 80, 84);
  expect(rows.length).toBeGreaterThan(0);
  expect(rows.every((r) => r.league === 3 && r.rating >= 80 && r.rating <= 84)).toBe(true);
});

test("PlayerIndex gives O(1) buckets, cheapest first, with prices and club merged", async () => {
  const db = await openCache();
  await applySync(db, full(3_000));
  await replaceClub(db, [{ id: "10", untradeable: true }]);
  const ix = await PlayerIndex.load(db);
  expect(ix.size).toBe(3_000);
  expect(ix.byId.get("10")?.owned).toBe(true);
  const league7 = ix.byLeague.get(7)!;
  expect(league7.every((c) => c.league === 7)).toBe(true);
  const costs = league7.map((c) => (c.owned ? 0 : c.price!));
  expect(costs).toEqual([...costs].sort((a, b) => a - b));
  expect(ix.byLeagueRating.get("7:57")?.every((c) => c.rating === 57)).toBe(true);
});

test("syncFromServer follows hasMore and a failed batch leaves the old version", async () => {
  const db = await openCache();
  const pages = [
    { ...full(100), version: 1, hasMore: true },
    { version: 2, full: false, players: players(1), prices: [], deleted: [], hasMore: false },
  ];
  let call = 0;
  const fakeFetch = (async () => new Response(JSON.stringify(pages[call++]))) as typeof fetch;
  const res = await syncFromServer(db, "http://api", fakeFetch);
  expect(res).toEqual({ version: 2, batches: 2 });

  const failing = (async () => new Response("", { status: 500 })) as typeof fetch;
  await expect(syncFromServer(db, "http://api", failing)).rejects.toThrow("HTTP 500");
  expect(await getSyncVersion(db)).toBe(2);
});

test("fetchWithTimeout aborts a hanging request", async () => {
  const hanging = ((_: string, init: RequestInit) =>
    new Promise((_, reject) =>
      init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))),
    )) as unknown as typeof fetch;
  await expect(fetchWithTimeout("http://x", {}, 50, hanging)).rejects.toBeInstanceOf(TimeoutError);
});
