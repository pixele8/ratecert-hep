"""Small, dependency-light input/output helpers for RateCert-HEP."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np


def load_scores(path: str | Path) -> np.ndarray:
    """Load a one-dimensional score stream from ``.npy`` or a one-column CSV."""

    source = Path(path)
    if source.suffix.lower() == ".npy":
        values = np.load(source, allow_pickle=False)
    else:
        with source.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        if not rows:
            raise ValueError("score file is empty")
        if any(len(row) != 1 for row in rows if row):
            raise ValueError("CSV score file must contain exactly one column")
        try:
            values = np.asarray([float(row[0]) for row in rows if row], dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("CSV score file must contain numeric values in its first column") from exc
    values = np.asarray(values, dtype=float)
    if values.ndim != 1:
        raise ValueError("score input must be one-dimensional")
    return values


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    """Write a JSON report with LF line endings on every platform.

    ``Path.write_text`` translates "\\n" to the platform line separator, so the
    same command produced different bytes on Windows and Linux.  That made
    checked-in reports non-reproducible: a reviewer on either platform would see
    spurious drift, and the committed evidence files ended up with mixed
    endings.  Writing explicitly with newline="\\n" fixes the bytes and keeps a
    regenerated report byte-identical to the committed one.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, allow_nan=False)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("configuration JSON must contain an object")
    return payload
