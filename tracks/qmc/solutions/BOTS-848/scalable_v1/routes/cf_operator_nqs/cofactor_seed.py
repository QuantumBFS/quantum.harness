"""Division-free analytic JK cofactors for the complete Route C seed family.

The implementation is array-namespace compatible: NumPy supplies the exact
reference path and JAX supplies the production tracing path.  No determinant,
matrix inverse, pivot, or electronic full-basis object appears here.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .seeds import JKCFSeedFamily


_L2_COMPONENTS = tuple(range(-2, 3))


def _product(values: list[object]) -> object:
    result: object = 1.0
    for value in values:
        result = result * value
    return result


def _elementary_homogeneous(
    spinors: object,
    rows: tuple[int, ...],
    *,
    xp: Any,
) -> object:
    """Coefficients of ``prod_s (v_s + u_s t)`` for the selected rows."""

    coefficients = [xp.asarray(1.0 + 0.0j)] + [
        xp.asarray(0.0 + 0.0j) for _ in rows
    ]
    for row in rows:
        updated = [xp.asarray(0.0 + 0.0j) for _ in coefficients]
        for degree in range(len(coefficients)):
            updated[degree] = (
                updated[degree] + spinors[row][1] * coefficients[degree]
            )
            if degree:
                updated[degree] = (
                    updated[degree]
                    + spinors[row][0] * coefficients[degree - 1]
                )
        coefficients = updated
    return xp.stack(coefficients)


def _replacement_column(
    family: JKCFSeedFamily,
    spinors: object,
    derivative_u: list[object],
    derivative_v: list[object],
    *,
    particle_twice_m: int,
) -> list[object]:
    twice_l = int(round(2.0 * family.particle_l))
    a = (twice_l + particle_twice_m) // 2
    b = (twice_l - particle_twice_m) // 2
    normalization = math.sqrt(math.comb(twice_l, a))
    result: list[object] = []
    for row in range(family.n_electrons):
        first: object = 0.0
        second: object = 0.0
        if b:
            first = (
                b
                * spinors[row][0] ** a
                * spinors[row][1] ** (b - 1)
                * derivative_u[row]
            )
        if a:
            second = (
                a
                * spinors[row][0] ** (a - 1)
                * spinors[row][1] ** b
                * derivative_v[row]
            )
        result.append(normalization * (first - second))
    return result


def _replacement_determinant(
    family: JKCFSeedFamily,
    spinors: object,
    jastrow: list[object],
    derivative_u: list[object],
    derivative_v: list[object],
    delta: list[list[object]],
    *,
    hole: int,
    particle_twice_m: int,
    xp: Any,
) -> object:
    n_electrons = family.n_electrons
    column = _replacement_column(
        family,
        spinors,
        derivative_u,
        derivative_v,
        particle_twice_m=particle_twice_m,
    )
    normalization = _product(
        [
            math.sqrt(math.comb(n_electrons - 1, orbital))
            for orbital in range(n_electrons)
            if orbital != hole
        ]
    )
    inversion_count = (n_electrons - 1) * (n_electrons - 2) // 2
    vandermonde_sign = -1.0 if inversion_count % 2 else 1.0
    terms: list[object] = []
    for row in range(n_electrons):
        retained = tuple(index for index in range(n_electrons) if index != row)
        excluded_vandermonde = _product(
            [
                delta[first][second]
                for first in retained
                for second in retained
                if first < second
            ]
        )
        elementary = _elementary_homogeneous(
            spinors,
            retained,
            xp=xp,
        )[n_electrons - 1 - hole]
        cofactor = (
            ((-1.0) ** (row + hole))
            * vandermonde_sign
            * normalization
            * _product([jastrow[index] for index in retained])
            * excluded_vandermonde
            * elementary
        )
        terms.append(cofactor * column[row])
    return sum(terms)


def cofactor_seed_family_amplitudes(
    family: JKCFSeedFamily,
    spinors: object,
    *,
    xp: Any = np,
) -> object:
    """Return ``(L0M0,L2M-2,...,L2M2)`` from explicit JK cofactors."""

    if not isinstance(family, JKCFSeedFamily):
        raise TypeError("family must be a JKCFSeedFamily")
    checked = xp.asarray(spinors)
    expected_shape = (family.n_electrons, 2)
    if tuple(checked.shape) != expected_shape:
        raise ValueError(f"spinor shape must be {expected_shape}")

    return _cofactor_seed_family_amplitudes(family, checked, xp=xp)


def _cofactor_seed_family_amplitudes(
    family: JKCFSeedFamily,
    checked: object,
    *,
    xp: Any,
) -> object:
    """Evaluate over an already validated scalar-ring spinor matrix."""

    n_electrons = family.n_electrons
    delta = [
        [
            checked[first][0] * checked[second][1]
            - checked[first][1] * checked[second][0]
            for second in range(n_electrons)
        ]
        for first in range(n_electrons)
    ]
    jastrow: list[object] = []
    derivative_u: list[object] = []
    derivative_v: list[object] = []
    for particle in range(n_electrons):
        others = [index for index in range(n_electrons) if index != particle]
        factors = [delta[particle][other] for other in others]
        jastrow.append(_product(factors))
        derivative_u.append(
            sum(
                checked[other][1]
                * _product(
                    [factor for index, factor in enumerate(factors) if index != slot]
                )
                for slot, other in enumerate(others)
            )
        )
        derivative_v.append(
            sum(
                -checked[other][0]
                * _product(
                    [factor for index, factor in enumerate(factors) if index != slot]
                )
                for slot, other in enumerate(others)
            )
        )

    ground = _product(
        [
            delta[first][second] ** 3
            for first in range(n_electrons)
            for second in range(first + 1, n_electrons)
        ]
    )
    tower: list[object] = []
    for total_m in _L2_COMPONENTS:
        value: object = 0.0
        for term in family._couplings[total_m]:
            value = value + term.coefficient * _replacement_determinant(
                family,
                checked,
                jastrow,
                derivative_u,
                derivative_v,
                delta,
                hole=term.hole_index,
                particle_twice_m=term.particle_twice_m,
                xp=xp,
            )
        tower.append(value)
    return xp.stack([ground, *tower])


__all__ = ["cofactor_seed_family_amplitudes"]
