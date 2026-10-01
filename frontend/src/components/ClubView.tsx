import { useMemo, useState } from "react";

import type { ClubRow } from "../lib/api";
import { FutCard } from "./FutCard";

export function ClubView({ rows }: { rows: ClubRow[] }) {
  const [q, setQ] = useState("");
  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? rows.filter((r) => `${r.name} ${r.league} ${r.nation} ${r.club}`.toLowerCase().includes(s)) : rows;
  }, [rows, q]);

  if (!rows.length)
    return (
      <div className="py-10 text-center text-slate-400">
        <div className="mb-2 text-4xl">🗂️</div>
        Ingen klubb importerad än. Öppna EA FC Web App och tryck <b>Importera klubb</b> i tillägget.
      </div>
    );
  return (
    <div>
      <input className="mb-4 w-full rounded-lg bg-white/5 px-3 py-2 text-sm ring-1 ring-white/10 placeholder:text-slate-500 focus:outline-none focus:ring-blue-500"
        placeholder={`Sök bland ${rows.length} spelare…`} value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="card-grid">
        {shown.slice(0, 300).map((r) => (
          <div key={r.item_id} className="card-cell">
            <div className="w-full max-w-[110px]"><FutCard card={{ ...r, position: r.positions?.[0] ?? "" }} /></div>
            <span className="text-[11px] text-slate-400">
              {r.untradeable ? "ej säljbar" : r.price ? r.price.toLocaleString("sv-SE") : ""}{r.loans ? " · lån" : ""}
            </span>
          </div>
        ))}
      </div>
      {shown.length > 300 && <p className="mt-3 text-xs text-slate-500">Visar 300 av {shown.length}. Sök för att hitta fler.</p>}
    </div>
  );
}
