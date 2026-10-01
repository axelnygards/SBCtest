import type { RatingPrice } from "../lib/api";
import { ownCount, setIn, type OwnPrices } from "../lib/ownPrices";

const n = (x: number) => x.toLocaleString("sv-SE");
const DEFAULT_RATINGS = Array.from({ length: 27 }, (_, i) => 91 - i); // 91 .. 65

/** Action-panel body: price per rating, per-player prices and excluded players. */
export function OwnPricesPanel({ value, update, market }: {
  value: OwnPrices; update: (f: (v: OwnPrices) => OwnPrices) => void; market: RatingPrice[];
}) {
  const byRating = new Map(market.map((m) => [m.rating, m]));
  const ratings = DEFAULT_RATINGS.filter((r) => byRating.has(r) || value.ratings[r] != null || !market.length);
  const cards = Object.entries(value.cards);
  const excluded = Object.entries(value.excluded);
  return (
    <div className="space-y-3">
      <label className="flex cursor-pointer items-center justify-between rounded-xl bg-white/[0.03] px-3 py-2 ring-1 ring-white/10">
        <span className="text-[12.5px] font-semibold text-white">Använd mina priser</span>
        <input type="checkbox" className="h-4 w-4 accent-[var(--color-neon-purple)]" checked={value.enabled}
          onChange={(e) => update((v) => ({ ...v, enabled: e.target.checked }))} />
      </label>
      <label className="flex cursor-pointer items-start justify-between gap-3 rounded-xl bg-white/[0.03] px-3 py-2 ring-1 ring-white/10">
        <span>
          <span className="block text-[12.5px] font-semibold text-white">Dela anonymt</span>
          <span className="block text-[11px] text-slate-500">Dina priser gör uppskattningarna bättre för alla. Bara pris, kort och plattform skickas.</span>
        </span>
        <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-neon-purple)]" checked={value.share}
          onChange={(e) => update((v) => ({ ...v, share: e.target.checked }))} />
      </label>
      <p className="text-[11px] leading-relaxed text-slate-500">
        Pris per betyg ersätter uppskattade priser för vanliga och sällsynta kort. Livepriser används fortfarande.
        Klicka på ett kort i truppen för att sätta pris på just den spelaren eller välja bort den.
      </p>
      <div className="max-h-64 overflow-y-auto rounded-xl ring-1 ring-white/10">
        <div className="sticky top-0 z-10 grid grid-cols-[44px_1fr_92px] gap-2 bg-ink-1/95 px-3 py-1.5 backdrop-blur">
          <span className="label">Betyg</span><span className="label">Marknaden</span><span className="label text-right">Ditt pris</span>
        </div>
        {ratings.map((r) => {
          const m = byRating.get(r);
          const own = value.ratings[r];
          return (
            <div key={r} className="grid grid-cols-[44px_1fr_92px] items-center gap-2 border-t border-white/[0.04] px-3 py-1">
              <span className="num text-sm font-bold text-white">{r}</span>
              <span className={`num text-[11.5px] ${own != null ? "text-slate-500 line-through" : "text-slate-400"}`}>
                {m ? <><span className={m.source === "live" ? "text-neon-cyan" : "text-amber-300"}>●</span> {n(m.price)}</> : "–"}
              </span>
              <input type="number" inputMode="numeric" min={0} step={50} placeholder="–"
                className={`field num !py-1 text-right text-[12.5px] ${own != null ? "!border-neon-purple/60 text-white" : ""}`}
                value={own ?? ""} aria-label={`Ditt pris för betyg ${r}`}
                onChange={(e) => {
                  const val = e.target.value === "" ? null : Math.max(0, Math.round(Number(e.target.value)));
                  update((v) => ({ ...v, ratings: setIn(v.ratings, String(r), val) }));
                }} />
            </div>
          );
        })}
      </div>
      {cards.length > 0 && (
        <div>
          <div className="label mb-1.5">Spelare med eget pris</div>
          <ul className="space-y-1">
            {cards.map(([id, c]) => (
              <li key={id} className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-2.5 py-1.5 text-[12.5px]">
                <span className="num w-6 font-bold text-white">{c.rating}</span>
                <span className="flex-1 truncate text-slate-200">{c.name}</span>
                <span className="num text-violet-200">{n(c.price)}</span>
                <button className="text-slate-500 hover:text-white" aria-label="Ta bort"
                  onClick={() => update((v) => ({ ...v, cards: setIn(v.cards, id, null) }))}>✕</button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {excluded.length > 0 && (
        <div>
          <div className="label mb-1.5">Används inte</div>
          <ul className="space-y-1">
            {excluded.map(([id, c]) => (
              <li key={id} className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-2.5 py-1.5 text-[12.5px]">
                <span className="num w-6 font-bold text-white">{c.rating}</span>
                <span className="flex-1 truncate text-slate-200">{c.name}{c.owned && <span className="text-slate-500"> · ditt kort</span>}</span>
                <button className="text-[11px] font-semibold text-neon-cyan hover:underline"
                  onClick={() => update((v) => ({ ...v, excluded: setIn(v.excluded, id, null) }))}>Använd igen</button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {(ownCount(value) > 0 || excluded.length > 0) && (
        <button className="text-[11px] text-slate-400 hover:text-white"
          onClick={() => update((v) => ({ ...v, ratings: {}, cards: {}, excluded: {} }))}>Rensa allt</button>
      )}
    </div>
  );
}
