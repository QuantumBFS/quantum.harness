#!/usr/bin/env python3
"""Independent local three-site Fock analysis for the frozen A/B vertices.

The script constructs the 8x8 Fock operators directly from the CAR algebra,
forms the complete S3 twirls, analyzes particle-number sectors, and decomposes
h=g(I-M) in the canonical S3-invariant operator basis

    I, N, K, Q2, P_s^dagger P_s, n1 n2 n3.

It does not import the CTQMC or ED implementation. Every run performs internal
algebra, symmetry, positivity, Fock-lift, and reconstruction checks before
emitting strict finite JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.linalg import expm


ALGORITHM_ID = "local-three-site-s3-twirl-physics-v1"
SOURCE_COMMIT = "886a082963429f3f62deb9e6090352a58a05b89a"
N_MODES = 3
FOCK_DIMENSION = 1 << N_MODES
EPSILON = 0.01
KAPPA = 0.02
VERTEX_STRENGTH = 0.25
COUPLING_G = 0.25
TOLERANCE = 2.0e-11


@dataclass(frozen=True)
class FockAlgebra:
    annihilation: Tuple[np.ndarray, ...]
    creation: Tuple[np.ndarray, ...]
    number: Tuple[np.ndarray, ...]
    total_number: np.ndarray


def occupied(mask: int) -> Tuple[int, ...]:
    return tuple(site for site in range(N_MODES) if mask & (1 << site))


def particle_number(mask: int) -> int:
    return int(mask.bit_count())


def annihilation_operator(site: int) -> np.ndarray:
    result = np.zeros((FOCK_DIMENSION, FOCK_DIMENSION), dtype=float)
    lower_mask = (1 << site) - 1
    for source in range(FOCK_DIMENSION):
        if not source & (1 << site):
            continue
        target = source ^ (1 << site)
        sign = -1.0 if (source & lower_mask).bit_count() % 2 else 1.0
        result[target, source] = sign
    return result


def build_fock_algebra() -> FockAlgebra:
    annihilation = tuple(annihilation_operator(i) for i in range(N_MODES))
    creation = tuple(operator.T for operator in annihilation)
    number = tuple(creation[i] @ annihilation[i] for i in range(N_MODES))
    total_number = sum(number, np.zeros((FOCK_DIMENSION, FOCK_DIMENSION)))
    return FockAlgebra(annihilation, creation, number, total_number)


def quadratic_lift(generator: np.ndarray, algebra: FockAlgebra) -> np.ndarray:
    result = np.zeros((FOCK_DIMENSION, FOCK_DIMENSION), dtype=float)
    for i in range(N_MODES):
        for j in range(N_MODES):
            result += float(generator[i, j]) * (
                algebra.creation[i] @ algebra.annihilation[j]
            )
    return result


def fock_lift(one_body: np.ndarray) -> np.ndarray:
    """Gamma(U) from exterior minors in the integer-mask Fock basis."""
    result = np.zeros((FOCK_DIMENSION, FOCK_DIMENSION), dtype=float)
    for source in range(FOCK_DIMENSION):
        columns = occupied(source)
        for target in range(FOCK_DIMENSION):
            rows = occupied(target)
            if len(rows) != len(columns):
                continue
            if not rows:
                result[target, source] = 1.0
            else:
                result[target, source] = float(
                    np.linalg.det(one_body[np.ix_(rows, columns)])
                )
    return result


def permutation_matrix(permutation: Sequence[int]) -> np.ndarray:
    return np.eye(N_MODES, dtype=float)[list(permutation)]


def matrix_inf_norm(matrix: np.ndarray) -> float:
    return float(np.linalg.norm(matrix, np.inf))


def relative_inf_residual(actual: np.ndarray, expected: np.ndarray) -> float:
    return matrix_inf_norm(actual - expected) / max(
        1.0, matrix_inf_norm(expected)
    )


def cluster_values(values: Sequence[float], tolerance: float = 2.0e-10) -> List[Dict[str, Any]]:
    clusters: List[List[float]] = []
    for value in sorted(float(item) for item in values):
        if not clusters or abs(value - sum(clusters[-1]) / len(clusters[-1])) > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [
        {
            "value": float(sum(cluster) / len(cluster)),
            "multiplicity": len(cluster),
        }
        for cluster in clusters
    ]


def sector_block(operator: np.ndarray, number: int) -> np.ndarray:
    indices = [mask for mask in range(FOCK_DIMENSION)
               if particle_number(mask) == number]
    return operator[np.ix_(indices, indices)]


def sector_report(
    hamiltonian: np.ndarray,
    twirl: Optional[np.ndarray],
) -> Mapping[str, Any]:
    labels = {
        0: "vacuum",
        1: "one_particle",
        2: "two_particle",
        3: "fully_occupied",
    }
    result: Dict[str, Any] = {}
    for number in range(N_MODES + 1):
        h_values = np.linalg.eigvalsh(sector_block(hamiltonian, number))
        entry: Dict[str, Any] = {
            "label": labels[number],
            "dimension": len(h_values),
            "hamiltonian_energies": cluster_values(h_values),
        }
        if twirl is not None:
            m_values = np.linalg.eigvalsh(sector_block(twirl, number))
            entry["twirl_eigenvalues"] = cluster_values(m_values)
        result[str(number)] = entry
    return result


def canonical_operators(algebra: FockAlgebra) -> Mapping[str, np.ndarray]:
    identity = np.eye(FOCK_DIMENSION)
    hopping = np.zeros_like(identity)
    for i in range(N_MODES):
        for j in range(N_MODES):
            if i != j:
                hopping += algebra.creation[i] @ algebra.annihilation[j]
    pair_density = np.zeros_like(identity)
    for i in range(N_MODES):
        for j in range(i + 1, N_MODES):
            pair_density += algebra.number[i] @ algebra.number[j]
    pair_creator = (
        algebra.creation[0] @ algebra.creation[1]
        - algebra.creation[0] @ algebra.creation[2]
        + algebra.creation[1] @ algebra.creation[2]
    ) / math.sqrt(3.0)
    sign_pair_projector = pair_creator @ pair_creator.T
    triple_density = algebra.number[0] @ algebra.number[1] @ algebra.number[2]
    return {
        "identity": identity,
        "N": algebra.total_number,
        "K": hopping,
        "Q2": pair_density,
        "Ps_dagger_Ps": sign_pair_projector,
        "n1_n2_n3": triple_density,
    }


def canonical_decomposition(
    operator: np.ndarray,
    basis: Mapping[str, np.ndarray],
) -> Mapping[str, Any]:
    names = list(basis)
    design = np.column_stack([basis[name].reshape(-1) for name in names])
    coefficients, _, rank, singular_values = np.linalg.lstsq(
        design, operator.reshape(-1), rcond=None
    )
    reconstructed = sum(
        float(coefficient) * basis[name]
        for name, coefficient in zip(names, coefficients)
    )
    residual = relative_inf_residual(reconstructed, operator)
    quadratic_design = np.column_stack(
        [basis[name].reshape(-1) for name in ("identity", "N", "K")]
    )
    quadratic_coefficients, _, _, _ = np.linalg.lstsq(
        quadratic_design, operator.reshape(-1), rcond=None
    )
    quadratic_fit = sum(
        float(coefficient) * basis[name]
        for name, coefficient in zip(
            ("identity", "N", "K"), quadratic_coefficients
        )
    )
    quadratic_residual = relative_inf_residual(quadratic_fit, operator)
    coefficient_map = {
        name: float(value) for name, value in zip(names, coefficients)
    }
    J = coefficient_map["Ps_dagger_Ps"]
    pair_signs = np.array([1.0, -1.0, 1.0])
    correlated_pair_matrix = (
        J / 3.0 * np.outer(pair_signs, pair_signs)
    )
    return {
        "basis_order": names,
        "coefficients": coefficient_map,
        "rank": int(rank),
        "singular_values": [float(value) for value in singular_values],
        "relative_reconstruction_residual_inf": residual,
        "best_quadratic_relative_residual_inf": quadratic_residual,
        "quartic_interpretation": {
            "pair_density_coefficient_after_expanding_projector":
                coefficient_map["Q2"] + J / 3.0,
            "correlated_pair_transition_prefactor": J / 3.0,
            "pair_basis": ["|12>", "|13>", "|23>"],
            "J_projector_matrix_in_pair_basis":
                correlated_pair_matrix.tolist(),
            "genuine_three_density_coefficient":
                coefficient_map["n1_n2_n3"],
        },
    }


def irrep_energies(coefficients: Mapping[str, float]) -> Mapping[str, Any]:
    C = coefficients["identity"]
    e = coefficients["N"]
    t = coefficients["K"]
    V = coefficients["Q2"]
    J = coefficients["Ps_dagger_Ps"]
    W = coefficients["n1_n2_n3"]
    return {
        "vacuum": {"energy": C, "multiplicity": 1},
        "one_particle_symmetric": {
            "energy": C + e + 2.0 * t,
            "multiplicity": 1,
        },
        "one_particle_standard": {
            "energy": C + e - t,
            "multiplicity": 2,
        },
        "two_particle_sign": {
            "energy": C + 2.0 * e - 2.0 * t + V + J,
            "multiplicity": 1,
        },
        "two_particle_standard": {
            "energy": C + 2.0 * e + t + V,
            "multiplicity": 2,
        },
        "fully_occupied": {
            "energy": C + 3.0 * e + 3.0 * V + J + W,
            "multiplicity": 1,
        },
    }


def irrep_spectrum_values(irrep: Mapping[str, Any], number: int) -> List[float]:
    names = {
        0: ("vacuum",),
        1: ("one_particle_symmetric", "one_particle_standard"),
        2: ("two_particle_sign", "two_particle_standard"),
        3: ("fully_occupied",),
    }[number]
    result: List[float] = []
    for name in names:
        result.extend(
            [float(irrep[name]["energy"])] * int(irrep[name]["multiplicity"])
        )
    return sorted(result)


def build_twirl(
    generator: np.ndarray,
    algebra: FockAlgebra,
) -> Tuple[np.ndarray, Mapping[str, Any]]:
    resolved: List[np.ndarray] = []
    fock_lift_residuals: List[float] = []
    for permutation in itertools.permutations(range(N_MODES)):
        P = permutation_matrix(permutation)
        oriented = P @ generator @ P.T
        direct = expm(VERTEX_STRENGTH * quadratic_lift(oriented, algebra))
        exterior = fock_lift(expm(VERTEX_STRENGTH * oriented))
        fock_lift_residuals.append(relative_inf_residual(direct, exterior))
        resolved.append(direct)
    twirl = sum(resolved, np.zeros_like(resolved[0])) / len(resolved)
    return twirl, {
        "resolved_orientation_count": len(resolved),
        "max_exponential_vs_exterior_residual_inf":
            max(fock_lift_residuals),
    }


def permutation_invariance_residual(
    operator: np.ndarray,
) -> float:
    residual = 0.0
    for permutation in itertools.permutations(range(N_MODES)):
        gamma_p = fock_lift(permutation_matrix(permutation))
        residual = max(
            residual,
            relative_inf_residual(gamma_p @ operator @ gamma_p.T, operator),
        )
    return residual


def operator_diagnostics(
    operator: np.ndarray,
    algebra: FockAlgebra,
) -> Mapping[str, float]:
    eigenvalues = np.linalg.eigvalsh((operator + operator.T) / 2.0)
    return {
        "hermiticity_relative_inf":
            relative_inf_residual(operator, operator.T),
        "number_commutator_relative_inf":
            matrix_inf_norm(operator @ algebra.total_number
                            - algebra.total_number @ operator)
            / max(1.0, matrix_inf_norm(operator)),
        "permutation_invariance_relative_inf":
            permutation_invariance_residual(operator),
        "minimum_eigenvalue": float(eigenvalues.min()),
        "maximum_eigenvalue": float(eigenvalues.max()),
    }


def analyze_operator(
    name: str,
    hamiltonian: np.ndarray,
    twirl: Optional[np.ndarray],
    basis: Mapping[str, np.ndarray],
    algebra: FockAlgebra,
    construction: Mapping[str, Any],
) -> Mapping[str, Any]:
    decomposition = canonical_decomposition(hamiltonian, basis)
    irreps = irrep_energies(decomposition["coefficients"])
    return {
        "name": name,
        "construction": dict(construction),
        "diagnostics": operator_diagnostics(hamiltonian, algebra),
        "particle_number_sectors": sector_report(hamiltonian, twirl),
        "canonical_decomposition": decomposition,
        "irrep_energies": irreps,
        "hamiltonian_matrix_fock_basis": hamiltonian.tolist(),
        "twirl_matrix_fock_basis": None if twirl is None else twirl.tolist(),
    }


def car_residual(algebra: FockAlgebra) -> float:
    identity = np.eye(FOCK_DIMENSION)
    residual = 0.0
    for i in range(N_MODES):
        for j in range(N_MODES):
            anti = (
                algebra.annihilation[i] @ algebra.creation[j]
                + algebra.creation[j] @ algebra.annihilation[i]
            )
            expected = identity if i == j else np.zeros_like(identity)
            residual = max(residual, matrix_inf_norm(anti - expected))
    return residual


def self_check(
    report: Mapping[str, Any],
    operators: Mapping[str, np.ndarray],
    basis: Mapping[str, np.ndarray],
    algebra: FockAlgebra,
) -> Mapping[str, Any]:
    checks: Dict[str, float] = {}
    checks["car_absolute_inf"] = car_residual(algebra)
    checks["total_additivity_relative_inf"] = relative_inf_residual(
        operators["A"] + operators["B"], operators["A_plus_B"]
    )
    for name, operator in operators.items():
        diagnostics = report["operators"][name]["diagnostics"]
        decomposition = report["operators"][name]["canonical_decomposition"]
        checks[f"{name}_hermiticity"] = float(
            diagnostics["hermiticity_relative_inf"]
        )
        checks[f"{name}_number_commutator"] = float(
            diagnostics["number_commutator_relative_inf"]
        )
        checks[f"{name}_S3_invariance"] = float(
            diagnostics["permutation_invariance_relative_inf"]
        )
        checks[f"{name}_basis_reconstruction"] = float(
            decomposition["relative_reconstruction_residual_inf"]
        )
        checks[f"{name}_negative_eigenvalue_violation"] = max(
            0.0, -float(diagnostics["minimum_eigenvalue"])
        )
        irreps = report["operators"][name]["irrep_energies"]
        for number in range(N_MODES + 1):
            actual = sorted(
                float(value) for value in np.linalg.eigvalsh(
                    sector_block(operator, number)
                )
            )
            predicted = irrep_spectrum_values(irreps, number)
            checks[f"{name}_sector_{number}_irrep_match"] = max(
                (abs(a - b) for a, b in zip(actual, predicted)),
                default=0.0,
            )
    for family in ("A", "B"):
        checks[f"{family}_fock_lift"] = float(
            report["operators"][family]["construction"][
                "max_exponential_vs_exterior_residual_inf"
            ]
        )
        vacuum_energy = report["operators"][family][
            "particle_number_sectors"
        ]["0"]["hamiltonian_energies"][0]["value"]
        checks[f"{family}_vacuum_energy"] = abs(float(vacuum_energy))
    maximum = max(checks.values())
    if maximum > TOLERANCE:
        failing = {name: value for name, value in checks.items()
                   if value > TOLERANCE}
        raise AssertionError(f"self-check failure: {failing}")
    return {
        "status": "pass",
        "tolerance": TOLERANCE,
        "maximum_residual_or_violation": maximum,
        "checks": checks,
    }


def assert_finite_json(value: Any, path: str = "root") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite JSON value at {path}")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            assert_finite_json(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_finite_json(child, f"{path}[{index}]")


def build_report() -> Mapping[str, Any]:
    algebra = build_fock_algebra()
    epsilon = EPSILON
    kappa = KAPPA
    A = np.array([
        [-1.0 - epsilon - kappa, 1.0, -epsilon],
        [0.0, -1.0 - kappa, 1.0],
        [2.0, 0.0, -2.0 - kappa],
    ])
    S = np.diag([1.0, 1.0, -1.0])
    B = S @ A @ S
    twirl_A, construction_A = build_twirl(A, algebra)
    twirl_B, construction_B = build_twirl(B, algebra)
    identity = np.eye(FOCK_DIMENSION)
    h_A = COUPLING_G * (identity - twirl_A)
    h_B = COUPLING_G * (identity - twirl_B)
    h_total = h_A + h_B
    basis = canonical_operators(algebra)
    operators = {"A": h_A, "B": h_B, "A_plus_B": h_total}
    basis_order = [
        {"mask": mask, "ket": "|" + "".join(
            str(int(bool(mask & (1 << site)))) for site in range(N_MODES)
        ) + ">", "particle_number": particle_number(mask)}
        for mask in range(FOCK_DIMENSION)
    ]
    report: Dict[str, Any] = {
        "schema_version": 1,
        "algorithm_id": ALGORITHM_ID,
        "status": "analytic_numeric_local_result",
        "scope": "one isolated three-site vertex; no lattice phase claim",
        "provenance": {
            "source_commit": SOURCE_COMMIT,
            "source_commit_role": "repository base commit; analysis files are uncommitted working-tree additions",
            "source_file": "tracks/qmc/solutions/Genshin_Impact-121/local_vertex_physics.py",
            "source_file_sha256": hashlib.sha256(
                Path(__file__).resolve().read_bytes()
            ).hexdigest(),
        },
        "frozen_parameters": {
            "epsilon": EPSILON,
            "kappa": KAPPA,
            "s": VERTEX_STRENGTH,
            "g_A": COUPLING_G,
            "g_B": COUPLING_G,
        },
        "generator_matrices": {"A": A.tolist(), "B": B.tolist()},
        "basis_convention": {
            "ordering": "integer masks 0,...,7",
            "ket_label": "|n1 n2 n3> written without spaces",
            "site_bit_order": "site 1 is the least-significant mask bit",
            "matrix_indices": "row=destination Fock state, column=source Fock state",
            "fermion_sign": "annihilation at site i contributes (-1)^(occupied sites below i)",
        },
        "fock_basis": basis_order,
        "canonical_basis_definition": {
            "N": "sum_i n_i",
            "K": "sum_{i!=j} c_i^dagger c_j",
            "Q2": "sum_{i<j} n_i n_j",
            "Ps_dagger": "(c1^dagger c2^dagger-c1^dagger c3^dagger+c2^dagger c3^dagger)/sqrt(3)",
            "three_body": "n1 n2 n3",
        },
        "operators": {
            "A": analyze_operator(
                "g(I-M_A)", h_A, twirl_A, basis, algebra, construction_A
            ),
            "B": analyze_operator(
                "g(I-M_B)", h_B, twirl_B, basis, algebra, construction_B
            ),
            "A_plus_B": analyze_operator(
                "g(I-M_A)+g(I-M_B)",
                h_total,
                None,
                basis,
                algebra,
                {"resolved_orientation_count": 12},
            ),
        },
    }
    checks = self_check(report, operators, basis, algebra)
    total_decomposition = report["operators"]["A_plus_B"][
        "canonical_decomposition"
    ]
    coefficients = total_decomposition["coefficients"]
    expected_W = float(
        (2.0 * COUPLING_G)
        * np.linalg.det(np.eye(N_MODES) - expm(VERTEX_STRENGTH * A))
    )
    observed_W = float(coefficients["n1_n2_n3"])
    W_identity_residual = abs(expected_W - observed_W)
    checks["checks"]["three_density_determinant_identity"] = W_identity_residual
    checks["maximum_residual_or_violation"] = max(
        float(checks["maximum_residual_or_violation"]), W_identity_residual
    )
    if W_identity_residual > TOLERANCE:
        raise AssertionError(
            "three-density determinant identity failed: "
            f"{W_identity_residual}"
        )
    report["self_checks"] = checks
    interaction_scale = max(
        abs(float(coefficients[name]))
        for name in ("Q2", "Ps_dagger_Ps", "n1_n2_n3")
    )
    report["physical_conclusion"] = {
        "is_exactly_quadratic": bool(
            total_decomposition["best_quadratic_relative_residual_inf"]
            <= TOLERANCE
        ),
        "has_density_density_interaction":
            abs(float(coefficients["Q2"])) > TOLERANCE,
        "has_correlated_pair_hopping":
            abs(float(coefficients["Ps_dagger_Ps"])) > TOLERANCE,
        "has_genuine_three_density_term":
            abs(float(coefficients["n1_n2_n3"])) > TOLERANCE,
        "largest_interaction_coefficient_abs": interaction_scale,
        "three_density_determinant_certificate": {
            "identity": "W=(g_A+g_B) det[I-exp(sA)]",
            "predicted": expected_W,
            "decomposed": observed_W,
            "absolute_residual": W_identity_residual,
        },
        "interpretation":
            "The complete A+B twirl is an S3-symmetric, number-conserving, "
            "positive-semidefinite interacting cluster term. Its nonzero "
            "Ps_dagger_Ps coefficient is a quartic correlated transition "
            "between two-particle configurations, and its residual n1 n2 n3 "
            "coefficient is a genuine three-density interaction after all "
            "constant, quadratic, and two-body canonical pieces are removed. "
            "The vacuum is the local zero-energy state; this local spectrum "
            "alone does not identify a macroscopic finite-density phase.",
    }
    assert_finite_json(report)
    return report


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="." + path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = build_report()
    if args.output is not None:
        atomic_write_json(args.output, report)
        print(json.dumps({
            "status": report["status"],
            "self_checks": report["self_checks"]["status"],
            "output": str(args.output),
        }, allow_nan=False))
    else:
        print(json.dumps(
            report,
            indent=None if args.compact else 2,
            sort_keys=True,
            allow_nan=False,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
