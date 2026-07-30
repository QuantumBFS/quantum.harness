"""Rank-two many-body response operators on fixed angular-momentum sectors."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from types import MappingProxyType
from typing import Literal, Mapping

import numpy as np
from scipy import sparse

from challenge15.angular import _ladder_matrix
from challenge15.chiral_source import (
    Helicity,
    lhyr_pair_reduced_source,
    pair_source_tensor,
)
from challenge15.fermions import DeterminantBasis
from challenge15.spec import SphereSpec
from challenge15.two_body import assemble_two_body


@dataclass(frozen=True, slots=True)
class ResponseFamily:
    spec: SphereSpec
    orientation: Literal[-1, 1]
    helicity: Helicity
    components: Mapping[int, sparse.csr_matrix]

    def __post_init__(self) -> None:
        if (
            isinstance(self.orientation, bool)
            or not isinstance(self.orientation, int)
            or self.orientation not in (-1, 1)
        ):
            raise ValueError("orientation must be -1 or 1")
        if self.helicity not in ("+", "-"):
            raise ValueError("helicity must be '+' or '-'")
        if (
            any(type(component_m) is not int for component_m in self.components)
            or set(self.components) != set(range(-2, 3))
        ):
            raise ValueError("components must contain exactly M=-2,-1,0,1,2")

        domain = DeterminantBasis.with_two_m(self.spec, 0)
        sealed = {}
        for component_m in range(-2, 3):
            matrix = self.components[component_m]
            codomain = DeterminantBasis.with_two_m(
                self.spec, 2 * component_m
            )
            if not sparse.isspmatrix_csr(matrix):
                raise ValueError("response components must be CSR matrices")
            if matrix.shape != (codomain.dimension, domain.dimension):
                raise ValueError("response component has the wrong sector shape")
            sealed[component_m] = matrix
        object.__setattr__(self, "components", MappingProxyType(sealed))


def build_response_family(
    spec: SphereSpec,
    helicity: Helicity,
    *,
    orientation: Literal[-1, 1] = 1,
) -> ResponseFamily:
    """Build all five rectangular many-body components of a rank-two source."""

    source = lhyr_pair_reduced_source(
        spec,
        helicity,
        orientation=orientation,
    )
    domain = DeterminantBasis.with_two_m(spec, 0)
    components = {}
    for component_m in range(-2, 3):
        codomain = DeterminantBasis.with_two_m(spec, 2 * component_m)
        tensor = pair_source_tensor(source, component_m)
        components[component_m] = assemble_two_body(
            domain,
            codomain,
            tensor,
        )
    return ResponseFamily(
        spec=spec,
        orientation=orientation,
        helicity=helicity,
        components=components,
    )


def tensor_commutator_residuals(
    family: ResponseFamily,
) -> Mapping[str, float]:
    """Return fixed-sector rank-two SU(2) commutator residuals."""

    spec = family.spec
    domain = DeterminantBasis.with_two_m(spec, 0)
    source = lhyr_pair_reduced_source(
        spec,
        family.helicity,
        orientation=family.orientation,
    )
    residuals: dict[str, float] = {}
    lz_domain = sparse.csr_matrix((domain.dimension, domain.dimension))

    for component_m, operator in family.components.items():
        codomain = DeterminantBasis.with_two_m(spec, 2 * component_m)
        lz_codomain = component_m * sparse.identity(
            codomain.dimension,
            format="csr",
        )
        expected_lz = component_m * operator
        actual_lz = lz_codomain @ operator - operator @ lz_domain
        residuals[f"lz[{component_m}]"] = _relative_frobenius_residual(
            actual_lz,
            expected_lz,
        )

        raised_domain = DeterminantBasis.with_two_m(spec, 2)
        raised_codomain = DeterminantBasis.with_two_m(
            spec, 2 * (component_m + 1)
        )
        lplus_left = _ladder_matrix(
            codomain,
            raised_codomain,
            step=1,
        )
        operator_from_raised = assemble_two_body(
            raised_domain,
            raised_codomain,
            pair_source_tensor(source, component_m),
        )
        actual_lplus = (
            lplus_left @ operator
            - operator_from_raised @ _ladder_matrix(
                domain, raised_domain, step=1
            )
        )
        expected_lplus = (
            sqrt((2 - component_m) * (3 + component_m))
            * family.components[component_m + 1]
            if component_m < 2
            else sparse.csr_matrix(actual_lplus.shape)
        )
        residuals[f"lplus[{component_m}]"] = _relative_frobenius_residual(
            actual_lplus,
            expected_lplus,
        )

        lowered_domain = DeterminantBasis.with_two_m(spec, -2)
        lowered_codomain = DeterminantBasis.with_two_m(
            spec, 2 * (component_m - 1)
        )
        lminus_left = _ladder_matrix(
            codomain,
            lowered_codomain,
            step=-1,
        )
        operator_from_lowered = assemble_two_body(
            lowered_domain,
            lowered_codomain,
            pair_source_tensor(source, component_m),
        )
        actual_lminus = (
            lminus_left @ operator
            - operator_from_lowered @ _ladder_matrix(
                domain, lowered_domain, step=-1
            )
        )
        expected_lminus = (
            sqrt((2 + component_m) * (3 - component_m))
            * family.components[component_m - 1]
            if component_m > -2
            else sparse.csr_matrix(actual_lminus.shape)
        )
        residuals[f"lminus[{component_m}]"] = _relative_frobenius_residual(
            actual_lminus,
            expected_lminus,
        )

    return MappingProxyType(residuals)


def adjoint_residual(
    plus: ResponseFamily,
    minus: ResponseFamily,
) -> float:
    """Return the largest full-operator spherical-adjoint residual."""

    if plus.spec != minus.spec:
        raise ValueError("plus and minus families must have equal SphereSpec")
    if plus.orientation != minus.orientation:
        raise ValueError("plus and minus families must have equal orientation")
    if plus.helicity != "+" or minus.helicity != "-":
        raise ValueError("families must be supplied in plus, minus order")

    source = lhyr_pair_reduced_source(
        minus.spec,
        "-",
        orientation=minus.orientation,
    )
    residual = 0.0
    for component_m, plus_operator in plus.components.items():
        minus_domain = DeterminantBasis.with_two_m(
            minus.spec, 2 * component_m
        )
        zero_sector = DeterminantBasis.with_two_m(minus.spec, 0)
        minus_operator = assemble_two_body(
            minus_domain,
            zero_sector,
            pair_source_tensor(source, -component_m),
        )
        expected = (-1) ** component_m * minus_operator.conj().T
        residual = max(
            residual,
            _relative_frobenius_residual(plus_operator, expected),
        )
    return residual


def monopole_reversal_matrix(
    spec: SphereSpec,
    two_m: int,
) -> sparse.csr_matrix:
    """Lift ``|Q,m> -> (-1)^(Q-m)|-Q,-m>`` to determinants."""

    domain = DeterminantBasis.with_two_m(spec, two_m)
    codomain = DeterminantBasis.with_two_m(spec, -two_m)
    rows = np.empty(domain.dimension, dtype=np.int64)
    columns = np.arange(domain.dimension, dtype=np.int64)
    data = np.empty(domain.dimension, dtype=np.float64)
    permutation_sign = (-1) ** (spec.particles * (spec.particles - 1) // 2)

    for column, state in enumerate(domain.states):
        reversed_state = 0
        phase = permutation_sign
        for orbital, orbital_two_m in enumerate(spec.two_m_values):
            if not state & (1 << orbital):
                continue
            reversed_state |= 1 << (spec.two_q - orbital)
            phase *= (-1) ** ((spec.two_q - orbital_two_m) // 2)
        rows[column] = codomain.state_index[reversed_state]
        data[column] = phase

    return sparse.csr_matrix(
        (data, (rows, columns)),
        shape=(codomain.dimension, domain.dimension),
    )


def monopole_reversal_residual(
    positive: ResponseFamily,
    reversed_family: ResponseFamily,
) -> float:
    """Return the largest residual of the full-family monopole reversal."""

    if positive.spec != reversed_family.spec:
        raise ValueError("response families must have equal SphereSpec")
    if positive.orientation != 1 or reversed_family.orientation != -1:
        raise ValueError("response families must have orientations +1 and -1")
    if positive.helicity == reversed_family.helicity:
        raise ValueError("monopole reversal must interchange helicities")

    reversal_zero = monopole_reversal_matrix(positive.spec, 0)
    residual = 0.0
    for component_m, operator in positive.components.items():
        actual = (
            monopole_reversal_matrix(positive.spec, 2 * component_m)
            @ operator.conjugate()
            @ reversal_zero.conj().T
        )
        expected = (
            (-1) ** component_m
            * reversed_family.components[-component_m]
        )
        residual = max(
            residual,
            _relative_frobenius_residual(actual, expected),
        )
    return residual


def _relative_frobenius_residual(
    actual: sparse.spmatrix,
    expected: sparse.spmatrix,
) -> float:
    difference = actual - expected
    return float(
        sparse.linalg.norm(difference)
        / max(float(sparse.linalg.norm(expected)), 1.0)
    )
