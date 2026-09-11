# CPC CPiP pre-submission compliance checklist

Verified against the **official** CPC Guide for Authors (archived 2025-08-02)
and the **official** CPiP LaTeX template
(`https://legacyfileshare.elsevier.com/promis_misc/cpc-cpip-template.tex`),
both retrieved during preparation. Local copies of the primary sources are in
`E:\123\cpc_ref\`.

Article type targeted: **Computer Programs in Physics (CPiP)** — a full paper
describing a program to be placed in the CPC Program Library.

---

## 1. Program Summary

The guide states, verbatim:

> "All CPiP manuscripts must contain the following Program Summary section
> immediately following the abstract."

| Official template field | Status in this manuscript |
|---|---|
| `Program Title:` | RateCert-HEP |
| `CPC Library link to program files:` | "(to be added by Technical Editor)" |
| `Developer's repository link:` | github.com/pixele8/ratecert-hep |
| `Licensing provisions (please choose one):` | MIT (on the approved list) |
| `Programming language:` | Python 3 |
| `Supplementary material:` | None; contents pointed to in the repository |
| `Journal reference of previous version:` | omitted — new program, not a new version |
| `Does the new version supersede…:` | omitted — new program |
| `Reasons for the new version:` | omitted — new program |
| `Summary of revisions:` | omitted — new program |
| `Nature of problem (approx. 50-250 words):` | present, ~180 words |
| `Solution method (approx. 50-250 words):` | present, ~210 words |
| `Additional comments including restrictions and unusual features (approx. 50-250 words):` | present, ~200 words |
| References | present, own numbered list `[1]–[3]` |

The four asterisked fields are, per the template footnote, *"only required for
new versions of programs previously published in the CPC Program Library"*, so
their omission here is correct.

**Placement:** the summary sits inside the `abstract` environment in the
`frontmatter`, immediately after the abstract text, exactly as the official
template does — so it appears on the article landing page, not in an appendix.

**Own reference list:** the template states that the Program Summary reference
list *"is different from the bibliography at the end of the Long Write-Up"* and
should contain *"only those items referenced in the Program Summary section"*,
typed in text as `[1]`, `[2]`. Implemented as a separate `refnummer` list.
Because of this, the Program Summary deliberately does **not** use `\cite`.

> **Caution for future edits.** arXiv preprints of CPC papers omit the Program
> Summary entirely — it is added by the publisher. Searching a preprint for
> these fields will wrongly suggest they are optional. The summary recovered
> here came from primary sources, not from a preprint.

---

## 2. Scope and the desk-rejection gate

The guide states, verbatim:

> "The focus of CPC is on contemporary computational methods and techniques and
> their implementation, the effectiveness of which will normally be evidenced by
> the author(s) within the context of a substantive problem in physics."

> "The introduction to each paper should be directed to a general audience and
> the author(s) must clearly articulate the novelty and significance of the
> paper and how it will advance the solution of an important physics
> application. Papers which, in the opinion of a Principal Editor, fail to do
> this **will not be sent for review**."

| Requirement | Where satisfied |
|---|---|
| Directed to a general audience | Sec. 1 opens with the trigger-rate budget problem, not with the package |
| Novelty articulated | Sec. 1 states the gap explicitly: prior limit-setting programs "return a number for a statistic" but are not attached to threshold provenance or register resolution |
| Significance articulated | Sec. 1 states the cost of both error directions — bandwith misallocation, signal lost to needless prescaling |
| Advances a physics application | Sec. 1 sets the collider trigger-menu context; Sec. 4 validates on a public HEP release |

## 3. Program submission package

The guide requires the following to accompany a CPiP manuscript. The Technical
Editor checks these **before** the paper reaches an editor, so a gap here stalls
the submission at intake.

| Required item | Status |
|---|---|
| Program source code | `src/ratecert/` |
| README with file/directory structure and install/run instructions | `README.md` |
| Sample input and output for at least one comprehensive test run | `examples/` + `reports/*.json` |
| User manual "where appropriate" | `README.md` + `docs/contract.md` |
| Licence from the approved list | `LICENSE` — MIT |

Note that the README documents a **clean-clone** path: clone, install, run the
synthetic certificate, run the test suite, regenerate every figure. This was
verified end to end from the live public repository.

## 4. Manuscript preparation

| Item | Status |
|---|---|
| Length | 30 pp. — within the ~20–35 pp. norm of comparable CPiP papers |
| Class | `elsarticle` `[preprint,12pt]`, matching the official template |
| Reference style | `elsarticle-num` |
| Keywords | 4, matching CPC convention |
| Declaration of competing interest | present |
| Data availability statement | present (Zenodo DOI + CC-BY-4.0) |
| CRediT authorship statement | present |
| Funding statement | present |

## 5. Known open items before submission

1. **CPC Library DOI** is assigned by the Technical Editor on deposit; the
   field already says so.
2. **Archival release DOI.** The GitHub tag `v0.1.0` exists, but no
   Zenodo/DataCite DOI is minted yet. Optional, but it strengthens the deposit.
3. **Article Processing Charge.** CPC is hybrid; a subscription route exists at
   no charge and gold OA is optional. The current APC was **not verified** —
   confirm on the journal page for any administrative purpose.
4. **Exact 中科院分区 (CAS zone) was not verified.** CPC carries a JCR impact
   factor so it has a CAS entry; the specific zone could not be confirmed from
   any reachable primary source.
5. **Confirmed data limitation, stated in the paper rather than hidden:**
   validation uses a public simulated release and a declared Poisson stream.
   There is no detector hardware, firmware, live trigger, or DAQ measurement,
   no latency or dead-time measurement, and no real-data live rate. This is
   disclosed in Sec. 1, Sec. 4.6, Sec. 7, and the Program Summary, and it is
   consistent with the scope of the comparable CPC statistics-tool papers
   (TRolke 2.0, POLE 1.0), which likewise carry no hardware results.
