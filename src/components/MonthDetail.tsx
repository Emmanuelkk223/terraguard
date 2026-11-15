import { BaselineChart } from "./Charts";
import { describeRain } from "../services/rain";
import type { CalRow, RainRow, Status } from "../types";

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const fmt = (n: number | null | undefined, digits = 0) =>
  n === null || n === undefined || Number.isNaN(n) ? "–" : n.toLocaleString("en-GB", { maximumFractionDigits: digits });
const signed = (n: number | null, digits = 0) =>
  n === null || Number.isNaN(n) ? "–" : `${n > 0 ? "+" : ""}${n.toLocaleString("en-GB", { maximumFractionDigits: digits })}`;

const STATUS_TEXT: Record<Status, { label: string; tone: string }> = {
  typical: { label: "Within the usual range", tone: "ok" },
  unusually_high: { label: "Unusually high", tone: "hi" },
  unusually_low: { label: "Unusually low", tone: "lo" },
  incomplete_coverage: { label: "Incomplete coverage", tone: "muted" },
  insufficient_baseline: { label: "Too few years to compare", tone: "muted" },
  above_flat_baseline: { label: "Above a flat baseline (no score)", tone: "muted" },
  below_flat_baseline: { label: "Below a flat baseline (no score)", tone: "muted" },
};

export default function MonthDetail({ row, rows, rain }: { row: CalRow | null; rows: CalRow[]; rain?: RainRow | null }) {
  if (!row) return <aside className="detail muted">Select a month in the calendar to compare it with the same month in other years.</aside>;
  const s = STATUS_TEXT[row.status];
  return (
    <aside className="detail" aria-live="polite">
      <h3>{MONTH_NAMES[row.month - 1]} {row.year}</h3>
      <p className={`badge ${s.tone}`}>{s.label}{!row.reliable && row.status !== "incomplete_coverage" ? " · low reliability" : ""}</p>
      {!row.coverage_ok && row.limited_reason === "terra_only" && (
        <p className="notice">
          Before August 2002 only the Terra satellite was observing (Aqua began delivering fire data in mid-2002), so this month has about
          half the overpasses of later years and is not compared with them.
        </p>
      )}
      {!row.coverage_ok && row.limited_reason !== "terra_only" && (
        <p className="notice">
          Partial data: the satellite record does not cover this whole month for one or both sensors, so it is not compared
          with history. Sensor counts below are incomplete.
        </p>
      )}
      {row.coverage_ok && row.estimated && (
        <p className="notice">
          <b>Estimated, not observed.</b> VIIRS did not exist yet. MODIS saw {fmt(row.observed_cell_days)} cell-days; expressed on the combined
          MODIS+VIIRS scale that is about {fmt(row.active_cell_days)} (90% range {fmt(row.estimate_low)} to {fmt(row.estimate_high)}),
          using the relationship measured from 2012 onwards.
        </p>
      )}
      <dl>
        <dt>Active cell-days{row.coverage_ok && row.estimated ? " (estimated)" : ""}</dt><dd>{row.coverage_ok ? fmt(row.active_cell_days) : "not comparable"}</dd>
        <dt>Historical median</dt><dd>{fmt(row.baseline_median)}</dd>
        <dt>Difference</dt><dd>{signed(row.abs_diff)} ({row.pct_diff === null ? "n/a" : `${signed(row.pct_diff)}%`})</dd>
        <dt>Robust score</dt><dd>{row.robust_score === null ? "–" : signed(row.robust_score, 1)} (flag at ±{row.threshold})</dd>
        <dt>Baseline</dt><dd>{row.baseline_n} other years ({MONTH_NAMES[row.month - 1]}), MAD {fmt(row.baseline_mad, 1)}</dd>
        <dt>Hotspots detected{row.coverage_ok ? "" : " (partial)"}</dt>
        <dd>
          MODIS {fmt(row.modis_detections)}
          {row.estimated ? <span className="muted"> (VIIRS did not exist yet)</span> : <> · VIIRS {fmt(row.viirs_detections)}</>}
        </dd>
        <dt>MODIS cell-days{row.coverage_ok ? "" : " (partial)"}</dt><dd>{fmt(row.modis_cell_days)}</dd>
        <dt>VIIRS cell-days{row.coverage_ok ? "" : " (partial)"}</dt><dd>{fmt(row.viirs_cell_days)}</dd>
        <dt>Seen by both{row.coverage_ok ? "" : " (partial)"}</dt><dd>{fmt(row.both_cell_days)}</dd>
      </dl>
      {rain && (
        <p className="rain-note" title="NASA POWER monthly precipitation, sampled at region centre points; coarse gridded context, not a cause">
          <b>Rainfall context:</b> {describeRain(rain)}.
        </p>
      )}
      {row.coverage_ok && (
        <>
          <div className="mini-title">How this month compares with history</div>
          <BaselineChart rows={rows} row={row} />
        </>
      )}
      <p className="explain">{row.explanation}</p>
    </aside>
  );
}
