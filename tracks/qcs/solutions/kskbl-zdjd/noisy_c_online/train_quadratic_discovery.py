"""Discover a sparse quadratic integer rule and compile it to Boolean gates.

The learner starts from a random coefficient prior over every generic
constant, linear and pairwise Boolean feature.  Fresh noisy bit observations
update a Bayesian table.  Weighted ridge projection onto the quadratic basis
uses only that posterior, after which integer coefficients are compiled with
column compressors into a two-input AND/XOR network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict, dataclass
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
    ShuffledCycleFreshNoiseStream,
)
from train_tabular_bayes import (
    BayesianTruthTable,
    PairwiseNoiseBayesianTruthTable,
)


INPUT_BITS = 12


@dataclass
class Config:
    steps: int
    batch_size: int
    noise_rate: float
    eval_every: int
    base_seed: int
    prior_jitter: float
    coefficient_prior_std: float
    projection_ridge: float
    weight_mode: str
    input_sampling: str
    design_size: int | None
    design_rank: int | None
    design_condition_number: float | None
    learner_noise_mode: str
    initial_noise_rate: float | None
    noise_prior_pairs: float | None
    device: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=2500)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--noise-rate", type=float, default=0.25)
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--base-seed", type=int, default=87_100)
    parser.add_argument("--prior-jitter", type=float, default=1e-6)
    parser.add_argument("--coefficient-prior-std", type=float, default=1.0)
    parser.add_argument("--projection-ridge", type=float, default=1e-3)
    parser.add_argument(
        "--weight-mode",
        choices=("confidence", "observation", "hybrid"),
        default="hybrid",
    )
    parser.add_argument(
        "--input-sampling",
        choices=(
            "uniform",
            "shuffled-cycle",
            "random-design-cycle",
            "d-optimal-cycle",
        ),
        default="uniform",
    )
    parser.add_argument(
        "--design-size",
        type=int,
        default=79,
        help="Number of label-blind design points for d-optimal-cycle.",
    )
    parser.add_argument(
        "--learner-noise-mode",
        choices=("known", "pairwise-estimated"),
        default="known",
    )
    parser.add_argument(
        "--initial-noise-rate",
        type=float,
        default=0.10,
        help="Learner-only initial guess when the oracle noise rate is hidden.",
    )
    parser.add_argument(
        "--noise-prior-pairs",
        type=float,
        default=1_000.0,
        help="Pairwise-disagreement pseudocount for unknown-noise estimation.",
    )
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quadratic_features() -> tuple[np.ndarray, list[dict[str, Any]]]:
    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    bits = ((ids[:, None] >> np.arange(INPUT_BITS)) & 1).astype(np.float64)
    columns = [np.ones(DOMAIN_SIZE, dtype=np.float64)]
    metadata: list[dict[str, Any]] = [
        {"kind": "constant", "input_bits": [], "mask": 0}
    ]
    for bit in range(INPUT_BITS):
        columns.append(bits[:, bit])
        metadata.append(
            {"kind": "linear", "input_bits": [bit], "mask": 1 << bit}
        )
    for left in range(INPUT_BITS):
        for right in range(left + 1, INPUT_BITS):
            columns.append(bits[:, left] * bits[:, right])
            metadata.append(
                {
                    "kind": "quadratic",
                    "input_bits": [left, right],
                    "mask": (1 << left) | (1 << right),
                }
            )
    return np.stack(columns, axis=1), metadata


def effect_coded_quadratic_features() -> np.ndarray:
    """Return an orthogonal full-domain basis used only to design inputs."""

    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    bits = ((ids[:, None] >> np.arange(INPUT_BITS)) & 1).astype(np.float64)
    effects = 2.0 * bits - 1.0
    columns = [np.ones(DOMAIN_SIZE, dtype=np.float64)]
    columns.extend(effects[:, bit] for bit in range(INPUT_BITS))
    columns.extend(
        effects[:, left] * effects[:, right]
        for left in range(INPUT_BITS)
        for right in range(left + 1, INPUT_BITS)
    )
    return np.stack(columns, axis=1)


def design_diagnostics(
    selected: np.ndarray,
    effect_features: np.ndarray,
) -> dict[str, float | int]:
    selected_features = effect_features[selected]
    return {
        "size": int(len(selected)),
        "rank": int(np.linalg.matrix_rank(selected_features)),
        "condition_number": float(np.linalg.cond(selected_features)),
    }


def d_optimal_design_ids(
    design_size: int,
) -> tuple[np.ndarray, dict[str, float | int]]:
    """Select a well-conditioned quadratic design without consulting labels."""

    if design_size < 79 or design_size > DOMAIN_SIZE:
        raise ValueError("design-size must lie between 79 and 4096")
    effect_features = effect_coded_quadratic_features()
    _, _, pivots = qr(
        effect_features.T,
        mode="economic",
        pivoting=True,
        check_finite=False,
    )
    selected = pivots[:design_size].astype(np.int64)
    diagnostics = design_diagnostics(selected, effect_features)
    if diagnostics["rank"] != effect_features.shape[1]:
        raise AssertionError("label-blind design is not full rank")
    return selected, diagnostics


def random_design_ids(
    design_size: int,
    seed: int,
) -> tuple[np.ndarray, dict[str, float | int]]:
    """Select a uniformly random fixed design without consulting labels."""

    if design_size < 79 or design_size > DOMAIN_SIZE:
        raise ValueError("design-size must lie between 79 and 4096")
    effect_features = effect_coded_quadratic_features()
    generator = np.random.default_rng(seed + 30_000)
    for _ in range(1_000):
        selected = generator.choice(
            DOMAIN_SIZE,
            size=design_size,
            replace=False,
        ).astype(np.int64)
        diagnostics = design_diagnostics(selected, effect_features)
        if diagnostics["rank"] == effect_features.shape[1]:
            return selected, diagnostics
    raise RuntimeError("failed to draw a full-rank random design")


def projection_weights(
    probabilities: np.ndarray,
    observation_count: np.ndarray,
    mode: str,
) -> np.ndarray:
    confidence = np.square(2.0 * probabilities - 1.0).mean(axis=1)
    observations = observation_count.astype(np.float64)
    if mode == "confidence":
        weights = confidence
    elif mode == "observation":
        weights = observations
    elif mode == "hybrid":
        weights = confidence * np.minimum(observations / 16.0, 1.0)
    else:
        raise ValueError(f"unsupported weight mode: {mode}")
    return np.maximum(weights, 1e-12)


def project_coefficients(
    features: np.ndarray,
    expected_values: np.ndarray,
    weights: np.ndarray,
    random_prior: np.ndarray,
    ridge: float,
) -> np.ndarray:
    weighted_features = features * weights[:, None]
    gram = features.T @ weighted_features
    rhs = weighted_features.T @ expected_values
    regularized = gram + ridge * np.eye(features.shape[1])
    return np.linalg.solve(regularized, rhs + ridge * random_prior)


def coefficients_to_values(
    features: np.ndarray,
    coefficients: np.ndarray,
) -> np.ndarray:
    values = np.rint(features @ coefficients).astype(np.int64)
    return np.mod(values, 1 << OUTPUT_BITS)


def values_to_bits(values: np.ndarray) -> np.ndarray:
    shifts = np.arange(OUTPUT_BITS, dtype=np.int64)
    return ((values[:, None] >> shifts[None, :]) & 1).astype(np.uint8)


def clean_metrics(
    values: np.ndarray,
    evaluator: CleanDomainEvaluator,
) -> dict[str, Any]:
    prediction = values_to_bits(values)
    targets = evaluator.targets.cpu().numpy().astype(np.uint8)
    matches = prediction == targets
    bit_weights = 1 << np.arange(OUTPUT_BITS, dtype=np.int64)
    target_values = targets.astype(np.int64) @ bit_weights
    return {
        "bit_accuracy": float(matches.mean()),
        "word_accuracy": float(matches.all(axis=1).mean()),
        "normalized_mae": float(
            np.abs(values - target_values).mean() / 4095.0
        ),
        "per_bit_accuracy": matches.mean(axis=0).tolist(),
    }


class GateBuilder:
    def __init__(self) -> None:
        self.gates: list[dict[str, str]] = []
        self.cache: dict[tuple[str, str, str], str] = {}

    def _gate(self, op: str, left: str, right: str) -> str:
        if op == "XOR":
            if left == "c0":
                return right
            if right == "c0":
                return left
            if left == right:
                return "c0"
        elif op == "AND":
            if left == "c0" or right == "c0":
                return "c0"
            if left == "c1":
                return right
            if right == "c1":
                return left
            if left == right:
                return left
        else:
            raise ValueError(f"unsupported gate: {op}")
        first, second = sorted((left, right))
        key = (op, first, second)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        output = f"g{len(self.gates)}"
        self.gates.append(
            {"op": op, "a": first, "b": second, "out": output}
        )
        self.cache[key] = output
        return output

    def xor(self, left: str, right: str) -> str:
        return self._gate("XOR", left, right)

    def and_(self, left: str, right: str) -> str:
        return self._gate("AND", left, right)

    def half_adder(self, left: str, right: str) -> tuple[str, str]:
        return self.xor(left, right), self.and_(left, right)

    def full_adder(
        self,
        first: str,
        second: str,
        third: str,
    ) -> tuple[str, str]:
        partial = self.xor(first, second)
        total = self.xor(partial, third)
        carry = self.xor(
            self.and_(first, second),
            self.and_(third, partial),
        )
        return total, carry


def signal_for_feature(
    feature: dict[str, Any],
    builder: GateBuilder,
) -> str:
    bits = feature["input_bits"]
    if not bits:
        return "c1"
    if len(bits) == 1:
        return f"i{bits[0]}"
    return builder.and_(f"i{bits[0]}", f"i{bits[1]}")


def synthesize_weighted_sum(
    coefficients: np.ndarray,
    metadata: list[dict[str, Any]],
) -> dict[str, Any]:
    builder = GateBuilder()
    columns: dict[int, list[str]] = {
        bit: [] for bit in range(OUTPUT_BITS + 1)
    }
    active_features = []
    for coefficient, feature in zip(coefficients, metadata, strict=True):
        coefficient_mod = int(coefficient) % (1 << OUTPUT_BITS)
        if coefficient_mod == 0:
            continue
        signal = signal_for_feature(feature, builder)
        active_features.append(
            {
                **feature,
                "coefficient": int(coefficient),
                "coefficient_mod_4096": coefficient_mod,
            }
        )
        for output_bit in range(OUTPUT_BITS):
            if coefficient_mod & (1 << output_bit):
                columns[output_bit].append(signal)

    compressor_full_adders = 0
    for column in range(OUTPUT_BITS):
        while len(columns[column]) > 2:
            first = columns[column].pop()
            second = columns[column].pop()
            third = columns[column].pop()
            total, carry = builder.full_adder(first, second, third)
            columns[column].append(total)
            columns[column + 1].append(carry)
            compressor_full_adders += 1

    outputs: list[str] = []
    carry = "c0"
    final_half_adders = 0
    final_full_adders = 0
    for column in range(OUTPUT_BITS):
        signals = columns[column]
        if len(signals) == 0:
            outputs.append(carry)
            carry = "c0"
        elif len(signals) == 1:
            if carry == "c0":
                outputs.append(signals[0])
            else:
                total, carry = builder.half_adder(signals[0], carry)
                outputs.append(total)
                final_half_adders += 1
        elif len(signals) == 2:
            if carry == "c0":
                total, carry = builder.half_adder(
                    signals[0],
                    signals[1],
                )
                outputs.append(total)
                final_half_adders += 1
            else:
                total, carry = builder.full_adder(
                    signals[0],
                    signals[1],
                    carry,
                )
                outputs.append(total)
                final_full_adders += 1
        else:
            raise AssertionError("column compression failed")

    gate_breakdown = {
        "AND": sum(gate["op"] == "AND" for gate in builder.gates),
        "XOR": sum(gate["op"] == "XOR" for gate in builder.gates),
    }
    return {
        "kind": "learned-quadratic-wallace-two-input-gate-network",
        "input_bits": INPUT_BITS,
        "output_bits": OUTPUT_BITS,
        "constants": ["c0", "c1"],
        "active_features": active_features,
        "gates": builder.gates,
        "outputs": outputs,
        "stats": {
            "active_integer_features": len(active_features),
            "compressor_full_adders": compressor_full_adders,
            "final_half_adders": final_half_adders,
            "final_full_adders": final_full_adders,
            "structurally_hashed_two_input_gates": len(builder.gates),
            "gate_breakdown": gate_breakdown,
            "discarded_overflow_signal": carry,
            "discarded_column_12_signals": len(columns[OUTPUT_BITS]),
        },
    }


def evaluate_gate_network(network: dict[str, Any]) -> np.ndarray:
    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    signals: dict[str, np.ndarray] = {
        "c0": np.zeros(DOMAIN_SIZE, dtype=np.uint8),
        "c1": np.ones(DOMAIN_SIZE, dtype=np.uint8),
    }
    for bit in range(INPUT_BITS):
        signals[f"i{bit}"] = ((ids >> bit) & 1).astype(np.uint8)
    for gate in network["gates"]:
        left = signals[gate["a"]]
        right = signals[gate["b"]]
        if gate["op"] == "AND":
            signals[gate["out"]] = left & right
        elif gate["op"] == "XOR":
            signals[gate["out"]] = left ^ right
        else:
            raise ValueError(f"unsupported gate: {gate['op']}")
    return np.stack(
        [signals[signal] for signal in network["outputs"]],
        axis=1,
    )


def main() -> None:
    args = parse_args()
    if not 0.0 < args.noise_rate < 0.5:
        raise ValueError("noise-rate must lie strictly between zero and 0.5")
    if args.steps <= 0 or args.batch_size <= 0 or args.eval_every <= 0:
        raise ValueError("steps, batch-size and eval-every must be positive")
    if args.projection_ridge <= 0.0 or args.coefficient_prior_std < 0.0:
        raise ValueError("invalid coefficient prior settings")
    if not 0.0 < args.initial_noise_rate < 0.5:
        raise ValueError("initial-noise-rate must lie between zero and 0.5")
    if args.noise_prior_pairs < 0.0:
        raise ValueError("noise-prior-pairs must be nonnegative")

    device = torch.device(args.device)
    design_ids: np.ndarray | None = None
    design_diagnostics: dict[str, float | int] | None = None
    if args.input_sampling == "d-optimal-cycle":
        design_ids, design_diagnostics = d_optimal_design_ids(
            args.design_size
        )
    elif args.input_sampling == "random-design-cycle":
        design_ids, design_diagnostics = random_design_ids(
            args.design_size,
            args.base_seed,
        )
    config = Config(
        steps=args.steps,
        batch_size=args.batch_size,
        noise_rate=args.noise_rate,
        eval_every=args.eval_every,
        base_seed=args.base_seed,
        prior_jitter=args.prior_jitter,
        coefficient_prior_std=args.coefficient_prior_std,
        projection_ridge=args.projection_ridge,
        weight_mode=args.weight_mode,
        input_sampling=args.input_sampling,
        design_size=(
            int(design_diagnostics["size"])
            if design_diagnostics is not None
            else None
        ),
        design_rank=(
            int(design_diagnostics["rank"])
            if design_diagnostics is not None
            else None
        ),
        design_condition_number=(
            float(design_diagnostics["condition_number"])
            if design_diagnostics is not None
            else None
        ),
        learner_noise_mode=args.learner_noise_mode,
        initial_noise_rate=(
            args.initial_noise_rate
            if args.learner_noise_mode == "pairwise-estimated"
            else None
        ),
        noise_prior_pairs=(
            args.noise_prior_pairs
            if args.learner_noise_mode == "pairwise-estimated"
            else None
        ),
        device=str(device),
    )
    if args.input_sampling == "uniform":
        stream = FreshNoiseStream(
            batch_size=args.batch_size,
            noise_rate=args.noise_rate,
            seed=args.base_seed,
            device=device,
        )
    elif args.input_sampling == "shuffled-cycle":
        stream = ShuffledCycleFreshNoiseStream(
            batch_size=args.batch_size,
            noise_rate=args.noise_rate,
            seed=args.base_seed,
            device=device,
        )
    else:
        if design_ids is None:
            raise AssertionError("fixed input design was not constructed")
        stream = FixedDesignFreshNoiseStream(
            batch_size=args.batch_size,
            noise_rate=args.noise_rate,
            seed=args.base_seed,
            device=device,
            design_ids=torch.from_numpy(design_ids),
        )
    if args.learner_noise_mode == "known":
        learner = BayesianTruthTable(
            noise_rate=args.noise_rate,
            prior_jitter=args.prior_jitter,
            seed=args.base_seed + 10_000,
            device=device,
        )
    else:
        learner = PairwiseNoiseBayesianTruthTable(
            initial_noise_rate=args.initial_noise_rate,
            prior_jitter=args.prior_jitter,
            noise_prior_pairs=args.noise_prior_pairs,
            seed=args.base_seed + 10_000,
            device=device,
        )
    evaluator = CleanDomainEvaluator(device)
    features, metadata = quadratic_features()
    coefficient_generator = np.random.default_rng(args.base_seed + 20_000)
    random_prior = coefficient_generator.normal(
        0.0,
        args.coefficient_prior_std,
        size=features.shape[1],
    )
    bit_weights = 1 << np.arange(OUTPUT_BITS, dtype=np.int64)
    input_weights = 2 ** torch.arange(
        INPUT_BITS,
        device=device,
        dtype=torch.int64,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "config.json").write_text(
        json.dumps(asdict(config), indent=2),
        encoding="utf-8",
    )

    metrics: list[dict[str, Any]] = []
    loss_ema: float | None = None
    first_exact_step: int | None = None
    final_integer_coefficients: np.ndarray | None = None
    start = time.perf_counter()
    for step in range(1, args.steps + 1):
        inputs, noisy_targets = stream.sample()
        ids = (inputs.to(torch.int64) * input_weights).sum(dim=1)
        loss = learner.noisy_loss_before_update(ids, noisy_targets)
        learner.update(ids, noisy_targets)
        loss_value = loss.item()
        loss_ema = (
            loss_value
            if loss_ema is None
            else 0.98 * loss_ema + 0.02 * loss_value
        )

        if step == 1 or step % args.eval_every == 0 or step == args.steps:
            probabilities = learner.probabilities().cpu().numpy()
            observations = learner.observation_count.cpu().numpy()
            expected_values = probabilities @ bit_weights
            weights = projection_weights(
                probabilities,
                observations,
                args.weight_mode,
            )
            continuous_coefficients = project_coefficients(
                features,
                expected_values,
                weights,
                random_prior,
                args.projection_ridge,
            )
            integer_coefficients = np.rint(
                continuous_coefficients
            ).astype(np.int64)
            projected_values = coefficients_to_values(
                features,
                integer_coefficients,
            )
            record = {
                "step": step,
                "examples_seen": step * args.batch_size,
                "elapsed_seconds": time.perf_counter() - start,
                "train_loss_ema": loss_ema,
                "teacher_mean_observations": float(observations.mean()),
                "teacher_min_observations": int(observations.min()),
                "estimated_noise_rate": float(
                    getattr(learner, "estimated_noise_rate", args.noise_rate)
                ),
                "effective_noise_pairs": float(
                    getattr(learner, "effective_noise_pairs", 0.0)
                ),
                "effective_projection_inputs": int(
                    np.count_nonzero(weights > 1e-8)
                ),
                "active_integer_coefficients": int(
                    np.count_nonzero(integer_coefficients)
                ),
                "maximum_rounding_residual": float(
                    np.max(
                        np.abs(
                            continuous_coefficients
                            - integer_coefficients
                        )
                    )
                ),
                **clean_metrics(projected_values, evaluator),
            }
            metrics.append(record)
            if first_exact_step is None and record["word_accuracy"] == 1.0:
                first_exact_step = step
            final_integer_coefficients = integer_coefficients
            if not args.quiet:
                print(
                    f"step={step:5d} "
                    f"loss={loss_ema:.5f} "
                    f"word={record['word_accuracy']:.6f} "
                    f"bit={record['bit_accuracy']:.6f} "
                    f"active={record['active_integer_coefficients']} "
                    f"round={record['maximum_rounding_residual']:.4f} "
                    f"wall={record['elapsed_seconds']:.2f}s",
                    flush=True,
                )
            (args.output_dir / "metrics.json").write_text(
                json.dumps(metrics, indent=2),
                encoding="utf-8",
            )

    if final_integer_coefficients is None:
        raise AssertionError("no coefficient checkpoint was evaluated")
    symbolic_values = coefficients_to_values(
        features,
        final_integer_coefficients,
    )
    network = synthesize_weighted_sum(
        final_integer_coefficients,
        metadata,
    )
    gate_prediction = evaluate_gate_network(network)
    if not np.array_equal(gate_prediction, values_to_bits(symbolic_values)):
        raise AssertionError("compiled gates do not reproduce symbolic model")
    gate_metrics = clean_metrics(
        gate_prediction.astype(np.int64) @ bit_weights,
        evaluator,
    )
    network["verification"] = {
        "domain_size": DOMAIN_SIZE,
        "matches_symbolic_integer_model": True,
        "clean_metrics": gate_metrics,
    }
    network_path = args.output_dir / "quadratic_gate_network.json"
    network_path.write_text(
        json.dumps(network, indent=2),
        encoding="utf-8",
    )
    coefficient_rows = [
        {
            **feature,
            "coefficient": int(coefficient),
        }
        for coefficient, feature in zip(
            final_integer_coefficients,
            metadata,
            strict=True,
        )
    ]
    run = {
        "kind": "online-bayesian-quadratic-rule-discovery",
        "config": asdict(config),
        "verification": {
            "clean_domain_size": DOMAIN_SIZE,
            "clean_labels_used_for_updates": False,
            "teacher_uses_only_fresh_noisy_stream": True,
            "fresh_noise_each_sample": True,
            "input_sampling": args.input_sampling,
            "input_design_uses_target_labels": False,
            "input_design_diagnostics": design_diagnostics,
            "learner_receives_oracle_noise_rate": (
                args.learner_noise_mode == "known"
            ),
            "noise_rate_estimation": (
                "pairwise repeated-label disagreement"
                if args.learner_noise_mode == "pairwise-estimated"
                else "known oracle setting"
            ),
            "target_formula_seeded": False,
            "existing_circuit_seeded": False,
            "generic_quadratic_basis_size": features.shape[1],
            "projection_uses_only_noisy_posterior": True,
            "gate_network_matches_symbolic_model": True,
        },
        "first_full_recovery_step": first_exact_step,
        "final": metrics[-1],
        "integer_coefficients": coefficient_rows,
        "synthesis": network["stats"],
        "network_sha256": sha256(network_path),
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(run, indent=2),
        encoding="utf-8",
    )
    if not args.quiet:
        print(json.dumps(run, indent=2), flush=True)
    else:
        print(
            json.dumps(
                {
                    "output_dir": str(args.output_dir),
                    "first_full_recovery_step": first_exact_step,
                    "final_word_accuracy": metrics[-1]["word_accuracy"],
                    "elapsed_seconds": metrics[-1]["elapsed_seconds"],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
