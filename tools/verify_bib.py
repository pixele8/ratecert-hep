"""Verify every bibliography entry against Crossref, INCLUDING author lists.

This exists because an earlier revision of references_cpc.bib carried a
fabricated fourth author (Riemann instead of Lopez on Lundberg2010TRolke) and a
wrong title and venue for the YODA reference.  Both survived an earlier manual
"Crossref-verified" pass, because that pass compared only titles and venues and
never compared author lists.  This script compares authors too, and exits
non-zero on any mismatch.

Usage:
    py tools/verify_bib.py            # verify
    py tools/verify_bib.py --offline  # parse and summarise only

Network: uses api.crossref.org. DataCite-prefixed DOIs (10.5281/*) are skipped
with a warning, since Crossref cannot serve them.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

BIB = pathlib.Path(__file__).resolve().parents[1] / "paper_cpc" / "references_cpc.bib"
UA = {"User-Agent": "ratecert-bib-check/1.0 (mailto:sunjianfeng10@hebut.edu.cn)"}
CROSSREF = "https://api.crossref.org/works/"


def parse_bib(text: str) -> list[dict]:
    """Minimal BibTeX field parser: enough for @article/@misc with brace values."""
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,]+),(.*?)\n\}", text, re.S):
        kind, key, body = m.group(1), m.group(2).strip(), m.group(3)
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{(.*?)\}\s*,?\s*(?=\w+\s*=|\Z)", body, re.S):
            fields[fm.group(1).lower()] = re.sub(r"\s+", " ", fm.group(2)).strip()
        fields["_kind"] = kind
        fields["_key"] = key
        entries.append(fields)
    return entries


def surname_list(bib_author: str) -> list[str]:
    """Extract surnames from a BibTeX author field."""
    if not bib_author:
        return []
    parts = re.split(r"\s+and\s+", bib_author)
    out = []
    for p in parts:
        p = p.strip()
        if not p or p.lower() in ("others",):
            continue
        if "{" in p:                      # {ALICE Collaboration} style
            out.append(p.strip("{}"))
        elif "," in p:
            out.append(p.split(",")[0].strip())
        else:
            out.append(p.split()[-1].strip())
    return out


def fetch(doi: str) -> dict | None:
    try:
        req = urllib.request.Request(CROSSREF + urllib.parse.quote(doi), headers=UA)
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())["message"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"_http404": True}
        return None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    entries = parse_bib(BIB.read_text(encoding="utf-8"))
    print("parsed %d entries from %s" % (len(entries), BIB.name))
    print()

    problems = []
    skipped = []

    for e in entries:
        key = e["_key"]
        doi = e.get("doi", "")
        if not doi:
            skipped.append((key, "no DOI in entry"))
            continue
        if doi.startswith("10.5281/"):
            skipped.append((key, "DataCite prefix, not served by Crossref"))
            continue
        if args.offline:
            continue

        msg = fetch(doi)
        if msg is None:
            problems.append((key, "NETWORK", "could not fetch " + doi))
            continue
        if msg.get("_http404"):
            problems.append((key, "DOI404", "Crossref cannot resolve " + doi))
            continue

        # ---- title ----
        cr_title = (msg.get("title") or [""])[0]
        bib_title = re.sub(r"[{}]", "", e.get("title", ""))
        norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
        ct, bt = norm(cr_title), norm(bib_title)
        if bt and ct and not (ct.startswith(bt[:40]) or bt.startswith(ct[:40])
                              or ct[:40] in bt or bt[:40] in ct):
            problems.append((key, "TITLE",
                             "bib=%r  crossref=%r" % (bib_title[:60], cr_title[:60])))

        # ---- authors (the check that was missing) ----
        cr_auth = [(a.get("family") or "") for a in msg.get("author", [])]
        bib_auth = surname_list(e.get("author", ""))
        if cr_auth:
            for s in bib_auth:
                if s.startswith("{"):
                    continue
                if s and not any(s.lower() in c.lower() or c.lower() in s.lower()
                                 for c in cr_auth):
                    problems.append((key, "AUTHOR",
                                     "bib surname %r not among Crossref authors %s"
                                     % (s, cr_auth[:6])))

        # ---- venue / volume / pages / year ----
        cr_j = (msg.get("container-title") or [""])[0]
        bib_j = e.get("journal", "")
        if bib_j and cr_j and norm(bib_j)[:18] not in norm(cr_j) \
                and norm(cr_j)[:18] not in norm(bib_j):
            problems.append((key, "VENUE", "bib=%r crossref=%r" % (bib_j[:40], cr_j[:40])))

        cr_vol = msg.get("volume")
        if cr_vol and e.get("volume") and e["volume"] != cr_vol:
            problems.append((key, "VOLUME", "bib=%s crossref=%s" % (e["volume"], cr_vol)))

        cr_page = msg.get("page") or msg.get("article-number") or ""
        if cr_page and e.get("pages"):
            a = re.sub(r"[^0-9]", "", e["pages"])
            b = re.sub(r"[^0-9]", "", cr_page)
            if a and b and a != b:
                problems.append((key, "PAGES", "bib=%s crossref=%s" % (e["pages"], cr_page)))

        cr_year = (msg.get("issued", {}).get("date-parts") or [[None]])[0][0]
        if cr_year and e.get("year"):
            try:
                if abs(int(e["year"]) - int(cr_year)) > 0:
                    problems.append((key, "YEAR", "bib=%s crossref=%s" % (e["year"], cr_year)))
            except ValueError:
                pass

    print("=" * 74)
    if problems:
        print("PROBLEMS FOUND: %d" % len(problems))
        print("=" * 74)
        for key, kind, detail in problems:
            print("  [%-8s] %-22s %s" % (kind, key, detail))
    else:
        print("NO PROBLEMS FOUND (title, AUTHORS, venue, volume, pages, year)")
        print("=" * 74)

    if skipped:
        print()
        print("SKIPPED (verify these by hand in the correct registry):")
        for key, why in skipped:
            print("  %-22s %s" % (key, why))

    return 1 if problems else 0


if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (used in fetch)
    raise SystemExit(main())
