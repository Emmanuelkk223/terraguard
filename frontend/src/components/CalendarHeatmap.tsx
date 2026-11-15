import { useMemo } from "react";
import type { CalRow, Selection } from "../types";
import { RAMP_LABEL, RAMP_NAMES, rampColor, textOn, type RampName } from "../services/colors";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmt = (n: number) => n.toLocaleString("en-GB");

export type Measure = "cells" | "hotspots";

interface Props {
  rows: CalRow[];
  selected: Selection | null;
  onSelect: (s: Selection) => void;
  ramp: RampName;
  onRamp: (r: RampName) => void;
  measure: Measure;
  onMeasure: (m: Measure) => void;
  sensor: "harmonized" | "steady" | "modis" | "viirs";
}

/** The number a calendar cell shows: active cell-days, or the satellite hotspots (detections) behind them. */
export function valueOf(row: CalRow, measure: Measure, sensor: Props["sensor"]): number {
  if (measure === "cells") return row.active_cell_days;
  if (sensor === "modis") return row.modis_detections;
  if (sensor === "viirs") return row.viirs_detections;
  if (sensor === "steady") return row.modis_detections + (row.viirs_steady_detections ?? row.viirs_detections);
  return row.modis_detections + row.viirs_detections;
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export default function CalendarHeatmap({ rows, selected, onSelect, ramp, onRamp, measure, onMeasure, sensor }: Props) {
  const { years, byKey, max, medians, annual } = useMemo(() => {
    const byKey = new Map(rows.map((r) => [`${r.year}-${r.month}`, r]));
    // Years with no comparable month at all (2000-2001, Terra only) would be two empty rows: leave them out.
    const years = [...new Set(rows.filter((r) => r.coverage_ok || r.year >= 2002).map((r) => r.year))].sort((a, b) => a - b);
    const complete = rows.filter((r) => r.coverage_ok);
    const max = Math.max(1, ...complete.map((r) => valueOf(r, measure, sensor)));
    const medians = MONTHS.map((_, i) => median(complete.filter((r) => r.month === i + 1).map((r) => valueOf(r, measure, sensor))));
    const annual = new Map(
      years.map((y) => {
        const yr = rows.filter((r) => r.year === y);
        return [y, {
          total: yr.reduce((s, r) => s + valueOf(r, measure, sensor), 0),
          complete: yr.length === 12 && yr.every((r) => r.coverage_ok),
          estimated: yr.some((r) => r.coverage_ok && r.estimated),
        }];
      }),
    );
    return { years, byKey, max, medians, annual };
  }, [rows, measure, sensor]);

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
              <th scope="row">
                {year}
                {sensor === "harmonized" && year === 2018 && <span className="join" title="NOAA-20 joined in April 2018: more satellites, more detections">+N20</span>}
                {sensor === "harmonized" && year === 2023 && <span className="join" title="NOAA-21 joined in March 2023: more satellites, more detections">+N21</span>}
              </th>
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
                const estimated = ok && !!row.estimated;
                const terraOnly = !ok && row.limited_reason === "terra_only";
                const isSel = selected?.year === year && selected.month === i + 1;
                const flag = row.status === "unusually_high" ? "▲" : row.status === "unusually_low" ? "▼" : "";
                const value = valueOf(row, measure, sensor);
                const unit = measure === "cells" ? "active cell-days" : "hotspots detected";
                const bg = ok ? rampColor(ramp, Math.sqrt(value / max)) : undefined;
                const label = ok
                  ? `${MONTHS[i]} ${year}: ${fmt(value)} ${unit}${estimated ? " (estimated: MODIS only, before VIIRS)" : ""}${flag ? (flag === "▲" ? ", unusually high" : ", unusually low") : ""}`
                  : terraOnly
                    ? `${MONTHS[i]} ${year}: only the Terra satellite was observing, not compared`
                    : `${MONTHS[i]} ${year}: incomplete satellite record coverage`;
                return (
                  <td key={i} className="cell-td">
                    <button
                      type="button"
                      className={`cell ${ok ? "" : "incomplete"} ${estimated ? "estimated" : ""} ${isSel ? "selected" : ""}`}
                      style={ok ? { background: bg, color: textOn(ramp, Math.sqrt(value / max)) } : undefined}
                      aria-label={label}
                      aria-pressed={isSel}
                      title={label}
                      onClick={() => onSelect({ year, month: i + 1 })}
                    >
                      {ok ? <span className="cell-val">{compact(value)}</span> : <span className="cell-val">·</span>}
                      {flag && <span className={`flag ${flag === "▲" ? "hi" : "lo"}`} aria-hidden="true">{flag}</span>}
                    </button>
                  </td>
                );
              })}
              <td className="annual">
                {fmt(annual.get(year)!.total)}
                {!annual.get(year)!.complete && <span className="partial" title="Not all 12 months have full coverage"> partial</span>}
                {annual.get(year)!.complete && annual.get(year)!.estimated && <span className="partial" title="Includes months estimated from MODIS alone"> est.</span>}
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
      {sensor === "harmonized" && (
        <p className="notice constellation">
          <b>All satellites are used, so more satellites mean more chances to see a fire.</b> NOAA-20 joined in April 2018 (+N20) and NOAA-21 in March 2023 (+N21),
          which raises counts from those years on, even if the amount of fire did not change. To compare years like for like, choose
          <b> Sensor view: Steady set</b> (Terra, Aqua and Suomi-NPP only).
        </p>
      )}
      <Legend max={max} ramp={ramp} onRamp={onRamp} measure={measure} onMeasure={onMeasure} anyEstimated={rows.some((r) => r.coverage_ok && r.estimated)} />
    </div>
  );
}

function compact(n: number): string {
  if (n >= 10000) return `${Math.round(n / 1000)}k`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(Math.round(n));
}

function Legend({ max, anyEstimated, ramp, onRamp, measure, onMeasure }: { max: number; anyEstimated: boolean; ramp: RampName; onRamp: (r: RampName) => void; measure: Measure; onMeasure: (m: Measure) => void }) {
  const stops = [0, 0.25, 0.5, 0.75, 1];
  return (
    <div className="legend">
      <span aria-hidden="true">0</span>
      <div className="ramp" aria-hidden="true" style={{ background: `linear-gradient(90deg, ${stops.map((s) => rampColor(ramp, s)).join(",")})` }} />
      <span aria-hidden="true">{fmt(max)}+ {measure === "cells" ? "active cell-days" : "hotspots detected"}</span>
      <span className="legend-item" role="group" aria-label="What the colours show">
        <button type="button" className={`tool ${measure === "cells" ? "on" : ""}`} aria-pressed={measure === "cells"} onClick={() => onMeasure("cells")}>Active cell-days</button>
        <button type="button" className={`tool ${measure === "hotspots" ? "on" : ""}`} aria-pressed={measure === "hotspots"} onClick={() => onMeasure("hotspots")}>Hotspots detected</button>
      </span>
      <label className="legend-item">Colours
        <select value={ramp} onChange={(e) => onRamp(e.target.value as RampName)} aria-label="Colour ramp">
          {RAMP_NAMES.map((r) => <option key={r} value={r}>{RAMP_LABEL[r]}</option>)}
        </select>
      </label>
      <span className="legend-item"><i className="swatch incomplete" /> incomplete coverage</span>
      {anyEstimated && <span className="legend-item"><i className="swatch estimated" /> estimated from MODIS (before VIIRS, 2002–2011)</span>}
      <span className="legend-item"><b className="flag hi">▲</b> unusually high</span>
      <span className="legend-item"><b className="flag lo">▼</b> unusually low</span>
      {measure === "hotspots" && (
        <span className="legend-note">Hotspots are raw satellite detections. MODIS and VIIRS count differently (VIIRS finds about 11 times more), so hotspot counts are only comparable within the same era of sensors; before 2012 only MODIS exists. Active cell-days are the harmonized measure.</span>
      )}
    </div>
  );
}
