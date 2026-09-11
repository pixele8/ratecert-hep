"""Small, explicit core for RateCert-HEP certification experiments."""

from .core import (
    CalibrationDecision,
    Certificate,
    FixedPointSpec,
    RateQuantizationSpec,
    QuantizedScores,
    choose_threshold,
    certify_rate,
    poisson_upper_rate,
    quantize_scores,
    rate_curve,
)
from .acceptance import (
    AcceptanceCertificate,
    AcceptanceDecision,
    binomial_upper_acceptance,
    certify_acceptance,
    choose_acceptance_threshold,
    quantization_acceptance_diagnostics,
)
from .public_data import (
    LHCOSplit,
    event_id_sha256,
    fixed_point_for_lhco,
    load_lhco_background_split,
)

__all__ = [
    "CalibrationDecision",
    "Certificate",
    "FixedPointSpec",
    "RateQuantizationSpec",
    "QuantizedScores",
    "choose_threshold",
    "certify_rate",
    "poisson_upper_rate",
    "quantize_scores",
    "rate_curve",
    "AcceptanceCertificate",
    "AcceptanceDecision",
    "binomial_upper_acceptance",
    "certify_acceptance",
    "choose_acceptance_threshold",
    "quantization_acceptance_diagnostics",
    "LHCOSplit",
    "event_id_sha256",
    "fixed_point_for_lhco",
    "load_lhco_background_split",
]
