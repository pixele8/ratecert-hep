"""Monte-Carlo stress test for the finite-sample binomial upper bound.

This is a diagnostic of implementation and numerical behavior, not a
replacement for the exact Clopper--Pearson coverage theorem.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import beta


def _write_text_lf(path, text: str) -> None:
    """Write text with LF line endings on every platform.

    Path.write_text would translate "\n" to os.linesep, so the same command
    produced CRLF on Windows and LF on Linux.  Checked-in reports must be
    byte-reproducible, and they must diff cleanly in git, so newline="\n" is
    forced explicitly here.
    """
    from pathlib import Path as _Path
    p = _Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _wilson(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    phat = successes / trials
    denom = 1.0 + z * z / trials
    centre = (phat + z * z / (2.0 * trials)) / denom
    radius = z * np.sqrt(phat * (1.0 - phat) / trials + z * z / (4.0 * trials * trials)) / denom
    return float(centre - radius), float(centre + radius)


def run(output_path: str | Path, *, repeats: int = 20_000, seed: int = 20260915) -> dict:
    if repeats < 100:
        raise ValueError("repeats must be at least 100")
    alpha = 0.00037037037037037
    scenarios = ((1_000, 0.005), (10_000, 0.005), (10_000, 0.01), (100_000, 0.01))
    rng = np.random.default_rng(seed)
    rows = []
    for n_events, true_acceptance in scenarios:
        counts = rng.binomial(n_events, true_acceptance, size=repeats)
        upper = beta.isf(alpha, counts + 1, n_events - counts)
        upper = np.asarray(upper, dtype=float)
        upper[counts == n_events] = 1.0
        covered = int(np.count_nonzero(upper >= true_acceptance))
        lo, hi = _wilson(covered, repeats)
        rows.append(
            {
                "n_events": n_events,
                "true_acceptance": true_acceptance,
                "alpha": alpha,
                "nominal_coverage": 1.0 - alpha,
                "repeats": repeats,
                "covered": covered,
                "coverage": covered / repeats,
                "coverage_mc_95_low": lo,
                "coverage_mc_95_high": hi,
                "min_upper": float(np.min(upper)),
            }
        )
    report = {
        "study": "RateCert-HEP binomial upper-bound coverage stress",
        "interpretation": "Monte-Carlo implementation diagnostic; exact coverage comes from Clopper-Pearson theorem",
        "seed": seed,
        "rows": rows,
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_text_lf(destination, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--repeats", type=int, default=20_000)
    args = parser.parse_args(argv)
    report = run(args.output, repeats=args.repeats)
    print(f"wrote {args.output} rows={len(report['rows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
