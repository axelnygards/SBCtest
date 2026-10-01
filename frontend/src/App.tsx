import { useCallback, useEffect, useState } from "react";

import { Account } from "./components/Account";
import { ClubView } from "./components/ClubView";
import { PRESETS, RequirementEditor } from "./components/RequirementEditor";
import { SolutionView } from "./components/SolutionView";
import { api, ApiError, getToken, setToken, type ClubRow, type Me, type Named, type Requirement,
  type Solution } from "./lib/api";
import { TimeoutError } from "./lib/guard";

type Tab = "solve" | "club" | "account";

const card = "rounded-xl bg-white p-4 shadow-sm dark:bg-slate-900";
const select = "rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900";

export default function App() {
  const [tab, setTab] = useState<Tab>("solve");
  const [me, setMe] = useState<Me | null>(null);
  const [club, setClub] = useState<ClubRow[]>([]);
  const [leagues, setLeagues] = useState<Named[]>([]);
  const [nations, setNations] = useState<Named[]>([]);
  const [formations, setFormations] = useState<string[]>(["4-4-2"]);
  const [cards, setCards] = useState<number | null>(null);

  const [formation, setFormation] = useState(PRESETS[0].formation);
  const [reqs, setReqs] = useState<Requirement[]>(PRESETS[0].reqs);
  const [useClub, setUseClub] = useState(true);
  const [onlyClub, setOnlyClub] = useState(false);
  const [alternatives, setAlternatives] = useState(0);
  const [preferUntradeable, setPreferUntradeable] = useState(true);

  const [solving, setSolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [solutions, setSolutions] = useState<Solution[]>([]);

  const refreshMe = useCallback(async () => {
    if (!getToken()) return setMe(null), setClub([]);
    try {
      setMe(await api.me());
      setClub(await api.club());
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setToken(null);
      setMe(null);
    }
  }, []);

  useEffect(() => {
    api.health().then((h) => setCards(h.cards)).catch(() => setError("Servern svarar inte."));
    api.leagues().then(setLeagues).catch(() => {});
    api.nations().then(setNations).catch(() => {});
    api.formations().then((f) => setFormations(Object.keys(f))).catch(() => {});
    refreshMe();
  }, [refreshMe]);

  async function solve() {
    setSolving(true);
    setError(null);
    setSolutions([]);
    try {
      const res = await api.solve({
        formation, requirements: reqs, use_club: useClub && !!me, only_club: onlyClub && !!me,
        buy_from_market: !onlyClub, alternatives, time_limit_s: 20,
        untradeable_bonus: preferUntradeable ? 50 : 0, excluded_ids: [],
      });
      setSolutions(res);
    } catch (e) {
      setError(e instanceof TimeoutError ? "Ingen lösning hittades inom tidsgränsen." : String((e as Error).message));
    } finally {
      setSolving(false);
    }
  }

  const tabBtn = (t: Tab, label: string) => (
    <button onClick={() => setTab(t)}
      className={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === t ? "bg-blue-600 text-white" : "hover:bg-slate-200 dark:hover:bg-slate-800"}`}>
      {label}
    </button>
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">FUT SBC Solver</h1>
        <span className="text-xs text-slate-500">FC 27{cards ? ` · ${cards.toLocaleString("sv-SE")} kort` : ""}</span>
        <nav className="ml-auto flex gap-1">
          {tabBtn("solve", "Lös SBC")}
          {tabBtn("club", `Min klubb${me ? ` (${me.club_size})` : ""}`)}
          {tabBtn("account", "Konto")}
        </nav>
      </header>

      {tab === "solve" && (
        <div className="space-y-4">
          <section className={card}>
            <div className="mb-3 flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <button key={p.name} className="rounded-full border border-slate-300 px-3 py-1 text-xs hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
                  onClick={() => { setFormation(p.formation); setReqs(p.reqs); setSolutions([]); }}>
                  {p.name}
                </button>
              ))}
            </div>
            <label className="mb-3 flex items-center gap-2 text-sm">
              Formation
              <select className={select} value={formation} onChange={(e) => setFormation(e.target.value)}>
                {formations.map((f) => <option key={f}>{f}</option>)}
              </select>
            </label>
            <RequirementEditor reqs={reqs} onChange={setReqs} leagues={leagues} nations={nations} />
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={useClub} disabled={!me} onChange={(e) => setUseClub(e.target.checked)} />
                Använd min klubb{!me && " (skapa konto först)"}
              </label>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={onlyClub} disabled={!me} onChange={(e) => setOnlyClub(e.target.checked)} />
                Bara min klubb
              </label>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={preferUntradeable} onChange={(e) => setPreferUntradeable(e.target.checked)} />
                Använd ej säljbara först
              </label>
              <label className="flex items-center gap-1.5">
                Alternativ
                <select className={select} value={alternatives} onChange={(e) => setAlternatives(Number(e.target.value))}>
                  {[0, 1, 2, 3].map((n) => <option key={n}>{n}</option>)}
                </select>
              </label>
            </div>
            <button onClick={solve} disabled={solving || !reqs.length}
              className="mt-4 w-full rounded-lg bg-blue-600 py-2.5 font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
              {solving ? "Räknar…" : "Hitta billigaste lösningen"}
            </button>
          </section>
          {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</div>}
          {solutions.map((s, i) => <SolutionView key={i} sol={s} index={i} />)}
        </div>
      )}

      {tab === "club" && <section className={card}><ClubView rows={club} /></section>}
      {tab === "account" && <section className={card}><Account me={me} onChange={refreshMe} /></section>}

      <footer className="mt-8 text-xs text-slate-500">
        Inte kopplat till eller godkänt av EA. Priser märkta "live" kommer från vad användare av tillägget sett på
        transfermarknaden; övriga är uppskattningar. Kontrollera alltid priset i spelet innan du köper.
      </footer>
    </div>
  );
}
