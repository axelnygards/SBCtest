// Pure functions turning Web App response bodies into what our backend accepts.
// Tested in test/parse.test.js. No chrome.* or network access here.

export function classify(path) {
  if (/\/club$/.test(path)) return "club";
  if (/\/transfermarket$/.test(path)) return "market";
  if (/\/marketdata\/item\/pricelimits$/.test(path)) return "limits";
  return null;
}

const isPlayer = (it) => it && (it.itemType === undefined || it.itemType === "player");

/** Club page -> itemData objects (players only), trimmed to the fields the backend reads. */
export function clubItems(body) {
  const items = (body && body.itemData) || [];
  return items.filter(isPlayer).map(trimItem);
}

const ITEM_FIELDS = ["id", "resourceId", "definitionId", "assetId", "resourceBaseId", "rating",
  "rareflag", "preferredPosition", "possiblePositions", "nation", "leagueId", "teamid",
  "untradeable", "loans", "itemType"];

export function trimItem(it) {
  const out = {};
  for (const k of ITEM_FIELDS) if (it[k] !== undefined) out[k] = it[k];
  return out;
}

/**
 * Transfer market search results -> lowest buy-now per card + the items (to learn rarity).
 * Only real listings the user saw; nothing is inferred.
 */
export function marketObservations(body) {
  const auctions = (body && body.auctionInfo) || [];
  const byDef = new Map();
  const items = [];
  for (const a of auctions) {
    const it = a && a.itemData;
    if (!isPlayer(it) || !a.buyNowPrice) continue;
    const def = it.resourceId || it.definitionId;
    if (!def) continue;
    items.push(trimItem(it));
    const cur = byDef.get(def);
    if (!cur) byDef.set(def, { definition_id: def, kind: "bin_min", price: a.buyNowPrice, sample_size: 1 });
    else {
      cur.price = Math.min(cur.price, a.buyNowPrice);
      cur.sample_size += 1;
    }
  }
  return { items, prices: [...byDef.values()] };
}

/** EA price limits (keyed by item id) -> observations, using item id -> definition id map. */
export function limitObservations(body, defOfItem) {
  const rows = Array.isArray(body) ? body : (body && body.itemPricingLimits) || [];
  const out = [];
  for (const r of rows) {
    const def = defOfItem.get(r.itemId) ?? defOfItem.get(String(r.itemId));
    if (!def) continue;
    if (r.minPrice) out.push({ definition_id: def, kind: "limit_min", price: r.minPrice });
    if (r.maxPrice) out.push({ definition_id: def, kind: "limit_max", price: r.maxPrice });
  }
  return out;
}
