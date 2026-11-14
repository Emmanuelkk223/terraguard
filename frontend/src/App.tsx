import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "./services/api";
import type {
  AnnualRow, AreaQuery, CalRow, Grid, HarmonizationMeta, Place, SeasonalRow, Selection, Sensor, Validation,
} from "./types";
import Overview from "./pages/Overview";
import CalendarPage from "./pages/CalendarPage";
import HistoricalPage from "./pages/HistoricalPage";
import SensorsPage from "./pages/SensorsPage";
import AnomaliesPage from "./pages/AnomaliesPage";
import DataPage from "./pages/DataPage";
import MethodologyPage from "./pages/MethodologyPage";
import PlaceBanner from "./components/PlaceBanner";
import PlaceSearch from "./components/PlaceSearch";
import { boxAround, boxToString, DEFAULT_RADIUS_KM, type Focus } from "./services/places";

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
  const [attempt, setAttempt] = useState(0); // bumped to reload the data
  const retries = useRef(0);
  const [place, setPlace] = useState<Place | null>(null); // a town chosen through search
  const [radiusKm, setRadiusKm] = useState(DEFAULT_RADIUS_KM);
  const [focus, setFocus] = useState<Focus | null>(null);
  const nonce = useRef(0);

  const q: AreaQuery = useMemo(() => ({ grid, region, bbox, sensor }), [grid, region, bbox, sensor]);
  const areaName = bbox ? "Custom area" : region; // used for logic: rainfall and model comparison exist for named areas only
  const townArea = bbox && place && place.covered && place.kind !== "country" && place.kind !== "region";
  const areaTitle = townArea ? `${place!.name} (${radiusKm} km)` : areaName; // used for display
  const heading = sensor === "harmonized" ? areaTitle : `${areaTitle} · ${SENSOR_LABEL[sensor]}`;

  /** Draw/type a box yourself: that replaces any place chosen through search. */
  const setBboxManually = (box: string | null) => {
    setPlace(null);
    setBbox(box);
  };

  const flyTo = (next: Omit<Focus, "nonce">) => {
    nonce.current += 1;
    setFocus({ ...next, nonce: nonce.current });
  };

  const choosePlace = (p: Place) => {
    setTab("calendar");
    if (p.kind === "country") {
      setPlace(null);
      if (p.covered) {
        setBbox(null);
        setRegion("Ghana");
      } else {
        setPlace(p); // explains that there is no data for this country yet
        setBbox(null);
        setRegion("Ghana"); // the analysis stays on the data we have; only the map moves
      }
      flyTo({ lat: p.lat, lon: p.lon, name: p.name, covered: p.covered, box: p.bbox, pin: false });
    } else if (p.kind === "region") {
      setPlace(null);
      setBbox(null);
      setRegion(p.region ?? p.name.replace(/ Region$/, ""));
      flyTo({ lat: p.lat, lon: p.lon, name: p.name, covered: true, box: p.bbox, pin: false });
    } else if (p.covered) {
      const box = boxAround(p.lat, p.lon, radiusKm);
      setPlace(p);
      setBbox(boxToString(box));
      flyTo({ lat: p.lat, lon: p.lon, name: p.name, covered: true, box, pin: true });
    } else {
      setPlace(p); // no data for this country: the page returns to Ghana and only the map moves
      setBbox(null);
      setRegion("Ghana");
      flyTo({ lat: p.lat, lon: p.lon, name: p.name, covered: false, pin: true });
    }
  };

  const changeRadius = (km: number) => {
    setRadiusKm(km);
    if (place && townArea) {
      const box = boxAround(place.lat, place.lon, km);
      setBbox(boxToString(box));
      flyTo({ lat: place.lat, lon: place.lon, name: place.name, covered: true, box, pin: true });
    }
  };

  const clearPlace = () => {
    setPlace(null);
    setBbox(null);
    setRegion("Ghana");
    flyTo({ lat: 7.95, lon: -1.0, name: "Ghana", covered: true, box: [-3.3, 4.7, 1.3, 11.2], pin: false });
  };

  useEffect(() => {
    api.harmonization().then(setMeta).catch(() => setMeta(null));
    api.validation().then(setValidation).catch(() => setValidation(null));
  }, []);

  useEffect(() => {
    api.regions(grid).then((r) => setRegions(r.regions)).catch(() => undefined);
  }, [grid]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    setLoading(true);
    setError(null);
    Promise.all([
      api.calendar(q), api.annual(q), api.seasonal(q), api.anomalies(q),
      // The sensor-comparison page always needs both sensors, whatever view is selected.
      sensor === "harmonized" ? Promise.resolve(null) : api.calendar({ ...q, sensor: "harmonized" }),
    ])
      .then(([c, a, s, an, both]) => {
        if (cancelled) return;
        retries.current = 0;
        setRows(c);
        setAnnual(a);
        setSeasonal(s);
        setAnomalies(an);
        setRowsBoth(both ?? c);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setRows([]);
        const updating = e instanceof ApiError && e.status === 503 && /updating/i.test(e.message);
        if (updating && retries.current < 4) {
          // The pipeline is rewriting a data file right now: wait a moment and try again.
          retries.current += 1;
          setError(null);
          timer = window.setTimeout(() => setAttempt((n) => n + 1), 3000);
          return;
        }
        setError(e instanceof ApiError && e.status === 503
          ? (updating ? "The data is being updated and could not be read yet." : "No processed data is available yet. Run the data pipeline (see README), then reload.")
          : `Could not load data: ${(e as Error).message}`);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [q, sensor, attempt]);

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
        <PlaceSearch onSelect={choosePlace} />
        <div className="controls">
          <label>
            Area
            {bbox ? (
              <span className="chip" title={`West, south, east, north: ${bbox}`}>
                {townArea ? place!.name : "Custom area"}
                <button type="button" className="chip-x" onClick={() => { setPlace(null); setBbox(null); }} aria-label="Clear the chosen area">✕</button>
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
      {place && (
        <PlaceBanner
          place={place}
          radiusKm={radiusKm}
          onRadius={changeRadius}
          onWholeRegion={() => { const r = place.region; setPlace(null); setBbox(null); if (r) setRegion(r); }}
          onClear={clearPlace}
        />
      )}
      <main>
        {loading && (rows.length ? <span className="updating" role="status">Updating…</span> : <p className="muted">Loading…</p>)}
        {error && (
          <p className="error" role="alert">
            {error}{" "}
            <button type="button" className="tool" onClick={() => { retries.current = 0; setAttempt((n) => n + 1); }}>Retry</button>
          </p>
        )}
        {ready && tab === "overview" && <Overview rows={rows} annual={annual} region={heading} onOpenCalendar={() => setTab("calendar")} />}
        {ready && tab === "calendar" && (
          <CalendarPage rows={rows} q={q} heading={heading} selection={selection} onSelect={setSelection} onBbox={setBboxManually} focus={focus} />
        )}
        {ready && tab === "historical" && <HistoricalPage annual={annual} seasonal={seasonal} rows={rows} grid={grid} region={heading} area={areaName} />}
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
