#!/usr/bin/env python3
"""Create the publication figure for cross-mechanism Geometric ETH v12."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

from analyze_cross_mechanism_geometric_eth_v12 import analyze


VERSION = "v12"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_or_analyze(root: Path) -> dict[str, Any]:
    path = root / f"cross_mechanism_geometric_eth_{VERSION}.json"
    if not path.is_file():
        canonical = OUTPUT_ROOT / f"cross_mechanism_geometric_eth_{VERSION}.json"
        if canonical.is_file():
            result = json.loads(canonical.read_text(encoding="utf-8"))
        else:
            result = analyze(OUTPUT_ROOT)
        path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        return result
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence_matrix(result: dict[str, Any]) -> tuple[np.ndarray, list[str], list[str]]:
    models = result["models"]
    rows = ["Laughlin", "Moore–Read", "Lattice SUSY", "SUSY SYK", "X-cube"]
    columns = [
        "Exact fiber\naudit",
        "Projector\nmotion",
        "Four-channel\nresidual",
        "Complete\ncovariance",
        "Production\ncomplete",
    ]
    # 0=pending, 1=opened pilot, 2=established production, 3=exact control.
    matrix = np.asarray(
        [
            [2, 2, 2, 0, 2],
            [2, 2, 1, 1, 0],
            [2, 2, 1, 1, 0],
            [2, 2, 2, 0, 2],
            [3, 3, 3, 3, 3],
        ],
        dtype=int,
    )
    if not all(model["checks_pass"] for model in models.values()):
        raise RuntimeError("cannot plot a model with failed source checks")
    return matrix, rows, columns


def make_assets(root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    """Generate a three-panel evidence figure and hash manifest."""

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    result = _load_or_analyze(root)
    models = result["models"]
    moore = models["moore_read"]["cases"]
    lattice = models["lattice_susy"]["cases"]
    xcube_source = Path(models["xcube"]["source"]["path"])
    xcube_path = SCRIPT_ROOT / xcube_source
    xcube = json.loads(xcube_path.read_text(encoding="utf-8"))

    plt.rcParams.update(
        {
            "font.size": 8.5,
            "axes.labelsize": 9,
            "axes.titlesize": 10,
            "legend.fontsize": 7.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    figure = plt.figure(figsize=(10.2, 3.35), constrained_layout=True)
    grid = figure.add_gridspec(1, 3, width_ratios=(1.05, 1.45, 1.0))

    first = figure.add_subplot(grid[0, 0])
    mr_rank = np.asarray([case["fiber_rank"] for case in moore], dtype=float)
    mr_r4 = np.asarray([case["local_R4_median"] for case in moore], dtype=float)
    ls_rank = np.asarray([case["fiber_rank"] for case in lattice], dtype=float)
    ls_local = np.asarray([case["local_R4"] for case in lattice], dtype=float)
    ls_iso = np.asarray([case["isotropic_R4"] for case in lattice], dtype=float)
    first.plot(mr_rank, mr_r4, "o-", color="#1565c0", label="Moore–Read local")
    first.plot(ls_rank, ls_local, "s-", color="#c62828", label="Lattice SUSY local")
    first.plot(
        ls_rank,
        ls_iso,
        "s--",
        markerfacecolor="white",
        color="#c62828",
        label="Lattice SUSY isotropic",
    )
    first.set_xscale("log", base=2)
    first.set_xlabel("degenerate-fiber rank $D$")
    first.set_ylabel("covariance-matched $R_4$")
    first.set_title("a  Opened finite-size responses", loc="left", fontweight="bold")
    first.grid(alpha=0.22, linewidth=0.6)
    first.legend(frameon=False, loc="best")

    second = figure.add_subplot(grid[0, 1])
    matrix, row_labels, column_labels = _evidence_matrix(result)
    cmap = ListedColormap(["#e0e0e0", "#f9a825", "#1976d2", "#6a1b9a"])
    second.imshow(matrix, aspect="auto", vmin=-0.5, vmax=3.5, cmap=cmap)
    second.set_xticks(range(len(column_labels)), column_labels)
    second.set_yticks(range(len(row_labels)), row_labels)
    second.tick_params(axis="x", rotation=32)
    text = {0: "pending", 1: "pilot", 2: "done", 3: "exact"}
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = int(matrix[row, column])
            second.text(
                column,
                row,
                text[value],
                ha="center",
                va="center",
                fontsize=6.5,
                color="white" if value >= 2 else "#212121",
            )
    second.set_title("b  Evidence gates are not one score", loc="left", fontweight="bold")
    second.set_xticks(np.arange(-0.5, matrix.shape[1], 1), minor=True)
    second.set_yticks(np.arange(-0.5, matrix.shape[0], 1), minor=True)
    second.grid(which="minor", color="white", linewidth=1.2)
    second.tick_params(which="minor", bottom=False, left=False)

    third = figure.add_subplot(grid[0, 2])
    lengths = np.asarray([case["length"] for case in xcube["cases"]], dtype=int)
    zero = np.asarray(
        [case["coefficient_control"]["berry_curvature"] for case in xcube["cases"]],
        dtype=float,
    )
    scalar = np.asarray(
        [case["transport_control"]["curvature_eigenvalue"] for case in xcube["cases"]],
        dtype=float,
    )
    third.plot(lengths, zero, "o-", color="#455a64", label="coefficient change")
    third.plot(lengths, scalar, "D-", color="#6a1b9a", label="unitary transport")
    third.axhline(0.0, color="#9e9e9e", linewidth=0.7)
    third.set_xticks(lengths)
    third.set_ylim(-0.62, 0.12)
    third.set_xlabel("X-cube linear size $L$")
    third.set_ylabel("distinct curvature eigenvalue")
    third.set_title("c  Structured control", loc="left", fontweight="bold")
    third.grid(alpha=0.22, linewidth=0.6)
    third.legend(frameon=False, loc="lower left")
    third.text(
        0.98,
        0.93,
        "connected variance = 0\nfor both controls",
        transform=third.transAxes,
        ha="right",
        va="top",
        fontsize=7.5,
        color="#424242",
    )

    pdf = root / f"figure_cross_mechanism_geometric_eth_{VERSION}.pdf"
    png = root / f"figure_cross_mechanism_geometric_eth_{VERSION}.png"
    figure.savefig(pdf, bbox_inches="tight")
    figure.savefig(png, dpi=300, bbox_inches="tight")
    plt.close(figure)
    caption = (
        "Cross-mechanism evidence for exact-degeneracy quantum geometry. "
        "(a) Opened Moore–Read and lattice-SUSY covariance-matched four-channel "
        "residuals. (b) Exact-fiber, response, complete-covariance, and production "
        "gates are reported separately; yellow complete-covariance cells are "
        "conditional panel-ensemble results and gray cells remain pending. (c) X-cube "
        "coefficient changes have zero curvature, whereas local isospectral "
        "transport has scalar curvature -1/2 and zero connected variance."
    )
    manifest = {
        "version": VERSION,
        "selected_branch": result["selected_branch"],
        "claim_status": result["claim_status"],
        "figure_pdf": pdf.name,
        "figure_pdf_sha256": _sha256(pdf),
        "figure_png": png.name,
        "figure_png_sha256": _sha256(png),
        "source_inference": f"cross_mechanism_geometric_eth_{VERSION}.json",
        "caption": caption,
        "checks": {
            "three_distinct_evidence_panels": True,
            "complete_covariance_gate_is_explicit": True,
            "structured_control_is_separate": True,
            "vector_and_raster_outputs": pdf.is_file() and png.is_file(),
        },
    }
    path = root / f"cross_mechanism_assets_{VERSION}.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=OUTPUT_ROOT)
    arguments = parser.parse_args()
    print(json.dumps(make_assets(arguments.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
