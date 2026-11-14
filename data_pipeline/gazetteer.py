"""Build the West Africa place gazetteer used by the dashboard's search box.

Source: GeoNames (https://www.geonames.org/, CC BY 4.0), the per-country dumps for the 16 West African
countries plus countryInfo.txt and admin1CodesASCII.txt. Downloads are kept unchanged in data/raw/gazetteer/.

What is kept:
  * Every populated place (feature class P) in the 16 countries, so someone in a small town can find it. Abandoned,
    destroyed and historical places are dropped. GeoNames records population as 0 (unknown) for most places, so population
    is NOT used to filter; administrative importance (capital, regional seat, district seat) ranks results instead.
  * The 16 countries themselves, and Ghana's 16 regions (the areas TerraGuard analyses).

Place names are searched locally and offline: what a user types never leaves the application.
"""

from __future__ import annotations

import argparse
import io
import re
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from . import atomic
from .regions import DEFAULT_ADM1, GhanaRegions

BASE_URL = "https://download.geonames.org/export/dump/"
WEST_AFRICA = {
    "BJ": "Benin", "BF": "Burkina Faso", "CV": "Cabo Verde", "CI": "Côte d'Ivoire", "GM": "The Gambia", "GH": "Ghana",
    "GN": "Guinea", "GW": "Guinea-Bissau", "LR": "Liberia", "ML": "Mali", "MR": "Mauritania", "NE": "Niger",
    "NG": "Nigeria", "SN": "Senegal", "SL": "Sierra Leone", "TG": "Togo",
}
EXCLUDED_CODES = {"PPLQ", "PPLW", "PPLH", "PPLCH"}  # abandoned, destroyed, historical
# administrative importance of a populated place: capital > regional seat > district seat > other
SEAT_RANK = {"PPLC": 4, "PPLA": 3, "PPLA2": 2, "PPLA3": 1}
CITY_POPULATION, TOWN_POPULATION = 50_000, 5_000
MAX_ALT_CHARS = 160
COLUMNS = ["geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude", "feature_class", "feature_code",
           "country_code", "cc2", "admin1_code", "admin2_code", "admin3_code", "admin4_code", "population", "elevation",
           "dem", "timezone", "modified"]
OUTPUT_COLUMNS = ["id", "name", "kind", "norm", "alt_norm", "admin1", "country", "country_code", "lat", "lon", "population",
                  "feature_code", "seat_rank", "ghana_region", "west", "south", "east", "north"]


def normalise(text: str) -> str:
    """Lower case, accents and punctuation removed, single spaces: 'Côte d'Ivoire' -> 'cote d ivoire'."""
    folded = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", folded)).strip()


def kind_for(population: float, feature_code: str) -> str:
    """city / town / place. Most places have unknown population, so seats of government count too."""
    if feature_code in ("PPLC", "PPLA") or population >= CITY_POPULATION:
        return "city"
    return "town" if feature_code in ("PPLA2", "PPLA3") or population >= TOWN_POPULATION else "place"


def download(raw_dir: Path, names: list[str]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        target = raw_dir / name
        if target.exists():  # raw downloads are kept unchanged and never refetched
            continue
        with urllib.request.urlopen(BASE_URL + name, timeout=120) as response:
            atomic.write_bytes(target, response.read())


def read_country(raw_dir: Path, code: str) -> pd.DataFrame:
    with zipfile.ZipFile(raw_dir / f"{code}.zip") as archive:
        with archive.open(f"{code}.txt") as handle:
            frame = pd.read_csv(handle, sep="\t", header=None, names=COLUMNS, dtype=str, keep_default_na=False, quoting=3)
    frame["population"] = pd.to_numeric(frame["population"], errors="coerce").fillna(0)
    for column in ("latitude", "longitude"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["latitude", "longitude"])


def select_places(frame: pd.DataFrame, code: str) -> pd.DataFrame:
    populated = frame[(frame["feature_class"] == "P") & ~frame["feature_code"].isin(EXCLUDED_CODES)]
    return populated


def admin1_names(raw_dir: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    for line in (raw_dir / "admin1CodesASCII.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            names[parts[0]] = parts[1]
    return names


def build(raw_dir: Path, adm1: Path = DEFAULT_ADM1) -> pd.DataFrame:
    admin = admin1_names(raw_dir)
    regions = GhanaRegions(adm1)
    rows: list[pd.DataFrame] = []
    country_boxes: dict[str, tuple[float, float, float, float]] = {}
    for code, country in WEST_AFRICA.items():
        places = select_places(read_country(raw_dir, code), code).copy()
        if places.empty:
            continue
        country_boxes[code] = (places["longitude"].min(), places["latitude"].min(), places["longitude"].max(), places["latitude"].max())
        alt = places["alternatenames"].map(lambda s: normalise(s.replace(",", " "))[:MAX_ALT_CHARS])
        frame = pd.DataFrame({
            "id": places["geonameid"].astype(int),
            "name": places["name"],
            "kind": [kind_for(p, c) for p, c in zip(places["population"], places["feature_code"])],
            "norm": places["name"].map(normalise),
            "alt_norm": alt,
            "admin1": [admin.get(f"{code}.{a}", "") for a in places["admin1_code"]],
            "country": country, "country_code": code,
            "lat": places["latitude"].round(5), "lon": places["longitude"].round(5),
            "population": places["population"].astype(int), "feature_code": places["feature_code"],
            "seat_rank": places["feature_code"].map(SEAT_RANK).fillna(0).astype(int),
        })
        if code == "GH":  # which of TerraGuard's 16 regions each Ghanaian place falls in
            frame["ghana_region"] = regions.region_for(frame["lon"].to_numpy(), frame["lat"].to_numpy())
        rows.append(frame)

    countries = pd.DataFrame([
        {"id": -(i + 1), "name": name, "kind": "country", "norm": normalise(name), "alt_norm": normalise(code),
         "admin1": "", "country": name, "country_code": code, "seat_rank": 5,
         "lat": round((box[1] + box[3]) / 2, 4), "lon": round((box[0] + box[2]) / 2, 4), "population": 0, "feature_code": "PCLI",
         "west": round(box[0] - 0.2, 3), "south": round(box[1] - 0.2, 3), "east": round(box[2] + 0.2, 3), "north": round(box[3] + 0.2, 3)}
        for i, (code, name) in enumerate((c, WEST_AFRICA[c]) for c in country_boxes) for box in [country_boxes[code]]
    ])
    ghana_regions = pd.DataFrame([
        {"id": -(100 + i), "name": f"{name} Region", "kind": "region", "norm": normalise(f"{name} region"), "alt_norm": normalise(name),
         "admin1": "", "country": "Ghana", "country_code": "GH", "ghana_region": name, "seat_rank": 5,
         "lat": round(geom.representative_point().y, 4), "lon": round(geom.representative_point().x, 4), "population": 0,
         "feature_code": "ADM1", "west": round(geom.bounds[0], 3), "south": round(geom.bounds[1], 3),
         "east": round(geom.bounds[2], 3), "north": round(geom.bounds[3], 3)}
        for i, (name, geom) in enumerate(zip(regions.names, regions.geoms))
    ])
    table = pd.concat(rows + [countries, ghana_regions], ignore_index=True)
    for column in OUTPUT_COLUMNS:
        if column not in table:
            table[column] = np.nan
    return table[OUTPUT_COLUMNS].drop_duplicates(subset=["id"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/gazetteer"))
    parser.add_argument("--output", type=Path, default=Path("data/reference/west_africa_places.parquet"))
    parser.add_argument("--adm1", type=Path, default=DEFAULT_ADM1)
    args = parser.parse_args()
    download(args.raw_dir, [f"{c}.zip" for c in WEST_AFRICA] + ["countryInfo.txt", "admin1CodesASCII.txt"])
    table = build(args.raw_dir, args.adm1)
    atomic.to_parquet(table, args.output, index=False, compression="zstd")
    print(f"{len(table):,} entries -> {args.output} ({args.output.stat().st_size / 1e6:.1f} MB)")
    print(table["kind"].value_counts().to_dict())
    print(table[table["kind"].isin(["city", "town", "village"])].groupby("country_code").size().to_dict())


if __name__ == "__main__":
    main()
