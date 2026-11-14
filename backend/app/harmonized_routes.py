"""Routes serving the harmonized calendar, map cells and CSV exports."""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response

from data_pipeline.harmonize import cell_centres

Grid = Literal["1km", "2km", "5km"]
GRID_KM = {"1km": 1.0, "2km": 2.0, "5km": 5.0}
MAX_MAP_CELLS = 20000
METADATA = "harmonized/harmonization_metadata.json"


def register(app: FastAPI, store: Any, jsonable: Any) -> None:
    """Attach the harmonized endpoints; ``store`` is the app's DataStore."""

    def analytics(kind: str, grid: str) -> pd.DataFrame:
        return store.csv(f"analytics/{kind}_{grid}.csv")

    def by_region(frame: pd.DataFrame, region: str | None) -> pd.DataFrame:
        if region:
            if region not in set(frame["region"].unique()):
                raise HTTPException(422, f"Unknown region '{region}'")
            frame = frame[frame["region"] == region]
        return frame

    def by_years(frame: pd.DataFrame, start_year: int | None, end_year: int | None) -> pd.DataFrame:
        if start_year and end_year and end_year < start_year:
            raise HTTPException(422, "end_year must not be earlier than start_year")
        if start_year:
            frame = frame[frame["year"] >= start_year]
        if end_year:
            frame = frame[frame["year"] <= end_year]
        return frame

    @app.get("/api/boundaries")
    def boundaries() -> Any:
        """Ghana ADM1 outline (geoBoundaries, simplified; CC BY-SA 2.0)."""
        path = store.base.parent / "reference" / "GHA_ADM1.geojson"
        if not path.is_file():
            raise HTTPException(503, "Reference boundaries are not available")
        return Response(path.read_text(encoding="utf-8"), media_type="application/geo+json")

    @app.get("/api/harmonization")
    def harmonization() -> dict[str, Any]:
        result: dict[str, Any] = {"harmonization": store.json(METADATA)}
        if store.exists("analytics/analytics_metadata.json"):
            result["analytics"] = store.json("analytics/analytics_metadata.json")
        return result

    @app.get("/api/regions")
    def regions(grid: Grid = "5km") -> dict[str, Any]:
        names = sorted(analytics("calendar", grid)["region"].unique())
        return {"regions": ["Ghana"] + [n for n in names if n != "Ghana"]}

    @app.get("/api/calendar")
    def calendar_rows(
        grid: Grid = "5km", region: str = "Ghana",
        start_year: int | None = Query(None, ge=1990, le=2100),
        end_year: int | None = Query(None, ge=1990, le=2100),
    ) -> dict[str, Any]:
        frame = by_years(by_region(analytics("calendar", grid), region), start_year, end_year)
        return {"grid": grid, "region": region, "total": len(frame), "data": jsonable(frame)}

    @app.get("/api/calendar/anomalies")
    def calendar_anomalies(
        grid: Grid = "5km", region: str | None = None,
        direction: Literal["high", "low"] | None = None,
    ) -> dict[str, Any]:
        frame = by_region(analytics("anomalies", grid), region)
        if direction:
            frame = frame[frame["status"] == f"unusually_{direction}"]
        frame = frame.reindex(frame["robust_score"].abs().sort_values(ascending=False).index)
        return {"total": len(frame), "data": jsonable(frame)}

    @app.get("/api/seasonal")
    def seasonal(grid: Grid = "5km", region: str = "Ghana") -> dict[str, Any]:
        return {"grid": grid, "region": region,
                "data": jsonable(by_region(analytics("seasonal", grid), region))}

    @app.get("/api/annual")
    def annual(grid: Grid = "5km", region: str = "Ghana") -> dict[str, Any]:
        return {"grid": grid, "region": region,
                "data": jsonable(by_region(analytics("annual", grid), region))}

    def month_cells(grid: str, year: int, month: int, region: str | None) -> pd.DataFrame:
        path = f"harmonized/cell_days_{grid}.parquet"
        if not store.exists(path):
            raise HTTPException(503, f"Analytical dataset '{path}' is not available")
        start = pd.Timestamp(year=year, month=month, day=1)
        end = start + pd.offsets.MonthBegin(1)
        frame = pd.read_parquet(store.base / path, filters=[("date", ">=", start), ("date", "<", end)])
        if region and region != "Ghana":
            if "region" not in frame or region not in set(frame["region"].unique()):
                if "region" in frame and frame.empty:
                    return frame
                raise HTTPException(422, f"Unknown region '{region}'")
            frame = frame[frame["region"] == region]
        return frame

    def aggregate_cells(frame: pd.DataFrame, grid: str) -> pd.DataFrame:
        columns = ["grid_x", "grid_y", "active_days", "modis_detections", "viirs_detections",
                   "days_both", "longitude", "latitude"]
        if frame.empty:
            return pd.DataFrame(columns=columns)
        cells = (
            frame.assign(is_both=frame["occupied_by"] == "both")
            .groupby(["grid_x", "grid_y"], observed=True)
            .agg(active_days=("date", "nunique"), modis_detections=("modis_detections", "sum"),
                 viirs_detections=("viirs_detections", "sum"), days_both=("is_both", "sum"))
            .reset_index()
        )
        return cell_centres(cells, GRID_KM[grid])

    @app.get("/api/map/cells")
    def map_cells(
        year: int = Query(..., ge=1990, le=2100), month: int = Query(..., ge=1, le=12),
        grid: Grid = "5km", region: str | None = None,
    ) -> dict[str, Any]:
        cells = aggregate_cells(month_cells(grid, year, month, region), grid)
        truncated = len(cells) > MAX_MAP_CELLS
        if truncated:
            cells = cells.nlargest(MAX_MAP_CELLS, "active_days")
        features = [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
             "properties": {k: r[k] for k in ("active_days", "modis_detections", "viirs_detections", "days_both")}}
            for r in jsonable(cells)
        ]
        return {
            "type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": features, "truncated": truncated,
            "note": "Cell centres; active_days = days in the month with at least one detection.",
        }

    def csv_response(frame: pd.DataFrame, filename: str, header: dict[str, Any]) -> Response:
        meta = store.json(METADATA) if store.exists(METADATA) else {}
        lines = [
            "# TerraGuard export",
            "# source: NASA FIRMS standard-processing MODIS and VIIRS active-fire detections",
            f"# harmonization: {meta.get('harmonization_method', 'n/a')} version {meta.get('harmonization_version', 'n/a')}",
            "# note: counts are satellite detections or active cell-days, not unique fires; sensors are not calibrated to each other",
        ] + [f"# {k}: {v}" for k, v in header.items()]
        body = "\n".join(lines) + "\n" + frame.to_csv(index=False)
        return Response(body, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    @app.get("/api/export/calendar.csv")
    def export_calendar(grid: Grid = "5km", region: str = "Ghana",
                        start_year: int | None = None, end_year: int | None = None) -> Response:
        frame = by_years(by_region(analytics("calendar", grid), region), start_year, end_year)
        years = f"{frame['year'].min()}-{frame['year'].max()}" if len(frame) else "none"
        safe = region.replace(" ", "_")
        return csv_response(frame, f"terraguard_calendar_{safe}_{grid}.csv",
                            {"area": region, "grid": grid, "years": years})

    @app.get("/api/export/cells.csv")
    def export_cells(year: int = Query(..., ge=1990, le=2100), month: int = Query(..., ge=1, le=12),
                     grid: Grid = "5km", region: str | None = None) -> Response:
        cells = aggregate_cells(month_cells(grid, year, month, region), grid)
        return csv_response(cells, f"terraguard_cells_{year}-{month:02d}_{grid}.csv",
                            {"area": region or "Ghana", "grid": grid, "period": f"{year}-{month:02d}"})
