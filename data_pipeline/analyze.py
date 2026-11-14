"""Generate exploratory summaries from processed FIRMS observations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build_summary(observations: pd.DataFrame) -> dict[str, object]:
    """Return descriptive counts and coverage facts without calling them fires."""
    if observations.empty:
        return {
            "observation_count": 0,
            "earliest_observation": None,
            "latest_observation": None,
            "by_sensor": {},
            "by_year": {},
            "by_month": {},
            "quality": {},
            "frp": {},
        }

    frame = observations.copy()
    frame["acq_datetime"] = pd.to_datetime(frame["acq_datetime"], errors="coerce")
    frame["year"] = frame["acq_datetime"].dt.year
    frame["month"] = frame["acq_datetime"].dt.month
    summary: dict[str, object] = {
        "observation_count": int(len(frame)),
        "earliest_observation": frame["acq_datetime"].min().isoformat(),
        "latest_observation": frame["acq_datetime"].max().isoformat(),
        "by_sensor": {
            str(key): int(value)
            for key, value in frame["sensor"].value_counts(dropna=False).items()
        },
        "by_year": {
            str(key): int(value)
            for key, value in frame["year"].value_counts().sort_index().items()
        },
        "by_month": {
            str(key): int(value)
            for key, value in frame["month"].value_counts().sort_index().items()
        },
    }

    if "confidence" in frame:
        confidence = frame["confidence"].dropna()
        summary["quality"] = {
            "field": "confidence",
            "non_null_count": int(confidence.size),
            "missing_count": int(frame["confidence"].isna().sum()),
            "value_counts": {
                str(key): int(value)
                for key, value in confidence.value_counts().items()
            },
        }
    else:
        summary["quality"] = {"field": None, "non_null_count": 0, "missing_count": len(frame)}

    if "frp" in frame:
        frp = pd.to_numeric(frame["frp"], errors="coerce").dropna()
        summary["frp"] = {
            "field": "frp",
            "non_null_count": int(frp.size),
            "missing_count": int(frame["frp"].isna().sum()),
            "min": float(frp.min()) if not frp.empty else None,
            "median": float(frp.median()) if not frp.empty else None,
            "mean": float(frp.mean()) if not frp.empty else None,
            "max": float(frp.max()) if not frp.empty else None,
        }
    else:
        summary["frp"] = {"field": None, "non_null_count": 0, "missing_count": len(frame)}
    return summary


def write_summary(observations_path: Path, output_path: Path) -> dict[str, object]:
    observations = pd.read_csv(observations_path)
    summary = build_summary(observations)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--observations",
        type=Path,
        default=Path("data/processed/observations.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/exploratory_summary.json"),
    )
    args = parser.parse_args()
    print(json.dumps(write_summary(args.observations, args.output), indent=2))


if __name__ == "__main__":
    main()
