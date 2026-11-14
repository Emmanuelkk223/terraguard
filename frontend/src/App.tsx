import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "./services/api";
import type {
  AnnualRow, AreaQuery, CalRow, Grid, HarmonizationMeta, SeasonalRow, Selection, Sensor, Validation,
} from "./types";
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

const SENSOR_LABEL: Record<Sensor, string> = {
  harmonized: "Both sensors (harmonized)",
  modis: "MODIS only",
  viirs: "VIIRS only",
};

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [grid, setGrid] = useState<Grid>("5km");
  const [region, setRegion] = useState("Ghana");
  const [bbox, setBbox] = useState<string | null>(null);
  const [sensor, setSensor] = useState<Sensor>("harmonized");
  const [regions, setRegions] = useState<string[]>(["Ghana"]);
  const [rows, setRows] = useState<CalRow[]>([]);
  const [rowsBoth, setRowsBoth] = useState<CalRow[]>([]);
  const [anomalies, setAnomalies] = useState<CalRow[]>([]);
  const [annual, setAnnual] = useState<AnnualRow[]>([]);
  const [seasonal, setSeasonal] = useState<SeasonalRow[]>([]);
  const [meta, setMeta] = useState<HarmonizationMeta | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const q: AreaQuery = useMemo(() => ({ grid, region, bbox, sensor }), [grid, region, bbox, sensor]);
  const areaName = bbox ? "Custom area" : region;
  const heading = sensor === "harmonized" ? areaName : `${areaName} · ${SENSOR_LABEL[sensor]}`;

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
    Promise.all([
      api.calendar(q), api.annual(q), api.seasonal(q), api.anomalies(q),
      // The sensor-comparison page always needs both sensors, whatever view is selected.
      sensor === "harmonized" ? Promise.resolve(null) : api.calendar({ ...q, sensor: "harmonized" }),
    ])
      .then(([c, a, s, an, both]) => {
        if (cancelled) return;
        setRows(c);
        setAnnual(a);
        setSeasonal(s);
        setAnomalies(an);
        setRowsBoth(both ?? c);
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
  }, [q, sensor]);

  const openFromAnomaly = (s: Selection) => {
    setSelection(s);
    setTab("calendar");
  };

  // Keep the current page mounted while new data loads, so a chosen period and map position survive view changes.
  const ready = !error && (rows.length > 0 || !loading);
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
            {bbox ? (
              <span className="chip" title={`West, south, east, north: ${bbox}`}>
                Custom area
                <button type="button" className="chip-x" onClick={() => setBbox(null)} aria-label="Clear custom area">✕</button>
              </span>
            ) : (
              <select value={region} onChange={(e) => setRegion(e.target.value)}>
                {regions.map((r) => <option key={r}>{r}</option>)}
              </select>
            )}
          </label>
          <label>
            Sensor view
            <select value={sensor} onChange={(e) => setSensor(e.target.value as Sensor)}>
              {(Object.keys(SENSOR_LABEL) as Sensor[]).map((s) => <option key={s} value={s}>{SENSOR_LABEL[s]}</option>)}
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
        {loading && (rows.length ? <span className="updating" role="status">Updating…</span> : <p className="muted">Loading…</p>)}
        {error && <p className="error" role="alert">{error}</p>}
        {ready && tab === "overview" && <Overview rows={rows} annual={annual} region={heading} onOpenCalendar={() => setTab("calendar")} />}
        {ready && tab === "calendar" && (
          <CalendarPage rows={rows} q={q} heading={heading} selection={selection} onSelect={setSelection} onBbox={setBbox} />
        )}
        {ready && tab === "historical" && <HistoricalPage annual={annual} seasonal={seasonal} rows={rows} grid={grid} region={heading} />}
        {ready && tab === "sensors" && <SensorsPage rows={rowsBoth} meta={meta} validation={validation} grid={grid} region={areaName} />}
        {ready && tab === "anomalies" && <AnomaliesPage rows={anomalies} region={heading} area={bbox ? "Custom area" : region} onOpen={openFromAnomaly} />}
        {ready && tab === "data" && <DataPage q={q} meta={meta} />}
        {tab === "method" && <MethodologyPage />}
      </main>
      <footer>
        Satellite detections are not unique fires and are not an emergency alert. Data: NASA FIRMS. Descriptions of unusual activity refer to history, not predictions.
      </footer>
    </div>
  );
}
