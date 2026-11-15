import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { SensitivityReport } from "../types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const num = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? "–" : v.toFixed(d));
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(0)}%`);

/** How much do the national conclusions move when reasonable analysis choices change? */
export default function SensitivityPanel() {
  const [data, setData] = useState<SensitivityReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.sensitivity().then(setData).catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="muted">Sensitivity analysis is not available ({error}).</p>;
  if (!data) return <p className="muted">Loading sensitivity analysis…</p>;

  const entries = Object.entries(data.scenarios);
  const total = entries.length;
  const robust = data.default_flagged_months.map((flag) => ({
    flag,
    count: entries.filter(([, s]) => s.flagged_months.includes(flag)).length,
    missing: entries.filter(([, s]) => !s.flagged_months.includes(flag)).map(([, s]) => s.label),
  }));
  const peaks = new Set(entries.map(([, s]) => s.burning_season?.peak_month));

  return (
    <div>
      <h3>Sensitivity to analysis choices (all of Ghana)</h3>
      <p className="muted">
        The default settings are one defensible choice. Each row below re-runs the harmonization with one choice changed and
        compares the result with the default. “Correlation” is the rank correlation of the monthly series after removing
        seasonality; 1.00 means the same year-to-year story.
      </p>
      <table className="table">
        <thead>
          <tr><th>Scenario</th><th>Correlation with default</th><th>Seen by both sensors</th><th>VIIRS ÷ MODIS</th><th>Burning season</th><th>Nationally flagged</th></tr>
        </thead>
        <tbody>
          {entries.map(([key, s]) => (
            <tr key={key} className={key === "default_5km" ? "row-default" : ""}>
              <th><span className="group-tag">{s.group}</span>{s.label}</th>
              <td>{key === "default_5km" ? "–" : num(s.correlation_with_default_deseasonalised)}</td>
              <td>{pct(s.share_seen_by_both_sensors)}</td>
              <td>{num(s.viirs_to_modis_cell_day_ratio)}</td>
              <td>{s.burning_season ? `${s.burning_season.label} (peak ${MONTHS[s.burning_season.peak_month - 1]})` : "–"}</td>
              <td>{s.flagged_months.length ? s.flagged_months.join(", ") : "none"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="callout">
        {robust.length ? robust.map((r) => (
          <p key={r.flag}>
            <b>{r.flag}</b> is flagged in <b>{r.count} of {total}</b> scenarios
            {r.missing.length ? `; it is not flagged when: ${r.missing.join("; ")}.` : "."}
          </p>
        )) : <p>No month is flagged nationally under the default settings.</p>}
        <p>
          The peak month is {peaks.size === 1 ? <b>the same in every scenario</b> : <b>not the same in every scenario</b>}. The edges of the burning
          season move by about a month with the grid size and the quality filter, so season boundaries should be read as approximate.
          Mixing in NOAA-20 and NOAA-21 changes the series the most, because they add overpasses part-way through the record; that is
          why the default keeps the constellation constant. The high-confidence-only scenario keeps only a small share of detections
          and its confidence classes are not comparable across sensors.
        </p>
      </div>
      <ul className="muted small">{data.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}
