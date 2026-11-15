"""Run the full pipeline: process raw FIRMS CSVs, harmonize, build calendar analytics.

Usage:  python -m data_pipeline.run_all
Raw files are only read. Outputs go to data/processed/.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from . import atomic
from .calendar_analytics import run as run_analytics
from .harmonize import STABLE_PLATFORMS, harmonize
from .process import process
from .regions import DEFAULT_ADM1, GhanaRegions
from .model_comparison import compare as compare_models
from .environment import run as run_environment
from .sensitivity import run as run_sensitivity
from .validation import run as run_validation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/firms"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--boundary", type=Path, default=DEFAULT_ADM1)
    parser.add_argument("--cell-sizes-km", type=float, nargs="+", default=[1.0, 2.0, 5.0])
    parser.add_argument("--skip-process", action="store_true", help="Reuse the processed observations (steps 2 to 7 only)")
    parser.add_argument("--steady-only", action="store_true", help="Use only Terra, Aqua and Suomi-NPP (default: all satellites)")
    args = parser.parse_args()

    print("1/7 processing raw files ...", flush=True)
    meta = json.loads((args.output_dir / "metadata.json").read_text(encoding="utf-8")) if args.skip_process else process(args.raw_dir, args.output_dir)
    covered = {name: info["covered_ranges"] for name, info in meta["products"].items()}

    print("2/7 harmonizing ...", flush=True)
    harmonized = harmonize(
        sorted((args.output_dir / "observations").glob("*.parquet")),
        args.output_dir / "harmonized",
        cell_sizes_km=tuple(args.cell_sizes_km),
        platforms=STABLE_PLATFORMS if args.steady_only else None,
        regions=GhanaRegions(args.boundary),
        covered_ranges=covered,
    )

    print("3/7 calendar analytics ...", flush=True)
    summaries = [
        run_analytics(path, args.output_dir / "analytics")
        for path in sorted((args.output_dir / "harmonized").glob("monthly_*km.csv"))
    ]
    atomic.write_text(args.output_dir / "analytics" / "analytics_metadata.json", json.dumps(summaries, indent=2))
    import pandas as pd

    print("4/7 validation ...", flush=True)
    run_validation(args.output_dir / "harmonized", args.output_dir / "observations",
                   args.output_dir / "analytics" / "validation.json")

    from .bridge import backtest

    atomic.write_text(args.output_dir / "analytics" / "bridge_validation.json",
                      json.dumps(backtest(pd.read_csv(args.output_dir / "harmonized" / "monthly_5km.csv")), indent=2))
    print("5/7 baseline vs Isolation Forest comparison ...", flush=True)
    import pandas as pd

    comparison = compare_models(pd.read_csv(args.output_dir / "analytics" / "calendar_5km.csv"))
    atomic.write_text(args.output_dir / "analytics" / "model_comparison.json", json.dumps(comparison, indent=2))

    print("6/7 sensitivity analysis ...", flush=True)
    sensitivity = run_sensitivity(args.output_dir / "observations", args.output_dir / "harmonized", covered, args.boundary)
    atomic.write_text(args.output_dir / "analytics" / "sensitivity.json", json.dumps(sensitivity, indent=2))

    print("7/7 rainfall context (NASA POWER; needs network) ...", flush=True)
    try:
        run_environment(args.boundary, Path("data/raw/environment"), args.output_dir / "environment",
                        args.output_dir / "analytics" / "calendar_5km.csv", start=2002, end=date.today().year)
    except Exception as exc:  # the rest of the pipeline is complete and valid without rainfall context
        print(f"  skipped rainfall context: {exc}", flush=True)

    print(json.dumps({"observations_used": harmonized["observations_used"], "analytics": summaries}, indent=2))


if __name__ == "__main__":
    main()
