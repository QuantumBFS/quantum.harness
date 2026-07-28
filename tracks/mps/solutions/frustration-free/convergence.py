#!/usr/bin/env python3
"""Restartable Challenge 81 finite-bath convergence orchestration."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import importlib.util
import inspect
import json
import math
import numbers
import os
from pathlib import Path
import platform
import signal
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable, Sequence

from jsonschema import Draft202012Validator


MODULE_VERSION = "4.0.0"
SOFTWARE_VERSION = "challenge81-frustration-free-2"
PLAN_SCHEMA_VERSION = 1
CELL_SCHEMA_VERSION = 1
ANALYSIS_SCHEMA_VERSION = 1
SOLUTION_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOLUTION_DIR.parents[3]
SOLUTION_RELATIVE_PATH = SOLUTION_DIR.relative_to(REPOSITORY_ROOT).as_posix()
JULIA_PROJECT_RELATIVE_PATH = f"{SOLUTION_RELATIVE_PATH}/julia"
JULIA_DIR = SOLUTION_DIR / "julia"
JULIA_RUNNER = JULIA_DIR / "finite_bath_mps_runner.jl"
LOCAL_WALL_LIMIT_SECONDS = 600
LOCAL_RSS_LIMIT_BYTES = 16 * 1024**3
CHECKPOINT_GRACE_SECONDS = 30.0
CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_WRITER_VERSION = "1.0.0"
JULIA_PROCESS_STARTUP_SECONDS = 35.0
JULIA_PROCESS_BASE_RSS_BYTES = 1024**3
MEMORY_SAFETY_FACTOR = 1.5
WALL_SAFETY_FACTOR = 2.0
N48_VALIDATED_SOLVER_CAPABILITIES: frozenset[tuple[str, str]] = frozenset()
DEFAULT_TOLERANCES = {
    "bath_size": {"name": "bath_observable_absolute_max", "absolute": 5.0e-4},
    "time_step": {"name": "timestep_observable_absolute_max", "absolute": 1.0e-4},
    "maxdim": {"name": "maxdim_observable_absolute_max", "absolute": 1.0e-4},
    "krylov_error": {"name": "local_krylov_error_max", "absolute": 1.0e-8},
    "truncation": {"name": "local_truncation_error_max", "absolute": 1.0e-8},
}
DEFAULT_GRID = {
    "betas": [16.0, 32.0],
    "bath_sizes": [12, 24, 48],
    "time_steps": [0.2, 0.1, 0.05],
    "cutoffs": [1.0e-12],
    "maxdims": [128, 256, 512],
    "tau_fractions": [0.0, 0.25, 0.5, 0.75, 1.0],
}
STAGED_ANCHOR = {"n_bath": 12, "time_step": 0.05, "maxdim": 512}
SCHEMA_PATH = SOLUTION_DIR / "convergence.schema.json"


class ContinuationAvailable(RuntimeError):
    """A runner stopped cooperatively after publishing a fresh checkpoint."""

    def __init__(self, checkpoint: Any):
        super().__init__("validated continuation checkpoint is available")
        self.checkpoint = checkpoint


def _load_local_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SOLUTION_DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bath = _load_local_module("challenge_81_convergence_bath", "bath.py")
acceptance = _load_local_module(
    "challenge_81_convergence_acceptance", "acceptance.py"
)
MODEL = copy.deepcopy(bath.MODEL_DEFINITION["parameters"])


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _digest(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be 64 lowercase hexadecimal digits")
    return value


def _real(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if positive and result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _positive_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} must be a positive integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


def _unique(values: Sequence[Any], name: str) -> list[Any]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence")
    if not values:
        raise ValueError(f"{name} must not be empty")
    result = list(values)
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _source_hashes(julia_project: Path = JULIA_DIR) -> dict[str, str]:
    julia_project.resolve(strict=True)
    source_root = JULIA_DIR
    paths = {
        "acceptance.py": SOLUTION_DIR / "acceptance.py",
        "bath.py": SOLUTION_DIR / "bath.py",
        "convergence.py": Path(__file__),
        "convergence.schema.json": SCHEMA_PATH,
        "model.json": SOLUTION_DIR / "model.json",
        "pyproject.toml": SOLUTION_DIR / "pyproject.toml",
        "uv.lock": SOLUTION_DIR / "uv.lock",
        "finite_bath_mps_runner.jl": source_root / "finite_bath_mps_runner.jl",
        "finite_bath_checkpoint.jl": source_root / "finite_bath_checkpoint.jl",
        "finite_bath_observables.jl": source_root / "finite_bath_observables.jl",
        "finite_bath_purification.jl": source_root / "finite_bath_purification.jl",
    }
    return {name: _sha256_file(path) for name, path in paths.items()}


def _project_hashes(julia_project: Path = JULIA_DIR) -> dict[str, str]:
    project = julia_project.resolve(strict=True)
    return {
        "Project.toml": _sha256_file(project / "Project.toml"),
        "Manifest.toml": _sha256_file(project / "Manifest.toml"),
    }


def validate_artifact_schema(value: Any, definition: str) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
    )
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = ".".join(str(item) for item in first.absolute_path) or "<root>"
        raise ValueError(f"{definition} schema validation failed at {location}: {first.message}")


def _validated_grid(
    *,
    betas: Sequence[float],
    bath_sizes: Sequence[int],
    time_steps: Sequence[float],
    cutoffs: Sequence[float],
    maxdims: Sequence[int],
    tau_fractions: Sequence[float],
) -> dict[str, list[Any]]:
    beta_values = [_real(value, "beta", positive=True) for value in _unique(betas, "betas")]
    bath_values = [
        _positive_integer(value, "bath size")
        for value in _unique(bath_sizes, "bath_sizes")
    ]
    step_values = [
        _real(value, "time_step", positive=True)
        for value in _unique(time_steps, "time_steps")
    ]
    cutoff_values = [
        _real(value, "cutoff") for value in _unique(cutoffs, "cutoffs")
    ]
    if any(value < 0 for value in cutoff_values):
        raise ValueError("cutoff must be nonnegative")
    maxdim_values = [
        _positive_integer(value, "maxdim")
        for value in _unique(maxdims, "maxdims")
    ]
    fractions = [
        _real(value, "tau fraction")
        for value in _unique(tau_fractions, "tau_fractions")
    ]
    if any(value < 0 or value > 1 for value in fractions):
        raise ValueError("tau fractions must lie in [0, 1]")
    if fractions != sorted(fractions):
        raise ValueError("tau fractions must be increasing")
    return {
        "betas": beta_values,
        "bath_sizes": bath_values,
        "time_steps": step_values,
        "cutoffs": cutoff_values,
        "maxdims": maxdim_values,
        "tau_fractions": fractions,
    }


def _cell_input_payload(
    *,
    beta: float,
    n_bath: int,
    time_step: float,
    cutoff: float,
    maxdim: int,
    tau_fractions: list[float],
    bath_artifact: dict[str, Any],
    source_hashes: dict[str, str],
    project_hashes: dict[str, str],
    julia_project: str,
    diagnostic_limits: dict[str, dict[str, Any]],
    solver_capability: dict[str, Any],
) -> dict[str, Any]:
    return {
        "model": {**MODEL, "beta": beta},
        "bath_artifact": bath_artifact,
        "tau_fractions": tau_fractions,
        "solver_settings": {
            "time_step": time_step,
            "cutoff": cutoff,
            "maxdim": maxdim,
            "krylov_expansion_dim": 0,
        },
        "source_sha256": source_hashes,
        "julia_environment_sha256": project_hashes,
        "julia_project": julia_project,
        "diagnostic_limits": diagnostic_limits,
        "solver_capability": solver_capability,
    }


def _nearest_bath_energy(bath_artifact: dict[str, Any]) -> float:
    return min(abs(float(value)) for value in bath_artifact["payload"]["epsilon"])


def _staged_specs(betas: Sequence[float], cutoff: float) -> list[tuple[float, int, float, float, int]]:
    specs: list[tuple[float, int, float, float, int]] = []
    for beta in betas:
        candidates = [
            *((beta, n_bath, 0.05, cutoff, 512) for n_bath in (12, 24, 48)),
            *((beta, 12, time_step, cutoff, 512) for time_step in (0.2, 0.1, 0.05)),
            *((beta, 12, 0.05, cutoff, maxdim) for maxdim in (128, 256, 512)),
        ]
        for candidate in candidates:
            if candidate not in specs:
                specs.append(candidate)
    return specs


def make_plan(
    *,
    betas: Sequence[float] = DEFAULT_GRID["betas"],
    bath_sizes: Sequence[int] | None = None,
    time_steps: Sequence[float] | None = None,
    cutoffs: Sequence[float] = DEFAULT_GRID["cutoffs"],
    maxdims: Sequence[int] | None = None,
    tau_fractions: Sequence[float] = DEFAULT_GRID["tau_fractions"],
    stage: str = "production",
    tolerances: dict[str, dict[str, Any]] | None = None,
    julia_project: str | os.PathLike[str] = JULIA_DIR,
) -> dict[str, Any]:
    """Create a deterministic staged plan, or an explicit pilot/test Cartesian plan."""
    if stage not in {"pilot", "production"}:
        raise ValueError("stage must be 'pilot' or 'production'")
    selected_project = Path(julia_project).resolve(strict=True)
    if not (selected_project / "Project.toml").is_file() or not (
        selected_project / "Manifest.toml"
    ).is_file():
        raise ValueError("selected Julia project must contain Project.toml and Manifest.toml")
    explicit_grid = any(value is not None for value in (bath_sizes, time_steps, maxdims))
    bath_sizes = bath_sizes or DEFAULT_GRID["bath_sizes"]
    time_steps = time_steps or DEFAULT_GRID["time_steps"]
    maxdims = maxdims or DEFAULT_GRID["maxdims"]
    grid = _validated_grid(
        betas=betas,
        bath_sizes=bath_sizes,
        time_steps=time_steps,
        cutoffs=cutoffs,
        maxdims=maxdims,
        tau_fractions=tau_fractions,
    )
    source_hashes = _source_hashes(selected_project)
    project_hashes = _project_hashes(selected_project)
    tolerance_values = copy.deepcopy(tolerances or DEFAULT_TOLERANCES)
    solver_capability = {
        "bath_representation": "direct_star",
        "n_bath_48_execution_validated": False,
        "capability_evidence_sha256": None,
        "policy": (
            "N_b=48 execution is forbidden until chain or approved compressed-MPO "
            "capability evidence is implemented and schema-validated"
        ),
    }
    cells = []
    bath_artifacts = {
        n_bath: bath.make_bath_artifact(
            gamma=MODEL["Gamma"],
            bandwidth=MODEL["D"],
            n_bath=n_bath,
            frequency_grid=[-MODEL["D"], 0.0, MODEL["D"]],
        )
        for n_bath in grid["bath_sizes"]
    }
    if not explicit_grid:
        if len(grid["cutoffs"]) != 1:
            raise ValueError("staged production plan requires exactly one cutoff")
        specs = _staged_specs(grid["betas"], grid["cutoffs"][0])
        grid_kind = "controlled_staged"
    else:
        specs = [
            (beta, n_bath, time_step, cutoff, maxdim)
            for beta in grid["betas"]
            for n_bath in grid["bath_sizes"]
            for time_step in grid["time_steps"]
            for cutoff in grid["cutoffs"]
            for maxdim in grid["maxdims"]
        ]
        grid_kind = "explicit_cartesian"
    for beta, n_bath, time_step, cutoff, maxdim in specs:
        input_payload = _cell_input_payload(
            beta=beta,
            n_bath=n_bath,
            time_step=time_step,
            cutoff=cutoff,
            maxdim=maxdim,
            tau_fractions=grid["tau_fractions"],
            bath_artifact=bath_artifacts[n_bath],
            source_hashes=source_hashes,
            project_hashes=project_hashes,
            julia_project=JULIA_PROJECT_RELATIVE_PATH,
            diagnostic_limits={
                "krylov_error": copy.deepcopy(tolerance_values["krylov_error"]),
                "truncation": copy.deepcopy(tolerance_values["truncation"]),
            },
            solver_capability=solver_capability,
        )
        input_sha256 = _sha256(_canonical_json(input_payload))
        nearest_energy = _nearest_bath_energy(bath_artifacts[n_bath])
        cells.append(
            {
                "cell_id": f"c{len(cells):04d}-{input_sha256[:12]}",
                "input_sha256": input_sha256,
                "parameters": {"beta": beta, "n_bath": n_bath},
                "tau_fractions": copy.deepcopy(grid["tau_fractions"]),
                "solver_settings": copy.deepcopy(input_payload["solver_settings"]),
                "diagnostic_limits": copy.deepcopy(input_payload["diagnostic_limits"]),
                "solver_capability": copy.deepcopy(solver_capability),
                "bath_artifact": copy.deepcopy(bath_artifacts[n_bath]),
                "bath_artifact_sha256": bath_artifacts[n_bath]["sha256"],
                "bath_resolution": {
                    "nearest_absolute_energy": nearest_energy,
                    "temperature": 1.0 / beta,
                    "nearest_energy_over_temperature": nearest_energy * beta,
                },
                "execution_class": (
                    "requires_chain_mapping_optimization"
                    if n_bath == 48
                    else "direct_star_calibration"
                ),
                "provenance": {
                    "source_sha256": copy.deepcopy(source_hashes),
                    "julia_environment_sha256": copy.deepcopy(project_hashes),
                    "julia_project": JULIA_PROJECT_RELATIVE_PATH,
                },
            }
        )
    payload = {
        "artifact_type": "convergence_plan",
        "generator": {"name": "convergence.py", "version": MODULE_VERSION},
        "software_version": SOFTWARE_VERSION,
        "schema_version": PLAN_SCHEMA_VERSION,
        "stage": stage,
        "model": copy.deepcopy(MODEL),
        "grid": {**grid, "kind": grid_kind},
        "tolerances": tolerance_values,
        "execution_environment": {
            "repository_relative_paths": {
                "solution": SOLUTION_RELATIVE_PATH,
                "julia_project": JULIA_PROJECT_RELATIVE_PATH,
            },
            "julia_environment_sha256": copy.deepcopy(project_hashes),
            "source_sha256": copy.deepcopy(source_hashes),
        },
        "bath_resolution_policy": {
            "name": "three_level_nearest_energy_resolution",
            "bath_sizes": [12, 24, 48],
            "finest_ratio_limit": 1.1,
            "requires_strictly_decreasing_nearest_energy": True,
            "requires_three_level_controlled_trend": True,
        },
        "solver_feasibility": {
            "direct_star_mpo": "MPO bond dimension grows with bath size and long-range impurity couplings",
            "n_bath_48": {
                "local_execution_allowed": False,
                "cluster_calibration_required": True,
                "chain_mapping_required": True,
                "status": "planned evidence cell; blocked pending scalable solver optimization",
            },
        },
        "solver_capability": copy.deepcopy(solver_capability),
        "claim_policy": {
            "production_eligible": stage == "production"
            and set(grid["betas"]) == {16.0, 32.0}
            and grid_kind == "controlled_staged",
            "requires_all_axes": ["bath_size", "time_step", "maxdim"],
            "nonmonotonic_timestep_blocks_claim": True,
            "nonmonotonic_controlled_trend_blocks_claim": True,
            "diagnostics_must_pass": True,
            "single_setting_never_sufficient": True,
        },
        "cells": cells,
    }
    digest = plan_sha256(payload)
    plan = {
        **payload,
        "run_id": f"run-{digest[:16]}",
        "plan_sha256": digest,
    }
    validate_artifact_schema(plan, "convergencePlan")
    validate_plan(plan)
    return plan


def plan_sha256(plan: dict[str, Any]) -> str:
    payload = copy.deepcopy(
        {
            key: value
            for key, value in plan.items()
            if key not in {"plan_sha256", "run_id"}
        }
    )
    return _sha256(_canonical_json(payload))


def validate_plan(plan: Any) -> None:
    validate_artifact_schema(plan, "convergencePlan")
    if not isinstance(plan, dict):
        raise TypeError("plan must be a JSON object")
    required = {
        "artifact_type",
        "generator",
        "software_version",
        "run_id",
        "schema_version",
        "stage",
        "model",
        "grid",
        "tolerances",
        "execution_environment",
        "bath_resolution_policy",
        "solver_feasibility",
        "solver_capability",
        "claim_policy",
        "cells",
        "plan_sha256",
    }
    if set(plan) != required:
        raise ValueError("plan keys do not match schema")
    if plan["schema_version"] != PLAN_SCHEMA_VERSION:
        raise ValueError("unsupported plan schema version")
    if plan["artifact_type"] != "convergence_plan":
        raise ValueError("unsupported plan artifact type")
    if plan["generator"] != {
        "name": "convergence.py",
        "version": MODULE_VERSION,
    }:
        raise ValueError("unsupported or stale plan generator version")
    if plan["software_version"] != SOFTWARE_VERSION:
        raise ValueError("unsupported or stale plan software version")
    if plan["run_id"] != f"run-{plan['plan_sha256'][:16]}":
        raise ValueError("plan run ID is not content addressed")
    if plan["model"] != MODEL:
        raise ValueError("plan model does not match Challenge 81")
    if not isinstance(plan["cells"], list) or not plan["cells"]:
        raise ValueError("plan cells must be nonempty")
    ids: set[str] = set()
    for cell in plan["cells"]:
        if not isinstance(cell, dict):
            raise TypeError("cell must be an object")
        if cell["cell_id"] in ids:
            raise ValueError("cell IDs must be unique")
        ids.add(cell["cell_id"])
        settings = cell["solver_settings"]
        if settings.get("krylov_expansion_dim") != 0:
            raise ValueError("production/scalable cells require krylov_expansion_dim=0")
        if cell.get("solver_capability") != plan["solver_capability"]:
            raise ValueError("cell solver capability does not match plan")
        bath.verify_bath_artifact(cell["bath_artifact"])
        if cell["bath_artifact"]["sha256"] != cell["bath_artifact_sha256"]:
            raise ValueError("bath artifact SHA256 linkage mismatch")
        expected_payload = _cell_input_payload(
            beta=cell["parameters"]["beta"],
            n_bath=cell["parameters"]["n_bath"],
            time_step=settings["time_step"],
            cutoff=settings["cutoff"],
            maxdim=settings["maxdim"],
            tau_fractions=cell["tau_fractions"],
            bath_artifact=cell["bath_artifact"],
            source_hashes=cell["provenance"]["source_sha256"],
            project_hashes=cell["provenance"]["julia_environment_sha256"],
            julia_project=cell["provenance"]["julia_project"],
            diagnostic_limits=cell["diagnostic_limits"],
            solver_capability=cell["solver_capability"],
        )
        if _sha256(_canonical_json(expected_payload)) != cell["input_sha256"]:
            raise ValueError("cell input SHA256 mismatch")
    if _digest(plan["plan_sha256"], "plan SHA256") != plan_sha256(plan):
        raise ValueError("plan SHA256 mismatch")


def validate_execution_environment(
    cell: dict[str, Any],
    *,
    julia_project: str | os.PathLike[str],
) -> None:
    provenance = cell.get("provenance", {})
    selected = Path(julia_project).resolve(strict=True)
    if provenance.get("source_sha256") != _source_hashes(selected):
        raise ValueError(
            "cell source provenance does not match the current checkout"
        )
    if provenance.get("julia_environment_sha256") != _project_hashes(selected):
        raise ValueError(
            "cell Julia environment provenance does not match the current checkout"
        )


def _maximum_per_bond(diagnostics: dict[str, Any]) -> list[int]:
    values = diagnostics.get("maximum_link_dimensions_by_bond")
    if not isinstance(values, list) or not values:
        raise ValueError("solver diagnostics lack maximum per-bond dimensions")
    return [_positive_integer(value, "per-bond dimension") for value in values]


def _validate_diagnostic_entry(
    entry: Any,
    *,
    name: str,
    maxdim: int,
    krylov_limit: float,
    truncation_limit: float,
    require_updates: bool,
) -> None:
    if not isinstance(entry, dict) or not entry:
        raise ValueError(f"{name} diagnostics must be a nonempty object")
    required = {
        "max_link_dimension",
        "maximum_link_dimensions_by_bond",
        "truncation_max_error",
        "krylov_all_converged",
        "krylov_max_error_estimate",
        "krylov_num_operations",
        "krylov_num_iterations",
        "krylov_local_updates",
    }
    if not required.issubset(entry):
        raise ValueError(f"{name} diagnostics missing required fields")
    dimensions = _maximum_per_bond(entry)
    if max(dimensions) >= maxdim or _positive_integer(
        entry["max_link_dimension"], f"{name} max link dimension"
    ) >= maxdim:
        raise ValueError(f"{name} maxdim saturation blocks completion")
    if entry["krylov_all_converged"] is not True:
        raise ValueError(f"{name} Krylov updates did not all converge")
    krylov_error = _real(entry["krylov_max_error_estimate"], f"{name} Krylov error")
    if krylov_error < 0 or krylov_error > krylov_limit:
        raise ValueError(f"{name} Krylov error exceeds named limit")
    truncation = _real(entry["truncation_max_error"], f"{name} truncation")
    if truncation < 0 or truncation > truncation_limit:
        raise ValueError(f"{name} truncation exceeds named limit")
    updates = int(entry["krylov_local_updates"])
    if updates < 0 or (require_updates and updates == 0):
        raise ValueError(f"{name} has empty Krylov update history")
    for field in ("krylov_num_operations", "krylov_num_iterations"):
        if not isinstance(entry[field], int) or isinstance(entry[field], bool) or entry[field] < 0:
            raise ValueError(f"{name} {field} must be a nonnegative integer")


def validate_solver_diagnostics(
    diagnostics: Any,
    *,
    cell: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(diagnostics, dict):
        raise ValueError("solver diagnostics are missing")
    if diagnostics.get("krylov_expansion_dim") != 0 or diagnostics.get(
        "expansion_policy"
    ) != "tdvp_only":
        raise ValueError("diagnostics do not confirm TDVP-only evolution")
    maxdim = cell["solver_settings"]["maxdim"]
    limits = cell["diagnostic_limits"]
    krylov_limit = _real(limits["krylov_error"]["absolute"], "Krylov error limit")
    truncation_limit = _real(limits["truncation"]["absolute"], "truncation limit")
    thermal = diagnostics.get("thermal")
    if not isinstance(thermal, dict) or not thermal:
        raise ValueError("thermal diagnostics are missing or empty")
    if not isinstance(thermal.get("steps"), int) or thermal["steps"] <= 0:
        raise ValueError("thermal diagnostics have empty history")
    _validate_diagnostic_entry(
        thermal,
        name="thermal",
        maxdim=maxdim,
        krylov_limit=krylov_limit,
        truncation_limit=truncation_limit,
        require_updates=True,
    )
    expected_points = len(cell["tau_fractions"])
    beta = cell.get("parameters", {}).get("beta")
    for spin, key in (("up", "green_up"), ("dn", "green_down")):
        entries = diagnostics.get(key)
        if not isinstance(entries, list) or len(entries) != expected_points:
            raise ValueError(f"Green-branch diagnostics for {spin} are missing or incomplete")
        for index, entry in enumerate(entries):
            fraction = cell["tau_fractions"][index]
            expected_tau = (
                _real(beta, "beta", positive=True) * fraction
                if beta is not None
                else None
            )
            if entry.get("spin") != spin or (
                expected_tau is not None
                and _real(entry.get("tau"), "Green-branch tau") != expected_tau
            ):
                raise ValueError(
                    f"Green-branch identity mismatch for {spin}[{index}]"
                )
            _validate_diagnostic_entry(
                entry,
                name=f"Green-branch {spin}[{index}]",
                maxdim=maxdim,
                krylov_limit=krylov_limit,
                truncation_limit=truncation_limit,
                require_updates=fraction not in (0.0, 1.0),
            )
    overall = _maximum_per_bond(diagnostics)
    if max(overall) >= maxdim:
        raise ValueError("overall maxdim saturation blocks completion")
    return {
        "passed": True,
        "krylov_error_limit": copy.deepcopy(limits["krylov_error"]),
        "truncation_limit": copy.deepcopy(limits["truncation"]),
        "maxdim_saturation_forbidden": True,
        "required_green_branches": 2 * expected_points,
    }


def validate_cell_observables(
    *,
    tau: Any,
    observables: Any,
    cell: dict[str, Any],
) -> tuple[list[float], dict[str, Any]]:
    """Validate the exact requested grid and elementary fermionic bounds."""

    fractions = cell.get("tau_fractions")
    if not isinstance(fractions, list) or not fractions:
        raise ValueError("cell tau fractions must be a nonempty list")
    beta = _real(cell.get("parameters", {}).get("beta"), "beta", positive=True)
    expected_tau = [beta * _real(value, "tau fraction") for value in fractions]
    if not isinstance(tau, list) or not tau:
        raise ValueError("tau must be a nonempty list")
    tau_values = [_real(value, "tau") for value in tau]
    if tau_values != expected_tau:
        raise ValueError("tau must exactly equal beta * tau_fractions")
    if not isinstance(observables, dict) or set(observables) != {
        "n_d",
        "double_occupancy",
        "G_up",
        "G_down",
    }:
        raise ValueError("solver observables do not match the supported schema")
    n_d = _real(observables["n_d"], "n_d")
    double = _real(observables["double_occupancy"], "double occupancy")
    tolerance = 1.0e-6
    if n_d < -tolerance or n_d > 2.0 + tolerance:
        raise ValueError("n_d is outside the physical interval [0, 2]")
    lower_double = max(0.0, n_d - 1.0)
    upper_double = n_d / 2.0
    if double < lower_double - tolerance or double > upper_double + tolerance:
        raise ValueError("double occupancy is outside physical bounds")
    checked: dict[str, Any] = {
        "n_d": n_d,
        "double_occupancy": double,
    }
    for name in ("G_up", "G_down"):
        values = observables[name]
        if not isinstance(values, list) or len(values) != len(expected_tau):
            raise ValueError(
                f"{name} must have exactly {len(expected_tau)} values"
            )
        green = [_real(value, f"{name} finite value") for value in values]
        if any(value < -1.0 - tolerance or value > tolerance for value in green):
            raise ValueError(f"{name} is outside the physical interval [-1, 0]")
        if expected_tau[0] == 0.0 and not math.isclose(
            green[0], -(1.0 - n_d / 2.0), rel_tol=0.0, abs_tol=tolerance
        ):
            raise ValueError(f"{name} G(0+) endpoint identity failed")
        if expected_tau[-1] == beta and not math.isclose(
            green[-1], -n_d / 2.0, rel_tol=0.0, abs_tol=tolerance
        ):
            raise ValueError(f"{name} G(beta-) endpoint identity failed")
        checked[name] = green
    return tau_values, checked


def validate_solver_provenance(
    provenance: Any, *, cell: dict[str, Any]
) -> None:
    if not isinstance(provenance, dict):
        raise ValueError("solver provenance is missing")
    source = cell["provenance"]["source_sha256"]
    environment = cell["provenance"]["julia_environment_sha256"]
    expected = {
        "runner": "finite_bath_mps_runner",
        "runner_source_sha256": source["finite_bath_mps_runner.jl"],
        "checkpoint_source_sha256": source["finite_bath_checkpoint.jl"],
        "purification_source_sha256": source["finite_bath_purification.jl"],
        "observables_source_sha256": source["finite_bath_observables.jl"],
        "model_definition_sha256": source["model.json"],
        "project_toml_sha256": environment["Project.toml"],
        "manifest_toml_sha256": environment["Manifest.toml"],
        "bath_artifact_file_sha256": _sha256(
            _canonical_json(cell["bath_artifact"]) + b"\n"
        ),
        "krylov_expansion_dim": 0,
        "expansion_policy": "tdvp_only",
    }
    for name, expected_value in expected.items():
        if provenance.get(name) != expected_value:
            raise ValueError(f"solver provenance {name} mismatch")


def make_cell_artifact(
    *,
    cell: dict[str, Any],
    solver_output: dict[str, Any],
    wall_time_seconds: float,
    peak_rss_bytes: int | None,
    peak_rss_method: str | None,
    artifact_file_sha256: dict[str, str] | None = None,
) -> dict[str, Any]:
    settings = solver_output.get("solver", {}).get("settings")
    if settings != cell["solver_settings"]:
        raise ValueError("solver settings do not match cell")
    if settings.get("krylov_expansion_dim") != 0:
        raise ValueError("completed cells require krylov_expansion_dim=0")
    diagnostics = solver_output.get("diagnostics")
    gate = validate_solver_diagnostics(diagnostics, cell=cell)
    per_bond = _maximum_per_bond(diagnostics)
    observables = solver_output.get("observables")
    tau, observables = validate_cell_observables(
        tau=solver_output.get("tau"), observables=observables, cell=cell
    )
    solver_provenance = solver_output.get("provenance")
    validate_solver_provenance(solver_provenance, cell=cell)
    profiling = diagnostics.get("profiling")
    if not isinstance(profiling, dict):
        raise ValueError("solver profiling telemetry is missing")
    phase_timings = profiling.get("phase_timings_seconds")
    expected_phases = {
        "request_validation",
        "context_and_evolution",
        "result_serialization",
    }
    if not isinstance(phase_timings, dict) or set(phase_timings) != expected_phases:
        raise ValueError("solver phase timing telemetry is incomplete")
    phase_timings = {
        name: _real(value, f"{name} phase timing")
        for name, value in phase_timings.items()
    }
    if any(value < 0 for value in phase_timings.values()):
        raise ValueError("solver phase timings must be nonnegative")
    julia_threads = _positive_integer(
        profiling.get("julia_threads"), "Julia thread count"
    )
    blas_threads = _positive_integer(
        profiling.get("blas_threads"), "BLAS thread count"
    )
    blas_vendor = profiling.get("blas_vendor")
    if not isinstance(blas_vendor, str) or not blas_vendor:
        raise ValueError("BLAS vendor telemetry is missing")
    solver_peak_rss = profiling.get("peak_rss_bytes")
    if solver_peak_rss is not None:
        solver_peak_rss = _positive_integer(
            solver_peak_rss, "solver peak RSS"
        )
    mpo_dimensions = profiling.get("actual_mpo_link_dimensions")
    if not isinstance(mpo_dimensions, list) or not mpo_dimensions:
        raise ValueError("actual MPO link dimensions are missing")
    mpo_dimensions = [
        _positive_integer(value, "MPO link dimension")
        for value in mpo_dimensions
    ]
    if artifact_file_sha256 is None:
        artifact_file_sha256 = {
            "bath.json": _sha256(
                _canonical_json(cell["bath_artifact"]) + b"\n"
            ),
            "mps-input.json": _sha256(
                _canonical_json({"input_sha256": cell["input_sha256"]}) + b"\n"
            ),
            "mps-result.json": _sha256(
                _canonical_json(solver_output) + b"\n"
            ),
        }
    if set(artifact_file_sha256) != {
        "bath.json",
        "mps-input.json",
        "mps-result.json",
    }:
        raise ValueError("artifact file SHA256 mapping is incomplete")
    artifact_file_sha256 = {
        name: _digest(value, f"{name} SHA256")
        for name, value in artifact_file_sha256.items()
    }
    artifact = {
        "artifact_type": "completed_cell",
        "generator": {"name": "convergence.py", "version": MODULE_VERSION},
        "software_version": SOFTWARE_VERSION,
        "schema_version": CELL_SCHEMA_VERSION,
        "status": "completed",
        "cell_id": cell["cell_id"],
        "input_sha256": cell["input_sha256"],
        "parameters": copy.deepcopy(cell["parameters"]),
        "tau_fractions": copy.deepcopy(cell["tau_fractions"]),
        "tau": copy.deepcopy(tau),
        "solver_settings": copy.deepcopy(settings),
        "diagnostic_limits": copy.deepcopy(cell["diagnostic_limits"]),
        "observables": copy.deepcopy(observables),
        "diagnostics": {
            "maximum_link_dimensions_by_bond": per_bond,
            "thermal_max_link_dimension": diagnostics.get(
                "thermal_max_link_dimension"
            ),
            "thermal": copy.deepcopy(diagnostics["thermal"]),
            "green_up": copy.deepcopy(diagnostics.get("green_up", [])),
            "green_down": copy.deepcopy(diagnostics.get("green_down", [])),
            "krylov_expansion_dim": diagnostics.get("krylov_expansion_dim"),
            "expansion_policy": diagnostics.get("expansion_policy"),
            "gate": gate,
        },
        "resources": {
            "wall_time_seconds": _real(
                wall_time_seconds, "wall time", positive=True
            ),
            "peak_rss_bytes": peak_rss_bytes,
            "peak_rss_method": peak_rss_method,
            "solver_peak_rss_bytes": solver_peak_rss,
            "phase_timings_seconds": phase_timings,
            "thread_settings": {
                "julia_threads": julia_threads,
                "blas_threads": blas_threads,
                "blas_vendor": blas_vendor,
            },
            "julia_version": profiling.get("julia_version"),
            "actual_mpo_link_dimensions": mpo_dimensions,
        },
        "bath_artifact_sha256": cell["bath_artifact_sha256"],
        "artifact_file_sha256": copy.deepcopy(artifact_file_sha256),
        "provenance": {
            **copy.deepcopy(cell["provenance"]),
            "solver": copy.deepcopy(solver_provenance),
            "orchestrator": "convergence.py",
            "orchestrator_version": MODULE_VERSION,
            "python_version": platform.python_version(),
        },
    }
    artifact["artifact_sha256"] = _sha256(_canonical_json(artifact))
    validate_artifact_schema(artifact, "completedCell")
    validate_cell_artifact(artifact, expected_cell=cell)
    return artifact


def validate_cell_artifact(
    artifact: Any,
    *,
    expected_cell: dict[str, Any] | None = None,
    artifact_directory: str | os.PathLike[str] | None = None,
) -> None:
    if not isinstance(artifact, dict):
        raise TypeError("cell artifact must be an object")
    validate_artifact_schema(artifact, "completedCell")
    if artifact.get("schema_version") != CELL_SCHEMA_VERSION:
        raise ValueError("unsupported cell schema")
    if artifact.get("artifact_type") != "completed_cell":
        raise ValueError("unsupported cell artifact type")
    if artifact.get("generator") != {
        "name": "convergence.py",
        "version": MODULE_VERSION,
    }:
        raise ValueError("unsupported or stale cell generator version")
    if artifact.get("software_version") != SOFTWARE_VERSION:
        raise ValueError("unsupported or stale cell software version")
    if artifact.get("status") != "completed":
        raise ValueError("cell is not completed")
    if artifact.get("solver_settings", {}).get("krylov_expansion_dim") != 0:
        raise ValueError("completed cells require krylov_expansion_dim=0")
    if artifact.get("diagnostics", {}).get("krylov_expansion_dim") != 0:
        raise ValueError("diagnostics do not confirm krylov_expansion_dim=0")
    diagnostic_cell = expected_cell or {
        "solver_settings": artifact["solver_settings"],
        "diagnostic_limits": artifact["diagnostic_limits"],
        "tau_fractions": artifact["tau_fractions"],
        "parameters": artifact["parameters"],
    }
    validate_solver_diagnostics(artifact["diagnostics"], cell=diagnostic_cell)
    validate_cell_observables(
        tau=artifact["tau"],
        observables=artifact["observables"],
        cell=diagnostic_cell,
    )
    digest = _digest(artifact.get("artifact_sha256"), "cell artifact SHA256")
    payload = {
        key: value for key, value in artifact.items() if key != "artifact_sha256"
    }
    if digest != _sha256(_canonical_json(payload)):
        raise ValueError("cell artifact SHA256 mismatch")
    file_hashes = artifact.get("artifact_file_sha256")
    if not isinstance(file_hashes, dict) or set(file_hashes) != {
        "bath.json",
        "mps-input.json",
        "mps-result.json",
    }:
        raise ValueError("cell artifact file SHA256 mapping is incomplete")
    for filename, file_digest in file_hashes.items():
        _digest(file_digest, f"{filename} SHA256")
    if artifact_directory is not None:
        directory = Path(artifact_directory)
        expected_entries = {"cell.json", *file_hashes}
        actual_entries = {path.name for path in directory.iterdir()}
        if actual_entries != expected_entries:
            raise ValueError(
                f"unexpected cell artifact files: expected {sorted(expected_entries)}, "
                f"got {sorted(actual_entries)}"
            )
        for filename, expected_digest in file_hashes.items():
            path = directory / filename
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"cell artifact file is missing: {filename}")
            if _sha256_file(path) != expected_digest:
                raise ValueError(f"cell artifact file SHA256 mismatch: {filename}")
    acceptance._validate_finite_tree(artifact, "cell artifact")
    if expected_cell is not None:
        validate_solver_provenance(
            artifact.get("provenance", {}).get("solver"),
            cell=expected_cell,
        )
        if artifact.get("cell_id") != expected_cell["cell_id"]:
            raise ValueError("cell ID mismatch")
        if artifact.get("input_sha256") != expected_cell["input_sha256"]:
            raise ValueError("cell input SHA256 mismatch")
        if artifact.get("bath_artifact_sha256") != expected_cell[
            "bath_artifact_sha256"
        ]:
            raise ValueError("cell bath SHA256 mismatch")
        if artifact.get("solver_settings") != expected_cell["solver_settings"]:
            raise ValueError("cell solver settings mismatch")
        if artifact.get("diagnostic_limits") != expected_cell["diagnostic_limits"]:
            raise ValueError("cell diagnostic limits mismatch")
        if artifact.get("parameters") != expected_cell["parameters"]:
            raise ValueError("cell parameters mismatch")
        if artifact.get("provenance", {}).get("source_sha256") != expected_cell[
            "provenance"
        ]["source_sha256"]:
            raise ValueError("cell source provenance mismatch")
        if artifact.get("provenance", {}).get(
            "julia_environment_sha256"
        ) != expected_cell["provenance"]["julia_environment_sha256"]:
            raise ValueError("cell Julia environment provenance mismatch")


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(
        directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _unused_sibling(parent: Path, prefix: str) -> Path:
    descriptor, name = tempfile.mkstemp(dir=parent, prefix=prefix)
    os.close(descriptor)
    os.unlink(name)
    return Path(name)


def archive_superseded_directory(path: Path) -> Path:
    """Move an invalid immutable artifact aside without deleting user data."""

    archived = _unused_sibling(path.parent, f".{path.name}.superseded-")
    os.replace(path, archived)
    _fsync_directory(path.parent)
    return archived


def recover_abandoned_cell_state(cells_root: Path, cell_id: str) -> list[Path]:
    """Archive stage/backup trees left by abrupt process termination."""

    recovered = []
    for state in ("stage", "backup", "failed"):
        for path in cells_root.glob(f".{cell_id}.{state}-*"):
            archived = _unused_sibling(
                cells_root, f".{cell_id}.abandoned-{state}-"
            )
            os.replace(path, archived)
            recovered.append(archived)
    if recovered:
        _fsync_directory(cells_root)
    return recovered


def atomic_publish_directory(staging: Path, destination: Path) -> None:
    staging = staging.resolve()
    destination = destination.resolve()
    if staging.parent != destination.parent:
        raise ValueError("staging and destination must share a parent")
    if not staging.is_dir() or staging.is_symlink():
        raise ValueError("staging must be a real directory")
    if destination.exists() and (
        not destination.is_dir() or destination.is_symlink()
    ):
        raise ValueError("destination must be a real directory")
    backup = None
    published = False
    try:
        if destination.exists():
            backup = _unused_sibling(
                destination.parent, f".{destination.name}.backup-"
            )
            os.replace(destination, backup)
            _fsync_directory(destination.parent)
        os.replace(staging, destination)
        published = True
        _fsync_directory(destination.parent)
    except BaseException:
        failed = None
        try:
            if published and destination.exists():
                failed = _unused_sibling(
                    destination.parent, f".{destination.name}.failed-"
                )
                os.replace(destination, failed)
            if backup is not None and backup.exists():
                os.replace(backup, destination)
            _fsync_directory(destination.parent)
        finally:
            if failed is not None and failed.exists():
                shutil.rmtree(failed, ignore_errors=True)
        raise
    if backup is not None and backup.exists():
        shutil.rmtree(backup)


@contextmanager
def cell_advisory_lock(cells_root: Path, cell_id: str):
    lock_root = cells_root / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_path = lock_root / f"{cell_id}.lock"
    with lock_path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def resource_sha256(resources: dict[str, Any]) -> str:
    payload = {
        key: value for key, value in resources.items() if key != "resource_sha256"
    }
    return _sha256(_canonical_json(payload))


def validate_resources(resources: Any, plan: dict[str, Any]) -> None:
    if not isinstance(resources, dict):
        raise TypeError("resources must be a JSON object")
    validate_artifact_schema(resources, "resourceEstimate")
    if resources.get("artifact_type") != "resource_estimate":
        raise ValueError("unsupported resource artifact type")
    if resources.get("generator") != {
        "name": "convergence.py",
        "version": MODULE_VERSION,
    }:
        raise ValueError("unsupported or stale resource generator version")
    if resources.get("software_version") != SOFTWARE_VERSION:
        raise ValueError("unsupported or stale resource software version")
    if resources.get("plan_sha256") != plan["plan_sha256"]:
        raise ValueError("resources plan SHA256 does not match plan")
    if _digest(resources.get("resource_sha256"), "resource SHA256") != resource_sha256(
        resources
    ):
        raise ValueError("resources SHA256 mismatch")


def _write_canonical(path: Path, value: Any) -> None:
    path.write_bytes(_canonical_json(value) + b"\n")
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def read_linux_process_peak_rss(
    pid: int, *, proc_root: Path = Path("/proc")
) -> int | None:
    try:
        lines = (proc_root / str(pid) / "status").read_text(
            encoding="utf-8"
        ).splitlines()
    except (FileNotFoundError, PermissionError, OSError):
        return None
    values = {}
    for line in lines:
        if line.startswith(("VmHWM:", "VmRSS:")):
            name, raw = line.split(":", 1)
            fields = raw.split()
            if len(fields) == 2 and fields[1] == "kB":
                values[name] = int(fields[0]) * 1024
    return values.get("VmHWM", values.get("VmRSS"))


def process_rss_monitoring_method() -> str | None:
    return (
        "linux_proc_status_vmhwm"
        if platform.system() == "Linux"
        else None
    )


def _runner_request_for_cell(cell: dict[str, Any]) -> dict[str, Any]:
    beta = cell["parameters"]["beta"]
    fixture = {
        "model": {
            "U": MODEL["U"],
            "epsilon_d": MODEL["epsilon_d"],
            "mu": MODEL["mu"],
            "beta": beta,
        },
        "tau": [beta * value for value in cell["tau_fractions"]],
        "solver_settings": copy.deepcopy(cell["solver_settings"]),
    }
    bath_json = (
        _canonical_json(cell["bath_artifact"]) + b"\n"
    ).decode("utf-8")
    return acceptance._make_mps_request(bath_json, fixture)


def _strict_canonical_json_file(path: Path, name: str) -> Any:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{name} must be a regular non-symlink file")
    raw = path.read_bytes()
    value = acceptance.strict_json_loads(raw.decode("utf-8"), name=name)
    if raw != _canonical_json(value) + b"\n":
        raise ValueError(f"{name} must use canonical JSON")
    return value


def validate_checkpoint_root(
    checkpoint_root: str | os.PathLike[str],
    *,
    cell: dict[str, Any],
) -> str:
    """Validate a Task 3 checkpoint tree and return its current fingerprint."""

    root = Path(checkpoint_root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("checkpoint root must be a real directory")
    if {path.name for path in root.iterdir()} != {"current.json", "generations"}:
        raise ValueError("checkpoint root entries do not match schema")
    generations = root / "generations"
    if not generations.is_dir() or generations.is_symlink():
        raise ValueError("checkpoint generations must be a real directory")
    pointer_path = root / "current.json"
    pointer = _strict_canonical_json_file(pointer_path, "checkpoint current pointer")
    validate_artifact_schema(pointer, "checkpointPointer")
    pointer_keys = {
        "checkpoint_schema",
        "writer_version",
        "generation",
        "completed_steps",
        "metadata_sha256",
        "state_sha256",
        "completion_sha256",
    }
    if not isinstance(pointer, dict) or set(pointer) != pointer_keys:
        raise ValueError("checkpoint current pointer keys do not match schema")
    if (
        pointer["checkpoint_schema"] != CHECKPOINT_SCHEMA_VERSION
        or pointer["writer_version"] != CHECKPOINT_WRITER_VERSION
    ):
        raise ValueError("checkpoint current pointer version mismatch")
    generation_name = pointer["generation"]
    metadata_digest = _digest(
        pointer["metadata_sha256"], "checkpoint metadata SHA256"
    )
    if generation_name != f"checkpoint-{metadata_digest}":
        raise ValueError("checkpoint generation does not bind metadata SHA256")
    if (
        isinstance(pointer["completed_steps"], bool)
        or not isinstance(pointer["completed_steps"], int)
        or pointer["completed_steps"] < 0
    ):
        raise ValueError("checkpoint completed_steps must be nonnegative")
    state_digest = _digest(pointer["state_sha256"], "checkpoint state SHA256")
    completion_digest = _digest(
        pointer["completion_sha256"], "checkpoint completion SHA256"
    )

    request = _runner_request_for_cell(cell)
    payload = acceptance.strict_json_loads(
        request["payload_json"], name="checkpoint-bound request payload"
    )
    checkpoint_request = payload["checkpoint"]
    expected_identity = {
        "request_sha256": _sha256(_canonical_json(request) + b"\n"),
        "input_payload_sha256": request["sha256"],
        "bath_sha256": cell["bath_artifact"]["sha256"],
        "solver_settings": {
            "beta": cell["parameters"]["beta"],
            "tau": [
                cell["parameters"]["beta"] * value
                for value in cell["tau_fractions"]
            ],
            "time_step": cell["solver_settings"]["time_step"],
            "cutoff": cell["solver_settings"]["cutoff"],
            "maxdim": cell["solver_settings"]["maxdim"],
            "krylov_expansion_dim": cell["solver_settings"][
                "krylov_expansion_dim"
            ],
        },
        "source_hashes": checkpoint_request["source_hashes"],
        "project_toml_sha256": checkpoint_request["project_toml_sha256"],
        "manifest_toml_sha256": checkpoint_request["manifest_toml_sha256"],
        "checkpoint_schema": CHECKPOINT_SCHEMA_VERSION,
        "writer_version": CHECKPOINT_WRITER_VERSION,
    }
    identity_keys = {
        *expected_identity,
        "julia_version",
        "itensors_version",
        "itensormps_version",
        "hdf5_version",
    }
    generation_entries = list(generations.iterdir())
    if not generation_entries:
        raise ValueError("checkpoint generations must not be empty")
    current_validated = False
    for generation in generation_entries:
        if (
            not generation.is_dir()
            or generation.is_symlink()
            or not generation.name.startswith("checkpoint-")
            or len(generation.name) != len("checkpoint-") + 64
        ):
            raise ValueError("checkpoint generation entry is invalid")
        if {path.name for path in generation.iterdir()} != {
            "metadata.json",
            "state.h5",
            "completion.json",
        }:
            raise ValueError("checkpoint generation entries do not match schema")
        metadata_path = generation / "metadata.json"
        state_path = generation / "state.h5"
        completion_path = generation / "completion.json"
        metadata = _strict_canonical_json_file(
            metadata_path, "checkpoint metadata"
        )
        completion = _strict_canonical_json_file(
            completion_path, "checkpoint completion"
        )
        validate_artifact_schema(metadata, "checkpointMetadata")
        validate_artifact_schema(completion, "checkpointCompletion")
        if not state_path.is_file() or state_path.is_symlink():
            raise ValueError("checkpoint state must be a regular non-symlink file")
        if not isinstance(metadata, dict) or set(metadata) != {
            "checkpoint_schema",
            "writer_version",
            "identity",
            "completed_steps",
            "resume_state",
        }:
            raise ValueError("checkpoint metadata keys do not match schema")
        identity = metadata["identity"]
        if not isinstance(identity, dict) or set(identity) != identity_keys:
            raise ValueError("checkpoint identity keys do not match schema")
        for name, expected in expected_identity.items():
            if identity[name] != expected:
                raise ValueError(f"checkpoint identity mismatch: {name}")
        for name in (
            "julia_version",
            "itensors_version",
            "itensormps_version",
            "hdf5_version",
        ):
            if not isinstance(identity[name], str) or not identity[name]:
                raise ValueError(f"checkpoint identity {name} is invalid")
        generation_metadata_digest = _sha256_file(metadata_path)
        if generation.name != f"checkpoint-{generation_metadata_digest}":
            raise ValueError("checkpoint generation name hash mismatch")
        if not isinstance(completion, dict) or set(completion) != {
            "checkpoint_schema",
            "writer_version",
            "generation",
            "metadata_sha256",
            "state_sha256",
        }:
            raise ValueError("checkpoint completion keys do not match schema")
        expected_completion = {
            "checkpoint_schema": CHECKPOINT_SCHEMA_VERSION,
            "writer_version": CHECKPOINT_WRITER_VERSION,
            "generation": generation.name,
            "metadata_sha256": generation_metadata_digest,
            "state_sha256": _sha256_file(state_path),
        }
        if completion != expected_completion:
            raise ValueError("checkpoint completion bindings mismatch")
        if generation.name == generation_name:
            if (
                metadata["completed_steps"] != pointer["completed_steps"]
                or generation_metadata_digest != metadata_digest
                or expected_completion["state_sha256"] != state_digest
                or _sha256_file(completion_path) != completion_digest
            ):
                raise ValueError("checkpoint current pointer bindings mismatch")
            current_validated = True
    if not current_validated:
        raise ValueError("checkpoint current generation is missing")
    return _sha256_file(pointer_path)


def invoke_julia_runner_monitored(
    command: Sequence[str],
    *,
    output_path: Path,
    timeout_seconds: float | None = None,
    max_rss_bytes: int | None = None,
    checkpoint_validator: Callable[[], Any | None] | None = None,
    checkpoint_grace_period: Callable[[], float] | None = None,
) -> dict[str, Any]:
    if output_path.exists() or output_path.is_symlink():
        raise ValueError("refusing pre-existing Julia output as stale")
    previous_checkpoint = (
        checkpoint_validator() if checkpoint_validator is not None else None
    )
    process = subprocess.Popen(
        list(command), cwd=SOLUTION_DIR, start_new_session=True
    )
    started = time.monotonic()
    peak = None
    method = process_rss_monitoring_method()
    grace_deadline = None
    timed_out = False
    old_handlers: dict[int, Any] = {}

    def forward(signum, _frame):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signum)
            except ProcessLookupError:
                pass

    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGUSR1, signal.SIGTERM):
            old_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, forward)
    try:
        while process.poll() is None:
            if method is not None:
                observed = read_linux_process_peak_rss(process.pid)
                if observed is not None:
                    peak = observed if peak is None else max(peak, observed)
                    if max_rss_bytes is not None and peak > max_rss_bytes:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                        raise MemoryError(
                            f"subprocess peak RSS exceeded {max_rss_bytes} bytes"
                        )
            now = time.monotonic()
            if (
                timeout_seconds is not None
                and not timed_out
                and now - started > timeout_seconds
            ):
                timed_out = True
                grace = (
                    checkpoint_grace_period()
                    if checkpoint_grace_period is not None
                    else CHECKPOINT_GRACE_SECONDS
                )
                grace = _real(grace, "checkpoint grace period")
                if grace < 0:
                    raise ValueError("checkpoint grace period must be nonnegative")
                grace_deadline = now + grace
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            if (
                grace_deadline is not None
                and process.poll() is None
                and now >= grace_deadline
            ):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                raise subprocess.TimeoutExpired(list(command), timeout_seconds)
            time.sleep(0.05)
    except BaseException:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
    if method is not None:
        observed = read_linux_process_peak_rss(process.pid)
        if observed is not None:
            peak = observed if peak is None else max(peak, observed)
    if process.returncode == 75:
        current_checkpoint = (
            checkpoint_validator() if checkpoint_validator is not None else None
        )
        if (
            current_checkpoint is not None
            and current_checkpoint != previous_checkpoint
        ):
            raise ContinuationAvailable(current_checkpoint)
    if timed_out and process.returncode not in (0, 75):
        raise subprocess.TimeoutExpired(list(command), timeout_seconds)
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, list(command))
    if not output_path.is_file() or output_path.is_symlink():
        raise ValueError("Julia runner exited successfully but did not create output")
    return {"peak_rss_bytes": peak, "peak_rss_method": method if peak is not None else None}


def _default_executor(
    cell: dict[str, Any],
    staging: Path,
    checkpoint_root: Path,
    *,
    julia_executable: str | os.PathLike[str] | None = None,
    julia_project: str | os.PathLike[str] = JULIA_DIR,
    timeout_seconds: float | None = LOCAL_WALL_LIMIT_SECONDS,
    max_rss_bytes: int | None = LOCAL_RSS_LIMIT_BYTES,
) -> tuple[dict[str, Any], dict[str, Any]]:
    julia = acceptance.resolve_julia(julia_executable)
    project = Path(julia_project).resolve(strict=True)
    bath_path = staging / "bath.json"
    input_path = staging / "mps-input.json"
    output_path = staging / "mps-result.json"
    _write_canonical(bath_path, cell["bath_artifact"])
    request = _runner_request_for_cell(cell)
    acceptance.atomic_write_json(input_path, request)
    payload = acceptance.strict_json_loads(
        request["payload_json"], name="cell MPS request"
    )
    expected_provenance = acceptance.expected_runner_provenance(
        julia_project=project,
        bath_file_sha256=payload["bath_artifact_file_sha256"],
        krylov_expansion_dim=0,
    )
    command = [
        str(julia),
        f"--project={project}",
        str(JULIA_RUNNER),
        str(input_path),
        str(output_path),
        str(checkpoint_root),
    ]
    measurement = invoke_julia_runner_monitored(
        command,
        output_path=output_path,
        timeout_seconds=timeout_seconds,
        max_rss_bytes=max_rss_bytes,
        checkpoint_validator=lambda: (
            validate_checkpoint_root(checkpoint_root, cell=cell)
            if checkpoint_root.exists() or checkpoint_root.is_symlink()
            else None
        ),
    )
    output = acceptance.strict_json_loads(
        output_path.read_text(encoding="utf-8"), name="cell MPS result"
    )
    acceptance.verify_mps_output(
        output,
        expected_input_sha256=_sha256(input_path.read_bytes()),
        expected_input_payload_sha256=request["sha256"],
        expected_settings=cell["solver_settings"],
        expected_tau=[
            cell["parameters"]["beta"] * value
            for value in cell["tau_fractions"]
        ],
        expected_provenance=expected_provenance,
    )
    return output, measurement


def _n48_solver_capability_is_valid(plan: dict[str, Any]) -> bool:
    capability = plan["solver_capability"]
    capability_key = (
        capability["bath_representation"],
        capability["capability_evidence_sha256"] or "",
    )
    return (
        capability["n_bath_48_execution_validated"] is True
        and capability_key in N48_VALIDATED_SOLVER_CAPABILITIES
    )


def run_cell(
    plan: dict[str, Any],
    cell_index: int,
    run_directory: str | os.PathLike[str],
    *,
    executor: Callable[..., dict[str, Any]] | None = None,
    julia_executable: str | os.PathLike[str] | None = None,
    julia_project: str | os.PathLike[str] | None = None,
    resources: dict[str, Any] | None = None,
    resource_acknowledgment: str | None = None,
    execution_target: str = "local",
) -> dict[str, Any]:
    validate_plan(plan)
    if isinstance(cell_index, bool) or not isinstance(cell_index, int):
        raise TypeError("cell index must be an integer")
    if cell_index < 0 or cell_index >= len(plan["cells"]):
        raise ValueError("cell index is out of range")
    cell = plan["cells"][cell_index]
    if julia_project is None:
        raise ValueError("execution requires an explicit runtime Julia project path")
    selected_project = Path(julia_project).resolve(strict=True)
    validate_execution_environment(cell, julia_project=selected_project)
    if execution_target not in {"local", "cluster"}:
        raise ValueError("execution_target must be local or cluster")
    if cell["parameters"]["n_bath"] == 48:
        if not _n48_solver_capability_is_valid(plan):
            raise ValueError(
                "N_b=48 solver capability is not implemented and validated; "
                "execution is forbidden for every target"
            )
    if plan["stage"] == "production":
        if resources is None:
            raise ValueError("production execution requires resources.json")
        validate_resources(resources, plan)
        if resource_acknowledgment != resources["resource_sha256"]:
            raise ValueError("production resource acknowledgment is missing or incorrect")
    run_root = Path(run_directory).resolve()
    cells_root = run_root / "cells"
    cells_root.mkdir(parents=True, exist_ok=True)
    checkpoints_root = run_root / "checkpoints"
    if checkpoints_root.exists() or checkpoints_root.is_symlink():
        if not checkpoints_root.is_dir() or checkpoints_root.is_symlink():
            raise ValueError("checkpoints must be a real directory")
    checkpoint_root = checkpoints_root / cell["cell_id"]
    destination = cells_root / cell["cell_id"]
    with cell_advisory_lock(cells_root, cell["cell_id"]):
        recover_abandoned_cell_state(cells_root, cell["cell_id"])
        existing_valid = False
        if destination.is_dir() and not destination.is_symlink():
            try:
                existing = acceptance.strict_json_loads(
                    (destination / "cell.json").read_text(encoding="utf-8"),
                    name="existing cell",
                )
                validate_cell_artifact(
                    existing,
                    expected_cell=cell,
                    artifact_directory=destination,
                )
                existing_valid = True
            except (OSError, TypeError, ValueError):
                existing_valid = False
        if existing_valid:
            if checkpoint_root.exists() or checkpoint_root.is_symlink():
                if checkpoint_root.is_dir() and not checkpoint_root.is_symlink():
                    shutil.rmtree(checkpoint_root)
                else:
                    checkpoint_root.unlink()
                _fsync_directory(checkpoints_root)
            return {"action": "skipped", "cell": existing, "path": destination}
        if destination.exists() or destination.is_symlink():
            archived = archive_superseded_directory(destination)
            raise ValueError(
                "stale or invalid immutable cell was archived at "
                f"{archived}; generate a new content-addressed plan"
            )
        if checkpoint_root.exists() or checkpoint_root.is_symlink():
            try:
                validate_checkpoint_root(checkpoint_root, cell=cell)
            except (OSError, TypeError, ValueError) as error:
                if (
                    checkpoint_root.is_dir()
                    and not checkpoint_root.is_symlink()
                ):
                    archived = archive_superseded_directory(checkpoint_root)
                else:
                    checkpoints_root.mkdir(parents=True, exist_ok=True)
                    archived = _unused_sibling(
                        checkpoints_root,
                        f".{cell['cell_id']}.superseded-",
                    )
                    os.replace(checkpoint_root, archived)
                    _fsync_directory(checkpoints_root)
                raise ValueError(
                    f"invalid checkpoint was archived at {archived}: {error}"
                ) from error
        action = "completed"
        staging = Path(
            tempfile.mkdtemp(dir=cells_root, prefix=f".{cell['cell_id']}.stage-")
        )
        started = time.monotonic()
        try:
            measurement = {"peak_rss_bytes": None, "peak_rss_method": None}
            if executor is None:
                solver_output, measurement = _default_executor(
                    cell,
                    staging,
                    checkpoint_root,
                    julia_executable=julia_executable,
                    julia_project=selected_project,
                    timeout_seconds=(
                        LOCAL_WALL_LIMIT_SECONDS
                        if execution_target == "local"
                        else None
                    ),
                    max_rss_bytes=(
                        LOCAL_RSS_LIMIT_BYTES
                        if execution_target == "local"
                        else None
                    ),
                )
            else:
                parameters = inspect.signature(executor).parameters.values()
                accepts_checkpoint = any(
                    parameter.kind
                    in (
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    )
                    for parameter in parameters
                ) or len(
                    [
                        parameter
                        for parameter in parameters
                        if parameter.kind
                        in (
                            inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        )
                    ]
                ) >= 3
                executed = (
                    executor(cell, staging, checkpoint_root)
                    if accepts_checkpoint
                    else executor(cell, staging)
                )
                if isinstance(executed, tuple):
                    solver_output, measurement = executed
                else:
                    solver_output = executed
            runtime_project = solver_output.get("provenance", {}).get(
                "active_project_path"
            )
            if runtime_project != str(
                (selected_project / "Project.toml").resolve()
            ):
                raise ValueError(
                    "solver runtime Julia project path does not match explicit "
                    "execution path"
                )
            bath_path = staging / "bath.json"
            input_path = staging / "mps-input.json"
            result_path = staging / "mps-result.json"
            if not bath_path.exists():
                _write_canonical(bath_path, cell["bath_artifact"])
            if not input_path.exists():
                _write_canonical(
                    input_path, {"input_sha256": cell["input_sha256"]}
                )
            if not result_path.exists():
                _write_canonical(result_path, solver_output)
            file_hashes = {
                path.name: _sha256_file(path)
                for path in (bath_path, input_path, result_path)
            }
            wall = time.monotonic() - started
            artifact = make_cell_artifact(
                cell=cell,
                solver_output=solver_output,
                wall_time_seconds=max(wall, float.fromhex("0x1p-1022")),
                peak_rss_bytes=measurement.get("peak_rss_bytes"),
                peak_rss_method=measurement.get("peak_rss_method"),
                artifact_file_sha256=file_hashes,
            )
            _write_canonical(staging / "cell.json", artifact)
            _fsync_directory(staging)
            atomic_publish_directory(staging, destination)
            if checkpoint_root.exists() or checkpoint_root.is_symlink():
                if checkpoint_root.is_dir() and not checkpoint_root.is_symlink():
                    shutil.rmtree(checkpoint_root)
                else:
                    checkpoint_root.unlink()
                _fsync_directory(checkpoints_root)
            return {"action": action, "cell": artifact, "path": destination}
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)


def classify_failure(error: BaseException) -> str:
    text = str(error).lower()
    if "bath" in text:
        return "bath_discretization"
    if "time_step" in text or "timestep" in text or "step count" in text:
        return "timestep"
    if "maxdim" in text or "truncat" in text or "bond" in text:
        return "maxdim_truncation"
    if isinstance(error, (MemoryError, subprocess.TimeoutExpired)) or any(
        token in text for token in ("out of memory", "oom", "killed", "timeout")
    ):
        return "runtime_memory"
    if isinstance(error, (TypeError, ValueError)):
        return "input_validation"
    return "solver_runtime"


def _observable_vector(artifact: dict[str, Any]) -> list[float]:
    values = artifact["observables"]
    return [
        _real(values["n_d"], "n_d"),
        _real(values["double_occupancy"], "double occupancy"),
        *[_real(value, "G_up") for value in values["G_up"]],
        *[_real(value, "G_down") for value in values["G_down"]],
    ]


def _pair_delta(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_values = _observable_vector(left)
    right_values = _observable_vector(right)
    if len(left_values) != len(right_values):
        raise ValueError("observable vector lengths do not match")
    return max(abs(a - b) for a, b in zip(left_values, right_values))


def _pair_differences(
    left: dict[str, Any], right: dict[str, Any]
) -> list[float]:
    left_values = _observable_vector(left)
    right_values = _observable_vector(right)
    if len(left_values) != len(right_values):
        raise ValueError("observable vector lengths do not match")
    return [
        right_value - left_value
        for left_value, right_value in zip(left_values, right_values)
    ]


def _controlled_pairs(
    artifacts: list[dict[str, Any]], axis: str
) -> list[dict[str, Any]]:
    field = {"bath_size": "n_bath", "time_step": "time_step", "maxdim": "maxdim"}[
        axis
    ]

    def coordinates(artifact):
        return {
            "beta": artifact["parameters"]["beta"],
            "n_bath": artifact["parameters"]["n_bath"],
            "time_step": artifact["solver_settings"]["time_step"],
            "cutoff": artifact["solver_settings"]["cutoff"],
            "maxdim": artifact["solver_settings"]["maxdim"],
        }

    fixed = [name for name in ("beta", "n_bath", "time_step", "cutoff", "maxdim") if name != field]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for artifact in artifacts:
        coordinate = coordinates(artifact)
        groups.setdefault(tuple(coordinate[name] for name in fixed), []).append(
            artifact
        )
    pairs = []
    for key in sorted(groups):
        ordered = sorted(
            groups[key],
            key=lambda item: coordinates(item)[field],
            reverse=axis == "time_step",
        )
        for left, right in zip(ordered, ordered[1:]):
            left_coordinate = coordinates(left)
            right_coordinate = coordinates(right)
            pairs.append(
                {
                    "left_cell_id": left["cell_id"],
                    "right_cell_id": right["cell_id"],
                    "left_value": left_coordinate[field],
                    "right_value": right_coordinate[field],
                    "fixed": {
                        name: left_coordinate[name] for name in fixed
                    },
                    "controlled": all(
                        left_coordinate[name] == right_coordinate[name]
                        for name in fixed
                    ),
                    "max_observable_delta": _pair_delta(left, right),
                    "observable_differences": _pair_differences(left, right),
                }
            )
    return pairs


def _axis_nonmonotonic(pairs: list[dict[str, Any]], axis: str) -> bool:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for pair in pairs:
        key = tuple(sorted(pair["fixed"].items()))
        grouped.setdefault(key, []).append(pair)
    for group in grouped.values():
        ordered = sorted(
            group,
            key=lambda pair: pair["left_value"],
            reverse=axis == "time_step",
        )
        deltas = [pair["max_observable_delta"] for pair in ordered]
        if any(finer > coarser * (1 + 1.0e-12) for coarser, finer in zip(deltas, deltas[1:])):
            return True
        for coarser, finer in zip(ordered, ordered[1:]):
            if any(
                left * right < 0.0
                for left, right in zip(
                    coarser["observable_differences"],
                    finer["observable_differences"],
                )
            ):
                return True
    return False


def _bath_resolution_status(
    plan: dict[str, Any], available_cell_ids: set[str] | None = None
) -> dict[str, Any]:
    policy = plan["bath_resolution_policy"]
    result = {}
    for beta in sorted({cell["parameters"]["beta"] for cell in plan["cells"]}):
        cells = [
            cell
            for cell in plan["cells"]
            if (
                available_cell_ids is None
                or cell["cell_id"] in available_cell_ids
            )
            if cell["parameters"]["beta"] == beta
            and cell["solver_settings"]["time_step"] == STAGED_ANCHOR["time_step"]
            and cell["solver_settings"]["maxdim"] == STAGED_ANCHOR["maxdim"]
            and cell["parameters"]["n_bath"] in policy["bath_sizes"]
        ]
        cells.sort(key=lambda cell: cell["parameters"]["n_bath"])
        sizes = [cell["parameters"]["n_bath"] for cell in cells]
        nearest = [
            cell["bath_resolution"]["nearest_absolute_energy"] for cell in cells
        ]
        ratios = [
            cell["bath_resolution"]["nearest_energy_over_temperature"]
            for cell in cells
        ]
        complete = sizes == policy["bath_sizes"]
        decreasing = complete and all(
            right < left for left, right in zip(nearest, nearest[1:])
        )
        finest_ratio = ratios[-1] if complete else None
        passed = (
            complete
            and decreasing
            and finest_ratio is not None
            and finest_ratio <= policy["finest_ratio_limit"]
        )
        result[str(beta)] = {
            "bath_sizes": sizes,
            "nearest_absolute_energy": nearest,
            "temperature": 1.0 / beta,
            "nearest_energy_over_temperature": ratios,
            "nearest_energy_strictly_decreasing": decreasing,
            "finest_nearest_energy_over_temperature": finest_ratio,
            "finest_ratio_limit": policy["finest_ratio_limit"],
            "passed": passed,
        }
    return result


def _analysis_inputs(
    plan: dict[str, Any], artifacts: Sequence[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    validate_plan(plan)
    if plan["execution_environment"]["source_sha256"] != _source_hashes(
        JULIA_DIR
    ):
        raise ValueError(
            "plan source provenance does not match the current checkout"
        )
    by_id: dict[str, dict[str, Any]] = {}
    expected = {cell["cell_id"]: cell for cell in plan["cells"]}
    for artifact in artifacts:
        cell_id = artifact.get("cell_id")
        if cell_id not in expected:
            raise ValueError(f"unexpected cell {cell_id}")
        if cell_id in by_id:
            raise ValueError(f"duplicate cell {cell_id}")
        validate_cell_artifact(artifact, expected_cell=expected[cell_id])
        by_id[cell_id] = artifact
    missing = sorted(set(expected) - set(by_id))
    ordered = [
        by_id[cell["cell_id"]]
        for cell in plan["cells"]
        if cell["cell_id"] in by_id
    ]
    return ordered, missing


def _build_analysis(
    plan: dict[str, Any],
    ordered: list[dict[str, Any]],
    missing: list[str],
    *,
    analysis_mode: str,
) -> dict[str, Any]:
    pairs = {
        axis: _controlled_pairs(ordered, axis)
        for axis in ("bath_size", "time_step", "maxdim")
    }
    axis_status = {}
    blockers = []
    for axis, axis_pairs in pairs.items():
        tolerance = plan["tolerances"][axis]
        threshold = _real(tolerance["absolute"], f"{axis} tolerance")
        max_delta = max(
            (pair["max_observable_delta"] for pair in axis_pairs), default=None
        )
        enough_pairs = bool(axis_pairs)
        nonmonotonic = _axis_nonmonotonic(axis_pairs, axis)
        passed = (
            enough_pairs
            and max_delta is not None
            and max_delta <= threshold
            and not nonmonotonic
        )
        axis_status[axis] = {
            "tolerance_name": tolerance["name"],
            "tolerance_absolute": threshold,
            "max_observable_delta": max_delta,
            "pair_count": len(axis_pairs),
            "nonmonotonic": nonmonotonic,
            "passed": passed,
        }
        if nonmonotonic:
            label = axis.replace("_", " ")
            blockers.insert(
                0,
                f"non-monotonic {label} controlled trend blocks a convergence claim",
            )
        elif not passed:
            blockers.append(f"{axis} tolerance not established")
    bath_resolution = _bath_resolution_status(
        plan, {artifact["cell_id"] for artifact in ordered}
    )
    if not all(status["passed"] for status in bath_resolution.values()):
        blockers.append("three-level bath resolution policy not established")
    if not plan["claim_policy"]["production_eligible"]:
        blockers.append("plan stage/grid is not production eligible")
    if missing:
        expected = {cell["cell_id"]: cell for cell in plan["cells"]}
        details = []
        for cell_id in missing:
            cell = expected[cell_id]
            details.append(
                f"{cell_id} (beta={cell['parameters']['beta']},"
                f"N_b={cell['parameters']['n_bath']},"
                f"dt={cell['solver_settings']['time_step']},"
                f"maxdim={cell['solver_settings']['maxdim']},"
                f"class={cell['execution_class']})"
            )
        blockers.insert(
            0, "missing completed cells: " + "; ".join(details)
        )
    if not _n48_solver_capability_is_valid(plan):
        blockers.append(
            "N_b=48 solver capability is not validated and allowlisted"
        )
    if analysis_mode != "complete":
        blockers.append(
            "incomplete calibration analysis never establishes convergence"
        )
    claim = not blockers and all(
        status["passed"] for status in axis_status.values()
    )
    if analysis_mode != "complete":
        claim = False
    peak_values = [
        artifact["resources"]["peak_rss_bytes"]
        for artifact in ordered
        if artifact["resources"]["peak_rss_bytes"] is not None
    ]
    peak_methods = sorted(
        {
            artifact["resources"]["peak_rss_method"]
            for artifact in ordered
            if artifact["resources"]["peak_rss_method"] is not None
        }
    )
    report = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "analysis_mode": analysis_mode,
        "plan_sha256": plan["plan_sha256"],
        "cell_count": len(ordered),
        "available_cell_count": len(ordered),
        "missing_cell_ids": missing,
        "pair_counts": {axis: len(value) for axis, value in pairs.items()},
        "pairs": pairs,
        "axis_status": axis_status,
        "bath_resolution": bath_resolution,
        "convergence_claim": claim,
        "claim_blockers": blockers,
        "calibration_telemetry": {
            "observed_cell_count": len(ordered),
            "total_wall_time_seconds": sum(
                artifact["resources"]["wall_time_seconds"]
                for artifact in ordered
            ),
            "max_peak_rss_bytes": max(peak_values, default=None),
            "peak_rss_unavailable_count": len(ordered) - len(peak_values),
            "peak_rss_methods": peak_methods,
        },
        "policy": (
            "beta=16/32 remains unaccepted until bath size, timestep, and "
            "maxdim axes all pass and a validated N_b=48 solver capability is "
            "allowlisted; detected non-monotonic timestep behavior always "
            "blocks a claim"
        ),
    }
    report["analysis_sha256"] = analysis_sha256(report)
    validate_artifact_schema(report, "convergenceAnalysis")
    return report


def analysis_sha256(analysis: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in analysis.items()
        if key != "analysis_sha256"
    }
    return _sha256(_canonical_json(payload))


def analyze_cells(
    plan: dict[str, Any], artifacts: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    ordered, missing = _analysis_inputs(plan, artifacts)
    if missing:
        raise ValueError(f"missing completed cells: {missing}")
    return _build_analysis(
        plan, ordered, missing, analysis_mode="complete"
    )


def analyze_available_cells(
    plan: dict[str, Any], artifacts: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    ordered, missing = _analysis_inputs(plan, artifacts)
    if not ordered:
        raise ValueError("incomplete analysis requires at least one valid cell")
    return _build_analysis(
        plan,
        ordered,
        missing,
        analysis_mode="incomplete_calibration",
    )


def estimate_plan_resources(plan: dict[str, Any]) -> dict[str, Any]:
    validate_plan(plan)
    estimates = []
    for cell in plan["cells"]:
        beta = cell["parameters"]["beta"]
        n_bath = cell["parameters"]["n_bath"]
        settings = cell["solver_settings"]
        sites = 2 * (n_bath + 1)
        mpo_width = 4 * n_bath + 4
        maxdim = settings["maxdim"]
        steps = math.ceil(beta / settings["time_step"])
        branches = 1 + 2 * sum(
            fraction not in (0.0, 1.0) for fraction in cell["tau_fractions"]
        )
        raw_rss = JULIA_PROCESS_BASE_RSS_BYTES + int(
            8 * sites * mpo_width * maxdim**2
        )
        raw_wall = JULIA_PROCESS_STARTUP_SECONDS + (
            steps
            * branches
            * sites
            * mpo_width
            * (maxdim / 128) ** 3
            * 1.0e-6
        )
        estimates.append(
            {
                "cell_id": cell["cell_id"],
                "n_bath": n_bath,
                "estimated_peak_rss_bytes": math.ceil(
                    raw_rss * MEMORY_SAFETY_FACTOR
                ),
                "estimated_wall_seconds": raw_wall * WALL_SAFETY_FACTOR,
                "raw_peak_rss_bytes": raw_rss,
                "raw_wall_seconds": raw_wall,
                "steps": steps,
                "branch_equivalents": branches,
                "direct_star_mpo_width_estimate": mpo_width,
                "requires_chain_mapping_optimization": n_bath == 48,
                "execution_permitted": n_bath != 48,
            }
        )
    max_rss = max(item["estimated_peak_rss_bytes"] for item in estimates)
    max_wall = max(item["estimated_wall_seconds"] for item in estimates)
    recommendation = (
        "cluster_array"
        if max_rss >= LOCAL_RSS_LIMIT_BYTES
        or max_wall >= LOCAL_WALL_LIMIT_SECONDS
        or plan["stage"] == "production"
        else "local_pilot"
    )
    artifact = {
        "schema_version": 1,
        "artifact_type": "resource_estimate",
        "generator": {"name": "convergence.py", "version": MODULE_VERSION},
        "software_version": SOFTWARE_VERSION,
        "plan_sha256": plan["plan_sha256"],
        "cell_count": len(estimates),
        "model": {
            "memory_scaling": "O(L * W * maxdim^2)",
            "work_scaling": "O(steps * L * W * maxdim^3)",
            "startup_seconds_per_cell": JULIA_PROCESS_STARTUP_SECONDS,
            "baseline_rss_bytes_per_cell": JULIA_PROCESS_BASE_RSS_BYTES,
            "status": (
                "conservative planning heuristic including Julia process "
                "startup; calibrate tensor-work coefficient from pilot telemetry"
            ),
        },
        "safety_factors": {
            "memory": MEMORY_SAFETY_FACTOR,
            "wall": WALL_SAFETY_FACTOR,
        },
        "local_limits": {
            "wall_seconds": LOCAL_WALL_LIMIT_SECONDS,
            "peak_rss_bytes": LOCAL_RSS_LIMIT_BYTES,
        },
        "max_estimated_peak_rss_bytes": max_rss,
        "max_estimated_wall_seconds": max_wall,
        "recommendation": recommendation,
        "calibrated_recommendation": {
            "execution": "staged_cluster_array",
            "start_with": "N_b=12 dt/maxdim sweeps before bath trend",
            "n_bath_48": (
                "do not submit direct-star production cell until chain mapping "
                "or equivalent scalable MPO optimization is implemented and calibrated"
            ),
        },
        "direct_star_mpo_assessment": {
            "n_bath_48_feasible": False,
            "reason": (
                "98 interleaved sites plus O(N_b) long-range star-MPO width makes "
                "TDVP work and memory estimates unsuitable for an uncalibrated run"
            ),
            "required_optimization": "star-to-chain mapping or equivalent compressed MPO",
        },
        "cells": estimates,
    }
    artifact["resource_sha256"] = resource_sha256(artifact)
    validate_artifact_schema(artifact, "resourceEstimate")
    return artifact


def _load_json(path: Path, name: str) -> Any:
    return acceptance.strict_json_loads(
        path.read_text(encoding="utf-8"), name=name
    )


PLAN_RUN_CORE_FILES = {"plan.json", "resources.json", "completion.json"}
PLAN_RUN_ALLOWED_ENTRIES = {
    *PLAN_RUN_CORE_FILES,
    "cells",
    "checkpoints",
    "analysis.json",
}


def _plan_completion_sha256(completion: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in completion.items()
        if key != "completion_sha256"
    }
    return _sha256(_canonical_json(payload))


def validate_published_plan_run(
    run_directory: str | os.PathLike[str],
    *,
    expected_plan: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Validate the immutable plan/resources publication envelope."""

    root = Path(run_directory)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("published run must be a real directory")
    entries = {path.name for path in root.iterdir()}
    missing = PLAN_RUN_CORE_FILES - entries
    unexpected = entries - PLAN_RUN_ALLOWED_ENTRIES
    if missing or unexpected:
        raise ValueError(
            f"published run bundle mismatch: missing={sorted(missing)} "
            f"unexpected={sorted(unexpected)}"
        )
    for name in PLAN_RUN_CORE_FILES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"published run entry must be a real file: {name}")
    plan = _load_json(root / "plan.json", "published convergence plan")
    validate_plan(plan)
    if expected_plan is not None and plan != expected_plan:
        raise ValueError("published plan does not match requested plan")
    resources = _load_json(root / "resources.json", "published resources")
    validate_resources(resources, plan)
    completion = _load_json(root / "completion.json", "plan completion")
    required_completion = {
        "schema_version",
        "run_id",
        "plan_sha256",
        "resource_sha256",
        "artifact_file_sha256",
        "completion_sha256",
    }
    if not isinstance(completion, dict) or set(completion) != required_completion:
        raise ValueError("plan completion keys do not match schema")
    if completion["schema_version"] != 1:
        raise ValueError("unsupported plan completion schema")
    if (
        completion["run_id"] != plan["run_id"]
        or completion["plan_sha256"] != plan["plan_sha256"]
        or completion["resource_sha256"] != resources["resource_sha256"]
    ):
        raise ValueError("plan completion identity mismatch")
    expected_hashes = {
        "plan.json": _sha256_file(root / "plan.json"),
        "resources.json": _sha256_file(root / "resources.json"),
    }
    if completion["artifact_file_sha256"] != expected_hashes:
        raise ValueError("plan completion file hashes mismatch")
    if _digest(
        completion["completion_sha256"], "plan completion SHA256"
    ) != _plan_completion_sha256(completion):
        raise ValueError("plan completion SHA256 mismatch")
    return plan, resources, completion


def recover_plan_publication_state(
    output_root: str | os.PathLike[str],
) -> list[Path]:
    """Archive plan publication staging trees left by abrupt termination."""

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    recovered = []
    for path in root.glob(".run.stage-*"):
        archived = _unused_sibling(root, ".run.abandoned-stage-")
        os.replace(path, archived)
        recovered.append(archived)
    if recovered:
        _fsync_directory(root)
    return recovered


def _validate_current_pointer(
    run_directory: Path,
    *,
    plan: dict[str, Any],
    resources: dict[str, Any],
    completion: dict[str, Any],
) -> None:
    pointer_path = run_directory.parent / "current.json"
    if not pointer_path.exists():
        return
    if not pointer_path.is_file() or pointer_path.is_symlink():
        raise ValueError("current pointer must be a regular non-symlink file")
    pointer = _load_json(pointer_path, "current run pointer")
    expected = {
        "schema_version": 1,
        "run_id": plan["run_id"],
        "plan_sha256": plan["plan_sha256"],
        "resource_sha256": resources["resource_sha256"],
        "completion_sha256": completion["completion_sha256"],
        "relative_path": run_directory.name,
    }
    if not isinstance(pointer, dict):
        raise TypeError("current run pointer must be an object")
    if set(pointer) != set(expected):
        raise ValueError("current run pointer keys do not match schema")
    if pointer["schema_version"] != 1:
        raise ValueError("unsupported current run pointer schema")
    for name in (
        "plan_sha256",
        "resource_sha256",
        "completion_sha256",
    ):
        _digest(pointer[name], f"current pointer {name}")
    run_id = pointer["run_id"]
    if (
        not isinstance(run_id, str)
        or not run_id.startswith("run-")
        or len(run_id) != 20
        or pointer["relative_path"] != run_id
    ):
        raise ValueError("current run pointer identity is malformed")
    refers_to_run = (
        pointer.get("run_id") == plan["run_id"]
        or pointer.get("relative_path") == run_directory.name
    )
    if refers_to_run and pointer != expected:
        raise ValueError("current pointer does not match the published run")


def validate_analysis_artifact(
    path: str | os.PathLike[str],
    *,
    plan: dict[str, Any],
    artifacts: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Validate and independently recompute a convergence analysis artifact."""

    analysis_path = Path(path)
    if not analysis_path.is_file() or analysis_path.is_symlink():
        raise ValueError("analysis.json must be a regular non-symlink file")
    analysis = _load_json(analysis_path, "convergence analysis")
    validate_artifact_schema(analysis, "convergenceAnalysis")
    if analysis.get("plan_sha256") != plan["plan_sha256"]:
        raise ValueError("analysis plan SHA256 does not match plan")
    if _digest(
        analysis.get("analysis_sha256"), "analysis SHA256"
    ) != analysis_sha256(analysis):
        raise ValueError("analysis SHA256 mismatch")
    mode = analysis.get("analysis_mode")
    if mode == "complete":
        expected = analyze_cells(plan, artifacts)
    elif mode == "incomplete_calibration":
        expected = analyze_available_cells(plan, artifacts)
    else:
        raise ValueError("unsupported analysis mode")
    if analysis != expected:
        raise ValueError("analysis semantics do not match completed cells")
    return analysis


def validate_existing(
    *,
    plan_path: str | os.PathLike[str],
    resources_path: str | os.PathLike[str] | None = None,
    run_directory: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Fail closed unless every existing generated artifact is current."""

    plan = _load_json(Path(plan_path), "convergence plan")
    validate_plan(plan)
    checked = {
        "plan": True,
        "resources": False,
        "cells": 0,
        "checkpoints": 0,
        "archived_cells": 0,
        "archived_checkpoints": 0,
        "analysis": False,
    }
    if resources_path is not None:
        resources = _load_json(Path(resources_path), "resource estimate")
        validate_resources(resources, plan)
        checked["resources"] = True
    if run_directory is not None:
        root = Path(run_directory)
        published_plan, published_resources, completion = (
            validate_published_plan_run(root, expected_plan=plan)
        )
        _validate_current_pointer(
            root,
            plan=published_plan,
            resources=published_resources,
            completion=completion,
        )
        if Path(plan_path).resolve() != (root / "plan.json").resolve():
            raise ValueError("run directory must use its bundled plan.json")
        if resources_path is not None:
            if Path(resources_path).resolve() != (
                root / "resources.json"
            ).resolve():
                raise ValueError(
                    "run directory must use its bundled resources.json"
                )
            if published_resources != resources:
                raise ValueError("bundled resources changed during validation")
        plan = published_plan
        cells_root = root / "cells"
        expected_cells = {cell["cell_id"]: cell for cell in plan["cells"]}
        expected_ids = set(expected_cells)
        if cells_root.exists():
            if not cells_root.is_dir() or cells_root.is_symlink():
                raise ValueError("cells must be a real directory")
            for entry in cells_root.iterdir():
                name = entry.name
                if name in expected_ids:
                    continue
                if name == ".locks":
                    if not entry.is_dir() or entry.is_symlink():
                        raise ValueError("cell locks must be a real directory")
                    expected_locks = {f"{cell_id}.lock" for cell_id in expected_ids}
                    unexpected_locks = {
                        path.name for path in entry.iterdir()
                    } - expected_locks
                    if unexpected_locks:
                        raise ValueError(
                            f"unexpected stale cell locks: {sorted(unexpected_locks)}"
                        )
                    continue
                if any(
                    name.startswith(f".{cell_id}.superseded-")
                    or name.startswith(f".{cell_id}.abandoned-")
                    for cell_id in expected_ids
                ):
                    if not entry.is_dir() or entry.is_symlink():
                        raise ValueError(
                            f"cell archive must be a real directory: {name}"
                        )
                    checked["archived_cells"] += 1
                    continue
                raise ValueError(f"unexpected stale cell entry: {name}")
        checkpoints_root = root / "checkpoints"
        if checkpoints_root.exists() or checkpoints_root.is_symlink():
            if (
                not checkpoints_root.is_dir()
                or checkpoints_root.is_symlink()
            ):
                raise ValueError("checkpoints must be a real directory")
            for entry in list(checkpoints_root.iterdir()):
                name = entry.name
                if name in expected_ids:
                    with cell_advisory_lock(cells_root, name):
                        try:
                            validate_checkpoint_root(
                                entry, cell=expected_cells[name]
                            )
                        except (OSError, TypeError, ValueError) as error:
                            archived = archive_superseded_directory(entry)
                            raise ValueError(
                                "invalid checkpoint was archived at "
                                f"{archived}: {error}"
                            ) from error
                    checked["checkpoints"] += 1
                    continue
                if any(
                    name.startswith(f".{cell_id}.superseded-")
                    for cell_id in expected_ids
                ):
                    if not entry.is_dir() or entry.is_symlink():
                        raise ValueError(
                            "checkpoint archive must be a real directory: "
                            f"{name}"
                        )
                    checked["archived_checkpoints"] += 1
                    continue
                raise ValueError(f"unexpected checkpoint entry: {name}")
        artifacts = []
        for cell in plan["cells"]:
            directory = root / "cells" / cell["cell_id"]
            if not directory.exists():
                continue
            artifact = _load_json(directory / "cell.json", "completed cell")
            validate_cell_artifact(
                artifact,
                expected_cell=cell,
                artifact_directory=directory,
            )
            artifacts.append(artifact)
            checked["cells"] += 1
        analysis_path = root / "analysis.json"
        if analysis_path.exists() or analysis_path.is_symlink():
            validate_analysis_artifact(
                analysis_path,
                plan=plan,
                artifacts=artifacts,
            )
            checked["analysis"] = True
    return {"valid": True, **checked}


def _save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    acceptance.atomic_write_json(path, value)


def create_plan_run(
    output_root: str | os.PathLike[str], plan: dict[str, Any]
) -> Path:
    """Create one immutable content-addressed run directory."""

    validate_plan(plan)
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    recover_plan_publication_state(root)
    run_directory = root / plan["run_id"]
    if run_directory.exists() or run_directory.is_symlink():
        existing_plan, resources, completion = validate_published_plan_run(
            run_directory, expected_plan=plan
        )
        if existing_plan != plan:
            raise ValueError("immutable run contains a different plan")
    else:
        resources = estimate_plan_resources(plan)
        staging = Path(tempfile.mkdtemp(dir=root, prefix=".run.stage-"))
        plan_path = staging / "plan.json"
        resources_path = staging / "resources.json"
        _write_canonical(plan_path, plan)
        _write_canonical(resources_path, resources)
        completion = {
            "schema_version": 1,
            "run_id": plan["run_id"],
            "plan_sha256": plan["plan_sha256"],
            "resource_sha256": resources["resource_sha256"],
            "artifact_file_sha256": {
                "plan.json": _sha256_file(plan_path),
                "resources.json": _sha256_file(resources_path),
            },
        }
        completion["completion_sha256"] = _plan_completion_sha256(completion)
        _write_canonical(staging / "completion.json", completion)
        _fsync_directory(staging)
        validate_published_plan_run(staging, expected_plan=plan)
        os.replace(staging, run_directory)
        _fsync_directory(root)
    plan_path = run_directory / "plan.json"
    acceptance.atomic_write_json(
        root / "current.json",
        {
            "schema_version": 1,
            "run_id": plan["run_id"],
            "plan_sha256": plan["plan_sha256"],
            "resource_sha256": resources["resource_sha256"],
            "completion_sha256": completion["completion_sha256"],
            "relative_path": plan["run_id"],
        },
    )
    _fsync_directory(root)
    return plan_path


def _parse_csv(value: str, converter: Callable[[str], Any]) -> list[Any]:
    return [converter(item) for item in value.split(",") if item]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_output = plan_parser.add_mutually_exclusive_group(required=True)
    plan_output.add_argument("--output", type=Path)
    plan_output.add_argument("--output-root", type=Path)
    plan_parser.add_argument("--stage", choices=("pilot", "production"), default="production")
    plan_parser.add_argument("--betas", default="16,32")
    plan_parser.add_argument("--bath-sizes")
    plan_parser.add_argument("--time-steps")
    plan_parser.add_argument("--cutoffs", default="1e-12")
    plan_parser.add_argument("--maxdims")
    plan_parser.add_argument("--tau-fractions", default="0,0.25,0.5,0.75,1")
    plan_parser.add_argument("--julia-project", type=Path, default=JULIA_DIR)

    estimate_parser = subparsers.add_parser("estimate")
    estimate_parser.add_argument("--plan", type=Path, required=True)
    estimate_parser.add_argument("--output", type=Path)

    cell_parser = subparsers.add_parser("run-cell")
    cell_parser.add_argument("--plan", type=Path, required=True)
    cell_parser.add_argument("--run-directory", type=Path, required=True)
    cell_parser.add_argument("--cell-index", type=int)
    cell_parser.add_argument("--julia", type=Path)
    cell_parser.add_argument("--julia-project", type=Path)
    cell_parser.add_argument("--resources", type=Path)
    cell_parser.add_argument("--acknowledge-resources")
    cell_parser.add_argument("--execution-target", choices=("local", "cluster"), default="local")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--plan", type=Path, required=True)
    run_parser.add_argument("--run-directory", type=Path, required=True)
    run_parser.add_argument("--julia", type=Path)
    run_parser.add_argument("--julia-project", type=Path)
    run_parser.add_argument("--resources", type=Path)
    run_parser.add_argument("--acknowledge-resources")
    run_parser.add_argument("--execution-target", choices=("local", "cluster"), default="local")

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--plan", type=Path, required=True)
    analyze_parser.add_argument("--run-directory", type=Path, required=True)
    analyze_parser.add_argument("--output", type=Path)
    analyze_parser.add_argument("--allow-incomplete", action="store_true")
    validate_parser = subparsers.add_parser("validate-existing")
    validate_parser.add_argument("--plan", type=Path, required=True)
    validate_parser.add_argument("--resources", type=Path)
    validate_parser.add_argument("--run-directory", type=Path)
    args = parser.parse_args(argv)

    if args.command == "plan":
        plan = make_plan(
            betas=_parse_csv(args.betas, float),
            bath_sizes=(
                _parse_csv(args.bath_sizes, int) if args.bath_sizes else None
            ),
            time_steps=(
                _parse_csv(args.time_steps, float) if args.time_steps else None
            ),
            cutoffs=_parse_csv(args.cutoffs, float),
            maxdims=_parse_csv(args.maxdims, int) if args.maxdims else None,
            tau_fractions=_parse_csv(args.tau_fractions, float),
            stage=args.stage,
            julia_project=args.julia_project,
        )
        if args.output_root is not None:
            output = create_plan_run(args.output_root, plan)
        else:
            if args.output.exists() or args.output.is_symlink():
                raise ValueError(
                    "refusing to supersede an existing generated plan"
                )
            _save_json(args.output, plan)
            output = args.output
        print(
            f"planned cells={len(plan['cells'])} sha256={plan['plan_sha256']} "
            f"output={output}",
            flush=True,
        )
        return 0
    if args.command == "validate-existing":
        result = validate_existing(
            plan_path=args.plan,
            resources_path=args.resources,
            run_directory=args.run_directory,
        )
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    plan = _load_json(args.plan, "convergence plan")
    validate_plan(plan)
    if args.command == "estimate":
        estimate = estimate_plan_resources(plan)
        if args.output:
            _save_json(args.output, estimate)
        print(json.dumps(estimate, sort_keys=True), flush=True)
        return 0
    if args.command in {"run-cell", "run"}:
        if args.julia_project is None:
            raise ValueError(
                "run and run-cell require --julia-project at execution time"
            )
        resources = None
        if plan["stage"] == "production":
            run_root = args.run_directory.resolve()
            if args.plan.resolve() != (run_root / "plan.json").resolve():
                raise ValueError(
                    "production execution requires a published bundled plan.json"
                )
            _published_plan, bundled_resources, _completion = (
                validate_published_plan_run(run_root, expected_plan=plan)
            )
            if args.resources is not None and args.resources.resolve() != (
                run_root / "resources.json"
            ).resolve():
                raise ValueError(
                    "production execution requires bundled resources.json"
                )
            resources = bundled_resources
        elif args.resources is not None:
            resources = _load_json(args.resources, "resource estimate")
        if args.command == "run-cell":
            raw_index = (
                args.cell_index
                if args.cell_index is not None
                else os.environ.get("HARNESS_CELL_INDEX")
                or os.environ.get("SLURM_ARRAY_TASK_ID")
            )
            if raw_index is None:
                raise ValueError(
                    "set --cell-index, HARNESS_CELL_INDEX, or SLURM_ARRAY_TASK_ID"
                )
            try:
                indices = [int(raw_index)]
            except (TypeError, ValueError):
                print(
                    f"progress cell={raw_index} id=unresolved action=failed "
                    "category=input_validation error=cell index must be an integer",
                    flush=True,
                )
                return 1
        else:
            indices = list(range(len(plan["cells"])))
        failures = 0
        for index in indices:
            cell_id = (
                plan["cells"][index]["cell_id"]
                if 0 <= index < len(plan["cells"])
                else "out-of-range"
            )
            try:
                result = run_cell(
                    plan,
                    index,
                    args.run_directory,
                    julia_executable=args.julia,
                    julia_project=args.julia_project,
                    resources=resources,
                    resource_acknowledgment=args.acknowledge_resources,
                    execution_target=args.execution_target,
                )
                print(
                    f"progress cell={index} id={cell_id} "
                    f"action={result['action']}",
                    flush=True,
                )
            except ContinuationAvailable as continuation:
                print(
                    f"progress cell={index} id={cell_id} "
                    f"action=continuation checkpoint={continuation.checkpoint}",
                    flush=True,
                )
                if args.command == "run-cell":
                    return 75
                return 75
            except BaseException as error:
                failures += 1
                print(
                    f"progress cell={index} id={cell_id} "
                    f"action=failed category={classify_failure(error)} "
                    f"error={error}",
                    flush=True,
                )
        return 1 if failures else 0
    validate_existing(
        plan_path=args.plan,
        run_directory=args.run_directory,
    )
    artifacts = []
    for cell in plan["cells"]:
        path = args.run_directory / "cells" / cell["cell_id"] / "cell.json"
        if path.is_file():
            artifacts.append(_load_json(path, f"cell {cell['cell_id']}"))
    report = (
        analyze_available_cells(plan, artifacts)
        if args.allow_incomplete
        else analyze_cells(plan, artifacts)
    )
    output = args.output or (args.run_directory / "analysis.json")
    _save_json(output, report)
    print(
        f"analysis convergence_claim={report['convergence_claim']} "
        f"output={output}",
        flush=True,
    )
    return 0 if report["convergence_claim"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
