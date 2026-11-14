"""Tests for Ghana region assignment using the committed reference boundaries.

Locations used are well-known city coordinates; this checks the geometry code.
"""

from __future__ import annotations

import numpy as np

from data_pipeline.regions import GhanaRegions

REGIONS = GhanaRegions()


def test_sixteen_regions_loaded() -> None:
    assert len(REGIONS.names) == 16 and "Greater Accra" in REGIONS.names


def test_known_cities_fall_in_expected_regions() -> None:
    lon = np.array([-0.187, -1.624, -0.843, 9.0])
    lat = np.array([5.603, 6.688, 9.402, 50.0])  # Accra, Kumasi, Tamale, Europe
    assert REGIONS.inside_country(lon, lat).tolist() == [True, True, True, False]
    assert REGIONS.region_for(lon[:3], lat[:3]).tolist() == ["Greater Accra", "Ashanti", "Northern"]


def test_border_point_is_assigned_to_nearest_region_not_dropped() -> None:
    assert REGIONS.region_for(np.array([-3.5]), np.array([5.0]))[0] in REGIONS.names
