"""Exact asymmetric TN Gaussian decomposition of a repulsive ``t-V`` bond.

The local Fock basis is ``|0>, |1>, |2>, |12>``.  For a number-conserving
one-body propagator ``B``, its second-quantized action in that basis is
``Gamma(B) = diag(1, B, det(B))``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math

import numpy as np


@dataclass(frozen=True)
class TNRepulsiveBondDecomposition:
    """Two-field positive Gaussian representation of one physical bond gate."""

    target_one_particle: np.ndarray
    propagator_plus: np.ndarray
    propagator_minus: np.ndarray
    target_double_occupation: float


@dataclass(frozen=True)
class TNBondConfigurationWeight:
    """Determinantal weight of an ordered sequence of sampled bond gates."""

    determinant: float
    auxiliary_field_prefactor: float

    @property
    def total(self) -> float:
        return self.auxiliary_field_prefactor * self.determinant


def asymmetric_tn_bond_decomposition(
    *,
    time_step: float,
    hopping: float,
    interaction: float,
    chemical_potential: float = 0.0,
    asymmetry: float = 0.5,
) -> TNRepulsiveBondDecomposition:
    """Decompose an exact repulsive spinless-fermion bond gate.

    The physical local Hamiltonian is

    ``h = -t(c1^dag c2 + c2^dag c1) + V n1 n2 - mu(n1+n2)``.

    For ``V >= 0`` and ``0 <= asymmetry < 1``, this returns two invertible
    totally nonnegative 2-by-2 matrices ``B_plus`` and ``B_minus`` satisfying

    ``exp(-dt h) = (Gamma(B_plus) + Gamma(B_minus)) / 2``.

    Positive asymmetry makes the two auxiliary propagators non-symmetric and
    prevents them from sharing one positive diagonal symmetrizing gauge.
    """

    if time_step <= 0.0:
        raise ValueError("time_step must be positive")
    if hopping < 0.0:
        raise ValueError("hopping must be nonnegative in the chosen fixed gauge")
    if interaction < 0.0:
        raise ValueError("interaction must be nonnegative")
    if not 0.0 <= asymmetry < 1.0:
        raise ValueError("asymmetry must satisfy 0 <= asymmetry < 1")

    scale = math.exp(time_step * chemical_potential)
    argument = time_step * hopping
    diagonal = scale * math.cosh(argument)
    off_diagonal = scale * math.sinh(argument)
    determinant = scale * scale
    target_double = determinant * math.exp(-time_step * interaction)

    skew = asymmetry * off_diagonal
    splitting = math.sqrt(
        skew * skew
        + determinant * (1.0 - math.exp(-time_step * interaction))
    )

    target_one_particle = np.asarray(
        [
            [diagonal, off_diagonal],
            [off_diagonal, diagonal],
        ],
        dtype=float,
    )
    propagator_plus = np.asarray(
        [
            [diagonal + splitting, off_diagonal + skew],
            [off_diagonal - skew, diagonal - splitting],
        ],
        dtype=float,
    )
    propagator_minus = np.asarray(
        [
            [diagonal - splitting, off_diagonal - skew],
            [off_diagonal + skew, diagonal + splitting],
        ],
        dtype=float,
    )
    return TNRepulsiveBondDecomposition(
        target_one_particle=target_one_particle,
        propagator_plus=propagator_plus,
        propagator_minus=propagator_minus,
        target_double_occupation=target_double,
    )


def gaussian_fock_matrix(one_particle_propagator: np.ndarray) -> np.ndarray:
    """Return ``Gamma(B)`` in the basis ``|0>, |1>, |2>, |12>``."""

    matrix = np.asarray(one_particle_propagator, dtype=float)
    if matrix.shape != (2, 2):
        raise ValueError("one_particle_propagator must have shape (2, 2)")
    return number_conserving_gaussian_fock_matrix(matrix)


def number_conserving_gaussian_fock_matrix(
    one_particle_propagator: np.ndarray,
) -> np.ndarray:
    """Build ``Gamma(B)`` from all minors of an arbitrary small matrix.

    Fock states are indexed by bit masks.  Within each fixed-particle-number
    sector, ``Gamma(B)[R,C]`` is the minor ``det(B[R,C])``.
    """

    matrix = np.asarray(one_particle_propagator, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("one_particle_propagator must be square")
    sites = matrix.shape[0]
    if sites < 1:
        raise ValueError("one_particle_propagator must be nonempty")

    dimension = 1 << sites
    result = np.zeros((dimension, dimension), dtype=float)
    result[0, 0] = 1.0
    subsets_by_size = {
        particles: list(combinations(range(sites), particles))
        for particles in range(1, sites + 1)
    }
    for subsets in subsets_by_size.values():
        for row_subset in subsets:
            row_mask = sum(1 << index for index in row_subset)
            for column_subset in subsets:
                column_mask = sum(1 << index for index in column_subset)
                minor = matrix[np.ix_(row_subset, column_subset)]
                result[row_mask, column_mask] = float(np.linalg.det(minor))
    return result


def physical_bond_gate(
    *,
    time_step: float,
    hopping: float,
    interaction: float,
    chemical_potential: float = 0.0,
) -> np.ndarray:
    """Return the exact local ``exp(-dt h)`` in the four-state Fock basis."""

    decomposition = asymmetric_tn_bond_decomposition(
        time_step=time_step,
        hopping=hopping,
        interaction=interaction,
        chemical_potential=chemical_potential,
        asymmetry=0.0,
    )
    result = np.zeros((4, 4), dtype=float)
    result[0, 0] = 1.0
    result[1:3, 1:3] = decomposition.target_one_particle
    result[3, 3] = decomposition.target_double_occupation
    return result


def embed_adjacent_bond(
    bond_propagator: np.ndarray,
    *,
    sites: int,
    left_site: int,
) -> np.ndarray:
    """Embed a two-site one-body matrix on adjacent sites of an open path."""

    matrix = np.asarray(bond_propagator, dtype=float)
    if matrix.shape != (2, 2):
        raise ValueError("bond_propagator must have shape (2, 2)")
    if sites < 2:
        raise ValueError("sites must be at least two")
    if not 0 <= left_site < sites - 1:
        raise ValueError("left_site must identify an adjacent bond")

    embedded = np.eye(sites)
    embedded[left_site : left_site + 2, left_site : left_site + 2] = matrix
    return embedded


def tn_bond_configuration_weight(
    auxiliary_fields: np.ndarray,
    bond_sequence: np.ndarray,
    *,
    sites: int,
    time_step: float,
    hopping: float,
    interaction: float,
    chemical_potential: float = 0.0,
    asymmetry: float = 0.5,
) -> TNBondConfigurationWeight:
    """Evaluate an ordered checkerboard/Trotter sequence of local bond fields."""

    fields = np.asarray(auxiliary_fields)
    bonds = np.asarray(bond_sequence)
    if fields.ndim != 1 or bonds.ndim != 1 or fields.size != bonds.size:
        raise ValueError("auxiliary_fields and bond_sequence must be equal 1D arrays")
    if fields.size < 1:
        raise ValueError("at least one bond gate is required")
    if not np.all(np.isin(fields, (-1, 1))):
        raise ValueError("auxiliary_fields must contain only +/-1")
    if not np.issubdtype(bonds.dtype, np.integer):
        raise ValueError("bond_sequence must contain integer left-site indices")

    decomposition = asymmetric_tn_bond_decomposition(
        time_step=time_step,
        hopping=hopping,
        interaction=interaction,
        chemical_potential=chemical_potential,
        asymmetry=asymmetry,
    )
    product_matrix = np.eye(sites)
    for field, left_site in zip(fields, bonds, strict=True):
        local = (
            decomposition.propagator_plus
            if field == 1
            else decomposition.propagator_minus
        )
        product_matrix = product_matrix @ embed_adjacent_bond(
            local,
            sites=sites,
            left_site=int(left_site),
        )

    determinant = float(np.linalg.det(np.eye(sites) + product_matrix))
    return TNBondConfigurationWeight(
        determinant=determinant,
        auxiliary_field_prefactor=0.5 ** fields.size,
    )
