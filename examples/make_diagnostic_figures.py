"""Create independent diagnostic figures from the checked-in benchmark reports.

The figures are deliberately derived from JSON reports rather than rerunning a
different analysis.  This keeps every plotted point tied to a certificate,
its finite-sample diagnostic, and the report hashes recorded in the manifest.
"""

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
    "teal": "#2F7F86",
    "violet": "#8A4F9F",
    "red": "#B64342",
    "amber": "#C27A1A",
    "green": "#2E7D4F",
    "slate": "#475569",
    "grid": "#CFCECE",
}


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
            # Embed TrueType (Type 42) rather than the default Type 3
            # bitmap fonts; Elsevier production treats Type 3 as a defect.
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 9.5,
            "axes.linewidth": 1.1,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelsize": 9.5,
            "axes.titlesize": 10.5,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if trials <= 0:
        return 0.0, 0.0
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2.0 * trials)) / denominator
    half = z * np.sqrt((p * (1.0 - p) + z * z / (4.0 * trials)) / trials) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def _save(fig: plt.Figure, stem: Path) -> list[Path]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for suffix in (".png", ".pdf"):
        path = stem.with_suffix(suffix)
        fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.05)
        outputs.append(path)
    plt.close(fig)
    return outputs


def _coverage_figure(coverage_report: dict, unified_report: dict, stem: Path) -> list[Path]:
    rows = sorted(coverage_report["rows"], key=lambda row: (row["n_events"], row["true_acceptance"]))
    poisson = [
        unified_report["explicit_rate"]["coverage_by_exposure"][key]
        for key in sorted(unified_report["explicit_rate"]["coverage_by_exposure"], key=float)
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0), constrained_layout=True)

    x = np.arange(len(rows))
    observed = np.asarray([row["coverage"] for row in rows], dtype=float)
    low = np.asarray([row["coverage_mc_95_low"] for row in rows], dtype=float)
    high = np.asarray([row["coverage_mc_95_high"] for row in rows], dtype=float)
    # The stored repeat interval can round to 0.9999999999999999 when the
    # observed coverage is exactly one; errorbar requires non-negative errors.
    low = np.minimum(low, observed)
    high = np.maximum(high, observed)
    axes[0].errorbar(
        x,
        observed,
        yerr=np.vstack((observed - low, high - observed)),
        fmt="o",
        color=PALETTE["blue"],
        ecolor=PALETTE["blue"],
        capsize=3,
        markersize=5,
        linewidth=1.2,
    )
    nominal = float(rows[0]["nominal_coverage"])
    axes[0].axhline(nominal, color=PALETTE["red"], linestyle="--", linewidth=1.2, label=f"nominal {nominal:.6f}")
    axes[0].set_xticks(x, [f"n={r['n_events']:,}\np={r['true_acceptance']:g}" for r in rows])
    axes[0].set_ylim(nominal - 0.0010, 1.00015)
    axes[0].set_ylabel("empirical coverage")
    axes[0].set_title("(a) binomial boundary stress", loc="left", fontweight="bold")
    axes[0].grid(axis="y", color=PALETTE["grid"], alpha=0.5, linewidth=0.7)
    axes[0].legend(frameon=False, fontsize=8, loc="lower left")

    x = np.arange(len(poisson))
    observed = np.asarray([row["coverage"] for row in poisson], dtype=float)
    intervals = np.asarray([_wilson_interval(int(row["covered"]), int(row["repeats"])) for row in poisson])
    axes[1].errorbar(
        x,
        observed,
        yerr=np.vstack((observed - intervals[:, 0], intervals[:, 1] - observed)),
        fmt="s",
        color=PALETTE["teal"],
        ecolor=PALETTE["teal"],
        capsize=3,
        markersize=5,
        linewidth=1.2,
    )
    nominal = float(poisson[0]["nominal_coverage"])
    axes[1].axhline(nominal, color=PALETTE["red"], linestyle="--", linewidth=1.2, label=f"nominal {nominal:.6f}")
    axes[1].set_xticks(x, [f"{row['exposure_s']:g} s" for row in poisson])
    axes[1].set_ylim(nominal - 0.0010, 1.00015)
    axes[1].set_ylabel("empirical coverage")
    axes[1].set_title("(b) Poisson exposure diagnostic", loc="left", fontweight="bold")
    axes[1].grid(axis="y", color=PALETTE["grid"], alpha=0.5, linewidth=0.7)
    axes[1].legend(frameon=False, fontsize=8, loc="lower left")

    return _save(fig, stem)


def _acceptance_figure(unified_report: dict, stem: Path) -> list[Path]:
    cells = unified_report["public_acceptance"]["cells"]
    bits_values = sorted({int(row["bits"]) for row in cells})
    targets = sorted({float(row["target_acceptance"]) for row in cells})
    colors = [PALETTE["blue"], PALETTE["teal"], PALETTE["violet"]]
    fig, axes = plt.subplots(1, len(bits_values), figsize=(11.0, 3.8), sharey=True, constrained_layout=True)
    if len(bits_values) == 1:
        axes = [axes]
    for ax, bits in zip(axes, bits_values):
        for target, color in zip(targets, colors):
            subset = sorted(
                [row for row in cells if int(row["bits"]) == bits and float(row["target_acceptance"]) == target],
                key=lambda row: int(row["sample_size"]),
            )
            x = np.asarray([int(row["sample_size"]) for row in subset], dtype=float)
            ratio = np.asarray([float(row["upper_acceptance"]) / target for row in subset])
            ax.plot(x, ratio, color=color, linewidth=1.5, alpha=0.9, label=f"target {100*target:g}%")
            for row, x_value, y_value in zip(subset, x, ratio):
                ax.scatter(
                    x_value,
                    y_value,
                    s=34,
                    marker="o" if bool(row["certified"]) else "x",
                    color=color,
                    linewidth=1.4,
                    zorder=3,
                )
        ax.axhline(1.0, color=PALETTE["red"], linestyle="--", linewidth=1.1)
        ax.set_xscale("log")
        ax.set_xticks([10_000, 50_000, 100_000], ["10k", "50k", "100k"])
        ax.set_xlabel("deployment prefix")
        ax.set_title(f"{bits}-bit score", loc="left", fontweight="bold")
        ax.grid(axis="y", color=PALETTE["grid"], alpha=0.5, linewidth=0.7)
    axes[0].set_ylabel("upper acceptance / target")
    axes[0].legend(frameon=False, fontsize=8, loc="lower left")
    fig.suptitle("Acceptance certification margin across public-data prefixes", fontsize=11, fontweight="bold")
    return _save(fig, stem)


def _refusal_figure(unified_report: dict, stem: Path) -> list[Path]:
    cells = unified_report["explicit_rate"]["cells"]
    exposures = sorted({float(row["exposure_s"]) for row in cells})
    categories = [
        ("certified", PALETTE["green"]),
        ("budget margin", PALETTE["red"]),
        ("counter full scale", PALETTE["amber"]),
        ("count overflow", PALETTE["violet"]),
    ]
    counts = {name: [] for name, _ in categories}
    for exposure in exposures:
        subset = [row for row in cells if float(row["exposure_s"]) == exposure]
        counts["certified"].append(sum(bool(row["certified"]) for row in subset))
        counts["budget margin"].append(sum(any("plus fixed-point margin exceeds budget" in reason for reason in row["reasons"]) for row in subset))
        counts["counter full scale"].append(sum(any("full scale" in reason for reason in row["reasons"]) for row in subset))
        counts["count overflow"].append(sum(any("overflow" in reason for reason in row["reasons"]) for row in subset))

    fig, ax = plt.subplots(figsize=(8.4, 4.1), constrained_layout=True)
    x = np.arange(len(exposures))
    width = 0.18
    offsets = np.linspace(-1.5 * width, 1.5 * width, len(categories))
    for offset, (name, color) in zip(offsets, categories):
        bars = ax.bar(x + offset, counts[name], width=width, color=color, label=name)
        for bar, value in zip(bars, counts[name]):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.2, str(value), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x, [f"{exposure:g} s" for exposure in exposures])
    ax.set_xlabel("declared exposure")
    ax.set_ylabel("cells / predicate count")
    ax.set_ylim(0, max(max(values) for values in counts.values()) + 3)
    ax.set_title("(a) Explicit-rate refusal predicates by exposure", loc="left", fontweight="bold")
    ax.grid(axis="y", color=PALETTE["grid"], alpha=0.5, linewidth=0.7)
    ax.legend(frameon=False, ncol=2, fontsize=8, loc="upper right")
    ax.text(
        0.0,
        -0.26,
        "Predicate counts can overlap: a single cell may fail both budget and counter-range checks.",
        transform=ax.transAxes,
        fontsize=8,
        color=PALETTE["slate"],
    )
    return _save(fig, stem)


def _assumption_figure(assumption_report: dict, stem: Path) -> list[Path]:
    rows = assumption_report["rows"]
    names = [row["scenario"].replace("_", "\n") for row in rows]
    coverage = np.asarray([float(row["coverage"]) for row in rows])
    nominal = float(rows[0]["nominal_coverage"])
    colors = [PALETTE["blue"], PALETTE["red"], PALETTE["amber"]]
    fig, ax = plt.subplots(figsize=(8.2, 4.0), constrained_layout=True)
    bars = ax.bar(np.arange(len(rows)), coverage, color=colors, width=0.58)
    for bar, value in zip(bars, coverage):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    ax.axhline(nominal, color=PALETTE["slate"], linestyle="--", linewidth=1.2, label=f"nominal {nominal:.2f}")
    ax.set_xticks(np.arange(len(rows)), names)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("coverage of nominal 8 Hz mean rate")
    ax.set_title("Poisson assumption boundary: same nominal mean, different window process", loc="left", fontweight="bold")
    ax.grid(axis="y", color=PALETTE["grid"], alpha=0.5, linewidth=0.7)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    ax.text(
        0.0,
        -0.25,
        "Burst and mixed-rate windows intentionally violate the fixed-rate Poisson model; low coverage marks the contract boundary.",
        transform=ax.transAxes,
        fontsize=8,
        color=PALETTE["slate"],
    )
    return _save(fig, stem)


def make_figures(
    unified_path: str | Path,
    coverage_path: str | Path,
    output_dir: str | Path,
    assumption_path: str | Path | None = None,
) -> list[Path]:
    unified_path = Path(unified_path)
    coverage_path = Path(coverage_path)
    output_dir = Path(output_dir)
    unified = json.loads(unified_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    assumption = None
    if assumption_path is not None:
        assumption_path = Path(assumption_path)
        assumption = json.loads(assumption_path.read_text(encoding="utf-8"))
    _style()
    outputs: list[Path] = []
    outputs.extend(_coverage_figure(coverage, unified, output_dir / "coverage_diagnostics"))
    outputs.extend(_acceptance_figure(unified, output_dir / "acceptance_certification"))
    outputs.extend(_refusal_figure(unified, output_dir / "refusal_taxonomy"))
    if assumption is not None:
        outputs.extend(_assumption_figure(assumption, output_dir / "assumption_boundary"))
    manifest = {
        "source_reports": {
            "unified": str(unified_path.resolve()),
            "coverage": str(coverage_path.resolve()),
        },
        "source_sha256": {"unified": _sha256(unified_path), "coverage": _sha256(coverage_path)},
        "outputs": [str(path.resolve()) for path in outputs],
        "figures": {
            "coverage_diagnostics": "Monte-Carlo coverage with 95% repeat uncertainty for binomial and Poisson diagnostics",
            "acceptance_certification": "public-data finite-sample upper acceptance divided by requested target; x marks are refusals",
            "refusal_taxonomy": "explicit-rate predicate counts by exposure; categories are intentionally overlapping",
        },
    }
    if assumption_path is not None:
        manifest["source_reports"]["assumption_boundary"] = str(assumption_path.resolve())
        manifest["source_sha256"]["assumption_boundary"] = _sha256(assumption_path)
        manifest["figures"]["assumption_boundary"] = "coverage under stationary Poisson, burst, and mixed-rate windows with the same nominal mean"
    manifest_path = output_dir / "diagnostic_figure_manifest.json"
    _write_text_lf(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    outputs.append(manifest_path)
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unified", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--assumption")
    args = parser.parse_args(argv)
    outputs = make_figures(args.unified, args.coverage, args.output_dir, args.assumption)
    print("wrote " + ", ".join(str(path) for path in outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
