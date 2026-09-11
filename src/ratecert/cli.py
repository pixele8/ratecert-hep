"""Command-line entry point for a single RateCert-HEP certificate."""

from __future__ import annotations

import argparse
import sys

from .core import FixedPointSpec, RateQuantizationSpec, certify_rate
from .io import load_scores, read_json, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="certify a finite-sample fixed-point trigger rate")
    parser.add_argument("--config", required=True, help="JSON deployment specification")
    parser.add_argument("--scores", required=True, help="deployment scores (.npy or one-column CSV)")
    parser.add_argument("--exposure-s", required=True, type=float)
    parser.add_argument("--threshold-code", required=True, type=int)
    parser.add_argument("--output", required=True, help="certificate JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = read_json(args.config)
        score_spec = FixedPointSpec(**config["score"])
        cert_config = config["certification"]
        rate_spec = RateQuantizationSpec(
            lsb_hz=float(cert_config["rate_lsb_hz"]),
            rounding=cert_config.get("rate_rounding", "nearest_even"),
            counter_bits=cert_config.get("rate_counter_bits"),
        )
        blocks = config["blocks"]
        certificate = certify_rate(
            load_scores(args.scores),
            exposure_s=args.exposure_s,
            threshold_code=args.threshold_code,
            rate_budget_hz=float(cert_config["rate_budget_hz"]),
            alpha=float(cert_config["alpha"]),
            spec=score_spec,
            rate_spec=rate_spec,
            deployment_block_id=blocks["deployment"],
            calibration_block_id=blocks["calibration"],
            prescale=int(cert_config.get("prescale", 1)),
        )
        write_json(args.output, certificate.as_dict())
        print(certificate.status)
        return 0
    except (KeyError, OSError, TypeError, ValueError) as exc:
        print(f"ratecert-hep input error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
