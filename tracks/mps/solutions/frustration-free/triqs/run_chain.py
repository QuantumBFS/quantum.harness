"""Run and atomically publish one validated Challenge 81 CT-HYB chain."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import math
import os
from pathlib import Path
import platform
import resource
import socket
import stat
import sys
import time
from types import SimpleNamespace
from typing import Any
import uuid

from jsonschema import Draft202012Validator
import numpy as np

from artifacts import (
    _directory_descriptor,
    _read_regular_file,
    atomic_write_bytes,
    canonical_json,
    sha256_bytes,
    sha256_file,
    strict_json_load,
)
from hybridization import install_g0, reported_tau_indices
from make_input import verify_input
import make_input as input_builder
from source_manifest import build_source_manifest


SOLUTION_DIR = Path(__file__).resolve().parent
SCHEMA_VERSION = 2
RAW_ARCHIVE_MEMBERS = (
    "input_bytes",
    "input_sha256",
    "input_payload_sha256",
    "chain_index",
    "seed",
    "G0_iw",
    "Delta_iw",
    "G_iw",
    "G_tau",
    "density_matrix",
    "h_loc_diagonalization",
    "perturbation_order",
    "average_sign",
    "auto_corr_time",
    "auto_corr_time_converged",
    "solve_parameters",
    "solve_status",
    "last_configuration",
    "runtime",
)
_THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
)
_BUNDLE_FILES = {
    "raw.h5",
    "chain-summary.json",
    "completion.json",
    "stdout.log",
    "stderr.log",
}


def _solver_class():
    from triqs_cthyb import Solver

    return Solver


def _archive_class():
    from h5 import HDFArchive

    return HDFArchive


def _number_operator(spin: str, orbital: int):
    from triqs.operators import n

    return n(spin, orbital)


def _trace_rho_op(density_matrix, operator, h_loc_diagonalization):
    from triqs.atom_diag import trace_rho_op

    return trace_rho_op(density_matrix, operator, h_loc_diagonalization)


def _mpi_size() -> int:
    from triqs.utility import mpi

    return int(mpi.size)


def _conda_package_version(prefix: Path, name: str) -> str:
    records = sorted((prefix / "conda-meta").glob(f"{name}-*.json"))
    if len(records) != 1:
        raise ValueError(f"locked prefix must contain exactly one {name} record")
    record = strict_json_load(records[0])
    if (
        not isinstance(record, dict)
        or record.get("name") != name
        or not isinstance(record.get("version"), str)
    ):
        raise ValueError(f"invalid locked conda record for {name}")
    return record["version"]


def _runtime_identity() -> dict[str, str]:
    prefix = Path(sys.prefix)
    identity = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "triqs": _conda_package_version(prefix, "triqs"),
        "triqs_cthyb": _conda_package_version(prefix, "triqs_cthyb"),
        "hdf5": _conda_package_version(prefix, "hdf5"),
    }
    if not identity["python"].startswith("3.12."):
        raise RuntimeError("locked CT-HYB runtime requires Python 3.12")
    for name in ("triqs", "triqs_cthyb"):
        if identity[name] != "4.0.0":
            raise RuntimeError(f"locked CT-HYB runtime requires {name}=4.0.0")
    return identity


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_runtime_shape() -> dict[str, str]:
    size = _mpi_size()
    if size != 1:
        raise RuntimeError(f"CT-HYB production requires exactly one MPI rank, got {size}")
    values: dict[str, str] = {}
    for name in _THREAD_VARIABLES:
        value = os.environ.get(name)
        if value != "1":
            raise RuntimeError(f"{name} must be exactly 1")
        values[name] = value
    return values


def _validate_chain_index(chain_index: object, payload: dict[str, object]) -> int:
    if isinstance(chain_index, bool) or not isinstance(chain_index, int):
        raise TypeError("chain_index must be an integer")
    chains = payload["chains"]
    assert isinstance(chains, dict)
    count = chains["count"]
    if chain_index < 0 or chain_index >= count:
        raise ValueError(f"chain_index must be in [0, {count - 1}]")
    return chain_index


def make_test_pilot_input(
    production_artifact: dict[str, object],
) -> dict[str, object]:
    """Derive the one allowed bounded test profile from a verified production input."""
    production_payload = verify_input(production_artifact, SOLUTION_DIR)
    payload = copy.deepcopy(production_payload)
    payload["artifact_type"] = "cthyb_test_input"
    payload["monte_carlo"]["warmup_cycles"] = 50
    payload["monte_carlo"]["measurement_cycles"] = 200
    payload["gates"]["minimum_effective_samples_per_chain"] = 1
    payload["gates"]["minimum_effective_samples_total"] = 4
    return _artifact(payload)


def make_source_bound_test_pilot_input(
    solution_dir: Path = SOLUTION_DIR,
) -> dict[str, object]:
    """Build the bounded test profile without claiming accepted calibration."""
    repository_root = solution_dir.resolve().parents[4]
    manifest = build_source_manifest(repository_root)
    model, model_conventions = input_builder._load_model(solution_dir)
    omega, delta = input_builder._matsubara_data()
    marker = {
        "artifact_type": "cthyb_test_calibration_marker",
        "schema_version": 2,
        "status": "not_run",
    }
    payload = {
        "artifact_type": "cthyb_test_input",
        "schema_version": input_builder.SCHEMA_VERSION,
        "model": model,
        "conventions": input_builder._production_conventions(model_conventions),
        "hybridization": {
            "kind": "analytic_semicircle",
            "formula": (
                "Delta(iw) = i*(Gamma/D)*(w-sign(w)*sqrt(w*w+D*D))"
            ),
            "dtype": "complex128",
            "n_iw": input_builder.N_IW,
            "matsubara_omega": omega,
            "delta_iw": delta,
            "common_real_frequency": {
                **input_builder.COMMON_REAL_FREQUENCY,
                "sha256": input_builder.COMMON_REAL_FREQUENCY_SHA256,
            },
        },
        "meshes": {
            "n_tau": input_builder.N_TAU,
            "reported_tau": [0.0, 4.0, 8.0, 12.0, 16.0],
        },
        "chains": {
            "count": 4,
            "random_generator": "mt19937",
            "master_seed": 810000,
            "seeds": [810001, 810002, 810003, 810004],
        },
        "monte_carlo": {
            "warmup_cycles": 50,
            "measurement_cycles": 200,
            "cycle_length": 50,
            "measure_G_tau": True,
            "measure_density_matrix": True,
            "use_norm_as_weight": True,
            "measure_pert_order": True,
        },
        "gates": {
            "minimum_average_sign": 0.99,
            "require_autocorrelation_converged": True,
            "maximum_integrated_autocorrelation_cycles": 5.0,
            "minimum_effective_samples_per_chain": 1,
            "minimum_effective_samples_total": 4,
            "maximum_spin_asymmetry": 0.005,
            "maximum_half_filling_error": 0.005,
            "minimum_completed_chains": 4,
        },
        "runtime": {"mpi_ranks_per_chain": 1, "threads_per_rank": 1},
        "calibration": {
            "artifact_sha256": sha256_bytes(canonical_json(marker)),
        },
        "provenance_inputs": input_builder._provenance_hashes(manifest),
    }
    artifact = _artifact(payload)
    _verify_chain_input(artifact)
    return artifact


def _verify_chain_input(artifact: dict[str, object]) -> dict[str, object]:
    payload = artifact.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("chain input payload must be an object")
    if payload.get("artifact_type") == "cthyb_production_input":
        return verify_input(artifact, SOLUTION_DIR)
    if payload.get("artifact_type") != "cthyb_test_input":
        raise ValueError("unsupported chain input artifact type")
    production_payload = copy.deepcopy(payload)
    production_payload["artifact_type"] = "cthyb_production_input"
    monte_carlo = production_payload.get("monte_carlo")
    if not isinstance(monte_carlo, dict):
        raise ValueError("test input Monte Carlo controls are malformed")
    if (
        monte_carlo.get("warmup_cycles") != 50
        or monte_carlo.get("measurement_cycles") != 200
    ):
        raise ValueError("test input must use the exact bounded pilot controls")
    gates = production_payload.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("test input gates are malformed")
    if (
        gates.get("minimum_effective_samples_per_chain") != 1
        or gates.get("minimum_effective_samples_total") != 4
    ):
        raise ValueError("test input must use the exact bounded pilot gates")
    monte_carlo["warmup_cycles"] = 50000
    monte_carlo["measurement_cycles"] = 1000000
    gates["minimum_effective_samples_per_chain"] = 100000
    gates["minimum_effective_samples_total"] = 400000
    production_artifact = _artifact(production_payload)
    verify_input(production_artifact, SOLUTION_DIR)
    if artifact.get("sha256") != sha256_bytes(canonical_json(payload)):
        raise ValueError("test input payload hash mismatch")
    return payload


def _green_blocks(value: Any) -> dict[str, np.ndarray]:
    try:
        indices = tuple(value.indices)
        result = {
            name: np.asarray(value[name].data[:, 0, 0], dtype=np.complex128)
            for name in indices
        }
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        if isinstance(value, dict) and set(value) == {"up", "down"}:
            result = {
                name: np.asarray(value[name], dtype=np.complex128)
                for name in ("up", "down")
            }
        else:
            raise ValueError("Green-function blocks are malformed") from error
    if set(result) != {"up", "down"}:
        raise ValueError("Green-function blocks must be exactly up and down")
    if any(array.ndim != 1 for array in result.values()):
        raise ValueError("Green-function block arrays must be one-dimensional")
    if any(
        not np.all(np.isfinite(array.real)) or not np.all(np.isfinite(array.imag))
        for array in result.values()
    ):
        raise ValueError("Green-function block arrays must be finite")
    return result


def _finite_scalar(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a real number")
    try:
        converted_complex = complex(value)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must be a real number") from error
    if not math.isfinite(converted_complex.real) or not math.isfinite(
        converted_complex.imag
    ):
        raise ValueError(f"{name} must be finite")
    if abs(converted_complex.imag) > 1.0e-12:
        raise ValueError(f"{name} must be real within tolerance")
    converted = float(converted_complex.real)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _normal_solve_status(value: object) -> str:
    if isinstance(value, bool):
        raise ValueError(f"solver status is not normal: {value!r}")
    if value == "normal" or value == 0:
        return "normal"
    raise ValueError(f"solver status is not normal: {value!r}")


def _real_green_values(
    blocks: dict[str, np.ndarray],
    indices: list[int],
) -> tuple[list[float], list[float]]:
    result: list[list[float]] = []
    for spin in ("up", "down"):
        array = blocks[spin]
        if not indices or max(indices) >= len(array):
            raise ValueError("G_tau does not cover the reported tau mesh")
        selected = array[indices]
        if np.any(np.abs(selected.imag) > 1.0e-12):
            raise ValueError("reported G_tau values must be real within tolerance")
        result.append([float(value) for value in selected.real])
    return result[0], result[1]


def extract_chain_observables(
    solver: Any,
    payload: dict[str, object],
    solve_parameters: dict[str, object] | None = None,
) -> dict[str, object]:
    """Extract all per-chain scientific values from measured solver state."""
    density_matrix = getattr(solver, "density_matrix", None)
    h_loc = getattr(solver, "h_loc_diagonalization", None)
    if density_matrix is None or h_loc is None:
        raise ValueError("measured density matrix evidence is missing")
    up = _number_operator("up", 0)
    down = _number_operator("down", 0)
    n_up = _finite_scalar(_trace_rho_op(density_matrix, up, h_loc), "n_up")
    n_down = _finite_scalar(_trace_rho_op(density_matrix, down, h_loc), "n_down")
    double = _finite_scalar(
        _trace_rho_op(density_matrix, up * down, h_loc),
        "double_occupancy",
    )

    model = payload["model"]
    meshes = payload["meshes"]
    assert isinstance(model, dict) and isinstance(meshes, dict)
    tau = meshes["reported_tau"]
    assert isinstance(tau, list)
    indices = reported_tau_indices(model["beta"], meshes["n_tau"], tau)
    g_up, g_down = _real_green_values(_green_blocks(solver.G_tau), indices)

    status = _normal_solve_status(getattr(solver, "solve_status", None))
    average_sign = _finite_scalar(
        getattr(solver, "average_sign", None),
        "average_sign",
    )
    auto_corr_time = _finite_scalar(
        getattr(solver, "auto_corr_time", None),
        "auto_corr_time",
    )
    converged = getattr(solver, "auto_corr_time_converged", None)
    if converged is not True:
        raise ValueError("autocorrelation estimate is unconverged")
    monte_carlo = payload["monte_carlo"]
    gates = payload["gates"]
    assert isinstance(monte_carlo, dict) and isinstance(gates, dict)
    if average_sign < gates["minimum_average_sign"]:
        raise ValueError("average sign is below the per-chain gate")
    if auto_corr_time < 0.0 or auto_corr_time > gates[
        "maximum_integrated_autocorrelation_cycles"
    ]:
        raise ValueError("autocorrelation time is outside the per-chain gate")
    effective_samples = math.floor(
        monte_carlo["measurement_cycles"] / (2.0 * max(1.0, auto_corr_time))
    )
    if effective_samples < gates["minimum_effective_samples_per_chain"]:
        raise ValueError("effective sample count is below the per-chain gate")
    return {
        "observables": {
            "n_up": n_up,
            "n_down": n_down,
            "n_d": n_up + n_down,
            "double_occupancy": double,
            "G_up": g_up,
            "G_down": g_down,
        },
        "diagnostics": {
            "average_sign": average_sign,
            "auto_corr_time": auto_corr_time,
            "auto_corr_time_converged": True,
            "effective_samples": effective_samples,
        },
        "solve": {
            "status": status,
            "parameters": _normalized_solve_parameters(
                solve_parameters
                if solve_parameters is not None
                else getattr(solver, "solve_parameters", None)
            ),
        },
    }


def _normalized_solve_parameters(parameters: object) -> dict[str, object]:
    if not isinstance(parameters, dict):
        raise ValueError("solver solve_parameters evidence is missing")
    normalized = {
        key: value
        for key, value in parameters.items()
        if key != "h_int"
    }
    normalized["h_int"] = "U*n('up',0)*n('down',0)"
    try:
        canonical_json(normalized)
    except (TypeError, ValueError) as error:
        raise ValueError("solve parameters are not canonically serializable") from error
    return normalized


def _solve_parameters(payload: dict[str, object], seed: int) -> dict[str, object]:
    monte_carlo = payload["monte_carlo"]
    chains = payload["chains"]
    model = payload["model"]
    assert isinstance(monte_carlo, dict)
    assert isinstance(chains, dict)
    assert isinstance(model, dict)
    if monte_carlo["use_norm_as_weight"] is not True:
        raise ValueError("use_norm_as_weight must remain true")
    up = _number_operator("up", 0)
    down = _number_operator("down", 0)
    return {
        "h_int": model["U"] * up * down,
        "random_seed": seed,
        "random_name": chains["random_generator"],
        "n_warmup_cycles": monte_carlo["warmup_cycles"],
        "n_cycles": monte_carlo["measurement_cycles"],
        "length_cycle": monte_carlo["cycle_length"],
        "measure_G_tau": monte_carlo["measure_G_tau"],
        "measure_density_matrix": monte_carlo["measure_density_matrix"],
        "use_norm_as_weight": monte_carlo["use_norm_as_weight"],
        "measure_pert_order": monte_carlo["measure_pert_order"],
        "performance_analysis": False,
    }


def _raw_solver_state(
    solver: Any,
    input_bytes: bytes,
    input_artifact: dict[str, object],
    chain_index: int,
    seed: int,
    runtime: dict[str, object],
    solve_parameters: dict[str, object] | None = None,
) -> dict[str, object]:
    input_payload = input_artifact["payload"]
    assert isinstance(input_payload, dict)
    hybridization = input_payload["hybridization"]
    assert isinstance(hybridization, dict)
    split_delta = hybridization["delta_iw"]
    assert isinstance(split_delta, dict)
    delta = np.asarray(split_delta["real"], dtype=np.float64) + 1j * np.asarray(
        split_delta["imag"], dtype=np.float64
    )
    return {
        "input_bytes": np.frombuffer(input_bytes, dtype=np.uint8).copy(),
        "input_sha256": input_artifact["sha256"],
        "input_payload_sha256": sha256_bytes(
            canonical_json(input_artifact["payload"])
        ),
        "chain_index": chain_index,
        "seed": seed,
        "G0_iw": _green_blocks(solver.G0_iw),
        "Delta_iw": {"up": delta.copy(), "down": delta.copy()},
        "G_iw": _green_blocks(solver.G_iw),
        "G_tau": _green_blocks(solver.G_tau),
        "density_matrix": solver.density_matrix,
        "h_loc_diagonalization": solver.h_loc_diagonalization,
        "perturbation_order": solver.perturbation_order,
        "average_sign": solver.average_sign,
        "auto_corr_time": solver.auto_corr_time,
        "auto_corr_time_converged": solver.auto_corr_time_converged,
        "solve_parameters": _normalized_solve_parameters(
            solve_parameters
            if solve_parameters is not None
            else getattr(solver, "solve_parameters", None)
        ),
        "solve_status": _normal_solve_status(solver.solve_status),
        "last_configuration": solver.last_configuration,
        "runtime": runtime,
    }


def _write_raw(path: Path, state: dict[str, object]) -> None:
    if set(state) != set(RAW_ARCHIVE_MEMBERS):
        raise ValueError("raw archive state has an unexpected inventory")
    archive_type = _archive_class()
    with archive_type(str(path), "w") as archive:
        for name in RAW_ARCHIVE_MEMBERS:
            archive[name] = state[name]
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _load_raw(path: Path) -> dict[str, object]:
    sha256_file(path)
    archive_type = _archive_class()
    with archive_type(str(path), "r") as archive:
        keys = set(archive.keys())
        if keys != set(RAW_ARCHIVE_MEMBERS):
            raise ValueError(
                "raw archive member inventory mismatch: "
                f"missing={sorted(set(RAW_ARCHIVE_MEMBERS) - keys)}, "
                f"extra={sorted(keys - set(RAW_ARCHIVE_MEMBERS))}"
            )
        return {name: archive[name] for name in RAW_ARCHIVE_MEMBERS}


def _solver_from_raw(raw: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        G_tau=raw["G_tau"],
        density_matrix=raw["density_matrix"],
        h_loc_diagonalization=raw["h_loc_diagonalization"],
        average_sign=raw["average_sign"],
        auto_corr_time=raw["auto_corr_time"],
        auto_corr_time_converged=raw["auto_corr_time_converged"],
        solve_status=raw["solve_status"],
        solve_parameters=raw["solve_parameters"],
    )


def _resource_record(
    started_utc: str,
    finished_utc: str,
    wall_seconds: float,
) -> dict[str, object]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    peak = int(usage.ru_maxrss)
    if sys.platform != "darwin":
        peak *= 1024
    slurm_names = (
        "SLURM_JOB_ID",
        "SLURM_ARRAY_JOB_ID",
        "SLURM_ARRAY_TASK_ID",
        "SLURM_CPUS_PER_TASK",
        "SLURM_NTASKS",
    )
    return {
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "wall_seconds": wall_seconds,
        "peak_rss_bytes": peak,
        "hostname": socket.gethostname(),
        "slurm": {
            name: os.environ[name]
            for name in slurm_names
            if name in os.environ
        },
    }


def _summary_payload(
    input_artifact: dict[str, object],
    chain_index: int,
    seed: int,
    raw_digest: str,
    raw: dict[str, object],
) -> dict[str, object]:
    input_payload = input_artifact["payload"]
    assert isinstance(input_payload, dict)
    extracted = extract_chain_observables(_solver_from_raw(raw), input_payload)
    provenance = input_payload["provenance_inputs"]
    assert isinstance(provenance, dict)
    runtime = raw["runtime"]
    assert isinstance(runtime, dict)
    return {
        "artifact_type": "cthyb_chain_summary",
        "schema_version": SCHEMA_VERSION,
        "chain_id": f"chain-{chain_index:03d}",
        "chain_index": chain_index,
        "seed": seed,
        "input_sha256": input_artifact["sha256"],
        "input_payload_sha256": sha256_bytes(canonical_json(input_payload)),
        "raw_h5_sha256": raw_digest,
        "raw_archive_members": list(RAW_ARCHIVE_MEMBERS),
        "model": input_payload["model"],
        "reported_tau": input_payload["meshes"]["reported_tau"],
        **extracted,
        "resources": runtime["resources"],
        "provenance": {
            "source_manifest": provenance["source_manifest"],
            "source_manifest_sha256": provenance["source_manifest_sha256"],
            "conda_lock_sha256": provenance["conda_lock_sha256"],
            "environment_yml_sha256": provenance["environment_yml_sha256"],
            "runtime": runtime["versions"],
        },
    }


def _artifact(payload: dict[str, object]) -> dict[str, object]:
    return {
        "payload": payload,
        "sha256": sha256_bytes(canonical_json(payload)),
    }


def _chain_schema() -> dict[str, object]:
    value = strict_json_load(SOLUTION_DIR / "cthyb-chain.schema.json")
    if not isinstance(value, dict):
        raise ValueError("chain schema must be an object")
    Draft202012Validator.check_schema(value)
    return value


def _validate_schema(artifact: object) -> None:
    errors = sorted(
        Draft202012Validator(_chain_schema()).iter_errors(artifact),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ValueError(f"chain schema validation failed: {errors[0].message}")


def _strict_artifact(path: Path) -> dict[str, object]:
    value = strict_json_load(path)
    if not isinstance(value, dict):
        raise ValueError(f"artifact must be an object: {path}")
    expected = canonical_json(value) + b"\n"
    if _read_regular_file(path) != expected:
        raise ValueError(f"artifact is not canonical newline-terminated JSON: {path}")
    payload = value.get("payload")
    if not isinstance(payload, dict) or value.get("sha256") != sha256_bytes(
        canonical_json(payload)
    ):
        raise ValueError(f"artifact payload hash mismatch: {path}")
    _validate_schema(value)
    return value


def _require_bundle_directory(path: Path) -> None:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"chain bundle must be a non-symlink directory: {path}")
    names = {child.name for child in path.iterdir()}
    if names != _BUNDLE_FILES:
        raise ValueError(
            f"chain bundle file inventory mismatch: "
            f"missing={sorted(_BUNDLE_FILES - names)}, "
            f"extra={sorted(names - _BUNDLE_FILES)}"
        )
    for child in path.iterdir():
        child_metadata = child.lstat()
        if stat.S_ISLNK(child_metadata.st_mode):
            raise ValueError(f"symlink is forbidden in chain bundle: {child}")
        if not stat.S_ISREG(child_metadata.st_mode):
            raise ValueError(f"regular file required in chain bundle: {child}")


def validate_chain_bundle(
    path: Path,
    input_artifact: dict[str, object],
    chain_index: int,
) -> dict[str, object]:
    """Fully reload and validate an immutable chain bundle."""
    input_payload = _verify_chain_input(input_artifact)
    index = _validate_chain_index(chain_index, input_payload)
    expected_seed = input_payload["chains"]["seeds"][index]
    _require_bundle_directory(path)
    summary = _strict_artifact(path / "chain-summary.json")
    completion = _strict_artifact(path / "completion.json")
    if summary["payload"]["artifact_type"] != "cthyb_chain_summary":
        raise ValueError("chain summary artifact type mismatch")
    if completion["payload"]["artifact_type"] != "cthyb_chain_completion":
        raise ValueError("chain completion artifact type mismatch")
    payload = summary["payload"]
    assert isinstance(payload, dict)
    for name, expected in (
        ("chain_id", f"chain-{index:03d}"),
        ("chain_index", index),
        ("seed", expected_seed),
        ("input_sha256", input_artifact["sha256"]),
        ("input_payload_sha256", sha256_bytes(canonical_json(input_payload))),
    ):
        if payload[name] != expected:
            raise ValueError(f"chain summary binding mismatch: {name}")
    raw_digest = sha256_file(path / "raw.h5")
    if payload["raw_h5_sha256"] != raw_digest:
        raise ValueError("raw.h5 byte SHA256 mismatch")
    raw = _load_raw(path / "raw.h5")
    expected_input_bytes = canonical_json(input_artifact) + b"\n"
    if bytes(np.asarray(raw["input_bytes"], dtype=np.uint8)) != expected_input_bytes:
        raise ValueError("raw input bytes mismatch")
    for name, expected in (
        ("input_sha256", input_artifact["sha256"]),
        ("input_payload_sha256", sha256_bytes(canonical_json(input_payload))),
        ("chain_index", index),
        ("seed", expected_seed),
    ):
        if raw[name] != expected:
            raise ValueError(f"raw archive binding mismatch: {name}")
    reproduced = _summary_payload(
        input_artifact,
        index,
        expected_seed,
        raw_digest,
        raw,
    )
    if canonical_json(payload) != canonical_json(reproduced):
        raise ValueError("chain summary is not reproducible from raw evidence")
    completion_payload = completion["payload"]
    assert isinstance(completion_payload, dict)
    expected_completion = {
        "artifact_type": "cthyb_chain_completion",
        "schema_version": SCHEMA_VERSION,
        "chain_index": index,
        "seed": expected_seed,
        "input_sha256": input_artifact["sha256"],
        "chain_summary_sha256": summary["sha256"],
        "raw_h5_sha256": raw_digest,
    }
    if completion_payload != expected_completion:
        raise ValueError("chain completion binding mismatch")
    return payload


def _ensure_directory(path: Path) -> None:
    descriptor = _directory_descriptor(path, create=True)
    os.close(descriptor)


def _archive_abandoned(work: Path, chain_id: str) -> None:
    for attempt in sorted(work.glob(f".attempt-{chain_id}-*")):
        metadata = attempt.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"unsafe abandoned attempt: {attempt}")
        destination = work / f".abandoned-{chain_id}-{uuid.uuid4().hex}"
        os.rename(attempt, destination)


def _lock_chain(work: Path, chain_id: str) -> int:
    path = work / f".{chain_id}.lock"
    descriptor = os.open(
        path,
        os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"regular chain lock required: {path}")
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    return descriptor


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_bundle(path: Path) -> None:
    for child in path.iterdir():
        descriptor = os.open(
            child,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    _fsync_directory(path)


def _write_attempt_file(path: Path, value: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | os.O_NOFOLLOW,
        0o600,
    )
    try:
        view = memoryview(value)
        while view:
            view = view[os.write(descriptor, view) :]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def run_chain(input_path: Path, chain_index: int, output_root: Path) -> Path:
    """Run one production chain and atomically publish its validated bundle."""
    runtime_threads = _require_runtime_shape()
    input_bytes = _read_regular_file(input_path)
    input_artifact = strict_json_load(input_path)
    if not isinstance(input_artifact, dict):
        raise ValueError("input artifact must be an object")
    if input_bytes != canonical_json(input_artifact) + b"\n":
        raise ValueError("input artifact must be canonical newline-terminated JSON")
    payload = _verify_chain_input(input_artifact)
    index = _validate_chain_index(chain_index, payload)
    seed = payload["chains"]["seeds"][index]
    chain_id = f"chain-{index:03d}"

    work = output_root / "work" / input_artifact["sha256"]
    _ensure_directory(work)
    lock_descriptor = _lock_chain(work, chain_id)
    try:
        destination = work / chain_id
        if destination.exists() or destination.is_symlink():
            validate_chain_bundle(destination, input_artifact, index)
            return destination
        _archive_abandoned(work, chain_id)
        attempt = work / f".attempt-{chain_id}-{uuid.uuid4().hex}"
        attempt.mkdir(mode=0o700)
        _fsync_directory(work)

        model = payload["model"]
        meshes = payload["meshes"]
        hybridization = payload["hybridization"]
        assert isinstance(model, dict)
        assert isinstance(meshes, dict)
        assert isinstance(hybridization, dict)
        solver_type = _solver_class()
        solver = solver_type(
            beta=model["beta"],
            gf_struct=[("up", 1), ("down", 1)],
            n_iw=hybridization["n_iw"],
            n_tau=meshes["n_tau"],
        )
        install_g0(solver, payload)
        parameters = _solve_parameters(payload, seed)
        started_utc = _utc_now()
        started = time.monotonic()
        solver.solve(**parameters)
        wall_seconds = time.monotonic() - started
        finished_utc = _utc_now()
        extract_chain_observables(solver, payload, parameters)
        resources = _resource_record(started_utc, finished_utc, wall_seconds)
        runtime = {
            "versions": _runtime_identity(),
            "threads": runtime_threads,
            "resources": resources,
        }
        raw_state = _raw_solver_state(
            solver,
            input_bytes,
            input_artifact,
            index,
            seed,
            runtime,
            parameters,
        )
        raw_path = attempt / "raw.h5"
        _write_raw(raw_path, raw_state)
        raw = _load_raw(raw_path)
        raw_digest = sha256_file(raw_path)
        summary = _artifact(
            _summary_payload(
                input_artifact,
                index,
                seed,
                raw_digest,
                raw,
            )
        )
        completion = _artifact(
            {
                "artifact_type": "cthyb_chain_completion",
                "schema_version": SCHEMA_VERSION,
                "chain_index": index,
                "seed": seed,
                "input_sha256": input_artifact["sha256"],
                "chain_summary_sha256": summary["sha256"],
                "raw_h5_sha256": raw_digest,
            }
        )
        _validate_schema(summary)
        _validate_schema(completion)
        _write_attempt_file(
            attempt / "chain-summary.json",
            canonical_json(summary) + b"\n",
        )
        _write_attempt_file(
            attempt / "completion.json",
            canonical_json(completion) + b"\n",
        )
        _write_attempt_file(attempt / "stdout.log", b"")
        _write_attempt_file(attempt / "stderr.log", b"")
        validate_chain_bundle(attempt, input_artifact, index)
        _fsync_bundle(attempt)
        os.rename(attempt, destination)
        _fsync_directory(work)
        validate_chain_bundle(destination, input_artifact, index)
        return destination
    finally:
        os.close(lock_descriptor)


def locked_prefix_pilot_command(
    locked_prefix: Path,
    input_path: Path,
    chain_index: int,
    output_root: Path,
) -> list[str]:
    """Return the bounded offline real-Solver pilot command without executing it."""
    if not all(path.is_absolute() for path in (locked_prefix, input_path, output_root)):
        raise ValueError("pilot paths must be absolute")
    if isinstance(chain_index, bool) or chain_index not in range(4):
        raise ValueError("pilot chain index must be 0 through 3")
    micromamba = locked_prefix.parent / "micromamba"
    return [
        "/usr/bin/env",
        "OMP_NUM_THREADS=1",
        "OPENBLAS_NUM_THREADS=1",
        "MKL_NUM_THREADS=1",
        str(micromamba),
        "run",
        "--offline",
        "--prefix",
        str(locked_prefix),
        "python",
        str(SOLUTION_DIR / "run_chain.py"),
        "--input",
        str(input_path),
        "--chain-index",
        str(chain_index),
        "--output-root",
        str(output_root),
        "--test-pilot",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--chain-index", type=int, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--test-pilot", action="store_true")
    arguments = parser.parse_args()
    if not arguments.test_pilot:
        run_chain(arguments.input, arguments.chain_index, arguments.output_root)
        return
    production = strict_json_load(arguments.input)
    if not isinstance(production, dict):
        raise ValueError("production input must be an object")
    pilot = make_test_pilot_input(production)
    pilot_path = arguments.output_root / "test-pilot-input.json"
    atomic_write_bytes(pilot_path, canonical_json(pilot) + b"\n")
    run_chain(pilot_path, arguments.chain_index, arguments.output_root)


if __name__ == "__main__":
    main()
