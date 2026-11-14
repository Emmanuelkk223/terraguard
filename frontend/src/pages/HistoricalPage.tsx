import { AnnualChart, SeasonalChart } from "../components/Charts";
import type { AnnualRow, SeasonalRow } from "../types";

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export default function HistoricalPage({ annual, seasonal, region }: { annual: AnnualRow[]; seasonal: SeasonalRow[]; region: string }) {
  const peak = seasonal.reduce<SeasonalRow | null>((b, s) => (!b || s.median > b.median ? s : b), null);
  const quiet = seasonal.reduce<SeasonalRow | null>((b, s) => (!b || s.median < b.median ? s : b), null);
  return (
    <section>
      <h2>Historical analysis · {region}</h2>
      <h3>Seasonal pattern</h3>
      <p className="muted">Median and range of active cell-days for each calendar month, across years with full coverage.</p>
      {seasonal.length ? <SeasonalChart data={seasonal} /> : <p className="muted">No seasonal data.</p>}
      {peak && quiet && (
        <p>
          Typical peak: <b>{MONTH_NAMES[peak.month - 1]}</b> (median {Math.round(peak.median).toLocaleString("en-GB")}, based on {peak.n_years} years).
          Typical low: <b>{MONTH_NAMES[quiet.month - 1]}</b> (median {Math.round(quiet.median).toLocaleString("en-GB")}).
        </p>
      )}
      <h3>Annual totals</h3>
      <p className="muted">Muted bars are partial years — some months lack sufficient satellite record coverage — and must not be compared with complete years.</p>
      {annual.length ? <AnnualChart data={annual} /> : <p className="muted">No annual data.</p>}
    </section>
  );
}
