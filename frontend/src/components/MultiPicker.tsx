import { useMemo, useRef, useState } from "react";

export interface PickItem {
  id: number;
  name: string;
  img?: string | null;
}

/** Searchable multi-select with chips (league / nation / club filters). */
export function MultiPicker({ label, items, value, onChange, placeholder }: {
  label: string; items: PickItem[]; value: number[]; onChange: (v: number[]) => void; placeholder: string;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const byId = useMemo(() => new Map(items.map((i) => [i.id, i])), [items]);
  const hits = useMemo(() => {
    const s = q.trim().toLowerCase();
    return items.filter((i) => !value.includes(i.id) && (!s || i.name.toLowerCase().includes(s))).slice(0, 40);
  }, [items, q, value]);

  return (
    <div ref={box} className="relative" onBlur={(e) => { if (!box.current?.contains(e.relatedTarget as Node)) setOpen(false); }}>
      <div className="label mb-1.5">{label}</div>
      <div className="field flex min-h-[40px] flex-wrap items-center gap-1.5 !py-1.5">
        {value.map((id) => (
          <span key={id} className="flex items-center gap-1 rounded-full bg-neon-cyan/10 py-0.5 pl-2 pr-1 text-xs text-cyan-100 ring-1 ring-neon-cyan/40">
            {byId.get(id)?.img && <img src={byId.get(id)!.img!} alt="" className="h-3.5 w-auto" />}
            {byId.get(id)?.name ?? id}
            <button className="grid h-4 w-4 place-items-center rounded-full hover:bg-white/10" aria-label="Ta bort"
              onClick={() => onChange(value.filter((v) => v !== id))}>×</button>
          </span>
        ))}
        <input className="min-w-[90px] flex-1 bg-transparent py-0.5 text-sm outline-none placeholder:text-slate-500"
          value={q} placeholder={value.length ? "" : placeholder}
          onFocus={() => setOpen(true)} onChange={(e) => { setQ(e.target.value); setOpen(true); }} />
      </div>
      {open && hits.length > 0 && (
        <div className="glass absolute z-30 mt-1.5 max-h-60 w-full overflow-auto !rounded-xl p-1">
          {hits.map((i) => (
            <button key={i.id} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm hover:bg-white/10"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => { onChange([...value, i.id]); setQ(""); }}>
              {i.img ? <img src={i.img} alt="" className="h-4 w-5 object-contain" /> : <span className="w-5" />}
              {i.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
