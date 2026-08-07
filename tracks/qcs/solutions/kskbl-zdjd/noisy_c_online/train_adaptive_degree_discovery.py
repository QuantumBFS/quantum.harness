"""Select polynomial degree using only an independent fresh-noise holdout.

The learner begins with a generic linear integer model.  A degree is rejected
when its frozen predictions disagree with independently corrupted holdout
labels substantially more often than the noise rate inferred from repeated
training labels.  A degree is accepted only after consecutive holdout checks
match the inferred noise floor and integer coefficients have a safe rounding
margin.  Clean full-domain metrics are attached only after all decisions are
locked.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from scipy.linalg import qr

from hidden_oracle import (
    CleanDomainEvaluator,
    DOMAIN_SIZE,
    FixedDesignFreshNoiseStream,
    FreshNoiseStream,
    OUTPUT_BITS,
)
from train_quadratic_discovery import (
    INPUT_BITS,
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
    parser.add_argument("--validation-words", type=int, default=4096)
    parser.add_argument("--noise-rate", type=float, default=0.25)
    parser.add_argument("--initial-noise-rate", type=float, default=0.10)
    parser.add_argument("--noise-prior-pairs", type=float, default=1000.0)
    parser.add_argument("--base-seed", type=int, default=277_100)
    parser.add_argument("--projection-ridge", type=float, default=1e-3)
    parser.add_argument("--coefficient-prior-std", type=float, default=1.0)
    parser.add_argument("--rounding-threshold", type=float, default=0.10)
    parser.add_argument("--accept-gap", type=float, default=0.01)
    parser.add_argument("--reject-gap", type=float, default=0.15)
    parser.add_argument("--consecutive-checks", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def polynomial_features(
    degree: int,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    bits = ((ids[:, None] >> np.arange(INPUT_BITS)) & 1).astype(
        np.float64
    )
    effects = 2.0 * bits - 1.0
    binary_columns = [np.ones(DOMAIN_SIZE, dtype=np.float64)]
    effect_columns = [np.ones(DOMAIN_SIZE, dtype=np.float64)]
    metadata: list[dict[str, Any]] = [
        {"kind": "constant", "degree": 0, "input_bits": [], "mask": 0}
    ]
    for current_degree in range(1, degree + 1):
        for combination in itertools.combinations(
            range(INPUT_BITS),
            current_degree,
        ):
            binary_columns.append(
                np.prod(bits[:, combination], axis=1)
            )
            effect_columns.append(
                np.prod(effects[:, combination], axis=1)
            )
            metadata.append(
                {
                    "kind": f"degree-{current_degree}",
                    "degree": current_degree,
                    "input_bits": list(combination),
                    "mask": int(sum(1 << bit for bit in combination)),
                }
            )
    return (
        np.stack(binary_columns, axis=1),
        np.stack(effect_columns, axis=1),
        metadata,
    )


def d_optimal_ids(
    effect_features: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    _, _, pivots = qr(
        effect_features.T,
        mode="economic",
        pivoting=True,
        check_finite=False,
    )
    size = effect_features.shape[1]
    selected = pivots[:size].astype(np.int64)
    selected_matrix = effect_features[selected]
    diagnostics = {
        "size": int(size),
        "rank": int(np.linalg.matrix_rank(selected_matrix)),
        "condition_number": float(np.linalg.cond(selected_matrix)),
        "selection_uses_output_labels": False,
    }
    if diagnostics["rank"] != size:
        raise AssertionError("degree design is not full rank")
    return selected, diagnostics


def input_ids(inputs: torch.Tensor, device: torch.device) -> torch.Tensor:
    weights = 2 ** torch.arange(
        INPUT_BITS,
        device=device,
        dtype=torch.int64,
    )
    return (inputs.to(torch.int64) * weights).sum(dim=1)


def noisy_holdout_disagreement(
    predicted_values: np.ndarray,
    stream: FreshNoiseStream,
    validation_words: int,
    device: torch.device,
) -> dict[str, float | int]:
    total_disagreements = 0
    total_bits = 0
    batches = (validation_words + stream.batch_size - 1) // stream.batch_size
    remaining = validation_words
    for _ in range(batches):
        inputs, noisy_targets = stream.sample()
        ids = input_ids(inputs, device).cpu().numpy()
        take = min(remaining, len(ids))
        prediction = values_to_bits(predicted_values[ids[:take]])
        observed = noisy_targets[:take].cpu().numpy().astype(np.uint8)
        total_disagreements += int(np.count_nonzero(prediction != observed))
        total_bits += int(prediction.size)
        remaining -= take
    return {
        "validation_words": validation_words,
        "validation_bits": total_bits,
        "observed_disagreement_rate": total_disagreements / total_bits,
    }


def posterior_word_entropy(
    probabilities: np.ndarray,
    observations: np.ndarray,
) -> float:
    observed = probabilities[observations > 0].astype(np.float64)
    clipped = np.clip(observed, 1e-12, 1.0 - 1e-12)
    entropy = -(
        clipped * np.log2(clipped)
        + (1.0 - clipped) * np.log2(1.0 - clipped)
    )
    return float(entropy.sum(axis=1).mean())


def main() -> None:
    args = parse_args()
    degrees = [int(token) for token in args.degrees.split(",")]
    if not degrees or degrees != sorted(set(degrees)):
        raise ValueError("degrees must be a strictly increasing list")
    if min(degrees) < 1 or max(degrees) > INPUT_BITS:
        raise ValueError("degree lies outside the input dimension")
    if not 0.0 < args.noise_rate < 0.5:
        raise ValueError("noise-rate must lie between zero and 0.5")
    if args.validation_words <= 0:
        raise ValueError("validation-words must be positive")

    device = torch.device("cpu")
    bit_weights = 1 << np.arange(OUTPUT_BITS, dtype=np.int64)
    validation_stream = FreshNoiseStream(
        batch_size=min(512, args.validation_words),
        noise_rate=args.noise_rate,
        seed=args.base_seed + 90_000,
        device=device,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    stage_records: list[dict[str, Any]] = []
    accepted_stage: dict[str, Any] | None = None
    cumulative_training_examples = 0

    for stage_index, degree in enumerate(degrees):
        features, effect_features, metadata = polynomial_features(degree)
        design_ids, design = d_optimal_ids(effect_features)
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
        prior_generator = np.random.default_rng(
            args.base_seed + 20_000 + stage_index
        )
        random_prior = prior_generator.normal(
            0.0,
            args.coefficient_prior_std,
            size=features.shape[1],
        )
        checks: list[dict[str, Any]] = []
        consecutive_accepts = 0
        consecutive_rejects = 0
        decision: str | None = None
        final_coefficients: np.ndarray | None = None

        for step in range(1, args.max_stage_steps + 1):
            inputs, noisy_targets = stream.sample()
            ids = input_ids(inputs, device)
            learner.update(ids, noisy_targets)
            cumulative_training_examples += args.batch_size
            if step % args.eval_every != 0 and step != args.max_stage_steps:
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
            validation = noisy_holdout_disagreement(
                predicted_values,
                validation_stream,
                args.validation_words,
                device,
            )
            estimated_noise = learner.estimated_noise_rate
            gap = (
                float(validation["observed_disagreement_rate"])
                - estimated_noise
            )
            residual = float(np.max(np.abs(continuous - integer)))
            record = {
                "degree": degree,
                "stage_step": step,
                "stage_training_examples": step * args.batch_size,
                "cumulative_training_examples": cumulative_training_examples,
                "elapsed_seconds": time.perf_counter() - start,
                "candidate_count": int(features.shape[1]),
                "estimated_noise_rate": estimated_noise,
                "holdout_disagreement_gap": gap,
                "maximum_rounding_residual": residual,
                "active_integer_coefficients": int(np.count_nonzero(integer)),
                "mean_design_word_posterior_entropy": posterior_word_entropy(
                    probabilities,
                    observations,
                ),
                **validation,
                "integer_coefficients": integer.tolist(),
            }
            checks.append(record)
            final_coefficients = integer

            accept_eligible = step >= args.min_stage_steps and (
                residual < args.rounding_threshold
            )
            reject_eligible = (
                step >= args.min_stage_steps
                and gap > args.reject_gap
            )
            if accept_eligible and abs(gap) < args.accept_gap:
                consecutive_accepts += 1
            else:
                consecutive_accepts = 0
            # A misspecified model can remain halfway between integer
            # coefficients forever.  That must not suppress strong,
            # independently measured evidence that it predicts worse than
            # the inferred noise floor.  Rounding is therefore an acceptance
            # safeguard, while rejection depends only on fresh holdout data.
            if reject_eligible:
                consecutive_rejects += 1
            else:
                consecutive_rejects = 0

            if not args.quiet:
                print(
                    f"degree={degree} step={step:3d} "
                    f"p={estimated_noise:.4f} "
                    f"holdout_gap={gap:+.4f} "
                    f"round={residual:.4f} "
                    f"accept_seq={consecutive_accepts} "
                    f"reject_seq={consecutive_rejects}",
                    flush=True,
                )
            if consecutive_accepts >= args.consecutive_checks:
                decision = "accept"
                break
            if consecutive_rejects >= args.consecutive_checks:
                decision = "reject-and-expand"
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

    accepted_degree = accepted_stage["degree"]
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
        "kind": "fresh-noise-holdout-adaptive-degree-discovery",
        "config": {
            "degrees": degrees,
            "max_stage_steps": args.max_stage_steps,
            "min_stage_steps": args.min_stage_steps,
            "eval_every": args.eval_every,
            "batch_size": args.batch_size,
            "validation_words_per_check": args.validation_words,
            "oracle_noise_rate": args.noise_rate,
            "learner_initial_noise_rate": args.initial_noise_rate,
            "noise_prior_pairs": args.noise_prior_pairs,
            "base_seed": args.base_seed,
            "projection_ridge": args.projection_ridge,
            "coefficient_prior_std": args.coefficient_prior_std,
            "rounding_threshold": args.rounding_threshold,
            "accept_gap": args.accept_gap,
            "reject_gap": args.reject_gap,
            "consecutive_checks": args.consecutive_checks,
        },
        "verification": {
            "training_uses_only_fresh_noisy_labels": True,
            "validation_uses_independent_fresh_noisy_labels": True,
            "validation_labels_used_for_updates": False,
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
                "final_holdout_gap": stage["checks"][-1][
                    "holdout_disagreement_gap"
                ],
            }
            for stage in stage_records
        ],
        "final_clean_word_accuracy": final_clean_metrics["word_accuracy"],
        "cumulative_training_examples": cumulative_training_examples,
    }
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
