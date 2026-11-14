import { useEffect, useMemo, useState } from "react";
import CalendarHeatmap from "../components/CalendarHeatmap";
import { SeriesChart } from "../components/Charts";
import MapView from "../components/MapView";
import MonthDetail from "../components/MonthDetail";
import ChartFrame from "../components/ChartFrame";
import { api, exportUrl, reportUrl } from "../services/api";
import type { AreaQuery, CalRow, Period, RainRow, Selection, SeriesRow } from "../types";

const MAX_DAILY_DAYS = 1100;
const DAY_MS = 86_400_000;
const fmt = (n: number) => Math.round(n).toLocaleString("en-GB");

const pad = (n: number) => String(n).padStart(2, "0");
const monthPeriod = ({ year, month }: Selection): Period => {
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return { start: `${year}-${pad(month)}-01`, end: `${year}-${pad(month)}-${pad(last)}` };
};
const spanDays = (p: Period) => Math.round((Date.parse(p.end) - Date.parse(p.start)) / DAY_MS) + 1;

interface Props {
  rows: CalRow[];
  q: AreaQuery;
  heading: string;
  selection: Selection | null;
  onSelect: (s: Selection) => void;
  onBbox: (bbox: string | null) => void;
}

export default function CalendarPage({ rows, q, heading, selection, onSelect, onBbox }: Props) {
  const [period, setPeriod] = useState<Period | null>(selection ? monthPeriod(selection) : null);
  const [wantedInterval, setWantedInterval] = useState<"day" | "week">("day");
  const [series, setSeries] = useState<SeriesRow[]>([]);
  const [seriesError, setSeriesError] = useState<string | null>(null);
  const [rain, setRain] = useState<RainRow[]>([]);

  // Rainfall context exists for Ghana and its named regions, not for a custom area.
  useEffect(() => {
    if (q.bbox) return setRain([]);
    api.rainfall(q.region).then(setRain).catch(() => setRain([]));
  }, [q.bbox, q.region]);

  // Start with the most recent complete month so the page is never empty.
  useEffect(() => {
    if (selection || !rows.length) return;
    const latest = [...rows].reverse().find((r) => r.coverage_ok);
    if (latest) onSelect({ year: latest.year, month: latest.month });
  }, [rows, selection, onSelect]);

  // Picking a month in the calendar sets the period to that month.
  useEffect(() => {
    if (selection) setPeriod(monthPeriod(selection));
  }, [selection]);

  const days = period ? spanDays(period) : 0;
  const interval: "day" | "week" = days > MAX_DAILY_DAYS ? "week" : wantedInterval;

  useEffect(() => {
    if (!period) return;
    let cancelled = false;
    setSeriesError(null);
    api
      .series(q, period, interval)
      .then((s) => !cancelled && setSeries(s))
      .catch((e: Error) => !cancelled && (setSeries([]), setSeriesError(e.message)));
    return () => {
      cancelled = true;
    };
  }, [q, period, interval]);

  const bounds = useMemo(() => {
    if (!rows.length) return { min: "2012-01-01", max: "2025-12-31" };
    const first = rows[0], last = rows[rows.length - 1];
    return { min: first.month_start, max: monthPeriod({ year: last.year, month: last.month }).end };
  }, [rows]);

  const singleMonth = selection && period && period.start === monthPeriod(selection).start && period.end === monthPeriod(selection).end;
  const row = selection ? rows.find((r) => r.year === selection.year && r.month === selection.month) ?? null : null;

  const setDate = (field: "start" | "end", value: string) => {
    if (!value || !period) return;
    const next = { ...period, [field]: value };
    if (next.end < next.start) next[field === "start" ? "end" : "start"] = value;
    setPeriod(next);
  };

  const totals = useMemo(() => {
    const sum = (f: (r: SeriesRow) => number) => series.reduce((s, r) => s + f(r), 0);
    const peak = series.reduce<SeriesRow | null>((b, r) => (!b || r.value > b.value ? r : b), null);
    return {
      value: sum((r) => r.value), modis: sum((r) => r.modis_cell_days), viirs: sum((r) => r.viirs_cell_days),
      both: sum((r) => r.both_cell_days), active: series.filter((r) => r.value > 0).length, peak,
    };
  }, [series]);

  return (
    <section>
      <h2>Burning activity calendar · {heading}</h2>
      <p className="lead">
        Each cell is one month. Colour shows active cell-days for the chosen sensor view. Select a month to compare it with the
        same calendar month in other years, then refine the period, draw a custom area, or click a bar to zoom to a day or week.
      </p>
      <CalendarHeatmap rows={rows} selected={selection} onSelect={onSelect} />

      <h3>Period</h3>
      <div className="period-bar">
        <label>From
          <input type="date" value={period?.start ?? ""} min={bounds.min} max={bounds.max} onChange={(e) => setDate("start", e.target.value)} />
        </label>
        <label>To
          <input type="date" value={period?.end ?? ""} min={bounds.min} max={bounds.max} onChange={(e) => setDate("end", e.target.value)} />
        </label>
        <div className="seg" role="group" aria-label="Series interval">
          <button type="button" className={interval === "day" ? "on" : ""} disabled={days > MAX_DAILY_DAYS} onClick={() => setWantedInterval("day")}>Day</button>
          <button type="button" className={interval === "week" ? "on" : ""} onClick={() => setWantedInterval("week")}>Week</button>
        </div>
        {selection && !singleMonth && (
          <button type="button" className="tool" onClick={() => setPeriod(monthPeriod(selection))}>Back to selected month</button>
        )}
        {days > MAX_DAILY_DAYS && <span className="muted small">Daily view is limited to {MAX_DAILY_DAYS} days; showing weeks.</span>}
      </div>

      <div className="split">
        {singleMonth ? (
          <MonthDetail row={row} rows={rows} rain={selection ? rain.find((r) => r.year === selection.year && r.month === selection.month) ?? null : null} />
        ) : (
          <aside className="detail" aria-live="polite">
            <h3>{period ? `${period.start} → ${period.end}` : "No period"}</h3>
            <p className="badge muted">Custom period</p>
            <dl>
              <dt>Days in period</dt><dd>{days}</dd>
              <dt>Active cell-days</dt><dd>{fmt(totals.value)}</dd>
              <dt>MODIS cell-days</dt><dd>{fmt(totals.modis)}</dd>
              <dt>VIIRS cell-days</dt><dd>{fmt(totals.viirs)}</dd>
              <dt>Seen by both</dt><dd>{fmt(totals.both)}</dd>
              <dt>{interval === "day" ? "Days" : "Weeks"} with activity</dt><dd>{totals.active} of {series.length}</dd>
              <dt>Busiest {interval}</dt><dd>{totals.peak ? `${totals.peak.period_start} (${fmt(totals.peak.value)})` : "–"}</dd>
            </dl>
            <p className="explain">
              Historical comparison is made month against the same calendar month in other years, so a custom period has none.
              Select a calendar month to see how it compares.
            </p>
          </aside>
        )}
        <MapView q={q} period={period} onBbox={onBbox} />
      </div>

      <h3>{interval === "day" ? "Daily" : "Weekly"} activity</h3>
      {seriesError ? <p className="error">{seriesError}</p> : series.length ? (
        <>
          <ChartFrame title={`${heading} · ${interval === "day" ? "daily" : "weekly"} active cell-days, ${period?.start} to ${period?.end}`} filename={`terraguard_${interval}_${period?.start}_${period?.end}.png`}>
            <SeriesChart data={series} interval={interval} onPick={(r) => setPeriod({ start: r.period_start, end: r.period_end })} />
          </ChartFrame>
          <p className="muted small">Click a bar to zoom the map to that {interval}. Active cell-days: grid cells with at least one detection, counted per {interval === "day" ? "day" : "day within the week"}.</p>
        </>
      ) : <p className="muted">No activity series for this selection.</p>}

      <div className="actions">
        <a className="button" href={exportUrl("calendar", q)}>Download calendar CSV</a>
        <a className="button" href={reportUrl("html", q, period ? { start: period.start, end: period.end } : {})} target="_blank" rel="noreferrer">Summary report (printable)</a>
        <a className="button" href={reportUrl("md", q, period ? { start: period.start, end: period.end } : {})}>Summary report (Markdown)</a>
        {period && (
          <>
            <a className="button" href={exportUrl("cells", q, { start: period.start, end: period.end })}>Download this period's cells CSV</a>
            <a className="button" href={exportUrl("series", q, { start: period.start, end: period.end, interval })}>Download {interval}ly series CSV</a>
          </>
        )}
      </div>
    </section>
  );
}
