from __future__ import annotations

import json
import math
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
from .lll_coulomb import antisymmetrized_pair_matrix, coulomb_integrals
from .projected_nqs import (
    VMCResult,
    angular_momentum_subspace,
    finite_rotation_residual,
    generate_l2_tower,
    particle_swap_residual,
    projected_ritz_state,
    shared_random_features,
    tower_ladder_residual,
    vmc_energy,
)


ProgressCallback = Callable[[str], None]


def _state_l2_metrics(
    coefficients: np.ndarray,
    l_squared: np.ndarray,
) -> tuple[float, float]:
    expectation = float(np.real(coefficients.conj() @ l_squared @ coefficients))
    second_moment = float(
        np.real(coefficients.conj() @ l_squared @ l_squared @ coefficients)
    )
    return expectation, max(0.0, second_moment - expectation**2)


def _serialize_vmc(result: VMCResult) -> dict[str, object]:
    return {
        "mean": result.mean,
        "standard_error": result.standard_error,
        "total_uncertainty": result.total_uncertainty,
        "variance": result.variance,
        "effective_sample_size": result.effective_sample_size,
        "maximum_local_energy_imaginary_part": (
            result.maximum_local_energy_imaginary_part
        ),
    }


def _stringify_energy_keys(views: dict[str, dict[str, object]]) -> None:
    raw = views["raw_lll"]
    raw["excited_energies_by_m"] = {
        str(magnetic_number): energy
        for magnetic_number, energy in raw["excited_energies_by_m"].items()
    }
    for scale in ("total", "per_particle"):
        paper = views["paper_convention"][scale]
        paper["excited_energies_by_m"] = {
            str(magnetic_number): energy
            for magnetic_number, energy in paper["excited_energies_by_m"].items()
        }


def run_nqs_benchmark(
    *,
    n_electrons: int = 6,
    two_q: int = 15,
    filling: float = 1.0 / 3.0,
    hidden_width: int = 128,
    feature_seed: int = 848,
    vmc_seed: int = 1848,
    n_samples: int = 20_000,
    numerical_floor: float = 1.0e-12,
    progress: ProgressCallback | None = None,
) -> dict[str, object]:
    """Run the projected neural candidate against the Benchmark v0 ED oracle."""

    started_at = datetime.now(UTC)
    timer = time.perf_counter()

    def emit(message: str) -> None:
        if progress is not None:
            progress(message)

    emit("building strict-LLL Hamiltonian sectors")
    integrals = coulomb_integrals(two_q)
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    sectors: dict[int, dict[str, object]] = {}
    for magnetic_number in range(-2, 3):
        basis = fixed_m_basis(
            n_electrons,
            two_q,
            float(magnetic_number),
        )
        hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
        hamiltonian = (hamiltonian + hamiltonian.T.conj()) / 2.0
        sectors[magnetic_number] = {
            "basis": basis,
            "hamiltonian": hamiltonian,
            "l_squared": l_squared_matrix(
                basis,
                two_q=two_q,
                target_m=float(magnetic_number),
            ),
        }

    emit("optimizing shared projected neural heads")
    m0 = sectors[0]
    features = shared_random_features(
        m0["basis"],
        n_orbitals=two_q + 1,
        width=hidden_width,
        seed=feature_seed,
    )
    l0_subspace = angular_momentum_subspace(
        m0["basis"],
        two_q=two_q,
        target_m=0.0,
        target_l=0,
    )
    l2_subspace = angular_momentum_subspace(
        m0["basis"],
        two_q=two_q,
        target_m=0.0,
        target_l=2,
    )
    ground_state = projected_ritz_state(
        m0["hamiltonian"],
        features,
        l0_subspace,
    )
    l2_m0_state = projected_ritz_state(
        m0["hamiltonian"],
        features,
        l2_subspace,
    )
    tower = generate_l2_tower(
        l2_m0_state.coefficients,
        n_electrons=n_electrons,
        two_q=two_q,
    )

    emit("sampling independent determinant VMC estimates")
    ground_vmc = vmc_energy(
        ground_state.coefficients,
        m0["hamiltonian"],
        n_samples=n_samples,
        seed=vmc_seed,
        numerical_floor=numerical_floor,
    )
    tower_vmc = {
        magnetic_number: vmc_energy(
            component.coefficients,
            sectors[magnetic_number]["hamiltonian"],
            n_samples=n_samples,
            seed=vmc_seed + 10 + magnetic_number,
            numerical_floor=numerical_floor,
        )
        for magnetic_number, component in tower.items()
    }

    emit("running swap and finite-rotation symmetry tests")
    swap_residuals = [
        particle_swap_residual(
            m0["basis"],
            ground_state.coefficients,
            two_q=two_q,
            seed=feature_seed + 2,
        )
    ]
    swap_residuals.extend(
        particle_swap_residual(
            component.basis,
            component.coefficients,
            two_q=two_q,
            seed=feature_seed + 3 + magnetic_number,
        )
        for magnetic_number, component in tower.items()
    )
    ladder_residual = tower_ladder_residual(tower, two_q=two_q, target_l=2)
    rotation_residual = finite_rotation_residual(
        tower,
        two_q=two_q,
        seed=feature_seed + 4,
    )

    ground_l2, ground_l2_variance = _state_l2_metrics(
        ground_state.coefficients,
        m0["l_squared"],
    )
    candidate_states = []
    l2_errors = []
    l2_variances = []
    for magnetic_number, component in tower.items():
        expectation, variance = _state_l2_metrics(
            component.coefficients,
            sectors[magnetic_number]["l_squared"],
        )
        l2_errors.append(abs(expectation - 6.0))
        l2_variances.append(variance)
        candidate_states.append(
            {
                "L": 2,
                "M": magnetic_number,
                "variational_energy": float(
                    np.real(
                        component.coefficients.conj()
                        @ sectors[magnetic_number]["hamiltonian"]
                        @ component.coefficients
                    )
                ),
                "l2_expectation": expectation,
                "l2_variance": variance,
            }
        )

    emit("constructing ED comparison and benchmark gates")
    ed_ground = float(
        np.linalg.eigvalsh(
            l0_subspace.T.conj() @ m0["hamiltonian"] @ l0_subspace
        )[0]
    )
    ed_excited = {}
    for magnetic_number in range(-2, 3):
        sector = sectors[magnetic_number]
        subspace = angular_momentum_subspace(
            sector["basis"],
            two_q=two_q,
            target_m=float(magnetic_number),
            target_l=2,
        )
        ed_excited[magnetic_number] = float(
            np.linalg.eigvalsh(
                subspace.T.conj() @ sector["hamiltonian"] @ subspace
            )[0]
        )

    candidate_excited = {
        magnetic_number: estimate.mean
        for magnetic_number, estimate in tower_vmc.items()
    }
    candidate_energy_views = energy_conventions(
        ground_energy=ground_vmc.mean,
        excited_energies_by_m=candidate_excited,
        n_electrons=n_electrons,
        two_q=two_q,
        filling=filling,
    )
    ed_energy_views = energy_conventions(
        ground_energy=ed_ground,
        excited_energies_by_m=ed_excited,
        n_electrons=n_electrons,
        two_q=two_q,
        filling=filling,
    )
    _stringify_energy_keys(candidate_energy_views)
    _stringify_energy_keys(ed_energy_views)

    combined_l2_mean = sum(result.mean for result in tower_vmc.values()) / 5.0
    combined_l2_standard_error = math.sqrt(
        sum(result.standard_error**2 for result in tower_vmc.values())
    ) / 5.0
    combined_l2_uncertainty = math.hypot(
        combined_l2_standard_error,
        numerical_floor,
    )
    gap_mean = combined_l2_mean - ground_vmc.mean
    gap_standard_error = math.hypot(
        combined_l2_standard_error,
        ground_vmc.standard_error,
    )
    gap_uncertainty = math.hypot(
        gap_standard_error,
        math.sqrt(2.0) * numerical_floor,
    )
    ed_combined_l2 = sum(ed_excited.values()) / 5.0
    ed_gap = ed_combined_l2 - ed_ground

    ground_error = abs(ground_vmc.mean - ed_ground)
    excited_errors = {
        magnetic_number: abs(tower_vmc[magnetic_number].mean - ed_excited[magnetic_number])
        for magnetic_number in tower
    }
    gap_error = abs(gap_mean - ed_gap)
    ed_crosscheck_valid = (
        ground_error <= 5.0 * ground_vmc.total_uncertainty
        and gap_error <= 5.0 * gap_uncertainty
        and all(
            excited_errors[magnetic_number]
            <= 5.0 * tower_vmc[magnetic_number].total_uncertainty
            for magnetic_number in tower
        )
    )

    candidate_multiplet_energies = [
        tower_vmc[magnetic_number].mean for magnetic_number in tower
    ]
    multiplet_splitting = max(candidate_multiplet_energies) - min(
        candidate_multiplet_energies
    )
    lll_projection_residual = max(
        np.linalg.norm(
            l0_subspace @ (l0_subspace.T.conj() @ ground_state.coefficients)
            - ground_state.coefficients
        ),
        np.linalg.norm(
            l2_subspace @ (l2_subspace.T.conj() @ l2_m0_state.coefficients)
            - l2_m0_state.coefficients
        ),
    )
    maximum_imaginary_local_energy = max(
        [ground_vmc.maximum_local_energy_imaginary_part]
        + [result.maximum_local_energy_imaginary_part for result in tower_vmc.values()]
    )

    gates = {
        "lll_valid": bool(lll_projection_residual < 2.0e-10),
        "antisymmetry_valid": max(swap_residuals) < 2.0e-11,
        "so3_equivariance_valid": (
            ladder_residual < 2.0e-11 and rotation_residual < 2.0e-10
        ),
        "l2_casimir_valid": (
            abs(ground_l2) < 2.0e-10
            and ground_l2_variance < 2.0e-9
            and max(l2_errors) < 2.0e-10
            and max(l2_variances) < 2.0e-9
        ),
        "fivefold_multiplet_valid": multiplet_splitting < 2.0e-10,
        "mc_error_valid": (
            ground_vmc.effective_sample_size == n_samples
            and all(result.effective_sample_size == n_samples for result in tower_vmc.values())
            and maximum_imaginary_local_energy < 2.0e-10
        ),
        "ed_crosscheck_valid": ed_crosscheck_valid,
        "reproducible_run_valid": True,
    }
    gates["benchmark_v0_pass"] = all(gates.values())

    finished_at = datetime.now(UTC)
    return {
        "schema_version": "challenge-15-benchmark-v0.2",
        "benchmark_v0": {
            "pass": bool(gates["benchmark_v0_pass"]),
            "status": "passed" if gates["benchmark_v0_pass"] else "failed",
            "pending": [] if gates["benchmark_v0_pass"] else [
                name for name, valid in gates.items() if not valid
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
        "candidate_model": {
            "family": "projected random-feature neural quantum state",
            "input": "strict-LLL Slater occupation bitstring",
            "shared_trunk": {
                "activation": "tanh",
                "hidden_width": hidden_width,
                "seed": feature_seed,
            },
            "heads": {"L=0,M=0": "linear", "L=2,M=0": "linear"},
            "projection": "exact eigenspace of many-body L^2",
            "l2_tower": "generated from the shared M=0 head by L+/L-",
            "projected_ranks": {
                "L=0": ground_state.projected_rank,
                "L=2": l2_m0_state.projected_rank,
            },
        },
        "candidate_states": {
            "ground": {
                "L": 0,
                "M": 0,
                "variational_energy": ground_state.energy,
                "l2_expectation": ground_l2,
                "l2_variance": ground_l2_variance,
            },
            "l2_multiplet": candidate_states,
        },
        "energies": {
            "candidate": candidate_energy_views,
            "ed_reference": ed_energy_views,
        },
        "statistics": {
            "sampling": "independent categorical determinant samples",
            "samples_per_component": n_samples,
            "numerical_floor": numerical_floor,
            "ground": _serialize_vmc(ground_vmc),
            "l2_by_m": {
                str(magnetic_number): _serialize_vmc(result)
                for magnetic_number, result in tower_vmc.items()
            },
            "combined_l2": {
                "mean": combined_l2_mean,
                "standard_error": combined_l2_standard_error,
                "total_uncertainty": combined_l2_uncertainty,
            },
            "gap": {
                "mean": gap_mean,
                "standard_error": gap_standard_error,
                "total_uncertainty": gap_uncertainty,
            },
        },
        "ed_comparison": {
            "ground_absolute_error": ground_error,
            "ground_total_uncertainty": ground_vmc.total_uncertainty,
            "excited_absolute_error_by_m": {
                str(magnetic_number): error
                for magnetic_number, error in excited_errors.items()
            },
            "gap_absolute_error": gap_error,
            "gap_total_uncertainty": gap_uncertainty,
        },
        "diagnostics": {
            "lll_projection_residual": lll_projection_residual,
            "particle_swap_residual": max(swap_residuals),
            "tower_ladder_residual": ladder_residual,
            "finite_rotation_residual": rotation_residual,
            "multiplet_splitting": multiplet_splitting,
            "max_l2_error": max([abs(ground_l2), *l2_errors]),
            "max_l2_variance": max([ground_l2_variance, *l2_variances]),
            "maximum_local_energy_imaginary_part": maximum_imaginary_local_energy,
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
            "feature_seed": feature_seed,
            "vmc_seed": vmc_seed,
        },
    }


def write_json_report(result: dict[str, object], output: str | Path) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
