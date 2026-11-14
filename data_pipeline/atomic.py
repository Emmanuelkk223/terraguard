"""Atomic file writes: readers only ever see a complete old file or a complete new file.

Every output is written to a temporary file in the same folder and then swapped into place with
``os.replace``. Without this, a reader (the API) can open a half-written parquet/CSV/JSON while the
pipeline is regenerating it, and a crash mid-write leaves a truncated file that later runs would
treat as valid (the resumable downloader skips files that already exist).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

import pandas as pd

REPLACE_ATTEMPTS = 8
REPLACE_PAUSE = 0.25  # seconds; on Windows a file that is open elsewhere briefly refuses to be replaced


def _replace(tmp: Path, path: Path) -> None:
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_PAUSE)


def _write(path: str | Path, writer: Callable[[Path], None]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        writer(tmp)
        _replace(tmp, path)
    finally:
        if tmp.exists():  # only left behind if the write or the swap failed
            tmp.unlink(missing_ok=True)
    return path


def write_bytes(path: str | Path, data: bytes) -> Path:
    return _write(path, lambda tmp: tmp.write_bytes(data))


def write_text(path: str | Path, text: str, encoding: str = "utf-8") -> Path:
    return _write(path, lambda tmp: tmp.write_text(text, encoding=encoding))


def to_csv(frame: pd.DataFrame, path: str | Path, **kwargs) -> Path:
    return _write(path, lambda tmp: frame.to_csv(tmp, **kwargs))


def to_parquet(frame: pd.DataFrame, path: str | Path, **kwargs) -> Path:
    return _write(path, lambda tmp: frame.to_parquet(tmp, **kwargs))
