import { expect, test } from "vitest";

import { classify, clubItems, limitObservations, marketObservations } from "../src/parse.js";

const player = (id, def, extra = {}) => ({
  id, resourceId: def, assetId: def % 16777216, rating: 84, rareflag: 1, itemType: "player",
  preferredPosition: "ST", possiblePositions: ["ST", "CF"], nation: 18, leagueId: 13, teamid: 1,
  untradeable: false, loans: 0, sessionStuff: "x", ...extra,
});

test("classify paths", () => {
  expect(classify("/ut/game/fc27/club")).toBe("club");
  expect(classify("/ut/game/fc27/transfermarket")).toBe("market");
  expect(classify("/ut/game/fc27/marketdata/item/pricelimits")).toBe("limits");
  expect(classify("/ut/game/fc27/purchased/items")).toBe(null);
});

test("club items keep only player items and known fields", () => {
  const out = clubItems({ itemData: [player(1, 231747), { id: 2, itemType: "training" }] });
  expect(out).toHaveLength(1);
  expect(out[0]).not.toHaveProperty("sessionStuff");
  expect(out[0]).toMatchObject({ id: 1, resourceId: 231747, rareflag: 1 });
});

test("market search -> lowest buy-now per card with sample size", () => {
  const body = {
    auctionInfo: [
      { buyNowPrice: 1500, itemData: player(10, 5) },
      { buyNowPrice: 1200, itemData: player(11, 5) },
      { buyNowPrice: 900, itemData: player(12, 6) },
      { buyNowPrice: 0, itemData: player(13, 7) },          // no BIN -> ignored
      { buyNowPrice: 500, itemData: { id: 14, itemType: "staff" } },
    ],
  };
  const { prices, items } = marketObservations(body);
  expect(prices).toEqual([
    { definition_id: 5, kind: "bin_min", price: 1200, sample_size: 2 },
    { definition_id: 6, kind: "bin_min", price: 900, sample_size: 1 },
  ]);
  expect(items).toHaveLength(3);
});

test("price limits mapped through item id -> definition id", () => {
  const defOfItem = new Map([["10", 5]]);
  const out = limitObservations([{ itemId: 10, minPrice: 700, maxPrice: 10000 }, { itemId: 99, minPrice: 1 }], defOfItem);
  expect(out).toEqual([
    { definition_id: 5, kind: "limit_min", price: 700 },
    { definition_id: 5, kind: "limit_max", price: 10000 },
  ]);
});

test("empty / odd bodies never throw", () => {
  expect(clubItems(null)).toEqual([]);
  expect(marketObservations({})).toEqual({ items: [], prices: [] });
  expect(limitObservations(undefined, new Map())).toEqual([]);
});
