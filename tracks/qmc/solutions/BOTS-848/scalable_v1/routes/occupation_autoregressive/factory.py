"""Strict environment-only loader for a frozen occupation candidate."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from benchmark_v0.lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
)

from ...audit import sha256_file, verify_manifest
from ...contracts import ResourceMetrics
from ...protocol import load_protocol
from .adapter import OccupationCandidate
from .model import AutoregressiveNQS
from .operators import PreparedPairOperator


RUN_DIR_ENV = "BOTS848_SCALABLE_RUN_DIR"
ROUTE = "occupation_autoregressive"
ATTEMPT = "s02a-a05"
SOLUTION_ROOT = Path(__file__).resolve().parents[3]
ROUTE_PACKAGE = Path(__file__).resolve().parent
EXPECTED_ARTIFACT_PATHS = {
    "checkpoint": "checkpoint.npz",
    "optimizer_state": "optimizer-state.npz",
    "training_log": "training.jsonl",
}


def _pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_hook,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON artifact: {path.name}") from error
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON artifact must be an object: {path.name}")
    return value


def _scalar(archive: Mapping[str, np.ndarray], name: str) -> Any:
    if name not in archive:
        raise ValueError(f"checkpoint field missing: {name}")
    array = np.asarray(archive[name])
    if array.shape != ():
        raise ValueError(f"checkpoint field must be scalar: {name}")
    return array.item()


def _expected_sources() -> set[str]:
    files = [
        SOLUTION_ROOT / "train_occupation_autoregressive.py",
        *sorted(ROUTE_PACKAGE.glob("*.py")),
    ]
    return {path.relative_to(SOLUTION_ROOT).as_posix() for path in files}


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            return {name: np.asarray(archive[name]).copy() for name in archive.files}
    except (OSError, ValueError) as error:
        raise ValueError(f"invalid NPZ artifact: {path.name}") from error


def _training_records(path: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise ValueError("invalid training log") from error
    if not lines or any(not line.strip() for line in lines):
        raise ValueError("training log must contain non-empty JSONL records")
    for line in lines:
        try:
            record = json.loads(line, object_pairs_hook=_pairs_hook)
        except json.JSONDecodeError as error:
            raise ValueError("invalid training log JSONL") from error
        if not isinstance(record, Mapping):
            raise ValueError("training log records must be objects")
        records.append(record)
    return records


def _resource_metrics(
    selected: Mapping[str, Any],
    *,
    checkpoint_bytes: int,
) -> ResourceMetrics:
    raw = selected.get("resource_metrics")
    if not isinstance(raw, Mapping):
        raise ValueError("selected training record is missing measured resource metrics")
    expected = {
        "placement",
        "wall_seconds",
        "peak_rss_bytes",
        "peak_vram_bytes",
        "estimator_evaluations",
        "effective_sample_size",
        "n8_smoke_complete",
        "n8_to_n6_time_ratio",
        "n8_to_n6_memory_ratio",
        "device_fingerprint",
    }
    if set(raw) != expected:
        raise ValueError("measured resource metric schema mismatch")
    return ResourceMetrics(
        placement=str(raw["placement"]),
        wall_seconds=float(raw["wall_seconds"]),
        peak_rss_bytes=int(raw["peak_rss_bytes"]),
        peak_vram_bytes=(
            None if raw["peak_vram_bytes"] is None else int(raw["peak_vram_bytes"])
        ),
        checkpoint_bytes=checkpoint_bytes,
        estimator_evaluations=int(raw["estimator_evaluations"]),
        effective_sample_size=float(raw["effective_sample_size"]),
        n8_smoke_complete=bool(raw["n8_smoke_complete"]),
        n8_to_n6_time_ratio=float(raw["n8_to_n6_time_ratio"]),
        n8_to_n6_memory_ratio=float(raw["n8_to_n6_memory_ratio"]),
        device_fingerprint=str(raw["device_fingerprint"]),
    )


def _run_dir_from_environment() -> Path:
    raw = os.environ.get(RUN_DIR_ENV)
    if raw is None or not raw.strip():
        raise ValueError(f"{RUN_DIR_ENV} must name exactly one run directory")
    parts = raw.split(os.pathsep)
    if len(parts) != 1 or not parts[0].strip():
        raise ValueError(f"{RUN_DIR_ENV} must name exactly one run directory")
    path = Path(parts[0]).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"{RUN_DIR_ENV} is not an existing run directory")
    return path


def load_candidate() -> OccupationCandidate:
    """Load only the directory named by ``BOTS848_SCALABLE_RUN_DIR``."""

    run_dir = _run_dir_from_environment()
    protocol = load_protocol()
    manifest_path = run_dir / "training-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("training manifest is missing")
    manifest = _json(manifest_path)
    audit = verify_manifest(
        manifest_path,
        project_root=SOLUTION_ROOT,
        protocol=protocol,
    )
    if not audit.valid:
        raise ValueError("; ".join(audit.issues))
    if manifest.get("route") != ROUTE:
        raise ValueError("manifest route mismatch")
    if manifest.get("attempt") != ATTEMPT:
        raise ValueError("manifest attempt mismatch")
    training_seed = manifest.get("training_seed")
    if isinstance(training_seed, bool) or not isinstance(training_seed, int):
        raise ValueError("manifest training seed mismatch")
    if manifest.get("selected_update") != protocol.training["optimizer_updates"]:
        raise ValueError("manifest selected update mismatch")
    source_items = manifest.get("source_files")
    if not isinstance(source_items, list) or {
        item.get("path") for item in source_items if isinstance(item, Mapping)
    } != _expected_sources() or len(source_items) != len(_expected_sources()):
        raise ValueError("manifest source-file set mismatch")
    artifact_items = manifest.get("artifacts")
    if not isinstance(artifact_items, list):
        raise ValueError("manifest artifact schema mismatch")
    by_role = {
        item.get("role"): item for item in artifact_items if isinstance(item, Mapping)
    }
    if set(by_role) != set(EXPECTED_ARTIFACT_PATHS) or len(artifact_items) != 3:
        raise ValueError("manifest artifact role mismatch")
    for role, expected_path in EXPECTED_ARTIFACT_PATHS.items():
        item = by_role[role]
        if item.get("path") != expected_path:
            raise ValueError(f"manifest artifact path mismatch: {role}")
        path = run_dir / expected_path
        if item.get("bytes") != path.stat().st_size:
            raise ValueError(f"artifact byte size mismatch: {role}")
        if item.get("sha256") != sha256_file(path):
            raise ValueError(f"artifact hash mismatch: {role}")

    checkpoint_path = run_dir / EXPECTED_ARTIFACT_PATHS["checkpoint"]
    checkpoint = _load_npz(checkpoint_path)
    optimizer = _load_npz(run_dir / EXPECTED_ARTIFACT_PATHS["optimizer_state"])
    capacity = protocol.capacity["routes"][ROUTE]
    expected_scalars = {
        "selected_update": protocol.training["optimizer_updates"],
        "completed_update": protocol.training["optimizer_updates"],
        "training_seed": training_seed,
        "selection_rule": "final_update",
        "protocol_sha256": protocol.sha256,
        "n_electrons": protocol.physics["n_electrons"],
        "two_q": protocol.physics["two_q"],
        "target_m2": 0,
        "width": capacity["hidden_width"],
        "layers": capacity["hidden_layers"],
        "batch_size_per_sector": protocol.training["batch_size_per_sector"],
    }
    for name, expected in expected_scalars.items():
        observed = _scalar(checkpoint, name)
        if observed != expected:
            if name == "training_seed":
                raise ValueError("checkpoint training seed mismatch")
            if name == "protocol_sha256":
                raise ValueError("checkpoint protocol hash mismatch")
            raise ValueError(f"checkpoint {name} mismatch")
    if _scalar(optimizer, "update") != protocol.training["optimizer_updates"]:
        raise ValueError("optimizer final update mismatch")
    if _scalar(optimizer, "training_seed") != training_seed:
        raise ValueError("optimizer training seed mismatch")
    if _scalar(optimizer, "protocol_sha256") != protocol.sha256:
        raise ValueError("optimizer protocol hash mismatch")

    parameters = np.asarray(checkpoint.get("parameters"))
    model = AutoregressiveNQS.initialize(
        n_electrons=protocol.physics["n_electrons"],
        two_q=protocol.physics["two_q"],
        target_m2=0,
        width=capacity["hidden_width"],
        layers=capacity["hidden_layers"],
        seed=training_seed,
        max_trainable_parameters=protocol.capacity["max_trainable_parameters"],
    )
    if parameters.shape != (model.parameter_count,):
        raise ValueError("checkpoint parameter shape mismatch")
    model.set_flat_parameters(parameters)
    for name in ("first_moment", "second_moment"):
        values = np.asarray(optimizer.get(name))
        if values.shape != (model.parameter_count,) or not np.all(np.isfinite(values)):
            raise ValueError(f"optimizer {name} mismatch")

    records = _training_records(run_dir / EXPECTED_ARTIFACT_PATHS["training_log"])
    selected_records = [record for record in records if record.get("selected") is True]
    if len(selected_records) != 1:
        raise ValueError("training log must select exactly one final update")
    selected = selected_records[0]
    if (
        selected.get("update") != protocol.training["optimizer_updates"]
        or selected.get("selection_rule") != "final_update"
        or selected.get("training_seed") != training_seed
    ):
        raise ValueError("training log final selection mismatch")
    resources = _resource_metrics(
        selected,
        checkpoint_bytes=checkpoint_path.stat().st_size,
    )

    integrals = coulomb_integrals(protocol.physics["two_q"])
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    operator = PreparedPairOperator.build(pairs, pair_matrix, protocol.physics["two_q"])
    return OccupationCandidate(
        model=model,
        operator=operator,
        protocol=protocol,
        resources=resources,
        training_seed=training_seed,
        manifest_sha256=sha256_file(manifest_path),
        checkpoint_sha256=sha256_file(checkpoint_path),
    )
