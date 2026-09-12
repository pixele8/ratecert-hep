"""Build the CPC program-deposit archive from an explicit allow-list.

The CPC Guide for Authors requires that a Computer Programs in Physics (CPiP)
manuscript be accompanied by the program source code; a README describing the
file/directory structure and how to install and run the program; sample input
and output for at least one comprehensive test run; and, where appropriate, a
user manual.  This script assembles exactly that archive.

WHY AN ALLOW-LIST
-----------------
An audit of the previous archive found it shipped material no reviewer should
receive:

  * docs/reviewer_response.md         -- a DRAFT REFEREE REBUTTAL
  * docs/cpc_submission_checklist.md  -- internal notes, including the author's
                                         local path E:\\123\\cpc_ref\\
  * docs/cpc_fit_and_revision_plan.md -- venue-fit strategy notes
  * src/ratecert_hep.egg-info/*       -- stale, git-ignored build artefacts

and that it shipped NO `reports/` directory even though the manuscript's own
clean-run block passes `--coverage reports/coverage_stress.json`, so a reviewer
following the paper inside the deposit hit FileNotFoundError.

The archive is now built from an explicit list of what to include, so a file
that is not named here cannot enter by accident.  Docs are listed one by one for
that reason.

The archive is deliberately NOT committed: it is a build product.  Rebuild with

    py tools/build_deposit.py

A note on the external dataset, because it is easy to get wrong: this package's
required sample input lives at ``examples/data/scores.csv``, while the 141 MB
external LHCO dataset lives at the repository root in ``data/``.  Excluding by
the bare directory name ``data`` would silently drop the sample input and break
the very test run the submission is required to provide.
"""

from __future__ import annotations

import pathlib
import zipfile

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "dist" / "ratecert-hep_cpc_program_deposit.zip"

# Directories included in full, subject to the filters below.
INCLUDE_DIRS = ["src", "tests", "examples", "configs", "reports"]
# Individual files included.
INCLUDE_FILES = [
    "README.md", "LICENSE", "CITATION.cff", "pyproject.toml",
    "requirements-lock.txt", ".gitignore",
]
# Documentation, listed individually on purpose: only what a reviewer needs.
INCLUDE_DOCS = [
    "docs/contract.md",
    "docs/validation_report.md",
]

SKIP_DIR_PARTS = {"__pycache__", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".pyo", ".log", ".aux", ".blg", ".out", ".toc", ".bbl"}
SKIP_TOP = {"data", "tmp", "dist"}


def _excluded(p: pathlib.Path) -> bool:
    if any(part in SKIP_DIR_PARTS for part in p.parts):
        return True
    if any(part.endswith(".egg-info") for part in p.parts):
        return True
    if p.suffix.lower() in SKIP_SUFFIX:
        return True
    try:
        rel = p.relative_to(REPO)
    except ValueError:
        return True
    return bool(rel.parts) and rel.parts[0] in SKIP_TOP


def build() -> tuple[pathlib.Path, list[str], int]:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    added: list[str] = []
    total = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for d in INCLUDE_DIRS:
            base = REPO / d
            if not base.exists():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_file() and not _excluded(p):
                    arc = p.relative_to(REPO).as_posix()
                    z.write(p, arc)
                    added.append(arc)
                    total += p.stat().st_size
        for rel in INCLUDE_FILES + INCLUDE_DOCS:
            p = REPO / rel
            if p.is_file():
                z.write(p, rel)
                added.append(rel)
                total += p.stat().st_size
    return OUT, added, total


FORBIDDEN = [
    "docs/reviewer_response.md",
    "docs/cpc_submission_checklist.md",
    "docs/cpc_fit_and_revision_plan.md",
]
LEAK_FRAGMENTS = ["egg-info", "cpc_ref"]


def main() -> int:
    out, added, total = build()
    with zipfile.ZipFile(out) as z:
        names = z.namelist()

    print("wrote %s" % out)
    print("  entries      : %d" % len(added))
    print("  uncompressed : %d bytes (%.2e)" % (total, float(total)))
    print("  archive      : %d bytes" % out.stat().st_size)

    print()
    print("  CPC-required items:")
    required = [
        "README.md", "LICENSE",
        "examples/data/scores.csv",
        "examples/expected/README.md",
        "examples/expected/case1_certified.json",
        "examples/expected/case2_budget_refusal.json",
        "examples/expected/case3_counter_refusal.json",
    ]
    ok = True
    for r in required:
        present = r in names
        ok &= present
        print("    %-46s %s" % (r, "present" if present else "MISSING"))

    print()
    print("  internal material must NOT be present:")
    for f in FORBIDDEN:
        shipped = f in names
        ok &= not shipped
        print("    %-46s %s" % (f, "SHIPPED (defect)" if shipped else "absent"))

    print()
    print("  reports/ included (the manuscript's clean-run block needs it):")
    reps = sorted(n for n in names if n.startswith("reports/") and n.endswith(".json"))
    print("    %d JSON reports" % len(reps))
    cov = "reports/coverage_stress.json" in names
    print("    reports/coverage_stress.json present: %s" % cov)
    ok &= cov

    print()
    leaks = [n for n in names
             if any(frag.lower() in n.lower() for frag in LEAK_FRAGMENTS)]
    print("  leaking entries: %s" % (leaks if leaks else "NONE"))
    ok &= not leaks

    print()
    print("DEPOSIT CLEAN:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
