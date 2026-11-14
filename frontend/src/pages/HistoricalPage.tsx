import { useEffect, useMemo, useState } from "react";
import { AnnualChart, SeasonalChart, YearCompareChart } from "../components/Charts";
import { api } from "../services/api";
import { burningSeason, MONTH_ABBR } from "../services/season";
import type { AnnualRow, CalRow, Grid, SeasonalRow } from "../types";

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const fmt = (n: number) => Math.round(n).toLocaleString("en-GB");
const MAX_COMPARE = 4;

interface Props {
  annual: AnnualRow[];
  seasonal: SeasonalRow[];
  rows: CalRow[];
  grid: Grid;
  region: string;
}

function median(values: number[]): number {
  const s = [...values].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length ? (s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2) : NaN;
}

export default function HistoricalPage({ annual, seasonal, rows, grid, region }: Props) {
  const [fraction, setFraction] = useState(0.25);
  const [allRegions, setAllRegions] = useState<SeasonalRow[]>([]);
  const complete = useMemo(() => annual.filter((a) => a.complete_year), [annual]);
  const [years, setYears] = useState<number[]>([]);

  useEffect(() => {
    api.seasonalAllRegions(grid).then(setAllRegions).catch(() => setAllRegions([]));
  }, [grid]);

  // Default comparison: the busiest and the most recent complete year.
  useEffect(() => {
    if (!complete.length) return setYears([]);
    const busiest = complete.reduce((b, a) => (a.active_cell_days > b.active_cell_days ? a : b));
    const latest = complete[complete.length - 1];
    setYears([...new Set([busiest.year, latest.year])].sort((a, b) => a - b));
  }, [complete]);

  const season = useMemo(() => burningSeason(seasonal, fraction), [seasonal, fraction]);
  const byRegion = useMemo(() => {
    const groups = new Map<string, SeasonalRow[]>();
    allRegions.forEach((r) => groups.set(r.region, [...(groups.get(r.region) ?? []), r]));
    return [...groups.entries()]
      .map(([name, data]) => ({ name, season: burningSeason(data, fraction), peakMedian: Math.max(...data.map((d) => d.median)) }))
      .sort((a, b) => (a.name === "Ghana" ? -1 : b.name === "Ghana" ? 1 : a.name.localeCompare(b.name)));
  }, [allRegions, fraction]);

  const typicalYear = median(complete.map((a) => a.active_cell_days));
  const toggleYear = (y: number) =>
    setYears((cur) => (cur.includes(y) ? cur.filter((v) => v !== y) : [...cur, y].slice(-MAX_COMPARE).sort((a, b) => a - b)));

  return (
    <section>
      <h2>Historical analysis · {region}</h2>

      <h3>Seasonal pattern and burning season</h3>
      <p className="muted">Median and range of active cell-days for each calendar month, across years with full coverage.</p>
      <div className="control-row">
        <label>
          <span>Season threshold: months with a median of at least <b>{Math.round(fraction * 100)}%</b> of the busiest month</span>
          <input type="range" min={5} max={75} step={5} value={Math.round(fraction * 100)} onChange={(e) => setFraction(Number(e.target.value) / 100)} />
        </label>
      </div>
      {seasonal.length ? <SeasonalChart data={seasonal} season={season?.months ?? []} /> : <p className="muted">No seasonal data.</p>}
      {season && (
        <p>
          Burning season: <b>{season.label}</b>, peaking in <b>{MONTH_NAMES[season.peak - 1]}</b>. These {season.months.length} months hold{" "}
          <b>{(season.share * 100).toFixed(0)}%</b> of a typical year's activity. The threshold is a presentation choice, not a physical
          boundary; move the slider to see how the season changes.
        </p>
      )}

      {byRegion.length > 0 && (
        <>
          <h3>Burning season by region</h3>
          <table className="table">
            <thead><tr><th>Region</th><th>Season</th><th>Peak month</th><th>Share of a typical year</th><th>Typical peak (cell-days)</th></tr></thead>
            <tbody>
              {byRegion.map((r) => (
                <tr key={r.name}>
                  <th>{r.name}</th>
                  <td>{r.season?.label ?? "–"}</td>
                  <td>{r.season ? MONTH_ABBR[r.season.peak - 1] : "–"}</td>
                  <td>{r.season ? `${(r.season.share * 100).toFixed(0)}%` : "–"}</td>
                  <td>{fmt(r.peakMedian)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">Uses the harmonized view for every named region, at the same threshold as the chart above.</p>
        </>
      )}

      <h3>Compare years</h3>
      <p className="muted">Pick up to {MAX_COMPARE} years to overlay month by month against the typical year (median across years). Months without full coverage are left blank.</p>
      <div className="chips" role="group" aria-label="Years to compare">
        {[...new Set(rows.filter((r) => r.coverage_ok).map((r) => r.year))].sort((a, b) => a - b).map((y) => (
          <button key={y} type="button" className={`chip-btn ${years.includes(y) ? "on" : ""}`} aria-pressed={years.includes(y)} onClick={() => toggleYear(y)}>{y}</button>
        ))}
      </div>
      {years.length > 0 && seasonal.length > 0 ? <YearCompareChart rows={rows} years={years} seasonal={seasonal} /> : <p className="muted">Select at least one year.</p>}
      {years.length > 0 && (
        <table className="table narrow">
          <thead><tr><th>Year</th><th>Annual active cell-days</th><th>Versus a typical complete year</th></tr></thead>
          <tbody>
            {years.map((y) => {
              const a = annual.find((x) => x.year === y);
              const diff = a && a.complete_year && typicalYear > 0 ? ((a.active_cell_days - typicalYear) / typicalYear) * 100 : null;
              return (
                <tr key={y}>
                  <th>{y}</th>
                  <td>{a ? fmt(a.active_cell_days) : "–"}{a && !a.complete_year ? " (partial year)" : ""}</td>
                  <td>{diff === null ? "not comparable" : `${diff > 0 ? "+" : ""}${diff.toFixed(0)}%`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <h3>Annual totals</h3>
      <p className="muted">Muted bars are partial years — some months lack sufficient satellite record coverage — and must not be compared with complete years.</p>
      {annual.length ? <AnnualChart data={annual} /> : <p className="muted">No annual data.</p>}
    </section>
  );
}
