import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Account } from "./components/Account";
import { CardSheet, type SheetCard } from "./components/CardSheet";
import { ClubView } from "./components/ClubView";
import { CostTile, Ring } from "./components/Metrics";
import { MultiPicker, type PickItem } from "./components/MultiPicker";
import { OwnPricesPanel } from "./components/OwnPrices";
import { Pitch } from "./components/Pitch";
import { RequirementEditor } from "./components/RequirementEditor";
import { RequirementLines, RequirementList } from "./components/RequirementList";
import { Alternatives, SolutionList } from "./components/SolutionView";
import { StreamlinedCards } from "./components/StreamlinedView";
import { api, ApiError, getToken, setToken, streamlinedApi, type ClubRow, type Me, type Named,
  type Preset, type PriceStatus, type RatingPrice, type Requirement, type Solution, type StreamlinedResult } from "./lib/api";
import { TimeoutError } from "./lib/guard";
import { groupFormations } from "./lib/formations";
import { excludedIds, ownCount, pricesKey, requestPrices, unreportedRatings, useOwnPrices, usePlatform } from "./lib/ownPrices";
import { lookup } from "./lib/reqText";

type Tab = "solve" | "club" | "account";
type Mode = "streamlined" | "puzzle";

const isExpired = (p: Preset) => !!p.expires && new Date(p.expires).getTime() < Date.now();

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-9 w-9">
        <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-neon-purple to-neon-cyan opacity-80 blur-md" />
        <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-ink-0 ring-1 ring-white/15">
          <span className="font-display text-sm font-black tracking-tight text-white">SB</span>
        </div>
      </div>
      <div className="leading-tight">
        <div className="font-display text-[17px] font-extrabold tracking-tight text-white">SBC SOLVER</div>
        <div className="text-[11px] font-medium text-slate-400">EA SPORTS FC 27 · Ultimate Team</div>
      </div>
    </div>
  );
}

function SourceToggle({ on, disabled = false, onClick, title, sub }: {
  on: boolean; disabled?: boolean; onClick: () => void; title: string; sub: string;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-pressed={on}
      className={`lift relative rounded-2xl border p-3 pr-7 text-left disabled:opacity-40 ${on
        ? "border-neon-cyan/60 bg-neon-cyan/10 shadow-[0_0_18px_-6px_rgba(34,211,238,.7)]" : "border-white/10 bg-white/[0.03] hover:border-white/25"}`}>
      <span className={`absolute right-2.5 top-2.5 grid h-4 w-4 place-items-center rounded-full text-[10px] font-black ${on ? "bg-neon-cyan text-black" : "ring-1 ring-white/25"}`}>{on ? "✓" : ""}</span>
      <div className="font-display text-[12.5px] font-bold leading-tight text-white">{title}</div>
      <div className="mt-1 text-[11px] text-slate-400">{sub}</div>
    </button>
  );
}

function Section({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="space-y-2.5">
      <div className="flex items-center justify-between"><h3 className="label">{title}</h3>{right}</div>
      {children}
    </section>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("solve");
  const [me, setMe] = useState<Me | null>(null);
  const [club, setClub] = useState<ClubRow[]>([]);
  const [leagues, setLeagues] = useState<Named[]>([]);
  const [nations, setNations] = useState<Named[]>([]);
  const [clubs, setClubs] = useState<PickItem[]>([]);
  const [formations, setFormations] = useState<Record<string, string[]>>({});
  const [cards, setCards] = useState<number | null>(null);

  const [presets, setPresets] = useState<Preset[]>([]);
  const [mode, setMode] = useState<Mode>("puzzle");
  const [activePreset, setActivePreset] = useState<Preset | null>(null);
  const [formation, setFormation] = useState("4-4-2");
  const [reqs, setReqs] = useState<Requirement[]>([{ type: "team_rating", value: 84, op: "min", values: [] }]);
  const [editing, setEditing] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<{ league: number[]; nation: number[]; club: number[] }>({ league: [], nation: [], club: [] });
  const [target, setTarget] = useState(2500);
  const [minOvr, setMinOvr] = useState(0);
  const [already, setAlready] = useState(0);
  const [useClub, setUseClub] = useState(true);
  const [useMarket, setUseMarket] = useState(true);
  const [own, updateOwn] = useOwnPrices();
  const [market, setMarket] = useState<RatingPrice[]>([]);
  const [showPrices, setShowPrices] = useState(false);
  const [sheet, setSheet] = useState<SheetCard | null>(null);
  const [solvedKey, setSolvedKey] = useState<string | null>(null);
  const [lastAlts, setLastAlts] = useState(0);
  const [anonPlatform, setAnonPlatform] = usePlatform();
  const [priceStatus, setPriceStatus] = useState<PriceStatus | null>(null);

  const [solving, setSolving] = useState<null | "one" | "alts">(null);
  const [error, setError] = useState<string | null>(null);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [shown, setShown] = useState(0);
  const [solvedFormation, setSolvedFormation] = useState("4-4-2");
  const [solvedReqs, setSolvedReqs] = useState<Requirement[]>([]);
  const [streamlined, setStreamlined] = useState<StreamlinedResult | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
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
    api.clubs().then((cs) => setClubs(cs.map((c) => ({ id: c.id, name: c.name, img: c.badge })))).catch(() => {});
    api.formations().then(setFormations).catch(() => {});
    streamlinedApi.presets().then(setPresets).catch(() => {});
    refreshMe();
  }, [refreshMe]);

  const platform = me?.platform ?? anonPlatform;
  useEffect(() => {
    api.ratingPrices(platform).then(setMarket).catch(() => {});
    api.priceStatus(platform).then(setPriceStatus).catch(() => {});
  }, [platform]);

  async function reportCard(definitionId: number, price: number) {
    try {
      await api.reportPrices({ platform, cards: { [definitionId]: price } });
      return true;
    } catch {
      return false;
    }
  }

  /** Share changed fodder prices (anonymous); never blocks solving. */
  function reportRatings() {
    const ratings = unreportedRatings(own);
    if (!Object.keys(ratings).length) return;
    api.reportPrices({ platform, ratings })
      .then(() => updateOwn((v) => ({ ...v, reported: { ...v.reported, ...ratings } })))
      .catch(() => {});
  }

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

  /** League / nation / club filters: all 11 players must come from the chosen ones. */
  function filterReqs(): Requirement[] {
    return (["league", "nation", "club"] as const)
      .filter((a) => filters[a].length)
      .map((a) => ({ type: "count", value: 11, op: "exact", attr: a, values: filters[a], label: "filter" }));
  }

  async function run(alternatives: number) {
    setSolving(alternatives ? "alts" : "one");
    setLastAlts(alternatives);
    setSolvedKey(pricesKey(own));
    reset();
    reportRatings();
    const prices = requestPrices(own);
    try {
      if (mode === "streamlined") {
        setStreamlined(await streamlinedApi.solve({
          target, min_ovr: minOvr, already, use_club: fromClub, buy_from_market: useMarket,
          prices, excluded_ids: excludedIds(own), platform,
        }));
      } else {
        setSolvedFormation(formation);
        setSolvedReqs(reqs);
        setShown(0);
        setSolutions(await api.solve({
          formation, requirements: [...reqs, ...filterReqs()], use_club: fromClub,
          only_club: fromClub && !useMarket, buy_from_market: useMarket, alternatives, time_limit_s: 30,
          untradeable_bonus: 0, excluded_ids: excludedIds(own), prices, platform,
        }));
      }
    } catch (e) {
      setError(e instanceof TimeoutError ? "Ingen lösning hittades inom tidsgränsen." : String((e as Error).message));
    } finally {
      setSolving(null);
      if (window.matchMedia("(max-width: 1279px)").matches)
        resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  const fromClub = useClub && !!me;
  const noSource = !fromClub && !useMarket;
  const sol = solutions[shown];
  const solOk = sol && ["OPTIMAL", "FEASIBLE"].includes(sol.status);
  const ratingTarget = solvedReqs.find((r) => r.type === "team_rating")?.value ?? null;
  const chemTarget = solvedReqs.find((r) => r.type === "team_chem")?.value ?? null;
  const filterCount = filters.league.length + filters.nation.length + filters.club.length;
  const priceCount = ownCount(own) + excludedIds(own).length;
  const hasResult = solOk || streamlined?.status === "OPTIMAL";
  const outdated = hasResult && !solving && solvedKey !== null && solvedKey !== pricesKey(own);

  // ---------------- left: action panel ----------------
  const actions = (
    <aside className="glass space-y-6 p-5">
      <div className="grid grid-cols-2 gap-1 rounded-2xl bg-black/40 p-1">
        {(["puzzle", "streamlined"] as Mode[]).map((m) => (
          <button key={m} onClick={() => { setMode(m); setActivePreset(null); reset(); }}
            className={`rounded-xl px-2 py-2.5 font-display text-[13px] font-bold transition ${mode === m
              ? "bg-white/10 text-white shadow-[inset_0_0_0_1px_rgba(34,211,238,.5),0_0_18px_-6px_rgba(34,211,238,.7)]" : "text-slate-400 hover:text-white"}`}>
            {m === "puzzle" ? "Pussel-SBC" : "Poäng-SBC"}
          </button>
        ))}
      </div>

      <Section title="Aktuella SBC:er">
        <div className="flex flex-wrap gap-1.5">
          {presets.filter((p) => p.kind === mode).map((p) => (
            <button key={p.id} title={`${p.group} · källa: ${p.source}`} onClick={() => choosePreset(p)}
              className={`chip-btn ${activePreset?.id === p.id ? "active" : ""} ${isExpired(p) ? "opacity-40" : ""}`}>
              {p.name}
            </button>
          ))}
        </div>
        {activePreset && (
          <p className="text-[11px] text-slate-500">
            {activePreset.group} · <a className="underline hover:text-neon-cyan" href={activePreset.source} target="_blank" rel="noreferrer">källa</a>
            {activePreset.expires && ` · ${isExpired(activePreset) ? "utgången" : "utgår " + new Date(activePreset.expires).toLocaleString("sv-SE")}`}
          </p>
        )}
      </Section>

      {mode === "puzzle" ? (
        <>
          <Section title="Krav" right={
            <button className="text-[11px] font-semibold text-neon-cyan hover:underline" onClick={() => setEditing(!editing)}>
              {editing ? "Klar" : "Redigera"}
            </button>}>
            {editing
              ? <RequirementEditor reqs={reqs} onChange={(r) => { setReqs(r); setActivePreset(null); }} leagues={leagues} nations={nations} />
              : <RequirementList reqs={reqs} names={names} title={activePreset?.name ?? "Egen SBC"} />}
          </Section>

          <Section title="Formation" right={activePreset?.formation === formation
            ? <span className="text-[11px] text-slate-500">SBC:ns standard i spelet</span> : undefined}>
            <select className="field num" value={formation} onChange={(e) => { setFormation(e.target.value); setSolutions([]); }}>
              {groupFormations(Object.keys(formations)).map(([group, names]) => (
                <optgroup key={group} label={group}>
                  {names.map((f) => <option key={f} value={f}>{f}{activePreset?.formation === f ? "  (standard)" : ""}</option>)}
                </optgroup>
              ))}
            </select>
          </Section>

          <Section title={`Filter${filterCount ? ` · ${filterCount} valda` : ""}`} right={
            <span className="flex gap-3">
              {filterCount > 0 && <button className="text-[11px] text-slate-400 hover:text-white" onClick={() => setFilters({ league: [], nation: [], club: [] })}>Rensa</button>}
              <button className="text-[11px] font-semibold text-neon-cyan hover:underline" onClick={() => setShowFilters(!showFilters)}>
                {showFilters ? "Dölj" : "Liga · nation · klubb"}
              </button>
            </span>}>
            {showFilters && <>
            <MultiPicker label="Ligor" placeholder="Sök liga…" items={leagues} value={filters.league}
              onChange={(v) => setFilters({ ...filters, league: v })} />
            <MultiPicker label="Nationer" placeholder="Sök nation…" items={nations} value={filters.nation}
              onChange={(v) => setFilters({ ...filters, nation: v })} />
            <MultiPicker label="Klubbar" placeholder="Sök klubb…" items={clubs} value={filters.club}
              onChange={(v) => setFilters({ ...filters, club: v })} />
            <p className="text-[11px] text-slate-500">Alla 11 spelare måste komma från de valda ligorna, nationerna och klubbarna.</p>
            </>}
          </Section>
        </>
      ) : (
        <Section title="Krav">
          <RequirementLines title={activePreset?.name ?? "Egen SBC"} done={streamlined?.status === "OPTIMAL"}
            lines={[`Item Score: ${target.toLocaleString("en-US")}`, ...(minOvr > 0 ? [`Player OVR: Min. ${minOvr}`] : [])]} />
          <div className="grid grid-cols-3 gap-2">
            <label><span className="label mb-1 block">Mål</span>
              <input type="number" className="field num" value={target} min={1} onChange={(e) => setTarget(Number(e.target.value))} /></label>
            <label><span className="label mb-1 block">Min OVR</span>
              <input type="number" className="field num" value={minOvr} min={0} max={99} onChange={(e) => setMinOvr(Number(e.target.value))} /></label>
            <label><span className="label mb-1 block">Inlämnat</span>
              <input type="number" className="field num" value={already} min={0} onChange={(e) => setAlready(Number(e.target.value))} /></label>
          </div>
        </Section>
      )}

      <Section title={`Egna priser${priceCount ? ` · ${priceCount}` : ""}${priceCount && !own.enabled ? " (av)" : ""}`} right={
        <button className="text-[11px] font-semibold text-neon-cyan hover:underline" onClick={() => setShowPrices(!showPrices)}>
          {showPrices ? "Dölj" : "Pris per betyg · spelare"}
        </button>}>
        {showPrices && <OwnPricesPanel value={own} update={updateOwn} market={market} />}
      </Section>

      <Section title="Hämta spelare från">
        <div className="grid grid-cols-2 gap-2">
          <SourceToggle on={fromClub} disabled={!me} onClick={() => setUseClub(!useClub)} title="Min klubb"
            sub={me ? `${me.club_size} spelare` : "Skapa konto under Konto"} />
          <SourceToggle on={useMarket} onClick={() => setUseMarket(!useMarket)} title={"Transfer\u00admarknaden"}
            sub="Köp det som saknas" />
        </div>
        <p className="text-[11px] leading-relaxed text-slate-500">
          {noSource ? <span className="text-rose-300">Välj minst en källa.</span>
            : fromClub ? "Ej säljbara kort används först. Säljbara kort räknas som vad du skulle få om du sålde dem (−5 % skatt), så dyra kort sparas när det är billigare att köpa."
            : "Allt köps på transfermarknaden."}
        </p>
      </Section>

      <div className="space-y-2.5">
        <button className="btn-primary" onClick={() => run(0)} disabled={!!solving || noSource || (mode === "puzzle" ? !reqs.length : target <= 0)}>
          {solving === "one" ? "Beräknar…" : "Beräkna lösning"}
        </button>
        {mode === "puzzle" && (
          <button className="btn-ghost" onClick={() => run(2)} disabled={!!solving || noSource || !reqs.length}>
            {solving === "alts" ? "Beräknar alternativ…" : "Beräkna alternativ"}
          </button>
        )}
      </div>
    </aside>
  );

  // ---------------- right: data dashboard ----------------
  const dashboard = mode === "puzzle" ? (
    <div className="space-y-4">
      {solOk ? (
        <>
          <CostTile coins={sol.total_cost} estimatedShare={sol.estimated_cost_share} ownShare={sol.own_cost_share}
            status={sol.status} time={sol.wall_time_s} ownedValue={sol.owned_value} cachedAge={sol.cached_age_s} />
          <div className="glass-inset grid grid-cols-3 gap-2 px-2 py-4">
            <Ring value={sol.team_rating} max={99} target={ratingTarget} label="Betyg" sub={ratingTarget ? `mål ${ratingTarget}` : undefined} size={84} />
            <Ring value={sol.team_chem} max={33} target={chemTarget} label="Chem" sub={chemTarget ? `mål ${chemTarget}` : "/ 33"} size={84} />
            <Ring value={sol.slots.filter((s) => !s.owned).length} max={11} label="Köp" sub="/ 11" size={84} />
          </div>
          {sol.requirements?.length >= solvedReqs.length && solvedReqs.length > 0 && (
            <RequirementList reqs={solvedReqs} names={names} status={sol.requirements.slice(0, solvedReqs.length)}
              title={activePreset?.name ?? "Krav"} />
          )}
          <Alternatives sols={solutions} shown={shown} onShow={setShown} />
        </>
      ) : (
        <div className="glass-inset p-5 text-sm text-slate-400">
          {sol ? <span className="text-rose-200">{sol.message || "Ingen lösning hittades."}</span>
            : solving ? "Lösaren arbetar, upp till 30 s…" : "Kostnad, betyg och chemistry visas här när truppen är beräknad."}
        </div>
      )}
    </div>
  ) : (
    <div className="space-y-4">
      {streamlined?.status === "OPTIMAL" ? (
        <>
          <CostTile coins={streamlined.total_coins} estimatedShare={streamlined.estimated_cost_share}
            ownShare={streamlined.own_cost_share} status="OPTIMAL" />
          <div className="glass-inset grid place-items-center py-5">
            <Ring value={streamlined.points} max={Math.max(streamlined.target, 1)} target={streamlined.target} label="Item Score"
              sub={`mål ${streamlined.target.toLocaleString("sv-SE")}`} size={120} />
          </div>
        </>
      ) : (
        <div className="glass-inset p-5 text-sm text-slate-400">
          {streamlined ? <span className="text-rose-200">{streamlined.message}</span>
            : "Välj en SBC eller ange målpoäng. Du får exakt vilka kort du ska lämna in och köpa, billigast möjligt."}
        </div>
      )}
    </div>
  );

  // ---------------- centre: pitch / cards ----------------
  const centre = (
    <div ref={resultRef} className="glass scroll-mt-4 p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="label">{mode === "puzzle" ? "Uppställning" : "Inlämning"}</div>
          <div className="font-display text-xl font-extrabold text-white">
            {mode === "puzzle" ? (solOk ? solvedFormation : formation) : activePreset?.name ?? "Poäng-SBC"}
          </div>
        </div>
        {mode === "puzzle" && solOk && (
          <div className="text-right">
            <div className="label">Kostnad</div>
            <div className="num text-xl font-extrabold text-white">{sol.total_cost.toLocaleString("sv-SE")}</div>
          </div>
        )}
      </div>
      {error && <div className="mb-4 rounded-xl bg-rose-500/10 p-3 text-sm text-rose-200 ring-1 ring-rose-500/30">{error}</div>}
      {outdated && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-xl bg-neon-purple/10 px-3.5 py-2.5 text-[13px] text-violet-100 ring-1 ring-neon-purple/40">
          <span>Dina priser eller val har ändrats sedan beräkningen.</span>
          <button className="shrink-0 font-semibold text-white underline-offset-2 hover:underline" onClick={() => run(lastAlts)}>Beräkna igen</button>
        </div>
      )}
      {mode === "puzzle" ? (
        <div className="space-y-4">
          <div className="mx-auto max-w-[640px]">
            <Pitch positions={formations[solOk ? solvedFormation : formation] ?? []} slots={solOk ? sol.slots : undefined}
              loading={!!solving} onSelect={setSheet} />
          </div>
          {solOk && (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <SolutionList sol={sol} />
              <span className="text-[11px] text-slate-500">Köpt korten? Klicka på ett kort och ange vad det kostade, så blir priserna bättre för alla.</span>
            </div>
          )}
        </div>
      ) : streamlined ? (
        <StreamlinedCards res={streamlined} onSelect={setSheet} />
      ) : (
        <div className="grid min-h-[320px] place-items-center text-center text-slate-500">
          <p className="max-w-xs text-sm">{solving ? "Räknar…" : "Korten du ska lämna in och köpa visas här."}</p>
        </div>
      )}
    </div>
  );

  const navBtn = (t: Tab, label: string) => (
    <button onClick={() => setTab(t)}
      className={`rounded-full px-4 py-1.5 font-display text-[13px] font-bold transition ${tab === t
        ? "bg-white text-ink-0 shadow-[0_0_20px_-4px_rgba(255,255,255,.5)]" : "text-slate-300 hover:text-white"}`}>
      {label}
    </button>
  );

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-5 sm:px-6 sm:py-7">
      <header className="mb-6 flex flex-wrap items-center gap-4">
        <Logo />
        {cards != null && (
          <span className="glass hidden !rounded-full px-3 py-1 text-[11px] text-slate-400 md:inline">
            <span className="text-neon-green">●</span> <span className="num">{cards.toLocaleString("sv-SE")}</span> spelare · FC 27
          </span>
        )}
        {priceStatus && (
          <span className="glass hidden !rounded-full px-3 py-1 text-[11px] text-slate-400 lg:inline"
            title={`Senaste dygnet: ${priceStatus.observations_24h} prisobservationer från ${priceStatus.reporters_24h} användare. Kort utan livepris får en uppskattning från liknande kort.`}>
            <span className={priceStatus.live_cards ? "text-neon-cyan" : "text-amber-300"}>●</span>{" "}
            <span className="num">{priceStatus.live_cards.toLocaleString("sv-SE")}</span> livepriser ·{" "}
            <span className="num">{priceStatus.cards_24h.toLocaleString("sv-SE")}</span> kort prissatta i dag
          </span>
        )}
        <div className="glass ml-auto flex gap-1 !rounded-full p-1" title={me ? "Plattform från ditt konto" : "Priserna skiljer sig mellan plattformar"}>
          {(["console", "pc"] as const).map((pf) => (
            <button key={pf} disabled={!!me} onClick={() => setAnonPlatform(pf)}
              className={`rounded-full px-3 py-1.5 font-display text-[12px] font-bold transition disabled:cursor-default ${platform === pf
                ? "bg-white/15 text-white" : "text-slate-400 hover:text-white disabled:opacity-40"}`}>
              {pf === "console" ? "PS / Xbox" : "PC"}
            </button>
          ))}
        </div>
        <nav className="glass flex gap-1 !rounded-full p-1">
          {navBtn("solve", "Lös SBC")}
          {navBtn("club", `Klubb${me ? ` · ${me.club_size}` : ""}`)}
          {navBtn("account", "Konto")}
        </nav>
      </header>

      {tab === "solve" && (
        <div className="grid items-start gap-5 lg:grid-cols-[360px_minmax(0,1fr)] xl:grid-cols-[350px_minmax(0,1fr)_340px]">
          {actions}
          <div className="space-y-5">
            {centre}
            <div className="xl:hidden">{dashboard}</div>
          </div>
          <div className="hidden xl:block">{dashboard}</div>
        </div>
      )}
      {tab === "club" && <section className="glass p-5"><ClubView rows={club} /></section>}
      {tab === "account" && <section className="glass max-w-xl p-5"><Account me={me} onChange={refreshMe} /></section>}

      {sheet && <CardSheet card={sheet} own={own} update={updateOwn} onClose={() => setSheet(null)} onRecalc={() => run(lastAlts)} onReport={reportCard} />}

      <footer className="mt-10 text-center text-[11px] leading-relaxed text-slate-500">
        Inte kopplat till eller godkänt av EA. Spelarbilder från EA:s publika betygsdatabas. Live-priser kommer från vad
        användare av tillägget sett på transfermarknaden; övriga är uppskattningar. Kontrollera alltid i spelet innan du köper.
      </footer>
    </div>
  );
}
