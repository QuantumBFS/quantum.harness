"""N1 random-start identity-RG certification for Issue #28."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any

import numpy as np

from .artifacts import (
    atomic_write_json,
    atomic_write_npz,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from .issue28_protocol import Issue28Protocol
from .issue28_workflow import create_stage_manifest, current_code_sha256
from .neural_checkpoint import NeuralCheckpoint, save_neural_checkpoint
from .neural_energy import D4EvenLocalMLP
from .operators import EVEN_SHAPES, OperatorBasis
from .training_protocol import TrainingProtocol, TrainingWindow, load_training_protocol


_ROOT = Path(__file__).resolve().parents[2]
_PILOT_CONFIG = _ROOT / "config" / "issue28_pilot_v1.json"
_STREAM_ROLES = (
    "model",
    "optimizer",
    "monitoring",
    "validation",
    "projection",
    "diagnostic",
    "gauge",
)
_IDENTITY_ENTROPIES = {
    "smoke": (2026285100,),
    "pilot": (2026285200,),
    "formal": (2026285301, 2026285302, 2026285303),
}


def identity_seed_records(preset: str) -> list[dict[str, Any]]:
    if preset not in _IDENTITY_ENTROPIES:
        raise ValueError(f"unknown N1 preset: {preset}")
    prefix = "identity-formal" if preset == "formal" else f"identity-{preset}"
    records = []
    for bundle_index, entropy in enumerate(_IDENTITY_ENTROPIES[preset], start=1):
        bundle_id = f"{prefix}-{bundle_index}" if preset == "formal" else prefix
        records.append(
            {
                "bundle_id": bundle_id,
                "streams": {
                    role: {"entropy": entropy, "spawn_key": [stream_index]}
                    for stream_index, role in enumerate(_STREAM_ROLES)
                },
            }
        )
    return records


def _stream_seed(record: dict[str, Any], role: str) -> int:
    value = record["streams"][role]
    sequence = np.random.SeedSequence(
        int(value["entropy"]),
        spawn_key=tuple(int(item) for item in value["spawn_key"]),
    )
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


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


def _training_protocol(preset: str, config_path: Path) -> TrainingProtocol:
    if preset == "smoke":
        return _smoke_training_protocol()
    value = json.loads(config_path.read_text(encoding="ascii"))
    if value.get("protocol") != "issue28_nonformal_pilot_v1":
        raise ValueError("unexpected Issue #28 pilot protocol")
    return load_training_protocol(dict(value["training"]))


def _flatten_parameters(model: D4EvenLocalMLP) -> np.ndarray:
    return np.concatenate(
        (model.weight_in.ravel(), model.bias_hidden.ravel(), model.weight_out.ravel())
    )


def _log_mean_exp(values: np.ndarray) -> float:
    maximum = float(np.max(values))
    return maximum + float(np.log(np.mean(np.exp(values - maximum))))


class _IdentityHeldOutMonitor:
    def __init__(
        self,
        length: int,
        couplings: np.ndarray,
        seed: int,
        configurations: int,
    ) -> None:
        from scripts.neural_challenge import patch_histogram

        self._patch_histogram = patch_histogram
        self.length = int(length)
        self.n_sites = self.length * self.length
        self.basis = OperatorBasis(self.length, EVEN_SHAPES)
        rng = np.random.default_rng(seed)
        self.spins = rng.choice(
            np.asarray([-1, 1], dtype=np.int8),
            size=(configurations, self.length, self.length),
        )
        self.operator_density = np.stack(
            [self.basis.values(spins) / self.n_sites for spins in self.spins]
        )
        self.hamiltonian = self.operator_density @ np.asarray(couplings) * self.n_sites
        self.target_patch = np.mean(
            [self._patch_histogram(spins) / self.n_sites for spins in self.spins],
            axis=0,
        )
        self.previous_objective: float | None = None
        self.previous_parameters: np.ndarray | None = None
        self.windows: list[dict[str, Any]] = []

    def __call__(
        self,
        update: int,
        model: D4EvenLocalMLP,
        record: Any,
        polyak_fraction: float,
    ) -> TrainingWindow:
        neural = np.asarray([model.energy(spins) for spins in self.spins])
        effective = self.hamiltonian + neural
        shifted = -effective - float(np.max(-effective))
        weights = np.exp(shifted)
        weights /= float(weights.sum())
        biased_operator = weights @ self.operator_density
        target_operator = self.operator_density.mean(axis=0)
        operator_equivalence = float(
            np.max(np.abs(biased_operator - target_operator))
        )
        biased_patch = np.zeros(512, dtype=np.float64)
        for weight, spins in zip(weights, self.spins):
            biased_patch += weight * self._patch_histogram(spins) / self.n_sites
        patch_tv = float(0.5 * np.sum(np.abs(biased_patch - self.target_patch)))
        objective = float(
            (
                _log_mean_exp(-effective)
                - _log_mean_exp(-self.hamiltonian)
                + float(np.mean(neural))
            )
            / self.n_sites
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
        self.windows.append(asdict(window))
        return window


def _identity_map(path: Path, coupling: float) -> None:
    couplings = [float(coupling), *([0.0] * 12)]
    atomic_write_json(
        path,
        {
            "schema_version": 1,
            "stage": "N1",
            "operator_names": [shape.name for shape in EVEN_SHAPES],
            "input_couplings": couplings,
            "final_renormalized_couplings": couplings,
            "exact_relation": "block_size=1_implies_H_prime_equals_H",
        },
    )


def _save_final_checkpoint(
    root: Path,
    protocol: Issue28Protocol,
    seed_record: dict[str, Any],
    training: TrainingProtocol,
    monitor: _IdentityHeldOutMonitor,
) -> dict[str, Any]:
    from scripts.neural_challenge import read_json

    model = D4EvenLocalMLP.load(str(root / "bias_model.npz"))
    config = read_json(root / "config.json")
    summary = read_json(root / "summary.json")
    gauge_rng = np.random.default_rng(_stream_seed(seed_record, "gauge"))
    gauge = gauge_rng.choice(
        np.asarray([-1, 1], dtype=np.int8),
        size=(8, int(config["length"]), int(config["length"])),
    )
    gauge_path = root / "gauge_reference.npz"
    atomic_write_npz(gauge_path, {"spins": gauge})
    gauge_hash = sha256_bytes(np.ascontiguousarray(gauge).tobytes(order="C"))
    atomic_write_json(
        root / "gauge_reference.json",
        {
            "shape": list(gauge.shape),
            "dtype": "int8",
            "raw_array_sha256": gauge_hash,
            "archive_sha256": sha256_file(gauge_path),
            "stream": seed_record["streams"]["gauge"],
        },
    )
    seed_hash = sha256_bytes(canonical_json_bytes(seed_record))
    code_hash = current_code_sha256()
    update = int(config["steps"])
    polyak_count = max(0, update - training.polyak_start_update + 1)
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
            role: np.random.default_rng(_stream_seed(seed_record, role)).bit_generator.state
            for role in _STREAM_ROLES
        },
        bundle_id=str(seed_record["bundle_id"]),
        round_index=1,
        predecessor_manifest_sha256=None,
        protocol_sha256=protocol.protocol_sha256,
        code_sha256=code_hash,
        operator_basis_sha256=protocol.operator_basis_sha256,
        gauge_reference_sha256=gauge_hash,
        seed_bundle_sha256=seed_hash,
        stop_state={
            "terminal_reason": summary["training_stop_reason"],
            "windows": monitor.windows,
        },
        metadata={
            "stage": "N1",
            "initialization": "random",
            "supervised_checkpoint": None,
        },
        gauge_energies=np.asarray([model.energy(spins) for spins in gauge]),
    )
    checkpoint_manifest = save_neural_checkpoint(root / "checkpoint", checkpoint)
    return {
        "code_sha256": code_hash,
        "gauge_reference_sha256": gauge_hash,
        "seed_bundle_sha256": seed_hash,
        "checkpoint_sha256": checkpoint_manifest["checkpoint_sha256"],
    }


def _run_seed(
    root: Path,
    protocol: Issue28Protocol,
    preset: str,
    seed_record: dict[str, Any],
    training: TrainingProtocol,
    fixed_map: Path,
) -> dict[str, Any]:
    from scripts.neural_challenge import project, read_json, train, validate
    from scripts.neural_identity_gradient_diagnostic import run as run_gradient_diagnostic

    monitor = _IdentityHeldOutMonitor(
        length=15,
        couplings=np.asarray([protocol.physical.coupling, *([0.0] * 12)]),
        seed=_stream_seed(seed_record, "monitoring"),
        configurations=(8 if preset == "smoke" else 32),
    )
    train(
        root,
        preset,
        fixed_map,
        model_seed=_stream_seed(seed_record, "model"),
        optimizer_seed=_stream_seed(seed_record, "optimizer"),
        representation="pure",
        block_size=1,
        length_override=15,
        training_protocol=training,
        monitor_callback=monitor,
    )
    atomic_write_json(root / "monitoring.json", {"windows": monitor.windows})
    validation = validate(
        root,
        preset,
        seed=_stream_seed(seed_record, "validation"),
        enforce_formal_gate=False,
    )
    projection = project(
        root,
        preset,
        seed=_stream_seed(seed_record, "projection"),
        enforce_formal_gate=False,
    )
    diagnostic: dict[str, Any] | None = None
    if projection["status"] != "PASS":
        diagnostic = run_gradient_diagnostic(
            preset=preset,
            output=root / "gradient_diagnostic",
            model_path=root / "bias_model.npz",
            fixed_point_map=fixed_map,
            seed=_stream_seed(seed_record, "diagnostic"),
        )
    config = read_json(root / "config.json")
    summary = read_json(root / "summary.json")
    bias = np.asarray(config["fixed_linear_bias"], dtype=np.float64)
    if bias.shape != (13,) or not np.array_equal(bias, np.zeros(13)):
        raise AssertionError("N1 pure-neural linear branch changed from exact zero")
    checkpoint = _save_final_checkpoint(root, protocol, seed_record, training, monitor)
    scientific_pass = bool(
        summary["training_stop_reason"] == "CONVERGED"
        and validation["status"] == "PASS"
        and projection["status"] == "PASS"
    )
    return {
        "bundle_id": seed_record["bundle_id"],
        "initialization": "random",
        "supervised_checkpoint": None,
        "fixed_linear_bias": bias.tolist(),
        "fixed_linear_bias_linf": float(np.max(np.abs(bias))),
        "model": {
            "architecture": "D4EvenLocalMLP",
            "radius": int(config["neural_radius"]),
            "hidden": int(config["hidden"]),
            "feature_mode": config["neural_feature_mode"],
        },
        "training_stop_reason": summary["training_stop_reason"],
        "training_updates": int(config["steps"]),
        "validation": validation,
        "projection": projection,
        "gradient_diagnostic": diagnostic,
        "scientific_pass": scientific_pass,
        "seed_record": seed_record,
        **checkpoint,
    }


def _all_output_paths(root: Path) -> tuple[str, ...]:
    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    )


def classify_identity_results(
    preset: str,
    results: list[dict[str, Any]],
) -> tuple[str, str]:
    if not results:
        raise ValueError("N1 classification requires at least one seed result")
    diagnoses = {
        item.get("gradient_diagnostic", {}).get("diagnosis")
        for item in results
        if item.get("gradient_diagnostic") is not None
    }
    if "SAMPLER_OR_GRADIENT_ESTIMATOR_MISMATCH" in diagnoses:
        return "CORRECTNESS_FAILURE", "N1_GRADIENT_ESTIMATOR_MISMATCH"
    if preset == "formal" and all(bool(item["scientific_pass"]) for item in results):
        return "EASY_GOAL_SUCCESS", "N1_FORMAL_CERTIFIED"
    if preset == "smoke":
        return "SCIENTIFIC_NEGATIVE", "SMOKE_STATISTICALLY_INSUFFICIENT"
    if preset == "pilot":
        return "SCIENTIFIC_NEGATIVE", "PILOT_NOT_FORMAL"
    return "SCIENTIFIC_NEGATIVE", "N1_FORMAL_GATES_NOT_MET"


def run_identity_certification(
    protocol: Issue28Protocol,
    preset: str,
    output: str | Path,
    *,
    resume: bool = False,
    pilot_config_path: str | Path = _PILOT_CONFIG,
) -> dict[str, Any]:
    """Run N1 without ever accepting a supervised initialization."""
    if preset not in ("smoke", "pilot", "formal"):
        raise ValueError(f"unknown N1 preset: {preset}")
    destination = Path(output)
    if destination.exists():
        if resume and (destination / "manifest.json").is_file():
            from .issue28_workflow import read_verified_stage_manifest

            read_verified_stage_manifest(
                destination / "manifest.json", protocol, expected_stage="N1"
            )
            return json.loads(
                (destination / "identity_report.json").read_text(encoding="ascii")
            )
        raise FileExistsError(f"refusing to overwrite N1 output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent)
    )
    started = time.perf_counter()
    try:
        fixed_map = staging / "identity_fixed_map.json"
        _identity_map(fixed_map, protocol.physical.coupling)
        training = _training_protocol(preset, Path(pilot_config_path))
        seed_records = identity_seed_records(preset)
        results = [
            _run_seed(
                staging / str(seed_record["bundle_id"]),
                protocol,
                preset,
                seed_record,
                training,
                fixed_map,
            )
            for seed_record in seed_records
        ]
        formal = preset == "formal"
        classification, reason = classify_identity_results(preset, results)
        elapsed = time.perf_counter() - started
        report = {
            "schema_version": 1,
            "stage": "N1",
            "scope": "RANDOM_START_IDENTITY_RG_CERTIFICATION",
            "preset": preset,
            "classification": classification,
            "reason": reason,
            "initialization": "random",
            "supervised_checkpoint": None,
            "exact_relation": "U_next=-V_frozen_and_H_prime_equals_H",
            "stage_setup": {
                "length": 15,
                "coupling": protocol.physical.coupling,
                "block_size": 1,
                "boundary": "periodic",
                "rg_transform": "identity",
                "target_distribution": "uniform_independent_ising_2d",
            },
            "formal_seed_count": 3 if formal else 0,
            "fixed_linear_bias_linf": max(
                float(item["fixed_linear_bias_linf"]) for item in results
            ),
            "training_protocol": asdict(training),
            "seed_results": results,
            "elapsed_seconds": elapsed,
        }
        atomic_write_json(staging / "identity_report.json", report)
        correctness_gates = {
            "random_initialization": "PASS",
            "no_supervised_checkpoint": "PASS",
            "pure_linear_branch_exact_zero": (
                "PASS" if report["fixed_linear_bias_linf"] == 0.0 else "FAIL"
            ),
            "checkpoints": "PASS",
        }
        scientific_gates = {
            item["bundle_id"]: "PASS" if item["scientific_pass"] else "FAIL"
            for item in results
        }
        manifest = create_stage_manifest(
            stage="N1",
            protocol=protocol,
            classification=classification,
            reason=reason,
            output_root=staging,
            outputs=_all_output_paths(staging),
            correctness_gates=correctness_gates,
            scientific_gates=scientific_gates,
            resources={
                "backend": "local" if preset == "smoke" else "slurm_required",
                "elapsed_seconds": elapsed,
                "threads": int(os.environ.get("OMP_NUM_THREADS", "1")),
            },
            code_sha256=current_code_sha256(),
        )
        manifest["scope"] = "N1_STAGE_ONLY"
        manifest["stage_setup"] = report["stage_setup"]
        manifest["formal_seed_count"] = report["formal_seed_count"]
        atomic_write_json(staging / "manifest.json", manifest)
        os.replace(staging, destination)
        return report
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
