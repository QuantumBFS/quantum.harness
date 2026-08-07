"""Fail-closed Stage 4 regression adapter for the existing two-dimensional MPS."""

from __future__ import annotations

from collections.abc import Mapping
import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from types import MappingProxyType
from typing import Any

import numpy as np

from vmcrg_ref.artifacts import (
    atomic_write_json,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from vmcrg_ref.blockspin import block_majority
from vmcrg_ref.checkpoint import load_mps_checkpoint, save_mps_checkpoint
from vmcrg_ref.ising import IsingLattice
from vmcrg_ref.mps_patch import PatchMPS
from vmcrg_ref.mps_sampler import MPSBiasedMetropolis
from vmcrg_ref.mps_vmcrg import MPSVMCRGOptimizer
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis
from vmcrg_ref.patch_table import PatchEnergyCache, PatchLookupTable, enumerate_patches

from .config import load_design
from .backend import BackendCase, NumpyReferenceBackend
from .bias import BiasRoute, LocalBiasCache, OverlapBias
from .exact import enumerate_l2, transfer_l3
from .equilibration import RoundTripTracker
from .linear_bias import LinearFeatureBasis
from .model import EABonds, energy
from .rg import MajorityRG3D, block_majority_3d
from .symmetry import cubic_transforms
from .templates import TemplateEncoder
from .tempering import (
    BiasedPairLadder,
    SingleReplicaLadder,
    TemperatureGrid,
    UnbiasedOverlapPT,
    enumerate_l2_pt_transition,
)
from .tensor_train import LocalTensorTrain, SymmetricLocalTT


TRACK_ROOT = Path(__file__).resolve().parents[2]
STAGE = "stage4"
STAGE5 = "stage5"
STAGE6 = "stage6"
PASS = "PASS"
CORRECTNESS_FAILURE = "CORRECTNESS_FAILURE"
SCIENTIFIC_NEGATIVE = "SCIENTIFIC_NEGATIVE"
GRADIENT_TOLERANCE = 2e-6
CANONICAL_TOLERANCE = 1e-12
DELTA_TOLERANCE = 1e-10
REGRESSION_STATEMENT = (
    "This two-dimensional MPS/VMCRG regression is not 3D Hard Goal evidence."
)

STAGE6_TRUSTED_SOURCE_PATHS = (
    "jobs/hard_goal_pilot.slurm",
    "jobs/hard_goal_science_pilot.slurm",
    "scripts/hard_goal_freeze_protocol.py",
    "scripts/hard_goal_pilot_cell.py",
    "scripts/hard_goal_science_pilot_cell.py",
    "src/spinglass3d/backend.py",
    "src/spinglass3d/config.py",
    "src/spinglass3d/equilibration.py",
    "src/spinglass3d/gauge.py",
    "src/spinglass3d/jax_backend.py",
    "src/spinglass3d/model.py",
    "src/spinglass3d/pilot.py",
    "src/spinglass3d/rg.py",
    "src/spinglass3d/science_pilot.py",
    "src/spinglass3d/symmetry.py",
    "src/spinglass3d/templates.py",
    "src/spinglass3d/tensor_train.py",
    "src/spinglass3d/workflow.py",
    "src/vmcrg_ref/artifacts.py",
)

_EXACT_CHECKS_SHA256 = (
    "6324ee957319d1682bc24ca957d38f979026183e8559fcb75200f21a852ca9b7"
)
_SOURCE_RELATIVE_PATHS = (
    "config/hard_goal/design_v1.toml",
    "results/mps_challenge/exact_checks.json",
    "src/spinglass3d/config.py",
    "src/spinglass3d/workflow.py",
    "src/vmcrg_ref/mps_patch.py",
    "src/vmcrg_ref/mps_sampler.py",
    "src/vmcrg_ref/mps_vmcrg.py",
    "src/vmcrg_ref/checkpoint.py",
    "scripts/hard_goal.py",
)


@dataclass(frozen=True)
class StageManifest:
    """Immutable public projection of a completed Stage 4 manifest."""

    stage: str
    classification: str
    failed_gates: tuple[str, ...]
    artifacts: Mapping[str, str]
    hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.stage not in {STAGE, STAGE5}:
            raise ValueError(f"unsupported stage: {self.stage!r}")
        if self.classification not in {
            PASS,
            CORRECTNESS_FAILURE,
            SCIENTIFIC_NEGATIVE,
        }:
            raise ValueError(f"unsupported classification: {self.classification!r}")
        failed = tuple(str(value) for value in self.failed_gates)
        if len(set(failed)) != len(failed):
            raise ValueError("failed gates must be unique")
        artifact_values = {str(key): str(value) for key, value in self.artifacts.items()}
        hash_values = {str(key): str(value) for key, value in self.hashes.items()}
        for name, digest in hash_values.items():
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError(f"invalid SHA-256 for {name!r}")
        object.__setattr__(self, "failed_gates", failed)
        object.__setattr__(self, "artifacts", MappingProxyType(artifact_values))
        object.__setattr__(self, "hashes", MappingProxyType(hash_values))

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "classification": self.classification,
            "failed_gates": list(self.failed_gates),
            "artifacts": dict(self.artifacts),
            "hashes": dict(self.hashes),
        }


@dataclass(frozen=True)
class _Stage4Config:
    source: Path
    design: Path
    exact_checks: Path
    exact_checks_sha256: str
    tests_glob: str
    gradient_epsilon: float
    local_delta_trials: int
    length: int
    coupling: float
    block_size: int
    rg_levels: int
    operator_count: int
    chi: int
    symmetrize: bool
    walkers: int
    optimizer_steps: int
    sweeps_per_step: int
    thermalization_sweeps: int
    frozen_measurement_sweeps: int
    measurement_thinning: int
    initial_alpha: float
    alpha_learning_rate: float
    core_learning_rate: float
    linear_learning_rate: float
    gradient_clip: float
    canonicalize_every: int
    cache_check_every: int
    compiled: bool
    parallel_walkers: bool
    seed: int

    def public_parameters(self) -> dict[str, object]:
        return {
            "dimensions": 2,
            "length": self.length,
            "block_size": self.block_size,
            "rg_levels": self.rg_levels,
            "coupling": self.coupling,
            "operator_count": self.operator_count,
            "chi": self.chi,
            "walkers": self.walkers,
            "optimizer_steps": self.optimizer_steps,
            "sweeps_per_step": self.sweeps_per_step,
            "thermalization_sweeps": self.thermalization_sweeps,
            "frozen_measurement_sweeps": self.frozen_measurement_sweeps,
            "measurement_thinning": self.measurement_thinning,
            "seed": self.seed,
        }


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], section: str
) -> None:
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise ValueError(f"missing keys in {section}: {sorted(missing)!r}")
    if unknown:
        raise ValueError(f"unknown keys in {section}: {sorted(unknown)!r}")


def _table(raw: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"missing or invalid [{key}] section")
    return value


def _finite_float(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _integer(value: object, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _string(value: object, name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be a string")
    return value


def _resolve_fixed_source(value: object, expected: str, name: str) -> Path:
    supplied = _string(value, name)
    if supplied != expected:
        raise ValueError(f"{name} must be {expected!r}")
    return TRACK_ROOT / supplied


def _expect_equal(actual: object, expected: object, name: str) -> None:
    if actual != expected:
        raise ValueError(f"{name} must be {expected!r}, got {actual!r}")


def _load_stage4_config(path: str | Path) -> _Stage4Config:
    source = Path(path).resolve()
    with source.open("rb") as handle:
        raw = tomllib.load(handle)
    _require_exact_keys(
        raw,
        {
            "schema_version",
            "stage",
            "classification_scope",
            "regression_only",
            "three_dimensional_hard_goal_evidence",
            "statement",
            "sources",
            "tolerances",
            "probes",
            "cell",
        },
        "top level",
    )
    _expect_equal(raw["schema_version"], 1, "schema_version")
    _expect_equal(raw["stage"], STAGE, "stage")
    _expect_equal(
        raw["classification_scope"],
        "two_dimensional_mps_regression",
        "classification_scope",
    )
    _expect_equal(raw["regression_only"], True, "regression_only")
    _expect_equal(
        raw["three_dimensional_hard_goal_evidence"],
        False,
        "three_dimensional_hard_goal_evidence",
    )
    _expect_equal(raw["statement"], REGRESSION_STATEMENT, "statement")

    sources = _table(raw, "sources")
    tolerances = _table(raw, "tolerances")
    probes = _table(raw, "probes")
    cell = _table(raw, "cell")
    _require_exact_keys(
        sources,
        {"hard_goal_design", "exact_checks", "exact_checks_sha256", "tests_glob"},
        "sources",
    )
    _require_exact_keys(
        tolerances,
        {"gradient_error", "canonical_error", "local_delta_error"},
        "tolerances",
    )
    _require_exact_keys(
        probes, {"gradient_epsilon", "local_delta_trials"}, "probes"
    )
    cell_keys = {
        "dimensions",
        "length",
        "block_size",
        "rg_levels",
        "coupling",
        "operator_count",
        "chi",
        "symmetrize",
        "walkers",
        "optimizer_steps",
        "sweeps_per_step",
        "thermalization_sweeps",
        "frozen_measurement_sweeps",
        "measurement_thinning",
        "initial_alpha",
        "alpha_learning_rate",
        "core_learning_rate",
        "linear_learning_rate",
        "gradient_clip",
        "canonicalize_every",
        "cache_check_every",
        "compiled",
        "parallel_walkers",
        "seed",
    }
    _require_exact_keys(cell, cell_keys, "cell")

    exact_hash = _string(sources["exact_checks_sha256"], "exact_checks_sha256")
    tests_glob = _string(sources["tests_glob"], "tests_glob")
    _expect_equal(exact_hash, _EXACT_CHECKS_SHA256, "exact_checks_sha256")
    _expect_equal(tests_glob, "tests/*mps*.py", "tests_glob")
    _expect_equal(
        _finite_float(tolerances["gradient_error"], "gradient_error"),
        GRADIENT_TOLERANCE,
        "gradient_error",
    )
    _expect_equal(
        _finite_float(tolerances["canonical_error"], "canonical_error"),
        CANONICAL_TOLERANCE,
        "canonical_error",
    )
    _expect_equal(
        _finite_float(tolerances["local_delta_error"], "local_delta_error"),
        DELTA_TOLERANCE,
        "local_delta_error",
    )

    exact_values: dict[str, object] = {
        "dimensions": 2,
        "length": 45,
        "block_size": 3,
        "rg_levels": 1,
        "coupling": 0.436,
        "operator_count": 13,
        "chi": 2,
        "symmetrize": True,
        "walkers": 4,
        "optimizer_steps": 8,
        "sweeps_per_step": 2,
        "thermalization_sweeps": 8,
        "frozen_measurement_sweeps": 16,
        "measurement_thinning": 1,
        "compiled": True,
        "parallel_walkers": False,
    }
    for name, expected in exact_values.items():
        _expect_equal(cell[name], expected, f"cell.{name}")
    _expect_equal(
        _integer(probes["local_delta_trials"], "local_delta_trials"),
        100,
        "local_delta_trials",
    )
    gradient_epsilon = _finite_float(
        probes["gradient_epsilon"], "gradient_epsilon"
    )
    if gradient_epsilon <= 0.0:
        raise ValueError("gradient_epsilon must be positive")

    float_names = (
        "coupling",
        "initial_alpha",
        "alpha_learning_rate",
        "core_learning_rate",
        "linear_learning_rate",
        "gradient_clip",
    )
    float_values = {
        name: _finite_float(cell[name], f"cell.{name}") for name in float_names
    }
    if float_values["alpha_learning_rate"] <= 0.0:
        raise ValueError("cell.alpha_learning_rate must be positive")
    if float_values["core_learning_rate"] <= 0.0:
        raise ValueError("cell.core_learning_rate must be positive")
    if float_values["linear_learning_rate"] < 0.0:
        raise ValueError("cell.linear_learning_rate cannot be negative")
    if float_values["gradient_clip"] <= 0.0:
        raise ValueError("cell.gradient_clip must be positive")

    return _Stage4Config(
        source=source,
        design=_resolve_fixed_source(
            sources["hard_goal_design"],
            "config/hard_goal/design_v1.toml",
            "hard_goal_design",
        ),
        exact_checks=_resolve_fixed_source(
            sources["exact_checks"],
            "results/mps_challenge/exact_checks.json",
            "exact_checks",
        ),
        exact_checks_sha256=exact_hash,
        tests_glob=tests_glob,
        gradient_epsilon=gradient_epsilon,
        local_delta_trials=_integer(
            probes["local_delta_trials"], "local_delta_trials"
        ),
        length=_integer(cell["length"], "cell.length"),
        coupling=float_values["coupling"],
        block_size=_integer(cell["block_size"], "cell.block_size"),
        rg_levels=_integer(cell["rg_levels"], "cell.rg_levels"),
        operator_count=_integer(cell["operator_count"], "cell.operator_count"),
        chi=_integer(cell["chi"], "cell.chi"),
        symmetrize=_boolean(cell["symmetrize"], "cell.symmetrize"),
        walkers=_integer(cell["walkers"], "cell.walkers"),
        optimizer_steps=_integer(cell["optimizer_steps"], "cell.optimizer_steps"),
        sweeps_per_step=_integer(cell["sweeps_per_step"], "cell.sweeps_per_step"),
        thermalization_sweeps=_integer(
            cell["thermalization_sweeps"], "cell.thermalization_sweeps"
        ),
        frozen_measurement_sweeps=_integer(
            cell["frozen_measurement_sweeps"],
            "cell.frozen_measurement_sweeps",
        ),
        measurement_thinning=_integer(
            cell["measurement_thinning"], "cell.measurement_thinning"
        ),
        initial_alpha=float_values["initial_alpha"],
        alpha_learning_rate=float_values["alpha_learning_rate"],
        core_learning_rate=float_values["core_learning_rate"],
        linear_learning_rate=float_values["linear_learning_rate"],
        gradient_clip=float_values["gradient_clip"],
        canonicalize_every=_integer(
            cell["canonicalize_every"], "cell.canonicalize_every"
        ),
        cache_check_every=_integer(
            cell["cache_check_every"], "cell.cache_check_every"
        ),
        compiled=_boolean(cell["compiled"], "cell.compiled"),
        parallel_walkers=_boolean(
            cell["parallel_walkers"], "cell.parallel_walkers"
        ),
        seed=_integer(cell["seed"], "cell.seed"),
    )


def classify_stage4(
    *,
    gradient_error: float,
    canonical_error: float,
    delta_error: float,
    checkpoint_equal: bool,
) -> dict[str, object]:
    """Classify the four numerical contracts, treating NaN and Inf as failures."""

    failed: list[str] = []
    if not math.isfinite(float(gradient_error)) or gradient_error > GRADIENT_TOLERANCE:
        failed.append("gradient_error")
    if not math.isfinite(float(canonical_error)) or canonical_error > CANONICAL_TOLERANCE:
        failed.append("canonicalization")
    if not math.isfinite(float(delta_error)) or delta_error > DELTA_TOLERANCE:
        failed.append("incremental_delta")
    if not checkpoint_equal:
        failed.append("checkpoint")
    return {
        "classification": PASS if not failed else CORRECTNESS_FAILURE,
        "failed_gates": failed,
    }


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(TRACK_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _all_finite(value: object) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if type(value) in (int, float):
        return math.isfinite(float(value))
    if isinstance(value, Mapping):
        return all(_all_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_all_finite(item) for item in value)
    return True


def _json_safe(value: object) -> object:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    raise TypeError(f"value is not JSON serializable: {type(value).__name__}")


def _source_paths(config: _Stage4Config, tests: tuple[Path, ...]) -> dict[str, Path]:
    paths = {relative: TRACK_ROOT / relative for relative in _SOURCE_RELATIVE_PATHS}
    paths["stage4_config"] = config.source
    for test in tests:
        paths[_display_path(test)] = test
    return dict(sorted(paths.items()))


def _hash_sources(paths: Mapping[str, Path]) -> tuple[dict[str, str], list[str]]:
    hashes: dict[str, str] = {}
    failures: list[str] = []
    for label, path in paths.items():
        if not path.is_file():
            failures.append(f"missing:{label}")
            continue
        try:
            hashes[label] = sha256_file(path)
        except OSError as error:
            failures.append(f"unreadable:{label}:{error}")
    return hashes, failures


def _validate_reference(config: _Stage4Config) -> dict[str, object]:
    result: dict[str, object] = {
        "path": _display_path(config.exact_checks),
        "expected_sha256": config.exact_checks_sha256,
        "actual_sha256": None,
        "status": None,
        "valid": False,
        "reason": None,
    }
    if not config.exact_checks.is_file():
        result["reason"] = "missing reference artifact"
        return result
    try:
        actual = sha256_file(config.exact_checks)
        result["actual_sha256"] = actual
        if actual != config.exact_checks_sha256:
            result["reason"] = "reference artifact hash mismatch"
            return result
        payload = json.loads(config.exact_checks.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        result["reason"] = f"invalid reference artifact: {error}"
        return result
    result["status"] = payload.get("status") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("status") != PASS:
        result["reason"] = "reference artifact does not declare PASS"
        return result
    if not _all_finite(payload):
        result["reason"] = "reference artifact contains nonfinite metrics"
        return result
    result["valid"] = True
    return result


def _run_mps_tests(tests: tuple[Path, ...]) -> dict[str, object]:
    started_at = _utc_now()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *[_display_path(path) for path in tests],
    ]
    print(f"stage4 tests start files={len(tests)}", flush=True)
    if not tests:
        return {
            "command": command,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "exit_code": None,
            "passed": False,
            "output": "No tests matched tests/*mps*.py\n",
        }
    process = subprocess.Popen(
        command,
        cwd=TRACK_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    lines: list[str] = []
    if process.stdout is None:
        raise RuntimeError("pytest stdout pipe was not created")
    for line in process.stdout:
        lines.append(line)
        print(line, end="", flush=True)
    exit_code = process.wait()
    print(f"stage4 tests exit={exit_code}", flush=True)
    return {
        "command": command,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "output": "".join(lines),
    }


def _couplings(config: _Stage4Config) -> np.ndarray:
    values = np.zeros(config.operator_count, dtype=np.float64)
    values[0] = config.coupling
    return values


def _gradient_probe(config: _Stage4Config) -> dict[str, object]:
    rng = np.random.default_rng(config.seed + 1)
    model = PatchMPS.random(
        chi=config.chi, seed=config.seed + 2, symmetrize=config.symmetrize
    )
    patches = rng.choice(np.array([-1, 1], dtype=np.int8), size=(7, 9))
    weights = rng.normal(size=7)
    analytic_gradient = model.gradient(patches, weights=weights, symmetrize=True)
    core_index = 4
    index = (1, 0, 1)
    original = float(model.cores[core_index][index])
    epsilon = config.gradient_epsilon
    model.cores[core_index][index] = original + epsilon
    plus = float(weights @ model.symmetric_values(patches))
    model.cores[core_index][index] = original - epsilon
    minus = float(weights @ model.symmetric_values(patches))
    model.cores[core_index][index] = original
    analytic = float(analytic_gradient.cores[core_index][index])
    numeric = (plus - minus) / (2.0 * epsilon)
    return {
        "error": abs(analytic - numeric),
        "analytic": analytic,
        "finite_difference": numeric,
        "epsilon": epsilon,
        "core": core_index,
        "index": list(index),
    }


def _canonical_probe(config: _Stage4Config) -> dict[str, object]:
    model = PatchMPS.random(
        chi=config.chi, seed=config.seed + 3, symmetrize=config.symmetrize
    )
    patches = enumerate_patches()
    before = model.raw_values(patches)
    model.left_canonicalize()
    after = model.raw_values(patches)
    return {
        "error": float(np.max(np.abs(after - before))),
        "patches": int(patches.shape[0]),
    }


def _delta_probe(config: _Stage4Config) -> dict[str, object]:
    rng = np.random.default_rng(config.seed + 4)
    shapes = EVEN_SHAPES[: config.operator_count]
    model = PatchMPS.random(
        chi=config.chi, seed=config.seed + 5, symmetrize=config.symmetrize
    )
    lookup = PatchLookupTable.from_model(model)
    linear_bias = np.linspace(-0.02, 0.004, config.operator_count)
    alpha = 0.2
    sampler = MPSBiasedMetropolis(
        IsingLattice.random(config.length, rng),
        _couplings(config),
        linear_bias,
        alpha,
        lookup,
        rng,
        shapes,
        block_size=config.block_size,
        rg_levels=config.rg_levels,
        compiled=False,
    )
    micro_basis = OperatorBasis(config.length, shapes)
    block_basis = OperatorBasis(config.length // config.block_size, shapes)
    errors: list[float] = []
    connected = 0
    for _ in range(config.local_delta_trials):
        x = int(rng.integers(config.length))
        y = int(rng.integers(config.length))
        before = sampler.effective_hamiltonian
        proposal = sampler.proposal_delta(x, y)
        trial = sampler.lattice.spins.copy()
        trial[x, y] *= -1
        coarse = block_majority(trial, config.block_size)
        after = float(
            _couplings(config) @ micro_basis.values(trial)
            + linear_bias @ block_basis.values(coarse)
            + alpha * PatchEnergyCache(coarse, lookup).energy
        )
        errors.append(abs((after - before) - proposal.delta_hamiltonian))
        connected += int(proposal.rg_proposal.final_changed)
    return {
        "error": max(errors),
        "trials": len(errors),
        "coarse_connectivity_events": connected,
    }


def _checkpoint_probe(config: _Stage4Config, output: Path) -> dict[str, object]:
    model = PatchMPS.random(
        chi=config.chi, seed=config.seed + 6, symmetrize=config.symmetrize
    )
    alpha = 0.37
    linear_bias = np.linspace(-0.2, 0.02, config.operator_count)
    metadata = {"probe": "stage4", "seed": config.seed, "trials": 1}
    save_mps_checkpoint(
        output, model=model, alpha=alpha, linear_bias=linear_bias, metadata=metadata
    )
    try:
        restored = load_mps_checkpoint(output)
        equal = bool(
            restored.alpha == alpha
            and restored.metadata == metadata
            and restored.model.chi == model.chi
            and restored.model.symmetrize == model.symmetrize
            and np.array_equal(restored.linear_bias, linear_bias)
            and all(
                np.array_equal(actual, expected)
                for actual, expected in zip(restored.model.cores, model.cores)
            )
        )
    except (OSError, KeyError, TypeError, ValueError):
        equal = False
    return {"equal": equal, "path": "checkpoint_probe"}


def _run_numerical_probes(
    config: _Stage4Config, checkpoint_output: Path
) -> dict[str, object]:
    print("stage4 probe gradient", flush=True)
    gradient = _gradient_probe(config)
    print("stage4 probe canonicalization", flush=True)
    canonical = _canonical_probe(config)
    print(f"stage4 probe local-deltas trials={config.local_delta_trials}", flush=True)
    delta = _delta_probe(config)
    print("stage4 probe checkpoint", flush=True)
    checkpoint = _checkpoint_probe(config, checkpoint_output)
    classification = classify_stage4(
        gradient_error=float(gradient["error"]),
        canonical_error=float(canonical["error"]),
        delta_error=float(delta["error"]),
        checkpoint_equal=bool(checkpoint["equal"]),
    )
    return {
        "gradient": gradient,
        "canonicalization": canonical,
        "incremental_delta": delta,
        "checkpoint": checkpoint,
        "classification": classification["classification"],
        "failed_gates": classification["failed_gates"],
    }


def _model_unchanged(model: PatchMPS, cores: tuple[np.ndarray, ...]) -> bool:
    return all(
        np.array_equal(actual, expected)
        for actual, expected in zip(model.cores, cores)
    )


def _run_connectivity_cell(config: _Stage4Config) -> dict[str, object]:
    print(
        "stage4 L=45 b=3 chi=2 connectivity cell: regression-only; "
        "not 3D Hard Goal evidence",
        flush=True,
    )
    shapes = EVEN_SHAPES[: config.operator_count]
    model = PatchMPS.random(
        chi=config.chi,
        seed=config.seed + 10_000,
        symmetrize=config.symmetrize,
    )
    optimizer = MPSVMCRGOptimizer(
        length=config.length,
        couplings=_couplings(config),
        linear_bias=np.zeros(config.operator_count, dtype=np.float64),
        model=model,
        shapes=shapes,
        walkers=config.walkers,
        seed=config.seed + 20_000,
        alpha=config.initial_alpha,
        block_size=config.block_size,
        rg_levels=config.rg_levels,
        compiled=config.compiled,
        parallel_walkers=config.parallel_walkers,
    )

    def progress(record: object) -> None:
        step = int(getattr(record, "step")) + 1
        objective = float(getattr(record, "objective"))
        gradient = float(getattr(record, "gradient_norm"))
        alpha = float(getattr(record, "alpha"))
        print(
            f"stage4 cell step={step}/{config.optimizer_steps} "
            f"objective={objective:.6g} grad={gradient:.6g} alpha={alpha:.6g}",
            flush=True,
        )

    records = optimizer.run(
        steps=config.optimizer_steps,
        sweeps_per_step=config.sweeps_per_step,
        alpha_learning_rate=config.alpha_learning_rate,
        core_learning_rate=config.core_learning_rate,
        linear_learning_rate=config.linear_learning_rate,
        gradient_clip=config.gradient_clip,
        canonicalize_every=config.canonicalize_every,
        cache_check_every=config.cache_check_every,
        callback=progress,
    )
    frozen_cores = tuple(core.copy() for core in model.cores)
    lookup = PatchLookupTable.from_model(model)
    measurement_rng = np.random.default_rng(config.seed + 30_000)
    sampler = MPSBiasedMetropolis(
        IsingLattice.random(config.length, measurement_rng),
        _couplings(config),
        optimizer.linear_bias,
        optimizer.alpha,
        lookup,
        measurement_rng,
        shapes,
        block_size=config.block_size,
        rg_levels=config.rg_levels,
        compiled=config.compiled,
    )
    print(
        f"stage4 cell thermalization sweeps={config.thermalization_sweeps}",
        flush=True,
    )
    sampler.run_sweeps(config.thermalization_sweeps)
    energies: list[float] = []
    correlations: list[float] = []
    residuals: list[float] = []
    for measurement in range(config.frozen_measurement_sweeps):
        sampler.run_sweeps(config.measurement_thinning)
        energies.append(
            float(sampler.couplings @ sampler.micro_values / sampler.lattice.n_sites)
        )
        correlations.append(
            -float(sampler.block_values[0])
            / float(sampler.block_basis.instance_counts[0])
        )
        residuals.append(
            float(sampler.patch_cache.energy / sampler.rg_state.coarse_spins.size)
        )
        count = measurement + 1
        if count == 1 or count % 4 == 0:
            print(
                "stage4 cell frozen-measurement "
                f"sweep={count}/{config.frozen_measurement_sweeps}",
                flush=True,
            )
    sampler.assert_cache_consistent()
    unchanged = _model_unchanged(model, frozen_cores)
    return {
        "status": "REGRESSION_COMPLETE",
        "regression_only": True,
        "three_dimensional_hard_goal_evidence": False,
        "statement": REGRESSION_STATEMENT,
        "parameters": config.public_parameters(),
        "optimizer": {
            "records": [record.to_dict() for record in records],
            "steps_completed": len(records),
            "final_alpha": optimizer.alpha,
            "final_model_diagnostics": model.diagnostics(),
        },
        "frozen_measurement": {
            "model_unchanged": unchanged,
            "thermalization_sweeps": config.thermalization_sweeps,
            "measurement_sweeps": len(energies),
            "thinning": config.measurement_thinning,
            "acceptance_rate": sampler.acceptance_rate,
            "energy_per_site_mean": float(np.mean(energies)),
            "block_nn_correlation_mean": float(np.mean(correlations)),
            "patch_residual_per_site_mean": float(np.mean(residuals)),
            "energy_per_site": energies,
            "block_nn_correlation": correlations,
            "patch_residual_per_site": residuals,
        },
    }


def _artifact_hashes(staging: Path) -> dict[str, str]:
    return {
        path.relative_to(staging).as_posix(): sha256_file(path)
        for path in sorted(staging.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def _verify_hashes(root: Path, expected: Mapping[str, str]) -> list[str]:
    failures: list[str] = []
    for relative, digest in expected.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"missing:{relative}")
        elif sha256_file(path) != digest:
            failures.append(f"hash_mismatch:{relative}")
    return failures


def _promote_directory_no_replace(staging: Path, destination: Path) -> None:
    """Atomically publish ``staging`` only while ``destination`` is absent."""

    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise RuntimeError("atomic no-replace directory promotion is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,  # AT_FDCWD
        os.fsencode(staging),
        -100,
        os.fsencode(destination),
        1,  # RENAME_NOREPLACE
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(
            error_number,
            f"refusing to overwrite Stage 4 output: {destination}",
            str(destination),
        )
    raise OSError(error_number, os.strerror(error_number), str(destination))


def _verified_promote_directory_no_replace(
    staging: Path, destination: Path, expected: Mapping[str, str]
) -> None:
    if not staging.is_dir():
        raise FileNotFoundError(f"staging directory does not exist: {staging}")
    failures = _verify_hashes(staging, expected)
    if failures:
        raise ValueError("staged artifact verification failed: " + ", ".join(failures))
    destination.parent.mkdir(parents=True, exist_ok=True)
    _promote_directory_no_replace(staging, destination)


def _append_unique(target: list[str], values: list[str] | tuple[str, ...]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def run_stage4(config: Path, output: Path) -> StageManifest:
    """Run and atomically publish the two-dimensional Stage 4 regression gate."""

    destination = Path(output).resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite Stage 4 output: {destination}")
    stage_config = _load_stage4_config(config)
    design = load_design(stage_config.design)
    if 45 not in design.sizes or design.rg.block_shape != (3, 3, 3):
        raise ValueError("Hard Goal design no longer provides the Stage 4 interfaces")

    test_paths = tuple(sorted(TRACK_ROOT.glob(stage_config.tests_glob)))
    source_paths = _source_paths(stage_config, test_paths)
    source_hashes, source_failures = _hash_sources(source_paths)
    reference = _validate_reference(stage_config)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.stage4-", dir=destination.parent)
    )
    try:
        print(REGRESSION_STATEMENT, flush=True)
        tests = _run_mps_tests(test_paths)
        numerical = _run_numerical_probes(stage_config, staging / "checkpoint_probe")
        cell = _run_connectivity_cell(stage_config)

        atomic_write_json(staging / "reference_check.json", _json_safe(reference))
        atomic_write_json(staging / "mps_tests.json", _json_safe(tests))
        atomic_write_json(staging / "numerical_checks.json", _json_safe(numerical))
        atomic_write_json(staging / "connectivity_cell.json", _json_safe(cell))
        atomic_write_json(
            staging / "run_config.json",
            {
                "source": _display_path(stage_config.source),
                "parameters": stage_config.public_parameters(),
                "tolerances": {
                    "gradient_error": GRADIENT_TOLERANCE,
                    "canonical_error": CANONICAL_TOLERANCE,
                    "local_delta_error": DELTA_TOLERANCE,
                },
                "regression_only": True,
                "three_dimensional_hard_goal_evidence": False,
                "statement": REGRESSION_STATEMENT,
            },
        )

        failed_gates = list(numerical["failed_gates"])
        if not reference["valid"]:
            _append_unique(failed_gates, ["reference_artifact"])
        if not tests["passed"]:
            _append_unique(failed_gates, ["mps_tests"])
        if source_failures:
            _append_unique(failed_gates, ["source_integrity"])
        if not _all_finite(numerical) or not _all_finite(cell):
            _append_unique(failed_gates, ["nonfinite_metrics"])
        frozen = cell["frozen_measurement"]
        if not isinstance(frozen, dict) or not frozen.get("model_unchanged"):
            _append_unique(failed_gates, ["frozen_measurement"])
        if cell["optimizer"]["steps_completed"] != stage_config.optimizer_steps:
            _append_unique(failed_gates, ["optimizer_schedule"])
        if frozen.get("measurement_sweeps") != stage_config.frozen_measurement_sweeps:
            _append_unique(failed_gates, ["measurement_schedule"])

        ending_hashes, ending_source_failures = _hash_sources(source_paths)
        if source_hashes != ending_hashes or ending_source_failures:
            _append_unique(failed_gates, ["source_integrity"])
        source_failures = sorted(set(source_failures + ending_source_failures))

        artifact_hashes = _artifact_hashes(staging)
        artifact_failures = _verify_hashes(staging, artifact_hashes)
        if artifact_failures:
            _append_unique(failed_gates, ["artifact_integrity"])
        classification = PASS if not failed_gates else CORRECTNESS_FAILURE
        artifacts = {
            "reference_check": "reference_check.json",
            "fresh_mps_tests": "mps_tests.json",
            "numerical_checks": "numerical_checks.json",
            "connectivity_cell": "connectivity_cell.json",
            "run_config": "run_config.json",
            "checkpoint_model": "checkpoint_probe/model.npz",
            "checkpoint_metadata": "checkpoint_probe/metadata.json",
        }
        combined_hashes = {
            **{f"source:{name}": digest for name, digest in source_hashes.items()},
            **{
                f"artifact:{name}": digest
                for name, digest in artifact_hashes.items()
            },
        }
        manifest = StageManifest(
            stage=STAGE,
            classification=classification,
            failed_gates=tuple(failed_gates),
            artifacts=artifacts,
            hashes=combined_hashes,
        )
        payload = {
            "schema_version": 1,
            **manifest.to_dict(),
            "created_at": _utc_now(),
            "regression_only": True,
            "three_dimensional_hard_goal_evidence": False,
            "statement": REGRESSION_STATEMENT,
            "numerical_tolerances": {
                "gradient_error": GRADIENT_TOLERANCE,
                "canonical_error": CANONICAL_TOLERANCE,
                "local_delta_error": DELTA_TOLERANCE,
            },
            "fresh_test_results": {
                "artifact": artifacts["fresh_mps_tests"],
                "command": tests["command"],
                "started_at": tests["started_at"],
                "finished_at": tests["finished_at"],
                "exit_code": tests["exit_code"],
                "passed": tests["passed"],
            },
            "cell_parameters": stage_config.public_parameters(),
            "reference_artifact": reference,
            "source_integrity": {
                "passed": not source_failures and source_hashes == ending_hashes,
                "failures": source_failures,
            },
            "artifact_integrity": {
                "passed": not artifact_failures,
                "failures": artifact_failures,
            },
        }
        atomic_write_json(staging / "manifest.json", _json_safe(payload))
        promotion_hashes = {
            **artifact_hashes,
            "manifest.json": sha256_file(staging / "manifest.json"),
        }
        _verified_promote_directory_no_replace(
            staging, destination, promotion_hashes
        )
        final_failures = _verify_hashes(destination, promotion_hashes)
        if final_failures:
            raise RuntimeError(
                "published Stage 4 artifact verification failed: "
                + ", ".join(final_failures)
            )
        print(
            f"stage4 classification={manifest.classification} output={destination}",
            flush=True,
        )
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


@dataclass(frozen=True)
class Stage6Config:
    """Hashable fixed contract for the approved medium-size pilot."""

    source: Path
    design: Path
    second_rg: bool
    lengths: tuple[int, ...]
    j_counts: tuple[int, ...]
    temperature_min: float
    temperature_max: float
    temperature_count: int
    temperature_schedule: str
    chain_pairs: int
    calibration_sweeps: int
    initial_equilibration_sweeps: int
    equilibration_multiplier: int
    maximum_equilibration_sweeps: int
    measurement_sweeps: int
    templates: tuple[str, ...]
    routes: tuple[str, ...]
    control: str
    chis: tuple[int, ...]
    swap_bottleneck: float
    swap_target_minimum: float
    swap_target_maximum: float
    minimum_round_trips: int
    maximum_rhat: float
    minimum_ess: float
    bin_sigma: float
    maximum_thermal_error_fraction: float
    memory_margin: float
    output_margin: float
    backend: str
    maximum_array_size: int
    maximum_wall_seconds: int
    progress_updates_minimum: int
    progress_updates_maximum: int
    pilot_seed: int
    bootstrap_seed: int

    def temperatures(self) -> tuple[float, ...]:
        beta_min = 1.0 / self.temperature_max
        beta_max = 1.0 / self.temperature_min
        betas = np.linspace(
            beta_min,
            beta_max,
            self.temperature_count,
            dtype=np.float64,
        )
        return tuple(float(value) for value in 1.0 / betas)

    def public_parameters(self) -> dict[str, object]:
        return {
            "second_rg": self.second_rg,
            "lengths": list(self.lengths),
            "j_counts": list(self.j_counts),
            "temperatures": list(self.temperatures()),
            "temperature_schedule": self.temperature_schedule,
            "chain_pairs": self.chain_pairs,
            "calibration_sweeps": self.calibration_sweeps,
            "initial_equilibration_sweeps": self.initial_equilibration_sweeps,
            "equilibration_multiplier": self.equilibration_multiplier,
            "maximum_equilibration_sweeps": self.maximum_equilibration_sweeps,
            "measurement_sweeps": self.measurement_sweeps,
            "templates": list(self.templates),
            "routes": list(self.routes),
            "control": self.control,
            "chis": list(self.chis),
            "backend": self.backend,
        }


def _stage6_integer_tuple(value: object, name: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a nonempty integer array")
    if any(type(item) is not int for item in value):
        raise ValueError(f"{name} must contain only integers")
    return tuple(int(item) for item in value)


def _stage6_string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a nonempty string array")
    if any(type(item) is not str for item in value):
        raise ValueError(f"{name} must contain only strings")
    return tuple(str(item) for item in value)


def load_stage6_config(path: str | Path) -> Stage6Config:
    """Load the exact user-approved Stage 6 matrix without silent reductions."""

    source = Path(path).resolve()
    with source.open("rb") as handle:
        raw = tomllib.load(handle)
    _require_exact_keys(
        raw,
        {
            "schema_version",
            "stage",
            "classification_scope",
            "second_rg",
            "sources",
            "sizes",
            "temperatures",
            "sampling",
            "comparison",
            "thresholds",
            "execution",
            "seeds",
        },
        "stage6 top level",
    )
    _expect_equal(raw["schema_version"], 1, "schema_version")
    _expect_equal(raw["stage"], STAGE6, "stage")
    _expect_equal(
        raw["classification_scope"],
        "medium_3d_equilibration_and_representation_pilot",
        "classification_scope",
    )
    _expect_equal(raw["second_rg"], False, "second_rg")

    sources = _table(raw, "sources")
    sizes = _table(raw, "sizes")
    temperatures = _table(raw, "temperatures")
    sampling = _table(raw, "sampling")
    comparison = _table(raw, "comparison")
    thresholds = _table(raw, "thresholds")
    execution = _table(raw, "execution")
    seeds = _table(raw, "seeds")
    _require_exact_keys(sources, {"hard_goal_design"}, "stage6 sources")
    _require_exact_keys(sizes, {"lengths", "j_counts"}, "stage6 sizes")
    _require_exact_keys(
        temperatures,
        {"minimum", "maximum", "count", "schedule"},
        "stage6 temperatures",
    )
    _require_exact_keys(
        sampling,
        {
            "chain_pairs",
            "calibration_sweeps",
            "equilibration_initial_sweeps",
            "equilibration_multiplier",
            "equilibration_maximum_sweeps",
            "measurement_sweeps",
        },
        "stage6 sampling",
    )
    _require_exact_keys(
        comparison,
        {"templates", "routes", "control", "chis"},
        "stage6 comparison",
    )
    _require_exact_keys(
        thresholds,
        {
            "swap_bottleneck",
            "swap_target_minimum",
            "swap_target_maximum",
            "minimum_round_trips",
            "maximum_rhat",
            "minimum_ess",
            "bin_sigma",
            "maximum_thermal_error_fraction",
            "memory_margin",
            "output_margin",
        },
        "stage6 thresholds",
    )
    _require_exact_keys(
        execution,
        {
            "backend",
            "maximum_array_size",
            "maximum_wall_seconds",
            "progress_updates_minimum",
            "progress_updates_maximum",
        },
        "stage6 execution",
    )
    _require_exact_keys(seeds, {"pilot", "bootstrap"}, "stage6 seeds")

    fixed = {
        "sizes.lengths": (sizes["lengths"], [12, 18, 24, 27]),
        "sizes.j_counts": (sizes["j_counts"], [64, 32, 16, 8]),
        "temperatures.minimum": (temperatures["minimum"], 0.80),
        "temperatures.maximum": (temperatures["maximum"], 2.00),
        "temperatures.count": (temperatures["count"], 48),
        "temperatures.schedule": (temperatures["schedule"], "linear_beta"),
        "sampling.chain_pairs": (sampling["chain_pairs"], 4),
        "sampling.calibration_sweeps": (sampling["calibration_sweeps"], 4096),
        "sampling.equilibration_initial_sweeps": (
            sampling["equilibration_initial_sweeps"],
            8192,
        ),
        "sampling.equilibration_multiplier": (
            sampling["equilibration_multiplier"],
            2,
        ),
        "sampling.equilibration_maximum_sweeps": (
            sampling["equilibration_maximum_sweeps"],
            1_048_576,
        ),
        "sampling.measurement_sweeps": (sampling["measurement_sweeps"], 8192),
        "comparison.templates": (comparison["templates"], ["cube", "cross"]),
        "comparison.routes": (comparison["routes"], ["C", "B"]),
        "comparison.control": (comparison["control"], "conditioned_linear"),
        "comparison.chis": (comparison["chis"], [2, 4, 8]),
        "thresholds.swap_bottleneck": (thresholds["swap_bottleneck"], 0.15),
        "thresholds.swap_target_minimum": (
            thresholds["swap_target_minimum"],
            0.20,
        ),
        "thresholds.swap_target_maximum": (
            thresholds["swap_target_maximum"],
            0.50,
        ),
        "thresholds.minimum_round_trips": (
            thresholds["minimum_round_trips"],
            10,
        ),
        "thresholds.maximum_rhat": (thresholds["maximum_rhat"], 1.05),
        "thresholds.minimum_ess": (thresholds["minimum_ess"], 200.0),
        "thresholds.bin_sigma": (thresholds["bin_sigma"], 2.0),
        "thresholds.maximum_thermal_error_fraction": (
            thresholds["maximum_thermal_error_fraction"],
            0.25,
        ),
        "thresholds.memory_margin": (thresholds["memory_margin"], 1.5),
        "thresholds.output_margin": (thresholds["output_margin"], 1.5),
        "execution.backend": (execution["backend"], "jax_gpu"),
        "execution.maximum_array_size": (execution["maximum_array_size"], 200),
        "execution.maximum_wall_seconds": (
            execution["maximum_wall_seconds"],
            86_400,
        ),
        "execution.progress_updates_minimum": (
            execution["progress_updates_minimum"],
            10,
        ),
        "execution.progress_updates_maximum": (
            execution["progress_updates_maximum"],
            50,
        ),
        "seeds.pilot": (seeds["pilot"], 2026073102),
        "seeds.bootstrap": (seeds["bootstrap"], 2026073101),
    }
    for name, (actual, expected) in fixed.items():
        _expect_equal(actual, expected, name)

    lengths = _stage6_integer_tuple(sizes["lengths"], "sizes.lengths")
    j_counts = _stage6_integer_tuple(sizes["j_counts"], "sizes.j_counts")
    templates = _stage6_string_tuple(comparison["templates"], "comparison.templates")
    routes = _stage6_string_tuple(comparison["routes"], "comparison.routes")
    chis = _stage6_integer_tuple(comparison["chis"], "comparison.chis")
    if len(lengths) != len(j_counts) or sum(j_counts) > int(
        execution["maximum_array_size"]
    ):
        raise ValueError("Stage 6 disorder cells exceed the array contract")
    design = _resolve_fixed_source(
        sources["hard_goal_design"],
        "config/hard_goal/design_v1.toml",
        "hard_goal_design",
    )
    load_design(design)
    return Stage6Config(
        source=source,
        design=design,
        second_rg=False,
        lengths=lengths,
        j_counts=j_counts,
        temperature_min=float(temperatures["minimum"]),
        temperature_max=float(temperatures["maximum"]),
        temperature_count=int(temperatures["count"]),
        temperature_schedule=str(temperatures["schedule"]),
        chain_pairs=int(sampling["chain_pairs"]),
        calibration_sweeps=int(sampling["calibration_sweeps"]),
        initial_equilibration_sweeps=int(
            sampling["equilibration_initial_sweeps"]
        ),
        equilibration_multiplier=int(sampling["equilibration_multiplier"]),
        maximum_equilibration_sweeps=int(
            sampling["equilibration_maximum_sweeps"]
        ),
        measurement_sweeps=int(sampling["measurement_sweeps"]),
        templates=templates,
        routes=routes,
        control=str(comparison["control"]),
        chis=chis,
        swap_bottleneck=float(thresholds["swap_bottleneck"]),
        swap_target_minimum=float(thresholds["swap_target_minimum"]),
        swap_target_maximum=float(thresholds["swap_target_maximum"]),
        minimum_round_trips=int(thresholds["minimum_round_trips"]),
        maximum_rhat=float(thresholds["maximum_rhat"]),
        minimum_ess=float(thresholds["minimum_ess"]),
        bin_sigma=float(thresholds["bin_sigma"]),
        maximum_thermal_error_fraction=float(
            thresholds["maximum_thermal_error_fraction"]
        ),
        memory_margin=float(thresholds["memory_margin"]),
        output_margin=float(thresholds["output_margin"]),
        backend=str(execution["backend"]),
        maximum_array_size=int(execution["maximum_array_size"]),
        maximum_wall_seconds=int(execution["maximum_wall_seconds"]),
        progress_updates_minimum=int(execution["progress_updates_minimum"]),
        progress_updates_maximum=int(execution["progress_updates_maximum"]),
        pilot_seed=int(seeds["pilot"]),
        bootstrap_seed=int(seeds["bootstrap"]),
    )


def _pilot_seed(design_hash: str, length: int, index: int, base_seed: int) -> int:
    payload = f"{design_hash}|{length}|{index}|{base_seed}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)


def build_pilot_run_spec(config: Stage6Config, run_id: str) -> dict[str, object]:
    """Build one full-temperature-ladder cell per preregistered J sample."""

    if not isinstance(config, Stage6Config):
        raise TypeError("config must be Stage6Config")
    if not isinstance(run_id, str) or not run_id or "/" in run_id or ".." in run_id:
        raise ValueError("run_id must be one safe path component")
    design_hash = sha256_file(config.design)
    config_hash = sha256_file(config.source)
    source_names = (
        "jobs/hard_goal_pilot.slurm",
        "scripts/hard_goal_pilot_cell.py",
        "src/spinglass3d/backend.py",
        "src/spinglass3d/jax_backend.py",
        "src/spinglass3d/model.py",
        "src/spinglass3d/pilot.py",
        "src/spinglass3d/workflow.py",
    )
    source_hashes = {
        name: sha256_file(TRACK_ROOT / name) for name in source_names
    }
    temperatures = list(config.temperatures())
    cells: list[dict[str, object]] = []
    for length, count in zip(config.lengths, config.j_counts, strict=True):
        for index in range(count):
            cell_id = f"L{length:02d}-J{index:04d}"
            cells.append(
                {
                    "cell_id": cell_id,
                    "params": {
                        "stage": STAGE6,
                        "phase": "calibration_and_pilot",
                        "length": length,
                        "j_index": index,
                        "j_seed": _pilot_seed(
                            design_hash,
                            length,
                            index,
                            config.pilot_seed,
                        ),
                        "temperatures": temperatures,
                        "chain_pairs": config.chain_pairs,
                        "rg_levels": 1,
                        "output": f"results/hard_goal/{run_id}/cells/{cell_id}",
                    },
                }
            )
    if len(cells) > config.maximum_array_size:
        raise ValueError(
            f"pilot has {len(cells)} cells, above array limit {config.maximum_array_size}"
        )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "run_dir": f"results/hard_goal/{run_id}",
        "axes": {"length": list(config.lengths), "disorder": "preregistered_by_length"},
        "settings": {
            "sampling": {
                "calibration_sweeps": config.calibration_sweeps,
                "initial_equilibration_sweeps": config.initial_equilibration_sweeps,
                "equilibration_multiplier": config.equilibration_multiplier,
                "maximum_equilibration_sweeps": config.maximum_equilibration_sweeps,
                "measurement_sweeps": config.measurement_sweeps,
            },
            "comparison": {
                "templates": list(config.templates),
                "routes": list(config.routes),
                "control": config.control,
                "chis": list(config.chis),
            },
            "thresholds": {
                "swap_bottleneck": config.swap_bottleneck,
                "swap_target_minimum": config.swap_target_minimum,
                "swap_target_maximum": config.swap_target_maximum,
            },
            "backend": config.backend,
            "second_rg": False,
        },
        "provenance": {
            "config_path": "config/hard_goal/stage6_pilot_v1.toml",
            "design_path": "config/hard_goal/design_v1.toml",
            "config_sha256": config_hash,
            "design_sha256": design_hash,
            "source_sha256": source_hashes,
            "claims": [
                "stage6 pilot only",
                "complete temperature ladder per cell",
                "no second RG",
                "not production or Tc evidence",
            ],
        },
        "cells": cells,
    }


def estimate_pilot_resources(
    config: Stage6Config,
    backend_evidence: str | Path,
) -> dict[str, object]:
    """Project the declared matrix from a fail-closed GPU smoke manifest."""

    if not isinstance(config, Stage6Config):
        raise TypeError("config must be Stage6Config")
    evidence_path = Path(backend_evidence)
    payload = json.loads(evidence_path.read_text(encoding="ascii"))
    runtime = payload.get("runtime")
    benchmark = payload.get("benchmark")
    if (
        payload.get("classification") != PASS
        or not isinstance(runtime, dict)
        or not isinstance(benchmark, dict)
        or runtime.get("default_backend") != "gpu"
        or runtime.get("x64_enabled") is not True
    ):
        raise ValueError("verified GPU backend evidence is required")
    devices = runtime.get("devices")
    if not isinstance(devices, list) or "cuda:0" not in devices:
        raise ValueError("verified GPU cuda:0 evidence is required")
    throughput = _finite_float(
        benchmark.get("warm_spin_proposals_per_second"),
        "warm_spin_proposals_per_second",
    )
    if throughput <= 0.0:
        raise ValueError("GPU throughput must be positive")
    walkers = 2 * config.chain_pairs
    proposals_per_sweep = sum(
        count * config.temperature_count * walkers * length**3
        for length, count in zip(config.lengths, config.j_counts, strict=True)
    )
    calibration = proposals_per_sweep * config.calibration_sweeps
    maximum = proposals_per_sweep * config.maximum_equilibration_sweeps
    smoke_length = int(benchmark.get("length", 0))
    smoke_checkpoint = int(benchmark.get("checkpoint_bytes", 0))
    smoke_device_memory = int(benchmark.get("peak_device_memory_bytes", 0))
    smoke_host_memory = int(benchmark.get("peak_host_memory_bytes", 0))
    if smoke_length < 1 or min(
        smoke_checkpoint,
        smoke_device_memory,
        smoke_host_memory,
    ) < 1:
        raise ValueError("GPU smoke resource telemetry is incomplete")
    per_length: dict[str, dict[str, object]] = {}
    total_calibration_seconds = 0.0
    for length, count in zip(config.lengths, config.j_counts, strict=True):
        one_sweep = config.temperature_count * walkers * length**3
        calibration_seconds = one_sweep * config.calibration_sweeps / throughput
        maximum_seconds = (
            one_sweep * config.maximum_equilibration_sweeps / throughput
        )
        scaled = (length / smoke_length) ** 3
        requested_wall = int(
            math.ceil(1.5 * calibration_seconds / 1800.0) * 1800
        )
        requested_wall = max(1800, min(config.maximum_wall_seconds, requested_wall))
        total_calibration_seconds += count * calibration_seconds
        per_length[str(length)] = {
            "cell_count": count,
            "spin_proposals_per_sweep": one_sweep,
            "calibration_seconds_per_cell": calibration_seconds,
            "maximum_equilibration_seconds_per_cell": maximum_seconds,
            "calibration_request_wall_seconds": requested_wall,
            "calibration_fits_24h_with_1_5x_margin": (
                1.5 * calibration_seconds <= config.maximum_wall_seconds
            ),
            "projected_checkpoint_bytes": int(math.ceil(smoke_checkpoint * scaled)),
            "projected_peak_device_memory_bytes": int(
                math.ceil(smoke_device_memory * max(1.0, scaled))
            ),
            "projected_peak_host_memory_bytes": int(
                math.ceil(smoke_host_memory * max(1.0, scaled))
            ),
        }
    return {
        "backend_evidence_sha256": sha256_file(evidence_path),
        "backend": "gpu",
        "device": "cuda:0",
        "x64_enabled": True,
        "measured_warm_spin_proposals_per_second": throughput,
        "minimum_calibration_proposals": calibration,
        "maximum_equilibration_proposals": maximum,
        "conservative_calibration_seconds": calibration / throughput,
        "maximum_equilibration_seconds": maximum / throughput,
        "smoke_peak_device_memory_bytes": smoke_device_memory,
        "smoke_peak_host_memory_bytes": smoke_host_memory,
        "per_length": per_length,
        "total_calibration_accelerator_hours": total_calibration_seconds / 3600.0,
        "assumption": (
            "conservative direct proposal-rate scaling; full-ladder calibration "
            "must replace this estimate before the pilot array is frozen"
        ),
    }


def prepare_pilot_run(
    config: str | Path,
    backend_evidence: str | Path,
    output: str | Path,
) -> dict[str, object]:
    """Immutably publish a Stage 6 launch package, never scientific evidence."""

    destination = Path(output).resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite pilot launch: {destination}")
    stage_config = load_stage6_config(config)
    run_spec = build_pilot_run_spec(stage_config, destination.name)
    estimate = estimate_pilot_resources(stage_config, backend_evidence)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.launch-",
            dir=destination.parent,
        )
    )
    try:
        run_spec_path = staging / "run_spec.json"
        estimate_path = staging / "resource_estimate.json"
        atomic_write_json(run_spec_path, _json_safe(run_spec))
        atomic_write_json(estimate_path, _json_safe(estimate))
        artifacts = {
            "run_spec.json": sha256_file(run_spec_path),
            "resource_estimate.json": sha256_file(estimate_path),
        }
        launch = {
            "schema_version": 1,
            "stage": STAGE6,
            "classification": "PLANNED",
            "scientific_evidence": False,
            "tc_evidence": False,
            "second_rg_enabled": False,
            "created_at": _utc_now(),
            "cell_count": len(run_spec["cells"]),
            "config_sha256": sha256_file(stage_config.source),
            "design_sha256": sha256_file(stage_config.design),
            "backend_evidence_sha256": estimate["backend_evidence_sha256"],
            "artifacts": artifacts,
        }
        launch_path = staging / "launch.json"
        atomic_write_json(launch_path, launch)
        promotion_hashes = {
            **artifacts,
            "launch.json": sha256_file(launch_path),
        }
        _verified_promote_directory_no_replace(
            staging,
            destination,
            promotion_hashes,
        )
        return launch
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _freeze_table(payload: Mapping[str, object], name: str) -> dict[str, object]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"pilot manifest is missing {name}")
    return dict(value)


def _freeze_positive(value: object, name: str) -> float:
    result = _finite_float(value, name)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def _reject_symlink_components(path: Path, name: str) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError as error:
            raise FileNotFoundError(f"{name} is missing: {current}") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"{name} contains a symlink: {current}")
    return absolute


def _regular_file_nofollow(path: Path, name: str) -> Path:
    absolute = _reject_symlink_components(path, name)
    if not stat.S_ISREG(os.lstat(absolute).st_mode):
        raise ValueError(f"{name} must be a regular file: {absolute}")
    return absolute


def _stage6_artifact_inventory(root: Path) -> dict[str, str]:
    artifact_root = _reject_symlink_components(root, "Stage 6 artifact root")
    if not stat.S_ISDIR(os.lstat(artifact_root).st_mode):
        raise ValueError("Stage 6 artifact root must be a directory")
    inventory: dict[str, str] = {}
    for directory, names, files in os.walk(artifact_root, followlinks=False):
        directory_path = Path(directory)
        for name in names:
            candidate = directory_path / name
            metadata = os.lstat(candidate)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise ValueError(
                    "Stage 6 artifact inventory contains a symlink or special entry: "
                    f"{candidate}"
                )
        for name in files:
            candidate = directory_path / name
            metadata = os.lstat(candidate)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise ValueError(
                    "Stage 6 artifact inventory contains a symlink or special entry: "
                    f"{candidate}"
                )
            relative = candidate.relative_to(artifact_root).as_posix()
            inventory[relative] = sha256_file(candidate)
    if not inventory:
        raise ValueError("Stage 6 artifact inventory is empty")
    return dict(sorted(inventory.items()))


def validate_stage6_pilot_manifest(pilot_manifest: str | Path) -> dict[str, object]:
    """Recompute every trusted Stage 6 input and published artifact digest."""

    source = _regular_file_nofollow(Path(pilot_manifest), "Stage 6 pilot manifest")
    try:
        payload = json.loads(source.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Stage 6 pilot manifest is not readable JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("Stage 6 pilot manifest must contain an object")
    if (
        payload.get("schema_version") != 1
        or payload.get("stage") != STAGE6
        or payload.get("classification") != PASS
        or payload.get("second_rg_enabled") is not False
    ):
        raise ValueError("Stage 6 pilot manifest is not a passing frozen record")

    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Stage 6 provenance is missing")
    expected_config = "config/hard_goal/stage6_pilot_v1.toml"
    expected_design = "config/hard_goal/design_v1.toml"
    if provenance.get("config_path") != expected_config:
        raise ValueError("Stage 6 config provenance path is not trusted")
    if provenance.get("design_path") != expected_design:
        raise ValueError("Stage 6 design provenance path is not trusted")
    config_path = _regular_file_nofollow(TRACK_ROOT / expected_config, "Stage 6 config")
    design_path = _regular_file_nofollow(TRACK_ROOT / expected_design, "Stage 6 design")
    loaded_config = load_stage6_config(config_path)
    if loaded_config.design != design_path:
        raise ValueError("Stage 6 config does not bind the declared design")
    config_hash = sha256_file(config_path)
    design_hash = sha256_file(design_path)
    if provenance.get("config_sha256") != config_hash:
        raise ValueError("Stage 6 config hash mismatch")
    if provenance.get("design_sha256") != design_hash:
        raise ValueError("Stage 6 design hash mismatch")

    declared_sources = provenance.get("source_sha256")
    if not isinstance(declared_sources, dict) or set(declared_sources) != set(
        STAGE6_TRUSTED_SOURCE_PATHS
    ):
        raise ValueError("Stage 6 source provenance inventory is incomplete")
    source_hashes: dict[str, str] = {}
    for relative in STAGE6_TRUSTED_SOURCE_PATHS:
        path = _regular_file_nofollow(TRACK_ROOT / relative, f"Stage 6 source {relative}")
        digest = sha256_file(path)
        if declared_sources.get(relative) != digest:
            raise ValueError(f"Stage 6 source hash mismatch: {relative}")
        source_hashes[relative] = digest

    artifact_root_value = payload.get("artifact_root")
    if (
        not isinstance(artifact_root_value, str)
        or not artifact_root_value
        or Path(artifact_root_value).is_absolute()
        or ".." in Path(artifact_root_value).parts
    ):
        raise ValueError("Stage 6 artifact root is invalid")
    artifact_root = Path(os.path.abspath(source.parent / artifact_root_value))
    try:
        artifact_root.relative_to(source.parent)
    except ValueError as error:
        raise ValueError("Stage 6 artifact root escapes the manifest directory") from error
    artifacts = _stage6_artifact_inventory(artifact_root)
    if payload.get("artifacts") != artifacts:
        raise ValueError("Stage 6 artifact inventory or hash mismatch")
    expected_artifact_names = {
        "equilibration.json",
        "power.json",
        "protocol.json",
        "resources.json",
        "selection.json",
    }
    if set(artifacts) != expected_artifact_names:
        raise ValueError("Stage 6 artifact inventory is not the complete trusted set")

    def artifact_payload(name: str) -> dict[str, object]:
        path = _regular_file_nofollow(
            artifact_root / name,
            f"Stage 6 artifact {name}",
        )
        try:
            value = json.loads(path.read_text(encoding="ascii"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Stage 6 artifact {name} is not readable JSON") from error
        if not isinstance(value, dict):
            raise ValueError(f"Stage 6 artifact {name} must contain an object")
        return value

    artifact_bindings = {
        "equilibration.json": payload.get("equilibration"),
        "power.json": payload.get("power"),
        "resources.json": payload.get("resources"),
        "selection.json": payload.get("selection"),
        "protocol.json": {
            "second_rg_enabled": payload.get("second_rg_enabled"),
            "temperatures_by_length": payload.get("temperatures_by_length"),
            "sampling": payload.get("sampling"),
            "thresholds": payload.get("thresholds"),
            "seeds": payload.get("seeds"),
        },
    }
    for name, expected in artifact_bindings.items():
        if artifact_payload(name) != expected:
            raise ValueError(f"Stage 6 artifact {name} disagrees with manifest evidence")

    hashes = payload.get("hashes")
    expected_hashes = {
        "config": config_hash,
        "design": design_hash,
        "sources": sha256_bytes(canonical_json_bytes(source_hashes)),
        "artifacts": sha256_bytes(canonical_json_bytes(artifacts)),
    }
    if hashes != expected_hashes:
        raise ValueError("Stage 6 aggregate hash provenance mismatch")
    return payload


def freeze_production_candidate(
    pilot_manifest: str | Path,
    output: str | Path,
) -> dict[str, object]:
    """Freeze measured Stage 6 evidence, refusing every unresolved gate."""

    source = Path(pilot_manifest)
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite production candidate: {destination}")
    payload = validate_stage6_pilot_manifest(source)
    if payload.get("schema_version") != 1 or payload.get("stage") != STAGE6:
        raise ValueError("pilot manifest is not Stage 6 schema version 1")
    if payload.get("classification") != PASS:
        raise ValueError("pilot classification must be PASS")
    if payload.get("second_rg_enabled") is not False:
        raise ValueError("second RG must remain disabled for the production candidate")

    equilibration = _freeze_table(payload, "equilibration")
    selection = _freeze_table(payload, "selection")
    power = _freeze_table(payload, "power")
    resources = _freeze_table(payload, "resources")
    thresholds = _freeze_table(payload, "thresholds")
    sampling = _freeze_table(payload, "sampling")
    seeds = _freeze_table(payload, "seeds")
    hashes = _freeze_table(payload, "hashes")
    provenance = _freeze_table(payload, "provenance")
    artifacts = _freeze_table(payload, "artifacts")
    temperatures = _freeze_table(payload, "temperatures_by_length")

    if thresholds.get("provisional") is not False:
        raise ValueError("provisional thresholds cannot be frozen")
    minimum_round_trips = int(
        _freeze_positive(thresholds.get("minimum_round_trips"), "minimum round trips")
    )
    if equilibration.get("passed") is not True:
        raise ValueError("equilibration did not pass")
    if int(
        _freeze_positive(equilibration.get("round_trips_min"), "round trips")
    ) < minimum_round_trips:
        raise ValueError("round trips are below the measured production threshold")
    if _freeze_positive(
        equilibration.get("swap_acceptance_min"), "swap acceptance"
    ) < _freeze_positive(thresholds.get("swap_bottleneck"), "swap bottleneck"):
        raise ValueError("swap acceptance is below the bottleneck threshold")
    if _freeze_positive(equilibration.get("rhat_max"), "R-hat") > _freeze_positive(
        thresholds.get("maximum_rhat"), "maximum R-hat"
    ):
        raise ValueError("R-hat exceeds the production threshold")
    if _freeze_positive(equilibration.get("ess_min"), "ESS") < _freeze_positive(
        thresholds.get("minimum_ess"), "minimum ESS"
    ):
        raise ValueError("ESS is below the production threshold")

    if selection.get("mps_beats_conditioned_linear") is not True:
        raise ValueError("MPS did not beat the conditioned linear baseline")
    if selection.get("route") not in {"C", "B"}:
        raise ValueError("selected route is invalid")
    if selection.get("template") not in {"cube", "cross"}:
        raise ValueError("selected template is invalid")
    if selection.get("chi") not in {2, 4, 8}:
        raise ValueError("selected chi is invalid")
    if power.get("sufficient") is not True:
        raise ValueError("disorder-sample power is insufficient")
    j_counts = power.get("j_counts")
    if not isinstance(j_counts, dict) or int(j_counts.get("45", 0)) < 1:
        raise ValueError("power schedule must include L=45")

    wall_seconds = _freeze_positive(resources.get("wall_seconds"), "wall seconds")
    projected_wall = _freeze_positive(
        resources.get("projected_l45_segment_seconds"),
        "projected L=45 segment seconds",
    )
    if wall_seconds > 86_400 or projected_wall > min(wall_seconds, 86_400):
        raise ValueError("projected L=45 segment does not fit the 24-hour limit")
    requested_memory = _freeze_positive(
        resources.get("memory_bytes"), "requested memory"
    )
    projected_memory = _freeze_positive(
        resources.get("projected_peak_memory_bytes"), "projected memory"
    )
    if requested_memory / projected_memory < 1.5:
        raise ValueError("memory margin is below 1.5x")
    projected_output = _freeze_positive(
        resources.get("projected_output_bytes"), "projected output"
    )
    reserved_output = _freeze_positive(
        resources.get("reserved_output_bytes"), "reserved output"
    )
    if reserved_output / projected_output < 1.5:
        raise ValueError("output margin is below 1.5x")

    if "45" not in temperatures or not isinstance(temperatures["45"], list):
        raise ValueError("temperature arrays must include L=45")
    for name, digest in hashes.items():
        if not isinstance(digest, str) or len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ValueError(f"invalid source/config hash: {name}")

    candidate = {
        "schema_version": 1,
        "classification": PASS,
        "created_at": _utc_now(),
        "pilot_manifest": _display_path(source.resolve()),
        "pilot_manifest_sha256": sha256_file(source),
        "artifact_root": payload["artifact_root"],
        "artifacts": artifacts,
        "provenance": provenance,
        "temperatures_by_length": temperatures,
        "sampling": sampling,
        "equilibration": equilibration,
        "selection": selection,
        "power": power,
        "resources": resources,
        "thresholds": thresholds,
        "seeds": seeds,
        "hashes": hashes,
        "second_rg_enabled": False,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            json.dump(_json_safe(candidate), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return candidate


@dataclass(frozen=True)
class Stage5Config:
    source: Path
    design: Path
    second_rg: bool
    l2_betas: tuple[float, ...]
    l2_seeds: tuple[int, ...]
    l2_samples: int
    l3_betas: tuple[float, ...]
    l3_seeds: tuple[int, ...]
    l3_epsilon: float
    pt_lengths: tuple[int, ...]
    pt_betas: tuple[float, ...]
    chain_pairs: int
    pt_sweeps: int
    biased_smoke_length: int
    biased_smoke_sweeps: int
    pt_seed: int
    templates: tuple[str, ...]
    routes: tuple[str, ...]
    chis: tuple[int, ...]
    vmcrg_disorder_samples: int
    vmcrg_pool_size: int
    vmcrg_training_steps: int
    vmcrg_learning_rate: float
    vmcrg_gradient_clip: float
    vmcrg_epsilon: float
    vmcrg_seed: int
    backends: tuple[str, ...]
    benchmark_length: int
    benchmark_temperatures: int
    benchmark_samples: int
    benchmark_walkers: int
    benchmark_sweeps: int
    benchmark_seed: int
    l2_absolute_tolerance: float
    l2_standard_errors: float
    l3_energy_tolerance: float
    detailed_balance_tolerance: float
    rg_cache_tolerance: float
    symmetry_tolerance: float
    gradient_tolerance: float

    def public_parameters(self) -> dict[str, object]:
        return {
            "second_rg": self.second_rg,
            "l2_betas": list(self.l2_betas),
            "l2_seeds": list(self.l2_seeds),
            "l2_samples": self.l2_samples,
            "l3_betas": list(self.l3_betas),
            "l3_seeds": list(self.l3_seeds),
            "pt_lengths": list(self.pt_lengths),
            "pt_betas": list(self.pt_betas),
            "chain_pairs": self.chain_pairs,
            "pt_sweeps": self.pt_sweeps,
            "templates": list(self.templates),
            "routes": list(self.routes),
            "chis": list(self.chis),
            "vmcrg_disorder_samples": self.vmcrg_disorder_samples,
            "vmcrg_pool_size": self.vmcrg_pool_size,
            "vmcrg_training_steps": self.vmcrg_training_steps,
            "backends": list(self.backends),
        }


def load_stage5_config(path: str | Path) -> Stage5Config:
    source = Path(path).resolve()
    with source.open("rb") as handle:
        raw = tomllib.load(handle)
    _require_exact_keys(
        raw,
        {
            "schema_version",
            "stage",
            "classification_scope",
            "second_rg",
            "sources",
            "exact",
            "parallel_tempering",
            "vmcrg",
            "backends",
            "tolerances",
        },
        "stage5 top level",
    )
    _expect_equal(raw["schema_version"], 1, "schema_version")
    _expect_equal(raw["stage"], STAGE5, "stage")
    _expect_equal(
        raw["classification_scope"],
        "exact_and_small_3d_validation",
        "classification_scope",
    )
    _expect_equal(raw["second_rg"], False, "second_rg")
    sources = _table(raw, "sources")
    exact = _table(raw, "exact")
    pt = _table(raw, "parallel_tempering")
    vmcrg = _table(raw, "vmcrg")
    backends = _table(raw, "backends")
    tolerances = _table(raw, "tolerances")
    _require_exact_keys(sources, {"hard_goal_design"}, "stage5 sources")
    _require_exact_keys(
        exact,
        {
            "l2_betas",
            "l2_seeds",
            "l2_samples",
            "l3_betas",
            "l3_seeds",
            "finite_difference_epsilon",
        },
        "stage5 exact",
    )
    _require_exact_keys(
        pt,
        {
            "lengths",
            "betas",
            "chain_pairs",
            "sweeps",
            "biased_smoke_length",
            "biased_smoke_sweeps",
            "seed",
        },
        "stage5 parallel_tempering",
    )
    _require_exact_keys(
        vmcrg,
        {
            "templates",
            "routes",
            "chis",
            "disorder_samples",
            "pool_size",
            "training_steps",
            "learning_rate",
            "gradient_clip",
            "finite_difference_epsilon",
            "seed",
        },
        "stage5 vmcrg",
    )
    _require_exact_keys(
        backends,
        {
            "names",
            "benchmark_length",
            "benchmark_temperatures",
            "benchmark_samples",
            "benchmark_walkers",
            "benchmark_sweeps",
            "seed",
        },
        "stage5 backends",
    )
    _require_exact_keys(
        tolerances,
        {
            "l2_absolute",
            "l2_standard_errors",
            "l3_energy_per_site",
            "detailed_balance",
            "rg_cache",
            "symmetry",
            "gradient",
        },
        "stage5 tolerances",
    )

    fixed = {
        "exact.l2_betas": (exact["l2_betas"], [0.4, 0.8, 0.9, 1.2]),
        "exact.l2_seeds": (
            exact["l2_seeds"],
            [2026073001, 2026073002, 2026073003, 2026073004],
        ),
        "exact.l2_samples": (exact["l2_samples"], 131072),
        "exact.l3_betas": (exact["l3_betas"], [0.55, 1.05]),
        "exact.l3_seeds": (exact["l3_seeds"], [2026073011, 2026073012]),
        "exact.finite_difference_epsilon": (
            exact["finite_difference_epsilon"],
            1e-5,
        ),
        "parallel_tempering.lengths": (pt["lengths"], [6, 9]),
        "parallel_tempering.betas": (
            pt["betas"],
            [0.30, 0.45, 0.60, 0.78, 0.98, 1.20],
        ),
        "parallel_tempering.chain_pairs": (pt["chain_pairs"], 4),
        "parallel_tempering.sweeps": (pt["sweeps"], 12),
        "parallel_tempering.biased_smoke_length": (
            pt["biased_smoke_length"],
            3,
        ),
        "parallel_tempering.biased_smoke_sweeps": (
            pt["biased_smoke_sweeps"],
            1,
        ),
        "parallel_tempering.seed": (pt["seed"], 2026073020),
        "vmcrg.templates": (vmcrg["templates"], ["cube", "cross"]),
        "vmcrg.routes": (vmcrg["routes"], ["C", "B"]),
        "vmcrg.chis": (vmcrg["chis"], [2, 4, 8]),
        "vmcrg.disorder_samples": (vmcrg["disorder_samples"], 3),
        "vmcrg.pool_size": (vmcrg["pool_size"], 24),
        "vmcrg.training_steps": (vmcrg["training_steps"], 1),
        "vmcrg.learning_rate": (vmcrg["learning_rate"], 0.02),
        "vmcrg.gradient_clip": (vmcrg["gradient_clip"], 1.0),
        "vmcrg.finite_difference_epsilon": (
            vmcrg["finite_difference_epsilon"],
            1e-6,
        ),
        "vmcrg.seed": (vmcrg["seed"], 2026073030),
        "backends.names": (
            backends["names"],
            ["reference", "available_accelerator"],
        ),
        "backends.benchmark_length": (backends["benchmark_length"], 3),
        "backends.benchmark_temperatures": (
            backends["benchmark_temperatures"],
            3,
        ),
        "backends.benchmark_samples": (backends["benchmark_samples"], 2),
        "backends.benchmark_walkers": (backends["benchmark_walkers"], 1),
        "backends.benchmark_sweeps": (backends["benchmark_sweeps"], 1),
        "backends.seed": (backends["seed"], 2026073040),
        "tolerances.l2_absolute": (tolerances["l2_absolute"], 2e-3),
        "tolerances.l2_standard_errors": (
            tolerances["l2_standard_errors"],
            5.0,
        ),
        "tolerances.l3_energy_per_site": (
            tolerances["l3_energy_per_site"],
            5e-4,
        ),
        "tolerances.detailed_balance": (
            tolerances["detailed_balance"],
            2e-13,
        ),
        "tolerances.rg_cache": (tolerances["rg_cache"], 0.0),
        "tolerances.symmetry": (tolerances["symmetry"], 5e-13),
        "tolerances.gradient": (tolerances["gradient"], 2e-6),
    }
    for name, (actual, expected) in fixed.items():
        _expect_equal(actual, expected, name)

    positive_integer_names = (
        (exact, "l2_samples"),
        (pt, "chain_pairs"),
        (pt, "sweeps"),
        (pt, "biased_smoke_length"),
        (pt, "biased_smoke_sweeps"),
        (vmcrg, "disorder_samples"),
        (vmcrg, "pool_size"),
        (vmcrg, "training_steps"),
        (backends, "benchmark_length"),
        (backends, "benchmark_temperatures"),
        (backends, "benchmark_samples"),
        (backends, "benchmark_walkers"),
        (backends, "benchmark_sweeps"),
    )
    for table, name in positive_integer_names:
        if _integer(table[name], name) < 1:
            raise ValueError(f"{name} must be positive")

    return Stage5Config(
        source=source,
        design=_resolve_fixed_source(
            sources["hard_goal_design"],
            "config/hard_goal/design_v1.toml",
            "hard_goal_design",
        ),
        second_rg=False,
        l2_betas=tuple(float(value) for value in exact["l2_betas"]),
        l2_seeds=tuple(int(value) for value in exact["l2_seeds"]),
        l2_samples=int(exact["l2_samples"]),
        l3_betas=tuple(float(value) for value in exact["l3_betas"]),
        l3_seeds=tuple(int(value) for value in exact["l3_seeds"]),
        l3_epsilon=_finite_float(
            exact["finite_difference_epsilon"],
            "exact.finite_difference_epsilon",
        ),
        pt_lengths=tuple(int(value) for value in pt["lengths"]),
        pt_betas=tuple(float(value) for value in pt["betas"]),
        chain_pairs=int(pt["chain_pairs"]),
        pt_sweeps=int(pt["sweeps"]),
        biased_smoke_length=int(pt["biased_smoke_length"]),
        biased_smoke_sweeps=int(pt["biased_smoke_sweeps"]),
        pt_seed=_integer(pt["seed"], "parallel_tempering.seed"),
        templates=tuple(str(value) for value in vmcrg["templates"]),
        routes=tuple(str(value) for value in vmcrg["routes"]),
        chis=tuple(int(value) for value in vmcrg["chis"]),
        vmcrg_disorder_samples=int(vmcrg["disorder_samples"]),
        vmcrg_pool_size=int(vmcrg["pool_size"]),
        vmcrg_training_steps=int(vmcrg["training_steps"]),
        vmcrg_learning_rate=_finite_float(
            vmcrg["learning_rate"], "vmcrg.learning_rate"
        ),
        vmcrg_gradient_clip=_finite_float(
            vmcrg["gradient_clip"], "vmcrg.gradient_clip"
        ),
        vmcrg_epsilon=_finite_float(
            vmcrg["finite_difference_epsilon"],
            "vmcrg.finite_difference_epsilon",
        ),
        vmcrg_seed=_integer(vmcrg["seed"], "vmcrg.seed"),
        backends=tuple(str(value) for value in backends["names"]),
        benchmark_length=int(backends["benchmark_length"]),
        benchmark_temperatures=int(backends["benchmark_temperatures"]),
        benchmark_samples=int(backends["benchmark_samples"]),
        benchmark_walkers=int(backends["benchmark_walkers"]),
        benchmark_sweeps=int(backends["benchmark_sweeps"]),
        benchmark_seed=_integer(backends["seed"], "backends.seed"),
        l2_absolute_tolerance=_finite_float(
            tolerances["l2_absolute"], "tolerances.l2_absolute"
        ),
        l2_standard_errors=_finite_float(
            tolerances["l2_standard_errors"],
            "tolerances.l2_standard_errors",
        ),
        l3_energy_tolerance=_finite_float(
            tolerances["l3_energy_per_site"],
            "tolerances.l3_energy_per_site",
        ),
        detailed_balance_tolerance=_finite_float(
            tolerances["detailed_balance"], "tolerances.detailed_balance"
        ),
        rg_cache_tolerance=_finite_float(
            tolerances["rg_cache"], "tolerances.rg_cache"
        ),
        symmetry_tolerance=_finite_float(
            tolerances["symmetry"], "tolerances.symmetry"
        ),
        gradient_tolerance=_finite_float(
            tolerances["gradient"], "tolerances.gradient"
        ),
    )


def classify_stage5(
    *,
    exact_passed: bool,
    pt_passed: bool,
    rg_passed: bool,
    vmcrg_finite: bool,
    tt_improved: bool,
    resources_passed: bool,
) -> dict[str, object]:
    failed: list[str] = []
    for name, passed in (
        ("exact", exact_passed),
        ("parallel_tempering", pt_passed),
        ("rg", rg_passed),
        ("vmcrg_finite", vmcrg_finite),
        ("resources", resources_passed),
    ):
        if not passed:
            failed.append(name)
    if failed:
        return {"classification": CORRECTNESS_FAILURE, "failed_gates": failed}
    if not tt_improved:
        return {
            "classification": SCIENTIFIC_NEGATIVE,
            "failed_gates": ["tt_improvement"],
        }
    return {"classification": PASS, "failed_gates": []}


_STAGE5_ARTIFACTS = {
    "exact": "exact.json",
    "pt": "pt.json",
    "rg": "rg.json",
    "vmcrg": "vmcrg.json",
    "resources": "resources.json",
}


def validate_stage5_manifest(path: str | Path) -> StageManifest:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="ascii"))
    if payload.get("stage") != STAGE5:
        raise ValueError("manifest is not Stage 5")
    if payload.get("second_rg_enabled") is not False:
        raise ValueError("second RG must remain disabled in Stage 5")
    artifacts = payload.get("artifacts")
    hashes = payload.get("hashes")
    if not isinstance(artifacts, dict) or not isinstance(hashes, dict):
        raise ValueError("Stage 5 manifest artifacts/hashes are invalid")
    if artifacts != _STAGE5_ARTIFACTS:
        raise ValueError("Stage 5 manifest artifact inventory is incomplete")
    for relative in _STAGE5_ARTIFACTS.values():
        artifact = manifest_path.parent / relative
        if not artifact.is_file():
            raise FileNotFoundError(f"missing Stage 5 evidence file: {relative}")
        key = f"artifact:{relative}"
        if hashes.get(key) != sha256_file(artifact):
            raise ValueError(f"Stage 5 artifact hash mismatch: {relative}")
    return StageManifest(
        stage=STAGE5,
        classification=str(payload.get("classification")),
        failed_gates=tuple(payload.get("failed_gates", ())),
        artifacts=artifacts,
        hashes=hashes,
    )


def _mean_and_standard_error(values: np.ndarray) -> tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    return (
        float(np.mean(array, dtype=np.float64)),
        float(np.std(array, ddof=1) / math.sqrt(array.size)),
    )


def _run_stage5_exact(config: Stage5Config) -> dict[str, object]:
    l2_records: list[dict[str, object]] = []
    for index, (beta, seed) in enumerate(
        zip(config.l2_betas, config.l2_seeds, strict=True),
        start=1,
    ):
        rng = np.random.default_rng(seed)
        bonds = EABonds.sample(2, rng)
        exact = enumerate_l2(beta, bonds)
        left_indices = rng.choice(
            exact.states.shape[0],
            size=config.l2_samples,
            p=exact.probabilities,
        )
        right_indices = rng.choice(
            exact.states.shape[0],
            size=config.l2_samples,
            p=exact.probabilities,
        )
        flat = exact.states.reshape(exact.states.shape[0], -1).astype(np.int16)
        overlap = np.mean(
            flat[left_indices] * flat[right_indices],
            axis=1,
            dtype=np.float64,
        )
        estimates = {
            "energy_per_site": _mean_and_standard_error(
                exact.energies[left_indices].astype(np.float64) / 8.0
            ),
            "q2": _mean_and_standard_error(overlap**2),
            "q4": _mean_and_standard_error(overlap**4),
        }
        expected = {
            "energy_per_site": exact.energy / 8.0,
            "q2": exact.q2,
            "q4": exact.q4,
        }
        metrics: dict[str, object] = {}
        sample_passed = True
        for name, (estimate, standard_error) in estimates.items():
            difference = abs(estimate - expected[name])
            absolute_passed = difference <= config.l2_absolute_tolerance
            sigma_passed = difference <= (
                config.l2_standard_errors * standard_error
                + 16.0 * np.finfo(np.float64).eps
            )
            metrics[name] = {
                "estimate": estimate,
                "standard_error": standard_error,
                "exact": expected[name],
                "absolute_error": difference,
                "absolute_passed": absolute_passed,
                "sigma_passed": sigma_passed,
            }
            sample_passed = sample_passed and absolute_passed and sigma_passed
        l2_records.append(
            {
                "sample": index - 1,
                "beta": beta,
                "seed": seed,
                "bond_sha256": hashlib.sha256(bonds.values.tobytes()).hexdigest(),
                "samples": config.l2_samples,
                "metrics": metrics,
                "passed": sample_passed,
                "sampler": "independent exact-distribution draws",
            }
        )
        print(
            f"stage5 exact L=2 case={index}/{len(config.l2_betas)} "
            f"beta={beta:.3f} "
            f"energy_per_site={estimates['energy_per_site'][0]:.8f} "
            f"q2={estimates['q2'][0]:.8f} "
            f"q4={estimates['q4'][0]:.8f} "
            f"passed={sample_passed}",
            flush=True,
        )

    l3_records: list[dict[str, object]] = []
    for index, (beta, seed) in enumerate(
        zip(config.l3_betas, config.l3_seeds, strict=True),
        start=1,
    ):
        bonds = EABonds.sample(3, np.random.default_rng(seed))
        reference = transfer_l3(beta, bonds)
        plus = transfer_l3(beta + config.l3_epsilon, bonds)
        minus = transfer_l3(beta - config.l3_epsilon, bonds)
        finite_difference = -(
            plus.log_partition - minus.log_partition
        ) / (2.0 * config.l3_epsilon)
        error_per_site = abs(reference.energy - finite_difference) / 27.0
        passed = error_per_site <= config.l3_energy_tolerance
        l3_records.append(
            {
                "sample": index - 1,
                "beta": beta,
                "seed": seed,
                "energy": reference.energy,
                "finite_difference_energy": finite_difference,
                "absolute_error_per_site": error_per_site,
                "passed": passed,
            }
        )
        print(
            f"stage5 exact L=3 case={index}/{len(config.l3_betas)} "
            f"error_per_site={error_per_site:.3e} passed={passed}",
            flush=True,
        )
    return {
        "scope": "exact and estimator correctness; not a Tc estimate",
        "l2": l2_records,
        "l3": l3_records,
        "passed": all(record["passed"] for record in (*l2_records, *l3_records)),
    }


def _round_trip_counts(history: Sequence[np.ndarray]) -> tuple[int, ...]:
    if not history:
        return ()
    tracker = RoundTripTracker(
        n_temperatures=len(history[0]),
        n_replicas=len(history[0]),
    )
    for positions in history:
        tracker.update(positions)
    return tracker.round_trips


def _run_stage5_pt(config: Stage5Config) -> dict[str, object]:
    detail_bonds = EABonds.sample(2, np.random.default_rng(config.pt_seed))
    transition, stationary = enumerate_l2_pt_transition(0.8, detail_bonds)
    flux = stationary[:, None] * transition
    detailed_balance_error = float(np.max(np.abs(flux - flux.T)))
    cases: list[dict[str, object]] = []
    for length_index, length in enumerate(config.pt_lengths):
        bonds = EABonds.sample(
            length,
            np.random.default_rng(config.pt_seed + 100 * (length_index + 1)),
        )
        grid = TemperatureGrid(np.asarray(config.pt_betas, dtype=np.float64))
        edge_attempts = np.zeros(len(grid) - 1, dtype=np.int64)
        edge_accepts = np.zeros(len(grid) - 1, dtype=np.int64)
        energy_mismatches = 0
        independent = True
        round_trips: list[tuple[int, ...]] = []
        energy_per_site_values: list[float] = []
        q2_values: list[float] = []
        for chain in range(config.chain_pairs):
            base_seed = config.pt_seed + 10_000 * length + 100 * chain
            left = SingleReplicaLadder.random(bonds, grid, seed=base_seed + 1)
            right = SingleReplicaLadder.random(bonds, grid, seed=base_seed + 2)
            paired = UnbiasedOverlapPT(left, right)
            paired.run_sweeps(config.pt_sweeps)
            independent = independent and not np.shares_memory(left.spins, right.spins)
            for ladder in (left, right):
                edge_attempts += ladder.swap_attempts
                edge_accepts += ladder.swap_accepts
                round_trips.append(_round_trip_counts(ladder.position_history))
                energy_per_site_values.extend(
                    float(value) / float(length**3) for value in ladder.energies
                )
                for temperature_index in range(len(grid)):
                    if ladder.energies[temperature_index] != energy(
                        ladder.spins[temperature_index], bonds
                    ):
                        energy_mismatches += 1
            q2_values.extend(
                float(np.mean(pair.a * pair.b, dtype=np.float64) ** 2)
                for pair in paired.measure_pairs()
            )
        acceptance = np.divide(
            edge_accepts,
            edge_attempts,
            out=np.zeros_like(edge_accepts, dtype=np.float64),
            where=edge_attempts > 0,
        )
        case_passed = bool(
            independent
            and energy_mismatches == 0
            and np.all(edge_attempts > 0)
            and np.all(np.isfinite(acceptance))
        )
        energy_per_site_mean = float(np.mean(energy_per_site_values))
        q2_mean = float(np.mean(q2_values))
        round_trip_total = sum(sum(values) for values in round_trips)
        cases.append(
            {
                "length": length,
                "chain_pairs": config.chain_pairs,
                "sweeps": config.pt_sweeps,
                "edge_attempts": edge_attempts.tolist(),
                "edge_acceptance": acceptance.tolist(),
                "round_trips": [list(values) for values in round_trips],
                "energy_cache_mismatches": energy_mismatches,
                "replicas_independent": independent,
                "energy_per_site_mean": energy_per_site_mean,
                "q2_mean": q2_mean,
                "equilibrium_claim": False,
                "passed": case_passed,
            }
        )
        print(
            f"stage5 PT L={length} chains={config.chain_pairs} "
            f"sweeps={config.pt_sweeps} "
            f"energy_per_site={energy_per_site_mean:.8f} "
            f"q2={q2_mean:.8f} "
            "swap_acceptance="
            f"{np.array2string(acceptance, precision=3, separator=',')} "
            f"round_trips={round_trip_total} passed={case_passed}",
            flush=True,
        )

    smoke_length = config.biased_smoke_length
    smoke_rng = np.random.default_rng(config.pt_seed + 900_000)
    smoke_bonds = EABonds.sample(smoke_length, smoke_rng)
    smoke_encoder = TemplateEncoder("cube", True, 1)
    smoke_tt = SymmetricLocalTT(
        LocalTensorTrain.random(smoke_encoder.token_count, 2, config.pt_seed + 7),
        smoke_encoder,
    )
    smoke_bias = OverlapBias(
        BiasRoute.B_CONDITIONED_TT,
        None,
        np.empty(0),
        smoke_tt,
    )

    def mps_bias_energy(left: np.ndarray, right: np.ndarray) -> float:
        coarse = block_majority_3d(left * right)
        return smoke_bias.value(coarse, smoke_bonds, smoke_encoder)

    smoke_grid = TemperatureGrid(np.asarray((0.45, 0.9), dtype=np.float64))
    smoke = BiasedPairLadder.random(
        smoke_bonds,
        smoke_grid,
        bias_energy=mps_bias_energy,
        seed=config.pt_seed + 8,
    )
    smoke.run_sweeps(config.biased_smoke_sweeps)
    smoke_energy_mismatches = 0
    smoke_bias_error = 0.0
    for temperature_index in range(len(smoke_grid)):
        expected_energy = energy(
            smoke.spins_a[temperature_index], smoke_bonds
        ) + energy(smoke.spins_b[temperature_index], smoke_bonds)
        smoke_energy_mismatches += int(
            expected_energy != smoke.energies[temperature_index]
        )
        smoke_bias_error = max(
            smoke_bias_error,
            abs(
                mps_bias_energy(
                    smoke.spins_a[temperature_index],
                    smoke.spins_b[temperature_index],
                )
                - smoke.bias_values[temperature_index]
            ),
        )
    biased_passed = bool(
        smoke_energy_mismatches == 0
        and smoke_bias_error <= config.symmetry_tolerance
    )
    return {
        "scope": "small reference PT mechanics; no equilibration or Tc claim",
        "detailed_balance_error": detailed_balance_error,
        "detailed_balance_passed": (
            detailed_balance_error <= config.detailed_balance_tolerance
        ),
        "unbiased_cases": cases,
        "biased_mps_pair": {
            "length": smoke_length,
            "sweeps": config.biased_smoke_sweeps,
            "update_mode": smoke.update_mode,
            "energy_cache_mismatches": smoke_energy_mismatches,
            "maximum_bias_cache_error": smoke_bias_error,
            "passed": biased_passed,
        },
        "passed": bool(
            detailed_balance_error <= config.detailed_balance_tolerance
            and all(case["passed"] for case in cases)
            and biased_passed
        ),
    }


def _run_stage5_rg(config: Stage5Config) -> dict[str, object]:
    rng = np.random.default_rng(config.vmcrg_seed + 500_000)
    q = rng.choice(np.asarray((-1, 1), dtype=np.int8), size=(9, 9, 9))
    maximum_origin_error = 0
    for origin in itertools.product(range(3), repeat=3):
        state = MajorityRG3D(q, levels=1, origin=origin)
        maximum_origin_error = max(
            maximum_origin_error,
            int(
                np.max(
                    np.abs(
                        state.coarse.astype(np.int16)
                        - block_majority_3d(q, origin=origin).astype(np.int16)
                    )
                )
            ),
        )
    incremental = MajorityRG3D(q, levels=1, origin=(2, 1, 0))
    for _ in range(100):
        site = tuple(int(rng.integers(9)) for _ in range(3))
        incremental.commit(incremental.proposal(site))
        incremental.assert_consistent()
    incremental_error = int(
        np.max(
            np.abs(
                incremental.coarse.astype(np.int16)
                - block_majority_3d(
                    incremental.q,
                    origin=(2, 1, 0),
                ).astype(np.int16)
            )
        )
    )

    bonds = EABonds.sample(9, rng)
    symmetry_error = 0.0
    token_action_errors = 0
    for kind in config.templates:
        encoder = TemplateEncoder(kind, True, 1)
        coarse = block_majority_3d(q)
        tokens = encoder.encode(coarse, bonds, (0, 0, 0))
        transforms = cubic_transforms()
        sequential = encoder.transform_tokens(
            encoder.transform_tokens(tokens, transforms[11]),
            transforms[29],
        )
        composed = encoder.transform_tokens(
            tokens,
            transforms[29].compose(transforms[11]),
        )
        token_action_errors += int(not np.array_equal(sequential, composed))
        model = SymmetricLocalTT(
            LocalTensorTrain.random(
                encoder.token_count,
                2,
                config.vmcrg_seed + 600_000 + encoder.token_count,
            ),
            encoder,
        )
        reference = model.value(tokens)
        symmetry_error = max(
            symmetry_error,
            *(abs(model.value(image) - reference) for image in encoder.symmetry_images(tokens)),
            abs(model.value(encoder.flip_q_tokens(tokens)) - reference),
        )

    cache_encoder = TemplateEncoder("cube", True, 1)
    cache_tt = SymmetricLocalTT(
        LocalTensorTrain.random(
            cache_encoder.token_count,
            2,
            config.vmcrg_seed + 700_000,
        ),
        cache_encoder,
    )
    cache_bias = OverlapBias(
        BiasRoute.B_CONDITIONED_TT,
        None,
        np.empty(0),
        cache_tt,
    )
    cache = LocalBiasCache(
        block_majority_3d(q),
        bonds,
        cache_encoder,
        cache_bias,
    )
    maximum_bias_delta_error = 0.0
    for _ in range(20):
        site = tuple(int(rng.integers(3)) for _ in range(3))
        proposal = cache.proposal(site)
        maximum_bias_delta_error = max(
            maximum_bias_delta_error,
            abs(proposal.delta - cache.full_delta(site)),
        )
        if float(rng.random()) < 0.5:
            cache.commit(proposal)
        cache.assert_consistent()
    passed = bool(
        maximum_origin_error <= config.rg_cache_tolerance
        and incremental_error <= config.rg_cache_tolerance
        and maximum_bias_delta_error <= 1e-10
        and token_action_errors == 0
        and symmetry_error <= config.symmetry_tolerance
        and not config.second_rg
    )
    print(
        "stage5 RG origins=27 incremental=100 "
        f"incremental_cache_error={incremental_error} "
        "bias_proposals=20 "
        f"bias_cache_error={maximum_bias_delta_error:.3e} "
        f"passed={passed}",
        flush=True,
    )
    return {
        "scope": "one 3x3x3 majority RG only",
        "second_rg_enabled": False,
        "origin_count": 27,
        "maximum_origin_error": maximum_origin_error,
        "incremental_cache_error": incremental_error,
        "bias_cache_proposals": 20,
        "maximum_bias_delta_error": maximum_bias_delta_error,
        "token_action_errors": token_action_errors,
        "maximum_symmetry_error": symmetry_error,
        "passed": passed,
    }


def _negative_softmax(values: np.ndarray) -> np.ndarray:
    shifted = -np.asarray(values, dtype=np.float64)
    shifted -= float(np.max(shifted))
    weights = np.exp(shifted)
    return weights / float(np.sum(weights, dtype=np.float64))


def _uniform_tv(probability: np.ndarray) -> float:
    values = np.asarray(probability, dtype=np.float64)
    return 0.5 * float(np.sum(np.abs(values - 1.0 / values.size)))


def _tt_validation_cell(
    config: Stage5Config,
    *,
    kind: str,
    route: str,
    chi: int,
    seed: int,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    encoder = TemplateEncoder(kind, True, 1)
    selected_route = BiasRoute(route)
    basis = (
        LinearFeatureBasis.cube_v1()
        if selected_route is BiasRoute.C_LINEAR_PLUS_TT
        else None
    )
    coefficients = (
        np.zeros(len(basis.features), dtype=np.float64)
        if basis is not None
        else np.empty(0, dtype=np.float64)
    )
    pools: list[np.ndarray] = []
    for _ in range(config.vmcrg_disorder_samples):
        bonds = EABonds.sample(9, rng)
        base = encoder.encode(
            np.ones((3, 3, 3), dtype=np.int8),
            bonds,
            (0, 0, 0),
        )
        tokens = np.repeat(base[None, :], config.vmcrg_pool_size, axis=0)
        tokens[:, np.asarray(encoder.q_token_indices)] = rng.choice(
            np.asarray((-1, 1), dtype=np.int8),
            size=(config.vmcrg_pool_size, encoder.q_token_count),
        )
        pools.append(tokens)
    all_tokens = np.concatenate(pools, axis=0)

    teacher_model = LocalTensorTrain.random(encoder.token_count, chi, seed + 1)
    teacher = SymmetricLocalTT(teacher_model, encoder)
    initial_teacher_values = teacher.values(all_tokens)
    scale = 0.4 / max(float(np.std(initial_teacher_values)), 1e-8)
    teacher.model.cores[0] *= scale
    physical_by_j = [teacher.values(tokens) for tokens in pools]

    candidate_model = LocalTensorTrain.from_arrays(teacher.model.save_arrays())
    candidate_model.cores[0] *= -0.5
    candidate = SymmetricLocalTT(candidate_model, encoder)
    uniform_weights = np.full(
        all_tokens.shape[0],
        1.0 / all_tokens.shape[0],
    )

    def metrics(
        model: SymmetricLocalTT | None,
        linear_coefficients: np.ndarray,
    ) -> tuple[float, list[np.ndarray]]:
        probabilities: list[np.ndarray] = []
        tv_values: list[float] = []
        bias = (
            None
            if model is None
            else OverlapBias(
                selected_route,
                basis,
                linear_coefficients,
                model,
            )
        )
        for tokens, physical in zip(pools, physical_by_j, strict=True):
            bias_values = (
                0.0
                if bias is None
                else np.asarray(
                    [bias.local_value(row) for row in tokens],
                    dtype=np.float64,
                )
            )
            probability = _negative_softmax(physical + bias_values)
            probabilities.append(probability)
            tv_values.append(_uniform_tv(probability))
        return float(np.mean(tv_values)), probabilities

    baseline_tv, _ = metrics(None, np.empty(0, dtype=np.float64))
    before_tv, probabilities = metrics(candidate, coefficients)
    maximum_gradient_error = 0.0
    unclipped_norms: list[float] = []
    for training_step in range(config.vmcrg_training_steps):
        biased_weights = np.concatenate(
            [
                probability / config.vmcrg_disorder_samples
                for probability in probabilities
            ]
        )
        gradient = candidate.gradient(all_tokens, uniform_weights).add(
            candidate.gradient(all_tokens, biased_weights).scale(-1.0)
        )
        if basis is None:
            linear_gradient = np.empty(0, dtype=np.float64)
        else:
            feature_matrix = np.asarray(
                [basis.local_features(row, encoder) for row in all_tokens],
                dtype=np.float64,
            )
            linear_gradient = (
                uniform_weights @ feature_matrix
                - biased_weights @ feature_matrix
            )
        gradient_norm = math.sqrt(
            gradient.norm() ** 2
            + float(np.vdot(linear_gradient, linear_gradient).real)
        )
        unclipped_norms.append(gradient_norm)
        if training_step == 0:
            core_index = min(4, len(candidate.model.cores) - 1)
            entry = tuple(0 for _ in range(3))
            epsilon = config.vmcrg_epsilon
            plus = LocalTensorTrain.from_arrays(candidate.model.save_arrays())
            minus = LocalTensorTrain.from_arrays(candidate.model.save_arrays())
            plus.cores[core_index][entry] += epsilon
            minus.cores[core_index][entry] -= epsilon
            plus_tt = SymmetricLocalTT(plus, encoder)
            minus_tt = SymmetricLocalTT(minus, encoder)

            def frozen_objective(model: SymmetricLocalTT) -> float:
                bias = OverlapBias(
                    selected_route,
                    basis,
                    coefficients,
                    model,
                )
                values = np.asarray(
                    [bias.local_value(row) for row in all_tokens],
                    dtype=np.float64,
                )
                return float(
                    uniform_weights @ values - biased_weights @ values
                )

            numeric = (
                frozen_objective(plus_tt) - frozen_objective(minus_tt)
            ) / (2.0 * epsilon)
            maximum_gradient_error = abs(
                gradient.cores[core_index][entry] - numeric
            )
        factor = min(
            1.0,
            config.vmcrg_gradient_clip
            / max(gradient_norm, np.finfo(np.float64).tiny),
        )
        candidate.model = LocalTensorTrain(
            [
                core - config.vmcrg_learning_rate * factor * derivative
                for core, derivative in zip(
                    candidate.model.cores,
                    gradient.cores,
                    strict=True,
                )
            ]
        )
        coefficients = coefficients - (
            config.vmcrg_learning_rate * factor * linear_gradient
        )
        _, probabilities = metrics(candidate, coefficients)
    after_tv, _ = metrics(candidate, coefficients)
    parameter_norm = math.sqrt(
        candidate.model.parameter_norm**2
        + float(np.vdot(coefficients, coefficients).real)
    )
    finite = bool(
        all(
            math.isfinite(value)
            for value in (
                baseline_tv,
                before_tv,
                after_tv,
                maximum_gradient_error,
                parameter_norm,
                *unclipped_norms,
            )
        )
        and np.all(np.isfinite(coefficients))
    )
    return {
        "template": kind,
        "route": selected_route.value,
        "chi": chi,
        "tt_initialization_seed": seed + 1,
        "parameter_count": candidate.model.parameter_count + coefficients.size,
        "linear_feature_names": [] if basis is None else list(basis.names),
        "linear_coefficients": coefficients.tolist(),
        "bias_composition": (
            "linear_plus_conditioned_tt"
            if basis is not None
            else "conditioned_tt"
        ),
        "disorder_samples": config.vmcrg_disorder_samples,
        "pool_size": config.vmcrg_pool_size,
        "training_steps": config.vmcrg_training_steps,
        "baseline_tv": baseline_tv,
        "initial_mps_tv": before_tv,
        "trained_mps_tv": after_tv,
        "unclipped_gradient_norms": unclipped_norms,
        "maximum_gradient_error": maximum_gradient_error,
        "parameter_norm": parameter_norm,
        "finite": finite,
        "improves_baseline": after_tv < baseline_tv - 1e-8,
        "training_nonregression": after_tv <= before_tv + 1e-8,
    }


def _run_stage5_vmcrg(config: Stage5Config) -> dict[str, object]:
    cells: list[dict[str, object]] = []
    unsupported: list[dict[str, str]] = []
    cell_index = 0
    for kind in config.templates:
        routes = ("C", "B") if kind == "cube" else ("B",)
        if any(route not in config.routes for route in routes):
            raise ValueError(f"Stage 5 routes for {kind} are not configured")
        if kind != "cube" and "C" in config.routes:
            unsupported.append(
                {
                    "template": kind,
                    "route": "C",
                    "reason": (
                        "the preregistered five-feature conditioned linear "
                        "baseline is defined on cube tokens"
                    ),
                }
            )
        for chi in config.chis:
            cell_index += 1
            initialization_seed = config.vmcrg_seed + 1000 * cell_index
            for route in routes:
                cell = _tt_validation_cell(
                    config,
                    kind=kind,
                    route=route,
                    chi=chi,
                    seed=initialization_seed,
                )
                cells.append(cell)
                print(
                    f"stage5 VMCRG template={kind} route={route} chi={chi} "
                    f"tv={cell['trained_mps_tv']:.4g} "
                    f"grad={cell['unclipped_gradient_norms'][-1]:.3e} "
                    f"improved={cell['improves_baseline']}",
                    flush=True,
                )
    finite = all(
        cell["finite"]
        and cell["maximum_gradient_error"] <= config.gradient_tolerance
        for cell in cells
    )
    improved = any(
        cell["route"] == "C"
        and cell["improves_baseline"]
        and cell["training_nonregression"]
        for cell in cells
    )
    return {
        "scope": "synthetic local overlap-field VMCRG representation validation",
        "effective_hamiltonian_note": (
            "The trained object is a local overlap-field effective Hamiltonian "
            "bias, not the original one-replica Hamiltonian."
        ),
        "target": "uniform local coarse-overlap pool",
        "cells": cells,
        "unsupported_combinations": unsupported,
        "finite": finite,
        "tt_improved": improved,
        "classification": PASS if finite and improved else (
            SCIENTIFIC_NEGATIVE if finite else CORRECTNESS_FAILURE
        ),
    }


def _run_stage5_resources(config: Stage5Config) -> dict[str, object]:
    case = BackendCase.random(
        length=config.benchmark_length,
        temperatures=config.benchmark_temperatures,
        samples=config.benchmark_samples,
        walkers=config.benchmark_walkers,
        seed=config.benchmark_seed,
    )
    reference = NumpyReferenceBackend(case)
    started = time.perf_counter()
    reference.sweeps(config.benchmark_sweeps)
    reference_seconds = time.perf_counter() - started
    reference_snapshot = reference.resource_snapshot()
    reference_record = {
        **reference_snapshot,
        "sweeps": config.benchmark_sweeps,
        "elapsed_seconds": reference_seconds,
        "proposals": reference.proposed_changes,
        "accepted": reference.accepted_changes,
        "proposals_per_second": (
            reference.proposed_changes / reference_seconds
        ),
    }
    accelerator: dict[str, object]
    accelerator_passed = True
    try:
        from .jax_backend import JaxBatchedBackend

        candidate = JaxBatchedBackend(case)
        candidate_deltas = candidate.all_proposal_deltas()
        reference_oracle = NumpyReferenceBackend(case)
        reference_deltas = reference_oracle.all_proposal_deltas()
        maximum_delta_error = float(
            np.max(np.abs(candidate_deltas - reference_deltas))
        )
        decision_rng = np.random.default_rng(config.benchmark_seed + 1)
        uniforms = decision_rng.uniform(
            np.finfo(np.float64).tiny,
            1.0,
            size=case.spins.shape,
        )
        decision_mismatches = int(
            np.count_nonzero(
                candidate.accept_decisions(uniforms)
                != reference_oracle.accept_decisions(uniforms)
            )
        )
        accelerator_started = time.perf_counter()
        candidate.sweeps(config.benchmark_sweeps)
        accelerator_seconds = time.perf_counter() - accelerator_started
        accelerator_energies = candidate.measure()["energy"]
        energies_finite = bool(np.all(np.isfinite(accelerator_energies)))
        accelerator_snapshot = candidate.resource_snapshot()
        accelerator_passed = bool(
            maximum_delta_error <= 1e-10
            and decision_mismatches == 0
            and accelerator_snapshot["float64_enabled"]
            and candidate.proposed_changes > 0
            and accelerator_seconds > 0.0
            and energies_finite
        )
        accelerator = {
            "status": "AVAILABLE",
            **accelerator_snapshot,
            "sweeps": config.benchmark_sweeps,
            "elapsed_seconds": accelerator_seconds,
            "proposals": candidate.proposed_changes,
            "accepted": candidate.accepted_changes,
            "proposals_per_second": (
                candidate.proposed_changes / accelerator_seconds
            ),
            "maximum_proposal_delta_error": maximum_delta_error,
            "maximum_accept_decision_mismatches": decision_mismatches,
            "energies_finite": energies_finite,
            "passed": accelerator_passed,
            "performance_claim": False,
        }
    except (ImportError, ModuleNotFoundError) as error:
        accelerator = {
            "status": "UNAVAILABLE_OPTIONAL",
            "reason": str(error),
            "passed": True,
            "performance_claim": False,
        }
    passed = bool(
        reference.proposed_changes > 0
        and reference_seconds > 0.0
        and math.isfinite(reference_record["proposals_per_second"])
        and accelerator_passed
    )
    return {
        "scope": "local Stage 5 resource smoke; not a cluster projection",
        "reference": reference_record,
        "available_accelerator": accelerator,
        "passed": passed,
    }


def _stage5_source_paths(config: Stage5Config) -> dict[str, Path]:
    paths = {
        _display_path(path): path
        for path in (
            config.source,
            config.design,
            TRACK_ROOT / "scripts/hard_goal.py",
            *sorted((TRACK_ROOT / "src/spinglass3d").glob("*.py")),
            *sorted(TRACK_ROOT.glob("tests/test_hg3d_*.py")),
        )
    }
    return dict(sorted(paths.items()))


def run_stage5(config: Path, output: Path) -> StageManifest:
    """Run and immutably publish exact and small-3D Stage 5 evidence."""

    destination = Path(output).resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite Stage 5 output: {destination}")
    stage_config = load_stage5_config(config)
    design = load_design(stage_config.design)
    if (
        design.model.distribution != "iid_pm1"
        or design.model.hamiltonian_sign != -1
        or not design.model.periodic
        or design.rg.block_shape != (3, 3, 3)
    ):
        raise ValueError("Stage 5 design no longer matches the confirmed model")
    source_paths = _stage5_source_paths(stage_config)
    starting_hashes, starting_failures = _hash_sources(source_paths)
    if starting_failures:
        raise FileNotFoundError(
            "Stage 5 source inventory is incomplete: " + ", ".join(starting_failures)
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.stage5-",
            dir=destination.parent,
        )
    )
    overall_started = time.perf_counter()
    try:
        sections: dict[str, dict[str, object]] = {}
        timings: dict[str, float] = {}
        for name, runner in (
            ("exact", _run_stage5_exact),
            ("pt", _run_stage5_pt),
            ("rg", _run_stage5_rg),
            ("vmcrg", _run_stage5_vmcrg),
        ):
            started = time.perf_counter()
            sections[name] = runner(stage_config)
            timings[name] = time.perf_counter() - started
            atomic_write_json(
                staging / _STAGE5_ARTIFACTS[name],
                _json_safe(sections[name]),
            )
            correctness_passed = bool(
                sections[name].get(
                    "finite" if name == "vmcrg" else "passed",
                    False,
                )
            )
            if not correctness_passed:
                raise RuntimeError(f"Stage 5 {name} correctness gate failed")

        resources_started = time.perf_counter()
        resources = _run_stage5_resources(stage_config)
        timings["resources"] = time.perf_counter() - resources_started
        resources["section_seconds"] = timings
        resources["elapsed_seconds_before_manifest"] = (
            time.perf_counter() - overall_started
        )
        atomic_write_json(
            staging / _STAGE5_ARTIFACTS["resources"],
            _json_safe(resources),
        )
        if not resources["passed"]:
            raise RuntimeError("Stage 5 resources correctness gate failed")

        ending_hashes, ending_failures = _hash_sources(source_paths)
        source_integrity = bool(
            not ending_failures and starting_hashes == ending_hashes
        )
        if not source_integrity:
            raise RuntimeError("Stage 5 source integrity gate failed")
        decision = classify_stage5(
            exact_passed=bool(sections["exact"]["passed"]),
            pt_passed=bool(sections["pt"]["passed"]),
            rg_passed=bool(sections["rg"]["passed"]),
            vmcrg_finite=bool(sections["vmcrg"]["finite"]),
            tt_improved=bool(sections["vmcrg"]["tt_improved"]),
            resources_passed=bool(resources["passed"] and source_integrity),
        )
        artifact_hashes = _artifact_hashes(staging)
        expected_artifact_names = set(_STAGE5_ARTIFACTS.values())
        if set(artifact_hashes) != expected_artifact_names:
            raise RuntimeError("Stage 5 evidence inventory changed during execution")
        combined_hashes = {
            **{
                f"source:{name}": digest
                for name, digest in starting_hashes.items()
            },
            **{
                f"artifact:{name}": digest
                for name, digest in artifact_hashes.items()
            },
        }
        manifest = StageManifest(
            stage=STAGE5,
            classification=str(decision["classification"]),
            failed_gates=tuple(decision["failed_gates"]),
            artifacts=_STAGE5_ARTIFACTS,
            hashes=combined_hashes,
        )
        payload = {
            "schema_version": 1,
            **manifest.to_dict(),
            "created_at": _utc_now(),
            "second_rg_enabled": False,
            "scope": "exact and small 3D validation; no Tc or equilibration claim",
            "config": stage_config.public_parameters(),
            "source_integrity": {
                "passed": source_integrity,
                "failures": ending_failures,
            },
        }
        atomic_write_json(staging / "manifest.json", _json_safe(payload))
        validate_stage5_manifest(staging / "manifest.json")
        promotion_hashes = {
            **artifact_hashes,
            "manifest.json": sha256_file(staging / "manifest.json"),
        }
        _verified_promote_directory_no_replace(
            staging,
            destination,
            promotion_hashes,
        )
        published = validate_stage5_manifest(destination / "manifest.json")
        print(
            f"stage5 classification={published.classification} "
            f"output={destination}",
            flush=True,
        )
        return published
    finally:
        if staging.exists():
            shutil.rmtree(staging)
