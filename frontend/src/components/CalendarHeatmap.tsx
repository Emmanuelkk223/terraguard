import { useMemo } from "react";
import type { CalRow, Selection } from "../types";
import { infernoColor, textOn } from "../services/colors";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmt = (n: number) => n.toLocaleString("en-GB");

interface Props {
  rows: CalRow[];
  selected: Selection | null;
  onSelect: (s: Selection) => void;
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export default function CalendarHeatmap({ rows, selected, onSelect }: Props) {
  const { years, byKey, max, medians, annual } = useMemo(() => {
    const byKey = new Map(rows.map((r) => [`${r.year}-${r.month}`, r]));
    const years = [...new Set(rows.map((r) => r.year))].sort((a, b) => a - b);
    const complete = rows.filter((r) => r.coverage_ok);
    const max = Math.max(1, ...complete.map((r) => r.active_cell_days));
    const medians = MONTHS.map((_, i) => median(complete.filter((r) => r.month === i + 1).map((r) => r.active_cell_days)));
    const annual = new Map(
      years.map((y) => {
        const yr = rows.filter((r) => r.year === y);
        return [y, { total: yr.reduce((s, r) => s + r.active_cell_days, 0), complete: yr.length === 12 && yr.every((r) => r.coverage_ok) }];
      }),
    );
    return { years, byKey, max, medians, annual };
  }, [rows]);

  if (!rows.length) return <p className="muted">No calendar data for this selection.</p>;

  return (
    <div className="heatmap-wrap" role="group" aria-label="Burning activity calendar: rows are years, columns are months">
      <table className="heatmap">
        <thead>
          <tr>
            <th scope="col">Year</th>
            {MONTHS.map((m) => <th key={m} scope="col">{m}</th>)}
            <th scope="col" className="annual-head">Year total</th>
          </tr>
        </thead>
        <tbody>
          {years.map((year) => (
            <tr key={year}>
              <th scope="row">{year}</th>
              {MONTHS.map((_, i) => {
                const row = byKey.get(`${year}-${i + 1}`);
                if (!row) {
                  return (
                    <td key={i} className="cell-td">
                      <div className="cell empty" role="img" aria-label={`${MONTHS[i]} ${year}: no data`} />
                    </td>
                  );
                }
                const ok = row.coverage_ok;
                const isSel = selected?.year === year && selected.month === i + 1;
                const flag = row.status === "unusually_high" ? "▲" : row.status === "unusually_low" ? "▼" : "";
                const bg = ok ? infernoColor(Math.sqrt(row.active_cell_days / max)) : undefined;
                const label = ok
                  ? `${MONTHS[i]} ${year}: ${fmt(row.active_cell_days)} active cell-days${flag ? (flag === "▲" ? ", unusually high" : ", unusually low") : ""}`
                  : `${MONTHS[i]} ${year}: incomplete satellite record coverage`;
                return (
                  <td key={i} className="cell-td">
                    <button
                      type="button"
                      className={`cell ${ok ? "" : "incomplete"} ${isSel ? "selected" : ""}`}
                      style={ok ? { background: bg, color: textOn(Math.sqrt(row.active_cell_days / max)) } : undefined}
                      aria-label={label}
                      aria-pressed={isSel}
                      title={label}
                      onClick={() => onSelect({ year, month: i + 1 })}
                    >
                      {ok ? <span className="cell-val">{compact(row.active_cell_days)}</span> : <span className="cell-val">·</span>}
                      {flag && <span className={`flag ${flag === "▲" ? "hi" : "lo"}`} aria-hidden="true">{flag}</span>}
                    </button>
                  </td>
                );
              })}
              <td className="annual">
                {fmt(annual.get(year)!.total)}
                {!annual.get(year)!.complete && <span className="partial" title="Not all 12 months have full coverage"> partial</span>}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Median</th>
            {medians.map((m, i) => <td key={i} className="median">{m === null ? "–" : compact(m)}</td>)}
            <td />
          </tr>
        </tfoot>
      </table>
      <Legend max={max} />
    </div>
  );
}

function compact(n: number): string {
  if (n >= 10000) return `${Math.round(n / 1000)}k`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(Math.round(n));
}

function Legend({ max }: { max: number }) {
  const stops = [0, 0.25, 0.5, 0.75, 1];
  return (
    <div className="legend" aria-hidden="true">
      <span>0</span>
      <div className="ramp" style={{ background: `linear-gradient(90deg, ${stops.map((s) => infernoColor(s)).join(",")})` }} />
      <span>{fmt(max)}+ active cell-days</span>
      <span className="legend-item"><i className="swatch incomplete" /> incomplete coverage</span>
      <span className="legend-item"><b className="flag hi">▲</b> unusually high</span>
      <span className="legend-item"><b className="flag lo">▼</b> unusually low</span>
    </div>
  );
}
