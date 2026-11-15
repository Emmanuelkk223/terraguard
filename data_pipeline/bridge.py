"""Bridge the MODIS-only record (Aug 2002 to 2011) onto the combined MODIS+VIIRS scale.

VIIRS only exists from 2012. Before then the only observation is MODIS, which counts
about 3 to 4 times fewer active cell-days than "either sensor" in the dry season (and far
fewer in the rainy season). Putting the two eras side by side would show a false jump in
2012. To avoid that, every pre-VIIRS month is expressed on the combined scale using the
relationship measured while both sensors were observing (2012 onwards):

    log1p(combined cell-days) = a + b * log1p(MODIS cell-days)      (one fit per calendar month)

This is an ESTIMATE, not an observation. Every estimated month is labelled, carries a 90%
range from the fit residuals, and the fit is checked by hold-out back-testing
(:func:`backtest`). What it cannot do: it assumes the MODIS-to-combined relationship of
2012 onwards also held before 2012, and it cannot recover fires only VIIRS could see.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_FIT_POINTS = 8
SLOPE_RANGE = (0.3, 1.5)  # a slope far from 1 on ~14 points is noise, not physics
Z90 = 1.645
# The in-sample fit residual understates the real error of predicting other years (the
# MODIS-to-combined ratio drifts and each fit has only ~14 points). Widening by this factor
# makes the stated 90% range cover about 90% of hidden months in the hold-out back-test.
RANGE_INFLATION = 3.0
REQUIRED = {"viirs_expected", "overlap_ok", "coverage_ok", "modis_cell_days", "active_cell_days"}


def fit_log_line(modis: np.ndarray, combined: np.ndarray) -> tuple[float, float, float]:
    """Intercept, slope and residual sigma of log1p(combined) on log1p(modis)."""
    x, y = np.log1p(modis.astype(float)), np.log1p(combined.astype(float))
    if len(x) < 2 or np.ptp(x) == 0:
        slope = 0.0
    else:
        slope = float(np.clip(np.polyfit(x, y, 1)[0], *SLOPE_RANGE))
    intercept = float(y.mean() - slope * x.mean())
    residual = y - intercept - slope * x
    dof = max(len(x) - 2, 1)
    return intercept, slope, float(np.sqrt((residual**2).sum() / dof))


def predict(modis: np.ndarray, intercept: float, slope: float, sigma: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Point estimate and 90% range on the combined scale, never below MODIS itself."""
    centre = intercept + slope * np.log1p(modis.astype(float))
    floor = modis.astype(float)
    value = np.maximum(np.expm1(centre), floor)
    low = np.maximum(np.expm1(centre - Z90 * RANGE_INFLATION * sigma), floor)
    high = np.maximum(np.expm1(centre + Z90 * RANGE_INFLATION * sigma), floor)
    return value, low, high


def bridge_monthly(monthly: pd.DataFrame) -> pd.DataFrame:
    """Add ``series_basis`` and express complete pre-VIIRS months on the combined scale.

    Adds ``observed_cell_days`` (what the satellites saw), ``series_basis``
    (``combined`` or ``modis_scaled``), ``estimate_low`` and ``estimate_high``.
    ``active_cell_days`` becomes the bridged value. Tables without the coverage columns
    (for example in unit tests) are returned unchanged apart from the new columns.
    """
    result = monthly.copy()
    # The relationship is fitted to the STEADY set (Terra, Aqua, Suomi-NPP): satellites added later (NOAA-20 from 2018,
    # NOAA-21 from 2023) change what "combined" means from year to year, while the steady set does not.
    target_column = "steady_cell_days" if "steady_cell_days" in result.columns else "active_cell_days"
    result["observed_cell_days"] = result["active_cell_days"]
    result["series_basis"] = "combined"
    result["estimate_low"] = result["active_cell_days"].astype(float)
    result["estimate_high"] = result["active_cell_days"].astype(float)
    if not REQUIRED.issubset(result.columns):
        return result
    months = pd.to_datetime(result["month"])
    expected = result["viirs_expected"].astype(bool)
    overlap = result["overlap_ok"].astype(bool) & expected
    target = result["coverage_ok"].astype(bool) & ~expected
    if not target.any():
        return result
    for region in result["region"].unique():
        in_region = result["region"] == region
        for month_number in sorted(months[in_region & target].dt.month.unique()):
            same_month = months.dt.month == month_number
            fit = result[in_region & overlap & same_month]
            rows = in_region & target & same_month
            if len(fit) < MIN_FIT_POINTS:
                result.loc[rows, "coverage_ok"] = False  # nothing to bridge with: do not guess
                continue
            a, b, sigma = fit_log_line(fit["modis_cell_days"].to_numpy(), fit[target_column].to_numpy())
            value, low, high = predict(result.loc[rows, "modis_cell_days"].to_numpy(), a, b, sigma)
            result.loc[rows, "active_cell_days"] = np.rint(value).astype("int64")
            if target_column != "active_cell_days":  # before 2018 every satellite is in the steady set
                result.loc[rows, target_column] = np.rint(value).astype("int64")
            result.loc[rows, "estimate_low"] = np.rint(low)
            result.loc[rows, "estimate_high"] = np.rint(high)
            result.loc[rows, "series_basis"] = "modis_scaled"
    return result


def backtest(monthly: pd.DataFrame, *, splits: tuple[int, ...] = (2019, 2021, 2023)) -> dict[str, object]:
    """Hold-out check: fit on overlap years up to ``split``, predict the later years.

    Uses only months where both sensors truly observed, so the truth is known. Reports
    the typical error and whether the 90% range really covers about 90% of cases.
    """
    frame = monthly[monthly["region"] == "Ghana"].copy()
    frame = frame[frame["overlap_ok"].astype(bool) & frame["viirs_expected"].astype(bool)]
    truth_column = "steady_cell_days" if "steady_cell_days" in frame.columns else "active_cell_days"
    frame["month_start"] = pd.to_datetime(frame["month"])
    frame["year"] = frame["month_start"].dt.year
    frame["cal_month"] = frame["month_start"].dt.month
    results = []
    for split in splits:
        train, test = frame[frame["year"] <= split], frame[frame["year"] > split]
        errors, covered, ratios = [], [], []
        for month_number, group in test.groupby("cal_month"):
            fit = train[train["cal_month"] == month_number]
            if len(fit) < MIN_FIT_POINTS:
                continue
            a, b, sigma = fit_log_line(fit["modis_cell_days"].to_numpy(), fit[truth_column].to_numpy())
            value, low, high = predict(group["modis_cell_days"].to_numpy(), a, b, sigma)
            truth = group[truth_column].to_numpy(float)
            errors.extend(np.abs(np.log1p(value) - np.log1p(truth)))
            ratios.extend(value / np.maximum(truth, 1) - 1)
            covered.extend((truth >= low) & (truth <= high))
        if errors:
            results.append({
                "fit_years": f"2012-{split}", "test_years": f"{split + 1}-{int(frame['year'].max())}",
                "test_months": len(errors),
                "median_absolute_error_pct": round(float(np.median(np.abs(ratios))) * 100, 1),
                "median_bias_pct": round(float(np.median(ratios)) * 100, 1),
                "mean_absolute_log_error": round(float(np.mean(errors)), 3),
                "range_90_coverage": round(float(np.mean(covered)), 3),
            })
    return {"method": "per-calendar-month log-log fit of combined on MODIS cell-days", "backtests": results}
