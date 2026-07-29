from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

import numpy as np

from .alias import build_distance_alias
from .artifacts import (
    CONVERSION_VERSION,
    load_verified_trajectory,
    publish_batch_manifest,
    publish_trajectory,
    reconstruct_progress,
)
from .counter_rng import (
    RNG_VERSION,
    STREAM_COUNT,
    StreamIdentity,
    derive_stream_material,
)
from .kernel import periodic_kernel
from .poisson_sweep import run_poisson_numba
from .runtime import runtime_capability
from .trajectory import TrajectoryRequest, request_digest
from .validation import (
    ValidationProtocol,
    _protocol_document,
    _repository_state,
    validate_report_payload,
)
from .validation_shards import validate_run_spec as validate_validation_run_spec


RUN_SPEC_SCHEMA = "challenge-194-pilot-run-spec-v1"
CELL_MANIFEST_SCHEMA = "challenge-194-pilot-cell-manifest-v1"
MERGED_SCHEMA = "challenge-194-pilot-progress-v1"
CORRECTNESS_APPROVAL_REVISION = "fd0aa314f324dc357918926e80f93f4356083fc0"
PILOT_SIGMAS = (0.8, 0.9, 1.0, 1.1)
PILOT_LENGTHS = (2**10, 2**14, 2**18)
PILOT_REPLICAS = tuple(range(8))
PILOT_KAPPAS = (0.0,) + tuple(0.25 * 1.25**j for j in range(15))
PILOT_MASTER_SEED = 19_420_260_729
PILOT_PHASE = "pilot"
RUN_SPEC_NAME = "run_spec.json"
MERGED_NAME = "progress.json"
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")

# This is intentionally narrower than validation's implementation inventory.
# Drift in any module that defines the model, RNG, trajectory, or production
# engine invalidates the correctness evidence; orchestration files may differ.
SCIENTIFIC_ENGINE_MODULES = (
    "src/long_range_percolation/model.py",
    "src/long_range_percolation/kernel.py",
    "src/long_range_percolation/counter_rng.py",
    "src/long_range_percolation/alias.py",
    "src/long_range_percolation/edge_set.py",
    "src/long_range_percolation/observables.py",
    "src/long_range_percolation/production_union_find.py",
    "src/long_range_percolation/trajectory.py",
    "src/long_range_percolation/poisson_reference.py",
    "src/long_range_percolation/poisson_sweep.py",
)


def _canonical_bytes(document: object) -> bytes:
    try:
        return (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("document is not canonical finite JSON") from error


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _document_hash(document: Mapping[str, object], field: str) -> str:
    unsigned = dict(document)
    unsigned.pop(field, None)
    return _sha256(_canonical_bytes(unsigned))


def _solution_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_root() -> Path:
    return _solution_root().parents[4]


def _read_canonical(path: Path, description: str) -> tuple[dict[str, object], bytes]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{description} must be a regular non-symlink file")
    payload = path.read_bytes()
    try:
        document = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{description} is not valid JSON") from error
    if not isinstance(document, dict) or payload != _canonical_bytes(document):
        raise RuntimeError(f"{description} is not canonical JSON")
    return document, payload


def _publish_once(path: Path, document: Mapping[str, object]) -> None:
    payload = _canonical_bytes(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            existing, existing_payload = _read_canonical(path, "immutable output")
            if existing_payload != payload or existing != dict(document):
                raise RuntimeError("immutable output already exists with other bytes")
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _file_hash(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"required regular file is missing: {path}")
    return _sha256(path.read_bytes())


def _lock_hash() -> str:
    return _file_hash(_solution_root() / "uv.lock")


def _scientific_hashes() -> dict[str, str]:
    root = _solution_root()
    return {relative: _file_hash(root / relative) for relative in SCIENTIFIC_ENGINE_MODULES}


def _aggregate_hash(values: Mapping[str, str]) -> str:
    return _sha256(_canonical_bytes(dict(values)))


def _current_source(*, require_clean: bool) -> dict[str, object]:
    source = _repository_state()
    revision = source.get("source_revision")
    if not isinstance(revision, str) or _HEX40.fullmatch(revision) is None:
        raise RuntimeError("current orchestration revision is unavailable")
    if require_clean and (
        source.get("clean_tree") is not True
        or source.get("provenance_error") is not None
    ):
        raise RuntimeError("current repository must be clean")
    return source


def _runtime_document() -> tuple[dict[str, object], str]:
    document = runtime_capability()
    return document, _sha256(_canonical_bytes(document))


def _analysis_plan_hash() -> str:
    path = _solution_root() / "PILOT_PLAN.md"
    return _file_hash(path)


def _validation_spec_path(report: Path) -> Path:
    candidates = (
        report.parent.parent / RUN_SPEC_NAME,
        report.parent / RUN_SPEC_NAME,
        report.with_name("validation_run_spec.json"),
    )
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    raise RuntimeError("approved correctness report lacks its immutable run spec")


def _verified_correctness(report_path: Path) -> dict[str, object]:
    report, report_payload = _read_canonical(report_path, "correctness report")
    protocol = ValidationProtocol.production_v1()
    validate_report_payload(report, protocol)
    if report.get("passed") is not True:
        raise RuntimeError("correctness report did not pass")
    source = report.get("source")
    validation_source_revision = (
        source.get("source_revision") if isinstance(source, Mapping) else None
    )
    if (
        not isinstance(source, Mapping)
        or not isinstance(validation_source_revision, str)
        or _HEX40.fullmatch(validation_source_revision) is None
        or source.get("clean_tree") is not True
        or source.get("provenance_error") is not None
    ):
        raise RuntimeError("correctness report source evidence is not approved")

    validation_spec_path = _validation_spec_path(report_path)
    validation_spec, validation_spec_payload = _read_canonical(
        validation_spec_path, "correctness run spec"
    )
    validate_validation_run_spec(validation_spec, enforce_production=True)
    cells = validation_spec.get("cells")
    if not isinstance(cells, list) or len(cells) != 120:
        raise RuntimeError("correctness run spec must contain exactly 120 cells")
    if (
        validation_spec.get("source_revision") != validation_source_revision
        or validation_spec.get("uv_lock_sha256") != _lock_hash()
        or validation_spec.get("runtime_capability") != report.get("runtime_capability")
    ):
        raise RuntimeError("correctness source/runtime/lock evidence is inconsistent")

    expected_identities = Counter(
        (str(check["family"]), str(check["check_case_id"]))
        for check in validation_spec["global_expected_checks"]
    )
    for cell in cells:
        expected_identities.update(
            (str(check["family"]), str(check["check_case_id"]))
            for check in cell["expected_checks"]
        )
    actual_identities = Counter(
        (str(check.get("family")), str(check.get("case_id")))
        for check in report["checks"]
    )
    if actual_identities != expected_identities:
        raise RuntimeError("correctness report check registry is incomplete or reordered")

    recorded_modules = validation_spec.get("implementation_modules")
    if not isinstance(recorded_modules, Mapping):
        raise RuntimeError("correctness run spec lacks implementation hashes")
    current = _scientific_hashes()
    approved = {path: recorded_modules.get(path) for path in SCIENTIFIC_ENGINE_MODULES}
    if approved != current:
        raise RuntimeError("scientific engine module drift from correctness report")
    return {
        "correctness_report_sha256": _sha256(report_payload),
        "correctness_run_spec_sha256": _sha256(validation_spec_payload),
        "validation_source_revision": validation_source_revision,
        "validated_engine_modules": current,
        "validated_engine_sha256": _aggregate_hash(current),
        "validation_runtime_capability_sha256": validation_spec[
            "runtime_capability_sha256"
        ],
    }


@dataclass(frozen=True)
class PilotCell:
    cell_index: int
    cell_id: str
    sigma: float
    length: int
    replica: int
    sigma_grid_id: str
    kappas: tuple[float, ...]
    kernel_sha256: str
    request_sha256: str
    cell_path: str
    run_path: str
    manifest_path: str
    rng_material_sha256: tuple[str, ...]

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> PilotCell:
        try:
            return cls(
                cell_index=int(document["cell_index"]),
                cell_id=str(document["cell_id"]),
                sigma=float.fromhex(str(document["sigma"])),
                length=int(document["length"]),
                replica=int(document["replica"]),
                sigma_grid_id=str(document["sigma_grid_id"]),
                kappas=tuple(float.fromhex(str(value)) for value in document["kappas"]),
                kernel_sha256=str(document["kernel_sha256"]),
                request_sha256=str(document["request_sha256"]),
                cell_path=str(document["cell_path"]),
                run_path=str(document["run_path"]),
                manifest_path=str(document["manifest_path"]),
                rng_material_sha256=tuple(
                    str(value) for value in document["rng_material_sha256"]
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("pilot cell is malformed") from error

    def request(self) -> TrajectoryRequest:
        return TrajectoryRequest(
            length=self.length,
            sigma=self.sigma,
            sigma_grid_id=self.sigma_grid_id,
            kappas=np.asarray(self.kappas, dtype=np.float64),
            master_seed=PILOT_MASTER_SEED,
            phase=PILOT_PHASE,
            replica=self.replica,
            kernel_sha256=self.kernel_sha256,
        )


def _stream_hashes(length: int, sigma_grid_id: str, replica: int) -> tuple[str, ...]:
    return tuple(
        derive_stream_material(
            StreamIdentity(
                master_seed=PILOT_MASTER_SEED,
                phase=PILOT_PHASE,
                length=length,
                sigma_grid_id=sigma_grid_id,
                replica=replica,
                stream_id=stream,
            )
        ).material_sha256
        for stream in range(STREAM_COUNT)
    )


def _build_document(
    *,
    lengths: Sequence[int],
    sigmas: Sequence[float],
    replicas: Sequence[int],
    kappas: Sequence[float],
    source: Mapping[str, object],
    runtime: Mapping[str, object],
    runtime_sha256: str,
    correctness: Mapping[str, object],
    waiver_timestamp: str,
    analysis_plan_sha256: str,
) -> dict[str, object]:
    protocol = {
        "lengths": list(lengths),
        "sigmas": [float(value).hex() for value in sigmas],
        "replicas": list(replicas),
        "kappas": [float(value).hex() for value in kappas],
        "master_seed": PILOT_MASTER_SEED,
        "phase": PILOT_PHASE,
        "loop_order": ["sigma", "length", "replica"],
        "purpose": "exploratory-window-selection-only",
    }
    protocol["sha256"] = _sha256(_canonical_bytes(protocol))
    cells: list[dict[str, object]] = []
    all_assignments: list[dict[str, object]] = []
    for sigma in sigmas:
        sigma_value = float(sigma)
        grid_id = f"pilot-p0-v1|sigma-f64={sigma_value.hex()}"
        for length in lengths:
            kernel = periodic_kernel(int(length), sigma_value)
            kernel_sha256 = _sha256(
                kernel.astype("<f8", copy=False).tobytes(order="C")
            )
            for replica in replicas:
                request = TrajectoryRequest(
                    length=int(length),
                    sigma=sigma_value,
                    sigma_grid_id=grid_id,
                    kappas=np.asarray(kappas, dtype=np.float64),
                    master_seed=PILOT_MASTER_SEED,
                    phase=PILOT_PHASE,
                    replica=int(replica),
                    kernel_sha256=kernel_sha256,
                )
                request_sha256 = request_digest(request)
                stream_hashes = _stream_hashes(int(length), grid_id, int(replica))
                index = len(cells)
                identity = {
                    "cell_index": index,
                    "sigma": sigma_value.hex(),
                    "length": int(length),
                    "replica": int(replica),
                    "request_sha256": request_sha256,
                }
                cell_id = f"{index:03d}-{_sha256(_canonical_bytes(identity))[:16]}"
                cell_path = f"cells/{cell_id}"
                cells.append(
                    {
                        **identity,
                        "cell_id": cell_id,
                        "sigma_grid_id": grid_id,
                        "kappas": [float(value).hex() for value in kappas],
                        "kernel_sha256": kernel_sha256,
                        "rng_material_sha256": list(stream_hashes),
                        "cell_path": cell_path,
                        "run_path": f"{cell_path}/run",
                        "manifest_path": f"{cell_path}/manifest.json",
                    }
                )
                all_assignments.append(
                    {
                        "cell_index": index,
                        "request_sha256": request_sha256,
                        "streams": list(stream_hashes),
                    }
                )
    rng_hash = _sha256(_canonical_bytes({"assignments": all_assignments}))
    engine_modules = dict(correctness["validated_engine_modules"])
    document: dict[str, object] = {
        "schema_version": RUN_SPEC_SCHEMA,
        "artifact_root": ".",
        "protocol": protocol,
        "cells": cells,
        "cell_count": len(cells),
        "correctness_report_sha256": correctness["correctness_report_sha256"],
        "correctness_run_spec_sha256": correctness[
            "correctness_run_spec_sha256"
        ],
        "correctness_approval_revision": CORRECTNESS_APPROVAL_REVISION,
        "validation_source_revision": correctness["validation_source_revision"],
        "validated_engine_modules": engine_modules,
        "validated_engine_sha256": correctness["validated_engine_sha256"],
        "validation_runtime_capability_sha256": correctness[
            "validation_runtime_capability_sha256"
        ],
        "orchestration_revision": source["source_revision"],
        "clean_tree": True,
        "uv_lock_sha256": _lock_hash(),
        "runtime_capability": dict(runtime),
        "runtime_capability_sha256": runtime_sha256,
        "analysis_plan_sha256": analysis_plan_sha256,
        "rng_assignment_sha256": rng_hash,
        "capability_waiver": {
            "reason": "user-waived-after-correctness-gate",
            "benchmark_status": "cancelled-without-capability-report",
            "utc_timestamp": waiver_timestamp,
        },
        "merged_progress_path": MERGED_NAME,
    }
    document["run_spec_sha256"] = _document_hash(document, "run_spec_sha256")
    _validate_pilot_spec(document, enforce_production=len(cells) == 96)
    return document


def build_pilot_run_spec(
    output_root: Path, validation_report: Path
) -> dict[str, object]:
    if not isinstance(output_root, Path) or not output_root.is_absolute():
        raise RuntimeError("output_root must be an absolute path")
    source = _current_source(require_clean=True)
    correctness = _verified_correctness(validation_report)
    runtime, runtime_hash = _runtime_document()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    document = _build_document(
        lengths=PILOT_LENGTHS,
        sigmas=PILOT_SIGMAS,
        replicas=PILOT_REPLICAS,
        kappas=PILOT_KAPPAS,
        source=source,
        runtime=runtime,
        runtime_sha256=runtime_hash,
        correctness=correctness,
        waiver_timestamp=timestamp,
        analysis_plan_sha256=_analysis_plan_hash(),
    )
    _publish_once(output_root / RUN_SPEC_NAME, document)
    return document


def _relative_path(root: Path, value: object, prefix: str) -> Path:
    if not isinstance(value, str):
        raise RuntimeError("artifact path must be a string")
    relative = Path(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
        or relative.parts[0] != prefix
    ):
        raise RuntimeError("artifact path escapes its portable namespace")
    candidate = root / relative
    if candidate.resolve(strict=False) != candidate:
        raise RuntimeError("artifact path contains a symlink or alias")
    return candidate


def _validate_pilot_spec(
    document: Mapping[str, object], *, enforce_production: bool
) -> None:
    expected_fields = {
        "schema_version",
        "artifact_root",
        "protocol",
        "cells",
        "cell_count",
        "correctness_report_sha256",
        "correctness_run_spec_sha256",
        "correctness_approval_revision",
        "validation_source_revision",
        "validated_engine_modules",
        "validated_engine_sha256",
        "validation_runtime_capability_sha256",
        "orchestration_revision",
        "clean_tree",
        "uv_lock_sha256",
        "runtime_capability",
        "runtime_capability_sha256",
        "analysis_plan_sha256",
        "rng_assignment_sha256",
        "capability_waiver",
        "merged_progress_path",
        "run_spec_sha256",
    }
    if set(document) != expected_fields or document.get("schema_version") != RUN_SPEC_SCHEMA:
        raise RuntimeError("pilot run spec fields or schema are invalid")
    if document.get("run_spec_sha256") != _document_hash(document, "run_spec_sha256"):
        raise RuntimeError("pilot run spec hash mismatch")
    if document.get("artifact_root") != "." or document.get("merged_progress_path") != MERGED_NAME:
        raise RuntimeError("pilot portable paths are not frozen")
    for field in (
        "correctness_report_sha256",
        "correctness_run_spec_sha256",
        "validated_engine_sha256",
        "validation_runtime_capability_sha256",
        "uv_lock_sha256",
        "runtime_capability_sha256",
        "analysis_plan_sha256",
        "rng_assignment_sha256",
    ):
        if not isinstance(document.get(field), str) or _HEX64.fullmatch(
            str(document[field])
        ) is None:
            raise RuntimeError(f"pilot {field} is malformed")
    if (
        document.get("clean_tree") is not True
        or not isinstance(document.get("orchestration_revision"), str)
        or _HEX40.fullmatch(str(document["orchestration_revision"])) is None
        or document.get("correctness_approval_revision")
        != CORRECTNESS_APPROVAL_REVISION
        or not isinstance(document.get("validation_source_revision"), str)
        or _HEX40.fullmatch(str(document["validation_source_revision"])) is None
    ):
        raise RuntimeError("pilot orchestration source evidence is invalid")
    runtime = document.get("runtime_capability")
    if not isinstance(runtime, Mapping) or _sha256(_canonical_bytes(runtime)) != document.get(
        "runtime_capability_sha256"
    ):
        raise RuntimeError("pilot runtime capability hash mismatch")
    modules = document.get("validated_engine_modules")
    if (
        not isinstance(modules, Mapping)
        or set(modules) != set(SCIENTIFIC_ENGINE_MODULES)
        or _aggregate_hash({str(k): str(v) for k, v in modules.items()})
        != document.get("validated_engine_sha256")
    ):
        raise RuntimeError("pilot scientific engine binding is invalid")
    waiver = document.get("capability_waiver")
    if (
        not isinstance(waiver, Mapping)
        or set(waiver) != {"reason", "benchmark_status", "utc_timestamp"}
        or waiver.get("reason") != "user-waived-after-correctness-gate"
        or waiver.get("benchmark_status")
        != "cancelled-without-capability-report"
        or not isinstance(waiver.get("utc_timestamp"), str)
        or not str(waiver["utc_timestamp"]).endswith("Z")
    ):
        raise RuntimeError("pilot capability waiver is invalid")

    protocol = document.get("protocol")
    if not isinstance(protocol, Mapping):
        raise RuntimeError("pilot protocol is malformed")
    unsigned_protocol = dict(protocol)
    protocol_hash = unsigned_protocol.pop("sha256", None)
    if protocol_hash != _sha256(_canonical_bytes(unsigned_protocol)):
        raise RuntimeError("pilot protocol hash mismatch")
    if enforce_production and unsigned_protocol != {
        "lengths": list(PILOT_LENGTHS),
        "sigmas": [value.hex() for value in PILOT_SIGMAS],
        "replicas": list(PILOT_REPLICAS),
        "kappas": [value.hex() for value in PILOT_KAPPAS],
        "master_seed": PILOT_MASTER_SEED,
        "phase": PILOT_PHASE,
        "loop_order": ["sigma", "length", "replica"],
        "purpose": "exploratory-window-selection-only",
    }:
        raise RuntimeError("pilot P0 protocol is not frozen")
    cells = document.get("cells")
    if (
        not isinstance(cells, list)
        or document.get("cell_count") != len(cells)
        or (enforce_production and len(cells) != 96)
    ):
        raise RuntimeError("pilot cell count is invalid")
    seen_ids: set[str] = set()
    seen_requests: set[str] = set()
    assignments: list[dict[str, object]] = []
    for index, raw in enumerate(cells):
        if not isinstance(raw, Mapping):
            raise RuntimeError("pilot cell is malformed")
        cell = PilotCell.from_document(raw)
        expected_keys = {
            "cell_index",
            "cell_id",
            "sigma",
            "length",
            "replica",
            "sigma_grid_id",
            "kappas",
            "kernel_sha256",
            "request_sha256",
            "rng_material_sha256",
            "cell_path",
            "run_path",
            "manifest_path",
        }
        if set(raw) != expected_keys or cell.cell_index != index:
            raise RuntimeError("pilot cell registry is noncanonical")
        if (
            cell.sigma_grid_id != f"pilot-p0-v1|sigma-f64={cell.sigma.hex()}"
            or request_digest(cell.request()) != cell.request_sha256
            or _HEX64.fullmatch(cell.kernel_sha256) is None
            or len(cell.rng_material_sha256) != STREAM_COUNT
            or tuple(cell.rng_material_sha256)
            != _stream_hashes(cell.length, cell.sigma_grid_id, cell.replica)
        ):
            raise RuntimeError("pilot cell request or RNG identity is stale")
        identity = {
            "cell_index": index,
            "sigma": cell.sigma.hex(),
            "length": cell.length,
            "replica": cell.replica,
            "request_sha256": cell.request_sha256,
        }
        expected_id = f"{index:03d}-{_sha256(_canonical_bytes(identity))[:16]}"
        expected_cell_path = f"cells/{expected_id}"
        if (
            cell.cell_id != expected_id
            or cell.cell_path != expected_cell_path
            or cell.run_path != f"{expected_cell_path}/run"
            or cell.manifest_path != f"{expected_cell_path}/manifest.json"
        ):
            raise RuntimeError("pilot cell paths are noncanonical")
        if cell.cell_id in seen_ids or cell.request_sha256 in seen_requests:
            raise RuntimeError("pilot cells contain duplicate identities")
        seen_ids.add(cell.cell_id)
        seen_requests.add(cell.request_sha256)
        assignments.append(
            {
                "cell_index": index,
                "request_sha256": cell.request_sha256,
                "streams": list(cell.rng_material_sha256),
            }
        )
    if _sha256(_canonical_bytes({"assignments": assignments})) != document.get(
        "rng_assignment_sha256"
    ):
        raise RuntimeError("pilot complete RNG assignment hash mismatch")


def load_pilot_run_spec(
    path: Path, verify_current_environment: bool
) -> dict[str, object]:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or path.name != RUN_SPEC_NAME
    ):
        raise RuntimeError("pilot run spec path must be absolute and canonical")
    document, _ = _read_canonical(path, "pilot run spec")
    _validate_pilot_spec(document, enforce_production=document.get("cell_count") == 96)
    if _lock_hash() != document["uv_lock_sha256"]:
        raise RuntimeError("uv.lock drift from pilot run spec")
    modules = _scientific_hashes()
    if modules != document["validated_engine_modules"] or _aggregate_hash(modules) != document[
        "validated_engine_sha256"
    ]:
        raise RuntimeError("scientific engine module drift from pilot run spec")
    if _analysis_plan_hash() != document["analysis_plan_sha256"]:
        raise RuntimeError("analysis plan drift from pilot run spec")
    if verify_current_environment:
        source = _current_source(require_clean=True)
        if source["source_revision"] != document["orchestration_revision"]:
            raise RuntimeError("orchestration revision drift from pilot run spec")
        runtime, runtime_hash = _runtime_document()
        if (
            runtime != document["runtime_capability"]
            or runtime_hash != document["runtime_capability_sha256"]
        ):
            raise RuntimeError("compute-node runtime capability drift")
    return document


def _expected(spec: Mapping[str, object], cell: PilotCell) -> dict[str, str]:
    return {
        "request_sha256": cell.request_sha256,
        "kernel_sha256": cell.kernel_sha256,
        "source_revision": str(spec["orchestration_revision"]),
        "uv_lock_sha256": str(spec["uv_lock_sha256"]),
        "runtime_capability_sha256": str(spec["runtime_capability_sha256"]),
        "analysis_plan_sha256": str(spec["analysis_plan_sha256"]),
        "rng_sha256": str(spec["rng_assignment_sha256"]),
        "conversion_version": CONVERSION_VERSION,
        "rng_version": RNG_VERSION,
    }


def _provenance(spec: Mapping[str, object]) -> dict[str, object]:
    return {
        "source_revision": spec["orchestration_revision"],
        "clean_tree": True,
        "uv_lock_sha256": spec["uv_lock_sha256"],
        "runtime_capability_sha256": spec["runtime_capability_sha256"],
        "analysis_plan_sha256": spec["analysis_plan_sha256"],
        "rng_sha256": spec["rng_assignment_sha256"],
        "conversion_version": CONVERSION_VERSION,
        "rng_version": RNG_VERSION,
    }


def _reject_markers(cell_root: Path) -> None:
    if not cell_root.exists():
        return
    for path in cell_root.rglob("*"):
        if path.name.endswith((".partial", ".intent")):
            raise RuntimeError(f"surviving publication marker: {path.name}")


def _initialize_run(
    run: Path, spec: Mapping[str, object], cell: PilotCell, kernel: np.ndarray
) -> None:
    if run.exists():
        return
    run.mkdir()
    kernel_dir = run / "kernel"
    kernel_dir.mkdir()
    (kernel_dir / "kernel-f64le.bin").write_bytes(
        kernel.astype("<f8", copy=False).tobytes(order="C")
    )
    documents = {
        "request.json": {
            "schema_version": "challenge-194-pilot-request-v1",
            "request_sha256": cell.request_sha256,
            "kernel_sha256": cell.kernel_sha256,
            "length": cell.length,
            "sigma": cell.sigma.hex(),
            "sigma_grid_id": cell.sigma_grid_id,
            "kappas": [value.hex() for value in cell.kappas],
            "master_seed": PILOT_MASTER_SEED,
            "phase": PILOT_PHASE,
            "replica": cell.replica,
        },
        "environment.json": {
            "schema_version": "challenge-194-pilot-environment-v1",
            "source_revision": spec["orchestration_revision"],
            "clean_tree": True,
            "uv_lock_sha256": spec["uv_lock_sha256"],
            "runtime_capability_sha256": spec["runtime_capability_sha256"],
            "conversion_version": CONVERSION_VERSION,
            "rng_version": RNG_VERSION,
        },
        "seed-manifest.json": {
            "schema_version": "challenge-194-pilot-seed-manifest-v1",
            "rng_sha256": spec["rng_assignment_sha256"],
            "cell_stream_material_sha256": list(cell.rng_material_sha256),
        },
        "capability.json": {
            "schema_version": "challenge-194-pilot-capability-v1",
            "runtime_capability_sha256": spec["runtime_capability_sha256"],
            "runtime_capability": spec["runtime_capability"],
            "capability_waiver": spec["capability_waiver"],
        },
        "manifest.json": {
            "schema_version": "challenge-194-pilot-inner-manifest-v1",
            "source_revision": spec["orchestration_revision"],
            "analysis_plan_sha256": spec["analysis_plan_sha256"],
            "run_spec_sha256": spec["run_spec_sha256"],
            "cell_id": cell.cell_id,
        },
    }
    for name, document in documents.items():
        _publish_once(run / name, document)


def _trajectory_path(run: Path, cell: PilotCell) -> Path:
    return run / "trajectories" / f"trajectory-{cell.request_sha256}.h5"


def _cell_manifest_document(
    spec: Mapping[str, object], cell: PilotCell, run: Path
) -> dict[str, object]:
    progress, progress_payload = _read_canonical(run / "progress.json", "cell progress")
    trajectory = _trajectory_path(run, cell)
    sidecar, _ = _read_canonical(
        trajectory.with_suffix(".sha256.json"), "trajectory digest"
    )
    if progress.get("trajectory_count") != 1 or progress.get("batch_count") != 1:
        raise RuntimeError("cell progress does not contain one complete trajectory")
    return {
        "schema_version": CELL_MANIFEST_SCHEMA,
        "status": "success",
        "run_spec_sha256": spec["run_spec_sha256"],
        "cell_index": cell.cell_index,
        "cell_id": cell.cell_id,
        "request_sha256": cell.request_sha256,
        "kernel_sha256": cell.kernel_sha256,
        "trajectory_path": (
            f"{cell.run_path}/trajectories/trajectory-{cell.request_sha256}.h5"
        ),
        "trajectory_sha256": sidecar["trajectory_sha256"],
        "progress_sha256": _sha256(progress_payload),
    }


def _verify_success_cell(
    root: Path, spec: Mapping[str, object], cell: PilotCell
) -> dict[str, object]:
    cell_root = _relative_path(root, cell.cell_path, "cells")
    _reject_markers(cell_root)
    run = _relative_path(root, cell.run_path, "cells")
    marker = _relative_path(root, cell.manifest_path, "cells")
    if not marker.is_file():
        raise RuntimeError("cell success manifest is missing")
    expected = _expected(spec, cell)
    progress = reconstruct_progress(run, expected)
    trajectory = _trajectory_path(run, cell)
    load_verified_trajectory(trajectory, expected)
    manifest, _ = _read_canonical(marker, "cell success manifest")
    required = _cell_manifest_document(spec, cell, run)
    if manifest != required:
        raise RuntimeError("cell success manifest is stale or corrupt")
    if progress.get("trajectory_count") != 1:
        raise RuntimeError("cell has duplicate trajectories")
    return manifest


def _run_cell(
    run_spec_path: Path,
    cell_index: int,
    *,
    verify_current_environment: bool,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    spec = load_pilot_run_spec(run_spec_path, verify_current_environment)
    cells = spec["cells"]
    if (
        isinstance(cell_index, bool)
        or not isinstance(cell_index, int)
        or not 0 <= cell_index < len(cells)
    ):
        raise ValueError("cell_index is outside the pilot run spec")
    cell = PilotCell.from_document(cells[cell_index])
    root = run_spec_path.parent
    cell_root = _relative_path(root, cell.cell_path, "cells")
    cell_root.mkdir(parents=True, exist_ok=True)
    _reject_markers(cell_root)
    descriptor = os.open(
        cell_root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        marker = _relative_path(root, cell.manifest_path, "cells")
        if marker.exists():
            manifest = _verify_success_cell(root, spec, cell)
            return {
                "cell_index": cell_index,
                "cell_id": cell.cell_id,
                "manifest_path": cell.manifest_path,
                "trajectory_sha256": manifest["trajectory_sha256"],
            }
        _reject_markers(cell_root)
        kernel = periodic_kernel(cell.length, cell.sigma)
        actual_kernel_hash = _sha256(
            kernel.astype("<f8", copy=False).tobytes(order="C")
        )
        if actual_kernel_hash != cell.kernel_sha256:
            raise RuntimeError("reconstructed kernel hash mismatch")
        run = _relative_path(root, cell.run_path, "cells")
        _initialize_run(run, spec, cell, kernel)
        expected = _expected(spec, cell)
        trajectory = _trajectory_path(run, cell)
        if trajectory.exists():
            load_verified_trajectory(trajectory, expected)
        else:
            trajectories = run / "trajectories"
            if trajectories.exists() and any(trajectories.iterdir()):
                raise RuntimeError("trajectory namespace is incomplete or noncanonical")
            request = cell.request()
            alias = build_distance_alias(
                cell.length, cell.sigma, kernel, cell.kernel_sha256
            )
            result = run_poisson_numba(request, kernel, alias)
            trajectory = publish_trajectory(
                run, request, result, _provenance(spec)
            )
        if crash_hook is not None:
            crash_hook("after-trajectory")
        batch = run / "batches" / f"batch-cell-{cell.cell_index:03d}.json"
        if not batch.exists():
            if (run / "batches").exists() and any((run / "batches").iterdir()):
                raise RuntimeError("batch namespace is noncanonical")
            publish_batch_manifest(
                run, f"cell-{cell.cell_index:03d}", [trajectory]
            )
        reconstruct_progress(run, expected)
        if crash_hook is not None:
            crash_hook("after-progress")
        manifest = _cell_manifest_document(spec, cell, run)
        _publish_once(marker, manifest)
        verified = _verify_success_cell(root, spec, cell)
        return {
            "cell_index": cell_index,
            "cell_id": cell.cell_id,
            "manifest_path": cell.manifest_path,
            "trajectory_sha256": verified["trajectory_sha256"],
        }
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def run_pilot_cell(
    run_spec_path: Path, cell_index: int
) -> dict[str, object]:
    return _run_cell(
        run_spec_path, cell_index, verify_current_environment=True
    )


def pending_pilot_cells(
    run_spec_path: Path, *, verify_current_environment: bool = True
) -> list[int]:
    spec = load_pilot_run_spec(run_spec_path, verify_current_environment)
    root = run_spec_path.parent
    pending: list[int] = []
    for raw in spec["cells"]:
        cell = PilotCell.from_document(raw)
        marker = _relative_path(root, cell.manifest_path, "cells")
        if marker.exists():
            _verify_success_cell(root, spec, cell)
        else:
            cell_root = _relative_path(root, cell.cell_path, "cells")
            _reject_markers(cell_root)
            pending.append(cell.cell_index)
    return pending


def _merged_document(
    run_spec_path: Path,
    *,
    verify_current_environment: bool,
) -> dict[str, object]:
    spec = load_pilot_run_spec(run_spec_path, verify_current_environment)
    root = run_spec_path.parent
    cells_root = root / "cells"
    expected_names = {PilotCell.from_document(raw).cell_id for raw in spec["cells"]}
    actual_names = (
        {path.name for path in cells_root.iterdir()} if cells_root.is_dir() else set()
    )
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing or extra:
        raise RuntimeError(f"pilot cell set mismatch; missing={missing}, extra={extra}")
    records = []
    requests: set[str] = set()
    for raw in spec["cells"]:
        cell = PilotCell.from_document(raw)
        manifest = _verify_success_cell(root, spec, cell)
        if cell.request_sha256 in requests:
            raise RuntimeError("merged pilot contains duplicate request identity")
        requests.add(cell.request_sha256)
        records.append(
            {
                "cell_index": cell.cell_index,
                "cell_id": cell.cell_id,
                "manifest_path": cell.manifest_path,
                "request_sha256": cell.request_sha256,
                "trajectory_sha256": manifest["trajectory_sha256"],
            }
        )
    return {
        "schema_version": MERGED_SCHEMA,
        "run_spec_sha256": spec["run_spec_sha256"],
        "cell_count": len(records),
        "trajectory_count": len(records),
        "cells": records,
        "purpose": "exploratory-window-selection-only",
        "physics_claims_authorized": False,
    }


def merge_pilot_progress(
    run_spec_path: Path, output: Path | None = None
) -> dict[str, object]:
    document = _merged_document(
        run_spec_path, verify_current_environment=True
    )
    fixed = run_spec_path.parent / MERGED_NAME
    if output is not None and output != fixed:
        raise RuntimeError("merge output must be the portable run-spec progress path")
    _publish_once(fixed, document)
    return document


def verify_pilot_download(run_spec_path: Path) -> dict[str, object]:
    document = _merged_document(
        run_spec_path, verify_current_environment=False
    )
    progress = run_spec_path.parent / MERGED_NAME
    if progress.exists():
        existing, _ = _read_canonical(progress, "merged pilot progress")
        if existing != document:
            raise RuntimeError("merged pilot progress is stale or corrupt")
    return document


def _test_source() -> dict[str, object]:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "source_revision": completed.stdout.strip(),
        "clean_tree": True,
        "provenance_error": None,
    }


def _build_test_pilot_run_spec(
    output_root: Path,
    *,
    lengths: Sequence[int] = PILOT_LENGTHS,
    sigmas: Sequence[float] = PILOT_SIGMAS,
    replicas: Sequence[int] = PILOT_REPLICAS,
    kappas: Sequence[float] = PILOT_KAPPAS,
) -> dict[str, object]:
    runtime, runtime_hash = _runtime_document()
    modules = _scientific_hashes()
    correctness = {
        "correctness_report_sha256": "1" * 64,
        "correctness_run_spec_sha256": "2" * 64,
        "validation_source_revision": "b" * 40,
        "validated_engine_modules": modules,
        "validated_engine_sha256": _aggregate_hash(modules),
        "validation_runtime_capability_sha256": "3" * 64,
    }
    plan = _solution_root() / "PILOT_PLAN.md"
    analysis_hash = (
        _file_hash(plan)
        if plan.exists()
        else _sha256(_canonical_bytes({"protocol": "P0/P1-test"}))
    )
    return _build_document(
        lengths=lengths,
        sigmas=sigmas,
        replicas=replicas,
        kappas=kappas,
        source=_test_source(),
        runtime=runtime,
        runtime_sha256=runtime_hash,
        correctness=correctness,
        waiver_timestamp="2026-07-29T00:00:00Z",
        analysis_plan_sha256=analysis_hash,
    )


def _write_test_pilot_run_spec(
    output_root: Path, **kwargs: object
) -> Path:
    document = _build_test_pilot_run_spec(output_root, **kwargs)
    path = output_root / RUN_SPEC_NAME
    _publish_once(path, document)
    return path


def _run_test_pilot_cell(
    run_spec_path: Path,
    cell_index: int,
    *,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, object]:
    return _run_cell(
        run_spec_path,
        cell_index,
        verify_current_environment=False,
        crash_hook=crash_hook,
    )


def _merge_test_pilot_progress(
    run_spec_path: Path, output: Path | None = None
) -> dict[str, object]:
    document = _merged_document(
        run_spec_path, verify_current_environment=False
    )
    fixed = run_spec_path.parent / MERGED_NAME
    if output is not None and output != fixed:
        raise RuntimeError("merge output must be the portable run-spec progress path")
    _publish_once(fixed, document)
    return document
