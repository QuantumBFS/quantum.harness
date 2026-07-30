"""Discover model degree with an adaptive, confidence-bounded noisy holdout.

Unlike the fixed-holdout experiment, this learner requests validation words
on a geometric schedule and stops as soon as an empirical-Bernstein interval
proves either clear misspecification or agreement with the inferred noise
floor.  A global failure budget is split over every possible interval query.
Clean labels are evaluated only after the degree decision has been locked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from hidden_oracle import (
    CleanDomainEvaluator,
    CommonXorFixedDesignFreshNoiseStream,
    CommonXorFreshNoiseStream,
    DOMAIN_SIZE,
    FixedDesignFreshNoiseStream,
    FreshNoiseStream,
    OUTPUT_BITS,
)
from train_adaptive_degree_discovery import (
    d_optimal_ids,
    input_ids,
    polynomial_features,
    posterior_word_entropy,
)
from train_quadratic_discovery import (
    clean_metrics,
    coefficients_to_values,
    project_coefficients,
    projection_weights,
    values_to_bits,
)
from train_tabular_bayes import PairwiseNoiseBayesianTruthTable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--degrees", default="1,2,3")
    parser.add_argument("--max-stage-steps", type=int, default=150)
    parser.add_argument("--min-stage-steps", type=int, default=30)
    parser.add_argument("--eval-every", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--holdout-look-sizes", default="128,256,512,1024,2048,4096,8192")
    parser.add_argument("--global-failure-probability", type=float, default=0.05)
    parser.add_argument("--noise-rate", type=float, default=0.25)
    parser.add_argument(
        "--noise-mode",
        choices=("independent", "common-xor"),
        default="independent",
    )
    parser.add_argument(
        "--independent-noise-rate",
        type=float,
        default=0.05,
    )
    parser.add_argument(
        "--noise-confidence-unit",
        choices=("bit", "word"),
        default="bit",
    )
    parser.add_argument(
        "--carry-noise-calibration-across-degrees",
        action="store_true",
    )
    parser.add_argument("--initial-noise-rate", type=float, default=0.10)
    parser.add_argument("--noise-prior-pairs", type=float, default=1000.0)
    parser.add_argument("--base-seed", type=int, default=317_100)
    parser.add_argument("--projection-ridge", type=float, default=1e-3)
    parser.add_argument("--coefficient-prior-std", type=float, default=1.0)
    parser.add_argument("--rounding-threshold", type=float, default=0.10)
    parser.add_argument("--accept-gap", type=float, default=0.035)
    parser.add_argument("--reject-gap", type=float, default=0.15)
    parser.add_argument("--stable-signature-checks", type=int, default=3)
    parser.add_argument(
        "--unstable-holdout-words-per-check",
        type=int,
        default=0,
        help=(
            "optional cap on newly requested holdout words before a "
            "coefficient signature is acceptance-ready; zero is unlimited"
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class BoundedAccumulator:
    count: int = 0
    total: float = 0.0
    total_square: float = 0.0

    def update(self, values: np.ndarray) -> None:
        flattened = np.asarray(values, dtype=np.float64).reshape(-1)
        self.count += int(flattened.size)
        self.total += float(flattened.sum())
        self.total_square += float(np.square(flattened).sum())

    @property
    def mean(self) -> float:
        return self.total / self.count if self.count else 0.5

    @property
    def sample_variance(self) -> float:
        if self.count < 2:
            return 0.25
        centered = self.total_square - self.total * self.total / self.count
        return max(centered / (self.count - 1), 0.0)


class DisjointPairNoiseEstimator:
    """Estimate p from independent pairs without access to clean labels."""

    def __init__(self, confidence_unit: str) -> None:
        if confidence_unit not in {"bit", "word"}:
            raise ValueError("confidence unit must be bit or word")
        self.confidence_unit = confidence_unit
        self.pending = np.zeros(
            (DOMAIN_SIZE, OUTPUT_BITS),
            dtype=np.uint8,
        )
        self.has_pending = np.zeros(DOMAIN_SIZE, dtype=bool)
        self.disagreement = BoundedAccumulator()

    def update(
        self,
        ids: torch.Tensor,
        noisy_targets: torch.Tensor,
    ) -> None:
        ids_array = ids.cpu().numpy()
        targets = noisy_targets.cpu().numpy().astype(np.uint8)
        for input_id, target in zip(ids_array, targets, strict=True):
            index = int(input_id)
            if self.has_pending[index]:
                difference = (
                    self.pending[index] != target
                ).astype(np.float64)
                if self.confidence_unit == "word":
                    self.disagreement.update(
                        np.array([float(np.mean(difference))])
                    )
                else:
                    self.disagreement.update(difference)
                self.has_pending[index] = False
            else:
                self.pending[index] = target
                self.has_pending[index] = True


def empirical_bernstein_interval(
    accumulator: BoundedAccumulator,
    delta: float,
) -> tuple[float, float, float]:
    if accumulator.count < 2:
        return 0.0, 1.0, 1.0
    log_term = math.log(3.0 / delta)
    radius = math.sqrt(
        2.0
        * accumulator.sample_variance
        * log_term
        / accumulator.count
    ) + 3.0 * log_term / accumulator.count
    return (
        max(0.0, accumulator.mean - radius),
        min(1.0, accumulator.mean + radius),
        radius,
    )


def disagreement_to_noise(disagreement: float) -> float:
    clipped = min(max(disagreement, 0.0), 0.5)
    return 0.5 * (1.0 - math.sqrt(max(1.0 - 2.0 * clipped, 0.0)))


def noise_interval(
    estimator: DisjointPairNoiseEstimator,
    delta: float,
) -> tuple[float, float, float, float]:
    lower_d, upper_d, _ = empirical_bernstein_interval(
        estimator.disagreement,
        delta,
    )
    lower_p = disagreement_to_noise(lower_d)
    upper_p = disagreement_to_noise(upper_d)
    estimate = disagreement_to_noise(estimator.disagreement.mean)
    return lower_p, upper_p, estimate, upper_p - lower_p


def add_holdout_words(
    predicted_values: np.ndarray,
    stream: FreshNoiseStream,
    accumulator: BoundedAccumulator,
    words: int,
    device: torch.device,
) -> None:
    remaining = words
    while remaining > 0:
        inputs, noisy_targets = stream.sample()
        ids = input_ids(inputs, device).cpu().numpy()
        take = min(remaining, len(ids))
        predicted = values_to_bits(predicted_values[ids[:take]])
        observed = noisy_targets[:take].cpu().numpy().astype(np.uint8)
        word_disagreement = np.mean(predicted != observed, axis=1)
        accumulator.update(word_disagreement)
        remaining -= take


def interval_record(
    accumulator: BoundedAccumulator,
    estimator: DisjointPairNoiseEstimator,
    delta: float,
) -> dict[str, float | int]:
    q_lower, q_upper, q_radius = empirical_bernstein_interval(
        accumulator,
        delta,
    )
    p_lower, p_upper, p_estimate, p_width = noise_interval(
        estimator,
        delta,
    )
    return {
        "holdout_words": accumulator.count,
        "observed_holdout_disagreement_rate": accumulator.mean,
        "holdout_disagreement_lower": q_lower,
        "holdout_disagreement_upper": q_upper,
        "holdout_interval_radius": q_radius,
        "disjoint_noise_pairs": estimator.disagreement.count,
        "selection_estimated_noise_rate": p_estimate,
        "selection_noise_rate_lower": p_lower,
        "selection_noise_rate_upper": p_upper,
        "selection_noise_interval_width": p_width,
        "holdout_excess_lower": q_lower - p_upper,
        "holdout_excess_point": accumulator.mean - p_estimate,
        "holdout_excess_upper": q_upper - p_lower,
    }


def sequential_evidence(
    predicted_values: np.ndarray,
    stream: FreshNoiseStream,
    accumulator: BoundedAccumulator,
    noise_estimator: DisjointPairNoiseEstimator,
    look_sizes: list[int],
    delta: float,
    accept_ready: bool,
    accept_gap: float,
    reject_gap: float,
    unstable_words_per_check: int,
    device: torch.device,
) -> tuple[str, dict[str, float | int], int]:
    words_before = accumulator.count
    last = interval_record(accumulator, noise_estimator, delta)
    if accumulator.count >= look_sizes[0]:
        if last["holdout_excess_lower"] > reject_gap:
            return "reject", last, 0
        if accept_ready and (
            last["holdout_excess_lower"] >= -accept_gap
            and last["holdout_excess_upper"] <= accept_gap
        ):
            return "accept", last, 0
        if (
            not accept_ready
            and last["holdout_excess_point"] <= reject_gap
        ):
            return "defer", last, 0
    for look_size in look_sizes:
        if look_size <= accumulator.count:
            continue
        target_size = look_size
        if not accept_ready and unstable_words_per_check > 0:
            target_size = min(
                target_size,
                words_before + unstable_words_per_check,
            )
        if target_size <= accumulator.count:
            return "defer", last, accumulator.count - words_before
        add_holdout_words(
            predicted_values,
            stream,
            accumulator,
            target_size - accumulator.count,
            device,
        )
        last = interval_record(accumulator, noise_estimator, delta)
        if last["holdout_excess_lower"] > reject_gap:
            return "reject", last, accumulator.count - words_before
        if accept_ready and (
            last["holdout_excess_lower"] >= -accept_gap
            and last["holdout_excess_upper"] <= accept_gap
        ):
            return "accept", last, accumulator.count - words_before

        # Before a coefficient signature is stable enough for acceptance,
        # spend beyond the first pilot only when the point estimate suggests
        # a potentially rejectable model.  Deferral makes no selection claim.
        if not accept_ready and accumulator.count >= look_sizes[0]:
            if last["holdout_excess_point"] <= reject_gap:
                return "defer", last, accumulator.count - words_before
            if last["holdout_excess_upper"] < reject_gap:
                return "defer", last, accumulator.count - words_before
            if (
                unstable_words_per_check > 0
                and accumulator.count - words_before
                >= unstable_words_per_check
            ):
                return "defer", last, accumulator.count - words_before

    return "unresolved", last, accumulator.count - words_before


def main() -> None:
    args = parse_args()
    degrees = [int(token) for token in args.degrees.split(",")]
    look_sizes = [
        int(token) for token in args.holdout_look_sizes.split(",")
    ]
    if not degrees or degrees != sorted(set(degrees)):
        raise ValueError("degrees must be strictly increasing")
    if not look_sizes or look_sizes != sorted(set(look_sizes)):
        raise ValueError("look sizes must be strictly increasing")
    if look_sizes[0] <= 1:
        raise ValueError("first holdout look must contain at least two words")
    if not 0.0 < args.global_failure_probability < 1.0:
        raise ValueError("global failure probability must lie in (0,1)")

    maximum_checks = (
        len(degrees)
        * math.ceil(args.max_stage_steps / args.eval_every)
    )
    interval_query_bound = 2 * maximum_checks * len(look_sizes)
    interval_delta = (
        args.global_failure_probability / interval_query_bound
    )
    device = torch.device("cpu")
    bit_weights = 1 << np.arange(OUTPUT_BITS, dtype=np.int64)
    if args.noise_mode == "common-xor":
        validation_stream = CommonXorFreshNoiseStream(
            batch_size=look_sizes[0],
            marginal_noise_rate=args.noise_rate,
            independent_noise_rate=args.independent_noise_rate,
            seed=args.base_seed + 90_000,
            device=device,
        )
        common_noise_rate = validation_stream.common_noise_rate
    else:
        validation_stream = FreshNoiseStream(
            batch_size=look_sizes[0],
            noise_rate=args.noise_rate,
            seed=args.base_seed + 90_000,
            device=device,
        )
        common_noise_rate = 0.0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    stage_records: list[dict[str, Any]] = []
    accepted_stage: dict[str, Any] | None = None
    cumulative_training_examples = 0
    cumulative_holdout_words = 0
    shared_selection_noise = (
        DisjointPairNoiseEstimator(args.noise_confidence_unit)
        if args.carry_noise_calibration_across_degrees
        else None
    )

    for stage_index, degree in enumerate(degrees):
        features, effect_features, metadata = polynomial_features(degree)
        design_ids, design = d_optimal_ids(effect_features)
        if args.noise_mode == "common-xor":
            stream = CommonXorFixedDesignFreshNoiseStream(
                batch_size=args.batch_size,
                marginal_noise_rate=args.noise_rate,
                independent_noise_rate=args.independent_noise_rate,
                seed=args.base_seed + 1_000 * stage_index,
                device=device,
                design_ids=torch.from_numpy(design_ids),
            )
        else:
            stream = FixedDesignFreshNoiseStream(
                batch_size=args.batch_size,
                noise_rate=args.noise_rate,
                seed=args.base_seed + 1_000 * stage_index,
                device=device,
                design_ids=torch.from_numpy(design_ids),
            )
        learner = PairwiseNoiseBayesianTruthTable(
            initial_noise_rate=args.initial_noise_rate,
            prior_jitter=1e-6,
            noise_prior_pairs=args.noise_prior_pairs,
            seed=args.base_seed + 10_000 + stage_index,
            device=device,
        )
        selection_noise = (
            shared_selection_noise
            if shared_selection_noise is not None
            else DisjointPairNoiseEstimator(args.noise_confidence_unit)
        )
        prior_generator = np.random.default_rng(
            args.base_seed + 20_000 + stage_index
        )
        random_prior = prior_generator.normal(
            0.0,
            args.coefficient_prior_std,
            size=features.shape[1],
        )
        checks: list[dict[str, Any]] = []
        holdouts: dict[tuple[int, ...], BoundedAccumulator] = {}
        previous_signature: tuple[int, ...] | None = None
        signature_streak = 0
        consecutive_rejects = 0
        decision: str | None = None
        final_coefficients: np.ndarray | None = None

        for step in range(1, args.max_stage_steps + 1):
            inputs, noisy_targets = stream.sample()
            ids = input_ids(inputs, device)
            learner.update(ids, noisy_targets)
            selection_noise.update(ids, noisy_targets)
            cumulative_training_examples += args.batch_size
            if step % args.eval_every != 0 and step != args.max_stage_steps:
                continue
            if step < args.min_stage_steps:
                continue

            probabilities = learner.probabilities().cpu().numpy()
            observations = learner.observation_count.cpu().numpy()
            expected_values = probabilities @ bit_weights
            weights = projection_weights(
                probabilities,
                observations,
                "observation",
            )
            continuous = project_coefficients(
                features,
                expected_values,
                weights,
                random_prior,
                args.projection_ridge,
            )
            integer = np.rint(continuous).astype(np.int64)
            predicted_values = coefficients_to_values(features, integer)
            residual = float(np.max(np.abs(continuous - integer)))
            signature = tuple(int(value) for value in integer)
            if signature == previous_signature:
                signature_streak += 1
            else:
                signature_streak = 1
                previous_signature = signature
            accumulator = holdouts.setdefault(
                signature,
                BoundedAccumulator(),
            )
            accept_ready = (
                residual < args.rounding_threshold
                and signature_streak >= args.stable_signature_checks
            )
            evidence, validation, words_added = sequential_evidence(
                predicted_values,
                validation_stream,
                accumulator,
                selection_noise,
                look_sizes,
                interval_delta,
                accept_ready,
                args.accept_gap,
                args.reject_gap,
                args.unstable_holdout_words_per_check,
                device,
            )
            if evidence == "reject":
                consecutive_rejects += 1
            else:
                consecutive_rejects = 0
            cumulative_holdout_words += words_added
            record = {
                "degree": degree,
                "stage_step": step,
                "stage_training_examples": step * args.batch_size,
                "cumulative_training_examples": cumulative_training_examples,
                "cumulative_holdout_words": cumulative_holdout_words,
                "cumulative_noisy_oracle_words": (
                    cumulative_training_examples
                    + cumulative_holdout_words
                ),
                "elapsed_seconds": time.perf_counter() - start,
                "candidate_count": int(features.shape[1]),
                "learner_estimated_noise_rate": learner.estimated_noise_rate,
                "maximum_rounding_residual": residual,
                "active_integer_coefficients": int(np.count_nonzero(integer)),
                "coefficient_signature_streak": signature_streak,
                "acceptance_ready": accept_ready,
                "sequential_evidence": evidence,
                "consecutive_reject_evidence": consecutive_rejects,
                "new_holdout_words": words_added,
                "mean_design_word_posterior_entropy": posterior_word_entropy(
                    probabilities,
                    observations,
                ),
                "integer_coefficients": integer.tolist(),
                **validation,
            }
            checks.append(record)
            final_coefficients = integer
            if not args.quiet:
                print(
                    f"degree={degree} step={step:3d} "
                    f"p={validation['selection_estimated_noise_rate']:.4f} "
                    f"gap=[{validation['holdout_excess_lower']:+.4f},"
                    f"{validation['holdout_excess_upper']:+.4f}] "
                    f"words=+{words_added}/{validation['holdout_words']} "
                    f"round={residual:.4f} streak={signature_streak} "
                    f"evidence={evidence}",
                    flush=True,
                )
            if (
                evidence == "reject"
                and consecutive_rejects >= args.stable_signature_checks
            ):
                decision = "reject-and-expand"
                break
            if evidence == "accept":
                decision = "accept"
                break

        if decision is None:
            decision = (
                "reject-and-expand"
                if degree != degrees[-1]
                else "unresolved"
            )
        if final_coefficients is None:
            raise AssertionError("stage has no evaluated coefficients")
        coefficient_rows = [
            {**feature, "coefficient": int(coefficient)}
            for feature, coefficient in zip(
                metadata,
                final_coefficients,
                strict=True,
            )
        ]
        stage = {
            "degree": degree,
            "candidate_count": int(features.shape[1]),
            "design": design,
            "decision": decision,
            "decision_uses_clean_labels": False,
            "checks": checks,
            "final_integer_coefficients": coefficient_rows,
        }
        stage_records.append(stage)
        if decision == "accept":
            accepted_stage = stage
            break

    if accepted_stage is None:
        raise RuntimeError("no model degree was accepted")

    accepted_degree = int(accepted_stage["degree"])
    accepted_features, _, _ = polynomial_features(accepted_degree)
    accepted_coefficients = np.array(
        [
            row["coefficient"]
            for row in accepted_stage["final_integer_coefficients"]
        ],
        dtype=np.int64,
    )
    accepted_values = coefficients_to_values(
        accepted_features,
        accepted_coefficients,
    )
    evaluator = CleanDomainEvaluator(device)
    final_clean_metrics = clean_metrics(accepted_values, evaluator)

    for stage in stage_records:
        stage_features, _, _ = polynomial_features(stage["degree"])
        for check in stage["checks"]:
            check_coefficients = np.array(
                check.pop("integer_coefficients"),
                dtype=np.int64,
            )
            check_values = coefficients_to_values(
                stage_features,
                check_coefficients,
            )
            check["clean_metrics_attached_after_all_decisions"] = (
                clean_metrics(check_values, evaluator)
            )

    run = {
        "kind": "confidence-sequential-noisy-holdout-degree-discovery",
        "config": {
            "degrees": degrees,
            "max_stage_steps": args.max_stage_steps,
            "min_stage_steps": args.min_stage_steps,
            "eval_every": args.eval_every,
            "batch_size": args.batch_size,
            "holdout_look_sizes": look_sizes,
            "global_failure_probability": (
                args.global_failure_probability
            ),
            "interval_query_bound": interval_query_bound,
            "per_interval_failure_probability": interval_delta,
            "oracle_noise_rate": args.noise_rate,
            "noise_mode": args.noise_mode,
            "independent_noise_rate": (
                args.independent_noise_rate
                if args.noise_mode == "common-xor"
                else args.noise_rate
            ),
            "common_noise_rate": common_noise_rate,
            "noise_confidence_unit": args.noise_confidence_unit,
            "carry_noise_calibration_across_degrees": (
                args.carry_noise_calibration_across_degrees
            ),
            "learner_initial_noise_rate": args.initial_noise_rate,
            "noise_prior_pairs": args.noise_prior_pairs,
            "base_seed": args.base_seed,
            "projection_ridge": args.projection_ridge,
            "coefficient_prior_std": args.coefficient_prior_std,
            "rounding_threshold": args.rounding_threshold,
            "accept_gap": args.accept_gap,
            "reject_gap": args.reject_gap,
            "stable_signature_checks": args.stable_signature_checks,
            "unstable_holdout_words_per_check": (
                args.unstable_holdout_words_per_check
            ),
        },
        "verification": {
            "training_uses_only_fresh_noisy_labels": True,
            "validation_uses_independent_fresh_noisy_labels": True,
            "validation_labels_used_for_updates": False,
            "noise_interval_uses_disjoint_noisy_label_pairs": True,
            "noise_interval_independence_unit": (
                args.noise_confidence_unit
            ),
            "global_interval_failure_budget_precommitted": True,
            "clean_labels_used_for_updates": False,
            "clean_labels_used_for_degree_selection": False,
            "clean_full_domain_evaluated_after_selection_locked": True,
            "target_formula_seeded": False,
            "existing_circuit_seeded": False,
            "target_degree_seeded": False,
            "input_design_uses_output_labels": False,
        },
        "accepted_degree": accepted_degree,
        "cumulative_training_examples": cumulative_training_examples,
        "cumulative_holdout_words": cumulative_holdout_words,
        "cumulative_noisy_oracle_words": (
            cumulative_training_examples + cumulative_holdout_words
        ),
        "stages": stage_records,
        "final_clean_metrics": final_clean_metrics,
        "elapsed_seconds": time.perf_counter() - start,
    }
    run_path = args.output_dir / "run.json"
    run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    summary = {
        "run": run_path.as_posix(),
        "run_sha256": sha256(run_path),
        "accepted_degree": accepted_degree,
        "stage_decisions": [
            {
                "degree": stage["degree"],
                "decision": stage["decision"],
                "decision_step": stage["checks"][-1]["stage_step"],
                "holdout_words": stage["checks"][-1]["holdout_words"],
                "holdout_excess_interval": [
                    stage["checks"][-1]["holdout_excess_lower"],
                    stage["checks"][-1]["holdout_excess_upper"],
                ],
            }
            for stage in stage_records
        ],
        "final_clean_word_accuracy": final_clean_metrics["word_accuracy"],
        "training_examples": cumulative_training_examples,
        "holdout_words": cumulative_holdout_words,
        "total_noisy_oracle_words": (
            cumulative_training_examples + cumulative_holdout_words
        ),
    }
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
