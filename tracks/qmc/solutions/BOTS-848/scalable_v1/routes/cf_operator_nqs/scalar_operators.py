"""SO(3)-scalar contractions of electronic-LLL projected densities.

The occupation backend represents a determinant by a Python integer bitset.
It applies one-body projected densities successively and coalesces equal
targets; it never enumerates a many-body basis.  For a fixed operator depth,
its neighborhood is polynomial in particle number.  Coordinate/spinor Route C
states remain representation-generic through the ``connected_scalar_action``
state hook documented by :meth:`ScalarOperator.connected_action`.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ...contracts import StateHandle
from .projected_density import projected_density_tensor


def _validate_operator_inputs(
    two_q: object, ell: object, depth: object
) -> tuple[int, int, int]:
    if type(two_q) is not int:
        raise TypeError("two_q must be an integer")
    if two_q <= 0:
        raise ValueError("two_q must be positive")
    if type(ell) is not int:
        raise TypeError("ell must be an integer")
    if not 0 <= ell <= two_q:
        raise ValueError("ell must satisfy 0 <= ell <= two_q")
    if type(depth) is not int:
        raise TypeError("depth must be an integer")
    if depth <= 0:
        raise ValueError("depth must be positive")
    return two_q, ell, depth


def _apply_annihilation(config: int, orbital: int) -> tuple[int, int] | None:
    mask = 1 << orbital
    if not config & mask:
        return None
    sign = -1 if (config & (mask - 1)).bit_count() % 2 else 1
    return config ^ mask, sign


def _apply_creation(config: int, orbital: int) -> tuple[int, int] | None:
    mask = 1 << orbital
    if config & mask:
        return None
    sign = -1 if (config & (mask - 1)).bit_count() % 2 else 1
    return config | mask, sign


def _one_body_action(one_body: np.ndarray, config: int) -> dict[int, complex]:
    targets: dict[int, complex] = {}
    for source in range(one_body.shape[1]):
        annihilated = _apply_annihilation(config, source)
        if annihilated is None:
            continue
        intermediate, sign_1 = annihilated
        for target in np.flatnonzero(one_body[:, source]):
            created = _apply_creation(intermediate, int(target))
            if created is None:
                continue
            connected, sign_2 = created
            value = complex(one_body[target, source]) * sign_1 * sign_2
            targets[connected] = targets.get(connected, 0.0j) + value
    return targets


def _scalar_once(two_q: int, ell: int, config: int) -> dict[int, complex]:
    targets: dict[int, complex] = {}
    for m in range(-ell, ell + 1):
        right_action = _one_body_action(
            projected_density_tensor(two_q=two_q, ell=ell, m=-m), config
        )
        left_tensor = projected_density_tensor(two_q=two_q, ell=ell, m=m)
        phase = -1 if m % 2 else 1
        for intermediate, right_value in right_action.items():
            for connected, left_value in _one_body_action(
                left_tensor, intermediate
            ).items():
                value = phase * left_value * right_value
                targets[connected] = targets.get(connected, 0.0j) + value
    return targets


def _validate_config(config: object, *, two_q: int) -> int:
    if isinstance(config, (bool, np.bool_)) or not isinstance(config, (int, np.integer)):
        raise TypeError("occupation configurations must be integer bitsets")
    checked = int(config)
    if checked < 0 or checked >> (two_q + 1):
        raise ValueError("occupation configuration lies outside the fixed electronic LLL")
    return checked


def _connected_for_config(
    *, two_q: int, ell: int, depth: int, config: int
) -> tuple[np.ndarray, np.ndarray]:
    current: dict[int, complex] = {config: 1.0 + 0.0j}
    for _ in range(depth):
        next_targets: dict[int, complex] = {}
        for source, source_value in current.items():
            for target, step_value in _scalar_once(two_q, ell, source).items():
                next_targets[target] = (
                    next_targets.get(target, 0.0j) + step_value * source_value
                )
        current = next_targets
    ordered = sorted(current.items())
    connected = np.asarray([item[0] for item in ordered], dtype=np.int64)
    weights = np.asarray([item[1] for item in ordered], dtype=np.complex128)
    return connected, weights


def connected_scalar_action(
    *, two_q: int, ell: int, depth: int = 1, configs: object
) -> tuple[np.ndarray, np.ndarray]:
    """Apply ``S_ell**depth`` to one bitset or a one-dimensional bitset batch.

    ``S_ell`` is contracted exactly as
    ``sum_m (-1)**m rho_bar[ell,m] rho_bar[ell,-m]``.  A scalar input returns
    one-dimensional connected configurations and weights.  A batch returns
    two padded arrays with one row per source; ``-1`` and zero mark padding.
    """

    checked_two_q, checked_ell, checked_depth = _validate_operator_inputs(
        two_q, ell, depth
    )
    scalar_input = isinstance(configs, (int, np.integer)) and not isinstance(
        configs, (bool, np.bool_)
    )
    if scalar_input:
        checked_configs = [_validate_config(configs, two_q=checked_two_q)]
    else:
        array = np.asarray(configs)
        if array.ndim != 1 or array.dtype.kind not in "iu" or array.dtype.kind == "b":
            raise TypeError(
                "non-bitset configurations require a connected_scalar_action state hook"
            )
        checked_configs = [
            _validate_config(config, two_q=checked_two_q) for config in array
        ]

    groups = [
        _connected_for_config(
            two_q=checked_two_q,
            ell=checked_ell,
            depth=checked_depth,
            config=config,
        )
        for config in checked_configs
    ]
    if scalar_input:
        return groups[0]

    width = max((len(group[0]) for group in groups), default=0)
    connected = np.full((len(groups), width), -1, dtype=np.int64)
    weights = np.zeros((len(groups), width), dtype=np.complex128)
    for row, (row_configs, row_weights) in enumerate(groups):
        connected[row, : len(row_configs)] = row_configs
        weights[row, : len(row_weights)] = row_weights
    return connected, weights


def _fixture_basis(two_q: int) -> tuple[int, ...]:
    """Return the exact two-electron certification fixture, never a runtime basis."""

    return tuple(
        (1 << first) | (1 << second)
        for first, second in itertools.combinations(range(two_q + 1), 2)
    )


def _second_quantized_fixture(
    one_body: np.ndarray, basis: tuple[int, ...]
) -> np.ndarray:
    index = {config: row for row, config in enumerate(basis)}
    matrix = np.zeros((len(basis), len(basis)), dtype=np.complex128)
    for column, source in enumerate(basis):
        for target, value in _one_body_action(one_body, source).items():
            matrix[index[target], column] += value
    return matrix


def _fixture_l2(two_q: int, basis: tuple[int, ...]) -> np.ndarray:
    n_orbitals = two_q + 1
    l_plus = np.zeros((n_orbitals, n_orbitals), dtype=np.complex128)
    for orbital in range(two_q):
        l_plus[orbital + 1, orbital] = math.sqrt(
            (two_q - orbital) * (orbital + 1)
        )
    l_minus = l_plus.T.conj()
    l_z = np.diag(np.arange(n_orbitals, dtype=float) - 0.5 * two_q)
    total_plus = _second_quantized_fixture(l_plus, basis)
    total_minus = _second_quantized_fixture(l_minus, basis)
    total_z = _second_quantized_fixture(l_z, basis)
    return (
        total_z @ total_z
        + 0.5 * (total_plus @ total_minus + total_minus @ total_plus)
    )


def _fixture_scalar_matrix(
    two_q: int, ell: int, depth: int, basis: tuple[int, ...]
) -> tuple[np.ndarray, bool]:
    index = {config: row for row, config in enumerate(basis)}
    matrix = np.zeros((len(basis), len(basis)), dtype=np.complex128)
    strict_lll = True
    mask = (1 << (two_q + 1)) - 1
    for column, source in enumerate(basis):
        connected, weights = _connected_for_config(
            two_q=two_q, ell=ell, depth=depth, config=source
        )
        for target, value in zip(connected, weights, strict=True):
            target_int = int(target)
            strict_lll &= (
                target_int & ~mask == 0
                and target_int.bit_count() == source.bit_count()
                and target_int in index
            )
            if target_int in index:
                matrix[index[target_int], column] += value
    return matrix, strict_lll


@dataclass(frozen=True)
class ScalarOperator:
    """A fixed-rank, fixed-depth LLL scalar with an exact N=2 certificate.

    ``matrix`` is deliberately only the exact two-electron fixture matrix used
    to certify Hermiticity and rotational covariance.  Production evaluation
    must use :meth:`connected_action`, which never builds a full many-body
    basis.  Coordinate/spinor states may implement
    ``connected_scalar_action(*, two_q, ell, depth, configs)``; otherwise the
    built-in occupation-bitset backend is selected.
    """

    two_q: int
    depth: int
    ell: int
    strict_lll: bool
    commutes_with_l2: bool
    matrix: np.ndarray = field(repr=False, compare=False)

    def connected_action(
        self, state: StateHandle, configs: object
    ) -> tuple[object, np.ndarray]:
        hook = getattr(state, "connected_scalar_action", None)
        if callable(hook):
            connected, weights = hook(
                two_q=self.two_q,
                ell=self.ell,
                depth=self.depth,
                configs=configs,
            )
            return connected, np.asarray(weights, dtype=np.complex128)
        return connected_scalar_action(
            two_q=self.two_q,
            ell=self.ell,
            depth=self.depth,
            configs=configs,
        )


def build_scalar_operator(
    *, two_q: int, ell: int, depth: int = 1
) -> ScalarOperator:
    """Build a strict-LLL scalar and its independent small-fixture certificate."""

    checked_two_q, checked_ell, checked_depth = _validate_operator_inputs(
        two_q, ell, depth
    )
    basis = _fixture_basis(checked_two_q)
    matrix, strict_lll = _fixture_scalar_matrix(
        checked_two_q, checked_ell, checked_depth, basis
    )
    l2 = _fixture_l2(checked_two_q, basis)
    scale = max(np.linalg.norm(matrix), np.finfo(float).tiny)
    commutator_residual = np.linalg.norm(matrix @ l2 - l2 @ matrix) / scale
    matrix.setflags(write=False)
    return ScalarOperator(
        two_q=checked_two_q,
        depth=checked_depth,
        ell=checked_ell,
        strict_lll=bool(strict_lll),
        commutes_with_l2=bool(commutator_residual < 1.0e-12),
        matrix=matrix,
    )


__all__ = [
    "ScalarOperator",
    "build_scalar_operator",
    "connected_scalar_action",
]
