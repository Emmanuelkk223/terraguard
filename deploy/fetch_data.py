"""Download and unpack the data bundle (see make_bundle.py) into /app, streaming so memory stays small.

    DATA_URL=https://.../terraguard-data.tar.gz python deploy/fetch_data.py

Does nothing if the data is already there or DATA_URL is not set.
"""

from __future__ import annotations

import os
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("TERRAGUARD_ROOT", Path(__file__).resolve().parents[1]))
MARKER = ROOT / "data" / "processed" / "analytics" / "calendar_5km.csv"


def main() -> int:
    url = os.environ.get("DATA_URL", "").strip()
    if MARKER.is_file():
        print("data already present")
        return 0
    if not url:
        print("DATA_URL is not set: starting without data (the site will say so)", file=sys.stderr)
        return 0
    print("downloading the data bundle ...", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "terraguard-deploy"})
    with urllib.request.urlopen(request, timeout=300) as response, tarfile.open(fileobj=response, mode="r|gz") as archive:
        archive.extractall(ROOT, filter="data")
    print("data ready", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
