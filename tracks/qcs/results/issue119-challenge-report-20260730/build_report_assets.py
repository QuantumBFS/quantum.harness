from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT = Path(__file__).resolve().parent


def method_comparison() -> None:
    raw_labels = [
        "This work  BP-TN χ=192",
        "This work  BP-TN χ=512",
        "Tracker  BP-TN χ=192",
        "Tracker  BP-TN χ=512",
        "This work  PEPO Dₒₚ=512",
    ]
    raw_values = np.array([0.8185618335, 0.8183229132, 0.8202512915, 0.8216584890, 0.8225508376])
    raw_errors = np.array([0.0019847196, 0.0019858354, 0.0, 0.0, 0.0003803891])
    colors = ["#0284c7", "#0369a1", "#f59e0b", "#d97706", "#059669"]
    markers = ["o", "s", "o", "s", "D"]
    filled = [True, True, False, False, True]

    fig, (ax, ax_context) = plt.subplots(
        1,
        2,
        figsize=(13.2, 6.1),
        gridspec_kw={"width_ratios": [3.5, 1.15], "wspace": 0.12},
    )
    ys = np.arange(len(raw_labels))[::-1]
    for y, value, error, color, marker, is_filled in zip(
        ys, raw_values, raw_errors, colors, markers, filled, strict=True
    ):
        ax.errorbar(
            value,
            y,
            xerr=error if error else None,
            fmt=marker,
            ms=10,
            mfc=color if is_filled else "white",
            mec=color,
            mew=2,
            ecolor=color,
            capsize=5,
            lw=2,
        )
        ax.text(value + 0.00038, y, f"{value:.6f}", va="center", fontsize=9.5)

    ax.set_yticks(ys, raw_labels)
    ax.set_xlabel("Raw operator Loschmidt echo  F")
    ax.set_xlim(0.8135, 0.8246)
    ax.grid(axis="x", alpha=0.22)
    ax.set_title("Like-for-like classical comparison", loc="left", weight="bold")
    ax.text(
        0.0,
        -0.16,
        "Horizontal bars: sampling SE (this-work BP-TN) or empirical "
        "ΔDₒₚ+Δχenv (PEPO). Tracker publishes no error bar.",
        transform=ax.transAxes,
        fontsize=9.5,
        color="#475569",
    )

    ax_context.set_facecolor("#f5f3ff")
    ax_context.errorbar(
        0.824,
        0,
        fmt="X",
        ms=12,
        mfc="white",
        mec="#9333ea",
        mew=2.3,
    )
    ax_context.text(0.824, 0.13, "0.824", ha="center", fontsize=10)
    ax_context.set_xlim(0.8135, 0.8275)
    ax_context.set_ylim(-0.7, 0.7)
    ax_context.set_yticks([0], ["IBM Heron R3"])
    ax_context.set_xlabel("Global-rescaled F")
    ax_context.grid(axis="x", alpha=0.18)
    ax_context.set_title("Hardware context", loc="left", weight="bold")
    ax_context.text(
        0.5,
        -0.16,
        "Different normalization;\nnot a direct raw benchmark.",
        transform=ax_context.transAxes,
        ha="center",
        fontsize=9.5,
        color="#6b21a8",
    )
    fig.suptitle("49×648 OLE baseline: keep raw and rescaled values visually separate", y=1.01)
    fig.tight_layout()
    fig.savefig(OUT / "ole-method-comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def method_positioning() -> None:
    fig, (ax_map, ax_repr) = plt.subplots(
        1,
        2,
        figsize=(13.2, 6.8),
        gridspec_kw={"width_ratios": [1.0, 1.35], "wspace": 0.2},
    )

    ax_map.set_xlim(0, 1)
    ax_map.set_ylim(0, 1)
    ax_map.axvline(0.5, color="#cbd5e1", lw=1.2)
    ax_map.axhline(0.5, color="#cbd5e1", lw=1.2)
    ax_map.set_xticks([0.2, 0.8], ["evolve states", "evolve operators"])
    ax_map.set_yticks([0.2, 0.8], ["sampled estimator", "direct contraction"])
    ax_map.set_title("Where the methods sit", loc="left", weight="bold")
    ax_map.grid(False)

    points = [
        (0.2, 0.2, "BP-TN", "#0369a1", 0.075),
        (0.8, 0.8, "PEPO-\nHeisenberg", "#047857", 0.075),
        (0.8, 0.2, "Pauli-path\nMonte Carlo", "#b45309", 0.075),
        (0.08, 0.08, "quantum hardware", "#7e22ce", 0.055),
    ]
    for x, y, label, color, dy in points:
        ax_map.scatter(x, y, s=260, color=color, edgecolor="white", linewidth=2, zorder=3)
        ax_map.text(x, y + dy, label, ha="center", va="bottom", fontsize=10.5, color=color)
    for spine in ax_map.spines.values():
        spine.set_color("#94a3b8")

    ax_repr.set_xlim(0, 10)
    ax_repr.set_ylim(0, 10)
    ax_repr.axis("off")
    ax_repr.set_title("Same heavy-hex graph, different local tensors", loc="left", weight="bold")

    coords = [(1.0, 7.0), (2.4, 8.2), (3.8, 7.0), (2.4, 5.7), (5.9, 7.0), (7.3, 8.2), (8.7, 7.0), (7.3, 5.7)]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4)]
    for offset, color, title in [(0, "#2563eb", "BP-TN state tensor  Aᵢ"), (4, "#059669", "PEPO operator tensor  Wᵢ")]:
        for a, b in edges[:4]:
            xa, ya = coords[a + offset]
            xb, yb = coords[b + offset]
            ax_repr.plot([xa, xb], [ya, yb], color="#64748b", lw=2.2, zorder=1)
        for idx in range(offset, offset + 4):
            x, y = coords[idx]
            ax_repr.scatter(x, y, s=420, color=color, edgecolor="white", linewidth=2.2, zorder=3)
            if offset == 0:
                ax_repr.plot([x, x], [y, y + 0.65], color="#0f172a", lw=1.8)
            else:
                ax_repr.plot([x, x], [y - 0.55, y + 0.55], color="#0f172a", lw=1.8)
        ax_repr.text(
            2.4 if offset == 0 else 7.3,
            4.85,
            title,
            ha="center",
            fontsize=11,
            color=color,
            weight="bold",
        )

    ax_repr.text(2.4, 4.25, "one physical leg / site\nvirtual bonds ≤ χ", ha="center", fontsize=10)
    ax_repr.text(7.3, 4.25, "two physical legs / site\nvirtual bonds ≤ Dₒₚ", ha="center", fontsize=10)

    bp_box = FancyBboxPatch(
        (0.45, 0.7),
        4.15,
        2.25,
        boxstyle="round,pad=0.12",
        facecolor="#eff6ff",
        edgecolor="#2563eb",
        linewidth=1.7,
    )
    pe_box = FancyBboxPatch(
        (5.35, 0.7),
        4.15,
        2.25,
        boxstyle="round,pad=0.12",
        facecolor="#ecfdf5",
        edgecolor="#059669",
        linewidth=1.7,
    )
    ax_repr.add_patch(bp_box)
    ax_repr.add_patch(pe_box)
    ax_repr.text(
        2.525,
        2.48,
        "BP-assisted\nreduced simple update",
        ha="center",
        va="center",
        fontsize=10.3,
        weight="bold",
        color="#1d4ed8",
    )
    ax_repr.text(2.525, 1.65, "messages → √env → QR", ha="center", fontsize=9.2)
    ax_repr.text(2.525, 1.15, "gate → SVD(χ) → undo gauge", ha="center", fontsize=9.2)
    ax_repr.text(
        7.425,
        2.48,
        "Vidal simple update\n(reduce-split)",
        ha="center",
        va="center",
        fontsize=10.3,
        weight="bold",
        color="#047857",
    )
    ax_repr.text(7.425, 1.65, "λ gauges → reduce → G†OG", ha="center", fontsize=9.2)
    ax_repr.text(7.425, 1.15, "SVD(Dₒₚ) → store new λ", ha="center", fontsize=9.2)
    ax_repr.add_patch(
        FancyArrowPatch((4.7, 1.82), (5.2, 1.82), arrowstyle="<->", mutation_scale=14, color="#64748b")
    )
    ax_repr.text(4.95, 0.42, "independent approximations", ha="center", fontsize=9.2, color="#475569")

    fig.tight_layout()
    fig.savefig(OUT / "tn-method-positioning.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    method_comparison()
    method_positioning()
