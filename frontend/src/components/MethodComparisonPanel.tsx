import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { Factor, Method, MethodComparison } from "../types";

const METHODS: [Method, string][] = [
  ["stat", "Seasonal baseline"],
  ["if_raw", "Isolation Forest (raw)"],
  ["if_deseason", "Isolation Forest (deseasonalised)"],
];
const FACTORS: [Factor, string][] = [
  ["x3", "a month tripled"],
  ["x2", "a month doubled"],
  ["div3", "a month cut to a third"],
];
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(1)}%`);
const num = (v: number | null | undefined) => (v === null || v === undefined ? "–" : v.toFixed(2));

/** Honest comparison of the explainable baseline with Isolation Forest (no ground truth exists). */
export default function MethodComparisonPanel({ area }: { area: string }) {
  const [data, setData] = useState<MethodComparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.modelComparison().then(setData).catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="muted">Method comparison is not available ({error}).</p>;
  if (!data) return <p className="muted">Loading method comparison…</p>;

  const { pooled } = data;
  const inj = pooled.synthetic_injection;
  const gaps = FACTORS.map(([f]) => Math.max(inj.auc[f].if_raw ?? 0, inj.auc[f].if_deseason ?? 0) - (inj.auc[f].stat ?? 0));
  const worstGap = Math.max(...gaps);
  const detail = data.areas[area];
  const trainEnd = String(data.protocol.train_years ?? "");

  return (
    <div className="method-panel">
      <h3>Baseline versus Isolation Forest</h3>
      <p className="lead">
        Both methods were fitted on the early years only ({trainEnd}) and then applied unchanged to later years, so neither
        has seen the months it is judged on. There are no ground-truth labels for “unusual burning”, so accuracy cannot be
        measured; this compares how the methods behave.
      </p>
      <table className="table">
        <thead>
          <tr><th>Measure ({pooled.areas} areas, {pooled.test_months.toLocaleString("en-GB")} held-out months)</th>
            {METHODS.map(([, label]) => <th key={label}>{label}</th>)}</tr>
        </thead>
        <tbody>
          <tr><th>Ordinary held-out months flagged</th>{METHODS.map(([m]) => <td key={m}>{pct(pooled.flag_rate_on_heldout_months[m])}</td>)}</tr>
          {FACTORS.map(([f, label]) => (
            <tr key={f}><th>Flags {label} (synthetic)</th>{METHODS.map(([m]) => <td key={m}>{pct(inj.detection_rate[f][m])}</td>)}</tr>
          ))}
          {FACTORS.map(([f, label]) => (
            <tr key={`auc-${f}`}><th>Ranking power, {label} (AUC)</th>{METHODS.map(([m]) => <td key={m}>{num(inj.auc[f][m])}</td>)}</tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        “Synthetic” rows scale real held-out months up or down one at a time; they measure sensitivity, not accuracy on real fires.
        AUC is threshold-free: the chance that an altered month scores higher than a genuine held-out month (0.5 = chance, 1 = perfect),
        which is the fair comparison because each method ships with a different alarm threshold.
      </p>
      <div className="callout">
        {worstGap <= 0.05
          ? "Isolation Forest ranks altered months about as well as the simple baseline (within 0.05 AUC in every case), so it brings no clear detection advantage here."
          : "Isolation Forest ranks at least one kind of change noticeably better than the baseline (more than 0.05 AUC); see the table."}{" "}
        It also gives no reason for a flag, no baseline to inspect and no sample size, which is why the explainable baseline is the
        primary method in this application and the forest is shown only as a check. Higher detection at its default setting comes with
        more false alarms on ordinary months.
      </div>

      {detail ? (
        <>
          <h3>Held-out months flagged in {area}</h3>
          <table className="table narrow">
            <tbody>
              {METHODS.map(([m, label]) => (
                <tr key={m}>
                  <th>{label}</th>
                  <td>{detail.flags[m].length ? detail.flags[m].join(", ") : "none"}</td>
                </tr>
              ))}
              <tr><th>Overlap, baseline vs forest (deseasonalised)</th><td>{num(detail.jaccard_stat_vs_if_deseason)} (1 = same months)</td></tr>
              <tr><th>Score rank correlation</th><td>{num(detail.spearman_abs_stat_vs_if.if_deseason)}</td></tr>
            </tbody>
          </table>
          <p className="muted small">{detail.test_months} months tested after training on {detail.train_months}.</p>
        </>
      ) : (
        <p className="muted small">Per-month comparison is available for Ghana and its named regions, not for custom areas.</p>
      )}
      <ul className="muted small">{data.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}
