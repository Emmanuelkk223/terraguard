"""Ghana boundary clipping and region assignment (vectorised, shapely 2)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import shape
from shapely.ops import unary_union

DEFAULT_ADM1 = Path("data/reference/GHA_ADM1.geojson")
COUNTRY_NAME = "Ghana"


class GhanaRegions:
    """Country outline (union of ADM1) and 16 region polygons."""

    def __init__(self, geojson_path: Path = DEFAULT_ADM1) -> None:
        payload = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
        features = [f for f in payload["features"] if f.get("geometry")]
        self.names = [
            str(f["properties"]["shapeName"]).removesuffix(" Region") for f in features
        ]
        self.geoms = [shapely.make_valid(shape(f["geometry"])) for f in features]
        self.country = unary_union(self.geoms)
        self._tree = shapely.STRtree(self.geoms)
        shapely.prepare(self.country)

    def inside_country(self, longitude: np.ndarray, latitude: np.ndarray) -> np.ndarray:
        return shapely.contains_xy(self.country, np.asarray(longitude), np.asarray(latitude))

    def region_for(self, longitude: np.ndarray, latitude: np.ndarray) -> np.ndarray:
        """Region name per point; nearest region when a point is on a gap/border."""
        lon, lat = np.asarray(longitude, float), np.asarray(latitude, float)
        result = np.full(len(lon), None, dtype=object)
        for name, geom in zip(self.names, self.geoms):
            unassigned = np.equal(result, None)
            if not unassigned.any():
                break
            hit = unassigned & shapely.contains_xy(geom, lon, lat)
            result[hit] = name
        missing = np.flatnonzero(np.equal(result, None))
        if len(missing):
            pairs = self._tree.query_nearest(shapely.points(lon[missing], lat[missing]))
            for point_index, tree_index in zip(pairs[0], pairs[1]):
                result[missing[point_index]] = self.names[tree_index]
        return result
