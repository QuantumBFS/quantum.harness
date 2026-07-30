#!/usr/bin/env python3
"""Run the three-layer small-system validation of the long-range MPO."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lrtfim.dmrg_workflow import default_dmrg_options
from lrtfim.exponential_fit import ExponentialFit, fit_power_law
from lrtfim.validation import validate_cell


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lengths", nargs="+", type=int, default=[8, 10, 12])
    parser.add_argument(
        "--gammas",
        nargs="+",
        type=float,
        default=[1.2, 1.56, 2.0],
    )
    parser.add_argument("--sigma", type=float, default=1.75)
    parser.add_argument("--k", type=int, default=24)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--r-fit", type=int, default=2048)
    parser.add_argument("--chi-max", type=int, default=128)
    parser.add_argument("--max-sweeps", type=int, default=30)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/phase5_mpo_validation"),
    )
    return parser.parse_args()


def _gamma_label(gamma: float) -> str:
    return f"{gamma:g}"


def _write_coupling_csv(path: Path, cell: dict) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=cell["coupling_profile"][0])
        writer.writeheader()
        writer.writerows(cell["coupling_profile"])


def _write_correlation_csv(path: Path, cell: dict) -> None:
    layers = cell["layers"]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "distance",
                "exact_pair_ed",
                "compact_mpo_ed",
                "compact_mpo_dmrg",
            ],
        )
        writer.writeheader()
        count = len(layers["exact_pair_ed"]["correlations"])
        for index in range(count):
            writer.writerow(
                {
                    "distance": index + 1,
                    **{
                        layer: layers[layer]["correlations"][index]
                        for layer in (
                            "exact_pair_ed",
                            "compact_mpo_ed",
                            "compact_mpo_dmrg",
                        )
                    },
                }
            )


def _flat_row(cell: dict) -> dict:
    parameters = cell["parameters"]
    mpo = cell["comparisons"]["mpo_representation"]
    mps = cell["comparisons"]["mps_optimization"]
    row = {
        "length": parameters["length"],
        "gamma": parameters["gamma"],
        "coupling_max_relative_error": cell["hamiltonian"][
            "coupling_max_relative_error"
        ],
        "relative_frobenius_error": cell["hamiltonian"][
            "relative_frobenius_error"
        ],
    }
    for comparison_name, comparison in (("mpo", mpo), ("mps", mps)):
        for observable in ("ground_energy", "excited_energy", "gap"):
            row[f"{comparison_name}_{observable}_absolute"] = comparison[observable][
                "absolute"
            ]
            row[f"{comparison_name}_{observable}_relative"] = comparison[observable][
                "relative"
            ]
        row[f"{comparison_name}_correlation_max_absolute"] = comparison[
            "correlation_max_absolute"
        ]
    diagnostics = cell["layers"]["compact_mpo_dmrg"]["diagnostics"]
    for name in (
        "ground_variance",
        "excited_variance",
        "ground_max_discarded_weight",
        "excited_max_discarded_weight",
        "ground_max_chi",
        "excited_max_chi",
        "overlap",
    ):
        row[name] = diagnostics[name]
    return row


def _write_summary_csv(path: Path, cells: list[dict]) -> None:
    rows = [_flat_row(cell) for cell in cells]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def _plot_coupling_errors(path: Path, cells: list[dict]) -> None:
    figure, axis = plt.subplots(figsize=(5.4, 3.7), constrained_layout=True)
    seen: set[int] = set()
    for cell in cells:
        length = cell["parameters"]["length"]
        if length in seen:
            continue
        seen.add(length)
        profile = cell["coupling_profile"]
        axis.semilogy(
            [row["distance"] for row in profile],
            [row["relative_error"] for row in profile],
            "o-",
            label=f"L={length}",
        )
    axis.set_xlabel("distance r")
    axis.set_ylabel("relative coupling error")
    axis.set_title("Periodized K-exponential coupling")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_observable_errors(path: Path, cells: list[dict]) -> None:
    labels = [
        f"L={cell['parameters']['length']}\nΓ={cell['parameters']['gamma']:g}"
        for cell in cells
    ]
    x = np.arange(len(cells))
    figure, axes = plt.subplots(1, 3, figsize=(11.0, 3.8), constrained_layout=True)
    observables = ("ground_energy", "gap", "correlation_max_absolute")
    titles = ("E₀ absolute error", "Δ absolute error", "max |δC(r)|")
    for axis, observable, title in zip(axes, observables, titles, strict=True):
        for comparison, label, color in (
            ("mpo_representation", "exact ED → MPO ED", "#0072B2"),
            ("mps_optimization", "MPO ED → DMRG", "#D55E00"),
        ):
            values = []
            for cell in cells:
                item = cell["comparisons"][comparison][observable]
                values.append(item if isinstance(item, float) else item["absolute"])
            axis.semilogy(x, np.maximum(values, np.finfo(float).tiny), "o-", label=label, color=color)
        axis.set_title(title)
        axis.set_xticks(x, labels, rotation=45, ha="right")
        axis.grid(alpha=0.25)
    axes[0].legend(fontsize=8)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    options = default_dmrg_options(args.chi_max)
    options["max_sweeps"] = args.max_sweeps
    summary_path = args.output_dir / "summary.json"
    if args.resume and summary_path.is_file():
        summary = json.loads(summary_path.read_text())
        stored = summary["fit"]
        requested = (args.sigma, args.k, args.alpha, args.r_fit)
        recorded = (
            stored["sigma"],
            stored["num_exponentials"],
            stored["alpha"],
            stored["r_fit"],
        )
        if requested != recorded:
            raise ValueError("resume fit parameters do not match existing summary")
        fit = ExponentialFit(
            sigma=stored["sigma"],
            r_fit=stored["r_fit"],
            lambdas=np.asarray(stored["lambdas"]),
            coefficients=np.asarray(stored["coefficients"]),
            max_relative_error=stored["kernel_max_relative_error"],
            rms_relative_error=stored["kernel_rms_relative_error"],
        )
        cells = summary["cells"]
        summary["dmrg_options"] = options
        print(f"resume: loaded fit and {len(cells)} completed cells", flush=True)
    else:
        print(
            f"fit: sigma={args.sigma:g}, K={args.k}, "
            f"alpha={args.alpha:g}, r_fit={args.r_fit}",
            flush=True,
        )
        fit = fit_power_law(
            sigma=args.sigma,
            num_exponentials=args.k,
            r_fit=args.r_fit,
            min_rate_scale=args.alpha,
        )
        cells = []
        summary = {
            "fit": {
                "sigma": args.sigma,
                "num_exponentials": args.k,
                "alpha": args.alpha,
                "r_fit": args.r_fit,
                "lambdas": fit.lambdas.tolist(),
                "coefficients": fit.coefficients.tolist(),
                "kernel_max_relative_error": fit.max_relative_error,
                "kernel_rms_relative_error": fit.rms_relative_error,
            },
            "dmrg_options": options,
            "cells": cells,
        }
    completed = {
        (cell["parameters"]["length"], cell["parameters"]["gamma"]) for cell in cells
    }
    for length in args.lengths:
        for gamma in args.gammas:
            if (length, gamma) in completed:
                print(f"L={length}, Gamma={gamma:g}: already complete", flush=True)
                continue
            print(f"L={length}, Gamma={gamma:g}: three-layer validation", flush=True)
            cell = validate_cell(
                length=length,
                sigma=args.sigma,
                gamma=gamma,
                fit=fit,
                dmrg_options=options,
            )
            cells.append(cell)
            label = f"L{length}_Gamma{_gamma_label(gamma)}"
            (args.output_dir / f"cell_{label}.json").write_text(
                json.dumps(cell, indent=2) + "\n"
            )
            _write_coupling_csv(args.output_dir / f"coupling_L{length}.csv", cell)
            _write_correlation_csv(
                args.output_dir / f"correlations_{label}.csv",
                cell,
            )
            summary_path.write_text(
                json.dumps(summary, indent=2) + "\n"
            )
            _write_summary_csv(args.output_dir / "summary.csv", cells)
            print(
                f"L={length}, Gamma={gamma:g}: "
                f"coupling={cell['hamiltonian']['coupling_max_relative_error']:.3e}, "
                f"gap MPO={cell['comparisons']['mpo_representation']['gap']['relative']:.3e}, "
                f"gap MPS={cell['comparisons']['mps_optimization']['gap']['relative']:.3e}",
                flush=True,
            )
    _plot_coupling_errors(args.output_dir / "coupling_error.png", cells)
    _plot_observable_errors(args.output_dir / "observable_errors.png", cells)


if __name__ == "__main__":
    main()
