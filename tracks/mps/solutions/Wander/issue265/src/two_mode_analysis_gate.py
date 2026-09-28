"""Fail-closed gates for the registered SCNet two-mode analysis chain."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from scripts.run_two_mode_comparison import (
    accepted_convergence_floor,
    analysis_source_closure,
    audit_available_inputs,
)
from src.production_b_policy import (
    KNOWN_VALIDATION_SELECTIONS,
    PRODUCTION_B_INELIGIBLE_SELECTIONS,
    is_production_b_eligible,
)
from src.production_reuse_gate import ALLOWED_REUSE
from src.research_dataset import file_sha256
from src.two_mode_cross_validation import (
    panel_sha256,
    registered_cross_validation_folds,
    rules_sha256,
)

LAUNCH_SOURCE_PATHS = (
    "hpc/scnet/submit_two_mode_analysis.py",
    "hpc/scnet/two_mode_cross_validation.sbatch",
    "hpc/scnet/two_mode_cross_validation_aggregate.sbatch",
    "hpc/scnet/two_mode_validation.sbatch",
    "scripts/run_two_mode_comparison.py",
    "scripts/run_two_mode_cross_validation.py",
    "src/production_b_policy.py",
    "src/two_mode_analysis_gate.py",
)
REGISTERED_COMPARISONS = {
    "independent_vs_scalar",
    "coupled_vs_scalar",
    "coupled_vs_independent",
}
REGISTERED_FIT_MODELS = {
    "gaussian_diffusion",
    "scalar_surrogate",
    "independent_two_burgers",
    "coupled_two_mode",
}


@dataclass(frozen=True)
class AnalysisPaths:
    team_root: Path
    source_root: Path
    production_record: Path
    reuse_attestations: Path
    convergence_audit: Path
    manifest: Path
    base_manifest: Path
    rules: Path
    solver_budget: Path
    data_root: Path
    analysis_root: Path


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid: {path}") from error
    if not isinstance(payload, dict):
        raise TypeError(f"{label} must be a JSON object: {path}")
    return dict(payload)


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: Any) -> bool:
    text = str(value)
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )


def _verify_production_record(
    record: Mapping[str, Any],
    *,
    execute_ids: set[str],
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in record.get("jobs", [])]
    if (
        record.get("stage") != "production_a"
        or record.get("status") != "complete"
        or record.get("all_complete") is not True
        or record.get("submission_complete") is not True
        or int(record.get("reuse_count", -1)) != 2
        or len(rows) != 32
        or {str(row.get("job_id")) for row in rows} != execute_ids
    ):
        raise ValueError(
            "production-A submission record is not exactly complete"
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
        ):
            raise ValueError(
                "production-A row lacks a fresh valid completion: "
                + str(row.get("job_id"))
            )
        if (
            file_sha256(output)
            != validation.get("dataset_sha256")
        ):
            raise ValueError(
                "production-A dataset hash changed: "
                + str(row.get("job_id"))
            )
        if (
            file_sha256(summary)
            != validation.get("run_summary_sha256")
        ):
            raise ValueError(
                "production-A run-summary hash changed: "
                + str(row.get("job_id"))
            )
    return rows


def _verify_reuse(
    payload: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    records = {
        str(key): dict(value)
        for key, value in payload.items()
        if not str(key).startswith("_")
        and isinstance(value, Mapping)
    }
    if set(records) != set(ALLOWED_REUSE):
        raise ValueError(
            "exactly two registered reuse attestations are required"
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
            != record.get("dataset_sha256")
            or file_sha256(summary)
            != record.get("run_summary_sha256")
        ):
            raise ValueError(
                f"reuse attestation is stale or invalid: {target}"
            )
    return records


def _verify_no_production_b(paths: AnalysisPaths) -> None:
    blind_root = paths.data_root / "production_b"
    if blind_root.exists() and any(blind_root.glob("*.npz")):
        raise ValueError("Production-B data exist before validation selection")
    for name in (
        "production_b_submission.json",
        "unblinding.json",
        "unblinding_record.json",
    ):
        if (paths.team_root / "jobs" / name).exists():
            raise ValueError(
                "Production-B or unblinding record exists before selection"
            )
    analysis_record = (
        paths.team_root / "jobs" / "two_mode_analysis_submission.json"
    )
    if (
        paths.analysis_root.exists()
        and any(path.is_file() for path in paths.analysis_root.rglob("*"))
        and not analysis_record.is_file()
    ):
        raise ValueError(
            "analysis output exists without an authoritative submission "
            "record"
        )


def prepare_analysis_plan(paths: AnalysisPaths) -> dict[str, Any]:
    """Return the frozen, hash-addressed 27-task plan or raise ValueError."""

    manifest = _load_json(paths.manifest, label="production-v2 manifest")
    summary = dict(manifest.get("summary", {}))
    production_a = [
        dict(job)
        for job in manifest.get("jobs", [])
        if job.get("stage") == "production_a"
    ]
    production_b = [
        dict(job)
        for job in manifest.get("jobs", [])
        if job.get("stage") == "production_b"
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
    if (
        summary.get("production_a_logical") != 34
        or summary.get("production_a_execute") != 32
        or summary.get("production_a_reuse") != 2
        or summary.get("production_b_logical") != 34
        or len(production_a) != 34
        or len(production_b) != 34
        or len(execute_ids) != 32
        or reuse_ids != set(ALLOWED_REUSE)
    ):
        raise ValueError("production-v2 manifest counts or row set changed")

    production_record = _load_json(
        paths.production_record,
        label="production-A submission record",
    )
    production_rows = _verify_production_record(
        production_record,
        execute_ids=execute_ids,
    )
    reuse_payload = _load_json(
        paths.reuse_attestations,
        label="production-v2 reuse attestations",
    )
    reuse_records = _verify_reuse(reuse_payload)
    convergence = _load_json(
        paths.convergence_audit,
        label="convergence audit",
    )
    quantum_floor = accepted_convergence_floor(convergence)
    solver_budget = _load_json(
        paths.solver_budget,
        label="two-mode solver budget",
    )
    if (
        solver_budget.get("status") != "pass"
        or not _is_sha256(solver_budget.get("config_sha256"))
    ):
        raise ValueError("two-mode solver budget is not a frozen pass")
    _verify_no_production_b(paths)

    input_summary, context = audit_available_inputs(
        manifest_path=paths.manifest,
        base_manifest_path=paths.base_manifest,
        rules_path=paths.rules,
        solver_budget_path=paths.solver_budget,
        reuse_attestations_path=paths.reuse_attestations,
        phase="validation",
        selection_record_path=None,
        data_root=paths.data_root,
    )
    if input_summary.get("status") != "observables_ready":
        raise ValueError(
            "production-A observables are not ready: "
            + str(input_summary.get("status"))
        )
    panel = context["panel"]
    rules = context["rules"]
    controls = rules["cross_validation"]
    folds = registered_cross_validation_folds(panel, controls)
    models = tuple(map(str, controls["models"]))
    tasks = [
        {
            "task_index": index,
            "model": model,
            "fold_id": fold.fold_id,
            "kind": fold.kind,
            "held_out_conditions": list(fold.held_out_conditions),
            "training_conditions": list(fold.training_conditions),
        }
        for index, (model, fold) in enumerate(
            (model, fold) for model in models for fold in folds
        )
    ]
    if len(tasks) != 27 or int(controls["expected_shards"]) != 27:
        raise ValueError("registered cross-validation task count is not 27")

    source = analysis_source_closure()
    shard_floor = max(
        float(rules["thresholds"]["scale_numerical_floor"]),
        quantum_floor,
    )
    launch_source = {
        relative: file_sha256(paths.source_root / relative)
        for relative in LAUNCH_SOURCE_PATHS
    }
    script_sha256 = {
        "cross_validation": launch_source[
            "hpc/scnet/two_mode_cross_validation.sbatch"
        ],
        "aggregate": launch_source[
            "hpc/scnet/two_mode_cross_validation_aggregate.sbatch"
        ],
        "validation": launch_source[
            "hpc/scnet/two_mode_validation.sbatch"
        ],
    }
    evidence_hashes = {
        "production_record": file_sha256(paths.production_record),
        "reuse_attestations": file_sha256(paths.reuse_attestations),
        "convergence_audit": file_sha256(paths.convergence_audit),
        "manifest": file_sha256(paths.manifest),
        "base_manifest": file_sha256(paths.base_manifest),
        "rules": file_sha256(paths.rules),
        "solver_budget": file_sha256(paths.solver_budget),
    }
    cv_outdir = paths.analysis_root / "cross_validation"
    identity = {
        "schema_version": 1,
        "stage": "two_mode_validation",
        "tasks": tasks,
        "panel_sha256": panel_sha256(panel),
        "rules_sha256": rules_sha256(rules),
        "analysis_source": source,
        "launch_source_sha256": launch_source,
        "evidence_sha256": evidence_hashes,
        "solver_budget_config_sha256": solver_budget["config_sha256"],
        "quantum_numerical_floor": quantum_floor,
        "shard_numerical_floor": shard_floor,
        "paths": {
            "source_root": str(paths.source_root.resolve()),
            "data_root": str(paths.data_root.resolve()),
            "cv_outdir": str(cv_outdir.resolve()),
            "validation_outdir": str(paths.analysis_root.resolve()),
        },
        "scripts": {
            "cross_validation": str(
                (
                    paths.source_root
                    / "hpc/scnet/two_mode_cross_validation.sbatch"
                ).resolve()
            ),
            "aggregate": str(
                (
                    paths.source_root
                    / "hpc/scnet/two_mode_cross_validation_aggregate.sbatch"
                ).resolve()
            ),
            "validation": str(
                (
                    paths.source_root
                    / "hpc/scnet/two_mode_validation.sbatch"
                ).resolve()
            ),
        },
        "script_sha256": script_sha256,
        "resources": {
            "cross_validation": {
                "cpus": 8,
                "memory": "24G",
                "walltime": "7-00:00:00",
            },
            "aggregate": {
                "cpus": 8,
                "memory": "24G",
                "walltime": "01:00:00",
            },
            "validation": {
                "cpus": 8,
                "memory": "24G",
                "walltime": "7-00:00:00",
            },
        },
        "production_rows": [
            {
                "job_id": str(row["job_id"]),
                "dataset_sha256": row["validation"]["dataset_sha256"],
                "run_summary_sha256": row["validation"][
                    "run_summary_sha256"
                ],
            }
            for row in production_rows
        ],
        "reuse_rows": [
            {
                "job_id": target,
                "dataset_sha256": reuse_records[target]["dataset_sha256"],
                "run_summary_sha256": reuse_records[target][
                    "run_summary_sha256"
                ],
            }
            for target in sorted(reuse_records)
        ],
    }
    return {
        "status": "ready",
        "plan_sha256": _canonical_sha256(identity),
        "identity": identity,
        "tasks": tasks,
        "panel_sha256": identity["panel_sha256"],
        "rules_sha256": identity["rules_sha256"],
        "analysis_source": source,
        "solver_budget_config_sha256": solver_budget["config_sha256"],
        "quantum_numerical_floor": quantum_floor,
        "shard_numerical_floor": shard_floor,
        "cv_outdir": identity["paths"]["cv_outdir"],
        "validation_outdir": identity["paths"]["validation_outdir"],
        "scripts": identity["scripts"],
        "script_sha256": script_sha256,
        "resources": identity["resources"],
    }


def _expected_shard_name(task: Mapping[str, Any]) -> str:
    return (
        f"{int(task['task_index']):02d}_{task['model']}"
        f"__{task['fold_id']}.json"
    )


def validate_cv_artifacts(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the exact shard-set validation report."""

    tasks = [dict(task) for task in plan.get("tasks", [])]
    expected = {
        _expected_shard_name(task): task for task in tasks
    }
    shard_root = Path(str(plan["cv_outdir"])) / "shards"
    observed = {
        path.name: path
        for path in shard_root.glob("*.json")
        if path.is_file()
    } if shard_root.is_dir() else {}
    missing_files = sorted(set(expected) - set(observed))
    extra_files = sorted(set(observed) - set(expected))
    errors: dict[str, list[str]] = {}
    valid_indexes: list[int] = []
    artifact_sha256: dict[str, str] = {}
    for name in sorted(set(expected) & set(observed)):
        task = expected[name]
        path = observed[name]
        row_errors: list[str] = []
        try:
            shard = _load_json(path, label=f"CV shard {name}")
        except (TypeError, ValueError) as error:
            errors[name] = [str(error)]
            continue
        artifact_sha256[name] = file_sha256(path)
        exact = {
            "task_index": int(task["task_index"]),
            "model": task["model"],
        }
        for key, value in exact.items():
            if shard.get(key) != value:
                row_errors.append(f"{key}_mismatch")
        fold = dict(shard.get("fold", {}))
        if (
            fold.get("fold_id") != task["fold_id"]
            or fold.get("kind") != task["kind"]
            or fold.get("held_out_conditions")
            != task.get("held_out_conditions")
            or fold.get("training_conditions")
            != task.get("training_conditions")
        ):
            row_errors.append("fold_mismatch")
        if shard.get("status") != "fit_complete":
            row_errors.append("fit_not_complete")
        if shard.get("panel_sha256") != plan["panel_sha256"]:
            row_errors.append("panel_sha256_mismatch")
        if shard.get("rules_sha256") != plan["rules_sha256"]:
            row_errors.append("rules_sha256_mismatch")
        if (
            shard.get("parameters_refit_on_held_out_data")
            is not False
        ):
            row_errors.append("heldout_refit_forbidden")
        if (
            shard.get("analysis_source", {}).get("closure_sha256")
            != plan["analysis_source"]["closure_sha256"]
        ):
            row_errors.append("analysis_source_mismatch")
        if (
            shard.get("solver_budget_config_sha256")
            != plan["solver_budget_config_sha256"]
        ):
            row_errors.append("solver_budget_mismatch")
        try:
            floor = float(shard["quantum_numerical_floor"])
        except (KeyError, TypeError, ValueError):
            floor = float("nan")
        if not np.isclose(
            floor,
            float(
                plan.get(
                    "shard_numerical_floor",
                    plan["quantum_numerical_floor"],
                )
            ),
            rtol=0.0,
            atol=0.0,
        ):
            row_errors.append("quantum_floor_mismatch")
        for key in (
            "training_scales_sha256",
            "holdout_scales_sha256",
        ):
            if not _is_sha256(shard.get(key)):
                row_errors.append(f"{key}_invalid")
        if row_errors:
            errors[name] = row_errors
        else:
            valid_indexes.append(int(task["task_index"]))
    missing_indexes = sorted(
        int(expected[name]["task_index"]) for name in missing_files
    )
    complete = (
        len(expected) == 27
        and not missing_files
        and not extra_files
        and not errors
    )
    return {
        "status": "complete" if complete else "invalid",
        "expected_shards": len(expected),
        "received_shards": len(observed),
        "received_indexes": sorted(valid_indexes),
        "valid_indexes": sorted(valid_indexes),
        "missing_indexes": missing_indexes,
        "missing_files": missing_files,
        "extra_files": extra_files,
        "invalid": errors,
        "artifact_sha256": artifact_sha256,
    }


def validate_aggregate(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return the aggregate validation report."""

    path = Path(str(plan["cv_outdir"])) / "summary.json"
    try:
        aggregate = _load_json(path, label="CV aggregate")
    except (TypeError, ValueError) as error:
        return {"status": "invalid", "errors": [str(error)]}
    errors: list[str] = []
    expected_folds = {
        str(task["fold_id"]) for task in plan["tasks"]
    }
    expected_fold_records = {
        str(task["fold_id"]): {
            "fold_id": str(task["fold_id"]),
            "kind": str(task["kind"]),
            "held_out_conditions": list(
                task.get("held_out_conditions", [])
            ),
            "training_conditions": list(
                task.get("training_conditions", [])
            ),
        }
        for task in plan["tasks"]
    }
    expected_models = {
        str(task["model"]) for task in plan["tasks"]
    }
    checks = {
        "status": aggregate.get("status") == "complete",
        "expected_shards": aggregate.get("expected_shards") == 27,
        "received_shards": aggregate.get("received_shards") == 27,
        "panel_sha256": (
            aggregate.get("panel_sha256") == plan["panel_sha256"]
        ),
        "rules_sha256": (
            aggregate.get("rules_sha256") == plan["rules_sha256"]
        ),
        "heldout_refit": (
            aggregate.get("parameters_refit_on_held_out_data") is False
        ),
        "analysis_source": (
            aggregate.get("analysis_source", {}).get("closure_sha256")
            == plan["analysis_source"]["closure_sha256"]
        ),
        "solver_budget": (
            aggregate.get("solver_budget_config_sha256")
            == plan["solver_budget_config_sha256"]
        ),
        "quantum_floor": np.isclose(
            float(aggregate.get("quantum_numerical_floor", np.nan)),
            float(plan["quantum_numerical_floor"]),
            rtol=0.0,
            atol=0.0,
        ),
        "folds": (
            {
                str(row.get("fold_id")): {
                    "fold_id": str(row.get("fold_id")),
                    "kind": str(row.get("kind")),
                    "held_out_conditions": list(
                        row.get("held_out_conditions", [])
                    ),
                    "training_conditions": list(
                        row.get("training_conditions", [])
                    ),
                }
                for row in aggregate.get("folds", [])
            }
            == expected_fold_records
            and len(aggregate.get("folds", [])) == len(expected_folds)
        ),
        "models": (
            set(aggregate.get("models", {})) == expected_models
            and all(
                {
                    str(row.get("fold_id"))
                    for row in aggregate["models"][model].get(
                        "folds", []
                    )
                }
                == expected_folds
                for model in expected_models
            )
        ),
        "comparisons": (
            set(aggregate.get("comparisons", {}))
            == REGISTERED_COMPARISONS
            and all(
                isinstance(
                    aggregate["comparisons"][name].get("pass"),
                    bool,
                )
                and {
                    str(row.get("fold_id"))
                    for row in aggregate["comparisons"][name].get(
                        "folds", []
                    )
                }
                == expected_folds
                for name in REGISTERED_COMPARISONS
            )
        ),
    }
    errors.extend(key for key, valid in checks.items() if not valid)
    return {
        "status": "valid" if not errors else "invalid",
        "errors": errors,
        "artifact_sha256": file_sha256(path),
        "path": str(path),
        "payload": aggregate,
    }


def validate_validation_summary(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the terminal validation-verdict report."""

    aggregate_report = validate_aggregate(plan)
    if aggregate_report.get("status") != "valid":
        return {
            "status": "invalid",
            "errors": ["aggregate_invalid"],
        }
    path = Path(str(plan["validation_outdir"])) / "summary.json"
    try:
        summary = _load_json(path, label="validation summary")
    except (TypeError, ValueError) as error:
        return {"status": "invalid", "errors": [str(error)]}
    selection = str(summary.get("status", ""))
    errors: list[str] = []
    if summary.get("schema_version") != 2:
        errors.append("schema_version")
    if summary.get("phase") != "validation":
        errors.append("phase")
    if (
        selection not in KNOWN_VALIDATION_SELECTIONS
        or summary.get("tested") is not True
    ):
        errors.append("nonterminal_or_untested_status")
    if summary.get("parameters_refit_on_blind_data") is not False:
        errors.append("blind_refit_forbidden")
    if not _is_sha256(summary.get("analysis_sha256")):
        errors.append("analysis_sha256")
    if (
        summary.get("analysis_source", {}).get("closure_sha256")
        != plan["analysis_source"]["closure_sha256"]
    ):
        errors.append("analysis_source")
    if summary.get("verdict", {}).get("status") != selection:
        errors.append("verdict_status")
    if set(summary.get("fits", {})) != REGISTERED_FIT_MODELS:
        errors.append("fit_model_set")
    if not _same_payload(
        summary.get("cross_validation"),
        aggregate_report["payload"],
    ):
        errors.append("cross_validation_payload")
    return {
        "status": "valid" if not errors else "invalid",
        "errors": errors,
        "validation_status": selection,
        "production_b_eligible": is_production_b_eligible(selection),
        "terminal_negative": (
            selection in PRODUCTION_B_INELIGIBLE_SELECTIONS
        ),
        "artifact_sha256": file_sha256(path),
        "path": str(path),
        "summary": summary,
        "aggregate_sha256": aggregate_report["artifact_sha256"],
    }


def _same_payload(left: Any, right: Any) -> bool:
    return _canonical_sha256(left) == _canonical_sha256(right)
