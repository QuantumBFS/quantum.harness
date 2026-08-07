"""N3 resumable neural-to-neural five-round pilot for Issue #28."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
import os
from pathlib import Path
import resource
import shutil
import tempfile
import time
from types import MappingProxyType
from typing import Any

import numpy as np

from .artifacts import (
    atomic_write_json,
    atomic_write_npz,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from .issue28_protocol import (
    Issue28Protocol,
    REQUIRED_STREAMS,
    SeedBundle,
    SeedStream,
)
from .local_execution import local_host_provenance, resolve_worker_limit
from .issue28_workflow import (
    create_stage_manifest,
    current_code_sha256,
    read_verified_stage_manifest,
)
from .issue28_validation import (
    excess_patch_tv_components,
    scientific_round_gates_pass,
)
from .neural_checkpoint import (
    CheckpointExpectations,
    NeuralCheckpoint,
    load_neural_checkpoint,
    save_neural_checkpoint,
)
from .neural_energy import D4EvenLocalMLP, MLPGradient
from .neural_hamiltonian import NeuralHamiltonian, NeuralToNeuralBiasedMetropolis
from .objective import ChainSet, bridge_objective
from .one_round import (
    _bundle_record,
    _candidate_diagnostics,
    _child_sequence,
    _integer_seed,
    _json_ready,
    _load_run_protocols,
    _output_paths,
    _stream_hash,
    run_one_round,
)
from .operators import EVEN_SHAPES, OperatorBasis
from .power import estimate_five_seed_power
from .training_protocol import (
    PolyakAverager,
    TrainingProtocol,
    TrainingStopState,
    TrainingWindow,
    clip_mlp_gradient,
    model_parameters_finite,
)


_ROOT = Path(__file__).resolve().parents[2]
_PILOT_CONFIG = _ROOT / "config" / "issue28_pilot_v1.json"


def five_round_pilot_bundle() -> SeedBundle:
    entropy = 2026287100
    return SeedBundle(
        "n3-five-round-pilot",
        MappingProxyType(
            {
                name: SeedStream(entropy, (index,))
                for index, name in enumerate(REQUIRED_STREAMS)
            }
        ),
    )


def _zero_gradient(model: D4EvenLocalMLP) -> MLPGradient:
    return MLPGradient(
        np.zeros_like(model.weight_in),
        np.zeros_like(model.bias_hidden),
        np.zeros_like(model.weight_out),
    )


def _scale_gradient(value: MLPGradient, scale: float) -> MLPGradient:
    return MLPGradient(
        value.weight_in * scale,
        value.bias_hidden * scale,
        value.weight_out * scale,
    )


def _add_gradient(total: MLPGradient, value: MLPGradient) -> None:
    total.weight_in += value.weight_in
    total.bias_hidden += value.bias_hidden
    total.weight_out += value.weight_out


def _subtract_gradient(target: MLPGradient, biased: MLPGradient) -> MLPGradient:
    return MLPGradient(
        target.weight_in - biased.weight_in,
        target.bias_hidden - biased.bias_hidden,
        target.weight_out - biased.weight_out,
    )


def _flatten_parameters(model: D4EvenLocalMLP) -> np.ndarray:
    return np.concatenate(
        (model.weight_in.ravel(), model.bias_hidden.ravel(), model.weight_out.ravel())
    )


def _log_mean_exp(values: np.ndarray) -> float:
    maximum = float(np.max(values))
    return maximum + float(np.log(np.mean(np.exp(values - maximum))))


def _sampling_budget(preset: str) -> dict[str, int]:
    if preset == "smoke":
        return {
            "walkers": 2,
            "monitor_chains": 2,
            "monitor_thermal": 2,
            "monitor_measurements": 4,
            "validation_chains": 2,
            "validation_thermal": 5,
            "validation_measurements": 5,
            "validation_spacing": 1,
        }
    if preset == "pilot":
        return {
            "walkers": 8,
            "monitor_chains": 4,
            "monitor_thermal": 20,
            "monitor_measurements": 16,
            "validation_chains": 8,
            "validation_thermal": 100,
            "validation_measurements": 100,
            "validation_spacing": 2,
        }
    return {
        "walkers": 16,
        "monitor_chains": 8,
        "monitor_thermal": 100,
        "monitor_measurements": 64,
        "validation_chains": 16,
        "validation_thermal": 1000,
        "validation_measurements": 1000,
        "validation_spacing": 5,
    }


def _neural_samples(
    previous_model: D4EvenLocalMLP,
    current_model: D4EvenLocalMLP,
    *,
    length: int,
    block_size: int,
    stream: SeedStream,
    child_prefix: tuple[int, ...],
    chains: int,
    thermal: int,
    measurements: int,
    spacing: int,
    workers: int | None = None,
    basis: OperatorBasis | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[float]]:
    coarse = length // block_size
    operator_basis = OperatorBasis(coarse, EVEN_SHAPES) if basis is None else basis
    if operator_basis.length != coarse or operator_basis.shapes != EVEN_SHAPES:
        raise ValueError("neural sampling basis does not match the coarse lattice")
    normalizers = np.asarray(operator_basis.instance_counts, dtype=np.float64)
    from scripts.neural_challenge import patch_histogram

    def one_chain(chain: int):
        operators = np.empty((measurements, len(EVEN_SHAPES)), dtype=np.float64)
        target_operators = np.empty_like(operators)
        biased_patch = np.zeros(512, dtype=np.float64)
        target_patch = np.zeros(512, dtype=np.float64)
        biased_energies = np.empty(measurements, dtype=np.float64)
        target_energies = np.empty_like(biased_energies)
        initial_rng = np.random.default_rng(
            _child_sequence(stream, *child_prefix, chain, 0)
        )
        transition_rng = np.random.default_rng(
            _child_sequence(stream, *child_prefix, chain, 1)
        )
        target_rng = np.random.default_rng(
            _child_sequence(stream, *child_prefix, chain, 2)
        )
        initial = initial_rng.choice(
            np.asarray([-1, 1], dtype=np.int8), size=(length, length)
        )
        sampler = NeuralToNeuralBiasedMetropolis(
            initial,
            previous_model,
            current_model,
            transition_rng,
            block_size=block_size,
            compiled=True,
        )
        sampler.run_sweeps(max(1, thermal))
        attempted = sampler.attempted
        accepted = sampler.accepted
        for measurement in range(measurements):
            sampler.run_sweeps(spacing)
            operators[measurement] = (
                operator_basis.values(sampler.block_spins) / normalizers
            )
            biased_patch += patch_histogram(sampler.block_spins)
            biased_energies[measurement] = current_model.energy(
                sampler.block_spins
            )
            target = target_rng.choice(
                np.asarray([-1, 1], dtype=np.int8), size=(coarse, coarse)
            )
            target_operators[measurement] = operator_basis.values(target) / normalizers
            target_patch += patch_histogram(target)
            target_energies[measurement] = current_model.energy(target)
        acceptance = (sampler.accepted - accepted) / (sampler.attempted - attempted)
        sampler.assert_cache_consistent()
        return (
            operators - target_operators,
            biased_patch / biased_patch.sum(),
            target_patch / target_patch.sum(),
            np.stack((biased_energies, target_energies)),
            float(acceptance),
        )

    worker_limit = resolve_worker_limit(workers, chains)
    with ThreadPoolExecutor(max_workers=worker_limit) as executor:
        results = list(executor.map(one_chain, range(chains)))
    return (
        np.stack([item[0] for item in results]),
        np.stack([item[1] for item in results]),
        np.stack([item[2] for item in results]),
        np.stack([item[3] for item in results], axis=1),
        [item[4] for item in results],
    )


def _monitor_window(
    previous_model: D4EvenLocalMLP,
    current_model: D4EvenLocalMLP,
    *,
    length: int,
    block_size: int,
    stream: SeedStream,
    round_index: int,
    update: int,
    budget: dict[str, int],
    previous_objective: float | None,
    previous_parameters: np.ndarray | None,
    record_gradient_norm: float,
    polyak_fraction: float,
    workers: int | None = None,
    basis: OperatorBasis | None = None,
) -> tuple[TrainingWindow, float, np.ndarray, dict[str, Any]]:
    differences, biased_patch, target_patch, energies, _ = _neural_samples(
        previous_model,
        current_model,
        length=length,
        block_size=block_size,
        stream=stream,
        child_prefix=(round_index, update),
        chains=budget["monitor_chains"],
        thermal=budget["monitor_thermal"],
        measurements=budget["monitor_measurements"],
        spacing=1,
        workers=workers,
        basis=basis,
    )
    operator_equivalence = float(np.max(np.abs(differences.mean(axis=(0, 1)))))
    observed_patch_tv, target_patch_tv, excess_patch_tv = (
        excess_patch_tv_components(biased_patch, target_patch)
    )
    patch_tv = float(np.mean(excess_patch_tv))
    patch_diagnostics = {
        "update": update,
        "statistic": "excess_vs_independent_uniform_baseline",
        "observed_patch_tv_by_chain": observed_patch_tv.tolist(),
        "target_patch_tv_by_chain": target_patch_tv.tolist(),
        "excess_patch_tv_by_chain": excess_patch_tv.tolist(),
        "raw_two_sample_patch_tv_by_chain": (
            0.5 * np.sum(np.abs(biased_patch - target_patch), axis=1)
        ).tolist(),
    }
    biased_energy, target_energy = energies
    coarse_sites = (length // block_size) ** 2
    objective = float(
        (-_log_mean_exp(biased_energy) + float(target_energy.mean())) / coarse_sites
    )
    objective_change = (
        1.0e6 if previous_objective is None else objective - previous_objective
    )
    parameters = _flatten_parameters(current_model)
    parameter_drift = (
        1.0e6
        if previous_parameters is None
        else float(
            np.linalg.norm(parameters - previous_parameters) / np.sqrt(parameters.size)
        )
    )
    return (
        TrainingWindow(
            update=update,
            held_out_objective=objective,
            held_out_objective_change=objective_change,
            gradient_norm=record_gradient_norm,
            operator_equivalence=operator_equivalence,
            patch_tv=patch_tv,
            parameter_drift=parameter_drift,
            polyak_fraction=polyak_fraction,
            parameters_finite=model_parameters_finite(current_model),
            gradient_finite=bool(np.isfinite(record_gradient_norm)),
        ),
        objective,
        parameters,
        patch_diagnostics,
    )


def _train_neural_round(
    previous_model: D4EvenLocalMLP,
    *,
    protocol: TrainingProtocol,
    bundle: SeedBundle,
    round_index: int,
    preset: str,
    length: int,
    block_size: int,
    output: Path,
    initial_spins: np.ndarray | None = None,
    workers: int | None = None,
) -> tuple[D4EvenLocalMLP, dict[str, Any]]:
    budget = _sampling_budget(preset)
    model = D4EvenLocalMLP.random(
        3,
        32,
        _integer_seed(bundle.streams["neural_training"], round_index, 0),
        feature_mode="multiscale",
    )
    initial_values: np.ndarray | None = None
    if initial_spins is not None:
        initial_values = np.asarray(initial_spins, dtype=np.int8)
        if initial_values.shape != (budget["walkers"], length, length):
            raise ValueError(
                "neural round initial spins must match the frozen walker/lattice budget"
            )
        if not np.all((initial_values == -1) | (initial_values == 1)):
            raise ValueError("neural round initial spins must contain only -1 and +1")
    samplers = []
    actual_initial = []
    for walker in range(budget["walkers"]):
        initial_rng = np.random.default_rng(
            _child_sequence(bundle.streams["initial_condition"], round_index, walker)
        )
        transition_rng = np.random.default_rng(
            _child_sequence(bundle.streams["neural_training"], round_index, walker, 1)
        )
        initial = (
            initial_rng.choice(
                np.asarray([-1, 1], dtype=np.int8), size=(length, length)
            )
            if initial_values is None
            else initial_values[walker].copy()
        )
        actual_initial.append(initial.copy())
        samplers.append(
            NeuralToNeuralBiasedMetropolis(
                initial,
                previous_model,
                model,
                transition_rng,
                block_size=block_size,
                compiled=True,
            )
        )
    target_rng = np.random.default_rng(
        _child_sequence(bundle.streams["neural_training"], round_index, 999)
    )
    coarse = length // block_size
    coarse_sites = coarse * coarse
    stop_state = TrainingStopState(protocol.stop)
    polyak = PolyakAverager(protocol.polyak_start_update)
    records: list[dict[str, Any]] = []
    previous_objective: float | None = None
    previous_parameters: np.ndarray | None = None
    terminal_reason: str | None = None
    patch_monitoring: list[dict[str, Any]] = []
    monitor_basis = OperatorBasis(length // block_size, EVEN_SHAPES)
    started = time.perf_counter()
    attempted_start = sum(sampler.attempted for sampler in samplers)
    worker_limit = resolve_worker_limit(workers, len(samplers))
    with ThreadPoolExecutor(max_workers=worker_limit) as executor:
        for step in range(protocol.maximum_updates):
            attempted_before = sum(sampler.attempted for sampler in samplers)
            accepted_before = sum(sampler.accepted for sampler in samplers)
            accumulated = _zero_gradient(model)
            biased_energy = 0.0
            target_energy = 0.0
            for _ in range(protocol.gradient_accumulation_batches):
                list(
                    executor.map(
                        lambda sampler: sampler.run_sweeps(
                            protocol.sweeps_per_gradient_batch
                        ),
                        samplers,
                    )
                )
                biased_features = np.stack(
                    [sampler.bias_cache.features for sampler in samplers]
                )
                target_spins = target_rng.choice(
                    np.asarray([-1, 1], dtype=np.int8),
                    size=(protocol.target_samples_per_batch, coarse, coarse),
                )
                target_features = np.stack(
                    [model.feature_grid(spins) for spins in target_spins]
                )
                biased_gradient = _scale_gradient(
                    model.gradient_from_features(biased_features),
                    1.0 / (len(samplers) * coarse_sites),
                )
                target_gradient = _scale_gradient(
                    model.gradient_from_features(target_features),
                    1.0 / (protocol.target_samples_per_batch * coarse_sites),
                )
                _add_gradient(
                    accumulated,
                    _subtract_gradient(target_gradient, biased_gradient),
                )
                biased_energy += float(
                    np.mean([sampler.bias_cache.energy for sampler in samplers])
                    / coarse_sites
                )
                target_energy += float(
                    model.density_from_features(target_features).sum()
                    / (protocol.target_samples_per_batch * coarse_sites)
                )
            gradient = _scale_gradient(
                accumulated,
                1.0 / protocol.gradient_accumulation_batches,
            )
            gradient, original_norm, clipped_norm = clip_mlp_gradient(
                gradient,
                protocol.gradient_clip_l2,
            )
            rate = protocol.schedule.rate(step)
            model.weight_in -= rate * gradient.weight_in
            model.bias_hidden -= rate * gradient.bias_hidden
            model.weight_out -= rate * gradient.weight_out
            if not model_parameters_finite(model):
                raise FloatingPointError("non-finite neural-to-neural training parameters")
            polyak.observe(step + 1, model)
            for sampler in samplers:
                sampler.refresh_bias_model(model)
            attempted = sum(sampler.attempted for sampler in samplers) - attempted_before
            accepted = sum(sampler.accepted for sampler in samplers) - accepted_before
            row = {
                "step": step,
                "update": step + 1,
                "learning_rate": rate,
                "unclipped_gradient_norm": original_norm,
                "clipped_gradient_norm": clipped_norm,
                "biased_energy_per_site": (
                    biased_energy / protocol.gradient_accumulation_batches
                ),
                "target_energy_per_site": (
                    target_energy / protocol.gradient_accumulation_batches
                ),
                "acceptance_rate": float(accepted / attempted),
                "stop_reason": "",
            }
            if (
                (step + 1) % protocol.stop.monitor_every == 0
                or step + 1 == protocol.maximum_updates
            ):
                (
                    window,
                    previous_objective,
                    previous_parameters,
                    patch_diagnostics,
                ) = _monitor_window(
                    previous_model,
                    model,
                    length=length,
                    block_size=block_size,
                    stream=bundle.streams["monitoring"],
                    round_index=round_index,
                    update=step + 1,
                    budget=budget,
                    previous_objective=previous_objective,
                    previous_parameters=previous_parameters,
                    record_gradient_norm=clipped_norm,
                    polyak_fraction=polyak.fraction(step + 1),
                    workers=worker_limit,
                    basis=monitor_basis,
                )
                patch_monitoring.append(patch_diagnostics)
                terminal_reason = stop_state.observe(window)
                if terminal_reason is not None:
                    row["stop_reason"] = terminal_reason
            records.append(row)
            if (
                step == 0
                or (step + 1) % protocol.progress_every == 0
                or terminal_reason is not None
            ):
                print(
                    f"N3 第{round_index}轮 更新{step + 1}/{protocol.maximum_updates} "
                    f"梯度={clipped_norm:.5g} 接受率={row['acceptance_rate']:.4f}",
                    flush=True,
                )
            if terminal_reason is not None:
                break
    if terminal_reason is None:
        terminal_reason = "NOT_CONVERGED"
    if terminal_reason != "CORRECTNESS_FAILURE" and polyak.sample_count > 0:
        polyak.assign_to(model)
        for sampler in samplers:
            sampler.refresh_bias_model(model)
    elapsed = time.perf_counter() - started
    attempted_total = sum(sampler.attempted for sampler in samplers) - attempted_start
    arrays = {
        key: np.asarray([row[key] for row in records])
        for key in records[0]
        if key != "stop_reason"
    }
    arrays["stop_reason"] = np.asarray([row["stop_reason"] for row in records])
    atomic_write_npz(output / "trajectory.npz", arrays)
    training_report = {
        "round": round_index,
        "updates": len(records),
        "stop_reason": terminal_reason,
        "protocol": asdict(protocol),
        "monitoring": stop_state.to_dict(),
        "patch_tv_statistic": "excess_vs_independent_uniform_baseline",
        "patch_tv_diagnostics": patch_monitoring,
        "polyak_sample_count": polyak.sample_count,
        "elapsed_seconds": elapsed,
        "proposals": int(attempted_total),
        "proposals_per_second": float(attempted_total / elapsed),
        "walkers": len(samplers),
        "threads": worker_limit,
        "fixed_linear_bias": [0.0] * 13,
        "initial_state_sha256": sha256_bytes(
            np.ascontiguousarray(np.stack(actual_initial)).tobytes(order="C")
        ),
    }
    atomic_write_json(output / "training.json", training_report)
    return model, training_report


def _validate_neural_round(
    previous_model: D4EvenLocalMLP,
    current_model: D4EvenLocalMLP,
    *,
    length: int,
    block_size: int,
    bundle: SeedBundle,
    round_index: int,
    preset: str,
    workers: int | None = None,
    operator_equivalence_upper: float = 0.02,
    excess_patch_tv_upper: float = 0.02,
) -> dict[str, Any]:
    budget = _sampling_budget(preset)
    differences, biased_patch, target_patch, _, acceptances = _neural_samples(
        previous_model,
        current_model,
        length=length,
        block_size=block_size,
        stream=bundle.streams["validation"],
        child_prefix=(round_index,),
        chains=budget["validation_chains"],
        thermal=budget["validation_thermal"],
        measurements=budget["validation_measurements"],
        spacing=budget["validation_spacing"],
        workers=workers,
    )
    chain_means = differences.mean(axis=1)
    means = chain_means.mean(axis=0)
    errors = chain_means.std(axis=0, ddof=1) / np.sqrt(chain_means.shape[0])
    operator_bound = float(np.max(np.abs(means) + 2.0 * errors))
    observed_patch_tv, target_patch_tv, excess_patch_tv = (
        excess_patch_tv_components(biased_patch, target_patch)
    )
    patch_bound = float(
        excess_patch_tv.mean()
        + 2.0 * excess_patch_tv.std(ddof=1) / np.sqrt(excess_patch_tv.size)
    )
    passed = bool(
        operator_bound <= operator_equivalence_upper
        and patch_bound <= excess_patch_tv_upper
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "operator_equivalence_upper_bound": operator_bound,
        "operator_equivalence_threshold": float(operator_equivalence_upper),
        "patch_tv_statistic": "excess_vs_independent_uniform_baseline",
        "excess_patch_tv_upper_bound": patch_bound,
        "excess_patch_tv_threshold": float(excess_patch_tv_upper),
        "observed_patch_tv_by_chain": observed_patch_tv.tolist(),
        "target_patch_tv_by_chain": target_patch_tv.tolist(),
        "excess_patch_tv_by_chain": excess_patch_tv.tolist(),
        "raw_two_sample_patch_tv_by_chain": (
            0.5 * np.sum(np.abs(biased_patch - target_patch), axis=1)
        ).tolist(),
        # Compatibility alias for readers created before the incident fix.
        "patch_tv_upper_bound": patch_bound,
        "operator_means_by_chain": chain_means.tolist(),
        "patch_tv_by_chain": excess_patch_tv.tolist(),
        "acceptance_rate_by_chain": [float(item) for item in acceptances],
        "stream_hash": _stream_hash(bundle.streams["validation"], round_index),
        "workers_per_bundle": resolve_worker_limit(
            workers,
            budget["validation_chains"],
        ),
    }


def _measure_neural_objective(
    previous_model: D4EvenLocalMLP,
    current_model: D4EvenLocalMLP,
    *,
    length: int,
    block_size: int,
    bundle: SeedBundle,
    round_index: int,
    objective_mapping: dict[str, Any],
    objective_protocol: Any,
    output: Path,
    workers: int | None = None,
) -> dict[str, Any]:
    ladder = tuple(float(item) for item in objective_mapping["lambda_ladder"])
    chains = int(objective_mapping["chains_per_bridge"])
    measurements = int(objective_mapping["measurements"])
    thermal = int(objective_mapping["thermal_sweeps"])
    spacing = int(objective_mapping["spacing_sweeps"])
    sets = []
    arrays: dict[str, np.ndarray] = {}
    stream_hashes = []
    worker_limit = resolve_worker_limit(workers, chains)
    with ThreadPoolExecutor(max_workers=worker_limit) as executor:
        for lambda_index, lambda_value in enumerate(ladder):
            stream = (
                bundle.streams["objective_anchor"]
                if lambda_index == 0
                else bundle.streams["objective_neural"]
            )
            scaled = current_model.copy()
            scaled.weight_out *= lambda_value

            def one_chain(chain: int) -> np.ndarray:
                energies = np.empty(measurements, dtype=np.float64)
                initial_rng = np.random.default_rng(
                    _child_sequence(stream, round_index, lambda_index, chain, 0)
                )
                transition_rng = np.random.default_rng(
                    _child_sequence(stream, round_index, lambda_index, chain, 1)
                )
                initial = initial_rng.choice(
                    np.asarray([-1, 1], dtype=np.int8), size=(length, length)
                )
                sampler = NeuralToNeuralBiasedMetropolis(
                    initial,
                    previous_model,
                    scaled,
                    transition_rng,
                    block_size=block_size,
                    compiled=True,
                )
                sampler.run_sweeps(max(1, thermal))
                for measurement in range(measurements):
                    sampler.run_sweeps(spacing)
                    energies[measurement] = current_model.energy(
                        sampler.block_spins
                    )
                sampler.assert_cache_consistent()
                return energies

            energies = np.stack(
                list(executor.map(one_chain, range(chains)))
            )
            stream_hash = _stream_hash(stream, round_index, lambda_index)
            sample_hash = sha256_bytes(
                np.ascontiguousarray(energies).tobytes(order="C")
            )
            sets.append(ChainSet(energies, lambda_value, stream_hash, sample_hash))
            arrays[f"lambda_{lambda_index:02d}"] = energies
            stream_hashes.append(stream_hash)
    target_stream = bundle.streams["objective_target"]
    target = np.empty((chains, measurements), dtype=np.float64)
    coarse = length // block_size
    for chain in range(chains):
        rng = np.random.default_rng(
            _child_sequence(target_stream, round_index, chain)
        )
        for measurement in range(measurements):
            spins = rng.choice(
                np.asarray([-1, 1], dtype=np.int8), size=(coarse, coarse)
            )
            target[chain, measurement] = current_model.energy(spins)
    target_hash = _stream_hash(target_stream, round_index)
    target_set = ChainSet(
        target,
        None,
        target_hash,
        sha256_bytes(np.ascontiguousarray(target).tobytes(order="C")),
    )
    arrays["target"] = target
    result = bridge_objective(sets[0], sets[1:], target_set, objective_protocol)
    atomic_write_npz(output / "objective_samples.npz", arrays)
    payload = {
        "estimator": "stratified_BAR",
        "common_zero_bias_anchor": True,
        "lambda_ladder": list(ladder),
        "stream_hashes": [*stream_hashes, target_hash],
        "workers_per_bundle": worker_limit,
        "result": _json_ready(asdict(result)),
    }
    atomic_write_json(output / "objective.json", payload)
    return payload


def _previous_checkpoint(
    previous_root: Path,
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    previous_round: int,
) -> tuple[NeuralCheckpoint, dict[str, Any], str, np.ndarray]:
    report_name = "one_round_report.json" if previous_round == 1 else "round_report.json"
    report = json.loads((previous_root / report_name).read_text(encoding="ascii"))
    gauge = np.load(previous_root / "gauge_reference.npz", allow_pickle=False)["spins"]
    manifest_hash = sha256_file(previous_root / "manifest.json")
    expected_predecessor = (
        None
        if previous_round == 1
        else str(report["predecessor_manifest_sha256"])
    )
    checkpoint = load_neural_checkpoint(
        previous_root / "checkpoint",
        CheckpointExpectations(
            bundle_id=bundle.bundle_id,
            round_index=previous_round,
            predecessor_manifest_sha256=expected_predecessor,
            protocol_sha256=protocol.protocol_sha256,
            code_sha256=current_code_sha256(),
            operator_basis_sha256=protocol.operator_basis_sha256,
            gauge_reference_sha256=str(report["gauge_reference_sha256"]),
            seed_bundle_sha256=str(report["seed_bundle_sha256"]),
            gauge_spins=gauge,
        ),
    )
    return checkpoint, report, manifest_hash, gauge


def _run_later_round(
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    *,
    round_index: int,
    preset: str,
    length: int,
    block_size: int,
    training_protocol: TrainingProtocol,
    objective_mapping: dict[str, Any],
    objective_protocol: Any,
    previous_root: Path,
    output: Path,
    initial_spins: np.ndarray | None = None,
    workers: int | None = None,
    backend: str = "slurm",
    local_compute_deviation: bool = False,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite round output: {output}")
    checkpoint, previous_report, predecessor_hash, gauge = _previous_checkpoint(
        previous_root,
        protocol,
        bundle,
        round_index - 1,
    )
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    started = time.perf_counter()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    try:
        current_model, training = _train_neural_round(
            checkpoint.model,
            protocol=training_protocol,
            bundle=bundle,
            round_index=round_index,
            preset=preset,
            workers=workers,
            length=length,
            block_size=block_size,
            output=staging,
            initial_spins=initial_spins,
        )
        current_model.save(str(staging / "bias_model.npz"))
        validation = _validate_neural_round(
            checkpoint.model,
            current_model,
            length=length,
            block_size=block_size,
            bundle=bundle,
            round_index=round_index,
            preset=preset,
            workers=workers,
            operator_equivalence_upper=float(
                protocol.gates["operator_equivalence_upper"]
            ),
            excess_patch_tv_upper=float(protocol.gates["excess_patch_tv_upper"]),
        )
        atomic_write_json(staging / "validation.json", validation)
        candidates = _candidate_diagnostics(
            current_model,
            length // block_size,
            preset,
            bundle.streams["projection"],
        )
        atomic_write_json(staging / "candidate_26.json", candidates)
        objective = _measure_neural_objective(
            checkpoint.model,
            current_model,
            length=length,
            block_size=block_size,
            bundle=bundle,
            round_index=round_index,
            objective_mapping=objective_mapping,
            objective_protocol=objective_protocol,
            output=staging,
            workers=workers,
        )
        atomic_write_npz(staging / "gauge_reference.npz", {"spins": gauge})
        gauge_hash = sha256_bytes(np.ascontiguousarray(gauge).tobytes(order="C"))
        atomic_write_json(
            staging / "gauge_reference.json",
            {
                "shape": list(gauge.shape),
                "dtype": "int8",
                "raw_array_sha256": gauge_hash,
                "inherited_from_round": round_index - 1,
            },
        )
        frozen = D4EvenLocalMLP.load(str(staging / "bias_model.npz"))
        handoff_model = NeuralHamiltonian(frozen, gauge[0])
        expected = -np.asarray([current_model.energy(spins) for spins in gauge])
        observed = np.asarray([handoff_model.full_energy(spins) for spins in gauge])
        difference = observed - expected
        difference -= difference.mean()
        handoff = {
            "relation": "U_next=-V_frozen",
            "maximum_gauge_centered_residual": float(np.max(np.abs(difference))),
            "gauge_reference_sha256": gauge_hash,
        }
        atomic_write_json(staging / "handoff.json", handoff)
        bundle_hash = sha256_bytes(canonical_json_bytes(_bundle_record(bundle)))
        polyak_count = max(
            0,
            int(training["updates"]) - training_protocol.polyak_start_update + 1,
        )
        code_hash = current_code_sha256()
        checkpoint_manifest = save_neural_checkpoint(
            staging / "checkpoint",
            NeuralCheckpoint(
                model=current_model,
                fixed_linear_bias=np.zeros(13, dtype=np.float64),
                update=int(training["updates"]),
                schedule_state=asdict(training_protocol),
                polyak_state={
                    "weight_in_sum": current_model.weight_in * polyak_count,
                    "bias_hidden_sum": current_model.bias_hidden * polyak_count,
                    "weight_out_sum": current_model.weight_out * polyak_count,
                    "sample_count": np.asarray(polyak_count, dtype=np.int64),
                },
                rng_states={
                    name: np.random.default_rng(
                        _child_sequence(stream, round_index, 9999)
                    ).bit_generator.state
                    for name, stream in bundle.streams.items()
                },
                bundle_id=bundle.bundle_id,
                round_index=round_index,
                predecessor_manifest_sha256=predecessor_hash,
                protocol_sha256=protocol.protocol_sha256,
                code_sha256=code_hash,
                operator_basis_sha256=protocol.operator_basis_sha256,
                gauge_reference_sha256=gauge_hash,
                seed_bundle_sha256=bundle_hash,
                stop_state={
                    "terminal_reason": training["stop_reason"],
                    "windows": training["monitoring"]["windows"],
                },
                metadata={
                    "stage": "N3",
                    "round": round_index,
                    "handoff": "U_next=-V_frozen",
                },
                gauge_energies=np.asarray(
                    [current_model.energy(spins) for spins in gauge]
                ),
            ),
        )
        elapsed = time.perf_counter() - started
        resources = {
            "elapsed_seconds": elapsed,
            "peak_rss_kib": int(
                max(rss_before, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            ),
            "checkpoint_bytes": int(
                sum(path.stat().st_size for path in (staging / "checkpoint").rglob("*") if path.is_file())
            ),
            "proposals_per_second": training["proposals_per_second"],
            "sweeps_per_second": float(
                training["proposals_per_second"] / (length * length)
            ),
            "threads": training["threads"],
            "workers_per_bundle": training["threads"],
            "backend": backend,
            "execution_policy": (
                "LOCAL_COMPUTE_DEVIATION"
                if backend == "local" and local_compute_deviation
                else ("LOCAL_TEST" if backend == "local" else "SLURM")
            ),
            "compact_output_bytes": int(
                sum(
                    path.stat().st_size
                    for path in staging.rglob("*")
                    if path.is_file()
                )
            ),
            "log_bytes": 0,
        }
        if backend == "local":
            resources["max_parallel_bundles"] = 2
            resources["host"] = local_host_provenance(
                workers_per_bundle=training["threads"],
                max_parallel_bundles=2,
            )
        atomic_write_json(staging / "resources.json", resources)
        correctness_pass = handoff["maximum_gauge_centered_residual"] <= 1e-10
        scientific_gates = {
            "training": training["stop_reason"],
            "validation": validation["status"],
            "objective": objective["result"]["classification"],
        }
        scientific_pass = scientific_round_gates_pass(scientific_gates)
        if not correctness_pass:
            classification = "CORRECTNESS_FAILURE"
            reason = "ROUND_HANDOFF_FAILED"
        elif scientific_pass:
            classification = "EASY_GOAL_SUCCESS"
            reason = "N3_ROUND_CERTIFIED"
        else:
            classification = "SCIENTIFIC_NEGATIVE"
            reason = "N3_ROUND_SCIENTIFIC_GATES_FAILED"
        report = {
            "schema_version": 1,
            "stage": "N3",
            "round": round_index,
            "bundle_id": bundle.bundle_id,
            "classification": classification,
            "reason": reason,
            "microscopic_hamiltonian": (
                f"U_round_{round_index}=-V_round_{round_index - 1}"
            ),
            "predecessor_manifest_sha256": predecessor_hash,
            "fixed_linear_bias": [0.0] * 13,
            "fixed_linear_bias_linf": 0.0,
            "initial_state_sha256": training["initial_state_sha256"],
            "training": training,
            "validation": validation,
            "candidate_26": candidates,
            "objective": objective,
            "scientific_gates": scientific_gates,
            "scientific_pass": scientific_pass,
            "handoff": handoff,
            "resources": resources,
            "code_sha256": code_hash,
            "seed_bundle_sha256": bundle_hash,
            "gauge_reference_sha256": gauge_hash,
            "checkpoint_sha256": checkpoint_manifest["checkpoint_sha256"],
        }
        atomic_write_json(staging / "round_report.json", report)
        manifest = create_stage_manifest(
            stage="N3",
            protocol=protocol,
            classification=classification,
            reason=reason,
            output_root=staging,
            outputs=_output_paths(staging),
            correctness_gates={
                "pure_linear_branch_exact_zero": "PASS",
                "handoff": "PASS" if correctness_pass else "FAIL",
                "checkpoint": "PASS",
            },
            scientific_gates=scientific_gates,
            resources=resources,
            predecessor_manifest_sha256=(predecessor_hash,),
            bundle_id=bundle.bundle_id,
            round_index=round_index,
            code_sha256=code_hash,
            gauge_reference_sha256=gauge_hash,
        )
        manifest["scope"] = "N3_ROUND"
        atomic_write_json(staging / "manifest.json", manifest)
        os.replace(staging, output)
        return {**report, "manifest": manifest}
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _round_summary(root: Path, round_index: int) -> dict[str, Any]:
    report_name = "one_round_report.json" if round_index == 1 else "round_report.json"
    report = json.loads((root / report_name).read_text(encoding="ascii"))
    manifest = json.loads((root / "manifest.json").read_text(encoding="ascii"))
    scientific_gates = dict(manifest["scientific_gates"])
    predecessor = (
        None
        if round_index == 1
        else str(report["predecessor_manifest_sha256"])
    )
    resources = dict(report["resources"])
    gauge_record = json.loads((root / "gauge_reference.json").read_text(encoding="ascii"))
    length = int(gauge_record["shape"][1])
    if "proposals_per_second" not in resources:
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        proposals = int(config["total_walker_sweeps"] * length * length)
        resources["proposals_per_second"] = float(
            proposals / resources["elapsed_seconds"]
        )
    resources.setdefault(
        "sweeps_per_second",
        float(resources["proposals_per_second"] / (length * length)),
    )
    resources.setdefault(
        "checkpoint_bytes",
        int(
            sum(
                path.stat().st_size
                for path in (root / "checkpoint").rglob("*")
                if path.is_file()
            )
        ),
    )
    resources.setdefault(
        "compact_output_bytes",
        int(sum(path.stat().st_size for path in root.rglob("*") if path.is_file())),
    )
    return {
        "round": round_index,
        "classification": report["classification"],
        "reason": report["reason"],
        "scientific_gates": scientific_gates,
        "scientific_pass": scientific_round_gates_pass(scientific_gates),
        "manifest_sha256": sha256_file(root / "manifest.json"),
        "predecessor_manifest_sha256": predecessor,
        "fixed_linear_bias_linf": float(report["fixed_linear_bias_linf"]),
        "initial_state_sha256": str(report["initial_state_sha256"]),
        "microscopic_hamiltonian": (
            "U_round_1=Ising_K_0.436"
            if round_index == 1
            else report["microscopic_hamiltonian"]
        ),
        "objective": report["objective"],
        "resources": resources,
        "manifest": manifest,
    }


def _power_from_round(report: dict[str, Any], bundle: SeedBundle) -> dict[str, Any]:
    result = report["objective"]["result"]
    replicates = result.get("jackknife_replicates")
    site_count = int(result.get("site_count", 1))
    if replicates is None or len(replicates) < 2:
        return {
            "status": "UNIDENTIFIABLE_FROM_PILOT",
            "formal_seed_count": 5,
            "postformal_seed_extension_allowed": False,
            "valid_negative_outcome": (
                "direction_correct_but_confidence_interval_misses_frozen_gate"
            ),
        }
    effects = np.asarray(replicates, dtype=np.float64) / site_count
    variance = float(np.var(effects, ddof=1))
    return {
        "status": "CHAIN_JACKKNIFE_PROXY",
        "between_seed_variance_not_identified": True,
        **estimate_five_seed_power(
            effects,
            np.full(effects.size, variance, dtype=np.float64),
            _integer_seed(bundle.streams["bootstrap"], 0),
        ),
    }


def run_five_round_chain(
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    output: str | Path,
    backend: str,
    resume: bool,
    *,
    preset: str = "pilot",
    rounds: int | None = None,
    pilot_config_path: str | Path = _PILOT_CONFIG,
    initial_spins_by_round: dict[int, np.ndarray] | None = None,
    allow_large_local: bool = False,
    workers: int | None = None,
) -> dict[str, Any]:
    round_count = protocol.formal_rounds if rounds is None else int(rounds)
    if not 2 <= round_count <= protocol.formal_rounds:
        raise ValueError("N3 round count must lie between two and the frozen formal depth")
    if backend not in ("local", "slurm"):
        raise ValueError(f"unknown N3 backend: {backend}")
    if (
        backend == "local"
        and (preset != "smoke" or round_count > 2)
        and not allow_large_local
    ):
        raise ValueError("large local N3 requires allow_large_local=True")
    _bundle_record(bundle)
    destination = Path(output)
    if destination.exists() and not resume:
        raise FileExistsError(f"refusing to overwrite N3 output: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / "manifest.json").is_file():
        if not resume:
            raise FileExistsError(f"refusing to overwrite complete N3 output: {destination}")
        read_verified_stage_manifest(
            destination / "manifest.json",
            protocol,
            expected_stage="N3",
            expected_code_sha256=current_code_sha256(),
        )
        report = json.loads((destination / "chain_report.json").read_text(encoding="ascii"))
        if int(report["requested_rounds"]) != round_count:
            raise ValueError("N3 resume round count does not match the completed run")
        previous_hash: str | None = None
        for round_index, summary in enumerate(report.get("rounds", ()), start=1):
            if int(summary.get("round", 0)) != round_index:
                raise ValueError("N3 round manifest dependency index mismatch")
            verified_round = read_verified_stage_manifest(
                destination / f"round-{round_index:02d}" / "manifest.json",
                protocol,
                expected_stage="N2" if round_index == 1 else "N3",
                expected_code_sha256=current_code_sha256(),
            )
            if verified_round["manifest_sha256"] != summary.get("manifest_sha256"):
                raise ValueError("N3 round manifest dependency hash mismatch")
            if round_index > 1 and previous_hash not in verified_round[
                "predecessor_manifest_sha256"
            ]:
                raise ValueError("N3 round manifest dependency chain mismatch")
            previous_hash = str(verified_round["manifest_sha256"])
        if previous_hash is None or len(report.get("rounds", ())) != round_count:
            raise ValueError("N3 round manifest dependency count mismatch")
        return report

    length = 21 if preset == "smoke" else protocol.physical.length
    block_size = protocol.physical.block_size
    training_protocol, objective_mapping, objective_protocol = _load_run_protocols(
        preset,
        Path(pilot_config_path),
        (length // block_size) ** 2,
    )
    paired_initials = {} if initial_spins_by_round is None else {
        int(index): np.asarray(values, dtype=np.int8)
        for index, values in initial_spins_by_round.items()
    }
    worker_limit = resolve_worker_limit(
        workers,
        _sampling_budget(preset)["walkers"],
    )
    if paired_initials and set(paired_initials) != set(range(1, round_count + 1)):
        raise ValueError("explicit neural initial states must cover every requested round")
    summaries: list[dict[str, Any]] = []
    for round_index in range(1, round_count + 1):
        round_root = destination / f"round-{round_index:02d}"
        if round_root.exists():
            if not resume:
                raise FileExistsError(f"refusing to overwrite N3 round {round_index}")
            expected_stage = "N2" if round_index == 1 else "N3"
            record = read_verified_stage_manifest(
                round_root / "manifest.json",
                protocol,
                expected_stage=expected_stage,
                expected_code_sha256=current_code_sha256(),
            )
            if round_index > 1 and summaries[-1]["manifest_sha256"] not in record[
                "predecessor_manifest_sha256"
            ]:
                raise ValueError("N3 resumed round has the wrong predecessor hash")
        elif round_index == 1:
            run_one_round(
                protocol,
                bundle,
                preset,
                round_root,
                pilot_config_path=pilot_config_path,
                initial_spins=paired_initials.get(round_index),
                backend=backend,
                workers=worker_limit,
                local_compute_deviation=(backend == "local" and allow_large_local),
            )
        else:
            _run_later_round(
                protocol,
                bundle,
                round_index=round_index,
                preset=preset,
                length=length,
                block_size=block_size,
                training_protocol=training_protocol,
                objective_mapping=objective_mapping,
                objective_protocol=objective_protocol,
                previous_root=destination / f"round-{round_index - 1:02d}",
                output=round_root,
                initial_spins=paired_initials.get(round_index),
                workers=worker_limit,
                backend=backend,
                local_compute_deviation=(backend == "local" and allow_large_local),
            )
        summary = _round_summary(round_root, round_index)
        if round_index in paired_initials:
            expected_initial_hash = sha256_bytes(
                np.ascontiguousarray(paired_initials[round_index]).tobytes(order="C")
            )
            if summary["initial_state_sha256"] != expected_initial_hash:
                raise ValueError("neural round initial-state hash does not match plan")
        if round_index > 1 and summary["predecessor_manifest_sha256"] != summaries[-1][
            "manifest_sha256"
        ]:
            raise ValueError("N3 round manifest dependency is not contiguous")
        summaries.append(summary)

    correctness_failure = any(
        item["classification"] in ("CORRECTNESS_FAILURE", "PROTOCOL_FAILURE")
        for item in summaries
    )
    pilot_complete = preset == "pilot" and round_count == protocol.formal_rounds
    passing_rounds = sum(bool(item["scientific_pass"]) for item in summaries)
    pilot_scientific_pass = bool(
        pilot_complete and passing_rounds == protocol.formal_rounds
    )
    if correctness_failure:
        classification = "CORRECTNESS_FAILURE"
        reason = "N3_ROUND_CORRECTNESS_FAILURE"
    elif pilot_scientific_pass:
        classification = "EASY_GOAL_SUCCESS"
        reason = "N3_PILOT_CERTIFIED"
    elif pilot_complete:
        classification = "SCIENTIFIC_NEGATIVE"
        reason = "N3_PILOT_SCIENTIFIC_GATES_FAILED"
    else:
        classification = "SCIENTIFIC_NEGATIVE"
        reason = "SMOKE_STATISTICALLY_INSUFFICIENT"
    power = _power_from_round(summaries[-1], bundle)
    resources = {
        "backend": backend,
        "execution_policy": (
            "LOCAL_COMPUTE_DEVIATION"
            if backend == "local" and allow_large_local
            else ("LOCAL_TEST" if backend == "local" else "SLURM")
        ),
        "workers_per_bundle": worker_limit,
        "max_parallel_bundles": 2,
        "round_wall_seconds": [
            float(item["resources"]["elapsed_seconds"]) for item in summaries
        ],
        "total_wall_seconds": float(
            sum(float(item["resources"]["elapsed_seconds"]) for item in summaries)
        ),
        "peak_rss_kib": int(
            max(int(item["resources"]["peak_rss_kib"]) for item in summaries)
        ),
        "output_bytes": int(
            sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
        ),
    }
    if backend == "local":
        resources["host"] = local_host_provenance(
            workers_per_bundle=worker_limit,
            max_parallel_bundles=2,
        )
    report = {
        "schema_version": 1,
        "stage": "N3",
        "scope": "SINGLE_SEED_FIVE_ROUND_PILOT",
        "preset": preset,
        "bundle_id": bundle.bundle_id,
        "requested_rounds": round_count,
        "classification": classification,
        "reason": reason,
        "rounds": summaries,
        "rounds_passing_scientific_gates": passing_rounds,
        "all_round_scientific_gates_pass": pilot_scientific_pass,
        "power": power,
        "resources": resources,
        "formal_seed_count": 5,
        "postformal_seed_extension_allowed": False,
    }
    atomic_write_json(destination / "chain_report.json", report)
    manifest = create_stage_manifest(
        stage="N3",
        protocol=protocol,
        classification=classification,
        reason=reason,
        output_root=destination,
        outputs=_output_paths(destination),
        correctness_gates={
            "round_count": "PASS" if round_count >= 2 else "FAIL",
            "manifest_chain": "PASS",
            "pure_linear_branch_exact_zero": "PASS",
        },
        scientific_gates={
            "pilot_depth": "PASS" if pilot_complete else "NOT_FORMAL_PILOT",
            "round_science": "PASS" if pilot_scientific_pass else "FAIL",
            "rounds_passing": passing_rounds,
            "power": power["status"],
        },
        resources=resources,
        predecessor_manifest_sha256=(summaries[-1]["manifest_sha256"],),
        bundle_id=bundle.bundle_id,
        round_index=round_count,
        code_sha256=current_code_sha256(),
        gauge_reference_sha256=str(
            summaries[-1]["manifest"]["gauge_reference_sha256"]
        ),
    )
    manifest["scope"] = "N3_STAGE_ONLY"
    atomic_write_json(destination / "manifest.json", manifest)
    return report
