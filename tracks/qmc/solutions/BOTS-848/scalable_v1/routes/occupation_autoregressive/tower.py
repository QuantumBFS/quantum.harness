"""Sparse log-domain construction of the ladder-derived spin-two tower."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from numbers import Integral
from types import MappingProxyType

import numpy as np

from .constraints import FeasibilityTable, occupation_m2
from .operators import ladder_neighbors, local_from_log_neighbors


LogAmplitude = Callable[[int], complex]
LogScore = Callable[[int], np.ndarray]
_SPIN_TWO_M_VALUES = (-2, -1, 0, 1, 2)


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    return int(value)


def _scalar_complex(raw_value: object, *, label: str) -> complex:
    value_array = np.asarray(raw_value)
    if value_array.shape != ():
        raise TypeError(f"{label} must be a scalar")
    try:
        value = complex(value_array.item())
    except (TypeError, ValueError) as error:
        raise TypeError(f"{label} must be numeric") from error
    if value.real == -math.inf and math.isfinite(value.imag):
        return value
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError(
            f"{label} must have a finite log-magnitude and phase or "
            "represent an exact zero"
        )
    return value


def _score_vector(raw_value: object, *, label: str) -> np.ndarray:
    raw = np.asarray(raw_value)
    if raw.ndim != 1:
        raise ValueError(f"{label} must be a one-dimensional vector")
    try:
        score = np.asarray(raw, dtype=np.complex128)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{label} must contain numeric values") from error
    if not np.all(np.isfinite(score.real)) or not np.all(
        np.isfinite(score.imag)
    ):
        raise ValueError(f"{label} must contain only finite values")
    return score


def _log_of_complex(value: complex) -> complex:
    if value == 0.0:
        return complex(-math.inf, 0.0)
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise FloatingPointError("derived ladder amplitude is non-finite")
    return complex(math.log(abs(value)), math.atan2(value.imag, value.real))


def _phase_factor(phase: float) -> complex:
    reduced = math.remainder(phase, 2.0 * math.pi)
    if reduced == 0.0:
        return 1.0 + 0.0j
    if abs(reduced) == math.pi:
        return -1.0 + 0.0j
    if reduced == math.pi / 2.0:
        return 0.0 + 1.0j
    if reduced == -math.pi / 2.0:
        return 0.0 - 1.0j
    return complex(math.cos(reduced), math.sin(reduced))


def spin2_ladder_coefficient(source_m: int, direction: int) -> float:
    """Return the analytic ``L=2`` ladder coefficient from ``source_m``."""

    m = _integer("source_m", source_m)
    step = _integer("direction", direction)
    if step not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    if m not in _SPIN_TWO_M_VALUES:
        raise ValueError("source_m must be in [-2, 2]")
    if step == 1 and m == 2:
        raise ValueError("cannot raise from M=2")
    if step == -1 and m == -2:
        raise ValueError("cannot lower from M=-2")
    return math.sqrt(2 * (2 + 1) - m * (m + step))


@dataclass(frozen=True, slots=True)
class _DerivedTerms:
    parent_logs: Mapping[int, complex]
    inverse_neighbors: Mapping[int, complex]
    shift: float
    scaled_sum: complex


@dataclass(frozen=True, slots=True)
class LadderComponent:
    """One fixed-``M`` component of a lazily evaluated spin-two tower."""

    m: int
    l: int
    n_electrons: int
    two_q: int
    _base_logpsi: LogAmplitude | None
    _base_log_score: LogScore | None
    _parent: LadderComponent | None
    _direction: int | None

    def _validated_state(self, state: object) -> int:
        configuration = _integer("state", state)
        if configuration < 0 or configuration >= 1 << (self.two_q + 1):
            raise ValueError("state is outside the orbital range")
        if (
            configuration.bit_count() != self.n_electrons
            or occupation_m2(configuration, self.two_q) != 2 * self.m
        ):
            raise ValueError("state is not in the fixed-N fixed-M sector")
        return configuration

    def _derived_terms(self, state: int) -> _DerivedTerms:
        parent = self._parent
        direction = self._direction
        if parent is None or direction is None:
            raise AssertionError("base component has no derived terms")

        inverse = ladder_neighbors(
            state,
            self.two_q,
            direction=-direction,
        )
        parent_logs: dict[int, complex] = {}
        active_neighbors: dict[int, complex] = {}
        for source, coefficient in inverse.items():
            parent_log = _scalar_complex(
                parent.logpsi(source),
                label="parent logpsi",
            )
            if parent_log.real == -math.inf:
                continue
            parent_logs[source] = parent_log
            active_neighbors[source] = coefficient * _phase_factor(
                parent_log.imag
            )

        shift = max(
            (value.real for value in parent_logs.values()),
            default=0.0,
        )

        def shifted_parent_logpsi(configuration: int) -> complex:
            if configuration == state:
                return complex(shift, 0.0)
            return complex(parent_logs[configuration].real, 0.0)

        scaled_sum = local_from_log_neighbors(
            state,
            active_neighbors,
            shifted_parent_logpsi,
        )
        return _DerivedTerms(
            parent_logs=MappingProxyType(parent_logs),
            inverse_neighbors=MappingProxyType(active_neighbors),
            shift=shift,
            scaled_sum=scaled_sum,
        )

    def logpsi(self, state: int) -> complex:
        """Evaluate this component without expanding a fixed-``M`` support."""

        configuration = self._validated_state(state)
        if self.m == 0:
            if self._base_logpsi is None:
                raise AssertionError("M=0 component is missing its callback")
            return _scalar_complex(
                self._base_logpsi(configuration),
                label="base logpsi",
            )

        terms = self._derived_terms(configuration)
        if terms.scaled_sum == 0.0:
            return complex(-math.inf, 0.0)
        if self._parent is None or self._direction is None:
            raise AssertionError("derived component is missing its parent")
        normalization = spin2_ladder_coefficient(
            self._parent.m,
            self._direction,
        )
        scaled_log = _log_of_complex(terms.scaled_sum)
        return complex(
            scaled_log.real + terms.shift - math.log(normalization),
            scaled_log.imag,
        )

    def log_score(self, state: int) -> np.ndarray:
        """Return the analytic parameter derivative of this log amplitude."""

        configuration = self._validated_state(state)
        if self.m == 0:
            if self._base_log_score is None:
                raise AssertionError("M=0 component is missing its score callback")
            return _score_vector(
                self._base_log_score(configuration),
                label="base log score",
            )

        terms = self._derived_terms(configuration)
        if terms.scaled_sum == 0.0:
            raise ValueError("log score is undefined for an exact zero amplitude")
        if self._parent is None:
            raise AssertionError("derived component is missing its parent")

        scores: list[np.ndarray] = []
        weights: list[complex] = []
        parameter_count: int | None = None
        for source, coefficient in terms.inverse_neighbors.items():
            score = _score_vector(
                self._parent.log_score(source),
                label="parent log score",
            )
            if parameter_count is None:
                parameter_count = score.size
            elif score.size != parameter_count:
                raise ValueError(
                    "parent log scores must have the same parameter count"
                )
            parent_log = terms.parent_logs[source]
            term = coefficient * math.exp(parent_log.real - terms.shift)
            weights.append(term / terms.scaled_sum)
            scores.append(score)

        if not scores:
            raise AssertionError("nonzero derived amplitude has no source terms")
        result = np.sum(
            np.asarray(weights, dtype=np.complex128)[:, None]
            * np.stack(scores, axis=0),
            axis=0,
        )
        if not np.all(np.isfinite(result.real)) or not np.all(
            np.isfinite(result.imag)
        ):
            raise FloatingPointError("derived log score is non-finite")
        return result


class LadderTower(Mapping[int, LadderComponent]):
    """Read-only mapping of ``M=-2,-1,0,1,2`` ladder components."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("LadderTower instances must be created with from_m0()")

    @classmethod
    def from_m0(
        cls,
        *,
        logpsi: LogAmplitude,
        log_score: LogScore,
        n_electrons: int,
        two_q: int,
        l: int = 2,
    ) -> LadderTower:
        """Build the five components from one reduced ``M=0`` callback pair."""

        if not callable(logpsi):
            raise TypeError("logpsi must be callable")
        if not callable(log_score):
            raise TypeError("log_score must be callable")
        angular_momentum = _integer("l", l)
        if angular_momentum != 2:
            raise ValueError("l must be 2")

        tables = {
            m: FeasibilityTable.build(
                n_electrons=n_electrons,
                two_q=two_q,
                target_m2=2 * m,
            )
            for m in _SPIN_TWO_M_VALUES
        }
        base_table = tables[0]
        components: dict[int, LadderComponent] = {
            0: LadderComponent(
                m=0,
                l=angular_momentum,
                n_electrons=base_table.n_electrons,
                two_q=base_table.two_q,
                _base_logpsi=logpsi,
                _base_log_score=log_score,
                _parent=None,
                _direction=None,
            )
        }
        for direction in (1, -1):
            parent = components[0]
            for _step in range(2):
                target_m = parent.m + direction
                table = tables[target_m]
                component = LadderComponent(
                    m=target_m,
                    l=angular_momentum,
                    n_electrons=table.n_electrons,
                    two_q=table.two_q,
                    _base_logpsi=None,
                    _base_log_score=None,
                    _parent=parent,
                    _direction=direction,
                )
                components[target_m] = component
                parent = component

        instance = object.__new__(cls)
        instance._components = MappingProxyType(
            {m: components[m] for m in _SPIN_TWO_M_VALUES}
        )
        return instance

    def component(self, target_m: int) -> LadderComponent:
        """Return one component with a clear fail-closed target error."""

        m = _integer("target_m", target_m)
        if m not in _SPIN_TWO_M_VALUES:
            raise ValueError("target_m must be in [-2, 2]")
        return self._components[m]

    def __getitem__(self, target_m: int) -> LadderComponent:
        return self.component(target_m)

    def __iter__(self) -> Iterator[int]:
        return iter(_SPIN_TWO_M_VALUES)

    def __len__(self) -> int:
        return len(_SPIN_TWO_M_VALUES)
