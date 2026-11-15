"""All satellites by default, with a steady-set (Terra, Aqua, Suomi-NPP) view for like-for-like years (TEST DATA)."""

import pandas as pd

from data_pipeline.area_analytics import activity_series, area_calendar
from data_pipeline.harmonize import archive_coverage, harmonized_cell_days, monthly_summary, sensor_cell_days, select_observations

COVERED = {"MODIS_SP": [["2012-01-01", "2025-12-31"]], "VIIRS_SNPP_SP": [["2012-01-20", "2025-12-31"]],
           "VIIRS_NOAA20_SP": [["2018-04-01", "2025-12-31"]]}


def observations() -> pd.DataFrame:
    rows = []
    for year in range(2013, 2022):
        for month in (1, 2, 3):
            for i in range(4):
                lat = 7.0 + i * 0.2
                rows.append((lat, -1.0, f"{year}-{month:02d}-10 10:30", "MODIS", "Aqua", 1.0, "nominal", True))
                rows.append((lat, -1.0, f"{year}-{month:02d}-10 13:30", "VIIRS", "Suomi-NPP", 1.0, "nominal", True))
                if year >= 2018:  # NOAA-20 sees extra cells on other days from 2018
                    rows.append((lat + 0.5, -1.0, f"{year}-{month:02d}-12 13:50", "VIIRS", "NOAA-20", 1.0, "nominal", True))
    frame = pd.DataFrame(rows, columns=["latitude", "longitude", "acq_datetime", "sensor", "platform", "frp", "confidence_class", "is_presumed_vegetation_fire"])
    frame["acq_datetime"] = pd.to_datetime(frame["acq_datetime"])
    return frame


def test_each_cell_day_keeps_a_steady_set_count() -> None:
    cd = harmonized_cell_days(sensor_cell_days(observations(), 5.0))
    assert "viirs_steady_detections" in cd
    extra = cd[(cd["date"].dt.year >= 2018) & (cd["date"].dt.day == 12)]
    assert len(extra) and (extra["viirs_detections"] > 0).all() and (extra["viirs_steady_detections"] == 0).all()


def test_all_satellites_count_more_than_the_steady_set_only_after_they_join() -> None:
    cd = harmonized_cell_days(sensor_cell_days(observations(), 5.0))
    cd["region"] = "Ashanti"
    months = cd["date"].dt.to_period("M").dt.start_time
    monthly = monthly_summary(cd, archive=archive_coverage(months, COVERED, None))
    national = monthly[monthly["region"] == "Ghana"].assign(year=lambda d: pd.to_datetime(d["month"]).dt.year)
    before, after = national[national["year"] < 2018], national[national["year"] >= 2018]
    assert (before["active_cell_days"] == before["steady_cell_days"]).all()
    assert (after["active_cell_days"] > after["steady_cell_days"]).all()


def test_steady_view_matches_the_steady_set_and_all_view_does_not() -> None:
    cd = harmonized_cell_days(sensor_cell_days(observations(), 5.0))
    cd["region"] = "Ashanti"
    months = cd["date"].dt.to_period("M").dt.start_time
    monthly = monthly_summary(cd, archive=archive_coverage(months, COVERED, None))
    steady = area_calendar(cd, 5.0, monthly, view="steady")
    both = area_calendar(cd, 5.0, monthly, view="harmonized")
    row_s = steady[(steady["year"] == 2020) & (steady["month"] == 1)].iloc[0]
    row_a = both[(both["year"] == 2020) & (both["month"] == 1)].iloc[0]
    assert row_s["active_cell_days"] < row_a["active_cell_days"] and set(steady["view"]) == {"steady"}
    # the steady set is flat across 2018, when NOAA-20 joined; the all-satellite series steps up
    assert steady[steady["year"] == 2017]["active_cell_days"].mean() == steady[steady["year"] == 2019]["active_cell_days"].mean()
    assert both[both["year"] == 2019]["active_cell_days"].mean() > both[both["year"] == 2017]["active_cell_days"].mean()


def test_daily_series_offers_the_steady_view() -> None:
    cd = harmonized_cell_days(sensor_cell_days(observations(), 5.0))
    series = activity_series(cd, pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-31"), "day", view="steady")
    assert series["value"].sum() == series["steady_cell_days"].sum() < series["harmonized_cell_days"].sum()


def test_selecting_no_platform_filter_keeps_every_satellite() -> None:
    obs = observations()
    assert set(select_observations(obs, platforms=None)["platform"]) == {"Aqua", "Suomi-NPP", "NOAA-20"}


def test_satellites_joining_cannot_raise_a_false_alarm() -> None:
    cd = harmonized_cell_days(sensor_cell_days(observations(), 5.0))
    cd["region"] = "Ashanti"
    months = cd["date"].dt.to_period("M").dt.start_time
    monthly = monthly_summary(cd, archive=archive_coverage(months, COVERED, None))
    cal = area_calendar(cd, 5.0, monthly, view="harmonized")
    late = cal[cal["year"] >= 2018]
    assert (late["active_cell_days"] > late["scored_cell_days"]).all()           # every satellite is counted and shown
    assert not late["status"].isin(["unusually_high"]).any()                      # but the history comparison is like for like
    assert (cal["scored_cell_days"] == cal["steady_cell_days"]).all()
    assert "steady set" in late[late["status"] == "typical"].iloc[0]["explanation"]
