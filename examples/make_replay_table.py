"""Flatten the unified JSON report into a reviewer-friendly cell table."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = [
    "chain",
    "score_bits",
    "deployment_prefix",
    "exposure_s",
    "target_acceptance",
    "rate_budget_hz",
    "rate_lsb_hz",
    "counter_bits",
    "alpha",
    "count",
    "sample_size",
    "point_estimate",
    "upper_bound",
    "rate_margin_hz",
    "counter_max_count",
    "status",
    "reasons",
]


def _public_rows(report: dict) -> list[dict[str, object]]:
    rows = []
    for cell in report["public_acceptance"]["cells"]:
        rows.append(
            {
                "chain": "LHCO acceptance",
                "score_bits": cell["bits"],
                "deployment_prefix": cell["sample_size"],
                "exposure_s": "",
                "target_acceptance": cell["target_acceptance"],
                "rate_budget_hz": "",
                "rate_lsb_hz": "",
                "counter_bits": "",
                "alpha": cell["alpha"],
                "count": cell["count"],
                "sample_size": cell["sample_size"],
                "point_estimate": cell["empirical_acceptance"],
                "upper_bound": cell["upper_acceptance"],
                "rate_margin_hz": "",
                "counter_max_count": "",
                "status": cell["status"],
                "reasons": "; ".join(cell["reasons"]),
            }
        )
    return rows


def _rate_rows(report: dict) -> list[dict[str, object]]:
    rows = []
    for cell in report["explicit_rate"]["cells"]:
        rate_spec = cell["fixed_point"]["rate_spec"]
        rows.append(
            {
                "chain": "Explicit Poisson rate",
                "score_bits": cell["fixed_point"]["score_spec"]["bits"],
                "deployment_prefix": "",
                "exposure_s": cell["exposure_s"],
                "target_acceptance": "",
                "rate_budget_hz": cell["rate_budget_hz"],
                "rate_lsb_hz": cell["rate_lsb_requested_hz"],
                "counter_bits": cell["counter_bits_requested"],
                "alpha": cell["alpha"],
                "count": cell["count"],
                "sample_size": cell["fixed_point"]["n_scores"],
                "point_estimate": cell["point_rate_hz"],
                "upper_bound": cell["upper_rate_hz"],
                "rate_margin_hz": cell["quantization_margin_hz"],
                "counter_max_count": rate_spec["max_count"],
                "status": cell["status"],
                "reasons": "; ".join(cell["reasons"]),
            }
        )
    return rows


def make_table(input_path: str | Path, output_path: str | Path) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    report = json.loads(input_path.read_text(encoding="utf-8"))
    rows = _public_rows(report) + _rate_rows(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    path = make_table(args.input, args.output)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
