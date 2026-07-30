#!/usr/bin/env python3
"""Assemble the bounded Track B physics deliverable from completed cells."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from lrtfim.phase7_reporting import (
    convergence_flags,
    interpolate_endpoint_value,
    two_size_power_exponent,
    z_eff_from_gaps,
)


ENDPOINTS = {
    1.60: (1.65, 1.70),
    1.75: (1.55, 1.60),
    1.80: (1.50, 1.55),
    2.00: (1.40, 1.45),
}
STRUCTURE_FACTOR_SIGMAS = (1.75, 1.80, 2.00)


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def even_path(root: Path, sigma: float, length: int, gamma: float) -> Path:
    return (
        root
        / "broad/cells"
        / (
            f"sigma{sigma:.2f}_L{length}_Gamma{gamma:.2f}"
            "_even_K24_chi64/summary.json"
        )
    )


def odd_path(root: Path, sigma: float, length: int, gamma: float) -> Path:
    return (
        root
        / "selective-gap-chi128"
        / f"sigma{sigma:.2f}_L{length}_Gamma{gamma:.2f}_odd/summary.json"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.results_root
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    broad_rows = list(csv.DictReader((root / "broad/broad-review.csv").open()))
    gamma_rows = [
        {
            "sigma": float(row["sigma"]),
            "Gamma_left": float(row["Gamma_left"]),
            "Gamma_right": float(row["Gamma_right"]),
            "Gamma_x": float(row["Gamma_x"]),
            "crossing_resolution": float(row["crossing_resolution"]),
        }
        for row in broad_rows
    ]

    previous_z = {
        float(row["sigma"]): float(row["z_eff"])
        for row in csv.DictReader(
            (root / "minimal-validation/report/z-eff.csv").open()
        )
    }
    gap_rows: list[dict] = []
    z_rows: list[dict] = []
    for sigma, endpoints in ENDPOINTS.items():
        decision = load(root / f"broad/decisions/sigma-{sigma:.2f}.json")
        gamma_x = float(decision["broad_Gamma_x"])
        interpolated = {}
        excited_unstable = False
        for length in (32, 64):
            gaps = []
            for gamma in endpoints:
                even = load(even_path(root, sigma, length, gamma))
                odd = load(odd_path(root, sigma, length, gamma))
                ground = even["direct"]["even"]
                excited = odd["direct"]["odd"]
                gap = float(excited["energy"] - ground["energy"])
                ground_flags = convergence_flags(
                    ground, max_sweeps=even["settings"]["max_sweeps"]
                )
                excited_flags = convergence_flags(
                    excited, max_sweeps=odd["settings"]["max_sweeps"]
                )
                excited_unstable = excited_unstable or bool(excited_flags)
                gap_rows.append(
                    {
                        "sigma": sigma,
                        "L": length,
                        "Gamma": gamma,
                        "ground_chi": ground["reached_chi"],
                        "ground_energy": ground["energy"],
                        "ground_variance": ground["variance"],
                        "ground_relative_variance": (
                            ground["variance"]
                            / max(ground["energy"] ** 2, 1.0)
                        ),
                        "ground_discarded_weight": ground[
                            "discarded_weight"
                        ],
                        "ground_sweeps": ground["sweeps"],
                        "ground_runtime_seconds": ground["wall_seconds"],
                        "ground_flags": ";".join(ground_flags),
                        "excited_chi": excited["reached_chi"],
                        "excited_energy": excited["energy"],
                        "excited_variance": excited["variance"],
                        "excited_relative_variance": (
                            excited["variance"]
                            / max(excited["energy"] ** 2, 1.0)
                        ),
                        "excited_discarded_weight": excited[
                            "discarded_weight"
                        ],
                        "excited_sweeps": excited["sweeps"],
                        "excited_runtime_seconds": excited["wall_seconds"],
                        "excited_flags": ";".join(excited_flags),
                        "gap": gap,
                    }
                )
                gaps.append(gap)
            interpolated[length] = interpolate_endpoint_value(
                endpoints[0], endpoints[1], gaps[0], gaps[1], gamma_x
            )
        z_eff = z_eff_from_gaps(interpolated[32], interpolated[64])
        provisional = previous_z.get(sigma)
        z_rows.append(
            {
                "sigma": sigma,
                "Gamma_x": gamma_x,
                "crossing_resolution": decision["broad_delta_gamma_grid"],
                "gap_L32": interpolated[32],
                "gap_L64": interpolated[64],
                "z_eff": z_eff,
                "provisional_chi64_z_eff": (
                    "" if provisional is None else provisional
                ),
                "change_from_provisional": (
                    "" if provisional is None else z_eff - provisional
                ),
                "status": (
                    "incomplete_excited_state_convergence"
                    if excited_unstable
                    else "accepted_two_size"
                ),
            }
        )

    gamma_nu_rows: list[dict] = []
    for sigma in STRUCTURE_FACTOR_SIGMAS:
        endpoints = ENDPOINTS[sigma]
        decision = load(root / f"broad/decisions/sigma-{sigma:.2f}.json")
        gamma_x = float(decision["broad_Gamma_x"])
        s_zero = {}
        for length in (32, 64):
            values = [
                float(
                    load(even_path(root, sigma, length, gamma))[
                        "raw_observables"
                    ]["s_zero"]
                )
                for gamma in endpoints
            ]
            s_zero[length] = interpolate_endpoint_value(
                endpoints[0],
                endpoints[1],
                values[0],
                values[1],
                gamma_x,
            )
        gamma_nu_rows.append(
            {
                "sigma": sigma,
                "Gamma_x": gamma_x,
                "S0_L32": s_zero[32],
                "S0_L64": s_zero[64],
                "gamma_over_nu_two_size": two_size_power_exponent(
                    s_zero[32], s_zero[64], size_ratio=2.0
                ),
                "status": "two_size_finite_size_estimate",
            }
        )

    phase6 = load(
        root.parent
        / "phase6_sigma1.75/validated-local-reproduction/analysis.json"
    )
    mpo_gap = max(
        abs(row["gap"]["relative"]) for row in phase6["mpo"]["comparisons"]
    )
    mpo_rxi = max(
        abs(row["r_xi"]["absolute"]) for row in phase6["mpo"]["comparisons"]
    )
    mps_gap = max(
        abs(row["gap"]["relative"]) for row in phase6["mps"]["comparisons"]
    )
    mps_rxi = max(
        abs(row["r_xi"]["absolute"]) for row in phase6["mps"]["comparisons"]
    )
    uncertainty_rows = [
        {
            "source": "MPO K=24 to K=32",
            "measured_scope": "sigma=1.75, L=32,64",
            "gap_relative": mpo_gap,
            "R_xi_absolute": mpo_rxi,
            "interpretation": "subdominant validated representation error",
        },
        {
            "source": "MPS chi=128 to chi=256",
            "measured_scope": "sigma=1.75, L=64",
            "gap_relative": mps_gap,
            "R_xi_absolute": mps_rxi,
            "interpretation": "subdominant validated truncation error",
        },
        {
            "source": "finite size",
            "measured_scope": "L=32,64 only",
            "gap_relative": "",
            "R_xi_absolute": "",
            "interpretation": "dominant; prevents thermodynamic exponent claim",
        },
    ]

    write_csv(out / "gamma-x.csv", gamma_rows)
    write_csv(out / "gap-diagnostics.csv", gap_rows)
    write_csv(out / "z-eff.csv", z_rows)
    write_csv(out / "gamma-over-nu.csv", gamma_nu_rows)
    write_csv(out / "uncertainty-budget.csv", uncertainty_rows)
    analysis = {
        "Gamma_x": gamma_rows,
        "z_eff": z_rows,
        "gamma_over_nu": gamma_nu_rows,
        "uncertainty_budget": uncertainty_rows,
        "scope": {
            "maximum_L": 64,
            "K": 24,
            "exploration_chi": 64,
            "selective_odd_chi": 128,
            "excluded": ["K=32 rerun", "L=128", "Gamma refinement"],
        },
    }
    (out / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n")

    plt.rcParams.update(
        {
            "font.size": 8,
            "axes.labelsize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "pdf.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.45))
    blue, orange, green = "#0072B2", "#E69F00", "#009E73"
    axes[0].errorbar(
        [row["sigma"] for row in gamma_rows],
        [row["Gamma_x"] for row in gamma_rows],
        yerr=[row["crossing_resolution"] for row in gamma_rows],
        fmt="o-",
        color=blue,
        capsize=2,
        markersize=4,
    )
    axes[0].set(xlabel=r"$\sigma$", ylabel=r"$\Gamma_\times(32,64)$")
    accepted_z = [
        row for row in z_rows if row["status"] == "accepted_two_size"
    ]
    incomplete_z = [
        row for row in z_rows if row["status"] != "accepted_two_size"
    ]
    axes[1].plot(
        [row["sigma"] for row in z_rows],
        [row["z_eff"] for row in z_rows],
        "-",
        color=orange,
        linewidth=1.2,
    )
    axes[1].plot(
        [row["sigma"] for row in accepted_z],
        [row["z_eff"] for row in accepted_z],
        "s",
        color=orange,
        markersize=4,
        label="accepted",
    )
    axes[1].plot(
        [row["sigma"] for row in incomplete_z],
        [row["z_eff"] for row in incomplete_z],
        "s",
        color=orange,
        markerfacecolor="white",
        markersize=5,
        label="incomplete",
    )
    axes[1].set(xlabel=r"$\sigma$", ylabel=r"$z_\mathrm{eff}(32,64)$")
    axes[1].legend(frameon=False)
    axes[2].plot(
        [row["sigma"] for row in gamma_nu_rows],
        [row["gamma_over_nu_two_size"] for row in gamma_nu_rows],
        "D-",
        color=green,
        markersize=4,
    )
    axes[2].set(
        xlabel=r"$\sigma$",
        ylabel=r"two-size $\gamma/\nu$ from $S(0)$",
    )
    for label, axis in zip(("a", "b", "c"), axes, strict=True):
        axis.text(
            -0.18,
            1.04,
            label,
            transform=axis.transAxes,
            fontweight="bold",
            va="bottom",
        )
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    fig.tight_layout(w_pad=1.5)
    fig.savefig(out / "track-b-summary.png", dpi=300)
    fig.savefig(out / "track-b-summary.pdf")
    plt.close(fig)

    report = [
        "# Challenge #86 Track B: validated local MPS deliverable",
        "",
        "This bounded local reproduction uses the pinned periodic Hurwitz-zeta "
        "coupling, a custom periodized exponential MPO, and parity-resolved "
        "TeNPy DMRG. It reports finite-size results through L=64 and makes no "
        "thermodynamic-limit crossover claim.",
        "",
        "## Gamma crossing trend",
        "",
        "| sigma | Gamma_x(32,64) | grid resolution |",
        "|---:|---:|---:|",
    ]
    report.extend(
        f"| {r['sigma']:.2f} | {r['Gamma_x']:.9f} | "
        f"{r['crossing_resolution']:.3f} |"
        for r in gamma_rows
    )
    report.extend(
        [
            "",
            "## Validated two-size gap exponents",
            "",
            "| sigma | Delta(32) | Delta(64) | gap-based pairwise z_eff | change from chi=64 |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for row in z_rows:
        change = row["change_from_provisional"]
        change_text = "n/a" if change == "" else f"{change:.3e}"
        report.append(
            f"| {row['sigma']:.2f} | {row['gap_L32']:.8f} | "
            f"{row['gap_L64']:.8f} | {row['z_eff']:.6f} | "
            f"{change_text} |"
        )
    report.extend(
        [
            "",
            "The sigma=1.60 estimate is incomplete because both L=64 "
            "chi=128 odd-sector endpoints retain discarded-weight flags; "
            "the other three requested sigma points pass the selective "
            "excited-state criteria.",
            "",
            "## Two-size structure-factor estimates",
            "",
            "| sigma | S(0), L=32 | S(0), L=64 | gamma/nu estimate |",
            "|---:|---:|---:|---:|",
        ]
    )
    report.extend(
        f"| {r['sigma']:.2f} | {r['S0_L32']:.8f} | "
        f"{r['S0_L64']:.8f} | {r['gamma_over_nu_two_size']:.6f} |"
        for r in gamma_nu_rows
    )
    report.extend(
        [
            "",
            "These gamma/nu values are two-size estimates from equal-time "
            "S(0) scaling at the broad-grid crossing, not extrapolated "
            "critical exponents.",
            "",
            "## Error separation",
            "",
            f"- MPO: K=24 to K=32 changes the validated relative gap by at "
            f"most {mpo_gap:.2e} and R_xi by {mpo_rxi:.2e}.",
            f"- MPS: chi=128 to chi=256 changes the validated relative gap "
            f"by at most {mps_gap:.2e} and R_xi by {mps_rxi:.2e}.",
            "- Finite size is dominant: only L=32,64 enter z_eff and "
            "gamma/nu, and Gamma_x has broad-grid resolution 0.025.",
            "",
            "## Completed",
            "",
            "- Hurwitz-zeta periodic convention and exponential MPO.",
            "- NN TFIM and small-system long-range validation.",
            "- Gamma_x(sigma) crossover scan.",
            "- Selectively converged odd-sector gap-based pairwise effective "
            "dynamical exponents.",
            "",
            "## Limitations",
            "",
            "- No L=256 scaling and no thermodynamic Gamma_c extrapolation.",
            "- No new K=32, L=128, or Gamma-refinement calculation.",
            "- The gamma/nu values are finite-size structure-factor estimates.",
        ]
    )
    (out / "final-report.md").write_text("\n".join(report) + "\n")
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
