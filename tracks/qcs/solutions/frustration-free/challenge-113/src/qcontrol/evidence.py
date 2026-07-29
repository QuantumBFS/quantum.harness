from __future__ import annotations

import hashlib
import json
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
    if payload["schema_version"] != 1:
        raise ValueError("unsupported evidence schema")
    revision = payload["source_revision"]
    if not isinstance(revision, str) or _REVISION.fullmatch(revision) is None:
        raise ValueError("evidence source revision is invalid")
    _require_hashes(payload["inputs"], name="evidence inputs")
    detail = payload["payload"]
    if not isinstance(detail, Mapping) or set(detail) != _PAYLOAD_FIELDS[evidence_type]:
        raise ValueError(f"{evidence_type} payload fields are not canonical")


def validate_evidence_directory(root: str | Path) -> dict[str, str]:
    directory = Path(root)
    expected_documents = set(REQUIRED_EVIDENCE_FILES) - {"index.json"}
    document_hashes: dict[str, str] = {}
    revisions: set[str] = set()
    for name in sorted(expected_documents):
        payload, data = _read_canonical(directory / name)
        validate_evidence_document(payload)
        document_hashes[name] = _sha256(data)
        revisions.add(str(payload["source_revision"]))
    index, index_data = _read_canonical(directory / "index.json")
    if (
        set(index) != {"documents", "schema_version", "source_revision"}
        or index["schema_version"] != 1
        or index["documents"] != document_hashes
        or len(revisions) != 1
        or index["source_revision"] not in revisions
    ):
        raise ValueError("evidence index is stale or noncanonical")
    return {**document_hashes, "index.json": _sha256(index_data)}


def validate_deployment(
    root: str | Path,
    *,
    expected_revision: str,
    expected_archive_sha256: str,
    expected_evidence_revision: str,
) -> None:
    directory = Path(root)
    deployment, _ = _read_canonical(directory / ".deployment.json")
    if set(deployment) != {
        "archive_name",
        "archive_sha256",
        "revision",
        "schema_version",
    } or deployment.get("schema_version") != 1:
        raise ValueError("deployment metadata is noncanonical")
    if deployment.get("revision") != expected_revision:
        raise ValueError("deployment revision is stale")
    if deployment.get("archive_sha256") != expected_archive_sha256:
        raise ValueError("deployment archive is stale")
    archive_name = deployment.get("archive_name")
    if (
        not isinstance(archive_name, str)
        or not archive_name
        or Path(archive_name).name != archive_name
    ):
        raise ValueError("deployment archive name is invalid")
    index, _ = _read_canonical(directory / "evidence" / "task10a" / "index.json")
    if index.get("source_revision") != expected_evidence_revision:
        raise ValueError("deployment evidence revision is stale")
    report_metadata, _ = _read_canonical(
        directory / "evidence" / "task10a" / "report_metadata.json"
    )
    validate_evidence_document(report_metadata)
    expected_report = report_metadata["payload"]["report_sha256"]
    if _sha256((directory / "REPORT.md").read_bytes()) != expected_report:
        raise ValueError("deployment report metadata is stale")
