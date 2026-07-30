"""Immutable selected-ladder planning for local Stage 6 science cells."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np

from vmcrg_ref.artifacts import (
    atomic_write_json,
    sha256_file,
    verified_promote_directory,
)

from .equilibration import EquilibrationThresholds
from .ladder_scan import select_ladder_candidate
from .pilot import CalibrationSpec
from .science_pilot import SciencePilotSpec
from .workflow import (
    Stage6Config,
    build_pilot_run_spec,
    load_stage6_config,
)


TRACK_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = TRACK_ROOT.parents[2]
LOCAL_EXECUTION_POLICY = "LOCAL_COMPUTE_DEVIATION"
SCIENCE_PHASE = "selected_ladder_science_pilot"
MEASUREMENT_CADENCE = 4
EQUILIBRATION_CADENCE = 32

_SCIENCE_SOURCE_NAMES = (
    "jobs/hard_goal_science_pilot.slurm",
    "scripts/hard_goal_science_pilot_cell.py",
    "scripts/hard_goal_stage6_local.py",
    "src/spinglass3d/science_pilot.py",
    "src/spinglass3d/stage6.py",
    "src/spinglass3d/stage6_aggregate.py",
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


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and not any(
        character not in "0123456789abcdef" for character in value
    )


def _load_json(path: Path, name: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not readable JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must contain an object")
    return payload


def _under_hard_goal(path: Path, root: Path, name: str) -> Path:
    resolved = path.resolve()
    allowed = (root / "results" / "hard_goal").resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError(f"{name} must remain under results/hard_goal")
    return resolved


def _resolve_recorded_path(value: object, root: Path, name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} path is missing")
    raw = Path(value)
    return _under_hard_goal(raw if raw.is_absolute() else root / raw, root, name)


def _display_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


@dataclass(frozen=True)
class SelectedLadder:
    """One measured, hash-bound temperature ladder selected for a size."""

    length: int
    temperatures: tuple[float, ...]
    selection_path: Path
    selection_sha256: str
    selected_manifest_path: Path
    selected_manifest_sha256: str
    selected_cell_id: str
    target_acceptance: float
    round_trips_min: int

    def __post_init__(self) -> None:
        if isinstance(self.length, bool) or not isinstance(
            self.length, (int, np.integer)
        ) or int(self.length) < 3:
            raise ValueError("selected ladder length is invalid")
        temperatures = np.asarray(self.temperatures, dtype=np.float64)
        if (
            temperatures.ndim != 1
            or temperatures.size < 2
            or not np.all(np.isfinite(temperatures))
            or np.any(temperatures <= 0.0)
            or np.any(np.diff(1.0 / temperatures) <= 0.0)
        ):
            raise ValueError("selected ladder temperatures are invalid")
        if not _valid_sha256(self.selection_sha256) or not _valid_sha256(
            self.selected_manifest_sha256
        ):
            raise ValueError("selected ladder hashes are invalid")
        if (
            not self.selected_cell_id
            or self.round_trips_min < 1
            or not 0.0 < float(self.target_acceptance) < 1.0
        ):
            raise ValueError("selected ladder evidence is incomplete")
        object.__setattr__(
            self,
            "temperatures",
            tuple(float(value) for value in temperatures),
        )
        object.__setattr__(self, "selection_path", self.selection_path.resolve())
        object.__setattr__(
            self,
            "selected_manifest_path",
            self.selected_manifest_path.resolve(),
        )


def load_selected_ladder(
    selection: str | Path,
    *,
    expected_length: int,
    track_root: str | Path = TRACK_ROOT,
    repo_root: str | Path = REPO_ROOT,
) -> SelectedLadder:
    """Recompute a measured ladder decision and reject every unresolved choice."""

    track = Path(track_root).resolve()
    repo = Path(repo_root).resolve()
    raw_selection = Path(selection)
    path = _under_hard_goal(
        raw_selection if raw_selection.is_absolute() else track / raw_selection,
        track,
        "ladder selection",
    )
    if path.is_symlink() or not path.is_file():
        raise ValueError("ladder selection must be one regular file")
    payload = _load_json(path, "ladder selection")
    if (
        payload.get("schema_version") != 1
        or payload.get("stage") != "stage6"
        or payload.get("phase") != "adaptive_temperature_ladder_selection"
        or payload.get("decision") != "SELECT"
        or payload.get("scientific_evidence") is not False
        or payload.get("tc_evidence") is not False
        or payload.get("second_rg_enabled") is not False
    ):
        raise ValueError("ladder selection is not a measured SELECT decision")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("ladder selection candidates are missing")
    manifest_paths = [
        _resolve_recorded_path(record.get("manifest"), track, "candidate manifest")
        for record in candidates
        if isinstance(record, dict) and record.get("manifest") is not None
    ]
    run_spec = _resolve_recorded_path(
        payload.get("run_spec"),
        track,
        "ladder run spec",
    )
    recomputed = select_ladder_candidate(
        run_spec,
        manifest_paths,
        track_root=track,
        repo_root=repo,
    )
    if recomputed != payload:
        raise ValueError("ladder selection does not match recomputed evidence")

    selected_cell_id = payload.get("selected_cell_id")
    selected = [
        record
        for record in candidates
        if isinstance(record, dict)
        and record.get("cell_id") == selected_cell_id
        and record.get("status") == "accepted"
    ]
    if len(selected) != 1:
        raise ValueError("selected ladder candidate is missing or nonunique")
    record = selected[0]
    manifest_path = _resolve_recorded_path(
        record.get("manifest"),
        track,
        "selected ladder manifest",
    )
    manifest_sha256 = record.get("manifest_sha256")
    if not _valid_sha256(manifest_sha256) or sha256_file(
        manifest_path
    ) != manifest_sha256:
        raise ValueError("selected ladder manifest hash mismatch")
    run_payload = _load_json(run_spec, "ladder run spec")
    matching_cells = [
        cell
        for cell in run_payload.get("cells", [])
        if isinstance(cell, dict) and cell.get("cell_id") == selected_cell_id
    ]
    if len(matching_cells) != 1 or not isinstance(
        matching_cells[0].get("params"), dict
    ):
        raise ValueError("selected ladder is absent from its run spec")
    params = matching_cells[0]["params"]
    if int(params.get("length", -1)) != int(expected_length):
        raise ValueError("selected ladder length does not match its size")
    if payload.get("selected_temperatures") != params.get("temperatures"):
        raise ValueError("selected temperature array differs from the run spec")
    return SelectedLadder(
        length=int(expected_length),
        temperatures=tuple(float(value) for value in params["temperatures"]),
        selection_path=path,
        selection_sha256=sha256_file(path),
        selected_manifest_path=manifest_path,
        selected_manifest_sha256=str(manifest_sha256),
        selected_cell_id=str(selected_cell_id),
        target_acceptance=float(payload["selected_target_acceptance"]),
        round_trips_min=int(payload["selected_round_trips_min"]),
    )


def _normalized_ladders(
    config: Stage6Config,
    ladders: Mapping[int, SelectedLadder],
) -> dict[int, SelectedLadder]:
    if not isinstance(ladders, Mapping) or set(ladders) != set(config.lengths):
        raise ValueError("one selected ladder is required for every Stage 6 length")
    normalized = {int(length): ladder for length, ladder in ladders.items()}
    for length, ladder in normalized.items():
        if not isinstance(ladder, SelectedLadder) or ladder.length != length:
            raise ValueError("selected ladder mapping has a mismatched length")
    return normalized


def build_selected_science_run_spec(
    config: Stage6Config,
    ladders: Mapping[int, SelectedLadder],
    run_id: str,
) -> dict[str, object]:
    """Build the complete 120-cell science matrix from measured ladders."""

    if not isinstance(config, Stage6Config):
        raise TypeError("config must be Stage6Config")
    safe_run_id = _safe_component(run_id, "run_id")
    selected = _normalized_ladders(config, ladders)
    base = build_pilot_run_spec(config, safe_run_id)
    source_hashes = dict(base["provenance"]["source_sha256"])
    for name in _SCIENCE_SOURCE_NAMES:
        path = TRACK_ROOT / name
        if not path.is_file():
            raise FileNotFoundError(f"Stage 6 science source is missing: {name}")
        source_hashes[name] = sha256_file(path)

    cells: list[dict[str, object]] = []
    for array_index, cell in enumerate(base["cells"], start=1):
        copied = json.loads(json.dumps(cell))
        params = copied["params"]
        length = int(params["length"])
        params["phase"] = SCIENCE_PHASE
        params["temperatures"] = list(selected[length].temperatures)
        params["output"] = (
            f"results/hard_goal/{safe_run_id}/science-cells/{copied['cell_id']}"
        )
        copied["array_index"] = array_index
        cells.append(copied)

    ladder_provenance = {
        str(length): {
            "selection_path": _display_path(ladder.selection_path, TRACK_ROOT),
            "selection_sha256": ladder.selection_sha256,
            "selected_manifest_path": _display_path(
                ladder.selected_manifest_path,
                TRACK_ROOT,
            ),
            "selected_manifest_sha256": ladder.selected_manifest_sha256,
            "selected_cell_id": ladder.selected_cell_id,
            "target_acceptance": ladder.target_acceptance,
            "round_trips_min": ladder.round_trips_min,
            "temperatures": list(ladder.temperatures),
        }
        for length, ladder in sorted(selected.items())
    }
    settings = json.loads(json.dumps(base["settings"]))
    settings["sampling"]["equilibration_cadence"] = EQUILIBRATION_CADENCE
    settings["sampling"]["measurement_cadence"] = MEASUREMENT_CADENCE
    settings["execution"] = {
        "backend": "jax_cpu",
        "execution_policy": LOCAL_EXECUTION_POLICY,
        "remote_execution": False,
    }
    settings["ladders_by_length"] = ladder_provenance
    provenance = json.loads(json.dumps(base["provenance"]))
    provenance["source_sha256"] = dict(sorted(source_hashes.items()))
    provenance["ladder_selection_sha256"] = {
        str(length): ladder.selection_sha256
        for length, ladder in sorted(selected.items())
    }
    provenance["claims"] = [
        "selected measured ladder per Stage 6 length",
        "complete preregistered 120-cell disorder matrix",
        "local CPU execution deviation only",
        "one RG level; no Tc evidence",
    ]
    return {
        "schema_version": 1,
        "stage": "stage6",
        "phase": SCIENCE_PHASE,
        "classification": "PLANNED",
        "scientific_evidence": False,
        "tc_evidence": False,
        "second_rg_enabled": False,
        "run_id": safe_run_id,
        "run_dir": f"results/hard_goal/{safe_run_id}",
        "axes": base["axes"],
        "array": {"count": len(cells), "index_origin": 1},
        "settings": settings,
        "provenance": provenance,
        "cells": cells,
    }


def prepare_selected_science_run(
    config_path: str | Path,
    selections: Mapping[int, str | Path],
    output: str | Path,
    *,
    track_root: str | Path = TRACK_ROOT,
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, object]:
    """Publish an immutable local science package without starting compute."""

    destination = Path(output).resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite Stage 6 science package: {destination}")
    config = load_stage6_config(config_path)
    if set(selections) != set(config.lengths):
        raise ValueError("science package requires four length-specific selections")
    ladders = {
        int(length): load_selected_ladder(
            path,
            expected_length=int(length),
            track_root=track_root,
            repo_root=repo_root,
        )
        for length, path in selections.items()
    }
    run_spec = build_selected_science_run_spec(config, ladders, destination.name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.science-", dir=destination.parent)
    )
    try:
        run_spec_path = staging / "run_spec.json"
        atomic_write_json(run_spec_path, run_spec)
        artifacts = {"run_spec.json": sha256_file(run_spec_path)}
        package = {
            "schema_version": 1,
            "stage": "stage6",
            "phase": SCIENCE_PHASE,
            "classification": "PLANNED",
            "scientific_evidence": False,
            "tc_evidence": False,
            "second_rg_enabled": False,
            "execution_policy": LOCAL_EXECUTION_POLICY,
            "remote_execution": False,
            "cell_count": len(run_spec["cells"]),
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


def _load_verified_science_run_spec(
    run_spec: str | Path,
    *,
    track_root: Path,
    repo_root: Path,
) -> tuple[dict[str, object], str]:
    path = Path(run_spec).resolve()
    payload = _load_json(path, "Stage 6 science run spec")
    package = _load_json(path.parent / "manifest.json", "Stage 6 science package")
    digest = sha256_file(path)
    if (
        package.get("schema_version") != 1
        or package.get("stage") != "stage6"
        or package.get("phase") != SCIENCE_PHASE
        or package.get("classification") != "PLANNED"
        or package.get("execution_policy") != LOCAL_EXECUTION_POLICY
        or package.get("remote_execution") is not False
        or package.get("artifacts") != {"run_spec.json": digest}
    ):
        raise ValueError("Stage 6 science package is invalid")
    provenance = payload.get("provenance")
    settings = payload.get("settings")
    if not isinstance(provenance, dict) or not isinstance(settings, dict):
        raise ValueError("Stage 6 science provenance is incomplete")
    config_path = track_root / "config/hard_goal/stage6_pilot_v1.toml"
    config = load_stage6_config(config_path)
    ladder_records = settings.get("ladders_by_length")
    if not isinstance(ladder_records, dict) or set(ladder_records) != {
        str(length) for length in config.lengths
    }:
        raise ValueError("Stage 6 science ladder inventory is incomplete")
    ladders = {
        length: load_selected_ladder(
            track_root / ladder_records[str(length)]["selection_path"],
            expected_length=length,
            track_root=track_root,
            repo_root=repo_root,
        )
        for length in config.lengths
    }
    expected = build_selected_science_run_spec(config, ladders, str(payload.get("run_id")))
    if payload != expected:
        raise ValueError("Stage 6 science run spec differs from measured inputs")
    if package.get("cell_count") != len(payload["cells"]):
        raise ValueError("Stage 6 science package cell count is inconsistent")
    return payload, digest


def load_selected_science_cell(
    run_spec: str | Path,
    selector: str | int,
    *,
    track_root: str | Path = TRACK_ROOT,
    repo_root: str | Path = REPO_ROOT,
) -> tuple[SciencePilotSpec, Path]:
    """Resolve one selected-ladder science cell after full hash reconstruction."""

    track = Path(track_root).resolve()
    repo = Path(repo_root).resolve()
    payload, run_spec_sha256 = _load_verified_science_run_spec(
        run_spec,
        track_root=track,
        repo_root=repo,
    )
    cells = payload["cells"]
    if isinstance(selector, int) or (isinstance(selector, str) and selector.isdigit()):
        index = int(selector)
        matches = [cell for cell in cells if cell.get("array_index") == index]
    else:
        matches = [cell for cell in cells if cell.get("cell_id") == selector]
    if len(matches) != 1:
        raise KeyError(f"unknown or nonunique Stage 6 science selector: {selector!r}")
    cell = matches[0]
    params = cell["params"]
    config = load_stage6_config(track / "config/hard_goal/stage6_pilot_v1.toml")
    source_hashes = {
        "run_spec.json": run_spec_sha256,
        **{str(name): str(value) for name, value in payload["provenance"]["source_sha256"].items()},
        **{
            f"ladder-selection-L{length}": str(value)
            for length, value in payload["provenance"]["ladder_selection_sha256"].items()
        },
    }
    thresholds = EquilibrationThresholds(
        swap_bottleneck=config.swap_bottleneck,
        swap_target_min=config.swap_target_minimum,
        swap_target_max=config.swap_target_maximum,
        min_round_trips=config.minimum_round_trips,
        max_rhat=config.maximum_rhat,
        min_ess=config.minimum_ess,
        bin_sigma=config.bin_sigma,
        max_thermal_error_fraction=config.maximum_thermal_error_fraction,
        min_chains=config.chain_pairs,
    )
    calibration = CalibrationSpec(
        cell_id=str(cell["cell_id"]),
        length=int(params["length"]),
        temperatures=tuple(float(value) for value in params["temperatures"]),
        chain_pairs=int(params["chain_pairs"]),
        calibration_sweeps=config.calibration_sweeps,
        j_seed=int(params["j_seed"]),
        swap_bottleneck=config.swap_bottleneck,
        swap_target_minimum=config.swap_target_minimum,
        swap_target_maximum=config.swap_target_maximum,
        source_hashes=source_hashes,
    )
    spec = SciencePilotSpec(
        cell_id=calibration.cell_id,
        length=calibration.length,
        temperatures=calibration.temperatures,
        chain_pairs=calibration.chain_pairs,
        calibration_sweeps=calibration.calibration_sweeps,
        equilibration_initial_sweeps=config.initial_equilibration_sweeps,
        equilibration_multiplier=config.equilibration_multiplier,
        equilibration_maximum_sweeps=config.maximum_equilibration_sweeps,
        measurement_sweeps=config.measurement_sweeps,
        equilibration_cadence=EQUILIBRATION_CADENCE,
        measurement_cadence=MEASUREMENT_CADENCE,
        j_seed=calibration.j_seed,
        thresholds=thresholds,
        templates=config.templates,
        rg_levels=1,
        source_hashes=source_hashes,
    )
    output = _under_hard_goal(
        repo / params["output"],
        repo,
        "Stage 6 science output",
    )
    expected_parent = (
        repo / "results" / "hard_goal" / payload["run_id"] / "science-cells"
    ).resolve()
    if output.parent != expected_parent:
        raise ValueError("Stage 6 science output differs from its run namespace")
    return spec, output


def load_stage6_science_cell(
    run_spec: str | Path,
    selector: str | int,
    *,
    track_root: str | Path = TRACK_ROOT,
    repo_root: str | Path = REPO_ROOT,
    measurement_cadence: int = MEASUREMENT_CADENCE,
) -> tuple[SciencePilotSpec, Path]:
    """Load a selected-ladder cell, retaining legacy launch compatibility."""

    payload = _load_json(Path(run_spec), "Stage 6 science run spec")
    if payload.get("phase") == SCIENCE_PHASE:
        if int(measurement_cadence) != MEASUREMENT_CADENCE:
            raise ValueError(
                f"selected Stage 6 measurement cadence is fixed at {MEASUREMENT_CADENCE}"
            )
        return load_selected_science_cell(
            run_spec,
            selector,
            track_root=track_root,
            repo_root=repo_root,
        )
    from .science_pilot import load_science_pilot_cell

    return load_science_pilot_cell(
        run_spec,
        str(selector),
        track_root=track_root,
        repo_root=repo_root,
        measurement_cadence=int(measurement_cadence),
    )


def load_terminal_science_manifest(
    spec: SciencePilotSpec,
    output: str | Path,
) -> dict[str, object]:
    """Rehash one promoted science cell and bind it to its selected spec."""

    destination = Path(output)
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("science cell output must be a real directory")
    manifest_path = destination / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("science cell manifest must be a regular file")
    manifest = _load_json(manifest_path, "science cell manifest")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("stage") != "stage6"
        or manifest.get("scope") != "scientific-stage6-pilot-cell"
        or manifest.get("classification") != "PILOT_PASS"
        or manifest.get("spec_sha256") != spec.sha256
        or manifest.get("cell_id") != spec.cell_id
        or manifest.get("tc_evidence") is not False
        or manifest.get("second_rg_enabled") is not False
        or manifest.get("representation_comparison") != "NOT_RUN"
        or manifest.get("production_freeze_allowed") is not False
    ):
        raise ValueError("science cell terminal manifest is invalid")
    declared = manifest.get("artifacts")
    if not isinstance(declared, dict) or any(
        not isinstance(name, str) or not _valid_sha256(digest)
        for name, digest in declared.items()
    ):
        raise ValueError("science cell artifact hashes are invalid")
    observed: dict[str, str] = {}
    for path in sorted(destination.rglob("*")):
        if path.is_symlink():
            raise ValueError("science cell artifacts must not contain symlinks")
        if path.is_file() and path.name != "manifest.json":
            relative = path.relative_to(destination).as_posix()
            observed[relative] = sha256_file(path)
    if declared != observed:
        raise ValueError("science cell artifact inventory or hash mismatch")
    required = {
        "equilibration_history.npz",
        "measurement_history.npz",
        "rg_once.npz",
        "status.json",
    }
    if not required <= set(observed) or not any(
        name.startswith("checkpoints/checkpoint-")
        for name in observed
    ):
        raise ValueError("science cell terminal artifact set is incomplete")
    equilibration = manifest.get("equilibration")
    if not isinstance(equilibration, dict) or equilibration.get("passed") is not True:
        raise ValueError("science cell terminal equilibration did not pass")
    reports = equilibration.get("reports")
    if not isinstance(reports, list) or len(reports) != len(spec.temperatures):
        raise ValueError("science cell temperature report inventory is incomplete")
    expected_ids = {
        f"{spec.cell_id}@T{index:03d}" for index in range(len(spec.temperatures))
    }
    if {
        report.get("j_id") for report in reports if isinstance(report, dict)
    } != expected_ids or any(
        not isinstance(report, dict) or report.get("passed") is not True
        for report in reports
    ):
        raise ValueError("science cell temperature reports are invalid")
    return manifest
