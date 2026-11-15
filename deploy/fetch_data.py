"""Download and unpack the data bundle (see make_bundle.py) into /app, streaming so memory stays small.

    DATA_URL=https://github.com/<you>/terraguard/releases/download/data-v1/terraguard-data.tar.gz python deploy/fetch_data.py

Does nothing if the data is already there. Tries DATA_URL first, then the published release below, so a missing or mistyped setting cannot leave the site
empty. If an address does not lead straight to the archive, it says what it got instead.
"""

from __future__ import annotations

import io
import os
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("TERRAGUARD_ROOT", Path(__file__).resolve().parents[1]))
MARKER = ROOT / "data" / "processed" / "analytics" / "calendar_5km.csv"
GZIP_MAGIC = bytes([0x1F, 0x8B])
FALLBACK_URL = os.environ.get(
    "DATA_URL_FALLBACK", "https://github.com/Emmanuelkk223/terraguard/releases/download/data-v1/terraguard-data.tar.gz"
)


def explain(url: str, what: str) -> str:
    hints = []
    if "github.com" in url and "/releases/download/" not in url:
        hints.append("This is not a file address. On the release page, right-click the file terraguard-data.tar.gz under 'Assets' and copy that link "
                     "(it contains /releases/download/).")
    if "github.com" in url:
        hints.append("The repository must be public for anyone (including Render) to download a release file.")
    hints.append("Test the address in a private browser window: it should start downloading a file of about 300 MB straight away.")
    return f"The address did not return the data archive ({what}).\n  address = {url}\n  " + "\n  ".join(hints)


def fetch(url: str) -> bool:
    """Download and unpack one address; True on success."""
    print(f"downloading the data bundle from {url} ...", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "terraguard-deploy"})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            stream = io.BufferedReader(response, buffer_size=1 << 20)
            if stream.peek(2)[:2] != GZIP_MAGIC:
                body = stream.read(200).decode("utf-8", "replace").replace("\n", " ")
                print(explain(url, f"HTTP {response.status}, {response.headers.get('content-type', 'unknown type')}, starts with: {body[:120]!r}"), file=sys.stderr)
                return False
            with tarfile.open(fileobj=stream, mode="r|gz") as archive:
                archive.extractall(ROOT, filter="data")
    except urllib.error.HTTPError as error:
        print(explain(url, f"HTTP {error.code} {error.reason}"), file=sys.stderr)
        return False
    except (urllib.error.URLError, OSError, tarfile.TarError) as error:
        print(explain(url, f"{type(error).__name__}: {error}"), file=sys.stderr)
        return False
    print("data ready", flush=True)
    return True


def main() -> int:
    if MARKER.is_file():
        print("data already present")
        return 0
    configured = os.environ.get("DATA_URL", "").strip()
    if not configured:
        print("DATA_URL is not set; using the published data release", file=sys.stderr)
    addresses = [configured] if configured else []
    if FALLBACK_URL and FALLBACK_URL not in addresses:
        addresses.append(FALLBACK_URL)
    for url in addresses:
        if fetch(url):
            return 0
    print("No data could be downloaded: the site will start without data and say so.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
