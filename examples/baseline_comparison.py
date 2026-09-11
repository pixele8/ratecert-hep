"""Quantitative baseline comparison for RateCert-HEP.

Motivation
----------
The manuscript previously asserted that the exact one-sided bounds are
preferable but never measured the alternatives.  This script supplies that
measurement by (a) applying standard upper-bound constructions to the *same*
27-cell public benchmark and (b) measuring empirical coverage of each
construction against a known ground-truth acceptance probability.

Four constructions are compared:

  naive_empirical     U = K/n                       (no uncertainty at all)
  normal_approx       U = p_hat + z_{1-alpha} * sqrt(p_hat(1-p_hat)/n)
  wilson              one-sided Wilson score interval
  clopper_pearson     U = Beta^{-1}(1-alpha; K+1, n-K)   (this work)

`naive_empirical` and `normal_approx` are the two practices the paper argues
against; they are included so the argument is quantitative rather than
rhetorical.  `wilson` is a serious competitor and is included for honesty.

Outputs a JSON report; the paper cites the numbers, not this script's prose.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import beta, norm

REPO = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# Upper-bound constructions
# --------------------------------------------------------------------------
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


def upper_naive_empirical(k: int, n: int, alpha: float) -> float:
    """Empirical tail reported as if it were the true acceptance probability."""
    return k / n


def upper_normal_approx(k: int, n: int, alpha: float) -> float:
    """One-sided normal (Wald) upper bound."""
    p = k / n
    z = norm.ppf(1.0 - alpha)
    return p + z * math.sqrt(max(p * (1.0 - p), 0.0) / n)


def upper_wilson(k: int, n: int, alpha: float) -> float:
    """One-sided Wilson score upper bound."""
    z = norm.ppf(1.0 - alpha)
    z2 = z * z
    p = k / n
    denom = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    halfwidth = z * math.sqrt(max(p * (1.0 - p) / n + z2 / (4.0 * n * n), 0.0))
    return (centre + halfwidth) / denom


def upper_clopper_pearson(k: int, n: int, alpha: float) -> float:
    """Exact one-sided Clopper-Pearson upper bound (survival-function form)."""
    if k >= n:
        # Incomplete beta degenerates when the second shape parameter is zero.
        return 1.0
    return float(beta.ppf(1.0 - alpha, k + 1, n - k))


METHODS = {
    "naive_empirical": upper_naive_empirical,
    "normal_approx": upper_normal_approx,
    "wilson": upper_wilson,
    "clopper_pearson": upper_clopper_pearson,
}


# --------------------------------------------------------------------------
# Part A: apply every method to the real 27-cell public benchmark
# --------------------------------------------------------------------------
def compare_on_public_cells() -> dict:
    src = REPO / "reports" / "public_lhco_acceptance.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    alpha_cell = data["per_cell_alpha"]

    rows = []
    for cell in data["cells"]:
        k = int(cell["count"])
        n = int(cell["sample_size"])
        target = float(cell["target_acceptance"])
        row = {
            "bits": cell["bits"],
            "sample_size": n,
            "target_acceptance": target,
            "count": k,
        }
        for name, fn in METHODS.items():
            upper = fn(k, n, alpha_cell)
            row[name] = upper
            row[name + "_certified"] = bool(upper < target)
        rows.append(row)

    totals = {
        name: sum(1 for r in rows if r[name + "_certified"]) for name in METHODS
    }

    return {
        "per_cell_alpha": alpha_cell,
        "cells": rows,
        "certified_counts": totals,
        "n_cells": len(rows),
        "note": (
            "All four constructions are applied to the identical deployment "
            "counts from the checked-in 27-cell benchmark, at the same per-cell "
            "alpha. Only the bound construction differs."
        ),
    }


# --------------------------------------------------------------------------
# Part B: empirical coverage against a known ground-truth p
# --------------------------------------------------------------------------
def measure_coverage(repeats: int = 20000, seed: int = 20260912) -> dict:
    """Fraction of repetitions in which each bound actually covers true p.

    A valid 1-alpha upper bound must satisfy Pr(U >= p) >= 1-alpha.  We measure
    how often U >= p over binomial draws with known p, at several (n, p).
    """
    settings = [
        (1000, 0.005),
        (10000, 0.005),
        (10000, 0.01),
        (100000, 0.01),
    ]
    alpha = 0.01 / 27  # the per-cell alpha used by the public sweep
    rng = np.random.default_rng(seed)

    out = []
    for n, p in settings:
        k = rng.binomial(n, p, size=repeats)
        entry = {"n": n, "true_p": p, "repeats": repeats, "nominal_coverage": 1 - alpha}
        for name, fn in METHODS.items():
            covered = sum(1 for kk in k if fn(int(kk), n, alpha) >= p)
            entry[name + "_coverage"] = covered / repeats
        out.append(entry)

    return {
        "per_cell_alpha": alpha,
        "nominal_coverage": 1.0 - alpha,
        "settings": out,
        "seed": seed,
        "note": (
            "Empirical coverage of the true acceptance probability. A valid "
            "one-sided 1-alpha bound must reach the nominal coverage; failure to "
            "do so is under-coverage and means real operating points can be "
            "certified that should not be."
        ),
    }


def main() -> int:
    report = {
        "study": "RateCert-HEP baseline comparison",
        "part_a_public_cells": compare_on_public_cells(),
        "part_b_coverage": measure_coverage(),
    }

    out_dir = REPO / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "baseline_comparison.json"
    _write_text_lf(out, json.dumps(report, indent=2) + "\n")

    # ---- console summary -------------------------------------------------
    a = report["part_a_public_cells"]
    print("=" * 68)
    print("PART A: same 27 deployment cells, four bound constructions")
    print("=" * 68)
    print("  per-cell alpha = %.10g" % a["per_cell_alpha"])
    print()
    print("  %-20s %s" % ("method", "cells certified (of 27)"))
    for name in METHODS:
        print("  %-20s %d" % (name, a["certified_counts"][name]))
    print()
    print("  %-6s %-8s %-6s %-9s %s" % ("bits", "n", "K", "target", "upper by method"))
    for r in a["cells"]:
        print(
            "  %-6d %-8d %-6d %-9.4g cp=%.6f  wilson=%.6f  normal=%.6f  naive=%.6f"
            % (
                r["bits"], r["sample_size"], r["count"], r["target_acceptance"],
                r["clopper_pearson"], r["wilson"], r["normal_approx"],
                r["naive_empirical"],
            )
        )

    b = report["part_b_coverage"]
    print()
    print("=" * 68)
    print("PART B: empirical coverage vs ground truth (nominal %.7f)" % b["nominal_coverage"])
    print("=" * 68)
    print("  %-9s %-9s %-14s %-11s %-11s %s" % ("n", "true_p", "clopper_pearson", "wilson", "normal", "naive"))
    for s in b["settings"]:
        print(
            "  %-9d %-9.4g %-14.6f %-11.6f %-11.6f %.6f"
            % (s["n"], s["true_p"], s["clopper_pearson_coverage"], s["wilson_coverage"],
               s["normal_approx_coverage"], s["naive_empirical_coverage"])
        )
    print()
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
