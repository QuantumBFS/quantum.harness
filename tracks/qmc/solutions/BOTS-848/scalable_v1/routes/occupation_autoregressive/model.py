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
        self._parameters: Mapping[str, np.ndarray] = MappingProxyType(by_name)
        self._parameter_names = tuple(name for name, _ in parameters)

        offset = 0
        slices: dict[str, slice] = {}
        for name, array in parameters:
            slices[name] = slice(offset, offset + array.size)
            offset += array.size
        self.parameter_slices: Mapping[str, slice] = MappingProxyType(slices)
        self.parameter_count = offset

        public_views = {
            name: self._readonly_view(array)
            for name, array in parameters
        }
        self._public_parameter_views: Mapping[str, np.ndarray] = MappingProxyType(
            public_views
        )
        shared = {
            "W1": public_views["trunk.W1"],
            "b1": public_views["trunk.b1"],
            "W2": public_views["trunk.W2"],
            "b2": public_views["trunk.b2"],
        }
        self._sector_views = {
            sector: MappingProxyType(
                {
                    **shared,
                    **{
                        name: public_views[f"{sector}.{name}"]
                        for name in (
                            "amplitude_W",
                            "amplitude_b",
                            "phase_W",
                            "phase_b",
                        )
                    },
                }
            )
            for sector in _SECTORS
        }
        self._logpsi_cache: dict[tuple[int, str], complex] = {}
        self._log_derivative_cache: dict[tuple[int, str], np.ndarray] = {}
        self._parameter_revision = 0

    @staticmethod
    def _readonly_view(array: np.ndarray) -> np.ndarray:
        buffer = memoryview(array).toreadonly()
        view = np.frombuffer(buffer, dtype=array.dtype, count=array.size).reshape(
            array.shape
        )
        view.setflags(write=False)
        return view

    def _parameter(self, name: str) -> np.ndarray:
        """Resolve one parameter from the sole authoritative parameter tree."""

        return self._parameters[name]

    @property
    def W1(self) -> np.ndarray:
        return self._public_parameter_views["trunk.W1"]

    @property
    def b1(self) -> np.ndarray:
        return self._public_parameter_views["trunk.b1"]

    @property
    def W2(self) -> np.ndarray:
        return self._public_parameter_views["trunk.W2"]

    @property
    def b2(self) -> np.ndarray:
        return self._public_parameter_views["trunk.b2"]

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

        return np.concatenate(
            [self._parameters[name].reshape(-1) for name in self._parameter_names]
        )

    @property
    def parameter_revision(self) -> int:
        """Return the monotonic cache token for the current parameter values."""

        return self._parameter_revision

    def clear_evaluation_cache(self) -> None:
        """Discard cached log-wavefunctions and log-derivatives."""

        self._logpsi_cache.clear()
        self._log_derivative_cache.clear()

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
        for name in self._parameter_names:
            array = self._parameters[name]
            parameter_slice = self.parameter_slices[name]
            array[...] = flat[parameter_slice].reshape(array.shape)
        self._logpsi_cache.clear()
        self._log_derivative_cache.clear()
        self._parameter_revision += 1

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

    @staticmethod
    def _require_finite_conditional(stage: str, *values: np.ndarray) -> None:
        if any(not np.all(np.isfinite(value)) for value in values):
            raise FloatingPointError(
                f"non-finite autoregressive conditional values at {stage}"
            )

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
        with np.errstate(over="ignore", invalid="ignore"):
            preactivation1 = (
                self._parameters["trunk.W1"] @ inputs
                + self._parameters["trunk.b1"]
            )
            hidden1 = np.tanh(preactivation1)
            preactivation2 = (
                self._parameters["trunk.W2"] @ hidden1
                + self._parameters["trunk.b2"]
            )
            hidden2 = np.tanh(preactivation2)
            logits = (
                self._parameter(f"{sector}.amplitude_W") @ hidden2
                + self._parameter(f"{sector}.amplitude_b")
            )
            phases = (
                self._parameter(f"{sector}.phase_W") @ hidden2
                + self._parameter(f"{sector}.phase_b")
            )
        self._require_finite_conditional(
            "scalar network evaluation",
            preactivation1,
            hidden1,
            preactivation2,
            hidden2,
            logits,
            phases,
        )

        allowed = np.asarray(
            self.feasibility.allowed(orbital, remaining, remaining_m2),
            dtype=bool,
        )
        allowed_logits = logits[allowed]
        if allowed_logits.size == 0:
            raise RuntimeError("feasibility table has no valid continuation")
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            log_probabilities = np.full(2, -np.inf, dtype=np.float64)
            log_probabilities[allowed] = allowed_logits - logsumexp(
                allowed_logits
            )
            probabilities = np.zeros(2, dtype=np.float64)
            probabilities[allowed] = np.exp(log_probabilities[allowed])
            probability_mass = float(np.sum(probabilities[allowed]))
        if (
            not np.all(np.isfinite(log_probabilities[allowed]))
            or not np.all(np.isfinite(probabilities[allowed]))
            or not np.isfinite(probability_mass)
            or abs(probability_mass - 1.0) > 1.0e-12
        ):
            raise FloatingPointError(
                "non-finite autoregressive conditional probabilities"
            )
        return (
            log_probabilities,
            phases,
            (inputs, hidden1, hidden2, probabilities),
        )

    def _conditional_batch(
        self,
        prefixes: np.ndarray,
        orbital: int,
        remaining: np.ndarray,
        remaining_m2: np.ndarray,
        sector: str,
    ) -> np.ndarray:
        """Return phase-free masked log probabilities for a full sample batch."""

        batch_size = prefixes.shape[0]
        if prefixes.shape != (batch_size, self.n_orbitals):
            raise ValueError("batched prefixes have the wrong shape")
        if remaining.shape != (batch_size,) or remaining_m2.shape != (batch_size,):
            raise ValueError("batched remaining contexts have the wrong shape")

        orbital_fraction = orbital / self.two_q if self.two_q else 0.0
        if self.n_electrons:
            remaining_fraction = remaining / self.n_electrons
        else:
            remaining_fraction = np.zeros(batch_size, dtype=np.float64)
        m2_scale = max(1, self.n_electrons * max(1, self.two_q))
        contexts = np.column_stack(
            (
                np.full(batch_size, orbital_fraction, dtype=np.float64),
                remaining_fraction,
                remaining_m2 / m2_scale,
            )
        )
        inputs = np.concatenate((prefixes, contexts), axis=1)
        amplitude_W = self._parameter(f"{sector}.amplitude_W")
        amplitude_b = self._parameter(f"{sector}.amplitude_b")
        with np.errstate(over="ignore", invalid="ignore"):
            preactivation1 = (
                inputs @ self._parameters["trunk.W1"].T
                + self._parameters["trunk.b1"]
            )
            hidden1 = np.tanh(preactivation1)
            preactivation2 = (
                hidden1 @ self._parameters["trunk.W2"].T
                + self._parameters["trunk.b2"]
            )
            hidden2 = np.tanh(preactivation2)
            logits = (
                hidden2 @ amplitude_W.T
                + amplitude_b
            )
        self._require_finite_conditional(
            "batched network evaluation",
            preactivation1,
            hidden1,
            preactivation2,
            hidden2,
            logits,
        )

        allowed = np.asarray(
            [
                self.feasibility.allowed(
                    orbital,
                    int(particles_left),
                    int(m2_left),
                )
                for particles_left, m2_left in zip(
                    remaining,
                    remaining_m2,
                    strict=True,
                )
            ],
            dtype=bool,
        )
        if np.any(~np.any(allowed, axis=1)):
            raise RuntimeError("feasibility table has no valid continuation")
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            masked_logits = np.where(allowed, logits, -np.inf)
            log_probabilities = masked_logits - logsumexp(
                masked_logits,
                axis=1,
            )[:, None]
            probabilities = np.zeros_like(log_probabilities)
            probabilities[allowed] = np.exp(log_probabilities[allowed])
            probability_mass = np.sum(probabilities, axis=1)
        if (
            not np.all(np.isfinite(log_probabilities[allowed]))
            or not np.all(np.isfinite(probabilities[allowed]))
            or not np.all(np.isfinite(probability_mass))
            or np.any(np.abs(probability_mass - 1.0) > 1.0e-12)
        ):
            raise FloatingPointError(
                "non-finite autoregressive conditional probabilities"
            )
        return log_probabilities

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
            with np.errstate(over="ignore", invalid="ignore"):
                log_amplitude += 0.5 * float(log_probabilities[selected])
            if not np.isfinite(log_amplitude):
                raise FloatingPointError(
                    "non-finite cumulative autoregressive log-amplitude"
                )
            with np.errstate(over="ignore", invalid="ignore"):
                phase += float(phases[selected])
            if not np.isfinite(phase):
                raise FloatingPointError(
                    "non-finite cumulative autoregressive phase"
                )
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

        configuration = self._validated_state(state)
        selected_sector = self._sector(sector)
        key = (configuration, selected_sector)
        cached = self._logpsi_cache.get(key)
        if cached is not None:
            return cached
        value, _ = self._evaluate(
            configuration,
            selected_sector,
            keep_cache=False,
        )
        self._logpsi_cache[key] = value
        return value

    def log_derivative(self, state: int, sector: str) -> np.ndarray:
        """Return analytic complex derivatives in stable flat-tree order."""

        configuration = self._validated_state(state)
        selected_sector = self._sector(sector)
        key = (configuration, selected_sector)
        cached = self._log_derivative_cache.get(key)
        if cached is not None:
            return cached.copy()
        _, caches = self._evaluate(
            configuration,
            selected_sector,
            keep_cache=True,
        )
        gradients = {
            name: np.zeros(self._parameters[name].shape, dtype=np.complex128)
            for name in self._parameter_names
        }
        amplitude_W = self._parameter(f"{selected_sector}.amplitude_W")
        phase_W = self._parameter(f"{selected_sector}.phase_W")
        with np.errstate(over="ignore", invalid="ignore"):
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
                    amplitude_W.T @ logit_gradient
                    + phase_W.T @ phase_gradient
                )
                preactivation2_gradient = hidden2_gradient * (1.0 - hidden2**2)
                gradients["trunk.W2"] += np.outer(
                    preactivation2_gradient,
                    hidden1,
                )
                gradients["trunk.b2"] += preactivation2_gradient

                hidden1_gradient = (
                    self._parameters["trunk.W2"].T @ preactivation2_gradient
                )
                preactivation1_gradient = hidden1_gradient * (1.0 - hidden1**2)
                gradients["trunk.W1"] += np.outer(
                    preactivation1_gradient,
                    inputs,
                )
                gradients["trunk.b1"] += preactivation1_gradient

        flattened = np.concatenate(
            [gradients[name].reshape(-1) for name in self._parameter_names]
        )
        if (
            not np.all(np.isfinite(flattened.real))
            or not np.all(np.isfinite(flattened.imag))
        ):
            raise FloatingPointError("non-finite autoregressive log-derivative")
        cached_score = flattened.copy()
        cached_score.setflags(write=False)
        self._log_derivative_cache[key] = cached_score
        return cached_score.copy()

    def sample(self, size: int, sector: str, *, seed: int) -> np.ndarray:
        """Sample sequentially from masked conditionals without support expansion."""

        sample_count = _integer("size", size)
        random_seed = _integer("seed", seed)
        selected_sector = self._sector(sector)
        if sample_count < 0:
            raise ValueError("size must be non-negative")
        if random_seed < 0:
            raise ValueError("seed must be non-negative")

        draws = np.zeros(sample_count, dtype=object)
        if sample_count == 0:
            return draws

        rng = np.random.default_rng(random_seed)
        prefixes = np.full(
            (sample_count, self.n_orbitals),
            -1.0,
            dtype=np.float64,
        )
        remaining = np.full(sample_count, self.n_electrons, dtype=np.int64)
        remaining_m2 = np.full(sample_count, self.target_m2, dtype=np.int64)
        for orbital in range(self.n_orbitals):
            log_probabilities = self._conditional_batch(
                prefixes,
                orbital,
                remaining,
                remaining_m2,
                selected_sector,
            )
            zero_forbidden = np.isneginf(log_probabilities[:, 0])
            one_forbidden = np.isneginf(log_probabilities[:, 1])
            selected = np.empty(sample_count, dtype=np.int8)
            selected[zero_forbidden] = 1
            selected[one_forbidden] = 0
            stochastic = ~(zero_forbidden | one_forbidden)
            stochastic_count = int(np.count_nonzero(stochastic))
            if stochastic_count:
                selected[stochastic] = (
                    rng.random(stochastic_count)
                    >= np.exp(log_probabilities[stochastic, 0])
                )
            prefixes[:, orbital] = selected
            occupied = np.flatnonzero(selected)
            orbital_bit = 1 << orbital
            for draw_index in occupied:
                draws[draw_index] = int(draws[draw_index]) | orbital_bit
            remaining -= selected
            remaining_m2 -= selected * (-self.two_q + 2 * orbital)
        if np.any(remaining != 0) or np.any(remaining_m2 != 0):
            raise RuntimeError("autoregressive sampler left the constrained sector")
        return draws
