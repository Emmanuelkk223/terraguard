import { useEffect, useRef, useState, type CSSProperties } from "react";
import { api } from "../services/api";
import FireMap from "../components/FireMap";

export type GoTarget = "overview" | "calendar" | "historical" | "sensors" | "anomalies" | "data" | "method";

interface Props {
  onGo: (tab: GoTarget, options?: { steady?: boolean }) => void;
  onSearch: () => void;
  onGuide?: () => void;
  onCountry?: (iso2: string) => void;
}

/** Adds .in to every .reveal element inside the page once it scrolls into view (sections fade and rise in). */
function useReveal(root: React.RefObject<HTMLElement>) {
  useEffect(() => {
    const items = root.current?.querySelectorAll<HTMLElement>(".reveal") ?? [];
    if (!("IntersectionObserver" in window)) { items.forEach((el) => el.classList.add("in")); return; }
    const seen = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); seen.unobserve(e.target); }
    }), { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    items.forEach((el) => seen.observe(el));
    return () => seen.disconnect();
  }, [root]);
}

/** A number that counts up when it first comes into view. */
function CountUp({ to, decimals = 0, suffix = "" }: { to: number; decimals?: number; suffix?: string }) {
  const el = useRef<HTMLSpanElement>(null);
  const [value, setValue] = useState(0);
  useEffect(() => {
    const node = el.current;
    if (!node) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) { setValue(to); return; }
    let frame = 0;
    const seen = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      seen.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / 1600);
        setValue(to * (1 - (1 - t) ** 4));
        if (t < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    });
    seen.observe(node);
    return () => { seen.disconnect(); cancelAnimationFrame(frame); };
  }, [to]);
  return <span ref={el}>{value.toLocaleString("en-GB", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}{suffix}</span>;
}

const ICONS = ["🚨", "🌾", "🔬", "🚒"];
const EMBERS = Array.from({ length: 22 }, (_, i) => ({
  left: `${(i * 37) % 100}%`, delay: `${(i * 0.73) % 7}s`, duration: `${6 + ((i * 1.7) % 6)}s`, size: `${2 + (i % 4)}px`, drift: `${((i % 5) - 2) * 18}px`,
}));
const FLOW = [
  { icon: "🛰️", title: "Two satellite records", text: "MODIS (Terra, Aqua) since 2000 and VIIRS (Suomi-NPP, NOAA-20, NOAA-21) since 2012 see the same fires differently." },
  { icon: "▦", title: "One common grid", text: "Every detection lands in a 1, 2 or 5 km square on a UTC day. One square-day counts once, whoever saw it." },
  { icon: "📅", title: "A fair calendar", text: "Months are compared on the steady satellite set, and 2002–2011 is bridged from MODIS with a stated range." },
  { icon: "⚑", title: "Unusual, explained", text: "Each month is set against the same month in other years, flagged only when far outside, with the reason in words." },
];

interface Audience {
  who: string;
  question: string;
  steps: string[];
  gets: string;
  not: string;
  go: { label: string; tab: GoTarget; steady?: boolean };
}

// The four groups NASA names for this challenge: early-warning and emergency responders, scientists, land managers and firefighters.
const AUDIENCES: Audience[] = [
  {
    who: "Early-warning and emergency responders",
    question: "Is this season already unusual where I work?",
    steps: [
      "Pick your area (or search your town).",
      "On the Overview, read “Right now, compared with earlier years”.",
      "Open Unusual activity to see flagged months and the reason for each.",
    ],
    gets: "How the last weeks, or this month so far, rank against the same dates in every year since 2002, and by how much they differ from normal.",
    not: "Not a live alert. For fires burning right now, use NASA's FIRMS fire map and your local authorities.",
    go: { label: "Check the present against history", tab: "overview" },
  },
  {
    who: "Land managers",
    question: "When does burning start and peak here, and is this year different?",
    steps: [
      "Pick a region, a country or draw your own area on the map.",
      "Open Historical analysis for the burning season and year-by-year comparison.",
      "Open the Burning calendar and click a month to see where it burned.",
    ],
    gets: "The usual burning season for your area, the busiest and quietest years, and a map of which grid squares were active in any month.",
    not: "Does not say whether a fire was a wildfire, a farm burn or something industrial, and does not measure the area burned.",
    go: { label: "See my area's burning season", tab: "historical" },
  },
  {
    who: "Scientists and researchers",
    question: "Can I trust a comparison across MODIS and VIIRS, and how was it built?",
    steps: [
      "Read Methodology for the method, the tests and the limits.",
      "Open Sensor harmonization for agreement, orbit drift, the accuracy check on 2002–2011 and the sensitivity analysis.",
      "Download the CSVs: every file carries its source, method, area and sensor view.",
    ],
    gets: "An open method with its failures shown, a like-for-like comparison, and data you can reuse (calendar, grid cells, daily series and individual hotspots).",
    not: "Not a replacement for validated burned-area or ground data: no accuracy against real fires can be claimed.",
    go: { label: "Read how it was harmonized", tab: "sensors" },
  },
  {
    who: "Firefighters and fire planners",
    question: "Which months and places usually see the most burning detections?",
    steps: [
      "Open the Burning calendar for your area.",
      "Click the months you plan around, and use the map to see where detections clustered.",
      "Download the hotspots for those dates to take into your own maps.",
    ],
    gets: "Seasonal timing and the places that repeatedly show heat, to help plan resources and training.",
    not: "Not an operational tool: it does not track an incident, forecast spread or give real-time positions.",
    go: { label: "Open the burning calendar", tab: "calendar" },
  },
];

const CAN = [
  "See when each area usually burns, and which years were busy or quiet, from 2002 to today.",
  "Find unusual months, each with a plain-language reason, and see whether MODIS and VIIRS each agree.",
  "Compare the latest 14, 30 or 60 days, or the month so far, with the same dates in every earlier year.",
  "Look at Ghana in full detail (1, 2 and 5 km, 16 regions), or any of 15 more West African countries.",
  "Choose any area: a named region or country, a town, a latitude and longitude, or a box you draw.",
  "Download the calendar, grid cells, daily or weekly series, every individual hotspot, a printable report and chart images.",
];

const CANNOT = [
  "Predict future fires or send alerts. It describes the past and flags unusual history.",
  "Show a live fire map. The newest days come from near-real-time data that arrives with a delay and can be revised.",
  "Count individual fires or measure fire size or area burned: one fire can leave many detections.",
  "Tell wildfires, farm burning and industrial heat apart, or say what caused a change.",
  "Be exact for 2002–2011: those months are estimated from MODIS (typical error about 20%) and are drawn dashed.",
  "Give full detail outside Ghana: other countries are country-level on a 5 km grid.",
];

const TIPS: [string, string][] = [
  ["Compare years like for like", "Set Sensor view to the steady set (Terra, Aqua, Suomi-NPP). More satellites joined in 2018 and 2023, so raw counts rise even when fire does not. Flags already use the steady set."],
  ["Read the dashed and hatched squares", "Dashed squares are estimates (before VIIRS existed). Hatched squares are months without complete data and are never scored."],
  ["Use the reason, not just the flag", "Click an unusual month: it shows its size, the typical value, how many years were compared and why it was or was not flagged."],
  ["Mind the small areas", "A 10 km box has few detections, so percentages swing widely. A bigger area gives steadier answers."],
  ["Try the hotspot switch carefully", "“Hotspots detected” shows raw detections. MODIS and VIIRS count differently, so compare hotspots only within one sensor view."],
  ["Take the evidence with you", "Every export names its source, method, area and dates, so a colleague can see exactly what the numbers are."],
];

export default function Landing({ onGo, onSearch, onGuide, onCountry }: Props) {
  const page = useRef<HTMLElement>(null);
  useReveal(page);
  const [asOf, setAsOf] = useState<string | null>(null);
  useEffect(() => {
    api.currentComparison({ grid: "5km", region: "Ghana", bbox: null, sensor: "harmonized" }, 30)
      .then((d) => setAsOf(d.as_of))
      .catch(() => setAsOf(null));
  }, []);
  const latest = asOf ? new Date(`${asOf}T00:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }) : "today";

  return (
    <section className="landing" ref={page}>
      <div className="lhero">
        <div className="lhero-sky" aria-hidden="true">
          <span className="aurora a1" /><span className="aurora a2" /><span className="aurora a3" />
          {EMBERS.map((e, i) => (
            <i key={i} className="ember" style={{ left: e.left, animationDelay: e.delay, animationDuration: e.duration, width: e.size, height: e.size, ["--drift" as string]: e.drift } as CSSProperties} />
          ))}
        </div>
        <div className="lhero-text">
          <div className="kicker lhero-kicker"><span className="live-dot" aria-hidden="true" /> NASA satellite fire history · Ghana first, all of West Africa</div>
          <h2 className="lhero-title">
            Is this month’s burning <span className="lhero-hot">unusual</span>
            <br />compared with history?
          </h2>
          <p className="land-lead lhero-lead">
            TerraGuard turns NASA’s two fire-satellite records, MODIS and VIIRS, which cannot simply be added together, into one fair burning calendar from 2002 to today.
            Pick a place and see when it usually burns, how now compares with the past, and download the evidence.
          </p>
          <div className="land-actions lhero-actions">
            <button type="button" className="primary lhero-cta" onClick={() => onGo("calendar")}>Open the burning calendar <span aria-hidden="true">→</span></button>
            <button type="button" className="tool" onClick={onSearch}>🔎 Search my town</button>
            {onGuide && <button type="button" className="tool lhero-guide" onClick={onGuide}>🤖 Ask TerraGuide</button>}
          </div>
          <ul className="lhero-stats" aria-label="At a glance">
            <li><b><CountUp to={24} suffix=" yrs" /></b><span>Aug 2002 – {latest}</span></li>
            <li><b><CountUp to={16} /></b><span>countries, Ghana in full detail</span></li>
            <li><b><CountUp to={5} /></b><span>satellites, all counted</span></li>
            <li><b><CountUp to={18.9} decimals={1} suffix="M" /></b><span>active cell-days mapped</span></li>
          </ul>
        </div>
        <div className="lhero-map">
          <FireMap onPick={onCountry ? (iso2) => onCountry(iso2) : undefined} />
        </div>
      </div>

      <h3 className="reveal">How TerraGuard works</h3>
      <ol className="flow">
        {FLOW.map((f, i) => (
          <li key={f.title} className="flow-step reveal" style={{ ["--i" as string]: i } as CSSProperties}>
            <span className="flow-icon" aria-hidden="true">{f.icon}</span>
            <b>{f.title}</b>
            <p>{f.text}</p>
          </li>
        ))}
      </ol>

      <h3 className="reveal">Who it is for, and where to start</h3>
      <div className="aud-grid">
        {AUDIENCES.map((a, i) => (
          <article key={a.who} className="aud-card reveal" style={{ ["--i" as string]: i } as CSSProperties}>
            <span className="aud-icon" aria-hidden="true">{ICONS[i]}</span>
            <h4>{a.who}</h4>
            <p className="aud-q">“{a.question}”</p>
            <ol>
              {a.steps.map((s) => <li key={s}>{s}</li>)}
            </ol>
            <p><b>You get:</b> {a.gets}</p>
            <p className="aud-not"><b>Keep in mind:</b> {a.not}</p>
            <button type="button" className="tool" onClick={() => onGo(a.go.tab, { steady: a.go.steady })}>{a.go.label} →</button>
          </article>
        ))}
      </div>

      <h3 className="reveal">Start in four steps</h3>
      <ol className="land-steps reveal">
        <li><b>Choose a place.</b> Search a town, type a latitude and longitude such as <code>6.69, -1.62</code>, pick an area from the menu (Ghana first), or draw a box on the map.</li>
        <li><b>Choose what to compare.</b> Sensor view: all satellites, the steady set (best for comparing years), MODIS only or VIIRS only.</li>
        <li><b>Read the calendar.</b> One square per month; brighter means more burning. ▲ ▼ mark unusual months, dashed squares are estimates, +N20 and +N21 mark when extra satellites joined.</li>
        <li><b>Click and download.</b> Click a month for its map and the comparison with other years, then download the data, every hotspot or a report.</li>
      </ol>

      <h3 className="reveal">What you can and cannot get</h3>
      <div className="can-grid">
        <div className="can-card yes reveal">
          <h4>You can</h4>
          <ul>{CAN.map((t) => <li key={t}>{t}</li>)}</ul>
        </div>
        <div className="can-card no reveal" style={{ ["--i" as string]: 1 } as CSSProperties}>
          <h4>You cannot</h4>
          <ul>{CANNOT.map((t) => <li key={t}>{t}</li>)}</ul>
        </div>
      </div>

      <h3 className="reveal">Get the most out of it</h3>
      <div className="tip-grid">
        {TIPS.map(([head, body], i) => (
          <div key={head} className="tip-card reveal" style={{ ["--i" as string]: i } as CSSProperties}>
            <b>{head}</b>
            <p>{body}</p>
          </div>
        ))}
      </div>

      <h3 className="reveal">How it is calculated, in short</h3>
      <div className="calc-grid reveal">
        <div className="tip-card"><b>One unit</b><p>An <i>active cell-day</i> is one grid square (1, 2 or 5 km) on one UTC day with at least one detection from any satellite. Monthly value = how many such square-days there were.</p></div>
        <div className="tip-card"><b>Is a month unusual?</b><p>Compare it with the same month in other years on a log scale: z = (ln(1+x) − median) ÷ (1.4826 × MAD). Flag it when |z| passes a threshold tuned so ordinary months are falsely flagged about 1% of the time.</p></div>
        <div className="tip-card"><b>Fair across satellites</b><p>Every satellite is counted, but history is judged on the steady set (Terra, Aqua, Suomi-NPP), because NOAA-20 (2018) and NOAA-21 (2023) raise counts with no extra fire.</p></div>
        <div className="tip-card"><b>2002 to 2011</b><p>VIIRS did not exist, so each month is estimated from MODIS with a line fitted on the years both observed, with a stated range. Hiding later years and predicting them gave about 20% typical error.</p></div>
        <div className="tip-card"><b>Right now vs history</b><p>The latest days, or the month so far, against the same calendar dates in every earlier year: rank, and percent above or below the typical value.</p></div>
        <div className="tip-card"><b>Check it yourself</b><p>The Methodology page has every formula, the constants and the reasons, plus a calculator that recomputes any month in your browser and matches the app.</p></div>
      </div>
      <p className="land-actions"><button type="button" className="tool" onClick={() => onGo("method")}>Open the full technical reference and the calculator →</button></p>

      <h3 className="reveal">Where the detail is</h3>
      <div className="table-wrap reveal">
        <table className="table">
          <thead><tr><th></th><th>Ghana</th><th>The other 15 West African countries</th></tr></thead>
          <tbody>
            <tr><th>Grids</th><td>1, 2 and 5 km</td><td>5 km only</td></tr>
            <tr><th>Areas</th><td>The country and its 16 regions</td><td>Each country, plus a West Africa total</td></tr>
            <tr><th>Rainfall context</th><td>Yes (NASA POWER)</td><td>No</td></tr>
            <tr><th>Sensor checks and sensitivity analysis</th><td>Yes</td><td>Produced for Ghana only</td></tr>
            <tr><th>Your own area or a town</th><td>Yes</td><td>Yes, on the 5 km grid</td></tr>
          </tbody>
        </table>
      </div>

      <p className="land-foot">
        A detection is a heat signal seen by a satellite, <b>not a confirmed fire</b>. TerraGuard describes unusual <i>history</i>; it does not predict fires or replace local reports.
        New to the method? Read the <button type="button" className="link" onClick={() => onGo("method")}>Methodology</button>, or go straight to the
        {" "}<button type="button" className="link" onClick={() => onGo("data")}>data and downloads</button>.
      </p>
    </section>
  );
}
