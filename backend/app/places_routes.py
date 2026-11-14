"""Place search for the dashboard: find a town, city, region or country across West Africa.

Runs entirely on a local gazetteer (GeoNames, CC BY 4.0), so what a user types is never sent to another service.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from data_pipeline.places import COVERED_COUNTRIES, Gazetteer

GAZETTEER_FILE = "west_africa_places.parquet"


def register(app: FastAPI, store: Any) -> None:
    holder: dict[str, Any] = {}

    def gazetteer() -> Gazetteer:
        path = store.base.parent / "reference" / GAZETTEER_FILE
        if not path.is_file():
            raise HTTPException(503, "The place gazetteer is not available. Build it with: python -m data_pipeline.gazetteer")
        stamp = path.stat().st_mtime
        if holder.get("stamp") != stamp:
            try:
                holder["gazetteer"], holder["stamp"] = Gazetteer.load(path), stamp
            except Exception as exc:  # unreadable or mid-write
                raise HTTPException(503, "The place gazetteer could not be read; it may be updating. Retry in a moment.") from exc
        return holder["gazetteer"]

    @app.get("/api/places/search")
    def search_places(q: str = Query("", max_length=80), limit: int = Query(8, ge=1, le=20)) -> dict[str, Any]:
        """Matches for a town, city, region or country, best first. ``covered`` says whether TerraGuard has fire data there."""
        return {"query": q, "covered_countries": sorted(COVERED_COUNTRIES), "data": gazetteer().search(q, limit)}

    @app.get("/api/places/coverage")
    def place_coverage() -> dict[str, Any]:
        table = gazetteer().table
        countries = table[table["kind"] == "country"]
        return {
            "covered_countries": sorted(COVERED_COUNTRIES),
            "searchable_countries": sorted(str(c) for c in countries["country"]),
            "places": int(len(table)),
            "note": "Search covers West Africa; fire data currently exist only for the covered countries.",
        }
