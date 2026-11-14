"""Calibrate the unusual-month threshold to a stated false-flag rate.

The common "modified z-score > 3.5" rule assumes a large baseline sample. With the 5-13 other
years available for a calendar month, median/MAD scores have heavy tails, so 3.5 falsely flags far
more ordinary months than its name suggests (about 2% with 13 years and 7% with 7 years even for
perfectly normal noise). This module finds, by simulation, the threshold that flags a chosen
share of ORDINARY months for each baseline size.

Assumptions (stated, not hidden): ordinary variation is Gaussian on the log scale, which is why
activity is scored on log1p. Real series can have heavier tails, so the realised false-flag rate
can be higher than the nominal target; flags remain a screening aid, not a verdict.

Regenerate the table with:  python -m data_pipeline.calibration
"""

from __future__ import annotations

import numpy as np

MAD_SCALE = 1.4826
TARGET_FALSE_FLAG_RATE = 0.01  # two-sided, per ordinary month
MIN_BASELINE_YEARS = 5
MAX_BASELINE_YEARS = 20

# threshold by number of baseline values; produced by calibrate_threshold(n) with seed 20260101
# (400,000 trials, two-sided target 1%). Verified by tests/test_calibration.py.
CALIBRATED_THRESHOLDS: dict[int, float] = {
    5: 14.3, 6: 8.1, 7: 7.8, 8: 5.9, 9: 5.8, 10: 5.0, 11: 4.9, 12: 4.4,
    13: 4.4, 14: 4.1, 15: 4.0, 16: 3.8, 17: 3.8, 18: 3.7, 19: 3.7, 20: 3.5,
}


def robust_scores(baseline: np.ndarray, values: np.ndarray) -> np.ndarray:
    """(value - median) / (1.4826 * MAD) for each row of ``baseline`` (NaN where MAD is 0)."""
    median = np.median(baseline, axis=1)
    mad = np.median(np.abs(baseline - median[:, None]), axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(mad > 0, (values - median) / (MAD_SCALE * mad), np.nan)


def false_flag_rate(n: int, threshold: float, trials: int = 200_000, seed: int = 0) -> float:
    """Share of ORDINARY months (same Gaussian noise as the baseline) that score beyond +-threshold."""
    rng = np.random.default_rng(seed)
    scores = robust_scores(rng.normal(size=(trials, n)), rng.normal(size=trials))
    scores = scores[~np.isnan(scores)]
    return float(np.mean(np.abs(scores) >= threshold))


def calibrate_threshold(n: int, target: float = TARGET_FALSE_FLAG_RATE, trials: int = 400_000, seed: int = 20260101) -> float:
    """Threshold whose false-flag rate on ordinary months equals ``target`` for a baseline of n values."""
    rng = np.random.default_rng(seed)
    scores = np.abs(robust_scores(rng.normal(size=(trials, n)), rng.normal(size=trials)))
    scores = scores[~np.isnan(scores)]
    return float(np.quantile(scores, 1 - target))


def threshold_for(n: int) -> float:
    """Calibrated threshold for a baseline of ``n`` values (clamped to the tabulated range)."""
    return CALIBRATED_THRESHOLDS[int(min(max(n, MIN_BASELINE_YEARS), MAX_BASELINE_YEARS))]


if __name__ == "__main__":
    table = {n: round(calibrate_threshold(n), 1) for n in range(MIN_BASELINE_YEARS, MAX_BASELINE_YEARS + 1)}
    print("CALIBRATED_THRESHOLDS = {")
    print("    " + ", ".join(f"{n}: {v}" for n, v in table.items()))
    print("}")
    print("\nFalse-flag rate on ordinary months at the old fixed threshold 3.5:")
    for n in (5, 7, 13):
        print(f"  n={n}: {false_flag_rate(n, 3.5) * 100:.2f}%   calibrated {table[n]}: {false_flag_rate(n, table[n]) * 100:.2f}%")
