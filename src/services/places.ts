import type { Place } from "../types";

export const RADII_KM = [10, 25, 50] as const;
export const DEFAULT_RADIUS_KM = 25;

/** A square box of the given half-width (km) around a point, as "west,south,east,north" degrees. */
export function boxAround(lat: number, lon: number, km: number): [number, number, number, number] {
  const dLat = km / 110.574;
  const dLon = km / (111.32 * Math.cos((lat * Math.PI) / 180));
  const r = (v: number) => Math.round(v * 1000) / 1000;
  return [r(lon - dLon), r(lat - dLat), r(lon + dLon), r(lat + dLat)];
}

export const boxToString = (b: readonly number[]) => b.join(",");

const KIND_LABEL: Record<Place["kind"], string> = { city: "City", town: "Town", place: "Place", region: "Region", country: "Country" };
export const kindLabel = (p: Place) => KIND_LABEL[p.kind];

/** "Ashanti, Ghana" for a place; just "Ghana" for a country. */
export function subtitle(p: Place): string {
  if (p.kind === "country") return "Country";
  return [p.admin1, p.country].filter(Boolean).join(", ");
}

export function coordinates(p: Place): string {
  return `${Math.abs(p.lat).toFixed(2)}°${p.lat >= 0 ? "N" : "S"} ${Math.abs(p.lon).toFixed(2)}°${p.lon >= 0 ? "E" : "W"}`;
}

/** What the map should show after a place is chosen. ``nonce`` makes choosing the same place twice fly again. */
export interface Focus {
  lat: number;
  lon: number;
  name: string;
  covered: boolean;
  box?: [number, number, number, number];
  pin: boolean;
  nonce: number;
}
