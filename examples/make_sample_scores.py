"""Generate a proper worked-example dataset plus its expected output.

CPC requires, verbatim, "sample input and output data for at least one
comprehensive test run that will convince the reviewers that the program
operates as specified".

The original examples/data/scores.csv held 8 values, was excluded from the
repository by a bare 'data/' gitignore rule, and could not exercise a passing
certification.  This script generates a deterministic sample that does.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "examples" / "data"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 20260912


def main() -> int:
    rng = np.random.default_rng(SEED)

    # A score in [0,1): a smoothly falling tail so that a range of thresholds is
    # attainable, with a small high-score population that a 0.5 % target can bite on.
    n = 8000
    bulk = rng.beta(2.0, 5.0, size=n)
    tail = rng.beta(8.0, 2.0, size=n) * 0.999 + 0.001
    scores = np.clip(np.concatenate([bulk, tail]), 0.0, 0.9999)
    rng.shuffle(scores)

    path = OUT / "scores.csv"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        # No header: load_scores() reads a one-column numeric CSV and rejects
        # non-numeric rows, so a header line would be a hard input error.
        for v in scores:
            fh.write("%.6f\n" % v)

    print("wrote %s  (%d rows, %d bytes)" % (path, scores.size, path.stat().st_size))
    print("  min=%.6f max=%.6f mean=%.6f" % (scores.min(), scores.max(), scores.mean()))
    print("  frac above 0.99 = %.5f" % float((scores > 0.99).mean()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
