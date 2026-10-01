// The user's own prices and excluded cards. Kept in this browser (localStorage) and sent with
// every solve, so they work without an account.
import { useCallback, useState } from "react";

export interface PricedCard { price: number; name: string; rating: number }
export interface ExcludedCard { name: string; rating: number; owned: boolean }

export interface OwnPrices {
  enabled: boolean;                       // use the prices (exclusions always apply)
  share: boolean;                         // also report them anonymously, for everyone
  reported: Record<string, number>;       // rating -> price last reported (avoid repeats)
  ratings: Record<string, number>;        // rating -> coins, replaces estimates
  cards: Record<string, PricedCard>;      // definition_id -> coins, replaces any price
  excluded: Record<string, ExcludedCard>; // card_id -> never use this card
}

const KEY = "futsbc.ownPrices.v1";
const EMPTY: OwnPrices = { enabled: true, share: true, reported: {}, ratings: {}, cards: {}, excluded: {} };

function load(): OwnPrices {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY;
  } catch {
    return EMPTY;
  }
}

function save(v: OwnPrices) {
  try {
    localStorage.setItem(KEY, JSON.stringify(v));
  } catch {
    /* private mode: kept for this session only */
  }
}

export function useOwnPrices() {
  const [value, setValue] = useState(load);
  const update = useCallback((f: (v: OwnPrices) => OwnPrices) => setValue((prev) => {
    const next = f(prev);
    save(next);
    return next;
  }), []);
  return [value, update] as const;
}

/** The request body part: undefined when there is nothing to send. */
export function requestPrices(v: OwnPrices): { ratings: Record<string, number>; cards: Record<string, number> } | undefined {
  if (!v.enabled) return undefined;
  const cards = Object.fromEntries(Object.entries(v.cards).map(([id, c]) => [id, c.price]));
  return Object.keys(v.ratings).length || Object.keys(cards).length ? { ratings: v.ratings, cards } : undefined;
}

/** Rating prices not yet reported (or changed since). */
export function unreportedRatings(v: OwnPrices): Record<string, number> {
  if (!v.share || !v.enabled) return {};
  return Object.fromEntries(Object.entries(v.ratings).filter(([r, p]) => v.reported[r] !== p));
}

const PLATFORM_KEY = "futsbc.platform";
export type Platform = "console" | "pc";

export function usePlatform() {
  const [p, setP] = useState<Platform>(() => {
    try {
      return localStorage.getItem(PLATFORM_KEY) === "pc" ? "pc" : "console";
    } catch {
      return "console";
    }
  });
  const set = useCallback((next: Platform) => {
    setP(next);
    try {
      localStorage.setItem(PLATFORM_KEY, next);
    } catch {
      /* session only */
    }
  }, []);
  return [p, set] as const;
}

export const excludedIds = (v: OwnPrices) => Object.keys(v.excluded);
export const ownCount = (v: OwnPrices) => Object.keys(v.ratings).length + Object.keys(v.cards).length;

/** Fingerprint of everything that changes a solve, to tell when the shown squad is outdated. */
export const pricesKey = (v: OwnPrices) => JSON.stringify([requestPrices(v) ?? null, excludedIds(v).sort()]);

export function setIn<T>(rec: Record<string, T>, key: string, val: T | null): Record<string, T> {
  const next = { ...rec };
  if (val == null) delete next[key];
  else next[key] = val;
  return next;
}
