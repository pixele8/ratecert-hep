"""Build the CPC program-deposit archive.

The CPC Guide for Authors requires that a Computer Programs in Physics (CPiP)
manuscript be accompanied by:

  * the program source code;
  * a README giving the names and a brief description of the files/directory
    structure that make up the package, and clear instructions on installation
    and execution;
  * sample input and output data for at least one comprehensive test run that
    will convince the reviewers that the program operates as specified; and
  * where appropriate, a user manual.

This script assembles exactly that archive from the repository.

The archive is deliberately NOT committed: it is a build product.  Rebuild it
with

    py tools/build_deposit.py

A note on exclusions, because it is easy to get wrong: this package's required
sample input lives at ``examples/data/scores.csv``, while the 141 MB external
LHCO dataset lives at the repository root in ``data/``.  Excluding by the bare
directory name ``data`` would silently drop the sample input and break the very
test run the CPC submission is required to provide.  Only the repository-root
``data/`` directory is excluded here.
"""

from __future__ import annotations

import pathlib
import zipfile

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "dist" / "ratecert-hep_cpc_program_deposit.zip"

INCLUDE_DIRS = ["src", "tests", "examples", "configs", "docs"]
INCLUDE_FILES = [
    "README.md", "LICENSE", "CITATION.cff", "pyproject.toml",
    "requirements-lock.txt", ".gitignore",
]
# Only caches.  See the module docstring for why "data" is not listed.
SKIP_DIR_PARTS = {"__pycache__", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".pyo", ".log", ".aux", ".blg", ".out", ".toc", ".bbl"}


def _excluded(p: pathlib.Path) -> bool:
    if any(part in SKIP_DIR_PARTS for part in p.parts):
        return True
    if p.suffix.lower() in SKIP_SUFFIX:
        return True
    try:
        rel = p.relative_to(REPO)
    except ValueError:
        return True
    return rel.parts[:1] in (("data",), ("tmp",), ("dist",))


def build() -> tuple[pathlib.Path, int, int]:
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
                    z.write(p, p.relative_to(REPO).as_posix())
                    added.append(p.relative_to(REPO).as_posix())
                    total += p.stat().st_size
        for f in INCLUDE_FILES:
            p = REPO / f
            if p.is_file():
                z.write(p, f)
                added.append(f)
                total += p.stat().st_size
    return OUT, len(added), total


def main() -> int:
    out, n, total = build()
    required = [
        "README.md", "LICENSE",
        "examples/data/scores.csv",
        "examples/expected/README.md",
        "examples/expected/case1_certified.json",
        "examples/expected/case2_budget_refusal.json",
        "examples/expected/case3_counter_refusal.json",
    ]
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())

    print("wrote %s" % out)
    print("  entries      : %d" % n)
    print("  uncompressed : %d bytes (%.2e)" % (total, float(total)))
    print("  archive      : %d bytes" % out.stat().st_size)
    print()
    print("  CPC-required items:")
    ok = True
    for r in required:
        present = r in names
        ok &= present
        print("    %-46s %s" % (r, "present" if present else "MISSING"))
    leaked = [x for x in names if x.startswith("data/")]
    print("    %-46s %s" % ("no external dataset leaked",
                            "clean" if not leaked else "LEAK: %s" % leaked))
    print()
    print("ALL REQUIRED ITEMS PRESENT:", ok and not leaked)
    return 0 if (ok and not leaked) else 1


if __name__ == "__main__":
    raise SystemExit(main())
