"""Exact TN planar-network vertices for correlated fermion hopping.

The primary construction uses the two possible orders of adjacent elementary
Jacobi shears on three modes.  Symmetrizing those orders and their transposes
produces a Hermitian three-site vertex containing a Jordan--Wigner parity
string.  Every auxiliary-field matrix is totally nonnegative.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


@dataclass(frozen=True)
class TNParityStringDecomposition:
    """Four-field positive decomposition of one three-site vertex."""

    first_weight: float
    second_weight: float
    propagators: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]


@dataclass(frozen=True)
class TNNetworkConfigurationWeight:
    """Determinantal weight of an ordered TN network history."""

    determinant: float
    auxiliary_field_prefactor: float

    @property
    def total(self) -> float:
        return self.determinant * self.auxiliary_field_prefactor


def adjacent_jacobi_shear(
    *,
    sites: int,
    row: int,
    column: int,
    weight: float,
) -> np.ndarray:
    """Return ``I + weight E_(row,column)`` for adjacent ordered modes."""

    if sites < 2:
        raise ValueError("sites must be at least two")
    if not 0 <= row < sites or not 0 <= column < sites:
        raise ValueError("row and column must identify valid modes")
    if abs(row - column) != 1:
        raise ValueError("Jacobi shear modes must be adjacent")
    if weight < 0.0:
        raise ValueError("weight must be nonnegative")

    result = np.eye(sites)
    result[row, column] = weight
    return result


def tn_parity_string_decomposition(
    *,
    first_weight: float,
    second_weight: float,
) -> TNParityStringDecomposition:
    """Construct the four TN fields for the three-site parity-string vertex."""

    if first_weight <= 0.0 or second_weight <= 0.0:
        raise ValueError("first_weight and second_weight must be positive")

    first = adjacent_jacobi_shear(
        sites=3,
        row=0,
        column=1,
        weight=first_weight,
    )
    second = adjacent_jacobi_shear(
        sites=3,
        row=1,
        column=2,
        weight=second_weight,
    )
    forward_order = first @ second
    reverse_order = second @ first
    return TNParityStringDecomposition(
        first_weight=first_weight,
        second_weight=second_weight,
        propagators=(
            forward_order,
            reverse_order,
            forward_order.T,
            reverse_order.T,
        ),
    )


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


def hard_core_annihilation_operator(*, sites: int, mode: int) -> np.ndarray:
    """Return the same occupation flip without a Jordan--Wigner parity sign."""

    if sites < 1:
        raise ValueError("sites must be positive")
    if not 0 <= mode < sites:
        raise ValueError("mode must identify a valid site")

    dimension = 1 << sites
    result = np.zeros((dimension, dimension), dtype=float)
    for state in range(dimension):
        if state & (1 << mode):
            output = state ^ (1 << mode)
            result[output, state] = 1.0
    return result


def parity_string_vertex_from_gaussians(
    *,
    first_weight: float,
    second_weight: float,
) -> np.ndarray:
    """Return the unnormalized sum of the four Gaussian auxiliary fields."""

    decomposition = tn_parity_string_decomposition(
        first_weight=first_weight,
        second_weight=second_weight,
    )
    return sum(
        (
            number_conserving_gaussian_fock_matrix(propagator)
            for propagator in decomposition.propagators
        ),
        start=np.zeros((8, 8), dtype=float),
    )


def parity_string_vertex_operator(
    *,
    first_weight: float,
    second_weight: float,
) -> np.ndarray:
    """Return the analytic three-site operator equal to the Gaussian sum.

    The result is

    ``4 I + 2a h_01 + 2b h_12 + ab h_02^parity``,

    where ``h_02^parity =
    c0^dag (1-2n1) c2 + c2^dag (1-2n1) c0``.
    """

    if first_weight <= 0.0 or second_weight <= 0.0:
        raise ValueError("first_weight and second_weight must be positive")

    annihilators = [
        fermion_annihilation_operator(sites=3, mode=mode)
        for mode in range(3)
    ]
    creators = [operator.T for operator in annihilators]
    occupations = [
        creators[mode] @ annihilators[mode]
        for mode in range(3)
    ]
    identity = np.eye(8)
    nearest_left = (
        creators[0] @ annihilators[1]
        + creators[1] @ annihilators[0]
    )
    nearest_right = (
        creators[1] @ annihilators[2]
        + creators[2] @ annihilators[1]
    )
    middle_parity = identity - 2.0 * occupations[1]
    correlated_hopping = (
        creators[0] @ middle_parity @ annihilators[2]
        + creators[2] @ middle_parity @ annihilators[0]
    )
    return (
        4.0 * identity
        + 2.0 * first_weight * nearest_left
        + 2.0 * second_weight * nearest_right
        + first_weight * second_weight * correlated_hopping
    )


def hard_core_xy_vertex_operator(
    *,
    first_weight: float,
    second_weight: float,
) -> np.ndarray:
    """Return the Jordan--Wigner-equivalent hard-core-boson/XY vertex."""

    if first_weight <= 0.0 or second_weight <= 0.0:
        raise ValueError("first_weight and second_weight must be positive")

    annihilators = [
        hard_core_annihilation_operator(sites=3, mode=mode)
        for mode in range(3)
    ]
    creators = [operator.T for operator in annihilators]
    nearest_left = (
        creators[0] @ annihilators[1]
        + creators[1] @ annihilators[0]
    )
    nearest_right = (
        creators[1] @ annihilators[2]
        + creators[2] @ annihilators[1]
    )
    next_nearest = (
        creators[0] @ annihilators[2]
        + creators[2] @ annihilators[0]
    )
    return (
        4.0 * np.eye(8)
        + 2.0 * first_weight * nearest_left
        + 2.0 * second_weight * nearest_right
        + first_weight * second_weight * next_nearest
    )


def physical_parity_string_interaction(
    *,
    coupling: float,
    first_weight: float,
    second_weight: float,
) -> np.ndarray:
    """Return ``v = -(coupling/4) sum_s Gaussian(B_s)``."""

    if coupling <= 0.0:
        raise ValueError("coupling must be positive")
    return -(coupling / 4.0) * parity_string_vertex_operator(
        first_weight=first_weight,
        second_weight=second_weight,
    )


def embed_contiguous_propagator(
    local_propagator: np.ndarray,
    *,
    sites: int,
    left_site: int,
) -> np.ndarray:
    """Embed a local one-body propagator on a contiguous ordered interval."""

    local = np.asarray(local_propagator, dtype=float)
    if local.ndim != 2 or local.shape[0] != local.shape[1]:
        raise ValueError("local_propagator must be square")
    local_sites = local.shape[0]
    if local_sites < 1 or sites < local_sites:
        raise ValueError("sites must contain the local propagator")
    if not 0 <= left_site <= sites - local_sites:
        raise ValueError("left_site places the propagator outside the chain")

    result = np.eye(sites)
    result[
        left_site : left_site + local_sites,
        left_site : left_site + local_sites,
    ] = local
    return result


def tn_parity_string_configuration_weight(
    auxiliary_fields: Sequence[int],
    left_sites: Sequence[int],
    *,
    sites: int,
    coupling: float,
    first_weight: float,
    second_weight: float,
) -> TNNetworkConfigurationWeight:
    """Evaluate an ordered history of overlapping three-site TN vertices."""

    fields = tuple(int(field) for field in auxiliary_fields)
    positions = tuple(int(left_site) for left_site in left_sites)
    if len(fields) != len(positions):
        raise ValueError("auxiliary_fields and left_sites must have equal length")
    if not fields:
        raise ValueError("at least one vertex is required")
    if any(field not in range(4) for field in fields):
        raise ValueError("auxiliary fields must be integers from 0 through 3")
    if coupling <= 0.0:
        raise ValueError("coupling must be positive")

    decomposition = tn_parity_string_decomposition(
        first_weight=first_weight,
        second_weight=second_weight,
    )
    product_matrix = np.eye(sites)
    for field, left_site in zip(fields, positions, strict=True):
        product_matrix = product_matrix @ embed_contiguous_propagator(
            decomposition.propagators[field],
            sites=sites,
            left_site=left_site,
        )

    determinant = float(np.linalg.det(np.eye(sites) + product_matrix))
    prefactor = math.pow(coupling / 4.0, len(fields))
    return TNNetworkConfigurationWeight(
        determinant=determinant,
        auxiliary_field_prefactor=prefactor,
    )
