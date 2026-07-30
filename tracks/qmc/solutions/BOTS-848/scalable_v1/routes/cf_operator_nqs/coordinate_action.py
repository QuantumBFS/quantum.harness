"""Exact pair-Casimir action on division-free JK coordinate seeds."""

from __future__ import annotations

from numbers import Integral

import numpy as np

from .jets import PairJet, jet_determinant
from .pair_casimir import PairCasimirDecomposition, pair_casimir_decomposition
from .seeds import CFSeed, polynomial_seed_amplitude


_APPROVED_RANKS = (2, 3, 4)


class CoordinateActionNumericalError(FloatingPointError):
    """Raised when exact coordinate action encounters a non-finite value."""


def apply_pair_dot(
    value: PairJet,
    coordinates: tuple[PairJet, ...],
) -> PairJet:
    """Apply ``J_i dot J_j`` to a four-coordinate pair jet."""

    if not isinstance(value, PairJet):
        raise TypeError("value must be a PairJet")
    if len(coordinates) != 4 or not all(
        isinstance(coordinate, PairJet) for coordinate in coordinates
    ):
        raise ValueError("coordinates must contain four PairJet variables")
    u_i, v_i, u_j, v_j = coordinates
    jzi = 0.5 * (u_i * value.derivative(0) - v_i * value.derivative(1))
    zz = 0.5 * (u_j * jzi.derivative(2) - v_j * jzi.derivative(3))
    plus_i = u_i * value.derivative(1)
    minus_i = v_i * value.derivative(0)
    plus_minus = v_j * plus_i.derivative(2)
    minus_plus = u_j * minus_i.derivative(3)
    return zz + 0.5 * (plus_minus + minus_plus)


def _checked_ells(ells: tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(ells, tuple) or not ells:
        raise ValueError("ells must be a nonempty tuple")
    checked: list[int] = []
    for ell in ells:
        if isinstance(ell, (bool, np.bool_)) or not isinstance(ell, Integral):
            raise TypeError("each ell must be an integer")
        integer = int(ell)
        if integer not in _APPROVED_RANKS:
            raise ValueError("ells must contain only ranks 2, 3, and 4")
        if integer in checked:
            raise ValueError("ells must not contain duplicates")
        checked.append(integer)
    return tuple(checked)


def _complex_determinant(matrix: object) -> complex:
    return complex(np.linalg.det(np.asarray(matrix, dtype=np.complex128)))


def _lift_pair(
    config: np.ndarray,
    first: int,
    second: int,
) -> tuple[list[list[PairJet]], tuple[PairJet, ...]]:
    lifted = [
        [PairJet.constant(config[particle, component]) for component in range(2)]
        for particle in range(len(config))
    ]
    coordinates = (
        PairJet.variable(config[first, 0], axis=0),
        PairJet.variable(config[first, 1], axis=1),
        PairJet.variable(config[second, 0], axis=2),
        PairJet.variable(config[second, 1], axis=3),
    )
    lifted[first][0], lifted[first][1] = coordinates[:2]
    lifted[second][0], lifted[second][1] = coordinates[2:]
    return lifted, coordinates


def _scaled_pair_powers(
    seed_jet: PairJet,
    coordinates: tuple[PairJet, ...],
    *,
    scale: float,
    degree: int,
) -> tuple[PairJet, ...]:
    powers = [seed_jet]
    for _ in range(degree):
        powers.append((1.0 / scale) * apply_pair_dot(powers[-1], coordinates))
    return tuple(powers)


def _pair_polynomial_value(
    decomposition: PairCasimirDecomposition,
    powers: tuple[PairJet, ...],
) -> complex:
    result = PairJet.constant(0.0)
    for coefficient, power in zip(
        decomposition.coefficients,
        powers[: len(decomposition.coefficients)],
        strict=True,
    ):
        result = result + coefficient * power
    return result.constant_term


def evaluate_seed_and_actions(
    state: CFSeed,
    configs: object,
    *,
    ells: tuple[int, ...] = (2, 3, 4),
) -> tuple[np.ndarray, np.ndarray]:
    """Return raw seed values and exact ``S_ell`` seed values per config."""

    if not isinstance(state, CFSeed):
        raise TypeError("state must be a CFSeed")
    checked_ells = _checked_ells(ells)
    try:
        checked_configs, _ = state._family._validated_configs(configs)
    except (TypeError, ValueError) as error:
        if "finite" in str(error):
            raise CoordinateActionNumericalError(str(error)) from error
        raise

    decompositions = tuple(
        pair_casimir_decomposition(two_q=state.two_q, ell=ell)
        for ell in checked_ells
    )
    scale = decompositions[0].scale
    if not all(
        np.isclose(item.scale, scale, rtol=0.0, atol=1.0e-13)
        for item in decompositions
    ):
        raise CoordinateActionNumericalError("pair-Casimir scales are inconsistent")
    degree = max(item.degree for item in decompositions)

    batch = len(checked_configs)
    seed_values = np.empty(batch, dtype=np.complex128)
    actions = np.empty((batch, len(decompositions)), dtype=np.complex128)
    for batch_index, config in enumerate(checked_configs):
        seed_value = complex(
            polynomial_seed_amplitude(state, config, _complex_determinant)
        )
        seed_values[batch_index] = seed_value
        action_values = np.asarray(
            [
                state.n_electrons * item.self_scalar * seed_value
                for item in decompositions
            ],
            dtype=np.complex128,
        )
        for first in range(state.n_electrons):
            for second in range(first + 1, state.n_electrons):
                lifted, coordinates = _lift_pair(config, first, second)
                raw_jet = polynomial_seed_amplitude(state, lifted, jet_determinant)
                if not isinstance(raw_jet, PairJet):
                    raise TypeError("jet seed evaluation did not return a PairJet")
                powers = _scaled_pair_powers(
                    raw_jet,
                    coordinates,
                    scale=scale,
                    degree=degree,
                )
                for ell_index, decomposition in enumerate(decompositions):
                    action_values[ell_index] += _pair_polynomial_value(
                        decomposition,
                        powers,
                    )
        actions[batch_index] = action_values

    if not np.all(np.isfinite(seed_values)) or not np.all(np.isfinite(actions)):
        raise CoordinateActionNumericalError(
            "coordinate action produced a non-finite coefficient or result"
        )
    return seed_values, actions


__all__ = [
    "CoordinateActionNumericalError",
    "apply_pair_dot",
    "evaluate_seed_and_actions",
]
