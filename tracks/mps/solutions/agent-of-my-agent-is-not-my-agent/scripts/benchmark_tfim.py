#!/usr/bin/env python3
"""Validate the shared TeNPy DMRG workflow on the periodic NN TFIM."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh

from lrtfim.dmrg_workflow import (
    build_mpo_model,
    default_dmrg_options,
    run_ground_and_first_excited,
)
from lrtfim.mpo import build_nearest_neighbor_tfim_mpo


def exact_tfim(length: int, gamma: float) -> tuple[np.ndarray, np.ndarray]:
    """Return the two lowest ED eigenpairs of the periodic Pauli TFIM."""
    dimension = 1 << length
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    for state in range(dimension):
        diagonal = 0.0
        for i in range(length):
            zi = 1.0 if (state >> i) & 1 == 0 else -1.0
            zj = 1.0 if (state >> ((i + 1) % length)) & 1 == 0 else -1.0
            diagonal -= zi * zj
            rows.append(state)
            columns.append(state ^ (1 << i))
            values.append(-gamma)
        rows.append(state)
        columns.append(state)
        values.append(diagonal)
    matrix = coo_matrix((values, (rows, columns)), shape=(dimension, dimension)).tocsr()
    energies, vectors = eigsh(matrix, k=2, which="SA", tol=1.0e-13)
    order = np.argsort(energies)
    return energies[order], vectors[:, order]


def exact_zz_correlations(vector: np.ndarray, length: int) -> np.ndarray:
    probabilities = np.abs(vector) ** 2
    states = np.arange(1 << length)
    z0 = 1.0 - 2.0 * ((states >> 0) & 1)
    return np.asarray(
        [
            np.dot(probabilities, z0 * (1.0 - 2.0 * ((states >> r) & 1)))
            for r in range(1, length)
        ]
    )


def _state_record(state) -> dict[str, float | int]:
    return {
        "energy": state.energy,
        "variance": state.variance,
        "max_discarded_weight": state.max_discarded_weight,
        "max_chi": state.max_chi,
    }


def run_size(length: int, gamma: float, options: dict) -> dict:
    exact_energies, exact_vectors = exact_tfim(length, gamma)
    mpo = build_nearest_neighbor_tfim_mpo(length, gamma)
    model = build_mpo_model(mpo)
    result = run_ground_and_first_excited(model, options)

    exact_correlations = exact_zz_correlations(exact_vectors[:, 0], length)
    dmrg_matrix = result.ground.psi.correlation_function("Sigmaz", "Sigmaz")
    dmrg_correlations = np.real(np.asarray(dmrg_matrix[0, 1:]))
    correlation_error = float(np.max(np.abs(dmrg_correlations - exact_correlations)))
    exact_gap = float(exact_energies[1] - exact_energies[0])

    tolerances = {
        "energy": 1.0e-8,
        "gap": 1.0e-8,
        "correlation": 1.0e-7,
        "variance": 1.0e-10,
        "overlap": 1.0e-10,
    }
    errors = {
        "ground_energy": abs(result.ground.energy - exact_energies[0]),
        "excited_energy": abs(result.excited.energy - exact_energies[1]),
        "gap": abs(result.gap - exact_gap),
        "correlation_max_abs": correlation_error,
    }
    accepted = (
        errors["ground_energy"] < tolerances["energy"]
        and errors["excited_energy"] < tolerances["energy"]
        and errors["gap"] < tolerances["gap"]
        and errors["correlation_max_abs"] < tolerances["correlation"]
        and result.ground.variance < tolerances["variance"]
        and result.excited.variance < tolerances["variance"]
        and result.overlap < tolerances["overlap"]
    )
    return {
        "length": length,
        "exact": {
            "ground_energy": float(exact_energies[0]),
            "excited_energy": float(exact_energies[1]),
            "gap": exact_gap,
        },
        "dmrg": {
            "ground": _state_record(result.ground),
            "excited": _state_record(result.excited),
            "gap": result.gap,
        },
        "length_times_gap": length * result.gap,
        "excited_targeting": {"overlap": result.overlap},
        "errors": errors,
        "tolerances": tolerances,
        "accepted": accepted,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lengths", nargs="+", type=int, default=[8, 10, 12])
    parser.add_argument("--gamma", type=float, default=1.0)
    parser.add_argument("--chi-max", type=int, default=128)
    parser.add_argument("--max-sweeps", type=int, default=30)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/phase4_nn_tfim"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    options = default_dmrg_options(args.chi_max)
    options["max_sweeps"] = args.max_sweeps
    records = []
    summary = {
        "model": {
            "hamiltonian": "-sum_i Z_i Z_(i+1) - Gamma sum_i X_i",
            "boundary": "periodic Hamiltonian represented by a finite OBC MPO/MPS",
            "gamma": args.gamma,
            "operator_convention": "Pauli Sigmax/Sigmaz",
        },
        "dmrg_options": options,
        "benchmark_variance_threshold": 1.0e-10,
        "sizes": records,
    }
    for length in args.lengths:
        print(f"L={length}: ED and DMRG benchmark", flush=True)
        record = run_size(length, args.gamma, options)
        records.append(record)
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n"
        )
        print(
            f"L={length}: L*gap={record['length_times_gap']:.12g}, "
            f"accepted={record['accepted']}",
            flush=True,
        )

    with (args.output_dir / "benchmark.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "length",
                "gap",
                "length_times_gap",
                "ground_variance",
                "excited_variance",
                "overlap",
                "accepted",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "length": record["length"],
                    "gap": record["dmrg"]["gap"],
                    "length_times_gap": record["length_times_gap"],
                    "ground_variance": record["dmrg"]["ground"]["variance"],
                    "excited_variance": record["dmrg"]["excited"]["variance"],
                    "overlap": record["excited_targeting"]["overlap"],
                    "accepted": record["accepted"],
                }
            )

    lengths = np.asarray([record["length"] for record in records])
    scaled_gaps = np.asarray([record["length_times_gap"] for record in records])
    gaps = np.asarray([record["dmrg"]["gap"] for record in records])
    figure, axes = plt.subplots(1, 2, figsize=(8.2, 3.4), constrained_layout=True)
    axes[0].plot(lengths, gaps, "o-", color="#0072B2", linewidth=1.6)
    axes[0].set_xlabel("L")
    axes[0].set_ylabel("Δ(L)")
    axes[1].plot(lengths, scaled_gaps, "o-", color="#D55E00", linewidth=1.6)
    axes[1].set_xlabel("L")
    axes[1].set_ylabel("L Δ(L)")
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.suptitle("Periodic nearest-neighbor TFIM at Γ = 1")
    figure.savefig(args.output_dir / "tfim_critical_gap.png", dpi=180)
    figure.savefig(args.output_dir / "tfim_critical_gap.pdf")
    plt.close(figure)

    if not all(record["accepted"] for record in records):
        raise SystemExit("one or more sizes failed the strict ED benchmark gate")


if __name__ == "__main__":
    main()
