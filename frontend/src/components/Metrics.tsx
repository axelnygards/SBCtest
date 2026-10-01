/** Dashboard metrics: progress rings and monospace numbers. */

export function Ring({ value, max, target, label, sub, size = 92 }: {
  value: number; max: number; target?: number | null; label: string; sub?: string; size?: number;
}) {
  const r = 40;
  const c = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, value / Math.max(max, 1)));
  const met = target == null || value >= target;
  const color = met ? "var(--color-neon-green)" : "var(--color-neon-purple)";
  const tFrac = target != null ? Math.min(1, target / Math.max(max, 1)) : null;
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative" style={{ width: size, height: size }}>
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r={r} fill="none" strokeWidth="7" className="ring-track" />
          <circle cx="50" cy="50" r={r} fill="none" strokeWidth="7" strokeLinecap="round" className="ring-bar"
            style={{ color, stroke: color, strokeDasharray: c, strokeDashoffset: c * (1 - frac) }} />
          {tFrac != null && (
            <line x1="50" y1="5" x2="50" y2="15" stroke="white" strokeWidth="2" strokeLinecap="round"
              transform={`rotate(${tFrac * 360} 50 50)`} opacity="0.7" />
          )}
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <div className="text-center leading-none">
            <div className="num text-2xl font-extrabold text-white">{value}</div>
            {sub && <div className="num mt-1 text-[10px] text-slate-400">{sub}</div>}
          </div>
        </div>
      </div>
      <span className="label">{label}</span>
    </div>
  );
}

export function CostTile({ coins, estimatedShare, ownShare = 0, status, time, ownedValue = 0, cachedAge = null }: {
  coins: number; estimatedShare: number; ownShare?: number; status?: string; time?: number; ownedValue?: number;
  cachedAge?: number | null;
}) {
  const est = Math.round(estimatedShare * 100);
  const own = Math.round(ownShare * 100);
  const live = Math.max(0, 100 - est - own);
  const when = cachedAge != null ? ` · klar direkt` : time != null ? ` · ${time.toFixed(1)}s` : "";
  return (
    <div className="glass-inset p-4">
      <div className="flex items-center justify-between">
        <span className="label">Total kostnad</span>
        {status && (
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${status === "OPTIMAL"
            ? "bg-neon-green/10 text-neon-green ring-1 ring-neon-green/30" : "bg-amber-400/10 text-amber-300 ring-1 ring-amber-300/30"}`}>
            {status === "OPTIMAL" ? "BEVISAT BILLIGAST" : "BÄSTA INOM TIDSGRÄNSEN"}{when}
          </span>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="num text-4xl font-extrabold text-white">{coins.toLocaleString("sv-SE")}</span>
        <span className="text-sm text-slate-400">mynt att köpa för</span>
      </div>
      {ownedValue > 0 && (
        <div className="mt-1 text-[11px] text-slate-400">
          + egna säljbara kort värda <span className="num text-slate-200">{ownedValue.toLocaleString("sv-SE")}</span> om du sålt dem
        </div>
      )}
      <div className="mt-3 flex h-1.5 overflow-hidden rounded-full bg-white/5">
        <div className="bg-neon-cyan shadow-[0_0_8px_var(--color-neon-cyan)]" style={{ width: `${live}%` }} />
        <div className="bg-neon-purple" style={{ width: `${own}%` }} />
        <div className="bg-amber-300/70" style={{ width: `${est}%` }} />
      </div>
      <div className="mt-1.5 flex justify-between gap-2 text-[11px] text-slate-400">
        <span><span className="text-neon-cyan">●</span> live {live}%</span>
        {own > 0 && <span><span className="text-neon-purple">●</span> dina priser {own}%</span>}
        <span><span className="text-amber-300">●</span> uppskattat {est}%</span>
      </div>
      {cachedAge != null && (
        <p className="mt-2 text-[11px] text-slate-500">
          Sparad lösning, beräknad för {cachedAge < 60 ? "under en minut" : `${Math.round(cachedAge / 60)} min`} sedan. Priserna på korten är kontrollerade.
        </p>
      )}
    </div>
  );
}
