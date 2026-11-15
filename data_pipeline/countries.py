"""West Africa country registry (Ghana first) and national boundaries.

Ghana is the primary area of TerraGuard: it keeps the full-detail pipeline (1, 2 and 5 km grids, 16 regions,
rainfall context). The other fifteen West African countries are processed on a 5 km grid at country level.
The order below is the order shown to users: Ghana, then its neighbours, then the rest alphabetically.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import numpy as np

from . import atomic

# (ISO3, ISO2, name, role). Order matters: Ghana first, neighbours next, then the rest alphabetically.
COUNTRIES: list[tuple[str, str, str, str]] = [
    ("GHA", "GH", "Ghana", "primary"),
    ("CIV", "CI", "Côte d'Ivoire", "neighbour"),
    ("TGO", "TG", "Togo", "neighbour"),
    ("BFA", "BF", "Burkina Faso", "neighbour"),
    ("BEN", "BJ", "Benin", "west-africa"),
    ("CPV", "CV", "Cabo Verde", "west-africa"),
    ("GMB", "GM", "Gambia", "west-africa"),
    ("GIN", "GN", "Guinea", "west-africa"),
    ("GNB", "GW", "Guinea-Bissau", "west-africa"),
    ("LBR", "LR", "Liberia", "west-africa"),
    ("MLI", "ML", "Mali", "west-africa"),
    ("MRT", "MR", "Mauritania", "west-africa"),
    ("NER", "NE", "Niger", "west-africa"),
    ("NGA", "NG", "Nigeria", "west-africa"),
    ("SEN", "SN", "Senegal", "west-africa"),
    ("SLE", "SL", "Sierra Leone", "west-africa"),
]
ISO2_BY_ISO3 = {c[0]: c[1] for c in COUNTRIES}
ROLE_BY_NAME = {c[2]: c[3] for c in COUNTRIES}
NAME_BY_ISO3 = {c[0]: c[2] for c in COUNTRIES}
ORDER = [c[2] for c in COUNTRIES]
REGION_NAME = "West Africa"
DEFAULT_BOUNDARIES = Path("data/reference/WA_ADM0.geojson")
API = "https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM0/"


def fetch_boundaries(output: Path = DEFAULT_BOUNDARIES) -> dict:
    """Download the simplified national outlines (geoBoundaries gbOpen) for the sixteen countries."""
    features, licences = [], {}
    for iso3, iso2, name, _ in COUNTRIES:
        with urllib.request.urlopen(API.format(iso3=iso3), timeout=60) as response:
            meta = json.load(response)
        licences[iso3] = meta.get("boundaryLicense")
        with urllib.request.urlopen(meta["simplifiedGeometryGeoJSON"], timeout=120) as response:
            shape = json.load(response)
        for feature in shape["features"]:
            feature["properties"] = {"iso3": iso3, "iso2": iso2, "name": name}
            features.append(feature)
    collection = {"type": "FeatureCollection", "features": features}
    atomic.write_text(output, json.dumps(collection, separators=(",", ":")))
    return {"features": len(features), "licences": licences}


def bounding_box(path: Path = DEFAULT_BOUNDARIES, margin: float = 0.25) -> tuple[float, float, float, float]:
    """(west, south, east, north) around every country, for the FIRMS download area."""
    collection = json.loads(Path(path).read_text(encoding="utf-8"))
    xs, ys = [], []

    def walk(node):
        if isinstance(node[0], (int, float)):
            xs.append(node[0])
            ys.append(node[1])
        else:
            for child in node:
                walk(child)

    for feature in collection["features"]:
        walk(feature["geometry"]["coordinates"])
    return (round(min(xs) - margin, 2), round(min(ys) - margin, 2), round(max(xs) + margin, 2), round(max(ys) + margin, 2))


class Countries:
    """Point-in-polygon assignment of detections to the sixteen countries (vectorised, prepared geometry)."""

    def __init__(self, path: Path = DEFAULT_BOUNDARIES) -> None:
        import shapely
        from shapely.geometry import shape

        collection = json.loads(Path(path).read_text(encoding="utf-8"))
        self._shapely = shapely
        self.names: list[str] = []
        self.geoms = []
        for feature in collection["features"]:
            geometry = shape(feature["geometry"])
            shapely.prepare(geometry)
            self.names.append(feature["properties"]["name"])
            self.geoms.append(geometry)
        self.bounds = [g.bounds for g in self.geoms]

    def country_for(self, longitude: np.ndarray, latitude: np.ndarray) -> np.ndarray:
        """Country name per point, or '' when the point lies in none of the sixteen (sea, neighbouring states)."""
        shapely = self._shapely
        result = np.full(len(longitude), "", dtype=object)
        for name, geometry, (west, south, east, north) in zip(self.names, self.geoms, self.bounds):
            candidate = np.flatnonzero((result == "") & (longitude >= west) & (longitude <= east)
                                       & (latitude >= south) & (latitude <= north))
            if candidate.size:
                inside = shapely.contains_xy(geometry, longitude[candidate], latitude[candidate])
                result[candidate[inside]] = name
        return result


def country_bounds(path: Path = DEFAULT_BOUNDARIES) -> dict[str, list[float]]:
    """[west, south, east, north] of each country (largest outline pieces included), for map navigation."""
    result: dict[str, list[float]] = {}
    countries = Countries(path)
    for name, (west, south, east, north) in zip(countries.names, countries.bounds):
        old = result.get(name)
        box = [west, south, east, north]
        result[name] = box if old is None else [min(old[0], west), min(old[1], south), max(old[2], east), max(old[3], north)]
    return {k: [round(v, 2) for v in box] for k, box in result.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_BOUNDARIES)
    args = parser.parse_args()
    info = fetch_boundaries(args.output)
    print(json.dumps(info, indent=2))
    west, south, east, north = bounding_box(args.output)
    print(f"download area (west,south,east,north): {west},{south},{east},{north}")


if __name__ == "__main__":
    main()
