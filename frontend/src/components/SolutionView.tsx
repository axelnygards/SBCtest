import { useState } from "react";

import type { Solution } from "../lib/api";

const coins = (n: number) => n.toLocaleString("sv-SE");

/** Collapsible table version of a squad (names, clubs, prices). */
export function SolutionList({ sol }: { sol: Solution }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button className="text-xs font-semibold text-slate-400 transition hover:text-neon-cyan" onClick={() => setOpen(!open)}>
        {open ? "▾ Dölj lista" : "▸ Visa som lista"}
      </button>
      {open && (
        <table className="mt-3 w-full text-sm">
          <tbody>
            {sol.slots.map((s) => (
              <tr key={s.slot} className="border-t border-white/5">
                <td className="num py-2 pr-3 text-xs text-slate-500">{s.position}</td>
                <td className="pr-2">
                  <div className="font-medium text-slate-100">{s.name}{!s.in_position && <span className="ml-1 text-xs text-rose-300">ur position</span>}</div>
                  <div className="text-xs text-slate-500">{[s.club, s.league, s.nation].filter(Boolean).join(" · ")}</div>
                </td>
                <td className="num px-2 text-right">{s.rating}</td>
                <td className="num pl-2 text-right">{s.owned ? "egen" : coins(s.price ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** Alternatives side by side: cost delta against the cheapest. */
export function Alternatives({ sols, shown, onShow }: { sols: Solution[]; shown: number; onShow: (i: number) => void }) {
  if (sols.length < 2) return null;
  const best = sols[0].total_cost;
  return (
    <div className="glass-inset overflow-hidden">
      <div className="label border-b border-white/5 px-3.5 py-2.5 !text-slate-300">Alternativ</div>
      {sols.map((s, i) => (
        <button key={i} onClick={() => onShow(i)}
          className={`flex w-full items-center gap-3 px-3.5 py-2.5 text-left transition hover:bg-white/5 ${shown === i ? "bg-neon-cyan/[0.07]" : ""}`}>
          <span className={`h-2 w-2 rounded-full ${shown === i ? "bg-neon-cyan shadow-[0_0_8px_var(--color-neon-cyan)]" : "bg-white/20"}`} />
          <span className="flex-1 text-sm font-medium">{i === 0 ? "Billigast" : `Alternativ ${i}`}</span>
          <span className="num text-xs text-slate-400">{s.team_rating} · {s.team_chem}c</span>
          <span className="num w-20 text-right text-sm font-bold text-white">
            {i === 0 ? coins(s.total_cost) : `+${coins(s.total_cost - best)}`}
          </span>
        </button>
      ))}
    </div>
  );
}
