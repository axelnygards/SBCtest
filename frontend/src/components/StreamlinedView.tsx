import type { StreamlinedCard, StreamlinedResult } from "../lib/api";
import { FutCard } from "./FutCard";

const n = (x: number) => x.toLocaleString("sv-SE");

function Cell({ c }: { c: StreamlinedCard }) {
  return (
    <div className="card-cell">
      {c.count > 1 && <span className="count-badge">×{c.count}</span>}
      <div className="w-full max-w-[112px]"><FutCard card={{ ...c, position: c.positions?.[0] ?? "" }} /></div>
      <span className="num text-[11px] text-slate-400">{n(c.points * c.count)} p</span>
      {c.owned
        ? <span className="chip chip-owned">{c.untradeable ? "EJ SÄLJBAR" : "EGEN"}</span>
        : <span className={`chip ${c.price_source === "live" ? "chip-live" : "chip-est"}`}>{n((c.price ?? 0) * c.count)}</span>}
    </div>
  );
}

/** Centre view for Item Score SBCs: the cards to submit and to buy. */
export function StreamlinedCards({ res }: { res: StreamlinedResult }) {
  if (res.status !== "OPTIMAL")
    return <div className="rounded-xl bg-rose-500/10 p-4 text-rose-200 ring-1 ring-rose-500/30">{res.message || "Ingen lösning hittades."}</div>;
  return (
    <div className="space-y-7">
      {res.message && <p className="text-sm text-slate-300">{res.message}</p>}
      {res.submit.length > 0 && (
        <section>
          <h4 className="label mb-4">Lämna in från din klubb · {res.submit.length}</h4>
          <div className="card-grid">{res.submit.map((c) => <Cell key={c.card_id} c={c} />)}</div>
        </section>
      )}
      {res.buy.length > 0 && (
        <section>
          <h4 className="label mb-4">Köp på transfermarknaden</h4>
          <div className="card-grid">{res.buy.map((c) => <Cell key={c.card_id} c={c} />)}</div>
          <p className="mt-4 text-xs text-slate-500">Vilket kort som helst med samma betyg ger samma poäng: köp det billigaste du hittar.</p>
        </section>
      )}
    </div>
  );
}
