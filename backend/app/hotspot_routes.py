"""Individual hotspot download and the "current period versus previous years" comparison.

Two outputs the harmonized calendar alone cannot give:

* ``/api/export/hotspots.csv`` lists the individual satellite detections inside a chosen
  area and date range (one row per detection), as the challenge asks for.
* ``/api/current-comparison`` puts the most recent period of data next to the same dates
  in every earlier year, so "how does what is happening now compare with the past?" has a
  direct, honest answer.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any, Callable

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response

from data_pipeline.area_analytics import select_cells
from data_pipeline.harmonize import AQUA_FIRST_FULL_MONTH, STABLE_PLATFORMS
from data_pipeline.regions import GhanaRegions

MAX_HOTSPOT_ROWS = 300_000
HOTSPOT_PRODUCTS = ("MODIS_SP", "VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP")
PRODUCT_COLUMNS = [
    "acq_datetime", "latitude", "longitude", "sensor", "satellite", "platform", "confidence",
    "confidence_class", "frp", "daynight", "source_product",
]
SENSOR_FILTER = {"harmonized": ("MODIS", "VIIRS"), "steady": ("MODIS", "VIIRS"), "modis": ("MODIS",), "viirs": ("VIIRS",)}
DEFAULT_WINDOW_DAYS = 30


def register(app: FastAPI, store: Any, jsonable: Callable, helpers: dict[str, Callable]) -> None:
    regions_holder: dict[str, Any] = {}

    def regions() -> GhanaRegions:
        if "regions" not in regions_holder:
            path = store.base.parent / "reference" / "GHA_ADM1.geojson"
            if not path.is_file():
                raise HTTPException(503, "Reference boundaries are not available")
            regions_holder["regions"] = GhanaRegions(path)
        return regions_holder["regions"]

    def read_hotspots(first: pd.Timestamp, last: pd.Timestamp, region: str, bbox_text: str | None, sensor: str) -> pd.DataFrame:
        bbox = helpers["parsed_bbox"](bbox_text)
        scope = helpers["scope_for"](region, bbox_text)
        if bbox is None and region != "Ghana":
            helpers["check_region"]("5km", region, scope)
        parts = []
        stop = last + pd.Timedelta(days=1)
        for product in HOTSPOT_PRODUCTS:
            path = store.base / ("wa/observations" if scope == "wa" else "observations") / (product if scope == "wa" else f"{product}.parquet")
            if not path.exists():
                continue
            expression = (ds.field("acq_datetime") >= first.to_datetime64()) & (ds.field("acq_datetime") < stop.to_datetime64())
            if bbox is not None:
                west, south, east, north = bbox
                expression &= (ds.field("longitude") >= west) & (ds.field("longitude") <= east)
                expression &= (ds.field("latitude") >= south) & (ds.field("latitude") <= north)
            try:
                columns = PRODUCT_COLUMNS + (["country"] if scope == "wa" else [])
                frame = ds.dataset(path).to_table(columns=columns, filter=expression).to_pandas()
            except Exception as exc:  # being rewritten: retryable
                raise HTTPException(503, "Detections could not be read; they may be updating. Retry in a moment.") from exc
            parts.append(frame)
        if not parts:
            raise HTTPException(501, "Individual hotspot downloads are not included in this copy of TerraGuard for this area. "
                                     "Run TerraGuard yourself with the downloaded NASA data (see the README) to export them.")
        frame = pd.concat(parts, ignore_index=True)
        frame = frame[frame["sensor"].isin(SENSOR_FILTER[sensor])]
        if sensor == "steady":  # only the satellites that observed for the whole record
            frame = frame[frame["platform"].isin(STABLE_PLATFORMS)]
        if frame.empty:
            frame["region"] = pd.Series(dtype=str)
            return frame
        if scope == "wa":
            frame = frame.rename(columns={"country": "region"})
            if bbox is None and region != helpers["national_name"]("wa"):
                frame = frame[frame["region"] == region]
            return frame.sort_values("acq_datetime").reset_index(drop=True)
        lon, lat = frame["longitude"].to_numpy(), frame["latitude"].to_numpy()
        inside = regions().inside_country(lon, lat)
        frame = frame[inside].copy()
        frame["region"] = regions().region_for(frame["longitude"].to_numpy(), frame["latitude"].to_numpy())
        if bbox is None and region != "Ghana":
            frame = frame[frame["region"] == region]
        return frame.sort_values("acq_datetime").reset_index(drop=True)

    def hotspot_period(start: date, end: date) -> tuple[pd.Timestamp, pd.Timestamp]:
        if end < start:
            raise HTTPException(422, "end must not be earlier than start")
        return pd.Timestamp(start), pd.Timestamp(end)

    @app.get("/api/hotspots/preview")
    def hotspots_preview(start: date, end: date, region: str = "Ghana", sensor: str = "harmonized",
                         bbox: str | None = None) -> dict[str, Any]:
        """How many detections a download would contain, before the user asks for them."""
        if sensor not in SENSOR_FILTER:
            raise HTTPException(422, f"sensor must be one of {sorted(SENSOR_FILTER)}")
        first, last = hotspot_period(start, end)
        frame = read_hotspots(first, last, region, bbox, sensor)
        by_sensor = frame["sensor"].value_counts().to_dict()
        return {"rows": int(len(frame)), "limit": MAX_HOTSPOT_ROWS, "too_large": bool(len(frame) > MAX_HOTSPOT_ROWS),
                "by_sensor": {str(k): int(v) for k, v in by_sensor.items()}}

    @app.get("/api/export/hotspots.csv")
    def export_hotspots(start: date, end: date, region: str = "Ghana", sensor: str = "harmonized",
                        bbox: str | None = None) -> Response:
        """One row per satellite detection (MODIS: Terra/Aqua, VIIRS: Suomi-NPP) in the area and dates."""
        if sensor not in SENSOR_FILTER:
            raise HTTPException(422, f"sensor must be one of {sorted(SENSOR_FILTER)}")
        first, last = hotspot_period(start, end)
        frame = read_hotspots(first, last, region, bbox, sensor)
        if len(frame) > MAX_HOTSPOT_ROWS:
            raise HTTPException(422, f"{len(frame):,} detections match, above the {MAX_HOTSPOT_ROWS:,} download limit. "
                                     "Choose a shorter period or a smaller area.")
        out = frame.rename(columns={"acq_datetime": "datetime_utc", "frp": "frp_mw", "satellite": "satellite_name"})
        out = out[["datetime_utc", "latitude", "longitude", "sensor", "satellite_name", "confidence",
                   "confidence_class", "frp_mw", "daynight", "region", "source_product"]]
        area = f"custom bounding box (west,south,east,north) {bbox}" if bbox else region
        lines = [
            "# TerraGuard hotspot export",
            "# source: NASA FIRMS standard-processing / near-real-time MODIS and VIIRS active-fire detections",
            "# each row is one satellite thermal-anomaly detection, not a confirmed or unique fire",
            "# confidence is the sensor's own scale (MODIS 0-100, VIIRS low/nominal/high); not comparable across sensors",
            "# software: TerraGuard, developed with AI-tool assistance (Claude Code); see README, section 'Built with AI assistance'",
            f"# area: {area}", f"# sensor view: {sensor}", f"# period: {first.date()} to {last.date()} (UTC)",
            f"# satellites: {'Terra, Aqua, Suomi-NPP only (steady set)' if sensor == 'steady' else 'all (Terra, Aqua, Suomi-NPP, NOAA-20, NOAA-21)'}", f"# rows: {len(out)}",
        ]
        buffer = io.StringIO()
        out.to_csv(buffer, index=False)
        label = "custom" if bbox else region.replace(" ", "_")
        return Response("\n".join(lines) + "\n" + buffer.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="terraguard_hotspots_{label}_{first.date()}_{last.date()}.csv"'})

    # ---- current period vs previous years ----

    def archive_end(product: str, scope: str = "ghana") -> pd.Timestamp:
        info = store.json("wa/metadata.json" if scope == "wa" else "metadata.json").get("products", {}).get(product)
        if not info or not info.get("covered_ranges"):
            raise HTTPException(503, f"No coverage information for {product}")
        return pd.Timestamp(info["covered_ranges"][-1][1])

    @app.get("/api/current-comparison")
    def current_comparison(
        grid: str = "5km", region: str = "Ghana", sensor: str = "harmonized", bbox: str | None = None,
        window_days: int = Query(DEFAULT_WINDOW_DAYS, ge=7, le=90),
        mode: str = Query("days", pattern="^(days|month)$"),
    ) -> dict[str, Any]:
        """The latest ``window_days`` of data against the same calendar dates in every earlier year."""
        if sensor not in SENSOR_FILTER:
            raise HTTPException(422, f"sensor must be one of {sorted(SENSOR_FILTER)}")
        if grid not in ("1km", "2km", "5km"):
            raise HTTPException(422, "grid must be 1km, 2km or 5km")
        parsed = helpers["parsed_bbox"](bbox)
        scope = helpers["scope_for"](region, bbox)
        helpers["check_grid"](grid, scope)
        if parsed is None:
            helpers["check_region"](grid, region, scope)
        km = {"1km": 1.0, "2km": 2.0, "5km": 5.0}[grid]
        ends = {"modis": archive_end("MODIS_SP", scope), "viirs": archive_end("VIIRS_SNPP_SP", scope)}
        as_of = min(ends.values()) if sensor in ("harmonized", "steady") else ends[sensor]
        window_end = as_of
        month_note = ""
        if mode == "month":  # the current month so far, against the same dates in every earlier year
            window_start = as_of.normalize().replace(day=1)
            if (as_of.normalize() - window_start).days < 6:
                # Under a week of the new month: too little to compare, so use the last full month instead.
                window_end = window_start - pd.Timedelta(days=1)
                window_start = window_end.replace(day=1)
                month_note = "The new month has under a week of data, so the last full month is compared instead. "
            window_days = int((window_end.normalize() - window_start).days) + 1
        else:
            window_start = as_of - pd.Timedelta(days=window_days - 1)
        bounds = []
        for year in range(2002, window_end.year + 1):
            offset = window_end.year - year
            first = window_start - pd.DateOffset(years=offset)
            last = window_end - pd.DateOffset(years=offset)
            if first >= AQUA_FIRST_FULL_MONTH:
                bounds.append((year, first, last))
        # Read only the dates being compared (about 25 windows), not the whole table: the server has little memory.
        table = helpers["read_cell_days"](
            grid, scope, region=None if parsed else region, bbox=parsed, ranges=[(f, l) for _, f, l in bounds],
            columns=["date", "grid_x", "grid_y", "region", "modis_detections", "viirs_detections", "viirs_steady_detections"],
        )
        selected = select_cells(table, km, region=None if parsed else region, bbox=parsed, national=helpers["national_name"](scope))
        viirs_steady = selected["viirs_steady_detections"] if "viirs_steady_detections" in selected else selected["viirs_detections"]
        steady_flag = ((selected["modis_detections"] > 0) | (viirs_steady > 0)).to_numpy()
        # Like for like: the combined view is compared on the steady set (Terra, Aqua, Suomi-NPP), so the satellites that
        # joined in 2018 and 2023 cannot make the present look busier than the past. The all-satellite count is reported too.
        flag = {"harmonized": steady_flag,
                "steady": steady_flag,
                "modis": (selected["modis_detections"] > 0).to_numpy(),
                "viirs": (viirs_steady > 0).to_numpy()}[sensor]  # VIIRS alone: Suomi-NPP, present for the whole record
        daily = selected.loc[flag].groupby("date").size()
        daily_all = selected.groupby("date").size()
        calendar = helpers["calendar_frame"](grid, region, sensor, bbox)
        ratio = calendar.assign(r=np.where(calendar["observed_cell_days"] > 0,
                                           calendar["active_cell_days"] / calendar["observed_cell_days"].clip(lower=1), 1.0)
                                ).set_index(["year", "month"])["r"] if "observed_cell_days" in calendar else None
        history, current = [], None
        for year, first, last in bounds:
            value = float(daily[(daily.index >= first) & (daily.index <= last)].sum())
            estimated = False
            if sensor in ("harmonized", "steady") and ratio is not None and year < 2012:
                value *= float(ratio.get((last.year, last.month), 1.0))
                estimated = True
            row = {"year": year, "value": round(value), "estimated": estimated,
                   "window_start": first.date().isoformat(), "window_end": last.date().isoformat()}
            if year == window_end.year:
                row["all_satellites_value"] = int(daily_all[(daily_all.index >= first) & (daily_all.index <= last)].sum())
                current = row
            else:
                history.append(row)
        if current is None or not history:
            raise HTTPException(422, "Not enough history to compare")
        values = np.array([h["value"] for h in history], float)
        median = float(np.median(values))
        rank = int((values > current["value"]).sum()) + 1
        return {
            "as_of": as_of.date().isoformat(), "window_days": window_days, "mode": mode, "basis": "steady set" if sensor in ("harmonized", "steady") else "sensor view", "window_label": ("The last full month" if month_note else "This month so far") if mode == "month" else None, "area": helpers["area_label"](region, bbox),
            "sensor": sensor, "grid": grid, "current": current, "history": history,
            "median": round(median), "pct_diff_from_median": None if median == 0 else round((current["value"] / median - 1) * 100, 1),
            "rank_among_years": rank, "years_compared": len(history) + 1,
            "percentile": round(float((values < current["value"]).mean() * 100), 1),
            "note": (month_note + "Active cell-days in the latest window against the same calendar dates in earlier years" + (", counted on the steady set (Terra, Aqua, Suomi-NPP) so satellites that joined later do not inflate the present. " if sensor in ("harmonized", "steady") else ". ") + " "
                     "Recent days come from near-real-time data and may be revised. "
                     + ("Years before 2012 had MODIS only; they are scaled to the combined scale with that month's bridge ratio, "
                        "an approximation." if sensor == "harmonized" else "")).strip(),
        }
