"""Model-agnostic rate certification primitives.

The prototype deliberately works on a caller-supplied score stream.  It does
not train or define a trigger model.  A certificate is about the declared
quantized deployment score and an independent finite exposure block.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Literal, Sequence

import numpy as np
from scipy.stats import chi2


Rounding = Literal["nearest_even", "floor", "trunc"]
Saturation = Literal["error", "saturate"]


@dataclass(frozen=True)
class FixedPointSpec:
    """Bit-exact fixed-point contract for a scalar score.

    ``value = code * 2**(-fractional_bits)``.  ``nearest_even`` delegates
    tie handling to NumPy's documented round-to-even operation.  Saturation is
    explicit: strict certification rejects an out-of-range value unless the
    caller opts into ``saturate``.
    """

    bits: int
    fractional_bits: int
    signed: bool = False
    rounding: Rounding = "nearest_even"
    saturation: Saturation = "error"

    def __post_init__(self) -> None:
        if self.bits < 1:
            raise ValueError("bits must be >= 1")
        if not 0 <= self.fractional_bits <= self.bits - int(self.signed):
            raise ValueError("fractional_bits is incompatible with bits/signed")
        if self.rounding not in {"nearest_even", "floor", "trunc"}:
            raise ValueError("unsupported rounding mode")
        if self.saturation not in {"error", "saturate"}:
            raise ValueError("unsupported saturation mode")

    @property
    def lsb(self) -> float:
        return 2.0 ** (-self.fractional_bits)

    @property
    def code_min(self) -> int:
        return -(2 ** (self.bits - 1)) if self.signed else 0

    @property
    def code_max(self) -> int:
        return (2 ** (self.bits - 1) - 1) if self.signed else (2**self.bits - 1)

    def as_dict(self) -> dict[str, object]:
        return asdict(self) | {
            "lsb": self.lsb,
            "code_min": self.code_min,
            "code_max": self.code_max,
        }


@dataclass(frozen=True)
class RateQuantizationSpec:
    """Deterministic fixed-point representation of the reported rate.

    ``lsb_hz`` comes from the deployment counter or firmware rate register.
    It is deliberately never inferred from an observed score histogram.
    """

    lsb_hz: float
    rounding: Rounding = "nearest_even"
    counter_bits: int | None = None
    signed: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.lsb_hz) or self.lsb_hz <= 0:
            raise ValueError("lsb_hz must be positive and finite")
        if self.rounding not in {"nearest_even", "floor", "trunc"}:
            raise ValueError("unsupported rate rounding mode")
        if self.counter_bits is not None:
            if self.counter_bits < 1:
                raise ValueError("counter_bits must be >= 1")
            if self.signed:
                raise ValueError("rate counters must be unsigned")

    @property
    def error_bound_hz(self) -> float:
        return self.lsb_hz / 2.0 if self.rounding == "nearest_even" else self.lsb_hz

    @property
    def max_count(self) -> int | None:
        return (2**self.counter_bits - 1) if self.counter_bits is not None else None

    @property
    def max_rate_hz(self) -> float | None:
        return self.max_count * self.lsb_hz if self.max_count is not None else None

    @classmethod
    def from_counter_window(
        cls,
        exposure_s: float,
        rounding: Rounding = "nearest_even",
        counter_bits: int | None = None,
    ) -> "RateQuantizationSpec":
        """Derive the exact count-per-window rate LSB, ``1 / exposure_s``."""

        if not math.isfinite(exposure_s) or exposure_s <= 0:
            raise ValueError("exposure_s must be positive and finite")
        return cls(
            lsb_hz=1.0 / exposure_s,
            rounding=rounding,
            counter_bits=counter_bits,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "lsb_hz": self.lsb_hz,
            "rounding": self.rounding,
            "error_bound_hz": self.error_bound_hz,
            "counter_bits": self.counter_bits,
            "signed": self.signed,
            "max_count": self.max_count,
            "max_rate_hz": self.max_rate_hz,
        }


@dataclass(frozen=True)
class QuantizedScores:
    codes: np.ndarray
    saturation_count: int
    max_abs_error: float
    error_bound: float

    def as_dict(self) -> dict[str, object]:
        return {
            "saturation_count": self.saturation_count,
            "max_abs_error": self.max_abs_error,
            "error_bound": self.error_bound,
            "n_scores": int(self.codes.size),
        }


@dataclass(frozen=True)
class CalibrationDecision:
    threshold_code: int
    empirical_rate_hz: float
    target_rate_hz: float
    n_events: int
    exposure_s: float
    quantization: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Certificate:
    """Serializable result of one independent deployment-block audit."""

    certified: bool
    status: str
    deployment_block_id: str
    calibration_block_id: str
    threshold_code: int
    count: int
    exposure_s: float
    point_rate_hz: float
    recorded_point_rate_hz: float
    upper_rate_hz: float
    recorded_upper_rate_hz: float
    alpha: float
    rate_budget_hz: float
    rate_resolution_hz: float | None
    observed_rate_step_hz: float | None
    quantization_margin_hz: float | None
    deployment_margin_hz: float | None
    deployment_score: float | None
    prescale: int
    fixed_point: dict[str, object]
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        result["warnings"] = list(self.warnings)
        def json_safe(value: object) -> object:
            if isinstance(value, float) and not math.isfinite(value):
                return None
            if isinstance(value, dict):
                return {key: json_safe(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [json_safe(item) for item in value]
            return value

        return json_safe(result)


def _as_finite_scores(scores: Sequence[float] | np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1:
        raise ValueError("scores must be a one-dimensional sequence")
    if values.size == 0:
        raise ValueError("scores must not be empty")
    if not np.all(np.isfinite(values)):
        raise ValueError("scores must contain only finite values")
    return values


def quantize_scores(
    scores: Sequence[float] | np.ndarray, spec: FixedPointSpec
) -> QuantizedScores:
    """Return integer deployment codes and a deterministic error bound."""

    values = _as_finite_scores(scores)
    scaled = values / spec.lsb
    if spec.rounding == "nearest_even":
        raw = np.rint(scaled)
        error_bound = spec.lsb / 2.0
    elif spec.rounding == "floor":
        raw = np.floor(scaled)
        error_bound = spec.lsb
    else:
        raw = np.trunc(scaled)
        error_bound = spec.lsb

    outside = (raw < spec.code_min) | (raw > spec.code_max)
    saturation_count = int(np.count_nonzero(outside))
    if saturation_count and spec.saturation == "error":
        raise ValueError(
            f"{saturation_count} score(s) exceed fixed-point range "
            f"[{spec.code_min}, {spec.code_max}]"
        )
    codes = np.clip(raw, spec.code_min, spec.code_max).astype(np.int64)
    dequantized = codes.astype(float) * spec.lsb
    max_abs_error = float(np.max(np.abs(values - dequantized)))
    if saturation_count:
        # A range-clipped value has no finite lsb-only error guarantee.
        error_bound = math.inf
    return QuantizedScores(codes, saturation_count, max_abs_error, error_bound)


def poisson_upper_rate(count: int, exposure_s: float, alpha: float) -> float:
    """Exact one-sided Poisson upper confidence bound in Hz.

    For an observed count ``N`` in exposure ``T``, the bound is
    ``0.5 * chi2.isf(alpha, 2*(N+1)) / T``.  The coverage statement is
    conditional on a Poisson count model and a threshold fixed independently
    of this deployment block.
    """

    if int(count) != count or count < 0:
        raise ValueError("count must be a non-negative integer")
    if not math.isfinite(exposure_s) or exposure_s <= 0:
        raise ValueError("exposure_s must be positive and finite")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    # ``isf`` avoids loss of precision when alpha is very small after a
    # family-wise correction over many benchmark cells.
    return float(0.5 * chi2.isf(alpha, 2 * (int(count) + 1)) / exposure_s)


def rate_curve(codes: Sequence[int] | np.ndarray, exposure_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Return attainable deterministic rates for every observed code threshold."""

    values = np.asarray(codes, dtype=np.int64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("codes must be a non-empty one-dimensional sequence")
    if exposure_s <= 0 or not math.isfinite(exposure_s):
        raise ValueError("exposure_s must be positive and finite")
    # ``np.unique`` returns sorted values and their multiplicities.  Building
    # the cumulative tail from those multiplicities avoids scanning the full
    # score stream once per threshold (which is quadratic in the number of
    # distinct codes for a dense fixed-point stream).
    thresholds, counts = np.unique(values, return_counts=True)
    rates = np.cumsum(counts[::-1])[::-1].astype(float) / exposure_s
    return thresholds, rates


def _rate_resolution(codes: np.ndarray, exposure_s: float) -> float | None:
    _, rates = rate_curve(codes, exposure_s)
    if rates.size < 2:
        return None
    # Thresholds are sorted from low to high, so attainable rates are
    # non-increasing.  Resolution is the magnitude of the smallest positive
    # jump, independent of traversal direction.
    gaps = np.abs(np.diff(rates))
    positive = gaps[gaps > 0]
    return float(np.min(positive)) if positive.size else None


def choose_threshold(
    calibration_scores: Sequence[float] | np.ndarray,
    *,
    exposure_s: float,
    target_rate_hz: float,
    spec: FixedPointSpec,
) -> CalibrationDecision:
    """Choose the lowest observed code whose calibration rate fits the target.

    Lower codes accept more events, so this choice maximises acceptance subject
    to the calibration-block target.  If no observed code fits, the first code
    above the representable range is returned, which is an explicit zero-rate
    fallback rather than an accidental over-budget deployment.
    """

    if target_rate_hz <= 0 or not math.isfinite(target_rate_hz):
        raise ValueError("target_rate_hz must be positive and finite")
    quantized = quantize_scores(calibration_scores, spec)
    thresholds, rates = rate_curve(quantized.codes, exposure_s)
    valid = np.flatnonzero(rates <= target_rate_hz)
    if valid.size:
        # thresholds are ascending; the first valid one maximises acceptance.
        selected = int(valid[0])
        threshold_code = int(thresholds[selected])
        empirical_rate_hz = float(rates[selected])
    else:
        threshold_code = spec.code_max + 1
        empirical_rate_hz = 0.0
    return CalibrationDecision(
        threshold_code=threshold_code,
        empirical_rate_hz=empirical_rate_hz,
        target_rate_hz=float(target_rate_hz),
        n_events=int(quantized.codes.size),
        exposure_s=float(exposure_s),
        quantization=quantized.as_dict() | {"spec": spec.as_dict()},
    )


def certify_rate(
    deployment_scores: Sequence[float] | np.ndarray,
    *,
    exposure_s: float,
    threshold_code: int,
    rate_budget_hz: float,
    alpha: float,
    spec: FixedPointSpec,
    rate_spec: RateQuantizationSpec | None,
    deployment_block_id: str,
    calibration_block_id: str,
    prescale: int = 1,
) -> Certificate:
    """Compose finite-sample and fixed-point checks into one certificate.

    The Poisson upper bound is the statistical part.  The rate fixed-point
    part is explicit and deterministic: ``rate_spec.lsb_hz`` comes from the
    deployment counter or firmware rate register, and its rounding error is
    reserved as the configuration margin.  The observed score-threshold step
    is retained as a diagnostic only and cannot make a certificate pass.
    """

    reasons: list[str] = []
    warnings: list[str] = []
    # Invalid numeric metadata must produce a structured refusal, never a
    # division-by-zero exception while constructing the refusal itself.
    def finite_or_nan(value: object) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError, OverflowError):
            return math.nan
        return converted if math.isfinite(converted) else math.nan

    exposure_s = finite_or_nan(exposure_s)
    rate_budget_hz = finite_or_nan(rate_budget_hz)
    alpha = finite_or_nan(alpha)
    raw_threshold = finite_or_nan(threshold_code)
    threshold_valid = math.isfinite(raw_threshold) and raw_threshold.is_integer()
    threshold_code = int(raw_threshold) if threshold_valid else 0
    raw_prescale = finite_or_nan(prescale)
    prescale_valid = (
        math.isfinite(raw_prescale) and raw_prescale >= 1 and raw_prescale.is_integer()
    )
    prescale = int(raw_prescale) if prescale_valid else 0
    budget_valid = math.isfinite(rate_budget_hz) and rate_budget_hz > 0
    if not deployment_block_id:
        reasons.append("missing deployment_block_id")
    if not calibration_block_id:
        reasons.append("missing calibration_block_id")
    if deployment_block_id and calibration_block_id and deployment_block_id == calibration_block_id:
        reasons.append("calibration and deployment blocks overlap by identity")
    if not threshold_valid:
        reasons.append("threshold_code must be an integer")
    if not budget_valid:
        reasons.append("rate_budget_hz must be positive and finite")
    if not prescale_valid:
        reasons.append("prescale must be a positive integer")
    if rate_spec is None:
        reasons.append("missing deterministic rate resolution spec")

    try:
        quantized = quantize_scores(deployment_scores, spec)
    except (TypeError, ValueError) as exc:
        reasons.append(f"invalid score stream: {exc}")
        # Keep the result structured even for malformed input.
        return Certificate(
            certified=False,
            status="NOT_CERTIFIED",
            deployment_block_id=deployment_block_id,
            calibration_block_id=calibration_block_id,
            threshold_code=int(threshold_code),
            count=0,
            exposure_s=float(exposure_s) if math.isfinite(exposure_s) else 0.0,
            point_rate_hz=math.nan,
            recorded_point_rate_hz=math.nan,
            upper_rate_hz=math.inf,
            recorded_upper_rate_hz=math.inf,
            alpha=float(alpha),
            rate_budget_hz=float(rate_budget_hz),
            rate_resolution_hz=None,
            observed_rate_step_hz=None,
            quantization_margin_hz=None,
            deployment_margin_hz=None,
            deployment_score=None,
            prescale=int(prescale) if int(prescale) == prescale else 0,
            fixed_point={
                "score_spec": spec.as_dict(),
                "rate_spec": rate_spec.as_dict() if rate_spec is not None else None,
            },
            reasons=tuple(reasons),
            warnings=tuple(warnings),
        )

    count = int(np.count_nonzero(quantized.codes >= int(threshold_code)))
    if rate_spec is not None and rate_spec.max_count is not None and count > rate_spec.max_count:
        reasons.append(
            f"rate counter overflow: count {count} exceeds {rate_spec.max_count}"
        )
    point_rate = count / exposure_s if exposure_s > 0 and math.isfinite(exposure_s) else math.nan
    try:
        upper_rate = poisson_upper_rate(count, exposure_s, alpha)
    except ValueError as exc:
        reasons.append(str(exc))
        upper_rate = math.inf
    if (
        rate_spec is not None
        and rate_spec.max_rate_hz is not None
        and math.isfinite(upper_rate)
        and upper_rate > rate_spec.max_rate_hz
    ):
        reasons.append(
            "finite-sample upper rate exceeds the declared rate-counter full scale"
        )
    observed_step = None
    if math.isfinite(exposure_s) and exposure_s > 0:
        observed_step = _rate_resolution(quantized.codes, exposure_s)
    if observed_step is None:
        warnings.append("fewer than two observed score levels; observed threshold step unavailable")
    else:
        warnings.append(
            "observed threshold step is diagnostic; deterministic rate LSB is used for certification"
        )
    if quantized.saturation_count:
        reasons.append("score saturation occurred")
    if quantized.error_bound == math.inf:
        reasons.append("fixed-point error bound is unbounded after saturation")
    deterministic_resolution = rate_spec.lsb_hz if rate_spec is not None else None
    quantization_margin = rate_spec.error_bound_hz if rate_spec is not None else None
    if rate_spec is not None and math.isfinite(upper_rate) and budget_valid:
        margin = rate_budget_hz - upper_rate - quantization_margin
    else:
        margin = None
    if margin is not None and margin < 0:
        reasons.append("finite-sample upper rate plus fixed-point margin exceeds budget")

    certified = not reasons
    deployment_score = margin / rate_budget_hz if margin is not None else None
    return Certificate(
        certified=certified,
        status="CERTIFIED" if certified else "NOT_CERTIFIED",
        deployment_block_id=deployment_block_id,
        calibration_block_id=calibration_block_id,
        threshold_code=int(threshold_code),
        count=count,
        exposure_s=float(exposure_s),
        point_rate_hz=float(point_rate),
        recorded_point_rate_hz=float(point_rate / prescale) if prescale_valid else math.nan,
        upper_rate_hz=float(upper_rate),
        recorded_upper_rate_hz=float(upper_rate / prescale) if prescale_valid else math.nan,
        alpha=float(alpha),
        rate_budget_hz=float(rate_budget_hz),
        rate_resolution_hz=deterministic_resolution,
        observed_rate_step_hz=observed_step,
        quantization_margin_hz=quantization_margin,
        deployment_margin_hz=float(margin) if margin is not None else None,
        deployment_score=float(deployment_score) if deployment_score is not None else None,
        prescale=int(prescale),
        fixed_point=quantized.as_dict()
        | {"score_spec": spec.as_dict()}
        | {"rate_spec": rate_spec.as_dict() if rate_spec is not None else None},
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )
