"""Frozen BAR objective estimation for Issue #28.

All energy arrays contain total energies.  Site normalization occurs only in
``bridge_objective`` after the complete free-energy and target terms have
been combined.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from scipy.optimize import brentq


IDENTIFIABLE = "IDENTIFIABLE"
UNIDENTIFIABLE_OVERLAP = "UNIDENTIFIABLE_OVERLAP"


def _fermi(argument: np.ndarray) -> np.ndarray:
    return np.exp(-np.logaddexp(0.0, argument))


def _normalized_weights(weights: np.ndarray | None, size: int) -> np.ndarray:
    if weights is None:
        return np.full(size, 1.0 / size, dtype=np.float64)
    values = np.asarray(weights, dtype=np.float64).reshape(-1)
    if values.size != size or np.any(values < 0.0) or not np.all(np.isfinite(values)):
        raise ValueError("BAR quadrature weights are invalid")
    total = float(values.sum())
    if total <= 0.0:
        raise ValueError("BAR quadrature weights must have positive mass")
    return values / total


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.dot(weights, values))


def _solve_delta_f(
    forward: np.ndarray,
    reverse: np.ndarray,
    root_tolerance: float,
    forward_weights: np.ndarray | None = None,
    reverse_weights: np.ndarray | None = None,
) -> float:
    left_values = np.asarray(forward, dtype=np.float64).reshape(-1)
    right_values = np.asarray(reverse, dtype=np.float64).reshape(-1)
    left_weights = _normalized_weights(forward_weights, left_values.size)
    right_weights = _normalized_weights(reverse_weights, right_values.size)
    log_sample_ratio = (
        0.0
        if forward_weights is not None or reverse_weights is not None
        else float(np.log(left_values.size / right_values.size))
    )

    def equation(delta_f: float) -> float:
        left = _weighted_mean(
            _fermi(left_values - delta_f + log_sample_ratio),
            left_weights,
        )
        right = _weighted_mean(
            _fermi(-right_values + delta_f - log_sample_ratio),
            right_weights,
        )
        return left - right

    lower = float(min(left_values.min(), right_values.min()) - 100.0)
    upper = float(max(left_values.max(), right_values.max()) + 100.0)
    lower_value = equation(lower)
    upper_value = equation(upper)
    expansion = 100.0
    for _ in range(20):
        if lower_value <= 0.0 <= upper_value:
            break
        expansion *= 2.0
        lower -= expansion
        upper += expansion
        lower_value = equation(lower)
        upper_value = equation(upper)
    else:
        raise ValueError("BAR root is not bracketed")
    if lower_value == 0.0:
        return lower
    if upper_value == 0.0:
        return upper
    return float(
        brentq(
            equation,
            lower,
            upper,
            xtol=root_tolerance,
            rtol=max(root_tolerance, 4.0 * np.finfo(np.float64).eps),
            maxiter=1000,
        )
    )


def _log_weighted_mean_exp(
    values: np.ndarray,
    weights: np.ndarray | None = None,
) -> float:
    flat = np.asarray(values, dtype=np.float64).reshape(-1)
    normalized = _normalized_weights(weights, flat.size)
    maximum = float(flat.max())
    return maximum + float(np.log(np.dot(normalized, np.exp(flat - maximum))))


def _kish_fraction(values: np.ndarray, weights: np.ndarray) -> float:
    first = _weighted_mean(values, weights)
    second = _weighted_mean(values * values, weights)
    if second <= 0.0:
        return 0.0
    return min(1.0, max(0.0, first * first / second))


def _closure_standard_error(work: np.ndarray, sign: float) -> float:
    values = np.asarray(work, dtype=np.float64)
    if values.ndim == 2 and values.shape[0] >= 2:
        estimates = np.asarray(
            [sign * _log_weighted_mean_exp(sign * chain) for chain in values],
            dtype=np.float64,
        )
        return float(estimates.std(ddof=1) / np.sqrt(estimates.size))
    flat = values.reshape(-1)
    shifted = sign * flat
    maximum = float(shifted.max())
    exponentials = np.exp(shifted - maximum)
    mean = float(exponentials.mean())
    if exponentials.size < 2 or mean == 0.0:
        return 0.0
    return float(exponentials.std(ddof=1) / np.sqrt(exponentials.size) / mean)


@dataclass(frozen=True)
class BarIntervalResult:
    delta_log_z: float | None
    delta_f: float | None
    standard_error: float | None
    overlap: float
    forward_kish_fraction: float
    reverse_kish_fraction: float
    closure_forward_delta_log_z: float | None
    closure_reverse_delta_log_z: float | None
    closure_disagreement: float | None
    closure_combined_standard_error: float | None
    closure_z: float | None
    classification: str
    failed_gates: tuple[str, ...]


def _bar_result(
    forward: np.ndarray,
    reverse: np.ndarray,
    *,
    root_tolerance: float,
    minimum_overlap: float,
    minimum_kish_fraction: float,
    maximum_closure_z: float,
    forward_weights: np.ndarray | None = None,
    reverse_weights: np.ndarray | None = None,
) -> BarIntervalResult:
    forward_array = np.asarray(forward, dtype=np.float64)
    reverse_array = np.asarray(reverse, dtype=np.float64)
    if forward_array.ndim not in (1, 2) or reverse_array.ndim not in (1, 2):
        raise ValueError("BAR work arrays must be one- or two-dimensional")
    if forward_array.size < 2 or reverse_array.size < 2:
        raise ValueError("BAR requires at least two samples in each direction")
    if not np.all(np.isfinite(forward_array)) or not np.all(np.isfinite(reverse_array)):
        raise ValueError("BAR work arrays must be finite")
    if root_tolerance <= 0.0:
        raise ValueError("BAR root tolerance must be positive")
    delta_f = _solve_delta_f(
        forward_array,
        reverse_array,
        root_tolerance,
        forward_weights,
        reverse_weights,
    )
    flat_forward = forward_array.reshape(-1)
    flat_reverse = reverse_array.reshape(-1)
    normalized_forward = _normalized_weights(forward_weights, flat_forward.size)
    normalized_reverse = _normalized_weights(reverse_weights, flat_reverse.size)
    log_sample_ratio = (
        0.0
        if forward_weights is not None or reverse_weights is not None
        else float(np.log(flat_forward.size / flat_reverse.size))
    )
    fermi_forward = _fermi(flat_forward - delta_f + log_sample_ratio)
    fermi_reverse = _fermi(-flat_reverse + delta_f - log_sample_ratio)
    overlap = 0.5 * (
        _weighted_mean(fermi_forward, normalized_forward)
        + _weighted_mean(fermi_reverse, normalized_reverse)
    )
    forward_kish = _kish_fraction(fermi_forward, normalized_forward)
    reverse_kish = _kish_fraction(fermi_reverse, normalized_reverse)
    closure_forward = _log_weighted_mean_exp(-flat_forward, forward_weights)
    closure_reverse = -_log_weighted_mean_exp(flat_reverse, reverse_weights)
    closure_disagreement = abs(closure_forward - closure_reverse)
    forward_se = _closure_standard_error(forward_array, -1.0)
    reverse_se = _closure_standard_error(reverse_array, 1.0)
    combined_se = float(np.hypot(forward_se, reverse_se))
    if combined_se > 0.0:
        closure_z = closure_disagreement / combined_se
    elif closure_disagreement == 0.0:
        closure_z = 0.0
    else:
        closure_z = float(np.finfo(np.float64).max)

    standard_error: float | None = None
    if (
        forward_array.ndim == 2
        and reverse_array.ndim == 2
        and forward_array.shape[0] == reverse_array.shape[0]
        and forward_array.shape[0] >= 2
        and forward_weights is None
        and reverse_weights is None
    ):
        replicates = []
        for chain in range(forward_array.shape[0]):
            replicates.append(
                -_solve_delta_f(
                    np.delete(forward_array, chain, axis=0),
                    np.delete(reverse_array, chain, axis=0),
                    root_tolerance,
                )
            )
        replicate_values = np.asarray(replicates, dtype=np.float64)
        replicate_mean = float(replicate_values.mean())
        standard_error = float(
            np.sqrt(
                (replicate_values.size - 1)
                / replicate_values.size
                * np.sum((replicate_values - replicate_mean) ** 2)
            )
        )

    failed = []
    if not np.isfinite(delta_f):
        failed.append("nonfinite_root")
    if overlap < minimum_overlap:
        failed.append("bar_overlap")
    if forward_kish < minimum_kish_fraction:
        failed.append("forward_kish")
    if reverse_kish < minimum_kish_fraction:
        failed.append("reverse_kish")
    if not np.isfinite(closure_z) or closure_z > maximum_closure_z:
        failed.append("closure")
    classification = IDENTIFIABLE if not failed else UNIDENTIFIABLE_OVERLAP
    return BarIntervalResult(
        delta_log_z=-delta_f if np.isfinite(delta_f) else None,
        delta_f=delta_f if np.isfinite(delta_f) else None,
        standard_error=standard_error,
        overlap=float(overlap),
        forward_kish_fraction=float(forward_kish),
        reverse_kish_fraction=float(reverse_kish),
        closure_forward_delta_log_z=float(closure_forward),
        closure_reverse_delta_log_z=float(closure_reverse),
        closure_disagreement=float(closure_disagreement),
        closure_combined_standard_error=combined_se,
        closure_z=float(closure_z),
        classification=classification,
        failed_gates=tuple(failed),
    )


def bar_free_energy_difference(
    work_forward: np.ndarray,
    work_reverse: np.ndarray,
    *,
    root_tolerance: float,
    minimum_overlap: float = 0.03,
    minimum_kish_fraction: float = 0.10,
    maximum_closure_z: float = 3.0,
) -> BarIntervalResult:
    """Estimate log(Z_B/Z_A); both work arrays store u_B-u_A."""
    return _bar_result(
        work_forward,
        work_reverse,
        root_tolerance=root_tolerance,
        minimum_overlap=minimum_overlap,
        minimum_kish_fraction=minimum_kish_fraction,
        maximum_closure_z=maximum_closure_z,
    )


def bar_from_exact_two_state_ensembles(
    delta_energy: np.ndarray,
    *,
    root_tolerance: float = 1e-13,
) -> BarIntervalResult:
    """Evaluate BAR using exact quadrature weights for a finite state space."""
    values = np.asarray(delta_energy, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("delta_energy must contain at least two finite states")
    forward_weights = np.full(values.size, 1.0 / values.size)
    log_reverse = -values
    log_reverse -= log_reverse.max()
    reverse_weights = np.exp(log_reverse)
    reverse_weights /= reverse_weights.sum()
    return _bar_result(
        values,
        values,
        root_tolerance=root_tolerance,
        minimum_overlap=0.03,
        minimum_kish_fraction=0.10,
        maximum_closure_z=3.0,
        forward_weights=forward_weights,
        reverse_weights=reverse_weights,
    )


@dataclass(frozen=True)
class ChainSet:
    energies: np.ndarray
    lambda_value: float | None
    stream_hash: str
    sample_hash: str

    def __post_init__(self) -> None:
        values = np.asarray(self.energies, dtype=np.float64).copy()
        if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 2:
            raise ValueError("ChainSet energies must have at least two chains and samples")
        if not np.all(np.isfinite(values)):
            raise ValueError("ChainSet energies must be finite")
        if self.lambda_value is not None and (
            not np.isfinite(self.lambda_value) or not 0.0 <= self.lambda_value <= 1.0
        ):
            raise ValueError("ChainSet lambda must lie in [0, 1]")
        if not self.stream_hash or not self.sample_hash:
            raise ValueError("ChainSet stream and sample hashes are required")
        values.setflags(write=False)
        object.__setattr__(self, "energies", values)


@dataclass(frozen=True)
class ObjectiveProtocol:
    lambda_ladder: tuple[float, ...]
    site_count: int
    root_tolerance: float = 1e-12
    minimum_overlap: float = 0.03
    minimum_kish_fraction: float = 0.10
    maximum_closure_z: float = 3.0
    jackknife_unit: str = "independent_chain"
    unidentifiable_classification: str = UNIDENTIFIABLE_OVERLAP
    bootstrap_hierarchy: tuple[str, ...] = ("seed_bundle", "independent_chain")
    common_zero_bias_anchor: bool = True
    independent_nonzero_streams: bool = True

    def __post_init__(self) -> None:
        ladder = tuple(float(value) for value in self.lambda_ladder)
        if len(ladder) < 2 or ladder[0] != 0.0 or ladder[-1] != 1.0:
            raise ValueError("objective lambda ladder must begin at zero and end at one")
        if any(right <= left for left, right in zip(ladder, ladder[1:])):
            raise ValueError("objective lambda ladder must be strictly increasing")
        if self.site_count <= 0 or self.root_tolerance <= 0.0:
            raise ValueError("objective site count and root tolerance must be positive")
        if self.jackknife_unit != "independent_chain":
            raise ValueError("objective jackknife unit must be independent_chain")
        if self.unidentifiable_classification != UNIDENTIFIABLE_OVERLAP:
            raise ValueError("objective overlap failures must remain unidentifiable")
        if self.bootstrap_hierarchy != ("seed_bundle", "independent_chain"):
            raise ValueError("objective bootstrap hierarchy changed")
        if not self.common_zero_bias_anchor or not self.independent_nonzero_streams:
            raise ValueError("objective anchor/stream independence contract changed")
        if not 0.0 < self.minimum_overlap <= 0.5:
            raise ValueError("objective overlap threshold is invalid")
        if not 0.0 < self.minimum_kish_fraction <= 1.0:
            raise ValueError("objective Kish threshold is invalid")
        if self.maximum_closure_z <= 0.0:
            raise ValueError("objective closure threshold must be positive")
        object.__setattr__(self, "lambda_ladder", ladder)


def objective_protocol_from_mapping(
    value: dict[str, Any],
    *,
    site_count: int,
) -> ObjectiveProtocol:
    required = {
        "estimator",
        "lambda_ladder",
        "chains_per_bridge",
        "thermal_sweeps",
        "measurements",
        "spacing_sweeps",
        "root_tolerance",
        "minimum_bar_overlap",
        "minimum_kish_ess_fraction",
        "maximum_closure_z",
        "jackknife_unit",
        "common_zero_bias_anchor",
        "independent_nonzero_streams",
        "unidentifiable_classification",
        "bootstrap_hierarchy",
    }
    missing = required - set(value)
    if missing:
        raise ValueError(f"objective protocol fields are missing: {sorted(missing)}")
    if value["estimator"] != "stratified_BAR":
        raise ValueError("objective estimator must remain stratified_BAR")
    if value["common_zero_bias_anchor"] is not True:
        raise ValueError("objective protocol requires the common zero-bias anchor")
    if value["independent_nonzero_streams"] is not True:
        raise ValueError("objective nonzero bridge streams must remain independent")
    for key in (
        "chains_per_bridge",
        "measurements",
        "spacing_sweeps",
    ):
        if int(value[key]) <= 0:
            raise ValueError(f"objective {key} must be positive")
    if int(value["chains_per_bridge"]) < 2:
        raise ValueError("objective requires at least two independent chains")
    if int(value["thermal_sweeps"]) < 0:
        raise ValueError("objective thermal sweeps cannot be negative")
    return ObjectiveProtocol(
        lambda_ladder=tuple(float(item) for item in value["lambda_ladder"]),
        site_count=site_count,
        root_tolerance=float(value["root_tolerance"]),
        minimum_overlap=float(value["minimum_bar_overlap"]),
        minimum_kish_fraction=float(value["minimum_kish_ess_fraction"]),
        maximum_closure_z=float(value["maximum_closure_z"]),
        jackknife_unit=str(value["jackknife_unit"]),
        unidentifiable_classification=str(value["unidentifiable_classification"]),
        bootstrap_hierarchy=tuple(str(item) for item in value["bootstrap_hierarchy"]),
        common_zero_bias_anchor=bool(value["common_zero_bias_anchor"]),
        independent_nonzero_streams=bool(value["independent_nonzero_streams"]),
    )


@dataclass(frozen=True)
class ObjectiveResult:
    classification: str
    objective_total: float | None
    objective_per_site: float | None
    log_z_ratio_total: float | None
    target_expectation_total: float | None
    standard_error_total: float | None
    standard_error_per_site: float | None
    intervals: tuple[BarIntervalResult, ...]
    anchor_hash: str
    anchor_stream_hash: str
    nonzero_stream_hashes: tuple[str, ...]
    target_stream_hash: str
    site_count: int
    jackknife_replicates: np.ndarray | None

    def __post_init__(self) -> None:
        if self.jackknife_replicates is not None:
            values = np.asarray(self.jackknife_replicates, dtype=np.float64).copy()
            values.setflags(write=False)
            object.__setattr__(self, "jackknife_replicates", values)


@dataclass(frozen=True)
class PairedObjectiveResult:
    classification: str
    delta_objective_total: float | None
    delta_objective_per_site: float | None
    standard_error_total: float | None
    standard_error_per_site: float | None
    anchor_hash: str


def chain_jackknife(values: np.ndarray, chain_axis: int = 0) -> dict[str, Any]:
    if chain_axis != 0:
        raise ValueError("chain axis must be zero; measurement-level jackknife is forbidden")
    data = np.asarray(values, dtype=np.float64)
    if data.ndim < 2 or data.shape[0] < 2 or not np.all(np.isfinite(data)):
        raise ValueError("jackknife values require at least two finite independent chains")
    chain_means = data.reshape(data.shape[0], -1).mean(axis=1)
    estimate = float(chain_means.mean())
    replicates = np.asarray(
        [np.delete(chain_means, index).mean() for index in range(chain_means.size)],
        dtype=np.float64,
    )
    replicate_mean = float(replicates.mean())
    standard_error = float(
        np.sqrt(
            (replicates.size - 1)
            / replicates.size
            * np.sum((replicates - replicate_mean) ** 2)
        )
    )
    return {
        "estimate": estimate,
        "standard_error": standard_error,
        "replicates": replicates.tolist(),
        "unit": "independent_chain",
        "chains": int(chain_means.size),
    }


def _objective_replicates(
    sets: Sequence[ChainSet],
    target: ChainSet,
    protocol: ObjectiveProtocol,
) -> np.ndarray:
    chains = sets[0].energies.shape[0]
    replicates = np.empty(chains, dtype=np.float64)
    for omitted in range(chains):
        log_z = 0.0
        for left, right in zip(sets, sets[1:]):
            delta_lambda = float(right.lambda_value - left.lambda_value)  # type: ignore[operator]
            delta_f = _solve_delta_f(
                delta_lambda * np.delete(left.energies, omitted, axis=0),
                delta_lambda * np.delete(right.energies, omitted, axis=0),
                protocol.root_tolerance,
            )
            log_z -= delta_f
        target_mean = float(np.delete(target.energies, omitted, axis=0).mean())
        replicates[omitted] = log_z + target_mean
    return replicates


def bridge_objective(
    anchor: ChainSet,
    bridges: Sequence[ChainSet],
    target_energies: ChainSet,
    protocol: ObjectiveProtocol,
) -> ObjectiveResult:
    sets = (anchor, *tuple(bridges))
    if anchor.lambda_value != 0.0:
        raise ValueError("objective anchor must be the zero-bias ensemble")
    observed_ladder = tuple(float(item.lambda_value) for item in sets)  # type: ignore[arg-type]
    if observed_ladder != protocol.lambda_ladder:
        raise ValueError("bridge chain sets do not match the frozen lambda ladder")
    if target_energies.lambda_value is not None:
        raise ValueError("target energies are not a bridge ensemble")
    shapes = {item.energies.shape for item in (*sets, target_energies)}
    if len(shapes) != 1:
        raise ValueError("all objective chain sets must use matched budgets")
    streams = [item.stream_hash for item in (*sets, target_energies)]
    if len(streams) != len(set(streams)):
        raise ValueError("objective anchor, bridges, and target require independent streams")

    intervals = []
    for left, right in zip(sets, sets[1:]):
        delta_lambda = float(right.lambda_value - left.lambda_value)  # type: ignore[operator]
        intervals.append(
            bar_free_energy_difference(
                delta_lambda * left.energies,
                delta_lambda * right.energies,
                root_tolerance=protocol.root_tolerance,
                minimum_overlap=protocol.minimum_overlap,
                minimum_kish_fraction=protocol.minimum_kish_fraction,
                maximum_closure_z=protocol.maximum_closure_z,
            )
        )
    interval_tuple = tuple(intervals)
    if any(item.classification != IDENTIFIABLE for item in interval_tuple):
        return ObjectiveResult(
            classification=UNIDENTIFIABLE_OVERLAP,
            objective_total=None,
            objective_per_site=None,
            log_z_ratio_total=None,
            target_expectation_total=None,
            standard_error_total=None,
            standard_error_per_site=None,
            intervals=interval_tuple,
            anchor_hash=anchor.sample_hash,
            anchor_stream_hash=anchor.stream_hash,
            nonzero_stream_hashes=tuple(item.stream_hash for item in sets[1:]),
            target_stream_hash=target_energies.stream_hash,
            site_count=protocol.site_count,
            jackknife_replicates=None,
        )
    log_z = float(sum(item.delta_log_z for item in interval_tuple))  # type: ignore[arg-type]
    target_mean = float(target_energies.energies.mean())
    total = log_z + target_mean
    replicates = _objective_replicates(sets, target_energies, protocol)
    replicate_mean = float(replicates.mean())
    standard_error = float(
        np.sqrt(
            (replicates.size - 1)
            / replicates.size
            * np.sum((replicates - replicate_mean) ** 2)
        )
    )
    return ObjectiveResult(
        classification=IDENTIFIABLE,
        objective_total=total,
        objective_per_site=total / protocol.site_count,
        log_z_ratio_total=log_z,
        target_expectation_total=target_mean,
        standard_error_total=standard_error,
        standard_error_per_site=standard_error / protocol.site_count,
        intervals=interval_tuple,
        anchor_hash=anchor.sample_hash,
        anchor_stream_hash=anchor.stream_hash,
        nonzero_stream_hashes=tuple(item.stream_hash for item in sets[1:]),
        target_stream_hash=target_energies.stream_hash,
        site_count=protocol.site_count,
        jackknife_replicates=replicates,
    )


def paired_objective_difference(
    neural: ObjectiveResult,
    linear: ObjectiveResult,
) -> PairedObjectiveResult:
    if neural.anchor_hash != linear.anchor_hash or neural.anchor_stream_hash != linear.anchor_stream_hash:
        raise ValueError("paired objectives must use the common zero-bias anchor")
    if neural.site_count != linear.site_count:
        raise ValueError("paired objectives must use the same site normalization")
    neural_streams = set(neural.nonzero_stream_hashes) | {neural.target_stream_hash}
    linear_streams = set(linear.nonzero_stream_hashes) | {linear.target_stream_hash}
    if neural_streams & linear_streams:
        raise ValueError("neural and linear nonzero objective streams must be independent")
    if neural.classification != IDENTIFIABLE or linear.classification != IDENTIFIABLE:
        return PairedObjectiveResult(
            classification=UNIDENTIFIABLE_OVERLAP,
            delta_objective_total=None,
            delta_objective_per_site=None,
            standard_error_total=None,
            standard_error_per_site=None,
            anchor_hash=neural.anchor_hash,
        )
    delta = float(neural.objective_total - linear.objective_total)  # type: ignore[operator]
    standard_error: float | None
    if (
        neural.jackknife_replicates is not None
        and linear.jackknife_replicates is not None
        and neural.jackknife_replicates.shape == linear.jackknife_replicates.shape
    ):
        replicates = neural.jackknife_replicates - linear.jackknife_replicates
        mean = float(replicates.mean())
        standard_error = float(
            np.sqrt(
                (replicates.size - 1)
                / replicates.size
                * np.sum((replicates - mean) ** 2)
            )
        )
    elif neural.standard_error_total is not None and linear.standard_error_total is not None:
        standard_error = float(
            np.hypot(neural.standard_error_total, linear.standard_error_total)
        )
    else:
        standard_error = None
    return PairedObjectiveResult(
        classification=IDENTIFIABLE,
        delta_objective_total=delta,
        delta_objective_per_site=delta / neural.site_count,
        standard_error_total=standard_error,
        standard_error_per_site=(
            None if standard_error is None else standard_error / neural.site_count
        ),
        anchor_hash=neural.anchor_hash,
    )


def hierarchical_paired_bootstrap(
    neural: np.ndarray,
    linear: np.ndarray,
    *,
    replicates: int,
    seed: int,
    confidence: float = 0.95,
) -> dict[str, Any]:
    neural_values = np.asarray(neural, dtype=np.float64)
    linear_values = np.asarray(linear, dtype=np.float64)
    if neural_values.shape != linear_values.shape or neural_values.ndim != 2:
        raise ValueError("hierarchical paired arrays must have shape (seed, chain)")
    if min(neural_values.shape) < 2 or not np.all(np.isfinite(neural_values)) or not np.all(np.isfinite(linear_values)):
        raise ValueError("hierarchical bootstrap requires finite multi-seed, multi-chain data")
    if replicates <= 0 or not 0.0 < confidence < 1.0:
        raise ValueError("bootstrap replicates and confidence are invalid")
    paired = neural_values - linear_values
    seed_count, chain_count = paired.shape
    rng = np.random.default_rng(seed)
    samples = np.empty(replicates, dtype=np.float64)
    for replicate in range(replicates):
        selected_seeds = rng.integers(0, seed_count, size=seed_count)
        seed_estimates = np.empty(seed_count, dtype=np.float64)
        for index, selected_seed in enumerate(selected_seeds):
            selected_chains = rng.integers(0, chain_count, size=chain_count)
            seed_estimates[index] = paired[selected_seed, selected_chains].mean()
        samples[replicate] = seed_estimates.mean()
    alpha = 1.0 - confidence
    return {
        "paired_estimate": float(paired.mean()),
        "ci95_low": float(np.quantile(samples, alpha / 2.0)),
        "ci95_high": float(np.quantile(samples, 1.0 - alpha / 2.0)),
        "confidence": confidence,
        "replicates": replicates,
        "seed": int(seed),
        "formal_seed_count": int(seed_count),
        "chains_per_seed": int(chain_count),
        "bootstrap_unit": ["seed_bundle", "independent_chain"],
    }
