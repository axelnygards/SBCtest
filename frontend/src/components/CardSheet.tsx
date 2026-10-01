import { useEffect, useState } from "react";

import type { CardView } from "../lib/api";
import { setIn, type OwnPrices } from "../lib/ownPrices";
import { FutCard } from "./FutCard";

export interface SheetCard extends CardView {
  card_id: string;
  definition_id: number | null;
  name: string;
  rating: number;
  position?: string;
  owned: boolean;
  untradeable: boolean;
  price: number | null;
  price_source: string | null;
  price_age_min?: number | null;
}

const n = (x: number) => x.toLocaleString("sv-SE");

function priceLabel(c: SheetCard): string {
  if (c.owned && c.untradeable) return "Ditt kort, ej säljbart: gratis att använda";
  const base = c.price_source === "live" ? `Livepris${c.price_age_min != null ? `, ${c.price_age_min} min sedan` : ""}`
    : c.price_source === "own" ? "Ditt eget pris"
    : c.price_source === "estimate" ? "Uppskattat pris (liknande kort)" : "Standardpris (ingen data ännu)";
  return c.owned ? `Ditt säljbara kort · ${base.toLowerCase()}` : base;
}

/** Player detail sheet: set an own price or stop using the card. Like the game's player bio. */
export function CardSheet({ card, own, update, onClose, onRecalc, onReport }: {
  card: SheetCard; own: OwnPrices; update: (f: (v: OwnPrices) => OwnPrices) => void;
  onClose: () => void; onRecalc: () => void; onReport: (definitionId: number, price: number) => Promise<boolean>;
}) {
  const did = card.definition_id != null ? String(card.definition_id) : null;
  const saved = did ? own.cards[did]?.price : undefined;
  const [draft, setDraft] = useState(saved != null ? String(saved) : "");
  const excluded = card.card_id in own.excluded;
  const [changed, setChanged] = useState(false);
  const [thanks, setThanks] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function share(value: number) {
    if (!own.share || card.definition_id == null || card.untradeable) return;
    setThanks((await onReport(card.definition_id, value)) ? "Tack! Priset hjälper alla som löser SBC:er." : null);
  }

  function savePrice(value: number | null) {
    if (!did) return;
    update((v) => ({ ...v, enabled: true, cards: setIn(v.cards, did, value == null ? null : { price: value, name: card.name, rating: card.rating }) }));
    setChanged(true);
    if (value != null) share(value);
  }

  function toggleExcluded() {
    update((v) => ({ ...v, excluded: setIn(v.excluded, card.card_id, excluded ? null : { name: card.name, rating: card.rating, owned: card.owned }) }));
    setChanged(true);
  }

  const draftValue = draft === "" ? null : Math.max(0, Math.round(Number(draft)));
  return (
    <div className="fixed inset-0 z-50 grid place-items-end bg-black/60 backdrop-blur-sm sm:place-items-center" onClick={onClose}
      role="dialog" aria-modal="true" aria-label={card.name}>
      <div className="glass w-full max-w-md !rounded-b-none p-5 sm:!rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex gap-4">
          <div className="w-28 shrink-0"><FutCard card={{ ...card, position: card.position ?? card.positions?.[0] ?? "" }} /></div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-display text-lg font-extrabold leading-tight text-white">{card.name}</h3>
              <button className="-mr-1 -mt-1 rounded-full px-2 text-lg text-slate-400 hover:text-white" onClick={onClose} aria-label="Stäng">×</button>
            </div>
            <p className="mt-1 text-[12px] text-slate-400">{[card.club, card.league, card.nation].filter(Boolean).join(" · ")}</p>
            <div className="mt-3 num text-2xl font-extrabold text-white">
              {card.owned && card.untradeable ? "0" : n(card.price ?? 0)}
            </div>
            <p className="text-[11px] text-slate-400">{priceLabel(card)}</p>
          </div>
        </div>

        {!card.untradeable && did && (
          <div className="mt-5">
            <span className="label mb-1.5 block">Vad kostar den i spelet?</span>
            <div className="flex gap-2">
              <input type="number" inputMode="numeric" min={0} step={50} className="field num flex-1" placeholder={n(card.price ?? 0)}
                value={draft} onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && draftValue != null && savePrice(draftValue)} />
              <button className="btn-ghost !w-auto px-4" disabled={draftValue == null || draftValue === saved}
                onClick={() => draftValue != null && savePrice(draftValue)}>Spara</button>
            </div>
            {!card.owned && card.price != null && card.price_source !== "own" && own.share && !thanks && (
              <button className="mt-1.5 mr-4 text-[11px] font-semibold text-neon-cyan hover:underline" onClick={() => share(card.price!)}>
                ✓ Priset stämmer i spelet
              </button>
            )}
            {thanks && <p className="mt-1.5 text-[11px] text-neon-green">{thanks}</p>}
            {saved != null && (
              <button className="mt-1.5 text-[11px] text-slate-400 hover:text-white" onClick={() => { setDraft(""); savePrice(null); }}>
                Ta bort eget pris ({n(saved)})
              </button>
            )}
          </div>
        )}

        <button onClick={toggleExcluded}
          className={`mt-4 w-full rounded-2xl border px-4 py-2.5 text-left text-[13px] font-semibold transition ${excluded
            ? "border-rose-400/50 bg-rose-500/10 text-rose-200" : "border-white/10 bg-white/[0.03] text-slate-200 hover:border-white/25"}`}>
          {excluded ? "✓ Används inte · klicka för att använda igen"
            : card.owned ? "Använd inte det här kortet (behåll det)" : "Använd inte den här spelaren"}
        </button>

        {changed && (
          <button className="btn-primary mt-4" onClick={() => { onClose(); onRecalc(); }}>Beräkna igen</button>
        )}
      </div>
    </div>
  );
}
