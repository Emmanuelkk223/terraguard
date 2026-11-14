import { useEffect, useMemo, useState } from "react";
import { CircleMarker, GeoJSON, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { PathOptions } from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../services/api";
import { infernoColor } from "../services/colors";
import type { CellCollection, Grid, Selection } from "../types";

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const regionStyle: PathOptions = { color: "#5f8f6b", weight: 1, fill: false, opacity: 0.8 };

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

  useEffect(() => {
    api.boundaries().then(setOutline).catch(() => setOutline(null));
  }, []);

  useEffect(() => {
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
  const radius = grid === "1km" ? 2 : grid === "2km" ? 3 : 5;

  return (
    <div className="map-card">
      <div className="map-head">
        {selection ? (
          <strong>{MONTH_NAMES[selection.month - 1]} {selection.year} · {region}</strong>
        ) : (
          <span className="muted">Select a month in the calendar to see where activity was detected.</span>
        )}
        {loading && <span className="muted"> Loading…</span>}
        {cells && <span className="muted"> {cells.features.length.toLocaleString("en-GB")} cells with detections</span>}
      </div>
      <MapContainer center={[7.95, -1.0]} zoom={7} minZoom={6} className="map" preferCanvas>
        <TileLayer
          className="basemap-dark"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={18}
        />
        {outline && <GeoJSON data={outline} style={() => regionStyle} />}
        {cells?.features.map((f, i) => {
          const [lon, lat] = f.geometry.coordinates;
          const p = f.properties;
          return (
            <CircleMarker
              key={i}
              center={[lat, lon]}
              radius={radius}
              pathOptions={{ color: infernoColor(p.active_days / maxDays), fillColor: infernoColor(p.active_days / maxDays), fillOpacity: 0.75, weight: 0 }}
            >
              <Tooltip>
                <div>
                  <b>{p.active_days}</b> day{p.active_days === 1 ? "" : "s"} with detections<br />
                  MODIS detections: {p.modis_detections.toLocaleString("en-GB")}<br />
                  VIIRS detections: {p.viirs_detections.toLocaleString("en-GB")}<br />
                  Days seen by both sensors: {p.days_both}
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}
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
      <p className="muted small">Each circle is a {grid} grid cell; colour shows how many days in the month it had at least one detection. Cells are detections, not individual fires.</p>
    </div>
  );
}
