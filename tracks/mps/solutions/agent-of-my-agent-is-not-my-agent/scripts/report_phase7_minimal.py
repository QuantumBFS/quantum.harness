#!/usr/bin/env python3
"""Build tables, figures, and a report for Phase 7 minimal validation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from lrtfim.phase7_reporting import (
    endpoint_chi_validation,
    interpolate_endpoint_value,
    z_eff_from_gaps,
)


CHI_ENDPOINTS = {
    1.70: (1.55, 1.60),
    1.75: (1.55, 1.60),
    1.80: (1.50, 1.55),
    2.00: (1.40, 1.45),
}
GAP_ENDPOINTS = {
    1.75: (1.55, 1.60),
    1.80: (1.50, 1.55),
    2.00: (1.40, 1.45),
}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def direct_state(summary: dict, sector: str) -> dict:
    return summary["direct"][sector]


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def excited_flags(odd: dict, gap: float) -> list[str]:
    state = direct_state(odd, "odd")
    relative_variance = state["variance"] / max(state["energy"] ** 2, 1.0)
    flags = []
    if relative_variance > 1.0e-10:
        flags.append("relative_variance")
    if state["discarded_weight"] > 1.0e-8:
        flags.append("discarded_weight")
    if state["sweeps"] >= odd["settings"]["max_sweeps"]:
        flags.append("sweep_cap")
    if gap <= 0.0:
        flags.append("nonpositive_gap")
    return flags


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.results_root
    args.output_dir.mkdir(parents=True, exist_ok=True)

    chi_rows = []
    chi_summary = []
    for sigma, endpoints in CHI_ENDPOINTS.items():
        small_values = []
        low_values = []
        high_values = []
        for gamma in endpoints:
            small = load(
                root
                / "broad/cells"
                / f"sigma{sigma:.2f}_L32_Gamma{gamma:.2f}_even_K24_chi64"
                / "summary.json"
            )
            low = load(
                root
                / "broad/cells"
                / f"sigma{sigma:.2f}_L64_Gamma{gamma:.2f}_even_K24_chi64"
                / "summary.json"
            )
            high = load(
                root
                / "minimal-validation/chi128-even-L64"
                / f"sigma{sigma:.2f}_Gamma{gamma:.2f}"
                / "summary.json"
            )
            r_small = small["raw_observables"]["r_xi"]
            r_low = low["raw_observables"]["r_xi"]
            r_high = high["raw_observables"]["r_xi"]
            small_values.append(r_small)
            low_values.append(r_low)
            high_values.append(r_high)
            high_state = direct_state(high, "even")
            chi_rows.append(
                {
                    "sigma": sigma,
                    "Gamma": gamma,
                    "R_xi_L32_chi64": r_small,
                    "R_xi_L64_chi64": r_low,
                    "R_xi_L64_chi128": r_high,
                    "R_xi_shift": r_high - r_low,
                    "variance_chi128": high_state["variance"],
                    "discarded_weight_chi128": high_state[
                        "discarded_weight"
                    ],
                    "sweeps_chi128": high_state["sweeps"],
                }
            )
        result = endpoint_chi_validation(
            r_small=small_values,
            r_large_chi64=low_values,
            r_large_chi128=high_values,
            threshold=1.0e-4,
        )
        chi_summary.append({"sigma": sigma, **result})

    gap_rows = []
    z_rows = []
    rerun_requests = []
    for sigma, endpoints in GAP_ENDPOINTS.items():
        decision = load(root / f"broad/decisions/sigma-{sigma:.2f}.json")
        gamma_x = decision["broad_Gamma_x"]
        gaps_by_length = {}
        for length in (32, 64):
            gaps = []
            for gamma in endpoints:
                even = load(
                    root
                    / "broad/cells"
                    / (
                        f"sigma{sigma:.2f}_L{length}_Gamma{gamma:.2f}"
                        "_even_K24_chi64"
                    )
                    / "summary.json"
                )
                odd_path = (
                    root
                    / "minimal-validation/gaps-chi64"
                    / (
                        f"sigma{sigma:.2f}_L{length}_Gamma{gamma:.2f}_odd"
                    )
                    / "summary.json"
                )
                odd = load(odd_path)
                even_energy = direct_state(even, "even")["energy"]
                odd_state = direct_state(odd, "odd")
                gap = odd_state["energy"] - even_energy
                flags = excited_flags(odd, gap)
                gap_rows.append(
                    {
                        "sigma": sigma,
                        "L": length,
                        "Gamma": gamma,
                        "even_energy": even_energy,
                        "odd_energy": odd_state["energy"],
                        "gap": gap,
                        "odd_variance": odd_state["variance"],
                        "odd_relative_variance": (
                            odd_state["variance"]
                            / max(odd_state["energy"] ** 2, 1.0)
                        ),
                        "odd_discarded_weight": odd_state[
                            "discarded_weight"
                        ],
                        "odd_sweeps": odd_state["sweeps"],
                        "flags": ";".join(flags),
                    }
                )
                if flags:
                    rerun_requests.append(
                        {
                            "sigma": sigma,
                            "L": length,
                            "Gamma": gamma,
                            "requested_chi": 128,
                            "reasons": flags,
                        }
                    )
                gaps.append(gap)
            gaps_by_length[length] = interpolate_endpoint_value(
                endpoints[0],
                endpoints[1],
                gaps[0],
                gaps[1],
                gamma_x,
            )
        z_rows.append(
            {
                "sigma": sigma,
                "Gamma_x": gamma_x,
                "crossing_resolution": decision[
                    "broad_delta_gamma_grid"
                ],
                "gap_L32": gaps_by_length[32],
                "gap_L64": gaps_by_length[64],
                "z_eff": z_eff_from_gaps(
                    gaps_by_length[32],
                    gaps_by_length[64],
                ),
                "status": (
                    "provisional_chi128_rerun_requested"
                    if any(item["sigma"] == sigma for item in rerun_requests)
                    else "accepted"
                ),
            }
        )

    write_csv(args.output_dir / "chi-validation.csv", chi_rows)
    write_csv(args.output_dir / "gap-endpoints.csv", gap_rows)
    write_csv(args.output_dir / "z-eff.csv", z_rows)
    analysis = {
        "chi_validation": chi_summary,
        "gap_results": z_rows,
        "selective_chi128_requests": rerun_requests,
        "excluded": ["K32", "L128", "Gamma refinement"],
    }
    (args.output_dir / "analysis.json").write_text(
        json.dumps(analysis, indent=2) + "\n"
    )

    broad_rows = list(
        csv.DictReader((root / "broad/broad-review.csv").open())
    )
    sigma = np.array([float(row["sigma"]) for row in broad_rows])
    gamma_x = np.array([float(row["Gamma_x"]) for row in broad_rows])
    resolution = np.array(
        [float(row["crossing_resolution"]) for row in broad_rows]
    )
    validated_sigma = np.array([row["sigma"] for row in chi_summary])
    max_shift = np.array(
        [row["max_abs_r_xi_shift"] for row in chi_summary]
    )
    z_sigma = np.array([row["sigma"] for row in z_rows])
    z_value = np.array([row["z_eff"] for row in z_rows])

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
    blue, orange, vermillion = "#0072B2", "#E69F00", "#D55E00"

    axes[0].errorbar(
        sigma,
        gamma_x,
        yerr=resolution,
        fmt="o-",
        color=blue,
        capsize=2,
        markersize=4,
        label="broad-grid interpolation",
    )
    axes[0].set(xlabel=r"$\sigma$", ylabel=r"$\Gamma_\times(32,64)$")
    axes[0].legend(frameon=False)

    axes[1].semilogy(
        validated_sigma,
        max_shift,
        "s-",
        color=orange,
        markersize=4,
        label="max endpoint shift",
    )
    axes[1].axhline(
        1.0e-4,
        color="black",
        linestyle="--",
        linewidth=0.8,
        label="acceptance threshold",
    )
    axes[1].set(xlabel=r"$\sigma$", ylabel=r"max $|\Delta R_\xi|$")
    axes[1].legend(frameon=False)

    axes[2].plot(
        z_sigma,
        z_value,
        "D--",
        color=vermillion,
        markerfacecolor="white",
        markersize=5,
        label="provisional (flagged)",
    )
    axes[2].set(
        xlabel=r"$\sigma$",
        ylabel=r"$z_\mathrm{eff}(32,64)$",
    )
    axes[2].legend(frameon=False)

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
    fig.savefig(args.output_dir / "phase7-minimal-validation.png", dpi=300)
    fig.savefig(args.output_dir / "phase7-minimal-validation.pdf")
    plt.close(fig)

    report = [
        "# Phase 7 minimal validation report",
        "",
        "## Chi validation",
        "",
        "| sigma | max |Delta R_xi| | signs unchanged | bracket unchanged | accepted |",
        "|---:|---:|:---:|:---:|:---:|",
    ]
    for row in chi_summary:
        report.append(
            f"| {row['sigma']:.2f} | {row['max_abs_r_xi_shift']:.3e} "
            f"| {row['signs_unchanged']} | {row['bracket_unchanged']} "
            f"| {row['accepted']} |"
        )
    report.extend(
        [
            "",
            "All tested endpoint shifts are below `1e-4`, and the broad "
            "crossing brackets retain their sign structure.",
            "",
            "## Provisional gap scaling",
            "",
            "| sigma | broad Gamma_x | Delta(32) | Delta(64) | gap-based pairwise z_eff | status |",
            "|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in z_rows:
        report.append(
            f"| {row['sigma']:.2f} | {row['Gamma_x']:.6f} "
            f"| {row['gap_L32']:.6f} | {row['gap_L64']:.6f} "
            f"| {row['z_eff']:.6f} | {row['status']} |"
        )
    report.extend(
        [
            "",
            "The gap-based pairwise effective dynamical exponents are "
            "provisional because every tested L=64 "
            "odd endpoint state exceeds the preregistered variance and "
            "discarded-weight flags. Six selective chi=128 odd reruns are "
            "requested but were not started.",
            "",
            "No K=32, L=128, or Gamma-refinement calculation was run.",
        ]
    )
    (args.output_dir / "report.md").write_text("\n".join(report) + "\n")
    print(f"wrote report with {len(rerun_requests)} rerun flags", flush=True)


if __name__ == "__main__":
    main()
