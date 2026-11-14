"""Summary report for a selected area, sensor view and (optionally) period.

A report is a list of simple blocks that render to Markdown and to self-contained, printable HTML
(use the browser's Print > Save as PDF). Everything in it is read from the generated analytics; nothing is
invented, and the limits of the data are stated in the report itself.
"""

from __future__ import annotations

import calendar as _calendar
from datetime import datetime, timezone
from html import escape

import pandas as pd

from .calendar_analytics import annual_summary, seasonal_summary
from .sensitivity import burning_season

Block = tuple

SENSOR_TEXT = {"harmonized": "both sensors (harmonized: a cell-day counts once if either sensor detected activity)",
               "modis": "MODIS only (Terra and Aqua)", "viirs": "VIIRS only (Suomi-NPP)"}
LIMITATIONS = [
    "A detection is a satellite-observed thermal anomaly, not a confirmed or unique fire; other heat sources can appear.",
    "Active cell-days count (day, grid cell) pairs with a detection. They depend on the grid size and are not burned area.",
    "MODIS and VIIRS are not made equivalent by a common grid; VIIRS detects far more, and the sensors flag the same cell-day only rarely.",
    "FRP and confidence are not calibrated between sensors, and orbit drift in Terra and Aqua can create apparent MODIS trends.",
    "A day with no detections is ambiguous (no fire, no overpass, cloud or missing data). Months are complete only when the data archive covers them.",
    "Unusual months describe history against the same month in other years. They are not forecasts or alerts; no ground truth exists, "
    "so accuracy is not reported. Flag thresholds are calibrated for about 1% false flags on ordinary months and assume Gaussian noise on a log scale.",
]


def _n(value: float | int | None, digits: int = 0) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "–"
    return f"{value:,.{digits}f}"


def build_blocks(
    calendar: pd.DataFrame, *, area: str, sensor: str, grid: str, meta: dict | None = None,
    period: tuple[str, str] | None = None, period_series: pd.DataFrame | None = None,
    quality: dict | None = None, generated: datetime | None = None,
) -> list[Block]:
    generated = generated or datetime.now(timezone.utc)
    complete = calendar[calendar["coverage_ok"]]
    blocks: list[Block] = [
        ("h1", "TerraGuard summary report"),
        ("p", f"**Area:** {area} · **Sensor view:** {SENSOR_TEXT.get(sensor, sensor)} · **Grid:** {grid} · "
              f"**Generated:** {generated:%Y-%m-%d %H:%M} UTC"),
        ("note", "Satellite detections are not unique fires and this is not an emergency alert or a prediction. "
                 "It describes historical satellite-detected activity."),
    ]
    if complete.empty:
        blocks.append(("p", "There are no months with full satellite record coverage for this selection."))
        return blocks + _closing(meta, quality)

    first, last = complete.iloc[0], complete.iloc[-1]
    total = complete["active_cell_days"].sum()
    peak = complete.loc[complete["active_cell_days"].idxmax()]
    annual = annual_summary(calendar)
    full_years = annual[annual["complete_year"]]
    headline: list[list[str]] = [
        ["Period with full coverage", f"{first['year']}-{int(first['month']):02d} to {last['year']}-{int(last['month']):02d} ({len(complete)} months)"],
        ["Total active cell-days", _n(total)],
        ["Average per month", _n(total / len(complete))],
        ["Busiest month", f"{_calendar.month_name[int(peak['month'])]} {int(peak['year'])} ({_n(peak['active_cell_days'])})"],
    ]
    if not full_years.empty:
        top = full_years.loc[full_years["active_cell_days"].idxmax()]
        low = full_years.loc[full_years["active_cell_days"].idxmin()]
        headline += [["Busiest complete year", f"{int(top['year'])} ({_n(top['active_cell_days'])})"],
                     ["Quietest complete year", f"{int(low['year'])} ({_n(low['active_cell_days'])})"]]
    if total:
        headline.append(["Cell-days seen by both sensors", f"{complete['both_cell_days'].sum() / total:.0%} of all active cell-days"])
    blocks += [("h2", "Headline figures"), ("table", ["Measure", "Value"], headline)]

    if period and period_series is not None and len(period_series):
        blocks += [
            ("h2", f"Selected period: {period[0]} to {period[1]}"),
            ("table", ["Measure", "Value"], [
                ["Days in period", str(len(pd.date_range(period[0], period[1])))],
                ["Active cell-days", _n(period_series["value"].sum())],
                ["MODIS cell-days", _n(period_series["modis_cell_days"].sum())],
                ["VIIRS cell-days", _n(period_series["viirs_cell_days"].sum())],
                ["Seen by both", _n(period_series["both_cell_days"].sum())],
                ["Busiest day or week (start date)", f"{period_series.loc[period_series['value'].idxmax(), 'period_start']} "
                                        f"({_n(period_series['value'].max())})"],
            ]),
            ("p", "Historical comparison is made month against the same calendar month in other years, so a custom period has none."),
        ]

    seasonal = seasonal_summary(calendar)
    season = burning_season(seasonal) if not seasonal.empty else None
    if season:
        blocks += [
            ("h2", "Seasonal pattern"),
            ("p", f"Burning season (months with a median of at least 25% of the busiest month): **{season['label']}**, peaking in "
                  f"**{_calendar.month_name[season['peak_month']]}**; these months hold {season['share_of_year']:.0%} of a typical year's activity."),
            ("table", ["Month", "Median", "Minimum (year)", "Maximum (year)", "Years"],
             [[_calendar.month_abbr[int(r.month)], _n(r.median), f"{_n(r.min)} ({int(r.min_year)})", f"{_n(r.max)} ({int(r.max_year)})", str(int(r.n_years))]
              for r in seasonal.itertuples()]),
        ]

    blocks += [("h2", "Annual totals"), ("table", ["Year", "Active cell-days", "MODIS cell-days", "VIIRS cell-days", "Coverage"],
               [[str(int(r.year)), _n(r.active_cell_days), _n(r.modis_cell_days), _n(r.viirs_cell_days),
                 "complete year" if r.complete_year else f"partial ({int(r.months_with_coverage)}/12 months)"]
                for r in annual.itertuples()])]

    flagged = calendar[calendar["status"].isin(["unusually_high", "unusually_low"])]
    flagged = flagged.reindex(flagged["robust_score"].abs().sort_values(ascending=False).index)
    blocks.append(("h2", "Unusual months"))
    if flagged.empty:
        blocks.append(("p", "No month is statistically unusual against the same month in other years under the calibrated threshold."))
    else:
        has_corr = "modis_status" in flagged and "viirs_status" in flagged
        headers = ["Month", "Active cell-days", "Median", "Change", "Score (limit)"] + (["Also unusual in"] if has_corr else [])
        rows = []
        for r in flagged.itertuples():
            row = [f"{_calendar.month_abbr[int(r.month)]} {int(r.year)}", _n(r.active_cell_days), _n(r.baseline_median),
                   f"{r.pct_diff:+.0f}%", f"{r.robust_score:+.1f} (±{r.threshold:.1f})"]
            if has_corr:
                seen = [n for n, s in (("MODIS", r.modis_status), ("VIIRS", r.viirs_status)) if s in ("unusually_high", "unusually_low")]
                row.append("both sensors" if len(seen) == 2 else (f"{seen[0]} only" if seen else "neither alone"))
            rows.append(row)
        blocks += [("table", headers, rows), ("h3", "Why each month was flagged"),
                   ("ul", [f"**{_calendar.month_abbr[int(r.month)]} {int(r.year)}:** {r.explanation}" for r in flagged.itertuples()])]
    return blocks + _closing(meta, quality)


def _closing(meta: dict | None, quality: dict | None) -> list[Block]:
    blocks: list[Block] = []
    if quality:
        cov = quality.get("coverage", {})
        incomplete = ", ".join(cov.get("incomplete_months", [])) or "none"
        blocks += [("h2", "Data quality"), ("ul", [
            f"Months with complete data-archive coverage (national): {cov.get('months_complete', '–')} of {cov.get('months_total', '–')}; incomplete: {incomplete}.",
            f"Detections used after the Ghana clip: {_n(quality.get('harmonization', {}).get('observations_used'))}; "
            f"excluded as outside Ghana: {_n(quality.get('harmonization', {}).get('observations_outside_ghana_excluded'))}.",
            "Records removed as invalid or duplicate: " + _n(sum(sum((p.get("exclusions_by_reason") or {}).values()) for p in quality.get("products", {}).values())) + ".",
            "Missing values in required fields: " + _n(sum(sum((p.get("missing_values") or {}).values()) for p in quality.get("products", {}).values())) + ".",
        ])]
    blocks += [("h2", "Limitations"), ("ul", LIMITATIONS), ("h2", "Provenance")]
    harmonization = (meta or {}).get("harmonization", meta or {})
    blocks.append(("ul", [
        "Source: NASA FIRMS standard-processing MODIS and VIIRS (375 m) active-fire detections, 2012-2025.",
        f"Method: {harmonization.get('harmonization_method', 'n/a')} (version {harmonization.get('harmonization_version', 'n/a')}); platforms: "
        f"{', '.join(harmonization['platforms']) if isinstance(harmonization.get('platforms'), list) else harmonization.get('platforms', 'n/a')}.",
        "Boundaries: geoBoundaries ADM1 (CC BY-SA 2.0), simplified; region totals near borders are approximate.",
    ]))
    return blocks


# ---- renderers ----

def _md_inline(text: str) -> str:
    return text


def to_markdown(blocks: list[Block]) -> str:
    out: list[str] = []
    for block in blocks:
        kind = block[0]
        if kind in ("h1", "h2", "h3"):
            out.append(f"{'#' * int(kind[1])} {block[1]}")
        elif kind in ("p", "note"):
            out.append(("> " if kind == "note" else "") + block[1])
        elif kind == "ul":
            out.append("\n".join(f"- {item}" for item in block[1]))
        elif kind == "table":
            headers, rows = block[1], block[2]
            out.append("\n".join(["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
                                 + ["| " + " | ".join(str(c).replace("|", "/") for c in row) + " |" for row in rows]))
    return "\n\n".join(out) + "\n"


def _html_inline(text: str) -> str:
    """Escape, then turn **bold** into <strong>."""
    parts = escape(text).split("**")
    return "".join(f"<strong>{p}</strong>" if i % 2 else p for i, p in enumerate(parts))


def to_html(blocks: list[Block], title: str = "TerraGuard summary report") -> str:
    body: list[str] = []
    for block in blocks:
        kind = block[0]
        if kind in ("h1", "h2", "h3"):
            body.append(f"<{kind}>{_html_inline(block[1])}</{kind}>")
        elif kind == "p":
            body.append(f"<p>{_html_inline(block[1])}</p>")
        elif kind == "note":
            body.append(f'<p class="note">{_html_inline(block[1])}</p>')
        elif kind == "ul":
            body.append("<ul>" + "".join(f"<li>{_html_inline(i)}</li>" for i in block[1]) + "</ul>")
        elif kind == "table":
            head = "".join(f"<th>{escape(h)}</th>" for h in block[1])
            rows = "".join("<tr>" + "".join(f"<td>{_html_inline(str(c))}</td>" for c in row) + "</tr>" for row in block[2])
            body.append(f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
  body {{ font: 14px/1.5 "Segoe UI", system-ui, sans-serif; color: #17202b; max-width: 920px; margin: 28px auto; padding: 0 18px; }}
  h1 {{ font-size: 26px; border-bottom: 4px solid #ea7a2b; padding-bottom: 6px; margin-bottom: 8px; }}
  h2 {{ font-size: 16px; text-transform: uppercase; letter-spacing: .08em; color: #8a4a12; margin: 28px 0 8px; }}
  h3 {{ font-size: 14px; margin: 18px 0 6px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0 14px; font-size: 13px; }}
  th, td {{ border: 1px solid #c9d2dc; padding: 5px 9px; text-align: left; vertical-align: top; }}
  th {{ background: #eef2f6; }}
  .note {{ background: #fff6e6; border-left: 4px solid #ea7a2b; padding: 8px 12px; }}
  li {{ margin: 3px 0; }}
  @media print {{ body {{ margin: 0; max-width: none; }} h2 {{ break-after: avoid; }} table, li {{ break-inside: avoid; }} }}
</style></head><body>
{chr(10).join(body)}
</body></html>
"""
