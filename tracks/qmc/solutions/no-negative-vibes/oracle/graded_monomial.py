"""A permutation-graded crossing extension of positive diagonal TN networks.

For a positive monomial matrix ``B = P D`` with ``D_ii >= 1``, the sign of
``det(I+B)`` is controlled by the permutation parity.  Attaching the scalar
grade ``sgn(P)`` therefore gives a nonnegative multiplicative-history weight.

The smallest physical generator is a dilated transposition.  Its Gaussian
Fock lift is a local Hermitian hopping-plus-attraction vertex.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
from typing import Sequence

import numpy as np

from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


@dataclass(frozen=True)
class MonomialCycle:
    """One permutation cycle and its factor in ``det(I+P D)``."""

    modes: tuple[int, ...]
    dilation_product: float
    determinant_factor: float


@dataclass(frozen=True)
class GradedMonomialCertificate:
    """Cycle-factor certificate for a positive monomial matrix."""

    permutation: tuple[int, ...]
    dilations: tuple[float, ...]
    permutation_grade: int
    cycles: tuple[MonomialCycle, ...]
    determinant: float
    graded_determinant: float


@dataclass(frozen=True)
class GradedMonomialHistoryWeight:
    """Weight of an ordered continuous-time transposition history."""

    determinant: float
    scalar_prefactor: float
    permutation_grade: int
    cycle_graded_determinant: float

    @property
    def total(self) -> float:
        return self.scalar_prefactor * self.determinant


@dataclass(frozen=True)
class GradedBondParameters:
    """Vertex parameters realizing a requested hopping and attraction."""

    coupling: float
    dilation: float
    hopping: float
    attraction: float


@dataclass(frozen=True)
class AncillaGradedHistoryWeight:
    """Positive weight after storing the crossing grade in one extra mode."""

    determinant: float
    auxiliary_field_prefactor: float
    physical_determinant: float
    ancilla_factor: float
    physical_permutation_grade: int

    @property
    def total(self) -> float:
        return self.auxiliary_field_prefactor * self.determinant


def positive_monomial_decomposition(
    matrix: np.ndarray,
    *,
    tolerance: float = 1e-12,
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """Return ``P D`` data for a positive monomial matrix.

    The returned permutation maps each column to the row containing its
    positive entry, and the returned dilation is that entry.
    """

    candidate = np.asarray(matrix, dtype=float)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise ValueError("matrix must be square")
    if candidate.shape[0] < 1:
        raise ValueError("matrix must be nonempty")
    if tolerance < 0.0:
        raise ValueError("tolerance must be nonnegative")

    permutation: list[int] = []
    dilations: list[float] = []
    for column in range(candidate.shape[1]):
        nonzero_rows = np.flatnonzero(np.abs(candidate[:, column]) > tolerance)
        if len(nonzero_rows) != 1:
            raise ValueError("matrix must have exactly one nonzero per column")
        row = int(nonzero_rows[0])
        value = float(candidate[row, column])
        if value <= 0.0:
            raise ValueError("monomial entries must be positive")
        permutation.append(row)
        dilations.append(value)

    if len(set(permutation)) != candidate.shape[0]:
        raise ValueError("matrix must have exactly one nonzero per row")
    return tuple(permutation), tuple(dilations)


def permutation_grade(permutation: Sequence[int]) -> int:
    """Return the sign of a permutation as ``+1`` or ``-1``."""

    values = tuple(int(value) for value in permutation)
    if sorted(values) != list(range(len(values))):
        raise ValueError("permutation must contain every index exactly once")
    inversions = sum(
        values[left] > values[right]
        for left in range(len(values))
        for right in range(left + 1, len(values))
    )
    return -1 if inversions % 2 else 1


def graded_monomial_certificate(
    matrix: np.ndarray,
    *,
    tolerance: float = 1e-12,
) -> GradedMonomialCertificate:
    """Certify ``sgn(P) det(I+P D) >= 0`` when every ``D_ii >= 1``."""

    permutation, dilations = positive_monomial_decomposition(
        matrix,
        tolerance=tolerance,
    )
    if min(dilations) < 1.0 - tolerance:
        raise ValueError("all monomial dilations must be at least one")

    visited: set[int] = set()
    cycles: list[MonomialCycle] = []
    determinant = 1.0
    for start in range(len(permutation)):
        if start in visited:
            continue
        modes: list[int] = []
        current = start
        while current not in visited:
            visited.add(current)
            modes.append(current)
            current = permutation[current]
        dilation_product = math.prod(dilations[mode] for mode in modes)
        factor = 1.0 + ((-1.0) ** (len(modes) - 1)) * dilation_product
        cycles.append(
            MonomialCycle(
                modes=tuple(modes),
                dilation_product=dilation_product,
                determinant_factor=factor,
            )
        )
        determinant *= factor

    grade = permutation_grade(permutation)
    graded_determinant = grade * determinant
    if graded_determinant < -tolerance:
        raise ArithmeticError("cycle factors violate the graded positivity bound")
    return GradedMonomialCertificate(
        permutation=permutation,
        dilations=dilations,
        permutation_grade=grade,
        cycles=tuple(cycles),
        determinant=determinant,
        graded_determinant=max(0.0, graded_determinant),
    )


def dilated_transposition_propagator(
    *,
    sites: int,
    first_mode: int,
    second_mode: int,
    dilation: float,
) -> np.ndarray:
    """Return identity with a symmetric ``dilation * SWAP`` mode block."""

    if sites < 2:
        raise ValueError("sites must be at least two")
    if not 0 <= first_mode < sites or not 0 <= second_mode < sites:
        raise ValueError("modes must identify valid sites")
    if first_mode == second_mode:
        raise ValueError("transposition modes must be distinct")
    if dilation <= 1.0:
        raise ValueError("dilation must be greater than one")

    result = np.eye(sites)
    result[first_mode, first_mode] = 0.0
    result[second_mode, second_mode] = 0.0
    result[first_mode, second_mode] = dilation
    result[second_mode, first_mode] = dilation
    return result


def ancilla_extended_transposition_propagator(
    *,
    sites: int,
    first_mode: int,
    second_mode: int,
    ancilla_mode: int,
    dilation: float,
) -> np.ndarray:
    """Store the transposition grade in a conserved ancillary mode.

    The physical mode block is ``dilation * SWAP`` and the ancilla entry is
    ``-dilation``.  The two negative eigenvalues have equal magnitude, so the
    complete real matrix has a real logarithm.
    """

    if not 0 <= ancilla_mode < sites:
        raise ValueError("ancilla_mode must identify a valid site")
    if ancilla_mode in (first_mode, second_mode):
        raise ValueError("ancilla_mode must differ from the physical modes")
    result = dilated_transposition_propagator(
        sites=sites,
        first_mode=first_mode,
        second_mode=second_mode,
        dilation=dilation,
    )
    result[ancilla_mode, ancilla_mode] = -dilation
    return result


def ancilla_extended_real_generator(
    *,
    sites: int,
    first_mode: int,
    second_mode: int,
    ancilla_mode: int,
    dilation: float,
) -> np.ndarray:
    """Return a real ``A`` with ``exp(A)`` equal to the extended field.

    In the symmetric endpoint mode the generator is ``log(dilation)``.  The
    antisymmetric endpoint mode and the ancilla span a real rotation by pi,
    plus the same logarithmic dilation.
    """

    ancilla_extended_transposition_propagator(
        sites=sites,
        first_mode=first_mode,
        second_mode=second_mode,
        ancilla_mode=ancilla_mode,
        dilation=dilation,
    )
    generator = np.zeros((sites, sites), dtype=float)
    logarithm = math.log(dilation)
    for mode in (first_mode, second_mode, ancilla_mode):
        generator[mode, mode] = logarithm

    rotation_entry = math.pi / math.sqrt(2.0)
    generator[ancilla_mode, first_mode] += rotation_entry
    generator[ancilla_mode, second_mode] -= rotation_entry
    generator[first_mode, ancilla_mode] -= rotation_entry
    generator[second_mode, ancilla_mode] += rotation_entry
    return generator


def fermion_annihilation_operator(*, sites: int, mode: int) -> np.ndarray:
    """Return a Jordan--Wigner annihilation matrix in bit-mask Fock order."""

    if sites < 1:
        raise ValueError("sites must be positive")
    if not 0 <= mode < sites:
        raise ValueError("mode must identify a valid site")

    dimension = 1 << sites
    result = np.zeros((dimension, dimension), dtype=float)
    lower_modes = (1 << mode) - 1
    for state in range(dimension):
        if state & (1 << mode):
            parity = (state & lower_modes).bit_count()
            output = state ^ (1 << mode)
            result[output, state] = -1.0 if parity % 2 else 1.0
    return result


def transposition_vertex_from_gaussian(
    *,
    sites: int,
    first_mode: int,
    second_mode: int,
    dilation: float,
) -> np.ndarray:
    """Return the exact Gaussian lift of one dilated mode transposition."""

    return number_conserving_gaussian_fock_matrix(
        dilated_transposition_propagator(
            sites=sites,
            first_mode=first_mode,
            second_mode=second_mode,
            dilation=dilation,
        )
    )


def transposition_vertex_operator(
    *,
    sites: int,
    first_mode: int,
    second_mode: int,
    dilation: float,
) -> np.ndarray:
    """Return the analytic local hopping-plus-attraction vertex.

    The operator is

    ``1-ni-nj+(1-r^2)ni*nj+r(ci^dag*cj+cj^dag*ci)``.
    """

    # Reuse the propagator validation so the analytic and Gaussian routes have
    # identical domains.
    dilated_transposition_propagator(
        sites=sites,
        first_mode=first_mode,
        second_mode=second_mode,
        dilation=dilation,
    )
    annihilators = [
        fermion_annihilation_operator(sites=sites, mode=mode)
        for mode in (first_mode, second_mode)
    ]
    creators = [operator.T for operator in annihilators]
    first_number = creators[0] @ annihilators[0]
    second_number = creators[1] @ annihilators[1]
    hopping = (
        creators[0] @ annihilators[1]
        + creators[1] @ annihilators[0]
    )
    identity = np.eye(1 << sites)
    return (
        identity
        - first_number
        - second_number
        + (1.0 - dilation * dilation) * first_number @ second_number
        + dilation * hopping
    )


def parameters_from_hopping_and_attraction(
    *,
    hopping: float,
    attraction: float,
) -> GradedBondParameters:
    """Realize arbitrary positive hopping and attractive density coupling."""

    if hopping <= 0.0:
        raise ValueError("hopping must be positive")
    if attraction <= 0.0:
        raise ValueError("attraction must be positive")
    ratio = attraction / hopping
    dilation = 0.5 * (ratio + math.sqrt(ratio * ratio + 4.0))
    coupling = hopping / dilation
    return GradedBondParameters(
        coupling=coupling,
        dilation=dilation,
        hopping=coupling * dilation,
        attraction=coupling * (dilation * dilation - 1.0),
    )


def graded_transposition_history_weight(
    edges: Sequence[tuple[int, int]],
    *,
    sites: int,
    dilations: Sequence[float],
    couplings: Sequence[float],
) -> GradedMonomialHistoryWeight:
    """Evaluate an ordered history of signed transposition vertices."""

    edge_sequence = tuple((int(left), int(right)) for left, right in edges)
    dilation_sequence = tuple(float(value) for value in dilations)
    coupling_sequence = tuple(float(value) for value in couplings)
    if not (
        len(edge_sequence)
        == len(dilation_sequence)
        == len(coupling_sequence)
    ):
        raise ValueError("edges, dilations, and couplings must have equal length")
    if sites < 2:
        raise ValueError("sites must be at least two")
    if any(coupling <= 0.0 for coupling in coupling_sequence):
        raise ValueError("couplings must be positive")

    product_matrix = np.eye(sites)
    scalar_prefactor = 1.0
    for (first_mode, second_mode), dilation, coupling in zip(
        edge_sequence,
        dilation_sequence,
        coupling_sequence,
        strict=True,
    ):
        product_matrix = dilated_transposition_propagator(
            sites=sites,
            first_mode=first_mode,
            second_mode=second_mode,
            dilation=dilation,
        ) @ product_matrix
        scalar_prefactor *= -coupling

    certificate = graded_monomial_certificate(product_matrix)
    determinant = float(np.linalg.det(np.eye(sites) + product_matrix))
    return GradedMonomialHistoryWeight(
        determinant=determinant,
        scalar_prefactor=scalar_prefactor,
        permutation_grade=certificate.permutation_grade,
        cycle_graded_determinant=certificate.graded_determinant,
    )


def ancilla_graded_history_weight(
    edges: Sequence[tuple[int, int]],
    *,
    sites: int,
    ancilla_mode: int,
    dilations: Sequence[float],
    couplings: Sequence[float],
) -> AncillaGradedHistoryWeight:
    """Evaluate a history with a positive scalar and a grade-storage mode."""

    edge_sequence = tuple((int(left), int(right)) for left, right in edges)
    dilation_sequence = tuple(float(value) for value in dilations)
    coupling_sequence = tuple(float(value) for value in couplings)
    if not (
        len(edge_sequence)
        == len(dilation_sequence)
        == len(coupling_sequence)
    ):
        raise ValueError("edges, dilations, and couplings must have equal length")
    if not 0 <= ancilla_mode < sites:
        raise ValueError("ancilla_mode must identify a valid site")
    if any(ancilla_mode in edge for edge in edge_sequence):
        raise ValueError("physical edges must not contain the ancilla mode")
    if any(coupling <= 0.0 for coupling in coupling_sequence):
        raise ValueError("couplings must be positive")

    extended_product = np.eye(sites)
    physical_modes = tuple(
        mode for mode in range(sites) if mode != ancilla_mode
    )
    physical_product = np.eye(len(physical_modes))
    physical_index = {
        mode: index for index, mode in enumerate(physical_modes)
    }
    auxiliary_field_prefactor = 1.0
    for (first_mode, second_mode), dilation, coupling in zip(
        edge_sequence,
        dilation_sequence,
        coupling_sequence,
        strict=True,
    ):
        extended_product = ancilla_extended_transposition_propagator(
            sites=sites,
            first_mode=first_mode,
            second_mode=second_mode,
            ancilla_mode=ancilla_mode,
            dilation=dilation,
        ) @ extended_product
        physical_product = dilated_transposition_propagator(
            sites=len(physical_modes),
            first_mode=physical_index[first_mode],
            second_mode=physical_index[second_mode],
            dilation=dilation,
        ) @ physical_product
        auxiliary_field_prefactor *= coupling

    physical_certificate = graded_monomial_certificate(physical_product)
    physical_determinant = float(
        np.linalg.det(np.eye(len(physical_modes)) + physical_product)
    )
    ancilla_product = ((-1.0) ** len(edge_sequence)) * math.prod(
        dilation_sequence
    )
    ancilla_factor = 1.0 + ancilla_product
    determinant = float(np.linalg.det(np.eye(sites) + extended_product))
    if determinant < -1e-10:
        raise ArithmeticError("ancilla grade failed to make the weight positive")
    return AncillaGradedHistoryWeight(
        determinant=max(0.0, determinant),
        auxiliary_field_prefactor=auxiliary_field_prefactor,
        physical_determinant=physical_determinant,
        ancilla_factor=ancilla_factor,
        physical_permutation_grade=(
            physical_certificate.permutation_grade
        ),
    )


def site_sign_stoquastic_gauges(
    *,
    sites: int,
    edges: Sequence[tuple[int, int]],
    hopping_amplitudes: Sequence[float] | None = None,
) -> tuple[tuple[int, ...], ...]:
    """Enumerate site ``+/-`` gauges making all hopping entries nonpositive."""

    edge_sequence = tuple((int(left), int(right)) for left, right in edges)
    if sites < 1:
        raise ValueError("sites must be positive")
    if hopping_amplitudes is None:
        amplitudes = (1.0,) * len(edge_sequence)
    else:
        amplitudes = tuple(float(value) for value in hopping_amplitudes)
    if len(edge_sequence) != len(amplitudes):
        raise ValueError("edges and hopping_amplitudes must have equal length")
    for first_mode, second_mode in edge_sequence:
        if not 0 <= first_mode < sites or not 0 <= second_mode < sites:
            raise ValueError("edges must identify valid sites")
        if first_mode == second_mode:
            raise ValueError("self edges are not allowed")
    if any(amplitude == 0.0 for amplitude in amplitudes):
        raise ValueError("hopping amplitudes must be nonzero")

    gauges: list[tuple[int, ...]] = []
    # Fix the first site to +1 because a global sign leaves every edge
    # unchanged.
    for tail in product((-1, 1), repeat=max(0, sites - 1)):
        gauge = (1, *tail)
        if all(
            gauge[left] * amplitude * gauge[right] < 0.0
            for (left, right), amplitude in zip(
                edge_sequence,
                amplitudes,
                strict=True,
            )
        ):
            gauges.append(gauge)
    return tuple(gauges)
