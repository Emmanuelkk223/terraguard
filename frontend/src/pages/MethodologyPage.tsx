import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { CalRow, Selection } from "../types";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const MAD_SCALE = 1.4826;
// Calibrated by simulation (see section 5): the score beyond which an ORDINARY month is flagged about 1% of the time, by number of baseline years.
const THRESHOLDS: Record<number, number> = {
  5: 14.3, 6: 8.1, 7: 7.8, 8: 5.9, 9: 5.8, 10: 5.0, 11: 4.9, 12: 4.4, 13: 4.4, 14: 4.1, 15: 4.0, 16: 3.8, 17: 3.8, 18: 3.7, 19: 3.7, 20: 3.5,
};

const median = (values: number[]): number => {
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
};
const fmt = (n: number, digits = 0) => n.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits });

const TOC: [string, string][] = [
  ["check", "Check any number yourself"],
  ["data", "1. The data and how it is cleaned"],
  ["grid", "2. The grid and the active cell-day"],
  ["complete", "3. Which months count"],
  ["satellites", "4. All satellites and the steady set"],
  ["score", "5. Is a month unusual? The score and its threshold"],
  ["estimate", "6. 2002 to 2011: the estimate"],
  ["now", "7. Right now compared with earlier years"],
  ["seasons", "8. Seasons, yearly totals and regions"],
  ["sensors", "9. MODIS against VIIRS: the statistics"],
  ["sensitivity", "10. Sensitivity analysis"],
  ["ml", "11. Isolation Forest comparison"],
  ["rain", "12. Rainfall context"],
  ["colours", "13. Colours, map and hotspot counts"],
  ["places", "14. Places, coordinates and areas"],
  ["columns", "15. What each exported column means"],
  ["decisions", "16. Our decisions and why"],
  ["limits", "17. Limits"],
];

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <>
      <h3 id={id}>{title}</h3>
      {children}
    </>
  );
}

function Formula({ children }: { children: string }) {
  return <pre className="formula">{children}</pre>;
}

/** Recomputes the unusual-month score for any month from the calendar the page already holds, and compares it with the app's own number. */
function WorkedExample({ rows, selection }: { rows: CalRow[]; selection: Selection | null }) {
  const complete = useMemo(() => rows.filter((r) => r.coverage_ok), [rows]);
  const initial = useMemo<Selection | null>(() => {
    if (selection) return selection;
    const flagged = [...rows].reverse().find((r) => r.status === "unusually_high" || r.status === "unusually_low");
    const pick = flagged ?? complete[complete.length - 1];
    return pick ? { year: pick.year, month: pick.month } : null;
  }, [rows, complete, selection]);
  const [pick, setPick] = useState<Selection | null>(initial);
  useEffect(() => setPick(initial), [initial]);

  if (!rows.length || !pick) return <p className="muted">Load a calendar (choose an area) to try the calculator.</p>;
  const years = [...new Set(complete.map((r) => r.year))].sort((a, b) => a - b);
  const target = rows.find((r) => r.year === pick.year && r.month === pick.month);
  const value = (r: CalRow) => r.scored_cell_days ?? r.active_cell_days;
  const peersRows = rows.filter((r) => r.month === pick.month && r.year !== pick.year && r.coverage_ok);
  const peers = peersRows.map(value);
  const n = peers.length;
  const x = target ? value(target) : null;
  const ok = !!target && target.coverage_ok && n >= 5;
  const logs = peers.map(Math.log1p);
  const medL = n ? median(logs) : NaN;
  const madL = n ? median(logs.map((l) => Math.abs(l - medL))) : NaN;
  const denom = MAD_SCALE * madL;
  const z = ok && x !== null && denom > 0 ? (Math.log1p(x) - medL) / denom : null;
  const medRaw = n ? median(peers) : NaN;
  const pct = ok && x !== null && medRaw > 0 ? ((x - medRaw) / medRaw) * 100 : null;
  const limit = THRESHOLDS[Math.min(20, Math.max(5, n))];
  const matches = z !== null && target?.robust_score != null && Math.abs(z - target.robust_score) < 0.01;

  return (
    <div className="worked">
      <div className="worked-pick">
        <label>Year
          <select value={pick.year} onChange={(e) => setPick({ ...pick, year: Number(e.target.value) })}>
            {years.map((y) => <option key={y}>{y}</option>)}
          </select>
        </label>
        <label>Month
          <select value={pick.month} onChange={(e) => setPick({ ...pick, month: Number(e.target.value) })}>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
        </label>
        <span className="muted small">Uses the area and sensor view selected at the top of the page.</span>
      </div>
      {!target || !target.coverage_ok ? (
        <p className="notice">This month is not complete for the chosen sensor view, so it is never scored.</p>
      ) : n < 5 ? (
        <p className="notice">Only {n} other complete years exist for this calendar month; at least 5 are needed.</p>
      ) : (
        <table className="table narrow">
          <tbody>
            <tr><th>Value x</th><td>{fmt(x ?? 0)}</td><td className="muted">active cell-days of {MONTHS[pick.month - 1]} {pick.year}{target.scored_cell_days !== undefined && target.scored_cell_days !== target.active_cell_days ? ` on the steady set (all satellites: ${fmt(target.active_cell_days)})` : ""}</td></tr>
            <tr><th>Peers P</th><td>{n} values</td><td className="muted">the same calendar month in the other complete years ({peersRows.map((r) => r.year).join(", ")})</td></tr>
            <tr><th>median(P)</th><td>{fmt(medRaw)}</td><td className="muted">typical value; the app shows {target.baseline_median === null ? "–" : fmt(target.baseline_median)}</td></tr>
            <tr><th>Difference</th><td>{pct === null ? "–" : `${pct > 0 ? "+" : ""}${fmt(pct, 1)}%`}</td><td className="muted">(x − median) ÷ median × 100; the app shows {target.pct_diff === null ? "–" : `${fmt(target.pct_diff, 1)}%`}</td></tr>
            <tr><th>median of ln(1+P)</th><td>{fmt(medL, 4)}</td><td className="muted">the typical value on the log scale</td></tr>
            <tr><th>MAD of ln(1+P)</th><td>{fmt(madL, 4)}</td><td className="muted">median of |ln(1+p) − {fmt(medL, 4)}| over the peers</td></tr>
            <tr><th>Score z</th><td><b>{z === null ? "–" : fmt(z, 3)}</b></td><td className="muted">(ln(1+x) − {fmt(medL, 4)}) ÷ (1.4826 × {fmt(madL, 4)}); the app shows {target.robust_score === null ? "–" : fmt(target.robust_score, 3)}</td></tr>
            <tr><th>Threshold</th><td>±{limit}</td><td className="muted">calibrated for {n} baseline years (table in section 5)</td></tr>
            <tr><th>Verdict</th><td><b>{z === null ? "no score (flat baseline)" : Math.abs(z) >= limit ? (z > 0 ? "unusually high" : "unusually low") : "within the usual range"}</b></td><td className="muted">the app says: {target.status.replace(/_/g, " ")}</td></tr>
          </tbody>
        </table>
      )}
      {matches && <p className="worked-ok">Matches the app: your browser has just recomputed the same score from the calendar.</p>}
    </div>
  );
}

interface Props {
  rows: CalRow[];
  selection: Selection | null;
  area: string;
}

export default function MethodologyPage({ rows, selection, area }: Props) {
  return (
    <section className="prose tech">
      <h2>Methodology and calculations</h2>
      <p className="lead">
        Everything TerraGuard computes, with its formulas, the constants we used, and why. You can check the key numbers yourself: the calculator below recomputes any month
        in your browser, and every export carries the columns needed to repeat it in a spreadsheet or in Python.
      </p>
      <nav className="toc" aria-label="Sections of this page">
        {TOC.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
      </nav>

      <Section id="check" title="Check any number yourself">
        <p>
          <b>Live calculator.</b> It takes the calendar currently loaded for <b>{area}</b>, recomputes the unusual-month score from scratch (the formulas are in section 5), and compares it with the number the app shows.
        </p>
        <WorkedExample rows={rows} selection={selection} />
        <p><b>Repeat it outside the app.</b> On the Burning calendar page choose <i>Download calendar CSV</i> (lines starting with # describe the file). In Python:</p>
        <Formula>{`import pandas as pd, numpy as np
cal  = pd.read_csv("terraguard_calendar_Ghana_harmonized_5km.csv", comment="#")
rows = cal[(cal.month == 12) & cal.coverage_ok]            # the same calendar month, complete months only
x    = rows.loc[rows.year == 2025, "scored_cell_days"].iloc[0]
logs = np.log1p(rows.loc[rows.year != 2025, "scored_cell_days"])   # the other years, on the log scale
med  = logs.median();  mad = (logs - med).abs().median()
z    = (np.log1p(x) - med) / (1.4826 * mad)                # -8.417 for December 2025 in Ghana`}</Formula>
        <p className="muted small">In a spreadsheet: take the values of the other years for that month, apply LN(1+value), take MEDIAN and then MEDIAN of the absolute differences from it, and use the formula above.</p>
      </Section>

      <Section id="data" title="1. The data and how it is cleaned">
        <ul>
          <li><b>Source.</b> NASA FIRMS active-fire detections through its area API: MODIS (Terra and Aqua) and VIIRS 375 m (Suomi-NPP, NOAA-20, NOAA-21), standard processing for the archive and near-real-time for the newest weeks. Requests are 5-day windows over Ghana's bounding box (west −3.26, south 4.74, east 1.20, north 11.17) and, for West Africa, over the box −25.61, 4.02, 16.25, 27.61. Raw files are never edited.</li>
          <li><b>A detection</b> is one satellite pixel flagged as a thermal anomaly. It is not a unique fire, not a fire size, and can be an agricultural burn or industrial heat.</li>
          <li><b>Checks.</b> Required fields present; latitude within −90 to 90 and longitude within −180 to 180; a valid time. Time = <code>acq_date</code> + <code>acq_time</code> (HHMM) read as UTC. Exact duplicates (same latitude, longitude, time, satellite, instrument and product) are removed once. Every removed record is logged with its reason, and nothing is imputed.</li>
          <li><b>Confidence classes</b> (kept only within each sensor): MODIS number 0–29 low, 30–79 nominal, 80–100 high; VIIRS letters l, n, h. They are not comparable across sensors. FIRMS type 0 is treated as a presumed vegetation fire.</li>
          <li><b>Clipping.</b> Ghana: the union of geoBoundaries ADM1 outlines, with each detection placed in one of 16 regions by point-in-polygon. West Africa: geoBoundaries national outlines; detections outside all 16 countries are dropped and counted.</li>
        </ul>
      </Section>

      <Section id="grid" title="2. The grid and the active cell-day">
        <p>Every detection is put on a regular grid of equal squares of side <i>s</i> = 1, 2 or 5 km, and on a UTC day.</p>
        <Formula>{`km per degree of latitude   = 110.574
km per degree of longitude  = 111.32 × cos(7.95°) ≈ 110.2     (7.95° = Ghana's centre latitude)
grid_x = floor( longitude × 110.2   / s )
grid_y = floor( latitude  × 110.574 / s )`}</Formula>
        <Formula>{`Active(cell, day) = 1  if MODIS or VIIRS detected anything in that cell on that UTC day, else 0
active_cell_days(month)  =  sum of Active over all cells and all days of the month
modis_cell_days  = same, counting only MODIS            viirs_cell_days = same, counting only VIIRS
both_cell_days   = cells seen by both on the same day    agreement = both_cell_days ÷ active_cell_days`}</Formula>
        <p>
          <b>Why this unit.</b> VIIRS has smaller pixels and reports about 11 times as many detections as MODIS in an average month. Asking only “was this square active on this day?” removes that size gap and counts a place seen by two sensors once.
          It does <b>not</b> make the sensors equivalent and does not count fires. <b>Limits:</b> the grid is fixed at the Ghana latitude, so squares are about 8% narrower than nominal at 25°N, and the squares are a convention, not natural units.
          A grid cell takes the region containing its centre (Ghana) or the country holding most of its detections (West Africa), so border cells are approximate.
        </p>
      </Section>

      <Section id="complete" title="3. Which months count">
        <p>
          A day with no detections is ambiguous (no fire, cloud, no overpass, or missing data), so we never infer a gap from silence. A month is <b>complete</b> only if the <i>downloaded archive</i> covers every day of it for every satellite product that existed by the end of that month.
        </p>
        <Formula>{`coverage_ok = MODIS archive complete  AND  ( VIIRS archives complete  OR  VIIRS did not exist yet )
overlap_ok  = MODIS archive complete  AND  VIIRS archives complete          (both sensors really observing)`}</Formula>
        <ul>
          <li>August 2002 is the first month with both Terra and Aqua, so it is the first month that is compared. Earlier months (Terra only, about half the overpasses) are shown but never scored.</li>
          <li>A region with no detections in a complete month is zero activity, not a gap; leaving it out once biased the baselines.</li>
          <li>The newest month is incomplete until every satellite's data covers it, and is not scored.</li>
        </ul>
      </Section>

      <Section id="satellites" title="4. All satellites and the steady set">
        <p>
          We count <b>every satellite</b> (Terra, Aqua, Suomi-NPP, NOAA-20, NOAA-21) because more satellites mean more chances to see a fire. But NOAA-20 joined in April 2018 and NOAA-21 in March 2023, and extra overpasses raise counts with no change in fire.
          Measured in Ghana (all satellites ÷ steady set, yearly active cell-days): about <b>1.21 in 2018</b>, <b>1.43 to 1.47 in 2019 to 2022</b> and <b>1.66 to 1.77 in 2023 to 2025</b>.
        </p>
        <p>
          So every cell-day also stores its <b>steady-set</b> count (Terra, Aqua and Suomi-NPP only), in <code>steady_cell_days</code>. Judging history on all satellites produced five false “unusually high” months (2019, 2020, 2023, 2024). The rule:
        </p>
        <table className="table narrow">
          <thead><tr><th>Uses all satellites</th><th>Uses the steady set (like for like)</th></tr></thead>
          <tbody>
            <tr><td>Counts shown on the calendar and the map; hotspot downloads; the “Hotspots detected” switch</td><td>The comparison with history, the ▲▼ flags, seasons, the rainfall association, the 2002–2011 estimate, “Right now” against earlier years, sensor-agreement statistics (Suomi-NPP only for VIIRS)</td></tr>
          </tbody>
        </table>
      </Section>

      <Section id="score" title="5. Is a month unusual? The score and its threshold">
        <p>For each area and calendar month (say December), each year is compared with the <b>other</b> years of the same month (leave-one-out), so seasons never count as unusual.</p>
        <Formula>{`x      = the month's steady-set active cell-days
P      = the same calendar month in the other complete years (n values; at least 5 needed)
L      = ln(1 + P)                          (counts are skewed and multiply, so we score on the log scale)
M      = median(L)                          MAD = median( |L − M| )
z      = ( ln(1 + x) − M ) / ( 1.4826 × MAD )
flag   = unusually high if z ≥ T(n),  unusually low if z ≤ −T(n)
difference % = (x − median(P)) / median(P) × 100          (median of the raw values)`}</Formula>
        <ul>
          <li><b>1.4826</b> makes the MAD comparable to a standard deviation when data are bell-shaped. <b>Median and MAD</b> resist outliers; the mean and standard deviation do not.</li>
          <li>The exported <code>baseline_mad</code> is the MAD of the <i>raw</i> peers in cell-days; the score uses the MAD on the <i>log</i> scale. That is why you cannot rebuild z from <code>baseline_mad</code>; use the peers as in the calculator.</li>
          <li><b>Statuses:</b> <code>typical</code>, <code>unusually_high</code>, <code>unusually_low</code>, <code>incomplete_coverage</code> (never scored), <code>insufficient_baseline</code> (fewer than 5 other years), <code>above_flat_baseline</code> / <code>below_flat_baseline</code> (MAD is 0: past years identical, so no score). Where the typical value is under 30 cell-days the app warns that percentage swings are routine.</li>
        </ul>
        <p>
          <b>Why the threshold changes with n.</b> The usual “modified z-score &gt; 3.5” rule assumes a large sample. With only 5 to 20 other years, median/MAD scores have heavy tails: even for perfectly ordinary Gaussian noise, 3.5 falsely flagged about 2% of months with 13 years and about 7% with 7 years.
          We therefore simulated: 400,000 trials per n, baseline and value drawn from a standard normal, z computed as above, and T(n) set to the 99th percentile of |z|, so ordinary months are flagged about 1% of the time (seed 20260101; checked by an automated test).
        </p>
        <table className="table narrow">
          <thead><tr><th>Baseline years n</th>{[5, 6, 7, 8, 9, 10, 12, 13, 15, 17, 20].map((k) => <th key={k}>{k}</th>)}</tr></thead>
          <tbody><tr><th>Threshold T(n)</th>{[5, 6, 7, 8, 9, 10, 12, 13, 15, 17, 20].map((k) => <td key={k}>{THRESHOLDS[k]}</td>)}</tr></tbody>
        </table>
        <p className="muted small">More than 20 years use 3.5; Ghana has 23 to 24 years for most months, so T = 3.5 there. Real series can have heavier tails than Gaussian, so the realised false-flag rate can be higher; flags are a screening aid, not a verdict. Observed result: 72 of 4,774 scored region-months were flagged (1.5%).</p>
      </Section>

      <Section id="estimate" title="6. 2002 to 2011: the estimate">
        <p>VIIRS did not exist yet, so the “either sensor” count cannot be observed. We estimate it from MODIS, separately for each area and calendar month, using the years when both observed (2012 onwards, months with <code>overlap_ok</code>).</p>
        <Formula>{`x = ln(1 + MODIS cell-days)         y = ln(1 + steady-set cell-days)         (one pair per overlap month, 14 or so)
b = slope of y on x, limited to 0.3 … 1.5           a = mean(y) − b × mean(x)
σ = sqrt( Σ (y − a − b·x)² / (n − 2) )
estimate = max( e^(a + b·ln(1+MODIS)) − 1 ,  MODIS )                               (never below what MODIS saw)
90% range = e^(a + b·ln(1+MODIS) ± 1.645 × 3 × σ) − 1                              (floored at MODIS)`}</Formula>
        <ul>
          <li><b>Why a line on the log scale:</b> the relationship between the two counts is multiplicative and changes with the season, so there is one line per calendar month. The slope limit stops 14 points from inventing an implausible slope.</li>
          <li><b>Why target the steady set:</b> it does not change over time, so the relationship is stable. (Before 2018 the steady set and all satellites are the same.)</li>
          <li><b>Why the factor 3:</b> we tested the method by hiding later years. The raw in-sample range covered only 57 to 60% of the hidden months; widening by 3 makes it cover about 90%.</li>
        </ul>
        <table className="table narrow">
          <thead><tr><th>Fitted on</th><th>Predicted</th><th>Hidden months</th><th>Typical error</th><th>Bias</th><th>90% range covers</th></tr></thead>
          <tbody>
            <tr><th>2012–2019</th><td>2020–2026</td><td>75</td><td>17.7%</td><td>+4.7%</td><td>86.7%</td></tr>
            <tr><th>2012–2021</th><td>2022–2026</td><td>58</td><td>21.3%</td><td>+6.9%</td><td>91.4%</td></tr>
            <tr><th>2012–2023</th><td>2024–2026</td><td>34</td><td>20.3%</td><td>+17.0%</td><td>97.1%</td></tr>
          </tbody>
        </table>
        <p className="muted small">Typical error = median of |estimate ÷ truth − 1|. The ratio between MODIS and the combined count drifts upwards over time, which is why the last test is biased high. The estimate assumes the 2012-onward relationship held earlier; that cannot be checked, and it cannot recover fires only VIIRS could see.</p>
      </Section>

      <Section id="now" title="7. Right now compared with earlier years">
        <Formula>{`window       = the last 14, 30 or 60 days of data, or the month so far
current      = active cell-days (steady set) in that window
history(y)   = active cell-days in the same calendar dates of year y, for every earlier year since 2002
median       = median of history        difference % = (current ÷ median − 1) × 100
rank         = 1 + number of earlier years with a larger value
percentile   = share of earlier years with a smaller value`}</Formula>
        <ul>
          <li>The window ends at the <b>earlier</b> of the MODIS and Suomi-NPP archive end dates, so both sensors cover all of it. The newest days come from near-real-time data and can be revised.</li>
          <li>If fewer than 7 days of the new month exist, “this month so far” compares the last full month instead, and says so.</li>
          <li>Years before 2012 are scaled by that month's estimate ratio (estimate ÷ observed), an approximation; they are marked as estimated.</li>
          <li>Counted on the steady set so satellites joining later cannot make the present look busier. The all-satellite figure is shown beside it.</li>
        </ul>
      </Section>

      <Section id="seasons" title="8. Seasons, yearly totals and regions">
        <Formula>{`typical(month m)  = median over complete years of the month's steady-set active cell-days
peak month        = the m with the largest typical value
burning season    = every month with typical(m) ≥ 0.25 × typical(peak month)
share of year     = sum of typical over the season months ÷ sum of typical over all 12 months
yearly total      = sum of the 12 monthly values (a year is complete only if all 12 months are)`}</Formula>
        <p>For Ghana this gives November to February, about 86% of a typical year, peaking in December. The 25% rule is a convention for “clearly active”. In the sensitivity runs the season is November to February in six of seven scenarios and December to January when only high-confidence detections are kept. Regional comparison repeats the same medians for every region.</p>
      </Section>

      <Section id="sensors" title="9. MODIS against VIIRS: the statistics">
        <Formula>{`Spearman ρ    = Pearson correlation of the RANKS of the monthly MODIS and VIIRS values
deseasonalised value  d(m) = ln( (v(m) + 1) / (median of v in that calendar month + 1) )
ratio         = mean over months of ( VIIRS ÷ MODIS )           CV = standard deviation ÷ mean (n−1)
overpass hour = median UTC hour of daytime detections, per satellite and year`}</Formula>
        <ul>
          <li>Computed on months with <code>overlap_ok</code> (both archives complete), using <b>Suomi-NPP</b> for VIIRS so satellite steps do not enter.</li>
          <li><b>Results (Ghana):</b> raw ρ 0.98 for both raw counts and cell-days (seasons dominate); deseasonalised ρ 0.77 (raw detections) and 0.76 (cell-days); VIIRS ÷ MODIS 10.6 for raw detections, 9.1 for cell-days; all VIIRS satellites together are about 19 times MODIS. Cell-days did <b>not</b> make the sensors agree better.</li>
          <li><b>Why rank correlation:</b> it needs no straight-line relationship and is not dominated by a few huge months. <b>Why deseasonalise:</b> both sensors follow the seasons, which inflates any raw correlation; the deseasonalised value measures shared year-to-year change.</li>
          <li>Orbit drift: from 2019 to 2025 Terra's overpass moved about 65 minutes earlier and Aqua's about 65 minutes later. We measure this but do not correct it.</li>
        </ul>
      </Section>

      <Section id="sensitivity" title="10. Sensitivity analysis">
        <p>We re-run the whole method under other reasonable choices and report how much the headline conclusions move: grids of 1, 2 and 5 km; all satellites against the steady set; confidence at least nominal; high confidence only; presumed vegetation fires only. For each scenario we report the national total, rank correlation with the default (raw and deseasonalised), the share of cell-days seen by both sensors, VIIRS ÷ MODIS, the burning season and the flagged months.</p>
        <p>December 2025 and April 2026 in Ghana are flagged in all 7 scenarios. Other months come and go (April 2023 at finer grids and under quality filters; seven more months under high-confidence-only), which is why we call flags a screening aid. No scenario can be called “correct”: there is no ground truth.</p>
      </Section>

      <Section id="ml" title="11. Isolation Forest comparison">
        <p>Isolation Forest is a machine-learning detector that randomly splits data; points isolated after few splits are “unusual”. We use it only as a <b>benchmark</b>; the flags come from the score in section 5.</p>
        <ul>
          <li><b>Protocol.</b> Both methods learn only from years up to 2019 and are applied unchanged to 2020 onward, for all 17 areas. Two forests (300 trees): one on ln(1+activity) and the month; one on activity relative to that month's training median. The forest flags its top 5% most unusual training months.</li>
          <li><b>Agreement:</b> Jaccard overlap = (months both flag) ÷ (months either flags); and Spearman ρ between the methods' rankings.</li>
          <li><b>Stability:</b> the share of held-out months each method flags (a noisy alarm flags many ordinary months).</li>
          <li><b>Synthetic stress test:</b> real held-out months are multiplied by 3, 2 or 1/3 (only months with a typical level of at least 30 cell-days), and we measure the <b>AUC</b> = the chance an altered month scores more unusual than a genuine one, computed as the Mann–Whitney statistic (0.5 is a coin flip, 1 is perfect). AUC is used because the methods have different built-in alarm levels.</li>
        </ul>
        <table className="table narrow">
          <thead><tr><th>Change</th><th>Our score</th><th>Forest (raw)</th><th>Forest (deseasonalised)</th></tr></thead>
          <tbody>
            <tr><th>×3 (rise)</th><td>0.79</td><td>0.86</td><td>0.84</td></tr>
            <tr><th>×2 (rise)</th><td>0.66</td><td>0.76</td><td>0.70</td></tr>
            <tr><th>÷3 (drop)</th><td><b>0.87</b></td><td>0.61</td><td>0.84</td></tr>
          </tbody>
        </table>
        <p className="muted small">The forest notices rises a bit better but misses drops, which are the case we most care about (December 2025), flags far more ordinary months (22% and 20% of held-out months against 6.8% for our score), and cannot give a reason. The test is synthetic: it measures sensitivity, not accuracy against real fires, and there are no labels to measure accuracy.</p>
      </Section>

      <Section id="rain" title="12. Rainfall context">
        <ul>
          <li><b>Source:</b> NASA POWER monthly precipitation (<code>PRECTOTCORR</code>, mm per day), sampled at one centre point per Ghana region; the national value is the area-weighted mean of the regions. It is coarse and for Ghana only.</li>
          <li><b>Percentile</b> = rank of that month's rainfall among the same calendar month in all years (1.0 = wettest on record).</li>
        </ul>
        <Formula>{`burn anomaly  = ln(1 + steady-set active cell-days) − median of that calendar month
rain anomaly  = ln(1 + monthly rainfall in mm)      − median of that calendar month
association   = Spearman ρ between them, at lags 0, 1, 2, 3 months and for the previous three months' total
reported only when at least 36 paired months exist`}</Formula>
        <p>Nationally ρ ≈ −0.32 at lag 0 (wetter months tend to burn less), −0.19, −0.19 and −0.01 at lags 1 to 3, over 289 months. This is descriptive: rain can suppress burning, grow fuel for later, or both, and many other factors act. December 2025 was the wettest December since 2002 (1.46 against a typical 0.41 mm a day); we call that an association, never a cause.</p>
      </Section>

      <Section id="colours" title="13. Colours, map and hotspot counts">
        <Formula>{`calendar colour  = ramp( sqrt( value ÷ largest complete month shown ) )       (square root keeps quiet months distinguishable)
map cell colour  = ramp( days active in the period ÷ days active in the busiest cell shown )   (linear, relative to what is on screen)
label colour     = near-white or near-black, whichever has the higher contrast:  (L1 + 0.05) ÷ (L2 + 0.05),  L = WCAG relative luminance`}</Formula>
        <p>Inferno, Viridis and Cividis increase steadily in lightness, so they read in greyscale; Cividis is designed for red-green colour-vision deficiency. Every cell also prints its number, and ▲▼ carry the “unusual” signal. The <b>Hotspots detected</b> switch shows raw detections (MODIS plus VIIRS, or the chosen sensor); they are not comparable across sensors or eras. The map draws at most 20,000 cells (the busiest) per request.</p>
      </Section>

      <Section id="places" title="14. Places, coordinates and areas">
        <ul>
          <li><b>Search</b> uses a local GeoNames list of populated places in West Africa (nothing you type is sent elsewhere). Ranking: how well the name matches (exact, starts with, word starts with, alternate name, contains), then administrative importance (capital, regional seat), a bonus for places with fire data and for Ghana, and a small preference for shorter names.</li>
          <li><b>Coordinates</b> are read as latitude, longitude in decimal degrees (for example <code>6.69, -1.62</code>).</li>
          <li><b>Area around a place</b> of radius <i>r</i> km is a square box: half-height <i>r</i> ÷ 110.574 degrees of latitude and half-width <i>r</i> ÷ (111.32 × cos(latitude)) degrees of longitude.</li>
          <li><b>Custom areas</b> are scored by the same code as named areas, from the grid cells whose centres lie inside the box. Small boxes hold few cells, so percentages swing widely.</li>
          <li>Boxes inside Ghana use the detailed Ghana data (1, 2, 5 km); anything else uses the West Africa data on the 5 km grid.</li>
        </ul>
      </Section>

      <Section id="columns" title="15. What each exported column means">
        <table className="table">
          <thead><tr><th>Column</th><th>Meaning</th></tr></thead>
          <tbody>
            <tr><th>active_cell_days</th><td>Cell-days with any detection, all satellites (shown on the calendar)</td></tr>
            <tr><th>scored_cell_days / steady_cell_days</th><td>The same on the steady set; <b>the value that is scored</b> in the harmonized view</td></tr>
            <tr><th>modis_cell_days, viirs_cell_days, both_cell_days</th><td>Cell-days seen by MODIS, by VIIRS (all VIIRS satellites), and by both</td></tr>
            <tr><th>modis_detections, viirs_detections</th><td>Raw detections (hotspots)</td></tr>
            <tr><th>coverage_ok</th><td>True when the month is complete (section 3); incomplete months get no score</td></tr>
            <tr><th>estimated, observed_cell_days, estimate_low, estimate_high</th><td>True for 2002–2011 months; what MODIS actually saw; the 90% range of the estimate</td></tr>
            <tr><th>baseline_n, baseline_median, baseline_mad</th><td>Number of other years; their median (raw cell-days); their MAD (raw cell-days)</td></tr>
            <tr><th>baseline_estimated_n</th><td>How many of the baseline years are estimates</td></tr>
            <tr><th>abs_diff, pct_diff</th><td>x − median and its percentage of the median</td></tr>
            <tr><th>robust_score, threshold, status, reliable</th><td>z, T(n), the verdict (section 5), and whether the baseline had enough variation</td></tr>
            <tr><th>explanation</th><td>The same result in words</td></tr>
          </tbody>
        </table>
        <p className="muted small">Every file also opens with # lines naming the source, method version, area, sensor view, grid and dates, and noting the use of AI assistance.</p>
      </Section>

      <Section id="decisions" title="16. Our decisions and why">
        <table className="table">
          <thead><tr><th>Decision</th><th>Why</th><th>What it costs</th></tr></thead>
          <tbody>
            <tr><th>Count active cell-days, not detections</th><td>Detections cannot be added across sensors (about 11× gap); a square-day is comparable</td><td>Not unique fires; sensors are not made equivalent</td></tr>
            <tr><th>No matching of MODIS and VIIRS hotspots</th><td>Needs assumptions we cannot verify; a wrong match looks authoritative</td><td>Cannot count unique fires</td></tr>
            <tr><th>All satellites counted, history judged on the steady set</th><td>More satellites see more, but joining satellites raise counts without more fire (five false highs measured)</td><td>Displayed count and compared value can differ; both are shown</td></tr>
            <tr><th>Median and MAD on a log scale, same month in other years</th><td>Counts are skewed and seasonal; robust statistics resist outliers</td><td>Short baselines only flag very large changes</td></tr>
            <tr><th>Threshold calibrated to about 1% false flags</th><td>The fixed 3.5 rule falsely flagged 2 to 12% of ordinary months</td><td>Assumes Gaussian noise on the log scale</td></tr>
            <tr><th>Isolation Forest compared, not used</th><td>No labels to measure accuracy; weaker on drops; cannot explain</td><td>We do not claim a smart detector</td></tr>
            <tr><th>2002–2011 estimated and labelled</th><td>Mixing eras creates a false jump in 2012; dropping them loses the early record</td><td>About 20% typical error, assumption of a stable relationship</td></tr>
            <tr><th>Complete months only; quiet days are zeros</th><td>An early version dropped rainy seasons and biased baselines</td><td>The newest month is unscored</td></tr>
            <tr><th>Ghana in full detail, West Africa at country level</th><td>Depth first makes the science defensible; the same method scales</td><td>Other countries: 5 km only, no regions, rainfall or sensor checks</td></tr>
            <tr><th>Rainfall as context only</th><td>Plausible driver, but association is not cause</td><td>Coarse sample points</td></tr>
            <tr><th>Offline place search, atomic file writes, resumable downloads</th><td>Privacy; no half-written reads; NASA's request quota and timeouts</td><td>Slower downloads</td></tr>
          </tbody>
        </table>
      </Section>

      <Section id="limits" title="17. Limits">
        <ul>
          <li>Detections are not unique fires, fire sizes or areas burned, and can include industrial heat. FRP and confidence are not calibrated between sensors.</li>
          <li>The common grid does not make the sensors equivalent: VIIRS still detects far more, and the two flag the same cell on the same day only a minority of the time.</li>
          <li>2002–2011 is estimated; before August 2002 only Terra observed; the newest weeks are near-real-time and can be revised.</li>
          <li>Terra and Aqua overpass times have drifted (measured, not corrected); region totals near borders are approximate.</li>
          <li>No ground truth exists, so no accuracy, precision or recall is claimed. TerraGuard does not predict fires or send alerts.</li>
        </ul>
      </Section>

      <h3>Built with AI assistance</h3>
      <p>
        TerraGuard was developed with the help of an AI coding assistant (Claude, by Anthropic), as the NASA Space Apps rules require us to say. The charts are drawn by code from the data; no generative images or video are used.
      </p>

      <h3>Credits</h3>
      <p>
        Fire data: NASA FIRMS (LANCE/EOSDIS). Boundaries: geoBoundaries. Place names: GeoNames (CC BY 4.0). Rainfall: NASA POWER. Map tiles: OpenStreetMap contributors.
      </p>
    </section>
  );
}
