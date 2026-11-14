import { useCallback, useEffect, useMemo, useState } from "react";
import { GeoJSON, MapContainer, Popup, Rectangle, TileLayer, useMap, useMapEvents } from "react-leaflet";
import type { LatLngBoundsExpression, PathOptions } from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../services/api";
import { infernoColor } from "../services/colors";
import type { CellCollection, CellFeature, Grid, Selection } from "../types";

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const regionStyle: PathOptions = { color: "#4f9d69", weight: 1, fill: false, opacity: 0.85 };
const fmt = (n: number) => n.toLocaleString("en-GB");

const GRID_KM: Record<Grid, number> = { "1km": 1, "2km": 2, "5km": 5 };
const KM_PER_DEG_LAT = 110.574;
const KM_PER_DEG_LON = 111.32 * Math.cos((7.95 * Math.PI) / 180);
const MIN_PIXELS = 4; // keep small cells visible at low zoom

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
  features: CellFeature[];
  maxDays: number;
  cellKm: number;
  pinned: number | null;
  onPick: (index: number) => void;
}

/** All cells as squares. Rebuilt only when data or zoom changes, not when a cell is pinned. */
function CellLayer({ features, maxDays, cellKm, pinned, onPick }: LayerProps) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) });

  const squares = useMemo(
    () =>
      features.map((f, i) => {
        const [lon, lat] = f.geometry.coordinates;
        const colour = infernoColor(f.properties.active_days / maxDays);
        return (
          <Rectangle
            key={i}
            bounds={cellBounds(lat, lon, cellKm, zoom)}
            bubblingMouseEvents={false}
            pathOptions={{ color: colour, fillColor: colour, fillOpacity: 0.85, weight: 0 }}
            eventHandlers={{ click: () => onPick(i) }}
          />
        );
      }),
    [features, maxDays, cellKm, zoom, onPick],
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

interface Props {
  grid: Grid;
  region: string;
  selection: Selection | null;
}

export default function MapView({ grid, region, selection }: Props) {
  const [cells, setCells] = useState<CellCollection | null>(null);
  const [outline, setOutline] = useState<GeoJSON.FeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Index of the cell whose popup is pinned open. It stays until another cell is clicked or it is closed.
  const [pinned, setPinned] = useState<number | null>(null);

  useEffect(() => {
    api.boundaries().then(setOutline).catch(() => setOutline(null));
  }, []);

  useEffect(() => {
    setPinned(null);
    if (!selection) {
      setCells(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .cells(grid, selection.year, selection.month, region)
      .then((c) => !cancelled && setCells(c))
      .catch((e: Error) => !cancelled && (setCells(null), setError(e.message)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [grid, region, selection]);

  const maxDays = useMemo(() => Math.max(1, ...(cells?.features.map((f) => f.properties.active_days) ?? [1])), [cells]);
  const onPick = useCallback((index: number) => setPinned(index), []);

  const active: CellFeature | null = pinned !== null && cells ? cells.features[pinned] ?? null : null;
  const [activeLon, activeLat] = active ? active.geometry.coordinates : [0, 0];

  return (
    <div className="map-card">
      <div className="map-head">
        {selection ? (
          <strong>{MONTH_NAMES[selection.month - 1]} {selection.year} · {region}</strong>
        ) : (
          <span className="muted">Select a month in the calendar to see where activity was detected.</span>
        )}
        {loading && <span className="muted"> · Loading…</span>}
        {cells && <span className="muted"> · {fmt(cells.features.length)} cells with detections</span>}
        {cells && cells.features.length > 0 && <span className="hint"> Click a cell to pin its details</span>}
      </div>
      <MapContainer center={[7.95, -1.0]} zoom={7} minZoom={6} className="map" preferCanvas>
        <TileLayer
          className="basemap-dark"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={18}
        />
        {outline && <GeoJSON data={outline} style={() => regionStyle} interactive={false} />}
        {cells && <CellLayer features={cells.features} maxDays={maxDays} cellKm={GRID_KM[grid]} pinned={pinned} onPick={onPick} />}
        {active && (
          <>
            <Popup
              key={pinned}
              position={[activeLat, activeLon]}
              closeOnClick={false}
              autoClose={false}
              maxWidth={280}
              eventHandlers={{ remove: () => setPinned((p) => (p === pinned ? null : p)) }}
            >
              <div className="popup">
                <div className="popup-title">{grid} cell</div>
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
          </>
        )}
      </MapContainer>
      {cells && cells.features.length > 0 && (
        <div className="legend" aria-hidden="true">
          <span>1 day</span>
          <div className="ramp" style={{ background: `linear-gradient(90deg, ${[0, 0.25, 0.5, 0.75, 1].map((s) => infernoColor(s)).join(",")})` }} />
          <span>{maxDays} days with a detection in the month (scale is relative to this month's busiest cell)</span>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {cells?.truncated && <p className="muted">Showing the most active cells only; export the CSV for all.</p>}
      <p className="muted small">Each square is a {grid} grid cell (drawn at least a few pixels wide so small cells stay visible); colour shows how many days in the month it had at least one detection.</p>
    </div>
  );
}
