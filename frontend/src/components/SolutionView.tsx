import { useState } from "react";

import type { Requirement, Solution } from "../lib/api";
import type { NameLookup } from "../lib/reqText";
import { Pitch } from "./Pitch";
import { RequirementList } from "./RequirementList";

const coins = (n: number) => n.toLocaleString("sv-SE");

function Stat({ label, value, accent = false }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="rounded-xl bg-white/5 px-3 py-2 ring-1 ring-white/10">
      <div className="text-[11px] uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`text-xl font-extrabold tabular-nums ${accent ? "text-amber-300" : ""}`}>{value}</div>
    </div>
  );
}

export function SolutionSummary({ sol, index }: { sol: Solution; index: number }) {
  const toBuy = sol.slots.filter((s) => !s.owned).length;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-bold">{index === 0 ? "Billigaste lösningen" : `Alternativ ${index}`}</h3>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${sol.status === "OPTIMAL" ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"}`}>
          {sol.status === "OPTIMAL" ? "✓ bevisat billigast" : "bästa inom tidsgränsen"} · {sol.wall_time_s.toFixed(1)} s
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Kostnad" value={coins(sol.total_cost)} accent />
        <Stat label="Betyg" value={sol.team_rating} />
        <Stat label="Chem" value={sol.team_chem} />
        <Stat label="Köp" value={`${toBuy}/11`} />
      </div>
      {sol.estimated_cost_share > 0.3 && (
        <p className="rounded-lg bg-amber-500/10 p-2.5 text-sm text-amber-200 ring-1 ring-amber-500/20">
          {Math.round(sol.estimated_cost_share * 100)} % av kostnaden bygger på uppskattade priser (gul prislapp).
          Kontrollera på transfermarknaden innan du köper.
        </p>
      )}
    </div>
  );
}

export function SolutionList({ sol }: { sol: Solution }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button className="text-sm text-slate-400 hover:text-slate-200" onClick={() => setOpen(!open)}>
        {open ? "▾ Dölj lista" : "▸ Visa som lista"}
      </button>
      {open && (
        <table className="mt-2 w-full text-sm">
          <tbody>
            {sol.slots.map((s) => (
              <tr key={s.slot} className="border-t border-white/5">
                <td className="py-1.5 pr-2 font-mono text-xs text-slate-400">{s.position}</td>
                <td className="pr-2">{s.name}{!s.in_position && <span className="ml-1 text-xs text-red-300">(ur position)</span>}
                  <div className="text-xs text-slate-500">{[s.club, s.league, s.nation].filter(Boolean).join(" · ")}</div></td>
                <td className="px-2 text-right tabular-nums">{s.rating}</td>
                <td className="pl-2 text-right tabular-nums">{s.owned ? "egen" : coins(s.price ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function SolutionView({ sol, index, formation, reqs, names }: {
  sol: Solution; index: number; formation: string; reqs: Requirement[]; names: NameLookup;
}) {
  if (!["OPTIMAL", "FEASIBLE"].includes(sol.status))
    return <div className="rounded-xl bg-red-500/10 p-4 text-red-200 ring-1 ring-red-500/30">{sol.message || "Ingen lösning hittades."}</div>;
  return (
    <div className="space-y-4">
      <SolutionSummary sol={sol} index={index} />
      {sol.requirements?.length === reqs.length && <RequirementList reqs={reqs} names={names} status={sol.requirements} />}
      <Pitch formation={formation} slots={sol.slots} />
      <SolutionList sol={sol} />
    </div>
  );
}
