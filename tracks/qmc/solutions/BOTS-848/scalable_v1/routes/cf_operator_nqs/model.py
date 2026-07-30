"""One-layer strict-LLL Operator-NQS coefficient model.

The expensive family action is supplied by ``action_kernel``.  This module
only parameterizes the three scalar-operator coefficients and therefore never
differentiates through the exact strict-LLL backend.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


ActionKernel = Callable[[object], tuple[object, object]]

_DESCRIPTORS = np.asarray(((1.0, 2.0), (1.0, 3.0), (1.0, 4.0)))
_SECTOR_COUNT = 6
_RANK_COUNT = 3
_MAX_PARAMETERS = 262_144


@dataclass
class _ComplexHead:
    real_weights: np.ndarray
    imaginary_weights: np.ndarray
    real_bias: float
    imaginary_bias: float

    @classmethod
    def zeros(cls, width: int) -> "_ComplexHead":
        return cls(
            real_weights=np.zeros(width, dtype=np.float64),
            imaginary_weights=np.zeros(width, dtype=np.float64),
            real_bias=0.0,
            imaginary_bias=0.0,
        )

    @property
    def complex_weights(self) -> np.ndarray:
        return self.real_weights + 1j * self.imaginary_weights

    @property
    def complex_bias(self) -> complex:
        return complex(self.real_bias, self.imaginary_bias)


class CFOperatorNQS:
    """Shared descriptor trunk with distinct ground and excited heads."""

    def __init__(
        self,
        *,
        n_electrons: int,
        two_q: int,
        trunk_weights: np.ndarray,
        trunk_bias: np.ndarray,
        ground_head: _ComplexHead,
        excited_head: _ComplexHead,
        action_kernel: ActionKernel,
    ) -> None:
        self.n_electrons = n_electrons
        self.two_q = two_q
        self._trunk_weights = trunk_weights
        self._trunk_bias = trunk_bias
        self._ground_head = ground_head
        self._excited_head = excited_head
        self._action_kernel = action_kernel

    @classmethod
    def initialize(
        cls,
        *,
        n_electrons: int,
        two_q: int,
        hidden_width: int,
        seed: int,
        action_kernel: ActionKernel,
    ) -> "CFOperatorNQS":
        for name, value in (
            ("n_electrons", n_electrons),
            ("two_q", two_q),
            ("hidden_width", hidden_width),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("seed must be an integer")
        if not callable(action_kernel):
            raise TypeError("action_kernel must be callable")

        parameter_count = 7 * hidden_width + 4
        if parameter_count > _MAX_PARAMETERS:
            raise ValueError(
                f"model has {parameter_count} parameters, exceeding {_MAX_PARAMETERS}"
            )

        rng = np.random.default_rng(seed)
        scale = 1.0 / np.sqrt(2.0)
        trunk_weights = rng.normal(
            loc=0.0, scale=scale, size=(hidden_width, 2)
        ).astype(np.float64)
        trunk_bias = rng.normal(
            loc=0.0, scale=scale, size=hidden_width
        ).astype(np.float64)
        return cls(
            n_electrons=n_electrons,
            two_q=two_q,
            trunk_weights=trunk_weights,
            trunk_bias=trunk_bias,
            ground_head=_ComplexHead.zeros(hidden_width),
            excited_head=_ComplexHead.zeros(hidden_width),
            action_kernel=action_kernel,
        )

    @property
    def hidden_width(self) -> int:
        return int(self._trunk_bias.size)

    @property
    def parameter_count(self) -> int:
        return 7 * self.hidden_width + 4

    @staticmethod
    def head_for_sector(sector_index: int) -> str:
        if (
            isinstance(sector_index, bool)
            or not isinstance(sector_index, (int, np.integer))
            or not 0 <= int(sector_index) < _SECTOR_COUNT
        ):
            raise ValueError("sector_index must be an integer from 0 through 5")
        return "ground" if int(sector_index) == 0 else "excited"

    def _head(self, sector_index: int) -> _ComplexHead:
        return (
            self._ground_head
            if self.head_for_sector(sector_index) == "ground"
            else self._excited_head
        )

    def _hidden(self) -> np.ndarray:
        return np.tanh(_DESCRIPTORS @ self._trunk_weights.T + self._trunk_bias)

    def _coefficients(self, head: _ComplexHead) -> np.ndarray:
        return self._hidden() @ head.complex_weights + head.complex_bias

    def _validated_action(
        self, configs: object
    ) -> tuple[np.ndarray, np.ndarray]:
        values = np.asarray(configs)
        if values.ndim != 3 or values.shape[1:] != (self.n_electrons, 2):
            raise ValueError(
                "configs must have shape (batch, n_electrons, 2)"
            )
        if values.shape[0] <= 0 or not np.all(np.isfinite(values)):
            raise ValueError("configs must be a non-empty finite batch")

        seeds_raw, actions_raw = self._action_kernel(configs)
        seeds = np.asarray(seeds_raw, dtype=np.complex128)
        actions = np.asarray(actions_raw, dtype=np.complex128)
        batch = values.shape[0]
        if seeds.shape != (batch, _SECTOR_COUNT):
            raise ValueError("action kernel seeds must have shape (batch, 6)")
        if actions.shape != (batch, _SECTOR_COUNT, _RANK_COUNT):
            raise ValueError("action kernel actions must have shape (batch, 6, 3)")
        if not np.all(np.isfinite(seeds)) or not np.all(np.isfinite(actions)):
            raise ValueError("action kernel returned non-finite values")
        return seeds, actions

    def amplitudes(self, configs: object) -> np.ndarray:
        seeds, actions = self._validated_action(configs)
        ground = self._coefficients(self._ground_head)
        excited = self._coefficients(self._excited_head)
        coefficients = np.vstack((ground, *(excited for _ in range(5))))
        return seeds + np.einsum("bsr,sr->bs", actions, coefficients)

    def log_amplitudes(self, configs: object) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.log(self.amplitudes(configs))

    def flat_parameters(self) -> np.ndarray:
        arrays = [
            self._trunk_weights.ravel(),
            self._trunk_bias,
            self._ground_head.real_weights,
            self._ground_head.imaginary_weights,
            np.asarray(
                (
                    self._ground_head.real_bias,
                    self._ground_head.imaginary_bias,
                )
            ),
            self._excited_head.real_weights,
            self._excited_head.imaginary_weights,
            np.asarray(
                (
                    self._excited_head.real_bias,
                    self._excited_head.imaginary_bias,
                )
            ),
        ]
        return np.concatenate(arrays).astype(np.float64, copy=True)

    def set_flat_parameters(self, parameters: object) -> None:
        values = np.asarray(parameters)
        if values.ndim != 1 or values.size != self.parameter_count:
            raise ValueError(
                f"parameters must have shape ({self.parameter_count},)"
            )
        if np.iscomplexobj(values) or not np.all(np.isfinite(values)):
            raise ValueError("parameters must be finite real values")
        values = values.astype(np.float64, copy=True)

        width = self.hidden_width
        offset = 0

        def take(count: int) -> np.ndarray:
            nonlocal offset
            result = values[offset : offset + count]
            offset += count
            return result

        self._trunk_weights = take(2 * width).reshape(width, 2).copy()
        self._trunk_bias = take(width).copy()
        self._ground_head.real_weights = take(width).copy()
        self._ground_head.imaginary_weights = take(width).copy()
        ground_bias = take(2)
        self._ground_head.real_bias = float(ground_bias[0])
        self._ground_head.imaginary_bias = float(ground_bias[1])
        self._excited_head.real_weights = take(width).copy()
        self._excited_head.imaginary_weights = take(width).copy()
        excited_bias = take(2)
        self._excited_head.real_bias = float(excited_bias[0])
        self._excited_head.imaginary_bias = float(excited_bias[1])
        if offset != self.parameter_count:
            raise RuntimeError("internal parameter packing error")

    def log_derivative(
        self, configs: object, sector_index: int
    ) -> np.ndarray:
        sector = int(sector_index)
        head_name = self.head_for_sector(sector_index)
        head = self._head(sector)
        seeds, actions = self._validated_action(configs)

        hidden = self._hidden()
        coefficients = hidden @ head.complex_weights + head.complex_bias
        psi = seeds[:, sector] + actions[:, sector, :] @ coefficients
        if not np.all(np.isfinite(psi)):
            raise ValueError("selected amplitudes are non-finite")
        if np.any(psi == 0.0):
            raise ValueError("log derivative is undefined at an exact node")

        batch = psi.size
        width = self.hidden_width
        derivative = np.zeros(
            (batch, self.parameter_count), dtype=np.complex128
        )
        selected_actions = actions[:, sector, :]
        hidden_slope = 1.0 - hidden * hidden
        head_weights = head.complex_weights

        trunk_bias_derivative = np.einsum(
            "br,rh,h->bh", selected_actions, hidden_slope, head_weights
        )
        trunk_weight_derivative = np.einsum(
            "br,rh,h,rk->bhk",
            selected_actions,
            hidden_slope,
            head_weights,
            _DESCRIPTORS,
        )
        head_weight_derivative = selected_actions @ hidden
        head_bias_derivative = np.sum(selected_actions, axis=1)

        offset = 0
        derivative[:, offset : offset + 2 * width] = (
            trunk_weight_derivative.reshape(batch, 2 * width)
        )
        offset += 2 * width
        derivative[:, offset : offset + width] = trunk_bias_derivative
        offset += width

        def write_head(active: bool) -> None:
            nonlocal offset
            if active:
                derivative[:, offset : offset + width] = head_weight_derivative
                derivative[:, offset + width : offset + 2 * width] = (
                    1j * head_weight_derivative
                )
                derivative[:, offset + 2 * width] = head_bias_derivative
                derivative[:, offset + 2 * width + 1] = 1j * head_bias_derivative
            offset += 2 * width + 2

        write_head(head_name == "ground")
        write_head(head_name == "excited")
        if offset != self.parameter_count:
            raise RuntimeError("internal derivative packing error")
        return derivative / psi[:, None]
