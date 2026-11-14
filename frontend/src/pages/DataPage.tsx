import { useEffect, useState } from "react";
import { api, exportUrl, reportUrl } from "../services/api";
import type { AreaQuery, HarmonizationMeta, Quality } from "../types";

const fmt = (n: number | null | undefined) => (n === null || n === undefined ? "–" : n.toLocaleString("en-GB"));
const sum = (o: Record<string, number> | undefined) => Object.values(o ?? {}).reduce((a, b) => a + b, 0);

export default function DataPage({ q, meta }: { q: AreaQuery; meta: HarmonizationMeta | null }) {
  const h = meta?.harmonization;
  const [quality, setQuality] = useState<Quality | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.quality(q.grid).then(setQuality).catch((e: Error) => setError(e.message));
  }, [q.grid]);

  const area = q.bbox ? "custom area" : q.region;
  const products = quality ? Object.entries(quality.products) : [];
  const platformTotal = quality ? sum(quality.records_by_platform) : 0;

  return (
    <section>
      <h2>Data and downloads</h2>
      <p className="lead">Every file starts with comment lines (#) stating the source, method version, area, sensor view and grid, so it stays interpretable on its own.</p>
      <div className="actions">
        <a className="button" href={exportUrl("calendar", q)}>Monthly calendar · {area} · {q.sensor}</a>
        <a className="button" href={reportUrl("html", q)} target="_blank" rel="noreferrer">Summary report · {area} (printable)</a>
        <a className="button" href={reportUrl("md", q)}>Summary report · {area} (Markdown)</a>
        {(q.bbox || q.region !== "Ghana" || q.sensor !== "harmonized") && (
          <a className="button" href={exportUrl("calendar", { ...q, bbox: null, region: "Ghana", sensor: "harmonized" })}>Monthly calendar · all of Ghana</a>
        )}
      </div>
      <p className="muted small">Cell and daily/weekly series exports, and a report for a chosen period, are on the calendar page. Every chart has a PNG button. Open the printable report and use Print, then Save as PDF.</p>

      <h3>Data quality</h3>
      {error && <p className="error">{error}</p>}
      {quality && (
        <>
          <div className="stats">
            <div className="stat"><div className="stat-label">Months with complete coverage</div>
              <div className="stat-value">{quality.coverage.months_complete} / {quality.coverage.months_total}</div>
              <div className="stat-note">{quality.coverage.incomplete_months.length ? `Incomplete: ${quality.coverage.incomplete_months.join(", ")}` : "no gaps"}</div></div>
            <div className="stat"><div className="stat-label">Detections used</div>
              <div className="stat-value">{fmt(quality.harmonization.observations_used)}</div>
              <div className="stat-note">after Ghana clip and platform selection</div></div>
            <div className="stat"><div className="stat-label">Outside Ghana (excluded)</div>
              <div className="stat-value">{fmt(quality.harmonization.observations_outside_ghana_excluded)}</div>
              <div className="stat-note">inside the download box only</div></div>
            <div className="stat"><div className="stat-label">Invalid or duplicate records</div>
              <div className="stat-value">{fmt(products.reduce((s, [, p]) => s + sum(p.exclusions_by_reason), 0))}</div>
              <div className="stat-note">removed during cleaning</div></div>
          </div>

          <table className="table">
            <thead><tr><th>Product</th><th>Period</th><th>Files</th><th>Records loaded</th><th>Kept</th><th>Removed</th><th>Missing values</th></tr></thead>
            <tbody>
              {products.map(([name, p]) => {
                const missing = sum(p.missing_values);
                return (
                  <tr key={name}>
                    <th>{name}</th>
                    <td>{p.earliest_observation?.slice(0, 10)} → {p.latest_observation?.slice(0, 10)}</td>
                    <td>{fmt(p.source_files)}</td>
                    <td>{fmt(p.loaded_records)}</td>
                    <td>{fmt(p.retained_records)}</td>
                    <td>{Object.keys(p.exclusions_by_reason ?? {}).length
                      ? Object.entries(p.exclusions_by_reason!).map(([k, v]) => `${fmt(v)} ${k.replace(/_/g, " ")}`).join(", ") : "none"}</td>
                    <td>{p.missing_values ? (missing ? `${fmt(missing)} (see below)` : "none") : "not recorded"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {products.some(([, p]) => sum(p.missing_values) > 0) && (
            <p className="muted small">
              Missing values by field: {products.map(([n, p]) => `${n}: ${Object.entries(p.missing_values ?? {}).filter(([, v]) => v > 0).map(([k, v]) => `${k} ${fmt(v)}`).join(", ") || "none"}`).join(" · ")}
            </p>
          )}

          <h3>Sensor mix (all records before platform selection)</h3>
          <table className="table narrow">
            <tbody>
              {Object.entries(quality.records_by_platform).sort((a, b) => b[1] - a[1]).map(([name, count]) => (
                <tr key={name}><th>{name}</th><td>{fmt(count)}</td><td>{platformTotal ? `${((count / platformTotal) * 100).toFixed(1)}%` : ""}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            VIIRS platforms record several times more detections than MODIS; that is why raw counts are never added across sensors.
            Non-vegetation-type detections (static land sources, offshore) are flagged, not removed:{" "}
            {fmt(products.reduce((s, [, p]) => s + (p.non_vegetation_type_records ?? 0), 0))} records.
          </p>
        </>
      )}

      {h && (
        <>
          <h3>Processing record</h3>
          <table className="table narrow">
            <tbody>
              <tr><th>Source</th><td>NASA FIRMS standard-processing MODIS and VIIRS (375 m) active-fire detections</td></tr>
              <tr><th>Method</th><td>{h.harmonization_method} · version {h.harmonization_version}</td></tr>
              <tr><th>Platforms</th><td>{Array.isArray(h.platforms) ? h.platforms.join(", ") : h.platforms}</td></tr>
              <tr><th>Spatial clip</th><td>{h.spatial_clip}</td></tr>
              <tr><th>Quality filters</th><td>confidence ≥ {h.min_confidence ?? "none"}; vegetation-fire type only: {h.vegetation_only ? "yes" : "no"}</td></tr>
              <tr><th>Boundaries</th><td>geoBoundaries ADM1 (CC BY-SA 2.0), simplified</td></tr>
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
