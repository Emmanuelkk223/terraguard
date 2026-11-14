"""Process raw FIRMS CSV files into validated, per-product parquet datasets.

Each product (MODIS, VIIRS SNPP/NOAA-20/NOAA-21) is processed separately so
memory stays bounded and the source product is never lost. Raw files are
read-only inputs. Sensors are never merged or summed here.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from .pipeline import (
    add_derived_fields,
    canonicalize,
    filter_to_boundary,
    load_firms_csv,
    load_geojson_geometry,
    validate_observations,
)

PRODUCT_FILE = re.compile(
    r"^(MODIS_SP|VIIRS_(?:SNPP|NOAA20|NOAA21)_SP)_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.csv$"
)


def group_files_by_product(input_dir: Path) -> dict[str, list[Path]]:
    """Group CSVs by the product named in the file name; ignore other files."""
    groups: dict[str, list[Path]] = {}
    for path in sorted(Path(input_dir).glob("*.csv")):
        match = PRODUCT_FILE.match(path.name)
        if match:
            groups.setdefault(match.group(1), []).append(path)
    return groups


def covered_ranges(files: list[Path]) -> list[list[str]]:
    """Contiguous [start, end] date ranges covered by the downloaded windows.

    Each file name carries its request window. A window with zero detections
    still returns a (header-only) file, so file coverage = archive coverage.
    """
    windows = []
    for path in files:
        parts = path.stem.split("_")
        windows.append((pd.Timestamp(parts[-2]), pd.Timestamp(parts[-1])))
    merged: list[list[pd.Timestamp]] = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1] + pd.Timedelta(days=1):
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [[a.date().isoformat(), b.date().isoformat()] for a, b in merged]


def process_product(
    files: list[Path],
    product: str,
    *,
    boundary_rings: list | None,
    output_dir: Path,
) -> dict[str, object]:
    loaded = pd.concat([load_firms_csv(p, product) for p in files], ignore_index=True)
    valid, exclusions = validate_observations(loaded)
    if boundary_rings is not None:
        valid, boundary_exclusions = filter_to_boundary(valid, boundary_rings)
        exclusions = pd.concat([exclusions, boundary_exclusions], ignore_index=True)
    retained = canonicalize(add_derived_fields(valid))
    # Mixed MODIS (numeric) / VIIRS (l,n,h) confidence must share one dtype.
    retained["confidence"] = retained["confidence"].astype("string")

    output_dir.mkdir(parents=True, exist_ok=True)
    retained.to_parquet(output_dir / f"{product}.parquet", index=False)
    exclusions.to_csv(output_dir / f"{product}_exclusions.csv", index=False)
    return {
        "source_files": len(files),
        "covered_ranges": covered_ranges(files),
        "loaded_records": int(len(loaded)),
        "retained_records": int(len(retained)),
        "exclusions_by_reason": {
            str(k): int(v) for k, v in exclusions["reason"].value_counts().items()
        },
        "earliest_observation": None if retained.empty else retained["acq_datetime"].min().isoformat(),
        "latest_observation": None if retained.empty else retained["acq_datetime"].max().isoformat(),
        "records_by_platform": {
            str(k): int(v) for k, v in retained["platform"].value_counts().items()
        },
        "records_by_confidence_class": {
            str(k): int(v) for k, v in retained["confidence_class"].value_counts(dropna=False).items()
        },
        "non_vegetation_type_records": int((retained["is_presumed_vegetation_fire"] == False).sum()),  # noqa: E712
    }


def process(input_dir: Path, output_dir: Path, *, boundary: Path | None = None) -> dict[str, object]:
    groups = group_files_by_product(input_dir)
    if not groups:
        raise SystemExit(f"No FIRMS product CSV files found in {input_dir}")
    rings = load_geojson_geometry(boundary) if boundary else None
    products = {
        product: process_product(files, product, boundary_rings=rings, output_dir=output_dir / "observations")
        for product, files in sorted(groups.items())
    }
    metadata = {
        "coordinate_reference_system": "EPSG:4326",
        "spatial_filter": (
            f"boundary polygon ({boundary.name})" if boundary
            else "bounding box only (-3.26,4.74,1.20,11.17); includes parts of neighbouring countries"
        ),
        "products": products,
        "observation_counts_by_sensor": _by_sensor(products),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _by_sensor(products: dict[str, dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for product, info in products.items():
        sensor = "MODIS" if product.startswith("MODIS") else "VIIRS"
        totals[sensor] = totals.get(sensor, 0) + int(info["retained_records"])
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw/firms"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--boundary", type=Path, default=None,
                        help="Optional GeoJSON boundary; omit for bounding-box-only filtering")
    args = parser.parse_args()
    print(json.dumps(process(args.input_dir, args.output_dir, boundary=args.boundary), indent=2))


if __name__ == "__main__":
    main()
