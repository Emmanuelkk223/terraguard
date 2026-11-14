import type { RainRow } from "../types";

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** Plain-language description of a month's rainfall relative to the same month in other years. */
export function describeRain(row: RainRow): string {
  const month = MONTH_NAMES[row.month - 1];
  const p = row.rain_percentile;
  const rank = p >= 0.95 ? `the wettest ${month} in the record` : p <= 0.05 ? `the driest ${month} in the record`
    : p >= 0.8 ? `wetter than usual for ${month}` : p <= 0.2 ? `drier than usual for ${month}` : `typical for ${month}`;
  return `${row.rainfall_mm_per_day.toFixed(2)} mm/day (typical ${row.rain_median_mm_per_day.toFixed(2)}): ${rank}`;
}
