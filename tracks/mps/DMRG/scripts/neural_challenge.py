"""二维 L=45 混合神经 VMCRG 基础挑战的完整实验流程。

实现声明
--------
这是独立复现与研究扩展代码，不是论文作者的原始程序。它实现的偏置为

    V(mu) = J . S_13(mu) + V_theta(mu),

有效哈密顿量为

    H_eff(sigma) = K . S_13(sigma) + V(tau(sigma)),

其中 ``tau`` 是 3x3 多数规则。13 项线性分支保留已验证的长程结构，
神经网络只学习剩余局域误差，因此当前结果属于“混合神经表示”，不应
表述为纯神经网络替代，也不等同于论文 Table I 或三维自旋玻璃复现。

本文件依次执行六个不可省略的阶段：训练、冻结验证、13 维投影、独立
样本消融、自相关比较、验收报告。核心 Metropolis 和梯度更新位于
``vmcrg_ref.hybrid_neural``，神经能量位于 ``vmcrg_ref.neural_energy``。
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vmcrg_ref.hybrid_neural import (
    HybridNeuralVMCRGOptimizer,
    LinearNeuralBiasedMetropolis,
    NeuralOptimizationRecord,
)
from vmcrg_ref.artifacts import sha256_bytes
from vmcrg_ref.ising import IsingLattice, nearest_neighbor_operator
from vmcrg_ref.issue28_validation import excess_patch_tv_components
from vmcrg_ref.local_execution import resolve_worker_limit
from vmcrg_ref.neural_energy import D4EvenLocalMLP, LocalEnergyCache
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis
from vmcrg_ref.training_protocol import TrainingProtocol, TrainingWindow


PRESETS = {
    "smoke": {
        "train": dict(length=15, walkers=2, steps=3, sweeps=1, targets=4),
        "validation": dict(chains=2, thermal=5, measurements=5, spacing=1),
        "ablation": dict(chains=2, thermal=5, measurements=10, spacing=1),
        "autocorrelation": dict(chains=2, thermal=10, measurements=100, lag=20),
        "projection_samples": 500,
    },
    "pilot": {
        "train": dict(length=45, walkers=8, steps=100, sweeps=2, targets=16),
        "validation": dict(chains=8, thermal=100, measurements=100, spacing=2),
        "ablation": dict(chains=8, thermal=100, measurements=100, spacing=2),
        "autocorrelation": dict(chains=4, thermal=200, measurements=2000, lag=300),
        "projection_samples": 5000,
    },
    "formal": {
        "train": dict(length=45, walkers=16, steps=3000, sweeps=20, targets=32),
        "validation": dict(chains=16, thermal=1000, measurements=1000, spacing=5),
        "ablation": dict(chains=16, thermal=1000, measurements=1000, spacing=5),
        "autocorrelation": dict(
            chains=8, thermal=1000, measurements=5000, lag=1000
        ),
        "projection_samples": 20000,
    },
}

EQUIVALENCE_TOLERANCE = 0.02
FIXED_POINT_ABSOLUTE_TOLERANCE = 0.001
FIXED_POINT_RELATIVE_TOLERANCE = 0.005
AUTOCORRELATION_RATIO_TOLERANCE = 0.5
CONFIDENCE_MULTIPLIER = 2.0


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def update_summary(root: Path, **values: object) -> None:
    path = root / "summary.json"
    summary = read_json(path)
    summary.update(values)
    write_json(path, summary)


def fit_operator_projection(
    operator_densities: np.ndarray,
    renormalized_energy_density: np.ndarray,
) -> tuple[np.ndarray, int, np.ndarray]:
    """Fit H'/N = constant + sum_alpha K'_alpha S_alpha/N.

    The caller must pass ``-V/N`` as the renormalized energy density because
    the uniform-reference VMCRG identity is ``H' = -V_min + constant``.
    """
    x = np.asarray(operator_densities, dtype=np.float64)
    y = np.asarray(renormalized_energy_density, dtype=np.float64)
    if x.ndim != 2 or y.shape != (x.shape[0],):
        raise ValueError("projection arrays have incompatible shapes")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("projection arrays must be finite")
    design = np.column_stack((np.ones(x.shape[0]), x))
    parameters, _, rank, singular = np.linalg.lstsq(design, y, rcond=None)
    if int(rank) != design.shape[1]:
        raise ValueError("operator projection design is rank deficient")
    return parameters, int(rank), singular


def patch_histogram(spins: np.ndarray) -> np.ndarray:
    codes = np.zeros(spins.shape, dtype=np.int32)
    bit = 0
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            shifted = np.roll(spins, shift=(-dx, -dy), axis=(0, 1))
            codes |= (shifted > 0).astype(np.int32) << bit
            bit += 1
    return np.bincount(codes.ravel(), minlength=512).astype(np.int64)


def context(root: Path) -> tuple[dict, D4EvenLocalMLP, OperatorBasis, OperatorBasis]:
    config = read_json(root / "config.json")
    model = D4EvenLocalMLP.load(str(root / "bias_model.npz"))
    length = int(config["length"])
    block_size = int(config["block_size"])
    return (
        config,
        model,
        OperatorBasis(length, EVEN_SHAPES),
        OperatorBasis(length // block_size, EVEN_SHAPES),
    )


def sampler(
    config: dict,
    model: D4EvenLocalMLP,
    lattice: IsingLattice,
    rng: np.random.Generator,
    micro_basis: OperatorBasis,
    block_basis: OperatorBasis,
    linear_bias: np.ndarray | None = None,
) -> LinearNeuralBiasedMetropolis:
    bias = (
        np.asarray(config["fixed_linear_bias"], dtype=np.float64)
        if linear_bias is None
        else np.asarray(linear_bias, dtype=np.float64)
    )
    return LinearNeuralBiasedMetropolis(
        lattice,
        np.asarray(config["microscopic_couplings"], dtype=np.float64),
        bias,
        model,
        rng,
        EVEN_SHAPES,
        block_size=int(config["block_size"]),
        compiled=True,
        micro_basis=micro_basis,
        block_basis=block_basis,
    )


def train(
    root: Path,
    preset: str,
    fixed_point_map: Path,
    *,
    model_seed: int = 20260719,
    optimizer_seed: int = 20260720,
    representation: str = "hybrid",
    block_size: int = 3,
    length_override: int | None = None,
    training_overrides: dict[str, int] | None = None,
    optimizer_name: str = "adam",
    learning_rate_override: float | None = None,
    gradient_accumulation_steps: int = 1,
    decay_scale: float = 300.0,
    decay_power: float = 0.75,
    initial_model_path: Path | None = None,
    training_protocol: TrainingProtocol | None = None,
    monitor_callback: Callable[
        [int, D4EvenLocalMLP, NeuralOptimizationRecord, float],
        TrainingWindow,
    ]
    | None = None,
    initial_spins: np.ndarray | None = None,
    max_workers: int | None = None,
) -> None:
    settings = dict(PRESETS[preset]["train"])
    if training_protocol is not None:
        if training_overrides is not None:
            raise ValueError("explicit training protocol forbids ad hoc overrides")
        if representation != "pure":
            raise ValueError("explicit Issue #28 training is restricted to pure neural runs")
        if monitor_callback is None:
            raise ValueError("explicit training protocol requires held-out monitoring")
        settings.update(
            steps=training_protocol.maximum_updates,
            sweeps=training_protocol.sweeps_per_gradient_batch,
            targets=training_protocol.target_samples_per_batch,
        )
        optimizer_name = "literal_robbins_monro"
        gradient_accumulation_steps = (
            training_protocol.gradient_accumulation_batches
        )
    if training_overrides is not None:
        unknown = set(training_overrides).difference(settings)
        if unknown:
            raise ValueError(f"unknown training overrides: {sorted(unknown)}")
        settings.update({key: int(value) for key, value in training_overrides.items()})
    if any(int(settings[key]) <= 0 for key in ("length", "walkers", "steps", "sweeps", "targets")):
        raise ValueError("all training settings must be positive")
    if length_override is not None:
        settings["length"] = int(length_override)
    if block_size < 1 or settings["length"] % block_size != 0:
        raise ValueError("block_size must be positive and divide the lattice length")
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    fixed_map = read_json(fixed_point_map)
    expected_names = [shape.name for shape in EVEN_SHAPES]
    if fixed_map.get("operator_names") != expected_names:
        raise ValueError("fixed-point map must use the published 13-even-operator basis")
    couplings = np.asarray(fixed_map["input_couplings"], dtype=np.float64)
    mapped = np.asarray(fixed_map["final_renormalized_couplings"], dtype=np.float64)
    if couplings.shape != (13,) or mapped.shape != (13,):
        raise ValueError("fixed-point map must contain two 13-component vectors")

    if representation not in {"hybrid", "pure", "pure_shell_v1"}:
        raise ValueError(
            "representation must be 'hybrid', 'pure', or 'pure_shell_v1'"
        )
    if (
        representation in {"pure", "pure_shell_v1"}
        and settings["length"] // block_size < 7
    ):
        if length_override is not None:
            raise ValueError("pure radius-three model requires a coarse length >= 7")
        # Radius three requires at least a 7x7 block lattice.  The ordinary
        # b=3 smoke therefore uses the smallest compatible microscopic L=21.
        settings["length"] = 7 * block_size
    learning_rate = (
        training_protocol.schedule.rate(0)
        if training_protocol is not None
        else (5e-4 if learning_rate_override is None else float(learning_rate_override))
    )
    if learning_rate <= 0.0:
        raise ValueError("learning_rate must be positive")
    if representation == "hybrid":
        model = D4EvenLocalMLP.random(1, 32, model_seed, feature_mode="patch")
        linear_bias = -mapped
        representation_name = "13_operator_skip_plus_d4_z2_patch_residual"
        status_name = "hybrid_neural_vmcrg_easy_challenge"
    elif representation == "pure":
        # Exact inner-site features distinguish all six published four-spin
        # geometries.  Outer D4 shells cover every published two-spin range.
        model = D4EvenLocalMLP.random(3, 32, model_seed, feature_mode="multiscale")
        linear_bias = np.zeros_like(mapped)
        representation_name = "pure_d4_z2_radius3_multiscale_neural_energy"
        status_name = "pure_neural_vmcrg_replacement"
    else:
        # Radius three covers every published two-body displacement without
        # passing any hand-written operator value into the neural network.  It
        # is retained only to reproduce the frozen v1 protocol; shell pooling
        # cannot independently represent four of the six four-spin terms.
        model = D4EvenLocalMLP.random(3, 32, model_seed, feature_mode="shell")
        linear_bias = np.zeros_like(mapped)
        representation_name = "pure_d4_z2_radius3_shell_neural_energy"
        status_name = "pure_neural_vmcrg_replacement"
    if representation == "pure" and not np.array_equal(
        linear_bias,
        np.zeros(13, dtype=np.float64),
    ):
        raise AssertionError("pure-neural 13-operator branch is not exactly zero")
    if initial_model_path is not None:
        initial_model = D4EvenLocalMLP.load(str(initial_model_path))
        expected = (model.radius, model.hidden, model.feature_mode, model.n_features)
        observed = (
            initial_model.radius,
            initial_model.hidden,
            initial_model.feature_mode,
            initial_model.n_features,
        )
        if observed != expected:
            raise ValueError(
                f"initial model architecture {observed} does not match {expected}"
            )
        model = initial_model
    optimizer = HybridNeuralVMCRGOptimizer(
        settings["length"],
        couplings,
        linear_bias,
        model,
        EVEN_SHAPES,
        walkers=settings["walkers"],
        seed=optimizer_seed,
        block_size=block_size,
        max_workers=max_workers,
        initial_spins=initial_spins,
    )
    interval = (
        training_protocol.progress_every
        if training_protocol is not None
        else max(1, settings["steps"] // 20)
    )

    def progress(record) -> None:
        completed = record.step + 1
        if completed == 1 or completed % interval == 0 or completed == settings["steps"]:
            print(
                f"train {completed}/{settings['steps']} "
                f"grad={record.gradient_norm:.5g} "
                f"nn={record.biased_nn_per_site:.5g} "
                f"accept={record.acceptance_rate:.4f}",
                flush=True,
            )

    averaging_start = (
        training_protocol.polyak_start_update
        if training_protocol is not None
        else settings["steps"] // 2
    )
    started = time.perf_counter()
    if training_protocol is None:
        records = optimizer.run(
            settings["steps"],
            settings["sweeps"],
            learning_rate,
            target_samples=settings["targets"],
            averaging_start=averaging_start,
            callback=progress,
            optimizer_name=optimizer_name,
            gradient_accumulation_steps=gradient_accumulation_steps,
            decay_scale=decay_scale,
            decay_power=decay_power,
        )
    else:
        records = optimizer.run_protocol(
            training_protocol,
            monitor_callback=monitor_callback,
            callback=progress,
        )
    elapsed = time.perf_counter() - started
    if representation == "pure" and not np.array_equal(
        linear_bias,
        np.zeros(13, dtype=np.float64),
    ):
        raise AssertionError("pure-neural 13-operator branch changed during training")
    model.save(str(root / "bias_model.npz"))
    fields = tuple(asdict(records[0]))
    np.savez_compressed(
        root / "trajectory.npz",
        **{field: np.asarray([getattr(item, field) for item in records]) for field in fields},
    )
    total_sweeps = (
        len(records)
        * settings["sweeps"]
        * settings["walkers"]
        * gradient_accumulation_steps
    )
    config = {
        "status": status_name,
        "representation": representation_name,
        "microscopic_hamiltonian": "linear13",
        "microscopic_couplings": couplings.tolist(),
        "fixed_linear_bias": linear_bias.tolist(),
        "operator_names": [shape.name for shape in EVEN_SHAPES],
        "reference_distribution": optimizer.reference_distribution.name,
        "reference_distribution_role": (
            "variational_sampling_reference_not_physical_temperature"
        ),
        "renormalized_hamiltonian_relation": "H_prime=-V_min+constant_for_uniform_reference",
        "physical_temperature_parameter": "microscopic_dimensionless_couplings_K",
        "fixed_point_map_source": str(fixed_point_map),
        "preset": preset,
        "length": settings["length"],
        "block_size": block_size,
        "rg_transform": "identity" if block_size == 1 else "majority_rule",
        "walkers": settings["walkers"],
        "workers": optimizer.max_workers,
        "steps": len(records),
        "maximum_updates": settings["steps"],
        "sweeps": settings["sweeps"],
        "target_samples": settings["targets"],
        "total_walker_sweeps": total_sweeps,
        "hidden": 32,
        "neural_radius": model.radius,
        "neural_feature_mode": model.feature_mode,
        "learning_rate": learning_rate,
        "optimizer_name": optimizer_name,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "decay_scale": decay_scale,
        "decay_power": decay_power,
        "averaging_start": averaging_start,
        "training_protocol": (
            None if training_protocol is None else asdict(training_protocol)
        ),
        "training_stop_reason": optimizer.training_stop_reason,
        "model_initialization": (
            "random" if initial_model_path is None else "certified_checkpoint"
        ),
        "initial_model_path": (
            None if initial_model_path is None else str(initial_model_path)
        ),
        "seed": model_seed,
        "model_seed": model_seed,
        "optimizer_seed": optimizer_seed,
        "initial_state_sha256": (
            None
            if initial_spins is None
            else sha256_bytes(
                np.ascontiguousarray(
                    np.asarray(initial_spins, dtype=np.int8)
                ).tobytes(order="C")
            )
        ),
    }
    write_json(root / "config.json", config)
    last = records[-1]
    write_json(
        root / "summary.json",
        {
            **config,
            "elapsed_seconds": elapsed,
            "final_gradient_norm": last.gradient_norm,
            "final_learning_rate": last.learning_rate,
            "final_biased_nn_per_site": last.biased_nn_per_site,
            "final_target_nn_per_site": last.target_nn_per_site,
            "final_acceptance_rate": last.acceptance_rate,
            "training_stop_reason": optimizer.training_stop_reason,
            "validation": "NOT_RUN",
            "projection": "NOT_RUN",
            "neural_ablation": "NOT_RUN",
            "autocorrelation": "NOT_RUN",
        },
    )


def validate(
    root: Path,
    preset: str,
    *,
    seed: int = 20260716,
    enforce_formal_gate: bool = True,
    max_workers: int | None = None,
) -> dict:
    config, model, micro_basis, block_basis = context(root)
    settings = PRESETS[preset]["validation"]
    normalizers = np.asarray(block_basis.instance_counts, dtype=np.float64)
    chain_means, patch_probabilities, target_probabilities, acceptances = [], [], [], []
    sequences = np.random.SeedSequence(seed).spawn(settings["chains"] * 2)
    coarse = block_basis.length
    worker_limit = resolve_worker_limit(max_workers, settings["chains"])

    def one_chain(chain: int):
        rng = np.random.default_rng(sequences[2 * chain])
        target_rng = np.random.default_rng(sequences[2 * chain + 1])
        run = sampler(
            config,
            model,
            IsingLattice.random(int(config["length"]), rng),
            rng,
            micro_basis,
            block_basis,
        )
        run.run_sweeps(settings["thermal"])
        attempted, accepted = run.attempted, run.accepted
        samples = []
        observed = np.zeros(512, dtype=np.int64)
        target = np.zeros(512, dtype=np.int64)
        for _ in range(settings["measurements"]):
            run.run_sweeps(settings["spacing"])
            samples.append(block_basis.values(run.block_spins) / normalizers)
            observed += patch_histogram(run.block_spins)
            uniform = target_rng.choice(
                np.array([-1, 1], dtype=np.int8), size=(coarse, coarse)
            )
            target += patch_histogram(uniform)
        result = (
            np.mean(samples, axis=0),
            observed / observed.sum(),
            target / target.sum(),
            (run.accepted - accepted) / (run.attempted - attempted),
        )
        run.assert_cache_consistent()
        return result

    with ThreadPoolExecutor(max_workers=worker_limit) as executor:
        results = list(executor.map(one_chain, range(settings["chains"])))
    for chain_mean, observed, target, acceptance in results:
        chain_means.append(chain_mean)
        patch_probabilities.append(observed)
        target_probabilities.append(target)
        acceptances.append(acceptance)

    chains = np.asarray(chain_means)
    means = chains.mean(axis=0)
    errors = chains.std(axis=0, ddof=1) / np.sqrt(settings["chains"])
    bounds = np.abs(means) + CONFIDENCE_MULTIPLIER * errors
    operator_passed = bool(np.all(bounds <= EQUIVALENCE_TOLERANCE))
    observed_tv, target_tv, excess = excess_patch_tv_components(
        np.asarray(patch_probabilities),
        np.asarray(target_probabilities),
    )
    excess_mean = float(excess.mean())
    excess_error = float(excess.std(ddof=1) / np.sqrt(settings["chains"]))
    excess_bound = excess_mean + CONFIDENCE_MULTIPLIER * excess_error
    patch_passed = excess_bound <= EQUIVALENCE_TOLERANCE
    passed = operator_passed and patch_passed
    result = {
        "status": "PASS" if passed else "FAIL",
        "statistical_criterion_met": passed,
        "operator_criterion_met": operator_passed,
        "patch_criterion_met": patch_passed,
        "equivalence_tolerance": EQUIVALENCE_TOLERANCE,
        "max_equivalence_bound": float(bounds.max()),
        "excess_patch_tv_upper_bound": excess_bound,
        "mean_acceptance_rate": float(np.mean(acceptances)),
        "operator_means_by_chain": chains.tolist(),
        "observed_patch_tv_by_chain": observed_tv.tolist(),
        "target_patch_tv_by_chain": target_tv.tolist(),
        "excess_patch_tv_by_chain": excess.tolist(),
        "acceptance_rate_by_chain": [float(value) for value in acceptances],
        "seed": seed,
        "preset": preset,
        "workers_per_bundle": worker_limit,
        **settings,
        "operators": [
            {
                "name": shape.name,
                "mean": float(means[index]),
                "standard_error": float(errors[index]),
                "equivalence_bound": float(bounds[index]),
            }
            for index, shape in enumerate(EVEN_SHAPES)
        ],
    }
    write_json(root / f"validation_{preset}.json", result)
    update_summary(root, validation=result["status"])
    if preset == "formal" and enforce_formal_gate and not passed:
        raise RuntimeError("formal frozen-distribution validation failed")
    return result


def project(
    root: Path,
    preset: str,
    *,
    seed: int = 20260717,
    enforce_formal_gate: bool = True,
) -> dict:
    config, model, _, block_basis = context(root)
    count = int(PRESETS[preset]["projection_samples"])
    rng = np.random.default_rng(seed)
    n_sites = block_basis.length**2
    x = np.empty((count, 13), dtype=np.float64)
    y = np.empty(count, dtype=np.float64)
    for index in range(count):
        spins = rng.choice(
            np.array([-1, 1], dtype=np.int8),
            size=(block_basis.length, block_basis.length),
        )
        x[index] = block_basis.values(spins) / n_sites
        y[index] = -model.energy(spins) / n_sites
    order = rng.permutation(count)
    train_count = int(0.8 * count)
    training, validation = order[:train_count], order[train_count:]
    parameters, rank, singular = fit_operator_projection(
        x[training], y[training]
    )
    prediction = parameters[0] + x[validation] @ parameters[1:]
    residual_energy = y[validation] - prediction
    centered = y[validation] - y[validation].mean()
    r_squared = 1.0 - float(
        np.dot(residual_energy, residual_energy) / np.dot(centered, centered)
    )
    total = -np.asarray(config["fixed_linear_bias"]) + parameters[1:]
    fixed_point = np.asarray(config["microscopic_couplings"])
    residual = total - fixed_point
    linf = float(np.max(np.abs(residual)))
    relative = float(np.linalg.norm(residual) / np.linalg.norm(fixed_point))
    passed = (
        linf <= FIXED_POINT_ABSOLUTE_TOLERANCE
        and relative <= FIXED_POINT_RELATIVE_TOLERANCE
    )
    result = {
        "status": "PASS" if passed else "FAIL",
        "fixed_point_criterion_met": passed,
        "samples": count,
        "rank": int(rank),
        "condition_number": float(singular[0] / singular[-1]),
        "validation_r_squared": r_squared,
        "validation_rmse_per_site": float(np.sqrt(np.mean(residual_energy**2))),
        "couplings": total.tolist(),
        "neural_residual_couplings": parameters[1:].tolist(),
        "fixed_point_linf_residual": linf,
        "fixed_point_relative_l2_residual": relative,
        "fixed_point_absolute_tolerance": FIXED_POINT_ABSOLUTE_TOLERANCE,
        "fixed_point_relative_l2_tolerance": FIXED_POINT_RELATIVE_TOLERANCE,
        "seed": seed,
    }
    write_json(root / "projection_13.json", result)
    update_summary(root, projection=result["status"])
    if preset == "formal" and enforce_formal_gate and not passed:
        raise RuntimeError("formal fixed-point projection failed")
    return result


def jackknife_log_mean_exp(values: np.ndarray) -> tuple[float, float]:
    maximum = float(np.max(values))
    weights = np.exp(values - maximum)
    estimate = maximum + float(np.log(weights.mean()))
    leave_one_out = maximum + np.log((weights.sum() - weights) / (weights.size - 1))
    corrected = weights.size * estimate - (weights.size - 1) * float(leave_one_out.mean())
    return corrected, corrected - estimate


def ablate(
    root: Path,
    preset: str,
    *,
    seed: int = 20260722,
    chains_override: int | None = None,
    enforce_formal_gate: bool = True,
) -> dict:
    config, model, micro_basis, block_basis = context(root)
    settings = dict(PRESETS[preset]["ablation"])
    if chains_override is not None:
        if chains_override <= 1:
            raise ValueError("ablation chains must be greater than one")
        settings["chains"] = chains_override
    use_lookup = model.lookup_size <= LocalEnergyCache.MAX_LOOKUP_STATES
    lookup = model.density_lookup_table() if use_lookup else None
    zero_model = model.copy()
    zero_model.weight_out.fill(0.0)
    sequences = np.random.SeedSequence(seed).spawn(settings["chains"] * 2)
    differences, corrections = [], []
    n_sites = block_basis.length**2

    for chain in range(settings["chains"]):
        rng = np.random.default_rng(sequences[2 * chain])
        target_rng = np.random.default_rng(sequences[2 * chain + 1])
        run = sampler(
            config,
            zero_model,
            IsingLattice.random(int(config["length"]), rng),
            rng,
            micro_basis,
            block_basis,
        )
        run.run_sweeps(settings["thermal"])
        base = np.empty(settings["measurements"])
        target = np.empty(settings["measurements"])
        for index in range(settings["measurements"]):
            run.run_sweeps(settings["spacing"])
            if lookup is not None:
                if run.bias_cache.state_index is None:
                    raise AssertionError("lookup ablation is missing state indices")
                base[index] = float(lookup[run.bias_cache.state_index].sum())
            else:
                base[index] = model.energy(run.block_spins)
            uniform = target_rng.choice(
                np.array([-1, 1], dtype=np.int8),
                size=(block_basis.length, block_basis.length),
            )
            if lookup is not None:
                indices = model.state_indices_from_features(model.feature_grid(uniform))
                target[index] = float(lookup[indices].sum())
            else:
                target[index] = model.energy(uniform)
        ratio, correction = jackknife_log_mean_exp(-base)
        differences.append((ratio + float(target.mean())) / n_sites)
        corrections.append(correction / n_sites)
        run.assert_cache_consistent()
        print(f"ablation {chain + 1}/{settings['chains']}", flush=True)

    values = np.asarray(differences)
    mean = float(values.mean())
    error = float(values.std(ddof=1) / np.sqrt(values.size))
    upper = mean + CONFIDENCE_MULTIPLIER * error
    passed = upper < 0.0
    result = {
        "status": "PASS" if passed else "FAIL",
        "statistical_criterion_met": passed,
        "criterion": "heldout_delta_omega_mean_plus_2se_below_zero",
        "delta_omega_per_block_site_mean": mean,
        "delta_omega_per_block_site_standard_error": error,
        "delta_omega_per_block_site_upper_bound": upper,
        "delta_omega_by_chain": values.tolist(),
        "mean_jackknife_correction_per_site": float(np.mean(corrections)),
        "seed": seed,
        "preset": preset,
        **settings,
    }
    write_json(root / f"neural_residual_ablation_{preset}.json", result)
    update_summary(root, neural_ablation=result["status"])
    if preset == "formal" and enforce_formal_gate and not passed:
        raise RuntimeError("formal neural-residual ablation failed")
    return result


def autocorrelation(series: np.ndarray, max_lag: int) -> np.ndarray:
    centered = series - series.mean()
    size = centered.size
    fft_size = 1 << (2 * size - 1).bit_length()
    spectrum = np.fft.rfft(centered, fft_size)
    covariance = np.fft.irfft(spectrum * np.conjugate(spectrum), fft_size)[:size]
    covariance /= np.arange(size, 0, -1)
    if covariance[0] <= 0.0:
        raise ValueError("autocorrelation observable has zero variance")
    return covariance[: max_lag + 1] / covariance[0]


def integrated_time(acf: np.ndarray) -> float:
    positive = acf[1 : np.argmax(acf[1:] <= 0.0) + 1]
    if positive.size == 0 and acf[1] > 0.0:
        positive = acf[1:]
    return 0.5 + float(positive.sum())


def compare_autocorrelation(
    root: Path,
    preset: str,
    *,
    seed: int = 20260718,
    enforce_formal_gate: bool = True,
) -> dict:
    config, model, micro_basis, block_basis = context(root)
    settings = PRESETS[preset]["autocorrelation"]
    zero_model = model.copy()
    zero_model.weight_out.fill(0.0)
    zero_bias = np.zeros(13, dtype=np.float64)
    sequences = np.random.SeedSequence(seed).spawn(settings["chains"] * 3)
    biased_times, unbiased_times = [], []
    biased_acfs, unbiased_acfs = [], []

    for chain in range(settings["chains"]):
        initial_rng = np.random.default_rng(sequences[3 * chain])
        initial = IsingLattice.random(int(config["length"]), initial_rng).spins
        pairs = (
            sampler(
                config,
                model,
                IsingLattice(initial.copy()),
                np.random.default_rng(sequences[3 * chain + 1]),
                micro_basis,
                block_basis,
            ),
            sampler(
                config,
                zero_model,
                IsingLattice(initial.copy()),
                np.random.default_rng(sequences[3 * chain + 2]),
                micro_basis,
                block_basis,
                zero_bias,
            ),
        )
        for run, destination, acf_destination in zip(
            pairs,
            (biased_times, unbiased_times),
            (biased_acfs, unbiased_acfs),
        ):
            run.run_sweeps(settings["thermal"])
            values = np.empty(settings["measurements"])
            for index in range(settings["measurements"]):
                run.run_sweeps(1)
                micro = nearest_neighbor_operator(run.lattice.spins) / run.lattice.n_sites
                block = nearest_neighbor_operator(run.block_spins) / run.block_spins.size
                values[index] = micro * block
            acf = autocorrelation(values, settings["lag"])
            acf_destination.append(acf)
            destination.append(integrated_time(acf))
            run.assert_cache_consistent()
        print(f"autocorrelation {chain + 1}/{settings['chains']}", flush=True)

    biased = np.asarray(biased_times)
    unbiased = np.asarray(unbiased_times)
    ratios = biased / unbiased
    mean = float(ratios.mean())
    error = float(ratios.std(ddof=1) / np.sqrt(ratios.size))
    upper = mean + CONFIDENCE_MULTIPLIER * error
    passed = upper <= AUTOCORRELATION_RATIO_TOLERANCE
    result = {
        "status": "PASS" if passed else "FAIL",
        "statistical_criterion_met": passed,
        "paired_ratio_mean": mean,
        "paired_ratio_standard_error": error,
        "paired_ratio_upper_bound": upper,
        "ratio_threshold": AUTOCORRELATION_RATIO_TOLERANCE,
        "biased_tau_mean": float(biased.mean()),
        "unbiased_tau_mean": float(unbiased.mean()),
        "biased_tau_by_chain": biased.tolist(),
        "unbiased_tau_by_chain": unbiased.tolist(),
        "seed": seed,
        "preset": preset,
        **settings,
    }
    write_json(root / f"autocorrelation_{preset}.json", result)
    np.savez_compressed(
        root / f"autocorrelation_{preset}.npz",
        biased_acf=np.asarray(biased_acfs),
        unbiased_acf=np.asarray(unbiased_acfs),
        biased_tau=biased,
        unbiased_tau=unbiased,
    )
    update_summary(root, autocorrelation=result["status"])
    if preset == "formal" and enforce_formal_gate and not passed:
        raise RuntimeError("formal autocorrelation comparison failed")
    return result


def report(root: Path, preset: str) -> dict:
    config = read_json(root / "config.json")
    validation = read_json(root / f"validation_{preset}.json")
    projection = read_json(root / "projection_13.json")
    ablation = read_json(root / f"neural_residual_ablation_{preset}.json")
    correlation = read_json(root / f"autocorrelation_{preset}.json")
    gates = {
        "formal_l45_training": preset == "formal" and config["length"] == 45,
        "frozen_distribution": validation["statistical_criterion_met"],
        "full13_fixed_point_projection": projection["fixed_point_criterion_met"],
        "neural_residual_improves_heldout_objective": ablation[
            "statistical_criterion_met"
        ],
        "sampling_acceleration": correlation["statistical_criterion_met"],
    }
    passed = all(gates.values())
    pure = config["representation"] in {
        "pure_d4_z2_radius3_shell_neural_energy",
        "pure_d4_z2_radius3_multiscale_neural_energy",
    }
    result = {
        "status": "PASS" if passed else ("FAIL" if preset == "formal" else "NOT_FORMAL"),
        "scope": (
            (
                "2D_L45_pure_neural_VMCRG_replacement"
                if pure
                else "2D_L45_hybrid_neural_VMCRG_easy_challenge"
            )
            if preset == "formal"
            else f"{preset}_{'pure_neural' if pure else 'hybrid'}_pipeline_check"
        ),
        "representation": config["representation"],
        "gates": gates,
        "training": {
            "steps": config["steps"],
            "walkers": config["walkers"],
            "sweeps_per_step": config["sweeps"],
            "total_walker_sweeps": config["total_walker_sweeps"],
        },
        "frozen_distribution": {
            "max_operator_bound": validation["max_equivalence_bound"],
            "patch_tv_bound": validation["excess_patch_tv_upper_bound"],
        },
        "fixed_point": {
            "linf_residual": projection["fixed_point_linf_residual"],
            "relative_l2_residual": projection["fixed_point_relative_l2_residual"],
        },
        "neural_ablation": {
            "delta_omega_mean": ablation["delta_omega_per_block_site_mean"],
            "delta_omega_upper_bound": ablation["delta_omega_per_block_site_upper_bound"],
        },
        "sampling": {
            "biased_tau": correlation["biased_tau_mean"],
            "unbiased_tau": correlation["unbiased_tau_mean"],
            "ratio_upper_bound": correlation["paired_ratio_upper_bound"],
        },
        "not_claimed": (
            (
                [
                    "formal_pure_neural_replacement",
                    "neural_Table_I_eigenvalues",
                    "3D_spin_glass_transition",
                ]
                if not passed
                else [
                    "neural_Table_I_eigenvalues",
                    "3D_spin_glass_transition",
                ]
            )
            if pure
            else [
                "pure_neural_replacement",
                "exact_multi_round_hybrid_fixed_point",
                "3D_spin_glass_transition",
            ]
        ),
    }
    write_json(root / "challenge_report.json", result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if preset == "formal" and not passed:
        raise RuntimeError("formal neural challenge failed")
    return result


def run(
    root: Path,
    preset: str,
    fixed_point_map: Path,
    *,
    representation: str = "hybrid",
    model_seed: int = 20260719,
    optimizer_seed: int = 20260720,
    validation_seed: int = 20260716,
    projection_seed: int = 20260717,
    ablation_seed: int = 20260722,
    autocorrelation_seed: int = 20260718,
) -> None:
    train(
        root,
        preset,
        fixed_point_map,
        model_seed=model_seed,
        optimizer_seed=optimizer_seed,
        representation=representation,
    )
    validate(root, preset, seed=validation_seed)
    project(root, preset, seed=projection_seed)
    ablate(root, preset, seed=ablation_seed)
    compare_autocorrelation(root, preset, seed=autocorrelation_seed)
    report(root, preset)


def main() -> None:
    parser = argparse.ArgumentParser(description="Complete hybrid-neural VMCRG challenge.")
    parser.add_argument("--preset", choices=tuple(PRESETS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--fixed-point-map",
        type=Path,
        default=ROOT
        / "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json",
    )
    parser.add_argument(
        "--representation", choices=("hybrid", "pure"), default="hybrid"
    )
    parser.add_argument("--model-seed", type=int, default=20260719)
    parser.add_argument("--optimizer-seed", type=int, default=20260720)
    parser.add_argument("--validation-seed", type=int, default=20260716)
    parser.add_argument("--projection-seed", type=int, default=20260717)
    parser.add_argument("--ablation-seed", type=int, default=20260722)
    parser.add_argument("--autocorrelation-seed", type=int, default=20260718)
    args = parser.parse_args()
    run(
        args.output.resolve(),
        args.preset,
        args.fixed_point_map.resolve(),
        representation=args.representation,
        model_seed=args.model_seed,
        optimizer_seed=args.optimizer_seed,
        validation_seed=args.validation_seed,
        projection_seed=args.projection_seed,
        ablation_seed=args.ablation_seed,
        autocorrelation_seed=args.autocorrelation_seed,
    )


if __name__ == "__main__":
    main()
