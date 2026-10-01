import { FORMATION_LAYOUT, FORMATION_POSITIONS } from "../lib/formations";
import type { Slot } from "../lib/api";
import { ChemPips, FutCard } from "./FutCard";

const coins = (n: number) => n.toLocaleString("sv-SE");

function PitchLines() {
  return (
    <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 132" preserveAspectRatio="none" aria-hidden>
      <defs>
        <pattern id="mow" width="100" height="16.5" patternUnits="userSpaceOnUse">
          <rect width="100" height="8.25" fill="rgba(255,255,255,0.018)" />
        </pattern>
      </defs>
      <rect width="100" height="132" fill="url(#mow)" />
      <g fill="none" stroke="rgba(190,255,220,0.16)" strokeWidth="0.3">
        <rect x="4" y="3.5" width="92" height="125" rx="0.6" />
        <line x1="4" y1="66" x2="96" y2="66" />
        <circle cx="50" cy="66" r="10" />
        <circle cx="50" cy="66" r="0.6" fill="rgba(190,255,220,0.3)" />
        <rect x="24" y="3.5" width="52" height="19" />
        <rect x="37" y="3.5" width="26" height="7" />
        <path d="M 41.5 22.5 A 10 10 0 0 0 58.5 22.5" />
        <rect x="24" y="109.5" width="52" height="19" />
        <rect x="37" y="121.5" width="26" height="7" />
        <path d="M 41.5 109.5 A 10 10 0 0 1 58.5 109.5" />
      </g>
    </svg>
  );
}

function PriceChip({ s }: { s: Slot }) {
  if (s.owned) return <span className="chip chip-owned">{s.untradeable ? "EJ SÄLJBAR" : "EGEN"}</span>;
  const live = s.price_source === "live";
  return (
    <span className={`chip ${live ? "chip-live" : "chip-est"}`}
      title={live ? `Livepris, ${s.price_age_min ?? "?"} min sedan` : "Uppskattat pris"}>
      {coins(s.price ?? 0)}
    </span>
  );
}

/** Top-down pitch with the squad in formation, like Ultimate Team's squad screen. */
export function Pitch({ formation, slots, loading = false }: { formation: string; slots?: Slot[]; loading?: boolean }) {
  const layout = FORMATION_LAYOUT[formation] ?? FORMATION_LAYOUT["4-4-2"];
  const positions = FORMATION_POSITIONS[formation] ?? FORMATION_POSITIONS["4-4-2"];
  return (
    <div className="pitch">
      <PitchLines />
      {layout.map(([x, y], i) => {
        const s = slots?.[i];
        return (
          <div key={i} className="pitch-slot" style={{ left: `${x}%`, top: `${y}%` }}>
            {s ? (
              <>
                <FutCard card={s} perfect={s.in_position && s.chemistry === 3} />
                <PriceChip s={s} />
                <ChemPips chem={s.chemistry} inPosition={s.in_position} />
              </>
            ) : (
              <div className={`pcard-empty ${loading ? "shimmer" : ""}`}>{positions[i]}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
