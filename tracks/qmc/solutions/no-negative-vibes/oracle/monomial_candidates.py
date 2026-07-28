"""Odd-order monomial semigroups and their minimal even-order boundary.

The factors in this module are finite single-particle propagators ``B``, not
generators ``A``.  This is intentional: a generalized permutation factor has
the exact multiplication law

```
P_g diag(d) P_h diag(e) = P_(gh) diag(d' * e),
```

so odd-order permutation groups give a directly testable multiplicative
semigroup.  Every generated factor is either a real exponential itself or is
accompanied by an explicit product-of-real-exponentials witness.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import expm, logm


@dataclass(frozen=True)
class MonomialCase:
    family: str
    shape: tuple[int, int]
    group: str
    block_size: int = 1
    prior_status: str = "candidate"


@dataclass(frozen=True)
class RealLogAudit:
    """Audit whether one finite real factor has a single real logarithm.

    Weighted permutation matrices are diagonalizable.  Hence Culver's
    negative-eigenvalue condition reduces here to requiring every distinct
    negative real eigenvalue to occur with even multiplicity.
    """

    exists: bool
    reason: str
    structure_residual: float
    min_abs_eigenvalue: float
    negative_real_eigenvalues: tuple[float, ...]


_CASES = {
    "odd_monomial_c3": MonomialCase(
        "odd_scalar_monomial",
        (3, 3),
        "c3",
        prior_status="analytic_nonnegative_candidate",
    ),
    "odd_monomial_c5": MonomialCase(
        "odd_scalar_monomial",
        (5, 5),
        "c5",
        prior_status="analytic_nonnegative_candidate",
    ),
    "even_monomial_v4": MonomialCase(
        "even_scalar_monomial",
        (4, 4),
        "v4_regular",
        prior_status="analytic_boundary_control",
    ),
    "odd_block_tn_c3": MonomialCase(
        "odd_tn_block_monomial",
        (6, 6),
        "c3",
        block_size=2,
        prior_status="analytic_nonnegative_candidate",
    ),
}


def available_cases() -> dict[str, MonomialCase]:
    return dict(_CASES)


def _validate_scale(scale: float) -> None:
    if not math.isfinite(scale) or scale < 0.0:
        raise ValueError("scale must be finite and nonnegative")


def _permutation_matrix(permutation: tuple[int, ...]) -> np.ndarray:
    size = len(permutation)
    matrix = np.zeros((size, size))
    matrix[np.asarray(permutation), np.arange(size)] = 1.0
    return matrix


def _cyclic_permutations(size: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple((column + shift) % size for column in range(size))
        for shift in range(size)
    )


def _v4_regular_permutations() -> tuple[tuple[int, ...], ...]:
    # Label the regular V4 action by the two-bit integers 0,1,2,3.
    return tuple(
        tuple(column ^ group_element for column in range(4))
        for group_element in range(4)
    )


def _case_permutations(case: str) -> tuple[tuple[int, ...], ...]:
    spec = _CASES[case]
    if spec.group == "c3":
        return _cyclic_permutations(3)
    if spec.group == "c5":
        return _cyclic_permutations(5)
    if spec.group == "v4_regular":
        return _v4_regular_permutations()
    raise AssertionError(f"unsupported monomial group: {spec.group}")


def _random_positive_diagonal(
    size: int,
    rng: np.random.Generator,
    *,
    scale: float,
) -> np.ndarray:
    return np.exp(scale * rng.standard_normal(size))


def _random_tn2(
    rng: np.random.Generator,
    *,
    scale: float,
) -> np.ndarray:
    """Sample an invertible 2-by-2 TN matrix by bidiagonal factorization."""

    lower_parameter = scale * abs(float(rng.standard_normal()))
    upper_parameter = scale * abs(float(rng.standard_normal()))
    diagonal = _random_positive_diagonal(2, rng, scale=scale)
    lower = np.array([[1.0, 0.0], [lower_parameter, 1.0]])
    upper = np.array([[1.0, upper_parameter], [0.0, 1.0]])
    return lower @ np.diag(diagonal) @ upper


def _block_permutation_matrix(
    permutation: tuple[int, ...],
    *,
    block_size: int,
) -> np.ndarray:
    return np.kron(_permutation_matrix(permutation), np.eye(block_size))


def _block_diagonal(blocks: list[np.ndarray]) -> np.ndarray:
    block_size = blocks[0].shape[0]
    result = np.zeros(
        (len(blocks) * block_size, len(blocks) * block_size)
    )
    for index, block in enumerate(blocks):
        start = index * block_size
        result[start : start + block_size, start : start + block_size] = block
    return result


def random_factor(
    case: str,
    rng: np.random.Generator,
    *,
    scale: float,
) -> np.ndarray:
    """Sample one finite propagator in a declared monomial family.

    For the even V4 boundary, each returned *atomic* factor still has a real
    logarithm: it is either a positive diagonal or an unweighted even
    permutation.  Products of these atoms generate weighted V4 monomials and
    can acquire negative determinant weights.
    """

    if case not in _CASES:
        raise ValueError(f"unknown monomial case: {case}")
    _validate_scale(scale)
    spec = _CASES[case]
    permutations = _case_permutations(case)

    if spec.family == "odd_scalar_monomial":
        permutation = permutations[int(rng.integers(len(permutations)))]
        weights = _random_positive_diagonal(
            spec.shape[0],
            rng,
            scale=scale,
        )
        return _permutation_matrix(permutation) @ np.diag(weights)

    if spec.family == "even_scalar_monomial":
        if rng.random() < 0.5:
            weights = _random_positive_diagonal(
                spec.shape[0],
                rng,
                scale=scale,
            )
            return np.diag(weights)
        # Every nonidentity regular V4 permutation is a product of two
        # transpositions.  Its -1 eigenspace is therefore even-dimensional,
        # so it has a real skew-symmetric logarithm.
        permutation = permutations[int(rng.integers(1, len(permutations)))]
        return _permutation_matrix(permutation)

    if spec.family == "odd_tn_block_monomial":
        permutation = permutations[int(rng.integers(len(permutations)))]
        blocks = [
            _random_tn2(rng, scale=scale)
            for _ in range(spec.shape[0] // spec.block_size)
        ]
        return _block_permutation_matrix(
            permutation,
            block_size=spec.block_size,
        ) @ _block_diagonal(blocks)

    raise AssertionError(f"unsupported monomial family: {spec.family}")


def _scalar_grade_decomposition(
    case: str,
    matrix: np.ndarray,
) -> tuple[tuple[int, ...], np.ndarray, float]:
    real_matrix = np.asarray(matrix).real
    scale = max(1.0, float(np.linalg.norm(matrix)))
    imaginary_residual = float(np.linalg.norm(np.asarray(matrix).imag)) / scale
    best: tuple[tuple[int, ...], np.ndarray, float] | None = None

    for permutation in _case_permutations(case):
        rows = np.asarray(permutation)
        columns = np.arange(len(permutation))
        allowed = np.zeros(real_matrix.shape, dtype=bool)
        allowed[rows, columns] = True
        weights = real_matrix[rows, columns]
        residual = max(
            imaginary_residual,
            float(np.linalg.norm(real_matrix[~allowed])) / scale,
            max(0.0, -float(np.min(weights))) / scale,
        )
        if best is None or residual < best[2]:
            best = (permutation, weights, residual)

    assert best is not None
    return best


def _block_grade_decomposition(
    case: str,
    matrix: np.ndarray,
) -> tuple[tuple[int, ...], list[np.ndarray], float]:
    spec = _CASES[case]
    block_size = spec.block_size
    real_matrix = np.asarray(matrix).real
    matrix_scale = max(1.0, float(np.linalg.norm(matrix)))
    imaginary_residual = (
        float(np.linalg.norm(np.asarray(matrix).imag)) / matrix_scale
    )
    best: tuple[tuple[int, ...], list[np.ndarray], float] | None = None

    for permutation in _case_permutations(case):
        allowed = np.zeros(real_matrix.shape, dtype=bool)
        blocks: list[np.ndarray] = []
        residuals = [imaginary_residual]
        for column_block, row_block in enumerate(permutation):
            row_start = row_block * block_size
            column_start = column_block * block_size
            row_slice = slice(row_start, row_start + block_size)
            column_slice = slice(column_start, column_start + block_size)
            allowed[row_slice, column_slice] = True
            block = real_matrix[row_slice, column_slice]
            blocks.append(block)
            residuals.append(
                max(0.0, -float(np.min(block))) / matrix_scale
            )
            residuals.append(
                max(0.0, -float(np.linalg.det(block)))
                / (matrix_scale * matrix_scale)
            )
        residuals.append(float(np.linalg.norm(real_matrix[~allowed])) / matrix_scale)
        residual = max(residuals)
        if best is None or residual < best[2]:
            best = (permutation, blocks, residual)

    assert best is not None
    return best


def factor_structure_residual(case: str, factor: np.ndarray) -> float:
    """Return a scale-normalized residual for the union of allowed grades."""

    if case not in _CASES:
        raise ValueError(f"unknown monomial case: {case}")
    matrix = np.asarray(factor)
    if matrix.shape != _CASES[case].shape:
        raise ValueError(
            f"{case} requires shape {_CASES[case].shape}, got {matrix.shape}"
        )
    if _CASES[case].block_size == 1:
        return _scalar_grade_decomposition(case, matrix)[2]
    return _block_grade_decomposition(case, matrix)[2]


def _cycles(permutation: tuple[int, ...]) -> list[tuple[int, ...]]:
    seen: set[int] = set()
    result: list[tuple[int, ...]] = []
    for start in range(len(permutation)):
        if start in seen:
            continue
        cycle: list[int] = []
        current = start
        while current not in seen:
            seen.add(current)
            cycle.append(current)
            current = permutation[current]
        result.append(tuple(cycle))
    return result


def _clustered_negative_roots(
    permutation: tuple[int, ...],
    weights: np.ndarray,
    *,
    rtol: float,
) -> list[list[float]]:
    negative_roots: list[float] = []
    for cycle in _cycles(permutation):
        if len(cycle) % 2 == 0:
            cycle_product = float(np.prod(weights[list(cycle)]))
            negative_roots.append(
                -(cycle_product ** (1.0 / len(cycle)))
            )

    clusters: list[list[float]] = []
    for root in sorted(negative_roots):
        for cluster in clusters:
            if math.isclose(root, cluster[0], rel_tol=rtol, abs_tol=rtol):
                cluster.append(root)
                break
        else:
            clusters.append([root])
    return clusters


def real_log_audit(
    case: str,
    factor: np.ndarray,
    *,
    tolerance: float = 1e-10,
) -> RealLogAudit:
    """Audit single-real-log existence using the family structure."""

    if case not in _CASES:
        raise ValueError(f"unknown monomial case: {case}")
    matrix = np.asarray(factor)
    residual = factor_structure_residual(case, matrix)
    eigenvalues = np.linalg.eigvals(matrix)
    min_abs_eigenvalue = float(np.min(np.abs(eigenvalues)))
    if residual > tolerance:
        return RealLogAudit(
            False,
            "factor is outside the declared monomial family",
            residual,
            min_abs_eigenvalue,
            (),
        )
    if min_abs_eigenvalue <= tolerance:
        return RealLogAudit(
            False,
            "a singular real matrix has no matrix logarithm",
            residual,
            min_abs_eigenvalue,
            (),
        )

    spec = _CASES[case]
    if spec.family == "odd_scalar_monomial":
        return RealLogAudit(
            True,
            "odd weighted cycles have no negative real eigenvalues",
            residual,
            min_abs_eigenvalue,
            (),
        )
    if spec.family == "odd_tn_block_monomial":
        return RealLogAudit(
            True,
            "odd block cycles over invertible TN blocks have no negative real eigenvalues",
            residual,
            min_abs_eigenvalue,
            (),
        )

    permutation, weights, _ = _scalar_grade_decomposition(case, matrix)
    clusters = _clustered_negative_roots(
        permutation,
        weights,
        rtol=100.0 * tolerance,
    )
    negative_values = tuple(cluster[0] for cluster in clusters)
    even_multiplicity = all(len(cluster) % 2 == 0 for cluster in clusters)
    return RealLogAudit(
        even_multiplicity,
        (
            "every negative eigenvalue has even Jordan-block multiplicity"
            if even_multiplicity
            else "a negative eigenvalue has odd Jordan-block multiplicity"
        ),
        residual,
        min_abs_eigenvalue,
        negative_values,
    )


def _real_log_of_even_permutation(permutation_matrix: np.ndarray) -> np.ndarray:
    """Construct a real logarithm for the even permutations used here."""

    principal = logm(permutation_matrix)
    imaginary_scale = float(np.linalg.norm(principal.imag))
    if imaginary_scale <= 1e-9 * max(1.0, float(np.linalg.norm(principal))):
        return principal.real

    # The only branch requiring a non-principal logarithm in the declared
    # cases is a regular V4 involution: its -1 eigenspace has dimension two.
    if not (
        np.allclose(permutation_matrix, permutation_matrix.T, atol=1e-12)
        and np.allclose(
            permutation_matrix @ permutation_matrix,
            np.eye(permutation_matrix.shape[0]),
            atol=1e-12,
        )
    ):
        raise RuntimeError("no implemented real logarithm for this permutation")
    eigenvalues, eigenvectors = np.linalg.eigh(permutation_matrix)
    negative_basis = eigenvectors[:, eigenvalues < -0.5]
    if negative_basis.shape[1] % 2:
        raise RuntimeError("permutation has odd-dimensional -1 eigenspace")
    logarithm = np.zeros_like(permutation_matrix)
    for index in range(0, negative_basis.shape[1], 2):
        first = negative_basis[:, index]
        second = negative_basis[:, index + 1]
        logarithm += math.pi * (
            np.outer(first, second) - np.outer(second, first)
        )
    return logarithm


def real_exponential_witnesses(
    case: str,
    factor: np.ndarray,
    *,
    tolerance: float = 1e-9,
) -> tuple[np.ndarray, ...]:
    """Return real generators whose ordered exponentials reproduce ``factor``.

    A factor may lack a *single* real logarithm (the V4 boundary product is
    the important example) while still being a product of two real
    exponentials.  This routine exposes that distinction explicitly.
    """

    if factor_structure_residual(case, factor) > tolerance:
        raise ValueError("factor is outside the declared monomial family")
    spec = _CASES[case]
    matrix = np.asarray(factor, dtype=float)

    if spec.block_size == 1:
        permutation, weights, _ = _scalar_grade_decomposition(case, matrix)
        if np.min(weights) <= 0.0:
            raise ValueError("active monomial weights must be strictly positive")
        permutation_matrix = _permutation_matrix(permutation)
        block_diagonal = np.diag(weights)
    else:
        permutation, blocks, _ = _block_grade_decomposition(case, matrix)
        if any(
            np.linalg.det(block) <= 0.0
            or np.min(block) < 0.0
            for block in blocks
        ):
            raise ValueError("active TN blocks must be invertible and nonnegative")
        permutation_matrix = _block_permutation_matrix(
            permutation,
            block_size=spec.block_size,
        )
        block_diagonal = _block_diagonal(blocks)

    permutation_logarithm = _real_log_of_even_permutation(
        permutation_matrix
    )
    diagonal_logarithm = logm(block_diagonal)
    if np.linalg.norm(diagonal_logarithm.imag) > tolerance * max(
        1.0,
        float(np.linalg.norm(diagonal_logarithm)),
    ):
        raise RuntimeError("positive/TN diagonal block did not yield a real logarithm")
    witnesses = (permutation_logarithm, diagonal_logarithm.real)
    reconstruction = expm(witnesses[0]) @ expm(witnesses[1])
    if not np.allclose(reconstruction, matrix, rtol=2e-8, atol=2e-9):
        raise RuntimeError("real exponential witness reconstruction failed")
    return witnesses


def even_v4_boundary_factors(q: float) -> tuple[np.ndarray, np.ndarray]:
    """Return two real-exponential atoms with an exactly negative product.

    The nonidentity V4 permutation has cycles ``(0 1)(2 3)``.  After the
    diagonal factor, their cycle products are respectively ``q**2`` and
    ``q**-2``, so the determinant weight is

    ``(1 - q**2) * (1 - q**-2) < 0`` for ``q != 1``.
    """

    if not math.isfinite(q) or q <= 0.0 or math.isclose(q, 1.0):
        raise ValueError("q must be finite, positive, and different from one")
    permutation = _permutation_matrix(_v4_regular_permutations()[1])
    diagonal = np.diag([q, q, 1.0 / q, 1.0 / q])
    return permutation, diagonal
