"""Immutable adaptive temperature-ladder planning and measured selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
import json
import math
from pathlib import Path
import shutil
import tempfile

import numpy as np
from scipy.special import erfcinv

from vmcrg_ref.artifacts import (
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
    verified_promote_directory,
)

from .pilot import (
    CALIBRATION_COMPLETE,
    CalibrationCheckpointParent,
    CalibrationExtensionSpec,
    CalibrationSpec,
    run_ladder_calibration_extension,
    run_ladder_calibration,
)


TRACK_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = TRACK_ROOT.parents[2]
TARGET_ACCEPTANCES = (0.35, 0.40)
SOURCE_EDGE_COUNT = 47
MEASURED_ACCEPTANCE_MINIMUM = 0.20
MEASURED_ACCEPTANCE_MAXIMUM = 0.50
MEASURED_ROUND_TRIPS_MINIMUM = 1

_SOURCE_NAMES = (
    "jobs/hard_goal_ladder_scan.slurm",
    "scripts/hard_goal_ladder_scan_cell.py",
    "src/spinglass3d/backend.py",
    "src/spinglass3d/jax_backend.py",
    "src/spinglass3d/ladder_scan.py",
    "src/spinglass3d/model.py",
    "src/spinglass3d/pilot.py",
    "src/vmcrg_ref/artifacts.py",
)

_EXTENSION_SOURCE_NAMES = (
    "jobs/hard_goal_ladder_extension.slurm",
    "scripts/hard_goal_ladder_extension_cell.py",
    "src/spinglass3d/backend.py",
    "src/spinglass3d/jax_backend.py",
    "src/spinglass3d/ladder_scan.py",
    "src/spinglass3d/model.py",
    "src/spinglass3d/pilot.py",
    "src/vmcrg_ref/artifacts.py",
)

_EXTENSION_CELL_FIELDS = {
    "array_index",
    "cell_id",
    "extension_spec",
    "extension_spec_sha256",
    "output",
}

_EXTENSION_RUNTIME_FIELDS = {
    "host",
    "python",
    "jax",
    "jaxlib",
    "default_backend",
    "devices",
    "x64_enabled",
    "elapsed_seconds",
    "spin_proposals",
    "spin_proposals_per_second",
    "invocation_spin_proposals",
    "peak_host_memory_bytes",
    "peak_device_memory_bytes",
    "backend_compile_seconds",
    "checkpoint_bytes",
}


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and not any(
        character not in "0123456789abcdef" for character in value
    )


def _safe_component(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
    ):
        raise ValueError(f"{name} must be one safe path component")
    return value


def _load_json_object(path: Path, name: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not readable JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must contain a JSON object")
    try:
        canonical_json_bytes(payload)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} contains noncanonical values") from error
    return payload


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(TRACK_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_from_track(value: object, track_root: Path, name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} is missing")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (track_root / path).resolve()


def _artifact_inventory(root: Path, *, exclude: set[str]) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() not in exclude
    }


def _verify_source_artifacts(
    source_root: Path,
    artifact_hashes: object,
) -> dict[str, str]:
    if not isinstance(artifact_hashes, dict) or not artifact_hashes:
        raise ValueError("source artifact inventory is missing")
    normalized = {str(name): str(digest) for name, digest in artifact_hashes.items()}
    if any(not _valid_sha256(digest) for digest in normalized.values()):
        raise ValueError("source artifact inventory contains an invalid SHA-256")
    actual_inventory = _artifact_inventory(source_root, exclude={"manifest.json"})
    if set(normalized) != actual_inventory:
        raise ValueError("source artifact inventory does not match the source cell")
    for relative, expected in sorted(normalized.items()):
        if sha256_file(source_root / relative) != expected:
            raise ValueError(f"source artifact hash mismatch: {relative}")
    return normalized


def _calibration_spec_from_payload(value: object, name: str) -> CalibrationSpec:
    if not isinstance(value, dict):
        raise ValueError(f"{name} is missing")
    expected = {
        "cell_id",
        "length",
        "temperatures",
        "chain_pairs",
        "calibration_sweeps",
        "j_seed",
        "swap_bottleneck",
        "swap_target_minimum",
        "swap_target_maximum",
        "source_hashes",
    }
    if set(value) != expected:
        raise ValueError(f"{name} fields are incomplete or unknown")
    try:
        return CalibrationSpec(
            cell_id=value["cell_id"],
            length=value["length"],
            temperatures=tuple(value["temperatures"]),
            chain_pairs=value["chain_pairs"],
            calibration_sweeps=value["calibration_sweeps"],
            j_seed=value["j_seed"],
            swap_bottleneck=value["swap_bottleneck"],
            swap_target_minimum=value["swap_target_minimum"],
            swap_target_maximum=value["swap_target_maximum"],
            source_hashes=value["source_hashes"],
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{name} is invalid: {error}") from error


def _edge_arrays(
    parallel_tempering: Mapping[str, object],
    *,
    expected_edges: int,
    name: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    raw_attempts = parallel_tempering.get("edge_attempts")
    raw_accepts = parallel_tempering.get("edge_accepts")
    raw_acceptance = parallel_tempering.get("edge_acceptance")
    if not all(isinstance(value, list) for value in (raw_attempts, raw_accepts, raw_acceptance)):
        raise ValueError(f"{name} edge arrays are missing")
    if not (
        len(raw_attempts) == len(raw_accepts) == len(raw_acceptance) == expected_edges
    ):
        raise ValueError(f"{name} must contain exactly {expected_edges} edges")
    if any(type(value) is not int or value <= 0 for value in raw_attempts):
        raise ValueError(f"{name} edge attempts must be positive integers")
    if any(type(value) is not int for value in raw_accepts):
        raise ValueError(f"{name} edge accepts must be integers")
    attempts = np.asarray(raw_attempts, dtype=np.int64)
    accepts = np.asarray(raw_accepts, dtype=np.int64)
    try:
        acceptance = np.asarray(raw_acceptance, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} edge acceptance must be numeric") from error
    if (
        np.any(accepts < 0)
        or np.any(accepts > attempts)
        or not np.all(np.isfinite(acceptance))
        or np.any(acceptance < 0.0)
        or np.any(acceptance > 1.0)
        or not np.allclose(
            acceptance,
            accepts / attempts,
            rtol=0.0,
            atol=np.finfo(np.float64).eps,
        )
    ):
        raise ValueError(f"{name} edge counts and acceptance are inconsistent")
    return attempts, accepts, acceptance


def _load_source_manifest(
    source_manifest: str | Path,
    source_sha256: str,
) -> tuple[Path, dict[str, object], CalibrationSpec, np.ndarray, np.ndarray]:
    if not _valid_sha256(source_sha256):
        raise ValueError("source manifest SHA-256 is invalid")
    source = Path(source_manifest).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"source calibration manifest is missing: {source}")
    actual_sha256 = sha256_file(source)
    if actual_sha256 != source_sha256:
        raise ValueError(
            "source manifest SHA-256 mismatch: "
            f"expected {source_sha256}, got {actual_sha256}"
        )
    payload = _load_json_object(source, "source calibration manifest")
    if payload.get("schema_version") != 1 or payload.get("stage") != "stage6":
        raise ValueError("source calibration manifest schema is unsupported")
    if payload.get("classification") != CALIBRATION_COMPLETE:
        raise ValueError("source calibration classification must be CALIBRATION_COMPLETE")
    if payload.get("status") != "complete" or payload.get("scope") != (
        "stage6-ladder-calibration-only"
    ):
        raise ValueError("source calibration manifest is not a completed ladder calibration")
    if payload.get("tc_evidence") is not False or payload.get("second_rg_enabled") is not False:
        raise ValueError("source calibration must not be Tc or second-RG evidence")

    source_spec = _calibration_spec_from_payload(payload.get("spec"), "source spec")
    if payload.get("cell_id") != source_spec.cell_id:
        raise ValueError("source calibration cell ID does not match its spec")
    if payload.get("spec_sha256") != source_spec.sha256:
        raise ValueError("source calibration spec SHA-256 mismatch")
    if payload.get("completed_sweeps") != source_spec.calibration_sweeps:
        raise ValueError("source calibration did not complete its declared sweep budget")
    if len(source_spec.temperatures) != SOURCE_EDGE_COUNT + 1:
        raise ValueError(f"source calibration must contain exactly {SOURCE_EDGE_COUNT} edges")
    betas = 1.0 / np.asarray(source_spec.temperatures, dtype=np.float64)
    if betas[0] != 0.5 or betas[-1] != 1.25 or np.any(np.diff(betas) <= 0.0):
        raise ValueError("source calibration beta ladder must run strictly from 0.5 to 1.25")

    parallel = payload.get("parallel_tempering")
    if not isinstance(parallel, dict):
        raise ValueError("source parallel-tempering record is missing")
    if parallel.get("all_edges_attempted") is not True:
        raise ValueError("source calibration did not attempt every edge")
    if parallel.get("ladder_decision") != "RECALIBRATE":
        raise ValueError("source ladder decision must be RECALIBRATE")
    _, _, acceptance = _edge_arrays(
        parallel,
        expected_edges=SOURCE_EDGE_COUNT,
        name="source calibration",
    )
    if np.any(acceptance <= 0.0) or np.any(acceptance >= 1.0):
        raise ValueError("source edge acceptance must lie strictly between zero and one")
    attempts = np.asarray(parallel["edge_attempts"], dtype=np.float64)
    _verify_source_artifacts(source.parent, payload.get("artifact_hashes"))
    return source, payload, source_spec, acceptance, attempts


def _proxy_record(
    acceptance: np.ndarray,
    attempts: np.ndarray,
) -> tuple[dict[str, object], np.ndarray]:
    ell = np.asarray(erfcinv(acceptance), dtype=np.float64)
    sigma_acceptance = np.sqrt(acceptance * (1.0 - acceptance) / attempts)
    sigma_ell = 0.5 * math.sqrt(math.pi) * np.exp(ell * ell) * sigma_acceptance
    if (
        not np.all(np.isfinite(ell))
        or np.any(ell <= 0.0)
        or not np.all(np.isfinite(sigma_ell))
    ):
        raise ValueError("source acceptance does not define a finite positive proxy metric")
    ell_total = float(np.sum(ell, dtype=np.float64))
    sigma_total = float(math.sqrt(float(np.sum(sigma_ell * sigma_ell))))
    cumulative = np.concatenate((np.zeros(1, dtype=np.float64), np.cumsum(ell)))
    return (
        {
            "classification": "PREDICTED_ONLY",
            "measured_success": False,
            "metric": "erfc_inverse_acceptance_length",
            "formula": {
                "edge_metric": "ell_i = erfcinv(A_i)",
                "acceptance_uncertainty": (
                    "sigma_A_i = sqrt(A_i * (1 - A_i) / n_i)"
                ),
                "edge_metric_uncertainty": (
                    "sigma_ell_i = (sqrt(pi) / 2) * exp(ell_i**2) * sigma_A_i"
                ),
                "total_metric": "ell_total = sum_i ell_i",
                "total_uncertainty": "sigma_total = sqrt(sum_i sigma_ell_i**2)",
                "edge_count": "ceil(ell_total / erfcinv(A_target))",
                "interpolation": (
                    "linear beta interpolation at equally spaced cumulative-ell coordinates"
                ),
            },
            "source_edge_count": int(acceptance.size),
            "ell_total": ell_total,
            "sigma_ell_total": sigma_total,
            "edge_ell": [float(value) for value in ell],
            "edge_sigma_ell": [float(value) for value in sigma_ell],
            "cumulative_ell": [float(value) for value in cumulative],
        },
        cumulative,
    )


def _candidate(
    *,
    source_spec: CalibrationSpec,
    source_betas: np.ndarray,
    proxy: Mapping[str, object],
    cumulative_ell: np.ndarray,
    target_acceptance: float,
    run_dir: str,
    array_index: int,
) -> dict[str, object]:
    target_metric = float(erfcinv(target_acceptance))
    ell_total = float(proxy["ell_total"])
    sigma_total = float(proxy["sigma_ell_total"])
    edge_count = int(math.ceil(ell_total / target_metric))
    minimum_edges = int(math.ceil(max(0.0, ell_total - sigma_total) / target_metric))
    maximum_edges = int(math.ceil((ell_total + sigma_total) / target_metric))
    target_coordinates = np.linspace(0.0, ell_total, edge_count + 1)
    betas = np.interp(target_coordinates, cumulative_ell, source_betas)
    betas[0] = source_betas[0]
    betas[-1] = source_betas[-1]
    if np.any(np.diff(betas) <= 0.0):
        raise ValueError("adaptive beta interpolation is not strictly increasing")
    temperatures = 1.0 / betas
    cell_id = f"{source_spec.cell_id}-A{int(round(100 * target_acceptance)):03d}"
    prediction = {
        "classification": "PREDICTED_ONLY",
        "measured_success": False,
        "target_acceptance": target_acceptance,
        "edge_count": edge_count,
        "temperature_count": edge_count + 1,
        "one_sigma_edge_count_min": minimum_edges,
        "one_sigma_edge_count_max": maximum_edges,
        "one_sigma_temperature_count_min": minimum_edges + 1,
        "one_sigma_temperature_count_max": maximum_edges + 1,
    }
    return {
        "array_index": array_index,
        "cell_id": cell_id,
        "params": {
            "stage": "stage6",
            "phase": "adaptive_temperature_ladder_scan",
            "target_acceptance": target_acceptance,
            "length": source_spec.length,
            "j_seed": source_spec.j_seed,
            "chain_pairs": source_spec.chain_pairs,
            "calibration_sweeps": source_spec.calibration_sweeps,
            "betas": [float(value) for value in betas],
            "temperatures": [float(value) for value in temperatures],
            "prediction": prediction,
            "output": f"{run_dir}/cells/{cell_id}",
        },
    }


def build_ladder_scan_spec(
    source_manifest: str | Path,
    source_sha256: str,
    run_id: str,
) -> dict[str, object]:
    """Build two paired, predicted-only ladders from one verified calibration."""

    safe_run_id = _safe_component(run_id, "run_id")
    source, payload, source_spec, acceptance, attempts = _load_source_manifest(
        source_manifest,
        source_sha256,
    )
    proxy, cumulative = _proxy_record(acceptance, attempts)
    source_betas = 1.0 / np.asarray(source_spec.temperatures, dtype=np.float64)
    run_dir = f"results/hard_goal/{safe_run_id}"
    cells = [
        _candidate(
            source_spec=source_spec,
            source_betas=source_betas,
            proxy=proxy,
            cumulative_ell=cumulative,
            target_acceptance=target,
            run_dir=run_dir,
            array_index=index,
        )
        for index, target in enumerate(TARGET_ACCEPTANCES, start=1)
    ]
    source_paths = {name: TRACK_ROOT / name for name in _SOURCE_NAMES}
    missing = [name for name, path in source_paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"ladder-scan source inventory is incomplete: {missing}")
    source_hashes = {
        name: sha256_file(path) for name, path in sorted(source_paths.items())
    }
    return {
        "schema_version": 1,
        "stage": "stage6",
        "phase": "adaptive_temperature_ladder_scan",
        "classification": "PLANNED",
        "scientific_evidence": False,
        "tc_evidence": False,
        "second_rg_enabled": False,
        "run_id": safe_run_id,
        "run_dir": run_dir,
        "axes": {"target_acceptance": list(TARGET_ACCEPTANCES)},
        "array": {"count": len(cells), "index_origin": 1},
        "settings": {
            "sampling": {
                "length": source_spec.length,
                "j_seed": source_spec.j_seed,
                "chain_pairs": source_spec.chain_pairs,
                "calibration_sweeps": source_spec.calibration_sweeps,
            },
            "thresholds": {
                "swap_bottleneck": source_spec.swap_bottleneck,
                "swap_target_minimum": MEASURED_ACCEPTANCE_MINIMUM,
                "swap_target_maximum": MEASURED_ACCEPTANCE_MAXIMUM,
                "round_trips_minimum": MEASURED_ROUND_TRIPS_MINIMUM,
            },
            "proxy": proxy,
            "second_rg": False,
        },
        "provenance": {
            "source_manifest": _display_path(source),
            "source_manifest_sha256": source_sha256,
            "source_spec_sha256": source_spec.sha256,
            "source_artifact_hashes": dict(payload["artifact_hashes"]),
            "source_sha256": source_hashes,
            "claims": [
                "adaptive ladder proxy predictions only",
                "measured calibration required before selection",
                "paired source disorder seed and sampling budget",
                "no second RG",
                "not Tc evidence",
            ],
        },
        "cells": cells,
    }


def prepare_ladder_scan(
    source_manifest: str | Path,
    source_sha256: str,
    run_id_or_output: str | Path,
    output: str | Path | None = None,
) -> dict[str, object]:
    """Publish an immutable run package without performing calibration."""

    if output is None:
        destination = Path(run_id_or_output).resolve()
        run_id = destination.name
    else:
        run_id = str(run_id_or_output)
        destination = Path(output).resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite ladder-scan package: {destination}")
    run_spec = build_ladder_scan_spec(source_manifest, source_sha256, run_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.ladder-scan-",
            dir=destination.parent,
        )
    )
    try:
        run_spec_path = staging / "run_spec.json"
        atomic_write_json(run_spec_path, run_spec)
        artifacts = {"run_spec.json": sha256_file(run_spec_path)}
        package = {
            "schema_version": 1,
            "stage": "stage6",
            "phase": "adaptive_temperature_ladder_scan",
            "classification": "PLANNED",
            "scientific_evidence": False,
            "tc_evidence": False,
            "second_rg_enabled": False,
            "cell_count": len(run_spec["cells"]),
            "source_manifest_sha256": source_sha256,
            "artifacts": artifacts,
        }
        manifest_path = staging / "manifest.json"
        atomic_write_json(manifest_path, package)
        verified_promote_directory(
            staging,
            destination,
            {**artifacts, "manifest.json": sha256_file(manifest_path)},
        )
        return package
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _load_verified_run_spec(
    run_spec: str | Path,
    *,
    track_root: str | Path,
    require_current_sources: bool = True,
) -> tuple[dict[str, object], Path, str]:
    path = Path(run_spec).resolve()
    payload = _load_json_object(path, "ladder-scan run spec")
    package_path = path.parent / "manifest.json"
    package = _load_json_object(package_path, "ladder-scan package manifest")
    artifacts = package.get("artifacts")
    if (
        package.get("schema_version") != 1
        or package.get("stage") != "stage6"
        or package.get("phase") != "adaptive_temperature_ladder_scan"
        or package.get("classification") != "PLANNED"
        or package.get("scientific_evidence") is not False
        or package.get("tc_evidence") is not False
        or package.get("second_rg_enabled") is not False
        or not isinstance(artifacts, dict)
        or set(artifacts) != {"run_spec.json"}
    ):
        raise ValueError("ladder-scan package manifest is invalid")
    run_spec_sha256 = sha256_file(path)
    if artifacts.get("run_spec.json") != run_spec_sha256:
        raise ValueError("ladder-scan package hash does not match run_spec.json")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("ladder-scan run spec provenance is missing")
    source = _resolve_from_track(
        provenance.get("source_manifest"),
        Path(track_root).resolve(),
        "source calibration manifest",
    )
    source_sha256 = provenance.get("source_manifest_sha256")
    if not isinstance(source_sha256, str):
        raise ValueError("source calibration manifest SHA-256 is missing")
    expected = build_ladder_scan_spec(source, source_sha256, payload.get("run_id"))
    if not require_current_sources:
        recorded_sources = provenance.get("source_sha256")
        if (
            not isinstance(recorded_sources, dict)
            or set(recorded_sources) != set(_SOURCE_NAMES)
            or any(not _valid_sha256(digest) for digest in recorded_sources.values())
        ):
            raise ValueError("historical ladder-scan source hashes are invalid")
        expected["provenance"]["source_sha256"] = dict(recorded_sources)
    if payload != expected:
        raise ValueError("run spec differs from the fixed generated scan")
    if package.get("cell_count") != len(payload["cells"]):
        raise ValueError("ladder-scan package cell count is inconsistent")
    if package.get("source_manifest_sha256") != source_sha256:
        raise ValueError("ladder-scan package source hash is inconsistent")
    return payload, path, run_spec_sha256


def _resolve_cell(payload: Mapping[str, object], selector: str | int) -> dict[str, object]:
    cells = payload["cells"]
    if isinstance(selector, int) or (isinstance(selector, str) and selector.isdigit()):
        index = int(selector)
        matches = [cell for cell in cells if cell.get("array_index") == index]
    else:
        matches = [cell for cell in cells if cell.get("cell_id") == selector]
    if len(matches) != 1:
        raise KeyError(f"unknown or nonunique ladder-scan cell selector: {selector!r}")
    return matches[0]


def _planned_calibration_spec(
    payload: Mapping[str, object],
    run_spec_sha256: str,
    cell: Mapping[str, object],
) -> CalibrationSpec:
    params = cell.get("params")
    settings = payload.get("settings")
    provenance = payload.get("provenance")
    if not isinstance(params, dict) or not isinstance(settings, dict) or not isinstance(
        provenance, dict
    ):
        raise ValueError("ladder-scan cell contract is incomplete")
    thresholds = settings.get("thresholds")
    source_hashes = provenance.get("source_sha256")
    if not isinstance(thresholds, dict) or not isinstance(source_hashes, dict):
        raise ValueError("ladder-scan settings or source hashes are incomplete")
    bound_hashes = {
        "run_spec.json": run_spec_sha256,
        "source_calibration_manifest.json": provenance["source_manifest_sha256"],
        **{str(name): str(digest) for name, digest in sorted(source_hashes.items())},
    }
    return CalibrationSpec(
        cell_id=str(cell["cell_id"]),
        length=params["length"],
        temperatures=tuple(params["temperatures"]),
        chain_pairs=params["chain_pairs"],
        calibration_sweeps=params["calibration_sweeps"],
        j_seed=params["j_seed"],
        swap_bottleneck=thresholds["swap_bottleneck"],
        swap_target_minimum=thresholds["swap_target_minimum"],
        swap_target_maximum=thresholds["swap_target_maximum"],
        source_hashes=bound_hashes,
    )


def _cell_output(
    payload: Mapping[str, object],
    cell: Mapping[str, object],
    repo_root: Path,
) -> Path:
    raw_output = Path(str(cell["params"]["output"]))
    output = (
        raw_output.resolve()
        if raw_output.is_absolute()
        else (repo_root / raw_output).resolve()
    )
    allowed = (repo_root / "results" / "hard_goal").resolve()
    if not output.is_relative_to(allowed):
        raise ValueError("ladder-scan cell output escapes results/hard_goal")
    expected_parent = (allowed / str(payload["run_id"]) / "cells").resolve()
    if output.parent != expected_parent:
        raise ValueError("ladder-scan cell output does not match its run namespace")
    return output


def load_ladder_scan_cell(
    run_spec: str | Path,
    selector: str | int,
    *,
    track_root: str | Path = TRACK_ROOT,
    repo_root: str | Path = REPO_ROOT,
) -> tuple[CalibrationSpec, Path]:
    """Rebuild a hash-bound run spec and resolve one opaque scan cell."""

    payload, _, run_spec_sha256 = _load_verified_run_spec(
        run_spec,
        track_root=track_root,
    )
    cell = _resolve_cell(payload, selector)
    spec = _planned_calibration_spec(payload, run_spec_sha256, cell)
    return spec, _cell_output(payload, cell, Path(repo_root).resolve())


def run_ladder_scan_cell(
    run_spec: str | Path,
    selector: str | int,
    *,
    required_platform: str,
    checkpoint_every: int,
    resume: bool = False,
    track_root: str | Path = TRACK_ROOT,
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, object]:
    """Execute one planned scan cell through the existing calibration runner."""

    spec, output = load_ladder_scan_cell(
        run_spec,
        selector,
        track_root=track_root,
        repo_root=repo_root,
    )
    return run_ladder_calibration(
        spec,
        output,
        required_platform=required_platform,
        checkpoint_every=checkpoint_every,
        resume=resume,
    )


def _extension_source_hashes(track_root: Path = TRACK_ROOT) -> dict[str, str]:
    paths = {name: track_root / name for name in _EXTENSION_SOURCE_NAMES}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"extension source inventory is incomplete: {missing}")
    return {name: sha256_file(path) for name, path in sorted(paths.items())}


def _sole_extension_cell(
    run_spec: Mapping[str, object],
    package: Mapping[str, object],
    name: str,
) -> dict[str, object]:
    cells = run_spec.get("cells")
    array = run_spec.get("array")
    run_id = _safe_component(run_spec.get("run_id"), f"{name} run_id")
    expected_run_dir = f"results/hard_goal/{run_id}"
    if (
        type(package.get("cell_count")) is not int
        or package.get("cell_count") != 1
        or not isinstance(array, dict)
        or set(array) != {"count", "index_origin"}
        or type(array.get("count")) is not int
        or type(array.get("index_origin")) is not int
        or array != {"count": 1, "index_origin": 1}
        or run_spec.get("run_dir") != expected_run_dir
        or not isinstance(cells, list)
        or len(cells) != 1
        or not isinstance(cells[0], dict)
        or set(cells[0]) != _EXTENSION_CELL_FIELDS
        or type(cells[0].get("array_index")) is not int
        or cells[0].get("array_index") != 1
        or cells[0].get("output")
        != f"{expected_run_dir}/cells/{cells[0].get('cell_id')}"
    ):
        raise ValueError(f"{name} run spec must contain exactly one canonical cell")
    return cells[0]


def _validate_pt_checkpoint_state_file(
    state_path: Path,
    spec: CalibrationSpec | CalibrationExtensionSpec,
    *,
    completed_sweeps: int,
    name: str,
) -> dict[str, object]:
    required = {
        "spins",
        "local_jax_key",
        "local_accepted_changes",
        "local_proposed_changes",
        "swap_key",
        "replica_ids",
        "swap_attempts",
        "swap_accepts",
        "sweep_count",
        "round_trip_phase",
        "round_trips",
        "time_since_endpoint",
    }
    try:
        with np.load(state_path, allow_pickle=False) as archive:
            if set(archive.files) != required:
                raise ValueError("array inventory is incomplete")
            arrays = {item: archive[item].copy() for item in required}
    except (EOFError, OSError, ValueError) as error:
        raise ValueError(f"{name} checkpoint state is not a valid NPZ archive") from error
    temperatures = len(spec.temperatures)
    walkers = 2 * spec.chain_pairs
    spins_shape = (
        1,
        temperatures,
        walkers,
        spec.length,
        spec.length,
        spec.length,
    )
    tracker_shape = (1, walkers, temperatures)
    spins = arrays["spins"]
    local_key = arrays["local_jax_key"]
    swap_key = arrays["swap_key"]
    replica_ids = arrays["replica_ids"]
    attempts = arrays["swap_attempts"]
    accepts = arrays["swap_accepts"]
    phase = arrays["round_trip_phase"]
    trips = arrays["round_trips"]
    since = arrays["time_since_endpoint"]
    scalar_names = (
        "local_accepted_changes",
        "local_proposed_changes",
        "sweep_count",
    )
    if any(
        arrays[item].dtype != np.dtype(np.int64) or arrays[item].shape != ()
        for item in scalar_names
    ):
        raise ValueError(f"{name} checkpoint state scalar counters are invalid")
    local_accepts = int(arrays["local_accepted_changes"])
    local_proposals = int(arrays["local_proposed_changes"])
    sweep_count = int(arrays["sweep_count"])
    expected_proposals = sweep_count * spins.size
    edge_indices = np.arange(temperatures - 1, dtype=np.int64)
    expected_attempts = np.where(
        edge_indices % 2 == 0,
        (sweep_count + 1) // 2,
        sweep_count // 2,
    ) * spins_shape[0] * walkers
    maximum_round_trips = sweep_count // (2 * (temperatures - 1))
    expected_ids = np.broadcast_to(
        np.arange(temperatures, dtype=np.int64)[None, :, None],
        (1, temperatures, walkers),
    )
    permutation_ok = (
        replica_ids.shape == expected_ids.shape
        and replica_ids.dtype == np.dtype(np.int64)
        and np.array_equal(np.sort(replica_ids, axis=1), expected_ids)
    )
    if (
        spins.dtype != np.dtype(np.int8)
        or spins.shape != spins_shape
        or not np.all((spins == -1) | (spins == 1))
        or local_key.dtype != np.dtype(np.uint32)
        or local_key.shape != (2,)
        or swap_key.dtype != np.dtype(np.uint32)
        or swap_key.shape != (2,)
        or not permutation_ok
        or attempts.dtype != np.dtype(np.int64)
        or accepts.dtype != np.dtype(np.int64)
        or attempts.shape != (temperatures - 1,)
        or accepts.shape != attempts.shape
        or phase.dtype != np.dtype(np.int8)
        or trips.dtype != np.dtype(np.int64)
        or since.dtype != np.dtype(np.int64)
        or phase.shape != tracker_shape
        or trips.shape != tracker_shape
        or since.shape != tracker_shape
        or sweep_count != completed_sweeps
        or local_accepts < 0
        or local_proposals < 0
        or local_proposals != expected_proposals
        or local_accepts > local_proposals
        or np.any(attempts < 0)
        or not np.array_equal(attempts, expected_attempts)
        or np.any(accepts < 0)
        or np.any(accepts > attempts)
        or np.any((phase < 0) | (phase > 2))
        or np.any(trips < 0)
        or np.any(trips > maximum_round_trips)
        or np.any(since < 0)
        or np.any(since > sweep_count + 1)
    ):
        raise ValueError(f"{name} checkpoint state semantics are invalid")
    return {
        "local_accepted_changes": local_accepts,
        "local_proposed_changes": local_proposals,
        "swap_attempts": attempts.copy(),
        "swap_accepts": accepts.copy(),
        "sweep_count": sweep_count,
        "round_trips_min": int(np.min(trips)),
        "round_trips_max": int(np.max(trips)),
        "travel": {
            "phase_counts": {
                str(value): int(np.count_nonzero(phase == value))
                for value in range(3)
            },
            "completed_tracker_count": int(np.count_nonzero(trips > 0)),
            "endpoint_timer": {
                "minimum": int(np.min(since)),
                "maximum": int(np.max(since)),
                "mean": float(np.mean(since, dtype=np.float64)),
            },
        },
    }


def _validated_extension_checkpoint_directory(
    checkpoint: Path,
    spec: CalibrationExtensionSpec,
    *,
    name: str,
) -> tuple[dict[str, object], str, str]:
    metadata_path = checkpoint / "metadata.json"
    state_path = checkpoint / "state.npz"
    metadata = _load_json_object(metadata_path, f"{name} checkpoint metadata")
    state_sha256 = sha256_file(state_path)
    if (
        set(metadata)
        != {"schema_version", "completed_sweeps", "spec_sha256", "state_sha256"}
        or type(metadata.get("schema_version")) is not int
        or metadata.get("schema_version") != 1
        or metadata.get("completed_sweeps") != spec.target_completed_sweeps
        or metadata.get("spec_sha256") != spec.sha256
        or metadata.get("state_sha256") != state_sha256
    ):
        raise ValueError(f"{name} checkpoint binding is invalid")
    summary = _validate_pt_checkpoint_state_file(
        state_path,
        spec,
        completed_sweeps=spec.target_completed_sweeps,
        name=name,
    )
    return summary, sha256_file(metadata_path), state_sha256


def _extension_parent_checkpoint_summary(
    package_root: Path,
    spec: CalibrationExtensionSpec,
) -> dict[str, object]:
    parent_manifest_path = package_root / "parent" / "manifest.json"
    parent_checkpoint = package_root / "parent" / "checkpoint"
    if sha256_file(parent_manifest_path) != spec.parent.manifest_sha256:
        raise ValueError("bundled parent manifest hash differs from extension lineage")
    payload = _load_json_object(parent_manifest_path, "bundled extension parent manifest")
    artifact_hashes = payload.get("artifact_hashes")
    if (
        not isinstance(artifact_hashes, dict)
        or artifact_hashes.get("checkpoint/metadata.json")
        != spec.parent.checkpoint_metadata_sha256
        or artifact_hashes.get("checkpoint/state.npz")
        != spec.parent.checkpoint_state_sha256
    ):
        raise ValueError("bundled parent checkpoint artifacts differ from extension lineage")
    if spec.parent.manifest_kind == "calibration":
        parent_spec: CalibrationSpec | CalibrationExtensionSpec = (
            _calibration_spec_from_payload(payload.get("spec"), "bundled parent spec")
        )
        valid_manifest = (
            type(payload.get("schema_version")) is int
            and payload.get("schema_version") == 1
            and payload.get("stage") == "stage6"
            and payload.get("classification") == CALIBRATION_COMPLETE
            and payload.get("scope") == "stage6-ladder-calibration-only"
            and payload.get("status") == "complete"
            and payload.get("spec_sha256") == parent_spec.sha256
        )
    else:
        parent_spec = CalibrationExtensionSpec.from_payload(
            payload.get("extension_spec")
        )
        valid_manifest = (
            type(payload.get("schema_version")) is int
            and payload.get("schema_version") == 1
            and payload.get("stage") == "stage6"
            and payload.get("phase") == "calibration_extension"
            and payload.get("classification") == "CALIBRATION_EXTENSION_COMPLETE"
            and payload.get("scope")
            == "stage6-ladder-calibration-extension-only"
            and payload.get("status") == "complete"
            and payload.get("extension_spec_sha256") == parent_spec.sha256
            and payload.get("completed_sweeps")
            == parent_spec.target_completed_sweeps
        )
    if (
        not valid_manifest
        or payload.get("cell_id") != spec.parent.cell_id
        or payload.get("completed_sweeps") != spec.parent.completed_sweeps
        or parent_spec.sha256 != spec.parent.checkpoint_spec_sha256
    ):
        raise ValueError("bundled parent manifest differs from extension lineage")
    metadata_path = parent_checkpoint / "metadata.json"
    state_path = parent_checkpoint / "state.npz"
    metadata = _load_json_object(metadata_path, "bundled parent checkpoint metadata")
    if (
        sha256_file(metadata_path) != spec.parent.checkpoint_metadata_sha256
        or sha256_file(state_path) != spec.parent.checkpoint_state_sha256
        or set(metadata)
        != {"schema_version", "completed_sweeps", "spec_sha256", "state_sha256"}
        or type(metadata.get("schema_version")) is not int
        or metadata.get("schema_version") != 1
        or metadata.get("completed_sweeps") != spec.parent.completed_sweeps
        or metadata.get("spec_sha256") != spec.parent.checkpoint_spec_sha256
        or metadata.get("state_sha256") != spec.parent.checkpoint_state_sha256
    ):
        raise ValueError("bundled parent checkpoint differs from extension lineage")
    return _validate_pt_checkpoint_state_file(
        state_path,
        parent_spec,
        completed_sweeps=spec.parent.completed_sweeps,
        name="bundled extension parent",
    )


def _validate_extension_runtime_record(
    runtime: object,
    parent_summary: Mapping[str, object],
    child_summary: Mapping[str, object],
    *,
    local_execution_evidence: Mapping[str, object] | None = None,
) -> None:
    expected_spin_proposals = int(child_summary["local_proposed_changes"]) - int(
        parent_summary["local_proposed_changes"]
    )
    string_fields = ("host", "python", "jax", "jaxlib")
    integer_fields = (
        "spin_proposals",
        "invocation_spin_proposals",
        "peak_host_memory_bytes",
        "peak_device_memory_bytes",
        "checkpoint_bytes",
    )
    numeric_fields = (
        "elapsed_seconds",
        "spin_proposals_per_second",
        "backend_compile_seconds",
    )
    gpu_runtime = (
        isinstance(runtime, dict)
        and runtime.get("default_backend") == "gpu"
    )
    local_runtime = (
        isinstance(runtime, dict)
        and runtime.get("default_backend") == "cpu"
        and runtime.get("peak_device_memory_bytes") == 0
        and isinstance(local_execution_evidence, Mapping)
        and local_execution_evidence.get("execution_policy")
        == "LOCAL_COMPUTE_DEVIATION"
        and local_execution_evidence.get("remote_execution") is False
        and local_execution_evidence.get("runtime_backend") == "cpu"
    )
    valid = (
        isinstance(runtime, dict)
        and set(runtime) == _EXTENSION_RUNTIME_FIELDS
        and all(isinstance(runtime.get(name), str) for name in string_fields)
        and (gpu_runtime or local_runtime)
        and isinstance(runtime.get("devices"), list)
        and bool(runtime.get("devices"))
        and all(isinstance(item, str) for item in runtime.get("devices", []))
        and runtime.get("x64_enabled") is True
        and all(type(runtime.get(name)) is int for name in integer_fields)
        and all(int(runtime[name]) >= 0 for name in integer_fields)
        and all(
            not isinstance(runtime.get(name), bool)
            and isinstance(runtime.get(name), (int, float))
            and math.isfinite(float(runtime[name]))
            and float(runtime[name]) >= 0.0
            for name in numeric_fields
        )
        and runtime.get("spin_proposals") == expected_spin_proposals
        and 0
        <= int(runtime.get("invocation_spin_proposals", -1))
        <= expected_spin_proposals
    )
    if not valid:
        raise ValueError(
            "extension runtime record is missing, non-GPU without authorized "
            "local evidence, or inconsistent"
        )


def write_local_extension_evidence(
    parent_manifest: str | Path,
    coordinator_state: str | Path,
    command_id: str,
    output: str | Path,
) -> dict[str, object]:
    """Bind one completed CPU extension to its terminal local coordinator."""

    manifest_path = Path(parent_manifest).resolve()
    coordinator_path = Path(coordinator_state).resolve()
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite local execution evidence: {destination}")
    manifest = _load_json_object(manifest_path, "local extension parent manifest")
    coordinator = _load_json_object(coordinator_path, "local extension coordinator")
    runtime = manifest.get("runtime")
    processes = coordinator.get("processes")
    completed = coordinator.get("completed")
    metadata = coordinator.get("metadata")
    if (
        manifest.get("phase") != "calibration_extension"
        or manifest.get("classification") != "CALIBRATION_EXTENSION_COMPLETE"
        or not isinstance(runtime, dict)
        or runtime.get("default_backend") != "cpu"
        or runtime.get("x64_enabled") is not True
        or runtime.get("peak_device_memory_bytes") != 0
        or coordinator.get("classification") != "RUN_COMPLETE"
        or not isinstance(completed, list)
        or command_id not in completed
        or coordinator.get("failed") != []
        or not isinstance(processes, dict)
        or not isinstance(processes.get(command_id), dict)
        or processes[command_id].get("return_code") != 0
        or not isinstance(metadata, dict)
        or metadata.get("stage") != "stage6"
        or metadata.get("execution_policy") != "LOCAL_COMPUTE_DEVIATION"
        or metadata.get("remote_execution") is not False
    ):
        raise ValueError("local extension execution evidence is not terminal and valid")
    evidence = {
        "schema_version": 1,
        "stage": "stage6",
        "phase": "calibration_extension_local_execution_evidence",
        "classification": "PASS",
        "execution_policy": "LOCAL_COMPUTE_DEVIATION",
        "remote_execution": False,
        "runtime_backend": "cpu",
        "parent_manifest": str(manifest_path),
        "parent_manifest_sha256": sha256_file(manifest_path),
        "coordinator_state": str(coordinator_path),
        "coordinator_state_sha256": sha256_file(coordinator_path),
        "command_id": str(command_id),
    }
    atomic_write_json(destination, evidence)
    return evidence


def _load_local_extension_evidence(
    evidence_path: str | Path | None,
    *,
    parent_manifest: Path,
) -> dict[str, object] | None:
    if evidence_path is None:
        return None
    path = Path(evidence_path).resolve()
    evidence = _load_json_object(path, "local extension execution evidence")
    expected = {
        "schema_version",
        "stage",
        "phase",
        "classification",
        "execution_policy",
        "remote_execution",
        "runtime_backend",
        "parent_manifest",
        "parent_manifest_sha256",
        "coordinator_state",
        "coordinator_state_sha256",
        "command_id",
    }
    if (
        set(evidence) != expected
        or evidence.get("schema_version") != 1
        or evidence.get("stage") != "stage6"
        or evidence.get("phase")
        != "calibration_extension_local_execution_evidence"
        or evidence.get("classification") != "PASS"
        or evidence.get("execution_policy") != "LOCAL_COMPUTE_DEVIATION"
        or evidence.get("remote_execution") is not False
        or evidence.get("runtime_backend") != "cpu"
        or evidence.get("parent_manifest_sha256") != sha256_file(parent_manifest)
    ):
        raise ValueError("local extension execution evidence is invalid")
    coordinator = Path(str(evidence.get("coordinator_state"))).resolve()
    if (
        not coordinator.is_file()
        or evidence.get("coordinator_state_sha256") != sha256_file(coordinator)
    ):
        raise ValueError("local extension coordinator hash mismatch")
    return evidence


def _validate_extension_terminal_evidence(
    manifest_path: Path,
    payload: Mapping[str, object],
    spec: CalibrationExtensionSpec,
    package_root: Path,
    *,
    local_execution_evidence: Mapping[str, object] | None = None,
) -> None:
    _verify_source_artifacts(manifest_path.parent, payload.get("artifact_hashes"))
    parent_summary = _extension_parent_checkpoint_summary(package_root, spec)
    child_summary, metadata_sha256, state_sha256 = (
        _validated_extension_checkpoint_directory(
            manifest_path.parent / "checkpoint",
            spec,
            name="terminal extension",
        )
    )
    target_summary, target_metadata_sha256, target_state_sha256 = (
        _validated_extension_checkpoint_directory(
            manifest_path.parent
            / "checkpoints"
            / f"sweep-{spec.target_completed_sweeps:09d}",
            spec,
            name="target-sweep extension",
        )
    )
    if (
        target_metadata_sha256 != metadata_sha256
        or target_state_sha256 != state_sha256
        or target_summary["sweep_count"] != child_summary["sweep_count"]
    ):
        raise ValueError("terminal and target-sweep extension checkpoints differ")

    parallel = payload.get("parallel_tempering")
    if not isinstance(parallel, dict):
        raise ValueError("parallel-tempering terminal evidence is missing")
    attempts, accepts, acceptance = _edge_arrays(
        parallel,
        expected_edges=len(spec.temperatures) - 1,
        name="cumulative extension terminal evidence",
    )
    window = parallel.get("extension_window")
    if not isinstance(window, dict):
        raise ValueError("extension-window terminal evidence is missing")
    window_attempts, window_accepts, window_acceptance = _edge_arrays(
        window,
        expected_edges=len(spec.temperatures) - 1,
        name="extension-window terminal evidence",
    )
    child_attempts = np.asarray(child_summary["swap_attempts"])
    child_accepts = np.asarray(child_summary["swap_accepts"])
    parent_attempts = np.asarray(parent_summary["swap_attempts"])
    parent_accepts = np.asarray(parent_summary["swap_accepts"])
    expected_window_attempts = child_attempts - parent_attempts
    expected_window_accepts = child_accepts - parent_accepts
    cumulative_band = bool(
        np.all(acceptance >= spec.swap_target_minimum)
        and np.all(acceptance <= spec.swap_target_maximum)
    )
    window_band = bool(
        np.all(window_acceptance >= spec.swap_target_minimum)
        and np.all(window_acceptance <= spec.swap_target_maximum)
    )
    bottleneck = bool(np.min(acceptance) >= spec.swap_bottleneck)
    decision = (
        "PASS" if bottleneck and cumulative_band and window_band else "RECALIBRATE"
    )
    if (
        payload.get("start_completed_sweeps") != spec.parent.completed_sweeps
        or payload.get("completed_sweeps") != spec.target_completed_sweeps
        or window.get("start_completed_sweeps") != spec.parent.completed_sweeps
        or window.get("completed_sweeps") != spec.target_completed_sweeps
        or not np.array_equal(attempts, child_attempts)
        or not np.array_equal(accepts, child_accepts)
        or np.any(expected_window_attempts <= 0)
        or np.any(expected_window_accepts < 0)
        or not np.array_equal(window_attempts, expected_window_attempts)
        or not np.array_equal(window_accepts, expected_window_accepts)
        or parallel.get("all_edges_attempted") is not bool(np.all(attempts > 0))
        or window.get("all_edges_attempted")
        is not bool(np.all(window_attempts > 0))
        or parallel.get("bottleneck_passed") is not bottleneck
        or parallel.get("target_band_passed") is not cumulative_band
        or window.get("target_band_passed") is not window_band
        or parallel.get("ladder_decision") != decision
        or type(parallel.get("round_trips_min")) is not int
        or type(parallel.get("round_trips_max")) is not int
        or parallel.get("round_trips_min") != child_summary["round_trips_min"]
        or parallel.get("round_trips_max") != child_summary["round_trips_max"]
    ):
        raise ValueError("extension terminal counters or decisions differ from checkpoint state")
    if payload.get("travel") != {
        "parent": parent_summary["travel"],
        "child": child_summary["travel"],
    }:
        raise ValueError("extension terminal travel differs from checkpoint state")
    _validate_extension_runtime_record(
        payload.get("runtime"),
        parent_summary,
        child_summary,
        local_execution_evidence=local_execution_evidence,
    )


def _checkpoint_parent(
    manifest_path: Path,
    payload: Mapping[str, object],
    *,
    manifest_kind: str,
    checkpoint_spec: CalibrationSpec | CalibrationExtensionSpec,
) -> CalibrationCheckpointParent:
    checkpoint = manifest_path.parent / "checkpoint"
    metadata_path = checkpoint / "metadata.json"
    state_path = checkpoint / "state.npz"
    metadata = _load_json_object(metadata_path, "parent checkpoint metadata")
    if set(metadata) != {
        "schema_version",
        "completed_sweeps",
        "spec_sha256",
        "state_sha256",
    } or type(metadata.get("schema_version")) is not int or metadata.get(
        "schema_version"
    ) != 1:
        raise ValueError("parent checkpoint metadata schema is invalid")
    state_sha256 = sha256_file(state_path)
    if metadata.get("state_sha256") != state_sha256:
        raise ValueError("parent checkpoint state hash mismatch")
    artifact_hashes = payload.get("artifact_hashes")
    if not isinstance(artifact_hashes, dict):
        raise ValueError("parent artifact hash inventory is missing")
    metadata_sha256 = sha256_file(metadata_path)
    if artifact_hashes.get("checkpoint/metadata.json") != metadata_sha256:
        raise ValueError("parent checkpoint metadata hash mismatch")
    if artifact_hashes.get("checkpoint/state.npz") != state_sha256:
        raise ValueError("parent checkpoint state hash mismatch")
    if metadata.get("spec_sha256") != checkpoint_spec.sha256:
        raise ValueError("parent checkpoint spec hash mismatch")
    completed = metadata.get("completed_sweeps")
    if type(completed) is not int or completed < 1 or payload.get("completed_sweeps") != completed:
        raise ValueError("parent completed-sweep count is inconsistent")
    _validate_pt_checkpoint_state_file(
        state_path,
        checkpoint_spec,
        completed_sweeps=completed,
        name="parent",
    )
    return CalibrationCheckpointParent(
        cell_id=payload.get("cell_id"),
        manifest_kind=manifest_kind,
        manifest_sha256=sha256_file(manifest_path),
        checkpoint_spec_sha256=checkpoint_spec.sha256,
        checkpoint_metadata_sha256=metadata_sha256,
        checkpoint_state_sha256=state_sha256,
        completed_sweeps=completed,
    )


def _load_extension_parent(
    parent_manifest: str | Path,
    parent_package_manifest: str | Path,
    local_execution_evidence: str | Path | None = None,
) -> tuple[dict[str, object], CalibrationCheckpointParent, dict[str, object]]:
    manifest_path = Path(parent_manifest).resolve()
    package_path = Path(parent_package_manifest).resolve()
    payload = _load_json_object(manifest_path, "parent calibration manifest")
    package = _load_json_object(package_path, "parent package manifest")
    local_evidence = _load_local_extension_evidence(
        local_execution_evidence,
        parent_manifest=manifest_path,
    )
    if package.get("classification") != "PLANNED" or any(
        package.get(name) is not False
        for name in ("scientific_evidence", "tc_evidence", "second_rg_enabled")
    ):
        raise ValueError("parent package manifest is invalid")
    run_spec_path = package_path.parent / "run_spec.json"
    run_spec = _load_json_object(run_spec_path, "parent run spec")
    artifacts = package.get("artifacts")
    if not isinstance(artifacts, dict) or artifacts.get("run_spec.json") != sha256_file(
        run_spec_path
    ):
        raise ValueError("parent package run-spec hash mismatch")
    if payload.get("schema_version") != 1 or payload.get("stage") != "stage6":
        raise ValueError("parent manifest schema is unsupported")
    if any(payload.get(name) is not False for name in ("tc_evidence", "second_rg_enabled")):
        raise ValueError("parent manifest improperly claims later-stage evidence")

    if (
        payload.get("classification") == CALIBRATION_COMPLETE
        and payload.get("scope") == "stage6-ladder-calibration-only"
        and payload.get("status") == "complete"
    ):
        if package.get("phase") != "adaptive_temperature_ladder_scan" or run_spec.get(
            "phase"
        ) != "adaptive_temperature_ladder_scan":
            raise ValueError("parent package is not an adaptive ladder scan")
        spec = _calibration_spec_from_payload(payload.get("spec"), "parent spec")
        if payload.get("spec_sha256") != spec.sha256 or payload.get("cell_id") != spec.cell_id:
            raise ValueError("parent calibration spec hash or cell ID is inconsistent")
        matches = [
            cell
            for cell in run_spec.get("cells", [])
            if isinstance(cell, dict) and cell.get("cell_id") == spec.cell_id
        ]
        if len(matches) != 1:
            raise ValueError("parent does not match one base candidate")
        params = matches[0].get("params")
        if not isinstance(params, dict) or any(
            params.get(name) != wanted
            for name, wanted in (
                ("length", spec.length),
                ("temperatures", list(spec.temperatures)),
                ("chain_pairs", spec.chain_pairs),
                ("j_seed", spec.j_seed),
                ("calibration_sweeps", spec.calibration_sweeps),
            )
        ):
            raise ValueError("parent physics differs from the base candidate")
        run_spec_sha256 = sha256_file(run_spec_path)
        if spec.source_hashes.get("run_spec.json") != run_spec_sha256:
            raise ValueError("parent spec is not bound to the base run spec")
        parent = _checkpoint_parent(
            manifest_path,
            payload,
            manifest_kind="calibration",
            checkpoint_spec=spec,
        )
        if parent.completed_sweeps != spec.calibration_sweeps:
            raise ValueError(
                "parent calibration did not complete its declared sweep budget"
            )
        base = {
            "base_cell_id": spec.cell_id,
            "base_run_id": run_spec.get("run_id"),
            "base_run_spec_sha256": run_spec_sha256,
            "base_package_manifest_sha256": sha256_file(package_path),
            "base_calibration_spec_sha256": spec.sha256,
            "length": spec.length,
            "temperatures": spec.temperatures,
            "chain_pairs": spec.chain_pairs,
            "j_seed": spec.j_seed,
            "swap_bottleneck": spec.swap_bottleneck,
            "swap_target_minimum": spec.swap_target_minimum,
            "swap_target_maximum": spec.swap_target_maximum,
        }
        return base, parent, payload

    if (
        payload.get("phase") == "calibration_extension"
        and payload.get("classification") == "CALIBRATION_EXTENSION_COMPLETE"
        and payload.get("scope") == "stage6-ladder-calibration-extension-only"
        and payload.get("status") == "complete"
    ):
        if payload.get("scientific_evidence") is not False:
            raise ValueError("parent extension must not claim scientific evidence")
        spec = CalibrationExtensionSpec.from_payload(payload.get("extension_spec"))
        expected_artifacts = {
            "run_spec.json",
            "parent/manifest.json",
            "parent/checkpoint/metadata.json",
            "parent/checkpoint/state.npz",
        }
        parent_local_descriptor = run_spec.get("local_execution_evidence")
        if parent_local_descriptor is not None:
            expected_artifacts.add("parent/local_execution_evidence.json")
        if (
            package.get("phase") != "calibration_extension"
            or run_spec.get("phase") != "calibration_extension"
            or package.get("cell_count") != 1
            or not isinstance(artifacts, dict)
            or set(artifacts) != expected_artifacts
        ):
            raise ValueError("parent extension package is invalid")
        for relative, digest in artifacts.items():
            if (
                not _valid_sha256(digest)
                or sha256_file(package_path.parent / relative) != digest
            ):
                raise ValueError("parent extension package artifact hash mismatch")
        expected_parent_artifacts = {
            "parent/manifest.json": spec.parent.manifest_sha256,
            "parent/checkpoint/metadata.json": (
                spec.parent.checkpoint_metadata_sha256
            ),
            "parent/checkpoint/state.npz": spec.parent.checkpoint_state_sha256,
        }
        if any(
            artifacts.get(relative) != digest
            for relative, digest in expected_parent_artifacts.items()
        ):
            raise ValueError(
                "parent extension package artifacts differ from declared lineage"
            )
        packaged_cell = _sole_extension_cell(run_spec, package, "parent extension")
        if packaged_cell.get("cell_id") != spec.cell_id:
            raise ValueError("parent extension run spec does not contain its terminal cell")
        try:
            packaged_spec = CalibrationExtensionSpec.from_payload(
                packaged_cell.get("extension_spec")
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("parent extension run spec is invalid") from error
        expected_lineage = {
            "base_cell_id": spec.base_cell_id,
            "base_run_id": spec.base_run_id,
            "base_run_spec_sha256": spec.base_run_spec_sha256,
            "base_package_manifest_sha256": spec.base_package_manifest_sha256,
            "base_calibration_spec_sha256": spec.base_calibration_spec_sha256,
            "parent_cell_id": spec.parent.cell_id,
            "parent_manifest_kind": spec.parent.manifest_kind,
            "parent_manifest_sha256": spec.parent.manifest_sha256,
            "parent_checkpoint_spec_sha256": spec.parent.checkpoint_spec_sha256,
            "parent_checkpoint_metadata_sha256": (
                spec.parent.checkpoint_metadata_sha256
            ),
            "parent_checkpoint_state_sha256": spec.parent.checkpoint_state_sha256,
        }
        if (
            payload.get("extension_spec_sha256") != spec.sha256
            or payload.get("cell_id") != spec.cell_id
            or payload.get("completed_sweeps") != spec.target_completed_sweeps
            or payload.get("lineage") != expected_lineage
            or packaged_cell.get("extension_spec_sha256") != spec.sha256
            or asdict(packaged_spec) != asdict(spec)
            or manifest_path.parent
            != (package_path.parent / "cells" / spec.cell_id).resolve()
        ):
            raise ValueError(
                "parent extension target, lineage, or package run spec is inconsistent"
            )
        _validate_extension_terminal_evidence(
            manifest_path,
            payload,
            spec,
            package_path.parent,
            local_execution_evidence=local_evidence,
        )
        parent = _checkpoint_parent(
            manifest_path,
            payload,
            manifest_kind="calibration_extension",
            checkpoint_spec=spec,
        )
        base = {
            name: getattr(spec, name)
            for name in (
                "base_cell_id",
                "base_run_id",
                "base_run_spec_sha256",
                "base_package_manifest_sha256",
                "base_calibration_spec_sha256",
                "length",
                "temperatures",
                "chain_pairs",
                "j_seed",
                "swap_bottleneck",
                "swap_target_minimum",
                "swap_target_maximum",
            )
        }
        return base, parent, payload
    raise ValueError("parent manifest is not a completed calibration or extension")


def build_ladder_extension_spec(
    parent_manifest: str | Path,
    parent_package_manifest: str | Path,
    *,
    target_completed_sweeps: int,
    run_id: str,
    local_execution_evidence: str | Path | None = None,
) -> dict[str, object]:
    """Build one parent-checkpoint-bound calibration extension cell."""

    safe_run_id = _safe_component(run_id, "run_id")
    base, parent, _ = _load_extension_parent(
        parent_manifest,
        parent_package_manifest,
        local_execution_evidence,
    )
    child_id = f"{base['base_cell_id']}-E{int(target_completed_sweeps):05d}"
    spec = CalibrationExtensionSpec(
        schema_version=1,
        kind="calibration_extension",
        cell_id=child_id,
        parent=parent,
        target_completed_sweeps=target_completed_sweeps,
        source_hashes=_extension_source_hashes(),
        **base,
    )
    run_dir = f"results/hard_goal/{safe_run_id}"
    result = {
        "schema_version": 1,
        "stage": "stage6",
        "phase": "calibration_extension",
        "classification": "PLANNED",
        "scientific_evidence": False,
        "tc_evidence": False,
        "second_rg_enabled": False,
        "run_id": safe_run_id,
        "run_dir": run_dir,
        "array": {"count": 1, "index_origin": 1},
        "cells": [
            {
                "array_index": 1,
                "cell_id": spec.cell_id,
                "extension_spec": asdict(spec),
                "extension_spec_sha256": spec.sha256,
                "output": f"{run_dir}/cells/{spec.cell_id}",
            }
        ],
    }
    if local_execution_evidence is not None:
        evidence_path = Path(local_execution_evidence).resolve()
        result["local_execution_evidence"] = {
            "path": "parent/local_execution_evidence.json",
            "sha256": sha256_file(evidence_path),
        }
    return result


def prepare_ladder_extension(
    parent_manifest: str | Path,
    parent_package_manifest: str | Path,
    *,
    target_completed_sweeps: int,
    run_id: str,
    output: str | Path,
    local_execution_evidence: str | Path | None = None,
) -> dict[str, object]:
    """Atomically publish one immutable calibration-extension launch package."""

    destination = Path(output).resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite extension package: {destination}")
    run_spec = build_ladder_extension_spec(
        parent_manifest,
        parent_package_manifest,
        target_completed_sweeps=target_completed_sweeps,
        run_id=run_id,
        local_execution_evidence=local_execution_evidence,
    )
    source_manifest = Path(parent_manifest).resolve()
    source_checkpoint = source_manifest.parent / "checkpoint"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.extension-", dir=destination.parent)
    )
    try:
        run_spec_path = staging / "run_spec.json"
        atomic_write_json(run_spec_path, run_spec)
        (staging / "parent").mkdir()
        shutil.copy2(source_manifest, staging / "parent" / "manifest.json")
        shutil.copytree(source_checkpoint, staging / "parent" / "checkpoint")
        artifact_names = [
            "run_spec.json",
            "parent/manifest.json",
            "parent/checkpoint/metadata.json",
            "parent/checkpoint/state.npz",
        ]
        if local_execution_evidence is not None:
            shutil.copy2(
                Path(local_execution_evidence).resolve(),
                staging / "parent" / "local_execution_evidence.json",
            )
            artifact_names.append("parent/local_execution_evidence.json")
        artifacts = {
            relative: sha256_file(staging / relative)
            for relative in artifact_names
        }
        spec = CalibrationExtensionSpec.from_payload(
            run_spec["cells"][0]["extension_spec"]
        )
        if (
            artifacts["parent/manifest.json"] != spec.parent.manifest_sha256
            or artifacts["parent/checkpoint/metadata.json"]
            != spec.parent.checkpoint_metadata_sha256
            or artifacts["parent/checkpoint/state.npz"]
            != spec.parent.checkpoint_state_sha256
        ):
            raise ValueError("copied parent artifact hash mismatch")
        package = {
            "schema_version": 1,
            "stage": "stage6",
            "phase": "calibration_extension",
            "classification": "PLANNED",
            "scientific_evidence": False,
            "tc_evidence": False,
            "second_rg_enabled": False,
            "cell_count": 1,
            "artifacts": artifacts,
        }
        manifest_path = staging / "manifest.json"
        atomic_write_json(manifest_path, package)
        verified_promote_directory(
            staging,
            destination,
            {**artifacts, "manifest.json": sha256_file(manifest_path)},
        )
        return package
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def load_ladder_extension_cell(
    run_spec: str | Path,
    selector: str | int,
    *,
    track_root: str | Path = TRACK_ROOT,
    repo_root: str | Path = REPO_ROOT,
    require_current_sources: bool = True,
) -> tuple[CalibrationExtensionSpec, Path, Path]:
    """Validate an immutable extension package and resolve its sole child."""

    path = Path(run_spec).resolve()
    payload = _load_json_object(path, "extension run spec")
    package_path = path.parent / "manifest.json"
    package = _load_json_object(package_path, "extension package manifest")
    expected_artifacts = {
        "run_spec.json",
        "parent/manifest.json",
        "parent/checkpoint/metadata.json",
        "parent/checkpoint/state.npz",
    }
    local_descriptor = payload.get("local_execution_evidence")
    if local_descriptor is not None:
        expected_artifacts.add("parent/local_execution_evidence.json")
    artifacts = package.get("artifacts")
    if (
        any(package.get(name) is not False for name in (
            "scientific_evidence",
            "tc_evidence",
            "second_rg_enabled",
        ))
        or type(package.get("schema_version")) is not int
        or package.get("schema_version") != 1
        or package.get("stage") != "stage6"
        or package.get("phase") != "calibration_extension"
        or package.get("classification") != "PLANNED"
        or package.get("cell_count") != 1
        or not isinstance(artifacts, dict)
        or set(artifacts) != expected_artifacts
    ):
        raise ValueError("extension package manifest is invalid")
    for relative, digest in artifacts.items():
        if not _valid_sha256(digest) or sha256_file(path.parent / relative) != digest:
            raise ValueError(f"extension package artifact hash mismatch: {relative}")
    if (
        type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
        or payload.get("stage") != "stage6"
        or payload.get("phase") != "calibration_extension"
        or payload.get("classification") != "PLANNED"
        or any(payload.get(name) is not False for name in (
            "scientific_evidence",
            "tc_evidence",
            "second_rg_enabled",
        ))
    ):
        raise ValueError("extension run spec is invalid")
    if local_descriptor is not None:
        evidence_path = path.parent / "parent" / "local_execution_evidence.json"
        if (
            not isinstance(local_descriptor, dict)
            or set(local_descriptor) != {"path", "sha256"}
            or local_descriptor.get("path")
            != "parent/local_execution_evidence.json"
            or local_descriptor.get("sha256") != sha256_file(evidence_path)
        ):
            raise ValueError("extension local execution evidence descriptor is invalid")
        bundled_parent = path.parent / "parent" / "manifest.json"
        _load_local_extension_evidence(
            evidence_path,
            parent_manifest=bundled_parent,
        )
    expected_cell = _sole_extension_cell(payload, package, "extension")
    cell = _resolve_cell(payload, selector)
    if cell is not expected_cell:
        raise ValueError("extension selector did not resolve the sole canonical cell")
    spec = CalibrationExtensionSpec.from_payload(cell.get("extension_spec"))
    if cell.get("cell_id") != spec.cell_id or cell.get("extension_spec_sha256") != spec.sha256:
        raise ValueError("extension spec is not canonical")
    if (
        set(spec.source_hashes) != set(_EXTENSION_SOURCE_NAMES)
        or any(not _valid_sha256(digest) for digest in spec.source_hashes.values())
    ):
        raise ValueError("extension source hashes are invalid")
    if require_current_sources and spec.source_hashes != _extension_source_hashes(
        Path(track_root).resolve()
    ):
        raise ValueError("extension source hashes do not match current execution sources")
    parent_manifest_path = path.parent / "parent" / "manifest.json"
    parent_checkpoint = path.parent / "parent" / "checkpoint"
    if sha256_file(parent_manifest_path) != spec.parent.manifest_sha256:
        raise ValueError("bundled parent manifest hash mismatch")
    parent_payload = _load_json_object(
        parent_manifest_path, "bundled parent manifest"
    )
    if spec.parent.manifest_kind == "calibration":
        if (
            parent_payload.get("classification") != CALIBRATION_COMPLETE
            or parent_payload.get("scope") != "stage6-ladder-calibration-only"
            or parent_payload.get("status") != "complete"
        ):
            raise ValueError("bundled parent is not a completed calibration")
        parent_spec = _calibration_spec_from_payload(
            parent_payload.get("spec"), "bundled parent spec"
        )
        base_matches = (
            parent_payload.get("cell_id") == parent_spec.cell_id
            and parent_payload.get("spec_sha256") == parent_spec.sha256
            and parent_payload.get("completed_sweeps")
            == spec.parent.completed_sweeps
            and spec.parent.completed_sweeps == parent_spec.calibration_sweeps
            and spec.parent.cell_id == parent_spec.cell_id
            and spec.base_cell_id == parent_spec.cell_id
            and spec.base_run_spec_sha256
            == parent_spec.source_hashes.get("run_spec.json")
            and spec.base_calibration_spec_sha256 == parent_spec.sha256
            and spec.length == parent_spec.length
            and spec.temperatures == parent_spec.temperatures
            and spec.chain_pairs == parent_spec.chain_pairs
            and spec.j_seed == parent_spec.j_seed
            and spec.swap_bottleneck == parent_spec.swap_bottleneck
            and spec.swap_target_minimum == parent_spec.swap_target_minimum
            and spec.swap_target_maximum == parent_spec.swap_target_maximum
        )
    else:
        if (
            parent_payload.get("phase") != "calibration_extension"
            or parent_payload.get("classification")
            != "CALIBRATION_EXTENSION_COMPLETE"
            or parent_payload.get("scope")
            != "stage6-ladder-calibration-extension-only"
            or parent_payload.get("status") != "complete"
            or parent_payload.get("scientific_evidence") is not False
            or parent_payload.get("tc_evidence") is not False
            or parent_payload.get("second_rg_enabled") is not False
        ):
            raise ValueError("bundled parent is not a completed calibration extension")
        parent_spec = CalibrationExtensionSpec.from_payload(
            parent_payload.get("extension_spec")
        )
        base_names = (
            "base_cell_id",
            "base_run_id",
            "base_run_spec_sha256",
            "base_package_manifest_sha256",
            "base_calibration_spec_sha256",
            "length",
            "temperatures",
            "chain_pairs",
            "j_seed",
            "swap_bottleneck",
            "swap_target_minimum",
            "swap_target_maximum",
        )
        base_matches = (
            parent_payload.get("cell_id") == parent_spec.cell_id
            and parent_payload.get("extension_spec_sha256") == parent_spec.sha256
            and parent_payload.get("completed_sweeps")
            == spec.parent.completed_sweeps
            and parent_payload.get("completed_sweeps")
            == parent_spec.target_completed_sweeps
            and spec.parent.cell_id == parent_spec.cell_id
            and all(getattr(spec, name) == getattr(parent_spec, name) for name in base_names)
        )
    parent_artifacts = parent_payload.get("artifact_hashes")
    if (
        not base_matches
        or not isinstance(parent_artifacts, dict)
        or parent_artifacts.get("checkpoint/metadata.json")
        != spec.parent.checkpoint_metadata_sha256
        or parent_artifacts.get("checkpoint/state.npz")
        != spec.parent.checkpoint_state_sha256
    ):
        raise ValueError("extension base physics or checkpoint differs from bundled parent")
    metadata = _load_json_object(
        parent_checkpoint / "metadata.json", "bundled parent checkpoint metadata"
    )
    if (
        sha256_file(parent_checkpoint / "metadata.json")
        != spec.parent.checkpoint_metadata_sha256
        or sha256_file(parent_checkpoint / "state.npz")
        != spec.parent.checkpoint_state_sha256
        or type(metadata.get("schema_version")) is not int
        or metadata.get("schema_version") != 1
        or metadata.get("spec_sha256") != spec.parent.checkpoint_spec_sha256
        or metadata.get("state_sha256") != spec.parent.checkpoint_state_sha256
        or metadata.get("completed_sweeps") != spec.parent.completed_sweeps
    ):
        raise ValueError("bundled parent checkpoint does not match extension spec")
    _validate_pt_checkpoint_state_file(
        parent_checkpoint / "state.npz",
        parent_spec,
        completed_sweeps=spec.parent.completed_sweeps,
        name="bundled parent",
    )
    raw_output = Path(str(cell.get("output")))
    output = raw_output.resolve() if raw_output.is_absolute() else (
        Path(repo_root).resolve() / raw_output
    ).resolve()
    allowed = (Path(repo_root).resolve() / "results" / "hard_goal").resolve()
    expected_parent = (allowed / str(payload.get("run_id")) / "cells").resolve()
    if not output.is_relative_to(allowed) or output.parent != expected_parent:
        raise ValueError("extension child output escapes its run namespace")
    return spec, output, parent_checkpoint


def run_ladder_extension_cell(
    run_spec: str | Path,
    selector: str | int,
    *,
    required_platform: str,
    checkpoint_every: int,
    resume: bool = False,
    track_root: str | Path = TRACK_ROOT,
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, object]:
    """Execute one extension using only its package-bundled parent checkpoint."""

    spec, output, parent_checkpoint = load_ladder_extension_cell(
        run_spec,
        selector,
        track_root=track_root,
        repo_root=repo_root,
    )
    return run_ladder_calibration_extension(
        spec,
        parent_checkpoint,
        output,
        required_platform=required_platform,
        checkpoint_every=checkpoint_every,
        resume=resume,
    )


def _extension_measured_record(
    path: Path,
    payload: Mapping[str, object],
    planned: CalibrationSpec,
    cell: Mapping[str, object],
    *,
    track_root: Path,
    repo_root: Path,
) -> dict[str, object]:
    failures: list[str] = []
    parent_summary: dict[str, object] | None = None
    local_evidence: dict[str, object] | None = None
    try:
        extension = CalibrationExtensionSpec.from_payload(
            payload.get("extension_spec")
        )
    except (AttributeError, TypeError, ValueError) as error:
        failures.append(f"extension spec is invalid: {error}")
        extension = None
    if extension is not None:
        try:
            package_root = path.resolve().parents[2]
            packaged, packaged_output, parent_checkpoint = load_ladder_extension_cell(
                package_root / "run_spec.json",
                extension.cell_id,
                track_root=track_root,
                repo_root=repo_root,
                require_current_sources=False,
            )
            if (
                asdict(packaged) != asdict(extension)
                or packaged.sha256 != extension.sha256
                or packaged_output != path.resolve().parent
            ):
                raise ValueError(
                    "terminal extension does not match its immutable package"
                )
            parent_payload = _load_json_object(
                package_root / "parent" / "manifest.json",
                "selector bundled parent manifest",
            )
            if packaged.parent.manifest_kind == "calibration":
                parent_spec: CalibrationSpec | CalibrationExtensionSpec = (
                    _calibration_spec_from_payload(
                        parent_payload.get("spec"),
                        "selector bundled parent spec",
                    )
                )
            else:
                parent_spec = CalibrationExtensionSpec.from_payload(
                    parent_payload.get("extension_spec")
                )
            parent_summary = _validate_pt_checkpoint_state_file(
                parent_checkpoint / "state.npz",
                parent_spec,
                completed_sweeps=packaged.parent.completed_sweeps,
                name="selector bundled parent",
            )
            local_evidence_path = package_root / "local_execution_evidence.json"
            local_evidence = (
                _load_local_extension_evidence(
                    local_evidence_path,
                    parent_manifest=path.resolve(),
                )
                if local_evidence_path.is_file()
                else None
            )
            _validate_extension_terminal_evidence(
                path,
                payload,
                packaged,
                package_root,
                local_execution_evidence=local_evidence,
            )
        except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
            failures.append(f"extension package binding is invalid: {error}")
    if (
        type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
        or payload.get("stage") != "stage6"
        or payload.get("phase") != "calibration_extension"
        or payload.get("classification") != "CALIBRATION_EXTENSION_COMPLETE"
        or payload.get("scope") != "stage6-ladder-calibration-extension-only"
        or payload.get("status") != "complete"
    ):
        failures.append("manifest is not a completed calibration extension")
    if (
        payload.get("scientific_evidence") is not False
        or payload.get("tc_evidence") is not False
        or payload.get("second_rg_enabled") is not False
    ):
        failures.append("extension improperly claims scientific or later-stage evidence")

    if extension is not None:
        if payload.get("extension_spec_sha256") != extension.sha256:
            failures.append("extension spec SHA-256 is inconsistent")
        if payload.get("cell_id") != extension.cell_id:
            failures.append("extension manifest cell ID is inconsistent")
        base_matches = (
            extension.base_cell_id == planned.cell_id
            and extension.base_run_spec_sha256
            == planned.source_hashes.get("run_spec.json")
            and extension.base_calibration_spec_sha256 == planned.sha256
            and extension.length == planned.length
            and extension.temperatures == planned.temperatures
            and extension.chain_pairs == planned.chain_pairs
            and extension.j_seed == planned.j_seed
            and extension.swap_bottleneck == planned.swap_bottleneck
            and extension.swap_target_minimum == planned.swap_target_minimum
            and extension.swap_target_maximum == planned.swap_target_maximum
        )
        if not base_matches:
            failures.append("extension has changed base ladder or physics")
        if payload.get("start_completed_sweeps") != extension.parent.completed_sweeps:
            failures.append("extension start does not match its parent")
        if payload.get("completed_sweeps") != extension.target_completed_sweeps:
            failures.append("extension did not complete its target sweep count")
        lineage = payload.get("lineage")
        expected_lineage = {
            "base_cell_id": extension.base_cell_id,
            "base_run_id": extension.base_run_id,
            "base_run_spec_sha256": extension.base_run_spec_sha256,
            "base_package_manifest_sha256": extension.base_package_manifest_sha256,
            "base_calibration_spec_sha256": extension.base_calibration_spec_sha256,
            "parent_cell_id": extension.parent.cell_id,
            "parent_manifest_kind": extension.parent.manifest_kind,
            "parent_manifest_sha256": extension.parent.manifest_sha256,
            "parent_checkpoint_spec_sha256": (
                extension.parent.checkpoint_spec_sha256
            ),
            "parent_checkpoint_metadata_sha256": (
                extension.parent.checkpoint_metadata_sha256
            ),
            "parent_checkpoint_state_sha256": (
                extension.parent.checkpoint_state_sha256
            ),
        }
        if lineage != expected_lineage:
            failures.append("extension lineage does not match its canonical spec")

    parallel = payload.get("parallel_tempering")
    attempts: np.ndarray | None = None
    accepts: np.ndarray | None = None
    acceptance: np.ndarray | None = None
    window_attempts: np.ndarray | None = None
    window_accepts: np.ndarray | None = None
    window_acceptance: np.ndarray | None = None
    round_trips_min: int | None = None
    round_trips_max: int | None = None
    if not isinstance(parallel, dict):
        failures.append("parallel-tempering record is missing")
    else:
        try:
            attempts, accepts, acceptance = _edge_arrays(
                parallel,
                expected_edges=len(planned.temperatures) - 1,
                name="cumulative extension calibration",
            )
        except ValueError as error:
            failures.append(str(error))
            attempts = accepts = None
        window = parallel.get("extension_window")
        if not isinstance(window, dict):
            failures.append("extension window is missing")
        else:
            try:
                window_attempts, window_accepts, window_acceptance = _edge_arrays(
                    window,
                    expected_edges=len(planned.temperatures) - 1,
                    name="extension window",
                )
            except ValueError as error:
                failures.append(str(error))
                window_attempts = window_accepts = window_acceptance = None
            if extension is not None and (
                window.get("start_completed_sweeps")
                != extension.parent.completed_sweeps
                or window.get("completed_sweeps")
                != extension.target_completed_sweeps
            ):
                failures.append("extension window sweep interval is inconsistent")
            if window.get("all_edges_attempted") is not True:
                failures.append("extension window did not attempt every edge")
            if window.get("target_band_passed") is not True:
                failures.append("extension window target-band decision is not passing")
            if window_acceptance is not None and (
                np.any(window_acceptance < MEASURED_ACCEPTANCE_MINIMUM)
                or np.any(window_acceptance > MEASURED_ACCEPTANCE_MAXIMUM)
            ):
                failures.append("one or more extension-window edges are outside [0.20, 0.50]")
            if (
                attempts is not None
                and window_attempts is not None
                and (
                    np.any(attempts <= window_attempts)
                    or np.any(accepts < window_accepts)
                )
            ):
                failures.append("extension reset counters instead of continuing the parent")
        if parallel.get("all_edges_attempted") is not True:
            failures.append("not every cumulative extension edge was attempted")
        if acceptance is not None and (
            np.any(acceptance < MEASURED_ACCEPTANCE_MINIMUM)
            or np.any(acceptance > MEASURED_ACCEPTANCE_MAXIMUM)
        ):
            failures.append("one or more cumulative extension edges are outside [0.20, 0.50]")
        if parallel.get("target_band_passed") is not True:
            failures.append("cumulative extension target-band decision is not passing")
        if parallel.get("ladder_decision") != "PASS":
            failures.append("extension ladder decision is not PASS")
        raw_round_trips = parallel.get("round_trips_min")
        raw_round_trips_max = parallel.get("round_trips_max")
        if (
            type(raw_round_trips) is not int
            or raw_round_trips < 0
            or type(raw_round_trips_max) is not int
            or raw_round_trips_max < raw_round_trips
        ):
            failures.append("round-trip extrema must be ordered nonnegative integers")
        else:
            round_trips_min = raw_round_trips
            round_trips_max = raw_round_trips_max
            if round_trips_min < MEASURED_ROUND_TRIPS_MINIMUM:
                failures.append("extension has fewer than 1 complete round trip")

    artifact_hashes = payload.get("artifact_hashes")
    if not isinstance(artifact_hashes, dict):
        failures.append("measured artifact hash inventory is missing")
    else:
        normalized = {str(name): str(digest) for name, digest in artifact_hashes.items()}
        inventory = _artifact_inventory(path.parent, exclude={"manifest.json"})
        if set(normalized) != inventory:
            failures.append("measured artifact inventory is incomplete")
        else:
            for relative, digest in sorted(normalized.items()):
                if not _valid_sha256(digest) or sha256_file(path.parent / relative) != digest:
                    failures.append(f"measured artifact hash mismatch: {relative}")
    child_summary: dict[str, object] | None = None
    try:
        if extension is None:
            raise ValueError("canonical extension spec is unavailable")
        child_summary, metadata_sha256, state_sha256 = (
            _validated_extension_checkpoint_directory(
                path.parent / "checkpoint",
                extension,
                name="terminal extension",
            )
        )
        target_summary, target_metadata_sha256, target_state_sha256 = (
            _validated_extension_checkpoint_directory(
                path.parent
                / "checkpoints"
                / f"sweep-{extension.target_completed_sweeps:09d}",
                extension,
                name="target-sweep extension",
            )
        )
        if (
            target_metadata_sha256 != metadata_sha256
            or target_state_sha256 != state_sha256
            or target_summary["sweep_count"] != child_summary["sweep_count"]
        ):
            raise ValueError(
                "terminal and target-sweep extension checkpoints differ"
            )
    except (FileNotFoundError, ValueError) as error:
        failures.append(f"terminal extension checkpoint state is invalid: {error}")

    if child_summary is not None and parent_summary is not None:
        child_attempts = np.asarray(child_summary["swap_attempts"])
        child_accepts = np.asarray(child_summary["swap_accepts"])
        parent_attempts = np.asarray(parent_summary["swap_attempts"])
        parent_accepts = np.asarray(parent_summary["swap_accepts"])
        expected_window_attempts = child_attempts - parent_attempts
        expected_window_accepts = child_accepts - parent_accepts
        if (
            attempts is None
            or accepts is None
            or not np.array_equal(attempts, child_attempts)
            or not np.array_equal(accepts, child_accepts)
        ):
            failures.append("cumulative extension counters differ from checkpoint state")
        if (
            window_attempts is None
            or window_accepts is None
            or np.any(expected_window_attempts < 0)
            or np.any(expected_window_accepts < 0)
            or not np.array_equal(window_attempts, expected_window_attempts)
            or not np.array_equal(window_accepts, expected_window_accepts)
        ):
            failures.append("extension-window counters differ from parent/child state")
        if (
            round_trips_min != child_summary["round_trips_min"]
            or round_trips_max != child_summary["round_trips_max"]
        ):
            failures.append("extension round-trip extrema differ from checkpoint state")
        expected_travel = {
            "parent": parent_summary["travel"],
            "child": child_summary["travel"],
        }
        if payload.get("travel") != expected_travel:
            failures.append("extension travel record differs from parent/child state")

        try:
            _validate_extension_runtime_record(
                payload.get("runtime"),
                parent_summary,
                child_summary,
                local_execution_evidence=local_evidence,
            )
        except ValueError as error:
            failures.append(str(error))

    params = cell["params"]
    return {
        "cell_id": planned.cell_id,
        "target_acceptance": params["target_acceptance"],
        "temperature_count": len(planned.temperatures),
        "manifest": str(path.resolve()),
        "manifest_sha256": sha256_file(path),
        "status": "accepted" if not failures else "rejected",
        "failures": failures,
        "round_trips_min": round_trips_min,
        "edge_acceptance_min": (
            float(np.min(acceptance)) if acceptance is not None else None
        ),
        "edge_acceptance_max": (
            float(np.max(acceptance)) if acceptance is not None else None
        ),
        "evidence_kind": "calibration_extension",
    }


def _measured_record(
    path: Path,
    payload: Mapping[str, object],
    planned: CalibrationSpec,
    cell: Mapping[str, object],
) -> dict[str, object]:
    failures: list[str] = []
    if payload.get("spec_sha256") != planned.sha256:
        failures.append("manifest does not match planned CalibrationSpec.sha256")
    if payload.get("schema_version") != 1 or payload.get("stage") != "stage6":
        failures.append("manifest schema is not Stage 6 version 1")
    if payload.get("classification") != CALIBRATION_COMPLETE:
        failures.append("manifest classification is not CALIBRATION_COMPLETE")
    if payload.get("status") != "complete" or payload.get("scope") != (
        "stage6-ladder-calibration-only"
    ):
        failures.append("manifest is not a completed ladder calibration")
    if payload.get("tc_evidence") is not False or payload.get("second_rg_enabled") is not False:
        failures.append("manifest improperly claims Tc or second-RG evidence")
    if payload.get("cell_id") != planned.cell_id:
        failures.append("manifest cell ID does not match the planned cell")
    try:
        embedded = _calibration_spec_from_payload(payload.get("spec"), "measured spec")
    except ValueError as error:
        failures.append(str(error))
        embedded = None
    if embedded is not None and (
        embedded.sha256 != planned.sha256 or asdict(embedded) != asdict(planned)
    ):
        failures.append("measured spec differs from the planned CalibrationSpec")
    if payload.get("completed_sweeps") != planned.calibration_sweeps:
        failures.append("manifest did not complete the planned calibration sweeps")

    parallel = payload.get("parallel_tempering")
    acceptance: np.ndarray | None = None
    round_trips_min: int | None = None
    if not isinstance(parallel, dict):
        failures.append("parallel-tempering record is missing")
    else:
        if parallel.get("all_edges_attempted") is not True:
            failures.append("not every measured edge was attempted")
        try:
            _, _, acceptance = _edge_arrays(
                parallel,
                expected_edges=len(planned.temperatures) - 1,
                name="measured calibration",
            )
        except ValueError as error:
            failures.append(str(error))
        if acceptance is not None and (
            np.any(acceptance < MEASURED_ACCEPTANCE_MINIMUM)
            or np.any(acceptance > MEASURED_ACCEPTANCE_MAXIMUM)
        ):
            failures.append("one or more measured edges are outside [0.20, 0.50]")
        if parallel.get("target_band_passed") is not True:
            failures.append("manifest target-band decision is not passing")
        if parallel.get("ladder_decision") != "PASS":
            failures.append("manifest ladder decision is not PASS")
        raw_round_trips = parallel.get("round_trips_min")
        if type(raw_round_trips) is not int or raw_round_trips < 0:
            failures.append("round_trips_min must be a nonnegative integer")
        else:
            round_trips_min = raw_round_trips
            if round_trips_min < MEASURED_ROUND_TRIPS_MINIMUM:
                failures.append(
                    "measured calibration has fewer than "
                    f"{MEASURED_ROUND_TRIPS_MINIMUM} complete round trip"
                )

    artifact_hashes = payload.get("artifact_hashes")
    if not isinstance(artifact_hashes, dict):
        failures.append("measured artifact hash inventory is missing")
    else:
        normalized = {str(name): str(digest) for name, digest in artifact_hashes.items()}
        inventory = _artifact_inventory(path.parent, exclude={"manifest.json"})
        if set(normalized) != inventory:
            failures.append("measured artifact inventory is incomplete")
        else:
            for relative, digest in sorted(normalized.items()):
                if not _valid_sha256(digest) or sha256_file(path.parent / relative) != digest:
                    failures.append(f"measured artifact hash mismatch: {relative}")

    params = cell["params"]
    return {
        "cell_id": planned.cell_id,
        "target_acceptance": params["target_acceptance"],
        "temperature_count": len(planned.temperatures),
        "manifest": str(path.resolve()),
        "manifest_sha256": sha256_file(path),
        "status": "accepted" if not failures else "rejected",
        "failures": failures,
        "round_trips_min": round_trips_min,
        "edge_acceptance_min": (
            float(np.min(acceptance)) if acceptance is not None else None
        ),
        "edge_acceptance_max": (
            float(np.max(acceptance)) if acceptance is not None else None
        ),
    }


def select_ladder_candidate(
    run_spec: str | Path,
    measured_manifest_paths: Sequence[str | Path],
    *,
    output: str | Path | None = None,
    track_root: str | Path = TRACK_ROOT,
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, object]:
    """Select only from measured in-band calibrations, preserving every failure."""

    payload, run_spec_path, run_spec_sha256 = _load_verified_run_spec(
        run_spec,
        track_root=track_root,
        require_current_sources=False,
    )
    planned_cells = {str(cell["cell_id"]): cell for cell in payload["cells"]}
    supplied: dict[str, list[tuple[Path, dict[str, object]]]] = {}
    extras: list[dict[str, object]] = []
    for raw_path in measured_manifest_paths:
        path = Path(raw_path)
        if path.is_dir():
            path = path / "manifest.json"
        try:
            manifest = _load_json_object(path, "measured calibration manifest")
        except (FileNotFoundError, ValueError) as error:
            extras.append(
                {
                    "cell_id": None,
                    "target_acceptance": None,
                    "temperature_count": None,
                    "manifest": str(path.resolve()),
                    "manifest_sha256": sha256_file(path) if path.is_file() else None,
                    "status": "rejected",
                    "failures": [str(error)],
                    "round_trips_min": None,
                    "edge_acceptance_min": None,
                    "edge_acceptance_max": None,
                }
            )
            continue
        extensionish = (
            manifest.get("phase") == "calibration_extension"
            or manifest.get("classification") == "CALIBRATION_EXTENSION_COMPLETE"
            or manifest.get("scope") == "stage6-ladder-calibration-extension-only"
        )
        if extensionish:
            if not (
                manifest.get("phase") == "calibration_extension"
                and manifest.get("classification")
                == "CALIBRATION_EXTENSION_COMPLETE"
                and manifest.get("scope")
                == "stage6-ladder-calibration-extension-only"
            ):
                extras.append(
                    {
                        "cell_id": None,
                        "target_acceptance": None,
                        "temperature_count": None,
                        "manifest": str(path.resolve()),
                        "manifest_sha256": sha256_file(path),
                        "status": "rejected",
                        "failures": ["malformed calibration extension discriminator"],
                        "round_trips_min": None,
                        "edge_acceptance_min": None,
                        "edge_acceptance_max": None,
                    }
                )
                continue
            try:
                extension = CalibrationExtensionSpec.from_payload(
                    manifest.get("extension_spec")
                )
            except (AttributeError, TypeError, ValueError) as error:
                extras.append(
                    {
                        "cell_id": None,
                        "target_acceptance": None,
                        "temperature_count": None,
                        "manifest": str(path.resolve()),
                        "manifest_sha256": sha256_file(path),
                        "status": "rejected",
                        "failures": [f"extension spec is invalid: {error}"],
                        "round_trips_min": None,
                        "edge_acceptance_min": None,
                        "edge_acceptance_max": None,
                    }
                )
                continue
            cell_id = extension.base_cell_id
        else:
            cell_id = manifest.get("cell_id")
        if not isinstance(cell_id, str) or cell_id not in planned_cells:
            extras.append(
                {
                    "cell_id": cell_id if isinstance(cell_id, str) else None,
                    "target_acceptance": None,
                    "temperature_count": None,
                    "manifest": str(path.resolve()),
                    "manifest_sha256": sha256_file(path),
                    "status": "rejected",
                    "failures": ["manifest does not belong to a planned scan cell"],
                    "round_trips_min": None,
                    "edge_acceptance_min": None,
                    "edge_acceptance_max": None,
                }
            )
            continue
        supplied.setdefault(cell_id, []).append((path, manifest))

    candidates: list[dict[str, object]] = []
    for cell in payload["cells"]:
        cell_id = str(cell["cell_id"])
        matches = supplied.get(cell_id, [])
        if not matches:
            candidates.append(
                {
                    "cell_id": cell_id,
                    "target_acceptance": cell["params"]["target_acceptance"],
                    "temperature_count": len(cell["params"]["temperatures"]),
                    "manifest": None,
                    "manifest_sha256": None,
                    "status": "missing",
                    "failures": ["measured calibration manifest is missing"],
                    "round_trips_min": None,
                    "edge_acceptance_min": None,
                    "edge_acceptance_max": None,
                }
            )
            continue
        if len(matches) != 1:
            candidates.append(
                {
                    "cell_id": cell_id,
                    "target_acceptance": cell["params"]["target_acceptance"],
                    "temperature_count": len(cell["params"]["temperatures"]),
                    "manifest": None,
                    "manifest_sha256": None,
                    "status": "rejected",
                    "failures": ["multiple measured manifests claim the same scan cell"],
                    "round_trips_min": None,
                    "edge_acceptance_min": None,
                    "edge_acceptance_max": None,
                }
            )
            for duplicate_path, _ in matches:
                extras.append(
                    {
                        "cell_id": cell_id,
                        "target_acceptance": cell["params"]["target_acceptance"],
                        "temperature_count": len(cell["params"]["temperatures"]),
                        "manifest": str(duplicate_path.resolve()),
                        "manifest_sha256": sha256_file(duplicate_path),
                        "status": "rejected",
                        "failures": ["duplicate measured manifest"],
                        "round_trips_min": None,
                        "edge_acceptance_min": None,
                        "edge_acceptance_max": None,
                    }
                )
            continue
        path, measured = matches[0]
        planned = _planned_calibration_spec(payload, run_spec_sha256, cell)
        if measured.get("phase") == "calibration_extension":
            candidates.append(
                _extension_measured_record(
                    path,
                    measured,
                    planned,
                    cell,
                    track_root=Path(track_root).resolve(),
                    repo_root=Path(repo_root).resolve(),
                )
            )
        else:
            candidates.append(_measured_record(path, measured, planned, cell))
    candidates.extend(sorted(extras, key=lambda record: str(record["manifest"])))

    accepted = [record for record in candidates if record["status"] == "accepted"]
    extension_present = any(
        record.get("evidence_kind") == "calibration_extension"
        for record in candidates
    )
    paired_complete = all(
        any(
            record.get("cell_id") == cell_id
            and record.get("manifest") is not None
            for record in candidates
        )
        for cell_id in planned_cells
    )
    if extension_present and not paired_complete:
        accepted = []
    accepted.sort(
        key=lambda record: (
            -int(record["round_trips_min"]),
            int(record["temperature_count"]),
            str(record["cell_id"]),
        )
    )
    selected = accepted[0] if accepted else None
    selected_cell = planned_cells[str(selected["cell_id"])] if selected else None
    result = {
        "schema_version": 1,
        "stage": "stage6",
        "phase": "adaptive_temperature_ladder_selection",
        "decision": "SELECT" if selected else "RECALIBRATE",
        "scientific_evidence": False,
        "tc_evidence": False,
        "second_rg_enabled": False,
        "run_spec": str(run_spec_path),
        "run_spec_sha256": run_spec_sha256,
        "selected_cell_id": selected["cell_id"] if selected else None,
        "selected_target_acceptance": (
            selected["target_acceptance"] if selected else None
        ),
        "selected_temperature_count": (
            selected["temperature_count"] if selected else None
        ),
        "selected_round_trips_min": (
            selected["round_trips_min"] if selected else None
        ),
        "selected_temperatures": (
            list(selected_cell["params"]["temperatures"]) if selected_cell else None
        ),
        "candidates": candidates,
    }
    if output is not None:
        destination = Path(output)
        if destination.exists():
            raise FileExistsError(
                f"refusing to overwrite ladder-scan selection: {destination}"
            )
        atomic_write_json(destination, result)
    return result
