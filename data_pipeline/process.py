"""Process FIRMS CSV files into validated observations and summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .pipeline import (
    aggregate_observations,
    canonicalize,
    filter_to_boundary,
    load_firms_csv,
    load_geojson_geometry,
    validate_observations,
)


def process(
    input_files: list[Path],
    *,
    boundary: Path,
    output_dir: Path,
    product: str,
    cell_size_km: float = 5.0,
) -> dict[str, object]:
    frames = [load_firms_csv(path, product) for path in input_files]
    loaded = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    valid, validation_exclusions = validate_observations(loaded)
    retained, boundary_exclusions = filter_to_boundary(
        valid, load_geojson_geometry(boundary)
    )
    retained = canonicalize(retained)
    output_dir.mkdir(parents=True, exist_ok=True)
    retained.to_csv(output_dir / "observations.csv", index=False)
    exclusions = pd.concat(
        [validation_exclusions, boundary_exclusions], ignore_index=True
    )
    exclusions.to_csv(output_dir / "exclusions.csv", index=False)
    summaries = {
        period: aggregate_observations(retained, period=period, cell_size_km=cell_size_km)
        for period in ("day", "week", "month")
    }
    for period, summary in summaries.items():
        summary.to_csv(output_dir / f"summary_{period}.csv", index=False)

    metadata = {
        "source_product": product,
        "source_files": [path.name for path in input_files],
        "boundary_file": str(boundary),
        "coordinate_reference_system": "EPSG:4326",
        "grid_method": "equirectangular; 5 km nominal cell size",
        "cell_size_km": cell_size_km,
        "loaded_records": int(len(loaded)),
        "valid_records_before_boundary": int(len(valid)),
        "retained_records": int(len(retained)),
        "excluded_records": int(len(exclusions)),
        "exclusions_by_reason": {
            str(key): int(value)
            for key, value in exclusions["reason"].value_counts().items()
        },
        "earliest_observation": (
            retained["acq_datetime"].min().isoformat()
            if not retained.empty
            else None
        ),
        "latest_observation": (
            retained["acq_datetime"].max().isoformat()
            if not retained.empty
            else None
        ),
        "observation_counts_by_sensor": {
            str(key): int(value)
            for key, value in retained["sensor"].value_counts().items()
        },
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--boundary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--product", required=True)
    parser.add_argument("--cell-size-km", type=float, default=5.0)
    args = parser.parse_args()
    files = sorted(args.input_dir.glob("*.csv"))
    if not files:
        raise SystemExit(f"No CSV files found in {args.input_dir}")
    metadata = process(
        files,
        boundary=args.boundary,
        output_dir=args.output_dir,
        product=args.product,
        cell_size_km=args.cell_size_km,
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
