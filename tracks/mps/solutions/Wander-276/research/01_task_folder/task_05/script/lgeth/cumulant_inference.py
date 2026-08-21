"""Realization-level U-statistic inference for complete response cumulants."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CumulantEstimate:
    """Complete physical, Wick, and cumulant tensors for one ensemble."""

    realization_count: int
    unordered_pair_count: int
    physical_mean: np.ndarray
    wick_pairings: np.ndarray
    wick_total: np.ndarray
    cumulant: np.ndarray


@dataclass(frozen=True)
class DirectionalJackknife:
    """A fixed tensor-direction estimate and delete-one pseudo-values."""

    direction: np.ndarray
    estimate: float
    delete_one_estimates: np.ndarray
    pseudovalues: np.ndarray
    standard_error: float


@dataclass(frozen=True)
class PairedMultiplierResult:
    """Joint sector inference from shared realization multipliers."""

    sectors: tuple[str, ...]
    estimates: np.ndarray
    standard_errors: np.ndarray
    z_scores: np.ndarray
    p_values: np.ndarray
    interval_low: np.ndarray
    interval_high: np.ndarray
    simultaneous_quantile: float
    bootstrap_z: np.ndarray
    replicates: int
    seed: int
    family_alpha: float


@dataclass(frozen=True)
class FittedDirection:
    """Phase-fixed tensor direction learned from opened development sizes."""

    direction: np.ndarray
    sizes: tuple[int, ...]
    normalized_tensors: np.ndarray
    raw_weights: np.ndarray
    capped_weights: np.ndarray
    cap: float


@dataclass(frozen=True)
class DirectionValidation:
    """Frozen-direction validation against one untouched development size."""

    overlap: float
    p_value: float
    interval_low: float
    significant_positive: bool
    positive_interval: bool
    overlap_pass: bool
    passed: bool


@dataclass(frozen=True)
class EquivalenceBound:
    """Smallest effect treated as scientifically meaningful in one sector."""

    separable_component: float
    gaussian_component: float
    value: float


@dataclass(frozen=True)
class SectorDecision:
    """One primary sector's directional state under frozen thresholds."""

    status: str
    estimate: float
    p_value: float
    interval_low: float
    interval_high: float
    equivalence_bound: float


@dataclass(frozen=True)
class ProspectivePowerResult:
    """Development-only sample-count choice for the prospective size."""

    selected_count: int | None
    candidate_counts: tuple[int, ...]
    joint_positive_power: np.ndarray
    joint_equivalence_power: np.ndarray
    positive_target: float
    equivalence_target: float
    trials: int
    multiplier_replicates: int
    seed: int
    branch: str


@dataclass(frozen=True)
class BranchDecision:
    """Exactly one frozen complete-covariance result branch."""

    branch: str
    central_status: str
    adjacent_status: str
    sparse_positive: bool
    omnibus_positive: bool
    numerical_ok: bool
    prospective_power_ok: bool


def _validated_shards(
    self_tensors: np.ndarray,
    pair_sums: Mapping[tuple[int, int], np.ndarray],
) -> tuple[np.ndarray, dict[tuple[int, int], np.ndarray]]:
    self_values = np.asarray(self_tensors, dtype=complex)
    if self_values.ndim < 2 or self_values.shape[0] < 4:
        raise ValueError("cumulant aggregation requires at least four realizations")
    if not (
        np.all(np.isfinite(self_values.real))
        and np.all(np.isfinite(self_values.imag))
    ):
        raise ValueError("self tensors must be finite")
    count = int(self_values.shape[0])
    expected_keys = {
        (first, second)
        for first in range(count)
        for second in range(first + 1, count)
    }
    observed_keys = set(pair_sums)
    if observed_keys != expected_keys:
        raise ValueError("complete unordered pair grid is required")
    expected_shape = (3,) + self_values.shape[1:]
    pairs: dict[tuple[int, int], np.ndarray] = {}
    for key in sorted(expected_keys):
        value = np.asarray(pair_sums[key], dtype=complex)
        if value.shape != expected_shape:
            raise ValueError("pair tensor shape disagrees with self tensors")
        if not (
            np.all(np.isfinite(value.real))
            and np.all(np.isfinite(value.imag))
        ):
            raise ValueError("pair tensors must be finite")
        pairs[key] = value
    return self_values, pairs


def aggregate_cumulant(
    self_tensors: np.ndarray,
    pair_sums: Mapping[tuple[int, int], np.ndarray],
) -> CumulantEstimate:
    """Aggregate one self tensor per realization and one unordered pair sum."""

    self_values, pairs = _validated_shards(self_tensors, pair_sums)
    count = int(self_values.shape[0])
    physical_mean = np.mean(self_values, axis=0)
    pair_total = np.sum(np.asarray(list(pairs.values())), axis=0)
    wick_pairings = pair_total / (count * (count - 1))
    wick_total = np.sum(wick_pairings, axis=0)
    cumulant = physical_mean - wick_total
    return CumulantEstimate(
        realization_count=count,
        unordered_pair_count=len(pairs),
        physical_mean=physical_mean,
        wick_pairings=wick_pairings,
        wick_total=wick_total,
        cumulant=cumulant,
    )


def delete_one_cumulants(
    self_tensors: np.ndarray,
    pair_sums: Mapping[tuple[int, int], np.ndarray],
) -> np.ndarray:
    """Return complete cumulants after deleting each realization and its pairs."""

    self_values, pairs = _validated_shards(self_tensors, pair_sums)
    count = int(self_values.shape[0])
    self_total = np.sum(self_values, axis=0)
    pair_total = np.sum(np.asarray(list(pairs.values())), axis=0)
    incident = np.zeros((count,) + pair_total.shape, dtype=complex)
    for (first, second), value in pairs.items():
        incident[first] += value
        incident[second] += value
    result = np.empty((count,) + self_values.shape[1:], dtype=complex)
    for omitted in range(count):
        physical = (self_total - self_values[omitted]) / (count - 1)
        wick_pairings = (pair_total - incident[omitted]) / (
            (count - 1) * (count - 2)
        )
        result[omitted] = physical - np.sum(wick_pairings, axis=0)
    return result


def _normalized_direction(
    direction: np.ndarray,
    expected_shape: tuple[int, ...],
) -> np.ndarray:
    values = np.asarray(direction, dtype=complex)
    if values.shape != expected_shape:
        raise ValueError("cumulant direction has the wrong shape")
    if not (
        np.all(np.isfinite(values.real))
        and np.all(np.isfinite(values.imag))
    ):
        raise ValueError("cumulant direction must be finite")
    length = float(np.linalg.norm(values))
    if length <= np.finfo(float).tiny:
        raise ValueError("cumulant direction has zero length")
    return values / length


def directional_pseudovalues(
    self_tensors: np.ndarray,
    pair_sums: Mapping[tuple[int, int], np.ndarray],
    direction: np.ndarray,
) -> DirectionalJackknife:
    """Project the complete cumulant and form delete-one pseudo-values."""

    estimate = aggregate_cumulant(self_tensors, pair_sums)
    normalized = _normalized_direction(direction, estimate.cumulant.shape)
    full_value = float(np.vdot(normalized, estimate.cumulant).real)
    deleted_tensors = delete_one_cumulants(self_tensors, pair_sums)
    deleted_values = np.asarray(
        [float(np.vdot(normalized, value).real) for value in deleted_tensors],
        dtype=float,
    )
    count = estimate.realization_count
    pseudovalues = count * full_value - (count - 1) * deleted_values
    standard_error = float(np.std(pseudovalues, ddof=1) / np.sqrt(count))
    return DirectionalJackknife(
        direction=normalized,
        estimate=full_value,
        delete_one_estimates=deleted_values,
        pseudovalues=pseudovalues,
        standard_error=standard_error,
    )


def paired_multiplier_inference(
    pseudovalues: Mapping[str, np.ndarray],
    *,
    replicates: int,
    seed: int,
    family_alpha: float = 0.05,
) -> PairedMultiplierResult:
    """Return one-sided tests and simultaneous intervals with shared weights."""

    sectors = tuple(str(key) for key in pseudovalues)
    if not sectors:
        raise ValueError("paired multiplier inference requires at least one sector")
    rows = [np.asarray(pseudovalues[key], dtype=float) for key in pseudovalues]
    if any(row.ndim != 1 for row in rows):
        raise ValueError("pseudo-values must be one-dimensional")
    counts = {row.size for row in rows}
    if len(counts) != 1 or next(iter(counts)) < 4:
        raise ValueError("sectors must share at least four realizations")
    values = np.asarray(rows, dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("pseudo-values must be finite")
    count = int(values.shape[1])
    draws = int(replicates)
    alpha = float(family_alpha)
    if draws < 100 or not 0.0 < alpha < 1.0:
        raise ValueError("multiplier configuration is invalid")
    estimates = np.mean(values, axis=1)
    sample_deviations = np.std(values, axis=1, ddof=1)
    if np.any(sample_deviations <= np.finfo(float).tiny):
        raise ValueError("pseudo-values must have nonzero variance")
    standard_errors = sample_deviations / np.sqrt(count)
    z_scores = estimates / standard_errors
    centered = values - estimates[:, None]
    rng = np.random.default_rng(int(seed))
    multipliers = rng.normal(size=(draws, count))
    bootstrap_z = (
        multipliers @ centered.T
    ) / (np.sqrt(count) * sample_deviations[None, :])
    p_values = (
        1.0 + np.sum(bootstrap_z >= z_scores[None, :], axis=0)
    ) / (draws + 1.0)
    maximum = np.max(np.abs(bootstrap_z), axis=1)
    simultaneous_quantile = float(
        np.quantile(maximum, 1.0 - alpha, method="higher")
    )
    interval_low = estimates - simultaneous_quantile * standard_errors
    interval_high = estimates + simultaneous_quantile * standard_errors
    return PairedMultiplierResult(
        sectors=sectors,
        estimates=estimates,
        standard_errors=standard_errors,
        z_scores=z_scores,
        p_values=np.asarray(p_values, dtype=float),
        interval_low=np.asarray(interval_low, dtype=float),
        interval_high=np.asarray(interval_high, dtype=float),
        simultaneous_quantile=simultaneous_quantile,
        bootstrap_z=np.asarray(bootstrap_z, dtype=float),
        replicates=draws,
        seed=int(seed),
        family_alpha=alpha,
    )


def _phase_fixed(values: np.ndarray) -> np.ndarray:
    tensor = np.asarray(values, dtype=complex)
    if tensor.size < 1 or not (
        np.all(np.isfinite(tensor.real))
        and np.all(np.isfinite(tensor.imag))
    ):
        raise ValueError("direction tensor must be nonempty and finite")
    flat = tensor.reshape(-1)
    anchor = int(np.argmax(np.abs(flat)))
    magnitude = float(np.abs(flat[anchor]))
    if magnitude <= np.finfo(float).tiny:
        raise ValueError("direction tensor has zero length")
    phase = np.conj(flat[anchor]) / magnitude
    rotated = tensor * phase
    rotated_flat = rotated.reshape(-1)
    rotated_flat[anchor] = complex(abs(rotated_flat[anchor]), 0.0)
    return rotated


def fit_direction(
    cumulants: Mapping[int, np.ndarray],
    wick_tensors: Mapping[int, np.ndarray],
    jackknife_variances: Mapping[int, float],
) -> FittedDirection:
    """Fit a phase-fixed inverse-variance direction from development tensors."""

    sizes = tuple(sorted(int(size) for size in cumulants))
    if len(sizes) < 2:
        raise ValueError("direction fitting requires at least two sizes")
    if set(sizes) != set(wick_tensors) or set(sizes) != set(jackknife_variances):
        raise ValueError("direction inputs must share the same sizes")
    shape = np.asarray(cumulants[sizes[0]]).shape
    normalized: list[np.ndarray] = []
    variances: list[float] = []
    for size in sizes:
        cumulant = np.asarray(cumulants[size], dtype=complex)
        wick = np.asarray(wick_tensors[size], dtype=complex)
        if cumulant.shape != shape or wick.shape != shape:
            raise ValueError("direction tensors must share one shape")
        wick_norm = float(np.linalg.norm(wick))
        variance = float(jackknife_variances[size])
        if not np.isfinite(wick_norm) or wick_norm <= np.finfo(float).tiny:
            raise ValueError("complete Wick tensor has zero norm")
        if not np.isfinite(variance) or variance <= 0.0:
            raise ValueError("jackknife variances must be positive")
        normalized.append(_phase_fixed(cumulant / wick_norm))
        variances.append(variance)
    raw_weights = 1.0 / np.asarray(variances, dtype=float)
    cap = float(10.0 * np.median(raw_weights))
    capped_weights = np.minimum(raw_weights, cap)
    stacked = np.asarray(normalized, dtype=complex)
    average = np.tensordot(
        capped_weights / np.sum(capped_weights),
        stacked,
        axes=(0, 0),
    )
    average = _phase_fixed(average)
    length = float(np.linalg.norm(average))
    if length <= np.finfo(float).tiny:
        raise ValueError("phase-aligned development tensors cancel")
    return FittedDirection(
        direction=np.asarray(average / length, dtype=complex),
        sizes=sizes,
        normalized_tensors=stacked,
        raw_weights=raw_weights,
        capped_weights=capped_weights,
        cap=cap,
    )


def validate_direction(
    direction: np.ndarray,
    cumulant: np.ndarray,
    wick_tensor: np.ndarray,
    *,
    p_value: float,
    interval_low: float,
    threshold: float = 0.025,
    minimum_overlap: float = 0.5,
) -> DirectionValidation:
    """Validate a development direction without refitting it."""

    candidate = _phase_fixed(np.asarray(direction, dtype=complex))
    candidate /= np.linalg.norm(candidate)
    cumulant_values = np.asarray(cumulant, dtype=complex)
    wick_values = np.asarray(wick_tensor, dtype=complex)
    if cumulant_values.shape != candidate.shape or wick_values.shape != candidate.shape:
        raise ValueError("validation tensors disagree with the frozen direction")
    wick_norm = float(np.linalg.norm(wick_values))
    if wick_norm <= np.finfo(float).tiny:
        raise ValueError("validation Wick tensor has zero norm")
    target = _phase_fixed(cumulant_values / wick_norm)
    target /= np.linalg.norm(target)
    overlap = float(np.vdot(candidate, target).real)
    probability = float(p_value)
    lower = float(interval_low)
    alpha = float(threshold)
    minimum = float(minimum_overlap)
    if not (
        np.isfinite(probability)
        and 0.0 <= probability <= 1.0
        and np.isfinite(lower)
        and 0.0 < alpha < 1.0
        and -1.0 <= minimum <= 1.0
    ):
        raise ValueError("direction validation thresholds are invalid")
    significant = probability < alpha
    positive = lower > 0.0
    overlap_pass = overlap >= minimum
    return DirectionValidation(
        overlap=overlap,
        p_value=probability,
        interval_low=lower,
        significant_positive=significant,
        positive_interval=positive,
        overlap_pass=overlap_pass,
        passed=bool(significant and positive and overlap_pass),
    )


def equivalence_bound(
    separable_directional_excess: float,
    gaussian_calibration_abs_quantile_95: float,
) -> EquivalenceBound:
    """Freeze the larger of the physical-quarter and calibration bounds."""

    excess = float(separable_directional_excess)
    calibration = float(gaussian_calibration_abs_quantile_95)
    if not np.isfinite(excess) or not np.isfinite(calibration) or calibration < 0.0:
        raise ValueError("equivalence-bound inputs are invalid")
    separable_component = 0.25 * abs(excess)
    gaussian_component = abs(calibration)
    return EquivalenceBound(
        separable_component=separable_component,
        gaussian_component=gaussian_component,
        value=max(separable_component, gaussian_component),
    )


def classify_sector(
    *,
    estimate: float,
    p_value: float,
    interval_low: float,
    interval_high: float,
    bound: float,
    threshold: float = 0.025,
) -> SectorDecision:
    """Classify positive, equivalent, rotated, or inconclusive evidence."""

    theta = float(estimate)
    probability = float(p_value)
    lower = float(interval_low)
    upper = float(interval_high)
    delta = float(bound)
    alpha = float(threshold)
    if not all(np.isfinite(value) for value in (theta, probability, lower, upper, delta, alpha)):
        raise ValueError("sector decision inputs must be finite")
    if not (0.0 <= probability <= 1.0 and lower <= upper and delta > 0.0):
        raise ValueError("sector decision inputs are invalid")
    if theta > 0.0 and probability < alpha and lower > 0.0:
        status = "positive"
    elif upper < 0.0:
        status = "direction_failure"
    elif lower > -delta and upper < delta:
        status = "equivalent"
    else:
        status = "inconclusive"
    return SectorDecision(
        status=status,
        estimate=theta,
        p_value=probability,
        interval_low=lower,
        interval_high=upper,
        equivalence_bound=delta,
    )


def choose_prospective_count(
    pseudovalues: Mapping[str, np.ndarray],
    lower_effects: Mapping[str, float],
    equivalence_bounds: Mapping[str, float],
    *,
    candidate_counts: Sequence[int] = (64, 96, 128),
    trials: int = 500,
    multiplier_replicates: int = 499,
    seed: int,
    positive_target: float = 0.90,
    equivalence_target: float = 0.80,
    sector_threshold: float = 0.025,
) -> ProspectivePowerResult:
    """Choose a prospective count using development pseudo-values only."""

    sectors = tuple(str(key) for key in pseudovalues)
    if len(sectors) < 2 or set(sectors) != set(lower_effects) or set(sectors) != set(equivalence_bounds):
        raise ValueError("prospective inputs must share at least two sectors")
    rows = np.asarray([pseudovalues[sector] for sector in sectors], dtype=float)
    if rows.ndim != 2 or rows.shape[1] < 4 or not np.all(np.isfinite(rows)):
        raise ValueError("development pseudo-values are invalid")
    if np.any(np.std(rows, axis=1, ddof=1) <= np.finfo(float).tiny):
        raise ValueError("development pseudo-values require nonzero variance")
    counts = tuple(int(value) for value in candidate_counts)
    if not counts or any(value < 4 for value in counts) or tuple(sorted(set(counts))) != counts:
        raise ValueError("candidate counts must be unique and increasing")
    repetitions = int(trials)
    bootstrap = int(multiplier_replicates)
    if repetitions < 50 or bootstrap < 100:
        raise ValueError("prospective calibration is too small")
    positive_goal = float(positive_target)
    equivalence_goal = float(equivalence_target)
    alpha = float(sector_threshold)
    if not (0.0 < positive_goal <= 1.0 and 0.0 < equivalence_goal <= 1.0 and 0.0 < alpha < 1.0):
        raise ValueError("prospective targets are invalid")
    lower = np.asarray([lower_effects[sector] for sector in sectors], dtype=float)
    bounds = np.asarray([equivalence_bounds[sector] for sector in sectors], dtype=float)
    if not np.all(np.isfinite(lower)) or not np.all(np.isfinite(bounds)) or np.any(bounds <= 0.0):
        raise ValueError("prospective effects and bounds are invalid")
    residuals = rows - np.mean(rows, axis=1, keepdims=True)
    rng = np.random.default_rng(int(seed))
    positive_power = np.zeros(len(counts), dtype=float)
    equivalence_power = np.zeros(len(counts), dtype=float)
    for count_index, count in enumerate(counts):
        positive_successes = 0
        equivalence_successes = 0
        for _ in range(repetitions):
            indices = rng.integers(0, rows.shape[1], size=count)
            sampled = residuals[:, indices]
            multiplier_seed = int(rng.integers(0, np.iinfo(np.int64).max))
            positive_result = paired_multiplier_inference(
                {
                    sector: sampled[index] + lower[index]
                    for index, sector in enumerate(sectors)
                },
                replicates=bootstrap,
                seed=multiplier_seed,
            )
            positive_successes += int(
                np.all(positive_result.p_values < alpha)
                and np.all(positive_result.interval_low > 0.0)
            )
            equivalence_result = paired_multiplier_inference(
                {
                    sector: sampled[index]
                    for index, sector in enumerate(sectors)
                },
                replicates=bootstrap,
                seed=multiplier_seed + 1,
            )
            equivalence_successes += int(
                np.all(equivalence_result.interval_low > -bounds)
                and np.all(equivalence_result.interval_high < bounds)
            )
        positive_power[count_index] = positive_successes / repetitions
        equivalence_power[count_index] = equivalence_successes / repetitions
    selected: int | None = None
    for index, count in enumerate(counts):
        if (
            positive_power[index] >= positive_goal
            and equivalence_power[index] >= equivalence_goal
        ):
            selected = count
            break
    return ProspectivePowerResult(
        selected_count=selected,
        candidate_counts=counts,
        joint_positive_power=positive_power,
        joint_equivalence_power=equivalence_power,
        positive_target=positive_goal,
        equivalence_target=equivalence_goal,
        trials=repetitions,
        multiplier_replicates=bootstrap,
        seed=int(seed),
        branch=("prospective_ready" if selected is not None else "prospective_power_failure"),
    )


def select_complete_covariance_branch(
    central: SectorDecision,
    adjacent: SectorDecision,
    *,
    sparse_positive: bool = False,
    omnibus_positive: bool = False,
    numerical_ok: bool = True,
    prospective_power_ok: bool = True,
) -> BranchDecision:
    """Apply the frozen eight-branch precedence without data-dependent edits."""

    allowed = {"positive", "equivalent", "direction_failure", "inconclusive"}
    if central.status not in allowed or adjacent.status not in allowed:
        raise ValueError("unknown primary-sector status")
    statuses = (central.status, adjacent.status)
    if not numerical_ok:
        branch = "numerical_feasibility_failure"
    elif not prospective_power_ok:
        branch = "prospective_power_failure"
    elif statuses == ("positive", "positive"):
        branch = "complete_covariance_geometric_cumulant"
    elif (
        statuses == ("positive", "equivalent")
        or statuses == ("equivalent", "positive")
    ):
        branch = "sector_dependent_cumulant"
    elif statuses == ("equivalent", "equivalent") and sparse_positive:
        branch = "sparse_coordinate_memory"
    elif statuses == ("equivalent", "equivalent"):
        branch = "covariance_explained_geometry"
    elif "direction_failure" in statuses and omnibus_positive:
        branch = "unpredicted_tensor_rotation"
    else:
        branch = "underpowered_inconclusive"
    return BranchDecision(
        branch=branch,
        central_status=central.status,
        adjacent_status=adjacent.status,
        sparse_positive=bool(sparse_positive),
        omnibus_positive=bool(omnibus_positive),
        numerical_ok=bool(numerical_ok),
        prospective_power_ok=bool(prospective_power_ok),
    )
