from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


RUN_REQUIRED_FIELDS = {
    "instance",
    "method",
    "k",
    "model_truth_gap",
    "shots_per_query",
    "seed",
    "query_budget",
    "final_exact_true_infidelity",
    "stopped_on_exact_check",
    "claim_success",
    "initial_pulse_id",
    "stopping_rule",
    "optimizer",
}

FORBIDDEN_PATTERNS = [
    re.compile(r"\bimport\s+socket\b"),
    re.compile(r"\bfrom\s+socket\s+import\b"),
    re.compile(r"\bimport\s+requests\b"),
    re.compile(r"\bimport\s+urllib\b"),
    re.compile(r"\bfrom\s+urllib\b"),
    re.compile(r"\bimport\s+http\.client\b"),
    re.compile(r"\bimport\s+subprocess\b"),
    re.compile(r"\bos\.environ\b"),
    re.compile(r"research/benchmark/private"),
    re.compile(r"\.ssh"),
    re.compile(r"id_ed25519"),
    re.compile(r"lookup_table"),
    re.compile(r"hardcoded_answers?"),
    re.compile(r"true_gradient"),
    re.compile(r"true_hessian"),
]

SOURCE_SUFFIXES = {".py", ".sh", ".bash", ".zsh", ".ipynb"}


def error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    payload.update(extra)
    return payload


def environment_report(instances: str, timeout_seconds: float) -> dict[str, Any]:
    return {
        "engine": "python-subprocess",
        "python": sys.version.split()[0],
        "instances": instances,
        "timeout_seconds": timeout_seconds,
        "sandbox": "static-source-scan+subprocess-timeout",
        "docker": "unavailable",
    }


def make_report(
    status: str,
    score: float | None,
    per_instance: dict[str, Any] | None,
    errors: list[dict[str, Any]] | None,
    environment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "score": score,
        "per_instance": per_instance or {},
        "errors": errors or [],
        "environment": environment,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError:
        return None, [error("missing_submission", f"{path.name} was not found")]
    except json.JSONDecodeError as exc:
        return None, [error("invalid_json", f"{path.name} is not valid JSON", detail=str(exc))]
    if not isinstance(payload, dict):
        return None, [error("invalid_schema", "submission root must be a JSON object")]
    return payload, []


def scan_forbidden_sources(candidate_dir: Path) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not candidate_dir.exists() or not candidate_dir.is_dir():
        return [error("missing_candidate_dir", "candidate directory does not exist")]
    for path in sorted(candidate_dir.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        rel = path.relative_to(candidate_dir).as_posix()
        try:
            text = path.read_text(errors="ignore")
        except OSError as exc:
            errors.append(error("source_read_error", f"could not read {rel}", detail=str(exc)))
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                errors.append(
                    error(
                        "forbidden_source",
                        f"forbidden candidate source pattern in {rel}",
                        file=rel,
                        pattern=pattern.pattern,
                    )
                )
                break
    return errors


def extract_runs(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    if payload.get("schema_version") != 1:
        errors.append(error("invalid_schema", "schema_version must be 1"))
        return [], errors

    if "runs" in payload:
        runs = payload["runs"]
        if not isinstance(runs, list):
            return [], [error("invalid_schema", "runs must be a list")]
        normalized = [dict(run) for run in runs if isinstance(run, dict)]
        if len(normalized) != len(runs):
            errors.append(error("invalid_schema", "every run must be an object"))
        return normalized, errors

    if "results" in payload:
        normalized: list[dict[str, Any]] = []
        results = payload["results"]
        if not isinstance(results, list):
            return [], [error("invalid_schema", "results must be a list")]
        for group in results:
            if not isinstance(group, dict):
                errors.append(error("invalid_schema", "every result group must be an object"))
                continue
            seeds = group.get("seeds", [])
            if not isinstance(seeds, list):
                errors.append(error("invalid_schema", "result group seeds must be a list"))
                continue
            shared = {key: value for key, value in group.items() if key != "seeds"}
            for seed_row in seeds:
                if not isinstance(seed_row, dict):
                    errors.append(error("invalid_schema", "every seed result must be an object"))
                    continue
                row = dict(shared)
                row.update(seed_row)
                normalized.append(row)
        return normalized, errors

    return [], [error("invalid_schema", "submission must include runs or results")]


def validate_run_shape(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(runs):
        missing = sorted(RUN_REQUIRED_FIELDS - set(row))
        if missing:
            errors.append(
                error("missing_field", "run is missing required fields", index=index, fields=missing)
            )
            continue
        if row.get("claim_success") and "queries_to_target" not in row:
            errors.append(
                error(
                    "missing_field",
                    "successful run is missing queries_to_target",
                    index=index,
                    fields=["queries_to_target"],
                )
            )
    return errors
