"""Regression tests for defects found by an adversarial external audit.

Each test here corresponds to a concrete bug that shipped in an earlier
revision.  They exist so the same class of failure cannot return silently.

The two most serious were FALSE CERTIFICATIONS, which are the worst possible
failure for a tool whose entire promise is that CERTIFIED means every contract
clause was satisfied:

C1  An unsigned 64-bit FixedPointSpec declared code_max = 2**64 - 1, which
    exceeds int64.  The range test compared in float64, passed, and the
    subsequent .astype(np.int64) wrapped every code to INT64_MIN.  Scores of
    0.9/0.8/0.7 against threshold 0 therefore produced count 0 and a CERTIFIED
    status, when the true count is 3 and the true upper rate exceeds the budget.

C2  certify_acceptance applied only the budget clause, never the rate-counter
    full-scale clause, so a 4-bit counter with a 1.5 Hz full scale certified an
    upper rate of 6.2e4 Hz while certify_rate refused the identical physics.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ratecert.acceptance import certify_acceptance
from ratecert.core import (
    FixedPointSpec,
    RateQuantizationSpec,
    certify_rate,
    quantize_scores,
)


# --------------------------------------------------------------------------
# C1: widths that cannot be represented must be refused, not silently wrapped
# --------------------------------------------------------------------------
def test_unsigned_64bit_spec_is_refused():
    with pytest.raises(ValueError, match="bits must be <= 63"):
        FixedPointSpec(bits=64, fractional_bits=64, signed=False)


def test_signed_64bit_spec_is_refused():
    with pytest.raises(ValueError, match="bits must be <= 63"):
        FixedPointSpec(bits=64, fractional_bits=8, signed=True)


def test_widest_accepted_spec_does_not_wrap():
    spec = FixedPointSpec(bits=63, fractional_bits=8, signed=False)
    assert spec.code_max == 2**63 - 1
    q = quantize_scores([0.9, 0.8, 0.7], spec)
    assert q.saturation_count == 0
    # every code must be non-negative and actually above threshold 0
    assert np.all(q.codes >= 0)
    assert int(np.count_nonzero(q.codes >= 0)) == 3


def test_c1_original_repro_no_longer_certifies_vacuously():
    """The exact call that used to return CERTIFIED with count 0."""
    with pytest.raises(ValueError):
        certify_rate(
            [0.9, 0.8, 0.7], exposure_s=1.0, threshold_code=0,
            rate_budget_hz=5.0, alpha=0.05,
            spec=FixedPointSpec(bits=64, fractional_bits=64),
            rate_spec=RateQuantizationSpec(lsb_hz=0.05),
            deployment_block_id="dep", calibration_block_id="cal",
        )


# --------------------------------------------------------------------------
# C2: both entry points must apply the same clauses
# --------------------------------------------------------------------------
def _acceptance_kwargs(counter_bits):
    return dict(
        threshold_code=200,
        target_acceptance=0.10,
        alpha=0.05,
        spec=FixedPointSpec(bits=8, fractional_bits=8, signed=False),
        calibration_block_id="cal-1",
        deployment_block_id="dep-1",
        input_rate_hz=1e6,
        rate_budget_hz=1e5,
        rate_spec=RateQuantizationSpec(lsb_hz=0.1, counter_bits=counter_bits),
    )


def test_acceptance_path_refuses_counter_full_scale_overflow():
    """4-bit counter, 0.1 Hz LSB -> 1.5 Hz full scale, upper rate 6.2e4 Hz."""
    cert = certify_acceptance([0.9] * 2 + [0.1] * 98, **_acceptance_kwargs(4))
    assert cert.status == "NOT_CERTIFIED"
    assert cert.reasons, "a refusal must carry at least one reason"
    joined = " ".join(cert.reasons)
    assert "full scale" in joined or "overflow" in joined


def test_both_entry_points_agree_on_the_same_physics():
    """The acceptance path and the explicit-rate path must reach the same verdict."""
    acc = certify_acceptance([0.9] * 2 + [0.1] * 98, **_acceptance_kwargs(4))
    rate = certify_rate(
        [0.9] * 2 + [0.1] * 98, exposure_s=1.0, threshold_code=200,
        rate_budget_hz=1e5, alpha=0.05,
        spec=FixedPointSpec(bits=8, fractional_bits=8, signed=False),
        rate_spec=RateQuantizationSpec(lsb_hz=0.1, counter_bits=4),
        deployment_block_id="dep-1", calibration_block_id="cal-1",
    )
    assert acc.certified == rate.certified == False  # noqa: E712


def test_acceptance_path_still_certifies_when_counter_has_range():
    """Widening the counter must make the same configuration pass."""
    cert = certify_acceptance([0.9] * 2 + [0.1] * 98, **_acceptance_kwargs(63))
    assert cert.status == "CERTIFIED", cert.reasons


# --------------------------------------------------------------------------
# M2: illegal declarations must be clean input errors, not OverflowError
# --------------------------------------------------------------------------
def test_oversized_counter_bits_is_refused():
    with pytest.raises(ValueError, match="counter_bits must be <= 63"):
        RateQuantizationSpec(lsb_hz=0.05, counter_bits=1024)


def test_declared_code_range_matches_int64():
    """code_max must always be representable in the int64 code array."""
    for bits in (1, 8, 16, 32, 63):
        spec = FixedPointSpec(bits=bits, fractional_bits=min(bits, 8))
        assert spec.code_max <= np.iinfo(np.int64).max
        assert spec.code_min >= np.iinfo(np.int64).min
