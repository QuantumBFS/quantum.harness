"""Fail-closed parallel-tempering equilibration diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType

import numpy as np

from vmcrg_ref.autocorrelation import autocorrelation_summary


class RoundTripTracker:
    def __init__(self, n_temperatures: int, n_replicas: int) -> None:
        if n_temperatures < 2 or n_replicas < 1:
            raise ValueError("round-trip tracker dimensions are invalid")
        self.n_temperatures = int(n_temperatures)
        self.n_replicas = int(n_replicas)
        self._phase = np.zeros(n_replicas, dtype=np.int8)
        self._round_trips = np.zeros(n_replicas, dtype=np.int64)
        self._time_since_endpoint = np.zeros(n_replicas, dtype=np.int64)

    def update(self, positions: np.ndarray) -> None:
        values = np.asarray(positions)
        if values.shape != (self.n_replicas,) or np.any(values < 0) or np.any(
            values >= self.n_temperatures
        ):
            raise ValueError("replica positions are invalid")
        for replica, position in enumerate(values):
            position = int(position)
            if position in (0, self.n_temperatures - 1):
                self._time_since_endpoint[replica] = 0
            else:
                self._time_since_endpoint[replica] += 1
            if self._phase[replica] == 0 and position == 0:
                self._phase[replica] = 1
            elif self._phase[replica] == 1 and position == self.n_temperatures - 1:
                self._phase[replica] = 2
            elif self._phase[replica] == 2 and position == 0:
                self._round_trips[replica] += 1
                self._phase[replica] = 1

    @property
    def round_trips(self) -> tuple[int, ...]:
        return tuple(int(value) for value in self._round_trips)

    @property
    def time_since_endpoint(self) -> tuple[int, ...]:
        return tuple(int(value) for value in self._time_since_endpoint)


@dataclass(frozen=True)
class BinEstimate:
    block_size: int
    block_count: int
    mean: float
    standard_error: float


def log_bin_estimates(series: np.ndarray) -> tuple[BinEstimate, ...]:
    values = np.asarray(series, dtype=np.float64)
    if values.ndim != 1 or values.size < 8 or not np.all(np.isfinite(values)):
        raise ValueError("log-bin series must contain at least eight finite values")
    run_lengths: list[int] = []
    run_length = 8
    while run_length <= values.size:
        run_lengths.append(run_length)
        run_length *= 2
    if run_lengths[-1] != values.size:
        run_lengths.append(int(values.size))

    estimates: list[BinEstimate] = []
    for run_length in run_lengths:
        prefix = values[:run_length]
        summary = observable_iat_ess(prefix, elapsed_seconds=1.0)
        variance = float(np.var(prefix, ddof=1))
        standard_error = math.sqrt(
            variance * 2.0 * float(summary["tau_int"]) / run_length
        )
        estimates.append(
            BinEstimate(
                block_size=run_length,
                block_count=run_length,
                mean=float(np.mean(prefix, dtype=np.float64)),
                standard_error=standard_error,
            )
        )
    return tuple(estimates)


def split_rhat(chains: np.ndarray) -> float:
    values = np.asarray(chains, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 4 or values.shape[1] < 8:
        raise ValueError("split-Rhat needs at least four chains with eight samples")
    half = values.shape[1] // 2
    split = np.concatenate((values[:, :half], values[:, -half:]), axis=0)
    length = split.shape[1]
    chain_means = np.mean(split, axis=1)
    within = float(np.mean(np.var(split, axis=1, ddof=1)))
    if within == 0.0:
        return 1.0 if np.all(split == split[0, 0]) else math.inf
    between = length * float(np.var(chain_means, ddof=1))
    variance = (length - 1.0) / length * within + between / length
    return math.sqrt(max(0.0, variance / within))


def observable_iat_ess(
    series: np.ndarray,
    elapsed_seconds: float,
) -> dict[str, float | int | str]:
    values = np.asarray(series, dtype=np.float64)
    try:
        return autocorrelation_summary(values, elapsed_seconds)
    except ValueError as error:
        if "zero variance" not in str(error):
            raise
        return {
            "samples": int(values.size),
            "tau_int": 0.5,
            "window": 0,
            "window_rule": "constant_series_exact",
            "ess": float(values.size),
            "elapsed_seconds": float(elapsed_seconds),
            "ess_per_second": float(values.size / elapsed_seconds),
        }


@dataclass(frozen=True)
class EquilibrationThresholds:
    swap_bottleneck: float = 0.15
    swap_target_min: float = 0.20
    swap_target_max: float = 0.50
    min_round_trips: int = 10
    max_rhat: float = 1.05
    min_ess: float = 200.0
    bin_sigma: float = 2.0
    max_thermal_error_fraction: float = 0.25
    min_chains: int = 4

    def __post_init__(self) -> None:
        if not (
            0.0 <= self.swap_bottleneck <= self.swap_target_min
            <= self.swap_target_max <= 1.0
        ):
            raise ValueError("swap thresholds are inconsistent")
        if (
            self.min_round_trips < 1
            or self.max_rhat < 1.0
            or self.min_ess <= 0.0
            or self.bin_sigma <= 0.0
            or self.min_chains < 4
            or not 0.0 <= self.max_thermal_error_fraction <= 1.0
        ):
            raise ValueError("equilibration thresholds are invalid")


@dataclass(frozen=True)
class EquilibrationRecord:
    j_id: str
    edge_acceptance: tuple[float, ...]
    round_trips: tuple[int, ...]
    observables: Mapping[str, np.ndarray]
    elapsed_seconds: float
    thermal_error_fraction: float
    extension_count: int
    tmax_forgetting_passed: bool

    def __post_init__(self) -> None:
        if (
            not self.j_id
            or not math.isfinite(self.elapsed_seconds)
            or self.elapsed_seconds <= 0.0
            or self.extension_count < 0
        ):
            raise ValueError("equilibration record metadata is invalid")
        if not isinstance(self.tmax_forgetting_passed, (bool, np.bool_)):
            raise ValueError("T_max forgetting decision must be Boolean")
        if not math.isfinite(self.thermal_error_fraction) or not (
            0.0 <= self.thermal_error_fraction <= 1.0
        ):
            raise ValueError("thermal error fraction is invalid")
        if not self.edge_acceptance or not all(
            math.isfinite(value) and 0.0 <= value <= 1.0
            for value in self.edge_acceptance
        ):
            raise ValueError("edge acceptance values are invalid")
        if not self.round_trips or any(value < 0 for value in self.round_trips):
            raise ValueError("round-trip values are invalid")
        owned: dict[str, np.ndarray] = {}
        for name, series in self.observables.items():
            values = np.asarray(series, dtype=np.float64)
            if values.ndim != 2 or not np.all(np.isfinite(values)):
                raise ValueError("observable chains must be finite two-dimensional arrays")
            copy = values.copy()
            copy.setflags(write=False)
            owned[str(name)] = copy
        if not owned:
            raise ValueError("at least one equilibration observable is required")
        required = {"energy", "q2", "q4", "chi0", "chik_x", "chik_y", "chik_z"}
        missing = required - set(owned)
        if missing:
            raise ValueError("missing required observables: " + ", ".join(sorted(missing)))
        object.__setattr__(self, "observables", MappingProxyType(owned))


@dataclass(frozen=True)
class EquilibrationReport:
    j_id: str
    passed: bool
    failed_gates: tuple[str, ...]
    components: Mapping[str, object]
    disorder_count: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "components", MappingProxyType(dict(self.components)))

    def with_failure(self, gate: str) -> "EquilibrationReport":
        failures = tuple(dict.fromkeys((*self.failed_gates, str(gate))))
        return replace(self, passed=False, failed_gates=failures)


def _half_consistent(values: np.ndarray, sigma: float) -> tuple[bool, float]:
    half = values.size // 2
    first, second = values[:half], values[-half:]
    difference = abs(float(np.mean(first) - np.mean(second)))
    first_iat = observable_iat_ess(first, elapsed_seconds=1.0)
    second_iat = observable_iat_ess(second, elapsed_seconds=1.0)
    error = math.sqrt(
        float(
            np.var(first, ddof=1)
            * 2.0
            * float(first_iat["tau_int"])
            / first.size
            + np.var(second, ddof=1)
            * 2.0
            * float(second_iat["tau_int"])
            / second.size
        )
    )
    return difference <= sigma * max(error, np.finfo(np.float64).eps), difference


def assess_equilibration(
    record: EquilibrationRecord,
    thresholds: EquilibrationThresholds,
) -> EquilibrationReport:
    if not isinstance(record, EquilibrationRecord):
        raise TypeError("record must be EquilibrationRecord")
    failures: list[str] = []
    components: dict[str, object] = {}
    edge_acceptance = np.asarray(record.edge_acceptance, dtype=np.float64)
    components["edge_acceptance"] = tuple(float(value) for value in edge_acceptance)
    if float(np.min(edge_acceptance)) < thresholds.swap_bottleneck:
        failures.append("swap_bottleneck")
    if np.any(edge_acceptance < thresholds.swap_target_min) or np.any(
        edge_acceptance > thresholds.swap_target_max
    ):
        failures.append("swap_target_band")
    if min(record.round_trips) < thresholds.min_round_trips:
        failures.append("round_trips")
    components["round_trips"] = record.round_trips
    components["extension_count"] = record.extension_count
    components["tmax_forgetting_passed"] = bool(record.tmax_forgetting_passed)
    components["thermal_error_fraction"] = float(record.thermal_error_fraction)
    if not record.tmax_forgetting_passed:
        failures.append("tmax_forgetting")
    if record.thermal_error_fraction > thresholds.max_thermal_error_fraction:
        failures.append("thermal_error_fraction")

    for name, chains in record.observables.items():
        if chains.shape[0] < thresholds.min_chains:
            failures.append(f"{name}:independent_chains")
            continue
        rhat = split_rhat(chains)
        if not math.isfinite(rhat) or rhat > thresholds.max_rhat:
            failures.append(f"{name}:rhat")
        summaries = [
            observable_iat_ess(chain, record.elapsed_seconds / chains.shape[0])
            for chain in chains
        ]
        minimum_ess = min(float(summary["ess"]) for summary in summaries)
        if minimum_ess < thresholds.min_ess:
            failures.append(f"{name}:ess")
        time_mean = np.mean(chains, axis=0, dtype=np.float64)
        half_check = _half_consistent(time_mean, thresholds.bin_sigma)
        if not half_check[0]:
            failures.append(f"{name}:half_consistency")
        bins = log_bin_estimates(time_mean)
        selected = bins[-3:]
        stable = len(selected) == 3
        comparisons = tuple(zip(selected, selected[1:], strict=False))
        if len(selected) == 3:
            comparisons = (*comparisons, (selected[0], selected[-1]))
        for left, right in comparisons:
            combined = math.hypot(left.standard_error, right.standard_error)
            if abs(left.mean - right.mean) > thresholds.bin_sigma * max(
                combined,
                np.finfo(np.float64).eps,
            ):
                stable = False
        if not stable:
            failures.append(f"{name}:log_bins")
        components[name] = {
            "rhat": rhat,
            "minimum_ess": minimum_ess,
            "iat": tuple(summaries),
            "half_difference": half_check[1],
            "log_bins": selected,
        }

    unique_failures = tuple(dict.fromkeys(failures))
    return EquilibrationReport(
        j_id=record.j_id,
        passed=not unique_failures,
        failed_gates=unique_failures,
        components=components,
    )


@dataclass(frozen=True)
class FitEligibility:
    eligible: bool
    completion_fraction: float
    passed_ids: tuple[str, ...]
    failed_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    hardness_difference: float | None


def completion_eligibility(
    reports: Sequence[EquilibrationReport],
    *,
    preregistered_ids: Sequence[str],
    hardness: Mapping[str, float],
    minimum_fraction: float = 0.95,
) -> FitEligibility:
    expected = tuple(preregistered_ids)
    expected_set = set(expected)
    if len(expected_set) != len(expected) or not expected:
        raise ValueError("preregistered IDs must be unique and nonempty")
    if not math.isfinite(minimum_fraction) or not 0.0 < minimum_fraction <= 1.0:
        raise ValueError("minimum fraction must lie in (0,1]")
    if not expected_set <= set(hardness):
        raise ValueError("hardness is missing preregistered IDs")
    if any(not math.isfinite(float(hardness[identifier])) for identifier in expected):
        raise ValueError("hardness values must be finite")
    by_id: dict[str, EquilibrationReport] = {}
    for report in reports:
        if report.j_id not in expected_set:
            raise ValueError("report ID is not preregistered; substitution is forbidden")
        if report.j_id in by_id:
            raise ValueError("duplicate report for one preregistered ID")
        by_id[report.j_id] = report
    passed = tuple(identifier for identifier in expected if identifier in by_id and by_id[identifier].passed)
    failed = tuple(identifier for identifier in expected if identifier in by_id and not by_id[identifier].passed)
    missing = tuple(identifier for identifier in expected if identifier not in by_id)
    fraction = len(passed) / len(expected)
    hardness_difference: float | None = None
    passed_hardness = [hardness[value] for value in passed if value in hardness]
    failed_hardness = [hardness[value] for value in failed if value in hardness]
    if passed_hardness and failed_hardness:
        hardness_difference = float(np.mean(failed_hardness) - np.mean(passed_hardness))
    return FitEligibility(
        eligible=fraction >= minimum_fraction,
        completion_fraction=fraction,
        passed_ids=passed,
        failed_ids=failed,
        missing_ids=missing,
        hardness_difference=hardness_difference,
    )
