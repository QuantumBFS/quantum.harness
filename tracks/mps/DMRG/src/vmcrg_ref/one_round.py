"""N2 one-round pure-neural VMCRG execution for Issue #28."""

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
from .candidate_operators import candidate_basis_metadata, candidate_even_shapes
from .hybrid_neural import LinearNeuralBiasedMetropolis
from .ising import IsingLattice
from .issue28_protocol import (
    Issue28Protocol,
    REQUIRED_STREAMS,
    SeedBundle,
    SeedStream,
)
from .local_execution import local_host_provenance, resolve_worker_limit
from .issue28_workflow import create_stage_manifest, current_code_sha256
from .issue28_validation import excess_patch_tv_components
from .neural_checkpoint import NeuralCheckpoint, save_neural_checkpoint
from .neural_energy import D4EvenLocalMLP
from .neural_hamiltonian import NeuralHamiltonian
from .objective import (
    ChainSet,
    IDENTIFIABLE,
    bridge_objective,
    objective_protocol_from_mapping,
)
from .operators import EVEN_SHAPES, OperatorBasis
from .training_protocol import TrainingProtocol, TrainingWindow, load_training_protocol


_ROOT = Path(__file__).resolve().parents[2]
_PILOT_CONFIG = _ROOT / "config" / "issue28_pilot_v1.json"


def one_round_seed_bundle(preset: str) -> SeedBundle:
    entropies = {
        "smoke": 2026286100,
        "pilot": 2026286200,
        "formal": 2026286300,
    }
    if preset not in entropies:
        raise ValueError(f"unknown N2 seed-bundle preset: {preset}")
    entropy = entropies[preset]
    streams = {
        name: SeedStream(entropy, (index,))
        for index, name in enumerate(REQUIRED_STREAMS)
    }
    suffix = "formal-certification" if preset == "formal" else preset
    return SeedBundle(f"n2-{suffix}", MappingProxyType(streams))


def _bundle_record(bundle: SeedBundle) -> dict[str, Any]:
    if set(bundle.streams) != set(REQUIRED_STREAMS):
        raise ValueError("N2 seed bundle does not contain every required stream")
    records = [
        (stream.entropy, stream.spawn_key) for stream in bundle.streams.values()
    ]
    if len(records) != len(set(records)):
        raise ValueError("N2 seed bundle reuses an RNG stream")
    return {
        "bundle_id": bundle.bundle_id,
        "streams": {
            name: stream.to_dict() for name, stream in bundle.streams.items()
        },
    }


def _child_sequence(stream: SeedStream, *child: int) -> np.random.SeedSequence:
    return np.random.SeedSequence(
        stream.entropy,
        spawn_key=(*stream.spawn_key, *(int(item) for item in child)),
    )


def _integer_seed(stream: SeedStream, *child: int) -> int:
    return int(_child_sequence(stream, *child).generate_state(1, dtype=np.uint64)[0])


def _stream_hash(stream: SeedStream, *child: int) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {"entropy": stream.entropy, "spawn_key": [*stream.spawn_key, *child]}
        )
    )


def _smoke_training_protocol() -> TrainingProtocol:
    return load_training_protocol(
        {
            "eta_0": 0.02,
            "t_0": 1.0,
            "p": 0.75,
            "minimum_updates": 1,
            "maximum_updates": 2,
            "sweeps_per_gradient_batch": 1,
            "gradient_accumulation_batches": 1,
            "target_samples_per_batch": 2,
            "polyak_start_update": 1,
            "polyak_start_fraction": 0.5,
            "gradient_clip_l2": 10.0,
            "monitor_every": 1,
            "patience_windows": 2,
            "checkpoint_every": 1,
            "progress_every": 1,
            "held_out_objective_change_upper": 1.0,
            "gradient_norm_upper": 10.0,
            "operator_equivalence_upper": 1.0,
            "patch_tv_upper": 1.0,
            "parameter_drift_upper": 10.0,
            "minimum_polyak_fraction": 0.5,
            "independent_sampling_before_update": True,
            "monitoring_stream_role": "held_out_stopping_only",
            "nonfinite_action": "CORRECTNESS_FAILURE",
            "hard_cap_action": "NOT_CONVERGED",
        }
    )


def _load_run_protocols(
    preset: str,
    config_path: Path,
    coarse_sites: int,
) -> tuple[TrainingProtocol, dict[str, Any], Any]:
    value = json.loads(config_path.read_text(encoding="ascii"))
    marker = value.get("protocol")
    allowed = {"issue28_nonformal_pilot_v1"}
    if preset == "formal":
        allowed.add("issue28_formal_execution_v1")
    if marker not in allowed:
        raise ValueError("unexpected Issue #28 pilot protocol")
    if preset == "smoke":
        objective = dict(value["objective"])
        objective.update(
            lambda_ladder=[0.0, 0.5, 1.0],
            chains_per_bridge=2,
            thermal_sweeps=2,
            measurements=4,
            spacing_sweeps=1,
        )
        training = _smoke_training_protocol()
    else:
        objective = dict(value["objective"])
        training = load_training_protocol(dict(value["training"]))
    return training, objective, objective_protocol_from_mapping(
        objective,
        site_count=coarse_sites,
    )


def _flatten_parameters(model: D4EvenLocalMLP) -> np.ndarray:
    return np.concatenate(
        (model.weight_in.ravel(), model.bias_hidden.ravel(), model.weight_out.ravel())
    )


def _log_mean_exp(values: np.ndarray) -> float:
    maximum = float(np.max(values))
    return maximum + float(np.log(np.mean(np.exp(values - maximum))))


class _OneRoundMonitor:
    def __init__(
        self,
        *,
        length: int,
        block_size: int,
        coupling: float,
        stream: SeedStream,
        preset: str,
    ) -> None:
        self.length = int(length)
        self.block_size = int(block_size)
        self.coarse = self.length // self.block_size
        self.couplings = np.asarray([coupling, *([0.0] * 12)], dtype=np.float64)
        self.stream = stream
        self.preset = preset
        self.previous_objective: float | None = None
        self.previous_parameters: np.ndarray | None = None
        self.windows: list[dict[str, Any]] = []
        self.micro_basis = OperatorBasis(self.length, EVEN_SHAPES)
        self.block_basis = OperatorBasis(self.coarse, EVEN_SHAPES)
        self.micro_basis.packed_incidence()
        self.block_basis.packed_incidence()
        self.normalizers = np.asarray(
            self.block_basis.instance_counts,
            dtype=np.float64,
        )

    def __call__(
        self,
        update: int,
        model: D4EvenLocalMLP,
        record: Any,
        polyak_fraction: float,
    ) -> TrainingWindow:
        from scripts.neural_challenge import patch_histogram

        chains = 2 if self.preset == "smoke" else 4
        thermal = 2 if self.preset == "smoke" else 20
        measurements = 4 if self.preset == "smoke" else 16
        operator_values = []
        biased_patches = np.zeros(512, dtype=np.float64)
        target_patches = np.zeros(512, dtype=np.float64)
        biased_energies = []
        target_energies = []
        for chain in range(chains):
            rng = np.random.default_rng(_child_sequence(self.stream, update, chain, 0))
            target_rng = np.random.default_rng(
                _child_sequence(self.stream, update, chain, 1)
            )
            sampler = LinearNeuralBiasedMetropolis(
                IsingLattice.random(self.length, rng),
                self.couplings,
                np.zeros(13, dtype=np.float64),
                model.copy(),
                rng,
                EVEN_SHAPES,
                block_size=self.block_size,
                compiled=True,
                micro_basis=self.micro_basis,
                block_basis=self.block_basis,
            )
            sampler.run_sweeps(thermal)
            for _ in range(measurements):
                sampler.run_sweeps(1)
                operator_values.append(
                    self.block_basis.values(sampler.block_spins) / self.normalizers
                )
                biased_patches += patch_histogram(sampler.block_spins)
                biased_energies.append(model.energy(sampler.block_spins))
                target = target_rng.choice(
                    np.asarray([-1, 1], dtype=np.int8),
                    size=(self.coarse, self.coarse),
                )
                target_patches += patch_histogram(target)
                target_energies.append(model.energy(target))
            sampler.assert_cache_consistent()
        operators = np.asarray(operator_values)
        operator_equivalence = float(np.max(np.abs(operators.mean(axis=0))))
        biased_patches /= float(biased_patches.sum())
        target_patches /= float(target_patches.sum())
        observed_patch_tv, target_patch_tv, excess_patch_tv = (
            excess_patch_tv_components(biased_patches, target_patches)
        )
        patch_tv = float(excess_patch_tv)
        objective = float(
            (
                -_log_mean_exp(np.asarray(biased_energies))
                + float(np.mean(target_energies))
            )
            / (self.coarse * self.coarse)
        )
        objective_change = (
            1.0e6
            if self.previous_objective is None
            else objective - self.previous_objective
        )
        parameters = _flatten_parameters(model)
        parameter_drift = (
            1.0e6
            if self.previous_parameters is None
            else float(
                np.linalg.norm(parameters - self.previous_parameters)
                / np.sqrt(parameters.size)
            )
        )
        self.previous_objective = objective
        self.previous_parameters = parameters.copy()
        window = TrainingWindow(
            update=update,
            held_out_objective=objective,
            held_out_objective_change=objective_change,
            gradient_norm=float(record.clipped_gradient_norm),
            operator_equivalence=operator_equivalence,
            patch_tv=patch_tv,
            parameter_drift=parameter_drift,
            polyak_fraction=polyak_fraction,
            parameters_finite=bool(np.all(np.isfinite(parameters))),
            gradient_finite=bool(np.isfinite(record.unclipped_gradient_norm)),
        )
        self.windows.append(
            {
                **asdict(window),
                "patch_tv_statistic": "excess_vs_independent_uniform_baseline",
                "observed_patch_tv": float(observed_patch_tv),
                "target_patch_tv": float(target_patch_tv),
                "raw_two_sample_patch_tv": float(
                    0.5 * np.sum(np.abs(biased_patches - target_patches))
                ),
            }
        )
        return window


def _write_microscopic_map(path: Path, coupling: float) -> None:
    atomic_write_json(
        path,
        {
            "schema_version": 1,
            "operator_names": [shape.name for shape in EVEN_SHAPES],
            "input_couplings": [coupling, *([0.0] * 12)],
            "final_renormalized_couplings": [0.0] * 13,
            "role": "N2_pure_neural_microscopic_Ising_input",
        },
    )


def _projection(
    model: D4EvenLocalMLP,
    length: int,
    shapes: tuple[Any, ...],
    count: int,
    seed: int,
) -> dict[str, Any]:
    basis = OperatorBasis(length, shapes)
    rng = np.random.default_rng(seed)
    n_sites = length * length
    x = np.empty((count, len(shapes)), dtype=np.float64)
    y = np.empty(count, dtype=np.float64)
    for index in range(count):
        spins = rng.choice(np.asarray([-1, 1], dtype=np.int8), size=(length, length))
        x[index] = basis.values(spins) / n_sites
        y[index] = -model.energy(spins) / n_sites
    design = np.column_stack((np.ones(count), x))
    parameters, _, rank, singular = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ parameters
    return {
        "samples": count,
        "rank": int(rank),
        "columns": int(design.shape[1]),
        "condition_number": (
            None if singular[-1] == 0.0 else float(singular[0] / singular[-1])
        ),
        "rmse_per_site": float(np.sqrt(np.mean(residual * residual))),
        "constant": float(parameters[0]),
        "couplings": parameters[1:].tolist(),
        "operator_names": [shape.name for shape in shapes],
    }


def _candidate_diagnostics(
    model: D4EvenLocalMLP,
    coarse: int,
    preset: str,
    stream: SeedStream,
) -> dict[str, Any]:
    count = 160 if preset == "smoke" else 2000
    result = {}
    for index, tie in enumerate(("axis5", "generic43")):
        shapes = candidate_even_shapes(tie)
        result[tie] = {
            **_projection(
                model,
                coarse,
                shapes,
                count,
                _integer_seed(stream, 100, index),
            ),
            "basis": candidate_basis_metadata(tie),
        }
    return result


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _measure_objective(
    model: D4EvenLocalMLP,
    *,
    length: int,
    block_size: int,
    coupling: float,
    bundle: SeedBundle,
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
    couplings = np.asarray([coupling, *([0.0] * 12)], dtype=np.float64)
    zero_bias = np.zeros(13, dtype=np.float64)
    coarse = length // block_size
    micro_basis = OperatorBasis(length, EVEN_SHAPES)
    block_basis = OperatorBasis(coarse, EVEN_SHAPES)
    micro_basis.packed_incidence()
    block_basis.packed_incidence()
    arrays: dict[str, np.ndarray] = {}
    sets = []
    stream_hashes = []
    worker_limit = resolve_worker_limit(workers, chains)
    with ThreadPoolExecutor(max_workers=worker_limit) as executor:
        for lambda_index, lambda_value in enumerate(ladder):
            stream = (
                bundle.streams["objective_anchor"]
                if lambda_index == 0
                else bundle.streams["objective_neural"]
            )
            child = (lambda_index,)
            stream_hash = _stream_hash(stream, *child)
            scaled = model.copy()
            scaled.weight_out *= lambda_value

            def one_chain(chain: int) -> np.ndarray:
                energies = np.empty(measurements, dtype=np.float64)
                rng = np.random.default_rng(
                    _child_sequence(stream, lambda_index, chain)
                )
                sampler = LinearNeuralBiasedMetropolis(
                    IsingLattice.random(length, rng),
                    couplings,
                    zero_bias,
                    scaled.copy(),
                    rng,
                    EVEN_SHAPES,
                    block_size=block_size,
                    compiled=True,
                    micro_basis=micro_basis,
                    block_basis=block_basis,
                )
                sampler.run_sweeps(max(1, thermal))
                for measurement in range(measurements):
                    sampler.run_sweeps(spacing)
                    energies[measurement] = model.energy(sampler.block_spins)
                sampler.assert_cache_consistent()
                return energies

            energies = np.stack(list(executor.map(one_chain, range(chains))))
            key = f"lambda_{lambda_index:02d}"
            arrays[key] = energies
            sample_hash = sha256_bytes(
                np.ascontiguousarray(energies).tobytes(order="C")
            )
            sets.append(ChainSet(energies, lambda_value, stream_hash, sample_hash))
            stream_hashes.append(stream_hash)

    target_stream = bundle.streams["objective_target"]
    target_stream_hash = _stream_hash(target_stream, 0)
    target = np.empty((chains, measurements), dtype=np.float64)
    for chain in range(chains):
        rng = np.random.default_rng(_child_sequence(target_stream, 0, chain))
        for measurement in range(measurements):
            spins = rng.choice(
                np.asarray([-1, 1], dtype=np.int8), size=(coarse, coarse)
            )
            target[chain, measurement] = model.energy(spins)
    arrays["target"] = target
    target_set = ChainSet(
        target,
        None,
        target_stream_hash,
        sha256_bytes(np.ascontiguousarray(target).tobytes(order="C")),
    )
    result = bridge_objective(sets[0], sets[1:], target_set, objective_protocol)
    atomic_write_npz(output / "objective_samples.npz", arrays)
    payload = {
        "estimator": "stratified_BAR",
        "common_zero_bias_anchor": True,
        "lambda_ladder": list(ladder),
        "chains": chains,
        "measurements_per_chain": measurements,
        "workers_per_bundle": worker_limit,
        "stream_hashes": [*stream_hashes, target_stream_hash],
        "result": _json_ready(asdict(result)),
    }
    atomic_write_json(output / "objective.json", payload)
    return payload


def _gauge_reference(
    model: D4EvenLocalMLP,
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    preset: str,
    length: int,
    output: Path,
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    if preset == "formal":
        configurations = protocol.gauge.configurations
        gauge_length = protocol.gauge.length
        stream = protocol.gauge.seed
    else:
        configurations = 8 if preset == "smoke" else 32
        gauge_length = length
        stream = bundle.streams["projection"]
    rng = np.random.default_rng(_child_sequence(stream, 900))
    spins = rng.choice(
        np.asarray([-1, 1], dtype=np.int8),
        size=(configurations, gauge_length, gauge_length),
    )
    atomic_write_npz(output / "gauge_reference.npz", {"spins": spins})
    raw_hash = sha256_bytes(np.ascontiguousarray(spins).tobytes(order="C"))
    record = {
        "shape": list(spins.shape),
        "dtype": "int8",
        "raw_array_sha256": raw_hash,
        "stream_hash": _stream_hash(stream, 900),
        "formal_reference": preset == "formal",
    }
    atomic_write_json(output / "gauge_reference.json", record)
    frozen = D4EvenLocalMLP.load(str(output / "bias_model.npz"))
    handoff = NeuralHamiltonian(frozen, spins[0])
    expected = -np.asarray([model.energy(state) for state in spins])
    observed = np.asarray([handoff.full_energy(state) for state in spins])
    difference = observed - expected
    difference -= difference.mean()
    handoff_record = {
        "relation": "U_next=-V_frozen",
        "gauge_reference_sha256": raw_hash,
        "additive_constant": float(np.mean(observed - expected)),
        "maximum_gauge_centered_residual": float(np.max(np.abs(difference))),
    }
    atomic_write_json(output / "handoff.json", handoff_record)
    return spins, record, handoff_record


def _save_checkpoint(
    output: Path,
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    training: TrainingProtocol,
    monitor: _OneRoundMonitor,
    gauge: np.ndarray,
    gauge_hash: str,
) -> dict[str, Any]:
    from scripts.neural_challenge import read_json

    model = D4EvenLocalMLP.load(str(output / "bias_model.npz"))
    config = read_json(output / "config.json")
    summary = read_json(output / "summary.json")
    bundle_record = _bundle_record(bundle)
    bundle_hash = sha256_bytes(canonical_json_bytes(bundle_record))
    update = int(config["steps"])
    polyak_count = max(0, update - training.polyak_start_update + 1)
    code_hash = current_code_sha256()
    checkpoint = NeuralCheckpoint(
        model=model,
        fixed_linear_bias=np.zeros(13, dtype=np.float64),
        update=update,
        schedule_state=asdict(training),
        polyak_state={
            "weight_in_sum": model.weight_in * polyak_count,
            "bias_hidden_sum": model.bias_hidden * polyak_count,
            "weight_out_sum": model.weight_out * polyak_count,
            "sample_count": np.asarray(polyak_count, dtype=np.int64),
        },
        rng_states={
            name: np.random.default_rng(_child_sequence(stream, 999)).bit_generator.state
            for name, stream in bundle.streams.items()
        },
        bundle_id=bundle.bundle_id,
        round_index=1,
        predecessor_manifest_sha256=None,
        protocol_sha256=protocol.protocol_sha256,
        code_sha256=code_hash,
        operator_basis_sha256=protocol.operator_basis_sha256,
        gauge_reference_sha256=gauge_hash,
        seed_bundle_sha256=bundle_hash,
        stop_state={
            "terminal_reason": summary["training_stop_reason"],
            "windows": monitor.windows,
        },
        metadata={
            "stage": "N2",
            "handoff": "U_next=-V_frozen",
            "initialization": "random",
            "initial_state_sha256": config["initial_state_sha256"],
        },
        gauge_energies=np.asarray([model.energy(spins) for spins in gauge]),
    )
    manifest = save_neural_checkpoint(output / "checkpoint", checkpoint)
    return {
        "code_sha256": code_hash,
        "seed_bundle_sha256": bundle_hash,
        "checkpoint_sha256": manifest["checkpoint_sha256"],
    }


def _output_paths(root: Path) -> tuple[str, ...]:
    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    )


def run_one_round(
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    preset: str,
    output: str | Path,
    *,
    pilot_config_path: str | Path = _PILOT_CONFIG,
    initial_spins: np.ndarray | None = None,
    backend: str | None = None,
    workers: int | None = None,
    local_compute_deviation: bool = False,
) -> dict[str, Any]:
    if preset not in ("smoke", "pilot", "formal"):
        raise ValueError(f"unknown N2 preset: {preset}")
    bundle_record = _bundle_record(bundle)
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite N2 output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent)
    )
    input_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.inputs-", dir=destination.parent)
    )
    started = time.perf_counter()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    try:
        length = 21 if preset == "smoke" else protocol.physical.length
        block_size = protocol.physical.block_size
        coarse = length // block_size
        training, objective_mapping, objective_protocol = _load_run_protocols(
            preset,
            Path(pilot_config_path),
            coarse * coarse,
        )
        fixed_map = input_root / "microscopic_map.json"
        _write_microscopic_map(fixed_map, protocol.physical.coupling)
        walkers = 2 if preset == "smoke" else (8 if preset == "pilot" else 16)
        actual_backend = backend or ("local" if preset == "smoke" else "slurm")
        if actual_backend not in ("local", "slurm"):
            raise ValueError(f"unknown N2 backend: {actual_backend}")
        worker_limit = resolve_worker_limit(workers, walkers)
        if initial_spins is None:
            initial_values = np.stack(
                [
                    np.random.default_rng(
                        _child_sequence(
                            bundle.streams["initial_condition"],
                            1,
                            walker,
                        )
                    ).choice(
                        np.asarray([-1, 1], dtype=np.int8),
                        size=(length, length),
                    )
                    for walker in range(walkers)
                ]
            )
        else:
            initial_values = np.asarray(initial_spins, dtype=np.int8)
            if initial_values.shape != (walkers, length, length):
                raise ValueError(
                    "N2 initial spins must match the frozen walker/lattice budget"
                )
            if not np.all((initial_values == -1) | (initial_values == 1)):
                raise ValueError("N2 initial spins must contain only -1 and +1")
        monitor = _OneRoundMonitor(
            length=length,
            block_size=block_size,
            coupling=protocol.physical.coupling,
            stream=bundle.streams["monitoring"],
            preset=preset,
        )
        from scripts.neural_challenge import project, read_json, train, validate

        train(
            staging,
            preset,
            fixed_map,
            model_seed=_integer_seed(bundle.streams["neural_training"], 0),
            optimizer_seed=_integer_seed(bundle.streams["neural_training"], 1),
            representation="pure",
            block_size=block_size,
            length_override=length,
            training_protocol=training,
            monitor_callback=monitor,
            initial_spins=initial_values,
            max_workers=worker_limit,
        )
        atomic_write_json(
            staging / "microscopic_map.json",
            json.loads(fixed_map.read_text(encoding="ascii")),
        )
        atomic_write_json(staging / "monitoring.json", {"windows": monitor.windows})
        validation = validate(
            staging,
            preset,
            seed=_integer_seed(bundle.streams["validation"], 0),
            enforce_formal_gate=False,
            max_workers=worker_limit,
        )
        projection_13 = project(
            staging,
            preset,
            seed=_integer_seed(bundle.streams["projection"], 0),
            enforce_formal_gate=False,
        )
        model = D4EvenLocalMLP.load(str(staging / "bias_model.npz"))
        candidates = _candidate_diagnostics(
            model,
            coarse,
            preset,
            bundle.streams["projection"],
        )
        atomic_write_json(staging / "candidate_26.json", candidates)
        objective = _measure_objective(
            model,
            length=length,
            block_size=block_size,
            coupling=protocol.physical.coupling,
            bundle=bundle,
            objective_mapping=objective_mapping,
            objective_protocol=objective_protocol,
            output=staging,
            workers=worker_limit,
        )
        gauge, gauge_record, handoff = _gauge_reference(
            model,
            protocol,
            bundle,
            preset,
            length,
            staging,
        )
        checkpoint = _save_checkpoint(
            staging,
            protocol,
            bundle,
            training,
            monitor,
            gauge,
            str(gauge_record["raw_array_sha256"]),
        )
        config = read_json(staging / "config.json")
        summary = read_json(staging / "summary.json")
        bias = np.asarray(config["fixed_linear_bias"], dtype=np.float64)
        if bias.shape != (13,) or not np.array_equal(bias, np.zeros(13)):
            raise AssertionError("N2 pure-neural 13-operator branch changed")
        objective_result = objective["result"]
        objective_upper = None
        if objective_result["objective_per_site"] is not None:
            error = objective_result["standard_error_per_site"]
            objective_upper = float(
                objective_result["objective_per_site"]
                + (0.0 if error is None else 2.0 * error)
            )
        correctness_pass = bool(
            handoff["maximum_gauge_centered_residual"] <= 1e-10
            and np.all(np.isfinite(_flatten_parameters(model)))
        )
        scientific_pass = bool(
            summary["training_stop_reason"] == "CONVERGED"
            and validation["status"] == "PASS"
            and objective_result["classification"] == IDENTIFIABLE
            and objective_upper is not None
            and objective_upper < 0.0
        )
        if not correctness_pass:
            classification = "CORRECTNESS_FAILURE"
            reason = "N2_CORRECTNESS_GATE_FAILED"
        elif preset == "formal" and scientific_pass:
            classification = "EASY_GOAL_SUCCESS"
            reason = "N2_FORMAL_CERTIFIED"
        else:
            classification = "SCIENTIFIC_NEGATIVE"
            reason = (
                "SMOKE_STATISTICALLY_INSUFFICIENT"
                if preset == "smoke"
                else ("PILOT_NOT_FORMAL" if preset == "pilot" else "N2_GATES_NOT_MET")
            )
        elapsed = time.perf_counter() - started
        proposals = int(config["total_walker_sweeps"] * length * length)
        resources = {
            "elapsed_seconds": elapsed,
            "peak_rss_kib": int(
                max(rss_before, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            ),
            "threads": int(config.get("workers", worker_limit)),
            "workers_per_bundle": worker_limit,
            "backend": actual_backend,
            "execution_policy": (
                "LOCAL_COMPUTE_DEVIATION"
                if actual_backend == "local" and local_compute_deviation
                else ("LOCAL_TEST" if actual_backend == "local" else "SLURM")
            ),
            "proposals": proposals,
            "proposals_per_second": float(proposals / elapsed),
            "sweeps_per_second": float(config["total_walker_sweeps"] / elapsed),
            "checkpoint_bytes": int(
                sum(
                    path.stat().st_size
                    for path in (staging / "checkpoint").rglob("*")
                    if path.is_file()
                )
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
        if actual_backend == "local":
            resources["max_parallel_bundles"] = 2
            resources["host"] = local_host_provenance(
                workers_per_bundle=worker_limit,
                max_parallel_bundles=2,
            )
        atomic_write_json(staging / "resources.json", resources)
        stage_setup = {
            "length": length,
            "coupling": protocol.physical.coupling,
            "block_size": block_size,
            "coarse_length": coarse,
            "boundary": protocol.physical.boundary,
            "rg_transform": "majority_rule",
        }
        report = {
            "schema_version": 1,
            "stage": "N2",
            "preset": preset,
            "bundle_id": bundle.bundle_id,
            "classification": classification,
            "reason": reason,
            "stage_setup": stage_setup,
            "model": {
                "architecture": protocol.neural.architecture,
                "radius": model.radius,
                "hidden": model.hidden,
                "feature_mode": model.feature_mode,
            },
            "fixed_linear_bias": bias.tolist(),
            "fixed_linear_bias_linf": float(np.max(np.abs(bias))),
            "initial_state_sha256": config["initial_state_sha256"],
            "training_stop_reason": summary["training_stop_reason"],
            "validation": validation,
            "projection_13": projection_13,
            "candidate_26": candidates,
            "objective": {**objective, "objective_upper_per_site": objective_upper},
            "handoff": handoff,
            "resources": resources,
            "seed_bundle": bundle_record,
            "gauge_reference_sha256": gauge_record["raw_array_sha256"],
            **checkpoint,
        }
        atomic_write_json(staging / "one_round_report.json", report)
        manifest = create_stage_manifest(
            stage="N2",
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
            scientific_gates={
                "training": summary["training_stop_reason"],
                "frozen_validation": validation["status"],
                "objective": objective_result["classification"],
                "objective_improvement": (
                    "PASS"
                    if objective_upper is not None and objective_upper < 0.0
                    else "FAIL"
                ),
            },
            resources=resources,
            bundle_id=bundle.bundle_id,
            round_index=1,
            code_sha256=checkpoint["code_sha256"],
            gauge_reference_sha256=str(gauge_record["raw_array_sha256"]),
        )
        manifest["scope"] = "N2_STAGE_ONLY"
        manifest["stage_setup"] = stage_setup
        atomic_write_json(staging / "manifest.json", manifest)
        report["manifest"] = manifest
        os.replace(staging, destination)
        shutil.rmtree(input_root)
        return report
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        if input_root.exists():
            shutil.rmtree(input_root)
        raise
