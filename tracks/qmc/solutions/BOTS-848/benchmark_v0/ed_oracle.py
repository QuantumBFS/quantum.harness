from __future__ import annotations

import json
import platform
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import scipy

from .conventions import energy_conventions
from .fock_ed import fixed_m_basis, hamiltonian_matrix, l_squared_matrix
from .lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
    monopole_orbital_grid,
)


ProgressCallback = Callable[[str], None]


def _operator_residual(matrix: np.ndarray) -> float:
    return float(np.max(np.abs(matrix))) if matrix.size else 0.0


def _state_quantum_numbers(
    eigenvector: np.ndarray,
    l_squared: np.ndarray,
) -> tuple[float, float]:
    expectation = float(np.real(eigenvector.conj() @ l_squared @ eigenvector))
    second_moment = float(
        np.real(eigenvector.conj() @ l_squared @ l_squared @ eigenvector)
    )
    variance = max(0.0, second_moment - expectation**2)
    return expectation, variance


def _select_lowest_l_state(
    energies: np.ndarray,
    eigenvectors: np.ndarray,
    l_squared: np.ndarray,
    *,
    target_l: int,
) -> dict[str, object]:
    target = float(target_l * (target_l + 1))
    candidates = []
    for index, energy in enumerate(energies):
        expectation, variance = _state_quantum_numbers(
            eigenvectors[:, index],
            l_squared,
        )
        candidates.append((index, float(energy), expectation, variance))

    matching = [
        item
        for item in candidates
        if abs(item[2] - target) < 1.0e-5 and item[3] < 1.0e-4
    ]
    selected = min(matching or candidates, key=lambda item: (item[1], abs(item[2] - target)))
    index, energy, expectation, variance = selected
    return {
        "eigenvector_index": index,
        "energy_raw": energy,
        "L": target_l,
        "l2_expectation": expectation,
        "l2_variance": variance,
    }


def run_ed_oracle(
    *,
    n_electrons: int = 6,
    two_q: int = 15,
    filling: float = 1.0 / 3.0,
    n_theta: int | None = None,
    n_phi: int | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, object]:
    """Run the strict-LLL fixed-M dense-ED Benchmark v0 oracle."""

    started_at = datetime.now(UTC)
    timer = time.perf_counter()
    n_theta = n_theta or max(48, 4 * two_q + 4)
    n_phi = n_phi or max(64, 4 * two_q + 4)

    def emit(message: str) -> None:
        if progress is not None:
            progress(message)

    emit("building normalized LLL orbitals")
    grid = monopole_orbital_grid(
        two_q,
        n_theta=n_theta,
        n_phi=n_phi,
    )
    overlap = np.einsum(
        "pa,p,pc->ac",
        grid.orbitals.conj(),
        grid.weights,
        grid.orbitals,
    )
    overlap_residual = _operator_residual(overlap - np.eye(two_q + 1))

    emit("constructing strict-LLL Coulomb matrix elements")
    integrals = coulomb_integrals(
        two_q,
        n_theta=n_theta,
        n_phi=n_phi,
    )
    two_body_hermiticity = _operator_residual(
        integrals - integrals.transpose(2, 3, 0, 1).conj()
    )
    antisymmetrized = integrals - integrals.swapaxes(2, 3)
    antisymmetry_residual = max(
        _operator_residual(antisymmetrized + antisymmetrized.swapaxes(0, 1)),
        _operator_residual(antisymmetrized + antisymmetrized.swapaxes(2, 3)),
    )
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)

    sector_data: dict[int, dict[str, object]] = {}
    hamiltonian_hermiticity_by_m: dict[str, float] = {}
    commutator_by_m: dict[str, float] = {}
    for magnetic_number in range(-2, 3):
        emit(f"diagonalizing M={magnetic_number:+d} sector")
        basis = fixed_m_basis(n_electrons, two_q, float(magnetic_number))
        hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
        hermiticity_residual = _operator_residual(
            hamiltonian - hamiltonian.T.conj()
        )
        hamiltonian_hermiticity_by_m[str(magnetic_number)] = hermiticity_residual
        hermitian_hamiltonian = (hamiltonian + hamiltonian.T.conj()) / 2.0
        l_squared = l_squared_matrix(
            basis,
            two_q=two_q,
            target_m=float(magnetic_number),
        )
        commutator_by_m[str(magnetic_number)] = _operator_residual(
            hermitian_hamiltonian @ l_squared - l_squared @ hermitian_hamiltonian
        )
        eigenvalues, eigenvectors = np.linalg.eigh(hermitian_hamiltonian)
        sector_data[magnetic_number] = {
            "basis_dimension": len(basis),
            "energies": eigenvalues,
            "eigenvectors": eigenvectors,
            "l_squared": l_squared,
        }

    zero_sector = sector_data[0]
    ground = _select_lowest_l_state(
        zero_sector["energies"],
        zero_sector["eigenvectors"],
        zero_sector["l_squared"],
        target_l=0,
    )
    ground_energy = float(ground["energy_raw"])
    ground["M"] = 0
    ground["is_unique"] = bool(
        np.count_nonzero(
            np.isclose(
                zero_sector["energies"],
                ground_energy,
                rtol=0.0,
                atol=1.0e-10,
            )
        )
        == 1
    )

    l2_multiplet = []
    for magnetic_number in range(-2, 3):
        sector = sector_data[magnetic_number]
        state = _select_lowest_l_state(
            sector["energies"],
            sector["eigenvectors"],
            sector["l_squared"],
            target_l=2,
        )
        state["M"] = magnetic_number
        l2_multiplet.append(state)

    excited_energies = {
        int(state["M"]): float(state["energy_raw"]) for state in l2_multiplet
    }
    energies = energy_conventions(
        ground_energy=ground_energy,
        excited_energies_by_m=excited_energies,
        n_electrons=n_electrons,
        two_q=two_q,
        filling=filling,
    )
    energies["raw_lll"]["excited_energies_by_m"] = {
        str(magnetic_number): energy
        for magnetic_number, energy in energies["raw_lll"][
            "excited_energies_by_m"
        ].items()
    }
    for scale in ("total", "per_particle"):
        paper_view = energies["paper_convention"][scale]
        paper_view["excited_energies_by_m"] = {
            str(magnetic_number): energy
            for magnetic_number, energy in paper_view[
                "excited_energies_by_m"
            ].items()
        }

    expected_l2 = 6.0
    l2_errors = [abs(float(state["l2_expectation"]) - expected_l2) for state in l2_multiplet]
    l2_errors.append(abs(float(ground["l2_expectation"])))
    l2_variances = [float(state["l2_variance"]) for state in l2_multiplet]
    l2_variances.append(float(ground["l2_variance"]))
    multiplet_energies = list(excited_energies.values())
    multiplet_splitting = max(multiplet_energies) - min(multiplet_energies)
    so3_residual = max(commutator_by_m.values())
    max_hamiltonian_hermiticity = max(hamiltonian_hermiticity_by_m.values())

    gates = {
        "lll_valid": overlap_residual < 1.0e-10,
        "antisymmetry_valid": (
            antisymmetry_residual < 1.0e-10
            and two_body_hermiticity < 1.0e-10
            and max_hamiltonian_hermiticity < 1.0e-10
        ),
        "so3_equivariance_valid": so3_residual < 5.0e-10,
        "l2_casimir_valid": (
            max(l2_errors) < 1.0e-8 and max(l2_variances) < 1.0e-7
        ),
        "fivefold_multiplet_valid": (
            [state["M"] for state in l2_multiplet] == [-2, -1, 0, 1, 2]
            and multiplet_splitting < 5.0e-10
        ),
        "zero_statistical_error_valid": True,
        "ed_reference_valid": bool(ground["is_unique"]),
        "reproducible_run_valid": True,
    }
    gates["ed_oracle_valid"] = all(gates.values())

    finished_at = datetime.now(UTC)
    return {
        "schema_version": "challenge-15-benchmark-v0.1",
        "benchmark": {
            "challenge": 15,
            "role": "strict-LLL exact-diagonalization reference oracle",
        },
        "benchmark_v0": {
            "pass": False,
            "status": "ed_reference_ready",
            "pending": [
                "nqs_vmc_candidate",
                "mc_error_valid",
                "ed_crosscheck_valid",
            ],
        },
        "system": {
            "n_electrons": n_electrons,
            "two_q": two_q,
            "q": two_q / 2.0,
            "filling": filling,
            "geometry": "Haldane sphere",
            "polarization": "fully polarized fermions",
        },
        "hamiltonian": {
            "projection": "strict LLL",
            "interaction": "1/(sqrt(Q) * |Omega_i-Omega_j|)",
            "units": "e^2/(epsilon*l_B)",
            "background_in_raw_hamiltonian": False,
        },
        "states": {
            "ground": ground,
            "l2_multiplet": l2_multiplet,
        },
        "energies": energies,
        "statistics": {
            "method": "deterministic exact diagonalization",
            "standard_error": 0.0,
            "effective_sample_size": None,
        },
        "diagnostics": {
            "orbital_overlap_residual": overlap_residual,
            "two_body_hermiticity_residual": two_body_hermiticity,
            "antisymmetry_residual": antisymmetry_residual,
            "hamiltonian_hermiticity_residual_by_m": hamiltonian_hermiticity_by_m,
            "commutator_h_l2_residual_by_m": commutator_by_m,
            "so3_commutator_residual": so3_residual,
            "multiplet_splitting": multiplet_splitting,
            "max_l2_error": max(l2_errors),
            "max_l2_variance": max(l2_variances),
            "sector_dimensions": {
                str(magnetic_number): int(sector_data[magnetic_number]["basis_dimension"])
                for magnetic_number in range(-2, 3)
            },
        },
        "gates": gates,
        "runtime": {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "elapsed_seconds": time.perf_counter() - timer,
            "python_version": sys.version.split()[0],
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "platform": platform.platform(),
            "quadrature": {"n_theta": n_theta, "n_phi": n_phi},
        },
    }


def write_json_report(result: dict[str, object], output: str | Path) -> None:
    """Write a Benchmark v0 result as deterministic, human-readable JSON."""

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
