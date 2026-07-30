from __future__ import annotations

from math import sqrt

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh

from challenge15.fermions import DeterminantBasis, apply_one_body, state_two_m


SPARSE_GRAM_TOLERANCE = 1e-12
SPARSE_L2_RESIDUAL_TOLERANCE = 1e-11
SPARSE_LADDER_TOLERANCE = 1e-11


def angular_operators(basis: DeterminantBasis, return_l2_only: bool = False):
    if return_l2_only:
        return _fixed_sector_l2(basis)
    if basis.total_two_m is not None:
        raise ValueError("full angular operators require the unrestricted determinant basis")

    lz_values = np.array(
        [state_two_m(basis.spec, state) / 2.0 for state in basis.states],
        dtype=np.float64,
    )
    lz = sparse.diags(lz_values, format="csr")
    lp = _ladder_matrix(basis, basis, step=1)
    lm = _ladder_matrix(basis, basis, step=-1)
    return lz, lp, lm


def target_irrep_isometry(basis: DeterminantBasis, target_l: int) -> np.ndarray:
    _validate_target_l(basis.spec, target_l)
    if basis.total_two_m != 0:
        raise ValueError("target irrep isometries are defined in the fixed-M=0 sector")

    l2 = np.asarray(angular_operators(basis, return_l2_only=True), dtype=np.complex128)
    target_eigenvalue = target_l * (target_l + 1)
    eigenvalues, eigenvectors = np.linalg.eigh(l2)
    eigenspace = eigenvectors[:, np.abs(eigenvalues - target_eigenvalue) <= 1e-10]
    if eigenspace.shape[1] == 0:
        raise ValueError(f"no states found in the L={target_l} irrep")
    return _canonical_thin_subspace_basis(eigenspace)[0]


def target_irrep_isometry_sparse(
    basis: DeterminantBasis,
    target_l: int,
    *,
    return_diagnostics: bool = False,
) -> np.ndarray | tuple[np.ndarray, dict[str, object]]:
    """Construct only one known-multiplicity L sector with sparse shift-invert."""

    _validate_target_l(basis.spec, target_l)
    if basis.total_two_m != 0:
        raise ValueError("target irrep isometries are defined in the fixed-M=0 sector")
    isometry, diagnostics = _sparse_target_l2_basis(basis, target_l)
    ladder = verify_ladder_multiplet(basis, target_l, isometry)
    ladder_error = max(
        float(ladder["max_ladder_error"]),
        float(ladder["max_norm_error"]),
        float(ladder["max_orthogonality_error"]),
    )
    if ladder_error > SPARSE_LADDER_TOLERANCE:
        raise RuntimeError("sparse target-sector ladder residual exceeds 1e-11")
    diagnostics = {
        **diagnostics,
        "ladder_intertwining_residual": ladder_error,
        "generator_ladder_intertwining_residual": ladder_error,
        "ladder_intertwining_tolerance": SPARSE_LADDER_TOLERANCE,
        "generator_ladder_intertwining_tolerance": SPARSE_LADDER_TOLERANCE,
    }
    return (isometry, diagnostics) if return_diagnostics else isometry


def _sparse_target_l2_basis(
    basis: DeterminantBasis,
    target_l: int,
) -> tuple[np.ndarray, dict[str, object]]:
    at_l = DeterminantBasis.with_two_m(basis.spec, 2 * target_l).dimension
    above_l = (
        DeterminantBasis.with_two_m(basis.spec, 2 * (target_l + 1)).dimension
        if target_l < basis.spec.l_max
        else 0
    )
    multiplicity = at_l - above_l
    if multiplicity <= 0:
        raise ValueError(f"no states found in the L={target_l} irrep")
    if multiplicity >= basis.dimension - 1:
        raise ValueError("sparse target sector is not bounded for this small basis")

    l2 = _fixed_sector_l2_sparse(basis)
    target = float(target_l * (target_l + 1))
    eigenvalues, eigenvectors = eigsh(
        l2,
        k=multiplicity,
        sigma=target + 1e-7,
        which="LM",
        tol=1e-12,
        maxiter=max(1000, 20 * basis.dimension),
    )
    residual = np.linalg.norm(l2 @ eigenvectors - eigenvectors * eigenvalues)
    scale = max(np.linalg.norm(eigenvectors), 1.0)
    if residual / scale > SPARSE_L2_RESIDUAL_TOLERANCE:
        raise RuntimeError("sparse target-sector eigensolver residual is too large")
    if np.max(np.abs(eigenvalues - target)) > SPARSE_L2_RESIDUAL_TOLERANCE:
        raise RuntimeError("sparse target-sector eigensolver found the wrong sector")
    isometry, thin_diagnostics = _canonical_thin_subspace_basis(eigenvectors)
    gram_error = float(
        np.linalg.norm(
            isometry.conj().T @ isometry - np.eye(multiplicity), ord=2
        )
    )
    target_error = float(
        np.linalg.norm(l2 @ isometry - target * isometry)
        / max(np.linalg.norm(isometry), 1.0)
    )
    if gram_error > SPARSE_GRAM_TOLERANCE:
        raise RuntimeError("sparse target-sector Gram defect exceeds 1e-12")
    if target_error > SPARSE_L2_RESIDUAL_TOLERANCE:
        raise RuntimeError("sparse target-sector L2 residual exceeds 1e-11")
    if isometry.shape != (basis.dimension, multiplicity):
        raise RuntimeError("sparse target-sector isometry validation failed")
    diagnostics = {
        **thin_diagnostics,
        "multiplicity": multiplicity,
        "gram_defect": gram_error,
        "l2_target_residual": target_error,
        "gram_tolerance": SPARSE_GRAM_TOLERANCE,
        "l2_target_residual_tolerance": SPARSE_L2_RESIDUAL_TOLERANCE,
    }
    return isometry, diagnostics


def _canonical_thin_subspace_basis(
    vectors: np.ndarray,
    *,
    pivot_tolerance: float = 1e-7,
) -> tuple[np.ndarray, dict[str, object]]:
    """Fix a multiplicity gauge using only D×r and r×r intermediates."""

    matrix = np.asarray(vectors, dtype=np.complex128)
    if matrix.ndim != 2 or matrix.shape[0] < matrix.shape[1]:
        raise ValueError("thin subspace basis must have shape D by r with D>=r")
    dimension, rank = matrix.shape
    if rank == 0:
        return matrix.copy(), {
            "row_pivots": [],
            "workspace_elements_upper_bound": 0,
            "dense_projector_allocated": False,
        }
    gram = matrix.conj().T @ matrix
    gram_values, gram_vectors = np.linalg.eigh(gram)
    if gram_values[0] <= np.finfo(np.float64).eps * gram_values[-1]:
        raise ValueError("thin subspace basis is rank deficient")
    inverse_sqrt = (
        gram_vectors * (1.0 / np.sqrt(gram_values))
    ) @ gram_vectors.conj().T
    orthonormal = matrix @ inverse_sqrt

    row_scale = max(float(np.max(np.linalg.norm(orthonormal, axis=1))), 1.0)
    threshold_squared = (pivot_tolerance * row_scale) ** 2
    pivots: list[int] = []
    selected = np.zeros((0, rank), dtype=np.complex128)
    for row_index, row in enumerate(orthonormal):
        residual_squared = float(np.vdot(row, row).real)
        if pivots:
            row_gram = selected @ selected.conj().T
            overlaps = selected @ row.conj()
            residual_squared -= float(
                np.vdot(overlaps, np.linalg.solve(row_gram, overlaps)).real
            )
        if max(residual_squared, 0.0) > threshold_squared:
            candidate_pivots = [*pivots, row_index]
            candidate = orthonormal[candidate_pivots, :]
            candidate_singular_values = np.linalg.svd(
                candidate, compute_uv=False
            )
            if (
                candidate_singular_values[-1]
                > pivot_tolerance * candidate_singular_values[0]
            ):
                pivots = candidate_pivots
                selected = candidate
                if len(pivots) == rank:
                    break
    if len(pivots) != rank:
        raise ValueError("thin subspace basis has no stable lexicographic pivots")

    pivot_rows = orthonormal[pivots, :]
    left_vectors, singular_values, right_vectors_h = np.linalg.svd(
        pivot_rows, full_matrices=False
    )
    if singular_values[-1] <= np.finfo(np.float64).eps * singular_values[0]:
        raise ValueError("gauge-fixed thin basis lost rank")
    polar_unitary = left_vectors @ right_vectors_h
    canonical = orthonormal @ polar_unitary.conj().T
    return canonical, {
        "row_pivots": pivots,
        "workspace_elements_upper_bound": dimension * rank + 4 * rank * rank,
        "dense_projector_allocated": False,
    }


def verify_ladder_multiplet(
    basis: DeterminantBasis,
    target_l: int,
    isometry: np.ndarray,
) -> dict[str, object]:
    _validate_target_l(basis.spec, target_l)
    if basis.total_two_m != 0:
        raise ValueError("ladder verification expects the fixed-M=0 sector")

    vectors = np.asarray(isometry, dtype=np.complex128)
    if vectors.ndim == 1:
        vectors = vectors[:, None]
    if vectors.shape[0] != basis.dimension:
        raise ValueError("isometry row count must match the supplied basis dimension")

    sector_vectors: dict[int, np.ndarray] = {0: vectors.copy()}
    max_norm_error = 0.0
    max_orthogonality_error = 0.0
    max_ladder_error = 0.0

    def update_errors(matrix: np.ndarray) -> None:
        nonlocal max_norm_error, max_orthogonality_error
        gram = matrix.conj().T @ matrix
        identity = np.eye(matrix.shape[1], dtype=np.complex128)
        max_norm_error = max(
            max_norm_error,
            float(np.max(np.abs(np.diag(gram) - 1.0))),
        )
        max_orthogonality_error = max(
            max_orthogonality_error,
            float(np.max(np.abs(gram - np.diag(np.diag(gram))))),
        )
        max_orthogonality_error = max(
            max_orthogonality_error,
            float(np.max(np.abs(gram - identity))),
        )

    update_errors(sector_vectors[0])

    current_basis = basis
    current_vectors = sector_vectors[0]
    for current_m in range(0, target_l):
        next_basis = DeterminantBasis.with_two_m(basis.spec, 2 * (current_m + 1))
        lp = _ladder_matrix(current_basis, next_basis, step=1)
        factor = sqrt(target_l * (target_l + 1) - current_m * (current_m + 1))
        next_vectors = np.asarray(lp @ current_vectors, dtype=np.complex128) / factor
        sector_vectors[2 * (current_m + 1)] = next_vectors
        update_errors(sector_vectors[2 * (current_m + 1)])
        lm = _ladder_matrix(next_basis, current_basis, step=-1)
        lowered = np.asarray(lm @ sector_vectors[2 * (current_m + 1)], dtype=np.complex128)
        max_ladder_error = max(
            max_ladder_error,
            _ladder_coefficient_error(current_vectors, lowered, factor),
        )
        current_basis = next_basis
        current_vectors = sector_vectors[2 * (current_m + 1)]

    current_basis = basis
    current_vectors = sector_vectors[0]
    for current_m in range(0, -target_l, -1):
        next_basis = DeterminantBasis.with_two_m(basis.spec, 2 * (current_m - 1))
        lm = _ladder_matrix(current_basis, next_basis, step=-1)
        factor = sqrt(target_l * (target_l + 1) - current_m * (current_m - 1))
        next_vectors = np.asarray(lm @ current_vectors, dtype=np.complex128) / factor
        sector_vectors[2 * (current_m - 1)] = next_vectors
        update_errors(sector_vectors[2 * (current_m - 1)])
        lp = _ladder_matrix(next_basis, current_basis, step=1)
        raised = np.asarray(lp @ sector_vectors[2 * (current_m - 1)], dtype=np.complex128)
        max_ladder_error = max(
            max_ladder_error,
            _ladder_coefficient_error(current_vectors, raised, factor),
        )
        current_basis = next_basis
        current_vectors = sector_vectors[2 * (current_m - 1)]

    ordered_two_m = tuple(range(-2 * target_l, 2 * target_l + 1, 2))
    ordered_vectors = {two_m: sector_vectors[two_m] for two_m in ordered_two_m}
    return {
        "sector_two_m": ordered_two_m,
        "vectors": ordered_vectors,
        "max_norm_error": max_norm_error,
        "max_orthogonality_error": max_orthogonality_error,
        "max_ladder_error": max_ladder_error,
    }


def _fixed_sector_l2(basis: DeterminantBasis) -> np.ndarray:
    return _fixed_sector_l2_sparse(basis).toarray()


def _fixed_sector_l2_sparse(basis: DeterminantBasis) -> sparse.csr_matrix:
    if basis.total_two_m is None:
        lz, lp, lm = angular_operators(basis)
        return (
            lm @ lp + lz @ (lz + sparse.identity(basis.dimension, format="csr"))
        ).tocsr()

    current_m = basis.total_two_m / 2.0
    plus_basis = DeterminantBasis.with_two_m(basis.spec, basis.total_two_m + 2)
    lp = _ladder_matrix(basis, plus_basis, step=1)
    lm_from_plus = _ladder_matrix(plus_basis, basis, step=-1)
    l2 = (lm_from_plus @ lp).astype(np.complex128).tocsr()
    if current_m != 0.0:
        l2 = l2 + current_m * (current_m + 1.0) * sparse.identity(
            basis.dimension, dtype=np.complex128, format="csr"
        )
    return l2


def _ladder_matrix(
    domain_basis: DeterminantBasis,
    codomain_basis: DeterminantBasis,
    step: int,
) -> sparse.csr_matrix:
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []

    for column, state in enumerate(domain_basis.states):
        for source, two_m in enumerate(domain_basis.spec.two_m_values):
            target = source + step
            if target < 0 or target >= domain_basis.spec.orbital_count:
                continue
            moved = apply_one_body(state, source=source, target=target)
            if moved is None:
                continue
            row = codomain_basis.state_index.get(moved.state)
            if row is None:
                continue
            rows.append(row)
            cols.append(column)
            data.append(moved.sign * _single_particle_ladder(domain_basis.spec.two_q, two_m, step))

    return sparse.csr_matrix(
        (np.asarray(data, dtype=np.float64), (rows, cols)),
        shape=(codomain_basis.dimension, domain_basis.dimension),
    )


def _single_particle_ladder(two_q: int, two_m: int, step: int) -> float:
    if step == 1:
        return 0.5 * sqrt((two_q - two_m) * (two_q + two_m + 2))
    if step == -1:
        return 0.5 * sqrt((two_q + two_m) * (two_q - two_m + 2))
    raise ValueError("step must be +1 or -1")


def _ladder_coefficient_error(
    reference_vectors: np.ndarray,
    ladder_image: np.ndarray,
    factor: float,
) -> float:
    """Return the maximum columnwise relative ladder residual.

    Each multiplet column is compared directly against ``factor * reference`` in
    Euclidean norm, with an absolute floor of ``1.0`` in the denominator so the
    public ``1e-11`` acceptance threshold remains meaningful even for tiny
    expected vectors.
    """

    expected = factor * np.asarray(reference_vectors, dtype=np.complex128)
    actual = np.asarray(ladder_image, dtype=np.complex128)
    residual = actual - expected
    max_error = 0.0
    for column in range(expected.shape[1]):
        scale = max(np.linalg.norm(expected[:, column]), 1.0)
        column_error = np.linalg.norm(residual[:, column]) / scale
        max_error = max(max_error, float(column_error))
    return max_error


def _canonical_projector_basis(projector: np.ndarray, rank: int, tol: float = 1e-10) -> np.ndarray:
    matrix = np.asarray(projector, dtype=np.complex128)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("projector must be a square matrix")
    if not isinstance(rank, int) or isinstance(rank, bool) or rank < 0:
        raise ValueError("rank must be a nonnegative Python integer")
    if rank == 0:
        return np.zeros((matrix.shape[0], 0), dtype=np.complex128)
    if not np.allclose(matrix, matrix.conj().T, atol=tol, rtol=0.0):
        raise ValueError("projector must be Hermitian")

    basis_columns: list[np.ndarray] = []
    selected_columns: list[int] = []

    while len(basis_columns) < rank:
        candidates: list[tuple[tuple[object, ...], int, np.ndarray]] = []
        for column_index in range(matrix.shape[1]):
            if column_index in selected_columns:
                continue
            residual = matrix[:, column_index].copy()
            for basis_vector in basis_columns:
                residual -= basis_vector * np.vdot(basis_vector, residual)
            residual_norm = np.linalg.norm(residual)
            if residual_norm <= tol:
                continue
            normalized = _phase_fix_column(residual / residual_norm)
            candidates.append((_column_sort_key(normalized), column_index, normalized))

        if not candidates:
            raise ValueError("ambiguous projector rank")

        candidates.sort(key=lambda item: (item[0], item[1]))
        _, column_index, vector = candidates[0]
        for basis_vector in basis_columns:
            vector -= basis_vector * np.vdot(basis_vector, vector)
        vector_norm = np.linalg.norm(vector)
        if vector_norm <= tol:
            raise ValueError("ambiguous projector rank")
        basis_columns.append(_phase_fix_column(vector / vector_norm))
        selected_columns.append(column_index)

    canonical = matrix @ np.column_stack(basis_columns)
    canonical, triangular = np.linalg.qr(canonical, mode="reduced")
    if np.any(np.abs(np.diag(triangular)) <= tol):
        raise ValueError("canonical projector basis lost rank during reorthonormalization")
    canonical = _sort_phase_fixed_columns(canonical)
    gram = canonical.conj().T @ canonical
    if not np.allclose(gram, np.eye(rank, dtype=np.complex128), atol=tol, rtol=0.0):
        raise ValueError("canonical projector basis is not orthonormal")
    if not np.allclose(canonical @ canonical.conj().T, matrix, atol=1e-9, rtol=0.0):
        raise ValueError("canonical projector basis does not reproduce the projector")
    return canonical


def _sort_phase_fixed_columns(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.complex128)
    if matrix.ndim != 2:
        raise ValueError("matrix must be two-dimensional")
    if matrix.shape[1] == 0:
        return matrix

    columns = [_phase_fix_column(matrix[:, index]) for index in range(matrix.shape[1])]
    columns.sort(key=_column_sort_key)
    return np.column_stack(columns)


def _phase_fix_column(column: np.ndarray) -> np.ndarray:
    fixed = np.asarray(column, dtype=np.complex128).copy()
    pivot = _pivot_index(fixed)
    if pivot is None:
        return fixed
    phase = np.exp(-1j * np.angle(fixed[pivot]))
    fixed *= phase
    if fixed[pivot].real < 0:
        fixed *= -1.0
    if abs(fixed[pivot].imag) < 1e-14:
        fixed[pivot] = fixed[pivot].real + 0.0j
    return fixed


def _pivot_index(column: np.ndarray) -> int | None:
    for index, value in enumerate(column):
        if abs(value) > 1e-12:
            return index
    return None


def _column_sort_key(column: np.ndarray) -> tuple[object, ...]:
    pivot = _pivot_index(column)
    if pivot is None:
        return (column.shape[0],)
    rounded_real = tuple(np.round(column.real, 12))
    rounded_imag = tuple(np.round(column.imag, 12))
    return (pivot, *rounded_real, *rounded_imag)


def _validate_target_l(spec, target_l: int) -> None:
    if not isinstance(target_l, int) or isinstance(target_l, bool):
        raise ValueError("target_l must be a Python integer")
    if target_l < 0:
        raise ValueError("target_l must be nonnegative")
    if target_l > spec.l_max:
        raise ValueError("target_l must satisfy 0 <= target_l <= particles * two_q / 2")
