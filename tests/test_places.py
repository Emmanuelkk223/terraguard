"""Tests for the gazetteer build and place search.

The small tables are hand-built TEST DATA in GeoNames' format (not a claim about real places or populations).
A few integration checks use the committed gazetteer for well-known towns.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline import gazetteer
from data_pipeline.places import COVERED_COUNTRIES, Gazetteer

REAL = Path("data/reference/west_africa_places.parquet")


def _row(geonameid, name, lat, lon, code, feature="PPL", population=0, admin1="01", alternates="", cls="P") -> str:
    fields = [str(geonameid), name, name, alternates, str(lat), str(lon), cls, feature, code, "", admin1, "", "", "", str(population), "", "", "", "2020-01-01"]
    return "\t".join(fields)


def _zip(raw: Path, code: str, rows: list[str]) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{code}.txt", "\n".join(rows) + "\n")
    (raw / f"{code}.zip").write_bytes(buffer.getvalue())


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> pd.DataFrame:
    raw = tmp_path_factory.mktemp("raw")
    _zip(raw, "GH", [
        _row(1, "Kumasi", 6.69, -1.62, "GH", "PPLA", 3_000_000, "AS"),
        _row(2, "Kumasi", 6.0, 0.4, "GH", "PPL", 0, "VO"),  # a village with the same name
        _row(3, "Accra", 5.55, -0.2, "GH", "PPLC", 2_000_000, "AA", alternates="Akra,Nkran"),
        _row(4, "Old Fort", 5.5, -0.1, "GH", "PPLQ"),  # abandoned: must be dropped
        _row(5, "Lake Volta", 7.0, 0.0, "GH", "LK", cls="H"),  # not a populated place
    ])
    _zip(raw, "NG", [_row(10, "Lagos", 6.45, 3.4, "NG", "PPLA", 8_000_000, "05"), _row(11, "Kumasi", 9.0, 8.0, "NG")])
    _zip(raw, "CI", [_row(20, "Abidjan", 5.35, -4.0, "CI", "PPLA", 4_000_000, "01")])
    for code in gazetteer.WEST_AFRICA:
        if not (raw / f"{code}.zip").exists():
            _zip(raw, code, [_row(900 + len(code) + ord(code[0]), f"Town of {code}", 10.0, 1.0, code)])
    (raw / "admin1CodesASCII.txt").write_text("GH.AS\tAshanti Region\tx\t1\nGH.VO\tVolta Region\tx\t2\nGH.AA\tGreater Accra Region\tx\t3\n"
                                              "NG.05\tLagos\tx\t4\nCI.01\tAbidjan District\tx\t5\n", encoding="utf-8")
    return gazetteer.build(raw)


@pytest.fixture(scope="module")
def search(built) -> Gazetteer:
    return Gazetteer(built)


def test_normalise_folds_accents_case_and_punctuation() -> None:
    assert gazetteer.normalise("Côte d'Ivoire") == "cote d ivoire"
    assert gazetteer.normalise("  Sekondi-Takoradi ") == "sekondi takoradi"


def test_build_keeps_populated_places_only_and_adds_countries_and_regions(built: pd.DataFrame) -> None:
    kinds = built["kind"].value_counts().to_dict()
    assert kinds["country"] == 16 and kinds["region"] == 16
    assert "Old Fort" not in set(built["name"]) and "Lake Volta" not in set(built["name"])  # historical / not populated
    kumasi = built[(built["name"] == "Kumasi") & (built["country_code"] == "GH")]
    assert len(kumasi) == 2 and set(kumasi["ghana_region"]) <= set(built["ghana_region"].dropna())
    assert built.loc[built["name"] == "Accra", "kind"].iloc[0] == "city"  # capital
    assert built["id"].is_unique


def test_exact_and_prefix_matches_rank_the_important_place_first(search: Gazetteer) -> None:
    top = search.search("kumasi")[0]
    assert top["name"] == "Kumasi" and top["kind"] == "city" and top["region"] is not None
    assert top["covered"] is True and top["country_code"] == "GH"
    assert search.search("kum")[0]["name"] == "Kumasi"  # as-you-type prefix


def test_accents_case_and_alternate_names(search: Gazetteer) -> None:
    assert search.search("ACCRA")[0]["name"] == "Accra"
    assert search.search("nkran")[0]["name"] == "Accra"  # an alternate name
    assert search.search("Côte d'Ivoire")[0]["kind"] == "country"
    assert search.search("ivory coast")[0]["country_code"] == "CI"  # alias of the country name


def test_country_suffix_restricts_the_search(search: Gazetteer) -> None:
    ng = search.search("kumasi, nigeria")
    assert [r["country_code"] for r in ng] == ["NG"]
    assert [r["country_code"] for r in search.search("kumasi ghana")] == ["GH", "GH"]
    assert search.search("kumasi, ng")[0]["country_code"] == "NG"  # ISO code after a comma


def test_typing_a_country_name_finds_the_country_first(search: Gazetteer) -> None:
    top = search.search("ghana")[0]
    assert top["kind"] == "country" and top["bbox"][0] < top["bbox"][2] and top["covered"] is True
    assert search.search("nigeria")[0]["kind"] == "country" and search.search("nigeria")[0]["covered"] is True  # all sixteen countries are covered


def test_regions_and_coverage_flags(search: Gazetteer) -> None:
    region = [r for r in search.search("ashanti") if r["kind"] == "region"]
    assert region and region[0]["region"] == "Ashanti" and region[0]["bbox"]
    lagos = search.search("lagos")[0]
    assert lagos["covered"] is True and "GH" in COVERED_COUNTRIES and "NG" in COVERED_COUNTRIES and len(COVERED_COUNTRIES) == 16


def test_short_empty_and_nonsense_queries_are_harmless(search: Gazetteer) -> None:
    assert search.search("") == [] and search.search("a") == [] and search.search("   ") == []
    assert search.search("zzzzqq") == []
    assert len(search.search("town", limit=3)) <= 3
    assert search.search("kumasi") == search.search("kumasi")  # cached result is identical


@pytest.mark.skipif(not REAL.exists(), reason="committed gazetteer not present")
def test_real_gazetteer_finds_well_known_towns() -> None:
    real = Gazetteer.load(REAL)
    checks = {"kumasi": ("Kumasi", "GH"), "tamale": ("Tamale", "GH"), "accra": ("Accra", "GH"), "lagos": ("Lagos", "NG"),
              "abidjan": ("Abidjan", "CI"), "dakar": ("Dakar", "SN"), "bamako": ("Bamako", "ML"), "ouagadougou": ("Ouagadougou", "BF")}
    for query, (name, code) in checks.items():
        top = real.search(query)[0]
        assert (top["name"], top["country_code"]) == (name, code), query
    ghana = real.search("ghana")[0]
    assert ghana["kind"] == "country" and ghana["covered"] and real.search("ivory coast")[0]["country_code"] == "CI"
    assert real.search("Tamale, Ghana")[0]["region"] == "Northern"
    assert len(real.table) > 100_000 and real.table["country_code"].nunique() == 16


def test_search_api_returns_ranked_places_with_coverage(tmp_path: Path, search: Gazetteer) -> None:
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    client = TestClient(create_app(tmp_path))
    assert client.get("/api/places/search", params={"q": "kumasi"}).status_code == 503  # gazetteer not built yet
    (tmp_path / "data" / "reference").mkdir(parents=True)
    search.table.to_parquet(tmp_path / "data" / "reference" / "west_africa_places.parquet", index=False)
    body = client.get("/api/places/search", params={"q": "Kumasi, Ghana", "limit": 3}).json()
    assert "GH" in body["covered_countries"] and len(body["covered_countries"]) == 16 and body["data"][0]["name"] == "Kumasi" and body["data"][0]["covered"] is True
    assert len(body["data"]) <= 3
    lagos = client.get("/api/places/search", params={"q": "lagos"}).json()["data"][0]
    assert lagos["country_code"] == "NG" and lagos["covered"] is True
    assert client.get("/api/places/search", params={"q": "x"}).json()["data"] == []  # too short
    assert client.get("/api/places/search", params={"q": "a" * 81}).status_code == 422
    assert client.get("/api/places/search", params={"q": "ab", "limit": 99}).status_code == 422
    coverage = client.get("/api/places/coverage").json()
    assert "GH" in coverage["covered_countries"] and len(coverage["covered_countries"]) == 16 and "Ghana" in coverage["searchable_countries"] and coverage["places"] > 0


def test_ghana_wins_an_otherwise_equal_match() -> None:
    from data_pipeline.places import Gazetteer
    rows = [
        {"id": 1, "name": "Bonuso", "norm": "bonuso", "alt_norm": "", "kind": "town", "admin1": "A", "country": "Togo", "country_code": "TG",
         "lat": 8.0, "lon": 1.0, "population": 0, "seat_rank": 0, "region": None},
        {"id": 2, "name": "Bonuso", "norm": "bonuso", "alt_norm": "", "kind": "town", "admin1": "B", "country": "Ghana", "country_code": "GH",
         "lat": 7.0, "lon": -1.0, "population": 0, "seat_rank": 0, "region": "Ashanti"},
    ]
    results = Gazetteer(pd.DataFrame(rows)).search("bonuso")
    assert [r["country_code"] for r in results] == ["GH", "TG"]
