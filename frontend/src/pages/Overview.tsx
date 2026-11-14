import type { AnnualRow, CalRow } from "../types";

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmt = (n: number) => Math.round(n).toLocaleString("en-GB");

interface Props {
  rows: CalRow[];
  annual: AnnualRow[];
  region: string;
  onOpenCalendar: () => void;
}

export default function Overview({ rows, annual, region, onOpenCalendar }: Props) {
  const ok = rows.filter((r) => r.coverage_ok);
  const total = ok.reduce((s, r) => s + r.active_cell_days, 0);
  const modis = ok.reduce((s, r) => s + r.modis_cell_days, 0);
  const viirs = ok.reduce((s, r) => s + r.viirs_cell_days, 0);
  const peakMonth = ok.reduce<CalRow | null>((b, r) => (!b || r.active_cell_days > b.active_cell_days ? r : b), null);
  const completeYears = annual.filter((a) => a.complete_year);
  const peakYear = completeYears.reduce<AnnualRow | null>((b, a) => (!b || a.active_cell_days > b.active_cell_days ? a : b), null);
  const flagged = rows.filter((r) => r.status === "unusually_high" || r.status === "unusually_low").length;
  const first = ok[0], last = ok[ok.length - 1];  // fully covered months only

  return (
    <section>
      <h2>Overview · {region}</h2>
      <p className="lead">
        A harmonized history of satellite-detected burning activity from NASA MODIS and VIIRS.
        Figures are <b>active cell-days</b> — grid cells with at least one detection on a day — not counts of fires,
        and the two sensors are never added together as raw counts.
      </p>
      {!ok.length ? <p className="muted">No months with sufficient coverage for this selection yet.</p> : (
        <div className="stats">
          <Stat label="Active cell-days (harmonized)" value={fmt(total)} note={`${ok.length} months with full coverage`} />
          <Stat label="Seen by MODIS" value={fmt(modis)} note="cell-days" />
          <Stat label="Seen by VIIRS" value={fmt(viirs)} note="cell-days" />
          <Stat label="Average per month" value={fmt(total / ok.length)} note="complete months only" />
          <Stat label="Highest month" value={peakMonth ? `${MONTH_NAMES[peakMonth.month - 1]} ${peakMonth.year}` : "–"} note={peakMonth ? `${fmt(peakMonth.active_cell_days)} cell-days` : ""} />
          <Stat label="Highest year" value={peakYear ? String(peakYear.year) : "–"} note={peakYear ? `${fmt(peakYear.active_cell_days)} cell-days (complete years only)` : "no complete year"} />
          <Stat label="Unusual months flagged" value={String(flagged)} note="vs same month in other years" />
          <Stat label="Period covered" value={first ? `${first.year}–${last.year}` : "–"} note="Terra, Aqua, Suomi-NPP" />
        </div>
      )}
      <button className="primary" onClick={onOpenCalendar}>Open the burning activity calendar →</button>
    </section>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-note">{note}</div>
    </div>
  );
}
