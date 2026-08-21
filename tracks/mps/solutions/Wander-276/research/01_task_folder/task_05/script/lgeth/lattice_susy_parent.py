"""Hard-core-fermion lattice supersymmetry on independence complexes."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

import numpy as np
from scipy import sparse


@dataclass(frozen=True)
class LatticeSUSYFrame:
    """Spectral Hodge frame in one fermion-number sector."""

    cycles: int
    n_vertices: int
    charge: int
    edges: tuple[tuple[int, int], ...]
    basis: tuple[int, ...]
    projector_frame: np.ndarray
    complement_frame: np.ndarray
    zero_energies: np.ndarray
    positive_energies: np.ndarray
    gap: float
    kernel_residual: float
    orthogonality_error: float
    expected_rank: int
    q_in: sparse.csr_matrix
    q_out: sparse.csr_matrix
    hamiltonian: sparse.csr_matrix


@dataclass(frozen=True)
class LatticeSUSYResponse:
    """Exact/coexact complement-to-cohomology response factors."""

    minus: np.ndarray
    plus: np.ndarray
    total: np.ndarray
    direct: np.ndarray
    branch_sum_relative_error: float
    direct_relative_error: float
    orthogonality_relative_error: float
    target_leakage: float
    checks: dict[str, bool]


def cycle_union_edges(cycles: int) -> tuple[tuple[int, int], ...]:
    """Return the canonical edges of a disjoint union of six-site cycles."""

    count = int(cycles)
    if count < 1:
        raise ValueError("cycles must be positive")
    return tuple(
        (6 * component + site, 6 * component + (site + 1) % 6)
        for component in range(count)
        for site in range(6)
    )


@lru_cache(maxsize=None)
def _adjacency_masks(
    n_vertices: int,
    edges: tuple[tuple[int, int], ...],
) -> tuple[int, ...]:
    masks = [0] * int(n_vertices)
    for first, second in edges:
        left = int(first)
        right = int(second)
        if not (0 <= left < n_vertices and 0 <= right < n_vertices):
            raise ValueError("edge endpoint is outside the graph")
        if left == right:
            raise ValueError("self-loops are incompatible with the model")
        masks[left] |= 1 << right
        masks[right] |= 1 << left
    return tuple(masks)


@lru_cache(maxsize=None)
def independence_basis(
    n_vertices: int,
    edges: tuple[tuple[int, int], ...],
    charge: int,
) -> tuple[int, ...]:
    """Return sorted independent-set bit strings at fixed fermion number."""

    vertices = int(n_vertices)
    particles = int(charge)
    if vertices < 1:
        raise ValueError("n_vertices must be positive")
    if particles < 0 or particles > vertices:
        return ()
    canonical_edges = tuple(sorted(tuple(sorted(edge)) for edge in edges))
    masks = _adjacency_masks(vertices, canonical_edges)
    states: list[int] = []
    for occupied in combinations(range(vertices), particles):
        state = sum(1 << site for site in occupied)
        if all(not (masks[site] & state) for site in occupied):
            states.append(state)
    return tuple(states)


def normalized_cycle_couplings(cycles: int, seed: int) -> np.ndarray:
    """Draw deterministic complex site couplings normalized on each cycle."""

    count = int(cycles)
    if count < 1:
        raise ValueError("cycles must be positive")
    rng = np.random.default_rng(int(seed))
    values = rng.normal(size=(count, 6)) + 1j * rng.normal(size=(count, 6))
    norms = np.linalg.norm(values, axis=1)
    if np.any(norms <= 0.0):
        raise RuntimeError("cycle coupling draw has a zero component")
    return np.asarray((values / norms[:, None]).reshape(-1), dtype=complex)


def linear_supercharge(
    n_vertices: int,
    edges: tuple[tuple[int, int], ...],
    charge: int,
    couplings: np.ndarray,
) -> sparse.csr_matrix:
    """Return Q_r for constrained single-fermion creation on a graph."""

    vertices = int(n_vertices)
    source_charge = int(charge)
    coefficients = np.asarray(couplings, dtype=complex)
    if coefficients.shape != (vertices,):
        raise ValueError("site coupling vector has the wrong shape")
    if not (
        np.all(np.isfinite(coefficients.real))
        and np.all(np.isfinite(coefficients.imag))
    ):
        raise ValueError("site couplings must be finite")
    canonical_edges = tuple(sorted(tuple(sorted(edge)) for edge in edges))
    masks = _adjacency_masks(vertices, canonical_edges)
    source = independence_basis(vertices, canonical_edges, source_charge)
    target = independence_basis(vertices, canonical_edges, source_charge + 1)
    target_index = {state: index for index, state in enumerate(target)}
    rows: list[int] = []
    columns: list[int] = []
    data: list[complex] = []
    for column, state in enumerate(source):
        for site in range(vertices):
            bit = 1 << site
            if state & bit or masks[site] & state:
                continue
            parity = (state & (bit - 1)).bit_count() % 2
            rows.append(target_index[state | bit])
            columns.append(column)
            data.append((-1 if parity else 1) * coefficients[site])
    return sparse.csr_matrix(
        (np.asarray(data, dtype=complex), (rows, columns)),
        shape=(len(target), len(source)),
        dtype=complex,
    )


def solve_cycle_union_frame(
    cycles: int,
    couplings: np.ndarray,
    *,
    relative_tolerance: float = 1e-10,
) -> LatticeSUSYFrame:
    """Diagonalize the registered C6-union Hodge Laplacian exactly."""

    count = int(cycles)
    vertices = 6 * count
    charge = 2 * count
    coefficients = np.asarray(couplings, dtype=complex)
    if coefficients.shape != (vertices,):
        raise ValueError("site coupling vector disagrees with cycle count")
    edges = cycle_union_edges(count)
    basis = independence_basis(vertices, edges, charge)
    q_in = linear_supercharge(vertices, edges, charge - 1, coefficients)
    q_out = linear_supercharge(vertices, edges, charge, coefficients)
    nilpotency = float(np.linalg.norm((q_out @ q_in).toarray()))
    if nilpotency > 5e-11:
        raise RuntimeError("lattice supercharge is not nilpotent")
    hamiltonian = (q_in @ q_in.getH() + q_out.getH() @ q_out).tocsr()
    dense = np.asarray(hamiltonian.toarray(), dtype=complex)
    dense = 0.5 * (dense + dense.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(dense)
    expected = 2**count
    scale = max(float(np.max(np.abs(eigenvalues))), 1.0)
    tolerance = float(relative_tolerance) * scale
    if expected >= eigenvalues.size:
        raise RuntimeError("registered sector has no positive complement")
    if float(np.max(np.abs(eigenvalues[:expected]))) > tolerance:
        raise RuntimeError("registered cohomology rank is too large")
    if float(eigenvalues[expected]) <= tolerance:
        raise RuntimeError("registered cohomology rank is incomplete")
    projector = np.asarray(eigenvectors[:, :expected], dtype=complex)
    complement = np.asarray(eigenvectors[:, expected:], dtype=complex)
    zero = np.asarray(eigenvalues[:expected], dtype=float)
    positive = np.asarray(eigenvalues[expected:], dtype=float)
    kernel_residual = float(np.linalg.norm(hamiltonian @ projector, ord="fro"))
    orthogonality = max(
        float(np.linalg.norm(projector.conj().T @ projector - np.eye(expected))),
        float(
            np.linalg.norm(
                complement.conj().T @ complement - np.eye(complement.shape[1])
            )
        ),
        float(np.linalg.norm(projector.conj().T @ complement)),
    )
    return LatticeSUSYFrame(
        cycles=count,
        n_vertices=vertices,
        charge=charge,
        edges=edges,
        basis=basis,
        projector_frame=projector,
        complement_frame=complement,
        zero_energies=zero,
        positive_energies=positive,
        gap=float(positive[0]),
        kernel_residual=kernel_residual,
        orthogonality_error=orthogonality,
        expected_rank=expected,
        q_in=q_in,
        q_out=q_out,
        hamiltonian=hamiltonian,
    )


def project_component_tangents(
    couplings: np.ndarray,
    candidates: np.ndarray,
    cycles: int,
    *,
    relative_tolerance: float = 1e-12,
) -> np.ndarray:
    """Remove every component-wise rescaling line and orthonormalize tangents."""

    count = int(cycles)
    coefficients = np.asarray(couplings, dtype=complex)
    values = np.asarray(candidates, dtype=complex)
    if coefficients.shape != (6 * count,):
        raise ValueError("coupling vector disagrees with cycle count")
    if values.ndim != 2 or values.shape[1] != coefficients.size:
        raise ValueError("tangent candidates have the wrong shape")
    projected = values.copy()
    for component in range(count):
        block = slice(6 * component, 6 * (component + 1))
        reference = coefficients[block]
        norm_squared = float(np.vdot(reference, reference).real)
        overlaps = projected[:, block] @ reference.conj()
        projected[:, block] -= np.outer(overlaps / norm_squared, reference)
    q, r = np.linalg.qr(projected.T, mode="reduced")
    diagonal = np.diag(r)
    scale = max(float(np.linalg.norm(projected, ord=2)), np.finfo(float).tiny)
    if diagonal.size != values.shape[0] or np.any(
        np.abs(diagonal) <= float(relative_tolerance) * scale
    ):
        raise ValueError("projected tangent candidates do not have full rank")
    phases = diagonal / np.abs(diagonal)
    tangents = np.asarray((q * phases[None, :]).T, dtype=complex)
    return tangents


def _pseudoinverse_apply(frame: LatticeSUSYFrame, rhs: np.ndarray) -> np.ndarray:
    coordinates = frame.complement_frame.conj().T @ np.asarray(rhs, dtype=complex)
    return frame.complement_frame @ (coordinates / frame.positive_energies[:, None])


def _relative_error(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(float(np.linalg.norm(second)), np.finfo(float).tiny)
    return float(np.linalg.norm(first - second) / scale)


def lattice_susy_response(
    frame: LatticeSUSYFrame,
    couplings: np.ndarray,
    tangents: np.ndarray,
    *,
    tolerance: float = 5e-10,
) -> LatticeSUSYResponse:
    """Return exact, coexact, and direct projector responses."""

    coefficients = np.asarray(couplings, dtype=complex)
    directions = np.asarray(tangents, dtype=complex)
    if coefficients.shape != (frame.n_vertices,):
        raise ValueError("coupling vector disagrees with the frame")
    if directions.ndim != 2 or directions.shape[1] != frame.n_vertices:
        raise ValueError("tangent panel disagrees with the frame")
    projector = frame.projector_frame
    minus_values: list[np.ndarray] = []
    plus_values: list[np.ndarray] = []
    direct_values: list[np.ndarray] = []
    for tangent in directions:
        dq_in = linear_supercharge(
            frame.n_vertices,
            frame.edges,
            frame.charge - 1,
            tangent,
        )
        dq_out = linear_supercharge(
            frame.n_vertices,
            frame.edges,
            frame.charge,
            tangent,
        )
        rhs_minus = frame.q_in @ (dq_in.getH() @ projector)
        rhs_plus = frame.q_out.getH() @ (dq_out @ projector)
        derivative = (
            dq_in @ frame.q_in.getH()
            + frame.q_in @ dq_in.getH()
            + dq_out.getH() @ frame.q_out
            + frame.q_out.getH() @ dq_out
        ).tocsr()
        minus_values.append(-_pseudoinverse_apply(frame, rhs_minus))
        plus_values.append(-_pseudoinverse_apply(frame, rhs_plus))
        direct_values.append(-_pseudoinverse_apply(frame, derivative @ projector))
    minus = np.asarray(minus_values, dtype=complex)
    plus = np.asarray(plus_values, dtype=complex)
    direct = np.asarray(direct_values, dtype=complex)
    total = minus + plus
    branch_error = _relative_error(total, minus + plus)
    direct_error = _relative_error(total, direct)
    orthogonality_errors = []
    for left, right in zip(minus, plus, strict=True):
        scale = max(
            float(np.linalg.norm(left) * np.linalg.norm(right)),
            np.finfo(float).tiny,
        )
        orthogonality_errors.append(
            float(np.linalg.norm(left.conj().T @ right) / scale)
        )
    orthogonality = max(orthogonality_errors)
    total_norm = max(float(np.linalg.norm(total)), np.finfo(float).tiny)
    leakage = float(
        np.linalg.norm(
            np.einsum("ir,mij->mrj", projector.conj(), total, optimize=True)
        )
        / total_norm
    )
    checks = {
        "finite_response": bool(
            np.all(np.isfinite(total.real)) and np.all(np.isfinite(total.imag))
        ),
        "branch_sum": branch_error < float(tolerance),
        "direct_resolvent": direct_error < float(tolerance),
        "hodge_orthogonality": orthogonality < float(tolerance),
        "target_leakage": leakage < float(tolerance),
    }
    return LatticeSUSYResponse(
        minus=minus,
        plus=plus,
        total=total,
        direct=direct,
        branch_sum_relative_error=branch_error,
        direct_relative_error=direct_error,
        orthogonality_relative_error=orthogonality,
        target_leakage=leakage,
        checks=checks,
    )
