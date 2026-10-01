import type { Slot, Solution } from "../lib/api";

const coins = (n: number) => n.toLocaleString("sv-SE");

function PriceBadge({ s }: { s: Slot }) {
  if (s.owned)
    return <span className="inline-block whitespace-nowrap rounded bg-emerald-100 px-1.5 py-0.5 text-xs text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
      egen{s.untradeable ? " · ej säljbar" : ""}</span>;
  if (s.price_source === "live")
    return <span className="inline-block whitespace-nowrap rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-800 dark:bg-blue-900 dark:text-blue-200">
      live{s.price_age_min != null ? ` · ${s.price_age_min} min` : ""}</span>;
  return <span title="Inget aktuellt marknadspris – uppskattat från liknande kort"
    className="inline-block whitespace-nowrap rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800 dark:bg-amber-900 dark:text-amber-200">
    {s.price_source === "estimate" ? "uppskattat" : "standardpris"}</span>;
}

export function SolutionView({ sol, index }: { sol: Solution; index: number }) {
  if (!["OPTIMAL", "FEASIBLE"].includes(sol.status))
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
      {sol.message || "Ingen lösning hittades."}</div>;
  const toBuy = sol.slots.filter((s) => !s.owned).length;
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm dark:bg-slate-900">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h3 className="text-lg font-semibold">{index === 0 ? "Billigaste lösningen" : `Alternativ ${index}`}</h3>
        <span className="text-2xl font-bold tabular-nums">{coins(sol.total_cost)} <span className="text-sm font-normal">mynt</span></span>
        <span className="text-sm text-slate-500">Betyg {sol.team_rating} · Chem {sol.team_chem} · köp {toBuy} / 11</span>
        <span className="text-xs text-slate-400">
          {sol.status === "OPTIMAL" ? "bevisat billigast" : "bästa inom tidsgränsen"} · {sol.wall_time_s} s
        </span>
      </div>
      {sol.estimated_cost_share > 0.3 && (
        <p className="mb-3 rounded-md bg-amber-50 p-2 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          {Math.round(sol.estimated_cost_share * 100)} % av kostnaden bygger på uppskattade priser. Kontrollera priserna
          på transfermarknaden innan du köper – med tillägget delas de du ser automatiskt.
        </p>
      )}
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-slate-500">
          <tr><th className="py-1 pr-2">Pos</th><th className="pr-2">Spelare</th><th className="px-2 text-right">Betyg</th>
            <th className="px-2 text-right">Chem</th><th className="pl-2 text-right">Pris</th>
            <th className="hidden sm:table-cell"></th></tr>
        </thead>
        <tbody>
          {sol.slots.map((s) => (
            <tr key={s.slot} className="border-t border-slate-100 dark:border-slate-800">
              <td className="py-1.5 pr-2 font-mono text-xs">{s.position}</td>
              <td className="pr-2">{s.name}{!s.in_position && <span className="ml-1 text-xs text-slate-400">(ur position)</span>}
                <div className="sm:hidden"><PriceBadge s={s} /></div></td>
              <td className="px-2 text-right tabular-nums">{s.rating}</td>
              <td className="px-2 text-right tabular-nums">{s.chemistry}</td>
              <td className="pl-2 text-right tabular-nums whitespace-nowrap">{s.owned ? "–" : coins(s.price ?? 0)}</td>
              <td className="hidden pl-2 text-right sm:table-cell"><PriceBadge s={s} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
