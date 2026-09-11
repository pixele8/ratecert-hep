# RateCert-HEP → Computer Physics Communications (CPC)

Fit assessment and revision plan. Prepared 2026-09-12.

Every precedent DOI below was verified live against the Crossref REST API
(`api.crossref.org`) during preparation, so the venue/title/year/page data are
primary-source facts, not recollection.

---

## 1. Verdict

**Recommend submitting to CPC. Fit is good — better than the current SciPost
Physics Codebases target on every axis that matters for this paper.**

The single blocking gap is not scientific: **the code is not yet a public,
citable artifact.** The workspace is not even a Git repository, and no
repository URL appears anywhere in 881 lines of LaTeX. CPC is a
program-publication journal; a submission whose program cannot be obtained
fails on that alone. Everything else is editing work.

| Dimension | Assessment |
|---|---|
| Scientific soundness | **Strong.** Core identities re-verified numerically (see §4). |
| Venue precedent | **Strong and directly on-target** (see §3). |
| Scope match | **Good**, after reframing (see §5). |
| Length | **Fine.** 17 pp. is at or above the CPC norm for tool papers. |
| Code availability | **Blocking.** No repo, no URL, no tag, no archive DOI. |
| Format compliance | **Not started.** No Program Summary, no keywords, wrong class. |

---

## 2. What CPC is, and how it differs from the current target

CPC is Elsevier's software journal for physics: physics, chemistry, materials
science, geophysics and astronomy. It publishes a *program* and the paper that
documents it, and it maintains the **CPC Program Library** for archival deposit.
The manuscript class is named *Computer Physics Descriptions*.

The differences that matter for this manuscript:

| | SciPost Physics Codebases (current) | CPC (proposed) |
|---|---|---|
| Primary criterion | Codebase + reproducible release | Program + documentation + deposit |
| Structured front matter | Not required | **Mandatory "Program Summary"** with fixed fields |
| Code archival | Repository-oriented | **CPC Library deposit, DOI in the summary** |
| Keyword block | Not required | Required |
| Ambition | "new science" freely | Tool that others can obtain, build and re-run |

The move is an upgrade in conventional recognition (subscription-based
Elsevier title with long-standing indexing) and, for this particular paper, a
better *tonal* match: CPC has always been comfortable publishing a well-engineered
small utility whose value is correctness and reproducibility.

---

## 3. Verified CPC precedent — this is the strongest part of the case

The paper's contribution sits at the intersection of three things CPC
demonstrably publishes. All records below are confirmed via Crossref.

### 3a. Statistical tools for exactly this quantity (upper limits / intervals)

| Paper | Year | Vol, pages | DOI |
|---|---|---|---|
| *A program for confidence interval calculations for a Poisson process with background including systematic uncertainties: POLE 1.0* | 2004 | 158, 117–123 | `10.1016/j.cpc.2003.12.002` |
| *Limits, discovery and cut optimization for a Poisson process with uncertainty in background and signal efficiency: TRolke 2.0* | 2010 | 181, 683–686 | `10.1016/j.cpc.2009.11.001` |
| *Confidence interval optimization for testing hypotheses under data with low statistics* | 2014 | — | `10.1016/j.cpc.2013.12.016` |
| *BAT — The Bayesian analysis toolkit* | 2009 | — | `10.1016/j.cpc.2009.06.026` |

**This is decisive.** `POLE 1.0` and `TRolke 2.0` are *Poisson upper-limit and
confidence-interval programs for HEP* — the same class of object as
RateCert-HEP's Eq. (1). A reviewer at CPC cannot argue that a one-sided
Poisson-limit tool is out of scope.

Two things follow, and both go in our favour:

1. **Length is not a problem.** These precedent tool papers are **3–6 pages**
   (683–686 is four pages). Our 17 pages is *more* substantial than the
   established norm, not less. Do not cut to match; the extra content is
   evidence of care.
2. **The differentiator is clear and defensible.** `POLE`/`TRolke` handle the
   statistics but say nothing about *how the statistic was materialised in
   firmware*. RateCert-HEP's contribution — coupling the finite-sample bound to
   a fixed-point score format, a rate-register LSB, and a counter full scale,
   with an explicit refusal taxonomy — is genuinely orthogonal to them. That is
   the gap the paper fills.

### 3b. HEP analysis/statistics toolkits

| Paper | Year | Vol, pages | DOI |
|---|---|---|---|
| *NNDrone: A toolkit for the mass application of machine learning in High Energy Physics* | 2019 | 240, 15–20 | `10.1016/j.cpc.2019.03.002` |
| *BAT — The Bayesian analysis toolkit* | 2009 | — | `10.1016/j.cpc.2009.06.026` |

### 3c. Trigger / real-time / fixed-point hardware

| Paper | Year | Vol, pages | DOI |
|---|---|---|---|
| *Real-time data processing in the ALICE High Level Trigger at the LHC* | 2019 | 242, 25–48 | `10.1016/j.cpc.2019.04.011` |
| *Hardware acceleration of complex HEP algorithms with HLS and FPGAs: Methodology and preliminary implementation* (Wojenski et al.) | 2024 | 295, 108997 | `10.1016/j.cpc.2023.108997` |
| *CMS online event filter software* | 1998 | — | `10.1016/s0010-4655(97)00161-6` |
| *A calorimeter software trigger for the Mark II detector at SLC* | 1989 | — | `10.1016/0010-4655(89)90227-0` |

CPC has published trigger software **continuously from 1989 to 2019**, and as
recently as 2024 published an FPGA/HLS methodology paper. The fixed-point,
real-time, detector-facing framing is squarely in scope.

### 3d. One negative data point worth knowing

`pyhf` ("pure-Python implementation of HistFactory statistical models") did
**not** go to CPC — it is in JOSS (`10.21105/joss.02823`). Existence proof that
some statistical tooling lands in lightweight software venues instead. It does
not weaken the case, because JOSS has no physics-refereeing depth and
`POLE`/`TRolke` show CPC's appetite for this exact object, but do not cite
`pyhf` as a CPC precedent.

---

## 4. Independent verification of the manuscript's core claims

I re-derived the numerical spine of the paper rather than trusting the text.

| Claim in manuscript | Independent result |
|---|---|
| Eq. (2) `Beta^{-1}(1-α; K+1, n-K)` | Matches direct binomial-tail inversion to `2.9e-14` |
| Eq. (1) `χ²_{1-α,2(N+1)} / 2T` | `1.0072340109398463` vs numeric `1.0072340109398468` |
| Worked example `U = 9.4897902928` Hz (N=158, T=20 s, α=0.01) | **Reproduces to all 10 digits** |
| Nominal per-cell coverage `0.9996296` (α=0.01/27) | `0.9996296296296296` ✓ |
| Nominal per-cell coverage `0.9997222` (α=0.01/36) | `0.9997222222222222` ✓ |
| Test suite `23 passed` | **Confirmed: 23 passed** |

One genuine numerical note to fold into the revision: `Beta^{-1}(1-α; n+1, 0)`
evaluates to **NaN**, not 1, in the `K = n` boundary case. The manuscript
already states the routine special-cases this to return 1, so the *behaviour*
is correct — but the text currently reads as though the identity covers the
boundary naturally. Say explicitly that the boundary is special-cased because
the incomplete-beta identity degenerates there. A CPC referee who actually runs
the code will find this, and a paper that names it first reads as competent
rather than as having a bug.

---

## 5. Scope risks and how the revision handles them

### Risk 1 — "This is not physics, it is quality assurance."

The manuscript *invites* this. §3.1 currently says the program "does not train a
classifier, choose a physics observable, estimate a detector cross section, or
synthesize an FPGA", and the discussion calls the result "not a detector-hardware
timing or live-rate measurement". Honest — and it stays honest — but as written
the non-goals section is longer and more prominent than the physics motivation.

**Fix:** keep every disclaimer, but lead with the physics. Add a concrete
motivation paragraph naming the real constraints (L1/HLT output rate budgets,
bandwidth allocation, firmware register widths) so the reader learns *why a
trigger rate must be certified* before learning what the program declines to do.
Move the non-goals to the end of the program-specification section and shorten
the preamble to them.

### Risk 2 — "The validation is synthetic."

The LHCO benchmark is a simulated R&D release with no live time, and the 36-cell
rate sweep is a synthetic Poisson stream. The manuscript says so plainly, which
is right, but a referee may read "no real detector data" as "not validated".

**Fix:** reframe the two chains by *what property each one proves* — chain 1
proves the acceptance-probability path on public community data; chain 2 proves
the rate/register semantics against a known-truth generator. Add an explicit
sentence that a synthetic stream with known ground truth is the correct
instrument for a *coverage* claim, because on real data coverage is unobservable
(the true rate is unknown). That turns a perceived weakness into a
methodological argument.

### Risk 3 — "Code not available."

**Blocking. Must be fixed before submission.** See §6.

### Risk 4 — Misleading parallel with the FPGA paper.

`10.1016/j.cpc.2023.108997` is a *hardware implementation* paper. Ours is not.
Cite it as evidence that the fixed-point/FPGA constraint is a real, actively
published concern in CPC — **not** as a comparable contribution.

---

## 6. Blocking prerequisite: make the program obtainable

CPC requires the program to be deposited and citable. Current state, verified:
no `.git` directory, no remote, no URL anywhere in the manuscript.

Required, in order:

1. `git init` in `ratecert_hep/`, commit the tree, add a public remote.
2. Choose and confirm the licence — `CITATION.cff` already declares **MIT**,
   and `LICENSE` exists. Keep MIT; state it in `Licensing provisions`.
3. Tag the release (`v0.1.0`) and mint an archival DOI (Zenodo/GitHub release).
4. Ensure the deposit is self-contained: `src/`, `tests/`, `examples/`,
   `configs/`, `reports/`, `requirements-lock.txt`, `README.md`, `LICENSE`,
   `CITATION.cff`.
5. **Recheck the README's install path.** It says `pip install -e ".[dev]"` but
   `pyproject.toml` declares `package-dir = {"" = "src"}` and the CLI entry
   point is `ratecert.cli:main`. Confirm a clean-clone install and run works
   from scratch on a machine that has never built it.

Until step 1–3 are done, the Program Summary's `CPC Library link to program
files` and `Developer's repository link` cannot be filled. The revision marks
these with a clearly visible placeholder.

---

## 7. Revision plan

New CPC manuscript: `paper_cpc/ratecert_hep_cpc.tex`, class `elsarticle`
(`preprint, 12pt`, `num` reference style).

### R1 — Format conversion
- Port `SciPost.cls` document → `elsarticle`. Drop the SciPost class and the
  Scipost bibstyle; drop the page-top "SciPost Physics / Submission" stamp.
- **Remove the table of contents** — not CPC practice, and it consumes a page.
- Renumber nothing topically; the math and equations carry over unchanged.

### R2 — Add mandatory front matter (new)
- **Program Summary block** with the standard field set: Program Title; CPC
  Library link to program files; Developer's repository link; Licensing
  provisions; Programming language; Nature of problem; Solution method;
  Additional comments including restrictions and unusual features; References.
- **Keywords** (new — currently zero).
- **Declaration of Competing Interest** (Elsevier-wide requirement), replacing
  the free-text "Conflict of interest" paragraph.
- **Data availability statement.**
- **Highlights** (optional; 3–5 × ≤85 chars) — worth adding.

### R3 — Reframe for physics scope
- **Title:** keep the informative core but foreground the domain. Candidate:
  *"RateCert-HEP: a program for finite-sample certification of fixed-point
  trigger rates"*.
- **Abstract:** restructure to lead with the physics problem, then the method,
  then the numbers. Keep every existing caveat.
- **§1 Introduction:** add the trigger-rate-budget motivation paragraph
  (L1/HLT bandwidth, prescale semantics, firmware register widths). Add the
  verified CPC precedents (`POLE`, `TRolke 2.0`, ALICE HLT, Wojenski et al.)
  as positioning, and make the *orthogonality* argument explicit: prior limit
  software handles the statistic, this handles the statistic **composed with
  the fixed-point representation**.
- **§7.1 "Position relative to existing HEP software":** currently compares only
  to YODA. Extend to `POLE`/`TRolke`/`pyhf`/RooStats-class tooling so the
  novelty claim is anchored to the actual state of the art rather than to one
  histogram library.
- **Discussion:** demote the non-goals from lead position; keep all of them.

### R4 — Content corrections
- State the `K = n` boundary is **special-cased** (incomplete beta degenerates
  to NaN there) — see §4.
- Add the missing self-contained-build statement once the repo exists.
- Replace the "For a Codebases review…" sentence in §7.2 with CPC-appropriate
  wording; drop the SciPost Codebases citation entirely.
- Appendix B step 6 currently says "run the paper build with the checked-in
  SciPost class" — retarget to the Elsevier class.

### R5 — Verify
- Compile with `pdflatex` → `bibtex` → `pdflatex` ×2; require zero undefined
  references and zero fatal errors.
- Confirm all six figures still resolve and that no figure text overflows.
- Re-run `py -m pytest tests -q` and confirm 23 passed.

### Explicitly out of scope
No change to the science, the statistics, the benchmark results, or the
measured timings. The numbers stand as published.

---

## 8. Addendum: comparison against actual published CPC manuscripts

To check the revision against the *published* standard rather than a guessed
template, four comparable CPC papers were retrieved in full text from their
arXiv preprints and analysed directly:

| Paper | CPC | Preprint |
|---|---|---|
| TRolke 2.0 | 181, 683–686 (2010) | arXiv:0907.3450 |
| POLE 1.0 | 158, 117–123 (2004) | — |
| BAT | 180, 2197–2209 (2009) | arXiv:0808.2552 |
| NNDrone | 240, 15–20 (2019) | arXiv:1712.09114 |
| ALICE HLT | 242, 25–48 (2019) | arXiv:1812.08036 |

### The canonical Program Summary field set (now matched exactly)

The initial revision used a generic field template. The **actual** published
Program Summary of TRolke 2.0 uses this bulleted set, which differs materially:

```
Title of Program
Program available from
Licensing provisions
Computer for which the program is designed
Operating Systems under which the program has been tested
Programming Language used
Memory required to execute with typical data
No. of bytes in distributed program, including initialization file, etc.
Distribution Format
Keywords
Nature of the Physical Problem
Method of solution
Typical Running Time
```

Six of these were absent from the first revision and have now been added with
real values: platform, tested operating systems, memory, distributed size,
distribution format, and **Typical Running Time** (drawn from the checked-in
`reports/performance_benchmark.json`). The field names "Nature of the Physical
Problem", "Method of solution" and "Typical Running Time" replace the generic
"Nature of problem"/"Solution method" wording.

Note also that the arXiv preprints **omit** their Program Summary — it is added
by the publisher. Searching a preprint for those fields will wrongly suggest
they are not required. This is why the published version had to be recovered
from the v2 preprint of TRolke, which retains it.

### Other gaps found and closed

- **Pseudocode was absent.** TRolke 2.0 gives full method-by-method API
  documentation. Two algorithms have been added: the two-call certify
  procedure, and the four bound constructions compared in the baseline study.
- **No quantitative baseline existed.** Three competitors (empirical tail,
  normal/Wald, Wilson) are now evaluated on the identical 27 cells and against
  a known ground truth. This is the single largest addition and is what the
  table of contents of any comparable paper would lead with.
- **Keyword count.** TRolke uses four keywords; the first revision listed
  seven. Trimmed to four.

### Section-count position

NNDrone (a 6-page published CPC tool paper) uses 5 top-level sections. The
revision uses 8 plus two appendices with 30 pages total, i.e. substantially
more structure and more evidence than the published comparators, which is the
intended direction.

---

## 9. Residual uncertainty in this assessment

Stated so the author can price the risk honestly:

- **The exact current Program Summary field list is not verified from a primary
  source.** `sciencedirect.com` returns HTTP 403 and `www.elsevier.com` blocks
  our egress. The field set used in §7/R2 is the long-standing standard CPC
  template; the *existence* of the structured fields (e.g. "Solution method")
  is corroborated by CPC's own indexed content, but the precise current wording
  and ordering should be confirmed against the live Guide for Authors before
  submission. In particular, confirm whether a legacy `Program obtainable from:`
  line is still expected.
- **Deposit timing is unverified** — whether the CPC Library archive is required
  at first submission or only at acceptance. Assume it is needed early; it is
  required in either case.
- **Bibliometrics were deliberately not reported.** Live impact factor,
  CiteScore, acceptance rate and turnaround could not be verified, and a
  guessed number is worse than an absent one. CPC is known to be a
  long-established, well-indexed subscription title; check current figures on
  the journal page for any administrative use.
- CPC is hybrid (subscription route plus optional gold OA), so a **no-charge
  publication route exists**; the exact APC was not verified.
