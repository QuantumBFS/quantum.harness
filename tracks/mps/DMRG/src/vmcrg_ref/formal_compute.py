"""Compute kernels for the paired Issue #28 N4 experiment."""

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
from typing import Any, Callable, Mapping

import numpy as np

from .artifacts import (
    atomic_write_json,
    atomic_write_npz,
    sha256_bytes,
    sha256_file,
)
from .autocorrelation import normalized_autocorrelation
from .hybrid_neural import LinearNeuralBiasedMetropolis
from .ising import IsingLattice
from .issue28_protocol import Issue28Protocol, SeedBundle, SeedStream
from .local_execution import local_host_provenance, resolve_worker_limit
from .issue28_workflow import (
    create_stage_manifest,
    current_code_sha256,
    read_verified_stage_manifest,
)
from .multi_optimizer import MultiOperatorOptimizer
from .neural_energy import D4EvenLocalMLP
from .objective import (
    ChainSet,
    bridge_objective,
    objective_protocol_from_mapping,
    paired_objective_difference,
)
from .one_round import _child_sequence, _integer_seed, _stream_hash
from .operators import EVEN_SHAPES, OperatorBasis


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _prepare_output(output: Path) -> None:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError(f"refusing to overwrite nonempty output: {output}")
    output.mkdir(parents=True, exist_ok=True)


def _atomic_compute_directory(
    output: str | Path,
    writer: Callable[[Path], Any],
) -> Any:
    """Publish a compute subtree only after its writer returns successfully."""
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to replace compute output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-", dir=destination.parent
        )
    )
    try:
        result = writer(staging)
        os.replace(staging, destination)
        return result
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def train_linear_round(
    *,
    length: int,
    block_size: int,
    couplings: np.ndarray,
    initial_spins: np.ndarray,
    steps: int,
    sweeps_per_step: int,
    learning_rate: float,
    seed: int,
    output: str | Path,
    workers: int | None = None,
) -> dict[str, Any]:
    """Train one traditional 13-operator VMCRG round from paired states."""
    destination = Path(output)
    _prepare_output(destination)
    initial = np.asarray(initial_spins, dtype=np.int8)
    expected = (initial.shape[0], int(length), int(length))
    if initial.shape != expected or initial.shape[0] < 2:
        raise ValueError("linear initial spins must contain at least two square walkers")
    if not np.all((initial == -1) | (initial == 1)):
        raise ValueError("linear initial spins must contain only -1 and +1")
    initial_hash = sha256_bytes(np.ascontiguousarray(initial).tobytes(order="C"))
    microscopic_couplings = np.asarray(couplings, dtype=np.float64)
    started = time.perf_counter()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    optimizer = MultiOperatorOptimizer(
        length=length,
        couplings=microscopic_couplings,
        shapes=EVEN_SHAPES,
        walkers=initial.shape[0],
        seed=int(seed),
        block_size=block_size,
        compiled=True,
        max_workers=workers,
        initial_spins=initial,
    )
    progress_every = max(1, steps // 20)

    def progress(record: Any) -> None:
        completed = int(record.step) + 1
        if completed == 1 or completed % progress_every == 0 or completed == steps:
            print(
                f"线性训练 {completed}/{steps} 梯度范数={record.gradient_norm:.5g}",
                flush=True,
            )

    records = optimizer.run(
        steps=steps,
        sweeps_per_step=sweeps_per_step,
        learning_rate=learning_rate,
        callback=progress,
    )
    elapsed = time.perf_counter() - started
    final_bias = records[-1].running_bias.copy()
    arrays = {
        "instantaneous_bias": np.stack(
            [record.instantaneous_bias for record in records]
        ),
        "running_bias": np.stack([record.running_bias for record in records]),
        "mean_operators": np.stack([record.mean_operators for record in records]),
        "gradient": np.stack([record.gradient for record in records]),
        "update": np.stack([record.update for record in records]),
        "gradient_norm": np.asarray(
            [record.gradient_norm for record in records], dtype=np.float64
        ),
        "acceptance_rates": np.stack(
            [record.acceptance_rates for record in records]
        ),
    }
    atomic_write_npz(destination / "trajectory.npz", arrays)
    report = {
        "schema_version": 1,
        "representation": "traditional_13_operator",
        "length": int(length),
        "block_size": int(block_size),
        "walkers": int(initial.shape[0]),
        "steps": int(steps),
        "sweeps_per_step": int(sweeps_per_step),
        "learning_rate": float(learning_rate),
        "initial_state_sha256": initial_hash,
        "microscopic_couplings": microscopic_couplings.tolist(),
        "final_bias": final_bias.tolist(),
        "next_microscopic_couplings": (-final_bias).tolist(),
        "handoff_relation": "U_next=-V_frozen",
        "final_gradient_norm": float(records[-1].gradient_norm),
        "operator_names": [shape.name for shape in EVEN_SHAPES],
        "resources": {
            "elapsed_seconds": elapsed,
            "peak_rss_kib": int(
                max(rss_before, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            ),
            "proposals": int(
                steps * sweeps_per_step * initial.shape[0] * length * length
            ),
            "threads": optimizer.max_workers,
        },
    }
    atomic_write_json(destination / "linear_round.json", report)
    return report


def _read_linear_round(round_root: Path, expected_round: int) -> dict[str, Any]:
    manifest_path = round_root / "round_manifest.json"
    report_path = round_root / "linear_round.json"
    trajectory_path = round_root / "trajectory.npz"
    if not manifest_path.is_file() or not report_path.is_file() or not trajectory_path.is_file():
        raise ValueError(f"traditional round {expected_round} is incomplete")
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    if manifest.get("arm") != "linear" or int(manifest.get("round", 0)) != expected_round:
        raise ValueError("traditional round manifest identity mismatch")
    expected_outputs = {
        "linear_round.json": sha256_file(report_path),
        "trajectory.npz": sha256_file(trajectory_path),
    }
    if manifest.get("outputs") != expected_outputs:
        raise ValueError("traditional round manifest output hash mismatch")
    report = json.loads(report_path.read_text(encoding="ascii"))
    if (
        report.get("initial_state_sha256") != manifest.get("initial_state_sha256")
        or report.get("microscopic_couplings") != manifest.get("microscopic_couplings")
        or report.get("next_microscopic_couplings")
        != manifest.get("next_microscopic_couplings")
    ):
        raise ValueError("traditional round manifest/report mismatch")
    return {
        **report,
        "round": expected_round,
        "predecessor_manifest_sha256": manifest.get(
            "predecessor_manifest_sha256"
        ),
        "rng_stream_sha256": manifest["rng_stream_sha256"],
        "manifest_sha256": sha256_file(manifest_path),
    }


def run_traditional_chain(
    *,
    length: int,
    block_size: int,
    initial_couplings: np.ndarray,
    initial_spins_by_round: Mapping[int, np.ndarray],
    updates_by_round: Mapping[int, int],
    sweeps_per_update: int,
    learning_rate: float,
    stream: SeedStream,
    output: str | Path,
    resume: bool,
    workers: int | None = None,
) -> dict[str, Any]:
    """Run a hash-linked traditional 13-operator RG chain."""
    rounds = sorted(int(index) for index in initial_spins_by_round)
    if rounds != list(range(1, len(rounds) + 1)) or set(rounds) != {
        int(index) for index in updates_by_round
    }:
        raise ValueError("traditional round inputs must form one contiguous chain")
    if len(rounds) < 1 or sweeps_per_update <= 0 or learning_rate <= 0.0:
        raise ValueError("traditional chain budget is invalid")
    destination = Path(output)
    if destination.exists() and not resume:
        raise FileExistsError(f"refusing to overwrite traditional chain: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    couplings = np.asarray(initial_couplings, dtype=np.float64)
    if couplings.shape != (len(EVEN_SHAPES),):
        raise ValueError("traditional microscopic Hamiltonian must use 13 operators")
    records: list[dict[str, Any]] = []
    predecessor: str | None = None
    for round_index in rounds:
        round_root = destination / f"round-{round_index:02d}"
        expected_initial = np.asarray(initial_spins_by_round[round_index], dtype=np.int8)
        expected_initial_hash = sha256_bytes(
            np.ascontiguousarray(expected_initial).tobytes(order="C")
        )
        if round_root.exists():
            if not resume:
                raise FileExistsError(
                    f"refusing to overwrite traditional round {round_index}"
                )
            record = _read_linear_round(round_root, round_index)
        else:
            def write_round(staging: Path) -> None:
                trained = train_linear_round(
                    length=length,
                    block_size=block_size,
                    couplings=couplings,
                    initial_spins=expected_initial,
                    steps=int(updates_by_round[round_index]),
                    sweeps_per_step=sweeps_per_update,
                    learning_rate=learning_rate,
                    seed=_integer_seed(stream, round_index),
                    output=staging,
                    workers=workers,
                )
                manifest = {
                    "schema_version": 1,
                    "arm": "linear",
                    "round": round_index,
                    "initial_state_sha256": trained["initial_state_sha256"],
                    "microscopic_couplings": trained["microscopic_couplings"],
                    "next_microscopic_couplings": trained[
                        "next_microscopic_couplings"
                    ],
                    "handoff_relation": "U_next=-V_frozen",
                    "rng_stream_sha256": _stream_hash(stream, round_index),
                    "predecessor_manifest_sha256": predecessor,
                    "outputs": {
                        "linear_round.json": sha256_file(
                            staging / "linear_round.json"
                        ),
                        "trajectory.npz": sha256_file(
                            staging / "trajectory.npz"
                        ),
                    },
                }
                atomic_write_json(staging / "round_manifest.json", manifest)

            _atomic_compute_directory(round_root, write_round)
            record = _read_linear_round(round_root, round_index)
        if record["initial_state_sha256"] != expected_initial_hash:
            raise ValueError("traditional round initial-state hash mismatch")
        if not np.array_equal(
            np.asarray(record["microscopic_couplings"], dtype=np.float64),
            couplings,
        ):
            raise ValueError("traditional round handoff couplings mismatch")
        if record["predecessor_manifest_sha256"] != predecessor:
            raise ValueError("traditional round predecessor manifest mismatch")
        predecessor = str(record["manifest_sha256"])
        couplings = np.asarray(
            record["next_microscopic_couplings"], dtype=np.float64
        )
        records.append(record)
    report = {
        "schema_version": 1,
        "arm": "linear",
        "rounds_completed": len(records),
        "rounds": records,
        "handoff_relation": "U_next=-V_frozen",
    }
    atomic_write_json(destination / "chain_report.json", report)
    return report


def _zero_model_like(model: D4EvenLocalMLP) -> D4EvenLocalMLP:
    zero = model.copy()
    zero.weight_out.fill(0.0)
    return zero


def _sample_biased_blocks(
    *,
    length: int,
    block_size: int,
    couplings: np.ndarray,
    linear_bias: np.ndarray,
    neural_bias: D4EvenLocalMLP,
    stream: SeedStream,
    stream_child: tuple[int, ...],
    chains: int,
    thermal_sweeps: int,
    measurements: int,
    spacing_sweeps: int,
    micro_basis: OperatorBasis,
    block_basis: OperatorBasis,
    workers: int | None = None,
) -> np.ndarray:
    coarse = length // block_size
    worker_limit = resolve_worker_limit(workers, chains)

    def one_chain(chain: int) -> np.ndarray:
        configurations = np.empty(
            (measurements, coarse, coarse), dtype=np.int8
        )
        rng = np.random.default_rng(
            _child_sequence(stream, *stream_child, chain)
        )
        sampler = LinearNeuralBiasedMetropolis(
            IsingLattice.random(length, rng),
            couplings,
            linear_bias,
            neural_bias.copy(),
            rng,
            EVEN_SHAPES,
            block_size=block_size,
            compiled=True,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        if thermal_sweeps:
            sampler.run_sweeps(thermal_sweeps)
        for measurement in range(measurements):
            sampler.run_sweeps(spacing_sweeps)
            configurations[measurement] = sampler.block_spins
        sampler.assert_cache_consistent()
        return configurations

    with ThreadPoolExecutor(max_workers=worker_limit) as executor:
        return np.stack(list(executor.map(one_chain, range(chains))))


def _neural_energies(
    model: D4EvenLocalMLP, configurations: np.ndarray
) -> np.ndarray:
    chains, measurements = configurations.shape[:2]
    energies = np.empty((chains, measurements), dtype=np.float64)
    for chain in range(chains):
        for measurement in range(measurements):
            energies[chain, measurement] = model.energy(
                configurations[chain, measurement]
            )
    return energies


def _linear_energies(
    bias: np.ndarray,
    configurations: np.ndarray,
    basis: OperatorBasis,
) -> np.ndarray:
    chains, measurements = configurations.shape[:2]
    energies = np.empty((chains, measurements), dtype=np.float64)
    for chain in range(chains):
        for measurement in range(measurements):
            energies[chain, measurement] = float(
                np.dot(bias, basis.values(configurations[chain, measurement]))
            )
    return energies


def _uniform_targets(
    *,
    coarse: int,
    chains: int,
    measurements: int,
    stream: SeedStream,
    child: int,
) -> np.ndarray:
    configurations = np.empty(
        (chains, measurements, coarse, coarse), dtype=np.int8
    )
    choices = np.asarray([-1, 1], dtype=np.int8)
    for chain in range(chains):
        rng = np.random.default_rng(_child_sequence(stream, child, chain))
        configurations[chain] = rng.choice(
            choices, size=(measurements, coarse, coarse)
        )
    return configurations


def measure_paired_round1_objective(
    *,
    length: int,
    block_size: int,
    coupling: float,
    neural_model: D4EvenLocalMLP,
    linear_bias: np.ndarray,
    objective: Mapping[str, Any],
    anchor_stream: SeedStream,
    neural_stream: SeedStream,
    linear_stream: SeedStream,
    target_stream: SeedStream,
    output: str | Path,
    workers: int | None = None,
) -> dict[str, Any]:
    """Measure paired round-one BAR objectives from one physical anchor."""
    destination = Path(output)
    _prepare_output(destination)
    if length % block_size != 0:
        raise ValueError("length must be divisible by block_size")
    coarse = length // block_size
    bias = np.asarray(linear_bias, dtype=np.float64)
    if bias.shape != (len(EVEN_SHAPES),):
        raise ValueError("linear bias must use the official 13-operator basis")
    ladder = tuple(float(value) for value in objective["neural_lambda_ladder"])
    if ladder != tuple(float(value) for value in objective["linear_lambda_ladder"]):
        raise ValueError("paired neural and linear BAR ladders must match")
    protocol = objective_protocol_from_mapping(
        {**dict(objective), "lambda_ladder": list(ladder)},
        site_count=coarse * coarse,
    )
    chains = int(objective["chains_per_bridge"])
    thermal = int(objective["thermal_sweeps"])
    measurements = int(objective["measurements"])
    spacing = int(objective["spacing_sweeps"])
    couplings = np.asarray([coupling, *([0.0] * 12)], dtype=np.float64)
    zero_bias = np.zeros(len(EVEN_SHAPES), dtype=np.float64)
    zero_model = _zero_model_like(neural_model)
    micro_basis = OperatorBasis(length, EVEN_SHAPES)
    block_basis = OperatorBasis(coarse, EVEN_SHAPES)
    micro_basis.packed_incidence()
    block_basis.packed_incidence()
    worker_limit = resolve_worker_limit(workers, chains)

    anchor_spins = _sample_biased_blocks(
        length=length,
        block_size=block_size,
        couplings=couplings,
        linear_bias=zero_bias,
        neural_bias=zero_model,
        stream=anchor_stream,
        stream_child=(0,),
        chains=chains,
        thermal_sweeps=thermal,
        measurements=measurements,
        spacing_sweeps=spacing,
        micro_basis=micro_basis,
        block_basis=block_basis,
        workers=worker_limit,
    )
    anchor_hash = sha256_bytes(
        np.ascontiguousarray(anchor_spins).tobytes(order="C")
    )
    anchor_stream_hash = _stream_hash(anchor_stream, 0)
    neural_sets: list[ChainSet] = []
    linear_sets: list[ChainSet] = []
    arrays: dict[str, np.ndarray] = {"common_anchor_spins": anchor_spins}

    neural_anchor_energy = _neural_energies(neural_model, anchor_spins)
    linear_anchor_energy = _linear_energies(bias, anchor_spins, block_basis)
    neural_sets.append(
        ChainSet(neural_anchor_energy, 0.0, anchor_stream_hash, anchor_hash)
    )
    linear_sets.append(
        ChainSet(linear_anchor_energy, 0.0, anchor_stream_hash, anchor_hash)
    )
    arrays["neural_anchor_energy"] = neural_anchor_energy
    arrays["linear_anchor_energy"] = linear_anchor_energy

    for lambda_index, lambda_value in enumerate(ladder[1:], start=1):
        scaled_model = neural_model.copy()
        scaled_model.weight_out *= lambda_value
        neural_spins = _sample_biased_blocks(
            length=length,
            block_size=block_size,
            couplings=couplings,
            linear_bias=zero_bias,
            neural_bias=scaled_model,
            stream=neural_stream,
            stream_child=(lambda_index,),
            chains=chains,
            thermal_sweeps=thermal,
            measurements=measurements,
            spacing_sweeps=spacing,
            micro_basis=micro_basis,
            block_basis=block_basis,
            workers=worker_limit,
        )
        neural_energy = _neural_energies(neural_model, neural_spins)
        neural_sample_hash = sha256_bytes(
            np.ascontiguousarray(neural_spins).tobytes(order="C")
        )
        neural_sets.append(
            ChainSet(
                neural_energy,
                lambda_value,
                _stream_hash(neural_stream, lambda_index),
                neural_sample_hash,
            )
        )
        arrays[f"neural_lambda_{lambda_index:02d}_spins"] = neural_spins
        arrays[f"neural_lambda_{lambda_index:02d}_energy"] = neural_energy

        linear_spins = _sample_biased_blocks(
            length=length,
            block_size=block_size,
            couplings=couplings,
            linear_bias=lambda_value * bias,
            neural_bias=zero_model,
            stream=linear_stream,
            stream_child=(lambda_index,),
            chains=chains,
            thermal_sweeps=thermal,
            measurements=measurements,
            spacing_sweeps=spacing,
            micro_basis=micro_basis,
            block_basis=block_basis,
            workers=worker_limit,
        )
        linear_energy = _linear_energies(bias, linear_spins, block_basis)
        linear_sample_hash = sha256_bytes(
            np.ascontiguousarray(linear_spins).tobytes(order="C")
        )
        linear_sets.append(
            ChainSet(
                linear_energy,
                lambda_value,
                _stream_hash(linear_stream, lambda_index),
                linear_sample_hash,
            )
        )
        arrays[f"linear_lambda_{lambda_index:02d}_spins"] = linear_spins
        arrays[f"linear_lambda_{lambda_index:02d}_energy"] = linear_energy

    neural_target_spins = _uniform_targets(
        coarse=coarse,
        chains=chains,
        measurements=measurements,
        stream=target_stream,
        child=0,
    )
    linear_target_spins = _uniform_targets(
        coarse=coarse,
        chains=chains,
        measurements=measurements,
        stream=target_stream,
        child=1,
    )
    neural_target_energy = _neural_energies(neural_model, neural_target_spins)
    linear_target_energy = _linear_energies(
        bias, linear_target_spins, block_basis
    )
    arrays.update(
        neural_target_spins=neural_target_spins,
        neural_target_energy=neural_target_energy,
        linear_target_spins=linear_target_spins,
        linear_target_energy=linear_target_energy,
    )
    neural_target = ChainSet(
        neural_target_energy,
        None,
        _stream_hash(target_stream, 0),
        sha256_bytes(np.ascontiguousarray(neural_target_spins).tobytes(order="C")),
    )
    linear_target = ChainSet(
        linear_target_energy,
        None,
        _stream_hash(target_stream, 1),
        sha256_bytes(np.ascontiguousarray(linear_target_spins).tobytes(order="C")),
    )
    neural_result = bridge_objective(
        neural_sets[0], neural_sets[1:], neural_target, protocol
    )
    linear_result = bridge_objective(
        linear_sets[0], linear_sets[1:], linear_target, protocol
    )
    paired_result = paired_objective_difference(neural_result, linear_result)
    atomic_write_npz(destination / "paired_objective_samples.npz", arrays)
    report = {
        "schema_version": 1,
        "estimator": "stratified_BAR",
        "lambda_ladder": list(ladder),
        "common_zero_bias_anchor": True,
        "actual_anchor_configurations_reused": True,
        "workers_per_bundle": worker_limit,
        "neural": _json_ready(asdict(neural_result)),
        "linear": _json_ready(asdict(linear_result)),
        "paired": _json_ready(asdict(paired_result)),
    }
    atomic_write_json(destination / "paired_objective.json", report)
    return report


def _initial_positive_sequence(
    series: np.ndarray,
    maximum_lag: int,
) -> tuple[np.ndarray, float, int]:
    acf = normalized_autocorrelation(series)[: maximum_lag + 1]
    tau = 0.5
    window = 0
    lag = 1
    while lag < acf.size:
        if lag + 1 < acf.size:
            pair = float(acf[lag] + acf[lag + 1])
            if pair <= 0.0:
                break
            tau += pair
            window = lag + 1
            lag += 2
        else:
            if acf[lag] <= 0.0:
                break
            tau += float(acf[lag])
            window = lag
            break
    return acf, max(0.5, float(tau)), window


def measure_three_arm_autocorrelation(
    *,
    length: int,
    block_size: int,
    coupling: float,
    neural_model: D4EvenLocalMLP,
    linear_bias: np.ndarray,
    initial_spins: np.ndarray,
    stream: SeedStream,
    protocol: Mapping[str, Any],
    output: str | Path,
    round_index: int = 1,
    workers: int | None = None,
) -> dict[str, Any]:
    """Measure neural, traditional, and unbiased chains from paired states."""
    expected_protocol = {
        "observable": "microscopic_nn_density_times_block_nn_density",
        "estimator": "initial_positive_sequence",
    }
    for key, expected in expected_protocol.items():
        if protocol.get(key) != expected:
            raise ValueError(f"formal autocorrelation {key} changed")
    chains = int(protocol["chains"])
    thermal = int(protocol["thermal_sweeps"])
    measurements = int(protocol["measurements"])
    spacing = int(protocol["spacing_sweeps"])
    maximum_lag = int(protocol["maximum_lag"])
    if (
        chains < 2
        or thermal < 0
        or measurements < 4
        or spacing <= 0
        or not 0 < maximum_lag < measurements
        or round_index < 1
    ):
        raise ValueError("formal autocorrelation sampling budget is invalid")
    initial = np.asarray(initial_spins, dtype=np.int8)
    if initial.shape != (chains, length, length):
        raise ValueError("autocorrelation initial states do not match the chain budget")
    if not np.all((initial == -1) | (initial == 1)):
        raise ValueError("autocorrelation initial states must contain only -1 and +1")
    worker_limit = resolve_worker_limit(workers, chains)
    bias = np.asarray(linear_bias, dtype=np.float64)
    if bias.shape != (len(EVEN_SHAPES),):
        raise ValueError("autocorrelation linear bias must contain 13 operators")
    destination = Path(output)
    _prepare_output(destination)
    couplings = np.asarray([coupling, *([0.0] * 12)], dtype=np.float64)
    zero_bias = np.zeros(len(EVEN_SHAPES), dtype=np.float64)
    zero_model = _zero_model_like(neural_model)
    micro_basis = OperatorBasis(length, EVEN_SHAPES)
    block_basis = OperatorBasis(length // block_size, EVEN_SHAPES)
    micro_basis.packed_incidence()
    block_basis.packed_incidence()
    micro_normalizer = float(micro_basis.instance_counts[0])
    block_normalizer = float(block_basis.instance_counts[0])
    initial_hash = sha256_bytes(np.ascontiguousarray(initial).tobytes(order="C"))
    arms = ("neural", "linear", "unbiased")
    specifications = {
        "neural": (zero_bias, neural_model),
        "linear": (bias, zero_model),
        "unbiased": (zero_bias, zero_model),
    }
    arrays: dict[str, np.ndarray] = {}
    report: dict[str, Any] = {
        "schema_version": 1,
        "arms": list(arms),
        "common_initial_state": True,
        "observable": protocol["observable"],
        "estimator": protocol["estimator"],
        "maximum_lag": maximum_lag,
        "round": int(round_index),
        "workers_per_bundle": worker_limit,
    }

    for arm_index, arm in enumerate(arms):
        arm_bias, arm_model = specifications[arm]

        def one_chain(chain: int) -> tuple[np.ndarray, np.ndarray, float, int, float, float]:
            rng = np.random.default_rng(
                _child_sequence(stream, round_index, arm_index, chain)
            )
            sampler = LinearNeuralBiasedMetropolis(
                IsingLattice(initial[chain].copy()),
                couplings,
                arm_bias,
                arm_model.copy(),
                rng,
                EVEN_SHAPES,
                block_size=block_size,
                compiled=True,
                micro_basis=micro_basis,
                block_basis=block_basis,
            )
            if thermal:
                sampler.run_sweeps(thermal)
            attempted_before = sampler.attempted
            accepted_before = sampler.accepted
            values = np.empty(measurements, dtype=np.float64)
            started = time.perf_counter()
            for measurement in range(measurements):
                sampler.run_sweeps(spacing)
                values[measurement] = (
                    sampler.micro_values[0]
                    / micro_normalizer
                    * sampler.block_values[0]
                    / block_normalizer
                )
            elapsed = time.perf_counter() - started
            attempted = sampler.attempted - attempted_before
            accepted = sampler.accepted - accepted_before
            sampler.assert_cache_consistent()
            acf, tau, window = _initial_positive_sequence(values, maximum_lag)
            return values, acf, tau, window, accepted / attempted, elapsed

        with ThreadPoolExecutor(
            max_workers=worker_limit
        ) as executor:
            results = list(executor.map(one_chain, range(chains)))
        series = np.stack([item[0] for item in results])
        acf = np.stack([item[1] for item in results])
        tau = np.asarray([item[2] for item in results], dtype=np.float64)
        windows = np.asarray([item[3] for item in results], dtype=np.int64)
        acceptance = np.asarray([item[4] for item in results], dtype=np.float64)
        elapsed = np.asarray([item[5] for item in results], dtype=np.float64)
        ess = measurements / (2.0 * tau)
        ess_per_second = ess / elapsed
        arrays[f"{arm}_series"] = series
        arrays[f"{arm}_acf"] = acf
        arrays[f"{arm}_tau_int"] = tau
        arrays[f"{arm}_ess_per_second"] = ess_per_second
        report[arm] = {
            "initial_state_sha256": initial_hash,
            "rng_stream_sha256": _stream_hash(
                stream, round_index, arm_index
            ),
            "tau_int_by_chain": tau.tolist(),
            "tau_int_mean": float(tau.mean()),
            "window_by_chain": windows.tolist(),
            "ess_by_chain": ess.tolist(),
            "ess_per_second_by_chain": ess_per_second.tolist(),
            "ess_per_second_mean": float(ess_per_second.mean()),
            "acceptance_rate_by_chain": acceptance.tolist(),
            "measurement_elapsed_seconds_by_chain": elapsed.tolist(),
        }
        print(f"三臂自相关 {arm} 完成 {chains} 条链", flush=True)
    atomic_write_npz(destination / "series.npz", arrays)
    atomic_write_json(destination / "autocorrelation.json", report)
    return report


def _json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid formal artifact: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"formal artifact must be a JSON object: {path}")
    return value


def finalize_formal_bundle(
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    output: str | Path,
    plan: Mapping[str, Any],
    *,
    backend: str = "slurm",
    workers: int | None = None,
) -> dict[str, Any]:
    """Validate completed arms and write the terminal N4 bundle manifest."""
    root = Path(output)
    if bundle.bundle_id != plan.get("bundle_id"):
        raise ValueError("formal bundle plan identity mismatch")
    planned_rounds = list(plan.get("rounds", ()))
    if len(planned_rounds) != protocol.formal_rounds:
        raise ValueError("formal bundle plan does not contain five rounds")
    neural = _json_file(root / "neural" / "chain_report.json")
    linear = _json_file(root / "linear" / "chain_report.json")
    objective = _json_file(root / "objective" / "paired_objective.json")
    autocorrelation = _json_file(
        root / "autocorrelation" / "autocorrelation.json"
    )
    neural_rounds = list(neural.get("rounds", ()))
    linear_rounds = list(linear.get("rounds", ()))
    rounds_complete = (
        int(neural.get("requested_rounds", 0)) == protocol.formal_rounds
        and int(linear.get("rounds_completed", 0)) == protocol.formal_rounds
        and len(neural_rounds) == protocol.formal_rounds
        and len(linear_rounds) == protocol.formal_rounds
    )
    paired_initials = rounds_complete
    pure_zero = rounds_complete
    for index, planned in enumerate(planned_rounds):
        if index >= len(neural_rounds) or index >= len(linear_rounds):
            paired_initials = False
            pure_zero = False
            break
        expected_hash = planned["initial_state_sha256"]
        paired_initials = paired_initials and (
            neural_rounds[index].get("initial_state_sha256") == expected_hash
            and linear_rounds[index].get("initial_state_sha256") == expected_hash
        )
        pure_zero = pure_zero and float(
            neural_rounds[index].get("fixed_linear_bias_linf", float("inf"))
        ) == 0.0

    objective_classification = str(
        dict(objective.get("paired", {})).get(
            "classification", "UNIDENTIFIABLE_OVERLAP"
        )
    )
    neural_anchor = dict(objective.get("neural", {})).get("anchor_hash")
    linear_anchor = dict(objective.get("linear", {})).get("anchor_hash")
    common_anchor = bool(neural_anchor and neural_anchor == linear_anchor)
    arms = list(autocorrelation.get("arms", ()))
    if arms != ["neural", "linear", "unbiased"]:
        raise ValueError("formal autocorrelation arm set changed")
    values = {arm: dict(autocorrelation.get(arm, {})) for arm in arms}
    tau_neural = float(values["neural"]["tau_int_mean"])
    tau_linear = float(values["linear"]["tau_int_mean"])
    tau_unbiased = float(values["unbiased"]["tau_int_mean"])
    ess_neural = float(values["neural"]["ess_per_second_mean"])
    ess_linear = float(values["linear"]["ess_per_second_mean"])
    ess_unbiased = float(values["unbiased"]["ess_per_second_mean"])
    if min(tau_neural, tau_linear, tau_unbiased, ess_neural, ess_linear, ess_unbiased) <= 0.0:
        raise ValueError("formal autocorrelation summaries must be positive")
    three_arm = {
        "tau_neural_over_unbiased": tau_neural / tau_unbiased,
        "tau_neural_over_linear": tau_neural / tau_linear,
        "ess_neural_over_unbiased": ess_neural / ess_unbiased,
        "ess_neural_over_linear": ess_neural / ess_linear,
        "tau_improves_over_unbiased": tau_neural < tau_unbiased,
        "tau_linear_noninferiority": tau_neural / tau_linear <= 1.10,
        "ess_improves_over_unbiased": ess_neural > ess_unbiased,
        "ess_linear_noninferiority": ess_neural / ess_linear >= 0.90,
    }
    atomic_write_json(root / "three_arm_comparison.json", three_arm)
    correctness_pass = rounds_complete and paired_initials and pure_zero and common_anchor
    scientific_pass = bool(
        objective_classification == "IDENTIFIABLE"
        and all(
            bool(three_arm[key])
            for key in (
                "tau_improves_over_unbiased",
                "tau_linear_noninferiority",
                "ess_improves_over_unbiased",
                "ess_linear_noninferiority",
            )
        )
    )
    if not correctness_pass:
        classification = "CORRECTNESS_FAILURE"
        reason = "FORMAL_BUNDLE_CORRECTNESS_FAILURE"
    elif not scientific_pass:
        classification = "SCIENTIFIC_NEGATIVE"
        reason = "FORMAL_BUNDLE_SCIENTIFIC_GATES_NOT_MET"
    else:
        classification = "EASY_GOAL_SUCCESS"
        reason = "FORMAL_BUNDLE_COMPLETE"
    elapsed_values = [
        float(round_record.get("resources", {}).get("elapsed_seconds", 0.0))
        for round_record in (*neural_rounds, *linear_rounds)
    ]
    rss_values = [
        int(round_record.get("resources", {}).get("peak_rss_kib", 0))
        for round_record in (*neural_rounds, *linear_rounds)
    ]
    runtime = dict(plan.get("runtime", {}))
    effective_workers = int(
        runtime.get(
            "workers_per_bundle",
            dict(plan["resources"]).get("cpus_per_task", workers or 1),
        )
    )
    if workers is not None and int(workers) != effective_workers:
        raise ValueError("formal worker limit does not match the frozen plan")
    resources = {
        "backend": backend,
        "execution_policy": runtime.get(
            "execution_policy", "SLURM" if backend == "slurm" else "LOCAL_COMPUTE_DEVIATION"
        ),
        "round_compute_seconds": elapsed_values,
        "total_round_compute_seconds": float(sum(elapsed_values)),
        "peak_rss_kib": max(rss_values, default=0),
        "threads": effective_workers,
        "workers_per_bundle": effective_workers,
        "max_parallel_bundles": int(runtime.get("max_parallel_bundles", 1)),
        "hardware_class": runtime.get(
            "hardware_class", dict(plan["resources"])["hardware_class"]
        ),
        "output_bytes_before_manifest": int(
            sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
        ),
    }
    if backend == "local":
        resources["host"] = local_host_provenance(
            workers_per_bundle=effective_workers,
            max_parallel_bundles=int(runtime.get("max_parallel_bundles", 2)),
        )
    atomic_write_json(root / "resources.json", resources)
    result = {
        "schema_version": 1,
        "stage": "N4",
        "scope": "N4_FORMAL_BUNDLE",
        "bundle_id": bundle.bundle_id,
        "rounds_completed": min(len(neural_rounds), len(linear_rounds)),
        "rounds": neural_rounds,
        "classification": classification,
        "reason": reason,
        "objective_classification": objective_classification,
        "three_arm": three_arm,
        "arms": ["neural", "linear", "unbiased"],
        "replacement_seed_allowed": False,
        "postformal_seed_extension_allowed": False,
        "correctness": {
            "five_rounds": rounds_complete,
            "paired_initial_states": paired_initials,
            "pure_linear_branch_exact_zero": pure_zero,
            "common_zero_bias_anchor": common_anchor,
        },
        "resources": resources,
    }
    atomic_write_json(root / "bundle_result.json", result)
    outputs = tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    )
    predecessors = ()
    neural_manifest = root / "neural" / "manifest.json"
    if neural_manifest.is_file():
        predecessors = (sha256_file(neural_manifest),)
    manifest = create_stage_manifest(
        stage="N4",
        protocol=protocol,
        classification=classification,
        reason=reason,
        output_root=root,
        outputs=outputs,
        correctness_gates={
            key: "PASS" if value else "FAIL"
            for key, value in result["correctness"].items()
        },
        scientific_gates={
            "objective": objective_classification,
            "three_arm": "PASS" if scientific_pass else "FAIL",
        },
        resources=resources,
        predecessor_manifest_sha256=predecessors,
        bundle_id=bundle.bundle_id,
        round_index=protocol.formal_rounds,
        code_sha256=current_code_sha256(),
    )
    manifest["scope"] = "N4_FORMAL_BUNDLE"
    atomic_write_json(root / "manifest.json", manifest)
    return result


def prepare_formal_bundle_inputs(
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    formal_execution: Mapping[str, Any],
    plan: Mapping[str, Any],
    output: str | Path,
    *,
    resume: bool,
) -> dict[str, Any]:
    """Materialize and verify the immutable paired states for all five rounds."""
    root = Path(output)
    if plan.get("bundle_id") != bundle.bundle_id:
        raise ValueError("formal input bundle identity mismatch")
    rounds = list(plan.get("rounds", ()))
    if len(rounds) != protocol.formal_rounds:
        raise ValueError("formal inputs require exactly five planned rounds")
    arrays: dict[str, np.ndarray] = {}
    records = []
    choices = np.asarray([-1, 1], dtype=np.int8)
    for item in rounds:
        round_index = int(item["round"])
        walkers = int(item["arms"]["neural"]["sampling_budget"]["walkers"])
        values = np.stack(
            [
                np.random.default_rng(
                    _child_sequence(
                        bundle.streams["initial_condition"],
                        round_index,
                        walker,
                    )
                ).choice(
                    choices,
                    size=(protocol.physical.length, protocol.physical.length),
                )
                for walker in range(walkers)
            ]
        )
        observed_hash = sha256_bytes(
            np.ascontiguousarray(values).tobytes(order="C")
        )
        if observed_hash != item["initial_state_sha256"]:
            raise ValueError("materialized formal initial state does not match plan")
        arrays[f"round_{round_index:02d}"] = values
        records.append(
            {
                "round": round_index,
                "shape": list(values.shape),
                "dtype": "int8",
                "sha256": observed_hash,
            }
        )
    objective = _json_ready(formal_execution["objective"])
    objective["lambda_ladder"] = list(objective["neural_lambda_ladder"])
    runtime = {
        "protocol": "issue28_formal_execution_v1",
        "training": _json_ready(formal_execution["training"]),
        "objective": objective,
        "autocorrelation": _json_ready(
            formal_execution.get("autocorrelation", {})
        ),
        "formal_execution_sha256": formal_execution.get(
            "formal_execution_sha256"
        ),
    }
    states_path = root / "paired_initial_states.npz"
    runtime_path = root / "formal_runtime_config.json"
    inputs_path = root / "formal_inputs.json"
    existing = [path for path in (states_path, runtime_path, inputs_path) if path.exists()]
    if existing and not resume:
        raise FileExistsError("refusing to overwrite formal inputs")
    if states_path.exists():
        if not states_path.is_file():
            raise ValueError("resumed formal initial-state archive is invalid")
        with np.load(states_path, allow_pickle=False) as archive:
            if set(archive.files) != set(arrays):
                raise ValueError("resumed formal initial-state keys changed")
            for key, expected in arrays.items():
                np.testing.assert_array_equal(archive[key], expected)
    else:
        atomic_write_npz(states_path, arrays)
    if runtime_path.exists():
        if not runtime_path.is_file():
            raise ValueError("resumed formal runtime protocol is invalid")
        if _json_file(runtime_path) != runtime:
            raise ValueError("resumed formal runtime protocol changed")
    else:
        atomic_write_json(runtime_path, runtime)
    report = {
        "schema_version": 1,
        "bundle_id": bundle.bundle_id,
        "rounds": len(records),
        "initial_states": records,
        "paired_initial_states_sha256": sha256_file(states_path),
        "runtime_config_sha256": sha256_file(runtime_path),
        "plan_sha256": plan["plan_sha256"],
    }
    if inputs_path.exists():
        if _json_file(inputs_path) != report:
            raise ValueError("resumed formal input record changed")
    else:
        atomic_write_json(inputs_path, report)
    return report


def execute_formal_bundle(
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    output: Path,
    formal_execution: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    resume: bool,
    backend: str = "slurm",
    workers: int | None = None,
    allow_large_local: bool = False,
) -> dict[str, Any]:
    """Execute one formal bundle after fail-closed plan verification."""
    destination = Path(output)
    expected_plan = _json_ready(dict(plan))
    plan_path = destination / "formal_plan.json"
    if destination.exists() and not resume:
        raise FileExistsError(f"refusing to overwrite formal bundle: {destination}")
    if destination.exists():
        if not plan_path.is_file():
            raise ValueError("formal resume plan is missing")
        try:
            observed_plan = json.loads(plan_path.read_text(encoding="ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("formal resume plan is invalid") from error
        if observed_plan != expected_plan:
            raise ValueError("formal resume plan does not match the frozen plan")
    else:
        destination.mkdir(parents=True)
        atomic_write_json(plan_path, expected_plan)
    manifest_path = destination / "manifest.json"
    if manifest_path.is_file():
        read_verified_stage_manifest(
            manifest_path,
            protocol,
            expected_stage="N4",
            expected_code_sha256=current_code_sha256(),
        )
        required_dependencies = (
            destination / "paired_initial_states.npz",
            destination / "formal_runtime_config.json",
            destination / "formal_inputs.json",
            destination / "neural" / "manifest.json",
        )
        if not all(path.is_file() for path in required_dependencies):
            raise ValueError("completed formal dependencies are missing")
        prepare_formal_bundle_inputs(
            protocol,
            bundle,
            formal_execution,
            plan,
            destination,
            resume=True,
        )
        with np.load(
            destination / "paired_initial_states.npz", allow_pickle=False
        ) as archive:
            completed_initials = {
                round_index: archive[f"round_{round_index:02d}"].copy()
                for round_index in range(1, protocol.formal_rounds + 1)
            }
        from .five_round import run_five_round_chain

        run_five_round_chain(
            protocol,
            bundle,
            destination / "neural",
            backend=backend,
            resume=True,
            preset="formal",
            rounds=protocol.formal_rounds,
            pilot_config_path=destination / "formal_runtime_config.json",
            initial_spins_by_round=completed_initials,
            allow_large_local=allow_large_local,
            workers=workers,
        )
        result = _json_file(destination / "bundle_result.json")
        if result.get("bundle_id") != bundle.bundle_id:
            raise ValueError("completed formal bundle result identity mismatch")
        return result

    prepare_formal_bundle_inputs(
        protocol,
        bundle,
        formal_execution,
        plan,
        destination,
        resume=resume,
    )
    with np.load(
        destination / "paired_initial_states.npz", allow_pickle=False
    ) as archive:
        initial_states = {
            round_index: archive[f"round_{round_index:02d}"].copy()
            for round_index in range(1, protocol.formal_rounds + 1)
        }

    from .five_round import run_five_round_chain

    neural_root = destination / "neural"
    neural = run_five_round_chain(
        protocol,
        bundle,
        neural_root,
        backend=backend,
        resume=resume and neural_root.exists(),
        preset="formal",
        rounds=protocol.formal_rounds,
        pilot_config_path=destination / "formal_runtime_config.json",
        initial_spins_by_round=initial_states,
        allow_large_local=allow_large_local,
        workers=workers,
    )
    if len(neural.get("rounds", ())) != protocol.formal_rounds:
        raise ValueError("formal neural chain did not complete five rounds")
    updates_by_round: dict[int, int] = {}
    for round_index in range(1, protocol.formal_rounds + 1):
        round_root = neural_root / f"round-{round_index:02d}"
        if round_index == 1:
            configuration = _json_file(round_root / "config.json")
            updates_by_round[round_index] = int(configuration["steps"])
        else:
            round_report = _json_file(round_root / "round_report.json")
            updates_by_round[round_index] = int(
                dict(round_report["training"])["updates"]
            )
        planned_hash = plan["rounds"][round_index - 1][
            "initial_state_sha256"
        ]
        if neural["rounds"][round_index - 1].get(
            "initial_state_sha256"
        ) != planned_hash:
            raise ValueError("formal neural initial-state hash mismatch")
        if float(
            neural["rounds"][round_index - 1]["fixed_linear_bias_linf"]
        ) != 0.0:
            raise ValueError("formal pure-neural 13-operator branch changed")

    training = _json_ready(formal_execution["training"])
    initial_rate = float(training["eta_0"]) * float(training["t_0"]) ** (
        -float(training["p"])
    )
    linear_root = destination / "linear"
    linear = run_traditional_chain(
        length=protocol.physical.length,
        block_size=protocol.physical.block_size,
        initial_couplings=np.asarray(
            [protocol.physical.coupling, *([0.0] * 12)], dtype=np.float64
        ),
        initial_spins_by_round=initial_states,
        updates_by_round=updates_by_round,
        sweeps_per_update=int(training["sweeps_per_gradient_batch"])
        * int(training["gradient_accumulation_batches"]),
        learning_rate=initial_rate,
        stream=bundle.streams["linear_training"],
        output=linear_root,
        resume=resume and linear_root.exists(),
        workers=workers,
    )

    round_one_model = D4EvenLocalMLP.load(
        str(neural_root / "round-01" / "bias_model.npz")
    )
    linear_bias = np.asarray(
        linear["rounds"][0]["final_bias"], dtype=np.float64
    )
    objective_root = destination / "objective"
    if (objective_root / "paired_objective.json").is_file():
        if not resume:
            raise FileExistsError("refusing to overwrite formal objective")
        objective = _json_file(objective_root / "paired_objective.json")
        if not (objective_root / "paired_objective_samples.npz").is_file():
            raise ValueError("formal paired objective samples are missing")
    else:
        objective = _atomic_compute_directory(
            objective_root,
            lambda staging: measure_paired_round1_objective(
                length=protocol.physical.length,
                block_size=protocol.physical.block_size,
                coupling=protocol.physical.coupling,
                neural_model=round_one_model,
                linear_bias=linear_bias,
                objective=_json_ready(formal_execution["objective"]),
                anchor_stream=bundle.streams["objective_anchor"],
                neural_stream=bundle.streams["objective_neural"],
                linear_stream=bundle.streams["objective_linear"],
                target_stream=bundle.streams["objective_target"],
                output=staging,
                workers=workers,
            ),
        )

    autocorrelation_root = destination / "autocorrelation"
    if (autocorrelation_root / "autocorrelation.json").is_file():
        if not resume:
            raise FileExistsError("refusing to overwrite formal autocorrelation")
        autocorrelation = _json_file(
            autocorrelation_root / "autocorrelation.json"
        )
        if not (autocorrelation_root / "series.npz").is_file():
            raise ValueError("formal autocorrelation series are missing")
    else:
        autocorrelation_protocol = _json_ready(
            formal_execution["autocorrelation"]
        )
        autocorrelation = _atomic_compute_directory(
            autocorrelation_root,
            lambda staging: measure_three_arm_autocorrelation(
                length=protocol.physical.length,
                block_size=protocol.physical.block_size,
                coupling=protocol.physical.coupling,
                neural_model=round_one_model,
                linear_bias=linear_bias,
                initial_spins=initial_states[1][
                    : int(autocorrelation_protocol["chains"])
                ],
                stream=bundle.streams["autocorrelation"],
                protocol=autocorrelation_protocol,
                output=staging,
                round_index=1,
                workers=workers,
            ),
        )
    if objective.get("paired") is None or autocorrelation.get("arms") != [
        "neural",
        "linear",
        "unbiased",
    ]:
        raise ValueError("formal measurement output contract mismatch")
    return finalize_formal_bundle(
        protocol,
        bundle,
        destination,
        plan,
        backend=backend,
        workers=workers,
    )
