import { AgreementChart, RatioChart, SensorCellDaysChart } from "../components/Charts";
import type { CalRow, HarmonizationMeta } from "../types";

export default function SensorsPage({ rows, meta, region }: { rows: CalRow[]; meta: HarmonizationMeta | null; region: string }) {
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
      <p className="muted">The gap shrinks but does not close: aggregation removes the effect of VIIRS's smaller pixels, yet VIIRS also detects activity MODIS does not.</p>
      <RatioChart rows={rows} />
      <h3>Cell-days by sensor</h3>
      <SensorCellDaysChart rows={rows} />
      <h3>Agreement between sensors</h3>
      <AgreementChart rows={rows} />
      {h && (
        <div className="callout">
          <b>Method {h.harmonization_version}</b> — {h.harmonization_method}. Platforms:{" "}
          {Array.isArray(h.platforms) ? h.platforms.join(", ") : h.platforms}. {h.observations_used.toLocaleString("en-GB")} detections used;{" "}
          {h.observations_outside_ghana_excluded.toLocaleString("en-GB")} outside Ghana excluded. Months need records from both sensors on at least{" "}
          {Math.round(h.min_coverage * 100)}% of days to count as complete.
        </div>
      )}
    </section>
  );
}
