import { useEffect, useState } from "react";
import { api } from "../services/api";

export type GoTarget = "overview" | "calendar" | "historical" | "sensors" | "anomalies" | "data" | "method";

interface Props {
  onGo: (tab: GoTarget, options?: { steady?: boolean }) => void;
  onSearch: () => void;
}

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

export default function Landing({ onGo, onSearch }: Props) {
  const [asOf, setAsOf] = useState<string | null>(null);
  useEffect(() => {
    api.currentComparison({ grid: "5km", region: "Ghana", bbox: null, sensor: "harmonized" }, 30)
      .then((d) => setAsOf(d.as_of))
      .catch(() => setAsOf(null));
  }, []);
  const latest = asOf ? new Date(`${asOf}T00:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }) : "today";

  return (
    <section className="landing">
      <div className="land-hero">
        <div className="kicker">Satellite fire history · Ghana first, then all of West Africa</div>
        <h2>Is this month’s burning unusual compared with history?</h2>
        <p className="land-lead">
          TerraGuard turns NASA’s two fire-satellite records (MODIS and VIIRS), which cannot simply be added together, into one fair burning calendar from 2002 to today.
          Pick a place and see when it usually burns, how now compares with the past, and download the evidence.
        </p>
        <div className="land-actions">
          <button type="button" className="primary" onClick={() => onGo("calendar")}>Open the burning calendar →</button>
          <button type="button" className="tool" onClick={() => onGo("overview")}>See the overview</button>
          <button type="button" className="tool" onClick={onSearch}>Search my town</button>
        </div>
        <ul className="land-facts" aria-label="At a glance">
          <li><b>Aug 2002 – {latest}</b><span>fire history</span></li>
          <li><b>16 countries</b><span>Ghana in full detail</span></li>
          <li><b>NASA data</b><span>FIRMS fires, POWER rainfall</span></li>
          <li><b>Free</b><span>CSV, reports, charts</span></li>
        </ul>
      </div>

      <h3>Who it is for, and where to start</h3>
      <div className="aud-grid">
        {AUDIENCES.map((a) => (
          <article key={a.who} className="aud-card">
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

      <h3>Start in four steps</h3>
      <ol className="land-steps">
        <li><b>Choose a place.</b> Search a town, type a latitude and longitude such as <code>6.69, -1.62</code>, pick an area from the menu (Ghana first), or draw a box on the map.</li>
        <li><b>Choose what to compare.</b> Sensor view: all satellites, the steady set (best for comparing years), MODIS only or VIIRS only.</li>
        <li><b>Read the calendar.</b> One square per month; brighter means more burning. ▲ ▼ mark unusual months, dashed squares are estimates, +N20 and +N21 mark when extra satellites joined.</li>
        <li><b>Click and download.</b> Click a month for its map and the comparison with other years, then download the data, every hotspot or a report.</li>
      </ol>

      <h3>What you can and cannot get</h3>
      <div className="can-grid">
        <div className="can-card yes">
          <h4>You can</h4>
          <ul>{CAN.map((t) => <li key={t}>{t}</li>)}</ul>
        </div>
        <div className="can-card no">
          <h4>You cannot</h4>
          <ul>{CANNOT.map((t) => <li key={t}>{t}</li>)}</ul>
        </div>
      </div>

      <h3>Get the most out of it</h3>
      <div className="tip-grid">
        {TIPS.map(([head, body]) => (
          <div key={head} className="tip-card">
            <b>{head}</b>
            <p>{body}</p>
          </div>
        ))}
      </div>

      <h3>How it is calculated, in short</h3>
      <div className="calc-grid">
        <div className="tip-card"><b>One unit</b><p>An <i>active cell-day</i> is one grid square (1, 2 or 5 km) on one UTC day with at least one detection from any satellite. Monthly value = how many such square-days there were.</p></div>
        <div className="tip-card"><b>Is a month unusual?</b><p>Compare it with the same month in other years on a log scale: z = (ln(1+x) − median) ÷ (1.4826 × MAD). Flag it when |z| passes a threshold tuned so ordinary months are falsely flagged about 1% of the time.</p></div>
        <div className="tip-card"><b>Fair across satellites</b><p>Every satellite is counted, but history is judged on the steady set (Terra, Aqua, Suomi-NPP), because NOAA-20 (2018) and NOAA-21 (2023) raise counts with no extra fire.</p></div>
        <div className="tip-card"><b>2002 to 2011</b><p>VIIRS did not exist, so each month is estimated from MODIS with a line fitted on the years both observed, with a stated range. Hiding later years and predicting them gave about 20% typical error.</p></div>
        <div className="tip-card"><b>Right now vs history</b><p>The latest days, or the month so far, against the same calendar dates in every earlier year: rank, and percent above or below the typical value.</p></div>
        <div className="tip-card"><b>Check it yourself</b><p>The Methodology page has every formula, the constants and the reasons, plus a calculator that recomputes any month in your browser and matches the app.</p></div>
      </div>
      <p className="land-actions"><button type="button" className="tool" onClick={() => onGo("method")}>Open the full technical reference and the calculator →</button></p>

      <h3>Where the detail is</h3>
      <div className="table-wrap">
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
