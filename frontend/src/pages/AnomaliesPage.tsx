import { useMemo, useState } from "react";
import MethodComparisonPanel from "../components/MethodComparisonPanel";
import type { CalRow, Selection, Status } from "../types";

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const flagged = (s?: Status | null) => s === "unusually_high" || s === "unusually_low";

/** Does each sensor's own history also flag this month? Agreement is stronger evidence than one sensor alone. */
function Corroboration({ row }: { row: CalRow }) {
  const parts = [["MODIS", row.modis_status], ["VIIRS", row.viirs_status]] as const;
  const seen = parts.filter(([, s]) => flagged(s)).map(([n]) => n);
  if (row.modis_status === undefined && row.viirs_status === undefined) return <>–</>;
  return (
    <span title="Whether this month is also unusual when each sensor is analysed on its own">
      {seen.length === 2 ? <b className="ok-text">Both sensors</b> : seen.length === 1 ? <b className="warn-text">{seen[0]} only</b> : <span className="muted">Neither alone</span>}
    </span>
  );
}

export default function AnomaliesPage({ rows, region, area, onOpen }: { rows: CalRow[]; region: string; area: string; onOpen: (s: Selection) => void }) {
  const [dir, setDir] = useState<"all" | "high" | "low">("all");
  const list = useMemo(
    () =>
      rows
        .filter((r) => (dir === "all" ? r.status === "unusually_high" || r.status === "unusually_low" : r.status === `unusually_${dir}`))
        .sort((a, b) => Math.abs(b.robust_score ?? 0) - Math.abs(a.robust_score ?? 0)),
    [rows, dir],
  );
  return (
    <section>
      <h2>Unusual historical activity · {region}</h2>
      <p className="lead">
        Months whose activity differs strongly from the same calendar month in other years (median and MAD,
        leave-one-out, complete months only). This describes the past; it is not a prediction or an alert.
      </p>
      <div className="seg" role="group" aria-label="Direction">
        {(["all", "high", "low"] as const).map((d) => (
          <button key={d} className={dir === d ? "on" : ""} onClick={() => setDir(d)}>{d === "all" ? "All" : d === "high" ? "Unusually high" : "Unusually low"}</button>
        ))}
      </div>
      {!list.length ? <p className="muted">No months flagged for this selection.</p> : (
        <table className="table">
          <thead><tr><th>Month</th><th>Active cell-days</th><th>Median</th><th>Δ%</th><th>Score</th><th>Also unusual in</th><th>Why flagged</th></tr></thead>
          <tbody>
            {list.slice(0, 100).map((r) => (
              <tr key={`${r.region}-${r.year}-${r.month}`}>
                <td><button className="link" onClick={() => onOpen({ year: r.year, month: r.month })}>{MONTH_NAMES[r.month - 1]} {r.year}</button></td>
                <td>{r.active_cell_days.toLocaleString("en-GB")}</td>
                <td>{r.baseline_median === null ? "–" : Math.round(r.baseline_median).toLocaleString("en-GB")}</td>
                <td>{r.pct_diff === null ? "–" : `${r.pct_diff > 0 ? "+" : ""}${Math.round(r.pct_diff)}%`}</td>
                <td className={r.status === "unusually_high" ? "hi" : "lo"}>{r.robust_score === null ? "–" : r.robust_score.toFixed(1)}</td>
                <td><Corroboration row={r} /></td>
                <td className="why">{r.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <MethodComparisonPanel area={area} />
    </section>
  );
}
