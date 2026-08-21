#!/usr/bin/env python3
"""Generate the publication figure for four-channel Wick factorization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT = SCRIPT_ROOT / "output"
SOURCE = OUTPUT / "matrix_element_geometric_eth_v3.json"
FIGURE_PDF = OUTPUT / "figure_6_wick_factorization_v3.pdf"
FIGURE_PNG = OUTPUT / "figure_6_wick_factorization_v3.png"
MANIFEST = OUTPUT / "figure_manifest_v3.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["STIXGeneral", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 8.4,
            "axes.titlesize": 9.2,
            "axes.labelsize": 8.6,
            "xtick.labelsize": 7.7,
            "ytick.labelsize": 7.7,
            "legend.fontsize": 7.1,
            "axes.linewidth": 0.75,
            "xtick.major.width": 0.65,
            "ytick.major.width": 0.65,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _panel_label(axis, label: str) -> None:
    axis.text(
        -0.15,
        1.08,
        label,
        transform=axis.transAxes,
        fontsize=9.2,
        fontweight="bold",
        va="top",
    )


def make_figure() -> dict[str, Any]:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if len(cases) != 3:
        raise RuntimeError("Figure 6 requires the full three-case artifact")
    _style()
    navy = "#24476b"
    orange = "#d8752d"
    teal = "#228b8d"
    grey = "#6d747d"
    pale = "#dfe8ef"
    N = np.asarray([case["N"] for case in cases], dtype=float)
    ranks = np.asarray([case["rank"] for case in cases], dtype=float)
    dimensions = np.asarray(
        [case["basis_dimension"] for case in cases],
        dtype=float,
    )
    gaps = np.asarray([case["external_gap"] for case in cases])
    physical = np.asarray(
        [case["physical_R4_median"] for case in cases]
    )
    physical_interval = np.asarray(
        [case["physical_R4_interval"] for case in cases]
    )
    structured = np.asarray([case["structured_R4"] for case in cases])
    gaussian = np.asarray(
        [case["gaussian_R4_interval"] for case in cases]
    )
    A_left = np.asarray([case["A_left_median"] for case in cases])
    B_right = np.asarray([case["B_right_median"] for case in cases])
    effective_external = ranks / B_right

    figure, axes = plt.subplots(
        2,
        2,
        figsize=(7.0, 5.15),
        constrained_layout=True,
    )

    axis = axes[0, 0]
    _panel_label(axis, "(a)")
    axis.plot(N, gaps, "o-", color=navy, lw=1.5, ms=4.3)
    axis.set_xlabel("particle number $N$")
    axis.set_ylabel("external gap $\\Delta$", color=navy)
    axis.tick_params(axis="y", colors=navy)
    axis.set_xticks(N)
    axis.set_title("Exact fixed-two-quasihole manifolds", pad=5)
    twin = axis.twinx()
    twin.semilogy(
        N,
        dimensions,
        "s--",
        color=grey,
        lw=1.2,
        ms=4.0,
    )
    twin.set_ylabel("$\\dim\\mathcal{H}$", color=grey)
    twin.tick_params(axis="y", colors=grey)
    annotation_offsets = ((0, 9), (0, -17), (0, 9))
    for x, gap, rank, offset in zip(
        N,
        gaps,
        ranks,
        annotation_offsets,
        strict=True,
    ):
        axis.annotate(
            f"$D={int(rank)}$",
            (x, gap),
            xytext=offset,
            textcoords="offset points",
            ha="center",
            color=navy,
            fontsize=7.1,
        )
    axis.grid(alpha=0.18, lw=0.55)

    axis = axes[0, 1]
    _panel_label(axis, "(b)")
    axis.fill_between(
        N,
        gaussian[:, 0],
        gaussian[:, 2],
        color=pale,
        label="covariance-matched Gaussian 95%",
        zorder=1,
    )
    axis.plot(
        N,
        gaussian[:, 1],
        "-",
        color=grey,
        lw=1.2,
        label="Gaussian median",
        zorder=2,
    )
    axis.errorbar(
        N,
        physical,
        yerr=np.vstack(
            [
                physical - physical_interval[:, 0],
                physical_interval[:, 1] - physical,
            ]
        ),
        fmt="o-",
        color=orange,
        lw=1.6,
        ms=4.5,
        capsize=2.5,
        label="local-density panels",
        zorder=4,
    )
    axis.plot(
        N,
        structured,
        "D--",
        color=teal,
        lw=1.25,
        ms=3.8,
        label="Fourier panel",
        zorder=3,
    )
    axis.set_xlabel("particle number $N$")
    axis.set_ylabel("four-channel residual $R_4$")
    axis.set_xticks(N)
    axis.set_title("Finite-size Wick test", pad=5)
    axis.legend(frameon=False, loc="upper right")
    axis.grid(alpha=0.18, lw=0.55)

    axis = axes[1, 0]
    _panel_label(axis, "(c)")
    physical_excess = physical - gaussian[:, 1]
    structured_excess = structured - gaussian[:, 1]
    axis.axhline(0.0, color="black", lw=0.7, alpha=0.55)
    axis.plot(
        N,
        physical_excess,
        "o-",
        color=orange,
        lw=1.6,
        ms=4.5,
        label="local-density excess",
    )
    axis.plot(
        N,
        structured_excess,
        "D--",
        color=teal,
        lw=1.25,
        ms=3.8,
        label="Fourier excess",
    )
    axis.set_xlabel("particle number $N$")
    axis.set_ylabel("$R_4-\\mathrm{median}(R_4^{\\rm G})$")
    axis.set_xticks(N)
    axis.set_title("Connected channel memory", pad=5)
    axis.legend(frameon=False)
    axis.grid(alpha=0.18, lw=0.55)
    axis.text(
        0.04,
        0.08,
        "resolved connected component at $N=5$",
        transform=axis.transAxes,
        color=orange,
        fontsize=7.3,
    )

    axis = axes[1, 1]
    _panel_label(axis, "(d)")
    axis.plot(
        N,
        A_left - 1.0,
        "o-",
        color=navy,
        lw=1.5,
        ms=4.2,
    )
    axis.set_xlabel("particle number $N$")
    axis.set_ylabel("target anisotropy $A_L-1$", color=navy)
    axis.tick_params(axis="y", colors=navy)
    axis.set_xticks(N)
    twin = axis.twinx()
    twin.plot(
        N,
        effective_external,
        "s--",
        color=grey,
        lw=1.25,
        ms=4.0,
    )
    twin.set_ylabel(
        "effective external dimension $M_{\\rm eff}=D/B_R$",
        color=grey,
    )
    twin.tick_params(axis="y", colors=grey)
    axis.set_title("Covariance envelope", pad=5)
    axis.grid(alpha=0.18, lw=0.55)
    axis.text(
        0.04,
        0.86,
        "registered branch:\n$\\bf{deformed\\ geometric\\ ETH}$",
        transform=axis.transAxes,
        color=orange,
        fontsize=7.5,
        va="top",
        bbox={
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.88,
            "pad": 1.5,
        },
    )
    axis.text(
        0.04,
        0.10,
        "$N=3,4,5$ finite-size baseline",
        transform=axis.transAxes,
        color="#444444",
        fontsize=6.9,
        bbox={
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.82,
            "pad": 1.2,
        },
    )

    figure.savefig(FIGURE_PDF)
    figure.savefig(FIGURE_PNG, dpi=300)
    plt.close(figure)
    manifest = (
        json.loads(MANIFEST.read_text(encoding="utf-8"))
        if MANIFEST.exists()
        else {}
    )
    manifest["figure_6_wick_factorization_v3"] = {
        "source": str(SOURCE.relative_to(SCRIPT_ROOT)),
        "source_sha256": _sha256(SOURCE),
        "pdf": str(FIGURE_PDF.relative_to(SCRIPT_ROOT)),
        "pdf_sha256": _sha256(FIGURE_PDF),
        "png": str(FIGURE_PNG.relative_to(SCRIPT_ROOT)),
        "png_sha256": _sha256(FIGURE_PNG),
        "width_inches": 7.0,
        "png_width_pixels": 2100,
        "result_branch": payload["result_branch"],
        "panels": [
            "genuine_manybody_sequence",
            "four_channel_residual",
            "non_gaussian_excess",
            "covariance_geometry",
        ],
    }
    _atomic_json(MANIFEST, manifest)
    return manifest["figure_6_wick_factorization_v3"]


def main() -> None:
    print(json.dumps(make_figure(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
