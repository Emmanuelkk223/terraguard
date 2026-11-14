import type {
  AnnualRow, AreaQuery, CalRow, CellCollection, HarmonizationMeta, MethodComparison, Period, Quality, RainAssociation, RainRow, SeasonalRow, SensitivityReport, SeriesRow, Validation,
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

async function getJSON<T>(path: string, params: Params = {}): Promise<T> {
  const qs = queryString(params);
  const response = await fetch(`/api/${path}${qs ? `?${qs}` : ""}`);
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
  regions: (grid: AreaQuery["grid"]) => getJSON<{ regions: string[] }>("regions", { grid }),
  calendar: (q: AreaQuery) => getJSON<{ data: CalRow[] }>("calendar", areaParams(q)).then((r) => r.data),
  anomalies: (q: AreaQuery) => getJSON<{ data: CalRow[] }>("calendar/anomalies", areaParams(q)).then((r) => r.data),
  seasonal: (q: AreaQuery) => getJSON<{ data: SeasonalRow[] }>("seasonal", areaParams(q)).then((r) => r.data),
  annual: (q: AreaQuery) => getJSON<{ data: AnnualRow[] }>("annual", areaParams(q)).then((r) => r.data),
  cells: (q: AreaQuery, p: Period) => getJSON<CellCollection>("map/cells", { ...areaParams(q), start: p.start, end: p.end }),
  series: (q: AreaQuery, p: Period, interval: "day" | "week") =>
    getJSON<{ data: SeriesRow[] }>("series", { ...areaParams(q), start: p.start, end: p.end, interval }).then((r) => r.data),
  quality: (grid: AreaQuery["grid"]) => getJSON<Quality>("quality", { grid }),
  boundaries: () => getJSON<GeoJSON.FeatureCollection>("boundaries"),
  harmonization: () => getJSON<HarmonizationMeta>("harmonization"),
  validation: () => getJSON<Validation>("validation"),
  rainfall: (region: string) => getJSON<{ data: RainRow[] }>("environment/rainfall", { region }).then((r) => r.data),
  rainfallAssociation: () => getJSON<RainAssociation>("environment/association"),
  sensitivity: () => getJSON<SensitivityReport>("sensitivity"),
  modelComparison: () => getJSON<MethodComparison>("model-comparison"),
  seasonalAllRegions: (grid: AreaQuery["grid"]) => getJSON<{ data: SeasonalRow[] }>("seasonal/regions", { grid }).then((r) => r.data),
};

export function reportUrl(format: "html" | "md", q: AreaQuery, extra: Params = {}): string {
  return `/api/export/report.${format}?${queryString({ ...areaParams(q), ...extra })}`;
}

export function exportUrl(kind: "calendar" | "cells" | "series", q: AreaQuery, extra: Params = {}): string {
  return `/api/export/${kind}.csv?${queryString({ ...areaParams(q), ...extra })}`;
}
