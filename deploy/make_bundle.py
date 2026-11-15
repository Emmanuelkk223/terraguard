"""Pack the processed data a hosted copy of TerraGuard needs into one archive.

    python deploy/make_bundle.py            # writes deploy/terraguard-data.tar.gz

What goes in (everything the dashboard reads, nothing it only needs to *build* the data):
  data/processed/metadata.json, analytics/, harmonized/, environment/   Ghana, all grids
  data/processed/observations/*.parquet                                 Ghana hotspots, slimmed to the exported columns
  data/processed/wa/{metadata.json, analytics/, harmonized/}            West Africa, country level, 5 km
What is left out: raw NASA files, intermediate work files, and West Africa's individual hotspots (about 1 GB).
A copy hosted from this archive therefore offers individual-hotspot downloads for Ghana only; the app says so elsewhere.
"""

from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUTPUT = Path(__file__).resolve().parent / "terraguard-data.tar.gz"
# The columns /api/export/hotspots.csv reads (backend/app/hotspot_routes.py).
HOTSPOT_COLUMNS = [
    "acq_datetime", "latitude", "longitude", "sensor", "satellite", "platform", "confidence",
    "confidence_class", "frp", "daynight", "source_product",
]
COPY_DIRS = ["analytics", "harmonized", "environment", "wa/analytics", "wa/harmonized"]
ROW_GROUP = 65_536  # small blocks with min/max statistics, so a request reads only the blocks it needs
COPY_FILES = ["metadata.json", "wa/metadata.json"]


def main() -> None:
    if not (PROCESSED / "analytics" / "calendar_5km.csv").is_file():
        raise SystemExit("No processed data found: run the pipeline first (see the README).")
    with tempfile.TemporaryDirectory() as scratch, tarfile.open(OUTPUT, "w:gz", compresslevel=9) as archive:
        for name in COPY_FILES:
            if (PROCESSED / name).is_file():
                archive.add(PROCESSED / name, arcname=f"data/processed/{name}")
        for name in COPY_DIRS:
            folder = PROCESSED / name
            if folder.is_dir():
                for path in sorted(folder.rglob("*")):
                    if not path.is_file():
                        continue
                    relative = path.relative_to(PROCESSED).as_posix()
                    if path.name.startswith("cell_days_") and path.suffix == ".parquet":
                        # Two copies: sorted by date (for "this month / this window") and sorted by place (for "this area, all years").
                        table = pq.read_table(path)
                        for label, keys, target in (("by date", [("date", "ascending"), ("grid_y", "ascending"), ("grid_x", "ascending")], path.name),
                                                    ("by place", [("grid_y", "ascending"), ("grid_x", "ascending"), ("date", "ascending")], path.name.replace(".parquet", "_by_place.parquet"))):
                            slim = Path(scratch) / f"{path.parent.name}_{target}"
                            pq.write_table(table.sort_by(keys), slim, compression="zstd", row_group_size=ROW_GROUP)
                            archive.add(slim, arcname=f"data/processed/{path.parent.relative_to(PROCESSED).as_posix()}/{target}")
                            print(f"  {relative} {label}: {slim.stat().st_size / 1e6:.0f} MB")
                            slim.unlink()
                        continue
                    archive.add(path, arcname=f"data/processed/{relative}")
        for path in sorted((PROCESSED / "observations").glob("*.parquet")):
            slim = Path(scratch) / path.name
            table = pq.read_table(path, columns=HOTSPOT_COLUMNS).sort_by([("acq_datetime", "ascending")])
            pq.write_table(table, slim, compression="zstd", row_group_size=ROW_GROUP)
            archive.add(slim, arcname=f"data/processed/observations/{path.name}")
            print(f"  {path.name}: {path.stat().st_size / 1e6:.0f} MB -> {slim.stat().st_size / 1e6:.0f} MB")
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
