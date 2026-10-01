import { fetchWithTimeout } from "./guard";

export type ReqType = "team_rating" | "team_chem" | "player_chem" | "count" | "same" | "distinct";
export type Op = "min" | "max" | "exact";

export interface Requirement {
  type: ReqType;
  value: number;
  op: Op;
  attr?: string | null;
  values: (number | string)[];
  label?: string;
}

export interface SolveRequest {
  formation: string;
  requirements: Requirement[];
  use_club: boolean;
  only_club: boolean;
  buy_from_market: boolean;
  alternatives: number;
  time_limit_s: number;
  untradeable_bonus: number;
  excluded_ids: string[];
}

export interface CardView {
  rarity: string;
  kind: string;
  positions: string[];
  nation: string | null;
  club: string | null;
  league: string | null;
  face: string | null;
  flag: string | null;
  badge: string | null;
}

export interface Slot extends CardView {
  slot: number;
  position: string;
  card_id: string;
  definition_id: number | null;
  name: string;
  rating: number;
  in_position: boolean;
  chemistry: number;
  owned: boolean;
  untradeable: boolean;
  price: number | null;
  price_source: "live" | "estimate" | "default" | null;
  price_age_min: number | null;
}

export interface Solution {
  status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN" | string;
  message: string;
  total_cost: number;
  team_rating: number;
  team_chem: number;
  slots: Slot[];
  violations: string[];
  pool_size: number;
  wall_time_s: number;
  estimated_cost_share: number;
  requirements: { ok: boolean; actual: number }[];
}

export interface Me {
  user_id: string;
  token?: string | null;
  platform: string;
  club_size: number;
  club_imported_at: string | null;
}

export interface ClubRow extends CardView {
  item_id: number;
  definition_id: number;
  name: string;
  rating: number;
  untradeable: boolean;
  loans: number;
  price: number | null;
  price_source: string | null;
}

export interface Named {
  id: number;
  name: string;
}

const TOKEN_KEY = "futsbc.token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private mode: token lives only for this session */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init: RequestInit = {}, timeoutMs = 15_000): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetchWithTimeout(path, { ...init, headers: { ...headers, ...(init.headers as object) } }, timeoutMs);
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : msg;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => call<{ ok: boolean; season: string; cards: number }>("/api/health"),
  createUser: (platform: string) =>
    call<Me>("/api/users", { method: "POST", body: JSON.stringify({ platform }) }),
  me: () => call<Me>("/api/me"),
  club: () => call<ClubRow[]>("/api/club"),
  leagues: () => call<Named[]>("/api/leagues"),
  nations: () => call<Named[]>("/api/nations"),
  formations: () => call<Record<string, string[]>>("/api/formations"),
  // the server stops after time_limit_s (+ grace); the client waits a bit longer
  solve: (req: SolveRequest) =>
    call<Solution[]>("/api/solve", { method: "POST", body: JSON.stringify(req) }, (req.time_limit_s + 25) * 1000),
};

export interface Preset {
  id: string;
  kind: "puzzle" | "streamlined";
  group: string;
  name: string;
  source: string;
  expires: string | null;
  formation?: string;
  requirements?: Requirement[];
  target?: number;
  min_ovr?: number;
}

export interface StreamlinedCard extends CardView {
  card_id: string;
  definition_id: number | null;
  name: string;
  rating: number;
  points: number;
  count: number;
  owned: boolean;
  untradeable: boolean;
  price: number | null;
  price_source: string | null;
  price_age_min: number | null;
}

export interface StreamlinedResult {
  status: string;
  message: string;
  target: number;
  points: number;
  total_coins: number;
  owned_value: number;
  submit: StreamlinedCard[];
  buy: StreamlinedCard[];
  estimated_cost_share: number;
}

export const streamlinedApi = {
  presets: () => call<Preset[]>("/api/presets"),
  solve: (body: { target: number; min_ovr: number; already: number; use_club: boolean; buy_from_market: boolean }) =>
    call<StreamlinedResult>("/api/solve/streamlined", { method: "POST", body: JSON.stringify(body) }),
};
