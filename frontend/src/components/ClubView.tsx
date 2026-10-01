import { useMemo, useState } from "react";

import type { ClubRow } from "../lib/api";

export function ClubView({ rows }: { rows: ClubRow[] }) {
  const [q, setQ] = useState("");
  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? rows.filter((r) => `${r.name} ${r.league} ${r.nation} ${r.club}`.toLowerCase().includes(s)) : rows;
  }, [rows, q]);

  if (!rows.length)
    return <p className="text-sm text-slate-500">Ingen klubb importerad. Öppna EA FC Web App och tryck "Importera klubb" i tillägget.</p>;
  return (
    <div>
      <input className="mb-2 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900"
        placeholder={`Sök bland ${rows.length} spelare…`} value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="max-h-[60vh] overflow-auto">
        <table className="w-full text-sm">
          <tbody>
            {shown.slice(0, 500).map((r) => (
              <tr key={r.item_id} className="border-t border-slate-100 dark:border-slate-800">
                <td className="py-1 tabular-nums font-semibold">{r.rating}</td>
                <td>{r.name}</td>
                <td className="hidden text-slate-500 sm:table-cell">{r.positions?.[0]}</td>
                <td className="hidden text-slate-500 md:table-cell">{r.league}</td>
                <td className="text-right text-xs text-slate-500">
                  {r.untradeable ? "ej säljbar" : r.price ? `${r.price.toLocaleString("sv-SE")}` : ""}
                  {r.loans ? " · lån" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
