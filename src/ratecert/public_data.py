"""Small public-data adapter for the LHC Olympics 2020 R&D features.

The adapter deliberately returns a *background acceptance* sample.  The
dataset is a selected Pythia8/Delphes simulation and does not contain live
time or an input crossing flux, so an event count is never silently reported
as Hz.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from .core import FixedPointSpec


LHCO_ZENODO_RECORD = "https://zenodo.org/records/6466204"
LHCO_ZENODO_FILE = (
    "https://zenodo.org/api/records/6466204/files/"
    "events_anomalydetection_v2.features.h5/content"
)
LHCO_DOI = "10.5281/zenodo.6466204"
LHCO_LICENSE = "CC-BY-4.0"
LHCO_MD5 = "271cf5e71fc756b2a8d2b32730689bdb"


@dataclass(frozen=True)
class LHCOSplit:
    """Independent background calibration/deployment scores and provenance."""

    calibration_scores: np.ndarray
    deployment_scores: np.ndarray
    calibration_event_ids: np.ndarray
    deployment_event_ids: np.ndarray
    source_path: str
    source_sha256: str
    source_md5: str
    source_record: str
    source_doi: str
    source_license: str
    score_definition: str
    score_normalization: float
    n_total: int
    n_background: int
    n_signal: int
    split_seed: int
    source_selection: str
    split_rule: str = "seeded permutation without replacement"
    event_id_disjoint: bool = True
    independence_claim: str = (
        "declared by the recorded split; independence is a caller/data assumption, not proven by the adapter"
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "source_md5": self.source_md5,
            "source_record": self.source_record,
            "source_doi": self.source_doi,
            "source_license": self.source_license,
            "score_definition": self.score_definition,
            "score_normalization": self.score_normalization,
            "n_total": self.n_total,
            "n_background": self.n_background,
            "n_signal": self.n_signal,
            "split_seed": self.split_seed,
            "source_selection": self.source_selection,
            "split_rule": self.split_rule,
            "event_id_disjoint": self.event_id_disjoint,
            "independence_claim": self.independence_claim,
            "calibration_n": int(len(self.calibration_scores)),
            "deployment_n": int(len(self.deployment_scores)),
            "calibration_event_id_sha256": event_id_sha256(self.calibration_event_ids),
            "deployment_event_id_sha256": event_id_sha256(self.deployment_event_ids),
        }


def _file_hashes(path: Path) -> tuple[str, str]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest()


def event_id_sha256(values: np.ndarray) -> str:
    digest = hashlib.sha256()
    for value in np.asarray(values).astype(str):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _read_features(path: Path, limit: int | None = None):
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "the public LHCO adapter requires pandas and PyTables; install "
            "the [public-data] extra"
        ) from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    frame = pd.read_hdf(path, key="df")
    required = {"pxj1", "pyj1", "label"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"LHCO feature table is missing columns: {missing}")
    if limit is not None:
        if isinstance(limit, bool) or int(limit) != limit or limit < 1:
            raise ValueError("limit must be a positive integer")
        frame = frame.iloc[: int(limit)].copy()
    if len(frame) == 0:
        raise ValueError("LHCO feature table is empty")
    labels = np.asarray(frame["label"], dtype=float)
    if not np.all(np.isin(labels, [0.0, 1.0])):
        raise ValueError("LHCO labels must be binary 0/1")
    return frame, labels


def load_lhco_background_split(
    path: str | Path,
    *,
    calibration_n: int = 100_000,
    deployment_n: int = 100_000,
    seed: int = 20260912,
    score_normalization: float = 5000.0,
    limit: int | None = None,
) -> LHCOSplit:
    """Load deterministic, non-overlapping background score blocks.

    The trigger score is ``sqrt(pxj1**2 + pyj1**2) / score_normalization``.
    It is a transparent scalar high-level feature, not a learned model.  The
    default 5 TeV normalization keeps the released background below one and
    is recorded in the returned provenance object.
    """

    if isinstance(calibration_n, bool) or int(calibration_n) != calibration_n or calibration_n < 1:
        raise ValueError("calibration_n must be a positive integer")
    if isinstance(deployment_n, bool) or int(deployment_n) != deployment_n or deployment_n < 1:
        raise ValueError("deployment_n must be a positive integer")
    if not np.isfinite(score_normalization) or score_normalization <= 0:
        raise ValueError("score_normalization must be finite and positive")
    frame, labels = _read_features(Path(path), limit=limit)
    background_idx = np.flatnonzero(labels == 0.0)
    need = int(calibration_n) + int(deployment_n)
    if len(background_idx) < need:
        raise ValueError(
            f"need {need} background events but table contains {len(background_idx)}"
        )
    rng = np.random.default_rng(seed)
    chosen = rng.permutation(background_idx)[:need]
    cal_idx = chosen[: int(calibration_n)]
    dep_idx = chosen[int(calibration_n) :]
    px = np.asarray(frame["pxj1"], dtype=float)
    py = np.asarray(frame["pyj1"], dtype=float)
    scores = np.hypot(px, py) / float(score_normalization)
    if not np.all(np.isfinite(scores)):
        raise ValueError("LHCO score derivation produced non-finite values")
    event_ids = np.asarray([f"lhco-rnd:{int(i)}" for i in range(len(frame))], dtype=str)
    calibration_event_ids = event_ids[cal_idx]
    deployment_event_ids = event_ids[dep_idx]
    if np.intersect1d(calibration_event_ids, deployment_event_ids).size:
        raise RuntimeError("calibration and deployment event IDs overlap")
    sha256, md5 = _file_hashes(Path(path))
    return LHCOSplit(
        calibration_scores=scores[cal_idx],
        deployment_scores=scores[dep_idx],
        calibration_event_ids=calibration_event_ids,
        deployment_event_ids=deployment_event_ids,
        # Record the path as supplied, NOT .resolve().  Resolving bakes the
        # author's absolute filesystem layout into the published provenance
        # (e.g. "E:\\123\\ratecert_hep\\data\\..."), which is both a needless
        # disclosure and useless to a reader on another machine.  The
        # authoritative identifiers are the SHA-256/MD5 hashes and the DOI;
        # the path is a human-readable locality hint and is kept relative when
        # the caller supplied a relative path.
        source_path=str(path),
        source_sha256=sha256,
        source_md5=md5,
        source_record=LHCO_ZENODO_RECORD,
        source_doi=LHCO_DOI,
        source_license=LHCO_LICENSE,
        score_definition=(
            "leading-jet pT = hypot(pxj1, pyj1), divided by "
            f"{float(score_normalization):g} GeV"
        ),
        score_normalization=float(score_normalization),
        n_total=int(len(frame)),
        n_background=int(len(background_idx)),
        n_signal=int(np.count_nonzero(labels == 1.0)),
        split_seed=int(seed),
        source_selection="label == 0 (QCD background); released sample already has pT-trigger selection",
    )


def fixed_point_for_lhco(bits: int) -> FixedPointSpec:
    """Return the unsigned score format used by the public-data example."""

    if isinstance(bits, bool) or int(bits) != bits or not 2 <= int(bits) <= 16:
        raise ValueError("bits must be an integer in [2, 16]")
    return FixedPointSpec(bits=int(bits), fractional_bits=int(bits))
