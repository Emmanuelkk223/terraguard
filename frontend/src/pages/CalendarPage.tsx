import CalendarHeatmap from "../components/CalendarHeatmap";
import MapView from "../components/MapView";
import MonthDetail from "../components/MonthDetail";
import { exportUrl } from "../services/api";
import type { CalRow, Grid, Selection } from "../types";

interface Props {
  rows: CalRow[];
  grid: Grid;
  region: string;
  selection: Selection | null;
  onSelect: (s: Selection) => void;
}

export default function CalendarPage({ rows, grid, region, selection, onSelect }: Props) {
  const row = selection ? rows.find((r) => r.year === selection.year && r.month === selection.month) ?? null : null;
  return (
    <section>
      <h2>Burning activity calendar · {region}</h2>
      <p className="lead">
        Each cell is one month. Colour shows harmonized active cell-days. Select a month to compare it with the same
        calendar month in other years and see where the detections were.
      </p>
      <CalendarHeatmap rows={rows} selected={selection} onSelect={onSelect} />
      <div className="split">
        <MonthDetail row={row} />
        <MapView grid={grid} region={region} selection={selection} />
      </div>
      <div className="actions">
        <a className="button" href={exportUrl("calendar", { grid, region })}>Download calendar CSV</a>
        {selection && (
          <a className="button" href={exportUrl("cells", { grid, region: region === "Ghana" ? undefined : region, year: selection.year, month: selection.month })}>
            Download this month's cells CSV
          </a>
        )}
      </div>
    </section>
  );
}
