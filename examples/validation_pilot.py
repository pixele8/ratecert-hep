"""Small validation pilot for the two claims in the prototype."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ratecert import FixedPointSpec, RateQuantizationSpec, certify_rate, poisson_upper_rate


def main() -> None:
    rng = np.random.default_rng(20260914)
    true_rate_hz = 8.0
    exposure_s = 20.0
    alpha = 0.01
    counts = rng.poisson(true_rate_hz * exposure_s, size=10_000)
    upper = np.array([poisson_upper_rate(int(count), exposure_s, alpha) for count in counts])
    coverage = float(np.mean(upper >= true_rate_hz))

    # A point estimate below the budget, but an exact finite-sample certificate
    # that correctly refuses the deployment near the boundary.
    spec = FixedPointSpec(bits=10, fractional_bits=8)
    rate_spec = RateQuantizationSpec(lsb_hz=0.1, rounding="nearest_even")
    boundary_scores = np.concatenate(
        [rng.uniform(0.0, 0.70, 905), rng.uniform(0.80, 0.99, 95)]
    )
    boundary = certify_rate(
        boundary_scores,
        exposure_s=10.0,
        threshold_code=205,
        rate_budget_hz=10.0,
        alpha=alpha,
        spec=spec,
        rate_spec=rate_spec,
        deployment_block_id="boundary-deploy-v1",
        calibration_block_id="boundary-cal-v1",
    )
    result = {
        "poisson_coverage_pilot": {
            "true_rate_hz": true_rate_hz,
            "exposure_s": exposure_s,
            "alpha": alpha,
            "replicates": int(counts.size),
            "observed_coverage": coverage,
            "expected_minimum_coverage": 1.0 - alpha,
        },
        "near_budget_boundary": boundary.as_dict(),
    }
    out = Path(__file__).resolve().parents[1] / "reports"
    out.mkdir(exist_ok=True)
    (out / "validation_pilot.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
