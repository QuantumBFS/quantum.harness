from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
import scipy.sparse
import scipy.sparse.linalg

from .lattice import PeriodicGraph, validate_graph

_LOCAL_SPARSE_GUARD_BYTES = 16 * 1024**3
_LOCAL_DENSE_GUARD_BYTES = 2 * 1024**3
_FLOAT64_BYTES = np.dtype(np.float64).itemsize
_INT64_BYTES = np.dtype(np.int64).itemsize
_PAULI_X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float64)
_PAULI_Z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.float64)
_IDENTITY = np.eye(2, dtype=np.float64)
_MAX_EXACT_THERMAL_SITES = 12
_GROUND_STATE_NORM_ATOL = 1e-8
_GROUND_STATE_RESIDUAL_ATOL = 1e-8


@dataclass(frozen=True)
class EDResourceEstimate:
    """Exact storage sizes and conservative local-workspace bounds.

    `dense_matrix_bytes` and `dense_eigenvector_bytes` are exact storage sizes
    for one float64 dense Hamiltonian matrix and one float64 dense eigenvector matrix.
    `sparse_diagonal_peak_bytes` is the conservative peak-workspace bound for the
    diagonal-only sparse fast path, `sparse_nonzero_field_peak_bytes` is the
    conservative peak-workspace bound for the nonzero-field COO->CSR path, and
    `sparse_peak_bytes` is a compatibility alias for the nonzero-field bound.
    `dense_builder_peak_bytes` and `dense_full_thermal_peak_bytes` are conservative
    peak-workspace bounds for the dense Kronecker builder and the full thermal
    dense workflow.
    """

    site_count: int
    dimension: int
    dense_matrix_bytes: int
    dense_eigenvector_bytes: int
    sparse_diagonal_peak_bytes: int
    sparse_nonzero_field_peak_bytes: int
    sparse_peak_bytes: int
    dense_builder_peak_bytes: int
    dense_full_thermal_peak_bytes: int


@dataclass(frozen=True)
class ThermalObservables:
    beta: float
    energy: float
    energy_density: float
    transverse_magnetization: float
    m2: float
    m4: float
    binder_ratio: float


def _require_int(value: object, *, name: str) -> int:
    if not isinstance(value, Integral) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int")
    return int(value)


def _require_finite_real(value: object, *, name: str) -> float:
    if not isinstance(value, Real) or isinstance(value, bool):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _require_positive_finite_real(value: object, *, name: str) -> float:
    if not isinstance(value, Real) or isinstance(value, bool):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a finite positive real number")
    return result


def estimate_ed_resources(site_count: int) -> EDResourceEstimate:
    site_count = _require_int(site_count, name="site_count")
    if site_count <= 0:
        raise ValueError("site_count must be positive")

    dimension = 1 << site_count
    dense_matrix_bytes = dimension * dimension * _FLOAT64_BYTES
    dense_eigenvector_bytes = dimension * dimension * _FLOAT64_BYTES
    dense_eigenvalue_bytes = dimension * _FLOAT64_BYTES

    diagonal_bytes = dimension * _FLOAT64_BYTES
    diagonal_indices_bytes = dimension * _INT64_BYTES
    diagonal_indptr_bytes = (dimension + 1) * _INT64_BYTES
    sparse_diagonal_peak_bytes = (
        diagonal_bytes + diagonal_indices_bytes + diagonal_indptr_bytes
    )

    sparse_nnz = (site_count + 1) * dimension
    coo_buffer_bytes = sparse_nnz * (2 * _INT64_BYTES + _FLOAT64_BYTES)
    csr_storage_bytes = sparse_nnz * (_INT64_BYTES + _FLOAT64_BYTES) + (
        dimension + 1
    ) * _INT64_BYTES
    sparse_nonzero_field_peak_bytes = (
        diagonal_bytes + coo_buffer_bytes + csr_storage_bytes
    )

    dense_kron_intermediate_bytes = (dense_matrix_bytes + 3) // 4
    dense_builder_peak_bytes = (
        dense_matrix_bytes + dense_matrix_bytes + dense_kron_intermediate_bytes
    )
    dense_full_thermal_peak_bytes = max(
        dense_builder_peak_bytes,
        dense_matrix_bytes + dense_eigenvector_bytes + dense_eigenvalue_bytes,
    )
    return EDResourceEstimate(
        site_count=site_count,
        dimension=dimension,
        dense_matrix_bytes=dense_matrix_bytes,
        dense_eigenvector_bytes=dense_eigenvector_bytes,
        sparse_diagonal_peak_bytes=sparse_diagonal_peak_bytes,
        sparse_nonzero_field_peak_bytes=sparse_nonzero_field_peak_bytes,
        sparse_peak_bytes=sparse_nonzero_field_peak_bytes,
        dense_builder_peak_bytes=dense_builder_peak_bytes,
        dense_full_thermal_peak_bytes=dense_full_thermal_peak_bytes,
    )


def _ising_diagonal_energy(
    graph: PeriodicGraph,
    *,
    state: int,
    coupling: float,
) -> float:
    energy = 0.0
    for left, right in graph.bonds:
        sigma_left = 1.0 if ((state >> left) & 1) == 0 else -1.0
        sigma_right = 1.0 if ((state >> right) & 1) == 0 else -1.0
        energy -= coupling * sigma_left * sigma_right
    return energy


def build_sparse_hamiltonian(
    graph: PeriodicGraph,
    *,
    coupling: float = 1.0,
    field: float,
) -> scipy.sparse.csr_matrix:
    validate_graph(graph)
    coupling = _require_finite_real(coupling, name="coupling")
    field = _require_finite_real(field, name="field")
    estimate = estimate_ed_resources(graph.site_count)
    sparse_peak_bytes = (
        estimate.sparse_diagonal_peak_bytes
        if field == 0.0
        else estimate.sparse_nonzero_field_peak_bytes
    )
    _enforce_sparse_guard(sparse_peak_bytes)

    dimension = estimate.dimension
    diagonal_entries = np.empty(dimension, dtype=np.float64)
    for state in range(dimension):
        diagonal_entries[state] = _ising_diagonal_energy(
            graph, state=state, coupling=coupling
        )

    if field == 0.0:
        indices = np.arange(dimension, dtype=np.int64)
        indptr = np.arange(dimension + 1, dtype=np.int64)
        return scipy.sparse.csr_matrix(
            (diagonal_entries, indices, indptr),
            shape=(dimension, dimension),
            dtype=np.float64,
            copy=False,
        )

    off_diagonal_count = graph.site_count * dimension
    total_nnz = dimension + off_diagonal_count
    rows = np.empty(total_nnz, dtype=np.int64)
    cols = np.empty(total_nnz, dtype=np.int64)
    data = np.empty(total_nnz, dtype=np.float64)

    cursor = 0
    for state in range(dimension):
        rows[cursor] = state
        cols[cursor] = state
        data[cursor] = diagonal_entries[state]
        cursor += 1

    for state in range(dimension):
        for site in range(graph.site_count):
            rows[cursor] = state
            cols[cursor] = state ^ (1 << site)
            data[cursor] = -field
            cursor += 1

    return scipy.sparse.coo_matrix(
        (data, (rows, cols)),
        shape=(dimension, dimension),
        dtype=np.float64,
    ).tocsr()


def _tensor_product(operators: list[np.ndarray]) -> np.ndarray:
    result = operators[0]
    for operator in operators[1:]:
        result = np.kron(result, operator)
    return result


def _single_site_operator(site_count: int, *, site: int, operator: np.ndarray) -> np.ndarray:
    # Tensor factors are ordered site_count-1 ... 0 so basis index bits match
    # the sparse convention with site 0 as the least-significant bit.
    factors = [
        operator if axis == site else _IDENTITY
        for axis in reversed(range(site_count))
    ]
    return _tensor_product(factors)


def _two_site_operator(
    site_count: int,
    *,
    left: int,
    right: int,
    operator: np.ndarray,
) -> np.ndarray:
    factors = []
    for axis in reversed(range(site_count)):
        if axis == left or axis == right:
            factors.append(operator)
        else:
            factors.append(_IDENTITY)
    return _tensor_product(factors)


def _enforce_exact_thermal_site_limit(graph: PeriodicGraph) -> None:
    if graph.site_count > _MAX_EXACT_THERMAL_SITES:
        raise MemoryError(
            "exact thermal ED requires site_count <= 12 before dense "
            "construction/eigensolve"
        )


def _longitudinal_magnetization_diagonal(site_count: int) -> np.ndarray:
    dimension = 1 << site_count
    diagonal = np.empty(dimension, dtype=np.float64)
    for state in range(dimension):
        diagonal[state] = (site_count - 2 * state.bit_count()) / site_count
    return diagonal


def _diagonal_operator_in_eigenbasis(
    eigenvectors: np.ndarray, diagonal_entries: np.ndarray
) -> np.ndarray:
    probabilities = np.abs(eigenvectors) ** 2
    return probabilities.T @ diagonal_entries


def _operator_diagonal_in_eigenbasis(
    eigenvectors: np.ndarray, operator: np.ndarray
) -> np.ndarray:
    rotated = operator @ eigenvectors
    diagonal = np.einsum("ij,ij->j", eigenvectors.conj(), rotated, optimize=True)
    return np.asarray(diagonal.real, dtype=np.float64)


def _thermal_average(weights: np.ndarray, values: np.ndarray) -> float:
    partition = float(np.sum(weights))
    return float(np.dot(weights, values) / partition)


def _transverse_magnetization_operator(site_count: int) -> np.ndarray:
    dimension = 1 << site_count
    operator = np.zeros((dimension, dimension), dtype=np.float64)
    for site in range(site_count):
        operator += _single_site_operator(site_count, site=site, operator=_PAULI_X)
    operator /= site_count
    return operator


def _transverse_magnetization_from_state(vector: np.ndarray, site_count: int) -> float:
    state = np.asarray(vector)
    expectation = 0.0
    basis = np.arange(state.size, dtype=np.int64)
    for site in range(site_count):
        expectation += float(np.vdot(state, state[basis ^ (1 << site)]).real)
    return expectation / site_count


def _thermal_observables_from_eigensystem(
    *,
    beta: float,
    energies: np.ndarray,
    eigenvectors: np.ndarray,
    site_count: int,
) -> ThermalObservables:
    shifted_weights = np.exp(-beta * (energies - float(np.min(energies))))
    magnetization = _longitudinal_magnetization_diagonal(site_count)
    m2_diagonal = _diagonal_operator_in_eigenbasis(eigenvectors, magnetization**2)
    m4_diagonal = _diagonal_operator_in_eigenbasis(eigenvectors, magnetization**4)
    transverse_diagonal = _operator_diagonal_in_eigenbasis(
        eigenvectors, _transverse_magnetization_operator(site_count)
    )

    energy = _thermal_average(shifted_weights, energies)
    m2 = _thermal_average(shifted_weights, m2_diagonal)
    m4 = _thermal_average(shifted_weights, m4_diagonal)
    transverse_magnetization = _thermal_average(shifted_weights, transverse_diagonal)
    return ThermalObservables(
        beta=beta,
        energy=energy,
        energy_density=energy / site_count,
        transverse_magnetization=transverse_magnetization,
        m2=m2,
        m4=m4,
        binder_ratio=m2**2 / m4,
    )


def thermal_observables_payload(result: ThermalObservables) -> dict[str, object]:
    beta = result.beta
    if math.isinf(beta):
        regime = "ground_state"
        beta_payload: float | None = None
    elif math.isfinite(beta) and beta > 0.0:
        regime = "finite_temperature"
        beta_payload = beta
    else:
        raise ValueError("observables beta must be positive finite or math.inf")

    return {
        "regime": regime,
        "beta": beta_payload,
        "energy": _require_finite_real(result.energy, name="energy"),
        "energy_density": _require_finite_real(
            result.energy_density, name="energy_density"
        ),
        "transverse_magnetization": _require_finite_real(
            result.transverse_magnetization, name="transverse_magnetization"
        ),
        "m2": _require_finite_real(result.m2, name="m2"),
        "m4": _require_finite_real(result.m4, name="m4"),
        "binder_ratio": _require_finite_real(result.binder_ratio, name="binder_ratio"),
    }


def _enforce_dense_guard(estimate: EDResourceEstimate) -> None:
    if estimate.dense_full_thermal_peak_bytes > _LOCAL_DENSE_GUARD_BYTES:
        gib = _LOCAL_DENSE_GUARD_BYTES / 1024**3
        raise MemoryError(
            "full thermal ED would require "
            f"{estimate.dense_full_thermal_peak_bytes} bytes, exceeding the "
            f"{gib:.0f} GiB local guard"
        )


def _enforce_sparse_guard(sparse_peak_bytes: int) -> None:
    if sparse_peak_bytes > _LOCAL_SPARSE_GUARD_BYTES:
        gib = _LOCAL_SPARSE_GUARD_BYTES / 1024**3
        raise MemoryError(
            "sparse Hamiltonian construction would require "
            f"{sparse_peak_bytes} bytes, exceeding the {gib:.0f} GiB "
            "local guard"
        )


def build_dense_hamiltonian_oracle(
    graph: PeriodicGraph,
    *,
    coupling: float = 1.0,
    field: float,
) -> np.ndarray:
    validate_graph(graph)
    coupling = _require_finite_real(coupling, name="coupling")
    field = _require_finite_real(field, name="field")

    estimate = estimate_ed_resources(graph.site_count)
    _enforce_dense_guard(estimate)

    dimension = estimate.dimension
    hamiltonian = np.zeros((dimension, dimension), dtype=np.float64)

    for left, right in graph.bonds:
        term = _two_site_operator(
            graph.site_count,
            left=left,
            right=right,
            operator=_PAULI_Z,
        )
        np.multiply(term, -coupling, out=term)
        hamiltonian += term

    for site in range(graph.site_count):
        term = _single_site_operator(
            graph.site_count,
            site=site,
            operator=_PAULI_X,
        )
        np.multiply(term, -field, out=term)
        hamiltonian += term

    return hamiltonian


def exact_thermal_observables(
    graph: PeriodicGraph, *, coupling: float, field: float, beta: float
) -> ThermalObservables:
    validate_graph(graph)
    _enforce_exact_thermal_site_limit(graph)
    coupling = _require_finite_real(coupling, name="coupling")
    field = _require_finite_real(field, name="field")
    beta = _require_positive_finite_real(beta, name="beta")

    hamiltonian = build_dense_hamiltonian_oracle(graph, coupling=coupling, field=field)
    energies, eigenvectors = np.linalg.eigh(hamiltonian)
    return _thermal_observables_from_eigensystem(
        beta=beta,
        energies=np.asarray(energies, dtype=np.float64),
        eigenvectors=np.asarray(eigenvectors),
        site_count=graph.site_count,
    )


def sparse_ground_state_observables(
    graph: PeriodicGraph, *, coupling: float, field: float
) -> ThermalObservables:
    validate_graph(graph)
    coupling = _require_finite_real(coupling, name="coupling")
    field = _require_positive_finite_real(field, name="field")

    hamiltonian = build_sparse_hamiltonian(graph, coupling=coupling, field=field)
    try:
        energies, vectors = scipy.sparse.linalg.eigsh(hamiltonian, k=1, which="SA")
    except scipy.sparse.linalg.ArpackNoConvergence as exc:
        raise ValueError("eigsh failed to converge") from exc

    energies = np.asarray(energies, dtype=np.float64)
    eigenvectors = np.asarray(vectors)
    if energies.shape != (1,) or eigenvectors.shape != (hamiltonian.shape[0], 1):
        raise ValueError("eigsh must return exactly one ground-state eigenpair")

    vector = eigenvectors[:, 0]
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or not math.isclose(
        norm, 1.0, rel_tol=0.0, abs_tol=_GROUND_STATE_NORM_ATOL
    ):
        raise ValueError("ground-state eigenvector must be normalized")

    residual = float(np.linalg.norm(hamiltonian @ vector - energies[0] * vector))
    if not math.isfinite(residual) or residual > _GROUND_STATE_RESIDUAL_ATOL:
        raise ValueError("ground-state eigenpair residual is too large")

    probabilities = np.abs(vector) ** 2
    magnetization = _longitudinal_magnetization_diagonal(graph.site_count)
    energy = float(energies[0])
    m2 = float(np.dot(probabilities, magnetization**2))
    m4 = float(np.dot(probabilities, magnetization**4))
    transverse_magnetization = _transverse_magnetization_from_state(
        vector, graph.site_count
    )
    return ThermalObservables(
        beta=math.inf,
        energy=energy,
        energy_density=energy / graph.site_count,
        transverse_magnetization=transverse_magnetization,
        m2=m2,
        m4=m4,
        binder_ratio=m2**2 / m4,
    )
