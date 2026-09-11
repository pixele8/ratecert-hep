import json

from ratecert.cli import main


def test_cli_writes_a_machine_readable_certificate(tmp_path):
    config = {
        "score": {
            "bits": 10,
            "fractional_bits": 8,
            "signed": False,
            "rounding": "nearest_even",
            "saturation": "error",
        },
        "certification": {
            "alpha": 0.05,
            "rate_budget_hz": 100.0,
            "prescale": 2,
            "rate_lsb_hz": 0.1,
            "rate_rounding": "nearest_even",
            "rate_counter_bits": 16,
        },
        "blocks": {"calibration": "cal-cli", "deployment": "deploy-cli"},
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    scores_path = tmp_path / "scores.csv"
    scores_path.write_text("0.1\n0.2\n0.99\n", encoding="utf-8")
    output_path = tmp_path / "certificate.json"
    assert main(
        [
            "--config",
            str(config_path),
            "--scores",
            str(scores_path),
            "--exposure-s",
            "10",
            "--threshold-code",
            "250",
            "--output",
            str(output_path),
        ]
    ) == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["status"] == "CERTIFIED"
    assert report["rate_resolution_hz"] == 0.1

    # A scientific refusal is a valid report, not a malformed command.
    config["certification"]["rate_budget_hz"] = 0.01
    config_path.write_text(json.dumps(config), encoding="utf-8")
    assert main(
        [
            "--config", str(config_path), "--scores", str(scores_path),
            "--exposure-s", "10", "--threshold-code", "250",
            "--output", str(output_path),
        ]
    ) == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["status"] == "NOT_CERTIFIED"
    assert report["reasons"]
