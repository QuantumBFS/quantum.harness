"""Whole-disorder resampling and covariance-aware finite-size scaling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import itertools
import math
from types import MappingProxyType

import numpy as np
from scipy.optimize import least_squares


_FIT_CONDITION_LIMIT = 1.0 / math.sqrt(np.finfo(np.float64).eps)
_COVARIANCE_CONDITION_LIMIT = 1.0e8


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and not any(
        character not in "0123456789abcdef" for character in value
    )


@dataclass(frozen=True)
class DisorderSeries:
    """Immutable Stage 7 summary for one J across its full temperature ladder."""

    j_id: str
    length: int
    temperatures: np.ndarray
    observables: Mapping[str, np.ndarray]
    source_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.j_id, str) or not self.j_id:
            raise ValueError("j_id must be a nonempty string")
        if (
            isinstance(self.length, (bool, np.bool_))
            or not isinstance(self.length, (int, np.integer))
            or int(self.length) < 2
        ):
            raise ValueError("length must be an integer at least two")
        temperatures = np.asarray(self.temperatures, dtype=np.float64)
        if temperatures.ndim != 1 or temperatures.size < 2:
            raise ValueError("temperatures must be a one-dimensional complete ladder")
        if not np.all(np.isfinite(temperatures)) or np.any(temperatures <= 0.0):
            raise ValueError("temperatures must be positive and finite")
        if not np.all(np.diff(temperatures) > 0.0):
            raise ValueError("temperatures must be strictly increasing without duplicates")
        if not isinstance(self.observables, Mapping) or not self.observables:
            raise ValueError("observables must be a nonempty mapping")
        owned_observables: dict[str, np.ndarray] = {}
        for name, raw in self.observables.items():
            if not isinstance(name, str) or not name:
                raise ValueError("observable names must be nonempty strings")
            values = np.asarray(raw, dtype=np.float64)
            if values.shape != temperatures.shape:
                raise ValueError("every observable must cover the complete temperature ladder")
            if not np.all(np.isfinite(values)):
                raise ValueError("observable values must be finite")
            owned = values.copy()
            owned.setflags(write=False)
            owned_observables[name] = owned
        if not _valid_sha256(self.source_hash):
            raise ValueError("source_hash must be one lowercase SHA-256 digest")
        owned_temperatures = temperatures.copy()
        owned_temperatures.setflags(write=False)
        object.__setattr__(self, "length", int(self.length))
        object.__setattr__(self, "temperatures", owned_temperatures)
        object.__setattr__(self, "observables", MappingProxyType(owned_observables))


@dataclass(frozen=True, order=True)
class RecordIdentity:
    length: int
    j_id: str
    source_hash: str

    def __post_init__(self) -> None:
        if int(self.length) < 2 or not self.j_id or not _valid_sha256(self.source_hash):
            raise ValueError("record identity is invalid")
        object.__setattr__(self, "length", int(self.length))


def _identity(record: DisorderSeries) -> RecordIdentity:
    return RecordIdentity(record.length, record.j_id, record.source_hash)


def _record_tuple(records: Sequence[DisorderSeries]) -> tuple[DisorderSeries, ...]:
    items = tuple(records)
    if not items:
        raise ValueError("at least one whole-disorder record is required")
    if not all(isinstance(record, DisorderSeries) for record in items):
        raise TypeError("records must contain only DisorderSeries values")
    return items


def resample_disorder(
    records: Sequence[DisorderSeries],
    indices: np.ndarray,
) -> tuple[DisorderSeries, ...]:
    """Select whole J records; no temperature or measurement axis is resampled."""

    items = _record_tuple(records)
    raw_indices = np.asarray(indices)
    if raw_indices.ndim != 1 or raw_indices.size == 0:
        raise ValueError("indices must be one nonempty one-dimensional array")
    if raw_indices.dtype.kind not in "iu":
        raise ValueError("indices must have an integer dtype")
    selected = raw_indices.astype(np.int64, copy=False)
    if np.any(selected < 0) or np.any(selected >= len(items)):
        raise IndexError("disorder resample index is out of range")
    return tuple(items[int(index)] for index in selected)


def _ordered_groups(
    records: Sequence[DisorderSeries],
) -> tuple[
    dict[int, tuple[DisorderSeries, ...]],
    dict[int, tuple[RecordIdentity, ...]],
]:
    items = _record_tuple(records)
    mutable: dict[int, list[DisorderSeries]] = {}
    seen: set[tuple[int, str]] = set()
    for record in items:
        key = (record.length, record.j_id)
        if key in seen:
            raise ValueError("duplicate disorder record")
        seen.add(key)
        mutable.setdefault(record.length, []).append(record)
    grouped = {
        length: tuple(sorted(group, key=lambda value: (value.j_id, value.source_hash)))
        for length, group in sorted(mutable.items())
    }
    axes = {
        length: tuple(_identity(record) for record in group)
        for length, group in grouped.items()
    }
    return grouped, axes


def _mean_curves(
    records: Sequence[DisorderSeries],
    observable: str,
    *,
    allow_duplicates: bool = False,
) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    items = _record_tuple(records)
    if not isinstance(observable, str) or not observable:
        raise ValueError("observable must be a nonempty string")
    grouped: dict[int, list[DisorderSeries]] = {}
    seen: set[tuple[int, str]] = set()
    for record in items:
        key = (record.length, record.j_id)
        if not allow_duplicates and key in seen:
            raise ValueError("duplicate disorder record")
        seen.add(key)
        if observable not in record.observables:
            raise ValueError(f"record is missing observable {observable!r}")
        grouped.setdefault(record.length, []).append(record)
    curves: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for length, group in grouped.items():
        reference = group[0].temperatures
        if any(not np.array_equal(record.temperatures, reference) for record in group[1:]):
            raise ValueError(f"size L={length} has a missing or inconsistent temperature grid")
        values = np.asarray(
            [record.observables[observable] for record in group],
            dtype=np.float64,
        )
        curves[length] = (reference, np.mean(values, axis=0, dtype=np.float64))
    return curves


def _roots_on_common_support(
    left_temperature: np.ndarray,
    left_values: np.ndarray,
    right_temperature: np.ndarray,
    right_values: np.ndarray,
) -> tuple[tuple[float, float] | None, tuple[float, ...], str]:
    lower = max(float(left_temperature[0]), float(right_temperature[0]))
    upper = min(float(left_temperature[-1]), float(right_temperature[-1]))
    if not lower < upper:
        return None, (), "size pair has no common temperature support"
    knots = np.unique(
        np.concatenate(
            (
                left_temperature[(left_temperature >= lower) & (left_temperature <= upper)],
                right_temperature[(right_temperature >= lower) & (right_temperature <= upper)],
                np.asarray((lower, upper), dtype=np.float64),
            )
        )
    )
    difference = np.interp(knots, left_temperature, left_values) - np.interp(
        knots,
        right_temperature,
        right_values,
    )
    scale = max(1.0, float(np.max(np.abs(difference))))
    zero_tolerance = 64.0 * np.finfo(np.float64).eps * scale
    is_zero = np.abs(difference) <= zero_tolerance
    roots: list[float] = [float(value) for value in knots[is_zero]]
    ambiguous = False
    for index in range(knots.size - 1):
        left_difference = float(difference[index])
        right_difference = float(difference[index + 1])
        if is_zero[index] and is_zero[index + 1]:
            ambiguous = True
            continue
        if is_zero[index] or is_zero[index + 1] or left_difference * right_difference >= 0.0:
            continue
        fraction = -left_difference / (right_difference - left_difference)
        roots.append(float(knots[index] + fraction * (knots[index + 1] - knots[index])))
    roots.sort()
    unique_roots: list[float] = []
    for root in roots:
        if not unique_roots or not math.isclose(
            root,
            unique_roots[-1],
            abs_tol=1e-14,
            rel_tol=0.0,
        ):
            unique_roots.append(root)
    if ambiguous:
        return (lower, upper), tuple(unique_roots), "curves coincide over a temperature interval"
    if not unique_roots:
        return (lower, upper), (), "no sign change in common temperature support"
    return (lower, upper), tuple(unique_roots), ""


@dataclass(frozen=True)
class PairCrossingResult:
    sizes: tuple[int, int]
    common_temperature_window: tuple[float, float] | None
    temperatures: tuple[float, ...]
    failed: bool
    reason: str


def _crossings_from_curves(
    curves: Mapping[int, tuple[np.ndarray, np.ndarray]],
) -> tuple[PairCrossingResult, ...]:
    results: list[PairCrossingResult] = []
    for left, right in itertools.combinations(sorted(curves), 2):
        window, roots, reason = _roots_on_common_support(
            curves[left][0],
            curves[left][1],
            curves[right][0],
            curves[right][1],
        )
        results.append(
            PairCrossingResult(
                sizes=(left, right),
                common_temperature_window=window,
                temperatures=roots,
                failed=bool(reason),
                reason=reason,
            )
        )
    return tuple(results)


def pair_crossings(
    records: Sequence[DisorderSeries],
    observable: str,
) -> tuple[PairCrossingResult, ...]:
    curves = _mean_curves(records, observable)
    if len(curves) < 2:
        raise ValueError("pair crossings require at least two sizes")
    return _crossings_from_curves(curves)


@dataclass(frozen=True)
class PairCrossingSample:
    resample_index: int
    sizes: tuple[int, int]
    common_temperature_window: tuple[float, float] | None
    temperatures: tuple[float, ...]
    failed: bool
    reason: str


@dataclass(frozen=True)
class BootstrapCrossingResult:
    observable: str
    seed: int
    resample_mode: str
    record_axes: Mapping[int, tuple[RecordIdentity, ...]]
    resample_indices: Mapping[int, np.ndarray]
    samples_by_pair: Mapping[tuple[int, int], tuple[PairCrossingSample, ...]]

    def __post_init__(self) -> None:
        if self.resample_mode not in {"generated_from_seed", "supplied_replay"}:
            raise ValueError("bootstrap crossing resample_mode is invalid")
        axes = {
            int(length): tuple(values) for length, values in self.record_axes.items()
        }
        matrices: dict[int, np.ndarray] = {}
        for length, raw in self.resample_indices.items():
            values = np.asarray(raw, dtype=np.int64).copy()
            values.setflags(write=False)
            matrices[int(length)] = values
        samples = {
            tuple(int(value) for value in pair): tuple(entries)
            for pair, entries in self.samples_by_pair.items()
        }
        object.__setattr__(self, "record_axes", MappingProxyType(axes))
        object.__setattr__(self, "resample_indices", MappingProxyType(matrices))
        object.__setattr__(self, "samples_by_pair", MappingProxyType(samples))


def _bootstrap_matrices(
    grouped: Mapping[int, tuple[DisorderSeries, ...]],
    axes: Mapping[int, tuple[RecordIdentity, ...]],
    *,
    n_resamples: int,
    seed: int,
    resample_indices: Mapping[int, np.ndarray] | None,
    record_axes: Mapping[int, Sequence[RecordIdentity]] | None,
) -> dict[int, np.ndarray]:
    if resample_indices is None:
        if record_axes is not None:
            raise ValueError("record_axes may be supplied only with resample indices")
        rng = np.random.default_rng(seed)
        return {
            length: rng.integers(
                0,
                len(group),
                size=(n_resamples, len(group)),
                dtype=np.int64,
            )
            for length, group in grouped.items()
        }
    if record_axes is None:
        raise ValueError("saved bootstrap record axes are required with resample indices")
    normalized_axes = {
        int(length): tuple(values) for length, values in record_axes.items()
    }
    if normalized_axes != dict(axes):
        raise ValueError("saved bootstrap record axes do not match ordered records")
    if set(resample_indices) != set(grouped):
        raise ValueError("saved bootstrap matrices have the wrong size inventory")
    matrices: dict[int, np.ndarray] = {}
    for length, group in grouped.items():
        raw = np.asarray(resample_indices[length])
        expected = (n_resamples, len(group))
        if raw.shape != expected or raw.dtype.kind not in "iu":
            raise ValueError(f"saved bootstrap matrix for L={length} must have shape {expected}")
        values = raw.astype(np.int64, copy=True)
        if np.any(values < 0) or np.any(values >= len(group)):
            raise ValueError("saved bootstrap matrix contains an out-of-range J index")
        matrices[length] = values
    return matrices


def bootstrap_pair_crossings(
    records: Sequence[DisorderSeries],
    observable: str,
    *,
    n_resamples: int,
    seed: int,
    resample_indices: Mapping[int, np.ndarray] | None = None,
    record_axes: Mapping[int, Sequence[RecordIdentity]] | None = None,
) -> BootstrapCrossingResult:
    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")
    grouped, axes = _ordered_groups(records)
    if len(grouped) < 2:
        raise ValueError("bootstrap crossings require at least two sizes")
    matrices = _bootstrap_matrices(
        grouped,
        axes,
        n_resamples=int(n_resamples),
        seed=int(seed),
        resample_indices=resample_indices,
        record_axes=record_axes,
    )
    pairs = tuple(itertools.combinations(sorted(grouped), 2))
    by_pair: dict[tuple[int, int], list[PairCrossingSample]] = {
        pair: [] for pair in pairs
    }
    for resample_index in range(int(n_resamples)):
        sampled: list[DisorderSeries] = []
        for length, group in grouped.items():
            sampled.extend(resample_disorder(group, matrices[length][resample_index]))
        curves = _mean_curves(sampled, observable, allow_duplicates=True)
        for crossing in _crossings_from_curves(curves):
            by_pair[crossing.sizes].append(
                PairCrossingSample(
                    resample_index=resample_index,
                    sizes=crossing.sizes,
                    common_temperature_window=crossing.common_temperature_window,
                    temperatures=crossing.temperatures,
                    failed=crossing.failed,
                    reason=crossing.reason,
                )
            )
    return BootstrapCrossingResult(
        observable=observable,
        seed=int(seed),
        resample_mode=(
            "supplied_replay" if resample_indices is not None else "generated_from_seed"
        ),
        record_axes=axes,
        resample_indices=matrices,
        samples_by_pair={pair: tuple(values) for pair, values in by_pair.items()},
    )


@dataclass(frozen=True)
class FSSVariant:
    """One ordered preregistered finite-size fit specification."""

    l_min: int
    temperature_window: tuple[float, float]
    polynomial_order: int
    parity: bool
    fixed_omega: float | None = None
    parity_order: int = 1
    fixed_omega_p: float | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.l_min, (bool, np.bool_))
            or not isinstance(self.l_min, (int, np.integer))
            or int(self.l_min) < 2
        ):
            raise ValueError("L_min must be an integer at least two")
        if len(self.temperature_window) != 2:
            raise ValueError("temperature window must contain two bounds")
        lower, upper = (float(value) for value in self.temperature_window)
        if not math.isfinite(lower) or not math.isfinite(upper) or not 0.0 < lower < upper:
            raise ValueError("temperature window must be positive, finite, and increasing")
        if (
            isinstance(self.polynomial_order, (bool, np.bool_))
            or not isinstance(self.polynomial_order, (int, np.integer))
            or not 1 <= int(self.polynomial_order) <= 5
        ):
            raise ValueError("polynomial order must be an integer from one through five")
        if type(self.parity) is not bool:
            raise ValueError("parity must be a boolean")
        parity_order = int(self.parity_order) if self.parity else 0
        if parity_order < 0 or parity_order > 2:
            raise ValueError("parity order must be zero, one, or two")
        for name, value in (
            ("fixed omega", self.fixed_omega),
            ("fixed parity omega", self.fixed_omega_p),
        ):
            if value is not None and (
                not math.isfinite(float(value)) or float(value) <= 0.0
            ):
                raise ValueError(f"{name} must be positive and finite")
        if not self.parity and self.fixed_omega_p is not None:
            raise ValueError("fixed_omega_p requires the parity family")
        object.__setattr__(self, "l_min", int(self.l_min))
        object.__setattr__(self, "temperature_window", (lower, upper))
        object.__setattr__(self, "polynomial_order", int(self.polynomial_order))
        object.__setattr__(self, "parity_order", parity_order)
        if self.fixed_omega is not None:
            object.__setattr__(self, "fixed_omega", float(self.fixed_omega))
        if self.fixed_omega_p is not None:
            object.__setattr__(self, "fixed_omega_p", float(self.fixed_omega_p))


@dataclass(frozen=True)
class NonlinearBounds:
    tc: tuple[float, float]
    nu: tuple[float, float] = (0.25, 8.0)
    omega: tuple[float, float] = (0.05, 4.0)
    omega_p: tuple[float, float] = (0.05, 4.0)

    def __post_init__(self) -> None:
        for name in ("tc", "nu", "omega", "omega_p"):
            raw = getattr(self, name)
            if len(raw) != 2:
                raise ValueError(f"{name} bounds must contain two values")
            lower, upper = (float(value) for value in raw)
            if not all(math.isfinite(value) for value in (lower, upper)) or not 0.0 < lower < upper:
                raise ValueError(f"{name} bounds must be positive, finite, and increasing")
            object.__setattr__(self, name, (lower, upper))


@dataclass(frozen=True)
class FSSFitResult:
    observable_names: tuple[str, ...]
    tc: float
    nu: float
    omega: float
    omega_p: float | None
    coefficients: Mapping[str, np.ndarray]
    working_parameter_covariance: np.ndarray
    whitened_rss: float
    dof: int
    residual_diagnostic: str
    covariance_diagnostic: str
    covariance_condition_max: float
    bound_hits: tuple[str, ...]
    failed_resamples: tuple[int, ...]
    l_min: int
    temperature_window: tuple[float, float]
    polynomial_order: int
    parity_order: int
    parity_model: str
    omega_treatment: str
    omega_p_treatment: str
    nonlinear_bounds: NonlinearBounds
    selected_records: tuple[RecordIdentity, ...]
    excluded_records: tuple[RecordIdentity, ...]
    success: bool
    failure_reason: str | None
    optimizer_message: str
    nfev: int
    multistart_attempts: int
    multistart_successes: int

    def __post_init__(self) -> None:
        if not self.success or self.failure_reason is not None:
            raise ValueError("FSSFitResult represents successful fits only")
        scalars = (
            self.tc,
            self.nu,
            self.omega,
            self.whitened_rss,
            self.covariance_condition_max,
        )
        if not all(math.isfinite(float(value)) for value in scalars):
            raise ValueError("fit result values must be finite")
        if self.omega_p is not None and not math.isfinite(float(self.omega_p)):
            raise ValueError("parity exponent must be finite")
        if self.nu <= 0.0 or self.omega <= 0.0 or self.whitened_rss < 0.0 or self.dof <= 0:
            raise ValueError("fit result scales and degrees of freedom must be positive")
        owned_coefficients: dict[str, np.ndarray] = {}
        for name in self.observable_names:
            values = np.asarray(self.coefficients[name], dtype=np.float64)
            if values.ndim != 1 or not np.all(np.isfinite(values)):
                raise ValueError("fit coefficients must be finite vectors")
            owned = values.copy()
            owned.setflags(write=False)
            owned_coefficients[name] = owned
        covariance = np.asarray(self.working_parameter_covariance, dtype=np.float64)
        if (
            covariance.ndim != 2
            or covariance.shape[0] != covariance.shape[1]
            or not np.all(np.isfinite(covariance))
        ):
            raise ValueError("working parameter covariance must be finite and square")
        owned_covariance = covariance.copy()
        owned_covariance.setflags(write=False)
        object.__setattr__(self, "coefficients", MappingProxyType(owned_coefficients))
        object.__setattr__(self, "working_parameter_covariance", owned_covariance)
        object.__setattr__(self, "bound_hits", tuple(self.bound_hits))
        object.__setattr__(self, "failed_resamples", tuple(self.failed_resamples))
        object.__setattr__(self, "selected_records", tuple(self.selected_records))
        object.__setattr__(self, "excluded_records", tuple(self.excluded_records))

    @property
    def covariance(self) -> np.ndarray:
        return self.working_parameter_covariance

    @property
    def chi2(self) -> float:
        return self.whitened_rss

    @property
    def chi2_per_dof(self) -> float:
        return self.whitened_rss_per_dof

    @property
    def whitened_rss_per_dof(self) -> float:
        return self.whitened_rss / self.dof

    @property
    def source_hashes(self) -> tuple[str, ...]:
        return tuple(sorted({value.source_hash for value in self.selected_records}))


@dataclass(frozen=True)
class FitFailure:
    resample_index: int
    variant_index: int
    reason: str
    bound_hits: tuple[str, ...] = ()


@dataclass(frozen=True)
class BootstrapInterval:
    lower: float
    median: float
    upper: float


@dataclass(frozen=True)
class SystematicSpread:
    minimum: float
    maximum: float
    half_range: float


@dataclass(frozen=True)
class BootstrapFSSResult:
    fit: FSSFitResult
    selected_variant_index: int
    declared_variants: tuple[FSSVariant, ...]
    seed: int
    resample_mode: str
    record_axes: Mapping[int, tuple[RecordIdentity, ...]]
    resample_indices: Mapping[int, np.ndarray]
    failed_resamples: tuple[FitFailure, ...]
    statistical_intervals: Mapping[str, BootstrapInterval]
    bootstrap_intervals_by_variant: Mapping[int, Mapping[str, BootstrapInterval]]
    bootstrap_success_counts: Mapping[int, int]
    bootstrap_success_fractions: Mapping[int, float]
    minimum_success_count: int
    minimum_success_fraction: float
    required_success_count: int
    adequate_variant_indices: tuple[int, ...]
    finite_size_systematic: Mapping[str, SystematicSpread]
    central_fits_by_variant: Mapping[int, FSSFitResult]
    variant_fits: tuple[FSSFitResult, ...]
    variant_failures: tuple[FitFailure, ...]

    def __post_init__(self) -> None:
        if self.resample_mode not in {"generated_from_seed", "supplied_replay"}:
            raise ValueError("bootstrap FSS resample_mode is invalid")
        matrices: dict[int, np.ndarray] = {}
        for length, raw in self.resample_indices.items():
            values = np.asarray(raw, dtype=np.int64).copy()
            values.setflags(write=False)
            matrices[int(length)] = values
        object.__setattr__(self, "record_axes", MappingProxyType({
            int(length): tuple(values) for length, values in self.record_axes.items()
        }))
        object.__setattr__(self, "resample_indices", MappingProxyType(matrices))
        object.__setattr__(self, "statistical_intervals", MappingProxyType(dict(self.statistical_intervals)))
        object.__setattr__(self, "bootstrap_intervals_by_variant", MappingProxyType({
            int(index): MappingProxyType(dict(values))
            for index, values in self.bootstrap_intervals_by_variant.items()
        }))
        object.__setattr__(self, "bootstrap_success_counts", MappingProxyType({
            int(index): int(value) for index, value in self.bootstrap_success_counts.items()
        }))
        object.__setattr__(self, "bootstrap_success_fractions", MappingProxyType({
            int(index): float(value) for index, value in self.bootstrap_success_fractions.items()
        }))
        object.__setattr__(self, "finite_size_systematic", MappingProxyType(dict(self.finite_size_systematic)))
        object.__setattr__(self, "central_fits_by_variant", MappingProxyType(dict(self.central_fits_by_variant)))
        object.__setattr__(self, "failed_resamples", tuple(self.failed_resamples))
        object.__setattr__(self, "variant_fits", tuple(self.variant_fits))
        object.__setattr__(self, "variant_failures", tuple(self.variant_failures))


class FSSFitError(RuntimeError):
    """Raised when an optimization cannot support a finite-size claim."""


@dataclass(frozen=True)
class _CovarianceBlock:
    point_slice: slice
    whitener: np.ndarray
    condition: float


@dataclass(frozen=True)
class _FitData:
    lengths: np.ndarray
    temperatures: np.ndarray
    values: Mapping[str, np.ndarray]
    errors: Mapping[str, np.ndarray]
    covariance_blocks: tuple[_CovarianceBlock, ...]
    covariance_condition_max: float
    selected_records: tuple[RecordIdentity, ...]
    excluded_records: tuple[RecordIdentity, ...]


def _observable_names(observable: str | Sequence[str]) -> tuple[str, ...]:
    names = (observable,) if isinstance(observable, str) else tuple(observable)
    if not names or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("observable names must be nonempty strings")
    if len(set(names)) != len(names):
        raise ValueError("observable names must be unique")
    return names


def _regularized_whitener(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    values = np.asarray(samples, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2:
        raise ValueError("whole-J covariance needs at least two records")
    covariance = np.cov(values, rowvar=False, ddof=1) / values.shape[0]
    covariance = np.atleast_2d(np.asarray(covariance, dtype=np.float64))
    diagonal = np.diag(covariance)
    if not np.all(np.isfinite(covariance)) or np.max(diagonal, initial=0.0) <= 0.0:
        raise ValueError("whole-J covariance has no positive disorder variance")
    dimension = covariance.shape[0]
    shrinkage = min(0.35, max(0.05, dimension / max(values.shape[0] - 1, 1) * 0.05))
    regularized = (1.0 - shrinkage) * covariance + shrinkage * np.diag(diagonal)
    scale = max(float(np.mean(diagonal)), np.finfo(np.float64).eps)
    regularized += np.eye(dimension) * scale * 1.0e-8
    eigenvalues, eigenvectors = np.linalg.eigh(regularized)
    floor = max(float(np.max(eigenvalues)) / _COVARIANCE_CONDITION_LIMIT, scale * 1.0e-10)
    clipped = np.maximum(eigenvalues, floor)
    condition = float(np.max(clipped) / np.min(clipped))
    whitener = (eigenvectors * np.power(clipped, -0.5)[None, :]) @ eigenvectors.T
    return regularized, whitener, condition


def _fit_data(
    records: Sequence[DisorderSeries],
    names: tuple[str, ...],
    variant: FSSVariant,
    *,
    allow_duplicate_records: bool,
) -> _FitData:
    items = _record_tuple(records)
    grouped: dict[int, list[DisorderSeries]] = {}
    seen: set[tuple[int, str]] = set()
    excluded: list[RecordIdentity] = []
    for record in items:
        key = (record.length, record.j_id)
        if not allow_duplicate_records and key in seen:
            raise ValueError("duplicate disorder record")
        seen.add(key)
        missing = [name for name in names if name not in record.observables]
        if missing:
            raise ValueError(f"record is missing observable {missing[0]!r}")
        if record.length >= variant.l_min:
            grouped.setdefault(record.length, []).append(record)
        else:
            excluded.append(_identity(record))
    if len(grouped) < 3:
        raise ValueError("a Tc fit requires at least three fitted sizes")
    unique_lengths = np.asarray(sorted(grouped), dtype=np.int64)
    if variant.parity and len(set(unique_lengths % 2)) < 2:
        raise ValueError("parity fits require both even and odd retained sizes")

    length_blocks: list[np.ndarray] = []
    temperature_blocks: list[np.ndarray] = []
    value_blocks: dict[str, list[np.ndarray]] = {name: [] for name in names}
    error_blocks: dict[str, list[np.ndarray]] = {name: [] for name in names}
    covariance_blocks: list[_CovarianceBlock] = []
    selected_identities: list[RecordIdentity] = []
    cursor = 0
    for length in sorted(grouped):
        group = grouped[length]
        if len(group) < 2:
            raise ValueError("each fitted size requires at least two disorder records")
        reference = group[0].temperatures
        if any(not np.array_equal(record.temperatures, reference) for record in group[1:]):
            raise ValueError(f"size L={length} has a missing or inconsistent temperature grid")
        lower, upper = variant.temperature_window
        selected = (reference >= lower) & (reference <= upper)
        if np.count_nonzero(selected) < 2:
            raise ValueError(f"size L={length} has insufficient temperatures in the fit window")
        temperatures = reference[selected]
        length_blocks.append(np.full(temperatures.shape, float(length)))
        temperature_blocks.append(temperatures)
        joint_samples: list[np.ndarray] = []
        for name in names:
            matrix = np.asarray(
                [record.observables[name][selected] for record in group],
                dtype=np.float64,
            )
            joint_samples.append(matrix)
            value_blocks[name].append(np.mean(matrix, axis=0, dtype=np.float64))
        joint = np.concatenate(joint_samples, axis=1)
        regularized, whitener, condition = _regularized_whitener(joint)
        diagonal_errors = np.sqrt(np.diag(regularized))
        width = temperatures.size
        for index, name in enumerate(names):
            error_blocks[name].append(diagonal_errors[index * width : (index + 1) * width])
        covariance_blocks.append(
            _CovarianceBlock(slice(cursor, cursor + width), whitener, condition)
        )
        cursor += width
        selected_identities.extend(_identity(record) for record in group)
    return _FitData(
        lengths=np.concatenate(length_blocks),
        temperatures=np.concatenate(temperature_blocks),
        values={name: np.concatenate(value_blocks[name]) for name in names},
        errors={name: np.concatenate(error_blocks[name]) for name in names},
        covariance_blocks=tuple(covariance_blocks),
        covariance_condition_max=max(block.condition for block in covariance_blocks),
        selected_records=tuple(selected_identities),
        excluded_records=tuple(excluded),
    )


def _feature_matrix(
    lengths: np.ndarray,
    temperatures: np.ndarray,
    *,
    tc: float,
    nu: float,
    omega: float,
    omega_p: float | None,
    polynomial_order: int,
    parity: bool,
    parity_order: int,
) -> np.ndarray:
    x = (temperatures - tc) * np.power(lengths, 1.0 / nu)
    correction = np.power(lengths, -omega)
    columns = [np.power(x, order) for order in range(polynomial_order + 1)]
    columns.extend(correction * np.power(x, order) for order in range(polynomial_order))
    if parity:
        if omega_p is None:
            raise ValueError("parity exponent is required for the parity family")
        parity_sign = np.where(lengths.astype(np.int64) % 2 == 0, 1.0, -1.0)
        parity_scale = parity_sign * np.power(lengths, -omega_p)
        columns.extend(
            parity_scale * np.power(x, order) for order in range(parity_order + 1)
        )
    return np.column_stack(columns)


def _coefficient_count(variant: FSSVariant) -> int:
    return (
        2 * variant.polynomial_order
        + 1
        + (variant.parity_order + 1 if variant.parity else 0)
    )


def _resolved_bounds(variant: FSSVariant, bounds: NonlinearBounds | None) -> NonlinearBounds:
    selected = bounds or NonlinearBounds(tc=variant.temperature_window)
    if selected.tc[1] < variant.temperature_window[0] or selected.tc[0] > variant.temperature_window[1]:
        raise ValueError("Tc bounds do not overlap the fit temperature window")
    for name, value in (
        ("omega", variant.fixed_omega),
        ("omega_p", variant.fixed_omega_p),
    ):
        if value is not None:
            lower, upper = getattr(selected, name)
            if not lower <= value <= upper:
                raise ValueError(f"fixed {name} lies outside nonlinear bounds")
    return selected


def _nonlinear_starts(
    variant: FSSVariant,
    bounds: NonlinearBounds,
) -> tuple[tuple[float, ...], ...]:
    free_omega = variant.fixed_omega is None
    free_omega_p = variant.parity and variant.fixed_omega_p is None
    fractions = (0.35, 0.5, 0.65, 0.42, 0.58, 0.5)
    nu_values = (1.2, 2.45, 4.5, 3.2, 1.8, 6.0)
    omega_values = (0.45, 1.0, 2.0, 1.5, 0.7, 3.0)
    omega_p_values = (0.55, 1.3, 2.4, 1.8, 0.85, 3.2)
    result: list[tuple[float, ...]] = []
    for index, fraction in enumerate(fractions):
        values = [
            bounds.tc[0] + fraction * (bounds.tc[1] - bounds.tc[0]),
            float(np.clip(nu_values[index], *bounds.nu)),
        ]
        if free_omega:
            values.append(float(np.clip(omega_values[index], *bounds.omega)))
        if free_omega_p:
            values.append(float(np.clip(omega_p_values[index], *bounds.omega_p)))
        result.append(tuple(values))
    return tuple(dict.fromkeys(result))


def _fit_impl(
    records: Sequence[DisorderSeries],
    names: tuple[str, ...],
    variant: FSSVariant,
    *,
    allow_duplicate_records: bool,
    nonlinear_bounds: NonlinearBounds | None,
    multistart: bool,
) -> FSSFitResult:
    data = _fit_data(
        records,
        names,
        variant,
        allow_duplicate_records=allow_duplicate_records,
    )
    bounds = _resolved_bounds(variant, nonlinear_bounds)
    free_omega = variant.fixed_omega is None
    free_omega_p = variant.parity and variant.fixed_omega_p is None
    nonlinear_count = 2 + int(free_omega) + int(free_omega_p)
    coefficients_per_observable = _coefficient_count(variant)
    parameter_count = nonlinear_count + coefficients_per_observable * len(names)
    observation_count = data.lengths.size * len(names)
    dof = observation_count - parameter_count
    if dof <= 0:
        raise ValueError("fit has no positive degrees of freedom")

    lower_nonlinear = [bounds.tc[0], bounds.nu[0]]
    upper_nonlinear = [bounds.tc[1], bounds.nu[1]]
    if free_omega:
        lower_nonlinear.append(bounds.omega[0])
        upper_nonlinear.append(bounds.omega[1])
    if free_omega_p:
        lower_nonlinear.append(bounds.omega_p[0])
        upper_nonlinear.append(bounds.omega_p[1])
    lower = np.asarray(lower_nonlinear + [-np.inf] * (coefficients_per_observable * len(names)))
    upper = np.asarray(upper_nonlinear + [np.inf] * (coefficients_per_observable * len(names)))

    def unpack(parameters: np.ndarray) -> tuple[float, float, float, float | None, dict[str, np.ndarray]]:
        cursor = 0
        tc = float(parameters[cursor]); cursor += 1
        nu = float(parameters[cursor]); cursor += 1
        omega = float(parameters[cursor]) if free_omega else float(variant.fixed_omega)
        cursor += int(free_omega)
        if variant.parity:
            omega_p = float(parameters[cursor]) if free_omega_p else float(variant.fixed_omega_p)
            cursor += int(free_omega_p)
        else:
            omega_p = None
        coefficients: dict[str, np.ndarray] = {}
        for name in names:
            coefficients[name] = parameters[cursor : cursor + coefficients_per_observable]
            cursor += coefficients_per_observable
        return tc, nu, omega, omega_p, coefficients

    def features_for(nonlinear: Sequence[float]) -> np.ndarray:
        cursor = 0
        tc = float(nonlinear[cursor]); cursor += 1
        nu = float(nonlinear[cursor]); cursor += 1
        omega = float(nonlinear[cursor]) if free_omega else float(variant.fixed_omega)
        cursor += int(free_omega)
        omega_p: float | None = None
        if variant.parity:
            omega_p = float(nonlinear[cursor]) if free_omega_p else float(variant.fixed_omega_p)
        return _feature_matrix(
            data.lengths,
            data.temperatures,
            tc=tc,
            nu=nu,
            omega=omega,
            omega_p=omega_p,
            polynomial_order=variant.polynomial_order,
            parity=variant.parity,
            parity_order=variant.parity_order,
        )

    def initial_for(nonlinear: Sequence[float]) -> np.ndarray:
        features = features_for(nonlinear)
        rank = np.linalg.matrix_rank(features)
        condition = np.linalg.cond(features)
        if rank != features.shape[1] or not math.isfinite(condition) or condition > _FIT_CONDITION_LIMIT:
            raise FSSFitError("feature matrix is rank-deficient or ill-conditioned")
        coefficients: list[float] = []
        for name in names:
            weighted_features = features / data.errors[name][:, None]
            weighted_values = data.values[name] / data.errors[name]
            solved, _, solved_rank, _ = np.linalg.lstsq(weighted_features, weighted_values, rcond=None)
            if solved_rank != features.shape[1]:
                raise FSSFitError("weighted feature matrix is rank-deficient")
            coefficients.extend(float(value) for value in solved)
        return np.asarray(tuple(nonlinear) + tuple(coefficients), dtype=np.float64)

    def residuals(parameters: np.ndarray) -> np.ndarray:
        tc, nu, omega, omega_p, coefficients = unpack(parameters)
        features = _feature_matrix(
            data.lengths,
            data.temperatures,
            tc=tc,
            nu=nu,
            omega=omega,
            omega_p=omega_p,
            polynomial_order=variant.polynomial_order,
            parity=variant.parity,
            parity_order=variant.parity_order,
        )
        blocks: list[np.ndarray] = []
        for block in data.covariance_blocks:
            raw = np.concatenate([
                features[block.point_slice] @ coefficients[name]
                - data.values[name][block.point_slice]
                for name in names
            ])
            blocks.append(block.whitener @ raw)
        return np.concatenate(blocks)

    starts = _nonlinear_starts(variant, bounds)
    if not multistart:
        starts = starts[:2]
    optimized_results = []
    failures: list[str] = []
    for start in starts:
        try:
            initial = initial_for(start)
            optimized = least_squares(
                residuals,
                initial,
                bounds=(lower, upper),
                method="trf",
                x_scale="jac",
                ftol=1e-10,
                xtol=1e-10,
                gtol=1e-10,
                max_nfev=12_000,
            )
            if not optimized.success or not np.all(np.isfinite(optimized.x)):
                failures.append(str(optimized.message))
                continue
            singular = np.linalg.svd(optimized.jac, compute_uv=False)
            tolerance = (
                max(optimized.jac.shape)
                * np.finfo(np.float64).eps
                * singular[0]
            )
            rank = int(np.count_nonzero(singular > tolerance))
            condition = float(singular[0] / singular[-1]) if singular[-1] > 0.0 else math.inf
            if rank != optimized.jac.shape[1] or not math.isfinite(condition) or condition > _FIT_CONDITION_LIMIT:
                failures.append("optimized Jacobian is rank-deficient or ill-conditioned")
                continue
            residual = residuals(optimized.x)
            optimized_results.append((float(residual @ residual), condition, optimized))
        except (ValueError, FloatingPointError, np.linalg.LinAlgError, FSSFitError) as error:
            failures.append(f"{type(error).__name__}: {error}")
    if not optimized_results:
        detail = failures[0] if failures else "no optimizer result"
        raise FSSFitError(f"all nonlinear multistarts failed: {detail}")
    whitened_rss, fit_condition, optimized = min(optimized_results, key=lambda item: item[0])
    tc, nu, omega, omega_p, coefficients = unpack(optimized.x)
    _, singular, right_vectors = np.linalg.svd(
        optimized.jac,
        full_matrices=False,
    )
    inverse_information = (
        right_vectors.T * np.square(np.reciprocal(singular))[None, :]
    ) @ right_vectors
    covariance = inverse_information * whitened_rss / dof
    if not np.all(np.isfinite(covariance)):
        raise FSSFitError("working parameter covariance is non-finite")

    nonlinear_names = ["tc", "nu"] + (["omega"] if free_omega else []) + (["omega_p"] if free_omega_p else [])
    bound_hits: list[str] = []
    for index, name in enumerate(nonlinear_names):
        width = upper[index] - lower[index]
        tolerance = max(1e-8, 1e-5 * width)
        if optimized.x[index] - lower[index] <= tolerance or upper[index] - optimized.x[index] <= tolerance:
            bound_hits.append(name)
    return FSSFitResult(
        observable_names=names,
        tc=tc,
        nu=nu,
        omega=omega,
        omega_p=omega_p,
        coefficients=coefficients,
        working_parameter_covariance=covariance,
        whitened_rss=whitened_rss,
        dof=dof,
        residual_diagnostic="regularized_covariance_whitened_rss",
        covariance_diagnostic="gauss_newton_working_covariance",
        covariance_condition_max=max(data.covariance_condition_max, fit_condition),
        bound_hits=tuple(bound_hits),
        failed_resamples=(),
        l_min=variant.l_min,
        temperature_window=variant.temperature_window,
        polynomial_order=variant.polynomial_order,
        parity_order=variant.parity_order,
        parity_model=(
            f"p(L)*L^-omega_p*Fp_order_{variant.parity_order}(x)"
            if variant.parity
            else "none"
        ),
        omega_treatment="free" if free_omega else "fixed",
        omega_p_treatment=("free" if free_omega_p else "fixed") if variant.parity else "none",
        nonlinear_bounds=bounds,
        selected_records=data.selected_records,
        excluded_records=data.excluded_records,
        success=True,
        failure_reason=None,
        optimizer_message=str(optimized.message),
        nfev=int(optimized.nfev),
        multistart_attempts=len(starts),
        multistart_successes=len(optimized_results),
    )


def fit_dimensionless_fss(
    records: Sequence[DisorderSeries],
    observable: str | Sequence[str],
    *,
    l_min: int,
    temperature_window: tuple[float, float],
    polynomial_order: int,
    parity: bool,
    fixed_omega: float | None = None,
    parity_order: int = 1,
    fixed_omega_p: float | None = None,
    nonlinear_bounds: NonlinearBounds | None = None,
) -> FSSFitResult:
    names = _observable_names(observable)
    variant = FSSVariant(
        l_min=l_min,
        temperature_window=temperature_window,
        polynomial_order=polynomial_order,
        parity=parity,
        fixed_omega=fixed_omega,
        parity_order=parity_order,
        fixed_omega_p=fixed_omega_p,
    )
    return _fit_impl(
        records,
        names,
        variant,
        allow_duplicate_records=False,
        nonlinear_bounds=nonlinear_bounds,
        multistart=True,
    )


def _failure(error: Exception, *, resample_index: int, variant_index: int) -> FitFailure:
    return FitFailure(
        resample_index=resample_index,
        variant_index=variant_index,
        reason=f"{type(error).__name__}: {error}",
    )


def _interval(values: Sequence[float]) -> BootstrapInterval:
    lower, median, upper = np.quantile(np.asarray(values), (0.025, 0.5, 0.975))
    return BootstrapInterval(float(lower), float(median), float(upper))


def _systematic(values: Sequence[float]) -> SystematicSpread:
    minimum, maximum = float(min(values)), float(max(values))
    return SystematicSpread(minimum, maximum, 0.5 * (maximum - minimum))


def bootstrap_success_adequate(
    success_count: int,
    n_resamples: int,
    *,
    minimum_count: int = 200,
    minimum_fraction: float = 0.8,
) -> bool:
    required = max(int(minimum_count), int(math.ceil(float(minimum_fraction) * n_resamples)))
    return int(success_count) >= required


def select_headline_variant(
    central_fits: Mapping[int, FSSFitResult],
    success_counts: Mapping[int, int],
    *,
    n_resamples: int,
    minimum_success_count: int,
    minimum_success_fraction: float,
) -> int:
    for index in sorted(central_fits):
        fit = central_fits[index]
        if fit.bound_hits:
            continue
        if bootstrap_success_adequate(
            success_counts.get(index, 0),
            n_resamples,
            minimum_count=minimum_success_count,
            minimum_fraction=minimum_success_fraction,
        ):
            return index
    raise FSSFitError("no preregistered fallback has adequate bootstrap success")


def bootstrap_fss(
    records: Sequence[DisorderSeries],
    observable: str | Sequence[str],
    *,
    variants: Sequence[FSSVariant],
    n_resamples: int,
    seed: int,
    minimum_success_count: int = 200,
    minimum_success_fraction: float = 0.8,
    resample_indices: Mapping[int, np.ndarray] | None = None,
    record_axes: Mapping[int, Sequence[RecordIdentity]] | None = None,
    nonlinear_bounds: NonlinearBounds | None = None,
) -> BootstrapFSSResult:
    items = _record_tuple(records)
    names = _observable_names(observable)
    declared_variants = tuple(variants)
    if not declared_variants or not all(isinstance(value, FSSVariant) for value in declared_variants):
        raise ValueError("variants must be a nonempty sequence of FSSVariant values")
    if isinstance(n_resamples, (bool, np.bool_)) or int(n_resamples) < 2:
        raise ValueError("n_resamples must be an integer at least two")
    if int(seed) < 0:
        raise ValueError("bootstrap seed must be nonnegative")
    if int(minimum_success_count) < 1 or not 0.0 < float(minimum_success_fraction) <= 1.0:
        raise ValueError("bootstrap success thresholds are invalid")
    count = int(n_resamples)
    required_success = max(
        int(minimum_success_count),
        int(math.ceil(float(minimum_success_fraction) * count)),
    )
    grouped, axes = _ordered_groups(items)
    matrices = _bootstrap_matrices(
        grouped,
        axes,
        n_resamples=count,
        seed=int(seed),
        resample_indices=resample_indices,
        record_axes=record_axes,
    )

    central: dict[int, FSSFitResult] = {}
    variant_failures: list[FitFailure] = []
    for index, variant in enumerate(declared_variants):
        try:
            fit = _fit_impl(
                items,
                names,
                variant,
                allow_duplicate_records=False,
                nonlinear_bounds=nonlinear_bounds,
                multistart=True,
            )
        except (ValueError, FSSFitError, np.linalg.LinAlgError) as error:
            variant_failures.append(_failure(error, resample_index=-1, variant_index=index))
            continue
        central[index] = fit
        if fit.bound_hits:
            variant_failures.append(
                FitFailure(-1, index, "central parameter bound hit", fit.bound_hits)
            )
    if not central:
        raise FSSFitError("every central FSS variant failed")

    bootstrap_fits: dict[int, list[FSSFitResult]] = {
        index: [] for index in range(len(declared_variants))
    }
    failures: list[FitFailure] = []
    for resample_index in range(count):
        sampled: list[DisorderSeries] = []
        for length, group in grouped.items():
            sampled.extend(resample_disorder(group, matrices[length][resample_index]))
        for index, variant in enumerate(declared_variants):
            try:
                fit = _fit_impl(
                    sampled,
                    names,
                    variant,
                    allow_duplicate_records=True,
                    nonlinear_bounds=nonlinear_bounds,
                    multistart=False,
                )
            except (ValueError, FSSFitError, np.linalg.LinAlgError) as error:
                failures.append(_failure(error, resample_index=resample_index, variant_index=index))
                continue
            if fit.bound_hits:
                failures.append(FitFailure(resample_index, index, "parameter bound hit", fit.bound_hits))
                continue
            bootstrap_fits[index].append(fit)
    success_counts = {index: len(values) for index, values in bootstrap_fits.items()}
    success_fractions = {index: value / count for index, value in success_counts.items()}
    adequate = tuple(
        index
        for index, value in success_counts.items()
        if bootstrap_success_adequate(
            value,
            count,
            minimum_count=int(minimum_success_count),
            minimum_fraction=float(minimum_success_fraction),
        )
    )
    selected_index = select_headline_variant(
        central,
        success_counts,
        n_resamples=count,
        minimum_success_count=int(minimum_success_count),
        minimum_success_fraction=float(minimum_success_fraction),
    )
    intervals_by_variant = {
        index: {
            "tc": _interval([fit.tc for fit in values]),
            "nu": _interval([fit.nu for fit in values]),
            "omega": _interval([fit.omega for fit in values]),
            **(
                {"omega_p": _interval([float(fit.omega_p) for fit in values])}
                if values and values[0].omega_p is not None
                else {}
            ),
        }
        for index, values in bootstrap_fits.items()
        if index in adequate
    }
    accepted_central = [
        fit for index, fit in central.items() if index in adequate and not fit.bound_hits
    ]
    systematic = {
        "tc": _systematic([fit.tc for fit in accepted_central]),
        "nu": _systematic([fit.nu for fit in accepted_central]),
        "omega": _systematic([fit.omega for fit in accepted_central]),
    }
    selected_failures = tuple(
        failure.resample_index for failure in failures if failure.variant_index == selected_index
    )
    headline = replace(central[selected_index], failed_resamples=selected_failures)
    return BootstrapFSSResult(
        fit=headline,
        selected_variant_index=selected_index,
        declared_variants=declared_variants,
        seed=int(seed),
        resample_mode=(
            "supplied_replay" if resample_indices is not None else "generated_from_seed"
        ),
        record_axes=axes,
        resample_indices=matrices,
        failed_resamples=tuple(failures),
        statistical_intervals=intervals_by_variant[selected_index],
        bootstrap_intervals_by_variant=intervals_by_variant,
        bootstrap_success_counts=success_counts,
        bootstrap_success_fractions=success_fractions,
        minimum_success_count=int(minimum_success_count),
        minimum_success_fraction=float(minimum_success_fraction),
        required_success_count=required_success,
        adequate_variant_indices=adequate,
        finite_size_systematic=systematic,
        central_fits_by_variant=central,
        variant_fits=tuple(central[index] for index in sorted(central)),
        variant_failures=tuple(variant_failures),
    )
