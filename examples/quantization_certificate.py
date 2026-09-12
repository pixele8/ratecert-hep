"""Quantization certificate, verified against a controlled CDF AND reported for
the real LHCO public-data sweep.

Part A verifies the theorem on a known distribution:
  (i)   |change| <= boundary mass        -- exact, assumption-free
  (ii)  boundary mass ~ L * Delta        -- linear scaling under Lipschitz F
  (iii) DKW finite-sample upper bound    -- certified, distribution-free

Part B applies the same construction to the actual 8/10/12-bit cell results
reported in the manuscript, turning the previously descriptive numbers
(0.0559 / 0.0146 / 0.0048) into a tested scaling statement.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]


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


def dkw_eps(n: int, alpha: float = 0.05) -> float:
    """DKW half-width: P(sup|F_hat - F| > eps) <= 2 exp(-2 n eps^2)."""
    return math.sqrt(math.log(2.0 / alpha) / (2.0 * n))


def quantization_change(values: np.ndarray, q: int, bits: int) -> dict:
    """Exact quantized-minus-unquantized acceptance change at code threshold q.

    THE TIE RULE MATTERS, and getting it wrong makes an "exact identity" false.
    For round-to-nearest with ties-to-even (numpy.rint), the value s = b - D/2
    has s/D = q - 0.5 exactly, and ties go to the EVEN neighbour:

        q even  ->  q - 0.5 rounds UP to q    -> endpoint is INCLUDED
        q odd   ->  q - 0.5 rounds DOWN to q-1 -> endpoint is EXCLUDED

    so the exact set of scores that round to >= q is the half-open
    [b - D/2, b) when q is even, and the open (b - D/2, b) when q is odd.
    A blanket "half-open" statement is therefore wrong for odd q, and a blanket
    "strict" statement is wrong for even q.  Both were tried and both failed
    roughly half the time.

    The SYMMETRIC form, P(b - D/2 <= S < b + D/2), is valid for every parity and
    every tie rule, and is what the paper relies on; it is looser by about a
    factor of two but needs no caveat.
    """
    delta = 2.0 ** (-bits)
    b = q * delta
    codes = np.rint(values / delta)
    p_quant = float((codes >= q).mean())
    p_unquant = float((values >= b).mean())
    change = p_quant - p_unquant

    in_halfcell = (values > b - delta / 2.0) & (values < b)
    if q % 2 == 0:
        in_halfcell = in_halfcell | (values == b - delta / 2.0)
    half_cell = float(in_halfcell.mean())

    # symmetric form: valid for all parities and tie rules
    full_cell = float(((values >= b - delta / 2.0)
                       & (values < b + delta / 2.0)).mean())

    return {
        "q": q, "bits": bits, "delta": delta, "b": b, "q_even": (q % 2 == 0),
        "p_quantized": p_quant, "p_unquantized": p_unquant,
        "signed_change": change, "abs_change": abs(change),
        "half_cell_mass": half_cell,
        "full_cell_mass": full_cell,
        # exact identity: |change| equals the parity-appropriate half-cell mass
        "identity_exact": abs(abs(change) - half_cell) < 1e-12,
        # the symmetric bound must hold regardless of parity
        "bound_holds": abs(change) <= full_cell + 1e-15,
    }


def adversarial_identity_check(repeats: int = 300, seed: int = 12345) -> dict:
    """Verify the identity on deliberately awkward score distributions.

    Two families are exercised:

    * randomised ones -- uniform, U-shaped Beta, discretised (atom-laden), point
      mass, narrow spike, coarse grid -- over 4..12 bit widths, because the
      identity must hold for every distribution and a smooth density is exactly
      the case that would hide a bug in the half-cell bookkeeping;
    * a deterministic endpoint family that places an ATOM exactly at
      ``b - D/2``, which is the configuration that distinguishes the half-open
      interval from the strict one.  The randomised family provably cannot reach
      it (it would need a non-integer code), so without this second family the
      earlier, wrong strict form passed the suite unnoticed.
    """
    rng = np.random.default_rng(seed)
    worst_excess = 0.0
    violations = 0
    exact_failures = 0
    tested = 0
    worst_exact_gap = 0.0
    parity_mismatches = 0
    endpoint_cases = 0

    for t in range(repeats):
        n = int(rng.integers(300, 4000))
        kind = t % 6
        if kind == 0:
            s = rng.random(n)
        elif kind == 1:
            s = rng.beta(0.3, 0.3, n)
        elif kind == 2:
            s = np.round(rng.random(n), 3)
        elif kind == 3:
            s = np.concatenate([rng.random(n // 2), np.full(n - n // 2, 0.5)])
        elif kind == 4:
            s = np.clip(rng.normal(0.5, 0.02, n), 0.0, 1.0)
        else:
            s = np.round(rng.random(n) * 8) / 8.0

        bits = int(rng.integers(4, 13))
        D = 2.0 ** (-bits)
        q = int(rng.integers(1, max(2, int(1.0 / D))))
        r = quantization_change(s, q, bits)

        tested += 1
        if not r["bound_holds"]:
            violations += 1
            worst_excess = max(worst_excess, r["abs_change"] - r["full_cell_mass"])
        if not r["identity_exact"]:
            exact_failures += 1
            worst_exact_gap = max(worst_exact_gap,
                                  abs(r["abs_change"] - r["half_cell_mass"]))

    # deterministic endpoint family: atom exactly at the left endpoint, where the
    # tie rule decides whether it rounds up (q even) or down (q odd)
    for bits in range(3, 13):
        D = 2.0 ** (-bits)
        for q in range(1, 40):
            if q >= 1.0 / D:
                continue
            b = q * D
            s = np.array([b - D / 2.0] * 1000)
            r = quantization_change(s, q, bits)
            tested += 1
            endpoint_cases += 1
            if not r["identity_exact"]:
                exact_failures += 1
                parity_mismatches += 1
                worst_exact_gap = max(worst_exact_gap,
                                      abs(r["abs_change"] - r["half_cell_mass"]))

    return {
        "repeats": repeats, "tested": tested,
        "bound_violations": violations, "worst_excess": worst_excess,
        "identity_exact_failures": exact_failures,
        "worst_exact_gap": worst_exact_gap,
        "endpoint_cases": endpoint_cases,
        "parity_mismatches": parity_mismatches,
    }


def certified_mass(values: np.ndarray, q: int, bits: int, alpha: float = 0.05) -> dict:
    """DKW-certified upper bound on the half-cell mass.

    The interval is the HALF-OPEN [b - D/2, b).  ``side="left"`` counts the
    endpoint b - D/2 as included, matching the identity; using the strict
    interval here would under-count an atom sitting exactly on the endpoint and
    the certificate would not cover the true change.
    """
    delta = 2.0 ** (-bits)
    b = q * delta
    n = values.size
    srt = np.sort(values)
    # number of observations < b - delta/2  (side="left" => insert before equals)
    n_below = float(np.searchsorted(srt, b - delta / 2.0, side="left")) / n
    # number of observations < b
    n_strictly_below = float(np.searchsorted(srt, b, side="left")) / n
    ecdf_mass = n_strictly_below - n_below
    eps = dkw_eps(n, alpha)
    return {"ecdf_mass": ecdf_mass, "epsilon": eps,
            "certified_upper": ecdf_mass + 2.0 * eps}


def main() -> int:
    rng = np.random.default_rng(20260912)
    report = {"study": "RateCert-HEP quantization certificate", "seed": 20260912}

    # ---------------- Part A: controlled distribution -----------------
    n = 200_000
    s = rng.beta(2.0, 5.0, size=n)
    a_cells = [quantization_change(s, q, b) for b in (8, 10, 12, 14) for q in (64, 128, 192)]
    print("=" * 78)
    print("PART A (i) EXACT identity: |change| == half-cell mass P(b-D/2 <= S < b)")
    print("=" * 78)
    print("%4s %5s %13s %14s %14s %s"
          % ("bits", "q", "|change|", "half cell", "full cell", "exact?"))
    for c in a_cells:
        print("%4d %5d %13.3g %14.3g %14.3g %s"
              % (c["bits"], c["q"], c["abs_change"], c["half_cell_mass"],
                 c["full_cell_mass"], "YES" if c["identity_exact"] else "NO"))
    identity_ok = all(c["identity_exact"] for c in a_cells)
    print("\nexact identity held in %d/%d cells"
          % (sum(c["identity_exact"] for c in a_cells), len(a_cells)))
    print("note: the full-cell column is ~2x the half-cell column, which is why")
    print("      the symmetric bound L*Delta_s is loose and L*Delta_s/2 is correct\n")

    print("=" * 78)
    print("PART A (i') ADVERSARIAL identity check across awkward distributions")
    print("=" * 78)
    adv = adversarial_identity_check()
    print("  configurations tested        : %d" % adv["tested"])
    print("  exact-identity failures      : %d  (worst gap %.2e)"
          % (adv["identity_exact_failures"], adv["worst_exact_gap"]))
    print("  symmetric-bound violations   : %d  (worst excess %.2e)"
          % (adv["bound_violations"], adv["worst_excess"]))
    print("  endpoint cases (atom at b-D/2): %d" % adv["endpoint_cases"])
    print("  parity-handling mismatches   : %d" % adv["parity_mismatches"])
    print("  -> the tie rule decides the endpoint: for round-half-to-EVEN the atom")
    print("     at b-D/2 rounds up when q is even and down when q is odd, so the")
    print("     half-cell interval is [b-D/2,b) for even q and (b-D/2,b) for odd q.")

    print()
    print("=" * 78)
    print("PART A (ii) scaling: half-cell mass = L * Delta/2,  q = 128")
    print("=" * 78)
    print("%4s %14s %14s %10s" % ("bits", "half cell", "L*Delta/2", "ratio"))
    scale_rows = []
    for bits in (8, 10, 12):
        c = quantization_change(s, 128, bits)
        delta = c["delta"]
        w = max(8.0 * delta, 1e-3)
        b = 128 * delta
        L = (float((s < b).mean()) - float((s < b - w).mean())) / w
        ratio = c["half_cell_mass"] / (L * delta / 2.0)
        scale_rows.append({"bits": bits, "half_cell": c["half_cell_mass"],
                           "L_delta_half": L * delta / 2.0, "ratio": ratio, "L": L})
        print("%4d %14.8g %14.8g %10.3f"
              % (bits, c["half_cell_mass"], L * delta / 2.0, ratio))

    print()
    print("=" * 78)
    print("PART A (iii) DKW-certified upper bound on the quantization effect")
    print("=" * 78)
    print("%9s %6s %5s %13s %12s %16s %s"
          % ("n", "bits", "q", "|change|", "ecdf", "certified", "covers"))
    cert_ok = True
    cert_rows = []
    for n_sub in (10_000, 50_000, 200_000):
        sub = s[:n_sub]
        for q in (128, 192):
            ch = quantization_change(sub, q, 10)["abs_change"]
            r = certified_mass(sub, q, 10, 0.05)
            covers = r["certified_upper"] >= ch
            cert_ok &= covers
            cert_rows.append({"n": n_sub, "q": q, "abs_change": ch, **r, "covers": covers})
            print("%9d %6d %5d %13.3g %12.3g %16.3g %s"
                  % (n_sub, 10, q, ch, r["ecdf_mass"], r["certified_upper"],
                     "yes" if covers else "NO"))
    print("\ncertificate covered the true change in every cell:", cert_ok)

    # ---------------- Part B: the real LHCO cell values ----------------
    print()
    print("=" * 78)
    print("PART B  real LHCO sweep: does the reported change scale with Delta/2?")
    print("=" * 78)
    # The three changes are READ FROM THE DEPOSITED PUBLIC-DATA REPORT, at a
    # single common deployment prefix, rather than typed in as literals.
    #
    # An earlier revision hard-coded obs = {8: 0.0559, 10: 0.0146, 12: 0.0048}
    # and read no file at all, so the "cross-check against the real LHCO
    # results" was arithmetic on three constants: it could not detect the
    # report changing, and two of the three values came from one prefix while
    # the third came from another.  Keys are `quantization_sweep.
    # max_abs_acceptance_delta`, the maximum over all observed code thresholds.
    PREFIX = 50000
    report_path = REPO / "reports" / "public_lhco_acceptance.json"
    if not report_path.exists():
        raise SystemExit(
            "missing %s: run examples/public_lhco_acceptance.py first, or set "
            "--public-report to a deposited report" % report_path
        )
    public = json.loads(report_path.read_text(encoding="utf-8"))
    obs: dict[int, float] = {}
    for cell in public["cells"]:
        if cell.get("sample_size_requested") != PREFIX:
            continue
        sweep = cell.get("quantization_sweep")
        if not isinstance(sweep, dict):
            continue
        value = sweep.get("max_abs_acceptance_delta")
        if value is None:
            continue
        bits = int(cell["bits"])
        obs[bits] = max(obs.get(bits, 0.0), float(value))
    want = (8, 10, 12)
    missing = [b for b in want if b not in obs]
    if missing:
        raise SystemExit(
            "report has no quantization_sweep maximum for bits %s at prefix %d; "
            "found %s" % (missing, PREFIX, sorted(obs))
        )
    print("  source: %s" % report_path.name)
    print("  prefix: %d events (common to all three widths)" % PREFIX)
    obs = {b: obs[b] for b in want}
    lsb = {b: 2.0 ** (-b) for b in obs}
    print("%4s %14s %16s %16s" % ("bits", "Delta_s", "reported change", "change/(Delta/2)"))
    for b in (8, 10, 12):
        print("%4d %14.8f %16.4f %16.3f" % (b, lsb[b], obs[b], obs[b] / (lsb[b] / 2.0)))
    print("\nsuccessive ratios (4.0 would be exact linearity):")
    r1 = obs[8] / obs[10]
    r2 = obs[10] / obs[12]
    print("   8->10 bit: %.3f     10->12 bit: %.3f" % (r1, r2))
    x = np.array([lsb[b] / 2.0 for b in (8, 10, 12)])
    y = np.array([obs[b] for b in (8, 10, 12)])
    slope = float((x @ y) / (x @ x))
    pred = slope * x
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2fit = 1 - ss_res / ss_tot
    ratio = {b: obs[b] / (lsb[b] / 2.0) for b in obs}
    L_eff = max(ratio.values())

    print("\nleast-squares fit through the origin:  L_bar = %.3f   R^2 = %.6f"
          % (slope, r2fit))
    print("  per-width ratios change/(Delta/2): "
          + "  ".join("%d bit %.2f" % (b, ratio[b]) for b in (8, 10, 12)))
    print()
    print("  IMPORTANT: a least-squares fit is a TREND LINE, NOT A BOUND.")
    print("  L_bar = %.2f fails to bound its own data:" % slope)
    for b in (8, 10, 12):
        bound = slope * (lsb[b] / 2.0)
        print("    %2d bit: change=%.4f  L_bar*(Delta/2)=%.4f  %s"
              % (b, obs[b], bound, "ok" if obs[b] <= bound else "NOT BOUNDED"))
    print()
    print("  bound-consistent constant: L_eff = max(change/(Delta/2)) = %.3f" % L_eff)
    print("  this bounds all three points:")
    for b in (8, 10, 12):
        bound = L_eff * (lsb[b] / 2.0)
        print("    %2d bit: change=%.4f  L_eff*(Delta/2)=%.4f  %s"
              % (b, obs[b], bound, "ok" if obs[b] <= bound else "NOT BOUNDED"))
    print()
    print("NOTE ON THE FACTOR: the proportionality is to Delta/2, the HALF cell, not")
    print("to the full LSB. Round-to-nearest places the decision boundary at a cell")
    print("centre, so the effective threshold moves by at most half a cell. Quoting")
    print("the bound as L*Delta overstates it by exactly two.")
    print()
    print("The three ratios are not constant (%.2f, %.2f, %.2f), so L is a LOCAL"
          % (ratio[8], ratio[10], ratio[12]))
    print("quantity and should be re-estimated near the operating threshold rather")
    print("than transferred from a fit at another width. The 12-bit point is the")
    print("outlier that drives L_eff above the fitted value.")

    report.update({
        "part_a": {
            "n": n, "identity_all_ok": identity_ok,
            "cells_identity": a_cells, "scaling": scale_rows,
            "certificate_rows": cert_rows, "certificate_all_cover": cert_ok,
            "adversarial_identity": adv,
        },
        "part_b_lhco": {
            "observed_change": {str(k): v for k, v in obs.items()},
            "lsb": {str(k): v for k, v in lsb.items()},
            "change_per_half_lsb": {str(b): obs[b] / (lsb[b] / 2.0) for b in obs},
            "ratio_8_10": r1, "ratio_10_12": r2,
            # A least-squares fit is a trend line, NOT a bound: L_bar lies below
            # two of the three measurements.  L_eff = max(change/(Delta/2)) is the
            # smallest constant that actually satisfies the Lipschitz bound on
            # this sample, and is what the paper quotes.
            "L_bar_least_squares": slope,
            "L_eff_bound_consistent": L_eff,
            "implied_sup_density": slope, "r_squared": r2fit,
        },
    })
    out = REPO / "reports" / "quantization_certificate.json"
    _write_text_lf(out, json.dumps(report, indent=2) + "\n")
    print("\nwrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
