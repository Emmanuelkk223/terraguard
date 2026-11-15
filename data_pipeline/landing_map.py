"""Build the small animated map on the landing page: West Africa's countries and where it burned in each month of one burning season.

    python -m data_pipeline.landing_map            # writes frontend/public/landing-map.json (about 100 KB)

The points are real: active 5 km cell-days from the West Africa dataset (all satellites), grouped into 0.2 degree squares so the file stays
small. Each month keeps its busiest squares; the size of a dot follows how many cell-days it had. Country outlines are geoBoundaries ADM0,
simplified for drawing only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from shapely.geometry import mapping, shape

from data_pipeline.harmonize import KM_PER_DEG_LAT, KM_PER_DEG_LON_EQUATOR, REFERENCE_LATITUDE

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "data" / "processed" / "wa" / "harmonized" / "cell_days_5km.parquet"
COUNTRIES = ROOT / "data" / "reference" / "WA_ADM0.geojson"
OUTPUT = ROOT / "frontend" / "public" / "landing-map.json"

WEST, EAST, SOUTH, NORTH = -18.0, 16.0, 4.0, 20.5  # the drawing frame (the Sahara north of 20.5 N is left out)
WIDTH = 1000
COS = math.cos(math.radians(12.0))
SCALE = WIDTH / ((EAST - WEST) * COS)
HEIGHT = round((NORTH - SOUTH) * SCALE)
BIN = 0.2  # degrees
MAX_POINTS = 650  # per month


def xy(lon: float, lat: float) -> tuple[float, float]:
    return round((lon - WEST) * COS * SCALE, 1), round((NORTH - lat) * SCALE, 1)


def ring_path(coords) -> str:
    pts = [xy(lon, lat) for lon, lat in coords]
    return "M" + "L".join(f"{x} {y}" for x, y in pts) + "Z"


def country_paths() -> list[dict]:
    out = []
    for feature in json.loads(COUNTRIES.read_text(encoding="utf-8"))["features"]:
        geom = shape(feature["geometry"]).simplify(0.06, preserve_topology=True)
        polys = mapping(geom)["coordinates"] if geom.geom_type == "MultiPolygon" else [mapping(geom)["coordinates"]]
        parts = [ring_path(poly[0]) for poly in polys if len(poly[0]) > 3]
        centre = geom.representative_point()
        cx, cy = xy(centre.x, centre.y)
        out.append({"iso2": feature["properties"]["iso2"], "name": feature["properties"]["name"], "d": "".join(parts), "cx": cx, "cy": cy})
    return out


def season_months(end_year: int) -> list[pd.Timestamp]:
    return [pd.Timestamp(year=end_year - 1 if m >= 10 else end_year, month=m, day=1) for m in (10, 11, 12, 1, 2, 3, 4)]


def main() -> None:
    km_lon = KM_PER_DEG_LON_EQUATOR * math.cos(math.radians(REFERENCE_LATITUDE))
    last = pd.Timestamp(ds.dataset(CELLS).to_table(columns=["date"]).column("date").to_pandas().max())
    end_year = last.year if last.month >= 5 else last.year - 1  # the latest season that is complete through April
    frames = []
    for start in season_months(end_year):
        stop = start + pd.offsets.MonthBegin(1)
        table = ds.dataset(CELLS).to_table(
            columns=["grid_x", "grid_y"],
            filter=(ds.field("date") >= start) & (ds.field("date") < stop),
        ).to_pandas()
        lon = (table["grid_x"] + 0.5) * 5 / km_lon
        lat = (table["grid_y"] + 0.5) * 5 / KM_PER_DEG_LAT
        keep = (lon >= WEST) & (lon <= EAST) & (lat >= SOUTH) & (lat <= NORTH)
        binned = pd.DataFrame({"bx": np.floor(lon[keep] / BIN), "by": np.floor(lat[keep] / BIN)}).value_counts().rename("n").reset_index()
        binned = binned.sort_values("n", ascending=False).head(MAX_POINTS)
        top = max(int(binned["n"].max()), 1) if len(binned) else 1
        points = []
        for bx, by, n in binned.itertuples(index=False):
            x, y = xy((bx + 0.5) * BIN, (by + 0.5) * BIN)
            points.append([x, y, round(math.log1p(n) / math.log1p(top), 2)])
        frames.append({"label": start.strftime("%B %Y"), "month": start.month, "cell_days": int(len(table)), "points": points})
        print(f"{start:%Y-%m}: {len(table):,} cell-days, {len(points)} dots")
    payload = {
        "width": WIDTH, "height": HEIGHT, "frame": [WEST, SOUTH, EAST, NORTH], "cos": COS, "scale": SCALE,
        "season": f"{end_year - 1}–{str(end_year)[2:]}",
        "source": "NASA FIRMS (MODIS and VIIRS, all satellites), active 5 km cell-days grouped into 0.2° squares; boundaries geoBoundaries",
        "countries": country_paths(), "frames": frames,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
