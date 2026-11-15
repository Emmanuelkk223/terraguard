import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { AreaQuery, CurrentComparison as Comparison } from "../types";

const fmt = (n: number) => Math.round(n).toLocaleString("en-GB");
const longDate = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

function ordinal(n: number): string {
  const rest = n % 100;
  if (rest >= 11 && rest <= 13) return `${n}th`;
  return `${n}${({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;
}

/** The latest weeks of data against the same dates in every earlier year. */
export default function CurrentComparison({ q }: { q: AreaQuery }) {
  const [days, setDays] = useState<number | "month">(30);
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api.currentComparison(q, days)
      .then((d) => !cancelled && setData(d))
      .catch((e: Error) => !cancelled && (setData(null), setError(e.message)));
    return () => {
      cancelled = true;
    };
  }, [q, days]);

  return (
    <div className="current">
      <div className="current-head">
        <h3>Right now, compared with earlier years</h3>
        <div className="seg" role="group" aria-label="Comparison window">
          {[14, 30, 60].map((d) => (
            <button key={d} type="button" className={days === d ? "on" : ""} onClick={() => setDays(d)}>{d} days</button>
          ))}
          <button type="button" className={days === "month" ? "on" : ""} onClick={() => setDays("month")}>This month so far</button>
        </div>
      </div>
      {error && <p className="muted small">{error}</p>}
      {data && <Body data={data} />}
    </div>
  );
}

function Body({ data }: { data: Comparison }) {
  const all = [...data.history, data.current];
  const max = Math.max(1, ...all.map((r) => r.value));
  const w = 760, h = 130, gap = 3;
  const bw = (w - gap * (all.length - 1)) / all.length;
  const diff = data.pct_diff_from_median;
  const direction = diff === null ? "" : diff >= 0 ? "above" : "below";
  return (
    <>
      <p className="current-line">
        <b>{data.mode === "month" && data.window_label ? `${data.window_label}, ` : ""}{longDate(data.current.window_start)} to {longDate(data.as_of)}</b> had <b>{fmt(data.current.value)}</b> active cell-days in {data.area}
        {diff === null ? "." : <>, <b>{Math.abs(diff).toFixed(0)}% {direction}</b> the typical {fmt(data.median)} for the same dates in {data.history.length} earlier years.</>}{" "}
        That ranks {ordinal(data.rank_among_years)} highest of {data.years_compared} years.
      </p>
      <svg className="current-chart" viewBox={`0 0 ${w} ${h + 16}`} role="img"
        aria-label={`Active cell-days for the latest ${data.window_days} days of data and the same dates in earlier years`}>
        {all.map((r, i) => {
          const bh = Math.max(2, (r.value / max) * (h - 6));
          const isCurrent = r.year === data.current.year;
          return (
            <rect key={r.year} x={i * (bw + gap)} y={h - bh} width={bw} height={bh}
              fill={isCurrent ? "#f2b84b" : r.estimated ? "#6b5a4a" : "#ea7a2b"} stroke={r.estimated ? "#c9b79c" : "none"} strokeDasharray={r.estimated ? "3 2" : undefined}>
              <title>{`${r.year}: ${fmt(r.value)}${r.estimated ? " (estimated, MODIS only era)" : ""}`}</title>
            </rect>
          );
        })}
        <line x1={0} x2={w} y1={h - (data.median / max) * (h - 6)} y2={h - (data.median / max) * (h - 6)} stroke="#86c99b" strokeDasharray="4 3" />
        <text x={0} y={h + 13}>{all[0].year}</text>
        <text x={w} y={h + 13} textAnchor="end">{all[all.length - 1].year}</text>
      </svg>
      <p className="muted small">
        Amber = the latest window; dashed bars before 2012 are estimated from MODIS; the green line is the median of earlier years.{" "}
        {data.note}
      </p>
    </>
  );
}
