import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { AnnualRow, CalRow, SeasonalRow } from "../types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const AXIS = { stroke: "#8fa0b3", fontSize: 12 };
const GRID = "#243447";
const TIP = { background: "#0f1b2a", border: "1px solid #2c3f55", borderRadius: 6, color: "#e8eef5" };
const MODIS_COLOR = "#e8a33d";
const VIIRS_COLOR = "#5ec2b7";

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

export function SeasonalChart({ data }: { data: SeasonalRow[] }) {
  const rows = data.map((d) => ({ month: MONTHS[d.month - 1], range: [d.min, d.max], median: d.median, mean: d.mean, n: d.n_years }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="month" {...AXIS} />
        <YAxis {...AXIS} width={56} />
        <Tooltip contentStyle={TIP} />
        <Legend />
        <Area dataKey="range" name="Min–max across years" stroke="none" fill="#e8863d" fillOpacity={0.25} />
        <Line dataKey="median" name="Median" stroke="#f6c453" strokeWidth={2.5} dot={{ r: 3 }} />
        <Line dataKey="mean" name="Mean" stroke="#8fa0b3" strokeDasharray="4 4" dot={false} />
      </ComposedChart>
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
