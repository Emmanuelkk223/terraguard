import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleMarker, GeoJSON, MapContainer, Popup, Rectangle, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import type { LatLng, LatLngBoundsExpression, PathOptions } from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../services/api";
import { rampColor, type RampName } from "../services/colors";
import type { Focus } from "../services/places";
import type { AreaQuery, CellCollection, CellFeature, Grid, Period } from "../types";

const regionStyle: PathOptions = { color: "#4f9d69", weight: 1, fill: false, opacity: 0.85 };
const boxStyle: PathOptions = { color: "#f2b84b", weight: 2, dashArray: "6 4", fillColor: "#f2b84b", fillOpacity: 0.06 };
const fmt = (n: number) => n.toLocaleString("en-GB");

const GRID_KM: Record<Grid, number> = { "1km": 1, "2km": 2, "5km": 5 };
const KM_PER_DEG_LAT = 110.574;
const KM_PER_DEG_LON = 111.32 * Math.cos((7.95 * Math.PI) / 180);
const MIN_PIXELS = 4; // keep small cells visible at low zoom

type Box = [number, number, number, number]; // west, south, east, north

const parseBox = (text: string | null): Box | null => {
  if (!text) return null;
  const parts = text.split(",").map(Number);
  return parts.length === 4 && parts.every(Number.isFinite) ? (parts as Box) : null;
};

/** Square footprint of a grid cell, enlarged to a minimum on-screen size. */
function cellBounds(lat: number, lon: number, cellKm: number, zoom: number): LatLngBoundsExpression {
  const metresPerPixel = (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** zoom;
  const halfKm = Math.max(cellKm / 2, (MIN_PIXELS * metresPerPixel) / 2000);
  return [
    [lat - halfKm / KM_PER_DEG_LAT, lon - halfKm / KM_PER_DEG_LON],
    [lat + halfKm / KM_PER_DEG_LAT, lon + halfKm / KM_PER_DEG_LON],
  ];
}

interface LayerProps {
  ramp: RampName;
  features: CellFeature[];
  maxDays: number;
  cellKm: number;
  pinned: number | null;
  drawing: boolean;
  onPick: (index: number) => void;
}

/** All cells as squares. Rebuilt only when data or zoom changes, not when a cell is pinned. */
function CellLayer({ ramp, features, maxDays, cellKm, pinned, drawing, onPick }: LayerProps) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) });

  const squares = useMemo(
    () =>
      features.map((f, i) => {
        const [lon, lat] = f.geometry.coordinates;
        const colour = rampColor(ramp, f.properties.active_days / maxDays);
        return (
          <Rectangle
            key={`${drawing}-${i}`}
            bounds={cellBounds(lat, lon, cellKm, zoom)}
            interactive={!drawing}
            bubblingMouseEvents={false}
            pathOptions={{ color: colour, fillColor: colour, fillOpacity: 0.85, weight: 0 }}
            eventHandlers={drawing ? {} : { click: () => onPick(i) }}
          />
        );
      }),
    [features, maxDays, cellKm, zoom, onPick, drawing, ramp],
  );

  const ring = pinned !== null ? features[pinned] : null;
  return (
    <>
      {squares}
      {ring && (
        <Rectangle
          bounds={cellBounds(ring.geometry.coordinates[1], ring.geometry.coordinates[0], cellKm * 1.6, zoom)}
          interactive={false}
          pathOptions={{ color: "#ffffff", weight: 2, fill: false }}
        />
      )}
    </>
  );
}

/** Drag-to-draw rectangle. While active, map panning is off so a drag draws instead. */
function DrawLayer({ active, onDone }: { active: boolean; onDone: (box: Box) => void }) {
  const map = useMap();
  const [start, setStart] = useState<LatLng | null>(null);
  const [current, setCurrent] = useState<LatLng | null>(null);

  useEffect(() => {
    const el = map.getContainer();
    if (active) {
      map.dragging.disable();
      el.style.cursor = "crosshair";
    } else {
      map.dragging.enable();
      el.style.cursor = "";
      setStart(null);
      setCurrent(null);
    }
    return () => {
      map.dragging.enable();
      el.style.cursor = "";
    };
  }, [active, map]);

  useMapEvents({
    mousedown(e) {
      if (!active) return;
      setStart(e.latlng);
      setCurrent(e.latlng);
    },
    mousemove(e) {
      if (active && start) setCurrent(e.latlng);
    },
    mouseup(e) {
      if (!active || !start) return;
      const w = Math.min(start.lng, e.latlng.lng), eEdge = Math.max(start.lng, e.latlng.lng);
      const s = Math.min(start.lat, e.latlng.lat), n = Math.max(start.lat, e.latlng.lat);
      setStart(null);
      setCurrent(null);
      if (eEdge - w > 0.01 && n - s > 0.01) onDone([w, s, eEdge, n].map((v) => Math.round(v * 1000) / 1000) as Box);
    },
  });

  if (!active || !start || !current) return null;
  return <Rectangle bounds={[[start.lat, start.lng], [current.lat, current.lng]]} interactive={false} pathOptions={boxStyle} />;
}

/** Moves the map to a place chosen in the search box (and marks it). */
function FlyToPlace({ focus }: { focus: Focus | null }) {
  const map = useMap();
  useEffect(() => {
    if (!focus) return;
    if (focus.box) {
      map.flyToBounds([[focus.box[1], focus.box[0]], [focus.box[3], focus.box[2]]], { padding: [30, 30], duration: 1.1, maxZoom: 11 });
    } else {
      map.flyTo([focus.lat, focus.lon], 10, { duration: 1.1 });
    }
  }, [focus?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!focus?.pin) return null;
  return (
    <CircleMarker
      center={[focus.lat, focus.lon]}
      radius={9}
      interactive={false}
      pathOptions={{ color: "#ffffff", weight: 3, fillColor: focus.covered ? "#f2b84b" : "#8a9db2", fillOpacity: 1 }}
    >
      <Tooltip permanent direction="top" offset={[0, -10]} className="place-pin">{focus.name}</Tooltip>
    </CircleMarker>
  );
}

interface Props {
  q: AreaQuery;
  period: Period | null;
  onBbox: (bbox: string | null) => void;
  focus?: Focus | null;
  ramp?: RampName;
  outsideGhana?: boolean;
}

export default function MapView({ q, period, onBbox, focus = null, ramp = "inferno", outsideGhana = false }: Props) {
  const [cells, setCells] = useState<CellCollection | null>(null);
  const [outline, setOutline] = useState<GeoJSON.FeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Index of the cell whose popup is pinned open. It stays until another cell is clicked or it is closed.
  const [pinned, setPinned] = useState<number | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [fields, setFields] = useState<string[]>(["", "", "", ""]);
  const [fieldError, setFieldError] = useState<string | null>(null);

  const box = parseBox(q.bbox);

  useEffect(() => {
    api.boundaries(outsideGhana ? "wa" : "ghana").then(setOutline).catch(() => setOutline(null));
  }, []);

  useEffect(() => {
    setFields(box ? box.map(String) : ["", "", "", ""]);
    setFieldError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.bbox]);

  useEffect(() => {
    setPinned(null);
    if (!period) {
      setCells(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .cells(q, period)
      .then((c) => !cancelled && setCells(c))
      .catch((e: Error) => !cancelled && (setCells(null), setError(e.message)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [q, period?.start, period?.end]); // eslint-disable-line react-hooks/exhaustive-deps

  const maxDays = useMemo(() => Math.max(1, ...(cells?.features.map((f) => f.properties.active_days) ?? [1])), [cells]);
  const onPick = useCallback((index: number) => setPinned(index), []);

  const applyFields = () => {
    const values = fields.map(Number);
    const [w, s, e, n] = values;
    if (fields.some((f) => f.trim() === "") || values.some((v) => !Number.isFinite(v))) return setFieldError("Enter all four numbers.");
    if (!(w < e && w >= -180 && e <= 180)) return setFieldError("West must be less than east (−180 to 180).");
    if (!(s < n && s >= -90 && n <= 90)) return setFieldError("South must be less than north (−90 to 90).");
    setFieldError(null);
    onBbox(values.join(","));
  };

  const active: CellFeature | null = pinned !== null && cells ? cells.features[pinned] ?? null : null;
  const [activeLon, activeLat] = active ? active.geometry.coordinates : [0, 0];
  const viewText = q.sensor === "harmonized" ? "either sensor" : q.sensor === "modis" ? "MODIS" : "VIIRS";

  return (
    <div className="map-card">
      <div className="map-head">
        {period ? (
          <strong>{period.start === period.end ? period.start : `${period.start} → ${period.end}`}</strong>
        ) : (
          <span className="muted">Select a month in the calendar to see where activity was detected.</span>
        )}
        {loading && <span className="muted"> · Loading…</span>}
        {cells && <span className="muted"> · {fmt(cells.features.length)} cells with detections ({viewText})</span>}
        {cells && cells.features.length > 0 && !drawing && <span className="hint"> Click a cell to pin its details</span>}
        {drawing && <span className="hint"> Drag on the map to draw your area</span>}
      </div>

      <div className="area-tools">
        <button type="button" className={`tool ${drawing ? "on" : ""}`} onClick={() => { setDrawing((d) => !d); setPinned(null); }}>
          {drawing ? "Cancel drawing" : "Draw area"}
        </button>
        {(["West", "South", "East", "North"] as const).map((label, i) => (
          <label key={label} className="coord">
            {label}
            <input
              type="number" step="0.001" value={fields[i]} aria-label={`${label} edge in degrees`}
              onChange={(e) => setFields((f) => f.map((v, j) => (j === i ? e.target.value : v)))}
              onKeyDown={(e) => e.key === "Enter" && applyFields()}
            />
          </label>
        ))}
        <button type="button" className="tool" onClick={applyFields}>Apply area</button>
        {q.bbox && <button type="button" className="tool" onClick={() => onBbox(null)}>Clear area</button>}
        {fieldError && <span className="error inline">{fieldError}</span>}
      </div>

      <div className={`map-wrap ${drawing ? "drawing" : ""}`}>
      <MapContainer center={[7.95, -1.0]} zoom={7} minZoom={4} className="map" preferCanvas>
        <TileLayer
          className="basemap-dark"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={18}
        />
        {outline && <GeoJSON data={outline} style={() => regionStyle} interactive={false} />}
        {cells && (
          <CellLayer ramp={ramp} features={cells.features} maxDays={maxDays} cellKm={GRID_KM[q.grid]} pinned={pinned} drawing={drawing} onPick={onPick} />
        )}
        {box && <Rectangle bounds={[[box[1], box[0]], [box[3], box[2]]]} interactive={false} pathOptions={boxStyle} />}
        <FlyToPlace focus={focus} />
        <DrawLayer active={drawing} onDone={(b) => { setDrawing(false); onBbox(b.join(",")); }} />
        {active && (
          <Popup
            key={pinned}
            position={[activeLat, activeLon]}
            closeOnClick={false}
            autoClose={false}
            maxWidth={280}
            eventHandlers={{ remove: () => setPinned((p) => (p === pinned ? null : p)) }}
          >
            <div className="popup">
              <div className="popup-title">{q.grid} cell</div>
              <div className="popup-coord">{activeLat.toFixed(3)}°N, {Math.abs(activeLon).toFixed(3)}°{activeLon < 0 ? "W" : "E"}</div>
              <dl>
                <dt>Days with a detection</dt><dd>{active.properties.active_days}</dd>
                <dt>MODIS detections</dt><dd>{fmt(active.properties.modis_detections)}</dd>
                <dt>VIIRS detections</dt><dd>{fmt(active.properties.viirs_detections)}</dd>
                <dt>Days seen by both</dt><dd>{active.properties.days_both}</dd>
              </dl>
              <p>Detection records, not fires. One fire can leave several records, and VIIRS records more of them.</p>
            </div>
          </Popup>
        )}
      </MapContainer>
      </div>
      {cells && cells.features.length > 0 && (
        <div className="legend" aria-hidden="true">
          <span>1 day</span>
          <div className="ramp" style={{ background: `linear-gradient(90deg, ${[0, 0.25, 0.5, 0.75, 1].map((s) => rampColor(ramp, s)).join(",")})` }} />
          <span>{maxDays} days with a detection in the period (scale is relative to the busiest cell shown)</span>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {cells?.truncated && <p className="muted">Showing the most active cells only; export the CSV for all.</p>}
      <p className="muted small">Each square is a {q.grid} grid cell (drawn at least a few pixels wide so small cells stay visible). The dashed amber box is your custom area.</p>
    </div>
  );
}
