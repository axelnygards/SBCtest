import type { ReactNode } from "react";

import type { Requirement } from "../lib/api";
import { reqText, type NameLookup } from "../lib/reqText";

export interface ReqStatus {
  ok: boolean;
  actual: number;
}

function Tick({ state }: { state: "none" | "ok" | "fail" }) {
  if (state === "none") return <span className="h-4 w-4 shrink-0 rounded-full ring-1 ring-white/20" />;
  return (
    <span className={`grid h-4 w-4 shrink-0 place-items-center rounded-full text-[10px] font-black ${state === "ok"
      ? "bg-neon-green text-black shadow-[0_0_8px_var(--color-neon-green)]" : "bg-rose-500 text-white"}`}>
      {state === "ok" ? "✓" : "✕"}
    </span>
  );
}

function Box({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <div className="glass-inset overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/5 px-3.5 py-2.5">
        <span className="label truncate !text-slate-300">{title}</span>
        {right}
      </div>
      <ul className="divide-y divide-white/[0.04]">{children}</ul>
    </div>
  );
}

/** Plain in-game style list of requirement lines (used for Item Score SBCs). */
export function RequirementLines({ lines, title, done }: { lines: string[]; title: string; done?: boolean }) {
  return (
    <Box title={title}>
      {lines.map((l) => (
        <li key={l} className="flex items-center gap-2.5 px-3.5 py-2 text-[13px]">
          <Tick state={done ? "ok" : "none"} /><span className="font-medium text-slate-100">{l}</span>
        </li>
      ))}
    </Box>
  );
}

/** The requirement list as the game words it, with a tick and the achieved value once solved. */
export function RequirementList({ reqs, names, status, title = "Requirements" }: {
  reqs: Requirement[]; names: NameLookup; status?: ReqStatus[]; title?: string;
}) {
  const done = status?.filter((s) => s.ok).length ?? 0;
  return (
    <Box title={title} right={status && (
      <span className={`num text-[11px] font-bold ${done === status.length ? "text-neon-green" : "text-rose-300"}`}>{done}/{status.length}</span>
    )}>
      {reqs.map((r, i) => {
        const st = status?.[i];
        return (
          <li key={i} className="flex items-center gap-2.5 px-3.5 py-2 text-[13px]">
            <Tick state={!st ? "none" : st.ok ? "ok" : "fail"} />
            <span className="flex-1 font-medium text-slate-100">{reqText(r, names)}</span>
            {st && !(r.attr === "quality" && r.op === "max") && <span className="num text-xs text-slate-400">{st.actual}</span>}
          </li>
        );
      })}
    </Box>
  );
}
