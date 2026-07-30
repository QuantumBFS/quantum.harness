"""Independent first-quantized Coulomb oracle for very small spheres.

This module deliberately does not use the production basis, interaction,
Hamiltonian, angular-momentum, or ED implementations.  It provides a second
physics kernel for the ``N=3,4`` acceptance cases:

* chord-Coulomb pseudopotentials are integrated directly in first
  quantization with Gauss-Legendre nodes in ``cos(theta_1/2)`` and a midpoint
  rule for the relative azimuth;
* two-particle projectors are generated from polynomial highest-weight
  coefficients and the elementary one-particle lowering rule; and
* a separate bit-determinant implementation assembles and diagonalizes the
  many-electron Hamiltonian.

The numerical integral is intended as a small-system oracle, not as the
production path for larger calculations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import combinations
from math import comb, pi, sqrt

import numpy as np
from scipy import linalg


@dataclass(frozen=True)
class IndependentOracleResult:
    """Symmetry-resolved result from the independent small-system oracle."""

    n_electrons: int
    two_q: int
    e_l0: float
    e_l2: float
    gap: float
    pseudopotentials: dict[int, float]
    x_order: int
    phi_points: int
    dimension_lz0: int
    dimension_lz2: int
    residual_l0: float
    residual_l2: float
    pair_completeness_error: float
    hermiticity_error: float
    quadrature: str = "Gauss-Legendre x1,x2; midpoint relative phi"
    energy_unit: str = "e^2/(epsilon*l_B)"
    method: str = "independent_first_quantized_chord_coulomb_oracle"

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready representation of the oracle result."""

        return asdict(self)


def _validate_quadrature(two_q: int, x_order: int, phi_points: int) -> None:
    if two_q <= 0:
        raise ValueError("independent Coulomb oracle requires two_q > 0")
    if x_order < 8:
        raise ValueError("x_order must be at least 8")
    if phi_points < 16:
        raise ValueError("phi_points must be at least 16")


def highest_weight_coefficients(two_q: int, relative_m: int) -> np.ndarray:
    r"""Return the normalized pair highest-weight coefficients.

    The coefficient multiplying the product whose two particles have been
    lowered ``k`` and ``relative_m-k`` times is

    .. math::

       c_k \propto (-1)^k {r \choose k}/
       \sqrt{{S \choose k}{S \choose r-k}},

    with ``S=two_q`` and ``r=relative_m``.  This follows by expanding
    ``(u1*v2-v1*u2)^r`` and therefore requires neither Clebsch-Gordan nor
    Wigner-symbol code.
    """

    if relative_m < 0 or relative_m > two_q:
        raise ValueError("relative_m must lie in [0, two_q]")
    coefficients = np.asarray(
        [
            (-1.0) ** k
            * comb(relative_m, k)
            / sqrt(comb(two_q, k) * comb(two_q, relative_m - k))
            for k in range(relative_m + 1)
        ],
        dtype=np.float64,
    )
    return coefficients / np.linalg.norm(coefficients)


@lru_cache(maxsize=None)
def _fermionic_coulomb_pseudopotentials_cached(
    two_q: int, x_order: int, phi_points: int
) -> tuple[tuple[int, float], ...]:
    """Numerically integrate all odd (fermionic) pair channels."""

    _validate_quadrature(two_q, x_order, phi_points)
    x, x_weights = np.polynomial.legendre.leggauss(x_order)
    phi = (np.arange(phi_points, dtype=np.float64) + 0.5) * (2.0 * pi / phi_points)

    x1 = x[:, None, None]
    x2 = x[None, :, None]
    relative_phi = phi[None, None, :]
    u1 = np.sqrt((1.0 + x1) / 2.0)
    v1 = np.sqrt((1.0 - x1) / 2.0)
    u2 = np.sqrt((1.0 + x2) / 2.0) * np.exp(0.5j * relative_phi)
    v2 = np.sqrt((1.0 - x2) / 2.0) * np.exp(-0.5j * relative_phi)

    cosine_gamma = (
        x1 * x2
        + np.sqrt(1.0 - x1 * x1)
        * np.sqrt(1.0 - x2 * x2)
        * np.cos(relative_phi)
    )
    radius_over_lb = sqrt(two_q / 2.0)
    chord_coulomb = 1.0 / (
        radius_over_lb * np.sqrt(np.maximum(2.0 - 2.0 * cosine_gamma, 1e-300))
    )
    integration_weights = (
        2.0
        * pi
        * x_weights[:, None, None]
        * x_weights[None, :, None]
        * (2.0 * pi / phi_points)
    )
    orbital_prefactor_product = (two_q + 1.0) / (4.0 * pi)

    values: list[tuple[int, float]] = []
    for relative_m in range(1, two_q + 1, 2):
        coefficients = highest_weight_coefficients(two_q, relative_m)
        wavefunction = np.zeros(
            (x_order, x_order, phi_points), dtype=np.complex128
        )
        for k, coefficient in enumerate(coefficients):
            first_normalization = sqrt(comb(two_q, k))
            second_lowerings = relative_m - k
            second_normalization = sqrt(comb(two_q, second_lowerings))
            wavefunction += (
                coefficient
                * orbital_prefactor_product
                * first_normalization
                * second_normalization
                * u1 ** (two_q - k)
                * v1**k
                * u2 ** (two_q - second_lowerings)
                * v2**second_lowerings
            )
        probability = np.abs(wavefunction) ** 2
        norm = float(np.sum(integration_weights * probability))
        if abs(norm - 1.0) > 5e-11:
            raise RuntimeError(
                f"pair wavefunction quadrature normalization failed for r={relative_m}: "
                f"{norm:.12g}"
            )
        value = float(np.sum(integration_weights * probability * chord_coulomb))
        if not np.isfinite(value):
            raise RuntimeError(f"non-finite pseudopotential for r={relative_m}")
        values.append((relative_m, value))
    return tuple(values)


def fermionic_coulomb_pseudopotentials(
    two_q: int, *, x_order: int = 64, phi_points: int = 256
) -> dict[int, float]:
    """Return independently integrated odd-channel Coulomb pseudopotentials.

    Even pair channels do not occur for spin-polarized fermions and are
    intentionally omitted.  Omitting ``r=0`` also avoids making the slow
    quadrature convergence at the Coulomb coincidence singularity look like a
    controlled number when it cannot affect the fermionic Hamiltonian.
    """

    return dict(
        _fermionic_coulomb_pseudopotentials_cached(two_q, x_order, phi_points)
    )


def _ordered_pairs(two_q: int) -> tuple[tuple[int, int], ...]:
    return tuple(combinations(range(two_q + 1), 2))


def _parity_below(state: int, orbital: int) -> int:
    return -1 if (state & ((1 << orbital) - 1)).bit_count() % 2 else 1


def _apply_one_body(
    state: int, create: int, annihilate: int
) -> tuple[int, int] | None:
    if not state & (1 << annihilate):
        return None
    sign = _parity_below(state, annihilate)
    intermediate = state ^ (1 << annihilate)
    if intermediate & (1 << create):
        return None
    sign *= _parity_below(intermediate, create)
    return intermediate | (1 << create), sign


def _apply_two_body(
    state: int, create_a: int, create_b: int, annihilate_c: int, annihilate_d: int
) -> tuple[int, int] | None:
    current = state
    sign = 1
    for create, orbital in (
        (False, annihilate_c),
        (False, annihilate_d),
        (True, create_b),
        (True, create_a),
    ):
        if create:
            if current & (1 << orbital):
                return None
            sign *= _parity_below(current, orbital)
            current |= 1 << orbital
        else:
            if not current & (1 << orbital):
                return None
            sign *= _parity_below(current, orbital)
            current ^= 1 << orbital
    return current, sign


@lru_cache(maxsize=None)
def _pair_projectors(
    two_q: int,
) -> tuple[tuple[tuple[int, np.ndarray], ...], float]:
    """Generate odd-channel projectors using only highest weights and L-."""

    pairs = _ordered_pairs(two_q)
    pair_index = {pair: index for index, pair in enumerate(pairs)}
    dimension = len(pairs)
    projectors: list[tuple[int, np.ndarray]] = []

    for relative_m in range(1, two_q + 1, 2):
        product = np.zeros((two_q + 1, two_q + 1), dtype=np.float64)
        coefficients = highest_weight_coefficients(two_q, relative_m)
        for k, coefficient in enumerate(coefficients):
            first = two_q - k
            second = two_q - (relative_m - k)
            product[first, second] += coefficient
        vector = np.asarray(
            [
                (product[first, second] - product[second, first]) / sqrt(2.0)
                for first, second in pairs
            ],
            dtype=np.float64,
        )
        vector /= np.linalg.norm(vector)

        pair_l = two_q - relative_m
        projector = np.outer(vector, vector)
        pair_m = pair_l
        for _ in range(2 * pair_l):
            lowered = np.zeros(dimension, dtype=np.float64)
            for source, (first, second) in enumerate(pairs):
                state = (1 << first) | (1 << second)
                for orbital in (first, second):
                    if orbital == 0:
                        continue
                    applied = _apply_one_body(state, orbital - 1, orbital)
                    if applied is None:
                        continue
                    new_state, sign = applied
                    occupied = tuple(
                        index for index in range(two_q + 1) if new_state & (1 << index)
                    )
                    coefficient = sqrt(orbital * (two_q - orbital + 1))
                    lowered[pair_index[occupied]] += sign * coefficient * vector[source]
            ladder_norm = sqrt((pair_l + pair_m) * (pair_l - pair_m + 1))
            vector = lowered / ladder_norm
            projector += np.outer(vector, vector)
            pair_m -= 1
        projectors.append((relative_m, projector))

    completeness = sum((item[1] for item in projectors), np.zeros((dimension, dimension)))
    completeness_error = float(np.linalg.norm(completeness - np.eye(dimension)))
    if completeness_error > 1e-10:
        raise RuntimeError(
            f"independent pair-projector completeness error {completeness_error:.3e}"
        )
    return tuple(projectors), completeness_error


def _fock_states(two_q: int, n_electrons: int, two_lz: int) -> tuple[int, ...]:
    two_m_values = tuple(range(-two_q, two_q + 1, 2))
    output: list[int] = []
    for occupied in combinations(range(two_q + 1), n_electrons):
        if sum(two_m_values[index] for index in occupied) != two_lz:
            continue
        output.append(sum(1 << index for index in occupied))
    return tuple(output)


def _many_body_raising(
    two_q: int, n_electrons: int, two_lz: int
) -> np.ndarray:
    source = _fock_states(two_q, n_electrons, two_lz)
    target = _fock_states(two_q, n_electrons, two_lz + 2)
    target_index = {state: index for index, state in enumerate(target)}
    matrix = np.zeros((len(target), len(source)), dtype=np.float64)
    for column, state in enumerate(source):
        for orbital in range(two_q):
            applied = _apply_one_body(state, orbital + 1, orbital)
            if applied is None:
                continue
            new_state, sign = applied
            coefficient = sqrt((two_q - orbital) * (orbital + 1))
            matrix[target_index[new_state], column] += sign * coefficient
    return matrix


def _many_body_hamiltonian(
    two_q: int,
    n_electrons: int,
    two_lz: int,
    pair_matrix: np.ndarray,
) -> tuple[tuple[int, ...], np.ndarray]:
    states = _fock_states(two_q, n_electrons, two_lz)
    state_index = {state: index for index, state in enumerate(states)}
    pairs = _ordered_pairs(two_q)
    pair_index = {pair: index for index, pair in enumerate(pairs)}
    hamiltonian = np.zeros((len(states), len(states)), dtype=np.float64)
    for column, state in enumerate(states):
        occupied = tuple(index for index in range(two_q + 1) if state & (1 << index))
        for annihilate_c, annihilate_d in combinations(occupied, 2):
            source_pair = pair_index[(annihilate_c, annihilate_d)]
            for target_pair, (create_a, create_b) in enumerate(pairs):
                interaction = pair_matrix[target_pair, source_pair]
                if abs(interaction) < 1e-14:
                    continue
                applied = _apply_two_body(
                    state,
                    create_a,
                    create_b,
                    annihilate_c,
                    annihilate_d,
                )
                if applied is None:
                    continue
                new_state, sign = applied
                row = state_index.get(new_state)
                if row is not None:
                    hamiltonian[row, column] += sign * interaction
    return states, 0.5 * (hamiltonian + hamiltonian.T)


def _lowest_fixed_l(
    two_q: int,
    n_electrons: int,
    total_l: int,
    pair_matrix: np.ndarray,
) -> tuple[float, int, float]:
    two_lz = 2 * total_l
    states, hamiltonian = _many_body_hamiltonian(
        two_q, n_electrons, two_lz, pair_matrix
    )
    raising = _many_body_raising(two_q, n_electrons, two_lz)
    highest_weights = linalg.null_space(raising, rcond=1e-12)
    if highest_weights.shape[1] == 0:
        raise RuntimeError(f"empty independent L={total_l} highest-weight sector")
    projected = highest_weights.T @ hamiltonian @ highest_weights
    values, vectors = linalg.eigh(projected, subset_by_index=(0, 0))
    vector = highest_weights @ vectors[:, 0]
    energy = float(values[0])
    residual = float(np.linalg.norm(hamiltonian @ vector - energy * vector))
    return energy, len(states), residual


def oracle_neutral_gap(
    n_electrons: int, *, x_order: int = 64, phi_points: int = 256
) -> IndependentOracleResult:
    """Compute the ``L=2`` neutral gap with an independent small-N kernel.

    The implementation is deliberately bounded to ``2 <= N <= 4``.  It is an
    acceptance oracle for the production implementation, not another scaling
    route.
    """

    if n_electrons < 2 or n_electrons > 4:
        raise ValueError("independent oracle is intentionally limited to 2 <= N <= 4")
    two_q = 3 * (n_electrons - 1)
    pseudopotentials = fermionic_coulomb_pseudopotentials(
        two_q, x_order=x_order, phi_points=phi_points
    )
    projectors, completeness_error = _pair_projectors(two_q)
    pair_matrix = sum(
        (
            pseudopotentials[relative_m] * projector
            for relative_m, projector in projectors
        ),
        np.zeros_like(projectors[0][1]),
    )
    hermiticity_error = float(np.linalg.norm(pair_matrix - pair_matrix.T))
    if hermiticity_error > 1e-12:
        raise RuntimeError(
            f"independent pair Hamiltonian Hermiticity error {hermiticity_error:.3e}"
        )

    e_l0, dimension_lz0, residual_l0 = _lowest_fixed_l(
        two_q, n_electrons, 0, pair_matrix
    )
    e_l2, dimension_lz2, residual_l2 = _lowest_fixed_l(
        two_q, n_electrons, 2, pair_matrix
    )
    return IndependentOracleResult(
        n_electrons=n_electrons,
        two_q=two_q,
        e_l0=e_l0,
        e_l2=e_l2,
        gap=e_l2 - e_l0,
        pseudopotentials=pseudopotentials,
        x_order=x_order,
        phi_points=phi_points,
        dimension_lz0=dimension_lz0,
        dimension_lz2=dimension_lz2,
        residual_l0=residual_l0,
        residual_l2=residual_l2,
        pair_completeness_error=completeness_error,
        hermiticity_error=hermiticity_error,
    )
