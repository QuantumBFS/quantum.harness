r"""Helicity-resolved rank-two pair operators on the Haldane sphere.

Liou--Haldane--Yang--Rezayi define the planar guiding-centre metric probes

    O_\mp = sum_q (q_x \mp i q_y)^2 V_q exp(-q^2 l_B^2/2) rho_q rho_-q

in ``tmp/pdfs/1904.12231_source/graviton.tex``, Eqs. (4) and the discussion
at lines 218--225.  For the fermionic Laughlin parent channel they identify

    O_+ : |m=1,M> -> |m=3,M>       (dark),
    O_- : |m=3,M> -> |m=1,M>       (bright).

On a sphere, a pair in the monopole shell ``l=Q`` has total angular momentum
``J=2Q-m``.  The rotationally covariant continuation is consequently a
rank-two spherical tensor between ``J=2Q-1`` and ``J=2Q-3``.  The ``q=+2``
component maps the parent ``m=1`` channel to ``m=3``; its adjoint is the
``q=-2`` bright component.  The coefficient multiplying the dark-channel
Clebsch--Gordan matrix element is set to one and fixes its adjoint's scale.
Thus absolute spectral weights are convention-dependent, but their vanishing
and bright/dark ratio are meaningful within this common convention.

This module deliberately implements the Laughlin parent-channel probe, not
the full metric derivative of an arbitrary finite-size Coulomb Hamiltonian.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import numpy as np
from scipy import sparse
from sympy.physics.wigner import wigner_3j

from .angular_momentum import angular_momentum_lowering
from .basis import FockBasis, apply_two_body
from .interactions import clebsch_gordan_equal_shell


Helicity = Literal["bright_minus", "dark_plus"]


@lru_cache(maxsize=None)
def _integer_clebsch_gordan(
    j1: int, m1: int, j2: int, m2: int, total_j: int, total_m: int
) -> float:
    """Return ``<j1,m1;j2,m2|J,M>`` in Condon--Shortley convention."""

    if m1 + m2 != total_m:
        return 0.0
    if abs(m1) > j1 or abs(m2) > j2 or abs(total_m) > total_j:
        return 0.0
    phase = -1.0 if (j1 - j2 + total_m) % 2 else 1.0
    return float(
        phase
        * np.sqrt(2 * total_j + 1)
        * wigner_3j(j1, j2, total_j, m1, m2, -total_m)
    )


@dataclass(frozen=True)
class PairTransition:
    """A non-Hermitian two-body transition in the ordered fermion-pair basis."""

    two_q: int
    source_relative_m: int
    target_relative_m: int
    component: int
    pairs: tuple[tuple[int, int], ...]
    matrix: np.ndarray


@dataclass(frozen=True)
class ChiralMetricOperator:
    """One helicity component between two fixed-``Lz`` many-body sectors."""

    helicity: Helicity
    component: int
    source: FockBasis
    target: FockBasis
    matrix: sparse.csr_matrix


@dataclass(frozen=True)
class ChiralWeights:
    """Unnormalised integrated spectral weights ``<0|O^dagger O|0>``."""

    bright_minus: float
    dark_plus: float

    @property
    def bright_to_dark(self) -> float:
        if self.dark_plus == 0.0:
            return float("inf") if self.bright_minus > 0.0 else 0.0
        return self.bright_minus / self.dark_plus


@dataclass(frozen=True)
class ChiralGravitonResponse:
    """Integrated and lowest-spin-2 spectral weights in both helicities."""

    integrated: ChiralWeights
    bright_graviton_weight: float
    dark_graviton_weight: float
    bright_graviton_fraction: float
    dark_graviton_fraction: float

    @property
    def graviton_bright_to_dark(self) -> float:
        if self.dark_graviton_weight == 0.0:
            return float("inf") if self.bright_graviton_weight > 0.0 else 0.0
        return self.bright_graviton_weight / self.dark_graviton_weight


def _pair_list(two_q: int) -> tuple[tuple[int, int], ...]:
    return tuple((a, b) for a in range(two_q + 1) for b in range(a + 1, two_q + 1))


def rank_two_pair_transition(
    two_q: int,
    source_relative_m: int,
    target_relative_m: int,
    component: int,
) -> PairTransition:
    """Construct a Clebsch--Gordan-normalized rank-two pair tensor.

    Matrix elements use the Wigner--Eckart convention

    ``<J_t M_t|T^(2)_q|J_s M_s> = <J_s M_s;2q|J_t M_t>``.

    Both relative angular momenta must be odd for spin-polarised fermions and
    differ by two.  The returned matrix acts on normalized ordered-pair Slater
    states; the factor two is the product of their ``sqrt(2)`` CG amplitudes.
    """

    if two_q < 3:
        raise ValueError("CG001: chiral m=1<->3 probe requires 2Q>=3")
    if source_relative_m < 0 or target_relative_m < 0:
        raise ValueError("CG001: relative angular momenta must be non-negative")
    if source_relative_m % 2 != 1 or target_relative_m % 2 != 1:
        raise ValueError("CG001: spin-polarized fermion pair channels must be odd")
    if abs(source_relative_m - target_relative_m) != 2:
        raise ValueError("CG001: rank-two parent probe must connect m and m+2")
    if abs(component) > 2:
        raise ValueError("CG001: rank-two component must satisfy |q|<=2")

    source_j = two_q - source_relative_m
    target_j = two_q - target_relative_m
    if source_j < 0 or target_j < 0:
        raise ValueError("CG001: requested relative channel is absent at this flux")

    two_m = tuple(range(-two_q, two_q + 1, 2))
    pairs = _pair_list(two_q)
    matrix = np.zeros((len(pairs), len(pairs)), dtype=np.float64)

    for column, (c, d) in enumerate(pairs):
        source_m = (two_m[c] + two_m[d]) // 2
        source_cg = clebsch_gordan_equal_shell(
            two_q, two_m[c], two_m[d], source_j, source_m
        )
        if abs(source_cg) <= 1e-15:
            continue
        target_m = source_m + component
        tensor_cg = _integer_clebsch_gordan(
            source_j, source_m, 2, component, target_j, target_m
        )
        if abs(tensor_cg) <= 1e-15:
            continue
        for row, (a, b) in enumerate(pairs):
            if two_m[a] + two_m[b] != 2 * target_m:
                continue
            target_cg = clebsch_gordan_equal_shell(
                two_q, two_m[a], two_m[b], target_j, target_m
            )
            matrix[row, column] += 2.0 * target_cg * tensor_cg * source_cg

    return PairTransition(
        two_q=two_q,
        source_relative_m=source_relative_m,
        target_relative_m=target_relative_m,
        component=component,
        pairs=pairs,
        matrix=matrix,
    )


@lru_cache(maxsize=None)
def laughlin_chiral_pair_transitions(two_q: int) -> tuple[PairTransition, PairTransition]:
    """Return ``(bright O_-, dark O_+)`` for the fermionic Laughlin channel.

    ``O_+`` is built as the ``q=+2`` transition ``m=1 -> 3``.  ``O_-`` is
    defined as its exact adjoint, giving ``q=-2`` and ``m=3 -> 1`` with the
    same reduced normalization.
    """

    dark = rank_two_pair_transition(two_q, 1, 3, component=+2)
    bright = PairTransition(
        two_q=two_q,
        source_relative_m=3,
        target_relative_m=1,
        component=-2,
        pairs=dark.pairs,
        matrix=dark.matrix.T.copy(),
    )
    return bright, dark


def build_pair_transition_operator(
    source: FockBasis, target: FockBasis, transition: PairTransition
) -> sparse.csr_matrix:
    """Lift a pair transition to a sparse many-fermion operator."""

    if source.system != target.system:
        raise ValueError("source and target must describe the same sphere")
    if source.system.two_q != transition.two_q:
        raise ValueError("pair transition and basis use different monopole flux")
    if target.two_lz != source.two_lz + 2 * transition.component:
        raise ValueError("target two_lz does not match the tensor component")

    rows: list[int] = []
    columns: list[int] = []
    data: list[float] = []
    target_index = target.index
    pair_lookup = {pair: index for index, pair in enumerate(transition.pairs)}

    for column, state in enumerate(source.states):
        occupied = source.occupied(state)
        occupied_pairs = ((c, d) for i, c in enumerate(occupied) for d in occupied[i + 1 :])
        for c, d in occupied_pairs:
            source_pair = pair_lookup[(c, d)]
            couplings = transition.matrix[:, source_pair]
            for target_pair in np.flatnonzero(np.abs(couplings) > 1e-14):
                a, b = transition.pairs[int(target_pair)]
                applied = apply_two_body(state, a, b, c, d)
                if applied is None:
                    continue
                new_state, sign = applied
                row = target_index.get(new_state)
                if row is None:
                    continue
                rows.append(row)
                columns.append(column)
                data.append(float(sign * couplings[target_pair]))

    matrix = sparse.coo_matrix(
        (data, (rows, columns)),
        shape=(target.dimension, source.dimension),
        dtype=np.float64,
    ).tocsr()
    matrix.sum_duplicates()
    return matrix


def chiral_metric_operator(source: FockBasis, helicity: Helicity) -> ChiralMetricOperator:
    """Build the bright ``O_-`` or dark ``O_+`` parent-channel component."""

    bright, dark = laughlin_chiral_pair_transitions(source.system.two_q)
    if helicity == "bright_minus":
        transition = bright
    elif helicity == "dark_plus":
        transition = dark
    else:
        raise ValueError(f"unknown helicity: {helicity}")
    target = FockBasis(
        source.system, source.two_lz + 2 * transition.component
    )
    matrix = build_pair_transition_operator(source, target, transition)
    return ChiralMetricOperator(
        helicity=helicity,
        component=transition.component,
        source=source,
        target=target,
        matrix=matrix,
    )


def chiral_weights(basis: FockBasis, state: np.ndarray) -> ChiralWeights:
    """Return the integrated bright/dark weights of a normalized state."""

    vector = np.asarray(state)
    if vector.shape != (basis.dimension,):
        raise ValueError("state has incompatible shape")
    norm = float(np.real(np.vdot(vector, vector)))
    if norm <= 0.0:
        raise ValueError("state must have nonzero norm")
    vector = vector / np.sqrt(norm)
    bright = chiral_metric_operator(basis, "bright_minus").matrix @ vector
    dark = chiral_metric_operator(basis, "dark_plus").matrix @ vector
    bright_weight = float(np.real(np.vdot(bright, bright)))
    dark_weight = float(np.real(np.vdot(dark, dark)))
    return ChiralWeights(bright_minus=bright_weight, dark_plus=dark_weight)


def chiral_graviton_response(
    ground_basis: FockBasis,
    ground_vector: np.ndarray,
    graviton_highest_basis: FockBasis,
    graviton_highest_vector: np.ndarray,
) -> ChiralGravitonResponse:
    """Resolve integrated weight and the lowest ``L=2`` pole in each helicity.

    The supplied graviton is the ``M=+2`` highest-weight member. Exact lowering
    constructs its ``M=-2`` partner before evaluating the bright ``q=-2``
    matrix element. This avoids identifying helicity from an ``M`` label alone.
    """

    if ground_basis.system != graviton_highest_basis.system:
        raise ValueError("ground and graviton must describe the same sphere")
    if ground_basis.two_lz != 0 or graviton_highest_basis.two_lz != 4:
        raise ValueError("response requires L=0,M=0 and L=2,M=2 inputs")
    ground = np.asarray(ground_vector, dtype=np.complex128)
    highest = np.asarray(graviton_highest_vector, dtype=np.complex128)
    ground /= np.linalg.norm(ground)
    highest /= np.linalg.norm(highest)

    basis = graviton_highest_basis
    lowest = highest
    for m_value in range(2, -2, -1):
        target = FockBasis(basis.system, basis.two_lz - 2)
        lowest = angular_momentum_lowering(basis, target) @ lowest
        lowest /= np.sqrt((2 + m_value) * (2 - m_value + 1))
        basis = target

    bright_operator = chiral_metric_operator(ground_basis, "bright_minus")
    dark_operator = chiral_metric_operator(ground_basis, "dark_plus")
    if bright_operator.target != basis or dark_operator.target != graviton_highest_basis:
        raise ValueError("chiral operator target does not match the L=2 multiplet")
    bright_state = bright_operator.matrix @ ground
    dark_state = dark_operator.matrix @ ground
    integrated = ChiralWeights(
        bright_minus=float(np.real(np.vdot(bright_state, bright_state))),
        dark_plus=float(np.real(np.vdot(dark_state, dark_state))),
    )
    bright_pole = float(abs(np.vdot(lowest, bright_state)) ** 2)
    dark_pole = float(abs(np.vdot(highest, dark_state)) ** 2)
    bright_fraction = (
        bright_pole / integrated.bright_minus if integrated.bright_minus > 0.0 else 0.0
    )
    dark_fraction = dark_pole / integrated.dark_plus if integrated.dark_plus > 0.0 else 0.0
    return ChiralGravitonResponse(
        integrated=integrated,
        bright_graviton_weight=bright_pole,
        dark_graviton_weight=dark_pole,
        bright_graviton_fraction=bright_fraction,
        dark_graviton_fraction=dark_fraction,
    )
