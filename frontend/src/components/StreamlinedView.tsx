import type { StreamlinedCard, StreamlinedResult } from "../lib/api";
import { FutCard } from "./FutCard";

const n = (x: number) => x.toLocaleString("sv-SE");

function Cell({ c }: { c: StreamlinedCard }) {
  return (
    <div className="card-cell">
      {c.count > 1 && <span className="count-badge">×{c.count}</span>}
      <div className="w-full max-w-[110px]">
        <FutCard card={{ ...c, position: c.positions?.[0] ?? "" }} />
      </div>
      <span className="text-xs font-semibold text-slate-300 tabular-nums">{n(c.points * c.count)} p</span>
      {c.owned ? (
        <span className="chip chip-owned">{c.untradeable ? "ej säljbar" : "egen"}</span>
      ) : (
        <span className={`chip ${c.price_source === "live" ? "chip-live" : "chip-est"}`}>{n((c.price ?? 0) * c.count)}</span>
      )}
    </div>
  );
}

export function StreamlinedView({ res }: { res: StreamlinedResult }) {
  if (res.status !== "OPTIMAL")
    return <div className="rounded-xl bg-red-500/10 p-4 text-red-200 ring-1 ring-red-500/30">{res.message || "Ingen lösning hittades."}</div>;
  const pct = Math.min(100, Math.round((res.points / Math.max(res.target, 1)) * 100));
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-bold">Billigaste sättet</h3>
        <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-semibold text-emerald-300">✓ bevisat billigast</span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-xl bg-white/5 px-3 py-2 ring-1 ring-white/10">
          <div className="text-[11px] uppercase tracking-wider text-slate-400">Kostnad</div>
          <div className="text-xl font-extrabold tabular-nums text-amber-300">{n(res.total_coins)}</div>
        </div>
        <div className="col-span-2 rounded-xl bg-white/5 px-3 py-2 ring-1 ring-white/10">
          <div className="flex justify-between text-[11px] uppercase tracking-wider text-slate-400">
            <span>Poäng</span><span className="tabular-nums">{n(res.points)} / {n(res.target)}</span>
          </div>
          <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-lime-300" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
      {res.message && <p className="text-sm text-slate-300">{res.message}</p>}
      {res.estimated_cost_share > 0.3 && (
        <p className="rounded-lg bg-amber-500/10 p-2.5 text-sm text-amber-200 ring-1 ring-amber-500/20">
          {Math.round(res.estimated_cost_share * 100)} % av kostnaden bygger på uppskattade priser (gul prislapp).
        </p>
      )}
      {res.submit.length > 0 && (
        <section>
          <h4 className="mb-3 text-sm font-semibold text-slate-300">Lämna in från din klubb · {res.submit.length} kort</h4>
          <div className="card-grid">{res.submit.map((c) => <Cell key={c.card_id} c={c} />)}</div>
        </section>
      )}
      {res.buy.length > 0 && (
        <section>
          <h4 className="mb-3 text-sm font-semibold text-slate-300">Köp på transfermarknaden</h4>
          <div className="card-grid">{res.buy.map((c) => <Cell key={c.card_id} c={c} />)}</div>
          <p className="mt-3 text-xs text-slate-500">Vilket kort som helst med samma betyg ger samma poäng: köp det billigaste du hittar.</p>
        </section>
      )}
    </div>
  );
}
