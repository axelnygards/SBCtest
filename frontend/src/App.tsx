import { useCallback, useEffect, useState } from "react";

import { Account } from "./components/Account";
import { ClubView } from "./components/ClubView";
import { RequirementEditor } from "./components/RequirementEditor";
import { SolutionView } from "./components/SolutionView";
import { StreamlinedView } from "./components/StreamlinedView";
import { api, ApiError, getToken, setToken, streamlinedApi, type ClubRow, type Me, type Named,
  type Preset, type Requirement, type Solution, type StreamlinedResult } from "./lib/api";
import { TimeoutError } from "./lib/guard";

type Tab = "solve" | "club" | "account";
type Mode = "streamlined" | "puzzle";

const isExpired = (p: Preset) => !!p.expires && new Date(p.expires).getTime() < Date.now();

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

  const [presets, setPresets] = useState<Preset[]>([]);
  const [mode, setMode] = useState<Mode>("streamlined");
  const [activePreset, setActivePreset] = useState<Preset | null>(null);
  const [formation, setFormation] = useState("4-4-2");
  const [reqs, setReqs] = useState<Requirement[]>([{ type: "team_rating", value: 84, op: "min", values: [] }]);
  const [target, setTarget] = useState(2500);
  const [minOvr, setMinOvr] = useState(0);
  const [already, setAlready] = useState(0);
  const [streamlined, setStreamlined] = useState<StreamlinedResult | null>(null);
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
    streamlinedApi.presets().then(setPresets).catch(() => {});
    refreshMe();
  }, [refreshMe]);

  function choosePreset(p: Preset) {
    setActivePreset(p);
    setSolutions([]);
    setStreamlined(null);
    if (p.kind === "streamlined") {
      setTarget(p.target ?? 0);
      setMinOvr(p.min_ovr ?? 0);
    } else {
      setFormation(p.formation ?? "4-4-2");
      setReqs(p.requirements ?? []);
    }
  }

  async function solveStreamlined() {
    setSolving(true);
    setError(null);
    setStreamlined(null);
    try {
      setStreamlined(await streamlinedApi.solve({
        target, min_ovr: minOvr, already, use_club: useClub && !!me, buy_from_market: !onlyClub,
      }));
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setSolving(false);
    }
  }

  async function solve() {
    setSolving(true);
    setError(null);
    setSolutions([]);
    try {
      const res = await api.solve({
        formation, requirements: reqs, use_club: useClub && !!me, only_club: onlyClub && !!me,
        buy_from_market: !onlyClub, alternatives, time_limit_s: 30,
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
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-slate-200 p-1 text-sm dark:bg-slate-800">
            {(["streamlined", "puzzle"] as Mode[]).map((m) => (
              <button key={m} onClick={() => { setMode(m); setActivePreset(null); setSolutions([]); setStreamlined(null); }}
                className={`rounded-md px-2 py-1.5 font-medium ${mode === m ? "bg-white shadow-sm dark:bg-slate-900" : ""}`}>
                {m === "streamlined" ? "Poäng-SBC (de flesta i FC 27)" : "Pussel-SBC (chemistry)"}
              </button>
            ))}
          </div>
          <section className={card}>
            <p className="mb-2 text-xs text-slate-500">
              {mode === "streamlined"
                ? "Spelar- och uppgraderings-SBC:er i FC 27: lämna in kort tills du når målpoängen. Bara betyget räknas."
                : "Marquee Matchups, Daily Puzzles och liga/nation-hybrider: krav på chemistry, betyg, ligor och nationer."}
            </p>
            <div className="mb-3 flex flex-wrap gap-2">
              {presets.filter((p) => p.kind === mode).map((p) => (
                <button key={p.id} title={`${p.group} · källa: ${p.source}`} onClick={() => choosePreset(p)}
                  className={`rounded-full border px-3 py-1 text-xs ${activePreset?.id === p.id ? "border-blue-600 bg-blue-50 dark:bg-blue-950" : "border-slate-300 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"} ${isExpired(p) ? "opacity-50" : ""}`}>
                  {p.name}{isExpired(p) ? " (utgången)" : ""}
                </button>
              ))}
            </div>
            {activePreset && (
              <p className="mb-3 text-xs text-slate-500">
                {activePreset.group} · <a className="underline" href={activePreset.source} target="_blank" rel="noreferrer">källa</a>
                {activePreset.expires && ` · utgår ${new Date(activePreset.expires).toLocaleString("sv-SE")}`}
                {" "}· kontrollera kraven i spelet
              </p>
            )}

            {mode === "streamlined" ? (
              <div className="flex flex-wrap gap-3 text-sm">
                <label className="flex flex-col gap-1">Målpoäng
                  <input type="number" className={`${select} w-32`} value={target} min={1}
                    onChange={(e) => setTarget(Number(e.target.value))} /></label>
                <label className="flex flex-col gap-1">Min. betyg per kort
                  <input type="number" className={`${select} w-24`} value={minOvr} min={0} max={99}
                    onChange={(e) => setMinOvr(Number(e.target.value))} /></label>
                <label className="flex flex-col gap-1">Redan inlämnat
                  <input type="number" className={`${select} w-28`} value={already} min={0}
                    onChange={(e) => setAlready(Number(e.target.value))} /></label>
              </div>
            ) : (
              <>
                <label className="mb-3 flex items-center gap-2 text-sm">
                  Formation
                  <select className={select} value={formation} onChange={(e) => setFormation(e.target.value)}>
                    {formations.map((f) => <option key={f}>{f}</option>)}
                  </select>
                </label>
                <RequirementEditor reqs={reqs} onChange={setReqs} leagues={leagues} nations={nations} />
              </>
            )}

            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={useClub} disabled={!me} onChange={(e) => setUseClub(e.target.checked)} />
                Använd min klubb{!me && " (skapa konto först)"}
              </label>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={onlyClub} disabled={!me} onChange={(e) => setOnlyClub(e.target.checked)} />
                Bara min klubb
              </label>
              {mode === "puzzle" && (
                <>
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
                </>
              )}
            </div>
            <button onClick={mode === "streamlined" ? solveStreamlined : solve}
              disabled={solving || (mode === "puzzle" ? !reqs.length : target <= 0)}
              className="mt-4 w-full rounded-lg bg-blue-600 py-2.5 font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
              {solving ? "Räknar…" : "Hitta billigaste lösningen"}
            </button>
          </section>
          {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</div>}
          {mode === "streamlined" && streamlined && <StreamlinedView res={streamlined} />}
          {mode === "puzzle" && solutions.map((s, i) => <SolutionView key={i} sol={s} index={i} />)}
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
