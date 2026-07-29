"""SO(3)-scalar contractions of electronic-LLL projected densities.

The occupation backend represents a determinant by a Python integer bitset.
It applies one-body projected densities successively and coalesces equal
targets; it never enumerates a many-body basis.  For a fixed operator depth,
its neighborhood is polynomial in particle number.  Coordinate/spinor Route C
states remain representation-generic through the ``connected_scalar_action``
state hook documented by :meth:`ScalarOperator.connected_action`.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Protocol, runtime_checkable

import numpy as np

from ...contracts import StateHandle
from .projected_density import projected_density_tensor


@runtime_checkable
class ConnectedScalarActionProvider(Protocol):
    """Optional state hook for representation-native scalar neighborhoods.

    ``weights.shape`` gives the batch/neighborhood axes.  ``connected`` must
    start with exactly those axes and may append representation axes, e.g.
    ``(B, K, N, 2)`` spinors paired with ``(B, K)`` weights.
    """

    def connected_scalar_action(
        self,
        *,
        two_q: int,
        ell: int,
        depth: int,
        configs: object,
    ) -> tuple[np.ndarray, np.ndarray]: ...


def _validate_operator_inputs(
    two_q: object, ell: object, depth: object
) -> tuple[int, int, int]:
    if isinstance(two_q, (bool, np.bool_)) or not isinstance(two_q, Integral):
        raise TypeError("two_q must be an integer")
    checked_two_q = int(two_q)
    if checked_two_q <= 0:
        raise ValueError("two_q must be positive")
    if checked_two_q > 62:
        raise ValueError("two_q must be <= 62 for the signed-int64 bitset backend")
    if isinstance(ell, (bool, np.bool_)) or not isinstance(ell, Integral):
        raise TypeError("ell must be an integer")
    checked_ell = int(ell)
    if not 0 <= checked_ell <= checked_two_q:
        raise ValueError("ell must satisfy 0 <= ell <= two_q")
    if isinstance(depth, (bool, np.bool_)) or not isinstance(depth, Integral):
        raise TypeError("depth must be an integer")
    checked_depth = int(depth)
    if checked_depth <= 0:
        raise ValueError("depth must be positive")
    return checked_two_q, checked_ell, checked_depth


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
    if isinstance(config, (bool, np.bool_)) or not isinstance(config, Integral):
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
    scalar_input = isinstance(configs, Integral) and not isinstance(
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


def _validate_hook_result(result: object) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(result, tuple) or len(result) != 2:
        raise TypeError("connected_scalar_action hook must return an ndarray pair")
    connected, weights = result
    if not isinstance(connected, np.ndarray):
        raise TypeError("hook connected configurations must be an ndarray")
    if not isinstance(weights, np.ndarray):
        raise TypeError("hook weights must be an ndarray")
    if weights.ndim == 0:
        raise ValueError("hook weights must be non-scalar")
    if not np.issubdtype(connected.dtype, np.number):
        raise TypeError("hook connected configurations must have numeric dtype")
    if not np.issubdtype(weights.dtype, np.number):
        raise TypeError("hook weights must have numeric dtype")
    if not np.all(np.isfinite(connected)) or not np.all(np.isfinite(weights)):
        raise ValueError("hook connected configurations and weights must be finite")
    if (
        connected.ndim < weights.ndim
        or connected.shape[: weights.ndim] != weights.shape
    ):
        raise ValueError(
            "hook connected leading dimensions must exactly match weights.shape"
        )
    return connected, weights.astype(np.complex128, copy=False)


@dataclass(frozen=True)
class ScalarOperator:
    """A fixed-rank, fixed-depth electronic-LLL scalar certificate.

    The construction flags follow from contracting two fixed-LLL irreducible
    tensors to rank zero; construction never builds or stores a many-body
    matrix.  Coordinate/spinor states may implement
    ``connected_scalar_action(*, two_q, ell, depth, configs)``; otherwise the
    built-in occupation-bitset backend is selected.
    """

    two_q: int
    depth: int
    ell: int
    strict_lll: bool
    commutes_with_l2: bool

    def connected_action(
        self, state: StateHandle, configs: object
    ) -> tuple[object, np.ndarray]:
        if isinstance(state, ConnectedScalarActionProvider):
            return _validate_hook_result(
                state.connected_scalar_action(
                    two_q=self.two_q,
                    ell=self.ell,
                    depth=self.depth,
                    configs=configs,
                )
            )
        return connected_scalar_action(
            two_q=self.two_q,
            ell=self.ell,
            depth=self.depth,
            configs=configs,
        )


def build_scalar_operator(
    *, two_q: int, ell: int, depth: int = 1
) -> ScalarOperator:
    """Build a parameter-only strict-LLL scalar construction certificate."""

    checked_two_q, checked_ell, checked_depth = _validate_operator_inputs(
        two_q, ell, depth
    )
    return ScalarOperator(
        two_q=checked_two_q,
        depth=checked_depth,
        ell=checked_ell,
        strict_lll=True,
        commutes_with_l2=True,
    )


__all__ = [
    "ConnectedScalarActionProvider",
    "ScalarOperator",
    "build_scalar_operator",
    "connected_scalar_action",
]
