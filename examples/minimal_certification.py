"""Reproducible first RateCert-HEP experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ratecert import FixedPointSpec, RateQuantizationSpec, certify_rate, choose_threshold


ROOT = Path(__file__).resolve().parents[1]


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


def main() -> None:
    config = json.loads((ROOT / "configs" / "minimal_synthetic.json").read_text())
    score_cfg = config["score"]
    cert_cfg = config["certification"]
    blocks = config["blocks"]
    spec = FixedPointSpec(**score_cfg)
    rate_spec = RateQuantizationSpec(
        lsb_hz=cert_cfg["rate_lsb_hz"],
        rounding=cert_cfg["rate_rounding"],
        counter_bits=cert_cfg["rate_counter_bits"],
    )

    # The two blocks are deliberately independent and use distinct seeds.
    calibration = np.random.default_rng(20260912).random(20_000) * 0.99
    deployment = np.random.default_rng(20260913).random(20_000) * 0.99
    decision = choose_threshold(
        calibration,
        exposure_s=20.0,
        target_rate_hz=8.0,
        spec=spec,
    )
    certificate = certify_rate(
        deployment,
        exposure_s=20.0,
        threshold_code=decision.threshold_code,
        rate_budget_hz=cert_cfg["rate_budget_hz"],
        alpha=cert_cfg["alpha"],
        spec=spec,
        rate_spec=rate_spec,
        deployment_block_id=blocks["deployment"],
        calibration_block_id=blocks["calibration"],
        prescale=cert_cfg["prescale"],
    )
    output = {"calibration_decision": decision.as_dict(), "certificate": certificate.as_dict()}
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    _write_text_lf(out / "minimal_certificate.json", json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
