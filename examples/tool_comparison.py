"""Compare the exact one-sided Poisson limit against a published construction.

Our own tool computes the exact one-sided Poisson upper limit
    U_alpha(N,T) = chi2.isf(alpha, 2(N+1)) / (2T),
the Garwood / Clopper-Pearson construction.  This script compares it with the
**profile-likelihood** construction of Rolke, Lopez and Conrad
(Nucl. Instrum. Meth. A 551 (2005) 493) as implemented by TRolke 2.0
(Lundberg et al., Comput. Phys. Commun. 181 (2010) 683-686), reimplemented here
directly from the published method because ROOT/TRolke has no Windows wheel.

WHAT THIS IS AND IS NOT
-----------------------
This is a SELF-CONSISTENCY check, not independent validation.  The
reimplementation is ours, it lives in this file, and it uses the same scipy
quantile routine as the exact limit; the script never imports `ratecert`, so the
package under test is not executed by it at all.  What the comparison does show
is that the two constructions are the same limit asymptotically, which is the
behaviour a correct transcription of the closed form must exhibit and which a
transcription error would destroy.

A CLs COLUMN WAS WITHDRAWN
--------------------------
An earlier revision of this script also computed a pyhf CLs limit and placed it
beside the exact limit.  That comparison was not apples-to-apples -- CLs bounds a
signal strength in a model that already contains background while the exact limit
bounds a total rate, so the two columns reported different parameters -- and pyhf
defaults to an asymptotic formula that is least reliable at the low counts where
the comparison was most interesting.  A reader who wants it should fix the model,
state the computational type, and quote both parameters explicitly.  Withdrawing
it also removed a silent-failure path: the old code caught the pyhf import error
and rewrote its report with null substitutions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import chi2, norm

REPO = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# our method
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


def exact_one_sided_poisson(n_obs: int, exposure: float, alpha: float) -> float:
    """Exact one-sided Poisson upper limit on the rate lambda."""
    return float(chi2.isf(alpha, 2 * (n_obs + 1)) / (2.0 * exposure))


# --------------------------------------------------------------------------
# TRolke-style profile likelihood, for a Poisson count with no background
# --------------------------------------------------------------------------
def profile_likelihood_upper(n_obs: int, exposure: float, alpha: float) -> float | None:
    """Upper limit on the rate from the profile-likelihood ratio (PDG form).

    For a single Poisson rate with observed count n and exposure T, writing
    mu = lambda*T, the profile-likelihood ratio is

        -2 ln L(lambda)/L(lam_hat) = 2[ mu - n - n ln(mu/n) ]        (n >= 1)

    which is zero at the maximum-likelihood mu_hat = n and strictly increasing
    for mu > n.  The one-sided upper limit solves this equal to the chi-square
    quantile with one degree of freedom at 2*alpha, the standard PDG convention
    (TRolke calls ChisquareQuantile(fCL, 1); the one-sided use CL = 0.90 gives
    exactly 2.705543).

    At n = 0 the statistic is NOT undefined: with L(0) = 1 and L(mu) = exp(-mu)
    it reduces to 2*mu exactly, so the limit is chi2.isf(2*alpha, 1)/2.  An
    earlier revision of this script refused the n = 0 row and the manuscript
    described that refusal as a mathematical degeneracy; it was neither.
    Refusing also hid the row where the asymptotic approximation is worst
    (0.067639 Hz against an exact 0.149787 Hz, a factor of 2.21).

    This is a REIMPLEMENTATION from the published method, not the original code:
    ROOT/TRolke has no Windows wheel and could not be installed here.  Because
    it is ours and runs inside this same script, agreement with the exact limit
    is SELF-CONSISTENCY, not independent validation.
    """
    from scipy.optimize import brentq

    q = chi2.isf(2.0 * alpha, 1)

    if n_obs == 0:
        return float(q / 2.0 / exposure)

    def ratio(lam: float) -> float:
        mu = lam * exposure
        return 2.0 * (mu - n_obs - n_obs * math.log(mu / n_obs))

    lo = n_obs / exposure                      # ratio == 0 here
    hi = (n_obs + 20.0 * math.sqrt(n_obs + 1) + 50.0) / exposure
    while ratio(hi) < q:
        hi *= 2.0
        if hi > 1e12:
            return None
    return float(brentq(lambda l: ratio(l) - q, lo, hi))


# --------------------------------------------------------------------------
# The CLs column has been WITHDRAWN, and is deliberately not computed here.
#
# An earlier revision of this script and of the manuscript placed a pyhf CLs
# limit beside the exact limit under a caption promising "identical inputs".
# That comparison is not apples-to-apples: CLs bounds a SIGNAL strength in a
# model that already contains background, whereas the exact one-sided limit
# bounds the TOTAL rate, so the two columns report different parameters.  The
# gap at N = 0 was about two thirds parameter mismatch.
#
# A second problem is that pyhf defaults to an asymptotic formula
# (calctype="asymptotics"), which is least reliable exactly where the comparison
# was most interesting: at N = 0 a toy-based CLs limit is roughly 3.3 events
# against the asymptotic 2.2, so the published N = 0 row would flip sign.
#
# Rather than relabel a misleading comparison we removed it.  A reader who wants
# it should fix the model, state the computational type, and quote both
# parameters explicitly.
# --------------------------------------------------------------------------


def main() -> int:
    exposure = 20.0
    alpha = 0.05
    counts = [0, 1, 2, 5, 10, 20, 50]

    print("=" * 80)
    print("COUNTING-EXPERIMENT COMPARISON  (T = %.0f s, 1 - alpha = %.2f)"
          % (exposure, 1 - alpha))
    print("The profile-likelihood column is OUR reimplementation, run in this")
    print("same script, so agreement is SELF-CONSISTENCY, not independent")
    print("validation.  No CLs column: see the note above.")
    print("=" * 80)
    print("%5s %15s %18s %14s"
          % ("N", "exact 1-sided", "profile-lik.", "rel. diff"))
    rows = []
    for n in counts:
        ex = exact_one_sided_poisson(n, exposure, alpha)
        pl = profile_likelihood_upper(n, exposure, alpha)
        rel = (abs(ex - pl) / ex) if pl is not None else None
        rows.append({"n": n, "exact": ex, "profile": pl,
                     "rel_diff": rel})
        print("%5d %15.6f %18s %14s"
              % (n, ex,
                 ("%.6f" % pl) if pl is not None else "n/a",
                 ("%.4f%%" % (100 * rel)) if rel is not None else "n/a"))

    pairs = [r for r in rows if r["profile"] is not None]
    print()
    print("exact vs profile-likelihood, relative difference:")
    for r in pairs:
        print("   N=%-7d %.4f%%" % (r["n"], 100 * abs(r["exact"] - r["profile"]) / r["exact"]))
    big = [r for r in pairs if r["n"] >= 1000] or [r for r in pairs if r["n"] >= 20]
    print("   -> agrees to %.3f%% already at N=%d, and the agreement tightens with N:"
          % (max(100 * abs(r["exact"] - r["profile"]) / r["exact"] for r in big), big[0]["n"]))
    print("      the published profile-likelihood construction tends to our exact")
    print("      one-sided limit asymptotically, which is the behaviour a correct")
    print("      transcription must show.  This is self-consistency, NOT an")
    print("      independent check: the reimplementation is ours and runs here.")

    report = {
        "study": "RateCert-HEP external tool comparison",
        "exposure_s": exposure,
        "alpha": alpha,
        "methods": {
            "exact_one_sided_poisson": "chi2_{1-a,2(N+1)}/2T (this work)",
            "profile_likelihood": "TRolke 2.0 construction, reimplemented from the publication",
        },
        "rows": rows,
        "rel_diff_exact_vs_profile": {
            str(r["n"]): abs(r["exact"] - r["profile"]) / r["exact"]
            for r in rows if r["profile"] is not None
        },
        "rel_diff_at_largest_n": (
            abs(pairs[-1]["exact"] - pairs[-1]["profile"]) / pairs[-1]["exact"]
            if pairs else None
        ),
    }
    out = REPO / "reports" / "tool_comparison.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_text_lf(out, json.dumps(report, indent=2) + "\n")
    print("\nwrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
