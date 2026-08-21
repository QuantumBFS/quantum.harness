"""Charge-resolved cubic N=2 SYK cochain complexes and BPS frames."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from math import comb

import numpy as np
import scipy.sparse as sp


@dataclass(frozen=True)
class BPSFrame:
    """Spectral Hodge frame for one fixed fermion-number sector."""

    N: int
    charge: int
    basis: tuple[int, ...]
    projector_frame: np.ndarray
    complement_frame: np.ndarray
    positive_energies: np.ndarray
    gap: float
    kernel_residual: float
    orthogonality_error: float
    expected_rank: int
    q_in: sp.csr_matrix
    q_out: sp.csr_matrix
    hamiltonian: sp.csr_matrix


@lru_cache(maxsize=None)
def charge_basis(N: int, charge: int) -> tuple[int, ...]:
    """Return sorted occupation bit strings in a fixed charge sector."""

    modes = int(N)
    particles = int(charge)
    if modes < 1:
        raise ValueError("N must be positive")
    if particles < 0 or particles > modes:
        return ()
    return tuple(
        state
        for state in range(1 << modes)
        if state.bit_count() == particles
    )


@lru_cache(maxsize=None)
def cubic_triples(N: int) -> tuple[tuple[int, int, int], ...]:
    """Return the lexicographically ordered cubic coupling coordinates."""

    modes = int(N)
    if modes < 3:
        raise ValueError("a cubic supercharge requires N >= 3")
    return tuple(combinations(range(modes), 3))


def normalized_complex_couplings(N: int, seed: int) -> np.ndarray:
    """Draw a deterministic unit-norm isotropic complex three-form."""

    rng = np.random.default_rng(int(seed))
    values = rng.normal(size=comb(int(N), 3)) + 1j * rng.normal(
        size=comb(int(N), 3)
    )
    norm = float(np.linalg.norm(values))
    if norm <= 0.0:
        raise RuntimeError("complex coupling draw has zero norm")
    return np.asarray(values / norm, dtype=complex)


def _create(state: int, mode: int) -> tuple[int, int] | None:
    """Apply one fermion creation operator in the occupation basis."""

    bit = 1 << int(mode)
    if int(state) & bit:
        return None
    parity = (int(state) & (bit - 1)).bit_count() % 2
    return int(state) | bit, (-1 if parity else 1)


def _apply_cubic_creation(
    state: int,
    triple: tuple[int, int, int],
) -> tuple[int, int] | None:
    """Apply psi_i psi_j psi_k, respecting right-to-left operator order."""

    current = int(state)
    sign = 1
    for mode in reversed(triple):
        result = _create(current, mode)
        if result is None:
            return None
        current, factor = result
        sign *= factor
    return current, sign


def cubic_supercharge(
    N: int,
    charge: int,
    couplings: np.ndarray,
) -> sp.csr_matrix:
    """Return Q_r: H_r -> H_{r+3} for a cubic complex supercharge."""

    modes = int(N)
    source_charge = int(charge)
    triples = cubic_triples(modes)
    coefficients = np.asarray(couplings, dtype=complex)
    if coefficients.shape != (len(triples),):
        raise ValueError("cubic coupling vector has the wrong shape")
    source = charge_basis(modes, source_charge)
    target = charge_basis(modes, source_charge + 3)
    target_lookup = {state: index for index, state in enumerate(target)}
    rows: list[int] = []
    columns: list[int] = []
    data: list[complex] = []
    for column, state in enumerate(source):
        for coordinate, triple in enumerate(triples):
            applied = _apply_cubic_creation(state, triple)
            if applied is None:
                continue
            target_state, sign = applied
            row = target_lookup.get(target_state)
            if row is None:
                raise RuntimeError("cubic creation left the target charge sector")
            amplitude = coefficients[coordinate] * sign
            if amplitude != 0.0:
                rows.append(row)
                columns.append(column)
                data.append(amplitude)
    return sp.coo_matrix(
        (np.asarray(data, dtype=complex), (rows, columns)),
        shape=(len(target), len(source)),
        dtype=complex,
    ).tocsr()


def charge_hamiltonian(
    N: int,
    charge: int,
    couplings: np.ndarray,
) -> sp.csr_matrix:
    """Return H_r = Q Q^dagger + Q^dagger Q in one charge sector."""

    q_in = cubic_supercharge(N, int(charge) - 3, couplings)
    q_out = cubic_supercharge(N, int(charge), couplings)
    return (q_in @ q_in.getH() + q_out.getH() @ q_out).tocsr()


def expected_generic_bps_rank(N: int, charge: int) -> int:
    """Return the registered generic BPS rank for even-N central sectors."""

    modes = int(N)
    particles = int(charge)
    if modes % 2:
        raise ValueError("the registered rank contract requires even N")
    middle = modes // 2
    if particles == middle:
        return 2 * 3 ** (middle - 1)
    if abs(particles - middle) == 1:
        return 3 ** (middle - 1)
    return 0


def decomposable_couplings(N: int, alpha: float = 1.0) -> np.ndarray:
    """Return C_3 = alpha e_1 wedge e_2 wedge e_3."""

    scale = float(alpha)
    if scale <= 0.0:
        raise ValueError("decomposable coupling scale must be positive")
    triples = cubic_triples(int(N))
    values = np.zeros(len(triples), dtype=complex)
    values[triples.index((0, 1, 2))] = scale
    return values


def decomposable_tangent(N: int, family: str, site: int) -> np.ndarray:
    """Return one canonical tangent preserving the decomposable three-form locus."""

    pairs = {"12": (0, 1), "13": (0, 2), "23": (1, 2)}
    label = str(family)
    if label not in pairs:
        raise ValueError("decomposable tangent family must be 12, 13, or 23")
    external = int(site)
    if external < 3 or external >= int(N):
        raise ValueError("decomposable tangent site must lie outside modes 1,2,3")
    triple = tuple(sorted((*pairs[label], external)))
    triples = cubic_triples(int(N))
    values = np.zeros(len(triples), dtype=complex)
    values[triples.index(triple)] = 1.0
    return values


def _safe_combination(n: int, k: int) -> int:
    return 0 if int(k) < 0 or int(k) > int(n) else comb(int(n), int(k))


def decomposable_bps_rank(N: int, charge: int) -> int:
    """Return 3 binom(N-2, r-1) for the decomposable model."""

    return 3 * _safe_combination(int(N) - 2, int(charge) - 1)


def analytic_decomposable_curvature_multiplicities(
    N: int,
    charge: int,
    kind: str,
) -> dict[str, int]:
    """Return Appendix-D multiplicities for diagonal/off-diagonal tangents."""

    modes = int(N)
    particles = int(charge)
    label = str(kind)
    if label == "diagonal":
        positive = _safe_combination(modes - 4, particles - 3)
        negative = _safe_combination(modes - 4, particles - 1)
    elif label == "off_diagonal":
        positive = _safe_combination(modes - 4, particles - 2)
        negative = positive
    else:
        raise ValueError("curvature kind must be diagonal or off_diagonal")
    rank = decomposable_bps_rank(modes, particles)
    zero = rank - positive - negative
    if zero < 0:
        raise RuntimeError("analytic curvature multiplicities exceed BPS rank")
    return {"negative": negative, "zero": zero, "positive": positive}


def solve_bps_frame(
    N: int,
    charge: int,
    couplings: np.ndarray,
    *,
    dense_cutoff: int = 4096,
    relative_tolerance: float = 1e-10,
    expected_rank_override: int | None = None,
) -> BPSFrame:
    """Diagonalize one registered sector and certify its harmonic fiber."""

    basis = charge_basis(int(N), int(charge))
    if not basis:
        raise ValueError("registered charge sector is empty")
    if len(basis) > int(dense_cutoff):
        raise ValueError("charge sector exceeds the current dense cutoff")
    expected = (
        expected_generic_bps_rank(N, charge)
        if expected_rank_override is None
        else int(expected_rank_override)
    )
    if expected <= 0 or expected >= len(basis):
        raise ValueError("charge sector is outside the registered BPS sequence")
    q_in = cubic_supercharge(N, int(charge) - 3, couplings)
    q_out = cubic_supercharge(N, int(charge), couplings)
    hamiltonian = (q_in @ q_in.getH() + q_out.getH() @ q_out).tocsr()
    dense = hamiltonian.toarray()
    dense = 0.5 * (dense + dense.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(dense)
    scale = max(1.0, float(np.max(np.abs(eigenvalues))))
    tolerance = float(relative_tolerance) * scale
    if float(np.max(np.abs(eigenvalues[:expected]))) > tolerance:
        raise RuntimeError("generic BPS eigenvalues exceed the registered tolerance")
    if float(eigenvalues[expected]) <= tolerance:
        raise RuntimeError("generic BPS nullity exceeds the registered rank")
    projector_frame = np.asarray(eigenvectors[:, :expected], dtype=complex)
    complement_frame = np.asarray(eigenvectors[:, expected:], dtype=complex)
    positive_energies = np.asarray(eigenvalues[expected:], dtype=float)
    kernel_residual = float(
        np.linalg.norm(hamiltonian @ projector_frame, ord="fro")
    )
    orthogonality_error = max(
        float(
            np.linalg.norm(
                projector_frame.conj().T @ projector_frame
                - np.eye(expected),
                ord="fro",
            )
        ),
        float(
            np.linalg.norm(
                complement_frame.conj().T @ complement_frame
                - np.eye(complement_frame.shape[1]),
                ord="fro",
            )
        ),
        float(
            np.linalg.norm(
                projector_frame.conj().T @ complement_frame,
                ord="fro",
            )
        ),
    )
    return BPSFrame(
        N=int(N),
        charge=int(charge),
        basis=basis,
        projector_frame=projector_frame,
        complement_frame=complement_frame,
        positive_energies=positive_energies,
        gap=float(positive_energies[0]),
        kernel_residual=kernel_residual,
        orthogonality_error=orthogonality_error,
        expected_rank=expected,
        q_in=q_in,
        q_out=q_out,
        hamiltonian=hamiltonian,
    )
