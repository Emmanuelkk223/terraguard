import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { AnnualRow, CalRow, SeasonalRow, SeriesRow } from "../types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const AXIS = { stroke: "#8fa0b3", fontSize: 12 };
const GRID = "#243447";
const TIP = { background: "#0f1b2a", border: "1px solid #2c3f55", borderRadius: 0, color: "#e8eef5" };
const MODIS_COLOR = "#e8a33d";
const VIIRS_COLOR = "#5ec2b7";
const MAD_SCALE = 1.4826;

export function AnnualChart({ data }: { data: AnnualRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" {...AXIS} />
        <YAxis {...AXIS} width={56} />
        <Tooltip contentStyle={TIP} formatter={(v: number, _n, p) => [`${v.toLocaleString("en-GB")}${p.payload.complete_year ? "" : " (partial year)"}`, "Active cell-days"]} />
        <Bar dataKey="active_cell_days" name="Active cell-days">
          {data.map((d) => <Cell key={d.year} fill={d.complete_year ? "#e8863d" : "#6b5a49"} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Seasonal median and range by calendar month; months in ``season`` are shaded as the burning season. */
export function SeasonalChart({ data, season = [] }: { data: SeasonalRow[]; season?: number[] }) {
  const top = Math.max(1, ...data.map((d) => d.max));
  const rows = data.map((d) => ({
    month: MONTHS[d.month - 1], range: [d.min, d.max], median: d.median, mean: d.mean, n: d.n_years,
    band: season.includes(d.month) ? top : 0,
  }));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap={0}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="month" {...AXIS} />
        <YAxis {...AXIS} width={56} />
        <Tooltip contentStyle={TIP} />
        <Legend />
        <Bar dataKey="band" name="Burning season" fill="#4f9d69" fillOpacity={0.16} isAnimationActive={false} />
        <Area dataKey="range" name="Min–max across years" stroke="none" fill="#e8863d" fillOpacity={0.25} />
        <Line dataKey="median" name="Median" stroke="#f6c453" strokeWidth={2.5} dot={{ r: 3 }} />
        <Line dataKey="mean" name="Mean" stroke="#8fa0b3" strokeDasharray="4 4" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

const median = (v: number[]) => {
  const s = [...v].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length ? (s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2) : NaN;
};

/** The selected month beside the same month in every other year, with the range treated as usual. */
export function BaselineChart({ rows, row }: { rows: CalRow[]; row: CalRow }) {
  const same = rows.filter((r) => r.month === row.month && r.coverage_ok).sort((a, b) => a.year - b.year);
  const peers = same.filter((r) => r.year !== row.year).map((r) => r.active_cell_days);
  const logs = peers.map((v) => Math.log1p(v));
  const logMed = median(logs);
  const logMad = median(logs.map((v) => Math.abs(v - logMed)));
  const band = peers.length >= 5 && logMad > 0
    ? [Math.max(0, Math.expm1(logMed - row.threshold * MAD_SCALE * logMad)), Math.expm1(logMed + row.threshold * MAD_SCALE * logMad)]
    : null;
  const data = same.map((r) => ({ year: String(r.year), value: r.active_cell_days, selected: r.year === row.year }));
  // Fix the axis to the data so the band (which can reach far above every bar) is clamped, not discarded.
  const rawTop = Math.max(1, ...same.map((r) => r.active_cell_days)) * 1.1;
  const step = 10 ** Math.max(0, Math.floor(Math.log10(rawTop)) - 1);
  const top = Math.ceil(rawTop / step) * step; // a round axis maximum keeps tick labels readable
  const compact = (v: number) => (v >= 10000 ? `${Math.round(v / 1000)}k` : v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(Math.round(v)));
  return (
    <div>
      <ResponsiveContainer width="100%" height={170}>
        <BarChart data={data} margin={{ top: 6, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="year" {...AXIS} fontSize={10} interval={0} tickFormatter={(v: string) => `’${v.slice(2)}`} />
          <YAxis {...AXIS} width={44} fontSize={10} domain={[0, top]} allowDataOverflow tickCount={4} tickFormatter={compact} />
          {band && <ReferenceArea y1={Math.min(band[0], top)} y2={Math.min(band[1], top)} fill="#4f9d69" fillOpacity={0.18} stroke="#4f9d69" strokeOpacity={0.5} />}
          {peers.length > 0 && <ReferenceLine y={median(peers)} stroke="#f2b84b" strokeDasharray="4 3" />}
          <Tooltip contentStyle={TIP} cursor={{ fill: "rgba(255,255,255,.05)" }} formatter={(v: number) => [v.toLocaleString("en-GB"), "Active cell-days"]} />
          <Bar dataKey="value">
            {data.map((d) => <Cell key={d.year} fill={d.selected ? "#f2b84b" : "#4a6785"} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="muted small">
        Same calendar month in each year (amber = selected). Dashed line: median of the other years.
        {band ? " Green band: the range treated as usual for this baseline size." : " No band: the baseline is too short or has no spread."}
      </p>
    </div>
  );
}

const YEAR_COLOURS = ["#f2b84b", "#4cc0b3", "#d1566b", "#9a8cff"];

/** Monthly activity of a few chosen years against the typical (median) year. */
export function YearCompareChart({ rows, years, seasonal }: { rows: CalRow[]; years: number[]; seasonal: SeasonalRow[] }) {
  const medianByMonth = new Map(seasonal.map((s) => [s.month, s.median]));
  const data = MONTHS.map((label, i) => {
    const point: Record<string, number | string | null> = { month: label, median: medianByMonth.get(i + 1) ?? null };
    for (const year of years) {
      const r = rows.find((x) => x.year === year && x.month === i + 1);
      point[`y${year}`] = r && r.coverage_ok ? r.active_cell_days : null;
    }
    return point;
  });
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="month" {...AXIS} />
        <YAxis {...AXIS} width={56} />
        <Tooltip contentStyle={TIP} />
        <Legend />
        <Line dataKey="median" name="Typical year (median)" stroke="#8fa0b3" strokeDasharray="5 4" strokeWidth={2} dot={false} />
        {years.map((year, i) => (
          <Line key={year} dataKey={`y${year}`} name={String(year)} stroke={YEAR_COLOURS[i % YEAR_COLOURS.length]} strokeWidth={2.4} dot={{ r: 2.5 }} connectNulls={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function monthLabel(r: CalRow) {
  return `${r.year}-${String(r.month).padStart(2, "0")}`;
}

export function SensorCellDaysChart({ rows }: { rows: CalRow[] }) {
  const data = rows.filter((r) => r.coverage_ok).map((r) => ({
    t: monthLabel(r), MODIS: r.modis_cell_days, VIIRS: r.viirs_cell_days, Union: r.active_cell_days,
  }));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="t" {...AXIS} minTickGap={40} />
        <YAxis {...AXIS} width={56} />
        <Tooltip contentStyle={TIP} />
        <Legend />
        <Line dataKey="MODIS" stroke={MODIS_COLOR} dot={false} strokeWidth={2} />
        <Line dataKey="VIIRS" stroke={VIIRS_COLOR} dot={false} strokeWidth={2} />
        <Line dataKey="Union" name="Harmonized (either sensor)" stroke="#f3efe8" dot={false} strokeDasharray="5 3" />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function RatioChart({ rows }: { rows: CalRow[] }) {
  const data = rows
    .filter((r) => r.coverage_ok && r.modis_detections > 0 && r.modis_cell_days > 0)
    .map((r) => ({ t: monthLabel(r), raw: r.viirs_detections / r.modis_detections, cells: r.viirs_cell_days / r.modis_cell_days }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="t" {...AXIS} minTickGap={40} />
        <YAxis {...AXIS} width={40} domain={[0, "auto"]} />
        <Tooltip contentStyle={TIP} formatter={(v: number) => v.toFixed(2)} />
        <Legend />
        <Line dataKey="raw" name="Raw detections (VIIRS ÷ MODIS)" stroke="#d1566b" dot={false} strokeWidth={2} />
        <Line dataKey="cells" name="Active cell-days (VIIRS ÷ MODIS)" stroke="#5ec2b7" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function AgreementChart({ rows }: { rows: CalRow[] }) {
  const data = rows
    .filter((r) => r.coverage_ok && r.active_cell_days > 0)
    .map((r) => ({ t: monthLabel(r), agreement: r.both_cell_days / r.active_cell_days }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="t" {...AXIS} minTickGap={40} />
        <YAxis {...AXIS} width={40} domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
        <Tooltip contentStyle={TIP} formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
        <Line dataKey="agreement" name="Cell-days seen by both sensors" stroke="#f6c453" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}

interface SeriesProps {
  data: SeriesRow[];
  interval: "day" | "week";
  onPick: (row: SeriesRow) => void;
}

/** Daily or weekly active cell-days for the chosen period. Click a bar to zoom the map to it. */
export function SeriesChart({ data, interval, onPick }: SeriesProps) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap={interval === "day" ? 1 : 3}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="period_start" {...AXIS} minTickGap={28} tickFormatter={(v: string) => v.slice(5)} />
        <YAxis {...AXIS} width={56} />
        <Tooltip
          contentStyle={TIP}
          cursor={{ fill: "rgba(242,184,75,.12)" }}
          labelFormatter={(v: string) => (interval === "week" ? `Week of ${v}` : v)}
          formatter={(v: number, _n, p) => [
            `${v.toLocaleString("en-GB")} (MODIS ${p.payload.modis_cell_days.toLocaleString("en-GB")}, VIIRS ${p.payload.viirs_cell_days.toLocaleString("en-GB")}, both ${p.payload.both_cell_days.toLocaleString("en-GB")})`,
            "Active cell-days",
          ]}
        />
        <Bar
          dataKey="value" name="Active cell-days" fill="#ea7a2b" cursor="pointer"
          onClick={(d: unknown) => onPick(((d as { payload?: SeriesRow }).payload ?? d) as SeriesRow)}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
