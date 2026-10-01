import { FORMATION_LAYOUT, FORMATION_POSITIONS } from "../lib/formations";
import type { Slot } from "../lib/api";
import { ChemPips, FutCard } from "./FutCard";

const coins = (n: number) => n.toLocaleString("sv-SE");

function PitchLines() {
  return (
    <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 140" preserveAspectRatio="none" aria-hidden>
      <defs>
        <pattern id="stripes" width="100" height="20" patternUnits="userSpaceOnUse">
          <rect width="100" height="10" fill="rgba(255,255,255,0.035)" />
        </pattern>
      </defs>
      <rect width="100" height="140" fill="url(#stripes)" />
      <g fill="none" stroke="rgba(255,255,255,0.28)" strokeWidth="0.35">
        <rect x="4" y="4" width="92" height="132" />
        <line x1="4" y1="70" x2="96" y2="70" />
        <circle cx="50" cy="70" r="11" />
        <rect x="24" y="4" width="52" height="21" />
        <rect x="37" y="4" width="26" height="8" />
        <rect x="24" y="115" width="52" height="21" />
        <rect x="37" y="128" width="26" height="8" />
        <path d="M 41 25 A 11 11 0 0 0 59 25" />
        <path d="M 41 115 A 11 11 0 0 1 59 115" />
      </g>
    </svg>
  );
}

function PriceChip({ s }: { s: Slot }) {
  if (s.owned)
    return <span className="chip chip-owned">{s.untradeable ? "egen · ej säljbar" : "egen"}</span>;
  const cls = s.price_source === "live" ? "chip-live" : "chip-est";
  return (
    <span className={`chip ${cls}`} title={s.price_source === "live" ? `Livepris, ${s.price_age_min ?? "?"} min sedan` : "Uppskattat pris"}>
      {coins(s.price ?? 0)}
    </span>
  );
}

/** The squad on a pitch, positioned like the formation screen in Ultimate Team. */
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
                <FutCard card={{ ...s, position: s.position }} />
                <PriceChip s={s} />
                <ChemPips chem={s.chemistry} inPosition={s.in_position} />
              </>
            ) : (
              <div className={`fut-card fut-card-empty ${loading ? "animate-pulse" : ""}`}>
                <span>{positions[i]}</span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
