"""Compare the seasonal median/MAD baseline with Isolation Forest, honestly.

There are no ground-truth labels for "unusual burning activity", so accuracy, precision and
recall cannot be measured and are not reported. What this module measures instead:

1. Agreement. Both methods are fitted on the early years only (default 2012-2019) and applied
   unchanged to later years (forward protocol, so neither sees the test period). We report how
   much their flagged months overlap and how their scores rank months.
2. Stability. The share of held-out months each method flags (a method fitted on early data
   should not flag a large share of ordinary later months).
3. Sensitivity on a CLEARLY SYNTHETIC test. Real held-out months are scaled up or down (x3, x2,
   /3), one at a time, and we check whether each method notices. This says how large a change a
   method can detect; it does not say how well it finds real fires. Synthetic values are used
   only inside this test and are never stored as observations. Because each method ships with a
   different false-alarm rate, the threshold-free AUC (how often an altered month scores higher than
   a genuine held-out month) is reported as the fair comparison of ranking power.

Methods:
  stat          fixed same-calendar-month median and MAD (log scale) from the training years, with a
                threshold calibrated to the training-set size (see calibration.py)
  if_raw        Isolation Forest on log activity and the month of the year (learns seasonality itself)
  if_deseason   Isolation Forest on log activity relative to the training median of that month
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import IsolationForest

from .calibration import MAD_SCALE, threshold_for

TRAIN_END_YEAR = 2019
CONTAMINATION = 0.05
MIN_LEVEL = 30  # injection test only uses months whose typical level is at least this many cell-days
MULTIPLIERS = {"x3": 3.0, "x2": 2.0, "div3": 1.0 / 3.0}
METHODS = ("stat", "if_raw", "if_deseason")
SERIES = ("active_cell_days", "modis_cell_days", "viirs_cell_days")
MIN_TRAIN_PER_MONTH = 5


def month_statistics(train: pd.DataFrame) -> dict[int, dict[str, float]]:
    """Per calendar month: median and MAD of the main series, and medians of all series."""
    stats: dict[int, dict[str, float]] = {}
    for month, group in train.groupby("month"):
        if len(group) < MIN_TRAIN_PER_MONTH:
            continue
        values = group["active_cell_days"].to_numpy(float)
        median = float(np.median(values))
        logs = np.log1p(values)
        log_median = float(np.median(logs))
        entry = {"median": median, "mad": float(np.median(np.abs(values - median))), "n": len(values),
                 "log_median": log_median, "log_mad": float(np.median(np.abs(logs - log_median)))}
        for name in SERIES:
            entry[f"median_{name}"] = float(group[name].median())
        stats[int(month)] = entry
    return stats


def stat_scores(values: np.ndarray, months: np.ndarray, stats: dict[int, dict[str, float]]) -> tuple[np.ndarray, np.ndarray]:
    """Log-scale robust score and calibrated limit per month.

    The score is NaN when the month has no usable baseline (no history, or zero spread).
    """
    scores = np.full(len(values), np.nan)
    limits = np.full(len(values), np.nan)
    for i, (value, month) in enumerate(zip(values, months)):
        s = stats.get(int(month))
        if s is None:
            continue
        limits[i] = threshold_for(int(s["n"]))
        if s["log_mad"] > 0:
            scores[i] = (np.log1p(value) - s["log_median"]) / (MAD_SCALE * s["log_mad"])
    return scores, limits


def _stat_flags(scores: np.ndarray, limits: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return np.abs(scores) >= limits  # NaN compares False, so unscorable months are never flagged


def feature_matrix(
    frame: pd.DataFrame, stats: dict[int, dict[str, float]], deseasonalise: bool,
) -> np.ndarray:
    """Features for Isolation Forest, from the frame's three series and months."""
    logs = np.log1p(frame[list(SERIES)].to_numpy(float))
    months = frame["month"].to_numpy()
    if not deseasonalise:
        angle = 2 * np.pi * (months - 1) / 12
        return np.column_stack([np.sin(angle), np.cos(angle), logs])
    baseline = np.array([[np.log1p(stats[int(m)][f"median_{name}"]) for name in SERIES] for m in months])
    return logs - baseline


class _Forest:
    """Isolation Forest with a flag threshold set from the TRAINING scores only."""

    def __init__(self, train_features: np.ndarray, seed: int) -> None:
        self.model = IsolationForest(n_estimators=300, random_state=seed).fit(train_features)
        train_scores = -self.model.score_samples(train_features)  # higher = more anomalous
        self.cutoff = float(np.quantile(train_scores, 1 - CONTAMINATION))

    def score(self, features: np.ndarray) -> np.ndarray:
        return -self.model.score_samples(features)

    def flags(self, features: np.ndarray) -> np.ndarray:
        return self.score(features) > self.cutoff


def _auc(altered: np.ndarray, genuine: np.ndarray) -> float | None:
    """P(altered score > genuine score), ties counted half (Mann-Whitney AUC)."""
    if len(altered) < 3 or len(genuine) < 3:
        return None
    ranks = rankdata(np.concatenate([altered, genuine]))
    n_a, n_g = len(altered), len(genuine)
    return float((ranks[:n_a].sum() - n_a * (n_a + 1) / 2) / (n_a * n_g))


def _json_safe(value):
    """Replace NaN/inf with None so the report is strict JSON (browsers and FastAPI reject NaN)."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _jaccard(a: set, b: set) -> float | None:
    return round(len(a & b) / len(a | b), 3) if (a or b) else None


def compare_area(
    frame: pd.DataFrame, *, train_end: int = TRAIN_END_YEAR, seed: int = 0,
) -> dict[str, object] | None:
    """Fit on years <= ``train_end`` and evaluate on later years. Returns None if data are insufficient."""
    usable = frame[frame["coverage_ok"].astype(bool)].sort_values(["year", "month"]).reset_index(drop=True)
    train, test = usable[usable["year"] <= train_end], usable[usable["year"] > train_end].reset_index(drop=True)
    stats = month_statistics(train)
    if len(stats) < 12 or len(test) < 12:
        return None
    test = test[test["month"].isin(stats)].reset_index(drop=True)
    train = train[train["month"].isin(stats)].reset_index(drop=True)

    forests = {
        "if_raw": (_Forest(feature_matrix(train, stats, False), seed), False),
        "if_deseason": (_Forest(feature_matrix(train, stats, True), seed), True),
    }
    months = test["month"].to_numpy()
    score_stat, limit_stat = stat_scores(test["active_cell_days"].to_numpy(float), months, stats)
    flag = {"stat": _stat_flags(score_stat, limit_stat)}
    anomaly = {}
    for name, (forest, deseason) in forests.items():
        features = feature_matrix(test, stats, deseason)
        flag[name] = forest.flags(features)
        anomaly[name] = forest.score(features)

    labels = [f"{int(y)}-{int(m):02d}" for y, m in zip(test["year"], test["month"])]
    sets = {name: {labels[i] for i in np.flatnonzero(flag[name])} for name in METHODS}
    ranks = pd.Series(np.abs(score_stat)).rank()
    spearman = {
        name: (None if ranks.notna().sum() < 5 else round(float(ranks.corr(pd.Series(anomaly[name]).rank())), 3))
        for name in ("if_raw", "if_deseason")
    }
    detail = {
        "train_months": int(len(train)), "test_months": int(len(test)),
        "flags": {name: sorted(sets[name]) for name in METHODS},
        "flag_counts": {name: len(sets[name]) for name in METHODS},
        "unscorable_by_stat": int(np.isnan(score_stat).sum()),
        "jaccard_stat_vs_if_raw": _jaccard(sets["stat"], sets["if_raw"]),
        "jaccard_stat_vs_if_deseason": _jaccard(sets["stat"], sets["if_deseason"]),
        "spearman_abs_stat_vs_if": spearman,
    }
    detail["_injection"] = _injection(test, stats, forests)
    return detail


def _method_scores(frame: pd.DataFrame, stats: dict, forests: dict) -> dict[str, np.ndarray]:
    """Continuous anomaly score per method (larger = more unusual, either direction)."""
    score, _ = stat_scores(frame["active_cell_days"].to_numpy(float), frame["month"].to_numpy(), stats)
    scores = {"stat": np.abs(np.nan_to_num(score))}  # unscorable months get 0: nothing to say
    for name, (forest, deseason) in forests.items():
        scores[name] = forest.score(feature_matrix(frame, stats, deseason))
    return scores


def _injection(test: pd.DataFrame, stats: dict, forests: dict) -> dict[str, object]:
    """Scale real held-out months one at a time and record which methods notice (SYNTHETIC test)."""
    eligible = test[test["month"].map(lambda m: stats[int(m)]["median"] >= MIN_LEVEL)].reset_index(drop=True)
    result: dict[str, object] = {"months": int(len(eligible)), "hits": {}, "auc": {}, "scorable_by_stat": 0}
    if eligible.empty:
        return result
    genuine = _method_scores(eligible, stats, forests)
    for label, factor in MULTIPLIERS.items():
        modified = eligible.copy()
        for name in SERIES:
            modified[name] = modified[name] * factor
        score, limit = stat_scores(modified["active_cell_days"].to_numpy(float), modified["month"].to_numpy(), stats)
        hits = {"stat": int(_stat_flags(score, limit).sum())}
        result["scorable_by_stat"] = int((~np.isnan(score)).sum())
        for name, (forest, deseason) in forests.items():
            hits[name] = int(forest.flags(feature_matrix(modified, stats, deseason)).sum())
        result["hits"][label] = hits
        altered = _method_scores(modified, stats, forests)
        result["auc"][label] = {name: _auc(altered[name], genuine[name]) for name in METHODS}
    return result


def compare(calendar: pd.DataFrame, *, train_end: int = TRAIN_END_YEAR, seed: int = 0) -> dict[str, object]:
    areas: dict[str, object] = {}
    pooled_hits = {label: {m: 0 for m in METHODS} for label in MULTIPLIERS}
    auc_sum = {label: {m: 0.0 for m in METHODS} for label in MULTIPLIERS}
    auc_weight = {label: {m: 0 for m in METHODS} for label in MULTIPLIERS}
    pooled_months = 0
    pooled_scorable = 0
    fp_hits = {m: 0 for m in METHODS}
    fp_total = 0
    for region, frame in calendar.groupby("region", sort=True):
        detail = compare_area(frame, train_end=train_end, seed=seed)
        if detail is None:
            continue
        injection = detail.pop("_injection")
        pooled_months += injection["months"]
        pooled_scorable += injection["scorable_by_stat"] if injection["months"] else 0
        for label, hits in injection["hits"].items():
            for method, n in hits.items():
                pooled_hits[label][method] += n
        for label, by_method in injection.get("auc", {}).items():
            for method, value in by_method.items():
                if value is not None:
                    auc_sum[label][method] += value * injection["months"]
                    auc_weight[label][method] += injection["months"]
        for method in METHODS:
            fp_hits[method] += detail["flag_counts"][method]
        fp_total += detail["test_months"]
        areas[str(region)] = detail
    rate = lambda n, d: round(n / d, 3) if d else None  # noqa: E731
    return _json_safe({
        "protocol": {
            "train_years": f"<= {train_end}", "test_years": f"> {train_end}",
            "stat_threshold": "calibrated to training-set size (about 1% false flags on ordinary months)", "stat_scale": "log1p",
            "if_contamination": CONTAMINATION, "if_trees": 300, "seed": seed,
            "injection_min_level": MIN_LEVEL, "injection_factors": MULTIPLIERS,
        },
        "areas": areas,
        "pooled": {
            "areas": len(areas), "test_months": fp_total,
            "flag_rate_on_heldout_months": {m: rate(fp_hits[m], fp_total) for m in METHODS},
            "synthetic_injection": {
                "months_per_factor": pooled_months,
                "stat_scorable_share": rate(pooled_scorable, pooled_months),
                "detection_rate": {label: {m: rate(pooled_hits[label][m], pooled_months) for m in METHODS} for label in MULTIPLIERS},
                "auc": {label: {m: (round(auc_sum[label][m] / auc_weight[label][m], 3) if auc_weight[label][m] else None)
                                for m in METHODS} for label in MULTIPLIERS},
            },
        },
        "notes": [
            "No ground-truth labels exist, so accuracy, precision and recall are not reported.",
            "Both methods are fitted on early years only and applied unchanged to later years.",
            "The injection test scales real months up or down and is synthetic: it measures sensitivity, not real-world accuracy.",
            "Isolation Forest flags both directions and gives no explanation; the statistical baseline gives a score, median and sample size.",
        ],
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calendar", type=Path, default=Path("data/processed/analytics/calendar_5km.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/analytics/model_comparison.json"))
    parser.add_argument("--train-end", type=int, default=TRAIN_END_YEAR)
    args = parser.parse_args()
    report = compare(pd.read_csv(args.calendar), train_end=args.train_end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["pooled"], indent=2))


if __name__ == "__main__":
    main()
