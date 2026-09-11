"""Stress the declared Poisson assumption with intentionally misspecified streams.

The reference Poisson path is exact only for a Poisson count with a fixed
threshold and exposure.  This script keeps the same nominal mean rate while replacing
the stationary process with bursty or mixed-rate windows.  The resulting
coverage is reported as a *failure-boundary diagnostic*, not as a new
confidence guarantee.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import chi2


def _upper_rate(counts: np.ndarray, exposure_s: float, alpha: float) -> np.ndarray:
    return 0.5 * chi2.isf(alpha, 2 * (counts + 1)) / exposure_s


def _coverage(counts: np.ndarray, exposure_s: float, true_rate_hz: float, alpha: float) -> dict[str, object]:
    upper = _upper_rate(counts, exposure_s, alpha)
    covered = int(np.count_nonzero(upper >= true_rate_hz))
    return {
        "covered": covered,
        "coverage": covered / int(counts.size),
        "repeats": int(counts.size),
        "nominal_coverage": 1.0 - alpha,
        "mean_count": float(np.mean(counts)),
        "mean_rate_hz": float(np.mean(counts) / exposure_s),
        "min_upper_rate_hz": float(np.min(upper)),
        "max_upper_rate_hz": float(np.max(upper)),
    }


def run(*, output: str | Path, seed: int = 20260918, repeats: int = 50_000) -> dict[str, object]:
    true_rate_hz = 8.0
    exposure_s = 10.0
    alpha = 0.01
    rng = np.random.default_rng(seed)
    mean_count = true_rate_hz * exposure_s

    poisson_counts = rng.poisson(mean_count, size=repeats)
    # A two-state burst process: each exposure is quiet or high-rate, with the
    # same nominal mean rate (0.8*0 + 0.2*40 = 8 Hz).
    burst_state = rng.random(repeats) < 0.2
    burst_counts = rng.poisson(np.where(burst_state, 40.0, 0.0) * exposure_s)
    # A gamma-Poisson mixture keeps the mean at 8 Hz but introduces window-level
    # rate variation (shape=2, scale=4 Hz).
    mixed_rates = rng.gamma(shape=2.0, scale=4.0, size=repeats)
    mixed_counts = rng.poisson(mixed_rates * exposure_s)
    scenarios = {
        "stationary_poisson": poisson_counts,
        "two_state_burst": burst_counts,
        "gamma_mixed_rate": mixed_counts,
    }
    rows = []
    for name, counts in scenarios.items():
        row = {
            "scenario": name,
            "model": {
                "stationary_poisson": "N ~ Poisson(8 Hz * 10 s)",
                "two_state_burst": "window rate is 0 Hz (80%) or 40 Hz (20%); nominal mean 8 Hz",
                "gamma_mixed_rate": "window rate ~ Gamma(shape=2, scale=4 Hz); nominal mean 8 Hz",
            }[name],
            **_coverage(counts, exposure_s, true_rate_hz, alpha),
        }
        rows.append(row)
    report = {
        "study": "RateCert-HEP Poisson assumption-boundary stress",
        "seed": seed,
        "repeats": repeats,
        "true_rate_hz": true_rate_hz,
        "exposure_s": exposure_s,
        "alpha": alpha,
        "interpretation": (
            "The stationary Poisson row is a reference. The burst and mixed-rate rows intentionally violate the fixed-rate Poisson assumption; their coverage is a refusal-boundary diagnostic, not a guarantee."
        ),
        "rows": rows,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=20260918)
    parser.add_argument("--repeats", type=int, default=50_000)
    args = parser.parse_args(argv)
    report = run(output=args.output, seed=args.seed, repeats=args.repeats)
    print("wrote " + str(args.output))
    for row in report["rows"]:
        print(f"{row['scenario']}: coverage={row['coverage']:.6f} mean_rate={row['mean_rate_hz']:.4f} Hz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
