import CurrentComparison from "../components/CurrentComparison";
import type { AnnualRow, AreaQuery, CalRow } from "../types";

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmt = (n: number) => Math.round(n).toLocaleString("en-GB");

interface Props {
  rows: CalRow[];
  annual: AnnualRow[];
  region: string;
  q: AreaQuery;
  onOpenCalendar: () => void;
}

export default function Overview({ rows, annual, region, q, onOpenCalendar }: Props) {
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
      <div className="hero">
        <div className="hero-text">
          <div className="kicker">Satellite fire intelligence · {region}</div>
          <h2>Burning activity, made comparable</h2>
          <p>
            A harmonized history of satellite-detected burning from NASA MODIS and VIIRS. Figures are <b>active cell-days</b> —
            grid cells with at least one detection on a day — not counts of fires, and the two sensors are never added together
            as raw counts.
          </p>
          <button className="primary" onClick={onOpenCalendar}>Open the burning calendar →</button>
        </div>
        <div className="hero-chart">
          <div className="cap">Active cell-days per year · muted = partial year</div>
          <Spark annual={annual} />
        </div>
      </div>
      {!ok.length ? <p className="muted">No months with sufficient coverage for this selection yet.</p> : (
        <div className="stats">
          <Stat label="Active cell-days (harmonized)" value={fmt(total)} note={`${ok.length} months with full coverage`} />
          <Stat label="Seen by MODIS" value={fmt(modis)} note="cell-days" />
          <Stat label="Seen by VIIRS" value={fmt(viirs)} note="cell-days" />
          <Stat label="Average per month" value={fmt(total / ok.length)} note="complete months only" />
          <Stat label="Highest month" value={peakMonth ? `${MONTH_NAMES[peakMonth.month - 1]} ${peakMonth.year}` : "–"} note={peakMonth ? `${fmt(peakMonth.active_cell_days)} cell-days` : ""} />
          <Stat label="Highest year" value={peakYear ? String(peakYear.year) : "–"} note={peakYear ? `${fmt(peakYear.active_cell_days)} cell-days (complete years only)` : "no complete year"} />
          <Stat label="Unusual months flagged" value={String(flagged)} note="vs same month in other years" />
          <Stat label="Period covered" value={first ? `${first.year}–${last.year}` : "–"} note={ok.some((r) => r.estimated) ? "All satellites · before 2012 estimated from MODIS" : "All satellites"} />
        </div>
      )}
      <CurrentComparison q={q} />
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

function Spark({ annual }: { annual: AnnualRow[] }) {
  if (!annual.length) return <p className="muted small">No annual data.</p>;
  const rows = [...annual].sort((a, b) => a.year - b.year);
  const max = Math.max(1, ...rows.map((r) => r.active_cell_days));
  const w = 400, h = 120, pad = 14, gap = 4;
  const bw = (w - gap * (rows.length - 1)) / rows.length;
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h + pad}`} role="img" aria-label="Annual active cell-days">
      {rows.map((r, i) => {
        const bh = Math.max(2, (r.active_cell_days / max) * (h - 8));
        return (
          <rect key={r.year} x={i * (bw + gap)} y={h - bh} width={bw} height={bh} fill={r.complete_year ? "#ea7a2b" : "#5b4a3b"}>
            <title>{`${r.year}: ${Math.round(r.active_cell_days).toLocaleString("en-GB")}${r.complete_year ? "" : " (partial year)"}`}</title>
          </rect>
        );
      })}
      <text x={0} y={h + pad - 2}>{rows[0].year}</text>
      <text x={w} y={h + pad - 2} textAnchor="end">{rows[rows.length - 1].year}</text>
    </svg>
  );
}
