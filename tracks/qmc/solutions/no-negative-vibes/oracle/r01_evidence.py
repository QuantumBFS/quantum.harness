"""Fail-closed validation for the raw evidence behind the R01 fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any


_FIXTURE_KEYS = {
    "exact_field",
    "experiments",
    "fixture_schema_version",
    "protocol",
    "raw_schema_version",
    "schema_notes",
    "transform",
}
_EXPERIMENT_KEYS = {"cells", "experiment_id", "source_commit"}
_CELL_KEYS = {
    "anchor_count",
    "anchors",
    "family",
    "host_role",
    "mask",
    "package_versions",
    "raw_results",
    "scientific_payload_equal_after_removing_only_top_level_execution",
    "system_shape",
}
_RAW_RECORD_KEYS = {"execution", "path", "role", "sha256"}
_RAW_PAYLOAD_KEYS = {
    "anchor_count",
    "anchors",
    "execution",
    "family",
    "mask",
    "package_versions",
    "protocol",
    "schema_version",
    "source_commit",
    "system",
}
_RAW_SYSTEM_KEYS = {
    "exact_field",
    "geometry",
    "system_shape",
    "transform",
}
_EXECUTION_KEYS = {
    "blas_threads",
    "process_start_method",
    "wall_time_seconds",
    "workers",
}
_BLAS_THREAD_KEYS = {
    "MKL_NUM_THREADS",
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
}
_RAW_ROLES = {"production", "smoke"}
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _require_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _require_array(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a JSON array")
    return value


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    context: str,
) -> None:
    observed = set(value)
    if observed == expected:
        return
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    raise ValueError(
        f"{context} keys are not exact: missing={missing}, extra={extra}"
    )


def _read_json_bytes(path: Path, context: str) -> tuple[bytes, dict[str, Any]]:
    try:
        encoded = path.read_bytes()
    except OSError as error:
        raise ValueError(f"{context} cannot be read: {path}") from error
    try:
        payload = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{context} is not valid UTF-8 JSON: {path}") from error
    return encoded, _require_object(payload, context)


def _resolve_raw_path(repository_root: Path, raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("raw result path must be a non-empty string")
    if (
        PurePosixPath(raw_path).is_absolute()
        or PureWindowsPath(raw_path).is_absolute()
    ):
        raise ValueError(f"raw result path must be relative: {raw_path!r}")

    unresolved = repository_root / raw_path
    try:
        resolved = unresolved.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"raw result is missing: {raw_path}") from error
    try:
        resolved.relative_to(repository_root)
    except ValueError as error:
        raise ValueError(
            f"raw result escapes repository root: {raw_path!r}"
        ) from error
    if not resolved.is_file():
        raise ValueError(f"raw result is not a file: {raw_path}")
    return resolved


def _validate_execution(value: Any, context: str) -> dict[str, Any]:
    execution = _require_object(value, context)
    _require_exact_keys(execution, _EXECUTION_KEYS, context)
    blas_threads = _require_object(
        execution["blas_threads"],
        f"{context}.blas_threads",
    )
    _require_exact_keys(
        blas_threads,
        _BLAS_THREAD_KEYS,
        f"{context}.blas_threads",
    )
    if (
        not isinstance(execution["workers"], int)
        or isinstance(execution["workers"], bool)
        or execution["workers"] < 1
    ):
        raise ValueError(f"{context}.workers must be a positive integer")
    wall_time = execution["wall_time_seconds"]
    if (
        not isinstance(wall_time, (int, float))
        or isinstance(wall_time, bool)
        or wall_time <= 0
    ):
        raise ValueError(
            f"{context}.wall_time_seconds must be a positive number"
        )
    if not isinstance(execution["process_start_method"], str):
        raise ValueError(
            f"{context}.process_start_method must be a string"
        )
    if not all(isinstance(value, str) for value in blas_threads.values()):
        raise ValueError(f"{context}.blas_threads values must be strings")
    return execution


def _anchor_kind(label: Any, context: str) -> str:
    if not isinstance(label, str):
        raise ValueError(f"{context}.label must be a string")
    if label.startswith("h"):
        return "hopping"
    if label.startswith("pa"):
        return "pair-annihilation"
    if label.startswith("pc"):
        return "pair-creation"
    raise ValueError(f"{context}.label has no recognized anchor kind")


def _compact_raw_branch(
    value: Any,
    *,
    classification: str,
    context: str,
) -> dict[str, Any]:
    branch = _require_object(value, context)
    if "status" not in branch:
        raise ValueError(f"{context} lacks status")
    if classification == "numerical-only":
        return dict(branch)

    compact = {"status": branch["status"]}
    if "exact_primal_certificate" in branch:
        compact["certificate"] = branch["exact_primal_certificate"]
    if "exact_replay_diagnostic" in branch:
        compact["exact_replay_diagnostic"] = branch[
            "exact_replay_diagnostic"
        ]
    return compact


def _compact_raw_anchor(value: Any, context: str) -> dict[str, Any]:
    anchor = _require_object(value, context)
    required = {"classification", "label", "negative", "positive"}
    missing = sorted(required - set(anchor))
    if missing:
        raise ValueError(f"{context} missing anchor fields: {missing}")
    classification = anchor["classification"]
    if classification not in {
        "certified-feasible",
        "certified-zero",
        "numerical-only",
    }:
        raise ValueError(f"{context}.classification is unsupported")

    compact = {
        "anchor_kind": _anchor_kind(anchor["label"], context),
        "classification": classification,
        "label": anchor["label"],
        "negative": _compact_raw_branch(
            anchor["negative"],
            classification=classification,
            context=f"{context}.negative",
        ),
        "positive": _compact_raw_branch(
            anchor["positive"],
            classification=classification,
            context=f"{context}.positive",
        ),
    }
    if classification == "certified-zero":
        if "zero_certificate" not in anchor:
            raise ValueError(f"{context} lacks zero_certificate")
        compact["zero_certificate"] = anchor["zero_certificate"]
    elif classification == "numerical-only":
        for key, item in anchor.items():
            if key not in required:
                compact[key] = item
    return compact


def _validate_fixture_anchors(
    raw_value: Any,
    fixture_value: Any,
    context: str,
) -> None:
    raw_anchors = _require_array(raw_value, f"{context} raw anchors")
    fixture_anchors = _require_array(
        fixture_value,
        f"{context} fixture anchors",
    )
    compact_anchors = [
        _compact_raw_anchor(
            anchor,
            f"{context} raw anchors[{index}]",
        )
        for index, anchor in enumerate(raw_anchors)
    ]
    if fixture_anchors != compact_anchors:
        raise ValueError(f"{context} fixture anchors do not match raw anchors")


def _validate_raw_provenance(
    *,
    raw_payload: dict[str, Any],
    raw_record: dict[str, Any],
    cell: dict[str, Any],
    experiment: dict[str, Any],
    fixture: dict[str, Any],
    context: str,
) -> None:
    expected_values = {
        "anchor_count": cell["anchor_count"],
        "family": cell["family"],
        "mask": cell["mask"],
        "package_versions": cell["package_versions"],
        "protocol": fixture["protocol"],
        "schema_version": fixture["raw_schema_version"],
        "source_commit": experiment["source_commit"],
    }
    for key, expected in expected_values.items():
        if raw_payload[key] != expected:
            raise ValueError(
                f"{context} provenance mismatch for {key}: "
                f"expected {expected!r}, observed {raw_payload[key]!r}"
            )

    system_context = f"{context}.system"
    system = _require_object(raw_payload["system"], system_context)
    _require_exact_keys(system, _RAW_SYSTEM_KEYS, system_context)
    if system.get("system_shape") != cell["system_shape"]:
        raise ValueError(f"{context} provenance mismatch for system_shape")
    if system["exact_field"] != fixture["exact_field"]:
        raise ValueError(f"{context} provenance mismatch for exact_field")
    if system["transform"] != fixture["transform"]:
        raise ValueError(f"{context} provenance mismatch for transform")
    anchors = _require_array(raw_payload["anchors"], f"{context}.anchors")
    if len(anchors) != raw_payload["anchor_count"]:
        raise ValueError(f"{context} anchor_count does not match anchors")

    fixture_execution = _validate_execution(
        raw_record["execution"],
        f"{context} fixture execution",
    )
    raw_execution = _validate_execution(
        raw_payload["execution"],
        f"{context} raw execution",
    )
    if fixture_execution != raw_execution:
        raise ValueError(f"{context} execution provenance mismatch")


def validate_r01_evidence(
    *,
    repository_root: Path | str,
    fixture_path: Path | str,
) -> dict[str, int]:
    """Validate all raw files and pair comparisons referenced by an R01 fixture."""
    try:
        root = Path(repository_root).resolve(strict=True)
    except OSError as error:
        raise ValueError(
            f"repository root does not exist: {repository_root}"
        ) from error
    if not root.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")

    try:
        resolved_fixture = Path(fixture_path).resolve(strict=True)
    except OSError as error:
        raise ValueError(f"fixture does not exist: {fixture_path}") from error
    _, fixture = _read_json_bytes(resolved_fixture, "fixture")
    _require_exact_keys(fixture, _FIXTURE_KEYS, "fixture")
    if fixture["fixture_schema_version"] != 2:
        raise ValueError("fixture_schema_version must be 2")

    experiments = _require_array(
        fixture["experiments"],
        "fixture.experiments",
    )
    if not experiments:
        raise ValueError("fixture.experiments must not be empty")

    experiment_ids: set[str] = set()
    cell_keys: set[tuple[str, str, str]] = set()
    raw_paths: set[str] = set()
    resolved_raw_paths: set[Path] = set()
    cell_count = 0
    raw_count = 0

    for experiment_index, experiment_value in enumerate(experiments):
        experiment_context = f"fixture.experiments[{experiment_index}]"
        experiment = _require_object(
            experiment_value,
            experiment_context,
        )
        _require_exact_keys(
            experiment,
            _EXPERIMENT_KEYS,
            experiment_context,
        )
        experiment_id = experiment["experiment_id"]
        source_commit = experiment["source_commit"]
        if not isinstance(experiment_id, str) or not experiment_id:
            raise ValueError(f"{experiment_context}.experiment_id is invalid")
        if not isinstance(source_commit, str) or not source_commit:
            raise ValueError(f"{experiment_context}.source_commit is invalid")
        if experiment_id in experiment_ids:
            raise ValueError(f"duplicate experiment_id: {experiment_id}")
        experiment_ids.add(experiment_id)

        cells = _require_array(
            experiment["cells"],
            f"{experiment_context}.cells",
        )
        if not cells:
            raise ValueError(f"{experiment_context}.cells must not be empty")
        for cell_index, cell_value in enumerate(cells):
            context = f"{experiment_context}.cells[{cell_index}]"
            cell = _require_object(cell_value, context)
            _require_exact_keys(cell, _CELL_KEYS, context)
            if cell[
                "scientific_payload_equal_after_removing_only_top_level_execution"
            ] is not True:
                raise ValueError(
                    f"{context} scientific payload equality flag is not true"
                )

            family = cell["family"]
            mask = cell["mask"]
            if not isinstance(family, str) or not isinstance(mask, str):
                raise ValueError(f"{context} family and mask must be strings")
            cell_key = (experiment_id, family, mask)
            if cell_key in cell_keys:
                raise ValueError(f"duplicate fixture cell: {cell_key!r}")
            cell_keys.add(cell_key)

            raw_results = _require_array(
                cell["raw_results"],
                f"{context}.raw_results",
            )
            if len(raw_results) != 2:
                raise ValueError(
                    f"{context}.raw_results must contain exactly two records"
                )
            payload_by_role: dict[str, dict[str, Any]] = {}
            for raw_index, raw_value in enumerate(raw_results):
                raw_context = f"{context}.raw_results[{raw_index}]"
                raw_record = _require_object(raw_value, raw_context)
                _require_exact_keys(
                    raw_record,
                    _RAW_RECORD_KEYS,
                    raw_context,
                )
                role = raw_record["role"]
                if (
                    not isinstance(role, str)
                    or role not in _RAW_ROLES
                    or role in payload_by_role
                ):
                    raise ValueError(
                        f"{context} raw roles must be exactly "
                        f"{sorted(_RAW_ROLES)}"
                    )

                raw_path = raw_record["path"]
                resolved_raw = _resolve_raw_path(root, raw_path)
                if resolved_raw in resolved_raw_paths:
                    raise ValueError(
                        f"{context} roles resolve to the same raw file"
                    )
                if raw_path in raw_paths:
                    raise ValueError(f"duplicate raw result path: {raw_path}")
                raw_paths.add(raw_path)
                resolved_raw_paths.add(resolved_raw)
                encoded, raw_payload = _read_json_bytes(
                    resolved_raw,
                    f"{raw_context} raw result",
                )

                expected_sha256 = raw_record["sha256"]
                if (
                    not isinstance(expected_sha256, str)
                    or _SHA256_PATTERN.fullmatch(expected_sha256) is None
                ):
                    raise ValueError(f"{raw_context}.sha256 is invalid")
                observed_sha256 = hashlib.sha256(encoded).hexdigest()
                if observed_sha256 != expected_sha256:
                    raise ValueError(
                        f"{raw_context} sha256 mismatch: "
                        f"expected {expected_sha256}, "
                        f"observed {observed_sha256}"
                    )

                _require_exact_keys(
                    raw_payload,
                    _RAW_PAYLOAD_KEYS,
                    f"{raw_context} raw result",
                )
                _validate_raw_provenance(
                    raw_payload=raw_payload,
                    raw_record=raw_record,
                    cell=cell,
                    experiment=experiment,
                    fixture=fixture,
                    context=raw_context,
                )
                payload_by_role[role] = raw_payload
                raw_count += 1

            if set(payload_by_role) != _RAW_ROLES:
                raise ValueError(
                    f"{context} raw roles must be exactly "
                    f"{sorted(_RAW_ROLES)}"
                )
            smoke_payload = dict(payload_by_role["smoke"])
            production_payload = dict(payload_by_role["production"])
            del smoke_payload["execution"]
            del production_payload["execution"]
            if smoke_payload != production_payload:
                raise ValueError(
                    f"{context} scientific payload mismatch after removing "
                    "only top-level execution"
                )
            _validate_fixture_anchors(
                smoke_payload["anchors"],
                cell["anchors"],
                context,
            )
            cell_count += 1

    return {
        "cell_count": cell_count,
        "experiment_count": len(experiments),
        "raw_count": raw_count,
    }


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate raw evidence referenced by the R01 fixture.",
    )
    parser.add_argument(
        "--repository-root",
        required=True,
        type=Path,
        help="Repository root used to resolve raw result paths.",
    )
    parser.add_argument(
        "--fixture",
        required=True,
        type=Path,
        help="R01 fixture JSON to validate.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _argument_parser()
    arguments = parser.parse_args(argv)
    try:
        summary = validate_r01_evidence(
            repository_root=arguments.repository_root,
            fixture_path=arguments.fixture,
        )
    except ValueError as error:
        parser.error(str(error))
    print(
        "validated R01 evidence: "
        f"experiments={summary['experiment_count']} "
        f"cells={summary['cell_count']} "
        f"raw_results={summary['raw_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
