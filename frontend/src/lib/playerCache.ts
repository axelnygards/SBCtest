/**
 * Local player database in IndexedDB (no ~5 MB localStorage limit; quota is a share of disk).
 *
 * Stores
 *   players  static card data, rarely changes         key: card id
 *   prices   price per card, changes often            key: card id   (separate so a price
 *            update never rewrites the player record)
 *   club     the user's own cards (from the extension)
 *   meta     sync version, last sync time
 *
 * Sync is incremental: the client sends its last version and receives only changed rows
 * (GET /api/sync?since=<version>). All rows of one sync are written in ONE readwrite
 * transaction with un-awaited put() calls, which is 10-100x faster than a transaction
 * per row, and a failed sync rolls back as a whole.
 *
 * IndexedDB indexes (O(log n)) serve UI queries such as "gold players in league X".
 * Hot loops use the in-memory PlayerIndex (Map-based, O(1)) built once from the store.
 */
import { openDB, type DBSchema, type IDBPDatabase } from "idb";

export type CardKind = "normal" | "icon" | "hero";

export interface PlayerRow {
  id: string;
  baseId: number;
  name: string;
  rating: number;
  positions: string[];
  nation: number;
  league: number;
  club: number;
  rarity: string;
  kind: CardKind;
}

export interface PriceRow {
  id: string;
  price: number;
  updatedAt: number; // epoch ms
}

export interface ClubRow {
  id: string;
  untradeable: boolean;
}

export interface SyncPayload {
  version: number;          // server's monotonic change counter after this batch
  full: boolean;            // true: client was too old, replace everything
  players: PlayerRow[];
  prices: PriceRow[];
  deleted: string[];        // card ids removed from the catalogue
}

interface FutDB extends DBSchema {
  players: {
    key: string;
    value: PlayerRow;
    indexes: {
      byRating: number;
      byNation: number;
      byLeague: number;
      byClub: number;
      byLeagueRating: [number, number];
      byNationRating: [number, number];
    };
  };
  prices: { key: string; value: PriceRow };
  club: { key: string; value: ClubRow };
  meta: { key: string; value: unknown };
}

export type FutCache = IDBPDatabase<FutDB>;

export const DB_NAME = "fut-sbc-solver";
export const DB_VERSION = 1;

export function openCache(name = DB_NAME): Promise<FutCache> {
  return openDB<FutDB>(name, DB_VERSION, {
    upgrade(db, oldVersion) {
      // Versioned migrations: add a new `if (oldVersion < N)` block per schema change.
      if (oldVersion < 1) {
        const players = db.createObjectStore("players", { keyPath: "id" });
        players.createIndex("byRating", "rating");
        players.createIndex("byNation", "nation");
        players.createIndex("byLeague", "league");
        players.createIndex("byClub", "club");
        players.createIndex("byLeagueRating", ["league", "rating"]);
        players.createIndex("byNationRating", ["nation", "rating"]);
        db.createObjectStore("prices", { keyPath: "id" });
        db.createObjectStore("club", { keyPath: "id" });
        db.createObjectStore("meta");
      }
    },
  });
}

export async function getSyncVersion(db: FutCache): Promise<number> {
  return ((await db.get("meta", "syncVersion")) as number | undefined) ?? 0;
}

/** Apply one sync batch atomically. */
export async function applySync(db: FutCache, p: SyncPayload): Promise<void> {
  const tx = db.transaction(["players", "prices", "meta"], "readwrite");
  const players = tx.objectStore("players");
  const prices = tx.objectStore("prices");
  const ops: Promise<unknown>[] = [];
  if (p.full) {
    ops.push(players.clear(), prices.clear());
  }
  for (const row of p.players) ops.push(players.put(row));
  for (const row of p.prices) ops.push(prices.put(row));
  for (const id of p.deleted) ops.push(players.delete(id), prices.delete(id));
  ops.push(tx.objectStore("meta").put(p.version, "syncVersion"));
  ops.push(tx.objectStore("meta").put(Date.now(), "lastSyncAt"));
  await Promise.all([...ops, tx.done]);
}

/** Pull changes from the backend until up to date. */
export async function syncFromServer(
  db: FutCache,
  baseUrl: string,
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<{ version: number; batches: number }> {
  let batches = 0;
  for (;;) {
    const since = await getSyncVersion(db);
    const res = await fetchImpl(`${baseUrl}/api/sync?since=${since}`, { signal });
    if (!res.ok) throw new Error(`sync failed: HTTP ${res.status}`);
    const payload = (await res.json()) as SyncPayload & { hasMore?: boolean };
    await applySync(db, payload);
    batches++;
    if (!payload.hasMore) return { version: payload.version, batches };
  }
}

export async function replaceClub(db: FutCache, rows: ClubRow[]): Promise<void> {
  const tx = db.transaction("club", "readwrite");
  await Promise.all([tx.store.clear(), ...rows.map((r) => tx.store.put(r)), tx.done]);
}

/** Indexed range query, e.g. league 13 rated 82-84. */
export function playersInLeague(db: FutCache, league: number, minRating = 0, maxRating = 99) {
  return db.getAllFromIndex(
    "players",
    "byLeagueRating",
    IDBKeyRange.bound([league, minRating], [league, maxRating]),
  );
}

/** Ask the browser not to evict our data under storage pressure. */
export async function requestPersistence(): Promise<boolean> {
  return (await navigator.storage?.persist?.()) ?? false;
}

export async function storageEstimate(): Promise<{ usage: number; quota: number } | null> {
  const e = await navigator.storage?.estimate?.();
  return e ? { usage: e.usage ?? 0, quota: e.quota ?? 0 } : null;
}

// ---------------------------------------------------------------------------------------
// In-memory hash index for hot loops: every lookup is a Map access, never filter()/find().
// ---------------------------------------------------------------------------------------

export interface IndexedCard extends PlayerRow {
  price: number | null;
  owned: boolean;
  untradeable: boolean;
}

function push<K, V>(m: Map<K, V[]>, k: K, v: V) {
  const arr = m.get(k);
  if (arr) arr.push(v);
  else m.set(k, [v]);
}

export class PlayerIndex {
  readonly byId = new Map<string, IndexedCard>();
  readonly byNation = new Map<number, IndexedCard[]>();
  readonly byLeague = new Map<number, IndexedCard[]>();
  readonly byClub = new Map<number, IndexedCard[]>();
  readonly byRating = new Map<number, IndexedCard[]>();
  readonly byLeagueRating = new Map<string, IndexedCard[]>(); // key `${league}:${rating}`

  constructor(cards: Iterable<IndexedCard>) {
    for (const c of cards) {
      this.byId.set(c.id, c);
      push(this.byNation, c.nation, c);
      push(this.byLeague, c.league, c);
      push(this.byClub, c.club, c);
      push(this.byRating, c.rating, c);
      push(this.byLeagueRating, `${c.league}:${c.rating}`, c);
    }
    // cheapest first inside every bucket, so "cheapest N" is a slice
    const cost = (c: IndexedCard) => (c.owned ? 0 : (c.price ?? Number.POSITIVE_INFINITY));
    for (const m of [this.byNation, this.byLeague, this.byClub, this.byRating, this.byLeagueRating])
      for (const arr of m.values()) arr.sort((a, b) => cost(a) - cost(b));
  }

  get size() {
    return this.byId.size;
  }

  static async load(db: FutCache): Promise<PlayerIndex> {
    const tx = db.transaction(["players", "prices", "club"]);
    const [players, prices, club] = await Promise.all([
      tx.objectStore("players").getAll(),
      tx.objectStore("prices").getAll(),
      tx.objectStore("club").getAll(),
      tx.done,
    ]);
    const priceById = new Map(prices.map((p) => [p.id, p.price]));
    const clubById = new Map(club.map((c) => [c.id, c]));
    return new PlayerIndex(
      players.map((p) => ({
        ...p,
        price: priceById.get(p.id) ?? null,
        owned: clubById.has(p.id),
        untradeable: clubById.get(p.id)?.untradeable ?? false,
      })),
    );
  }
}
