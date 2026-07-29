"""Sparse log-domain construction of the ladder-derived spin-two tower."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from numbers import Integral
from types import MappingProxyType

import numpy as np

from .constraints import FeasibilityTable, occupation_m2
from .operators import ladder_neighbors


LogAmplitude = Callable[[int], complex]
LogScore = Callable[[int], np.ndarray]
_SPIN_TWO_M_VALUES = (-2, -1, 0, 1, 2)
_LOG_COMPLEX128_MAX = math.log(np.finfo(np.float64).max)


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
    with np.errstate(over="ignore", invalid="ignore"):
        magnitudes = np.hypot(score.real, score.imag)
    if not np.all(np.isfinite(magnitudes)):
        raise FloatingPointError(
            f"{label} magnitude is outside complex128 range"
        )
    return score


def _phase_factor(phase: float) -> complex:
    reduced = math.remainder(phase, 2.0 * math.pi)
    quadrant = int(round(reduced / (math.pi / 2.0)))
    snapped = quadrant * (math.pi / 2.0)
    if reduced == snapped:
        axial = quadrant % 4
        if axial == 0:
            return 1.0 + 0.0j
        if axial == 1:
            return 0.0 + 1.0j
        if axial == 2:
            return -1.0 + 0.0j
        return 0.0 - 1.0j
    return complex(math.cos(reduced), math.sin(reduced))


def _normalized_phase(*parts: float) -> float:
    reduced = [math.remainder(part, 2.0 * math.pi) for part in parts]
    return math.remainder(math.fsum(reduced), 2.0 * math.pi)


@dataclass(frozen=True, slots=True)
class _LogTerm:
    source: int
    log_abs: float
    parent_phase: float
    coefficient_phase: float


@dataclass(frozen=True, slots=True)
class _LogPolar:
    log_abs: float
    phase: float


def _relative_phase_factor(term: _LogTerm, reference: _LogTerm) -> complex:
    return _phase_factor(
        _normalized_phase(
            term.parent_phase,
            term.coefficient_phase,
            -reference.parent_phase,
            -reference.coefficient_phase,
        )
    )


def _collapse_equal_log_bands(
    entries: list[tuple[float, complex]],
) -> list[tuple[float, complex]]:
    active = entries
    for _iteration in range(len(entries) + 1):
        grouped: dict[float, list[complex]] = {}
        for log_abs, unit_phase in active:
            grouped.setdefault(log_abs, []).append(unit_phase)
        collapsed: list[tuple[float, complex]] = []
        merged = False
        for log_abs, phases in grouped.items():
            merged = merged or len(phases) > 1
            summed = complex(
                math.fsum(value.real for value in phases),
                math.fsum(value.imag for value in phases),
            )
            if summed == 0.0:
                continue
            magnitude = abs(summed)
            collapsed.append(
                (
                    math.fsum((log_abs, math.log(magnitude))),
                    summed / magnitude,
                )
            )
        active = collapsed
        if not merged:
            return active
    raise AssertionError("log-band collapse did not converge")


def _reduce_log_terms(terms: tuple[_LogTerm, ...]) -> _LogPolar | None:
    if not terms:
        return None
    reference = terms[0]
    entries = _collapse_equal_log_bands(
        [
            (term.log_abs, _relative_phase_factor(term, reference))
            for term in terms
        ]
    )
    if not entries:
        return None
    shift = max(log_abs for log_abs, _unit_phase in entries)
    scaled = complex(
        math.fsum(
            math.exp(log_abs - shift) * unit_phase.real
            for log_abs, unit_phase in entries
        ),
        math.fsum(
            math.exp(log_abs - shift) * unit_phase.imag
            for log_abs, unit_phase in entries
        ),
    )
    if scaled == 0.0:
        return None
    log_abs = math.fsum((shift, math.log(abs(scaled))))
    if not math.isfinite(log_abs):
        raise FloatingPointError("derived ladder log-magnitude is non-finite")
    return _LogPolar(
        log_abs=log_abs,
        phase=_normalized_phase(
            reference.parent_phase,
            reference.coefficient_phase,
            math.atan2(scaled.imag, scaled.real),
        ),
    )


def _neumaier_sum_rows(values: np.ndarray) -> np.ndarray:
    if values.ndim != 2:
        raise AssertionError("Neumaier input must be two-dimensional")
    total = np.zeros(values.shape[1], dtype=np.float64)
    correction = np.zeros_like(total)
    for row in values:
        updated = total + row
        correction += np.where(
            np.abs(total) >= np.abs(row),
            (total - updated) + row,
            (row - updated) + total,
        )
        total = updated
    result = total + correction
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("derived log score sum is non-finite")
    return result


def _neumaier_complex_sum_rows(values: np.ndarray) -> np.ndarray:
    return _neumaier_sum_rows(values.real) + 1.0j * _neumaier_sum_rows(
        values.imag
    )


def _collapse_equal_score_log_bands(
    raw_logs: np.ndarray,
    normalized_logs: np.ndarray,
    unit_phases: np.ndarray,
    active: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    band_count, parameter_count = raw_logs.shape
    for _iteration in range(band_count + 1):
        next_raw_logs = np.full_like(raw_logs, -math.inf)
        next_normalized_logs = np.full_like(normalized_logs, -math.inf)
        next_unit_phases = np.zeros_like(unit_phases)
        next_active = np.zeros_like(active)
        merged = False
        for band_index in range(band_count):
            if band_index == 0:
                already_led = np.zeros(parameter_count, dtype=np.bool_)
            else:
                already_led = np.any(
                    active[:band_index]
                    & (
                        raw_logs[:band_index]
                        == raw_logs[band_index][None, :]
                    ),
                    axis=0,
                )
            leader = active[band_index] & ~already_led
            if not np.any(leader):
                continue
            same_band = (
                active
                & leader[None, :]
                & (raw_logs == raw_logs[band_index][None, :])
            )
            multiplicity = np.sum(same_band, axis=0)
            if np.any(multiplicity > 1):
                merged = True
            selected_phases = np.where(
                same_band,
                unit_phases,
                0.0j,
            )
            summed = _neumaier_complex_sum_rows(selected_phases)
            magnitudes = np.hypot(summed.real, summed.imag)
            if not np.all(np.isfinite(magnitudes)):
                raise FloatingPointError(
                    "derived log score band is non-finite"
                )
            nonzero = leader & (magnitudes > 0.0)
            if not np.any(nonzero):
                continue
            log_magnitudes = np.log(magnitudes[nonzero])
            collapsed_raw = (
                raw_logs[band_index, nonzero] + log_magnitudes
            )
            collapsed_normalized = (
                normalized_logs[band_index, nonzero] + log_magnitudes
            )
            if not np.all(np.isfinite(collapsed_raw)) or not np.all(
                np.isfinite(collapsed_normalized)
            ):
                raise FloatingPointError(
                    "derived log score band is non-finite"
                )
            next_raw_logs[band_index, nonzero] = collapsed_raw
            next_normalized_logs[band_index, nonzero] = (
                collapsed_normalized
            )
            next_unit_phases[band_index, nonzero] = (
                summed[nonzero] / magnitudes[nonzero]
            )
            next_active[band_index, nonzero] = True
        raw_logs = next_raw_logs
        normalized_logs = next_normalized_logs
        unit_phases = next_unit_phases
        active = next_active
        if not merged:
            return raw_logs, normalized_logs, unit_phases, active
    raise AssertionError("score log-band collapse did not converge")


def _score_ratio_from_log_terms(
    terms: tuple[_LogTerm, ...],
    scores: tuple[np.ndarray, ...],
    denominator: _LogPolar,
) -> np.ndarray:
    if len(terms) != len(scores):
        raise AssertionError("derived terms and scores must align")
    if not scores:
        raise AssertionError("nonzero derived amplitude has no source scores")
    parameter_count = scores[0].size
    if parameter_count == 0:
        return np.empty(0, dtype=np.complex128)

    reference = terms[0]
    band_count = len(terms)
    raw_logs = np.full(
        (band_count, parameter_count),
        -math.inf,
        dtype=np.float64,
    )
    normalized_logs = np.full_like(raw_logs, -math.inf)
    unit_phases = np.zeros(
        (band_count, parameter_count),
        dtype=np.complex128,
    )
    active = np.zeros((band_count, parameter_count), dtype=np.bool_)
    for band_index, (term, score) in enumerate(
        zip(terms, scores, strict=True)
    ):
        magnitudes = np.hypot(score.real, score.imag)
        nonzero_score = magnitudes > 0.0
        if not np.any(nonzero_score):
            continue
        log_score_magnitudes = np.log(magnitudes[nonzero_score])
        raw = term.log_abs + log_score_magnitudes
        term_relative_log = math.fsum(
            (term.log_abs, -denominator.log_abs)
        )
        normalized = term_relative_log + log_score_magnitudes
        phase = (
            _relative_phase_factor(term, reference)
            * (score[nonzero_score] / magnitudes[nonzero_score])
        )
        if (
            not np.all(np.isfinite(raw))
            or not np.all(np.isfinite(normalized))
            or not np.all(np.isfinite(phase.real))
            or not np.all(np.isfinite(phase.imag))
        ):
            raise FloatingPointError(
                "derived log score term is non-finite"
            )
        raw_logs[band_index, nonzero_score] = raw
        normalized_logs[band_index, nonzero_score] = normalized
        unit_phases[band_index, nonzero_score] = phase
        active[band_index, nonzero_score] = True

    raw_logs, normalized_logs, unit_phases, active = (
        _collapse_equal_score_log_bands(
            raw_logs,
            normalized_logs,
            unit_phases,
            active,
        )
    )
    has_numerator = np.any(active, axis=0)
    result = np.zeros(parameter_count, dtype=np.complex128)
    if not np.any(has_numerator):
        return result

    shifts = np.zeros(parameter_count, dtype=np.float64)
    active_logs = np.where(active, normalized_logs, -math.inf)
    shifts[has_numerator] = np.max(active_logs, axis=0)[has_numerator]
    scaled_terms = np.zeros_like(unit_phases)
    with np.errstate(under="ignore"):
        for band_index in range(band_count):
            selected = active[band_index]
            scaled_terms[band_index, selected] = (
                unit_phases[band_index, selected]
                * np.exp(
                    normalized_logs[band_index, selected]
                    - shifts[selected]
                )
            )
    if not np.all(np.isfinite(scaled_terms.real)) or not np.all(
        np.isfinite(scaled_terms.imag)
    ):
        raise FloatingPointError("derived log score sum is non-finite")
    scaled = _neumaier_complex_sum_rows(scaled_terms)
    scaled_magnitudes = np.hypot(scaled.real, scaled.imag)
    if not np.all(np.isfinite(scaled_magnitudes)):
        raise FloatingPointError("derived log score sum is non-finite")

    nonzero = has_numerator & (scaled_magnitudes > 0.0)
    if not np.any(nonzero):
        return result
    ratio_logs = shifts[nonzero] + np.log(scaled_magnitudes[nonzero])
    if not np.all(np.isfinite(ratio_logs)):
        raise FloatingPointError("derived log score is non-finite")
    if np.any(ratio_logs > _LOG_COMPLEX128_MAX):
        raise FloatingPointError("derived log score is outside complex128 range")
    ratio_phases = (
        np.angle(scaled[nonzero])
        + _normalized_phase(reference.parent_phase, reference.coefficient_phase)
        - denominator.phase
    )
    with np.errstate(under="ignore"):
        result[nonzero] = np.exp(ratio_logs) * (
            np.cos(ratio_phases) + 1.0j * np.sin(ratio_phases)
        )
    if not np.all(np.isfinite(result.real)) or not np.all(
        np.isfinite(result.imag)
    ):
        raise FloatingPointError("derived log score is non-finite")
    return result


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
    terms: tuple[_LogTerm, ...]
    amplitude: _LogPolar | None


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

    def _derived_terms(
        self,
        state: int,
        memo: dict[tuple[int, int], _DerivedTerms],
    ) -> _DerivedTerms:
        parent = self._parent
        direction = self._direction
        if parent is None or direction is None:
            raise AssertionError("base component has no derived terms")
        key = (self.m, state)
        if key in memo:
            return memo[key]

        inverse = ladder_neighbors(
            state,
            self.two_q,
            direction=-direction,
        )
        active_terms: list[_LogTerm] = []
        for source, coefficient_raw in inverse.items():
            parent_log = _scalar_complex(
                parent._logpsi(parent._validated_state(source), memo),
                label="parent logpsi",
            )
            if parent_log.real == -math.inf:
                continue
            coefficient = _scalar_complex(
                coefficient_raw,
                label="ladder coefficient",
            )
            if not math.isfinite(coefficient.real) or not math.isfinite(
                coefficient.imag
            ):
                raise ValueError("ladder coefficient must be finite")
            if coefficient == 0.0:
                continue
            log_abs = math.fsum(
                (parent_log.real, math.log(abs(coefficient)))
            )
            if not math.isfinite(log_abs):
                raise FloatingPointError(
                    "derived ladder term log-magnitude is non-finite"
                )
            active_terms.append(
                _LogTerm(
                    source=source,
                    log_abs=log_abs,
                    parent_phase=parent_log.imag,
                    coefficient_phase=math.atan2(
                        coefficient.imag,
                        coefficient.real,
                    ),
                )
            )
        terms = tuple(active_terms)
        derived = _DerivedTerms(
            terms=terms,
            amplitude=_reduce_log_terms(terms),
        )
        memo[key] = derived
        return derived

    def _logpsi(
        self,
        configuration: int,
        memo: dict[tuple[int, int], _DerivedTerms],
    ) -> complex:
        if self.m == 0:
            if self._base_logpsi is None:
                raise AssertionError("M=0 component is missing its callback")
            return _scalar_complex(
                self._base_logpsi(configuration),
                label="base logpsi",
            )

        terms = self._derived_terms(configuration, memo)
        if terms.amplitude is None:
            return complex(-math.inf, 0.0)
        if self._parent is None or self._direction is None:
            raise AssertionError("derived component is missing its parent")
        normalization = spin2_ladder_coefficient(
            self._parent.m,
            self._direction,
        )
        return complex(
            terms.amplitude.log_abs - math.log(normalization),
            terms.amplitude.phase,
        )

    def logpsi(self, state: int) -> complex:
        """Evaluate this component without expanding a fixed-``M`` support."""

        configuration = self._validated_state(state)
        return self._logpsi(configuration, {})

    def _log_score(
        self,
        configuration: int,
        memo: dict[tuple[int, int], _DerivedTerms],
    ) -> np.ndarray:
        if self.m == 0:
            if self._base_log_score is None:
                raise AssertionError("M=0 component is missing its score callback")
            return _score_vector(
                self._base_log_score(configuration),
                label="base log score",
            )

        terms = self._derived_terms(configuration, memo)
        if terms.amplitude is None:
            raise ValueError("log score is undefined for an exact zero amplitude")
        if self._parent is None:
            raise AssertionError("derived component is missing its parent")

        scores: list[np.ndarray] = []
        parameter_count: int | None = None
        for term in terms.terms:
            score = _score_vector(
                self._parent._log_score(
                    self._parent._validated_state(term.source),
                    memo,
                ),
                label="parent log score",
            )
            if parameter_count is None:
                parameter_count = score.size
            elif score.size != parameter_count:
                raise ValueError(
                    "parent log scores must have the same parameter count"
                )
            scores.append(score)

        result = _score_ratio_from_log_terms(
            terms.terms,
            tuple(scores),
            terms.amplitude,
        )
        if not np.all(np.isfinite(result.real)) or not np.all(
            np.isfinite(result.imag)
        ):
            raise FloatingPointError("derived log score is non-finite")
        return result

    def log_score(self, state: int) -> np.ndarray:
        """Return the analytic parameter derivative of this log amplitude."""

        configuration = self._validated_state(state)
        return self._log_score(configuration, {})


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
