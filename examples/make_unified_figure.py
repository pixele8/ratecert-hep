"""Create the publication-facing summary figure from the unified report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PALETTE = {
    "blue": "#0F4D92",
    "green": "#8BCF8B",
    "red": "#B64342",
    "teal": "#42949E",
    "violet": "#9A4D8E",
    "neutral": "#CFCECE",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.linewidth": 1.2,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelsize": 10,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def _public_panel(ax, cells: list[dict]) -> None:
    bits = sorted({int(row["bits"]) for row in cells})
    sample_sizes = sorted({int(row["sample_size_requested"]) for row in cells})
    colors = [PALETTE["blue"], PALETTE["teal"], PALETTE["violet"]]
    for bit, color in zip(bits, colors):
        values = []
        for n in sample_sizes:
            candidates = [
                row for row in cells
                if int(row["bits"]) == bit and int(row["sample_size_requested"]) == n
            ]
            values.append(max(float(row["quantization_sweep"]["max_abs_acceptance_delta"]) for row in candidates))
        ax.plot(sample_sizes, values, marker="o", linewidth=2.0, markersize=5, color=color, label=f"{bit} bit")
    ax.set_xscale("log")
    ax.set_xlabel("deployment events")
    ax.set_ylabel("max |Δ acceptance|")
    ax.set_title("(a) score quantization audit", loc="left", fontweight="bold")
    ax.grid(axis="y", color=PALETTE["neutral"], alpha=0.45, linewidth=0.8)
    ax.legend(frameon=False, title="score width", fontsize=8)


def _status_panel(ax, cells: list[dict]) -> None:
    exposures = sorted({float(row["exposure_s"]) for row in cells})
    budgets = sorted({float(row["rate_budget_requested_hz"]) for row in cells})
    matrix = np.zeros((len(exposures), len(budgets)), dtype=float)
    for i, exposure in enumerate(exposures):
        for j, budget in enumerate(budgets):
            selected = [
                row for row in cells
                if float(row["exposure_s"]) == exposure
                and float(row["rate_budget_requested_hz"]) == budget
            ]
            matrix[i, j] = np.mean([bool(row["certified"]) for row in selected])
    image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(budgets)), [f"{v:g}" for v in budgets])
    ax.set_yticks(range(len(exposures)), [f"{v:g}" for v in exposures])
    ax.set_xlabel("rate budget (Hz)")
    ax.set_ylabel("exposure (s)")
    ax.set_title("(b) certified fraction", loc="left", fontweight="bold")
    for i in range(len(exposures)):
        for j in range(len(budgets)):
            ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=9,
                    color="white" if matrix[i, j] > 0.55 else "black")
    cbar = ax.figure.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("fraction certified")


def _rate_panel(ax, cells: list[dict]) -> None:
    lsb_values = sorted({float(row["rate_lsb_requested_hz"]) for row in cells})
    bit_values = sorted({int(row["counter_bits_requested"]) for row in cells})
    colors = [PALETTE["blue"], PALETTE["teal"], PALETTE["violet"]]
    markers = {bit: marker for bit, marker in zip(bit_values, ("o", "s"))}
    for lsb, color in zip(lsb_values, colors):
        selected = [row for row in cells if float(row["rate_lsb_requested_hz"]) == lsb]
        for bit in bit_values:
            subset = [row for row in selected if int(row["counter_bits_requested"]) == bit]
            ax.scatter(
                [float(row["exposure_s"]) for row in subset],
                [float(row["upper_rate_hz"]) + float(row["quantization_margin_hz"] or 0.0) for row in subset],
                color=color,
                marker=markers[bit],
                s=28,
                alpha=0.82,
                label=f"LSB {lsb:g} Hz, {bit} bit",
            )
    for budget, color in zip(sorted({float(row["rate_budget_requested_hz"]) for row in cells}), (PALETTE["red"], PALETTE["green"])):
        ax.axhline(budget, color=color, linestyle="--", linewidth=1.1, alpha=0.85)
        ax.text(102, budget, f" budget {budget:g}", va="center", fontsize=8, color=color)
    ax.set_xscale("log")
    ax.set_xlabel("exposure (s)")
    ax.set_ylabel("upper rate + rate margin (Hz)")
    ax.set_title("(c) finite-sample rate contract", loc="left", fontweight="bold")
    ax.grid(axis="y", color=PALETTE["neutral"], alpha=0.45, linewidth=0.8)
    handles, labels = ax.get_legend_handles_labels()
    # Keep one legend entry for each LSB/bit combination and place it below.
    unique = dict(zip(labels, handles))
    ax.legend(unique.values(), unique.keys(), frameon=False, fontsize=7, ncol=2, loc="upper right")


def make_figure(report_path: str | Path, output_stem: str | Path) -> list[Path]:
    report_path = Path(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    public_cells = report["public_acceptance"]["cells"]
    rate_cells = report["explicit_rate"]["cells"]
    _style()
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.7), constrained_layout=True)
    _public_panel(axes[0], public_cells)
    _status_panel(axes[1], rate_cells)
    _rate_panel(axes[2], rate_cells)
    output_stem = Path(output_stem)
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    outputs = []
    for suffix in (".png", ".pdf"):
        destination = output_stem.with_suffix(suffix)
        fig.savefig(destination, dpi=300, bbox_inches="tight", pad_inches=0.05)
        outputs.append(destination)
    plt.close(fig)
    manifest = {
        "source_report": str(report_path.resolve()),
        "source_report_sha256": _sha256(report_path),
        "outputs": [str(path.resolve()) for path in outputs],
        "panels": {
            "a": "maximum observed acceptance change from score quantization, by score width and deployment prefix",
            "b": "fraction of rate cells certified, aggregated over LSB and counter width",
            "c": "one-sided upper rate plus declared rate-register margin, with budget lines",
        },
        "data_semantics": "LHCO is acceptance probability; explicit-rate panel uses declared Poisson exposure",
    }
    manifest_path = output_stem.with_name("figure_manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outputs.append(manifest_path)
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-stem", required=True)
    args = parser.parse_args(argv)
    outputs = make_figure(args.input, args.output_stem)
    print("wrote " + ", ".join(str(path) for path in outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

