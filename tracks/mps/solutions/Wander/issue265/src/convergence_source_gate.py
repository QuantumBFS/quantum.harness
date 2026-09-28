"""Fail-closed source provenance gate for formal convergence continuations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


EXPECTED_JOB_COUNT = 12


class SourceGateError(RuntimeError):
    """Raised when a continuation source has not passed frozen validation."""


@dataclass(frozen=True)
class SourceAttestation:
    """Machine-readable result of one successful source-gate check."""

    job_id: str
    source_pair_id: str
    runner_sha256: str
    backend_sha256: str
    submission_identity_sha256: str
    manifest_sha256: str
    evidence_sha256: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = "pass"
        return payload


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for *path*."""

    try:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        raise SourceGateError(
            f"source_gate: cannot hash file {Path(path)}: {error}"
        ) from error


def canonical_sha256(value: Any) -> str:
    """Hash one JSON value using a stable, whitespace-free encoding."""

    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SourceGateError(
            f"source_gate: value is not canonical JSON: {error}"
        ) from error
    return hashlib.sha256(payload).hexdigest()


def _initial_attempt(
    job: Mapping[str, Any],
) -> tuple[str, Mapping[str, Any]]:
    attempts = job.get("attempts")
    if isinstance(attempts, list) and attempts:
        first = attempts[0]
        if not isinstance(first, Mapping):
            raise SourceGateError(
                "source_gate: initial attempt is not an object"
            )
        return str(first["slurm_job_id"]), _mapping(
            first["resource"],
            "initial attempt resource",
        )
    return str(job["slurm_job_id"]), _mapping(
        job["resource"],
        "initial job resource",
    )


def submission_identity(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a mutable controller record onto its immutable launch identity."""

    try:
        raw_jobs = record["jobs"]
        if not isinstance(raw_jobs, list):
            raise TypeError("jobs is not a list")
        jobs: list[dict[str, Any]] = []
        for raw_job in raw_jobs:
            job = _mapping(raw_job, "submission job")
            slurm_job_id, resource = _initial_attempt(job)
            jobs.append(
                {
                    "job_id": str(job["job_id"]),
                    "condition_id": str(job["condition_id"]),
                    "resolution_level": str(job["resolution_level"]),
                    "fcs": bool(job["fcs"]),
                    "resource": dict(resource),
                    "slurm_job_id": slurm_job_id,
                    "output": str(job["output"]),
                }
            )
        return {
            "schema_version": record["schema_version"],
            "submitted_at": record["submitted_at"],
            "cluster": record["cluster"],
            "partition": record["partition"],
            "account": record["account"],
            "team_root": record["team_root"],
            "source_root": record["source_root"],
            "pilot_job_id": str(record["pilot_job_id"]),
            "pilot_state": record["pilot_state"],
            "manifest_sha256": record["manifest_sha256"],
            "runner_sha256": record["runner_sha256"],
            "submission_complete": bool(record["submission_complete"]),
            "jobs": jobs,
        }
    except (KeyError, TypeError, ValueError) as error:
        raise SourceGateError(
            f"source_gate: malformed submission identity: {error}"
        ) from error


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SourceGateError(f"source_gate: {label} is not an object")
    return value


def _load_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SourceGateError(
            f"source_gate: cannot parse {label}: {error}"
        ) from error
    return _mapping(value, label)


def _unique_by_job_id(
    values: list[Any],
    label: str,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for value in values:
        item = _mapping(value, label)
        if "job_id" not in item:
            raise SourceGateError(
                f"source_gate: {label} is missing job_id"
            )
        job_id = str(item["job_id"])
        if job_id in result:
            raise SourceGateError(
                f"source_gate: duplicate {label} job_id {job_id}"
            )
        result[job_id] = item
    return result


def _validate_recovered_artifacts(
    amendment: Mapping[str, Any],
    amendment_path: Path,
) -> None:
    artifacts = amendment.get("recovered_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise SourceGateError(
            "source_gate: expected two recovered source artifacts"
        )
    amendment_root = amendment_path.resolve().parent
    observed: set[str] = set()
    for raw_artifact in artifacts:
        artifact = _mapping(raw_artifact, "recovered artifact")
        relative = Path(str(artifact.get("path", "")))
        if relative.is_absolute():
            candidate = relative.resolve()
        else:
            candidate = (amendment_root / relative).resolve()
            try:
                candidate.relative_to(amendment_root)
            except ValueError as error:
                raise SourceGateError(
                    "source_gate: recovered artifact escapes evidence directory"
                ) from error
        expected = str(artifact.get("sha256", ""))
        if sha256_file(candidate) != expected:
            raise SourceGateError(
                "source_gate: recovered artifact hash mismatch"
            )
        observed.add(expected)
    original = _mapping(
        amendment.get("original_source"),
        "original source",
    )
    required = {
        str(original.get("runner_sha256", "")),
        str(original.get("backend_sha256", "")),
    }
    if observed != required:
        raise SourceGateError(
            "source_gate: recovered artifacts do not match original source"
        )


def _validate_job_comparisons(
    amendment: Mapping[str, Any],
    submitted_job_ids: set[str],
) -> None:
    comparison = _mapping(
        amendment.get("all_job_equivalence"),
        "all-job equivalence",
    )
    if comparison.get("status") != "pass":
        raise SourceGateError(
            "source_gate: all-job equivalence status is not pass"
        )
    if comparison.get("expected_job_count") != EXPECTED_JOB_COUNT:
        raise SourceGateError(
            "source_gate: all-job equivalence expected count is not 12"
        )
    raw_jobs = comparison.get("jobs")
    if not isinstance(raw_jobs, list):
        raise SourceGateError(
            "source_gate: all-job comparisons are not a list"
        )
    jobs = _unique_by_job_id(raw_jobs, "job comparison")
    if set(jobs) != submitted_job_ids:
        raise SourceGateError(
            "source_gate: comparison job set mismatch"
        )
    required_true = (
        "numerics_exact",
        "time_grid_exact",
        "canonical_job_sha256_exact",
    )
    for job_id, item in jobs.items():
        if (
            item.get("status") != "pass"
            or any(item.get(name) is not True for name in required_true)
            or item.get("time_grid_points") != 1001
        ):
            raise SourceGateError(
                f"source_gate: job comparison failed for {job_id}"
            )


def _validate_resume(amendment: Mapping[str, Any]) -> None:
    resume = _mapping(
        amendment.get("cross_version_resume"),
        "cross-version resume",
    )
    if resume.get("status") != "pass":
        raise SourceGateError(
            "source_gate: cross-version resume status is not pass"
        )
    if resume.get("interrupted_process_exit_code") != 143:
        raise SourceGateError(
            "source_gate: interruption exit code is not 143"
        )
    try:
        difference = float(resume["maximum_array_difference"])
        threshold = float(resume["threshold"])
    except (KeyError, TypeError, ValueError) as error:
        raise SourceGateError(
            f"source_gate: malformed resume threshold: {error}"
        ) from error
    if difference < 0.0 or threshold <= 0.0 or not difference < threshold:
        raise SourceGateError(
            "source_gate: resume difference is not below threshold"
        )


def _validate_source_pairs(
    amendment: Mapping[str, Any],
    *,
    runner_sha256: str,
    backend_sha256: str,
) -> str:
    raw_pairs = amendment.get("allowed_source_pairs")
    if not isinstance(raw_pairs, list) or len(raw_pairs) != 2:
        raise SourceGateError(
            "source_gate: expected exactly two allowed source pairs"
        )
    matches: list[str] = []
    observed_pair_ids: set[str] = set()
    for raw_pair in raw_pairs:
        pair = _mapping(raw_pair, "allowed source pair")
        pair_id = str(pair.get("pair_id", ""))
        if not pair_id or pair_id in observed_pair_ids:
            raise SourceGateError(
                "source_gate: allowed source pair IDs are invalid"
            )
        observed_pair_ids.add(pair_id)
        if (
            pair.get("runner_sha256") == runner_sha256
            and pair.get("backend_sha256") == backend_sha256
        ):
            matches.append(pair_id)
    if len(matches) != 1:
        raise SourceGateError(
            "source_gate: current source pair is not allowed"
        )
    return matches[0]


def validate_source_gate(
    *,
    submission_path: Path,
    manifest_path: Path,
    amendment_path: Path,
    job_id: str,
    runner_path: Path,
    backend_path: Path,
) -> SourceAttestation:
    """Validate one continuation against the frozen source amendment."""

    submission_path = Path(submission_path)
    manifest_path = Path(manifest_path)
    amendment_path = Path(amendment_path)
    record = _load_json(submission_path, "submission record")
    manifest = _load_json(manifest_path, "manifest")
    amendment = _load_json(amendment_path, "amendment")

    if amendment.get("schema_version") != 1:
        raise SourceGateError(
            "source_gate: unsupported amendment schema"
        )
    if amendment.get("status") != "pass":
        raise SourceGateError(
            "source_gate: amendment status is not pass"
        )
    if record.get("submission_complete") is not True:
        raise SourceGateError(
            "source_gate: submission record is incomplete"
        )
    raw_record_jobs = record.get("jobs")
    if (
        not isinstance(raw_record_jobs, list)
        or len(raw_record_jobs) != EXPECTED_JOB_COUNT
    ):
        raise SourceGateError(
            "source_gate: expected exactly 12 submitted jobs"
        )
    record_jobs = _unique_by_job_id(
        raw_record_jobs,
        "submission job",
    )
    requested_job_id = str(job_id)
    if requested_job_id not in record_jobs:
        raise SourceGateError(
            "source_gate: requested job is not in the submission record"
        )

    original = _mapping(
        amendment.get("original_source"),
        "original source",
    )
    if record.get("runner_sha256") != original.get("runner_sha256"):
        raise SourceGateError(
            "source_gate: original runner hash mismatch"
        )
    frozen_submission = _mapping(
        amendment.get("submission"),
        "frozen submission",
    )
    identity_sha256 = canonical_sha256(submission_identity(record))
    if identity_sha256 != frozen_submission.get("identity_sha256"):
        raise SourceGateError(
            "source_gate: submission identity mismatch"
        )

    frozen_manifest = _mapping(
        amendment.get("manifest"),
        "frozen manifest",
    )
    manifest_sha256 = sha256_file(manifest_path)
    if (
        manifest_sha256 != frozen_manifest.get("sha256")
        or record.get("manifest_sha256") != manifest_sha256
    ):
        raise SourceGateError(
            "source_gate: manifest hash mismatch"
        )

    raw_manifest_jobs = manifest.get("jobs")
    if not isinstance(raw_manifest_jobs, list):
        raise SourceGateError(
            "source_gate: manifest jobs are not a list"
        )
    manifest_jobs = _unique_by_job_id(raw_manifest_jobs, "manifest job")
    for submitted_job_id in record_jobs:
        item = manifest_jobs.get(submitted_job_id)
        if item is None:
            raise SourceGateError(
                "source_gate: submitted job is missing from manifest"
            )
        if item.get("stage") != "convergence":
            raise SourceGateError(
                "source_gate: requested manifest job is not convergence"
            )
        condition = _mapping(
            item.get("condition"),
            "manifest job condition",
        )
        try:
            j2 = float(condition.get("j2", 0.0))
        except (TypeError, ValueError) as error:
            raise SourceGateError(
                "source_gate: requested manifest job has invalid J2"
            ) from error
        if abs(j2) > 1e-15:
            raise SourceGateError(
                "source_gate: requested manifest job has nonzero J2"
            )

    _validate_recovered_artifacts(amendment, amendment_path)
    _validate_job_comparisons(amendment, set(record_jobs))
    _validate_resume(amendment)

    runner_sha256 = sha256_file(Path(runner_path))
    backend_sha256 = sha256_file(Path(backend_path))
    pair_id = _validate_source_pairs(
        amendment,
        runner_sha256=runner_sha256,
        backend_sha256=backend_sha256,
    )
    return SourceAttestation(
        job_id=requested_job_id,
        source_pair_id=pair_id,
        runner_sha256=runner_sha256,
        backend_sha256=backend_sha256,
        submission_identity_sha256=identity_sha256,
        manifest_sha256=manifest_sha256,
        evidence_sha256=sha256_file(amendment_path),
    )
