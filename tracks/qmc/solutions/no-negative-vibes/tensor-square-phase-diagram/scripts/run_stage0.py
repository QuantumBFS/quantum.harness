#!/usr/bin/env python3
"""Run the frozen determinant-oracle and m=3 Hamiltonian regression suite."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.linalg import expm

from tensor_square.algebra import (
    kron_sum,
    relative_error,
    tensor_square_weight_direct,
    tensor_square_weight_eigenvalues,
    tensor_square_weight_factorized,
)
from tensor_square.fock import (
    basis_states,
    d_gamma,
    many_body_hamiltonian,
    max_abs,
    normal_ordered_q_square,
    particle_number_operator,
)


def edge(m: int, i: int, j: int) -> np.ndarray:
    matrix = np.zeros((m, m))
    matrix[i, j] = matrix[j, i] = 1.0
    return matrix


def oracle_audit(seed: int, samples_per_m: int) -> dict[str, object]:
    records: list[dict[str, float | int]] = []
    for m in (2, 3, 4):
        rng = np.random.default_rng(seed + m)
        scales = [0.04, 0.35, 1.1]
        for sample in range(samples_per_m):
            x = np.eye(m)
            scale = scales[sample % len(scales)]
            for _slice in range(5):
                generator = rng.normal(scale=scale, size=(m, m))
                x = expm(generator) @ x
            direct = tensor_square_weight_direct(x)
            factorized = tensor_square_weight_factorized(x)
            eigenvalue = tensor_square_weight_eigenvalues(x)
            records.append(
                {
                    "m": m,
                    "sample": sample,
                    "direct": direct,
                    "factorized_relative_error": relative_error(
                        factorized, direct
                    ),
                    "eigenvalue_relative_error": relative_error(
                        eigenvalue, direct
                    ),
                }
            )
    near_zero_x = np.diag([2.0, -0.5 + 1.0e-7])
    near_zero = {
        "direct": tensor_square_weight_direct(near_zero_x),
        "factorized": tensor_square_weight_factorized(near_zero_x),
        "eigenvalue": tensor_square_weight_eigenvalues(near_zero_x),
    }
    return {
        "samples": len(records),
        "max_factorized_relative_error": max(
            float(row["factorized_relative_error"]) for row in records
        ),
        "max_eigenvalue_relative_error": max(
            float(row["eigenvalue_relative_error"]) for row in records
        ),
        "minimum_direct_weight": min(float(row["direct"]) for row in records),
        "negative_weight_threshold": -2.0e-10,
        "near_zero_case": near_zero,
    }


def hamiltonian_audit() -> dict[str, float | int]:
    m = 3
    a12, a23 = edge(m, 0, 1), edge(m, 1, 2)
    k = -0.6 * (a12 + a23)
    hamiltonian, basis, q_ops = many_body_hamiltonian(
        m, k, [a12, a23], [1.0, 0.75]
    )
    number = particle_number_operator(basis)
    hermiticity = max_abs(hamiltonian - hamiltonian.getH())
    number_commutator = max_abs(hamiltonian @ number - number @ hamiltonian)

    small_basis = basis_states(4)
    small_channel = np.array([[0.3, -0.7], [-0.7, 0.2]])
    one_body = kron_sum(small_channel)
    q_small = d_gamma(one_body, small_basis)
    normal_ordering = max_abs(
        q_small @ q_small - normal_ordered_q_square(one_body, small_basis)
    )
    return {
        "m": m,
        "hilbert_dimension": len(basis),
        "hamiltonian_nnz": int(hamiltonian.nnz),
        "q1_nnz": int(q_ops[0].nnz),
        "q2_nnz": int(q_ops[1].nnz),
        "hermiticity_max_abs": hermiticity,
        "number_commutator_max_abs": number_commutator,
        "normal_ordering_max_abs": normal_ordering,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2026072901)
    parser.add_argument("--samples-per-m", type=int, default=18)
    args = parser.parse_args()

    summary = {
        "experiment_id": "stage0-oracle-20260729",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "samples_per_m": args.samples_per_m,
        "oracle": oracle_audit(args.seed, args.samples_per_m),
        "hamiltonian": hamiltonian_audit(),
        "versions": {
            "python": __import__("sys").version.split()[0],
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
        },
    }
    encoded = json.dumps(summary, indent=2, sort_keys=True).encode()
    summary["content_sha256_without_hash"] = hashlib.sha256(encoded).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
