# RateCert-HEP

**Finite-sample certification of fixed-point trigger rates.**

RateCert-HEP certifies a trigger configuration by keeping three quantities
separate that are usually conflated: the finite-sample statistical bound on the
rate or acceptance probability, the deterministic margin implied by the
rate-register resolution, and the observed score-quantization diagnostic.

- **Repository:** https://github.com/pixele8/ratecert-hep
- **Licence:** MIT (see `LICENSE`)
- **Version:** 0.1.0
- **Requirements:** Python >= 3.10, NumPy, SciPy

This is a reference implementation: a finite-sample upper bound for a deployed
trigger rate composed with an explicit fixed-point score contract and a declared
rate-resolution margin.

It intentionally contains no neural network, no web service, and no detector
claim. The score stream is supplied by the caller. The minimum experiment is:

```powershell
py -m pip install -e ".[dev]"
py -m pytest
$env:PYTHONPATH = "src"
py examples/minimal_certification.py
py examples/validation_pilot.py
py -m ratecert --config configs/worked_example.json --scores examples/data/scores.csv --exposure-s 20 --threshold-code 250 --output reports/cli_certificate.json
```

That command must print `CERTIFIED`. It is the first of three fully specified
cases with checked-in expected output; see
[`examples/expected/README.md`](examples/expected/README.md) for the other two,
which document the exact numbers the certificate must contain and include a
worked refusal on the counter range.

The JSON report separates the raw trigger rate from the prescaled recorded rate,
states the Poisson confidence level, records the fixed-point format, and returns
`NOT_CERTIFIED` with reasons when the contract is violated.

The rate resolution is a deployment declaration (`rate_lsb_hz` and optional
`rate_counter_bits`). For a pure count-per-window implementation it can be
derived with `RateQuantizationSpec.from_counter_window(window_s, counter_bits=...)`.

## Public HEP validation

The public-data mode uses the 74 MB feature file from the LHC Olympics 2020
R&D release (Zenodo DOI `10.5281/zenodo.6466204`). Install the optional HDF5
reader and run the reproducible sweep:

```powershell
py -m pip install -e ".[dev,public-data]"
$env:PYTHONPATH = "src"
py examples/public_lhco_acceptance.py `
  --input data/public/lhco_rnd/events_anomalydetection_v2.features.full.h5 `
  --output reports/public_lhco_acceptance.json
```

The adapter selects the released `label == 0` QCD background, derives the
transparent scalar score `hypot(pxj1, pyj1) / 5000 GeV`, and creates
non-overlapping calibration and deployment blocks from a recorded seed. The
27-cell table sweeps 8/10/12-bit scores, 10k/50k/100k deployment events, and
0.5%/1%/2% acceptance budgets. A family-wise alpha of 1% is split over those
cells; the report records the file hashes, DOI, license, event-id hashes, and
all refusal reasons. It also audits every observed code threshold against the
unquantized score: the maximum absolute acceptance change was 0.0559 (8 bit),
0.0146 (10 bit), and 0.0048 (12 bit). These are distribution-specific
diagnostics, not universal error bounds.

This release is a selected Pythia8+Delphes simulation and provides no live
time or representative input flux. Consequently its certificate quantity is
`background_acceptance_probability`, not a detector Hz measurement. Supplying
an external `input_rate_hz`, rate budget, and `RateQuantizationSpec` enables an
explicitly labelled rate conversion; the conversion is never inferred from
the number of MC rows.

The implementation coverage diagnostic is reproducible with:

```powershell
py examples/coverage_stress.py --output reports/coverage_stress.json
```

At the same per-cell `alpha = 0.0003703703704` used by the public sweep, four
binomial boundary scenarios (20,000 repeats each) produced coverages between
0.99945 and 1.00000. This is an implementation check; the formal guarantee is
the exact Clopper–Pearson construction, not the finite Monte-Carlo repeat.

To run both evidence chains in one machine-readable artifact:

```powershell
py examples/unified_benchmark.py `
  --public-input data/public/lhco_rnd/events_anomalydetection_v2.features.full.h5 `
  --output reports/unified_benchmark.json
```

The explicit-rate section uses a declared Poisson background rate of 8 Hz and
exposures of 1/10/100 s, sweeping 0.01/0.05/0.1 Hz rate LSBs, 8/16-bit rate
counters, and 10/12 Hz budgets (36 cells). Eleven cells pass the complete
finite-sample plus rate-resolution contract; the remaining cells expose either
insufficient exposure, rate-counter full-scale, or budget-margin failures.
The generated report keeps those results separate from the LHCO acceptance
section and records the family-wise alpha and coverage diagnostics.

The assumption boundary is also executable:

```powershell
py examples/assumption_boundary_stress.py `
  --output reports/assumption_boundary_stress.json
```

It compares a stationary Poisson window with bursty and mixed-rate windows that
have the same nominal mean.  The latter are intentionally outside the theorem's model
and are reported as negative diagnostics rather than certified rates.

## Comparison against alternative bounds

The exact construction is compared quantitatively against the empirical tail,
a normal (Wald) bound, and a Wilson score bound:

```powershell
py examples/baseline_comparison.py
py examples/make_baseline_figure.py `
  --input reports/baseline_comparison.json `
  --output-stem reports/figures/baseline_coverage
```

`baseline_comparison.py` applies all four constructions to the identical 27
deployment cells and measures empirical coverage against a known ground-truth
acceptance probability. The results are that the empirical tail certifies all
27 cells while attaining only about 0.51-0.56 coverage against a nominal
0.9996, and that the normal bound under-covers at small counts yet certifies
more cells than the exact bound. Both facts are reported rather than hidden.

## Quantization certificate

Score quantization is usually reported as a descriptive diagnostic. Under a
Lipschitz condition on the score CDF it becomes a bound, and the exact identity
holds for *every* distribution:

```
| P(Q_b(S) >= q) - P(S >= q*Delta_s) |  <=  P( q*Delta_s - Delta_s/2 < S < q*Delta_s + Delta_s/2 )
```

```powershell
py examples/quantization_certificate.py
```

The script verifies the identity on a controlled distribution (12/12 cells),
measures the linear scaling `boundary mass ~ L * Delta_s` (Lipschitz form), and
applies a Dvoretzky-Kiefer-Wolfowitz band to turn the boundary mass into a
finite-sample certificate (6/6 cells covered). It then tests the scaling law
against the real 8/10/12-bit LHCO results, where a fit through the origin gives
R^2 = 0.9986.

The DKW route is rigorous but loose at small samples (2*eps ~ 0.027 at
n = 1e4); the script reports that cost rather than presenting only the
favourable numbers.

## Comparison with external limit-setting software

```powershell
py -m pip install pyhf
py examples/tool_comparison.py
```

Compares three constructions on identical counting-experiment inputs: this
work's exact one-sided Poisson limit, the TRolke 2.0 profile-likelihood
construction reimplemented from its publication (ROOT has no Windows wheel), and
the CLs upper limit from pyhf. The published profile-likelihood limit converges
to our exact limit (23.1% difference at N=1, 1.17% at N=50), which is an
independent check that our implementation computes the right quantity. CLs sits
systematically below both, which is expected for an exclusion criterion, and the
script says so rather than presenting it as agreement.

Generate the paper-facing static figure and its data manifest with:

```powershell
py -m pip install -e ".[figures]"
py examples/make_unified_figure.py `
  --input reports/unified_benchmark.json `
  --output-stem reports/figures/unified_benchmark
```

This writes both PNG (300 dpi) and vector PDF outputs. Panel (a) exposes the
score quantization effect, panel (b) aggregates certification fractions, and
panel (c) shows the upper-rate-plus-resolution-margin contract against each
budget line.

The paper architecture diagram is generated independently with:

```powershell
py examples/make_architecture_figure.py `
  --output-stem reports/figures/ratecert_architecture
```

The four independent result diagnostics are generated from the checked-in
JSON reports:

```powershell
py examples/make_diagnostic_figures.py `
  --unified reports/unified_benchmark.json `
  --coverage reports/coverage_stress.json `
  --assumption reports/assumption_boundary_stress.json `
  --output-dir reports/figures
```

This writes coverage diagnostics, public acceptance-certification margins, the
explicit-rate refusal taxonomy, and the assumption-boundary stress as both
300 dpi PNG and vector PDF files,
plus `diagnostic_figure_manifest.json` containing the input hashes.  The plots
are evidence views: they do not add claims beyond the certificate fields.

Generate the reviewer replay table with:

```powershell
py examples/make_replay_table.py `
  --input reports/unified_benchmark.json `
  --output reports/reviewer_replay_table.csv
```

The reference package versions used for the checked-in results are pinned in
`requirements-lock.txt`; install them with `py -m pip install -r requirements-lock.txt`
when exact numerical replay is required.

The reference-platform timing diagnostic is generated with:

```powershell
py examples/performance_benchmark.py
```

For 100,000 events and 20 repeats, the checked-in run records median timings of
2.37 ms for score quantization, 2.81 ms for the public acceptance certificate,
and 7.20 ms for the explicit rate certificate. These are Python throughput
measurements and do not represent detector or firmware latency.

## Repository layout

| Path | Contents |
| --- | --- |
| `src/ratecert/` | Core package: `core.py`, `acceptance.py`, `public_data.py`, `cli.py`, `io.py` |
| `tests/` | 78-test suite asserting scientific invariants, including the worked example |
| `examples/` | Benchmark, figure, coverage-stress, and replay-table scripts |
| `configs/` | Example configuration files |
| `reports/` | Checked-in JSON reports and generated figures |
| `paper/` | Original SciPost Physics Codebases manuscript source |
| `paper_cpc/` | Current Computer Physics Communications manuscript source |
| `docs/` | Contract, validation report, and CPC fit/revision plan |
| `data/` | **Not versioned.** External public data, fetched separately (see below) |

## External data

The public-data experiment uses the 74 MB feature file from the LHC Olympics
2020 R&D release. It is **not** stored in this repository; it is fetched from
Zenodo and verified against the hashes recorded in the paper and in the
generated reports:

- DOI: `10.5281/zenodo.6466204` (CC-BY-4.0)
- MD5: `271cf5e71fc756b2a8d2b32730689bdb`
- SHA-256: `933b1f11d7b66e6dae0ee2878723f8f5d7ab0f38399806f2d067c5cfd9a502b1`

Place the file at
`data/public/lhco_rnd/events_anomalydetection_v2.features.full.h5` to enable the
public-data commands. All core tests and the synthetic certificate run without
it; the public-data result is then correctly reported as unavailable rather than
being silently replaced by synthetic rows.

## Citation

If you use this software, please cite the accompanying manuscript and the
versioned release. Machine-readable metadata is in `CITATION.cff`.

## Licence

MIT. See `LICENSE`.

