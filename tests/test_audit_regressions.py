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


# --------------------------------------------------------------------------
# M1: an upper bound must never sit below the point estimate
# --------------------------------------------------------------------------
def test_alpha_above_one_half_is_refused_poisson():
    """alpha = 0.9 used to return 88.35 Hz against a point estimate of 100 Hz."""
    from ratecert.core import poisson_upper_rate

    assert poisson_upper_rate(10, 1.0, 0.5) >= 10.0
    with pytest.raises(ValueError, match="alpha must be <= 0.5"):
        poisson_upper_rate(10, 1.0, 0.9)
    with pytest.raises(ValueError, match="alpha must be <= 0.5"):
        poisson_upper_rate(10, 1.0, 0.5000001)


def test_alpha_above_one_half_is_refused_binomial():
    from ratecert.acceptance import binomial_upper_acceptance

    assert binomial_upper_acceptance(5, 100, 0.5) > 0.05
    with pytest.raises(ValueError, match="alpha must be <= 0.5"):
        binomial_upper_acceptance(5, 100, 0.9)


@pytest.mark.parametrize("alpha", [1e-12, 1e-6, 0.01, 0.05, 0.1, 0.25, 0.5])
@pytest.mark.parametrize("count", [0, 1, 5, 50, 1000])
def test_upper_bound_always_dominates_point_estimate(alpha, count):
    """Invariant: U_alpha(N,T) >= N/T for every admissible alpha."""
    from ratecert.core import poisson_upper_rate

    T = 3.5
    upper = poisson_upper_rate(count, T, alpha)
    assert upper >= count / T - 1e-12


# --------------------------------------------------------------------------
# M3 / complexity: the selector must be O(n log n) and bit-identical
# --------------------------------------------------------------------------
def test_selector_matches_independent_reference_and_is_fast():
    """The vectorised selector must agree with an independent reference.

    The version being replaced rescanned the score array once per distinct code,
    i.e. O(n * u); at 100,000 events and a 16-bit format that took 14.1 s against
    0.012 s for the cumulative form.

    The reference used here is deliberately NOT that slow loop: a naive
    re-implementation makes this test take ~43 s, which is unfit for a suite.
    Instead selection is recomputed by sorting the codes once and walking the
    distinct values in ascending order, tracking the running tail count.  That is
    a different code path from the cumsum under test, so agreement is still
    meaningful, and it is fast enough to run 400 configurations.
    """
    import time

    from ratecert.acceptance import binomial_upper_acceptance, choose_acceptance_threshold

    rng = np.random.default_rng(11)

    def reference_threshold(codes, n_events, target, sel_alpha, code_max):
        """Smallest code whose tail criterion meets the target, by a sorted walk."""
        ordered = np.sort(codes)
        distinct = np.unique(ordered)
        for value in distinct:                      # ascending
            count = int(np.count_nonzero(ordered >= value))
            crit = (binomial_upper_acceptance(count, n_events, sel_alpha)
                    if sel_alpha is not None else count / n_events)
            if crit <= target:
                return int(value)
        return code_max + 1

    # 60 draws x 2 selection rules = 120 configurations.  The count is kept
    # modest on purpose: with a selection alpha the reference makes one beta-tail
    # call per distinct code, so a larger sweep costs seconds per thousand
    # configurations and would make the suite unpleasant to run.  An earlier
    # revision of the manuscript claimed 400 configurations while this test ran
    # only 40, so the claim had no artifact behind it; the artifact now matches
    # the number the paper quotes.
    for _ in range(60):
        n = int(rng.integers(50, 600))
        bits = int(rng.integers(8, 13))
        spec = FixedPointSpec(bits=bits, fractional_bits=min(bits, 8))
        scores = rng.integers(0, spec.code_max + 1, size=n) * spec.lsb
        target = float(rng.uniform(0.01, 0.3))
        for sel_alpha in (None, 0.05):
            got = choose_acceptance_threshold(
                scores, target_acceptance=target, spec=spec, selection_alpha=sel_alpha
            ).threshold_code
            codes = quantize_scores(scores, spec).codes
            ref = reference_threshold(codes, n, target, sel_alpha, spec.code_max)
            assert got == ref, (
                "selector disagreement: bits=%d n=%d target=%.4f alpha=%s got=%d ref=%d"
                % (bits, n, target, sel_alpha, got, ref)
            )

    # timing guard: 100k events at 16 bits must not take seconds
    spec = FixedPointSpec(bits=16, fractional_bits=8)
    big = rng.integers(0, spec.code_max + 1, size=100_000) * spec.lsb
    t0 = time.perf_counter()
    choose_acceptance_threshold(big, target_acceptance=0.01, spec=spec)
    assert time.perf_counter() - t0 < 2.0


def test_quantization_diagnostics_does_not_allocate_by_code_range():
    """A 32-bit format used to allocate 8 * 2**32 bytes (34 GB) for 3 scores."""
    import tracemalloc

    from ratecert.acceptance import quantization_acceptance_diagnostics

    spec = FixedPointSpec(bits=32, fractional_bits=8)
    tracemalloc.start()
    result = quantization_acceptance_diagnostics([0.9, 0.8, 0.7], spec=spec)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 5 * 1024 * 1024, "peak allocation %.1f MB" % (peak / 1e6)
    assert result["thresholds_evaluated"] == 3
