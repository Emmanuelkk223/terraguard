"""Historical FIRMS activity summaries and robust seasonal baselines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .pipeline import add_grid_cell

PERIOD_ALIASES = {"day": "D", "week": "7D", "month": "MS"}
PERIOD_COLUMNS = {"day": "period_start", "week": "period_start", "month": "period_start"}
BASELINE_SCALE = 1.4826


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"historical analysis requires columns: {missing}")


def _period_start(values: pd.Series, period: str) -> pd.Series:
    if period == "day":
        return values.dt.floor("D")
    if period == "week":
        return values.dt.to_period("W-SUN").dt.start_time
    if period == "month":
        return values.dt.to_period("M").dt.start_time
    raise ValueError("period must be one of: day, week, month")


def temporal_activity(
    observations: pd.DataFrame,
    *,
    period: str = "week",
    include_empty_periods: bool = True,
    cell_size_km: float | None = None,
) -> pd.DataFrame:
    """Aggregate observation records by period and sensor.

    ``observation_count`` counts source satellite observation records, not
    unique physical fires. Empty periods are emitted with count zero and
    ``has_observations=False`` when the input has a continuous date range.
    """
    _require_columns(observations, ("acq_datetime", "sensor"))
    if period not in PERIOD_ALIASES:
        raise ValueError("period must be one of: day, week, month")
    frame = observations.copy()
    frame["acq_datetime"] = pd.to_datetime(frame["acq_datetime"], errors="coerce")
    frame = frame.loc[frame["acq_datetime"].notna()].copy()
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "period_start",
                "sensor",
                "observation_count",
                "frp_sum",
                "frp_mean",
                "has_observations",
            ]
        )
    frame["period_start"] = _period_start(frame["acq_datetime"], period)
    if cell_size_km is not None:
        frame = add_grid_cell(frame, cell_size_km=cell_size_km)
    group_columns = ["period_start", "sensor"]
    if cell_size_km is not None:
        group_columns.append("cell_id")
    grouped = (
        frame.groupby(group_columns, dropna=False)
        .agg(
            observation_count=("acq_datetime", "size"),
            frp_sum=("frp", "sum") if "frp" in frame else ("acq_datetime", lambda _: np.nan),
            frp_mean=("frp", "mean") if "frp" in frame else ("acq_datetime", lambda _: np.nan),
        )
        .reset_index()
    )
    grouped["has_observations"] = True
    if not include_empty_periods:
        return grouped.sort_values(["period_start", "sensor"]).reset_index(drop=True)

    dates = pd.date_range(
        grouped["period_start"].min(),
        grouped["period_start"].max(),
        freq=PERIOD_ALIASES[period],
    )
    index_values: list[pd.Index] = [
        dates,
        pd.Index(sorted(frame["sensor"].dropna().astype(str).unique()), name="sensor"),
    ]
    index_names = ["period_start", "sensor"]
    if cell_size_km is not None:
        index_values.append(pd.Index(sorted(frame["cell_id"].unique()), name="cell_id"))
        index_names.append("cell_id")
    index = pd.MultiIndex.from_product(index_values, names=index_names)
    result = grouped.set_index(group_columns).reindex(index)
    result["observation_count"] = result["observation_count"].fillna(0).astype("int64")
    result["frp_sum"] = result["frp_sum"].fillna(0.0)
    result["has_observations"] = result["has_observations"].fillna(False).astype(bool)
    return result.reset_index().sort_values(["period_start", "sensor"]).reset_index(drop=True)


def spatial_activity(
    observations: pd.DataFrame, *, cell_size_km: float = 5.0
) -> pd.DataFrame:
    """Aggregate observations by nominal grid cell and sensor."""
    _require_columns(observations, ("latitude", "longitude", "sensor", "acq_datetime"))
    frame = add_grid_cell(observations.copy(), cell_size_km=cell_size_km)
    frame["year"] = pd.to_datetime(frame["acq_datetime"], errors="coerce").dt.year
    return (
        frame.groupby(["cell_id", "sensor"], dropna=False)
        .agg(
            observation_count=("acq_datetime", "size"),
            latitude_mean=("latitude", "mean"),
            longitude_mean=("longitude", "mean"),
            frp_sum=("frp", "sum") if "frp" in frame else ("acq_datetime", lambda _: np.nan),
            first_observation=("acq_datetime", "min"),
            last_observation=("acq_datetime", "max"),
        )
        .reset_index()
        .sort_values(["cell_id", "sensor"])
        .reset_index(drop=True)
    )


def seasonal_baseline(
    activity: pd.DataFrame,
    *,
    seasonal_column: str = "month",
    value_column: str = "observation_count",
    min_samples: int = 3,
    threshold: float = 3.5,
) -> pd.DataFrame:
    """Calculate leave-one-out seasonal median/MAD robust scores.

    The comparison group is sensor plus spatial cell, when ``cell_id`` exists,
    plus ``seasonal_column``. The current period is excluded from its own
    baseline to avoid in-sample leakage. A score is only eligible when at least
    ``min_samples`` other periods exist. Scores are one-sided for unusually
    high activity; zero-MAD groups are flagged only when the value exceeds the
    common median.
    """
    _require_columns(activity, ("period_start", value_column))
    if min_samples < 1:
        raise ValueError("min_samples must be at least 1")
    if seasonal_column not in activity:
        frame = activity.copy()
        period = pd.to_datetime(frame["period_start"])
        frame[seasonal_column] = period.dt.month
    else:
        frame = activity.copy()
    frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
    group_columns = [column for column in ("cell_id", "sensor", seasonal_column) if column in frame]
    if not group_columns:
        group_columns = [seasonal_column]

    records: list[dict[str, object]] = []
    for _, group in frame.groupby(group_columns, dropna=False, sort=False):
        values = pd.to_numeric(group[value_column], errors="coerce").to_numpy(float)
        for position, (_, row) in enumerate(group.iterrows()):
            peers = np.delete(values, position)
            peers = peers[~np.isnan(peers)]
            median = float(np.median(peers)) if len(peers) else np.nan
            mad = (
                float(np.median(np.abs(peers - median)))
                if len(peers)
                else np.nan
            )
            score = np.nan
            eligible = len(peers) >= min_samples and not np.isnan(median)
            if eligible:
                if mad > 0:
                    score = (float(row[value_column]) - median) / (BASELINE_SCALE * mad)
                elif float(row[value_column]) > median:
                    score = np.inf
                else:
                    score = 0.0
            records.append(
                {
                    **row.to_dict(),
                    "baseline_sample_count": len(peers),
                    "baseline_median": median,
                    "baseline_mad": mad,
                    "robust_score": score,
                    "baseline_eligible": eligible,
                    "candidate_unusual": bool(eligible and score >= threshold),
                    "threshold": threshold,
                }
            )
    return pd.DataFrame(records)


def run_analysis(
    observations_path: Path,
    output_dir: Path,
    *,
    cell_size_km: float = 5.0,
    min_samples: int = 3,
    threshold: float = 3.5,
) -> dict[str, object]:
    """Generate all historical outputs from processed observations."""
    if not observations_path.exists():
        raise FileNotFoundError(
            f"Processed observations not found: {observations_path}. "
            "Run Milestone 1 processing with genuine FIRMS data first."
        )
    observations = pd.read_csv(observations_path)
    _require_columns(observations, ("acq_datetime", "sensor", "latitude", "longitude"))
    output_dir.mkdir(parents=True, exist_ok=True)
    temporal_outputs: dict[str, pd.DataFrame] = {}
    for period in ("day", "week", "month"):
        output = temporal_activity(observations, period=period)
        temporal_outputs[period] = output
        output.to_csv(output_dir / f"historical_{period}.csv", index=False)
    spatial = spatial_activity(observations, cell_size_km=cell_size_km)
    spatial.to_csv(output_dir / "historical_spatial.csv", index=False)

    weekly = temporal_activity(
        observations,
        period="week",
        cell_size_km=cell_size_km,
        include_empty_periods=False,
    )
    weekly["month"] = pd.to_datetime(weekly["period_start"]).dt.month
    baseline = seasonal_baseline(
        weekly,
        seasonal_column="month",
        min_samples=min_samples,
        threshold=threshold,
    )
    baseline.to_csv(output_dir / "seasonal_baseline.csv", index=False)
    metadata = {
        "source_observations": str(observations_path),
        "observation_count": int(len(observations)),
        "sensors": sorted(observations["sensor"].dropna().astype(str).unique()),
        "earliest_observation": str(observations["acq_datetime"].min()),
        "latest_observation": str(observations["acq_datetime"].max()),
        "cell_size_km": cell_size_km,
        "baseline": {
            "seasonal_column": "calendar month",
            "value_column": "observation_count",
            "min_samples": min_samples,
            "threshold": threshold,
            "mad_scale": BASELINE_SCALE,
            "leave_one_out": True,
        },
        "candidate_unusual_count": int(baseline["candidate_unusual"].sum()),
    }
    (output_dir / "historical_analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, default=Path("data/processed/observations.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/analysis"))
    parser.add_argument("--cell-size-km", type=float, default=5.0)
    parser.add_argument("--min-samples", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=3.5)
    args = parser.parse_args()
    print(json.dumps(run_analysis(
        args.observations,
        args.output_dir,
        cell_size_km=args.cell_size_km,
        min_samples=args.min_samples,
        threshold=args.threshold,
    ), indent=2))


if __name__ == "__main__":
    main()
