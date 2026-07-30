#!/usr/bin/env python3
"""Report the fixed-field sigma=1.8 Phase 9 gap validation."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lrtfim.phase9_protocol import SIGMA_18, analyze_sigma18_z
from scripts.report_phase9_validation import (
    OKABE_ITO_BLUE,
    _branch,
    _mpo_provenance,
    _write_gap_csv,
    atomic_json,
    atomic_text,
)


def _plot(path_stem: Path, analysis: dict) -> None:
    lengths = np.asarray(
        [record["L"] for record in analysis["gap_records"]],
        dtype=float,
    )
    gaps = np.asarray(
        [record["gap"] for record in analysis["gap_records"]],
        dtype=float,
    )
    direct = analysis["gap_scaling"]["direct"]
    predicted = np.asarray(direct["predicted_gaps"], dtype=float)

    fig, axis = plt.subplots(figsize=(4.8, 3.4))
    axis.loglog(
        lengths,
        gaps,
        "o",
        color=OKABE_ITO_BLUE,
        label="DMRG",
    )
    axis.loglog(
        lengths,
        predicted,
        "-",
        color=OKABE_ITO_BLUE,
        label=f"direct z={direct['exponent']:.3f}",
    )
    for exponent, linestyle, label in (
        (0.93, "--", "Shiratani-Todo QMC power z≈0.93"),
        (1.00, ":", "Shiratani-Todo QMC log z≈1.00"),
    ):
        guide = gaps[0] * (lengths / lengths[0]) ** (-exponent)
        axis.loglog(lengths, guide, linestyle, color="#000000", label=label)
    axis.set_xlabel("System size L")
    axis.set_ylabel("Parity gap Δ")
    axis.set_title("Long-range TFIM, σ=1.8, Γ=1.5288")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    for suffix in ("png", "pdf"):
        fig.savefig(path_stem.with_suffix(f".{suffix}"), dpi=300)
    plt.close(fig)


def _markdown(analysis: dict) -> str:
    scaling = analysis["gap_scaling"]
    correction = scaling["correction_sensitivity"]
    diagnostics = [
        (record["L"], sector, record[f"{sector}_diagnostics"])
        for record in analysis["gap_records"]
        for sector in ("even", "odd")
    ]
    accepted = sum(item[2]["accepted"] for item in diagnostics)
    warnings = [
        f"L={length} {sector}: {','.join(diagnostic['flags'])}"
        for length, sector, diagnostic in diagnostics
        if not diagnostic["accepted"]
    ]
    lines = [
        "# Phase 9 sigma=1.8 dynamical-exponent validation",
        "",
        (
            "Gamma_c=1.5288 is an external Shiratani-Todo benchmark field. "
            "This calculation validates finite-size gap scaling and does not "
            "independently determine Gamma_c."
        ),
        "",
        "| L | E_even | E_odd | Delta | accepted |",
        "|---:|---:|---:|---:|:---:|",
        *[
            (
                f"| {record['L']} | {record['E_even']:.12g} | "
                f"{record['E_odd']:.12g} | {record['gap']:.9g} | "
                f"{record['accepted']} |"
            )
            for record in analysis["gap_records"]
        ],
        "",
        (
            "Gap-based pairwise effective dynamical exponents: "
            + ", ".join(
                f"{pair}: {value:.6f}"
                for pair, value in zip(
                    scaling["z_eff"]["pairs"],
                    scaling["z_eff"]["values"],
                    strict=True,
                )
            )
            + "."
        ),
        (
            "Finite-size sensitivity estimates using "
            "L_eff=sqrt(L1*L2): "
            f"z_power={correction['power']['estimate']:.6f}, "
            f"z_log={correction['log']['estimate']:.6f}."
        ),
        (
            "Shiratani-Todo comparison: z_power≈0.93 and z_log≈1.00. "
            "The correction forms are compared following the spirit of "
            "their finite-size analysis, while the underlying estimator "
            "differs: DMRG uses excitation gaps and their QMC aspect-ratio "
            "tuning procedure uses the tuned imaginary-time size. This is "
            "a validation comparison only, not a precision reproduction "
            "claim."
        ),
        (
            f"Convergence: {accepted}/{len(diagnostics)} states pass the "
            "nominal gates"
            + ("." if not warnings else "; warnings: " + "; ".join(warnings) + ".")
        ),
        "",
        "## Numerical scope",
        "",
        (
            "K=24, chi=128, exact-zero MPO pruning, no approximate MPO "
            "compression, no Gamma search, no K=32 comparison, and no "
            "automatic chi increase."
        ),
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analysis = _branch(
        args.summary_root,
        analyze_sigma18_z,
        sigma=SIGMA_18,
    )
    if not analysis.get("gap_records"):
        raise ValueError(
            "sigma=1.8 report requires all ten successful fixed-field states"
        )
    analysis["mpo_provenance"] = _mpo_provenance(
        args.summary_root,
        SIGMA_18,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output_dir / "analysis.json", analysis)
    _write_gap_csv(args.output_dir / "gaps.csv", analysis)
    _plot(args.output_dir / "gap-scaling", analysis)
    atomic_text(args.output_dir / "report.md", _markdown(analysis))
    print(f"wrote sigma=1.8 report to {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
