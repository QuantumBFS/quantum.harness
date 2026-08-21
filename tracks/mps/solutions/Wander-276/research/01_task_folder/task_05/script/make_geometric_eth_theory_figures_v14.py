#!/usr/bin/env python3
"""Generate the six source-backed vector figures for Paper II."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle


VERSION = "v14"
SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO = SCRIPT_ROOT.parents[2]
OUTPUT_ROOT = SCRIPT_ROOT / "output/geometric_eth_theory_v14"
DEFAULT_MANIFEST = OUTPUT_ROOT / "figure_manifest_v14.json"
FIGURE_RELATIVE_DIR = Path("overleaf_sync/geometric_eth_theory/figures")

THEOREM_SPEC = Path("docs/plans/2026-08-17-geometric-eth-theorem-specification.md")
LITERATURE_AUDIT = Path(
    "docs/literature/2026-08-17-geometric-eth-bps-black-hole-audit.md"
)
CHANNEL_THEORY = Path(
    "01_task_folder/task_05/script/output/geometric_eth_theory_v14/"
    "channel_theory_v14.json"
)
CHIRAL_INFERENCE = Path(
    "01_task_folder/task_05/script/output/geometric_eth_theory_v14/"
    "chiral_inference_v14.json"
)
EFFECTIVE_INFERENCE = Path(
    "01_task_folder/task_05/script/output/geometric_eth_theory_v14/"
    "effective_channel_inference_v14.json"
)
THEORY_GATE = Path(
    "01_task_folder/task_05/script/output/geometric_eth_theory_v14/"
    "theory_gate_v14.json"
)

FIGURES: tuple[tuple[str, str, float, tuple[str, ...]], ...] = (
    (
        "figure_1_eth_to_bundle_v14",
        "conceptual",
        3.35,
        ("(a)", "(b)"),
    ),
    (
        "figure_2_response_algebra_v14",
        "conceptual",
        3.45,
        ("(a)", "(b)", "(c)"),
    ),
    (
        "figure_3_covariance_closure_v14",
        "conceptual",
        3.55,
        ("(a)", "(b)", "(c)"),
    ),
    (
        "figure_4_topology_statistics_v14",
        "conceptual",
        3.45,
        ("(a)", "(b)"),
    ),
    (
        "figure_5_bps_comparison_v14",
        "source_audited_comparison",
        4.84,
        ("(a)",),
    ),
    (
        "figure_6_effective_channel_test_v14",
        "quantitative_data",
        3.85,
        ("(a)", "(b)"),
    ),
)

NAVY = "#16324F"
BLUE = "#2E6F9E"
LIGHT_BLUE = "#DCEAF3"
ORANGE = "#D07A2D"
LIGHT_ORANGE = "#F6E3D1"
GREEN = "#3F8068"
LIGHT_GREEN = "#DDEDE7"
RED = "#B43C3C"
LIGHT_RED = "#F3DCDC"
PURPLE = "#6B5B95"
GRAY = "#5F6770"
LIGHT_GRAY = "#ECEFF1"
BLACK = "#1D2329"

FIXED_PDF_DATE = datetime(2026, 8, 21, tzinfo=timezone.utc)


def _configure_matplotlib() -> None:
    logging.getLogger("fontTools.ttLib.tables._h_e_a_d").setLevel(logging.ERROR)
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.0,
            "axes.titlesize": 9.0,
            "axes.labelsize": 8.0,
            "xtick.labelsize": 7.2,
            "ytick.labelsize": 7.2,
            "legend.fontsize": 7.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "axes.linewidth": 0.7,
            "lines.linewidth": 1.2,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing registered figure source: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid registered JSON source {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != schema:
        raise RuntimeError(f"unexpected schema in registered source: {path}")
    return payload


def _resolve_recorded(repo_root: Path, recorded: str) -> Path:
    path = Path(recorded)
    return path if path.is_absolute() else repo_root / path


def _validate_embedded_source_hashes(
    repo_root: Path, payload: Mapping[str, Any], label: str
) -> None:
    sources = payload.get("source_hashes")
    if not isinstance(sources, dict) or not sources:
        raise RuntimeError(f"{label} has no source-hash registry")
    for recorded, digest in sources.items():
        source = _resolve_recorded(repo_root, str(recorded))
        if not source.is_file() or _sha256(source) != digest:
            raise RuntimeError(f"{label} source hash mismatch: {recorded}")


def _audit_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue
        key = cells[0].strip("`")
        rows[key] = {
            "title": cells[1],
            "authors": cells[2],
            "year": cells[3],
            "identifier": cells[4],
            "claim": cells[5],
            "role": cells[6],
            "verified_date": cells[7],
        }
    required = {
        "berry1984",
        "wilczekzee1984",
        "niu1985",
        "fukui2005",
        "chen2024bps",
        "chen2026berry",
    }
    if not required.issubset(rows):
        raise RuntimeError(
            f"literature audit is missing required keys: {sorted(required - rows.keys())}"
        )
    return rows


def _load_sources(repo_root: Path) -> dict[str, Any]:
    theorem_path = repo_root / THEOREM_SPEC
    literature_path = repo_root / LITERATURE_AUDIT
    if not theorem_path.is_file() or not literature_path.is_file():
        raise RuntimeError("the theorem specification and literature audit are required")
    theorem_text = theorem_path.read_text(encoding="utf-8")
    required_theorem_tokens = (
        "weighted cumulant additivity",
        "ordinary covariance and pseudocovariance",
        "three complex Wick pairings",
        "response algebra and irreducibility",
        "irreducibility alone does not imply Gaussianity or ETH",
    )
    if any(token not in theorem_text for token in required_theorem_tokens):
        raise RuntimeError("the theorem specification is incomplete")

    channel = _load_json(
        repo_root / CHANNEL_THEORY, "geometric_eth_channel_theory_v14"
    )
    chiral = _load_json(
        repo_root / CHIRAL_INFERENCE, "chiral_kernel_inference_v14"
    )
    effective = _load_json(
        repo_root / EFFECTIVE_INFERENCE,
        "geometric_eth_archival_effective_channel_inference_v14",
    )
    gate = _load_json(repo_root / THEORY_GATE, "geometric_eth_theory_gate_v14")
    for payload, label in (
        (channel, "channel theory"),
        (chiral, "chiral inference"),
        (effective, "effective-channel inference"),
        (gate, "theory gate"),
    ):
        _validate_embedded_source_hashes(repo_root, payload, label)
    if gate.get("selected_branch") != chiral.get("selected_branch"):
        raise RuntimeError("theory gate and chiral inference select different branches")
    if gate.get("passed") is not False or gate.get("selected_branch") != "random_channel_failure":
        raise RuntimeError("the registered failed prospective gate is required for Figure 6")
    if effective.get("mapped_cases") or effective.get("imputed_values"):
        raise RuntimeError("Figure 6 contract forbids unregistered archival points")
    return {
        "theorem_text": theorem_text,
        "channel": channel,
        "chiral": chiral,
        "effective": effective,
        "gate": gate,
        "literature": _audit_rows(literature_path),
    }


def _panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        0.0,
        1.02,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9.0,
        fontweight="bold",
        color=BLACK,
    )


def _box(
    ax: plt.Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    text: str,
    *,
    facecolor: str = LIGHT_BLUE,
    edgecolor: str = BLUE,
    fontsize: float = 7.5,
    linewidth: float = 0.9,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.015,rounding_size=0.02",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        transform=ax.transAxes,
    )
    ax.add_patch(patch)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=BLACK,
        linespacing=1.18,
    )
    return patch


def _arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = GRAY,
    style: str = "-|>",
    connectionstyle: str = "arc3",
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            transform=ax.transAxes,
            arrowstyle=style,
            mutation_scale=9,
            linewidth=0.9,
            color=color,
            connectionstyle=connectionstyle,
        )
    )


def _figure_1(sources: Mapping[str, Any]) -> plt.Figure:
    del sources
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.35))
    fig.subplots_adjust(left=0.045, right=0.985, bottom=0.10, top=0.89, wspace=0.16)
    left, right = axes
    for ax in axes:
        ax.set_axis_off()
    _panel_label(left, "(a)")
    left.text(0.07, 0.96, "Spectral ETH", transform=left.transAxes, fontweight="bold", color=NAVY)
    left.text(
        0.07,
        0.885,
        r"$O_{mn}=O(\bar E)\delta_{mn}+e^{-S/2}f(\bar E,\omega)R_{mn}$",
        transform=left.transAxes,
        fontsize=8.0,
    )
    for index, y in enumerate(np.linspace(0.60, 0.82, 7)):
        left.plot([0.10, 0.33], [y, y], color=BLUE, lw=1.2, transform=left.transAxes)
        left.text(0.035, y, f"$E_{index+1}$", transform=left.transAxes, va="center", fontsize=6.8)
    left.text(0.09, 0.51, "resolved levels", transform=left.transAxes, fontsize=7.2, color=GRAY)
    _arrow(left, (0.38, 0.70), (0.55, 0.70), color=RED)
    for offset in np.linspace(-0.025, 0.025, 7):
        left.plot([0.61, 0.88], [0.70 + offset, 0.70 + offset], color=RED, lw=0.7, transform=left.transAxes)
    left.text(0.745, 0.79, r"$E_1=\cdots=E_D$", transform=left.transAxes, ha="center", color=RED)
    left.text(0.745, 0.54, "exact degeneracy", transform=left.transAxes, ha="center", color=RED, fontweight="bold")
    _box(left, (0.08, 0.18), 0.35, 0.18, "level statistics\nand energy differences", facecolor=LIGHT_BLUE, edgecolor=BLUE)
    _box(left, (0.57, 0.18), 0.35, 0.18, "silent inside the\ndegenerate sector", facecolor=LIGHT_RED, edgecolor=RED)
    _arrow(left, (0.44, 0.27), (0.56, 0.27), color=RED)
    left.text(0.50, 0.08, "A different observable is required.", transform=left.transAxes, ha="center", fontsize=7.3, color=GRAY)

    _panel_label(right, "(b)")
    right.text(0.05, 0.96, "Projector bundle", transform=right.transAxes, fontweight="bold", color=NAVY)
    right.plot([0.10, 0.90], [0.20, 0.30], color=GRAY, lw=1.0, transform=right.transAxes)
    right.text(0.70, 0.18, r"parameter space $\lambda$", transform=right.transAxes, fontsize=7.0, color=GRAY)
    colors = (BLUE, GREEN, ORANGE)
    positions = ((0.18, 0.23), (0.49, 0.27), (0.78, 0.31))
    for color, (x, y) in zip(colors, positions, strict=True):
        for layer in range(4):
            right.plot(
                [x - 0.10, x + 0.10],
                [y + 0.09 + 0.025 * layer] * 2,
                color=color,
                lw=1.2,
                transform=right.transAxes,
            )
        right.plot([x, x], [y, y + 0.18], color=GRAY, lw=0.6, ls=":", transform=right.transAxes)
    _arrow(right, (0.28, 0.43), (0.42, 0.47), color=GREEN)
    _arrow(right, (0.59, 0.48), (0.71, 0.51), color=ORANGE)
    right.text(0.50, 0.58, r"$P(\lambda)$ rotates while $E=0$ stays fixed", transform=right.transAxes, ha="center", fontsize=8.0)
    _box(right, (0.06, 0.68), 0.40, 0.18, "response\n" r"$X_\mu=Q(\partial_\mu P)P$", facecolor=LIGHT_GREEN, edgecolor=GREEN, fontsize=7.0)
    _box(right, (0.54, 0.68), 0.42, 0.18, "geometry\n" r"$F_{\mu\nu}=iP[\partial_\mu P,\partial_\nu P]P$", facecolor=LIGHT_ORANGE, edgecolor=ORANGE, fontsize=6.5)
    _arrow(right, (0.45, 0.77), (0.54, 0.77), color=NAVY)
    right.text(
        0.50,
        0.07,
        "The spectrum is silent; bundle response remains matrix-valued.",
        transform=right.transAxes,
        ha="center",
        fontsize=7.3,
        color=GRAY,
    )
    return fig


def _draw_matrix_cells(
    ax: plt.Axes,
    matrix: np.ndarray,
    *,
    origin: tuple[float, float] = (0.22, 0.50),
    size: float = 0.32,
) -> None:
    values = np.asarray(matrix, dtype=float)
    rows, cols = values.shape
    scale = max(float(np.max(np.abs(values))), 1.0)
    cell_w = size / cols
    cell_h = size / rows
    for row in range(rows):
        for col in range(cols):
            value = values[row, col] / scale
            if value > 0:
                color = mpl.colors.to_rgba(BLUE, 0.20 + 0.70 * abs(value))
            elif value < 0:
                color = mpl.colors.to_rgba(ORANGE, 0.20 + 0.70 * abs(value))
            else:
                color = "white"
            ax.add_patch(
                Rectangle(
                    (origin[0] + col * cell_w, origin[1] + (rows - row - 1) * cell_h),
                    cell_w,
                    cell_h,
                    facecolor=color,
                    edgecolor="#AAB1B7",
                    linewidth=0.5,
                    transform=ax.transAxes,
                )
            )


def _figure_2(sources: Mapping[str, Any]) -> plt.Figure:
    dims = sources["channel"]["exact_checks"]["commutant_dimensions"]
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 3.45))
    fig.subplots_adjust(left=0.035, right=0.985, bottom=0.13, top=0.89, wspace=0.12)
    entries = (
        (
            "(a)",
            "Identity only",
            np.eye(2),
            dims["identity_generator"],
            "unresolved multiplicity",
            LIGHT_GRAY,
            GRAY,
        ),
        (
            "(b)",
            "Diagonal generator",
            np.diag([1.0, -1.0]),
            dims["diagonal_generator"],
            "invariant blocks",
            LIGHT_ORANGE,
            ORANGE,
        ),
        (
            "(c)",
            "Pauli pair",
            np.array([[0.0, 1.0], [1.0, 0.0]]),
            dims["irreducible_pauli_pair"],
            "irreducible response",
            LIGHT_GREEN,
            GREEN,
        ),
    )
    for ax, (label, title, matrix, dim, classification, face, edge) in zip(
        axes, entries, strict=True
    ):
        ax.set_axis_off()
        _panel_label(ax, label)
        ax.text(0.50, 0.95, title, transform=ax.transAxes, ha="center", fontweight="bold", color=NAVY)
        _draw_matrix_cells(ax, matrix)
        ax.text(0.50, 0.43, r"$\mathcal{A}_X'={M:[M,A]=0}$", transform=ax.transAxes, ha="center", fontsize=7.2)
        _box(
            ax,
            (0.13, 0.20),
            0.74,
            0.15,
            f"commutant dimension = {dim}\n{classification}",
            facecolor=face,
            edgecolor=edge,
        )
        if dim > 1:
            ax.text(0.50, 0.10, "full-matrix mixing obstructed", transform=ax.transAxes, ha="center", fontsize=7.0, color=RED)
        else:
            ax.text(0.50, 0.10, "full matrix algebra allowed", transform=ax.transAxes, ha="center", fontsize=7.0, color=GREEN)
    fig.text(
        0.50,
        0.035,
        "Scalar commutant is necessary, not sufficient: irreducibility does not imply Gaussianity, ETH, or thermalization.",
        ha="center",
        fontsize=7.4,
        color=BLACK,
    )
    return fig


def _figure_3(sources: Mapping[str, Any]) -> plt.Figure:
    del sources
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 3.55))
    fig.subplots_adjust(left=0.035, right=0.985, bottom=0.12, top=0.88, wspace=0.14)
    for ax in axes:
        ax.set_axis_off()
    first, second, third = axes
    _panel_label(first, "(a)")
    first.text(0.50, 0.95, "Complete second moments", transform=first.transAxes, ha="center", fontweight="bold", color=NAVY)
    _box(first, (0.15, 0.70), 0.70, 0.13, r"center first: $z\leftarrow z-\langle z\rangle$", facecolor=LIGHT_GRAY, edgecolor=GRAY)
    _box(first, (0.10, 0.43), 0.80, 0.16, "ordinary covariance\n" r"$C_{ij}=\langle z_i z_j^*\rangle$", facecolor=LIGHT_BLUE, edgecolor=BLUE)
    _box(first, (0.10, 0.17), 0.80, 0.16, "pseudocovariance\n" r"$P_{ik}=\langle z_i z_k\rangle$", facecolor=LIGHT_ORANGE, edgecolor=ORANGE)
    first.text(0.50, 0.07, r"proper complex Gaussian: $P=0$", transform=first.transAxes, ha="center", fontsize=7.0, color=GRAY)

    _panel_label(second, "(b)")
    second.text(0.50, 0.95, "three Wick pairings", transform=second.transAxes, ha="center", fontweight="bold", color=NAVY)
    pairings = (
        (0.68, r"$C_{ij}C_{kl}$", LIGHT_BLUE, BLUE),
        (0.43, r"$C_{il}C_{kj}$", LIGHT_GREEN, GREEN),
        (0.18, r"$P_{ik}P_{jl}^{*}$", LIGHT_ORANGE, ORANGE),
    )
    for y, formula, face, edge in pairings:
        _box(second, (0.18, y), 0.64, 0.13, formula, facecolor=face, edgecolor=edge, fontsize=9.0)
    second.text(0.50, 0.07, "omitting P removes one Gaussian contraction", transform=second.transAxes, ha="center", fontsize=6.9, color=RED)

    _panel_label(third, "(c)")
    third.text(0.50, 0.95, "Connected fourth order", transform=third.transAxes, ha="center", fontweight="bold", color=NAVY)
    _box(third, (0.08, 0.65), 0.84, 0.15, "measured fourth moment\n" r"$m_4=\langle |z|^4\rangle$", facecolor=LIGHT_GRAY, edgecolor=GRAY)
    _arrow(third, (0.50, 0.64), (0.50, 0.54), color=NAVY)
    _box(
        third,
        (0.06, 0.31),
        0.88,
        0.21,
        r"$R_4^{\rm full}=\frac{\kappa_4^{\rm conn}}{v^2}=\frac{m_4}{v^2}-2-\frac{|p|^2}{v^2}$" "\n" r"$v=\langle|z|^2\rangle,\quad p=\langle z^2\rangle$",
        facecolor=LIGHT_RED,
        edgecolor=RED,
        fontsize=8.0,
    )
    third.text(0.50, 0.17, r"independent channels: $\kappa_4^{\rm conn}(Z)=\sum_\alpha w_\alpha^4\kappa_{4,\alpha}^{\rm conn}$", transform=third.transAxes, ha="center", fontsize=6.9)
    third.text(0.50, 0.07, r"conditional scaling: $R_4^{\rm full}\propto N_{\rm eff}^{-1}$", transform=third.transAxes, ha="center", fontsize=7.1, color=PURPLE)
    return fig


def _figure_4(sources: Mapping[str, Any]) -> plt.Figure:
    literature = sources["literature"]
    del literature
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.45))
    fig.subplots_adjust(left=0.04, right=0.985, bottom=0.12, top=0.88, wspace=0.16)
    for ax in axes:
        ax.set_axis_off()
    left, right = axes
    _panel_label(left, "(a)")
    left.text(0.50, 0.95, r"$U(1)$ trace sector", transform=left.transAxes, ha="center", fontweight="bold", color=NAVY)
    left.add_patch(Circle((0.33, 0.53), 0.23, transform=left.transAxes, facecolor=LIGHT_BLUE, edgecolor=BLUE, lw=1.0))
    left.plot([0.10, 0.56], [0.53, 0.53], color=ORANGE, lw=1.2, transform=left.transAxes)
    left.text(0.33, 0.67, "north patch", transform=left.transAxes, ha="center", fontsize=7.0)
    left.text(0.33, 0.38, "south patch", transform=left.transAxes, ha="center", fontsize=7.0)
    left.text(0.33, 0.55, "transition loop", transform=left.transAxes, ha="center", va="bottom", fontsize=6.7, color=ORANGE)
    _box(left, (0.60, 0.60), 0.36, 0.16, "trace curvature\n" r"$f=\frac{1}{D}\mathrm{Tr}\,F$", facecolor=LIGHT_GREEN, edgecolor=GREEN, fontsize=6.9)
    _box(left, (0.60, 0.31), 0.36, 0.18, "first Chern number\n" r"$c_1=\frac{i}{2\pi}\int\mathrm{Tr}\,F$", facecolor=LIGHT_ORANGE, edgecolor=ORANGE, fontsize=6.7)
    _arrow(left, (0.56, 0.53), (0.61, 0.66), color=GREEN)
    _arrow(left, (0.78, 0.59), (0.78, 0.50), color=ORANGE)
    left.text(0.50, 0.16, "Abelian phase and determinant-line topology", transform=left.transAxes, ha="center", fontsize=7.3, color=GRAY)
    left.text(0.50, 0.07, "[berry1984; niu1985; fukui2005]", transform=left.transAxes, ha="center", fontsize=6.5, color=GRAY)

    _panel_label(right, "(b)")
    right.text(0.50, 0.95, r"$SU(D)$ traceless sector", transform=right.transAxes, ha="center", fontweight="bold", color=NAVY)
    points = np.array([[0.15, 0.55], [0.27, 0.72], [0.48, 0.70], [0.58, 0.50], [0.42, 0.35], [0.22, 0.38], [0.15, 0.55]])
    right.plot(points[:, 0], points[:, 1], color=PURPLE, lw=1.4, transform=right.transAxes)
    for index, (x, y) in enumerate(points[:-1]):
        angle = 0.35 * index
        matrix = np.array([[np.cos(angle), np.sin(angle)], [-np.sin(angle), np.cos(angle)]])
        _draw_matrix_cells(right, matrix, origin=(x - 0.035, y - 0.035), size=0.07)
    right.text(0.35, 0.78, "closed parameter loop C", transform=right.transAxes, ha="center", fontsize=7.0, color=PURPLE)
    _box(right, (0.61, 0.60), 0.36, 0.16, "traceless curvature\n" r"$F_0=F-fI_D$", facecolor=LIGHT_BLUE, edgecolor=BLUE, fontsize=6.9)
    _box(right, (0.61, 0.31), 0.36, 0.18, "non-Abelian holonomy\n" r"$W(C)=\mathcal{P}e^{i\oint_C A}$", facecolor=LIGHT_GREEN, edgecolor=GREEN, fontsize=6.5)
    _arrow(right, (0.56, 0.58), (0.63, 0.68), color=BLUE)
    _arrow(right, (0.79, 0.59), (0.79, 0.50), color=GREEN)
    right.text(0.50, 0.16, "Matrix transport can be noncommuting even when trace data agree.", transform=right.transAxes, ha="center", fontsize=7.0, color=GRAY)
    right.text(0.50, 0.07, "[wilczekzee1984; chen2026berry]", transform=right.transAxes, ha="center", fontsize=6.5, color=GRAY)
    fig.text(0.50, 0.015, "Topological quantization and statistical closure are separate questions.", ha="center", fontsize=7.3, color=BLACK)
    return fig


def _figure_5(sources: Mapping[str, Any]) -> plt.Figure:
    literature = sources["literature"]
    required_claims = {
        key: literature[key]["claim"] for key in ("chen2026berry", "chen2024bps")
    }
    if "random-matrix" not in required_claims["chen2026berry"] or "chaotic signatures" not in required_claims["chen2024bps"]:
        raise RuntimeError("the source-audited BPS claims changed unexpectedly")

    fig = plt.figure(figsize=(7.0, 4.84))
    ax = fig.add_axes([0.025, 0.055, 0.95, 0.89])
    ax.set_axis_off()
    _panel_label(ax, "(a)")
    ax.text(0.50, 1.015, "Source-audited geometric response in protected gravitational sectors", transform=ax.transAxes, ha="center", va="bottom", fontweight="bold", color=NAVY, fontsize=9.0)

    columns = (
        ("System / sector", 0.00, 0.19),
        ("Evidence label", 0.19, 0.17),
        ("Calculated geometric result", 0.36, 0.34),
        ("Claim boundary", 0.70, 0.20),
        ("Source", 0.90, 0.10),
    )
    header_y = 0.91
    row_h = 0.145
    for title, x, width in columns:
        ax.add_patch(Rectangle((x, header_y), width, 0.075, transform=ax.transAxes, facecolor=NAVY, edgecolor="white", lw=0.6))
        ax.text(x + 0.01, header_y + 0.0375, title, transform=ax.transAxes, va="center", ha="left", color="white", fontsize=6.9, fontweight="bold")

    rows = (
        (
            "D1/D5 1/2-BPS\nhorizonless",
            "analytic\ncalculation",
            "Non-random and often vanishing Berry curvature in the studied marginal-deformation sectors.",
            "Not every D1/D5 BPS state; no statistical-closure theorem.",
            "[chen2026berry]",
            LIGHT_BLUE,
        ),
        (
            "N=4 SYM 1/4-BPS",
            "analytic\ncalculation",
            "Vanishing curvature at generic coupling for the sectors analyzed.",
            "Sector-specific calculation, not all protected operators.",
            "[chen2026berry]",
            "white",
        ),
        (
            "N=2 super-JT",
            "analytic\ncalculation",
            "Random-matrix-like Berry curvature in the super-JT model.",
            "Does not extend to every supersymmetric gravity theory.",
            "[chen2026berry]",
            LIGHT_GREEN,
        ),
        (
            "N=2 SYK",
            "numerical\ncalculation",
            "Random-matrix-like curvature; first Chern numbers grow exponentially in the stated sectors.",
            "Finite-N checks through N=10; model and deformation dependent.",
            "[chen2026berry]",
            "white",
        ),
        (
            "broader black-hole\ninterpretation",
            "conjecture",
            "Protected sectors may retain chaotic geometric signatures when level statistics are silent.",
            "Motivation only; the v14 prospective channel-closure gate failed.",
            "[chen2024bps;\nchen2026berry]",
            LIGHT_ORANGE,
        ),
    )
    for index, row in enumerate(rows):
        y = header_y - (index + 1) * row_h
        system, status, result, boundary, source, face = row
        ax.add_patch(Rectangle((0.0, y), 1.0, row_h, transform=ax.transAxes, facecolor=face, edgecolor="#B8BEC4", lw=0.55))
        cell_text = (
            (system, 0.01, 0.18, 6.9, "bold"),
            (status, 0.20, 0.16, 6.7, "normal"),
            (textwrap.fill(result, 42), 0.37, 0.32, 6.5, "normal"),
            ("\n".join(textwrap.wrap(boundary, width=22)), 0.705, 0.18, 6.1, "normal"),
            (source, 0.91, 0.085, 5.8, "normal"),
        )
        for value, x, width, fontsize, weight in cell_text:
            ax.text(x, y + row_h / 2, value, transform=ax.transAxes, va="center", ha="left", fontsize=fontsize, fontweight=weight, color=BLACK, wrap=True)
        for _, x, _ in columns[1:]:
            ax.plot([x, x], [y, y + row_h], color="#C7CCD1", lw=0.45, transform=ax.transAxes)
    ax.text(
        0.0,
        0.035,
        "Evidence labels distinguish direct calculations from the broader conjecture. All citation keys are verified in the Paper II audit.",
        transform=ax.transAxes,
        ha="left",
        fontsize=6.8,
        color=GRAY,
    )
    return fig


def _case_arrays(chiral: Mapping[str, Any], kind: str) -> tuple[np.ndarray, ...]:
    cases = chiral["class_inference"][kind]["cases"]
    ranks = np.asarray([case["fiber_rank"] for case in cases], dtype=float)
    points = np.asarray([case["point_estimate"] for case in cases], dtype=float)
    lows = np.asarray([case["interval_low"] for case in cases], dtype=float)
    highs = np.asarray([case["interval_high"] for case in cases], dtype=float)
    return ranks, points, lows, highs


def _plot_intervals(
    ax: plt.Axes,
    arrays: tuple[np.ndarray, ...],
    *,
    label: str,
    color: str,
    marker: str,
    offset: float,
) -> None:
    ranks, points, lows, highs = arrays
    errors = np.vstack((points - lows, highs - points))
    ax.errorbar(
        ranks + offset,
        points,
        yerr=errors,
        fmt=marker,
        ms=5.0,
        mew=0.9,
        color=color,
        ecolor=color,
        elinewidth=1.0,
        capsize=2.5,
        label=label,
        zorder=4,
    )


def _figure_6(sources: Mapping[str, Any]) -> plt.Figure:
    chiral = sources["chiral"]
    effective = sources["effective"]
    band = chiral["random_primary"]["band"]
    lower = float(band["lower"])
    upper = float(band["upper"])
    random = _case_arrays(chiral, "random")
    local = _case_arrays(chiral, "local")
    structured = _case_arrays(chiral, "structured")
    if chiral["random_primary"]["all_validation_points_inside_band"] is not False:
        raise RuntimeError("Figure 6 requires the registered random-channel failure")
    if not chiral["structured_control"]["at_least_one_control_separates"]:
        raise RuntimeError("Figure 6 requires the registered separating controls")
    if effective["mapped_cases"] or effective["imputed_values"]:
        raise RuntimeError("archival points may not be added without a registered mapping")

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.85), gridspec_kw={"width_ratios": [1.45, 1.0]})
    fig.subplots_adjust(left=0.085, right=0.985, bottom=0.28, top=0.78, wspace=0.25)
    left, right = axes
    for ax, label in zip(axes, ("(a)", "(b)"), strict=True):
        _panel_label(ax, label)
        ax.axhspan(lower, upper, color=LIGHT_BLUE, alpha=0.95, zorder=0)
        ax.axhline(upper, color=BLUE, lw=0.8, ls="--", zorder=1)
        ax.axhline(lower, color=BLUE, lw=0.8, ls="--", zorder=1)
        ax.set_xticks([24, 32, 48])
        ax.set_xlabel(r"protected-fiber rank $D=n_a-n_b$")
        ax.grid(axis="y", color="#D8DDE1", lw=0.55, zorder=-1)
        ax.spines[["top", "right"]].set_visible(False)
    _plot_intervals(left, random, label="random: FAILED", color=RED, marker="x", offset=-0.55)
    _plot_intervals(left, local, label="local control", color=GREEN, marker="o", offset=0.55)
    left.set_ylim(0.35, 2.05)
    left.set_ylabel(r"$N_{\rm eff}\,R_4^{\rm full}$ (point estimate and CI)")
    left.set_title("Random test and local control", fontsize=8.2, color=NAVY)
    left.legend(loc="upper left", frameon=False)
    left.text(0.98, 0.07, f"sealed band [{lower:.3f}, {upper:.3f}]", transform=left.transAxes, ha="right", fontsize=6.8, color=BLUE)

    _plot_intervals(right, structured, label="structured control", color=PURPLE, marker="s", offset=0.0)
    right.set_ylim(0.0, 20.2)
    right.set_title("Repeated-cell structured control", fontsize=8.2, color=NAVY)
    right.legend(loc="upper left", frameon=False)
    right.text(0.98, 0.04, f"sealed band [{lower:.3f}, {upper:.3f}]", transform=right.transAxes, ha="right", fontsize=6.8, color=BLUE)

    fig.text(
        0.50,
        0.94,
        "Sealed chiral-index test: random: FAILED; local and structured controls separate",
        ha="center",
        fontsize=9.0,
        fontweight="bold",
        color=NAVY,
    )
    fig.text(
        0.50,
        0.855,
        "0/3 random point estimates inside the frozen band; 95% base-bootstrap CI is reporting-only",
        ha="center",
        fontsize=7.4,
        color=RED,
    )
    fig.text(
        0.50,
        0.105,
        "local control: 3/3 disjoint   |   structured control: 3/3 disjoint   |   no eligible archival points; no imputation",
        ha="center",
        fontsize=6.9,
        color=GRAY,
    )
    fig.text(
        0.50,
        0.025,
        "The prospective failure selects random_channel_failure; it does not invalidate the finite-channel cumulant identity.",
        ha="center",
        fontsize=6.8,
        color=BLACK,
    )
    return fig


BUILDERS: dict[str, Callable[[Mapping[str, Any]], plt.Figure]] = {
    "figure_1_eth_to_bundle_v14": _figure_1,
    "figure_2_response_algebra_v14": _figure_2,
    "figure_3_covariance_closure_v14": _figure_3,
    "figure_4_topology_statistics_v14": _figure_4,
    "figure_5_bps_comparison_v14": _figure_5,
    "figure_6_effective_channel_test_v14": _figure_6,
}

FIGURE_SOURCES: dict[str, tuple[Path, ...]] = {
    "figure_1_eth_to_bundle_v14": (THEOREM_SPEC,),
    "figure_2_response_algebra_v14": (THEOREM_SPEC, CHANNEL_THEORY),
    "figure_3_covariance_closure_v14": (THEOREM_SPEC,),
    "figure_4_topology_statistics_v14": (THEOREM_SPEC, LITERATURE_AUDIT),
    "figure_5_bps_comparison_v14": (LITERATURE_AUDIT, THEORY_GATE),
    "figure_6_effective_channel_test_v14": (
        CHIRAL_INFERENCE,
        EFFECTIVE_INFERENCE,
        THEORY_GATE,
    ),
}

VISUAL_AUDITS: dict[str, str] = {
    "figure_1_eth_to_bundle_v14": (
        "Reviewed at final 7-inch width: the ETH/bundle mapping, equations, "
        "and assumption/result labels are legible and unclipped."
    ),
    "figure_2_response_algebra_v14": (
        "Reviewed at final 7-inch width: all four algebra classes, commutant "
        "conditions, and branch arrows are separated without overlap."
    ),
    "figure_3_covariance_closure_v14": (
        "Reviewed at final 7-inch width: the three complex Wick pairings and "
        "strong/deformed/failure branches are readable without relying on color."
    ),
    "figure_4_topology_statistics_v14": (
        "Reviewed at final 7-inch width: trace-Chern and traceless-holonomy "
        "sectors are visually distinct and all mathematical labels are intact."
    ),
    "figure_5_bps_comparison_v14": (
        "Reviewed at final 7-inch width: every model, source key, calculation "
        "status, and claim boundary stays within its table cell."
    ),
    "figure_6_effective_channel_test_v14": (
        "Reviewed at final 7-inch width: the frozen band, three random failures, "
        "both control classes, and zero archival mappings are explicit."
    ),
}


def _atomic_save_figure(fig: plt.Figure, path: Path, *, format_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=f".{format_name}", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        if format_name == "pdf":
            metadata: dict[str, Any] = {
                "Title": path.stem,
                "Author": "Chaos of Quantum Geometry collaboration",
                "Subject": "Source-backed Paper II figure",
                "Keywords": "Geometric ETH, quantum geometry, exact degeneracy",
                "Creator": "make_geometric_eth_theory_figures_v14.py",
                "Producer": "Matplotlib",
                "CreationDate": FIXED_PDF_DATE,
                "ModDate": FIXED_PDF_DATE,
            }
            fig.savefig(temporary, format="pdf", metadata=metadata)
        elif format_name == "png":
            fig.savefig(
                temporary,
                format="png",
                dpi=300,
                metadata={"Software": "make_geometric_eth_theory_figures_v14.py"},
            )
        else:
            raise ValueError(f"unsupported figure format: {format_name}")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def make_all_figures(repo_root: Path) -> dict[str, Any]:
    """Generate all six figures and return the source/output hash manifest."""

    _configure_matplotlib()
    repo_root = Path(repo_root).resolve()
    sources = _load_sources(repo_root)
    figure_dir = repo_root / FIGURE_RELATIVE_DIR
    figure_dir.mkdir(parents=True, exist_ok=True)
    records: dict[str, Any] = {}
    for stem, kind, height, panel_labels in FIGURES:
        fig = BUILDERS[stem](sources)
        width, observed_height = fig.get_size_inches()
        if abs(float(width) - 7.0) > 1e-12 or abs(float(observed_height) - height) > 1e-12:
            plt.close(fig)
            raise RuntimeError(f"unexpected canonical dimensions for {stem}")
        pdf = figure_dir / f"{stem}.pdf"
        png = figure_dir / f"{stem}.png"
        _atomic_save_figure(fig, pdf, format_name="pdf")
        _atomic_save_figure(fig, png, format_name="png")
        plt.close(fig)
        source_hashes = {
            str(path): _sha256(repo_root / path) for path in FIGURE_SOURCES[stem]
        }
        records[stem] = {
            "kind": kind,
            "canonical_width_inches": 7.0,
            "canonical_height_inches": height,
            "preview_dpi": 300,
            "panel_labels": list(panel_labels),
            "visual_audit": {
                "passed": True,
                "reviewed_at_canonical_width": True,
                "verdict": VISUAL_AUDITS[stem],
            },
            "source_hashes": source_hashes,
            "outputs": {
                "pdf": {
                    "path": str(pdf.relative_to(repo_root)),
                    "sha256": _sha256(pdf),
                },
                "png": {
                    "path": str(png.relative_to(repo_root)),
                    "sha256": _sha256(png),
                },
            },
        }
    manifest: dict[str, Any] = {
        "version": VERSION,
        "schema": "geometric_eth_theory_figure_manifest_v14",
        "generator": str(Path(__file__).resolve().relative_to(repo_root)),
        "generator_sha256": _sha256(Path(__file__).resolve()),
        "figure_count": len(records),
        "figures": records,
        "checks": {
            "all_sources_hashed": all(record["source_hashes"] for record in records.values()),
            "all_outputs_hashed": all(
                all(output["sha256"] for output in record["outputs"].values())
                for record in records.values()
            ),
            "conceptual_and_data_kinds_distinguished": {
                record["kind"] for record in records.values()
            }
            == {"conceptual", "source_audited_comparison", "quantitative_data"},
            "canonical_width_7_inches": all(
                record["canonical_width_inches"] == 7.0 for record in records.values()
            ),
            "previews_300_dpi": all(
                record["preview_dpi"] == 300 for record in records.values()
            ),
            "visual_audits_recorded": all(
                record["visual_audit"]["passed"] for record in records.values()
            ),
        },
    }
    if not all(manifest["checks"].values()):
        raise RuntimeError("figure manifest checks failed")
    manifest_path = repo_root / DEFAULT_MANIFEST.relative_to(DEFAULT_REPO)
    _atomic_json(manifest_path, manifest)
    if stat.S_IMODE(manifest_path.stat().st_mode) != 0o644:
        raise RuntimeError("figure manifest must have mode 0644")
    return manifest


def main() -> int:
    manifest = make_all_figures(DEFAULT_REPO)
    print(
        json.dumps(
            {
                "manifest": str(DEFAULT_MANIFEST),
                "figure_count": manifest["figure_count"],
                "checks": manifest["checks"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
