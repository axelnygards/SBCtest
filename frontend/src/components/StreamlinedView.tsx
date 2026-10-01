import type { StreamlinedCard, StreamlinedResult } from "../lib/api";

const n = (x: number) => x.toLocaleString("sv-SE");

function PriceTag({ c }: { c: StreamlinedCard }) {
  if (c.price_source === "live")
    return <span className="inline-block whitespace-nowrap rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-800 dark:bg-blue-900 dark:text-blue-200">
      live{c.price_age_min != null ? ` · ${c.price_age_min} min` : ""}</span>;
  return <span className="inline-block whitespace-nowrap rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800 dark:bg-amber-900 dark:text-amber-200">
    {c.price_source === "estimate" ? "uppskattat" : "standardpris"}</span>;
}

export function StreamlinedView({ res }: { res: StreamlinedResult }) {
  if (res.status !== "OPTIMAL")
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
      {res.message || "Ingen lösning hittades."}</div>;
  return (
    <div className="space-y-3 rounded-xl bg-white p-4 shadow-sm dark:bg-slate-900">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h3 className="text-lg font-semibold">Billigaste sättet</h3>
        <span className="text-2xl font-bold tabular-nums">{n(res.total_coins)} <span className="text-sm font-normal">mynt</span></span>
        <span className="text-sm text-slate-500">{n(res.points)} / {n(res.target)} poäng · bevisat billigast</span>
      </div>
      {res.message && <p className="text-sm text-slate-600 dark:text-slate-300">{res.message}</p>}
      {res.estimated_cost_share > 0.3 && (
        <p className="rounded-md bg-amber-50 p-2 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          {Math.round(res.estimated_cost_share * 100)} % av kostnaden bygger på uppskattade priser. Kontrollera
          priserna på transfermarknaden innan du köper.
        </p>
      )}
      {res.submit.length > 0 && (
        <section>
          <h4 className="mb-1 text-sm font-semibold">Lämna in från din klubb ({res.submit.length})</h4>
          <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
            {res.submit.map((c) => (
              <li key={c.card_id} className="flex justify-between py-1">
                <span><b className="tabular-nums">{c.rating}</b> {c.name}
                  {c.untradeable && <span className="ml-1 text-xs text-emerald-700 dark:text-emerald-300">ej säljbar</span>}</span>
                <span className="tabular-nums text-slate-500">{n(c.points)} p</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {res.buy.length > 0 && (
        <section>
          <h4 className="mb-1 text-sm font-semibold">Köp på transfermarknaden</h4>
          <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
            {res.buy.map((c) => (
              <li key={c.card_id} className="flex flex-wrap items-center justify-between gap-2 py-1">
                <span>{c.count} × <b className="tabular-nums">{c.rating}</b>-kort
                  <span className="text-slate-500"> (t.ex. {c.name})</span></span>
                <span className="flex items-center gap-2 tabular-nums">
                  {n((c.price ?? 0) * c.count)} <PriceTag c={c} />
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-slate-500">Vilket kort som helst med samma betyg ger samma poäng – köp det billigaste du hittar.</p>
        </section>
      )}
    </div>
  );
}
