import { useEffect, useState } from "react";
import { AgreementChart, RatioChart, SensorCellDaysChart } from "../components/Charts";
import ChartFrame from "../components/ChartFrame";
import SensitivityPanel from "../components/SensitivityPanel";
import { api } from "../services/api";
import type { BridgeValidation, CalRow, Grid, HarmonizationMeta, Validation } from "../types";

interface Props { rows: CalRow[]; meta: HarmonizationMeta | null; validation: Validation | null; grid: Grid; region: string }
const f2 = (n: number | null | undefined) => (n === null || n === undefined ? "–" : n.toFixed(2));

export default function SensorsPage({ rows: allRows, meta, validation, grid, region }: Props) {
  // Sensor comparisons only make sense where both sensors observed: drop the MODIS-only, estimated years.
  const rows = allRows.filter((r) => !r.estimated);
  const [bridge, setBridge] = useState<BridgeValidation | null>(null);
  useEffect(() => {
    api.bridgeValidation().then(setBridge).catch(() => setBridge(null));
  }, []);
  const v = validation?.grids[grid];
  const drift = validation?.overpass_hour_by_year;
  const hourText = (h: number | undefined) => (h === undefined ? "–" : `${Math.floor(h)}:${String(Math.round((h % 1) * 60)).padStart(2, "0")}`);
  const ok = rows.filter((r) => r.coverage_ok && r.modis_detections > 0 && r.modis_cell_days > 0);
  const avg = (f: (r: CalRow) => number) => (ok.length ? ok.reduce((s, r) => s + f(r), 0) / ok.length : NaN);
  const rawRatio = avg((r) => r.viirs_detections / r.modis_detections);
  const cellRatio = avg((r) => r.viirs_cell_days / r.modis_cell_days);
  const agreement = avg((r) => r.both_cell_days / r.active_cell_days);
  const h = meta?.harmonization;
  return (
    <section>
      <h2>Sensor harmonization · {region}</h2>
      <p className="lead">
        MODIS (1 km) and VIIRS (375 m) see the same landscape differently. TerraGuard puts both on a common grid and
        UTC day, counts <b>active cell-days</b>, and keeps each sensor's contribution visible.
      </p>
      {ok.length > 0 && (
        <div className="stats">
          <div className="stat"><div className="stat-label">VIIRS ÷ MODIS, raw detections</div><div className="stat-value">{rawRatio.toFixed(1)}×</div><div className="stat-note">average over complete months</div></div>
          <div className="stat"><div className="stat-label">VIIRS ÷ MODIS, active cell-days</div><div className="stat-value">{cellRatio.toFixed(1)}×</div><div className="stat-note">after common-grid aggregation</div></div>
          <div className="stat"><div className="stat-label">Same cell-day seen by both</div><div className="stat-value">{(agreement * 100).toFixed(0)}%</div><div className="stat-note">of all active cell-days</div></div>
        </div>
      )}
      <h3>Raw detections versus harmonized cell-days</h3>
      <p className="muted">
        Aggregating to a common grid only slightly reduces VIIRS's excess, and the ratio swings strongly with activity level
        (VIIRS finds relatively more when fires are few and small), so there is no single conversion factor between the sensors.
      </p>
      <ChartFrame title={`${region} · VIIRS ÷ MODIS ratio`} filename="terraguard_sensor_ratio.png"><RatioChart rows={rows} /></ChartFrame>
      <h3>Cell-days by sensor</h3>
      <ChartFrame title={`${region} · cell-days by sensor`} filename="terraguard_sensor_cell_days.png"><SensorCellDaysChart rows={rows} /></ChartFrame>
      <h3>Agreement between sensors</h3>
      <ChartFrame title={`${region} · agreement between sensors`} filename="terraguard_sensor_agreement.png"><AgreementChart rows={rows} /></ChartFrame>
      {v && (
        <>
          <h3>Do the sensors agree beyond the seasons? (all of Ghana, {grid})</h3>
          <p className="muted">
            Both sensors follow the dry and wet seasons, which inflates any raw correlation. The deseasonalised figure compares
            each month with its own calendar-month median, so it measures shared year-to-year change. Based on {v.months} complete months.
          </p>
          <table className="table narrow">
            <thead><tr><th></th><th>Raw detections</th><th>Active cell-days</th></tr></thead>
            <tbody>
              <tr><th>Rank correlation, raw series</th><td>{f2(v.raw_detections.spearman_raw_series)}</td><td>{f2(v.cell_days.spearman_raw_series)}</td></tr>
              <tr><th>Rank correlation, deseasonalised</th><td>{f2(v.raw_detections.spearman_deseasonalised)}</td><td>{f2(v.cell_days.spearman_deseasonalised)}</td></tr>
              <tr><th>VIIRS ÷ MODIS, average</th><td>{f2(v.raw_detections.ratio_viirs_over_modis_mean)}</td><td>{f2(v.cell_days.ratio_viirs_over_modis_mean)}</td></tr>
              <tr><th>Variability of that ratio (CV)</th><td>{f2(v.raw_detections.ratio_cv)}</td><td>{f2(v.cell_days.ratio_cv)}</td></tr>
            </tbody>
          </table>
          <p>
            The sensors share real year-to-year signal, but converting to cell-days does <b>not</b> make them noticeably more
            consistent with each other than raw counts. Its benefit is conceptual (no double counting, no pixel-size inflation),
            not a measured gain in agreement.
          </p>
        </>
      )}
      {drift && (
        <>
          <h3>Orbit drift (median daytime overpass hour, UTC)</h3>
          <table className="table narrow">
            <thead><tr><th>Platform</th><th>2019</th><th>2022</th><th>2025</th></tr></thead>
            <tbody>
              {["Terra", "Aqua", "Suomi-NPP", "NOAA-20", "NOAA-21"].filter((p) => drift[p]).map((p) => (
                <tr key={p}><th>{p}</th><td>{hourText(drift[p]["2019"])}</td><td>{hourText(drift[p]["2022"])}</td><td>{hourText(drift[p]["2025"])}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            Between 2019 and 2025 Terra's overpass moved about 65 minutes earlier and Aqua's about 65 minutes later, so the MODIS series can show changes that are not changes
            in fire. The VIIRS platforms stayed near 13:30, which is why Suomi-NPP anchors the default series.
          </p>
        </>
      )}
      {bridge && bridge.backtests.length > 0 && (
        <>
          <h3>Bridge check: how good are the estimated 2002–2011 months?</h3>
          <p className="muted">
            Before VIIRS existed, each month is estimated from MODIS using the relationship measured when both sensors observed.
            To test that, we hide the later years, fit on the earlier ones and predict the hidden months, whose true values we know.
          </p>
          <table className="table narrow">
            <thead><tr><th>Fitted on</th><th>Predicted</th><th>Months</th><th>Typical error</th><th>Bias</th><th>90% range covers</th></tr></thead>
            <tbody>
              {bridge.backtests.map((b) => (
                <tr key={b.fit_years}>
                  <th>{b.fit_years}</th><td>{b.test_years}</td><td>{b.test_months}</td>
                  <td>{b.median_absolute_error_pct.toFixed(0)}%</td>
                  <td>{b.median_bias_pct > 0 ? "+" : ""}{b.median_bias_pct.toFixed(0)}%</td>
                  <td>{(b.range_90_coverage * 100).toFixed(0)}% of months</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            Estimated months are therefore good for seasons and large swings, not for small differences between neighbouring years.
            The check cannot show that the relationship held before 2012.
          </p>
        </>
      )}
      <SensitivityPanel />
      {h && (
        <div className="callout">
          <b>Method {h.harmonization_version}</b> — {h.harmonization_method}. Platforms:{" "}
          {Array.isArray(h.platforms) ? h.platforms.join(", ") : h.platforms}. {h.observations_used.toLocaleString("en-GB")} detections used;{" "}
          {h.observations_outside_ghana_excluded.toLocaleString("en-GB")} outside Ghana excluded. A month counts as complete only when the downloaded
          archive covers all of it for every selected sensor product.
        </div>
      )}
    </section>
  );
}
