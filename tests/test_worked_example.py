"""Regression tests for the checked-in worked example.

This is the CPC-required "comprehensive test run": sample input, the documented
command, and expected output.  These tests assert that the three documented
cases still reproduce their checked-in certificates exactly.

The certificate contains no time-, platform- or path-dependent field, so exact
structural equality is a safe assertion and is stronger than comparing a couple
of scalars.  If a future change perturbs any reported number, one of these
tests fails.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ratecert.cli import main

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "worked_example.json"
CONFIG_NARROW = REPO / "configs" / "worked_example_narrow_counter.json"
SCORES = REPO / "examples" / "data" / "scores.csv"
EXPECTED = REPO / "examples" / "expected"

CASES = [
    ("case1_certified.json", CONFIG, "250", "CERTIFIED"),
    ("case2_budget_refusal.json", CONFIG, "249", "NOT_CERTIFIED"),
    ("case3_counter_refusal.json", CONFIG_NARROW, "250", "NOT_CERTIFIED"),
]


def test_worked_example_inputs_exist():
    for path in (CONFIG, CONFIG_NARROW, SCORES):
        assert path.is_file(), f"missing worked-example input: {path}"
    assert SCORES.stat().st_size > 10_000


@pytest.mark.parametrize("expected_name,config,code,status", CASES)
def test_worked_example_case_reproduces(tmp_path, expected_name, config, code, status):
    out = tmp_path / expected_name
    rc = main(
        [
            "--config", str(config),
            "--scores", str(SCORES),
            "--exposure-s", "20",
            "--threshold-code", code,
            "--output", str(out),
        ]
    )
    assert rc == 0

    produced = json.loads(out.read_text(encoding="utf-8"))
    reference = json.loads((EXPECTED / expected_name).read_text(encoding="utf-8"))

    assert produced == reference, (
        "the worked example no longer reproduces its checked-in certificate"
    )
    assert produced["status"] == status


def test_case1_documents_the_pass_predicate():
    """The certified case must demonstrate that the predicate, not the point
    estimate, decides."""
    d = json.loads((EXPECTED / "case1_certified.json").read_text(encoding="utf-8"))
    assert d["count"] == 145
    assert d["point_rate_hz"] == 7.25
    assert d["upper_rate_hz"] == pytest.approx(8.778530889551678)
    assert d["quantization_margin_hz"] == pytest.approx(0.025)

    # upper rate + register margin must fit the budget
    assert d["upper_rate_hz"] + d["quantization_margin_hz"] <= d["rate_budget_hz"]
    # and the reported remaining margin must be exactly the slack
    slack = d["rate_budget_hz"] - d["upper_rate_hz"] - d["quantization_margin_hz"]
    assert d["deployment_margin_hz"] == pytest.approx(slack, abs=1e-9)

    # prescale is reported separately and must not touch the raw rate
    assert d["prescale"] == 4
    assert d["recorded_point_rate_hz"] == pytest.approx(d["point_rate_hz"] / 4)


def test_case2_refusal_is_marginal_and_structured():
    d = json.loads((EXPECTED / "case2_budget_refusal.json").read_text(encoding="utf-8"))
    assert d["certified"] is False
    assert d["reasons"] == [
        "finite-sample upper rate plus fixed-point margin exceeds budget"
    ]
    # refused by a narrow margin, not by a wide one
    over = d["upper_rate_hz"] + d["quantization_margin_hz"] - d["rate_budget_hz"]
    assert 0 < over < 0.2


def test_case3_reports_two_independent_range_reasons():
    d = json.loads((EXPECTED / "case3_counter_refusal.json").read_text(encoding="utf-8"))
    assert d["certified"] is False
    assert len(d["reasons"]) == 2
    assert any("overflow" in r for r in d["reasons"])
    assert any("full scale" in r for r in d["reasons"])
