import type {
  AnnualRow, AreaList, AreaQuery, BridgeValidation, CalRow, CellCollection, CurrentComparison, HotspotPreview, HarmonizationMeta, MethodComparison, Period, Place, Quality, RainAssociation, RainRow, SeasonalRow, SensitivityReport, SeriesRow, Validation,
} from "../types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Params = Record<string, string | number | undefined | null>;

function queryString(params: Params): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && query.set(k, String(v)));
  return query.toString();
}

async function getJSON<T>(path: string, params: Params = {}, signal?: AbortSignal): Promise<T> {
  const qs = queryString(params);
  const response = await fetch(`/api/${path}${qs ? `?${qs}` : ""}`, { signal });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, String(detail));
  }
  return response.json() as Promise<T>;
}

/** Area parameters: a custom box overrides the named region. */
export function areaParams(q: AreaQuery): Params {
  return { grid: q.grid, sensor: q.sensor, bbox: q.bbox, region: q.bbox ? undefined : q.region };
}

export const api = {
  areas: () => getJSON<AreaList>("areas"),
  regions: (grid: AreaQuery["grid"]) => getJSON<{ regions: string[] }>("regions", { grid }),
  calendar: (q: AreaQuery) => getJSON<{ data: CalRow[] }>("calendar", areaParams(q)).then((r) => r.data),
  anomalies: (q: AreaQuery) => getJSON<{ data: CalRow[] }>("calendar/anomalies", areaParams(q)).then((r) => r.data),
  seasonal: (q: AreaQuery) => getJSON<{ data: SeasonalRow[] }>("seasonal", areaParams(q)).then((r) => r.data),
  annual: (q: AreaQuery) => getJSON<{ data: AnnualRow[] }>("annual", areaParams(q)).then((r) => r.data),
  cells: (q: AreaQuery, p: Period) => getJSON<CellCollection>("map/cells", { ...areaParams(q), start: p.start, end: p.end }),
  series: (q: AreaQuery, p: Period, interval: "day" | "week") =>
    getJSON<{ data: SeriesRow[] }>("series", { ...areaParams(q), start: p.start, end: p.end, interval }).then((r) => r.data),
  quality: (grid: AreaQuery["grid"]) => getJSON<Quality>("quality", { grid }),
  boundaries: (scope: "ghana" | "wa" = "ghana") => getJSON<GeoJSON.FeatureCollection>("boundaries", { scope }),
  harmonization: () => getJSON<HarmonizationMeta>("harmonization"),
  validation: () => getJSON<Validation>("validation"),
  rainfall: (region: string) => getJSON<{ data: RainRow[] }>("environment/rainfall", { region }).then((r) => r.data),
  rainfallAssociation: () => getJSON<RainAssociation>("environment/association"),
  searchPlaces: (q: string, limit: number, signal?: AbortSignal) =>
    getJSON<{ data: Place[]; covered_countries: string[] }>("places/search", { q, limit }, signal),
  sensitivity: () => getJSON<SensitivityReport>("sensitivity"),
  modelComparison: () => getJSON<MethodComparison>("model-comparison"),
  bridgeValidation: () => getJSON<BridgeValidation>("bridge-validation"),
  currentComparison: (q: AreaQuery, windowDays: number | "month") =>
    getJSON<CurrentComparison>("current-comparison", {
      ...areaParams(q), window_days: windowDays === "month" ? 30 : windowDays, mode: windowDays === "month" ? "month" : "days",
    }),
  hotspotPreview: (q: AreaQuery, p: Period, signal?: AbortSignal) =>
    getJSON<HotspotPreview>("hotspots/preview", { ...hotspotParams(q), start: p.start, end: p.end }, signal),
  seasonalAllRegions: (grid: AreaQuery["grid"]) => getJSON<{ data: SeasonalRow[] }>("seasonal/regions", { grid }).then((r) => r.data),
};

/** Hotspot downloads take no grid: they list individual detections. */
function hotspotParams(q: AreaQuery): Params {
  return { sensor: q.sensor, bbox: q.bbox, region: q.bbox ? undefined : q.region };
}

export function hotspotsUrl(q: AreaQuery, p: Period): string {
  return `/api/export/hotspots.csv?${queryString({ ...hotspotParams(q), start: p.start, end: p.end })}`;
}

export function reportUrl(format: "html" | "md", q: AreaQuery, extra: Params = {}): string {
  return `/api/export/report.${format}?${queryString({ ...areaParams(q), ...extra })}`;
}

export function exportUrl(kind: "calendar" | "cells" | "series", q: AreaQuery, extra: Params = {}): string {
  return `/api/export/${kind}.csv?${queryString({ ...areaParams(q), ...extra })}`;
}
