from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
import re


_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_REVISION = re.compile(r"[0-9a-f]{40}\Z", re.ASCII)
_PAYLOAD_FIELDS = {
    "calibration": {
        "config_sha256",
        "cpu_count",
        "exact_trajectory_seconds",
        "first_query_compilation_inclusive_seconds",
        "geometry_seconds",
        "jax_platform",
        "landscape_seconds",
        "open_loop_seconds",
        "parameter_count",
        "peak_rss_kib",
        "queries",
        "restricted_nfev",
        "restricted_optimization_seconds",
        "search_dimension",
        "warm_queries_per_second",
        "warm_query_seconds",
        "x64_enabled",
    },
    "environment": {
        "cpu_count",
        "jax",
        "jax_platform",
        "jaxlib",
        "numpy",
        "platform",
        "python",
        "scipy",
        "uv_lock_sha256",
        "x64_enabled",
    },
    "pilot": {
        "artifact_bytes",
        "config_sha256",
        "evaluations",
        "manifest_sha256",
        "plan_sha256",
        "ready_sha256",
        "total_queries",
        "trial_id",
        "trial_sha256",
    },
    "projection": {
        "cpus_per_trial",
        "formula",
        "pilot_artifact_bytes",
        "pilot_wall_seconds",
        "projected_core_hours",
        "projected_storage_bytes",
        "projected_trial_hours",
        "provisional",
        "trial_count",
    },
    "report_metadata": {"report_sha256"},
    "time": {
        "command_sha256",
        "cpu_percent",
        "exit_status",
        "peak_rss_kib",
        "system_seconds",
        "user_seconds",
        "wall_seconds",
    },
    "validation": {"completed", "errors", "expected", "pending", "valid"},
}
REQUIRED_EVIDENCE_FILES = (
    "calibration.json",
    "environment.json",
    "pilot.json",
    "projection.json",
    "report_metadata.json",
    "time.json",
    "validation.json",
    "index.json",
)


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _read_canonical(path: Path) -> tuple[dict[str, object], bytes]:
    data = path.read_bytes()
    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{path.name} is not valid JSON") from error
    if not isinstance(payload, dict) or data != _canonical_bytes(payload):
        raise ValueError(f"{path.name} is not canonical JSON")
    return payload, data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_hashes(value: object, *, name: str) -> dict[str, str]:
    if (
        not isinstance(value, Mapping)
        or not value
        or any(
            not isinstance(key, str)
            or not key
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
            for key, digest in value.items()
        )
    ):
        raise ValueError(f"{name} must contain canonical SHA256 values")
    return dict(value)


def _exact(value: object, expected: type, name: str) -> object:
    if type(value) is not expected:
        raise ValueError(f"{name} has invalid JSON type")
    return value


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    _exact(value, int, name)
    if value < minimum:
        raise ValueError(f"{name} is outside its valid range")
    return value


def _number(value: object, name: str, *, minimum: float = 0.0) -> float:
    if type(value) not in {int, float} or not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and in range")
    return float(value)


def _validate_payload(evidence_type: str, detail: Mapping[str, object]) -> None:
    hashes = {
        "config_sha256",
        "manifest_sha256",
        "plan_sha256",
        "ready_sha256",
        "report_sha256",
        "trial_sha256",
        "uv_lock_sha256",
        "command_sha256",
    }
    for name in hashes & set(detail):
        _exact(detail[name], str, name)
        if _SHA256.fullmatch(detail[name]) is None:
            raise ValueError(f"{name} is not a SHA256 digest")
    integer_fields = {
        "artifact_bytes",
        "completed",
        "cpu_count",
        "cpus_per_trial",
        "evaluations",
        "expected",
        "exit_status",
        "parameter_count",
        "peak_rss_kib",
        "pending",
        "queries",
        "restricted_nfev",
        "search_dimension",
        "total_queries",
        "trial_count",
    }
    for name in integer_fields & set(detail):
        _integer(detail[name], name)
    number_fields = {
        "cpu_percent",
        "exact_trajectory_seconds",
        "first_query_compilation_inclusive_seconds",
        "geometry_seconds",
        "landscape_seconds",
        "open_loop_seconds",
        "pilot_wall_seconds",
        "projected_core_hours",
        "projected_storage_bytes",
        "projected_trial_hours",
        "restricted_optimization_seconds",
        "system_seconds",
        "user_seconds",
        "wall_seconds",
        "warm_queries_per_second",
        "warm_query_seconds",
    }
    for name in number_fields & set(detail):
        _number(detail[name], name)
    for name in ("x64_enabled", "provisional", "valid"):
        if name in detail:
            _exact(detail[name], bool, name)
    if "errors" in detail and (
        type(detail["errors"]) is not list
        or any(type(item) is not str for item in detail["errors"])
    ):
        raise ValueError("errors must be a JSON string array")
    for name in (
        "formula",
        "jax",
        "jax_platform",
        "jaxlib",
        "numpy",
        "platform",
        "python",
        "scipy",
        "trial_id",
    ):
        if name in detail:
            _exact(detail[name], str, name)
    if evidence_type in {"calibration", "environment"}:
        if detail["x64_enabled"] is not True:
            raise ValueError("evidence must use the x64 runtime")
        if detail["jax_platform"] not in {"cpu", "gpu", "tpu"}:
            raise ValueError("JAX platform is invalid")
    if evidence_type == "projection" and detail["provisional"] is not True:
        raise ValueError("projection must remain provisional")


def validate_evidence_document(payload: object) -> None:
    if not isinstance(payload, Mapping) or set(payload) != {
        "evidence_type",
        "inputs",
        "payload",
        "schema_version",
        "source_revision",
    }:
        raise ValueError("evidence fields are not canonical")
    evidence_type = payload["evidence_type"]
    if evidence_type not in _PAYLOAD_FIELDS:
        raise ValueError("unsupported evidence type")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("unsupported evidence schema")
    revision = payload["source_revision"]
    if not isinstance(revision, str) or _REVISION.fullmatch(revision) is None:
        raise ValueError("evidence source revision is invalid")
    _require_hashes(payload["inputs"], name="evidence inputs")
    detail = payload["payload"]
    if not isinstance(detail, Mapping) or set(detail) != _PAYLOAD_FIELDS[evidence_type]:
        raise ValueError(f"{evidence_type} payload fields are not canonical")
    _validate_payload(str(evidence_type), detail)


def validate_evidence_directory(root: str | Path) -> dict[str, str]:
    directory = Path(root)
    expected_documents = set(REQUIRED_EVIDENCE_FILES) - {"index.json"}
    document_hashes: dict[str, str] = {}
    documents: dict[str, dict[str, object]] = {}
    revisions: set[str] = set()
    for name in sorted(expected_documents):
        payload, data = _read_canonical(directory / name)
        validate_evidence_document(payload)
        document_hashes[name] = _sha256(data)
        revisions.add(str(payload["source_revision"]))
        documents[name] = payload
    index, index_data = _read_canonical(directory / "index.json")
    if (
        set(index) != {"documents", "schema_version", "source_revision"}
        or type(index["schema_version"]) is not int
        or index["schema_version"] != 1
        or index["documents"] != document_hashes
        or len(revisions) != 1
        or index["source_revision"] not in revisions
    ):
        raise ValueError("evidence index is stale or noncanonical")
    calibration = documents["calibration.json"]
    environment = documents["environment.json"]
    pilot = documents["pilot.json"]
    projection = documents["projection.json"]
    timing = documents["time.json"]
    validation = documents["validation.json"]
    for dependent_name, required in {
        "projection.json": {"pilot": "pilot.json", "time": "time.json"},
    }.items():
        inputs = documents[dependent_name]["inputs"]
        for key, source_name in required.items():
            if inputs[key] != document_hashes[source_name]:
                raise ValueError("cross-document evidence hash is stale")
    calibration_payload = calibration["payload"]
    environment_payload = environment["payload"]
    pilot_payload = pilot["payload"]
    projection_payload = projection["payload"]
    timing_payload = timing["payload"]
    validation_payload = validation["payload"]
    if (
        calibration_payload["jax_platform"] != environment_payload["jax_platform"]
        or calibration_payload["x64_enabled"] != environment_payload["x64_enabled"]
        or calibration["inputs"]["uv_lock"] != environment_payload["uv_lock_sha256"]
        or environment["inputs"]["uv_lock"] != environment_payload["uv_lock_sha256"]
        or pilot["inputs"]["uv_lock"] != environment_payload["uv_lock_sha256"]
        or pilot["inputs"]["plan"] != pilot_payload["plan_sha256"]
        or pilot["inputs"]["trial"] != pilot_payload["trial_sha256"]
        or timing["inputs"]["trial"] != pilot_payload["trial_sha256"]
        or validation["inputs"]["trial"] != pilot_payload["trial_sha256"]
        or validation["inputs"]["ready"] != pilot_payload["ready_sha256"]
        or pilot_payload["evaluations"] != pilot_payload["total_queries"]
        or timing_payload["wall_seconds"] != projection_payload["pilot_wall_seconds"]
        or validation_payload["valid"] is not True
        or validation_payload["completed"] != validation_payload["expected"]
        or validation_payload["pending"] != 0
        or validation_payload["errors"] != []
        or pilot_payload["config_sha256"] != calibration_payload["config_sha256"]
    ):
        raise ValueError("evidence documents are semantically inconsistent")
    trial_count = projection_payload["trial_count"]
    trial_hours = projection_payload["pilot_wall_seconds"] * trial_count / 3600
    if (
        projection_payload["projected_trial_hours"] != trial_hours
        or projection_payload["projected_core_hours"]
        != trial_hours * projection_payload["cpus_per_trial"]
        or projection_payload["projected_storage_bytes"]
        != projection_payload["pilot_artifact_bytes"] * trial_count
        or projection_payload["pilot_artifact_bytes"]
        != pilot_payload["artifact_bytes"]
    ):
        raise ValueError("projection arithmetic is inconsistent")
    return {**document_hashes, "index.json": _sha256(index_data)}


def validate_deployment(
    root: str | Path,
    *,
    archive_path: str | Path,
    deployment_metadata_path: str | Path,
    expected_revision: str,
    expected_archive_sha256: str,
    expected_evidence_revision: str,
    expected_sif_sha256: str,
    expected_deployment_metadata_sha256: str,
    expected_pyproject_sha256: str,
    expected_uv_lock_sha256: str,
    expected_cluster_profile: str,
) -> None:
    directory = Path(root)
    archive = Path(archive_path)
    metadata = Path(deployment_metadata_path)
    if metadata.is_symlink() or not metadata.is_file():
        raise ValueError("deployment metadata must be a regular file")
    try:
        metadata.resolve(strict=True).relative_to(directory.resolve(strict=True))
    except ValueError:
        pass
    else:
        raise ValueError("deployment metadata must live outside the source tree")
    if (
        not isinstance(expected_deployment_metadata_sha256, str)
        or _SHA256.fullmatch(expected_deployment_metadata_sha256) is None
    ):
        raise ValueError("expected deployment metadata SHA256 is invalid")
    deployment, metadata_bytes = _read_canonical(metadata)
    if _sha256(metadata_bytes) != expected_deployment_metadata_sha256:
        raise ValueError("deployment metadata bytes are stale")
    if set(deployment) != {
        "archive_name",
        "archive_sha256",
        "cluster_profile",
        "critical_packages",
        "evidence_index_sha256",
        "pyproject_sha256",
        "python_version",
        "report_sha256",
        "revision",
        "schema_version",
        "sif_name",
        "sif_sha256",
        "uv_lock_sha256",
        "uv_version",
    } or deployment.get("schema_version") != 1:
        raise ValueError("deployment metadata is noncanonical")
    if deployment.get("revision") != expected_revision:
        raise ValueError("deployment revision is stale")
    if deployment.get("archive_sha256") != expected_archive_sha256:
        raise ValueError("deployment archive is stale")
    if (
        deployment.get("sif_sha256") != expected_sif_sha256
        or deployment.get("pyproject_sha256") != expected_pyproject_sha256
        or deployment.get("uv_lock_sha256") != expected_uv_lock_sha256
        or deployment.get("cluster_profile") != expected_cluster_profile
    ):
        raise ValueError("deployment runtime binding is stale")
    expected_packages = {
        "jax": "0.11.0",
        "jaxlib": "0.11.0",
        "numpy": "2.5.1",
        "scipy": "1.18.0",
    }
    if (
        deployment.get("python_version") != "3.12.12"
        or deployment.get("uv_version") != "0.9.9"
        or deployment.get("critical_packages") != expected_packages
    ):
        raise ValueError("deployment runtime versions are stale")
    archive_name = deployment.get("archive_name")
    if (
        not isinstance(archive_name, str)
        or not archive_name
        or Path(archive_name).name != archive_name
        or archive.name != archive_name
        or archive_name != f"challenge-113-{expected_revision[:7]}.tar.gz"
    ):
        raise ValueError("deployment archive name is invalid")
    if _sha256(archive.read_bytes()) != expected_archive_sha256:
        raise ValueError("deployment archive bytes are stale")
    if deployment.get("sif_name") != "uv-0.9.9-python3.12-bookworm-slim.sif":
        raise ValueError("deployment SIF identity is stale")
    if (
        _sha256((directory / "pyproject.toml").read_bytes())
        != expected_pyproject_sha256
        or _sha256((directory / "uv.lock").read_bytes())
        != expected_uv_lock_sha256
    ):
        raise ValueError("deployment lock inputs are stale")
    evidence_directory = directory / "evidence" / "task10a"
    hashes = validate_evidence_directory(evidence_directory)
    index, index_data = _read_canonical(evidence_directory / "index.json")
    if index.get("source_revision") != expected_evidence_revision:
        raise ValueError("deployment evidence revision is stale")
    if (
        deployment.get("evidence_index_sha256") != hashes["index.json"]
        or deployment.get("evidence_index_sha256") != _sha256(index_data)
    ):
        raise ValueError("deployment evidence binding is stale")
    report_metadata, _ = _read_canonical(
        directory / "evidence" / "task10a" / "report_metadata.json"
    )
    validate_evidence_document(report_metadata)
    expected_report = report_metadata["payload"]["report_sha256"]
    report_sha256 = _sha256((directory / "REPORT.md").read_bytes())
    if (
        report_sha256 != expected_report
        or deployment.get("report_sha256") != report_sha256
    ):
        raise ValueError("deployment report metadata is stale")
