import type { Named, Op, ReqType, Requirement } from "../lib/api";

const TYPES: { type: ReqType; label: string; ops: Op[]; attrs?: string[] }[] = [
  { type: "team_rating", label: "Lagbetyg", ops: ["min"] },
  { type: "team_chem", label: "Lagets chemistry", ops: ["min"] },
  { type: "player_chem", label: "Chemistry per spelare", ops: ["min"] },
  { type: "count", label: "Antal spelare från/med", ops: ["min", "max", "exact"],
    attrs: ["league", "nation", "club", "rare", "quality", "rarity"] },
  { type: "same", label: "Spelare från samma", ops: ["min", "max"], attrs: ["league", "nation", "club"] },
  { type: "distinct", label: "Olika", ops: ["min", "max", "exact"], attrs: ["league", "nation", "club"] },
];

const ATTR_LABEL: Record<string, string> = {
  league: "liga", nation: "nation", club: "klubb (id)", rare: "sällsynta (rare)",
  quality: "kvalitet", rarity: "raritet",
};
const OP_LABEL: Record<Op, string> = { min: "minst", max: "högst", exact: "exakt" };

interface Props {
  reqs: Requirement[];
  onChange: (r: Requirement[]) => void;
  leagues: Named[];
  nations: Named[];
}

const field = "rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900";

export function RequirementEditor({ reqs, onChange, leagues, nations }: Props) {
  const update = (i: number, patch: Partial<Requirement>) =>
    onChange(reqs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <div className="space-y-2">
      {reqs.map((r, i) => {
        const def = TYPES.find((t) => t.type === r.type)!;
        return (
          <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg bg-white p-2 shadow-sm dark:bg-slate-900">
            <select className={field} value={r.type} aria-label="Krav"
              onChange={(e) => {
                const t = TYPES.find((x) => x.type === e.target.value)!;
                update(i, { type: t.type, op: t.ops[0], attr: t.attrs?.[0] ?? null, values: [] });
              }}>
              {TYPES.map((t) => <option key={t.type} value={t.type}>{t.label}</option>)}
            </select>
            {def.attrs && (
              <select className={field} value={r.attr ?? ""} aria-label="Egenskap"
                onChange={(e) => update(i, { attr: e.target.value, values: [] })}>
                {def.attrs.map((a) => <option key={a} value={a}>{ATTR_LABEL[a]}</option>)}
              </select>
            )}
            {def.ops.length > 1 && (
              <select className={field} value={r.op} aria-label="Jämförelse"
                onChange={(e) => update(i, { op: e.target.value as Op })}>
                {def.ops.map((o) => <option key={o} value={o}>{OP_LABEL[o]}</option>)}
              </select>
            )}
            <input type="number" className={`${field} w-20`} value={r.value} min={0} max={99} aria-label="Värde"
              onChange={(e) => update(i, { value: Number(e.target.value) })} />
            {r.type === "count" && <ValuePicker req={r} leagues={leagues} nations={nations}
              onChange={(values) => update(i, { values })} />}
            <button className="ml-auto text-sm text-slate-500 hover:text-red-600" aria-label="Ta bort krav"
              onClick={() => onChange(reqs.filter((_, j) => j !== i))}>✕</button>
          </div>
        );
      })}
      <button className="text-sm font-medium text-blue-600 hover:underline"
        onClick={() => onChange([...reqs, { type: "team_rating", value: 80, op: "min", values: [] }])}>
        + Lägg till krav
      </button>
    </div>
  );
}

function ValuePicker({ req, leagues, nations, onChange }: {
  req: Requirement; leagues: Named[]; nations: Named[]; onChange: (v: (number | string)[]) => void;
}) {
  if (req.attr === "rare") return null;
  if (req.attr === "quality")
    return (
      <select className={field} value={String(req.values[0] ?? "gold")} onChange={(e) => onChange([e.target.value])}>
        <option value="gold">guld</option><option value="silver">silver</option><option value="bronze">brons</option>
      </select>
    );
  if (req.attr === "rarity")
    return <input className={field} placeholder="t.ex. rare" value={String(req.values[0] ?? "")}
      onChange={(e) => onChange([e.target.value])} />;
  if (req.attr === "club")
    return <input className={`${field} w-28`} placeholder="klubb-id" value={String(req.values[0] ?? "")}
      onChange={(e) => onChange(e.target.value ? [Number(e.target.value)] : [])} />;
  const opts = req.attr === "league" ? leagues : nations;
  return (
    <select className={`${field} max-w-48`} value={String(req.values[0] ?? "")} aria-label="Välj"
      onChange={(e) => onChange(e.target.value ? [Number(e.target.value)] : [])}>
      <option value="">välj…</option>
      {opts.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
    </select>
  );
}
