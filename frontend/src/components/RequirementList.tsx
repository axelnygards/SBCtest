import type { Requirement } from "../lib/api";
import { reqText, type NameLookup } from "../lib/reqText";

export interface ReqStatus {
  ok: boolean;
  actual: number;
}

/** Plain in-game style list of requirement lines (used for Item Score SBCs). */
export function RequirementLines({ lines, title, done }: { lines: string[]; title: string; done?: boolean }) {
  return (
    <div className="overflow-hidden rounded-xl bg-gradient-to-b from-[#16213f] to-[#0f1730] ring-1 ring-white/10">
      <div className="border-b border-white/10 px-3.5 py-2 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-300">{title}</div>
      <ul className="divide-y divide-white/5">
        {lines.map((l) => (
          <li key={l} className="flex items-center gap-2.5 px-3.5 py-2 text-[13px]">
            <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] font-black ${done ? "bg-emerald-500 text-emerald-950" : "ring-1 ring-white/25"}`}>{done ? "✓" : ""}</span>
            <span className="font-medium text-slate-100">{l}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The requirement list as the game shows it, with a tick per requirement once solved. */
export function RequirementList({ reqs, names, status, title = "Requirements" }: {
  reqs: Requirement[]; names: NameLookup; status?: ReqStatus[]; title?: string;
}) {
  return (
    <div className="overflow-hidden rounded-xl bg-gradient-to-b from-[#16213f] to-[#0f1730] ring-1 ring-white/10">
      <div className="flex items-center justify-between border-b border-white/10 px-3.5 py-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-300">{title}</span>
        {status && (
          <span className={`text-[11px] font-bold ${status.every((s) => s.ok) ? "text-emerald-300" : "text-red-300"}`}>
            {status.filter((s) => s.ok).length}/{status.length}
          </span>
        )}
      </div>
      <ul className="divide-y divide-white/5">
        {reqs.map((r, i) => {
          const st = status?.[i];
          return (
            <li key={i} className="flex items-center gap-2.5 px-3.5 py-2 text-[13px]">
              <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] font-black ${
                !st ? "ring-1 ring-white/25" : st.ok ? "bg-emerald-500 text-emerald-950" : "bg-red-500 text-white"}`}>
                {st ? (st.ok ? "✓" : "✕") : ""}
              </span>
              <span className="flex-1 font-medium text-slate-100">{reqText(r, names)}</span>
              {st && !(r.attr === "quality" && r.op === "max") && <span className="tabular-nums text-xs text-slate-400">{st.actual}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
