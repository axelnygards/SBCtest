import type { StreamlinedCard, StreamlinedResult } from "../lib/api";
import { FutCard } from "./FutCard";
import { PriceChip } from "./Pitch";

const n = (x: number) => x.toLocaleString("sv-SE");

function Cell({ c, onSelect }: { c: StreamlinedCard; onSelect?: (c: StreamlinedCard) => void }) {
  return (
    <div className="card-cell">
      {c.count > 1 && <span className="count-badge">×{c.count}</span>}
      <button type="button" className="block w-full max-w-[112px] cursor-pointer" onClick={() => onSelect?.(c)}
        aria-label={`${c.name}, ${c.rating}: pris och val`}>
        <FutCard card={{ ...c, position: c.positions?.[0] ?? "" }} />
      </button>
      <span className="num text-[11px] text-slate-400">{n(c.points * c.count)} p</span>
      <PriceChip s={c} />
    </div>
  );
}

/** Centre view for Item Score SBCs: the cards to submit and to buy. */
export function StreamlinedCards({ res, onSelect }: { res: StreamlinedResult; onSelect?: (c: StreamlinedCard) => void }) {
  if (res.status !== "OPTIMAL")
    return <div className="rounded-xl bg-rose-500/10 p-4 text-rose-200 ring-1 ring-rose-500/30">{res.message || "Ingen lösning hittades."}</div>;
  return (
    <div className="space-y-7">
      {res.message && <p className="text-sm text-slate-300">{res.message}</p>}
      {res.submit.length > 0 && (
        <section>
          <h4 className="label mb-4">Lämna in från din klubb · {res.submit.length}</h4>
          <div className="card-grid">{res.submit.map((c) => <Cell key={c.card_id} c={c} onSelect={onSelect} />)}</div>
        </section>
      )}
      {res.buy.length > 0 && (
        <section>
          <h4 className="label mb-4">Köp på transfermarknaden</h4>
          <div className="card-grid">{res.buy.map((c) => <Cell key={c.card_id} c={c} onSelect={onSelect} />)}</div>
          <p className="mt-4 text-xs text-slate-500">Vilket kort som helst med samma betyg ger samma poäng: köp det billigaste du hittar.</p>
        </section>
      )}
    </div>
  );
}
