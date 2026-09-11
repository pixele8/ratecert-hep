import json
import math

import numpy as np
import pytest

from ratecert import (
    FixedPointSpec,
    RateQuantizationSpec,
    binomial_upper_acceptance,
    certify_acceptance,
    choose_acceptance_threshold,
    quantization_acceptance_diagnostics,
)


def test_binomial_upper_uses_stable_isf_for_small_alpha():
    upper = binomial_upper_acceptance(0, 100_000, 1e-12)
    assert 2e-4 < upper < 4e-4


def test_acceptance_threshold_and_independent_certificate():
    spec = FixedPointSpec(bits=8, fractional_bits=8)
    decision = choose_acceptance_threshold(
        np.linspace(0.1, 0.9, 10_000),
        target_acceptance=0.03,
        spec=spec,
        calibration_block_id="lhco-cal",
        selection_alpha=0.01,
    )
    cert = certify_acceptance(
        np.linspace(0.1, 0.9, 10_000),
        threshold_code=decision.threshold_code,
        target_acceptance=0.03,
        alpha=0.01,
        spec=spec,
        calibration_block_id="lhco-cal",
        deployment_block_id="lhco-deploy",
    )
    assert cert.status == "CERTIFIED"
    assert cert.quantity == "background_acceptance_probability"
    assert cert.sample_size == 10_000
    assert cert.upper_acceptance <= 0.03
    assert cert.point_rate_hz is None
    assert decision.selection_rule == "clopper_pearson_upper_bound"
    assert "calibration Clopper-Pearson upper bound" in decision.warnings[0]
    json.dumps(cert.as_dict(), allow_nan=False)


def test_absolute_rate_requires_explicit_flux_and_keeps_prescale_separate():
    spec = FixedPointSpec(bits=8, fractional_bits=8)
    cert = certify_acceptance(
        [0.1] * 99 + [0.9],
        threshold_code=200,
        target_acceptance=0.1,
        alpha=0.01,
        spec=spec,
        calibration_block_id="cal",
        deployment_block_id="dep",
        input_rate_hz=100.0,
        rate_budget_hz=10.0,
        rate_spec=RateQuantizationSpec(lsb_hz=0.1),
        prescale=4,
    )
    assert cert.status == "CERTIFIED"
    assert cert.point_rate_hz == 1.0
    assert cert.recorded_point_rate_hz == 0.25
    assert cert.upper_rate_hz > cert.point_rate_hz
    assert cert.recorded_upper_rate_hz == cert.upper_rate_hz / 4


def test_rate_claim_without_flux_is_refused_and_explained():
    cert = certify_acceptance(
        [0.1, 0.2],
        threshold_code=100,
        target_acceptance=0.5,
        alpha=0.05,
        spec=FixedPointSpec(bits=8, fractional_bits=8),
        calibration_block_id="cal",
        deployment_block_id="dep",
        rate_budget_hz=1.0,
    )
    assert cert.status == "NOT_CERTIFIED"
    assert "input_rate_hz is required when rate_budget_hz is supplied" in cert.reasons


def test_invalid_numeric_inputs_still_serialize_strictly():
    cert = certify_acceptance(
        [0.1],
        threshold_code=1,
        target_acceptance="bad",
        alpha="bad",
        spec=FixedPointSpec(bits=8, fractional_bits=8),
        calibration_block_id="cal",
        deployment_block_id="dep",
        prescale=0,
    )
    payload = cert.as_dict()
    json.dumps(payload, allow_nan=False)
    assert cert.status == "NOT_CERTIFIED"
    assert math.isfinite(cert.score_lsb)


def test_quantization_effect_is_reported_as_a_diagnostic():
    spec = FixedPointSpec(bits=4, fractional_bits=4)
    cert = certify_acceptance(
        [0.49, 0.51, 0.90],
        threshold_code=8,
        target_acceptance=0.9,
        alpha=0.5,
        spec=spec,
        calibration_block_id="cal",
        deployment_block_id="dep",
    )
    assert cert.prequantized_acceptance == 2 / 3
    assert cert.empirical_acceptance == 1.0
    assert cert.quantization_acceptance_delta == pytest.approx(1 / 3)
    assert cert.score_quantization["threshold_value"] == 0.5


def test_quantization_sweep_finds_boundary_effect():
    diagnostic = quantization_acceptance_diagnostics(
        [0.49, 0.51, 0.90], spec=FixedPointSpec(bits=4, fractional_bits=4)
    )
    assert diagnostic["max_abs_acceptance_delta"] > 0
    assert diagnostic["thresholds_evaluated"] == 2
