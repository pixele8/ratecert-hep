"""Finite-sample acceptance certification for fixed-point trigger scores.

This module is the public-data mode of RateCert-HEP.  A finite MC/data sample
contains a number of accepted events but no detector live time, so the primary
quantity is a one-sided binomial upper confidence bound on the background
acceptance probability.  Conversion to Hz is opt-in and requires an explicit
external input flux.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
from scipy.stats import beta

from .core import FixedPointSpec, RateQuantizationSpec, quantize_scores


@dataclass(frozen=True)
class AcceptanceDecision:
    threshold_code: int
    empirical_acceptance: float
    target_acceptance: float
    n_events: int
    score_lsb: float
    calibration_block_id: str
    selection_rule: str = "empirical_tail"
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "threshold_code": self.threshold_code,
            "empirical_acceptance": self.empirical_acceptance,
            "target_acceptance": self.target_acceptance,
            "n_events": self.n_events,
            "score_lsb": self.score_lsb,
            "calibration_block_id": self.calibration_block_id,
            "selection_rule": self.selection_rule,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class AcceptanceCertificate:
    certified: bool
    status: str
    quantity: str
    threshold_code: int
    count: int
    sample_size: int
    empirical_acceptance: float
    upper_acceptance: float
    target_acceptance: float
    alpha: float
    confidence: float
    score_lsb: float | None
    rate_lsb_hz: float | None
    point_rate_hz: float | None
    upper_rate_hz: float | None
    recorded_point_rate_hz: float | None
    recorded_upper_rate_hz: float | None
    input_rate_hz: float | None
    rate_budget_hz: float | None
    prescale: int
    calibration_block_id: str
    deployment_block_id: str
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    score_quantization: dict[str, Any] | None = None
    rate_quantization: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    prequantized_acceptance: float | None = None
    quantization_acceptance_delta: float | None = None

    def as_dict(self) -> dict[str, Any]:
        def clean(value: Any) -> Any:
            if isinstance(value, float) and not math.isfinite(value):
                return None
            if isinstance(value, dict):
                return {str(k): clean(v) for k, v in value.items()}
            if isinstance(value, (tuple, list)):
                return [clean(v) for v in value]
            return value

        payload = {
            "certified": self.certified,
            "status": self.status,
            "quantity": self.quantity,
            "threshold_code": self.threshold_code,
            "count": self.count,
            "sample_size": self.sample_size,
            "empirical_acceptance": self.empirical_acceptance,
            "upper_acceptance": self.upper_acceptance,
            "target_acceptance": self.target_acceptance,
            "alpha": self.alpha,
            "confidence": self.confidence,
            "score_lsb": self.score_lsb,
            "rate_lsb_hz": self.rate_lsb_hz,
            "point_rate_hz": self.point_rate_hz,
            "upper_rate_hz": self.upper_rate_hz,
            "recorded_point_rate_hz": self.recorded_point_rate_hz,
            "recorded_upper_rate_hz": self.recorded_upper_rate_hz,
            "input_rate_hz": self.input_rate_hz,
            "rate_budget_hz": self.rate_budget_hz,
            "prescale": self.prescale,
            "calibration_block_id": self.calibration_block_id,
            "deployment_block_id": self.deployment_block_id,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "score_quantization": self.score_quantization,
            "rate_quantization": self.rate_quantization,
            "provenance": self.provenance,
            "prequantized_acceptance": self.prequantized_acceptance,
            "quantization_acceptance_delta": self.quantization_acceptance_delta,
        }
        return clean(payload)


def binomial_upper_acceptance(count: int, n_events: int, alpha: float) -> float:
    """One-sided exact Clopper–Pearson upper limit using ``beta.isf``."""

    if isinstance(count, bool) or int(count) != count:
        raise ValueError("count must be an integer")
    if isinstance(n_events, bool) or int(n_events) != n_events or n_events < 1:
        raise ValueError("n_events must be a positive integer")
    if count < 0 or count > n_events:
        raise ValueError("count must satisfy 0 <= count <= n_events")
    try:
        alpha_value = float(alpha)
    except (TypeError, ValueError):
        raise ValueError("alpha must lie in (0, 1)") from None
    if not math.isfinite(alpha_value) or not 0 < alpha_value < 1:
        raise ValueError("alpha must lie in (0, 1)")
    # Same guard as the Poisson path: for alpha > 0.5 the Clopper-Pearson upper
    # limit can fall below the observed proportion, i.e. the reported "upper"
    # bound would understate the very quantity it bounds.  An upper confidence
    # bound must dominate the point estimate, so the declaration is refused.
    if alpha_value > 0.5:
        raise ValueError(
            "alpha must be <= 0.5: a one-sided limit with alpha > 0.5 lies at or "
            "below the point estimate and is not an upper bound"
        )
    if count == n_events:
        return 1.0
    # isf is numerically stable for stringent alpha where ppf(1-alpha)
    # rounds to one.
    return float(beta.isf(alpha_value, count + 1, n_events - count))


def choose_acceptance_threshold(
    calibration_scores: Any,
    *,
    target_acceptance: float,
    spec: FixedPointSpec,
    calibration_block_id: str = "calibration",
    selection_alpha: float | None = None,
) -> AcceptanceDecision:
    """Choose the lowest representable threshold below a target.

    When ``selection_alpha`` is supplied, the threshold is selected using a
    one-sided exact calibration-block upper bound.  This prevents the common
    mistake of selecting on an empirical tail and then discovering that the
    independent deployment bound misses the target.
    """

    try:
        target_value = float(target_acceptance)
    except (TypeError, ValueError):
        raise ValueError("target_acceptance must lie in (0, 1)") from None
    if not math.isfinite(target_value) or not 0 < target_value < 1:
        raise ValueError("target_acceptance must lie in (0, 1)")
    if not calibration_block_id:
        raise ValueError("calibration_block_id must be non-empty")
    if selection_alpha is not None:
        try:
            selection_alpha_value = float(selection_alpha)
        except (TypeError, ValueError):
            raise ValueError("selection_alpha must lie in (0, 1)") from None
        if not math.isfinite(selection_alpha_value) or not 0 < selection_alpha_value < 1:
            raise ValueError("selection_alpha must lie in (0, 1)")
    else:
        selection_alpha_value = None
    quantized = quantize_scores(calibration_scores, spec)
    codes = quantized.codes
    n_events = len(codes)
    if n_events < 1:
        raise ValueError("calibration block must be non-empty")
    # Attainable counts are built from a single sort plus a reverse cumulative
    # sum over the distinct codes, which is O(n log n).
    #
    # This replaced a loop that called np.count_nonzero(codes >= value) once per
    # distinct code, i.e. O(n * u) work.  At 100,000 events and a 16-bit format
    # (u ~ 65,000) that measured 14.1 s against 0.012 s for the cumulative form
    # -- about a thousand times slower -- and it contradicted the complexity
    # statement in the manuscript.  Duplicate codes are counted once by
    # np.unique, so the vectorised path is also numerically identical.
    unique_codes, multiplicity = np.unique(codes, return_counts=True)
    attainable = np.cumsum(multiplicity[::-1])[::-1]
    if selection_alpha_value is not None:
        criterion = np.array(
            [binomial_upper_acceptance(int(c), n_events, selection_alpha_value)
             for c in attainable],
            dtype=float,
        )
    else:
        criterion = attainable / n_events
    passing = unique_codes[criterion <= target_value]
    warnings: list[str] = []
    if passing.size:
        threshold = int(passing.min())
    else:
        threshold = spec.code_max + 1
        warnings.append("target requires the structural reject-all threshold above code_max")
    empirical = float(np.count_nonzero(codes >= threshold) / n_events)
    if quantized.saturation_count:
        warnings.append("calibration score saturation was observed")
    if selection_alpha is not None:
        warnings.append("threshold selected against a calibration Clopper-Pearson upper bound")
    return AcceptanceDecision(
        threshold_code=threshold,
        empirical_acceptance=empirical,
        target_acceptance=target_value,
        n_events=n_events,
        score_lsb=spec.lsb,
        calibration_block_id=calibration_block_id,
        selection_rule=(
            "clopper_pearson_upper_bound"
            if selection_alpha_value is not None
            else "empirical_tail"
        ),
        warnings=tuple(warnings),
    )


def quantization_acceptance_diagnostics(
    scores: Any,
    *,
    spec: FixedPointSpec,
) -> dict[str, float | int]:
    """Measure score-quantization changes over every observed code threshold.

    The returned difference compares the quantized rule ``code >= q`` with the
    unquantized diagnostic rule ``score >= q * lsb``.  It is descriptive only:
    without a distributional assumption it is not a confidence bound.
    """

    raw = np.asarray(scores, dtype=float)
    if raw.ndim != 1 or raw.size == 0 or not np.all(np.isfinite(raw)):
        raise ValueError("scores must be a non-empty finite one-dimensional array")
    quantized = quantize_scores(raw, spec)
    codes = quantized.codes
    # Only codes that actually occur can be thresholds, so the histogram is built
    # over the O(u) distinct codes rather than over the full code range.
    #
    # This replaced np.bincount(codes - code_min, minlength=code_range), which
    # allocates 8 bytes per representable code: a 32-bit format demanded 34 GB
    # for a three-element input.  The memory now scales with the number of
    # distinct observed codes, and the result is identical because
    # np.unique(..., return_counts=True) with a reverse cumsum reproduces the
    # same attainable-count curve.
    thresholds, multiplicity = np.unique(codes, return_counts=True)
    q_counts = np.cumsum(multiplicity[::-1])[::-1]
    sorted_raw = np.sort(raw)
    raw_counts = raw.size - np.searchsorted(sorted_raw, thresholds * spec.lsb, side="left")
    deltas = (q_counts - raw_counts) / raw.size
    index = int(np.argmax(np.abs(deltas)))
    return {
        "max_abs_acceptance_delta": float(abs(deltas[index])),
        "signed_acceptance_delta_at_max": float(deltas[index]),
        "threshold_code_at_max": int(thresholds[index]),
        "threshold_value_at_max": float(thresholds[index] * spec.lsb),
        "thresholds_evaluated": int(len(thresholds)),
    }


def certify_acceptance(
    deployment_scores: Any,
    *,
    threshold_code: int,
    target_acceptance: float,
    alpha: float,
    spec: FixedPointSpec,
    deployment_block_id: str,
    calibration_block_id: str,
    input_rate_hz: float | None = None,
    rate_budget_hz: float | None = None,
    rate_spec: RateQuantizationSpec | None = None,
    prescale: int = 1,
    provenance: dict[str, Any] | None = None,
) -> AcceptanceCertificate:
    """Certify a fixed threshold on an independent finite event block.

    With no ``input_rate_hz`` the theorem is about acceptance probability only.
    If a flux, rate budget, and rate quantization declaration are all supplied,
    the same binomial upper bound is converted to raw/recorded Hz and checked
    against that budget.
    """

    reasons: list[str] = []
    warnings: list[str] = []
    score_q: dict[str, Any] | None = None
    rate_q: dict[str, Any] | None = None
    try:
        target_value = float(target_acceptance)
        alpha_value = float(alpha)
        if not math.isfinite(target_value) or not 0 < target_value < 1:
            raise ValueError
        if not math.isfinite(alpha_value) or not 0 < alpha_value < 1:
            raise ValueError
    except (TypeError, ValueError):
        target_value = math.nan
        alpha_value = math.nan
        reasons.append("target_acceptance and alpha must be finite values in (0, 1)")
    if not calibration_block_id or not deployment_block_id:
        reasons.append("calibration and deployment block ids must be non-empty")
    if calibration_block_id == deployment_block_id:
        reasons.append("calibration and deployment blocks overlap by identity")
    try:
        if isinstance(threshold_code, bool) or int(threshold_code) != threshold_code:
            raise ValueError
        threshold = int(threshold_code)
    except (TypeError, ValueError):
        threshold = 0
        reasons.append("threshold_code must be an integer")
    try:
        if isinstance(prescale, bool) or int(prescale) != prescale or prescale < 1:
            raise ValueError
        prescale_i = int(prescale)
    except (TypeError, ValueError):
        prescale_i = 0
        reasons.append("prescale must be a positive integer")
    if input_rate_hz is not None:
        try:
            input_rate = float(input_rate_hz)
            if not math.isfinite(input_rate) or input_rate <= 0:
                raise ValueError
        except (TypeError, ValueError):
            input_rate = math.nan
            reasons.append("input_rate_hz must be positive and finite")
    else:
        input_rate = math.nan
        warnings.append(
            "no live-time or input flux supplied: this certificate is an acceptance probability, not a detector Hz measurement"
        )
    if rate_budget_hz is not None:
        try:
            budget = float(rate_budget_hz)
            if not math.isfinite(budget) or budget <= 0:
                raise ValueError
        except (TypeError, ValueError):
            budget = math.nan
            reasons.append("rate_budget_hz must be positive and finite")
    else:
        budget = math.nan
    if input_rate_hz is not None or rate_budget_hz is not None:
        if rate_spec is None:
            reasons.append("rate_spec is required when an absolute rate is requested")
        else:
            rate_q = rate_spec.as_dict()
    if input_rate_hz is not None and rate_budget_hz is None:
        reasons.append("rate_budget_hz is required when input_rate_hz is supplied")
    if rate_budget_hz is not None and input_rate_hz is None:
        reasons.append("input_rate_hz is required when rate_budget_hz is supplied")
    raw_scores: np.ndarray | None = None
    try:
        raw_scores = np.asarray(deployment_scores, dtype=float)
        if raw_scores.ndim != 1 or raw_scores.size == 0 or not np.all(np.isfinite(raw_scores)):
            raise ValueError("score stream must be a non-empty finite one-dimensional array")
    except (TypeError, ValueError):
        raw_scores = None
    try:
        quantized = quantize_scores(deployment_scores, spec)
        score_q = {
            "spec": spec.as_dict(),
            "n_scores": int(len(quantized.codes)),
            "saturation_count": int(quantized.saturation_count),
            "max_abs_error": float(quantized.max_abs_error),
            "error_bound": None if not math.isfinite(quantized.error_bound) else float(quantized.error_bound),
        }
    except (TypeError, ValueError) as exc:
        quantized = None
        reasons.append(f"invalid score stream: {exc}")
    prequantized = None
    q_delta = None
    if quantized is None:
        n_events = 0
        count = 0
        empirical = math.nan
        upper = math.inf
        score_lsb: float | None = None
    else:
        n_events = int(len(quantized.codes))
        count = int(np.count_nonzero(quantized.codes >= threshold))
        empirical = count / n_events
        try:
            upper = binomial_upper_acceptance(count, n_events, alpha_value)
        except ValueError as exc:
            upper = math.inf
            reasons.append(str(exc))
        score_lsb = float(spec.lsb)
        if raw_scores is not None:
            prequantized = float(np.count_nonzero(raw_scores >= threshold * spec.lsb) / n_events)
            q_delta = float(empirical - prequantized)
            score_q["threshold_value"] = float(threshold * spec.lsb)
            score_q["prequantized_acceptance_at_threshold"] = prequantized
            score_q["quantization_acceptance_delta"] = q_delta
        if quantized.saturation_count:
            reasons.append("score quantization saturated deployment values")
    if n_events == 0:
        reasons.append("deployment block must be non-empty")
    point_rate = upper_rate = recorded_point = recorded_upper = None
    rate_lsb = None if rate_spec is None else float(rate_spec.lsb_hz)
    if input_rate_hz is not None and math.isfinite(input_rate):
        point_rate = float(input_rate * empirical)
        upper_rate = float(input_rate * upper)
        if prescale_i > 0:
            recorded_point = point_rate / prescale_i
            recorded_upper = upper_rate / prescale_i
        if rate_spec is not None and math.isfinite(upper_rate):
            # The documented contract is that the NUMERICAL quantity enters the
            # pass condition, which means the counter RANGE as well as the
            # rounding margin.  This path previously applied only the budget
            # clause, so the same physics could be certified here and refused by
            # certify_rate: a 4-bit counter at a 0.1 Hz LSB has a full scale of
            # 1.5 Hz, yet an upper rate of 6.2e4 Hz came back CERTIFIED with an
            # empty reason list.  Both entry points must agree, so the counter
            # full-scale and count-overflow clauses are applied here in the same
            # form as in certify_rate.
            if (n_events > 0 and rate_spec.max_count is not None
                    and count > rate_spec.max_count):
                reasons.append(
                    f"rate counter overflow: count {count} exceeds {rate_spec.max_count}"
                )
            if (rate_spec.max_rate_hz is not None
                    and upper_rate > rate_spec.max_rate_hz):
                reasons.append(
                    "finite-sample upper rate exceeds the declared rate-counter full scale"
                )
            if budget + 1e-15 < upper_rate + rate_spec.error_bound_hz:
                reasons.append("finite-sample upper rate plus fixed-point rate margin exceeds budget")
    elif rate_spec is not None and input_rate_hz is None:
        warnings.append("rate resolution is recorded as a declaration but cannot be applied without input flux")
    if math.isfinite(upper) and math.isfinite(target_value) and upper > target_value + 1e-15:
        reasons.append("finite-sample upper acceptance exceeds target_acceptance")
    certified = not reasons
    return AcceptanceCertificate(
        certified=certified,
        status="CERTIFIED" if certified else "NOT_CERTIFIED",
        quantity="background_acceptance_probability",
        threshold_code=threshold,
        count=count,
        sample_size=n_events,
        empirical_acceptance=float(empirical),
        upper_acceptance=float(upper),
        target_acceptance=target_value,
        alpha=alpha_value,
        confidence=float(1.0 - alpha_value) if math.isfinite(alpha_value) else math.nan,
        score_lsb=score_lsb,
        rate_lsb_hz=rate_lsb,
        point_rate_hz=point_rate,
        upper_rate_hz=upper_rate,
        recorded_point_rate_hz=recorded_point,
        recorded_upper_rate_hz=recorded_upper,
        input_rate_hz=None if not math.isfinite(input_rate) else input_rate,
        rate_budget_hz=None if not math.isfinite(budget) else budget,
        prescale=prescale_i,
        calibration_block_id=calibration_block_id,
        deployment_block_id=deployment_block_id,
        reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
        score_quantization=score_q,
        rate_quantization=rate_q,
        provenance=provenance,
        prequantized_acceptance=prequantized,
        quantization_acceptance_delta=q_delta,
    )
