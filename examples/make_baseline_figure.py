"""Figure for the baseline comparison (paper_cpc Sec. 5.3).

Left panel: empirical coverage of each bound construction against a known
ground-truth acceptance probability, at the per-cell alpha of the public sweep.
Right panel: the upper bounds each construction returns on the real 27-cell
deployment counts, with the pass boundary.

Style matches examples/make_diagnostic_figures.py.
"""

from __future__ import annotations

import argparse
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

METHOD_LABEL = {
    "clopper_pearson": "Clopper--Pearson (this work)",
    "wilson": "Wilson score",
    "normal_approx": "Normal (Wald)",
    "naive_empirical": "$K/n$ as a bound",
}
METHOD_COLOR = {
    "clopper_pearson": PALETTE["blue"],
    "wilson": PALETTE["teal"],
    "normal_approx": PALETTE["amber"],
    "naive_empirical": PALETTE["red"],
}


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


def _save(fig: plt.Figure, stem: Path) -> list[Path]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for suffix in (".png", ".pdf"):
        path = stem.with_suffix(suffix)
        fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.05)
        out.append(path)
    plt.close(fig)
    return out


def build(report: dict, stem: Path) -> list[Path]:
    _style()
    cov = report["part_b_coverage"]
    nominal = cov["nominal_coverage"]
    order = ["clopper_pearson", "wilson", "normal_approx", "naive_empirical"]

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.0), constrained_layout=True)

    # ---- (a) coverage ------------------------------------------------
    ax = axes[0]
    settings = cov["settings"]
    labels = ["$n=10^3$\n$p=0.005$", "$n=10^4$\n$p=0.005$",
              "$n=10^4$\n$p=0.01$", "$n=10^5$\n$p=0.01$"]
    x = np.arange(len(settings))
    width = 0.2
    for i, method in enumerate(order):
        vals = [s[method + "_coverage"] for s in settings]
        ax.bar(x + (i - 1.5) * width, vals, width,
               label=METHOD_LABEL[method], color=METHOD_COLOR[method],
               edgecolor="white", linewidth=0.6)
    ax.axhline(nominal, color=PALETTE["slate"], linestyle="--", linewidth=1.2)
    ax.text(len(settings) - 0.5, nominal - 0.045, "nominal %.4f" % nominal,
            ha="right", va="top", fontsize=8, color=PALETTE["slate"])
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylim(0.45, 1.02)
    ax.set_ylabel("empirical coverage of true $p$")
    ax.set_title("(a) coverage against a known ground truth", fontsize=9.5)
    ax.legend(fontsize=7.6, loc="lower left", framealpha=0.95, ncol=1)
    ax.grid(axis="y", color=PALETTE["grid"], linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)

    # ---- (b) certified cells on the real benchmark --------------------
    ax = axes[1]
    counts = report["part_a_public_cells"]["certified_counts"]
    total = report["part_a_public_cells"]["n_cells"]
    vals = [counts[m] for m in order]
    bars = ax.bar(np.arange(len(order)), vals,
                  color=[METHOD_COLOR[m] for m in order],
                  edgecolor="white", linewidth=0.8, width=0.62)
    for rect, v in zip(bars, vals):
        ax.text(rect.get_x() + rect.get_width() / 2, v + 0.5, str(v),
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.axhline(total, color=PALETTE["slate"], linestyle=":", linewidth=1.1)
    ax.set_xticks(np.arange(len(order)))
    ax.set_xticklabels([METHOD_LABEL[m].replace(" (this work)", "\n(this work)")
                        for m in order], fontsize=8.2)
    ax.set_ylim(0, total + 3.4)
    ax.set_ylabel("cells certified (of %d)" % total)
    ax.set_title("(b) certification decisions on identical cells", fontsize=9.5)
    ax.grid(axis="y", color=PALETTE["grid"], linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    ax.text(0.02, 0.97,
            "more certifiable is not better:\n$K/n$ certifies everything while\ncovering only ~51$-$56\\% of the time",
            transform=ax.transAxes, ha="left", va="top", fontsize=8.0,
            color=PALETTE["slate"])

    return _save(fig, stem)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/baseline_comparison.json")
    ap.add_argument("--output-stem", default="reports/figures/baseline_coverage")
    args = ap.parse_args()

    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    outs = build(report, Path(args.output_stem))
    for path in outs:
        print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
