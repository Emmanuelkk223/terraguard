"""Resumable bulk FIRMS download of standard-processing products.

Wraps ``acquire.download_historical_area`` one 5-day window at a time, with
retry/backoff and throttling. Already-downloaded windows are skipped, so the
script can be re-run safely after any interruption. Raw files are never
modified.
"""

from __future__ import annotations

import argparse
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.request import urlopen

from data_pipeline.acquire import DEFAULT_AREA, download_historical_area

# First date each standard product is available (from the FIRMS
# data_availability endpoint, checked 2026-11-14). Re-check before relying on it.
PRODUCT_START = {
    "MODIS_SP": date(2012, 1, 1),  # archive starts 2000-11; we use the overlap era
    "VIIRS_SNPP_SP": date(2012, 1, 20),
    "VIIRS_NOAA20_SP": date(2018, 4, 1),
    "VIIRS_NOAA21_SP": date(2023, 3, 1),
}
WINDOW_DAYS = 5


STATUS_URL = "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={key}"


def quota_used(map_key: str) -> tuple[int, int] | None:
    """Return (used, limit) transactions for the current interval, or None."""
    try:
        with urlopen(STATUS_URL.format(key=map_key), timeout=30) as response:
            body = response.read().decode("utf-8", "replace")
        limit = int(re.search(r'"transaction_limit"\s*:\s*(\d+)', body).group(1))
        used = int(re.search(r'"current_transactions"\s*:\s*(\d+)', body).group(1))
        return used, limit
    except (OSError, AttributeError, ValueError):
        return None


def wait_for_quota(map_key: str, *, max_fraction: float = 0.8) -> None:
    """Block while the key's 10-minute transaction budget is nearly spent.

    FIRMS answers over-limit requests with HTTP 400 'Invalid MAP_KEY', which
    looks like a bad request, so we check the counter instead of failing.
    """
    while True:
        status = quota_used(map_key)
        if status is None or status[0] < status[1] * max_fraction:
            return
        print(f"quota {status[0]}/{status[1]}; waiting for reset", flush=True)
        time.sleep(30)


def download_product(
    source: str,
    start: date,
    end: date,
    *,
    map_key: str,
    area: str,
    output_dir: Path,
    retries: int = 5,
    pause: float = 0.3,
) -> tuple[int, int]:
    """Download one product; return (windows_done, windows_failed)."""
    done = failed = 0
    current = start
    while current <= end:
        window_end = min(current + timedelta(days=WINDOW_DAYS - 1), end)
        if (done + failed) % 10 == 0:
            wait_for_quota(map_key)
        for attempt in range(1, retries + 1):
            try:
                download_historical_area(
                    map_key=map_key, source=source, area=area,
                    start_date=current, end_date=window_end,
                    days=WINDOW_DAYS, output_dir=output_dir,
                )
                done += 1
                break
            except RuntimeError as exc:
                if attempt == retries:
                    failed += 1
                    print(f"FAILED {source} {current}..{window_end}: {exc}", flush=True)
                else:
                    wait_for_quota(map_key)
                    time.sleep(min(60, 2**attempt))
        time.sleep(pause)
        if done and done % 100 == 0:
            print(f"{source}: {done} windows through {window_end}", flush=True)
        current = window_end + timedelta(days=1)
    return done, failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", default=list(PRODUCT_START))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--area", default=DEFAULT_AREA)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/firms"))
    args = parser.parse_args()
    map_key = os.environ.get("FIRMS_MAP_KEY")
    if not map_key:
        raise SystemExit("FIRMS_MAP_KEY is required (set it in your environment).")
    for source in args.sources:
        if source not in PRODUCT_START:
            raise SystemExit(f"Unknown source {source}; choose from {list(PRODUCT_START)}")
        done, failed = download_product(
            source, PRODUCT_START[source], args.end,
            map_key=map_key, area=args.area, output_dir=args.output_dir,
        )
        print(f"{source}: complete, {done} windows ok, {failed} failed", flush=True)


if __name__ == "__main__":
    main()
