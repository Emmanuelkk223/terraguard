import type { SeasonalRow } from "../types";

export const MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export interface Season {
  months: number[]; // calendar months (1-12) in the season
  label: string; // e.g. "Nov–Mar"
  peak: number; // month with the highest median
  share: number; // share of a typical year's activity that falls in the season (0-1)
}

/** Contiguous runs of months on a circular calendar, e.g. [11,12,1,2,3] -> "Nov–Mar". */
function describe(months: number[]): string {
  const set = new Set(months);
  if (set.size === 12) return "all year";
  const runs: number[][] = [];
  for (let m = 1; m <= 12; m++) {
    const prev = m === 1 ? 12 : m - 1;
    if (set.has(m) && !set.has(prev)) {
      const run = [m];
      let next = (m % 12) + 1;
      while (set.has(next) && next !== m) {
        run.push(next);
        next = (next % 12) + 1;
      }
      runs.push(run);
    }
  }
  return runs
    .map((r) => (r.length === 1 ? MONTH_ABBR[r[0] - 1] : `${MONTH_ABBR[r[0] - 1]}–${MONTH_ABBR[r[r.length - 1] - 1]}`))
    .join(", ");
}

/** Months whose typical (median) activity is at least ``fraction`` of the busiest month's. */
export function burningSeason(seasonal: SeasonalRow[], fraction: number): Season | null {
  const medians = new Map(seasonal.map((s) => [s.month, s.median]));
  const peakValue = Math.max(0, ...medians.values());
  if (peakValue <= 0) return null;
  const months = [...medians.entries()].filter(([, v]) => v >= fraction * peakValue).map(([m]) => m).sort((a, b) => a - b);
  const peak = [...medians.entries()].reduce((best, e) => (e[1] > best[1] ? e : best))[0];
  const total = [...medians.values()].reduce((s, v) => s + v, 0);
  const inSeason = months.reduce((s, m) => s + (medians.get(m) ?? 0), 0);
  return { months, label: describe(months), peak, share: total > 0 ? inSeason / total : 0 };
}
