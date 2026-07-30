"""Pure fail-closed evidence gates for one-time Production-B unblinding."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.production_b_policy import (
    PRODUCTION_B_ELIGIBLE_SELECTIONS,
    PRODUCTION_B_INELIGIBLE_SELECTIONS,
    is_production_b_eligible,
)
from src.production_reuse_gate import ALLOWED_REUSE
from src.research_dataset import file_sha256

PROTOCOL_VERSION = "1.2"
UNBLINDING_SOURCE_CLOSURE = (
    "src/production_b_policy.py",
    "src/production_b_gate.py",
    "scripts/unblind_research_test.py",
    "docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md",
    "docs/PROTOCOL_AMENDMENTS.md",
)


@dataclass(frozen=True)
class ProductionBGatePaths:
    """All immutable evidence needed to authorize Production B."""

    team_root: Path
    source_root: Path
    manifest: Path
    rules: Path
    convergence_audit: Path
    source_preflight: Path
    j2_validation: Path
    production_a_record: Path
    reuse_attestations: Path
    analysis_record: Path
    selection_record: Path
    unblinding_record: Path
    analysis_rules: Path | None = None


def canonical_sha256(value: Any) -> str:
    """Return SHA-256 of canonical UTF-8 JSON."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return dict(payload)


def _status(payload: Mapping[str, Any]) -> str:
    if "status" in payload:
        return str(payload["status"])
    return "accepted" if payload.get("accepted") is True else "missing"


def _is_sha256(value: Any) -> bool:
    text = str(value)
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )


def _verify_source_hashes(
    expected: Mapping[str, Any],
    *,
    source_root: Path,
    label: str,
) -> None:
    if not expected:
        raise ValueError(f"{label} lacks a source closure")
    stale = [
        str(relative)
        for relative, digest in expected.items()
        if not (source_root / str(relative)).is_file()
        or file_sha256(source_root / str(relative)) != str(digest)
    ]
    if stale:
        raise ValueError(
            f"{label} source closure is stale: "
            + ", ".join(sorted(stale))
        )


def _validate_primary_gates(
    paths: ProductionBGatePaths,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    convergence = _load_json(
        paths.convergence_audit,
        label="convergence audit",
    )
    records = list(convergence.get("records", []))
    if (
        _status(convergence) != "accepted"
        or not records
        or not all(
            isinstance(record, Mapping)
            and record.get("accepted") is True
            for record in records
        )
    ):
        raise ValueError(
            "convergence audit is not an all-accepted frozen record set"
        )

    preflight = _load_json(
        paths.source_preflight,
        label="production-v2 source preflight",
    )
    if _status(preflight) != "pass":
        raise ValueError("production-v2 source preflight is not pass")
    _verify_source_hashes(
        dict(preflight.get("source_closure", {}).get("files", {})),
        source_root=paths.source_root,
        label="production-v2 source preflight",
    )

    j2 = _load_json(paths.j2_validation, label="J2 validation")
    if _status(j2) != "pass":
        raise ValueError("J2 validation is not pass")
    _verify_source_hashes(
        dict(j2.get("source_sha256", {})),
        source_root=paths.source_root,
        label="J2 validation",
    )
    return convergence, preflight, j2


def _manifest_sets(
    manifest: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    jobs = [
        dict(job)
        for job in manifest.get("jobs", [])
        if isinstance(job, Mapping)
    ]
    production_a = [
        job for job in jobs if job.get("stage") == "production_a"
    ]
    production_b = [
        job for job in jobs if job.get("stage") == "production_b"
    ]
    execute_ids = {
        str(job["job_id"])
        for job in production_a
        if job.get("execution_mode") == "execute"
    }
    reuse_ids = {
        str(job["job_id"])
        for job in production_a
        if job.get("execution_mode") == "reuse"
    }
    fcs_count = sum(job.get("fcs_gamma") is not None for job in production_b)
    summary = dict(manifest.get("summary", {}))
    if (
        len(jobs) != 68
        or len(production_a) != 34
        or len(production_b) != 34
        or len(execute_ids) != 32
        or reuse_ids != set(ALLOWED_REUSE)
        or any(
            job.get("execution_mode") != "execute"
            for job in production_b
        )
        or fcs_count != 3
        or summary.get("production_a_logical") != 34
        or summary.get("production_a_execute") != 32
        or summary.get("production_a_reuse") != 2
        or summary.get("production_b_logical") != 34
        or summary.get("production_b_fcs") != 3
    ):
        raise ValueError("production-v2 manifest 34/34/3 row set changed")
    return production_a, production_b, execute_ids


def _validate_production_a(
    record: Mapping[str, Any],
    *,
    execute_ids: set[str],
) -> None:
    rows = [
        dict(row)
        for row in record.get("jobs", [])
        if isinstance(row, Mapping)
    ]
    if (
        record.get("stage") != "production_a"
        or record.get("status") != "complete"
        or record.get("submission_complete") is not True
        or record.get("all_complete") is not True
        or not _is_sha256(record.get("plan_sha256"))
        or int(record.get("reuse_count", -1)) != 2
        or len(rows) != 32
        or {str(row.get("job_id")) for row in rows} != execute_ids
    ):
        raise ValueError(
            "Production-A submission record is not exactly complete"
        )
    for row in rows:
        validation = dict(row.get("validation", {}))
        output = Path(str(row.get("output", "")))
        summary = output.with_suffix(".run.json")
        if (
            row.get("status") != "complete"
            or validation.get("status") != "valid"
            or not output.is_file()
            or not summary.is_file()
            or file_sha256(output)
            != str(validation.get("dataset_sha256"))
            or file_sha256(summary)
            != str(validation.get("run_summary_sha256"))
        ):
            raise ValueError(
                "Production-A row is stale or invalid: "
                + str(row.get("job_id"))
            )


def _validate_reuse(payload: Mapping[str, Any]) -> None:
    records = {
        str(key): dict(value)
        for key, value in payload.items()
        if not str(key).startswith("_") and isinstance(value, Mapping)
    }
    if set(records) != set(ALLOWED_REUSE):
        raise ValueError(
            "exactly two registered Production-A reuse rows are required"
        )
    for target, source in ALLOWED_REUSE.items():
        record = records[target]
        dataset = Path(str(record.get("dataset_path", "")))
        summary = dataset.with_suffix(".run.json")
        if (
            record.get("status") != "accepted"
            or record.get("source_job_id") != source
            or not dataset.is_file()
            or not summary.is_file()
            or file_sha256(dataset)
            != str(record.get("dataset_sha256"))
            or file_sha256(summary)
            != str(record.get("run_summary_sha256"))
        ):
            raise ValueError(
                f"Production-A reuse row is stale or invalid: {target}"
            )


def _validate_selection(
    paths: ProductionBGatePaths,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    analysis = _load_json(
        paths.analysis_record,
        label="two-mode analysis submission record",
    )
    analysis_plan_sha256 = str(analysis.get("plan_sha256", ""))
    if (
        analysis.get("stage") != "two_mode_validation"
        or analysis.get("status") != "decision_frozen"
        or not _is_sha256(analysis_plan_sha256)
    ):
        raise ValueError("two-mode analysis decision is not frozen")

    selection = _load_json(
        paths.selection_record,
        label="validation selection",
    )
    claimed_hash = str(selection.get("selection_sha256", ""))
    hash_payload = dict(selection)
    hash_payload.pop("selection_sha256", None)
    if (
        not _is_sha256(claimed_hash)
        or canonical_sha256(hash_payload) != claimed_hash
    ):
        raise ValueError("validation selection hash is invalid")

    analysis_selection = dict(analysis.get("selection", {}))
    status = str(selection.get("validation_status", ""))
    expected_eligible = is_production_b_eligible(status)
    if (
        selection.get("status") != "frozen"
        or analysis_selection.get("path")
        != str(paths.selection_record)
        or analysis_selection.get("selection_sha256") != claimed_hash
        or analysis_selection.get("validation_status") != status
        or bool(analysis_selection.get("production_b_eligible"))
        != expected_eligible
        or bool(selection.get("production_b_eligible"))
        != expected_eligible
        or bool(selection.get("terminal_negative"))
        != (status in PRODUCTION_B_INELIGIBLE_SELECTIONS)
        or selection.get("parameters_refit_on_blind_data") is not False
        or selection.get("plan_sha256") != analysis_plan_sha256
        or dict(selection.get("validation_summary", {})).get("status")
        != status
        or not _is_sha256(selection.get("analysis_sha256"))
    ):
        raise ValueError(
            "frozen validation selection and analysis record disagree"
        )
    if status not in (
        PRODUCTION_B_ELIGIBLE_SELECTIONS
        | PRODUCTION_B_INELIGIBLE_SELECTIONS
    ):
        raise ValueError(f"validation status is unresolved: {status}")
    if not expected_eligible:
        raise ValueError(
            f"validation status is not eligible for Production B: {status}"
        )
    return analysis, selection, claimed_hash


def _collect_seed_values(value: Any) -> set[int]:
    seeds: set[int] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if (
                normalized == "seed"
                or normalized.endswith("_seed")
                or normalized == "seeds"
            ):
                candidates = child if isinstance(child, list) else [child]
                for candidate in candidates:
                    if isinstance(candidate, int) and not isinstance(
                        candidate, bool
                    ):
                        seeds.add(candidate)
            seeds.update(_collect_seed_values(child))
    elif isinstance(value, list):
        for child in value:
            seeds.update(_collect_seed_values(child))
    return seeds


def _registered_random_seeds(
    paths: ProductionBGatePaths,
) -> dict[str, list[int]]:
    seeds: dict[str, list[int]] = {}
    if paths.analysis_rules is not None:
        rules = _load_json(
            paths.analysis_rules,
            label="two-mode analysis rules",
        )
        observed = sorted(_collect_seed_values(rules))
        if not observed:
            raise ValueError("two-mode analysis rules contain no random seed")
        seeds["analysis_rules"] = observed
    return seeds


def _source_hashes(source_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in UNBLINDING_SOURCE_CLOSURE:
        path = source_root / relative
        if not path.is_file():
            raise ValueError(f"unblinding source is missing: {relative}")
        hashes[relative] = file_sha256(path)
    return hashes


def validate_unblinding_prerequisites(
    paths: ProductionBGatePaths,
) -> dict[str, Any]:
    """Validate all pre-unblinding evidence without changing state."""

    _validate_primary_gates(paths)
    manifest = _load_json(
        paths.manifest,
        label="production-v2 manifest",
    )
    _, production_b, execute_ids = _manifest_sets(manifest)
    production_a = _load_json(
        paths.production_a_record,
        label="Production-A submission record",
    )
    _validate_production_a(production_a, execute_ids=execute_ids)
    reuse = _load_json(
        paths.reuse_attestations,
        label="Production-A reuse attestations",
    )
    _validate_reuse(reuse)
    analysis, selection, selection_hash = _validate_selection(paths)

    evidence_paths: dict[str, Path] = {
        "manifest": paths.manifest,
        "rules": paths.rules,
        "convergence_audit": paths.convergence_audit,
        "source_preflight": paths.source_preflight,
        "j2_validation": paths.j2_validation,
        "production_a_submission": paths.production_a_record,
        "production_a_reuse_attestations": paths.reuse_attestations,
        "two_mode_analysis_submission": paths.analysis_record,
        "validation_selection": paths.selection_record,
    }
    if paths.analysis_rules is not None:
        evidence_paths["analysis_rules"] = paths.analysis_rules
    evidence_sha256 = {
        label: file_sha256(path)
        for label, path in evidence_paths.items()
    }
    return {
        "status": "eligible",
        "protocol_version": PROTOCOL_VERSION,
        "validation_status": selection["validation_status"],
        "analysis_sha256": selection["analysis_sha256"],
        "selection_sha256": selection_hash,
        "production_a_execute_count": len(execute_ids),
        "production_a_reuse_count": len(ALLOWED_REUSE),
        "production_b_logical_count": len(production_b),
        "production_b_fcs_count": sum(
            job.get("fcs_gamma") is not None for job in production_b
        ),
        "analysis_plan_sha256": analysis.get("plan_sha256"),
        "random_seeds": _registered_random_seeds(paths),
        "evidence_sha256": evidence_sha256,
    }


def build_unblinding_record(
    paths: ProductionBGatePaths,
    *,
    command: str,
    now: str,
) -> dict[str, Any]:
    """Construct but do not write the one-time schema-v2 record."""

    evidence = validate_unblinding_prerequisites(paths)
    source_sha256 = _source_hashes(paths.source_root)
    return {
        "schema_version": 2,
        "status": "opened",
        "protocol_version": PROTOCOL_VERSION,
        "unblinded_at": str(now),
        "command": str(command),
        "eligibility_policy": {
            "eligible": sorted(PRODUCTION_B_ELIGIBLE_SELECTIONS),
            "ineligible": sorted(PRODUCTION_B_INELIGIBLE_SELECTIONS),
        },
        "validation_status": evidence["validation_status"],
        "analysis_sha256": evidence["analysis_sha256"],
        "selection_sha256": evidence["selection_sha256"],
        "evidence_sha256": evidence["evidence_sha256"],
        "source_sha256": source_sha256,
        "source_tree_sha256": canonical_sha256(source_sha256),
        "random_seeds": evidence["random_seeds"],
        "production_b_logical_count": 34,
        "production_b_fcs_count": 3,
    }


def validate_unblinding_record(
    paths: ProductionBGatePaths,
) -> dict[str, Any]:
    """Revalidate an existing unblinding record against current evidence."""

    record = _load_json(
        paths.unblinding_record,
        label="unblinding record",
    )
    if (
        record.get("schema_version") != 2
        or record.get("status") != "opened"
        or record.get("protocol_version") != PROTOCOL_VERSION
        or record.get("eligibility_policy")
        != {
            "eligible": sorted(PRODUCTION_B_ELIGIBLE_SELECTIONS),
            "ineligible": sorted(PRODUCTION_B_INELIGIBLE_SELECTIONS),
        }
        or record.get("production_b_logical_count") != 34
        or record.get("production_b_fcs_count") != 3
    ):
        raise ValueError("unblinding record schema or policy is invalid")

    evidence = validate_unblinding_prerequisites(paths)
    if (
        record.get("validation_status")
        != evidence["validation_status"]
        or record.get("analysis_sha256") != evidence["analysis_sha256"]
        or record.get("selection_sha256")
        != evidence["selection_sha256"]
        or record.get("evidence_sha256")
        != evidence["evidence_sha256"]
        or record.get("random_seeds") != evidence["random_seeds"]
    ):
        raise ValueError(
            "unblinding record evidence no longer matches current evidence"
        )
    source_sha256 = _source_hashes(paths.source_root)
    if (
        record.get("source_sha256") != source_sha256
        or record.get("source_tree_sha256")
        != canonical_sha256(source_sha256)
    ):
        raise ValueError(
            "unblinding record source closure no longer matches"
        )
    return record


def remote_gate_paths(team_root: Path) -> ProductionBGatePaths:
    """Return the registered SCNet evidence layout."""

    source = team_root / "source"
    jobs = team_root / "jobs"
    return ProductionBGatePaths(
        team_root=team_root,
        source_root=source,
        manifest=source
        / "results_research_program"
        / "production_manifest_v2.json",
        rules=source / "configs" / "burgers_decision_rules.json",
        convergence_audit=jobs / "convergence_audit.json",
        source_preflight=source
        / "results_research_program"
        / "hpc"
        / "production_v2_validation_20260730.json",
        j2_validation=source
        / "results_research_program"
        / "hpc"
        / "j2_validation_20260730.json",
        production_a_record=jobs / "production_a_submission.json",
        reuse_attestations=jobs
        / "production_v2_reuse_attestations.json",
        analysis_record=jobs / "two_mode_analysis_submission.json",
        selection_record=jobs / "validation_selection.json",
        unblinding_record=jobs / "unblinding.json",
        analysis_rules=source
        / "configs"
        / "two_mode_fcs_decision_rules_20260730.json",
    )
