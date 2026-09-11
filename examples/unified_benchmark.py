"""Run the public acceptance and explicit-exposure rate benchmarks together.

The two sections intentionally use different data semantics.  LHCO is a
selected simulation sample and remains a binomial acceptance result.  The
rate section samples a Poisson stream with a declared live time, then exercises
the production ``certify_rate`` path with rate-register quantization.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import chi2

from ratecert import FixedPointSpec, RateQuantizationSpec, certify_rate

try:
    from public_lhco_acceptance import run as run_public
except ImportError:  # pragma: no cover - module execution from repository root
    from examples.public_lhco_acceptance import run as run_public


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


def _rate_coverage(exposure_s: float, alpha: float, true_rate_hz: float, repeats: int, rng: np.random.Generator) -> dict:
    counts = rng.poisson(true_rate_hz * exposure_s, size=repeats)
    upper = 0.5 * chi2.isf(alpha, 2 * (counts + 1)) / exposure_s
    covered = int(np.count_nonzero(upper >= true_rate_hz))
    return {
        "exposure_s": exposure_s,
        "true_rate_hz": true_rate_hz,
        "repeats": repeats,
        "covered": covered,
        "coverage": covered / repeats,
        "nominal_coverage": 1.0 - alpha,
        "min_upper_rate_hz": float(np.min(upper)),
    }


def _run_rate_benchmark(*, seed: int = 20260916, coverage_repeats: int = 5_000) -> dict:
    exposure_grid = (1.0, 10.0, 100.0)
    lsb_grid = (0.01, 0.05, 0.1)
    counter_bits_grid = (8, 16)
    budget_grid = (10.0, 12.0)
    true_rate_hz = 8.0
    family_alpha = 0.01
    n_cells = len(exposure_grid) * len(lsb_grid) * len(counter_bits_grid) * len(budget_grid)
    cell_alpha = family_alpha / n_cells
    rng = np.random.default_rng(seed)
    coverage = {
        str(exposure): _rate_coverage(
            exposure, cell_alpha, true_rate_hz, coverage_repeats, rng
        )
        for exposure in exposure_grid
    }
    rows = []
    for exposure_s in exposure_grid:
        for rate_lsb_hz in lsb_grid:
            for counter_bits in counter_bits_grid:
                for budget in budget_grid:
                    observed_count = int(rng.poisson(true_rate_hz * exposure_s))
                    # The score stream is a minimal binary trigger stream.  Its
                    # exposure is supplied independently to certify_rate.
                    scores = np.ones(observed_count, dtype=float)
                    if observed_count == 0:
                        scores = np.array([0.0])
                    cert = certify_rate(
                        scores,
                        exposure_s=exposure_s,
                        threshold_code=1,
                        rate_budget_hz=budget,
                        alpha=cell_alpha,
                        spec=FixedPointSpec(bits=1, fractional_bits=0),
                        rate_spec=RateQuantizationSpec(
                            lsb_hz=rate_lsb_hz,
                            counter_bits=counter_bits,
                        ),
                        deployment_block_id=f"poisson-deploy-t{exposure_s}-q{rate_lsb_hz}-b{counter_bits}-r{budget}",
                        calibration_block_id=f"poisson-cal-t{exposure_s}-q{rate_lsb_hz}-b{counter_bits}-r{budget}",
                        prescale=4,
                    )
                    row = cert.as_dict()
                    row.update(
                        {
                            "true_rate_hz": true_rate_hz,
                            "exposure_s": exposure_s,
                            "observed_count_generated": observed_count,
                            "rate_lsb_requested_hz": rate_lsb_hz,
                            "counter_bits_requested": counter_bits,
                            "rate_budget_requested_hz": budget,
                            "selection_alpha": cell_alpha,
                            "threshold_selection_rule": "fixed_binary_threshold_code_1",
                            "coverage_diagnostic": coverage[str(exposure_s)],
                        }
                    )
                    rows.append(row)
    return {
        "study": "RateCert-HEP explicit-exposure rate and resolution sweep",
        "true_rate_hz": true_rate_hz,
        "familywise_alpha": family_alpha,
        "familywise_cells": n_cells,
        "per_cell_alpha": cell_alpha,
        "coverage_repeats": coverage_repeats,
        "interpretation": {
            "stream_model": "Poisson background count with declared exposure_s",
            "rate_fields_are_absolute": True,
            "prescale_semantics": "recorded rates are raw rates divided by the declared integer prescale",
            "hardware_status": "software contract benchmark; no FPGA or detector timing claim",
        },
        "coverage_by_exposure": coverage,
        "cells": rows,
    }


def run(public_input: str | Path, output_path: str | Path) -> dict:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    public_report = run_public(public_input, destination.parent / "public_lhco_acceptance.json")
    rate_report = _run_rate_benchmark()
    report = {
        "study": "RateCert-HEP v0.2 unified benchmark",
        "public_acceptance": public_report,
        "explicit_rate": rate_report,
        "claim_boundary": (
            "LHCO cells certify background acceptance probability; explicit-rate cells certify a Poisson count under declared exposure. "
            "Neither section is a detector-hardware deployment measurement."
        ),
    }
    _write_text_lf(destination, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = run(args.public_input, args.output)
    public_cells = report["public_acceptance"]["cells"]
    rate_cells = report["explicit_rate"]["cells"]
    print(
        f"wrote {args.output} public_certified={sum(x['certified'] for x in public_cells)}/{len(public_cells)} "
        f"rate_certified={sum(x['certified'] for x in rate_cells)}/{len(rate_cells)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
