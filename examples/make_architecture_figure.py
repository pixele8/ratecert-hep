"""Draw the paper-facing RateCert-HEP data-flow diagram."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Embed TrueType (Type 42) rather than the default Type 3 bitmap fonts; Elsevier
# production treats Type 3 as a defect.
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42


def _box(ax, x: float, y: float, w: float, h: float, title: str, body: str, color: str) -> None:
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=1.2, edgecolor=color, facecolor="#fbfdff",
    )
    ax.add_patch(patch)
    ax.text(x + 0.02, y + h - 0.035, title, fontsize=10, weight="bold", color=color,
            va="top", ha="left")
    ax.text(x + 0.02, y + h - 0.09, body, fontsize=8.2, color="#1f2937",
            va="top", ha="left", linespacing=1.35)


def _arrow(ax, start: tuple[float, float], end: tuple[float, float], label: str = "") -> None:
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=12,
                                 linewidth=1.2, color="#64748b"))
    if label:
        x = (start[0] + end[0]) / 2
        y = (start[1] + end[1]) / 2
        if abs(end[1] - start[1]) > abs(end[0] - start[0]):
            # Put vertical-edge labels beside the shaft, with a small opaque
            # patch so the label cannot be mistaken for part of the arrow.
            ax.text(x + 0.018, y, label, fontsize=7.8, color="#475569",
                    ha="left", va="center",
                    bbox=dict(facecolor="#fbfdff", edgecolor="none", pad=1.2))
        else:
            ax.text(x, y + 0.025, label, fontsize=7.8, color="#475569",
                    ha="center", va="bottom",
                    bbox=dict(facecolor="#fbfdff", edgecolor="none", pad=1.0))


def draw(output_stem: str | Path) -> tuple[Path, Path]:
    stem = Path(output_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10.2, 4.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("RateCert-HEP: independent blocks, explicit numerical contract, auditable certificate",
                 fontsize=12, weight="bold", pad=12)

    _box(ax, 0.03, 0.60, 0.22, 0.22, "Calibration block",
         "caller-supplied scores\nFixedPointSpec\nthreshold selection", "#2563eb")
    _box(ax, 0.03, 0.18, 0.22, 0.22, "Deployment block",
         "independent scores\nexposure or sample size\nblock identity", "#0f766e")
    _box(ax, 0.36, 0.60, 0.25, 0.22, "Score contract",
         "integer code + rounding\nrange / saturation audit\nq is frozen", "#7c3aed")
    _box(ax, 0.36, 0.18, 0.25, 0.22, "Finite-sample bound",
         "Poisson upper rate, or\nClopper--Pearson acceptance\ncomputed with survival functions", "#b45309")
    _box(ax, 0.72, 0.60, 0.24, 0.22, "Rate contract",
         "rate LSB + rounding\ncounter full scale\nprescale semantics", "#be123c")
    _box(ax, 0.72, 0.18, 0.24, 0.22, "Certificate JSON",
         "CERTIFIED / NOT_CERTIFIED\nupper bound + margin\nprovenance + reasons", "#334155")

    _arrow(ax, (0.25, 0.71), (0.36, 0.71), "select q")
    _arrow(ax, (0.25, 0.29), (0.36, 0.29), "count")
    _arrow(ax, (0.485, 0.60), (0.485, 0.40), "fixed q")
    _arrow(ax, (0.61, 0.71), (0.72, 0.71), "declare")
    _arrow(ax, (0.61, 0.29), (0.72, 0.29), "compare")
    _arrow(ax, (0.84, 0.60), (0.84, 0.40), "margin")

    ax.text(0.03, 0.055, "A public fixed-size sample stops at acceptance probability unless an external input flux is supplied.",
            fontsize=8.2, color="#475569", ha="left")
    fig.tight_layout()
    png = stem.with_suffix(".png")
    pdf = stem.with_suffix(".pdf")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png, pdf


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-stem", required=True)
    args = parser.parse_args()
    png, pdf = draw(args.output_stem)
    print(f"wrote {png} and {pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
