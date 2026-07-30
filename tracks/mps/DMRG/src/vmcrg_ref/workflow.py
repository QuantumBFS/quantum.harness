"""Reproducible Stage A/B execution and three-arm evaluation."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any

import numpy as np

from .autocorrelation import autocorrelation_summary
from .checkpoint import save_mps_checkpoint
from .config import ExperimentConfig
from .ising import IsingLattice
from .mps_patch import PatchMPS
from .mps_sampler import MPSBiasedMetropolis
from .mps_vmcrg import MPSVMCRGOptimizer
from .multi_optimizer import MultiOperatorOptimizer
from .observables import (
    displacement_correlation,
    multisite_product,
    patch_distribution_distances,
)
from .operators import EVEN_SHAPES, OperatorBasis, OperatorShape
from .patch_table import PatchLookupTable


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        mode="w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _shapes(config: ExperimentConfig) -> tuple[OperatorShape, ...]:
    return EVEN_SHAPES[: config.model.operator_count]


def _couplings(config: ExperimentConfig) -> np.ndarray:
    values = np.zeros(config.model.operator_count, dtype=np.float64)
    values[0] = config.model.coupling
    return values


def _config_payload(config: ExperimentConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["source"] = str(config.source)
    payload["run"]["output"] = str(config.run.output)
    payload["run"]["seeds"] = list(config.run.seeds)
    return payload


def run_traditional_baseline(
    config: ExperimentConfig,
    seed: int,
    output: Path,
) -> tuple[np.ndarray, dict[str, Any]]:
    if config.model.rg_levels != 1:
        raise ValueError("the paper Stage A optimizer currently supports rg_levels=1")
    shapes = _shapes(config)
    optimizer = MultiOperatorOptimizer(
        length=config.model.length,
        couplings=_couplings(config),
        shapes=shapes,
        walkers=config.training.walkers,
        seed=seed,
        block_size=config.model.block_size,
        compiled=config.training.compiled,
        parallel_walkers=config.training.parallel_walkers,
    )
    progress_every = max(1, config.training.baseline_steps // 20)

    def progress(record) -> None:
        if (record.step + 1) % progress_every == 0 or record.step == 0:
            print(
                "baseline "
                f"step={record.step + 1}/{config.training.baseline_steps} "
                f"grad={np.linalg.norm(record.gradient):.6g} "
                f"J0={record.running_bias[0]:.6g}",
                flush=True,
            )

    started = time.perf_counter()
    records = optimizer.run(
        steps=config.training.baseline_steps,
        sweeps_per_step=config.training.sweeps_per_step,
        learning_rate=config.training.baseline_learning_rate,
        callback=progress,
    )
    elapsed = time.perf_counter() - started
    bias = records[-1].running_bias.copy()
    trajectory = [
        {
            "step": int(record.step),
            "running_bias": record.running_bias.tolist(),
            "instantaneous_bias": record.instantaneous_bias.tolist(),
            "gradient_norm": float(np.linalg.norm(record.gradient)),
            "mean_operators": record.mean_operators.tolist(),
        }
        for record in records
    ]
    summary = {
        "stage": "A_traditional",
        "seed": int(seed),
        "length": config.model.length,
        "coarse_length": config.coarse_length,
        "coupling": config.model.coupling,
        "operator_names": [shape.name for shape in shapes],
        "linear_bias": bias.tolist(),
        "steps": config.training.baseline_steps,
        "sweeps_per_step": config.training.sweeps_per_step,
        "walkers": config.training.walkers,
        "learning_rate": config.training.baseline_learning_rate,
        "acceptance_rates": [sampler.acceptance_rate for sampler in optimizer.samplers],
        "elapsed_seconds": elapsed,
        "trajectory": trajectory,
    }
    _write_json(output / "baseline.json", summary)
    return bias, summary


def run_mps_training(
    config: ExperimentConfig,
    seed: int,
    linear_bias: np.ndarray,
    output: Path,
    initial_model: PatchMPS | None = None,
) -> tuple[PatchMPS, float, dict[str, Any]]:
    model = (
        PatchMPS.random(
            chi=config.mps.chi,
            seed=seed + 10_000,
            symmetrize=config.mps.symmetrize,
        )
        if initial_model is None
        else initial_model.copy()
    )
    optimizer = MPSVMCRGOptimizer(
        length=config.model.length,
        couplings=_couplings(config),
        linear_bias=linear_bias,
        model=model,
        shapes=_shapes(config),
        walkers=config.training.walkers,
        seed=seed + 20_000,
        alpha=0.0,
        block_size=config.model.block_size,
        rg_levels=config.model.rg_levels,
        compiled=config.training.compiled,
        parallel_walkers=config.training.parallel_walkers,
    )
    progress_every = max(1, config.training.residual_steps // 20)

    def progress(record) -> None:
        if (record.step + 1) % progress_every == 0 or record.step == 0:
            print(
                "mps "
                f"step={record.step + 1}/{config.training.residual_steps} "
                f"objective={record.objective:.6g} "
                f"grad={record.gradient_norm:.6g} "
                f"alpha={record.alpha:.6g} "
                f"accept={record.acceptance_rate:.3f}",
                flush=True,
            )

    records = optimizer.run(
        steps=config.training.residual_steps,
        sweeps_per_step=config.training.sweeps_per_step,
        alpha_learning_rate=config.training.alpha_learning_rate,
        core_learning_rate=config.training.core_learning_rate,
        linear_learning_rate=config.training.linear_learning_rate,
        gradient_clip=config.training.gradient_clip,
        canonicalize_every=config.training.canonicalize_every,
        cache_check_every=config.training.cache_check_every,
        callback=progress,
    )
    trajectory = [record.to_dict() for record in records]
    summary = {
        "stage": "B_mps_residual"
        if config.training.linear_learning_rate == 0.0
        else "C_joint_tuning",
        "seed": int(seed),
        "chi": model.chi,
        "symmetrized": model.symmetrize,
        "alpha": optimizer.alpha,
        "linear_bias": optimizer.linear_bias.tolist(),
        "model_diagnostics": model.diagnostics(),
        "steps": config.training.residual_steps,
        "sweeps_per_step": config.training.sweeps_per_step,
        "walkers": config.training.walkers,
        "trajectory": trajectory,
    }
    _write_json(output / "training.json", summary)
    save_mps_checkpoint(
        output / "checkpoint",
        model=model,
        alpha=optimizer.alpha,
        linear_bias=optimizer.linear_bias,
        metadata={
            "seed": int(seed),
            "steps": config.training.residual_steps,
            "objective": trajectory[-1]["objective"],
            "config": _config_payload(config),
        },
    )
    return model, optimizer.alpha, summary


def _evaluate_arm(
    config: ExperimentConfig,
    seed: int,
    initial_spins: np.ndarray,
    linear_bias: np.ndarray,
    alpha: float,
    lookup: PatchLookupTable,
) -> dict[str, Any]:
    shapes = _shapes(config)
    micro_basis = OperatorBasis(config.model.length, shapes)
    block_basis = OperatorBasis(config.coarse_length, shapes)
    sampler = MPSBiasedMetropolis(
        IsingLattice(initial_spins.copy()),
        _couplings(config),
        linear_bias,
        alpha,
        lookup,
        np.random.default_rng(seed),
        shapes,
        block_size=config.model.block_size,
        rg_levels=config.model.rg_levels,
        compiled=config.training.compiled,
        micro_basis=micro_basis,
        block_basis=block_basis,
    )
    sampler.run_sweeps(config.measurement.thermalization_sweeps)
    nn_series = np.empty(config.measurement.measurement_sweeps, dtype=np.float64)
    energy_series = np.empty_like(nn_series)
    magnetization_series = np.empty_like(nn_series)
    correlations = {key: np.empty_like(nn_series) for key in ("10", "11", "20")}
    higher = {key: np.empty_like(nn_series) for key in ("four", "six", "parity9")}
    histogram = np.zeros(512, dtype=np.int64)
    started = time.perf_counter()
    for measurement in range(config.measurement.measurement_sweeps):
        sampler.run_sweeps(config.measurement.thinning)
        coarse = sampler.rg_state.coarse_spins
        nn_series[measurement] = -sampler.block_values[0] / block_basis.instance_counts[0]
        energy_series[measurement] = (
            sampler.couplings @ sampler.micro_values / sampler.lattice.n_sites
        )
        magnetization_series[measurement] = float(np.mean(coarse))
        correlations["10"][measurement] = displacement_correlation(coarse, 1, 0)
        correlations["11"][measurement] = displacement_correlation(coarse, 1, 1)
        correlations["20"][measurement] = displacement_correlation(coarse, 2, 0)
        higher["four"][measurement] = multisite_product(
            coarse, ((0, 0), (1, 0), (0, 1), (1, 1))
        )
        higher["six"][measurement] = multisite_product(
            coarse, ((0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1))
        )
        higher["parity9"][measurement] = multisite_product(
            coarse,
            tuple((x, y) for x in range(-1, 2) for y in range(-1, 2)),
        )
        histogram += sampler.patch_cache.histogram
    elapsed = time.perf_counter() - started
    return {
        "acceptance_rate": sampler.acceptance_rate,
        "energy_per_site": float(energy_series.mean()),
        "coarse_magnetization": float(magnetization_series.mean()),
        "block_nn_correlation": float(nn_series.mean()),
        "two_point_correlations": {
            key: {"mean": float(values.mean()), "stderr": float(values.std(ddof=1) / np.sqrt(values.size))}
            for key, values in correlations.items()
        },
        "held_out_multispin": {
            key: {"mean": float(values.mean()), "stderr": float(values.std(ddof=1) / np.sqrt(values.size))}
            for key, values in higher.items()
        },
        "patch_distances": patch_distribution_distances(histogram),
        "autocorrelation": autocorrelation_summary(nn_series, elapsed),
        "elapsed_seconds": elapsed,
        "sweep_seconds": elapsed
        / (config.measurement.measurement_sweeps * config.measurement.thinning),
        "samples": config.measurement.measurement_sweeps,
    }


def evaluate_three_arms(
    config: ExperimentConfig,
    seed: int,
    linear_bias: np.ndarray,
    model: PatchMPS,
    alpha: float,
) -> dict[str, Any]:
    initial_rng = np.random.default_rng(seed + 30_000)
    initial = IsingLattice.random(config.model.length, initial_rng).spins
    lookup = PatchLookupTable.from_model(model)
    zero_bias = np.zeros_like(linear_bias)
    proposal_seed = seed + 40_000
    return {
        "unbiased": _evaluate_arm(
            config, proposal_seed, initial, zero_bias, 0.0, lookup
        ),
        "traditional": _evaluate_arm(
            config, proposal_seed, initial, linear_bias, 0.0, lookup
        ),
        "traditional_mps": _evaluate_arm(
            config, proposal_seed, initial, linear_bias, alpha, lookup
        ),
    }


def run_full_experiment(
    config: ExperimentConfig,
    seed: int,
    output: str | Path,
    initial_model: PatchMPS | None = None,
) -> dict[str, Any]:
    root = Path(output)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty output directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "config.json", _config_payload(config))
    started = time.perf_counter()
    linear_bias, baseline = run_traditional_baseline(config, seed, root)
    model, alpha, training = run_mps_training(
        config, seed, linear_bias, root, initial_model=initial_model
    )
    evaluation = evaluate_three_arms(config, seed, linear_bias, model, alpha)
    _write_json(root / "evaluation.json", evaluation)
    status = (
        "COMPLETE"
        if config.model.length == 45
        and config.model.operator_count == 13
        and len(config.run.seeds) >= 3
        else "SMOKE_COMPLETE"
    )
    summary = {
        "status": status,
        "scientific_sufficiency": status == "COMPLETE",
        "seed": int(seed),
        "length": config.model.length,
        "coarse_length": config.coarse_length,
        "coupling": config.model.coupling,
        "rg_levels": config.model.rg_levels,
        "chi": config.mps.chi,
        "baseline": {
            "linear_bias": baseline["linear_bias"],
            "elapsed_seconds": baseline["elapsed_seconds"],
        },
        "training": {
            "alpha": training["alpha"],
            "model_diagnostics": training["model_diagnostics"],
            "final_record": training["trajectory"][-1],
        },
        "evaluation": evaluation,
        "total_seconds": time.perf_counter() - started,
    }
    _write_json(root / "summary.json", summary)
    return summary
