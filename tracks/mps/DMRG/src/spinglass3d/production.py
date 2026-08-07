"""Fail-closed Stage 7 production planning and immutable cell lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import ctypes
from dataclasses import dataclass
import copy
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import MappingProxyType

import numpy as np

from vmcrg_ref.artifacts import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)

from .workflow import validate_stage6_pilot_manifest


TRACK_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = TRACK_ROOT.parents[2]
PASS = "PASS"
MAXIMUM_ARRAY_SIZE = 200
EVIDENCE_ARMS = (
    "unbiased_fss",
    "vmcrg_training",
    "neural_validation",
)
STAGE7_SOURCE_PATHS = (
    "jobs/hard_goal_array.slurm",
    "scripts/hard_goal.py",
    "src/spinglass3d/backend.py",
    "src/spinglass3d/equilibration.py",
    "src/spinglass3d/jax_backend.py",
    "src/spinglass3d/model.py",
    "src/spinglass3d/production.py",
    "src/spinglass3d/workflow.py",
    "src/vmcrg_ref/artifacts.py",
)
TERMINAL_CLASSIFICATIONS = frozenset(
    {
        PASS,
        "SCIENTIFIC_NEGATIVE",
        "EQUILIBRATION_FAILURE",
        "REPRESENTATION_FAILURE",
        "RESOURCE_NO_GO",
        "CORRECTNESS_FAILURE",
    }
)


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


def _positive_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be a positive integer")
    result = int(value)
    if result < 1:
        raise ValueError(f"{name} must be a positive integer")
    return result


def _finite_positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be finite and positive")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _accelerator_count(value: object) -> int:
    if not isinstance(value, str) or ":" not in value:
        raise ValueError("resources.accelerator must end in a positive device count")
    _, raw_count = value.rsplit(":", 1)
    try:
        count = int(raw_count)
    except ValueError as error:
        raise ValueError("resources.accelerator count is invalid") from error
    if str(count) != raw_count or count < 1:
        raise ValueError("resources.accelerator count must be positive")
    return count


def _json_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return json.loads(canonical_json_bytes(value))


@dataclass(frozen=True)
class _LoadedDocument:
    payload: dict[str, object]
    sha256: str
    source: Path | None


def _load_document(value: Mapping[str, object] | str | Path, name: str) -> _LoadedDocument:
    if isinstance(value, Mapping):
        payload = _json_mapping(value)
        return _LoadedDocument(
            payload=payload,
            sha256=sha256_bytes(canonical_json_bytes(payload)),
            source=None,
        )
    source = _regular_file_nofollow(Path(value), name)
    try:
        payload = json.loads(source.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not readable canonical JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must contain a JSON object")
    try:
        canonical_json_bytes(payload)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} contains noncanonical values") from error
    return _LoadedDocument(payload=payload, sha256=sha256_file(source), source=source)


def _table(payload: Mapping[str, object], name: str) -> dict[str, object]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"frozen candidate is missing {name}")
    return dict(value)


def _resolve_reference(reference: str, candidate_source: Path | None) -> Path:
    path = Path(reference)
    if path.is_absolute():
        return path
    choices = []
    if candidate_source is not None:
        choices.append(candidate_source.parent / path)
    choices.extend((TRACK_ROOT / path, Path.cwd() / path))
    for choice in choices:
        if choice.is_file():
            return choice
    return choices[0]


@dataclass(frozen=True)
class _FrozenCandidate:
    payload: Mapping[str, object]
    sha256: str
    source: Path | None
    pilot_manifest: Path
    j_counts: Mapping[str, int]
    temperatures: Mapping[str, tuple[float, ...]]
    resources: Mapping[str, object]


def _load_frozen_candidate(
    candidate: Mapping[str, object] | str | Path,
) -> _FrozenCandidate:
    loaded = _load_document(candidate, "production candidate")
    payload = loaded.payload
    if payload.get("schema_version") != 1:
        raise ValueError("production candidate schema version is unsupported")
    if payload.get("classification") != PASS:
        raise ValueError("production candidate classification must be PASS")
    if payload.get("second_rg_enabled") is not False:
        raise ValueError("production candidate must keep second RG disabled")

    pilot_reference = payload.get("pilot_manifest")
    pilot_digest = payload.get("pilot_manifest_sha256")
    if not isinstance(pilot_reference, str) or not _valid_sha256(pilot_digest):
        raise ValueError("production candidate pilot manifest binding is invalid")
    pilot_path = _resolve_reference(pilot_reference, loaded.source)
    pilot = validate_stage6_pilot_manifest(pilot_path)
    if sha256_file(pilot_path) != pilot_digest:
        raise ValueError("production candidate pilot manifest hash mismatch")
    if (
        pilot.get("schema_version") != 1
        or pilot.get("stage") != "stage6"
        or pilot.get("classification") != PASS
        or pilot.get("second_rg_enabled") is not False
    ):
        raise ValueError("bound pilot manifest is not a passing Stage 6 record")

    frozen_names = (
        "temperatures_by_length",
        "sampling",
        "equilibration",
        "selection",
        "power",
        "resources",
        "thresholds",
        "seeds",
        "hashes",
        "artifact_root",
        "artifacts",
        "provenance",
    )
    for name in frozen_names:
        if payload.get(name) != pilot.get(name):
            raise ValueError(f"frozen candidate {name} does not match its pilot manifest")

    hashes = _table(payload, "hashes")
    if "design" not in hashes or any(not _valid_sha256(value) for value in hashes.values()):
        raise ValueError("frozen candidate hashes must include valid design provenance")
    power = _table(payload, "power")
    if power.get("sufficient") is not True:
        raise ValueError("frozen candidate disorder power did not pass")
    raw_counts = power.get("j_counts")
    if not isinstance(raw_counts, dict) or not raw_counts:
        raise ValueError("frozen candidate J counts are missing")
    j_counts: dict[str, int] = {}
    for raw_length, raw_count in raw_counts.items():
        try:
            length = int(raw_length)
        except (TypeError, ValueError) as error:
            raise ValueError("frozen candidate length keys must be integers") from error
        if str(length) != str(raw_length) or length < 3 or length % 3:
            raise ValueError("frozen candidate lengths must be positive multiples of three")
        j_counts[str(length)] = _positive_integer(raw_count, f"J count for L={length}")
    if "45" not in j_counts:
        raise ValueError("frozen candidate must contain L=45")

    raw_temperatures = _table(payload, "temperatures_by_length")
    if set(raw_temperatures) != set(j_counts):
        raise ValueError("temperature ladders must exactly cover frozen lengths")
    temperatures: dict[str, tuple[float, ...]] = {}
    for length, raw_values in raw_temperatures.items():
        if not isinstance(raw_values, list):
            raise ValueError(f"temperature ladder for L={length} must be an array")
        values = np.asarray(raw_values, dtype=np.float64)
        if (
            values.ndim != 1
            or values.size < 2
            or not np.all(np.isfinite(values))
            or np.any(values <= 0.0)
            or np.any(np.diff(1.0 / values) <= 0.0)
        ):
            raise ValueError(
                f"temperature ladder for L={length} must be finite and complete"
            )
        temperatures[length] = tuple(float(value) for value in values)

    sampling = _table(payload, "sampling")
    _positive_integer(sampling.get("chain_pairs"), "sampling.chain_pairs")
    selection = _table(payload, "selection")
    if selection.get("route") not in {"C", "B"}:
        raise ValueError("frozen candidate selected route is invalid")
    _positive_integer(selection.get("chi"), "selection.chi")
    if selection.get("mps_beats_conditioned_linear") is not True:
        raise ValueError("frozen candidate neural comparison did not pass")

    resources = _table(payload, "resources")
    for name in ("cluster_profile", "partition", "accelerator"):
        if not isinstance(resources.get(name), str) or not resources[name]:
            raise ValueError(f"frozen resource {name} is missing")
    resources["accelerator_count"] = _accelerator_count(resources["accelerator"])
    _positive_integer(resources.get("cpus"), "resources.cpus")
    for name in (
        "memory_bytes",
        "wall_seconds",
        "projected_output_bytes",
        "reserved_output_bytes",
    ):
        _finite_positive(resources.get(name), f"resources.{name}")
    partitions = resources.get("partition_candidates", [resources["partition"]])
    if (
        not isinstance(partitions, list)
        or not partitions
        or any(not isinstance(value, str) or not value for value in partitions)
    ):
        raise ValueError("frozen partition candidates are invalid")
    resources["partition_candidates"] = list(partitions)

    return _FrozenCandidate(
        payload=MappingProxyType(copy.deepcopy(payload)),
        sha256=loaded.sha256,
        source=loaded.source,
        pilot_manifest=pilot_path,
        j_counts=MappingProxyType(j_counts),
        temperatures=MappingProxyType(temperatures),
        resources=MappingProxyType(resources),
    )


def _seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("ascii")
    value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return value & ((1 << 63) - 1) or 1


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(TRACK_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _batch_size(j_counts: Sequence[int]) -> int:
    minimum_cells = len(j_counts) * len(EVIDENCE_ARMS)
    if minimum_cells > MAXIMUM_ARRAY_SIZE:
        raise ValueError(
            f"production exceeds array limit {MAXIMUM_ARRAY_SIZE} even with one batch per length"
        )
    for batch_size in range(1, max(j_counts) + 1):
        count = len(EVIDENCE_ARMS) * sum(
            math.ceil(value / batch_size) for value in j_counts
        )
        if count <= MAXIMUM_ARRAY_SIZE:
            return batch_size
    raise AssertionError("one batch per length should satisfy the array limit")


def build_production_run_spec(
    candidate: Mapping[str, object] | str | Path,
    run_id: str,
) -> dict[str, object]:
    """Build immutable full-ladder Stage 7 cells from a passing frozen candidate."""

    selected = _load_frozen_candidate(candidate)
    safe_run_id = _safe_component(run_id, "run_id")
    ordered_lengths = tuple(sorted((int(value) for value in selected.j_counts)))
    counts = tuple(selected.j_counts[str(length)] for length in ordered_lengths)
    disorder_batch_size = _batch_size(counts)
    selection = _table(selected.payload, "selection")
    sampling = _table(selected.payload, "sampling")
    chain_pairs = _positive_integer(sampling["chain_pairs"], "sampling.chain_pairs")
    design_hash = str(_table(selected.payload, "hashes")["design"])
    run_dir = f"results/hard_goal/{safe_run_id}"

    cells: list[dict[str, object]] = []
    for length, count in zip(ordered_lengths, counts, strict=True):
        temperatures = list(selected.temperatures[str(length)])
        for batch_index, start in enumerate(range(0, count, disorder_batch_size)):
            sample_indices = tuple(range(start, min(count, start + disorder_batch_size)))
            j_seeds = {
                index: _seed(design_hash, length, index) for index in sample_indices
            }
            for arm in EVIDENCE_ARMS:
                model_chi = 0 if arm == "unbiased_fss" else int(selection["chi"])
                cell_seed = _seed(
                    selected.sha256,
                    length,
                    batch_index,
                    arm,
                    model_chi,
                )
                cell_id = (
                    f"L{length:03d}-B{batch_index:03d}-"
                    f"{arm.replace('_', '-')}-X{model_chi:02d}-S{cell_seed:016x}"
                )
                j_records = []
                for sample_index in sample_indices:
                    j_seed = j_seeds[sample_index]
                    chain_seeds = [
                        _seed(j_seed, arm, chain_index)
                        for chain_index in range(2 * chain_pairs)
                    ]
                    j_records.append(
                        {
                            "global_sample_index": sample_index,
                            "j_id": f"L{length:03d}-J{sample_index:06d}",
                            "j_seed": j_seed,
                            "chain_seeds": chain_seeds,
                        }
                    )
                key = [length, batch_index, arm, model_chi, cell_seed]
                cells.append(
                    {
                        "array_index": len(cells) + 1,
                        "cell_id": cell_id,
                        "key": key,
                        "params": {
                            "stage": "stage7",
                            "length": length,
                            "disorder_batch": batch_index,
                            "evidence_arm": arm,
                            "model_chi": model_chi,
                            "seed": cell_seed,
                            "temperatures": temperatures,
                            "chain_pairs": chain_pairs,
                            "j_records": j_records,
                            "candidate_sha256": selected.sha256,
                            "stream_namespace": arm,
                            "selected_model": copy.deepcopy(selection),
                            "output": f"{run_dir}/cells/{arm}/{cell_id}",
                        },
                    }
                )
    if len(cells) > MAXIMUM_ARRAY_SIZE:
        raise ValueError(
            f"production has {len(cells)} cells, above array limit {MAXIMUM_ARRAY_SIZE}"
        )

    source_paths = {
        name: _regular_file_nofollow(
            TRACK_ROOT / name,
            f"Stage 7 source {name}",
        )
        for name in STAGE7_SOURCE_PATHS
    }
    source_hashes = {
        name: sha256_file(path) for name, path in source_paths.items()
    }
    spec: dict[str, object] = {
        "schema_version": 1,
        "stage": "stage7",
        "classification": "PLANNED",
        "run_id": safe_run_id,
        "run_dir": run_dir,
        "axes": {
            "length": list(ordered_lengths),
            "disorder_batch": "deterministic_contiguous_J_batches",
            "evidence_arm": list(EVIDENCE_ARMS),
            "model_chi": [0, int(selection["chi"])],
            "seed": "sha256_63bit",
        },
        "array": {
            "count": len(cells),
            "limit": MAXIMUM_ARRAY_SIZE,
            "index_origin": 1,
            "disorder_batch_size": disorder_batch_size,
        },
        "settings": {
            "sampling": copy.deepcopy(sampling),
            "selection": copy.deepcopy(selection),
            "thresholds": copy.deepcopy(_table(selected.payload, "thresholds")),
            "resources": copy.deepcopy(dict(selected.resources)),
            "second_rg": False,
        },
        "provenance": {
            "candidate_path": _display_path(selected.source),
            "candidate_sha256": selected.sha256,
            "pilot_manifest": _display_path(selected.pilot_manifest),
            "pilot_manifest_sha256": selected.payload["pilot_manifest_sha256"],
            "frozen_sha256": copy.deepcopy(_table(selected.payload, "hashes")),
            "source_sha256": source_hashes,
            "seed_contract": {
                "J": "sha256(design_hash,L,global_sample_index)",
                "chain": "sha256(J_seed,evidence_arm,chain_index)",
            },
        },
        "cells": cells,
    }
    _validate_run_spec(spec)
    return spec


def _validate_run_spec(spec: Mapping[str, object]) -> None:
    if spec.get("schema_version") != 1 or spec.get("stage") != "stage7":
        raise ValueError("run spec is not Stage 7 schema version 1")
    axes = spec.get("axes")
    if not isinstance(axes, dict) or "temperature" in axes:
        raise ValueError("temperature must not be a production cell axis")
    cells = spec.get("cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError("production run spec contains no cells")
    if len(cells) > MAXIMUM_ARRAY_SIZE:
        raise ValueError(f"production exceeds array limit {MAXIMUM_ARRAY_SIZE}")
    array = spec.get("array")
    if (
        not isinstance(array, dict)
        or array.get("count") != len(cells)
        or array.get("limit") != MAXIMUM_ARRAY_SIZE
        or array.get("index_origin") != 1
    ):
        raise ValueError("production array metadata is inconsistent")
    run_dir_value = spec.get("run_dir")
    if not isinstance(run_dir_value, str) or not run_dir_value:
        raise ValueError("production run directory is invalid")
    run_dir = Path(run_dir_value)
    if not run_dir.is_absolute():
        run_dir = TRACK_ROOT / run_dir
    run_dir = Path(os.path.abspath(run_dir))
    identifiers: set[str] = set()
    outputs: set[str] = set()
    for expected_index, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict):
            raise ValueError("production cell must be an object")
        identifier = _safe_component(cell.get("cell_id"), "cell_id")
        if identifier in identifiers or cell.get("array_index") != expected_index:
            raise ValueError("production cell IDs or array indices are inconsistent")
        identifiers.add(identifier)
        key = cell.get("key")
        params = cell.get("params")
        if not isinstance(key, list) or len(key) != 5 or not isinstance(params, dict):
            raise ValueError("production cell key or parameters are invalid")
        if "temperature" in params:
            raise ValueError("temperature must not be a production cell parameter")
        temperatures = params.get("temperatures")
        if not isinstance(temperatures, list) or len(temperatures) < 2:
            raise ValueError("every production cell requires a complete temperature ladder")
        expected_key = [
            params.get("length"),
            params.get("disorder_batch"),
            params.get("evidence_arm"),
            params.get("model_chi"),
            params.get("seed"),
        ]
        if key != expected_key:
            raise ValueError("production cell key does not match parameters")
        output = params.get("output")
        if not isinstance(output, str) or not output or output in outputs:
            raise ValueError("production cell output namespaces must be unique")
        arm = params.get("evidence_arm")
        if arm not in EVIDENCE_ARMS:
            raise ValueError("production evidence arm is invalid")
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = TRACK_ROOT / output_path
        output_path = Path(os.path.abspath(output_path))
        expected_parent = run_dir / "cells" / str(arm)
        try:
            output_path.relative_to(expected_parent)
        except ValueError as error:
            raise ValueError(
                "production cell output namespace lies outside its evidence arm"
            ) from error
        outputs.add(output)
    provenance = spec.get("provenance")
    if not isinstance(provenance, dict) or not _valid_sha256(
        provenance.get("candidate_sha256")
    ):
        raise ValueError("run spec candidate provenance is invalid")
    source_hashes = provenance.get("source_sha256")
    if not isinstance(source_hashes, dict) or any(
        not _valid_sha256(value) for value in source_hashes.values()
    ):
        raise ValueError("run spec source hashes are invalid")


def cell_spec_sha256(cell: Mapping[str, object]) -> str:
    """Return the canonical hash binding one immutable Stage 7 cell."""

    return sha256_bytes(canonical_json_bytes(cell))


@dataclass(frozen=True)
class CellManifest:
    cell_id: str
    classification: str
    terminal: bool
    output: str
    artifacts: Mapping[str, str]
    hashes: Mapping[str, str]
    checkpoint: str | None = None
    resume_checkpoint: str | None = None
    completed_steps: int = 0

    def __post_init__(self) -> None:
        _safe_component(self.cell_id, "cell_id")
        if self.terminal and self.classification not in TERMINAL_CLASSIFICATIONS:
            raise ValueError("terminal cell classification is invalid")
        if not self.terminal and self.classification not in {"READY", "RESUME_REQUIRED"}:
            raise ValueError("nonterminal cell classification is invalid")
        if self.completed_steps < 0:
            raise ValueError("completed cell steps cannot be negative")
        artifacts = {str(name): str(path) for name, path in self.artifacts.items()}
        hashes = {str(path): str(digest) for path, digest in self.hashes.items()}
        if any(not _valid_sha256(value) for value in hashes.values()):
            raise ValueError("cell manifest hashes are invalid")
        object.__setattr__(self, "artifacts", MappingProxyType(artifacts))
        object.__setattr__(self, "hashes", MappingProxyType(hashes))

    @property
    def exit_code(self) -> int:
        if self.classification == PASS:
            return 0
        if self.classification in {"READY", "RESUME_REQUIRED"}:
            return 75
        return 2

    def to_dict(self) -> dict[str, object]:
        return {
            "cell_id": self.cell_id,
            "classification": self.classification,
            "terminal": self.terminal,
            "output": self.output,
            "artifacts": dict(self.artifacts),
            "hashes": dict(self.hashes),
            "checkpoint": self.checkpoint,
            "resume_checkpoint": self.resume_checkpoint,
            "completed_steps": self.completed_steps,
        }


def _load_bound_run_spec(
    value: str | Path,
    *,
    approved_run_spec_sha256: str | None,
) -> tuple[dict[str, object], str]:
    loaded = _load_document(value, "production run spec")
    if loaded.source is None:
        raise ValueError("production run spec must be a durable file")
    payload = loaded.payload
    if loaded.source.read_bytes() != canonical_json_bytes(payload):
        raise ValueError("production run spec bytes are not canonical JSON")
    _validate_run_spec(payload)
    provenance = payload["provenance"]
    candidate_reference = provenance.get("candidate_path")
    if not isinstance(candidate_reference, str) or not candidate_reference:
        raise ValueError("run spec has no bound candidate path")
    candidate_path = _resolve_reference(candidate_reference, loaded.source)
    expected = build_production_run_spec(candidate_path, str(payload.get("run_id")))
    if payload != expected:
        raise ValueError("run spec is not canonical candidate-derived output")
    if approved_run_spec_sha256 is not None:
        if not _valid_sha256(approved_run_spec_sha256):
            raise ValueError("approved run-spec SHA-256 is invalid")
        if loaded.sha256 != approved_run_spec_sha256:
            raise ValueError("approved run-spec SHA-256 mismatch")
    return payload, loaded.sha256


def _resolve_cell(spec: Mapping[str, object], selector: str | int) -> dict[str, object]:
    cells = spec["cells"]
    if isinstance(selector, int) or (isinstance(selector, str) and selector.isdigit()):
        index = int(selector)
        for cell in cells:
            if cell["array_index"] == index:
                return cell
    else:
        for cell in cells:
            if cell["cell_id"] == selector:
                return cell
    raise KeyError(f"unknown production cell selector: {selector!r}")


def _rooted(path: str, root: Path = TRACK_ROOT) -> Path:
    value = Path(path)
    return value if value.is_absolute() else root / value


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _assert_nofollow_components(
    path: Path,
    name: str,
    *,
    allow_missing: bool,
) -> Path:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    missing = False
    for component in absolute.parts[1:]:
        current /= component
        if missing:
            continue
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if allow_missing:
                missing = True
                continue
            raise FileNotFoundError(f"{name} is missing: {current}")
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"{name} contains a symlink: {current}")
    return absolute


def _mkdirs_nofollow(path: Path, name: str) -> Path:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            try:
                os.mkdir(current, 0o700)
            except FileExistsError:
                metadata = os.lstat(current)
            else:
                metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"{name} contains a symlink or non-directory: {current}")
    return absolute


def _lstat_or_none(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _regular_file_nofollow(path: Path, name: str) -> Path:
    absolute = _assert_nofollow_components(path, name, allow_missing=False)
    if not stat.S_ISREG(os.lstat(absolute).st_mode):
        raise ValueError(f"{name} is not a regular file: {absolute}")
    return absolute


def _directory_nofollow(path: Path, name: str) -> Path:
    absolute = _assert_nofollow_components(path, name, allow_missing=False)
    if not stat.S_ISDIR(os.lstat(absolute).st_mode):
        raise ValueError(f"{name} is not a directory: {absolute}")
    return absolute


def _safe_relative_file(root: Path, relative: object, name: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"{name} path is invalid")
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise ValueError(f"{name} path escapes its artifact root")
    candidate = _absolute(root / value)
    try:
        candidate.relative_to(_absolute(root))
    except ValueError as error:
        raise ValueError(f"{name} path escapes its artifact root") from error
    return _regular_file_nofollow(candidate, name)


def _artifact_inventory(root: Path, *, exclude: set[str]) -> set[str]:
    directory = _directory_nofollow(root, "artifact root")
    inventory: set[str] = set()
    for current, names, files in os.walk(directory, followlinks=False):
        current_path = Path(current)
        for name in names:
            candidate = current_path / name
            metadata = os.lstat(candidate)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise ValueError(
                    "artifact inventory contains a symlink or special directory: "
                    f"{candidate}"
                )
        for name in files:
            candidate = current_path / name
            metadata = os.lstat(candidate)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise ValueError(
                    "artifact inventory contains a symlink or special file: "
                    f"{candidate}"
                )
            relative = candidate.relative_to(directory).as_posix()
            if relative not in exclude:
                inventory.add(relative)
    return inventory


def _load_json_file_nofollow(path: Path, name: str) -> dict[str, object]:
    source = _regular_file_nofollow(path, name)
    try:
        payload = json.loads(source.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not readable JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must contain an object")
    return payload


def _receipt_payload(
    *,
    kind: str,
    cell: Mapping[str, object],
    manifest_path: Path,
    run_spec_sha256: str,
    completed_steps: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "kind": kind,
        "cell_id": cell["cell_id"],
        "cell_spec_sha256": cell_spec_sha256(cell),
        "run_spec_sha256": run_spec_sha256,
        "manifest_sha256": sha256_file(manifest_path),
    }
    if completed_steps is not None:
        payload["completed_steps"] = completed_steps
        payload["checkpoint"] = manifest_path.parent.name
    return payload


def _verify_receipt(path: Path, expected: Mapping[str, object]) -> None:
    payload = _load_json_file_nofollow(path, "immutable receipt anchor")
    if payload != dict(expected):
        raise ValueError("immutable receipt anchor does not match the manifest hash")


def _anchor_receipt_no_replace(path: Path, payload: Mapping[str, object]) -> None:
    destination = _absolute(path)
    parent = _mkdirs_nofollow(destination.parent, "receipt directory")
    if _lstat_or_none(destination) is not None:
        _verify_receipt(destination, payload)
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError:
            _verify_receipt(destination, payload)
        else:
            os.chmod(destination, 0o400, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def _finite_observable(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        return False
    return math.isfinite(float(value))


def _validate_pass_evidence(
    root: Path,
    cell: Mapping[str, object],
    artifacts: Mapping[str, object],
) -> None:
    if "summary" not in artifacts or "diagnostics" not in artifacts:
        raise ValueError("PASS requires summary and diagnostics artifacts")
    summary = _load_json_file_nofollow(
        _safe_relative_file(root, artifacts["summary"], "PASS summary"),
        "PASS summary",
    )
    diagnostics = _load_json_file_nofollow(
        _safe_relative_file(root, artifacts["diagnostics"], "PASS diagnostics"),
        "PASS diagnostics",
    )
    params = cell["params"]
    planned = [record["j_id"] for record in params["j_records"]]
    if not planned or len(set(planned)) != len(planned):
        raise ValueError("PASS cell has an invalid planned J inventory")
    records = diagnostics.get("j_records")
    if not isinstance(records, list) or len(records) != len(planned):
        raise ValueError("PASS diagnostics do not expose every planned J ID")
    by_id: dict[str, dict[str, object]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("j_id"), str):
            raise ValueError("PASS diagnostics contain an invalid J record")
        j_id = str(record["j_id"])
        if j_id in by_id:
            raise ValueError("PASS diagnostics contain a duplicate J ID")
        if (
            type(record.get("completed")) is not bool
            or type(record.get("equilibrated")) is not bool
        ):
            raise ValueError("PASS diagnostics contain invalid completion/equilibration flags")
        failed_gates = record.get("failed_gates")
        if not isinstance(failed_gates, list) or any(
            not isinstance(value, str) or not value for value in failed_gates
        ):
            raise ValueError("PASS diagnostics contain invalid equilibration gates")
        by_id[j_id] = record
    if set(by_id) != set(planned):
        raise ValueError("PASS diagnostics omit or invent planned J IDs")
    completed = [j_id for j_id in planned if by_id[j_id]["completed"]]
    if len(completed) / len(planned) < 0.95:
        raise ValueError("PASS preregistered completion is below 95%")
    for j_id in completed:
        if not by_id[j_id]["equilibrated"] or by_id[j_id]["failed_gates"]:
            raise ValueError(f"PASS included J did not pass equilibration: {j_id}")
    failed = [j_id for j_id in planned if j_id not in completed]
    if diagnostics.get("failed_j_ids") != failed:
        raise ValueError("PASS failed J IDs are not fully visible")

    if (
        summary.get("schema_version") != 1
        or summary.get("cell_id") != cell["cell_id"]
        or summary.get("length") != params["length"]
        or summary.get("j_ids") != completed
    ):
        raise ValueError("PASS summary does not match the cell and completed J inventory")
    observables = summary.get("observables_by_j")
    if not isinstance(observables, dict) or set(observables) != set(completed):
        raise ValueError("PASS summary lacks actual data for every completed J")
    for j_id, values in observables.items():
        if (
            not isinstance(values, dict)
            or not values
            or any(not _finite_observable(value) for value in values.values())
        ):
            raise ValueError(f"PASS summary has invalid actual data for J {j_id}")
    if int(params["length"]) == 45 and not completed:
        raise ValueError("PASS L=45 cell contains no actual completed data")


def _validated_terminal(
    root: Path,
    cell: Mapping[str, object],
    *,
    run_spec_sha256: str,
    receipt: Path | None,
) -> tuple[CellManifest, dict[str, object]]:
    root = _directory_nofollow(root, "terminal cell directory")
    manifest_path = root / "manifest.json"
    payload = _load_json_file_nofollow(manifest_path, "terminal cell manifest")
    if (
        payload.get("schema_version") != 1
        or payload.get("cell_id") != cell["cell_id"]
        or payload.get("cell_spec_sha256") != cell_spec_sha256(cell)
    ):
        raise ValueError("terminal cell manifest does not match its cell spec")
    classification = payload.get("classification")
    if classification not in TERMINAL_CLASSIFICATIONS:
        raise ValueError("terminal cell classification is invalid")
    artifacts = payload.get("artifacts")
    hashes = payload.get("hashes")
    checkpoint = payload.get("checkpoint")
    if not isinstance(artifacts, dict) or not isinstance(hashes, dict):
        raise ValueError("terminal cell artifact inventory is invalid")
    if set(hashes) != _artifact_inventory(root, exclude={"manifest.json"}):
        raise ValueError("terminal cell manifest does not hash every staged artifact")
    if any(not _valid_sha256(value) for value in hashes.values()):
        raise ValueError("terminal cell artifact hash is invalid")
    for relative, digest in hashes.items():
        artifact = _safe_relative_file(root, relative, "terminal cell artifact")
        if sha256_file(artifact) != digest:
            raise ValueError(f"terminal cell hash mismatch: {relative}")
    if any(relative not in hashes for relative in artifacts.values()):
        raise ValueError("terminal cell named artifact is not hash-linked")
    if not isinstance(checkpoint, str) or checkpoint not in hashes:
        raise ValueError("terminal cell checkpoint is not hash-linked")
    if classification == PASS:
        _validate_pass_evidence(root, cell, artifacts)
    receipt_payload = _receipt_payload(
        kind="terminal",
        cell=cell,
        manifest_path=manifest_path,
        run_spec_sha256=run_spec_sha256,
    )
    if receipt is not None:
        _verify_receipt(receipt, receipt_payload)
    return CellManifest(
        cell_id=str(cell["cell_id"]),
        classification=str(classification),
        terminal=True,
        output=str(root),
        artifacts=artifacts,
        hashes=hashes,
        checkpoint=str(root / checkpoint),
    ), receipt_payload


def _validated_checkpoint(
    path: Path,
    cell: Mapping[str, object],
    *,
    run_spec_sha256: str,
    receipt: Path,
) -> tuple[int, Path]:
    path = _directory_nofollow(path, "checkpoint directory")
    manifest_path = path / "manifest.json"
    payload = _load_json_file_nofollow(manifest_path, "checkpoint manifest")
    if (
        payload.get("schema_version") != 1
        or payload.get("cell_id") != cell["cell_id"]
        or payload.get("cell_spec_sha256") != cell_spec_sha256(cell)
    ):
        raise ValueError("checkpoint does not match its production cell")
    completed = _positive_integer(payload.get("completed_steps"), "completed_steps")
    hashes = payload.get("hashes")
    if not isinstance(hashes, dict) or set(hashes) != _artifact_inventory(
        path, exclude={"manifest.json"}
    ):
        raise ValueError("checkpoint artifact inventory is incomplete")
    for relative, digest in hashes.items():
        artifact = _safe_relative_file(path, relative, "checkpoint artifact")
        if not _valid_sha256(digest) or sha256_file(artifact) != digest:
            raise ValueError(f"checkpoint hash mismatch: {relative}")
    if "state.json" not in hashes:
        raise ValueError("checkpoint state.json is not hash-linked")
    state = _load_json_file_nofollow(path / "state.json", "checkpoint state")
    if state.get("completed_steps") != completed:
        raise ValueError("checkpoint completed steps do not match its state")
    receipt_payload = _receipt_payload(
        kind="checkpoint",
        cell=cell,
        manifest_path=manifest_path,
        run_spec_sha256=run_spec_sha256,
        completed_steps=completed,
    )
    _anchor_receipt_no_replace(receipt, receipt_payload)
    _verify_receipt(receipt, receipt_payload)
    return completed, path


def _promote_directory_nofollow(
    staging: Path,
    final: Path,
    expected: Mapping[str, str],
) -> None:
    staging = _directory_nofollow(staging, "staging directory")
    if set(expected) != _artifact_inventory(staging, exclude=set()):
        raise ValueError("staging inventory changed before promotion")
    for relative, digest in expected.items():
        artifact = _safe_relative_file(staging, relative, "staged artifact")
        if sha256_file(artifact) != digest:
            raise ValueError(f"staged artifact hash mismatch before promotion: {relative}")
    source_parent = _directory_nofollow(staging.parent, "staging parent")
    destination_parent = _mkdirs_nofollow(final.parent, "output parent")
    if _lstat_or_none(final) is not None:
        raise FileExistsError(f"refusing to replace production output: {final}")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    source_fd = os.open(source_parent, flags)
    destination_fd = os.open(destination_parent, flags)
    try:
        source_metadata = os.stat(staging.name, dir_fd=source_fd, follow_symlinks=False)
        if not stat.S_ISDIR(source_metadata.st_mode):
            raise ValueError("staging entry changed before promotion")
        try:
            os.stat(final.name, dir_fd=destination_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(f"refusing to replace production output: {final}")
        renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
        if renameat2 is None:
            raise RuntimeError("atomic no-replace production promotion is unavailable")
        renameat2.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        renameat2.restype = ctypes.c_int
        result = renameat2(
            source_fd,
            os.fsencode(staging.name),
            destination_fd,
            os.fsencode(final.name),
            1,  # RENAME_NOREPLACE
        )
        if result != 0:
            error_number = ctypes.get_errno()
            if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
                raise FileExistsError(
                    error_number,
                    f"refusing to replace production output: {final}",
                    str(final),
                )
            raise OSError(error_number, os.strerror(error_number), str(final))
        os.fsync(destination_fd)
    finally:
        os.close(destination_fd)
        os.close(source_fd)


def run_cell(
    run_spec: str | Path,
    cell_id: str | int,
    *,
    approved_run_spec_sha256: str,
    execution_root: str | Path = TRACK_ROOT,
) -> CellManifest:
    """Resolve, resume, or atomically promote one externally computed cell."""

    spec, run_spec_sha256 = _load_bound_run_spec(
        run_spec,
        approved_run_spec_sha256=approved_run_spec_sha256,
    )
    cell = _resolve_cell(spec, cell_id)
    root = Path(execution_root)
    run_dir = _rooted(str(spec["run_dir"]), root)
    output = _rooted(str(cell["params"]["output"]), root)
    staging = run_dir / "staging" / str(cell["cell_id"])
    _assert_nofollow_components(run_dir, "production run directory", allow_missing=True)
    _assert_nofollow_components(output, "production output", allow_missing=True)
    _assert_nofollow_components(staging, "production staging", allow_missing=True)
    receipt = run_dir / "receipts" / f"{cell['cell_id']}.terminal.json"
    output_metadata = _lstat_or_none(output)
    staging_metadata = _lstat_or_none(staging)
    if output_metadata is not None:
        if staging_metadata is not None:
            raise RuntimeError("terminal production cell conflicts with staging state")
        if stat.S_ISLNK(output_metadata.st_mode) or not stat.S_ISDIR(output_metadata.st_mode):
            raise ValueError("terminal production cell output is not a directory")
        terminal, _ = _validated_terminal(
            output,
            cell,
            run_spec_sha256=run_spec_sha256,
            receipt=receipt,
        )
        return terminal
    if staging_metadata is not None and (
        stat.S_ISLNK(staging_metadata.st_mode) or not stat.S_ISDIR(staging_metadata.st_mode)
    ):
        raise ValueError("production cell staging path is not a directory")
    manifest_metadata = _lstat_or_none(staging / "manifest.json")
    if manifest_metadata is not None:
        if stat.S_ISLNK(manifest_metadata.st_mode) or not stat.S_ISREG(manifest_metadata.st_mode):
            raise ValueError("terminal cell manifest is a symlink or special file")
        terminal, receipt_payload = _validated_terminal(
            staging,
            cell,
            run_spec_sha256=run_spec_sha256,
            receipt=None,
        )
        _anchor_receipt_no_replace(receipt, receipt_payload)
        terminal, _ = _validated_terminal(
            staging,
            cell,
            run_spec_sha256=run_spec_sha256,
            receipt=receipt,
        )
        expected = {
            **dict(terminal.hashes),
            "manifest.json": sha256_file(staging / "manifest.json"),
        }
        _promote_directory_nofollow(staging, output, expected)
        promoted, _ = _validated_terminal(
            output,
            cell,
            run_spec_sha256=run_spec_sha256,
            receipt=receipt,
        )
        return promoted

    checkpoint_root = staging / "checkpoints"
    checkpoint_metadata = _lstat_or_none(checkpoint_root)
    if checkpoint_metadata is not None:
        if stat.S_ISLNK(checkpoint_metadata.st_mode) or not stat.S_ISDIR(
            checkpoint_metadata.st_mode
        ):
            raise ValueError("checkpoint root is a symlink or non-directory")
        checkpoint_root = _directory_nofollow(checkpoint_root, "checkpoint root")
        checkpoint_records = []
        for checkpoint in sorted(checkpoint_root.iterdir()):
            if checkpoint.name.startswith("."):
                continue
            _safe_component(checkpoint.name, "checkpoint name")
            metadata = os.lstat(checkpoint)
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError("checkpoint inventory contains a symlink")
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("checkpoint inventory contains a non-directory entry")
            checkpoint_receipt = (
                run_dir
                / "checkpoint-receipts"
                / str(cell["cell_id"])
                / f"{checkpoint.name}.json"
            )
            checkpoint_records.append(
                _validated_checkpoint(
                    checkpoint,
                    cell,
                    run_spec_sha256=run_spec_sha256,
                    receipt=checkpoint_receipt,
                )
            )
        if checkpoint_records:
            completed, checkpoint = max(checkpoint_records, key=lambda item: item[0])
            return CellManifest(
                cell_id=str(cell["cell_id"]),
                classification="RESUME_REQUIRED",
                terminal=False,
                output=str(output),
                artifacts={},
                hashes={},
                resume_checkpoint=str(checkpoint),
                completed_steps=completed,
            )
    return CellManifest(
        cell_id=str(cell["cell_id"]),
        classification="READY",
        terminal=False,
        output=str(output),
        artifacts={},
        hashes={},
    )


@dataclass(frozen=True)
class SlurmPreview:
    array_count: int
    resources: Mapping[str, object]
    temperature_counts_by_length: Mapping[str, int]
    j_counts_by_length: Mapping[str, int]
    estimated_accelerator_hours_upper_bound: float
    output: Mapping[str, object]
    hashes: Mapping[str, str]
    recovery: Mapping[str, str]
    checks: Mapping[str, object]
    execution_performed: bool = False
    submission_authorized: bool = False

    def __post_init__(self) -> None:
        if self.array_count < 1 or self.array_count > MAXIMUM_ARRAY_SIZE:
            raise ValueError("Slurm preview array count is invalid")
        if self.submission_authorized:
            raise ValueError("SlurmPreview cannot authorize real submission")
        for name in (
            "resources",
            "temperature_counts_by_length",
            "j_counts_by_length",
            "output",
            "hashes",
            "recovery",
            "checks",
        ):
            object.__setattr__(self, name, _deep_freeze(getattr(self, name)))

    def to_dict(self) -> dict[str, object]:
        return {
            "array_count": self.array_count,
            "resources": _deep_thaw(self.resources),
            "temperature_counts_by_length": _deep_thaw(
                self.temperature_counts_by_length
            ),
            "j_counts_by_length": _deep_thaw(self.j_counts_by_length),
            "estimated_accelerator_hours_upper_bound": (
                self.estimated_accelerator_hours_upper_bound
            ),
            "output": _deep_thaw(self.output),
            "hashes": _deep_thaw(self.hashes),
            "recovery": _deep_thaw(self.recovery),
            "checks": _deep_thaw(self.checks),
            "execution_performed": self.execution_performed,
            "submission_authorized": self.submission_authorized,
        }


def _deep_freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    return copy.deepcopy(value)


def _deep_thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in value]
    return copy.deepcopy(value)


def _slurm_walltime(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"


def _run_preview_check(
    name: str,
    command: Sequence[str],
    *,
    command_runner: Callable[..., object],
    environment: Mapping[str, str],
) -> dict[str, object]:
    completed = command_runner(
        list(command),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=dict(environment),
    )
    try:
        returncode = int(completed.returncode)
        stdout = str(completed.stdout)
        stderr = str(completed.stderr)
    except AttributeError as error:
        raise TypeError("preview command runner returned an invalid result") from error
    record = {
        "command": list(command),
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
    }
    if returncode != 0:
        raise RuntimeError(
            f"Stage 7 {name} failed closed with exit {returncode}: {stderr or stdout}"
        )
    return record


def preview_slurm(
    candidate: str | Path,
    run_spec: str | Path,
    script: str | Path,
    *,
    command_runner: Callable[..., object] = subprocess.run,
) -> SlurmPreview:
    """Run precheck, queue probe, and scheduler test-only; never submit a job."""

    selected = _load_frozen_candidate(candidate)
    spec_path = _regular_file_nofollow(Path(run_spec), "production run spec")
    spec, run_spec_sha256 = _load_bound_run_spec(
        spec_path,
        approved_run_spec_sha256=None,
    )
    provenance = spec["provenance"]
    if provenance.get("candidate_sha256") != selected.sha256:
        raise ValueError("run spec does not match the frozen candidate hash")
    script_path = _regular_file_nofollow(Path(script), "Stage 7 Slurm wrapper")
    script_hash = sha256_file(script_path)
    expected_script_hash = provenance["source_sha256"].get(
        "jobs/hard_goal_array.slurm"
    )
    if script_hash != expected_script_hash:
        raise ValueError("Stage 7 Slurm wrapper hash mismatch")
    source = script_path.read_text(encoding="ascii")
    for forbidden in (
        "--partition",
        "--gres",
        "--mem",
        "--time",
        "A800",
        "/home/",
        "/scratch/",
    ):
        if forbidden in source:
            raise ValueError(f"Slurm wrapper contains profile-specific value: {forbidden}")
    for required in (
        "HARNESS_RUN_SPEC",
        "SLURM_ARRAY_TASK_ID",
        "HARNESS_PYTHON",
        "scripts/hard_goal.py",
    ):
        if required not in source:
            raise ValueError(f"Slurm wrapper is missing {required}")

    resources = selected.resources
    accelerator_count = int(resources["accelerator_count"])
    resource_record = {
        "profile": resources["cluster_profile"],
        "partition_candidates": list(resources["partition_candidates"]),
        "cpus": int(resources["cpus"]),
        "accelerator": resources["accelerator"],
        "accelerator_count": accelerator_count,
        "memory_bytes": int(resources["memory_bytes"]),
        "wall_seconds": int(resources["wall_seconds"]),
    }
    temperature_counts: dict[str, int] = {}
    for cell in spec["cells"]:
        length = str(cell["params"]["length"])
        count = len(cell["params"]["temperatures"])
        previous = temperature_counts.setdefault(length, count)
        if previous != count:
            raise ValueError("run spec temperature counts differ within one length")
    hashes = {
        "candidate_sha256": selected.sha256,
        "pilot_manifest_sha256": str(selected.payload["pilot_manifest_sha256"]),
        "run_spec_sha256": run_spec_sha256,
        "script_sha256": script_hash,
        **{
            f"frozen:{name}": str(value)
            for name, value in _table(selected.payload, "hashes").items()
        },
        **{
            f"source:{name}": str(value)
            for name, value in provenance["source_sha256"].items()
        },
    }
    wall_seconds = int(resources["wall_seconds"])
    harness = _regular_file_nofollow(
        REPO_ROOT / "scripts/harness_slurm.sh",
        "Slurm harness",
    )
    environment = {
        **os.environ,
        "HARNESS_CLUSTER_PROFILE": str(resources["cluster_profile"]),
    }
    precheck_command = [str(harness), "precheck"]
    probe_command = [str(harness), "probe-partitions"]
    test_only_command = [
        str(harness),
        "submit",
        "--test-only",
        "--script",
        str(script_path),
        "--array",
        str(len(spec["cells"])),
        "--run-spec",
        str(spec_path),
        "--command",
        "scripts/hard_goal.py cell",
        "--partition",
        str(resources["partition"]),
        "--time",
        _slurm_walltime(wall_seconds),
        "--cpus",
        str(resources["cpus"]),
    ]
    checks = {
        "precheck": _run_preview_check(
            "precheck",
            precheck_command,
            command_runner=command_runner,
            environment=environment,
        ),
        "probe_partitions": _run_preview_check(
            "partition probe",
            probe_command,
            command_runner=command_runner,
            environment=environment,
        ),
        "test_only": _run_preview_check(
            "scheduler test-only",
            test_only_command,
            command_runner=command_runner,
            environment=environment,
        ),
    }
    return SlurmPreview(
        array_count=len(spec["cells"]),
        resources=resource_record,
        temperature_counts_by_length=temperature_counts,
        j_counts_by_length=dict(selected.j_counts),
        estimated_accelerator_hours_upper_bound=(
            len(spec["cells"]) * wall_seconds * accelerator_count / 3600.0
        ),
        output={
            "run_dir": spec["run_dir"],
            "projected_output_bytes": int(resources["projected_output_bytes"]),
            "reserved_output_bytes": int(resources["reserved_output_bytes"]),
        },
        hashes=hashes,
        recovery={
            "successful_cells": "immutable_no_rerun",
            "failed_cells": "review_required_no_automatic_rerun",
            "incomplete_cells": "resume_latest_complete_checkpoint",
        },
        checks=checks,
        execution_performed=True,
    )
