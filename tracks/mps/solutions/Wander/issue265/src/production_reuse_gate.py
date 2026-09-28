"""Fail-closed attestations for production-v2 convergence-data reuse."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .research_dataset import (
    file_sha256,
    load_research_dataset,
    validate_research_dataset,
)
from .tenpy_research_backend import canonical_job_sha256


ALLOWED_REUSE = {
    "amp_mu005_up__production_a__v2": "amp_mu005_up__convergence__fine",
    "amp_mu005_down__production_a__v2": "amp_mu005_down__convergence__fine",
}


@dataclass(frozen=True)
class ReuseAttestation:
    target_job_id: str
    source_job_id: str
    dataset_path: str
    dataset_sha256: str
    run_summary_sha256: str
    dataset_validation_sha256: str
    convergence_audit_sha256: str
    canonical_job_sha256: str
    status: str = "accepted"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _payload(source: Mapping[str, Any] | str | Path) -> tuple[dict[str, Any], str]:
    if isinstance(source, Mapping):
        raw = dict(source)
        canonical = json.dumps(
            raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        import hashlib

        return raw, hashlib.sha256(canonical).hexdigest()
    path = Path(source)
    return json.loads(path.read_text()), file_sha256(path)


def _find_job(manifest: Mapping[str, Any], job_id: str) -> dict[str, Any]:
    matches = [
        dict(job)
        for job in manifest.get("jobs", [])
        if str(job.get("job_id")) == job_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one source job {job_id}")
    return matches[0]


def _require_equal_mapping(
    observed: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    label: str,
) -> None:
    if json.dumps(observed, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError(f"{label} mismatch")


def validate_reuse(
    target_job: Mapping[str, Any],
    *,
    base_manifest: Mapping[str, Any] | str | Path,
    dataset_path: str | Path,
    run_summary: Mapping[str, Any] | str | Path,
    dataset_validation: Mapping[str, Any] | str | Path,
    convergence_audit: Mapping[str, Any] | str | Path,
) -> ReuseAttestation:
    """Attest one of the two exact fine-resolution production-A reuses."""

    target_id = str(target_job.get("job_id"))
    source_id = str(target_job.get("reuse_from_job_id"))
    if (
        target_job.get("execution_mode") != "reuse"
        or ALLOWED_REUSE.get(target_id) != source_id
    ):
        raise ValueError("unregistered production reuse row")

    manifest, _ = _payload(base_manifest)
    summary, summary_hash = _payload(run_summary)
    validation, validation_hash = _payload(dataset_validation)
    audit, audit_hash = _payload(convergence_audit)
    audit_accepted = (
        audit.get("status") == "accepted"
        or audit.get("accepted") is True
        or audit.get("convergence", {}).get("accepted") is True
    )
    if not audit_accepted:
        raise ValueError("convergence audit is not accepted")

    source_job = _find_job(manifest, source_id)
    if str(summary.get("status")) != "complete":
        raise ValueError("source run summary is not complete")
    if str(summary.get("job_id")) != source_id:
        raise ValueError("run summary source job ID mismatch")
    effective = dict(summary.get("effective_numerics", {}))
    for key, expected in {
        "L": 512,
        "dt": 0.0125,
        "chi_max": 1024,
        "truncation_cutoff": 1e-11,
        "t_max": 200.0,
    }.items():
        if key not in effective or not np.isclose(
            float(effective[key]), float(expected), rtol=0.0, atol=1e-14
        ):
            raise ValueError(f"effective numerics mismatch for {key}")
    _require_equal_mapping(
        dict(target_job["condition"]),
        dict(source_job["condition"]),
        label="physical condition",
    )
    for key in ("L", "dt", "chi_max", "truncation_cutoff"):
        if not np.isclose(
            float(target_job["numerics"][key]),
            float(source_job["numerics"][key]),
            rtol=0.0,
            atol=1e-14,
        ):
            raise ValueError(f"target/source numerical mismatch for {key}")

    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"reuse dataset is missing: {path}")
    dataset = load_research_dataset(path)
    validate_research_dataset(dataset)
    if dataset.condition_id != str(target_job["condition_id"]):
        raise ValueError("reuse dataset condition mismatch")
    if dataset.t.shape != (1001,) or not np.allclose(
        dataset.t, np.linspace(0.0, 200.0, 1001), rtol=0.0, atol=1e-12
    ):
        raise ValueError("reuse dataset time grid must be 0..200 with 1001 points")
    if dataset.current is None or dataset.czz is None:
        raise ValueError("reuse dataset is missing current or czz")
    if dataset.fcs_gamma is None or dataset.fcs_logZ is None:
        raise ValueError("reuse dataset is missing FCS")
    expected_gamma = np.asarray([-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6])
    if not np.array_equal(np.asarray(dataset.fcs_gamma), expected_gamma):
        raise ValueError("reuse dataset FCS grid mismatch")
    expected_job_hash = canonical_job_sha256(source_job, effective)
    if str(dataset.metadata.get("raw_sha256")) != expected_job_hash:
        raise ValueError("canonical job hash mismatch")
    if str(dataset.metadata.get("job_id")) != source_id:
        raise ValueError("dataset source job ID mismatch")

    records = {
        str(record.get("job_id")): dict(record)
        for record in validation.get("records", [])
    }
    record = records.get(source_id)
    dataset_hash = file_sha256(path)
    if (
        record is None
        or record.get("status") != "valid"
        or str(record.get("file_sha256")) != dataset_hash
    ):
        raise ValueError("dataset validation is missing, failed, or stale")

    return ReuseAttestation(
        target_job_id=target_id,
        source_job_id=source_id,
        dataset_path=str(path.resolve()),
        dataset_sha256=dataset_hash,
        run_summary_sha256=summary_hash,
        dataset_validation_sha256=validation_hash,
        convergence_audit_sha256=audit_hash,
        canonical_job_sha256=expected_job_hash,
    )


def resolve_dataset_path(
    job: Mapping[str, Any],
    *,
    reuse_attestations: Mapping[str, ReuseAttestation],
) -> Path:
    """Resolve an execute output or a validated source dataset without copying."""

    mode = str(job.get("execution_mode"))
    if mode == "execute":
        return Path(str(job["output_path"]))
    if mode != "reuse":
        raise ValueError(f"unknown execution mode {mode}")
    job_id = str(job["job_id"])
    attestation = reuse_attestations.get(job_id)
    if attestation is None or attestation.status != "accepted":
        raise PermissionError(f"reuse attestation missing or failed for {job_id}")
    if attestation.source_job_id != str(job.get("reuse_from_job_id")):
        raise PermissionError(f"reuse attestation source mismatch for {job_id}")
    return Path(attestation.dataset_path)
