import type {
  AnnualRow, CalRow, CellCollection, Grid, HarmonizationMeta, SeasonalRow, Validation,
} from "../types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function getJSON<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && query.set(k, String(v)));
  const response = await fetch(`/api/${path}${query.size ? `?${query}` : ""}`);
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

export const api = {
  regions: (grid: Grid) => getJSON<{ regions: string[] }>("regions", { grid }),
  calendar: (grid: Grid, region: string) =>
    getJSON<{ data: CalRow[] }>("calendar", { grid, region }).then((r) => r.data),
  anomalies: (grid: Grid, region?: string) =>
    getJSON<{ data: CalRow[] }>("calendar/anomalies", { grid, region }).then((r) => r.data),
  seasonal: (grid: Grid, region: string) =>
    getJSON<{ data: SeasonalRow[] }>("seasonal", { grid, region }).then((r) => r.data),
  annual: (grid: Grid, region: string) =>
    getJSON<{ data: AnnualRow[] }>("annual", { grid, region }).then((r) => r.data),
  cells: (grid: Grid, year: number, month: number, region: string) =>
    getJSON<CellCollection>("map/cells", { grid, year, month, region: region === "Ghana" ? undefined : region }),
  boundaries: () => getJSON<GeoJSON.FeatureCollection>("boundaries"),
  harmonization: () => getJSON<HarmonizationMeta>("harmonization"),
  validation: () => getJSON<Validation>("validation"),
};

export function exportUrl(kind: "calendar" | "cells", params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && query.set(k, String(v)));
  return `/api/export/${kind}.csv?${query}`;
}
