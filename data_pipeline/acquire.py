"""Download FIRMS area data using an Earthdata-authenticated MAP_KEY."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import atomic

DEFAULT_SOURCE = "VIIRS_SNPP_NRT"
DEFAULT_AREA = "-3.26,4.74,1.20,11.17"
AREA_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/{area}/{days}"


def download_recent_area(
    *,
    map_key: str,
    source: str,
    area: str,
    days: int,
    output_dir: Path,
) -> list[Path]:
    """Download the latest FIRMS area observations.

    The area endpoint accepts a number of recent days, not arbitrary dates.
    Historical standard-quality data must be obtained through FIRMS Archive
    Download instead.
    """
    if not map_key.strip():
        raise ValueError("map_key must not be empty")
    if not 1 <= days <= 5:
        raise ValueError("days must be between 1 and 5 for the area endpoint")
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(output_dir.glob(f"{source}_recent_{days}d_*.csv"))
    if existing:
        return [existing[-1]]
    url = AREA_URL.format(map_key=map_key, source=source, area=area, days=days)
    request = Request(url, headers={"User-Agent": "TerraGuard-data-pipeline/1.0"})
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read()
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"FIRMS recent-area download failed for {source}: {exc}") from exc
    if not body.strip() or body.lstrip().startswith(b"<"):
        raise RuntimeError(f"FIRMS returned no CSV data for recent {source} area request")
    retrieved = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"{source}_recent_{days}d_{retrieved}.csv"
    atomic.write_bytes(output_path, body)
    return [output_path]


def download_historical_area(
    *,
    map_key: str,
    source: str,
    area: str,
    start_date: date,
    end_date: date,
    days: int,
    output_dir: Path,
) -> list[Path]:
    """Download dated FIRMS area API windows for standard-processing products."""
    if end_date < start_date:
        raise ValueError("end_date must not be earlier than start_date")
    if not 1 <= days <= 5:
        raise ValueError("days must be between 1 and 5 for the area endpoint")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    current = start_date
    while current <= end_date:
        window_end = min(current + timedelta(days=days - 1), end_date)
        stem = f"{source}_{current}_{window_end}"
        existing = sorted(output_dir.glob(f"{stem}.csv"))
        if existing:
            paths.append(existing[0])
            current = window_end + timedelta(days=1)
            continue
        url = (
            AREA_URL.format(
                map_key=map_key,
                source=source,
                area=area,
                days=(window_end - current).days + 1,
            )
            + f"/{current.isoformat()}"
        )
        request = Request(url, headers={"User-Agent": "TerraGuard-data-pipeline/1.0"})
        try:
            with urlopen(request, timeout=240) as response:  # a whole-region window is several MB
                body = response.read()
        except (HTTPError, URLError) as exc:
            raise RuntimeError(
                f"FIRMS historical download failed for {source} "
                f"{current} to {window_end}: {exc}"
            ) from exc
        if not body.strip() or body.lstrip().startswith(b"<"):
            raise RuntimeError(
                f"FIRMS returned no CSV data for {source} {current} to {window_end}"
            )
        output_path = output_dir / f"{stem}.csv"
        atomic.write_bytes(output_path, body)
        paths.append(output_path)
        current = window_end + timedelta(days=1)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--days", type=int, default=5)
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--area", default=DEFAULT_AREA)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    map_key = os.environ.get("FIRMS_MAP_KEY")
    if not map_key:
        raise SystemExit(
            "FIRMS_MAP_KEY is required. Obtain a NASA Earthdata/FIRMS MAP_KEY "
            "and set it as an environment variable; never place it in source control."
        )
    if (args.start is None) != (args.end is None):
        raise SystemExit("--start and --end must be provided together")
    if args.start is not None:
        paths = download_historical_area(
            map_key=map_key,
            source=args.source,
            area=args.area,
            start_date=args.start,
            end_date=args.end,
            days=args.days,
            output_dir=args.output_dir,
        )
    else:
        paths = download_recent_area(
            map_key=map_key,
            source=args.source,
            area=args.area,
            days=args.days,
            output_dir=args.output_dir,
        )
    print("\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
