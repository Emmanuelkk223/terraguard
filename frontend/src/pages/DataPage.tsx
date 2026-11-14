import { exportUrl } from "../services/api";
import type { Grid, HarmonizationMeta } from "../types";

export default function DataPage({ grid, region, meta }: { grid: Grid; region: string; meta: HarmonizationMeta | null }) {
  const h = meta?.harmonization;
  return (
    <section>
      <h2>Data and downloads</h2>
      <p className="lead">Every file starts with comment lines (#) stating the source, method version, area and grid, so it stays interpretable on its own.</p>
      <div className="actions">
        <a className="button" href={exportUrl("calendar", { grid, region })}>Monthly calendar · {region} · {grid}</a>
        <a className="button" href={exportUrl("calendar", { grid, region: "Ghana" })}>Monthly calendar · all of Ghana</a>
      </div>
      <p className="muted small">Map-cell exports for a single month are available from the calendar page after selecting a month.</p>
      {h && (
        <>
          <h3>Processing record</h3>
          <table className="table narrow">
            <tbody>
              <tr><th>Source</th><td>NASA FIRMS standard-processing MODIS and VIIRS (375 m) active-fire detections</td></tr>
              <tr><th>Method</th><td>{h.harmonization_method} · version {h.harmonization_version}</td></tr>
              <tr><th>Platforms</th><td>{Array.isArray(h.platforms) ? h.platforms.join(", ") : h.platforms}</td></tr>
              <tr><th>Spatial clip</th><td>{h.spatial_clip}</td></tr>
              <tr><th>Detections used</th><td>{h.observations_used.toLocaleString("en-GB")}</td></tr>
              <tr><th>Excluded (outside Ghana)</th><td>{h.observations_outside_ghana_excluded.toLocaleString("en-GB")}</td></tr>
              <tr><th>Quality filters</th><td>confidence ≥ {h.min_confidence ?? "none"}; vegetation-fire type only: {h.vegetation_only ? "yes" : "no"}</td></tr>
              <tr><th>Boundaries</th><td>geoBoundaries ADM1 (CC BY-SA 2.0), simplified</td></tr>
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
