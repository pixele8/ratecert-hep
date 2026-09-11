import math
import json

import numpy as np
import pytest

from ratecert import (
    FixedPointSpec,
    RateQuantizationSpec,
    certify_rate,
    choose_threshold,
    poisson_upper_rate,
    quantize_scores,
    rate_curve,
)
from ratecert.io import load_scores, read_json, write_json


def test_nearest_even_quantization_is_repeatable_and_bounded():
    spec = FixedPointSpec(bits=8, fractional_bits=4)
    values = np.array([0.0, 0.0625, 0.09375, 0.5])
    first = quantize_scores(values, spec)
    second = quantize_scores(values, spec)
    np.testing.assert_array_equal(first.codes, second.codes)
    assert first.saturation_count == 0
    assert first.max_abs_error <= spec.lsb / 2 + 1e-12


def test_saturation_is_explicit():
    strict = FixedPointSpec(bits=4, fractional_bits=2, saturation="error")
    with pytest.raises(ValueError, match="exceed fixed-point range"):
        quantize_scores([0.0, 4.0], strict)

    permissive = FixedPointSpec(bits=4, fractional_bits=2, saturation="saturate")
    result = quantize_scores([0.0, 4.0], permissive)
    assert result.saturation_count == 1
    assert math.isinf(result.error_bound)


def test_poisson_upper_bound_is_finite_and_above_point_estimate():
    upper = poisson_upper_rate(10, 2.0, 0.01)
    assert upper > 5.0
    assert math.isfinite(upper)


def test_poisson_upper_bound_remains_finite_after_familywise_alpha_split():
    upper = poisson_upper_rate(0, 10.0, 1e-12)
    assert 2.0 < upper < 4.0


def test_counter_window_derives_deterministic_rate_lsb():
    spec = RateQuantizationSpec.from_counter_window(20.0, counter_bits=8)
    assert spec.lsb_hz == 0.05
    assert spec.error_bound_hz == 0.025
    assert spec.max_count == 255
    assert spec.max_rate_hz == 12.75


def test_counter_overflow_is_a_structured_refusal():
    spec = FixedPointSpec(bits=8, fractional_bits=4)
    cert = certify_rate(
        np.full(256, 0.9),
        exposure_s=1.0,
        threshold_code=10,
        rate_budget_hz=1_000.0,
        alpha=0.05,
        spec=spec,
        rate_spec=RateQuantizationSpec(lsb_hz=1.0, counter_bits=8),
        deployment_block_id="deploy-overflow",
        calibration_block_id="cal-overflow",
    )
    assert not cert.certified
    assert "rate counter overflow: count 256 exceeds 255" in cert.reasons


def test_rate_counter_full_scale_is_part_of_the_certificate():
    spec = FixedPointSpec(bits=8, fractional_bits=4)
    cert = certify_rate(
        np.full(10, 0.9),
        exposure_s=1.0,
        threshold_code=10,
        rate_budget_hz=100.0,
        alpha=0.01,
        spec=spec,
        rate_spec=RateQuantizationSpec(lsb_hz=1.0, counter_bits=4),
        deployment_block_id="deploy-full-scale",
        calibration_block_id="cal-full-scale",
    )
    assert not cert.certified
    assert "finite-sample upper rate exceeds the declared rate-counter full scale" in cert.reasons


def test_json_and_score_io_round_trip(tmp_path):
    score_path = tmp_path / "scores.csv"
    score_path.write_text("0.1\n0.2\n0.3\n", encoding="utf-8")
    np.testing.assert_allclose(load_scores(score_path), [0.1, 0.2, 0.3])
    payload_path = tmp_path / "nested" / "payload.json"
    write_json(payload_path, {"status": "CERTIFIED", "count": 3})
    assert read_json(payload_path)["count"] == 3


def test_rate_curve_and_threshold_selection():
    spec = FixedPointSpec(bits=8, fractional_bits=4)
    decision = choose_threshold(
        [0.1, 0.2, 0.8, 0.9], exposure_s=2.0, target_rate_hz=1.1, spec=spec
    )
    assert decision.threshold_code == 13
    thresholds, rates = rate_curve([1, 2, 2, 4], exposure_s=2.0)
    np.testing.assert_array_equal(thresholds, [1, 2, 4])
    np.testing.assert_allclose(rates, [2.0, 1.5, 0.5])


def test_threshold_selection_has_explicit_zero_rate_fallback():
    spec = FixedPointSpec(bits=4, fractional_bits=2)
    decision = choose_threshold(
        [0.1, 0.2], exposure_s=1.0, target_rate_hz=0.1, spec=spec
    )
    assert decision.threshold_code == spec.code_max + 1
    assert decision.empirical_rate_hz == 0.0


def test_certified_case_reports_separate_raw_and_recorded_rates():
    spec = FixedPointSpec(bits=10, fractional_bits=8)
    scores = np.array([0.1, 0.2, 0.3, 0.99, 0.995, 0.1, 0.4, 0.7])
    cert = certify_rate(
        scores,
        exposure_s=10.0,
        threshold_code=255,
        rate_budget_hz=2.0,
        alpha=0.05,
        spec=spec,
        rate_spec=RateQuantizationSpec(lsb_hz=0.1),
        deployment_block_id="deploy-1",
        calibration_block_id="cal-1",
        prescale=4,
    )
    assert cert.status == "CERTIFIED"
    assert cert.count == 1
    assert cert.recorded_point_rate_hz == cert.point_rate_hz / 4
    assert cert.rate_resolution_hz == 0.1
    assert cert.observed_rate_step_hz is not None
    assert cert.deployment_margin_hz is not None
    assert cert.deployment_score == cert.deployment_margin_hz / cert.rate_budget_hz


def test_certificate_refuses_overlap_and_budget_overrun():
    spec = FixedPointSpec(bits=8, fractional_bits=4)
    cert = certify_rate(
        np.full(20, 0.9),
        exposure_s=1.0,
        threshold_code=10,
        rate_budget_hz=1.0,
        alpha=0.01,
        spec=spec,
        rate_spec=RateQuantizationSpec(lsb_hz=0.1),
        deployment_block_id="same",
        calibration_block_id="same",
    )
    assert not cert.certified
    assert "calibration and deployment blocks overlap by identity" in cert.reasons
    assert "finite-sample upper rate plus fixed-point margin exceeds budget" in cert.reasons


def test_certificate_refuses_saturation_in_strict_mode():
    spec = FixedPointSpec(bits=4, fractional_bits=2, saturation="error")
    cert = certify_rate(
        [0.1, 4.0],
        exposure_s=2.0,
        threshold_code=1,
        rate_budget_hz=100.0,
        alpha=0.05,
        spec=spec,
        rate_spec=RateQuantizationSpec(lsb_hz=0.1),
        deployment_block_id="deploy-2",
        calibration_block_id="cal-2",
    )
    assert not cert.certified
    assert any(reason.startswith("invalid score stream:") for reason in cert.reasons)


def test_missing_rate_resolution_spec_is_a_structured_refusal():
    spec = FixedPointSpec(bits=8, fractional_bits=4)
    cert = certify_rate(
        [0.1, 0.2],
        exposure_s=1.0,
        threshold_code=2,
        rate_budget_hz=100.0,
        alpha=0.05,
        spec=spec,
        rate_spec=None,
        deployment_block_id="deploy-3",
        calibration_block_id="cal-3",
    )
    assert not cert.certified
    assert "missing deterministic rate resolution spec" in cert.reasons


def test_invalid_numeric_metadata_still_serializes_as_strict_json():
    cert = certify_rate(
        [0.1, 0.2],
        exposure_s=0.0,
        threshold_code=2,
        rate_budget_hz=0.0,
        alpha=0.05,
        spec=FixedPointSpec(bits=8, fractional_bits=4),
        rate_spec=RateQuantizationSpec(lsb_hz=0.1),
        deployment_block_id="deploy-invalid",
        calibration_block_id="cal-invalid",
        prescale=0,
    )
    assert not cert.certified
    assert "prescale must be a positive integer" in cert.reasons
    assert "rate_budget_hz must be positive and finite" in cert.reasons
    json.dumps(cert.as_dict(), allow_nan=False)
