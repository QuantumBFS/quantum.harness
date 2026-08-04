#!/usr/bin/env python3
"""Generate the Hodge-resolved SUSY response inference figure and report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch

from merge_susy_hodge_pilot_v7 import OUTPUT_JSON as PILOT_JSON


SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"
INFERENCE_JSON = OUTPUT_ROOT / "susy_hodge_v7_N14_inference.json"
FIGURE_PDF = OUTPUT_ROOT / "figure_susy_hodge_geometric_eth_v7.pdf"
FIGURE_PNG = OUTPUT_ROOT / "figure_susy_hodge_geometric_eth_v7.png"
MANIFEST_JSON = OUTPUT_ROOT / "figure_susy_hodge_geometric_eth_v7.json"
REPORT_MD = OUTPUT_ROOT / "susy_hodge_geometric_eth_report_v7.md"
ALLOWED_BRANCHES = {
    "strong_covariance_universality",
    "hodge_resolved_geometric_eth",
    "cohomological_non_gaussian_class",
    "structured_cohomology",
    "feasibility_failure",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_text(path: Path, value: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("version") != "v7":
        raise ValueError(f"figure source has the wrong version: {path}")
    if not payload.get("passed") or not all(payload.get("checks", {}).values()):
        raise ValueError(f"figure source failed its checks: {path}")
    return payload


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["STIXGeneral", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 8.3,
            "axes.titlesize": 9.1,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 7.4,
            "ytick.labelsize": 7.4,
            "legend.fontsize": 6.8,
            "axes.linewidth": 0.75,
            "xtick.major.width": 0.65,
            "ytick.major.width": 0.65,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _panel_label(axis: Any, label: str) -> None:
    axis.text(
        -0.12,
        1.08,
        label,
        transform=axis.transAxes,
        fontsize=9.3,
        fontweight="bold",
        va="top",
    )


def _interval_error(interval: list[float]) -> tuple[float, np.ndarray]:
    values = np.asarray(interval, dtype=float)
    if values.shape == (2,):
        center = float(np.mean(values))
        return center, np.asarray([[center - values[0]], [values[1] - center]])
    if values.shape == (3,):
        center = float(values[1])
        return center, np.asarray([[center - values[0]], [values[2] - center]])
    raise ValueError("interval must contain two or three values")


def _draw_interval(
    axis: Any,
    x: float,
    interval: list[float],
    *,
    color: str,
    marker: str,
    zorder: int,
) -> None:
    center, errors = _interval_error(interval)
    axis.errorbar(
        [x],
        [center],
        yerr=errors,
        fmt=marker,
        color=color,
        ms=4.0,
        lw=1.15,
        capsize=2.0,
        zorder=zorder,
    )


def _branch_statement(branch: str) -> str:
    statements = {
        "strong_covariance_universality": (
            "Both covariance-only nulls cover the held-out sparse pair; the "
            "current data support strong finite-size covariance universality."
        ),
        "hodge_resolved_geometric_eth": (
            "Only the branch-resolved null covers the held-out pair; the Hodge "
            "decomposition supplies predictive information beyond collapsed covariance."
        ),
        "cohomological_non_gaussian_class": (
            "Neither covariance-only null covers the held-out pair, and the "
            "complete-realization uncertainty remains separated; a reproducible "
            "cohomological four-point memory survives the registered separable "
            "Hodge-covariance matching."
        ),
        "structured_cohomology": (
            "The generic response is not separated from the decomposable control "
            "under the frozen diagnostics."
        ),
        "feasibility_failure": (
            "At least one numerical, sealing, or preregistered inference gate failed; "
            "no scientific universality branch is claimed."
        ),
    }
    return statements[branch]


def _write_report(
    path: Path,
    pilot: dict[str, Any],
    inference: dict[str, Any],
    pilot_hash: str,
    inference_hash: str,
) -> None:
    branch = str(inference["selected_branch"])
    primary_lines = []
    for item in sorted(inference["primary_pair"], key=lambda value: value["sector"]):
        primary_lines.append(
            "- {sector}: observed median {observed:.8f}, physical bootstrap "
            "[{physical_low:.8f}, {physical_high:.8f}], collapsed prediction "
            "[{collapsed_low:.8f}, {collapsed_high:.8f}], Hodge prediction "
            "[{hodge_low:.8f}, {hodge_high:.8f}].".format(
                sector=item["sector"],
                observed=float(item["observed_median"]),
                physical_low=float(item["physical_bootstrap_interval"][0]),
                physical_high=float(item["physical_bootstrap_interval"][1]),
                collapsed_low=float(item["collapsed_prediction_interval"][0]),
                collapsed_high=float(item["collapsed_prediction_interval"][-1]),
                hodge_low=float(item["hodge_prediction_interval"][0]),
                hodge_high=float(item["hodge_prediction_interval"][-1]),
            )
        )
    report = f"""# Hodge-resolved Geometric ETH result report

## Verdict

Selected frozen branch: `{branch}`.

{_branch_statement(branch)}

## Established

- The charge-resolved cubic $\\mathcal N=2$ SYK BPS response splits into numerically orthogonal exact and coexact branches and agrees with the direct resolvent response under the registered tests.
- The pilot contains {len(pilot['groups'])} complete size/sector/panel groups and uses complete disorder realizations as its uncertainty unit.
- The held-out central/adjacent sparse pair was scored only after validating prediction SHA-256 `{inference['prediction_sha256']}`.

{chr(10).join(primary_lines)}

## Not established

- This is not conventional energy-resolved ETH, a real-time chaos result, or a thermodynamic-limit theorem.
- Generic $\\mathcal N=2$ SYK is an independent supersymmetric protection mechanism, but it is not a spatially local model; locality universality requires a later nilpotent lattice-supercharge benchmark.
- Berry-curvature chaos in this model is prior art. The contribution tested here is the pre-outcome response-complex/two-point prediction of a gauge-invariant four-channel statistic.
- The Gaussian nulls match the registered collapsed or branch-resolved marginal covariance data, not the complete entrywise covariance operator. Rejection therefore establishes failure of the frozen separable Hodge-Gaussian response law; by itself it does not distinguish intrinsic non-Gaussianity from unmodeled nonseparable two-point structure.

## Relation to prior work

- [Fu, Gaiotto, Maldacena, and Sachdev, *Supersymmetric SYK models*](https://arxiv.org/abs/1610.08917).
- [Chen, Colin-Ellerin, Mamroud, and Papadodimas, *Chaos of Berry curvature for BPS microstates*](https://arxiv.org/abs/2604.23287).
- [Chen, Lin, and Shenker, *BPS Chaos*](https://arxiv.org/abs/2407.19387).
- [Huijse and Schoutens, *Supersymmetry, lattice fermions, independence complexes and cohomology theory*](https://arxiv.org/abs/0903.0784).

## Provenance

- Pilot JSON SHA-256: `{pilot_hash}`.
- Held-out inference JSON SHA-256: `{inference_hash}`.
- Uncertainty unit: `{pilot['uncertainty_unit']}`.
"""
    _atomic_text(path, report)


def make_figure(
    *,
    pilot_json: Path = PILOT_JSON,
    inference_json: Path = INFERENCE_JSON,
    output_pdf: Path = FIGURE_PDF,
    output_png: Path = FIGURE_PNG,
    manifest_json: Path = MANIFEST_JSON,
    report_md: Path = REPORT_MD,
) -> dict[str, Any]:
    """Generate the final four-panel evidence figure and Markdown report."""

    pilot = _load(pilot_json)
    inference = _load(inference_json)
    branch = str(inference.get("selected_branch"))
    if branch not in ALLOWED_BRANCHES:
        raise ValueError("held-out inference has an unknown branch")
    groups = pilot.get("groups", [])
    expected_grid = {
        (N, sector, panel)
        for N in (8, 10, 12)
        for sector in ("central", "adjacent")
        for panel in ("sparse", "isotropic")
    }
    observed_grid = {
        (int(item["N"]), str(item["sector"]), str(item["panel_kind"]))
        for item in groups
    }
    if observed_grid != expected_grid:
        raise ValueError("pilot figure grid is incomplete")
    primary = inference.get("primary_pair", [])
    if {
        (int(item["N"]), str(item["sector"]), str(item["panel_kind"]))
        for item in primary
    } != {(14, "central", "sparse"), (14, "adjacent", "sparse")}:
        raise ValueError("held-out primary pair is incomplete")
    group_map = {
        (int(item["N"]), str(item["sector"]), str(item["panel_kind"])): item
        for item in groups
    }

    _style()
    colors = {
        "physical": "#1A1A1A",
        "collapsed": "#0072B2",
        "hodge": "#7A4EAB",
        "central": "#D55E00",
        "adjacent": "#009E73",
    }
    figure, axes = plt.subplots(2, 2, figsize=(7.0, 5.25), constrained_layout=True)

    axis = axes[0, 0]
    _panel_label(axis, "(a)")
    axis.set_axis_off()
    boxes = [
        (0.02, 0.58, 0.25, 0.25, "Laughlin parent\n" r"$B^\dagger B$", "#E8F2FA"),
        (0.39, 0.58, 0.23, 0.25, "protected fiber\n" r"$P(\lambda)$", "#F2F2F2"),
        (0.72, 0.70, 0.24, 0.18, "$X_-$ exact", "#FBE8DD"),
        (0.72, 0.44, 0.24, 0.18, "$X_+$ coexact", "#E3F3EC"),
    ]
    for x, y, width, height, label, color in boxes:
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.015",
            linewidth=0.8,
            edgecolor="#5C626A",
            facecolor=color,
            transform=axis.transAxes,
        )
        axis.add_patch(patch)
        axis.text(
            x + width / 2,
            y + height / 2,
            label,
            ha="center",
            va="center",
            transform=axis.transAxes,
        )
    axis.annotate(
        "",
        xy=(0.39, 0.705),
        xytext=(0.27, 0.705),
        xycoords=axis.transAxes,
        textcoords=axis.transAxes,
        arrowprops={"arrowstyle": "->", "lw": 1.0, "color": "#5C626A"},
    )
    axis.text(
        0.33,
        0.86,
        "one-sided",
        ha="center",
        va="bottom",
        transform=axis.transAxes,
        fontsize=7.2,
        color="#4F5660",
    )
    for y in (0.79, 0.53):
        axis.annotate(
            "",
            xy=(0.72, y),
            xytext=(0.62, 0.705),
            xycoords=axis.transAxes,
            textcoords=axis.transAxes,
            arrowprops={"arrowstyle": "->", "lw": 1.0, "color": "#5C626A"},
        )
    axis.text(
        0.50,
        0.24,
        r"$Q^2=0:\quad X=X_-\oplus X_+,\qquad X_-^\dagger X_+=0$",
        ha="center",
        transform=axis.transAxes,
        fontsize=8.8,
    )
    axis.text(
        0.50,
        0.08,
        "safe two-point Hodge data  $\\longrightarrow$  sealed four-channel test",
        ha="center",
        transform=axis.transAxes,
        fontsize=7.4,
        color="#4F5660",
    )
    axis.set_title("Protection mechanism becomes a response complex", pad=5)

    axis = axes[0, 1]
    _panel_label(axis, "(b)")
    for sector in ("central", "adjacent"):
        for panel, linestyle, marker in (
            ("sparse", "-", "o"),
            ("isotropic", "--", "s"),
        ):
            values = [
                group_map[(N, sector, panel)]["median_hodge_balance"]
                for N in (8, 10, 12)
            ]
            axis.plot(
                (8, 10, 12),
                values,
                color=colors[sector],
                ls=linestyle,
                marker=marker,
                lw=1.25,
                ms=3.8,
            )
    axis.set_xticks((8, 10, 12))
    axis.set_ylim(-0.03, 1.05)
    axis.set_xlabel("number of complex fermions $N$")
    axis.set_ylabel("median Hodge balance $\\eta_H$")
    axis.set_title("Two-point geometry resolves charge structure", pad=5)
    handles = [
        Line2D([0], [0], color=colors["central"], lw=1.3, label="central"),
        Line2D([0], [0], color=colors["adjacent"], lw=1.3, label="adjacent"),
        Line2D([0], [0], color="#555", ls="-", marker="o", lw=1.1, label="sparse"),
        Line2D([0], [0], color="#555", ls="--", marker="s", lw=1.1, label="isotropic"),
    ]
    axis.legend(handles=handles, frameon=False, ncol=2, loc="center right")

    axis = axes[1, 0]
    _panel_label(axis, "(c)")
    pilot_primary = [
        group_map[(N, sector, "sparse")]
        for N in (8, 10, 12)
        for sector in ("central", "adjacent")
    ]
    x_values = np.arange(len(pilot_primary), dtype=float)
    for x, item in zip(x_values, pilot_primary, strict=True):
        _draw_interval(
            axis,
            x - 0.17,
            item["physical_bootstrap_interval"],
            color=colors["physical"],
            marker="o",
            zorder=4,
        )
        _draw_interval(
            axis,
            x,
            item["collapsed_prediction_interval"],
            color=colors["collapsed"],
            marker="s",
            zorder=3,
        )
        _draw_interval(
            axis,
            x + 0.17,
            item["hodge_prediction_interval"],
            color=colors["hodge"],
            marker="^",
            zorder=3,
        )
    axis.set_xticks(
        x_values,
        [
            f"{item['N']}\n{'C' if item['sector'] == 'central' else 'A'}"
            for item in pilot_primary
        ],
    )
    axis.set_ylabel("normalized four-channel memory")
    axis.set_xlabel("pilot sparse panels: size / sector")
    axis.set_ylim(bottom=0.0)
    axis.set_title("Pilot: safe covariance does not fix four points", pad=5)
    axis.legend(
        handles=[
            Line2D([0], [0], color=colors["physical"], marker="o", lw=1.1, label="physical 95% bootstrap"),
            Line2D([0], [0], color=colors["collapsed"], marker="s", lw=1.1, label="collapsed 97.5%"),
            Line2D([0], [0], color=colors["hodge"], marker="^", lw=1.1, label="Hodge 97.5%"),
        ],
        frameon=False,
        loc="upper right",
    )

    axis = axes[1, 1]
    _panel_label(axis, "(d)")
    ordered_primary = sorted(primary, key=lambda item: item["sector"], reverse=True)
    for x, item in enumerate(ordered_primary):
        _draw_interval(
            axis,
            x - 0.17,
            item["physical_bootstrap_interval"],
            color=colors["physical"],
            marker="o",
            zorder=4,
        )
        _draw_interval(
            axis,
            x,
            item["collapsed_prediction_interval"],
            color=colors["collapsed"],
            marker="s",
            zorder=3,
        )
        _draw_interval(
            axis,
            x + 0.17,
            item["hodge_prediction_interval"],
            color=colors["hodge"],
            marker="^",
            zorder=3,
        )
    axis.set_xticks(
        np.arange(2),
        [str(item["sector"]) for item in ordered_primary],
    )
    axis.set_xlim(-0.55, 1.55)
    axis.set_ylim(bottom=0.0)
    axis.set_ylabel("normalized four-channel memory")
    axis.set_title("Held-out $N=14$: prediction sealed before opening", pad=5)
    axis.text(
        0.50,
        0.97,
        branch.replace("_", " "),
        transform=axis.transAxes,
        ha="center",
        va="top",
        fontsize=7.6,
        fontweight="bold",
        color="#8B1A1A" if branch != "strong_covariance_universality" else "#1B6E3C",
    )

    output_pdf = Path(output_pdf)
    output_png = Path(output_png)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_pdf, bbox_inches="tight")
    figure.savefig(output_png, dpi=300, bbox_inches="tight")
    plt.close(figure)

    pilot_hash = sha256(pilot_json)
    inference_hash = sha256(inference_json)
    _write_report(
        report_md,
        pilot,
        inference,
        pilot_hash,
        inference_hash,
    )
    checks = {
        "complete_pilot_grid": observed_grid == expected_grid,
        "complete_heldout_pair": len(primary) == 2,
        "known_selected_branch": branch in ALLOWED_BRANCHES,
        "figure_outputs_exist": output_pdf.is_file() and output_png.is_file(),
        "source_backed_report_exists": Path(report_md).is_file(),
    }
    manifest = {
        "version": "v7",
        "selected_branch": branch,
        "pilot_group_count": len(groups),
        "inputs": {
            Path(pilot_json).name: pilot_hash,
            Path(inference_json).name: inference_hash,
        },
        "outputs": {
            Path(output_pdf).name: sha256(output_pdf),
            Path(output_png).name: sha256(output_png),
            Path(report_md).name: sha256(report_md),
        },
        "plotted_values": {
            "pilot_groups": groups,
            "heldout_primary_pair": primary,
        },
        "caption": (
            "Hodge-resolved response-complex test across generic cubic "
            "supersymmetric cohomology: safe two-point charge structure, "
            "complete-realization pilot inference, and sealed held-out verdict."
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }
    _atomic_json(manifest_json, manifest)
    return manifest


def main() -> None:
    manifest = make_figure()
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
