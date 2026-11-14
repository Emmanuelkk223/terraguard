"""Run the full pipeline: process raw FIRMS CSVs, harmonize, build calendar analytics.

Usage:  python -m data_pipeline.run_all
Raw files are only read. Outputs go to data/processed/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .calendar_analytics import run as run_analytics
from .harmonize import STABLE_PLATFORMS, harmonize
from .process import process
from .regions import DEFAULT_ADM1, GhanaRegions
from .model_comparison import compare as compare_models
from .validation import run as run_validation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/firms"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--boundary", type=Path, default=DEFAULT_ADM1)
    parser.add_argument("--cell-sizes-km", type=float, nargs="+", default=[1.0, 2.0, 5.0])
    parser.add_argument("--all-platforms", action="store_true", help="Include NOAA-20/21 (constellation changes over time)")
    args = parser.parse_args()

    print("1/5 processing raw files ...", flush=True)
    meta = process(args.raw_dir, args.output_dir)
    covered = {name: info["covered_ranges"] for name, info in meta["products"].items()}

    print("2/5 harmonizing ...", flush=True)
    harmonized = harmonize(
        sorted((args.output_dir / "observations").glob("*.parquet")),
        args.output_dir / "harmonized",
        cell_sizes_km=tuple(args.cell_sizes_km),
        platforms=None if args.all_platforms else STABLE_PLATFORMS,
        regions=GhanaRegions(args.boundary),
        covered_ranges=covered,
    )

    print("3/5 calendar analytics ...", flush=True)
    summaries = [
        run_analytics(path, args.output_dir / "analytics")
        for path in sorted((args.output_dir / "harmonized").glob("monthly_*km.csv"))
    ]
    (args.output_dir / "analytics" / "analytics_metadata.json").write_text(
        json.dumps(summaries, indent=2), encoding="utf-8"
    )
    print("4/5 validation ...", flush=True)
    run_validation(args.output_dir / "harmonized", args.output_dir / "observations",
                   args.output_dir / "analytics" / "validation.json")

    print("5/5 baseline vs Isolation Forest comparison ...", flush=True)
    import pandas as pd

    comparison = compare_models(pd.read_csv(args.output_dir / "analytics" / "calendar_5km.csv"))
    (args.output_dir / "analytics" / "model_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    print(json.dumps({"observations_used": harmonized["observations_used"], "analytics": summaries}, indent=2))


if __name__ == "__main__":
    main()
