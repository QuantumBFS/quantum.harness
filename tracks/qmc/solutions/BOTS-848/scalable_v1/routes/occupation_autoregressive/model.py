"""Shared fixed-sector autoregressive log-wavefunction model."""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Integral
from types import MappingProxyType

import numpy as np
from scipy.special import logsumexp

from .constraints import FeasibilityTable, occupation_m2


_SECTORS = ("ground", "excited")


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    return int(value)


class AutoregressiveNQS:
    """Two-layer conditional NQS with a shared trunk and sector heads."""

    def __init__(
        self,
        *,
        feasibility: FeasibilityTable,
        width: int,
        parameters: tuple[tuple[str, np.ndarray], ...],
    ) -> None:
        self.feasibility = feasibility
        self.n_electrons = feasibility.n_electrons
        self.two_q = feasibility.two_q
        self.target_m2 = feasibility.target_m2
        self.n_orbitals = feasibility.two_q + 1
        self.width = width

        by_name = dict(parameters)
        self.W1 = by_name["trunk.W1"]
        self.b1 = by_name["trunk.b1"]
        self.W2 = by_name["trunk.W2"]
        self.b2 = by_name["trunk.b2"]
        self._heads = {
            sector: {
                "amplitude_W": by_name[f"{sector}.amplitude_W"],
                "amplitude_b": by_name[f"{sector}.amplitude_b"],
                "phase_W": by_name[f"{sector}.phase_W"],
                "phase_b": by_name[f"{sector}.phase_b"],
            }
            for sector in _SECTORS
        }
        self._parameter_items = parameters

        offset = 0
        slices: dict[str, slice] = {}
        for name, array in parameters:
            slices[name] = slice(offset, offset + array.size)
            offset += array.size
        self.parameter_slices: Mapping[str, slice] = MappingProxyType(slices)
        self.parameter_count = offset

        shared = {
            "W1": self.W1,
            "b1": self.b1,
            "W2": self.W2,
            "b2": self.b2,
        }
        self._sector_views = {
            sector: MappingProxyType({**shared, **self._heads[sector]})
            for sector in _SECTORS
        }

    @classmethod
    def initialize(
        cls,
        *,
        n_electrons: int,
        two_q: int,
        target_m2: int,
        width: int,
        layers: int = 2,
        seed: int,
        max_trainable_parameters: int = 262_144,
    ) -> AutoregressiveNQS:
        """Initialize a deterministic model after enforcing its capacity cap."""

        hidden_width = _integer("width", width)
        layer_count = _integer("layers", layers)
        random_seed = _integer("seed", seed)
        parameter_cap = _integer(
            "max_trainable_parameters",
            max_trainable_parameters,
        )
        if hidden_width <= 0:
            raise ValueError("width must be positive")
        if layer_count != 2:
            raise ValueError("AutoregressiveNQS requires exactly two hidden layers")
        if random_seed < 0:
            raise ValueError("seed must be non-negative")
        if parameter_cap < 0:
            raise ValueError("max_trainable_parameters must be non-negative")

        feasibility = FeasibilityTable.build(
            n_electrons=n_electrons,
            two_q=two_q,
            target_m2=target_m2,
        )
        input_size = feasibility.two_q + 1 + 3
        parameter_count = (
            hidden_width * input_size
            + hidden_width * hidden_width
            + 10 * hidden_width
            + 8
        )
        if parameter_count > parameter_cap:
            raise ValueError(
                f"trainable parameter count {parameter_count} exceeds parameter cap "
                f"{parameter_cap}"
            )

        rng = np.random.default_rng(random_seed)
        parameters: list[tuple[str, np.ndarray]] = []

        def random_array(shape: tuple[int, ...], scale: float) -> np.ndarray:
            return np.asarray(rng.normal(0.0, scale, size=shape), dtype=np.float64)

        parameters.extend(
            [
                (
                    "trunk.W1",
                    random_array(
                        (hidden_width, input_size),
                        1.0 / np.sqrt(input_size),
                    ),
                ),
                ("trunk.b1", np.zeros(hidden_width, dtype=np.float64)),
                (
                    "trunk.W2",
                    random_array(
                        (hidden_width, hidden_width),
                        1.0 / np.sqrt(hidden_width),
                    ),
                ),
                ("trunk.b2", np.zeros(hidden_width, dtype=np.float64)),
            ]
        )
        head_scale = 1.0 / np.sqrt(hidden_width)
        phase_scale = 0.1 / np.sqrt(hidden_width)
        for sector in _SECTORS:
            parameters.extend(
                [
                    (
                        f"{sector}.amplitude_W",
                        random_array((2, hidden_width), head_scale),
                    ),
                    (
                        f"{sector}.amplitude_b",
                        random_array((2,), head_scale),
                    ),
                    (
                        f"{sector}.phase_W",
                        random_array((2, hidden_width), phase_scale),
                    ),
                    (
                        f"{sector}.phase_b",
                        random_array((2,), phase_scale),
                    ),
                ]
            )
        return cls(
            feasibility=feasibility,
            width=hidden_width,
            parameters=tuple(parameters),
        )

    @staticmethod
    def _sector(sector: str) -> str:
        if sector not in _SECTORS:
            raise ValueError(f"sector must be one of {_SECTORS}")
        return sector

    def sector_parameters(self, sector: str) -> Mapping[str, np.ndarray]:
        """Return the identity-preserving parameter view for one sector."""

        return self._sector_views[self._sector(sector)]

    def trunk_parameter_ids(self, sector: str) -> tuple[int, int, int, int]:
        parameters = self.sector_parameters(sector)
        return tuple(id(parameters[name]) for name in ("W1", "b1", "W2", "b2"))

    def flat_parameters(self) -> np.ndarray:
        """Return a copy of parameters in the stable tree order."""

        return np.concatenate([array.reshape(-1) for _, array in self._parameter_items])

    def set_flat_parameters(self, values: np.ndarray) -> None:
        """Update parameter values in place without replacing shared arrays."""

        raw = np.asarray(values)
        if raw.shape != (self.parameter_count,):
            raise ValueError(
                f"flat parameters must have shape ({self.parameter_count},)"
            )
        if not np.issubdtype(raw.dtype, np.number) or np.iscomplexobj(raw):
            raise TypeError("flat parameters must be real numeric values")
        flat = np.asarray(raw, dtype=np.float64)
        if not np.all(np.isfinite(flat)):
            raise ValueError("flat parameters must be finite")
        for name, array in self._parameter_items:
            parameter_slice = self.parameter_slices[name]
            array[...] = flat[parameter_slice].reshape(array.shape)

    def _validated_state(self, state: int) -> int:
        configuration = _integer("state", state)
        if configuration < 0 or configuration >= 1 << self.n_orbitals:
            raise ValueError("state is outside the orbital range")
        if (
            configuration.bit_count() != self.n_electrons
            or occupation_m2(configuration, self.two_q) != self.target_m2
        ):
            raise ValueError("state is not in the fixed-N fixed-M2 sector")
        return configuration

    def _conditional(
        self,
        prefix: np.ndarray,
        orbital: int,
        remaining: int,
        remaining_m2: int,
        sector: str,
    ) -> tuple[np.ndarray, np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
        orbital_fraction = orbital / self.two_q if self.two_q else 0.0
        remaining_fraction = (
            remaining / self.n_electrons if self.n_electrons else 0.0
        )
        m2_scale = max(1, self.n_electrons * max(1, self.two_q))
        remaining_m2_fraction = remaining_m2 / m2_scale
        inputs = np.concatenate(
            (
                prefix,
                np.array(
                    [
                        orbital_fraction,
                        remaining_fraction,
                        remaining_m2_fraction,
                    ],
                    dtype=np.float64,
                ),
            )
        )
        hidden1 = np.tanh(self.W1 @ inputs + self.b1)
        hidden2 = np.tanh(self.W2 @ hidden1 + self.b2)
        heads = self._heads[sector]
        logits = heads["amplitude_W"] @ hidden2 + heads["amplitude_b"]
        phases = heads["phase_W"] @ hidden2 + heads["phase_b"]

        allowed = np.asarray(
            self.feasibility.allowed(orbital, remaining, remaining_m2),
            dtype=bool,
        )
        allowed_logits = logits[allowed]
        if allowed_logits.size == 0:
            raise RuntimeError("feasibility table has no valid continuation")
        log_probabilities = np.full(2, -np.inf, dtype=np.float64)
        log_probabilities[allowed] = allowed_logits - logsumexp(allowed_logits)
        probabilities = np.zeros(2, dtype=np.float64)
        probabilities[allowed] = np.exp(log_probabilities[allowed])
        return (
            log_probabilities,
            phases,
            (inputs, hidden1, hidden2, probabilities),
        )

    def _evaluate(
        self,
        state: int,
        sector: str,
        *,
        keep_cache: bool,
    ) -> tuple[complex, list[tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]]:
        configuration = self._validated_state(state)
        selected_sector = self._sector(sector)
        prefix = np.full(self.n_orbitals, -1.0, dtype=np.float64)
        remaining = self.n_electrons
        remaining_m2 = self.target_m2
        log_amplitude = 0.0
        phase = 0.0
        caches: list[
            tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]
        ] = []
        for orbital in range(self.n_orbitals):
            selected = (configuration >> orbital) & 1
            log_probabilities, phases, cache = self._conditional(
                prefix,
                orbital,
                remaining,
                remaining_m2,
                selected_sector,
            )
            if not np.isfinite(log_probabilities[selected]):
                raise ValueError("state is not in the fixed-N fixed-M2 sector")
            log_amplitude += 0.5 * float(log_probabilities[selected])
            phase += float(phases[selected])
            if keep_cache:
                inputs, hidden1, hidden2, probabilities = cache
                caches.append(
                    (selected, inputs, hidden1, hidden2, probabilities)
                )
            prefix[orbital] = selected
            if selected:
                remaining -= 1
                remaining_m2 -= -self.two_q + 2 * orbital
        if remaining != 0 or remaining_m2 != 0:
            raise ValueError("state is not in the fixed-N fixed-M2 sector")
        return complex(log_amplitude, phase), caches

    def logpsi(self, state: int, sector: str) -> complex:
        """Return the exactly normalized autoregressive log-wavefunction."""

        value, _ = self._evaluate(state, sector, keep_cache=False)
        return value

    def log_derivative(self, state: int, sector: str) -> np.ndarray:
        """Return analytic complex derivatives in stable flat-tree order."""

        selected_sector = self._sector(sector)
        _, caches = self._evaluate(state, selected_sector, keep_cache=True)
        gradients = {
            name: np.zeros(array.shape, dtype=np.complex128)
            for name, array in self._parameter_items
        }
        heads = self._heads[selected_sector]
        for selected, inputs, hidden1, hidden2, probabilities in caches:
            logit_gradient = -0.5 * probabilities.astype(np.complex128)
            logit_gradient[selected] += 0.5
            phase_gradient = np.zeros(2, dtype=np.complex128)
            phase_gradient[selected] = 1.0j

            gradients[f"{selected_sector}.amplitude_W"] += np.outer(
                logit_gradient,
                hidden2,
            )
            gradients[f"{selected_sector}.amplitude_b"] += logit_gradient
            gradients[f"{selected_sector}.phase_W"] += np.outer(
                phase_gradient,
                hidden2,
            )
            gradients[f"{selected_sector}.phase_b"] += phase_gradient

            hidden2_gradient = (
                heads["amplitude_W"].T @ logit_gradient
                + heads["phase_W"].T @ phase_gradient
            )
            preactivation2_gradient = hidden2_gradient * (1.0 - hidden2**2)
            gradients["trunk.W2"] += np.outer(
                preactivation2_gradient,
                hidden1,
            )
            gradients["trunk.b2"] += preactivation2_gradient

            hidden1_gradient = self.W2.T @ preactivation2_gradient
            preactivation1_gradient = hidden1_gradient * (1.0 - hidden1**2)
            gradients["trunk.W1"] += np.outer(
                preactivation1_gradient,
                inputs,
            )
            gradients["trunk.b1"] += preactivation1_gradient

        return np.concatenate(
            [gradients[name].reshape(-1) for name, _ in self._parameter_items]
        )

    def sample(self, size: int, sector: str, *, seed: int) -> np.ndarray:
        """Sample sequentially from masked conditionals without support expansion."""

        sample_count = _integer("size", size)
        random_seed = _integer("seed", seed)
        selected_sector = self._sector(sector)
        if sample_count < 0:
            raise ValueError("size must be non-negative")
        if random_seed < 0:
            raise ValueError("seed must be non-negative")

        rng = np.random.default_rng(random_seed)
        draws = np.empty(sample_count, dtype=object)
        for draw_index in range(sample_count):
            prefix = np.full(self.n_orbitals, -1.0, dtype=np.float64)
            remaining = self.n_electrons
            remaining_m2 = self.target_m2
            state = 0
            for orbital in range(self.n_orbitals):
                log_probabilities, _, _ = self._conditional(
                    prefix,
                    orbital,
                    remaining,
                    remaining_m2,
                    selected_sector,
                )
                if np.isneginf(log_probabilities[0]):
                    selected = 1
                elif np.isneginf(log_probabilities[1]):
                    selected = 0
                else:
                    selected = int(rng.random() >= np.exp(log_probabilities[0]))
                prefix[orbital] = selected
                if selected:
                    state |= 1 << orbital
                    remaining -= 1
                    remaining_m2 -= -self.two_q + 2 * orbital
            if remaining != 0 or remaining_m2 != 0:
                raise RuntimeError("autoregressive sampler left the constrained sector")
            draws[draw_index] = state
        return draws
