"""Reproduce the public LHC Olympics finite-sample acceptance study.

The file is intentionally a batch CLI rather than a GUI.  It sweeps fixed
point widths, deployment sample sizes, and acceptance budgets while applying a
Bonferroni family-wise alpha over the reported cells.  It never converts this
selected simulation sample to Hz because no live time or input flux is
contained in the release.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ratecert import (
    certify_acceptance,
    choose_acceptance_threshold,
    event_id_sha256,
    fixed_point_for_lhco,
    load_lhco_background_split,
    quantization_acceptance_diagnostics,
)


def run(input_path: str | Path, output_path: str | Path) -> dict:
    bits_grid = (8, 10, 12)
    sample_grid = (10_000, 50_000, 100_000)
    budget_grid = (0.005, 0.01, 0.02)
    n_cells = len(bits_grid) * len(sample_grid) * len(budget_grid)
    family_alpha = 0.01
    cell_alpha = family_alpha / n_cells
    split = load_lhco_background_split(
        input_path,
        calibration_n=max(sample_grid),
        deployment_n=max(sample_grid),
        seed=20260912,
    )
    rows = []
    for bits in bits_grid:
        spec = fixed_point_for_lhco(bits)
        for sample_size in sample_grid:
            calibration = split.calibration_scores[:sample_size]
            deployment = split.deployment_scores[:sample_size]
            quantization_sweep = quantization_acceptance_diagnostics(
                deployment, spec=spec
            )
            for budget in budget_grid:
                decision = choose_acceptance_threshold(
                    calibration,
                    target_acceptance=budget,
                    spec=spec,
                    calibration_block_id=f"lhco-rnd-cal-{sample_size}-b{bits}",
                    selection_alpha=cell_alpha,
                )
                certificate = certify_acceptance(
                    deployment,
                    threshold_code=decision.threshold_code,
                    target_acceptance=budget,
                    alpha=cell_alpha,
                    spec=spec,
                    calibration_block_id=f"lhco-rnd-cal-{sample_size}-b{bits}",
                    deployment_block_id=f"lhco-rnd-deploy-{sample_size}-b{bits}",
                    provenance={
                        "calibration_event_id_sha256": event_id_sha256(
                            split.calibration_event_ids[:sample_size]
                        ),
                        "deployment_event_id_sha256": event_id_sha256(
                            split.deployment_event_ids[:sample_size]
                        ),
                        "sample_prefix_n": sample_size,
                        "public_data_mode": True,
                    },
                )
                row = certificate.as_dict()
                row.update(
                    {
                        "bits": bits,
                        "sample_size_requested": sample_size,
                        "target_acceptance_requested": budget,
                        "selection_alpha": cell_alpha,
                        "calibration_selection_rule": decision.selection_rule,
                        "calibration_empirical_acceptance": decision.empirical_acceptance,
                        "calibration_warnings": list(decision.warnings),
                        "quantization_sweep": quantization_sweep,
                    }
                )
                rows.append(row)
    report = {
        "study": "RateCert-HEP public LHCO finite-sample acceptance sweep",
        "familywise_alpha": family_alpha,
        "familywise_cells": n_cells,
        "per_cell_alpha": cell_alpha,
        "score_contract": {
            "definition": split.score_definition,
            "normalization_GeV": split.score_normalization,
            "fixed_point": "unsigned bits=fractional_bits, nearest_even, no saturation expected",
        },
        "interpretation": {
            "primary_quantity": "background_acceptance_probability",
            "absolute_rate_hz": False,
            "reason": "the LHCO release is a selected simulation sample without live time or representative input flux",
            "shared_prefixes": True,
            "comparison_note": "each cell has a valid per-cell binomial bound; familywise alpha controls the displayed sweep",
        },
        "provenance": split.as_dict(),
        "cells": rows,
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = run(args.input, args.output)
    certified = sum(cell["certified"] for cell in report["cells"])
    print(f"wrote {args.output} cells={len(report['cells'])} certified={certified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
