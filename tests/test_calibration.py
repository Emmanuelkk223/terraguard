"""Tests for the calibrated unusual-month threshold (simulation based, fixed seeds)."""

from __future__ import annotations

import pytest

from data_pipeline.calibration import (
    CALIBRATED_THRESHOLDS, MAX_BASELINE_YEARS, MIN_BASELINE_YEARS, TARGET_FALSE_FLAG_RATE, false_flag_rate, threshold_for,
)


@pytest.mark.parametrize("n", [5, 7, 10, 13, 20])
def test_tabulated_threshold_gives_the_target_false_flag_rate(n: int) -> None:
    """Independent re-simulation (different seed): ordinary months are flagged about 1% of the time."""
    rate = false_flag_rate(n, CALIBRATED_THRESHOLDS[n], trials=300_000, seed=12345)
    assert abs(rate - TARGET_FALSE_FLAG_RATE) < 0.004


@pytest.mark.parametrize("n", [5, 7, 13])
def test_the_old_fixed_threshold_was_too_liberal_for_short_baselines(n: int) -> None:
    assert false_flag_rate(n, 3.5, trials=200_000, seed=1) > 2 * TARGET_FALSE_FLAG_RATE


def test_table_covers_the_range_and_shrinks_with_more_years() -> None:
    assert set(CALIBRATED_THRESHOLDS) == set(range(MIN_BASELINE_YEARS, MAX_BASELINE_YEARS + 1))
    assert CALIBRATED_THRESHOLDS[5] > CALIBRATED_THRESHOLDS[13] > CALIBRATED_THRESHOLDS[20]


def test_threshold_for_clamps_outside_the_table() -> None:
    assert threshold_for(2) == CALIBRATED_THRESHOLDS[5]
    assert threshold_for(99) == CALIBRATED_THRESHOLDS[20]
    assert threshold_for(13) == 4.4
