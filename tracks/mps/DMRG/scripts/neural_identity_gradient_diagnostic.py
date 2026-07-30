"""Diagnose the VMCRG gradient at a supervised identity-RG solution.

For identity RG with a uniform reference, the exact optimum is ``V=-H``.
The supervised model used here already passes an independent 13-coupling
projection.  Freezing that model lets us test the stochastic VMCRG machinery
without mixing the result with parameter updates.

Three estimates are compared:

1. Metropolis: the gradient used by ``HybridNeuralVMCRGOptimizer``;
2. importance oracle: an independent-uniform estimate reweighted by
   ``exp[-(H+V)]``;
3. null control: the difference of two independent uniform estimates.

The comparison is diagnostic, not a new training rule and not a post-hoc
correction of any coupling.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from statistics import NormalDist
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.neural_challenge import read_json, write_json
from vmcrg_ref.hybrid_neural import HybridNeuralVMCRGOptimizer
from vmcrg_ref.neural_energy import D4EvenLocalMLP, MLPGradient
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis


PRESETS = {
    "smoke": dict(
        walkers=4,
        burn_in_sweeps=10,
        batches=8,
        sweeps_between_batches=2,
        target_samples=4,
        oracle_samples=8,
    ),
    "pilot": dict(
        walkers=16,
        burn_in_sweeps=200,
        batches=40,
        sweeps_between_batches=20,
        target_samples=32,
        oracle_samples=32,
    ),
    "formal": dict(
        walkers=16,
        burn_in_sweeps=1000,
        batches=200,
        sweeps_between_batches=20,
        target_samples=64,
        oracle_samples=64,
    ),
}


def flatten_gradient(gradient: MLPGradient) -> np.ndarray:
    return np.concatenate(
        (
            gradient.weight_in.reshape(-1),
            gradient.bias_hidden.reshape(-1),
            gradient.weight_out.reshape(-1),
        )
    )


def parameter_labels(model: D4EvenLocalMLP) -> list[str]:
    labels = [
        f"weight_in[{hidden},{feature}]"
        for hidden in range(model.hidden)
        for feature in range(model.n_features)
    ]
    labels.extend(f"bias_hidden[{hidden}]" for hidden in range(model.hidden))
    labels.extend(f"weight_out[{hidden}]" for hidden in range(model.hidden))
    return labels


def configuration_gradient(model: D4EvenLocalMLP, spins: np.ndarray) -> np.ndarray:
    return flatten_gradient(model.gradient(spins)) / float(spins.size)


def batch_summary(
    batches: np.ndarray,
    labels: list[str],
    *,
    alpha: float = 0.05,
) -> dict:
    values = np.asarray(batches, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2:
        raise ValueError("batches must have shape (at least two, parameters)")
    if values.shape[1] != len(labels):
        raise ValueError("labels do not match the batch dimension")
    mean = values.mean(axis=0)
    standard_error = values.std(axis=0, ddof=1) / np.sqrt(values.shape[0])
    usable = standard_error > 1e-14
    z = np.zeros_like(mean)
    z[usable] = mean[usable] / standard_error[usable]
    z[~usable & (np.abs(mean) > 1e-14)] = np.inf
    tested = max(1, int(np.count_nonzero(usable)))
    threshold = NormalDist().inv_cdf(1.0 - alpha / (2.0 * tested))
    order = np.argsort(np.abs(z))[::-1][:10]
    se_l2 = float(np.linalg.norm(standard_error))
    return {
        "batches": int(values.shape[0]),
        "dimensions": int(values.shape[1]),
        "mean_l2_norm": float(np.linalg.norm(mean)),
        "standard_error_l2_norm": se_l2,
        "l2_signal_to_noise": (
            float(np.linalg.norm(mean) / se_l2) if se_l2 > 0.0 else float("inf")
        ),
        "maximum_absolute_z": float(np.max(np.abs(z))),
        "bonferroni_z_threshold": float(threshold),
        "zero_not_rejected": bool(np.max(np.abs(z)) <= threshold),
        "top_coordinates": [
            {
                "parameter": labels[int(index)],
                "mean": float(mean[index]),
                "standard_error": float(standard_error[index]),
                "z": float(z[index]),
            }
            for index in order
        ],
        "_mean": mean,
        "_standard_error": standard_error,
    }


def compare_summaries(left: dict, right: dict, labels: list[str]) -> dict:
    difference = left["_mean"] - right["_mean"]
    standard_error = np.sqrt(
        left["_standard_error"] ** 2 + right["_standard_error"] ** 2
    )
    usable = standard_error > 1e-14
    z = np.zeros_like(difference)
    z[usable] = difference[usable] / standard_error[usable]
    z[~usable & (np.abs(difference) > 1e-14)] = np.inf
    tested = max(1, int(np.count_nonzero(usable)))
    threshold = NormalDist().inv_cdf(1.0 - 0.05 / (2.0 * tested))
    order = np.argsort(np.abs(z))[::-1][:10]
    left_mean = left["_mean"]
    right_mean = right["_mean"]
    denominator = float(np.linalg.norm(left_mean) * np.linalg.norm(right_mean))
    cosine = (
        float(np.dot(left_mean, right_mean) / denominator)
        if denominator > 0.0
        else 0.0
    )
    return {
        "maximum_absolute_z": float(np.max(np.abs(z))),
        "bonferroni_z_threshold": float(threshold),
        "statistically_consistent": bool(np.max(np.abs(z)) <= threshold),
        "mean_difference_l2_norm": float(np.linalg.norm(difference)),
        "cosine_similarity": cosine,
        "top_discrepancies": [
            {
                "parameter": labels[int(index)],
                "difference": float(difference[index]),
                "standard_error": float(standard_error[index]),
                "z": float(z[index]),
            }
            for index in order
        ],
    }


def public_summary(summary: dict) -> dict:
    return {key: value for key, value in summary.items() if not key.startswith("_")}


def _run_all_samplers(
    optimizer: HybridNeuralVMCRGOptimizer, sweeps: int
) -> None:
    with ThreadPoolExecutor(
        max_workers=min(len(optimizer.samplers), os.cpu_count() or 1)
    ) as executor:
        list(executor.map(lambda sampler: sampler.run_sweeps(sweeps), optimizer.samplers))


def metropolis_batches(
    optimizer: HybridNeuralVMCRGOptimizer,
    settings: dict,
    basis: OperatorBasis,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[float]]:
    n_sites = optimizer.length**2
    _run_all_samplers(optimizer, int(settings["burn_in_sweeps"]))
    gradient_batches = []
    null_batches = []
    operator_batches = []
    acceptance_rates = []
    for _ in range(int(settings["batches"])):
        attempted_before = sum(sampler.attempted for sampler in optimizer.samplers)
        accepted_before = sum(sampler.accepted for sampler in optimizer.samplers)
        _run_all_samplers(optimizer, int(settings["sweeps_between_batches"]))
        biased_gradients = np.stack(
            [
                flatten_gradient(
                    optimizer.model.gradient_from_features(sampler.bias_cache.features)
                )
                / n_sites
                for sampler in optimizer.samplers
            ]
        )
        target_a = optimizer._reference_samples(  # noqa: SLF001
            int(settings["target_samples"]), optimizer.length
        )
        target_b = optimizer._reference_samples(  # noqa: SLF001
            int(settings["target_samples"]), optimizer.length
        )
        target_a_gradients = np.stack(
            [configuration_gradient(optimizer.model, spins) for spins in target_a]
        )
        target_b_gradients = np.stack(
            [configuration_gradient(optimizer.model, spins) for spins in target_b]
        )
        gradient_batches.append(
            target_a_gradients.mean(axis=0) - biased_gradients.mean(axis=0)
        )
        null_batches.append(
            target_a_gradients.mean(axis=0) - target_b_gradients.mean(axis=0)
        )
        biased_operators = np.stack(
            [sampler.block_values / n_sites for sampler in optimizer.samplers]
        )
        target_operators = np.stack(
            [basis.values(spins) / n_sites for spins in target_a]
        )
        operator_batches.append(
            target_operators.mean(axis=0) - biased_operators.mean(axis=0)
        )
        attempted = (
            sum(sampler.attempted for sampler in optimizer.samplers) - attempted_before
        )
        accepted = (
            sum(sampler.accepted for sampler in optimizer.samplers) - accepted_before
        )
        acceptance_rates.append(float(accepted / attempted))
    return (
        np.asarray(gradient_batches),
        np.asarray(null_batches),
        np.asarray(operator_batches),
        acceptance_rates,
    )


def importance_oracle_batches(
    model: D4EvenLocalMLP,
    couplings: np.ndarray,
    basis: OperatorBasis,
    settings: dict,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, list[float], list[float]]:
    length = basis.length
    n_sites = length**2
    gradient_batches = []
    operator_batches = []
    ess_fractions = []
    residual_standard_deviations = []
    for _ in range(int(settings["batches"])):
        count = int(settings["oracle_samples"])
        spins_batch = rng.choice(
            np.array([-1, 1], dtype=np.int8), size=(count, length, length)
        )
        gradients = np.empty(
            (count, model.weight_in.size + model.bias_hidden.size + model.weight_out.size),
            dtype=np.float64,
        )
        operators = np.empty((count, len(EVEN_SHAPES)), dtype=np.float64)
        residual = np.empty(count, dtype=np.float64)
        for index, spins in enumerate(spins_batch):
            values = basis.values(spins)
            operators[index] = values / n_sites
            gradients[index] = configuration_gradient(model, spins)
            residual[index] = float(couplings @ values + model.energy(spins))
        log_weight = -residual
        log_weight -= float(np.max(log_weight))
        weights = np.exp(log_weight)
        weights /= float(weights.sum())
        gradient_batches.append(
            gradients.mean(axis=0) - np.sum(weights[:, None] * gradients, axis=0)
        )
        operator_batches.append(
            operators.mean(axis=0) - np.sum(weights[:, None] * operators, axis=0)
        )
        ess_fractions.append(float(1.0 / np.sum(weights**2) / count))
        residual_standard_deviations.append(float(np.std(residual, ddof=1)))
    return (
        np.asarray(gradient_batches),
        np.asarray(operator_batches),
        ess_fractions,
        residual_standard_deviations,
    )


def run(
    *,
    preset: str,
    output: Path,
    model_path: Path,
    fixed_point_map: Path,
    seed: int,
) -> dict:
    settings = PRESETS[preset]
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    source = read_json(fixed_point_map)
    couplings = np.asarray(source["input_couplings"], dtype=np.float64)
    if couplings.shape != (len(EVEN_SHAPES),):
        raise ValueError("fixed-point map must contain 13 input couplings")
    model = D4EvenLocalMLP.load(str(model_path))
    if model.feature_mode != "multiscale" or model.radius != 3:
        raise ValueError("diagnostic requires the certified radius-3 multiscale model")
    length = 15
    basis = OperatorBasis(length, EVEN_SHAPES)
    optimizer = HybridNeuralVMCRGOptimizer(
        length=length,
        couplings=couplings,
        linear_bias=np.zeros_like(couplings),
        model=model,
        shapes=EVEN_SHAPES,
        walkers=int(settings["walkers"]),
        seed=seed,
        block_size=1,
        compiled=True,
        parallel_walkers=True,
    )
    start = time.perf_counter()
    sampler_gradient, null_gradient, sampler_operator, acceptance = metropolis_batches(
        optimizer, settings, basis
    )
    oracle_gradient, oracle_operator, ess, residual_sd = importance_oracle_batches(
        model,
        couplings,
        basis,
        settings,
        np.random.default_rng(seed + 1),
    )
    labels = parameter_labels(model)
    operator_labels = [shape.name for shape in EVEN_SHAPES]
    sampler_summary = batch_summary(sampler_gradient, labels)
    oracle_summary = batch_summary(oracle_gradient, labels)
    null_summary = batch_summary(null_gradient, labels)
    sampler_operator_summary = batch_summary(sampler_operator, operator_labels)
    oracle_operator_summary = batch_summary(oracle_operator, operator_labels)
    gradient_comparison = compare_summaries(
        sampler_summary, oracle_summary, labels
    )
    operator_comparison = compare_summaries(
        sampler_operator_summary, oracle_operator_summary, operator_labels
    )
    null_ok = bool(null_summary["zero_not_rejected"])
    estimator_ok = bool(gradient_comparison["statistically_consistent"])
    distribution_ok = bool(operator_comparison["statistically_consistent"])
    if not null_ok:
        diagnosis = "INCONCLUSIVE_NULL_CALIBRATION_FAILED"
    elif not estimator_ok or not distribution_ok:
        diagnosis = "SAMPLER_OR_GRADIENT_ESTIMATOR_MISMATCH"
    elif sampler_summary["zero_not_rejected"] and oracle_summary["zero_not_rejected"]:
        diagnosis = "ZERO_GRADIENT_CONFIRMED"
    else:
        diagnosis = "CONSISTENT_NONZERO_RESIDUAL_GRADIENT"
    output.mkdir(parents=True)
    report = {
        "status": "PASS" if estimator_ok and distribution_ok and null_ok else "FAIL",
        "diagnosis": diagnosis,
        "experiment": "frozen_supervised_identity_vmcrg_gradient_diagnostic",
        "preset": preset,
        "model_path": str(model_path),
        "fixed_point_map": str(fixed_point_map),
        "length": length,
        "block_size": 1,
        "fixed_linear_bias_linf": 0.0,
        "settings": settings,
        "elapsed_seconds": time.perf_counter() - start,
        "acceptance_rate_mean": float(np.mean(acceptance)),
        "importance_effective_sample_fraction_mean": float(np.mean(ess)),
        "effective_residual_energy_standard_deviation_mean": float(
            np.mean(residual_sd)
        ),
        "metropolis_gradient": public_summary(sampler_summary),
        "importance_oracle_gradient": public_summary(oracle_summary),
        "uniform_null_gradient": public_summary(null_summary),
        "metropolis_vs_oracle_gradient": gradient_comparison,
        "metropolis_operator_moments": public_summary(sampler_operator_summary),
        "importance_oracle_operator_moments": public_summary(
            oracle_operator_summary
        ),
        "metropolis_vs_oracle_operator_moments": operator_comparison,
        "seed": seed,
    }
    write_json(output / "identity_gradient_diagnostic.json", report)
    np.savez_compressed(
        output / "identity_gradient_batches.npz",
        metropolis_gradient=sampler_gradient,
        importance_oracle_gradient=oracle_gradient,
        uniform_null_gradient=null_gradient,
        metropolis_operator=sampler_operator,
        importance_oracle_operator=oracle_operator,
        acceptance_rate=np.asarray(acceptance),
        importance_ess_fraction=np.asarray(ess),
        effective_residual_energy_sd=np.asarray(residual_sd),
    )
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=tuple(PRESETS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT
        / "output/neural_supervised_identity_formal_v1/supervised_model.npz",
    )
    parser.add_argument(
        "--fixed-point-map",
        type=Path,
        default=ROOT
        / "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json",
    )
    parser.add_argument("--seed", type=int, default=202607281)
    args = parser.parse_args()
    run(
        preset=args.preset,
        output=args.output.resolve(),
        model_path=args.model.resolve(),
        fixed_point_map=args.fixed_point_map.resolve(),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
