#!/usr/bin/env python3
"""Assemble Phase 9 validation artifacts from completed cell summaries."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lrtfim.phase8_scaling import sensitivity_regression
from lrtfim.phase9_protocol import (
    MEAN_FIELD_BENCHMARKS,
    analyze_mean_field,
    analyze_nn,
    published_gamma_comparison,
)


OKABE_ITO_BLUE = "#0072B2"
OKABE_ITO_ORANGE = "#E69F00"


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
        stream.flush()
    temporary.replace(path)


def atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload)
    temporary.replace(path)


def _load_summaries(
    root: Path,
    *,
    sigma: float | None = None,
) -> dict[tuple[int, float, str], dict]:
    summaries = {}
    for path in sorted(root.rglob("summary.json")):
        summary = json.loads(path.read_text())
        settings = summary.get("settings", {})
        stored_sigma = settings.get("sigma")
        if sigma is not None and (
            stored_sigma is None
            or not np.isclose(float(stored_sigma), sigma)
        ):
            continue
        sectors = settings.get("sectors")
        if not sectors:
            sector = settings.get("sector")
            sectors = [] if sector is None else [sector]
        if len(sectors) != 1:
            continue
        key = (
            int(settings["length"]),
            float(settings["gamma"]),
            str(sectors[0]),
        )
        if key in summaries:
            raise ValueError(f"duplicate Phase 9 summary for {key}")
        summaries[key] = summary
    return summaries


def _branch(
    root: Path,
    analyzer: Callable[[dict], dict],
    *,
    sigma: float | None = None,
) -> dict:
    if not root.is_dir():
        return {
            "status": "unresolved",
            "reason": f"summary root not found: {root}",
        }
    try:
        result = analyzer(_load_summaries(root, sigma=sigma))
    except (KeyError, ValueError, TypeError) as error:
        return {"status": "unresolved", "reason": str(error)}
    flagged = [
        {
            "L": record["L"],
            "sector": sector,
            "flags": record[f"{sector}_diagnostics"]["flags"],
        }
        for record in result["gap_records"]
        for sector in ("even", "odd")
        if not record[f"{sector}_diagnostics"]["accepted"]
    ]
    result["status"] = "complete" if not flagged else "complete_with_warnings"
    result["convergence_warnings"] = flagged
    return result


def _write_gap_csv(path: Path, branch: dict) -> None:
    if not branch.get("gap_records"):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "L",
                "Gamma",
                "E_even",
                "E_odd",
                "gap",
                "even_relative_variance",
                "even_discarded_weight",
                "even_reached_chi",
                "even_sweeps",
                "even_wall_seconds",
                "odd_relative_variance",
                "odd_discarded_weight",
                "odd_reached_chi",
                "odd_sweeps",
                "odd_wall_seconds",
                "accepted",
            ],
        )
        writer.writeheader()
        for record in branch["gap_records"]:
            writer.writerow(
                {
                    "L": record["L"],
                    "Gamma": record["Gamma"],
                    "E_even": record["E_even"],
                    "E_odd": record["E_odd"],
                    "gap": record["gap"],
                    "even_relative_variance": record[
                        "even_diagnostics"
                    ]["relative_variance"],
                    "even_discarded_weight": record[
                        "even_diagnostics"
                    ]["discarded_weight"],
                    "even_reached_chi": record["even_diagnostics"]["reached_chi"],
                    "even_sweeps": record["even_diagnostics"]["sweeps"],
                    "even_wall_seconds": record["even_diagnostics"]["wall_seconds"],
                    "odd_relative_variance": record[
                        "odd_diagnostics"
                    ]["relative_variance"],
                    "odd_discarded_weight": record[
                        "odd_diagnostics"
                    ]["discarded_weight"],
                    "odd_reached_chi": record["odd_diagnostics"]["reached_chi"],
                    "odd_sweeps": record["odd_diagnostics"]["sweeps"],
                    "odd_wall_seconds": record["odd_diagnostics"]["wall_seconds"],
                    "accepted": record["accepted"],
                }
            )
        stream.flush()
    temporary.replace(path)


def _mean_field_power_panel_data(branch: dict) -> dict[str, np.ndarray | float]:
    """Return σ=2/3 z_eff data and its z+a/L_eff sensitivity curve."""
    scaling = branch["gap_scaling"]
    effective_lengths = np.asarray(
        scaling["z_eff"]["effective_lengths"],
        dtype=float,
    )
    z_eff = np.asarray(scaling["z_eff"]["values"], dtype=float)
    power = scaling["correction_sensitivity"]["power"]
    z_power = float(power["estimate"])
    coefficient = float(power["coefficient"])
    fit_lengths = np.linspace(
        float(effective_lengths.min()),
        1.35 * float(effective_lengths.max()),
        200,
    )
    return {
        "effective_lengths": effective_lengths,
        "z_eff": z_eff,
        "fit_lengths": fit_lengths,
        "fit_values": z_power + coefficient / fit_lengths,
        "z_power": z_power,
        "coefficient": coefficient,
    }


def _plot_gaps(path_stem: Path, nn: dict, mean_field: dict) -> None:
    mean_field_branch = mean_field["sigma_2over3"]
    complete = [
        branch
        for branch in (nn, mean_field_branch)
        if branch.get("gap_records")
    ]
    if not complete:
        return
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.labelsize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.8))

    axis = axes[0]
    axis.text(
        -0.18,
        1.05,
        "A",
        transform=axis.transAxes,
        fontweight="bold",
        va="top",
    )
    if nn.get("gap_records"):
        lengths = np.asarray(
            [record["L"] for record in nn["gap_records"]],
            dtype=float,
        )
        gaps = np.asarray(
            [record["gap"] for record in nn["gap_records"]],
            dtype=float,
        )
        guide = gaps[0] * (lengths / lengths[0]) ** (-1.0)
        axis.loglog(
            lengths,
            gaps,
            color=OKABE_ITO_BLUE,
            marker="o",
            linestyle="-",
            label="DMRG",
        )
        axis.loglog(
            lengths,
            guide,
            color="#000000",
            linestyle="--",
            label="guide z=1",
        )
    else:
        axis.text(
            0.5,
            0.5,
            _panel_status_text(nn),
            ha="center",
            va="center",
        )
    axis.set_title("NN TFIM")
    axis.set_xlabel("System size L")
    axis.set_ylabel("Parity gap Δ")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    handles, labels = axis.get_legend_handles_labels()
    if handles:
        axis.legend(handles, labels, frameon=False)

    axis = axes[1]
    axis.text(
        -0.18,
        1.05,
        "B",
        transform=axis.transAxes,
        fontweight="bold",
        va="top",
    )
    if mean_field_branch.get("gap_records"):
        panel = _mean_field_power_panel_data(mean_field_branch)
        axis.plot(
            panel["effective_lengths"],
            panel["z_eff"],
            color=OKABE_ITO_ORANGE,
            marker="s",
            linestyle="none",
            label=r"DMRG $z_{\mathrm{eff}}$",
            zorder=3,
        )
        axis.plot(
            panel["fit_lengths"],
            panel["fit_values"],
            color=OKABE_ITO_ORANGE,
            linestyle="-",
            label=r"$z_{\mathrm{eff}}=z+a/L_{\mathrm{eff}}$",
            zorder=2,
        )
        axis.axhline(
            panel["z_power"],
            color=OKABE_ITO_ORANGE,
            linestyle="--",
            label=rf"$z_{{\mathrm{{power}}}}={panel['z_power']:.3f}$",
            zorder=1,
        )
        axis.axhline(
            1.0 / 3.0,
            color="#000000",
            linestyle=":",
            label="mean field z=1/3",
            zorder=1,
        )
        axis.set_xlim(
            0.85 * float(panel["effective_lengths"].min()),
            float(panel["fit_lengths"].max()),
        )
    else:
        axis.text(
            0.5,
            0.5,
            _panel_status_text(mean_field_branch),
            ha="center",
            va="center",
        )
    axis.set_title("Long range, σ=2/3")
    axis.set_xlabel(r"Effective size $L_{\mathrm{eff}}$")
    axis.set_ylabel(r"Gap-based exponent $z_{\mathrm{eff}}$")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    handles, labels = axis.get_legend_handles_labels()
    if handles:
        axis.legend(handles, labels, frameon=False)

    fig.tight_layout()
    for suffix in ("png", "pdf"):
        fig.savefig(
            path_stem.with_suffix(f".{suffix}"),
            dpi=300,
            bbox_inches="tight",
        )
    plt.close(fig)


def _optional_json(path: Path | None) -> dict | None:
    return None if path is None else json.loads(path.read_text())


def _mean_field_assessment(branch: dict) -> str:
    if branch.get("status") == "complete":
        return "passes_baseline"
    if branch.get("status") == "complete_with_warnings":
        return "qualitative_consistency_with_convergence_warnings"
    return "unresolved"


def _add_correction_sensitivity(branch: dict) -> None:
    scaling = branch.get("gap_scaling")
    if scaling is None:
        return
    adjacent = scaling["z_eff"]
    power = sensitivity_regression(
        adjacent["values"],
        adjacent["effective_lengths"],
        "power",
    )
    log = sensitivity_regression(
        adjacent["values"],
        adjacent["effective_lengths"],
        "log",
    )
    scaling["correction_sensitivity"] = {
        "power": power,
        "log": log,
        "length_convention": "L_eff=sqrt(L1*L2)",
        "interpretation": (
            "finite_size_sensitivity_estimates_not_statistical_extrapolations"
        ),
    }


def _panel_status_text(branch: dict) -> str:
    if branch.get("status") == "excluded_mpo_bias":
        return "excluded: MPO bias"
    return branch.get("status", "unresolved").replace("_", " ")


def _mpo_provenance(root: Path, sigma: float) -> dict:
    summaries = _load_summaries(root, sigma=sigma)
    records = []
    for summary in summaries.values():
        fit = summary.get("fit")
        mpo = summary.get("mpo", {})
        if fit is None:
            raise ValueError("mean-field summary is missing fit provenance")
        records.append(
            {
                "fit": fit,
                "mpo": {
                    "pruned": mpo.get("pruned"),
                    "active_channels": mpo.get("active_channels"),
                    "chi": mpo.get("chi"),
                    "approximate_compression": mpo.get(
                        "approximate_compression"
                    ),
                },
                "code_hash": summary.get("code_hash"),
            }
        )
    if not records:
        raise ValueError("no mean-field summaries for MPO provenance")
    canonical = {
        json.dumps(record, sort_keys=True, separators=(",", ":"))
        for record in records
    }
    if len(canonical) != 1:
        raise ValueError("mean-field MPO provenance differs across cells")
    return {**records[0], "cells_audited": len(records)}


def _report_markdown(analysis: dict) -> str:
    nn = analysis["nearest_neighbor"]
    mean_field = analysis["mean_field"]
    sigma2 = analysis["sigma_2_gamma"]
    mean_field_main = mean_field["sigma_2over3"]
    lines = [
        "# Phase 9 validation report",
        "",
        (
            "Here z is obtained from excitation-gap scaling. The gap-based "
            "pairwise effective dynamical exponents are "
            "z_eff(L1,L2)=-log[Delta(L2)/Delta(L1)]/log(L2/L1), with "
            "L_eff=sqrt(L1*L2) used only as this DMRG analysis's logarithmic "
            "midpoint convention."
        ),
        (
            "Power/log sensitivity comparisons follow the spirit of "
            "Shiratani--Todo's finite-size correction analysis, while the "
            "underlying estimator differs from their QMC aspect-ratio "
            "tuning procedure."
        ),
        "",
        "## Method validation",
        "",
        (
            f"- NN TFIM: **{nn['status']}**. This checks the Hamiltonian and "
            "crossing/gap-scaling pipeline; it is not a precision reproduction "
            "of z=1 from the modest sizes."
        ),
        (
            "- Mean-field σ=2/3 at external Γc=3.673: "
            f"**{mean_field_main['status']}**; assessment "
            f"`{mean_field_main.get('assessment', 'unresolved')}`."
        ),
        (
            "- Mean-field σ=0.4 at external Γc=5.85: "
            f"**{mean_field['sigma_0p4']['status']}**; target z=0.2."
        ),
        (
            "- Second published-field benchmark: the reused σ=2.0 Phase 7 "
            f"crossing is Γₓ(32,64)={sigma2['Gamma_x_32_64']:.9f}, versus "
            f"the published Γc={sigma2['published_Gamma_c']:.4f}. This is a "
            "finite-size crossing comparison, not an exact reproduction."
        ),
        "",
    ]
    if nn.get("gap_records"):
        diagnostics = nn["cell_diagnostics"]
        accepted = sum(record["accepted"] for record in diagnostics)
        warnings = [
            (
                f"L={record['L']}, Gamma={record['Gamma']:g}, "
                f"{record['sector']}: {','.join(record['flags'])}"
            )
            for record in diagnostics
            if not record["accepted"]
        ]
        lines.extend(
            [
                "### Nearest-neighbor limit",
                "",
                (
                    "Hamiltonian: H=-sum_i Z_i Z_(i+1)-Gamma sum_i X_i "
                    "on the periodic ring, with even/odd parity-sector DMRG."
                ),
                (
                    "Crossings: "
                    + ", ".join(
                        f"Gamma_x({row['size_pair'].replace('_', ',')})="
                        f"{row['Gamma_x']:.6f}"
                        for row in nn["crossings"]
                    )
                    + "; exact Gamma_c=1."
                ),
                "",
                "| L | E_even | E_odd | Delta at Gamma=1 |",
                "|---:|---:|---:|---:|",
                *[
                    (
                        f"| {record['L']} | {record['E_even']:.12g} | "
                        f"{record['E_odd']:.12g} | {record['gap']:.9g} |"
                    )
                    for record in nn["gap_records"]
                ],
                "",
                (
                    "Gap-based pairwise effective dynamical exponents = "
                    + ", ".join(
                        f"{pair}: {value:.6f}"
                        for pair, value in zip(
                            nn["gap_scaling"]["z_eff"]["pairs"],
                            nn["gap_scaling"]["z_eff"]["values"],
                            strict=True,
                        )
                    )
                    + "."
                ),
                (
                    "Simple three-size estimate: "
                    f"z={nn['gap_scaling']['direct']['exponent']:.6f}; "
                    "expected z=1."
                ),
                (
                    f"Convergence: {accepted}/{len(diagnostics)} cells pass "
                    "the nominal convergence gates"
                    + (
                        "."
                        if not warnings
                        else "; diagnostic warning retained without rerun: "
                        + "; ".join(warnings)
                        + "."
                    )
                ),
                (
                    "This is a small-size scaling-pipeline validation, not a "
                    "high-precision thermodynamic extrapolation."
                ),
                "",
            ]
        )
    lines.extend(
        [
            "### Sigma=2/3 mean-field gap benchmark",
            "",
            (
                "Gamma_c=3.673 is an external published benchmark. This "
                "calculation tests z=sigma/2 and does not independently "
                "determine Gamma_c."
            ),
            "",
        ]
    )
    if mean_field_main.get("gap_records"):
        lines.extend(
            [
                "| L | E_even | E_odd | Delta | accepted |",
                "|---:|---:|---:|---:|:---:|",
                *[
                    (
                        f"| {record['L']} | {record['E_even']:.12g} | "
                        f"{record['E_odd']:.12g} | {record['gap']:.9g} | "
                        f"{record['accepted']} |"
                    )
                    for record in mean_field_main["gap_records"]
                ],
                "",
                (
                    "Gap-based pairwise effective dynamical exponents = "
                    + ", ".join(
                        f"{pair}: {value:.6f}"
                        for pair, value in zip(
                            mean_field_main["gap_scaling"]["z_eff"]["pairs"],
                            mean_field_main["gap_scaling"]["z_eff"]["values"],
                            strict=True,
                        )
                    )
                    + "."
                ),
                (
                    "Simple four-size estimate: "
                    f"z={mean_field_main['gap_scaling']['direct']['exponent']:.6f}; "
                    "expected z=0.333333."
                ),
                (
                    "Finite-size correction sensitivity using "
                    "L_eff=sqrt(L1*L2): "
                    f"z_power={mean_field_main['gap_scaling']['correction_sensitivity']['power']['estimate']:.6f}, "
                    f"z_log={mean_field_main['gap_scaling']['correction_sensitivity']['log']['estimate']:.6f}. "
                    "With only three z_eff values, these are sensitivity "
                    "estimates, not statistically reliable extrapolations."
                ),
                "",
            ]
        )
    lines.extend(
        [
        "## Long-range critical scaling",
        "",
        (
            "The σ=1.75 self-consistent and published-field branches remain "
            "separate sensitivity analyses."
        ),
        "",
        "## Numerical uncertainty",
        "",
        (
            "MPO K=24/K=32 bias, even-sector MPS error, odd-sector MPS error, "
            "and finite-size/critical-field sensitivity are reported as "
            "separate uncertainty sources in the supplied Phase 8 artifacts."
        ),
        "",
        "## Limitations",
        "",
        (
            "The zero-frequency susceptibility exponent gamma/nu is not "
            "measured: this ground-state DMRG workflow has no imaginary-time "
            "integration. Equal-time S_eq(0) is only an auxiliary diagnostic."
        ),
        (
            "No L=256 calculation, broad sigma scan, or automatic chi=128 "
            "refinement is part of Phase 9."
        ),
        "",
        "## Track B readiness checklist",
        "",
        f"- NN Hamiltonian and scaling pipeline: {nn['status']}.",
        (
            "- Mean-field σ=2/3 z benchmark: "
            f"{mean_field_main['status']}."
        ),
        "- Published-field comparisons: σ=1.75 and σ=2.0 documented.",
        (
            "- Unmet observable: zero-frequency susceptibility gamma/nu "
            "is outside the ground-state DMRG scope."
        ),
        "- Precision limitation: no thermodynamic-limit claim from Phase 9.",
        "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nn-root", type=Path, required=True)
    parser.add_argument("--mean-field-root", type=Path, required=True)
    parser.add_argument("--phase8-self-consistent", type=Path)
    parser.add_argument("--phase8-published-field", type=Path)
    parser.add_argument("--uncertainty-analysis", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    nn = _branch(args.nn_root, analyze_nn)
    benchmark = MEAN_FIELD_BENCHMARKS[0]
    mean_field = {
        "sigma_2over3": _branch(
            args.mean_field_root,
            lambda summaries: analyze_mean_field(
                summaries,
                sigma=benchmark["sigma"],
                gamma=benchmark["Gamma"],
            ),
            sigma=benchmark["sigma"],
        ),
        "sigma_0p4": {
            "status": "excluded_mpo_bias",
            "dmrg_run": False,
            "Gamma": 5.85,
            "target_z": 0.2,
            "acceptance_threshold": 0.01,
            "K32_max_relative_error": {
                "L64": 0.05999919011721651,
                "L96": 0.07056378892942441,
            },
            "reason": "K32_finite_ring_error_above_1_percent",
        },
    }
    mean_field["sigma_2over3"]["assessment"] = _mean_field_assessment(
        mean_field["sigma_2over3"]
    )
    _add_correction_sensitivity(mean_field["sigma_2over3"])
    if mean_field["sigma_2over3"].get("gap_records"):
        mean_field["sigma_2over3"]["mpo_provenance"] = _mpo_provenance(
            args.mean_field_root,
            benchmark["sigma"],
        )
    analysis = {
        "nearest_neighbor": nn,
        "mean_field": mean_field,
        "sigma_2_gamma": published_gamma_comparison(),
        "sigma_1_75": {
            "self_consistent": _optional_json(args.phase8_self_consistent),
            "published_field": _optional_json(args.phase8_published_field),
        },
        "numerical_uncertainty": _optional_json(args.uncertainty_analysis),
        "scope": {
            "automatic_chi128": False,
            "susceptibility_gamma_over_nu_measured": False,
            "equal_time_structure_factor_role": "auxiliary_diagnostic_only",
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output_dir / "analysis.json", analysis)
    _write_gap_csv(args.output_dir / "nn-gaps.csv", nn)
    _write_gap_csv(
        args.output_dir / "mean-field-sigma-2over3-gaps.csv",
        mean_field["sigma_2over3"],
    )
    _plot_gaps(args.output_dir / "validation-gaps", nn, mean_field)
    atomic_text(
        args.output_dir / "report.md",
        _report_markdown(analysis),
    )
    print(f"wrote Phase 9 report to {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
