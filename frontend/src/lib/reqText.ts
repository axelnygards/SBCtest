// Requirement text exactly as Ultimate Team shows it (the game is in English), e.g.
// "Leagues in Squad: Exactly 3", "Players from the same Club: Max. 2", "Min. 1 Player Italy or
// Belgium", "Total Chemistry: Min. 30". Wording follows the FC 27 SBC guides quoting the game.
import type { Named, Op, Requirement } from "./api";

const OP: Record<Op, string> = { min: "Min.", max: "Max.", exact: "Exactly" };
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const players = (n: number) => (n === 1 ? "Player" : "Players");

const GROUP: Record<string, { same: string; distinct: string }> = {
  club: { same: "Club", distinct: "Clubs" },
  league: { same: "League", distinct: "Leagues" },
  nation: { same: "Countries/Regions", distinct: "Countries/Regions" },
};

export interface NameLookup {
  leagues: Map<number, string>;
  nations: Map<number, string>;
}

export function lookup(leagues: Named[], nations: Named[]): NameLookup {
  return { leagues: new Map(leagues.map((l) => [l.id, l.name])), nations: new Map(nations.map((n) => [n.id, n.name])) };
}

function nameOf(attr: string | null | undefined, v: number | string, names: NameLookup): string {
  if (attr === "league") return names.leagues.get(Number(v)) ?? `League #${v}`;
  if (attr === "nation") return names.nations.get(Number(v)) ?? `Country #${v}`;
  if (attr === "club") return `Club #${v}`;
  return String(v);
}

export function reqText(r: Requirement, names: NameLookup): string {
  const op = OP[r.op] ?? "Min.";
  switch (r.type) {
    case "team_rating":
      return `Team Rating: Min. ${r.value}`;
    case "team_chem":
      return `Total Chemistry: Min. ${r.value}`;
    case "player_chem":
      return `Chemistry Points per Player: Min. ${r.value}`;
    case "same":
      return `Players from the same ${GROUP[r.attr ?? "club"]?.same ?? r.attr}: ${op} ${r.value}`;
    case "distinct":
      return `${GROUP[r.attr ?? "club"]?.distinct ?? r.attr} in Squad: ${op} ${r.value}`;
    case "count": {
      const v0 = r.values[0];
      if (r.attr === "quality") {
        if (r.op === "max" && r.value === 0 && v0 === "bronze") return "Player Quality: Min. Silver";
        if (r.op === "exact" && r.value === 11) return `Player Quality: Exactly ${cap(String(v0))}`;
        return `${op} ${r.value} ${players(r.value)} ${cap(String(v0 ?? ""))}`;
      }
      if (r.attr === "rare") return `${op} ${r.value} ${players(r.value)}: Rare`;
      if (r.attr === "rarity") return `${op} ${r.value} ${players(r.value)}: ${cap(String(v0 ?? ""))}`;
      if (r.attr === "rating_gte") return `${op} ${r.value} ${players(r.value)} OVR ${v0}+`;
      const who = r.values.map((v) => nameOf(r.attr, v, names)).join(" or ");
      return `${op} ${r.value} ${players(r.value)} ${who || "…"}`;
    }
    default:
      return r.label || r.type;
  }
}
