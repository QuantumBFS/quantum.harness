"""Pure Bernoulli finite-shot statistics for closed-loop decisions.

The functions in this module operate only on public success counts.  They do
not import an experiment executor, simulator state, random seed, or validation
oracle.  The KL confidence intervals follow Kaufmann and Kalyanakrishnan
(COLT 2013, Theorem 1) with

``beta(t, delta) = log(x) + log(log(x))``,
``x = k1 * K * t**alpha / delta``.

S4-D freezes ``alpha=2.1`` and ``k1=13``.  The confidence claim assumes that
each arm has a fixed Bernoulli mean within an episode and that observations
are conditionally independent; iteration drift violates that assumption.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import operator
from typing import Iterable


DEFAULT_KL_LUCB_ALPHA = 2.1
DEFAULT_KL_LUCB_K1 = 13.0


def _nonnegative_integer(value: int, *, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        integer = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if integer < 0:
        raise ValueError(f"{name} must be non-negative")
    return integer


def _probability(value: float, *, name: str) -> float:
    probability = float(value)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")
    return probability


def bernoulli_kl(p: float, q: float) -> float:
    """Return ``KL(Bernoulli(p) || Bernoulli(q))``.

    The implementation evaluates the exact limiting expressions at zero and
    one.  In particular, equal endpoints have zero divergence, whereas a
    positive mass assigned to an impossible outcome has infinite divergence.
    """

    p_value = _probability(p, name="p")
    q_value = _probability(q, name="q")
    if p_value == q_value:
        return 0.0
    if q_value == 0.0 or q_value == 1.0:
        return math.inf
    if p_value == 0.0:
        return -math.log1p(-q_value)
    if p_value == 1.0:
        return -math.log(q_value)
    return (
        p_value * math.log(p_value / q_value)
        + (1.0 - p_value)
        * math.log((1.0 - p_value) / (1.0 - q_value))
    )


def kl_lucb_exploration_rate(
    round_index: int,
    delta: float,
    arm_count: int,
    *,
    alpha: float = DEFAULT_KL_LUCB_ALPHA,
    k1: float = DEFAULT_KL_LUCB_K1,
) -> float:
    """Return the Kaufmann--Kalyanakrishnan KL-LUCB exploration rate.

    ``round_index`` is the one-based KL-LUCB stage index and ``arm_count`` is
    the total number of arms.  The computation is performed in log space to
    avoid overflow in ``round_index**alpha``.
    """

    stage = _nonnegative_integer(round_index, name="round_index")
    arms = _nonnegative_integer(arm_count, name="arm_count")
    delta_value = float(delta)
    alpha_value = float(alpha)
    k1_value = float(k1)
    if stage < 1:
        raise ValueError("round_index must be at least one")
    if arms < 1:
        raise ValueError("arm_count must be at least one")
    if (
        not math.isfinite(delta_value)
        or not 0.0 < delta_value < 1.0
    ):
        raise ValueError("delta must lie strictly between zero and one")
    if not math.isfinite(alpha_value) or alpha_value <= 1.0:
        raise ValueError("alpha must be finite and greater than one")
    if not math.isfinite(k1_value) or k1_value <= 0.0:
        raise ValueError("k1 must be finite and positive")

    log_x = (
        math.log(k1_value)
        + math.log(arms)
        + alpha_value * math.log(stage)
        - math.log(delta_value)
    )
    if not math.isfinite(log_x) or log_x <= 0.0:
        raise ValueError("exploration-rate logarithm must be positive")
    return log_x + math.log(log_x)


def bernoulli_kl_interval(
    empirical_mean: float,
    sample_count: int,
    threshold: float,
) -> tuple[float, float]:
    """Invert a Bernoulli KL ball into a closed confidence interval.

    The returned bounds solve

    ``sample_count * KL(empirical_mean || q) <= threshold``.

    An unobserved arm has the vacuous interval ``[0, 1]``.  At empirical means
    zero and one, analytic limiting forms are used instead of perturbing the
    data away from the endpoints.
    """

    mean = _probability(empirical_mean, name="empirical_mean")
    count = _nonnegative_integer(sample_count, name="sample_count")
    threshold_value = float(threshold)
    if not math.isfinite(threshold_value) or threshold_value < 0.0:
        raise ValueError("threshold must be finite and non-negative")
    if count == 0:
        return 0.0, 1.0
    if threshold_value == 0.0:
        return mean, mean

    radius = threshold_value / count
    if mean == 0.0:
        return 0.0, -math.expm1(-radius)
    if mean == 1.0:
        return math.exp(-radius), 1.0

    # On [0, mean], KL(mean || q) decreases monotonically from infinity to
    # zero.  ``lower_outside`` is infeasible and ``lower_inside`` feasible.
    lower_outside = 0.0
    lower_inside = mean
    for _ in range(80):
        midpoint = (lower_outside + lower_inside) / 2.0
        if bernoulli_kl(mean, midpoint) > radius:
            lower_outside = midpoint
        else:
            lower_inside = midpoint
    lower = lower_inside

    # On [mean, 1], the same divergence increases from zero to infinity.
    upper_inside = mean
    upper_outside = 1.0
    for _ in range(80):
        midpoint = (upper_inside + upper_outside) / 2.0
        if bernoulli_kl(mean, midpoint) > radius:
            upper_outside = midpoint
        else:
            upper_inside = midpoint
    upper = upper_inside
    return lower, upper


def bernoulli_kl_confidence_bounds(
    successes: int,
    trials: int,
    *,
    round_index: int,
    delta: float,
    arm_count: int,
    alpha: float = DEFAULT_KL_LUCB_ALPHA,
    k1: float = DEFAULT_KL_LUCB_K1,
) -> tuple[float, float]:
    """Return KL-LUCB bounds from aggregate public Bernoulli counts."""

    success_count = _nonnegative_integer(successes, name="successes")
    trial_count = _nonnegative_integer(trials, name="trials")
    if success_count > trial_count:
        raise ValueError("successes cannot exceed trials")
    threshold = kl_lucb_exploration_rate(
        round_index,
        delta,
        arm_count,
        alpha=alpha,
        k1=k1,
    )
    mean = success_count / trial_count if trial_count else 0.0
    return bernoulli_kl_interval(mean, trial_count, threshold)


@dataclass(frozen=True)
class BernoulliBatchResult:
    """One public batch reduced to the sufficient Bernoulli counts."""

    candidate_id: str
    successes: int
    trials: int

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id must be non-empty")
        success_count = _nonnegative_integer(
            self.successes, name="successes"
        )
        trial_count = _nonnegative_integer(self.trials, name="trials")
        if success_count > trial_count:
            raise ValueError("successes cannot exceed trials")


@dataclass(frozen=True)
class BernoulliArmStatistics:
    """Immutable aggregate statistics for one catalog candidate."""

    candidate_id: str
    successes: int = 0
    trials: int = 0
    batch_count: int = 0

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id must be non-empty")
        success_count = _nonnegative_integer(
            self.successes, name="successes"
        )
        trial_count = _nonnegative_integer(self.trials, name="trials")
        _nonnegative_integer(self.batch_count, name="batch_count")
        if success_count > trial_count:
            raise ValueError("successes cannot exceed trials")

    @property
    def empirical_mean(self) -> float | None:
        if self.trials == 0:
            return None
        return self.successes / self.trials

    def add_batch(
        self, batch: BernoulliBatchResult
    ) -> BernoulliArmStatistics:
        if batch.candidate_id != self.candidate_id:
            raise ValueError("batch candidate does not match arm")
        return BernoulliArmStatistics(
            candidate_id=self.candidate_id,
            successes=self.successes + batch.successes,
            trials=self.trials + batch.trials,
            batch_count=self.batch_count + 1,
        )

    def confidence_bounds(
        self,
        *,
        round_index: int,
        delta: float,
        arm_count: int,
        alpha: float = DEFAULT_KL_LUCB_ALPHA,
        k1: float = DEFAULT_KL_LUCB_K1,
    ) -> tuple[float, float]:
        return bernoulli_kl_confidence_bounds(
            self.successes,
            self.trials,
            round_index=round_index,
            delta=delta,
            arm_count=arm_count,
            alpha=alpha,
            k1=k1,
        )


def aggregate_arm_statistics(
    candidate_ids: Iterable[str],
    batches: Iterable[BernoulliBatchResult],
) -> tuple[BernoulliArmStatistics, ...]:
    """Aggregate batches while preserving the declared catalog tie order."""

    ids = tuple(candidate_ids)
    if not ids or any(not candidate_id for candidate_id in ids):
        raise ValueError("candidate catalog must be non-empty")
    if len(ids) != len(set(ids)):
        raise ValueError("candidate catalog contains duplicate ids")
    statistics = {
        candidate_id: BernoulliArmStatistics(candidate_id)
        for candidate_id in ids
    }
    for batch in batches:
        if batch.candidate_id not in statistics:
            raise ValueError(
                f"batch references unknown candidate {batch.candidate_id!r}"
            )
        statistics[batch.candidate_id] = statistics[
            batch.candidate_id
        ].add_batch(batch)
    return tuple(statistics[candidate_id] for candidate_id in ids)


@dataclass(frozen=True)
class KLArmConfidenceResult:
    """One arm's aggregate estimate and KL confidence bounds."""

    candidate_id: str
    successes: int
    trials: int
    empirical_mean: float
    lower: float
    upper: float


@dataclass(frozen=True)
class KLLUCBEvaluation:
    """Best/challenger pair and the frozen KL-LUCB stopping decision."""

    arms: tuple[KLArmConfidenceResult, ...]
    best_candidate_id: str
    challenger_candidate_id: str
    lower_best: float
    upper_challenger: float
    confidence_gap: float
    epsilon: float
    certified: bool


def evaluate_kl_lucb(
    statistics: Iterable[BernoulliArmStatistics],
    *,
    round_index: int,
    delta: float,
    epsilon: float,
    alpha: float = DEFAULT_KL_LUCB_ALPHA,
    k1: float = DEFAULT_KL_LUCB_K1,
) -> KLLUCBEvaluation:
    """Evaluate the empirical-best/challenger pair and stopping condition.

    Input order is the deterministic catalog tie-break order.  Every arm must
    have at least one valid trial, matching the frozen initialize-all-arms
    protocol.  The challenger is the non-best arm with the largest upper KL
    bound.  Certification occurs exactly when
    ``U_challenger - L_best <= epsilon``.
    """

    arms = tuple(statistics)
    if len(arms) < 2:
        raise ValueError("KL-LUCB requires at least two arms")
    ids = tuple(arm.candidate_id for arm in arms)
    if len(ids) != len(set(ids)):
        raise ValueError("arm statistics contain duplicate candidate ids")
    if any(arm.trials == 0 for arm in arms):
        raise ValueError("every KL-LUCB arm must have at least one trial")
    epsilon_value = float(epsilon)
    if not math.isfinite(epsilon_value) or epsilon_value < 0.0:
        raise ValueError("epsilon must be finite and non-negative")

    results = tuple(
        KLArmConfidenceResult(
            candidate_id=arm.candidate_id,
            successes=arm.successes,
            trials=arm.trials,
            empirical_mean=arm.successes / arm.trials,
            lower=bounds[0],
            upper=bounds[1],
        )
        for arm in arms
        for bounds in (
            arm.confidence_bounds(
                round_index=round_index,
                delta=delta,
                arm_count=len(arms),
                alpha=alpha,
                k1=k1,
            ),
        )
    )
    # ``max`` keeps the first item on exact ties, preserving catalog order.
    best = max(results, key=lambda result: result.empirical_mean)
    challengers = tuple(
        result
        for result in results
        if result.candidate_id != best.candidate_id
    )
    challenger = max(challengers, key=lambda result: result.upper)
    confidence_gap = challenger.upper - best.lower
    return KLLUCBEvaluation(
        arms=results,
        best_candidate_id=best.candidate_id,
        challenger_candidate_id=challenger.candidate_id,
        lower_best=best.lower,
        upper_challenger=challenger.upper,
        confidence_gap=confidence_gap,
        epsilon=epsilon_value,
        certified=confidence_gap <= epsilon_value,
    )
