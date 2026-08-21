#!/usr/bin/env python3
"""Generate the fixed-Chern Wilson-holonomy publication figure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lgeth.bundle_geometry import analyze_frame_bundle
from lgeth.holonomy import deform_orbital_mesh
from lgeth.lattice import BosonBasis
from lgeth.twist_bundle import default_checkpoint_path, load_twist_bundle


SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT = SCRIPT_ROOT / "output"
SOURCE_JSON = OUTPUT / "topological_holonomy_v3.json"
SOURCE_NPZ = OUTPUT / "topological_holonomy_v3.npz"
FIGURE_PDF = OUTPUT / "figure_7_topological_holonomy_v3.pdf"
FIGURE_PNG = OUTPUT / "figure_7_topological_holonomy_v3.png"
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
            "legend.fontsize": 7.0,
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


def _determinant_flow(
    plaquettes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    flux_by_transverse_slice = np.sum(
        np.angle(np.linalg.det(np.asarray(plaquettes))),
        axis=0,
    )
    transverse = np.arange(flux_by_transverse_slice.size + 1)
    transverse = transverse / flux_by_transverse_slice.size
    flow = np.concatenate(
        [[0.0], np.cumsum(flux_by_transverse_slice)]
    ) / (2.0 * np.pi)
    return transverse, flow


def _n4_determinant_flows(
    mesh: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, str]]:
    bundle = load_twist_bundle(
        default_checkpoint_path(4, mesh),
        expected_N=4,
        expected_n_flux=10,
        expected_rank=25,
        expected_mesh=mesh,
    )
    final_geometry = analyze_frame_bundle(
        bundle.coefficient_frames,
        deform_orbital_mesh(
            bundle.orbital_frames,
            g=1.0,
            seed=seed,
            commuting=False,
        ),
        BosonBasis(10, 4),
    )
    transverse, base_flow = _determinant_flow(
        bundle.geometry.plaquette
    )
    final_transverse, final_flow = _determinant_flow(
        final_geometry.plaquette
    )
    if not np.array_equal(transverse, final_transverse):
        raise RuntimeError("base and deformed determinant grids disagree")
    checkpoint_json = default_checkpoint_path(4, mesh)
    checkpoint_npz = checkpoint_json.with_suffix(".npz")
    return (
        transverse,
        base_flow,
        final_flow,
        {
            str(checkpoint_json.relative_to(SCRIPT_ROOT)): _sha256(
                checkpoint_json
            ),
            str(checkpoint_npz.relative_to(SCRIPT_ROOT)): _sha256(
                checkpoint_npz
            ),
        },
    )


def make_figure() -> dict[str, Any]:
    payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    if payload["result_branch"] != "fixed_chern_deformed_holonomy":
        raise RuntimeError("Figure 7 requires the accepted deformed branch")
    configuration = payload["configuration"]
    g_values = np.asarray(configuration["g_values"], dtype=float)
    seeds = np.asarray(configuration["generator_seeds"], dtype=np.int64)
    transverse, base_flow, final_flow, checkpoint_hashes = (
        _n4_determinant_flows(
            mesh=int(configuration["primary_mesh"]),
            seed=int(seeds[0]),
        )
    )
    with np.load(SOURCE_NPZ, allow_pickle=False) as arrays:
        gap_mean = [
            np.asarray(arrays[f"size_{index}_gap_mean"])
            for index in range(2)
        ]
        form_mean = [
            np.asarray(arrays[f"size_{index}_form_mean"])
            for index in range(2)
        ]
        commuting_gap = [
            np.asarray(arrays[f"size_{index}_commuting_gap"])
            for index in range(2)
        ]
        commuting_form = [
            np.asarray(arrays[f"size_{index}_commuting_form"])
            for index in range(2)
        ]
        cue_gap = [
            np.asarray(arrays[f"size_{index}_cue_gap"])
            for index in range(2)
        ]
        cue_form = [
            np.asarray(arrays[f"size_{index}_cue_form"])
            for index in range(2)
        ]
        cue_lower = [
            np.asarray(
                arrays[f"size_{index}_cue_form_simultaneous_lower"]
            )
            for index in range(2)
        ]
        cue_upper = [
            np.asarray(
                arrays[f"size_{index}_cue_form_simultaneous_upper"]
            )
            for index in range(2)
        ]

    _style()
    navy = "#24476b"
    orange = "#d8752d"
    teal = "#228b8d"
    grey = "#666b73"
    pale_navy = "#dce7f0"
    pale_orange = "#f3e3d7"
    figure, axes = plt.subplots(
        2,
        2,
        figsize=(7.0, 5.25),
        constrained_layout=True,
    )

    axis = axes[0, 0]
    _panel_label(axis, "(a)")
    for index, (size, color, marker) in enumerate(
        zip(payload["sizes"], (navy, orange), ("o", "s"), strict=True)
    ):
        chern = float(size["base_chern_integer"])
        axis.plot(
            g_values,
            np.full_like(g_values, chern),
            marker=marker,
            color=color,
            lw=1.45,
            ms=3.7,
            label=rf"$N={size['N']}$: $C_1={int(chern)}$",
        )
    axis.set_xlabel("isospectral deformation $g$")
    axis.set_ylabel("first Chern number $C_1$")
    axis.set_ylim(4.9, 11.0)
    axis.set_title("Topology and spectrum remain fixed", pad=5)
    axis.grid(alpha=0.18, lw=0.55)
    twin = axis.twinx()
    for size, color in zip(
        payload["sizes"],
        (navy, orange),
        strict=True,
    ):
        twin.plot(
            g_values,
            np.full_like(g_values, size["minimum_external_gap"]),
            ":",
            color=color,
            lw=1.1,
            alpha=0.75,
        )
    twin.set_ylabel("external gap $\\Delta$", color=grey)
    twin.tick_params(axis="y", colors=grey)
    axis.legend(frameon=False, loc="center left")
    axis.text(
        0.98,
        0.08,
        "$H_g=\\mathcal{U}_g H_0\\mathcal{U}_g^\\dagger$",
        transform=axis.transAxes,
        ha="right",
        color=grey,
        fontsize=7.2,
    )

    axis = axes[0, 1]
    _panel_label(axis, "(b)")
    axis.plot(
        transverse,
        base_flow,
        color=navy,
        lw=1.65,
        label="$g=0$",
    )
    axis.plot(
        transverse,
        final_flow,
        color=orange,
        lw=1.65,
        label="$g=1$",
    )
    axis.axhline(10.0, color=grey, lw=0.7, ls=":")
    axis.set_xlabel("transverse twist $\\theta_y/2\\pi$")
    axis.set_ylabel(
        "$\\frac{1}{2\\pi}\\sum_{y'<y}\\Phi_{\\det}(y')$"
    )
    axis.set_title("$N=4$: fixed winding, deformed flow", pad=5)
    axis.legend(frameon=False, loc="upper left")
    axis.grid(alpha=0.18, lw=0.55)
    axis.text(
        0.97,
        0.10,
        "both endpoints: $C_1=10$",
        transform=axis.transAxes,
        ha="right",
        color=orange,
        fontsize=7.2,
    )

    axis = axes[1, 0]
    _panel_label(axis, "(c)")
    for index, (color, pale, marker) in enumerate(
        zip(
            (navy, orange),
            (pale_navy, pale_orange),
            ("o", "s"),
            strict=True,
        )
    ):
        seed_interval = np.quantile(
            gap_mean[index],
            [0.025, 0.5, 0.975],
            axis=0,
        )
        axis.fill_between(
            g_values,
            seed_interval[0],
            seed_interval[2],
            color=pale,
            alpha=0.9,
            zorder=1,
        )
        axis.plot(
            g_values,
            seed_interval[1],
            marker=marker,
            color=color,
            lw=1.5,
            ms=3.7,
            label=rf"$N={payload['sizes'][index]['N']}$",
            zorder=3,
        )
        cue_interval = np.quantile(
            cue_gap[index],
            [0.025, 0.5, 0.975],
        )
        axis.axhline(
            cue_interval[1],
            color=color,
            lw=0.9,
            ls=":",
            alpha=0.9,
        )
    axis.plot(
        g_values,
        commuting_gap[1],
        "D--",
        color=grey,
        lw=1.15,
        ms=3.2,
        label="$N=4$ commuting control",
    )
    axis.axhspan(
        min(np.quantile(values, 0.025) for values in cue_gap),
        max(np.quantile(values, 0.975) for values in cue_gap),
        color="#ececef",
        alpha=0.75,
        zorder=0,
        label="CUE 95% range",
    )
    axis.set_xlabel("isospectral deformation $g$")
    axis.set_ylabel("Wilson circular gap ratio $\\langle r_W\\rangle$")
    axis.set_ylim(0.25, 0.77)
    axis.set_title("Holonomy changes, but remains non-CUE", pad=5)
    axis.legend(frameon=False, loc="upper left", ncol=2)
    axis.grid(alpha=0.18, lw=0.55)

    axis = axes[1, 1]
    _panel_label(axis, "(d)")
    size_index = 1
    rank = int(payload["sizes"][size_index]["rank"])
    stop = int(payload["sizes"][size_index]["cue_nonplateau_stop"])
    k_values = np.arange(1, stop + 1)
    base_form = form_mean[size_index][0, 0, :stop]
    final_form = np.median(
        form_mean[size_index][:, -1, :stop],
        axis=0,
    )
    control_form = commuting_form[size_index][-1, :stop]
    cue_mean = np.mean(cue_form[size_index][:, :stop], axis=0)
    lower = np.maximum(cue_lower[size_index][:stop], 1e-3)
    upper = cue_upper[size_index][:stop]
    axis.fill_between(
        k_values,
        lower,
        upper,
        color="#e5e5e8",
        alpha=0.9,
        label="CUE simultaneous band",
    )
    axis.plot(
        k_values,
        cue_mean,
        color="black",
        lw=1.0,
        label="CUE mean",
    )
    axis.plot(
        k_values,
        base_form,
        "o-",
        color=navy,
        lw=1.25,
        ms=3.2,
        label="$g=0$",
    )
    axis.plot(
        k_values,
        final_form,
        "s-",
        color=orange,
        lw=1.35,
        ms=3.2,
        label="$g=1$ median",
    )
    axis.plot(
        k_values,
        control_form,
        "D--",
        color=teal,
        lw=1.05,
        ms=2.8,
        label="commuting $g=1$",
    )
    axis.set_yscale("log")
    axis.set_xlabel("Wilson power $k$")
    axis.set_ylabel("$K_W(k)=|\\mathrm{Tr}\\,W^k|^2/D$")
    axis.set_title(rf"$N=4$, $D={rank}$: structured Wilson SFF", pad=5)
    axis.legend(frameon=False, loc="upper left", ncol=2)
    axis.grid(alpha=0.18, lw=0.55, which="both")

    figure.savefig(FIGURE_PDF)
    figure.savefig(FIGURE_PNG, dpi=300)
    plt.close(figure)
    manifest = (
        json.loads(MANIFEST.read_text(encoding="utf-8"))
        if MANIFEST.exists()
        else {}
    )
    manifest["figure_7_topological_holonomy_v3"] = {
        "source_json": str(SOURCE_JSON.relative_to(SCRIPT_ROOT)),
        "source_json_sha256": _sha256(SOURCE_JSON),
        "source_npz": str(SOURCE_NPZ.relative_to(SCRIPT_ROOT)),
        "source_npz_sha256": _sha256(SOURCE_NPZ),
        "checkpoint_hashes": checkpoint_hashes,
        "pdf": str(FIGURE_PDF.relative_to(SCRIPT_ROOT)),
        "pdf_sha256": _sha256(FIGURE_PDF),
        "png": str(FIGURE_PNG.relative_to(SCRIPT_ROOT)),
        "png_sha256": _sha256(FIGURE_PNG),
        "width_inches": 7.0,
        "png_width_pixels": 2100,
        "result_branch": payload["result_branch"],
        "panels": [
            "fixed_chern_and_gap",
            "determinant_winding",
            "wilson_gap_ratio",
            "wilson_form_factor",
        ],
    }
    _atomic_json(MANIFEST, manifest)
    return manifest["figure_7_topological_holonomy_v3"]


def main() -> None:
    print(json.dumps(make_figure(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
