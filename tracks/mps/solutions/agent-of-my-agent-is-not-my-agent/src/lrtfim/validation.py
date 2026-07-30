"""Small-system validation utilities for the compact long-range MPO."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import eigh
from tenpy.algorithms.exact_diag import ExactDiag
from tenpy.models.model import MPOModel
from tenpy.networks.mps import MPS
from tenpy.tools.misc import inverse_permutation

from .couplings import periodic_couplings
from .dmrg_workflow import build_mpo_model, run_ground_and_first_excited
from .exponential_fit import ExponentialFit, periodized_exponential_couplings
from .mpo import build_periodized_mpo


def exact_pair_hamiltonian(
    length: int,
    sigma: float,
    gamma: float,
) -> NDArray[np.float64]:
    """Construct the dense periodic Hurwitz-zeta Pauli TFIM Hamiltonian."""
    couplings = periodic_couplings(length, sigma)
    if not np.isfinite(gamma):
        raise ValueError("gamma must be finite")
    dimension = 1 << length
    states = np.arange(dimension)
    hamiltonian = np.zeros((dimension, dimension), dtype=float)
    diagonal = np.zeros(dimension, dtype=float)
    spins = np.empty((length, dimension), dtype=float)
    for site in range(length):
        bit = length - 1 - site
        spins[site] = 1.0 - 2.0 * ((states >> bit) & 1)
        hamiltonian[states, states ^ (1 << bit)] -= float(gamma)
    for i in range(length):
        for j in range(i + 1, length):
            diagonal -= couplings[j - i - 1] * spins[i] * spins[j]
    hamiltonian[states, states] = diagonal
    return hamiltonian


def lowest_eigenpairs(
    matrix: NDArray[np.float64],
    count: int = 2,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return the lowest eigenvalues and corresponding normalized vectors."""
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("matrix must be square")
    if not isinstance(count, (int, np.integer)) or not 1 <= count <= matrix.shape[0]:
        raise ValueError("count must lie between 1 and the matrix dimension")
    energies, vectors = eigh(
        matrix,
        subset_by_index=(0, count - 1),
        check_finite=False,
        overwrite_a=False,
        driver="evr",
    )
    return np.asarray(energies), np.asarray(vectors)


def translation_averaged_zz_statevector(
    vector: NDArray[np.complexfloating] | NDArray[np.floating],
    length: int,
) -> NDArray[np.float64]:
    """Compute periodic translation-averaged ``ZZ`` correlations."""
    state = np.asarray(vector)
    if state.ndim != 1 or state.size != 1 << length:
        raise ValueError("vector length must equal 2**length")
    probabilities = np.abs(state) ** 2
    norm = float(np.sum(probabilities))
    if norm <= 0.0:
        raise ValueError("state vector must have nonzero norm")
    probabilities = probabilities / norm
    basis = np.arange(1 << length)
    spins = np.asarray(
        [
            1.0 - 2.0 * ((basis >> (length - 1 - site)) & 1)
            for site in range(length)
        ]
    )
    correlations = []
    for distance in range(1, length // 2 + 1):
        values = [
            np.dot(
                probabilities,
                spins[site] * spins[(site + distance) % length],
            )
            for site in range(length)
        ]
        correlations.append(float(np.mean(values)))
    return np.asarray(correlations)


def translation_averaged_zz_mps(psi: MPS) -> NDArray[np.float64]:
    """Compute periodic translation-averaged ``ZZ`` correlations for an MPS."""
    correlations = []
    for distance in range(1, psi.L // 2 + 1):
        values = [
            psi.expectation_value_term(
                [
                    ("Sigmaz", site),
                    ("Sigmaz", (site + distance) % psi.L),
                ]
            )
            for site in range(psi.L)
        ]
        correlations.append(float(np.real(np.mean(values))))
    return np.asarray(correlations)


def scalar_errors(reference: float, value: float) -> dict[str, float | None]:
    """Return absolute and reference-relative scalar errors."""
    absolute = abs(float(value) - float(reference))
    relative = None if reference == 0.0 else absolute / abs(float(reference))
    return {"absolute": absolute, "relative": relative}


def dense_mpo_hamiltonian(model: MPOModel) -> NDArray[np.float64]:
    """Expand the actual finite MPO, explicitly sizing TeNPy's ED workspace."""
    dimension = int(np.prod([site.dim for site in model.lat.mps_sites()]))
    exact_diag = ExactDiag(model, max_size=dimension * dimension)
    exact_diag.build_full_H_from_mpo()
    if exact_diag.full_H is None:
        raise RuntimeError("TeNPy did not build the dense MPO Hamiltonian")
    tensor = exact_diag.full_H.split_legs()
    site_count = model.lat.N_sites
    tensor = tensor.itranspose(
        [
            f"p{site}{star}"
            for star in ("", "*")
            for site in range(site_count)
        ]
    )
    dense_tensor = tensor.to_ndarray()
    permutations = [
        inverse_permutation(site.perm) for site in model.lat.mps_sites()
    ] * 2
    dense_tensor = dense_tensor[np.ix_(*permutations)]
    return np.asarray(dense_tensor, dtype=float).reshape(dimension, dimension)


def _spectrum_record(
    energies: NDArray[np.float64],
    correlations: NDArray[np.float64],
) -> dict:
    return {
        "ground_energy": float(energies[0]),
        "excited_energy": float(energies[1]),
        "gap": float(energies[1] - energies[0]),
        "correlations": [float(value) for value in correlations],
    }


def _comparison(reference: dict, value: dict) -> dict:
    reference_correlations = np.asarray(reference["correlations"])
    value_correlations = np.asarray(value["correlations"])
    correlation_absolute = np.abs(value_correlations - reference_correlations)
    correlation_relative = np.divide(
        correlation_absolute,
        np.abs(reference_correlations),
        out=np.full_like(correlation_absolute, np.nan),
        where=reference_correlations != 0.0,
    )
    return {
        "ground_energy": scalar_errors(
            reference["ground_energy"], value["ground_energy"]
        ),
        "excited_energy": scalar_errors(
            reference["excited_energy"], value["excited_energy"]
        ),
        "gap": scalar_errors(reference["gap"], value["gap"]),
        "correlation_max_absolute": float(np.max(correlation_absolute)),
        "correlation_profile": [
            {
                "distance": distance,
                "absolute": float(absolute),
                "relative": None if np.isnan(relative) else float(relative),
            }
            for distance, (absolute, relative) in enumerate(
                zip(correlation_absolute, correlation_relative, strict=True),
                start=1,
            )
        ],
    }


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    return value


def validate_cell(
    *,
    length: int,
    sigma: float,
    gamma: float,
    fit: ExponentialFit,
    dmrg_options: dict,
) -> dict:
    """Run exact-pair ED, compact-MPO ED, and compact-MPO DMRG for one cell."""
    exact_couplings = periodic_couplings(length, sigma)
    compact_couplings = periodized_exponential_couplings(length, fit)
    coupling_profile = [
        {
            "distance": distance,
            "exact": float(exact),
            "compact": float(compact),
            "absolute_error": float(abs(compact - exact)),
            "relative_error": float(abs(compact - exact) / exact),
        }
        for distance, (exact, compact) in enumerate(
            zip(exact_couplings, compact_couplings, strict=True),
            start=1,
        )
    ]

    exact_matrix = exact_pair_hamiltonian(length, sigma, gamma)
    exact_energies, exact_vectors = lowest_eigenpairs(exact_matrix)
    exact_record = _spectrum_record(
        exact_energies,
        translation_averaged_zz_statevector(exact_vectors[:, 0], length),
    )

    mpo = build_periodized_mpo(
        length,
        fit.lambdas,
        fit.coefficients,
        gamma,
    )
    model = build_mpo_model(mpo)
    compact_matrix = dense_mpo_hamiltonian(model)
    relative_frobenius = float(
        np.linalg.norm(compact_matrix - exact_matrix) / np.linalg.norm(exact_matrix)
    )
    compact_energies, compact_vectors = lowest_eigenpairs(compact_matrix)
    compact_record = _spectrum_record(
        compact_energies,
        translation_averaged_zz_statevector(compact_vectors[:, 0], length),
    )
    del compact_matrix, exact_matrix, exact_vectors, compact_vectors

    dmrg = run_ground_and_first_excited(model, dmrg_options)
    dmrg_record = {
        "ground_energy": dmrg.ground.energy,
        "excited_energy": dmrg.excited.energy,
        "gap": dmrg.gap,
        "correlations": [
            float(value) for value in translation_averaged_zz_mps(dmrg.ground.psi)
        ],
        "diagnostics": {
            "ground_variance": dmrg.ground.variance,
            "excited_variance": dmrg.excited.variance,
            "ground_max_discarded_weight": dmrg.ground.max_discarded_weight,
            "excited_max_discarded_weight": dmrg.excited.max_discarded_weight,
            "ground_max_chi": dmrg.ground.max_chi,
            "excited_max_chi": dmrg.excited.max_chi,
            "overlap": dmrg.overlap,
            "ground_sweep_statistics": _json_safe(dmrg.ground.sweep_statistics),
            "excited_sweep_statistics": _json_safe(dmrg.excited.sweep_statistics),
        },
    }
    return {
        "parameters": {
            "length": int(length),
            "sigma": float(sigma),
            "gamma": float(gamma),
            "num_exponentials": int(len(fit.lambdas)),
            "r_fit": int(fit.r_fit),
        },
        "hamiltonian": {
            "relative_frobenius_error": relative_frobenius,
            "coupling_max_relative_error": max(
                row["relative_error"] for row in coupling_profile
            ),
        },
        "coupling_profile": coupling_profile,
        "layers": {
            "exact_pair_ed": exact_record,
            "compact_mpo_ed": compact_record,
            "compact_mpo_dmrg": dmrg_record,
        },
        "comparisons": {
            "mpo_representation": _comparison(exact_record, compact_record),
            "mps_optimization": _comparison(compact_record, dmrg_record),
        },
    }
