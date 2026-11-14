import { useEffect, useState } from "react";
import { api, ApiError } from "./services/api";
import type { AnnualRow, CalRow, Grid, HarmonizationMeta, SeasonalRow, Selection, Validation } from "./types";
import Overview from "./pages/Overview";
import CalendarPage from "./pages/CalendarPage";
import HistoricalPage from "./pages/HistoricalPage";
import SensorsPage from "./pages/SensorsPage";
import AnomaliesPage from "./pages/AnomaliesPage";
import DataPage from "./pages/DataPage";
import MethodologyPage from "./pages/MethodologyPage";

const TABS = [
  ["overview", "Overview"],
  ["calendar", "Burning calendar"],
  ["historical", "Historical analysis"],
  ["sensors", "Sensor harmonization"],
  ["anomalies", "Unusual activity"],
  ["data", "Data & downloads"],
  ["method", "Methodology"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [grid, setGrid] = useState<Grid>("5km");
  const [region, setRegion] = useState("Ghana");
  const [regions, setRegions] = useState<string[]>(["Ghana"]);
  const [rows, setRows] = useState<CalRow[]>([]);
  const [annual, setAnnual] = useState<AnnualRow[]>([]);
  const [seasonal, setSeasonal] = useState<SeasonalRow[]>([]);
  const [meta, setMeta] = useState<HarmonizationMeta | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.harmonization().then(setMeta).catch(() => setMeta(null));
    api.validation().then(setValidation).catch(() => setValidation(null));
  }, []);

  useEffect(() => {
    api.regions(grid).then((r) => setRegions(r.regions)).catch(() => undefined);
  }, [grid]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([api.calendar(grid, region), api.annual(grid, region), api.seasonal(grid, region)])
      .then(([c, a, s]) => {
        if (cancelled) return;
        setRows(c);
        setAnnual(a);
        setSeasonal(s);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setRows([]);
        setError(e instanceof ApiError && e.status === 503
          ? "No processed data is available yet. Run the data pipeline (see README), then reload."
          : `Could not load data: ${(e as Error).message}`);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [grid, region]);

  const openFromAnomaly = (s: Selection) => {
    setSelection(s);
    setTab("calendar");
  };

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="logo" aria-hidden="true">TG</span>
          <div>
            <h1>TerraGuard</h1>
            <p>Turning satellite fire observations into actionable environmental intelligence</p>
          </div>
        </div>
        <div className="controls">
          <label>
            Area
            <select value={region} onChange={(e) => { setRegion(e.target.value); }}>
              {regions.map((r) => <option key={r}>{r}</option>)}
            </select>
          </label>
          <label>
            Grid
            <select value={grid} onChange={(e) => setGrid(e.target.value as Grid)}>
              <option value="1km">1 km</option>
              <option value="2km">2 km</option>
              <option value="5km">5 km</option>
            </select>
          </label>
        </div>
      </header>
      <nav className="tabs" aria-label="Sections">
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id ? "on" : ""} onClick={() => setTab(id)} aria-current={tab === id ? "page" : undefined}>{label}</button>
        ))}
      </nav>
      <main>
        {loading && <p className="muted">Loading…</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {!loading && !error && tab === "overview" && <Overview rows={rows} annual={annual} region={region} onOpenCalendar={() => setTab("calendar")} />}
        {!loading && !error && tab === "calendar" && <CalendarPage rows={rows} grid={grid} region={region} selection={selection} onSelect={setSelection} />}
        {!loading && !error && tab === "historical" && <HistoricalPage annual={annual} seasonal={seasonal} region={region} />}
        {!loading && !error && tab === "sensors" && <SensorsPage rows={rows} meta={meta} validation={validation} grid={grid} region={region} />}
        {!loading && !error && tab === "anomalies" && <AnomaliesPage rows={rows} region={region} onOpen={openFromAnomaly} />}
        {!loading && !error && tab === "data" && <DataPage grid={grid} region={region} meta={meta} />}
        {tab === "method" && <MethodologyPage />}
      </main>
      <footer>
        Satellite detections are not unique fires and are not an emergency alert. Data: NASA FIRMS. Descriptions of unusual activity refer to history, not predictions.
      </footer>
    </div>
  );
}
