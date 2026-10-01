import { useId, useState } from "react";

export interface CardData {
  name: string;
  card_name?: string | null;
  rating: number;
  position: string;
  rarity?: string;
  kind?: string;
  face?: string | null;
  flag?: string | null;
  badge?: string | null;
  stats?: Record<string, number>;
}

/** Tier like the game: quality from rating, rare = shiny facets, specials/icons/heroes. */
export function cardTier(c: Pick<CardData, "rating" | "rarity" | "kind">): string {
  if (c.kind === "icon") return "icon";
  if (c.kind === "hero") return "hero";
  if (c.rarity && c.rarity.startsWith("special")) return "special";
  const q = c.rating >= 75 ? "gold" : c.rating >= 65 ? "silver" : "bronze";
  return c.rarity === "rare" ? `${q}-rare` : q;
}

interface Theme { stops: [string, string, string]; ink: string; facets: string | null; edge: string }
const THEMES: Record<string, Theme> = {
  "gold":        { stops: ["#f1d98c", "#dcb75a", "#c79f3f"], ink: "#3b2a06", facets: null, edge: "#a8812a" },
  "gold-rare":   { stops: ["#fbe9a6", "#ecc65c", "#c89a2b"], ink: "#3b2a06", facets: "#fff6cf", edge: "#b0862a" },
  "silver":      { stops: ["#eef1f4", "#cbd2da", "#a9b2bd"], ink: "#23282f", facets: null, edge: "#8e98a4" },
  "silver-rare": { stops: ["#ffffff", "#d7dee6", "#a6b1be"], ink: "#23282f", facets: "#ffffff", edge: "#8e98a4" },
  "bronze":      { stops: ["#ebb58b", "#c98552", "#a7653a"], ink: "#341b0a", facets: null, edge: "#8b5128" },
  "bronze-rare": { stops: ["#f5c79e", "#d48e57", "#a5612f"], ink: "#341b0a", facets: "#ffe2c7", edge: "#8b5128" },
  "special":     { stops: ["#2e2e33", "#18181c", "#0b0b0e"], ink: "#f1d68a", facets: "#f1d68a", edge: "#6d5a26" },
  "icon":        { stops: ["#fdf6e1", "#ecdcae", "#d2b979"], ink: "#3d2c06", facets: "#ffffff", edge: "#b39a5c" },
  "hero":        { stops: ["#4357d6", "#24308a", "#141c52"], ink: "#f6efdd", facets: "#9fb0ff", edge: "#0d1440" },
};

// The card silhouette (viewBox 100 x 132): shoulders, arched top, rounded shield bottom.
const SHAPE = "M5 17 C5 11.5 8 9 12.5 9 C19 9 22 6.5 26 4 C33 0.5 42 0 50 0 C58 0 67 0.5 74 4 C78 6.5 81 9 87.5 9 " +
  "C92 9 95 11.5 95 17 L95 112 C95 117.5 92.5 119.5 87 121 C72 124.5 60 127 50 131.5 C40 127 28 124.5 13 121 " +
  "C7.5 119.5 5 117.5 5 112 Z";
const FACETS = ["30,30 70,4 95,16", "44,54 76,8 95,38", "26,72 58,26 95,62", "5,38 30,22 48,40",
  "5,60 24,44 38,72", "58,26 84,48 95,38", "70,4 76,8 84,48", "84,48 95,70", "30,22 58,26"];
const FACET_FILLS = ["70,4 95,16 76,8", "58,26 84,48 76,8", "84,48 95,38 95,62"];
const STAT_X = [17.5, 30.5, 43.5, 56.5, 69.5, 82.5];

/** A card laid out like the in-game Ultimate Team item, drawn from current FC 27 data. */
export function FutCard({ card, perfect = false }: { card: CardData; perfect?: boolean }) {
  const uid = useId().replace(/:/g, "");
  const [faceOk, setFaceOk] = useState(true);
  const t = THEMES[cardTier(card)] ?? THEMES.gold;
  const name = card.card_name || card.name.split(" ").slice(-1)[0];
  const stats = Object.entries(card.stats ?? {}).slice(0, 6);
  const hasStats = stats.length === 6;
  const nameY = hasStats ? 98 : 104;
  return (
    <div className={`fcard ${perfect ? "perfect" : ""}`} title={`${card.name} · ${card.rating} ${card.position}`}>
      <svg viewBox="0 0 100 132" className="block h-auto w-full overflow-visible" role="img" aria-label={`${card.name} ${card.rating}`}>
        <defs>
          <linearGradient id={`g${uid}`} x1="0" y1="0" x2="0.35" y2="1">
            <stop offset="0" stopColor={t.stops[0]} /><stop offset="0.55" stopColor={t.stops[1]} /><stop offset="1" stopColor={t.stops[2]} />
          </linearGradient>
          <linearGradient id={`fade${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0.86" stopColor="white" /><stop offset="1" stopColor="black" />
          </linearGradient>
          <mask id={`m${uid}`}><rect x="0" y="0" width="100" height="87" fill={`url(#fade${uid})`} /></mask>
          <clipPath id={`c${uid}`}><path d={SHAPE} /></clipPath>
        </defs>
        <g clipPath={`url(#c${uid})`}>
          <rect width="100" height="132" fill={`url(#g${uid})`} />
          {t.facets && (
            <g>
              {FACET_FILLS.map((p) => <polygon key={p} points={p} fill={t.facets ?? undefined} opacity="0.22" />)}
              <g fill="none" stroke={t.facets} strokeWidth="0.6" opacity="0.85">
                {FACETS.map((p) => <polyline key={p} points={p} />)}
              </g>
            </g>
          )}
          <rect y="0" width="100" height="85" fill="white" opacity="0.07" />
          <rect y="85" width="100" height="47" fill="white" opacity="0.10" />
          {card.face && faceOk && (
            <image href={card.face} x="26" y="14" width="70" height="73" preserveAspectRatio="xMidYMin slice"
              mask={`url(#m${uid})`} onError={() => setFaceOk(false)} />
          )}
        </g>
        <path d={SHAPE} fill="none" stroke={t.edge} strokeOpacity="0.55" strokeWidth="0.8" />
        <g fill={t.ink} fontFamily="Barlow, 'Barlow Condensed', Montserrat, sans-serif" textAnchor="middle">
          <text x="19.5" y="29" fontSize="19.5" fontWeight="800" letterSpacing="-0.7">{card.rating}</text>
          <text x="19.5" y="38.5" fontSize="7.6" fontWeight="700">{card.position}</text>
          {!(card.face && faceOk) && (
            <text x="61" y="58" fontSize="22" fontWeight="800" opacity="0.18">
              {card.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
            </text>
          )}
          <text x="50" y={nameY} fontSize="11" fontWeight="800"
            {...(name.length > 11 ? { textLength: 78, lengthAdjust: "spacingAndGlyphs" } : {})}>{name}</text>
          {hasStats && stats.map(([k, v], i) => (
            <g key={k}>
              <text x={STAT_X[i]} y="106.5" fontSize="5" fontWeight="700" opacity="0.9">{k}</text>
              <text x={STAT_X[i]} y="115" fontSize="8.2" fontWeight="800">{v}</text>
            </g>
          ))}
        </g>
        {card.flag && <image href={card.flag} x="34.5" y={hasStats ? 118.5 : 111} width="11" height="7.4" preserveAspectRatio="xMidYMid slice" />}
        {card.badge && <image href={card.badge} x="55" y={hasStats ? 117.5 : 110} width="10" height="10" preserveAspectRatio="xMidYMid meet" />}
      </svg>
    </div>
  );
}

/** Chemistry pips: three diamonds, neon when earned, red when out of position. */
export function ChemPips({ chem, inPosition = true }: { chem: number; inPosition?: boolean }) {
  return (
    <div className="chem-pips" title={inPosition ? `Chemistry ${chem}/3` : "Ur position: 0 chemistry"}>
      {[0, 1, 2].map((i) => (
        <span key={i} className={`chem-pip ${i < chem ? "on" : ""} ${inPosition ? "" : "off-pos"}`} />
      ))}
    </div>
  );
}
