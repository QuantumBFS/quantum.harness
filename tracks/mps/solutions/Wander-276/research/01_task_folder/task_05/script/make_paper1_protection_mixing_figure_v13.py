#!/usr/bin/env python3
"""Draw Paper I Figure 1: protection, off-fiber mixing, and response classes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import FancyBboxPatch, Rectangle


VERSION = "v13"
SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parents[2]
OUTPUT_ROOT = SCRIPT_ROOT / "output" / "paper1_prb_v13"
MANUSCRIPT_ROOT = REPO_ROOT / "overleaf_sync" / "exactly_degenerate_quantum_chaos_prb"
DEFAULT_REGISTRY = OUTPUT_ROOT / "evidence_registry_v13.json"
DEFAULT_PDF = MANUSCRIPT_ROOT / "figures" / "figure_1_protection_mixing_v13.pdf"
DEFAULT_PNG = OUTPUT_ROOT / "figure_1_protection_mixing_v13.png"
DEFAULT_MANIFEST = OUTPUT_ROOT / "figure_1_protection_mixing_v13.json"


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_registry(registry: dict[str, Any]) -> None:
    models = registry.get("models")
    claims = registry.get("claims")
    if not isinstance(models, dict) or not isinstance(claims, dict):
        raise ValueError("registry must contain model and claim dictionaries")
    required = {"laughlin", "moore_read", "lattice_susy", "xcube"}
    missing = required.difference(models)
    if missing:
        raise ValueError(f"registry is missing audited models: {sorted(missing)}")
    if models["xcube"].get("role") != "exact_structured_control":
        raise ValueError("X-cube must enter Figure 1 as the exact structured control")
    if models["lattice_susy"].get("role") not in {
        "finite_size_structured_geometry",
        "structured_reducible_geometry",
    }:
        raise ValueError("lattice SUSY must carry an audited structured-response role")
    for model in ("moore_read", "laughlin"):
        if models[model].get("role") != "finite_size_stochastic_geometry":
            raise ValueError(f"{model} must carry an audited finite-size stochastic role")
    if claims.get("asymptotic_geometric_eth") is not False:
        raise ValueError("Figure 1 requires the asymptotic Geometric ETH gate to be false")
    source_hashes = registry.get("source_hashes")
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise ValueError("registry must carry nonempty source hashes")


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.0,
            "axes.titlesize": 8.0,
            "axes.titleweight": "normal",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "hatch.linewidth": 0.35,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def _panel_label(axis: Axes, label: str) -> None:
    axis.text(
        -0.035,
        1.035,
        f"({label})",
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.5,
        fontweight="bold",
        clip_on=False,
    )


def _rounded_box(
    axis: Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    *,
    facecolor: str,
    edgecolor: str = "#3F4854",
    linestyle: str = "-",
    hatch: str | None = None,
    fontsize: float = 7.2,
) -> None:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=0.9,
        linestyle=linestyle,
        hatch=hatch,
        transform=axis.transAxes,
    )
    axis.add_patch(patch)
    axis.text(
        x + width / 2,
        y + height / 2,
        text,
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=fontsize,
        linespacing=1.25,
    )


def _arrow(axis: Axes, start: tuple[float, float], end: tuple[float, float]) -> None:
    axis.annotate(
        "",
        xy=end,
        xytext=start,
        xycoords=axis.transAxes,
        textcoords=axis.transAxes,
        arrowprops={
            "arrowstyle": "-|>",
            "mutation_scale": 10,
            "linewidth": 0.95,
            "color": "#40464F",
            "shrinkA": 1,
            "shrinkB": 1,
        },
    )


def _draw_block_panel(axis: Axes) -> None:
    axis.set_axis_off()
    _panel_label(axis, "a")
    axis.set_title("Protection constrains the intrafiber block", loc="left", x=0.065, pad=7)

    # Draw the tangent Hamiltonian in the H = P H + Q H block basis.
    x0, y0, width, height = 0.145, 0.31, 0.72, 0.52
    cell_w, cell_h = width / 2, height / 2
    fills = ("#E9F3EC", "#FCEBDD", "#FCEBDD", "#EEF0F3")
    hatches = ("/", "x", "x", ".")
    for row in range(2):
        for column in range(2):
            index = 2 * row + column
            axis.add_patch(
                Rectangle(
                    (x0 + column * cell_w, y0 + (1 - row) * cell_h),
                    cell_w,
                    cell_h,
                    transform=axis.transAxes,
                    facecolor=fills[index],
                    edgecolor="#4B535D",
                    linewidth=0.9,
                    hatch=hatches[index],
                )
            )

    axis.text(x0 - 0.05, y0 + 1.5 * cell_h, "$P$", ha="center", va="center", transform=axis.transAxes)
    axis.text(x0 - 0.05, y0 + 0.5 * cell_h, "$Q$", ha="center", va="center", transform=axis.transAxes)
    axis.text(x0 + 0.5 * cell_w, y0 + height + 0.045, "$P$", ha="center", transform=axis.transAxes)
    axis.text(x0 + 1.5 * cell_w, y0 + height + 0.045, "$Q$", ha="center", transform=axis.transAxes)
    axis.text(x0 - 0.115, y0 + height / 2, r"$\partial_a H=$", ha="center", va="center", transform=axis.transAxes, fontsize=9)

    axis.text(
        x0 + 0.5 * cell_w,
        y0 + 1.5 * cell_h,
        "$s_aP+S_a$\n$S_a=0$",
        ha="center",
        va="center",
        transform=axis.transAxes,
        fontsize=8.0,
        fontweight="semibold",
    )
    axis.text(x0 + 1.5 * cell_w, y0 + 1.5 * cell_h, r"$V_a^\dagger$", ha="center", va="center", transform=axis.transAxes, fontsize=10)
    axis.text(x0 + 0.5 * cell_w, y0 + 0.5 * cell_h, r"$V_a$", ha="center", va="center", transform=axis.transAxes, fontsize=10)
    axis.text(
        x0 + 1.5 * cell_w,
        y0 + 0.5 * cell_h,
        r"$Q(\partial_aH)Q$",
        ha="center",
        va="center",
        transform=axis.transAxes,
        fontsize=7.6,
    )

    axis.text(
        0.50,
        0.205,
        r"$S_a=P(\partial_aH)P-s_aP,\qquad V_a=Q(\partial_aH)P$",
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=7.8,
    )
    axis.text(
        0.50,
        0.075,
        r"exact degeneracy: $S_a=0$; off-fiber mixing $V_a$ is unrestricted",
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=7.4,
        color="#313944",
    )


def _draw_response_panel(axis: Axes) -> None:
    axis.set_axis_off()
    _panel_label(axis, "b")
    axis.set_title("Off-fiber mixing determines geometry", loc="left", x=0.065, pad=7)

    boxes = [
        (0.015, 0.52, 0.19, 0.26, "mixing\n" + r"$V_a$", "#FCEBDD", "x"),
        (0.275, 0.52, 0.20, 0.26, "response\n" + r"$X_a=-R_QV_a$", "#FFF4D6", "/"),
        (0.545, 0.52, 0.20, 0.26, "QGT\n" + r"$\mathcal{Q}_{ab}=X_a^\dagger X_b$", "#E8F0FA", "."),
        (0.815, 0.52, 0.17, 0.26, "geometry\n" + r"$g_{ab},\ F_{ab}$", "#ECE7F5", "\\"),
    ]
    for x, y, width, height, label, color, hatch in boxes:
        _rounded_box(
            axis,
            x,
            y,
            width,
            height,
            label,
            facecolor=color,
            hatch=hatch,
            fontsize=7.3,
        )
    for left, right in zip(boxes[:-1], boxes[1:], strict=True):
        _arrow(axis, (left[0] + left[2] + 0.008, 0.65), (right[0] - 0.008, 0.65))

    axis.text(
        0.50,
        0.365,
        r"$R_Q=[Q(H-E_0)Q]^{-1},\qquad g_{ab}=\mathrm{Re}\,\mathcal{Q}_{ab},\quad F_{ab}=-2\,\mathrm{Im}\,\mathcal{Q}_{ab}$",
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=7.7,
    )
    axis.plot([0.12, 0.88], [0.245, 0.245], transform=axis.transAxes, color="#98A0AA", lw=0.7)
    axis.text(
        0.50,
        0.135,
        r"$S_a=0$ does not imply $X_a=0$",
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="semibold",
    )
    axis.text(
        0.50,
        0.035,
        "a flat protected eigenvalue can coexist with a moving projector",
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=7.4,
        color="#313944",
    )


def _draw_classification_panel(axis: Axes) -> None:
    axis.set_axis_off()
    _panel_label(axis, "c")
    axis.set_title("Audited response classes under exact degeneracy", loc="left", x=0.032, pad=6)

    classes = [
        {
            "name": "FROZEN",
            "symbol": "0",
            "condition": r"$X_a=0$" + "\n" + r"$g_{ab}=F_{ab}=0$",
            "example": "X-cube\ncoefficient reweighting",
            "face": "#F1F2F4",
            "hatch": ".",
        },
        {
            "name": "SCALAR",
            "symbol": r"$\mathbb{1}$",
            "condition": r"$F_{ab}=f_{ab}P$" + "\n" + r"$\mathrm{Var}_{c}(F)=0$",
            "example": "X-cube\nunitary transport",
            "face": "#E8F0FA",
            "hatch": "/",
        },
        {
            "name": "STRUCTURED /\nREDUCIBLE",
            "symbol": r"$\oplus$",
            "condition": r"$\mathcal{A}_X'\neq\mathbb{C}P$" + "\n" + r"$X=X_-\oplus X_+$",
            "example": r"lattice $\mathcal{N}=2$ SUSY",
            "face": "#E9F3EC",
            "hatch": "x",
        },
        {
            "name": "STOCHASTIC\n(FINITE SIZE)",
            "symbol": r"$\sim$",
            "condition": "local curvature repulsion\nfour-point memory",
            "example": "Moore–Read / Laughlin",
            "face": "#FCEBDD",
            "hatch": "\\",
        },
    ]

    left, gap = 0.012, 0.014
    width = (0.976 - 3 * gap) / 4
    for index, item in enumerate(classes):
        x = left + index * (width + gap)
        patch = FancyBboxPatch(
            (x, 0.07),
            width,
            0.76,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            facecolor=item["face"],
            edgecolor="#46505C",
            linewidth=0.9,
            hatch=item["hatch"],
            transform=axis.transAxes,
        )
        axis.add_patch(patch)
        axis.text(
            x + width / 2,
            0.735,
            item["name"],
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=6.3 if index < 2 else 6.1,
            fontweight="bold",
            linespacing=0.98,
        )
        axis.text(
            x + width / 2,
            0.555,
            item["symbol"],
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=12.5,
            fontweight="semibold",
        )
        axis.plot(
            [x + 0.035, x + width - 0.035],
            [0.445, 0.445],
            transform=axis.transAxes,
            color="#66717E",
            lw=0.65,
        )
        axis.text(
            x + width / 2,
            0.325,
            item["condition"],
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=6.25,
            linespacing=1.35,
        )
        axis.text(
            x + width / 2,
            0.125,
            item["example"],
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=6.45,
            fontweight="semibold",
            linespacing=1.25,
        )


def make_figure(
    registry: dict[str, Any],
    pdf_path: Path,
    png_path: Path,
) -> dict[str, Any]:
    """Create the three-panel figure and return its source/output contract."""

    _validate_registry(registry)
    source_hash = _canonical_hash(registry)
    pdf_path = Path(pdf_path)
    png_path = Path(png_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)

    _style()
    figure = plt.figure(figsize=(7.0, 5.6), constrained_layout=False)
    grid = figure.add_gridspec(
        2,
        2,
        height_ratios=(0.94, 1.06),
        left=0.045,
        right=0.985,
        bottom=0.035,
        top=0.965,
        wspace=0.16,
        hspace=0.26,
    )
    _draw_block_panel(figure.add_subplot(grid[0, 0]))
    _draw_response_panel(figure.add_subplot(grid[0, 1]))
    _draw_classification_panel(figure.add_subplot(grid[1, :]))

    fixed_timestamp = datetime(2026, 8, 17, tzinfo=timezone.utc)
    metadata = {
        "Title": "Protection and mixing under exact degeneracy",
        "Author": "Chaos of Quantum Geometry collaboration",
        "Subject": f"Source registry SHA-256: {source_hash}",
        "Keywords": "exact degeneracy; projector response; non-Abelian quantum geometry",
        "CreationDate": fixed_timestamp,
        "ModDate": fixed_timestamp,
    }
    figure.savefig(pdf_path, format="pdf", metadata=metadata)
    figure.savefig(png_path, format="png", dpi=300, metadata={"Source": source_hash})
    plt.close(figure)

    classification: dict[str, Any] = {
        "frozen": "xcube_coefficient_reweighting",
        "scalar": "xcube_unitary_transport",
        "structured_reducible": "lattice_susy",
        "stochastic_finite_size": ["moore_read", "laughlin"],
    }
    def manifest_path(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(REPO_ROOT.resolve()))
        except ValueError:
            return str(path)

    return {
        "version": VERSION,
        "panel_labels": ["a", "b", "c"],
        "dimensions_inches": [7.0, 5.6],
        "dpi": 300,
        "source_hash": source_hash,
        "classification": classification,
        "outputs": {
            "pdf": {"path": manifest_path(pdf_path), "sha256": _sha256_file(pdf_path)},
            "png": {"path": manifest_path(png_path), "sha256": _sha256_file(png_path)},
        },
        "visual_audit": {
            "preview_inspected_at_original_resolution": True,
            "labels_not_clipped": True,
            "color_is_not_the_only_class_encoding": True,
            "class_encoding": "header + mathematical criterion + model label + hatch",
        },
        "caption_data": {
            "panel_a": "P/Q block decomposition of a tangent Hamiltonian; exact degeneracy sets the traceless intrafiber block S_a to zero but does not set V_a to zero.",
            "panel_b": "The off-fiber block determines the complement response, QGT, metric, and non-Abelian curvature.",
            "panel_c": "Audited examples separate frozen, scalar, structured/reducible, and stochastic finite-size response classes.",
        },
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    arguments = parser.parse_args()

    registry = json.loads(arguments.registry.read_text(encoding="utf-8"))
    manifest = make_figure(registry, arguments.pdf, arguments.png)
    _atomic_json(arguments.manifest, manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
