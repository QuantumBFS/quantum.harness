"""Learn a noisy truth table, then synthesize a verified Boolean ANF network.

The learner receives only fresh noisy observations.  A Bayesian table removes
label noise, a Möbius transform extracts algebraic-normal-form coefficients,
and shared-prefix/CSE passes turn those coefficients into two-input AND/XOR
gates.  The clean domain is used only after each checkpoint is frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from hidden_oracle import (
    CleanDomainEvaluator,
    DOMAIN_SIZE,
    FreshNoiseStream,
    OUTPUT_BITS,
)
from train_tabular_bayes import BayesianTruthTable


INPUT_BITS = 12


@dataclass
class Config:
    steps: int
    batch_size: int
    noise_rate: float
    eval_every: int
    base_seed: int
    prior_jitter: float
    order_search_trials: int
    device: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=2500)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--noise-rate", type=float, default=0.25)
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--base-seed", type=int, default=77_100)
    parser.add_argument("--prior-jitter", type=float, default=1e-6)
    parser.add_argument("--order-search-trials", type=int, default=500)
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mobius_transform(values: np.ndarray) -> np.ndarray:
    """Apply the Boolean-lattice transform; over GF(2) it is self-inverse."""

    transformed = values.astype(np.uint8, copy=True)
    for bit in range(INPUT_BITS):
        stride = 1 << bit
        view = transformed.reshape(-1, 2 * stride, OUTPUT_BITS)
        view[:, stride:, :] ^= view[:, :stride, :]
    return transformed


def prefix_masks(
    required_monomials: set[int],
    variable_order: tuple[int, ...],
) -> set[int]:
    prefixes: set[int] = set()
    for monomial in required_monomials:
        prefix = 0
        degree = 0
        for bit in variable_order:
            if monomial & (1 << bit):
                prefix |= 1 << bit
                degree += 1
                if degree >= 2:
                    prefixes.add(prefix)
    return prefixes


def optimize_variable_order(
    required_monomials: set[int],
    trials: int,
    seed: int,
) -> tuple[tuple[int, ...], set[int]]:
    """Minimize shared prefix products without consulting clean labels."""

    generator = random.Random(seed)
    candidates = [
        tuple(range(INPUT_BITS)),
        tuple(reversed(range(INPUT_BITS))),
    ]
    candidates.extend(
        tuple(generator.sample(range(INPUT_BITS), INPUT_BITS))
        for _ in range(trials)
    )
    best_order = candidates[0]
    best_prefixes = prefix_masks(required_monomials, best_order)
    for order in candidates[1:]:
        prefixes = prefix_masks(required_monomials, order)
        if len(prefixes) < len(best_prefixes):
            best_order = order
            best_prefixes = prefixes

    improved = True
    while improved:
        improved = False
        for left in range(INPUT_BITS):
            for right in range(left + 1, INPUT_BITS):
                proposal = list(best_order)
                proposal[left], proposal[right] = (
                    proposal[right],
                    proposal[left],
                )
                proposal_order = tuple(proposal)
                prefixes = prefix_masks(
                    required_monomials,
                    proposal_order,
                )
                if len(prefixes) < len(best_prefixes):
                    best_order = proposal_order
                    best_prefixes = prefixes
                    improved = True
    return best_order, best_prefixes


def signal_for_monomial(mask: int) -> str:
    if mask == 0:
        return "c1"
    if mask.bit_count() == 1:
        return f"i{mask.bit_length() - 1}"
    return f"m{mask}"


def synthesize_network(
    coefficients: np.ndarray,
    order_search_trials: int,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    term_masks = [
        set(np.flatnonzero(coefficients[:, bit]).tolist())
        for bit in range(OUTPUT_BITS)
    ]
    required_monomials = {
        mask
        for terms in term_masks
        for mask in terms
        if mask.bit_count() >= 2
    }
    variable_order, prefixes = optimize_variable_order(
        required_monomials,
        order_search_trials,
        seed,
    )

    and_nodes: list[dict[str, str]] = []
    for mask in sorted(prefixes, key=lambda value: (value.bit_count(), value)):
        ordered_bits = [
            bit for bit in variable_order if mask & (1 << bit)
        ]
        last_bit = ordered_bits[-1]
        parent = mask ^ (1 << last_bit)
        and_nodes.append(
            {
                "op": "AND",
                "a": signal_for_monomial(parent),
                "b": f"i{last_bit}",
                "out": signal_for_monomial(mask),
            }
        )

    expressions = {
        bit: {signal_for_monomial(mask) for mask in terms}
        for bit, terms in enumerate(term_masks)
    }
    xor_nodes: list[dict[str, str]] = []
    shared_xor_groups = 0
    while True:
        best_intersection: set[str] = set()
        best_containers: list[int] = []
        best_saving = 0
        output_bits = tuple(expressions)
        for left_index, left in enumerate(output_bits):
            for right in output_bits[left_index + 1 :]:
                intersection = expressions[left] & expressions[right]
                if len(intersection) < 2:
                    continue
                containers = [
                    bit
                    for bit, expression in expressions.items()
                    if intersection <= expression
                ]
                saving = (len(intersection) - 1) * (
                    len(containers) - 1
                )
                if saving > best_saving:
                    best_intersection = intersection
                    best_containers = containers
                    best_saving = saving
        if best_saving <= 0:
            break

        ordered_signals = sorted(best_intersection)
        current = ordered_signals[0]
        for other in ordered_signals[1:]:
            output = f"x{len(xor_nodes)}"
            xor_nodes.append(
                {"op": "XOR", "a": current, "b": other, "out": output}
            )
            current = output
        for bit in best_containers:
            expressions[bit] -= best_intersection
            expressions[bit].add(current)
        shared_xor_groups += 1

    outputs: list[str] = []
    for bit in range(OUTPUT_BITS):
        ordered_signals = sorted(expressions[bit])
        if not ordered_signals:
            outputs.append("c0")
            continue
        current = ordered_signals[0]
        for other in ordered_signals[1:]:
            output = f"x{len(xor_nodes)}"
            xor_nodes.append(
                {"op": "XOR", "a": current, "b": other, "out": output}
            )
            current = output
        outputs.append(current)

    term_counts = [len(terms) for terms in term_masks]
    degree_per_output = [
        max((mask.bit_count() for mask in terms), default=0)
        for terms in term_masks
    ]
    unique_direct_and_gates = sum(
        mask.bit_count() - 1 for mask in required_monomials
    )
    direct_xor_gates = sum(max(count - 1, 0) for count in term_counts)
    stats = {
        "anf_term_count_per_output": term_counts,
        "anf_degree_per_output": degree_per_output,
        "unique_nonlinear_monomials": len(required_monomials),
        "direct_shared_monomial_and_gates": unique_direct_and_gates,
        "prefix_shared_and_gates": len(and_nodes),
        "direct_output_xor_gates": direct_xor_gates,
        "cse_xor_gates": len(xor_nodes),
        "shared_xor_groups": shared_xor_groups,
        "total_two_input_gates": len(and_nodes) + len(xor_nodes),
        "gate_breakdown": {
            "AND": len(and_nodes),
            "XOR": len(xor_nodes),
        },
        "variable_order": list(variable_order),
    }
    network = {
        "kind": "learned-anf-two-input-gate-network",
        "input_bits": INPUT_BITS,
        "output_bits": OUTPUT_BITS,
        "constants": ["c0", "c1"],
        "and_nodes": and_nodes,
        "xor_nodes": xor_nodes,
        "outputs": outputs,
        "stats": stats,
    }
    return network, stats


def evaluate_network(network: dict[str, Any]) -> np.ndarray:
    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    signals: dict[str, np.ndarray] = {
        "c0": np.zeros(DOMAIN_SIZE, dtype=np.uint8),
        "c1": np.ones(DOMAIN_SIZE, dtype=np.uint8),
    }
    for bit in range(INPUT_BITS):
        signals[f"i{bit}"] = ((ids >> bit) & 1).astype(np.uint8)
    for node in network["and_nodes"]:
        signals[node["out"]] = signals[node["a"]] & signals[node["b"]]
    for node in network["xor_nodes"]:
        signals[node["out"]] = signals[node["a"]] ^ signals[node["b"]]
    return np.stack(
        [signals[signal] for signal in network["outputs"]],
        axis=1,
    )


def clean_metrics(
    prediction: np.ndarray,
    evaluator: CleanDomainEvaluator,
) -> dict[str, Any]:
    targets = evaluator.targets.cpu().numpy().astype(np.uint8)
    matches = prediction == targets
    bit_weights = 1 << np.arange(OUTPUT_BITS, dtype=np.int64)
    predicted_values = prediction.astype(np.int64) @ bit_weights
    target_values = targets.astype(np.int64) @ bit_weights
    return {
        "bit_accuracy": float(matches.mean()),
        "word_accuracy": float(matches.all(axis=1).mean()),
        "normalized_mae": float(
            np.abs(predicted_values - target_values).mean() / 4095.0
        ),
        "per_bit_accuracy": matches.mean(axis=0).tolist(),
    }


def main() -> None:
    args = parse_args()
    if not 0.0 < args.noise_rate < 0.5:
        raise ValueError("noise-rate must lie strictly between zero and 0.5")
    if args.steps <= 0 or args.batch_size <= 0 or args.eval_every <= 0:
        raise ValueError("steps, batch-size and eval-every must be positive")
    if args.order_search_trials < 0:
        raise ValueError("order-search-trials must be non-negative")

    device = torch.device(args.device)
    config = Config(
        steps=args.steps,
        batch_size=args.batch_size,
        noise_rate=args.noise_rate,
        eval_every=args.eval_every,
        base_seed=args.base_seed,
        prior_jitter=args.prior_jitter,
        order_search_trials=args.order_search_trials,
        device=str(device),
    )
    stream = FreshNoiseStream(
        batch_size=args.batch_size,
        noise_rate=args.noise_rate,
        seed=args.base_seed,
        device=device,
    )
    learner = BayesianTruthTable(
        noise_rate=args.noise_rate,
        prior_jitter=args.prior_jitter,
        seed=args.base_seed + 10_000,
        device=device,
    )
    evaluator = CleanDomainEvaluator(device)
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
    start = time.perf_counter()
    first_exact_step: int | None = None
    final_coefficients: np.ndarray | None = None
    final_prediction: np.ndarray | None = None
    for step in range(1, args.steps + 1):
        inputs, noisy_targets = stream.sample()
        ids = (inputs.to(torch.int64) * input_weights).sum(dim=1)
        loss = learner.noisy_loss_before_update(
            ids,
            noisy_targets,
            args.noise_rate,
        )
        learner.update(ids, noisy_targets)
        loss_value = loss.item()
        loss_ema = (
            loss_value
            if loss_ema is None
            else 0.98 * loss_ema + 0.02 * loss_value
        )

        if step == 1 or step % args.eval_every == 0 or step == args.steps:
            prediction = (
                learner.probabilities().ge(0.5).cpu().numpy().astype(np.uint8)
            )
            coefficients = mobius_transform(prediction)
            reconstructed = mobius_transform(coefficients)
            if not np.array_equal(reconstructed, prediction):
                raise AssertionError("ANF round-trip failed")
            metrics_record = {
                "step": step,
                "examples_seen": step * args.batch_size,
                "elapsed_seconds": time.perf_counter() - start,
                "train_loss_ema": loss_ema,
                "teacher_mean_observations": (
                    learner.observation_count.float().mean().item()
                ),
                "teacher_min_observations": (
                    learner.observation_count.min().item()
                ),
                "anf_terms": int(coefficients.sum()),
                **clean_metrics(reconstructed, evaluator),
            }
            metrics.append(metrics_record)
            if (
                first_exact_step is None
                and metrics_record["word_accuracy"] == 1.0
            ):
                first_exact_step = step
            final_coefficients = coefficients
            final_prediction = prediction
            print(
                f"step={step:5d} "
                f"loss={loss_ema:.5f} "
                f"word={metrics_record['word_accuracy']:.6f} "
                f"bit={metrics_record['bit_accuracy']:.6f} "
                f"terms={metrics_record['anf_terms']} "
                f"min_obs={metrics_record['teacher_min_observations']} "
                f"wall={metrics_record['elapsed_seconds']:.2f}s",
                flush=True,
            )
            (args.output_dir / "metrics.json").write_text(
                json.dumps(metrics, indent=2),
                encoding="utf-8",
            )

    if final_coefficients is None or final_prediction is None:
        raise AssertionError("no final checkpoint was evaluated")
    network, synthesis = synthesize_network(
        final_coefficients,
        args.order_search_trials,
        args.base_seed + 20_000,
    )
    network_prediction = evaluate_network(network)
    if not np.array_equal(network_prediction, final_prediction):
        raise AssertionError("gate network does not reproduce learned table")
    network_metrics = clean_metrics(network_prediction, evaluator)
    network["verification"] = {
        "domain_size": DOMAIN_SIZE,
        "matches_learned_posterior_table": True,
        "clean_metrics": network_metrics,
    }
    network_path = args.output_dir / "boolean_network.json"
    network_path.write_text(
        json.dumps(network, indent=2),
        encoding="utf-8",
    )
    run = {
        "kind": "online-bayesian-anf-gate-synthesis",
        "config": asdict(config),
        "verification": {
            "clean_domain_size": DOMAIN_SIZE,
            "clean_labels_used_for_updates": False,
            "teacher_uses_only_fresh_noisy_stream": True,
            "fresh_noise_each_sample": True,
            "target_formula_seeded": False,
            "existing_circuit_seeded": False,
            "anf_extracted_only_from_noisy_posterior": True,
            "gate_network_matches_learned_table": True,
        },
        "first_full_recovery_step": first_exact_step,
        "final": metrics[-1],
        "synthesis": synthesis,
        "network_sha256": sha256(network_path),
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(run, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(run, indent=2), flush=True)


if __name__ == "__main__":
    main()
