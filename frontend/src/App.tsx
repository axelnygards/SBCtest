import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Account } from "./components/Account";
import { ClubView } from "./components/ClubView";
import { Pitch } from "./components/Pitch";
import { RequirementEditor } from "./components/RequirementEditor";
import { RequirementLines, RequirementList } from "./components/RequirementList";
import { SolutionView } from "./components/SolutionView";
import { StreamlinedView } from "./components/StreamlinedView";
import { api, ApiError, getToken, setToken, streamlinedApi, type ClubRow, type Me, type Named,
  type Preset, type Requirement, type Solution, type StreamlinedResult } from "./lib/api";
import { TimeoutError } from "./lib/guard";
import { lookup } from "./lib/reqText";

type Tab = "solve" | "club" | "account";
type Mode = "streamlined" | "puzzle";

const isExpired = (p: Preset) => !!p.expires && new Date(p.expires).getTime() < Date.now();
const panel = "rounded-2xl bg-white/[0.04] p-4 ring-1 ring-white/10 backdrop-blur sm:p-5";
const input = "rounded-lg bg-white/5 px-2.5 py-1.5 text-sm ring-1 ring-white/10 focus:outline-none focus:ring-blue-500";

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-8 w-6 rounded-[3px] bg-gradient-to-b from-amber-200 via-amber-400 to-amber-600 shadow-lg shadow-amber-500/20"
        style={{ clipPath: "polygon(50% 0,86% 3%,100% 10%,100% 86%,50% 100%,0 86%,0 10%,14% 3%)" }} />
      <div className="leading-tight">
        <div className="text-lg font-extrabold tracking-tight">SBC Solver</div>
        <div className="text-[11px] text-slate-400">för EA SPORTS FC 27 Ultimate Team</div>
      </div>
    </div>
  );
}

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
  const [useClub, setUseClub] = useState(true);
  const [onlyClub, setOnlyClub] = useState(false);
  const [alternatives, setAlternatives] = useState(0);
  const [preferUntradeable, setPreferUntradeable] = useState(true);

  const [solving, setSolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [shown, setShown] = useState(0);
  const [solvedFormation, setSolvedFormation] = useState("4-4-2");
  const [streamlined, setStreamlined] = useState<StreamlinedResult | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const [editing, setEditing] = useState(true);
  const [solvedReqs, setSolvedReqs] = useState<Requirement[]>([]);
  const names = useMemo(() => lookup(leagues, nations), [leagues, nations]);

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
    api.health().then((h) => setCards(h.cards)).catch(() => setError("Servern svarar inte. Är Docker igång?"));
    api.leagues().then(setLeagues).catch(() => {});
    api.nations().then(setNations).catch(() => {});
    api.formations().then((f) => setFormations(Object.keys(f))).catch(() => {});
    streamlinedApi.presets().then(setPresets).catch(() => {});
    refreshMe();
  }, [refreshMe]);

  function reset() {
    setSolutions([]);
    setStreamlined(null);
    setError(null);
  }

  function choosePreset(p: Preset) {
    setActivePreset(p);
    reset();
    if (p.kind === "streamlined") {
      setTarget(p.target ?? 0);
      setMinOvr(p.min_ovr ?? 0);
    } else {
      setFormation(p.formation ?? "4-4-2");
      setReqs(p.requirements ?? []);
      setEditing(false);
    }
  }

  async function run() {
    setSolving(true);
    reset();
    try {
      if (mode === "streamlined") {
        setStreamlined(await streamlinedApi.solve({
          target, min_ovr: minOvr, already, use_club: useClub && !!me, buy_from_market: !onlyClub,
        }));
      } else {
        setSolvedFormation(formation);
        setSolvedReqs(reqs);
        setShown(0);
        setSolutions(await api.solve({
          formation, requirements: reqs, use_club: useClub && !!me, only_club: onlyClub && !!me,
          buy_from_market: !onlyClub, alternatives, time_limit_s: 30,
          untradeable_bonus: preferUntradeable ? 50 : 0, excluded_ids: [],
        }));
      }
    } catch (e) {
      setError(e instanceof TimeoutError ? "Ingen lösning hittades inom tidsgränsen." : String((e as Error).message));
    } finally {
      setSolving(false);
      // on phones the result is below the form: bring it into view
      if (window.matchMedia("(max-width: 1023px)").matches)
        resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  const navBtn = (t: Tab, label: string) => (
    <button onClick={() => setTab(t)}
      className={`rounded-full px-3.5 py-1.5 text-sm font-semibold transition ${tab === t ? "bg-white text-slate-900" : "text-slate-300 hover:bg-white/10"}`}>
      {label}
    </button>
  );

  const controls = (
    <div className={`${panel} space-y-4`}>
      <div className="grid grid-cols-2 gap-1 rounded-xl bg-black/30 p-1 text-sm">
        {(["streamlined", "puzzle"] as Mode[]).map((m) => (
          <button key={m} onClick={() => { setMode(m); setActivePreset(null); reset(); }}
            className={`rounded-lg px-2 py-2 font-semibold transition ${mode === m ? "bg-blue-600 text-white shadow" : "text-slate-300 hover:bg-white/5"}`}>
            {m === "streamlined" ? "Poäng-SBC" : "Pussel-SBC"}
          </button>
        ))}
      </div>
      <p className="text-xs leading-relaxed text-slate-400">
        {mode === "streamlined"
          ? "De flesta spelar- och uppgraderings-SBC:er i FC 27: lämna in kort tills du når målpoängen. Bara betyget räknas."
          : "Marquee Matchups, Daily Puzzles och liga/nation-hybrider: chemistry, betyg, ligor och nationer."}
      </p>

      <div>
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Aktuella SBC:er</div>
        <div className="flex flex-wrap gap-1.5">
          {presets.filter((p) => p.kind === mode).map((p) => (
            <button key={p.id} title={`${p.group} · källa: ${p.source}`} onClick={() => choosePreset(p)}
              className={`rounded-full px-3 py-1 text-xs font-medium ring-1 transition ${activePreset?.id === p.id ? "bg-blue-600/20 text-blue-200 ring-blue-500" : "ring-white/15 hover:bg-white/10"} ${isExpired(p) ? "opacity-40" : ""}`}>
              {p.name}{isExpired(p) ? " · utgången" : ""}
            </button>
          ))}
        </div>
        {activePreset && (
          <p className="mt-2 text-[11px] text-slate-500">
            {activePreset.group} · <a className="underline hover:text-slate-300" href={activePreset.source} target="_blank" rel="noreferrer">källa</a>
            {activePreset.expires && ` · utgår ${new Date(activePreset.expires).toLocaleString("sv-SE")}`} · kontrollera kraven i spelet
          </p>
        )}
      </div>

      {mode === "streamlined" ? (
        <div className="space-y-3">
        <RequirementLines title={activePreset?.name ?? "Requirements"} done={!!streamlined && streamlined.status === "OPTIMAL"}
          lines={[`Item Score: ${target.toLocaleString("en-US")}`, ...(minOvr > 0 ? [`Player OVR: Min. ${minOvr}`] : [])]} />
        <div className="grid grid-cols-3 gap-2 text-xs text-slate-400">
          <label className="flex flex-col gap-1">Målpoäng
            <input type="number" className={input} value={target} min={1} onChange={(e) => setTarget(Number(e.target.value))} /></label>
          <label className="flex flex-col gap-1">Min. betyg
            <input type="number" className={input} value={minOvr} min={0} max={99} onChange={(e) => setMinOvr(Number(e.target.value))} /></label>
          <label className="flex flex-col gap-1">Redan inlämnat
            <input type="number" className={input} value={already} min={0} onChange={(e) => setAlready(Number(e.target.value))} /></label>
        </div>
        </div>
      ) : (
        <div className="space-y-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-slate-400">Formation</span>
            <select className={input} value={formation} onChange={(e) => { setFormation(e.target.value); setSolutions([]); }}>
              {formations.map((f) => <option key={f}>{f}</option>)}
            </select>
          </label>
          {reqs.length > 0 && <RequirementList reqs={reqs} names={names} title={activePreset?.name ?? "Requirements"} />}
          <button className="text-xs font-semibold text-blue-300 hover:text-blue-200" onClick={() => setEditing(!editing)}>
            {editing ? "▾ Dölj redigering" : "✎ Redigera krav"}
          </button>
          {editing && <RequirementEditor reqs={reqs} onChange={(r) => { setReqs(r); setActivePreset(null); }} leagues={leagues} nations={nations} />}
        </div>
      )}

      <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-300">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" className="accent-blue-500" checked={useClub} disabled={!me} onChange={(e) => setUseClub(e.target.checked)} />
          Använd min klubb{!me && <span className="text-slate-500"> (skapa konto)</span>}
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" className="accent-blue-500" checked={onlyClub} disabled={!me} onChange={(e) => setOnlyClub(e.target.checked)} />
          Bara min klubb
        </label>
        {mode === "puzzle" && (
          <>
            <label className="flex items-center gap-1.5">
              <input type="checkbox" className="accent-blue-500" checked={preferUntradeable} onChange={(e) => setPreferUntradeable(e.target.checked)} />
              Ej säljbara först
            </label>
            <label className="flex items-center gap-1.5">
              Alternativ
              <select className={input} value={alternatives} onChange={(e) => setAlternatives(Number(e.target.value))}>
                {[0, 1, 2, 3].map((n) => <option key={n}>{n}</option>)}
              </select>
            </label>
          </>
        )}
      </div>

      <button onClick={run} disabled={solving || (mode === "puzzle" ? !reqs.length : target <= 0)}
        className="w-full rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 py-3 font-bold text-white shadow-lg shadow-blue-900/40 transition hover:brightness-110 disabled:opacity-50">
        {solving ? (mode === "puzzle" ? "Bygger truppen…" : "Räknar…") : "Hitta billigaste lösningen"}
      </button>
    </div>
  );

  const result = (
    <div ref={resultRef} className={`${panel} min-h-[300px] scroll-mt-4`}>
      {error && <div className="mb-4 rounded-xl bg-red-500/10 p-3 text-sm text-red-200 ring-1 ring-red-500/30">{error}</div>}
      {mode === "puzzle" ? (
        solutions.length ? (
          <div className="space-y-4">
            {solutions.length > 1 && (
              <div className="flex gap-1.5">
                {solutions.map((_, i) => (
                  <button key={i} onClick={() => setShown(i)}
                    className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${shown === i ? "bg-white text-slate-900 ring-white" : "ring-white/20 hover:bg-white/10"}`}>
                    {i === 0 ? "Billigast" : `Alternativ ${i}`}
                  </button>
                ))}
              </div>
            )}
            <SolutionView sol={solutions[shown]} index={shown} formation={solvedFormation} reqs={solvedReqs} names={names} />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-baseline justify-between">
              <h3 className="text-lg font-bold">{formation}</h3>
              <span className="text-xs text-slate-400">{solving ? "Lösaren arbetar, upp till 30 s…" : "Välj krav och tryck Hitta billigaste lösningen"}</span>
            </div>
            <Pitch formation={formation} loading={solving} />
          </div>
        )
      ) : streamlined ? (
        <StreamlinedView res={streamlined} />
      ) : (
        <div className="grid h-full min-h-[260px] place-items-center text-center text-slate-400">
          <div>
            <div className="mb-3 text-5xl">{solving ? "⏳" : "🎯"}</div>
            <p className="max-w-xs text-sm">Välj en SBC eller ange målpoäng. Du får exakt vilka kort du ska lämna in och köpa, billigast möjligt.</p>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-5 sm:py-8">
      <header className="mb-6 flex flex-wrap items-center gap-3">
        <Logo />
        {cards != null && <span className="hidden rounded-full bg-white/5 px-2.5 py-1 text-xs text-slate-400 ring-1 ring-white/10 sm:inline">FC 27 · {cards.toLocaleString("sv-SE")} kort</span>}
        <nav className="ml-auto flex gap-1 rounded-full bg-white/5 p-1 ring-1 ring-white/10">
          {navBtn("solve", "Lös SBC")}
          {navBtn("club", `Min klubb${me ? ` · ${me.club_size}` : ""}`)}
          {navBtn("account", "Konto")}
        </nav>
      </header>

      {tab === "solve" && (
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(340px,420px)_1fr]">
          {controls}
          {result}
        </div>
      )}
      {tab === "club" && <section className={panel}><ClubView rows={club} /></section>}
      {tab === "account" && <section className={`${panel} max-w-xl`}><Account me={me} onChange={refreshMe} /></section>}

      <footer className="mt-10 text-center text-[11px] leading-relaxed text-slate-500">
        Inte kopplat till eller godkänt av EA. Spelarbilder från EA:s publika betygsdatabas. Priser märkta live kommer från vad
        användare av tillägget sett på transfermarknaden; övriga är uppskattningar. Kontrollera alltid i spelet innan du köper.
      </footer>
    </div>
  );
}
