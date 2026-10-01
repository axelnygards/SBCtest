import { useState } from "react";

export interface CardData {
  name: string;
  rating: number;
  position: string;
  rarity?: string;
  kind?: string;
  face?: string | null;
  flag?: string | null;
  badge?: string | null;
}

/** Visual tier like the game: quality from rating, rare = shiny, specials = dark. */
export function cardTier(c: Pick<CardData, "rating" | "rarity" | "kind">): string {
  if (c.kind === "icon") return "icon";
  if (c.kind === "hero") return "hero";
  if (c.rarity && c.rarity.startsWith("special")) return "special";
  const q = c.rating >= 75 ? "gold" : c.rating >= 65 ? "silver" : "bronze";
  return c.rarity === "rare" ? `${q}-rare` : q;
}

export function shortName(name: string): string {
  if (name.length <= 13) return name;
  const parts = name.split(" ");
  return parts[parts.length - 1];
}

function Img({ src, alt, className }: { src?: string | null; alt: string; className: string }) {
  const [ok, setOk] = useState(true);
  if (!src || !ok) return null;
  return <img src={src} alt={alt} className={className} loading="lazy" onError={() => setOk(false)} />;
}

export function FutCard({ card, dim = false }: { card: CardData; dim?: boolean }) {
  const [faceOk, setFaceOk] = useState(true);
  return (
    <div className={`fut-card tier-${cardTier(card)} ${dim ? "opacity-60" : ""}`}
      title={`${card.name} · ${card.rating} ${card.position}`}>
      <div className="fut-card-inner">
        <div className="fut-card-top">
          <span className="fut-rating">{card.rating}</span>
          <span className="fut-pos">{card.position}</span>
          <Img src={card.flag} alt="" className="fut-icon" />
          <Img src={card.badge} alt="" className="fut-icon" />
        </div>
        {card.face && faceOk
          ? <img className="fut-face" src={card.face} alt="" loading="lazy" onError={() => setFaceOk(false)} />
          : <div className="fut-face fut-face-fallback">{card.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}</div>}
        <div className="fut-name">{shortName(card.name)}</div>
      </div>
    </div>
  );
}

/** In-game style chemistry pips: three diamonds, filled up to the player's chemistry. */
export function ChemPips({ chem, inPosition = true }: { chem: number; inPosition?: boolean }) {
  return (
    <div className="flex items-center justify-center gap-[2px]" title={inPosition ? `Chemistry ${chem}` : "Ur position: 0 chemistry"}>
      {[0, 1, 2].map((i) => (
        <span key={i} className={`chem-pip ${i < chem ? "on" : ""} ${inPosition ? "" : "off-pos"}`} />
      ))}
    </div>
  );
}
