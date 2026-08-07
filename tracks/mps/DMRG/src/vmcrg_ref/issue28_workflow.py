"""Fail-closed stage manifests and dependency gates for Issue #28."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np

from .artifacts import canonical_json_bytes, sha256_bytes, sha256_file
from .issue28_protocol import Issue28Protocol, TERMINAL_CLASSIFICATIONS


StageName = Literal["B0", "N0", "N1", "N2", "N3", "N4", "N5"]
RunClassification = Literal[
    "CORRECTNESS_FAILURE",
    "PROTOCOL_FAILURE",
    "SCIENTIFIC_NEGATIVE",
    "EASY_GOAL_SUCCESS",
]

STAGE_ORDER: tuple[StageName, ...] = ("B0", "N0", "N1", "N2", "N3", "N4", "N5")
BLOCKING_CLASSIFICATIONS = frozenset(("CORRECTNESS_FAILURE", "PROTOCOL_FAILURE"))


def _validate_stage(stage: str) -> StageName:
    if stage not in STAGE_ORDER:
        raise ValueError(f"unknown Issue #28 stage: {stage}")
    return cast(StageName, stage)


def current_code_sha256() -> str:
    """Hash the package implementation used by every scientific stage."""
    package_root = Path(__file__).resolve().parent
    records = {
        path.name: sha256_file(path)
        for path in sorted(package_root.glob("*.py"))
        if path.is_file()
    }
    return sha256_bytes(canonical_json_bytes(records))


def gauge_spec_sha256(protocol: Issue28Protocol) -> str:
    spec = protocol.gauge
    return sha256_bytes(
        canonical_json_bytes(
            {
                "length": spec.length,
                "configurations": spec.configurations,
                "dtype": spec.dtype,
                "byte_order": spec.byte_order,
                "seed": spec.seed.to_dict(),
            }
        )
    )


def _physical_record(protocol: Issue28Protocol) -> dict[str, Any]:
    physical = protocol.physical
    return {
        "length": physical.length,
        "coupling": physical.coupling,
        "block_size": physical.block_size,
        "boundary": physical.boundary,
        "reference_distribution": physical.reference_distribution,
    }


def _validate_hash(value: object, label: str) -> str:
    text = str(value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"invalid {label}: {text!r}")
    return text


def create_stage_manifest(
    *,
    stage: StageName | str,
    protocol: Issue28Protocol,
    classification: RunClassification | str,
    reason: str,
    output_root: str | Path,
    outputs: Sequence[str | Path],
    correctness_gates: Mapping[str, Any],
    scientific_gates: Mapping[str, Any],
    resources: Mapping[str, Any],
    predecessor_manifest_sha256: Sequence[str] = (),
    bundle_id: str | None = None,
    round_index: int | None = None,
    code_sha256: str | None = None,
    gauge_reference_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a complete manifest after hashing every declared output."""
    checked_stage = _validate_stage(str(stage))
    if classification not in TERMINAL_CLASSIFICATIONS:
        raise ValueError(f"unknown Issue #28 classification: {classification}")
    if not reason:
        raise ValueError("stage manifest reason must be nonempty")
    if round_index is not None and round_index < 0:
        raise ValueError("round index must be nonnegative")

    root = Path(output_root).resolve()
    artifact_hashes: dict[str, str] = {}
    for value in outputs:
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts or relative.name == "manifest.json":
            raise ValueError(f"stage output must be a safe relative path: {relative}")
        candidate = (root / relative).resolve()
        if root not in candidate.parents:
            raise ValueError(f"stage output escapes its root: {relative}")
        if not candidate.is_file():
            raise FileNotFoundError(f"declared stage output is missing: {candidate}")
        key = relative.as_posix()
        if key in artifact_hashes:
            raise ValueError(f"duplicate stage output: {key}")
        artifact_hashes[key] = sha256_file(candidate)

    predecessors = [
        _validate_hash(value, "predecessor manifest hash")
        for value in predecessor_manifest_sha256
    ]
    actual_code_hash = _validate_hash(
        current_code_sha256() if code_sha256 is None else code_sha256,
        "code hash",
    )
    actual_gauge_hash = _validate_hash(
        gauge_spec_sha256(protocol)
        if gauge_reference_sha256 is None
        else gauge_reference_sha256,
        "gauge reference hash",
    )
    return {
        "schema_version": 1,
        "stage": checked_stage,
        "bundle_id": bundle_id,
        "round": round_index,
        "classification": str(classification),
        "reason": reason,
        "protocol_sha256": protocol.protocol_sha256,
        "code_sha256": actual_code_hash,
        "basis_sha256": protocol.operator_basis_sha256,
        "gauge_reference_sha256": actual_gauge_hash,
        "predecessor_manifest_sha256": predecessors,
        "physical": _physical_record(protocol),
        "pure_linear_bias": protocol.pure_linear_bias.tolist(),
        "correctness_gates": dict(correctness_gates),
        "scientific_gates": dict(scientific_gates),
        "resources": dict(resources),
        "outputs": artifact_hashes,
    }


def read_verified_stage_manifest(
    path: str | Path,
    protocol: Issue28Protocol,
    *,
    expected_stage: StageName | str | None = None,
    expected_code_sha256: str | None = None,
    expected_gauge_reference_sha256: str | None = None,
) -> dict[str, Any]:
    """Read a manifest only after provenance and output hashes verify."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"stage manifest is missing: {manifest_path}")
    try:
        value = json.loads(manifest_path.read_text(encoding="ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid stage manifest: {manifest_path}") from error
    if value.get("schema_version") != 1:
        raise ValueError("unsupported stage manifest schema")
    stage = _validate_stage(str(value.get("stage")))
    if expected_stage is not None and stage != _validate_stage(str(expected_stage)):
        raise ValueError(f"stage manifest mismatch: expected {expected_stage}, got {stage}")
    if value.get("protocol_sha256") != protocol.protocol_sha256:
        raise ValueError("stage manifest protocol hash mismatch")
    if value.get("basis_sha256") != protocol.operator_basis_sha256:
        raise ValueError("stage manifest operator basis hash mismatch")
    bias = np.asarray(value.get("pure_linear_bias"), dtype=np.float64)
    if bias.shape != (13,) or not np.array_equal(bias, np.zeros(13, dtype=np.float64)):
        raise ValueError("stage manifest pure-neural 13-operator branch is not exact zero")
    classification = str(value.get("classification"))
    if classification not in TERMINAL_CLASSIFICATIONS:
        raise ValueError(f"invalid stage manifest classification: {classification}")
    if value.get("physical") != _physical_record(protocol):
        raise ValueError("stage manifest physical setup mismatch")

    code_hash = _validate_hash(value.get("code_sha256"), "code hash")
    if expected_code_sha256 is not None and code_hash != expected_code_sha256:
        raise ValueError("stage manifest code hash mismatch")
    gauge_hash = _validate_hash(value.get("gauge_reference_sha256"), "gauge reference hash")
    expected_gauge = expected_gauge_reference_sha256
    if expected_gauge is not None and gauge_hash != expected_gauge:
        raise ValueError("stage manifest gauge reference hash mismatch")
    predecessors = value.get("predecessor_manifest_sha256")
    if not isinstance(predecessors, list):
        raise ValueError("stage manifest predecessor hashes are invalid")
    for predecessor in predecessors:
        _validate_hash(predecessor, "predecessor manifest hash")

    for field in ("correctness_gates", "scientific_gates", "resources", "outputs"):
        if not isinstance(value.get(field), dict):
            raise ValueError(f"stage manifest {field} record is invalid")
    root = manifest_path.parent.resolve()
    for relative_text, expected_hash in value["outputs"].items():
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe stage output path: {relative_text}")
        candidate = (root / relative).resolve()
        if root not in candidate.parents or not candidate.is_file():
            raise FileNotFoundError(f"stage output is missing: {candidate}")
        if sha256_file(candidate) != _validate_hash(expected_hash, "output hash"):
            raise ValueError(f"stage output hash mismatch: {relative_text}")

    return {
        **value,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": sha256_file(manifest_path),
    }


def verify_stage_dependencies(
    stage: StageName | str,
    root: str | Path,
    protocol: Issue28Protocol,
) -> list[dict[str, Any]]:
    """Verify every earlier stage and its immediate hash link."""
    checked_stage = _validate_stage(str(stage))
    required = STAGE_ORDER[: STAGE_ORDER.index(checked_stage)]
    records: list[dict[str, Any]] = []
    previous_hash: str | None = None
    for dependency in required:
        manifest_path = Path(root) / dependency / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError(f"required {dependency} stage manifest is missing")
        record = read_verified_stage_manifest(
            manifest_path,
            protocol,
            expected_stage=dependency,
        )
        if record["classification"] in BLOCKING_CLASSIFICATIONS:
            raise ValueError(
                f"required {dependency} stage has blocking classification "
                f"{record['classification']}"
            )
        if previous_hash is not None and previous_hash not in record["predecessor_manifest_sha256"]:
            raise ValueError(
                f"required {dependency} stage does not reference its predecessor manifest"
            )
        records.append(record)
        previous_hash = str(record["manifest_sha256"])
    return records


def run_stage(
    stage: StageName | str,
    protocol: Issue28Protocol,
    output: str | Path,
    backend: str,
    resume: bool,
) -> dict[str, Any]:
    """Dispatch an implemented stage after verifying its dependencies."""
    checked_stage = _validate_stage(str(stage))
    if backend not in ("local", "slurm"):
        raise ValueError(f"unknown Issue #28 backend: {backend}")
    root = Path(output)
    verify_stage_dependencies(checked_stage, root, protocol)
    stage_root = root / checked_stage
    if stage_root.exists() and any(stage_root.iterdir()) and not resume:
        raise FileExistsError(f"refusing to overwrite nonempty {checked_stage} output")

    if checked_stage == "B0":
        if backend != "local":
            raise ValueError("B0 Slurm dispatch is provided by the unified runner")
        from .baseline_certification import certify_traditional_baseline

        return certify_traditional_baseline(protocol, stage_root, preset="smoke")
    if checked_stage == "N0":
        if backend != "local":
            raise ValueError("N0 exact oracle must run on the local CPU backend")
        from scripts.issue28_exact_oracle import run_exact_oracle

        return run_exact_oracle(Path("config/issue28_n0_v1.json"), stage_root)
    raise NotImplementedError(f"{checked_stage} runner is not registered yet")
