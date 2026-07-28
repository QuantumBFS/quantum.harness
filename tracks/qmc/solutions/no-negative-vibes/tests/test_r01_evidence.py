from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

import pytest
import sympy as sp

from oracle.overlap_klein import build_system

try:
    from oracle.r01_evidence import validate_r01_evidence
except ModuleNotFoundError as error:
    if error.name != "oracle.r01_evidence":
        raise
    validate_r01_evidence = None


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
RAW_KEYS = {
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
PACKAGE_VERSIONS = {
    "numpy": "2.4.6",
    "oracle": "0.1.0",
    "scipy": "1.17.1",
    "sympy": "1.14.0",
}


def _validator() -> Callable[..., dict[str, int]]:
    assert validate_r01_evidence is not None, (
        "oracle.r01_evidence.validate_r01_evidence is required"
    )
    return validate_r01_evidence


def _execution(*, workers: int, wall_time_seconds: float) -> dict[str, Any]:
    return {
        "blas_threads": {
            "MKL_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
        },
        "process_start_method": "spawn",
        "wall_time_seconds": wall_time_seconds,
        "workers": workers,
    }


def _raw_payload(*, workers: int, wall_time_seconds: float) -> dict[str, Any]:
    payload = {
        "anchor_count": 1,
        "anchors": [
            {
                "classification": "certified-zero",
                "label": "h0<-4",
                "negative": {"status": "infeasible"},
                "positive": {"status": "infeasible"},
            }
        ],
        "execution": _execution(
            workers=workers,
            wall_time_seconds=wall_time_seconds,
        ),
        "family": "bdg",
        "mask": "rings-bridges",
        "package_versions": PACKAGE_VERSIONS,
        "protocol": "overlap-klein-v1",
        "schema_version": 1,
        "source_commit": "1" * 40,
        "system": {
            "exact_field": "Q(sqrt(2))",
            "system_shape": [1, 1],
            "transform": {"name": "synthetic-overlap-klein"},
        },
    }
    assert set(payload) == RAW_KEYS
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def _build_evidence_tree(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, Any], dict[str, dict[str, Any]]]:
    repository_root = tmp_path / "repository"
    fixture_path = tmp_path / "fixture.json"
    raw_directory = (
        repository_root
        / "tracks"
        / "qmc"
        / "results"
        / "no-negative-vibes"
        / "overlap-klein-v1"
    )
    raw_payloads = {
        "smoke": _raw_payload(workers=1, wall_time_seconds=1.25),
        "production": _raw_payload(workers=8, wall_time_seconds=0.75),
    }
    raw_records = []
    for role, raw_payload in raw_payloads.items():
        relative_path = Path(
            "tracks/qmc/results/no-negative-vibes/overlap-klein-v1"
        ) / f"synthetic-{role}.json"
        raw_records.append(
            {
                "execution": raw_payload["execution"],
                "path": relative_path.as_posix(),
                "role": role,
                "sha256": _write_json(
                    raw_directory / f"synthetic-{role}.json",
                    raw_payload,
                ),
            }
        )

    fixture = {
        "exact_field": "Q(sqrt(2))",
        "experiments": [
            {
                "cells": [
                    {
                        "anchor_count": 1,
                        "anchors": raw_payloads["smoke"]["anchors"],
                        "family": "bdg",
                        "host_role": "TEST",
                        "mask": "rings-bridges",
                        "package_versions": PACKAGE_VERSIONS,
                        "raw_results": raw_records,
                        (
                            "scientific_payload_equal_after_removing_only_"
                            "top_level_execution"
                        ): True,
                        "system_shape": [1, 1],
                    }
                ],
                "experiment_id": "R01-E999",
                "source_commit": "1" * 40,
            }
        ],
        "fixture_schema_version": 2,
        "protocol": "overlap-klein-v1",
        "raw_schema_version": 1,
        "schema_notes": {
            "scientific_payload_comparison": (
                "remove exactly the top-level execution object"
            )
        },
        "transform": {"name": "synthetic-overlap-klein"},
    }
    _write_json(fixture_path, fixture)
    return repository_root, fixture_path, fixture, raw_payloads


def test_raw_evidence_validator_accepts_a_complete_matching_pair(
    tmp_path: Path,
) -> None:
    repository_root, fixture_path, _, _ = _build_evidence_tree(tmp_path)

    assert _validator()(
        repository_root=repository_root,
        fixture_path=fixture_path,
    ) == {
        "cell_count": 1,
        "experiment_count": 1,
        "raw_count": 2,
    }


def test_raw_evidence_cli_accepts_explicit_repository_and_fixture_paths(
    tmp_path: Path,
) -> None:
    repository_root, fixture_path, _, _ = _build_evidence_tree(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "oracle.r01_evidence",
            "--repository-root",
            str(repository_root),
            "--fixture",
            str(fixture_path),
        ],
        cwd=SOLUTION_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == (
        "validated R01 evidence: experiments=1 cells=1 raw_results=2"
    )


def test_raw_evidence_validator_recomputes_each_raw_sha256(
    tmp_path: Path,
) -> None:
    repository_root, fixture_path, fixture, _ = _build_evidence_tree(
        tmp_path
    )
    fixture["experiments"][0]["cells"][0]["raw_results"][0]["sha256"] = (
        "0" * 64
    )
    _write_json(fixture_path, fixture)

    with pytest.raises(ValueError, match="sha256"):
        _validator()(
            repository_root=repository_root,
            fixture_path=fixture_path,
        )


def test_raw_evidence_validator_requires_exact_execution_provenance(
    tmp_path: Path,
) -> None:
    repository_root, fixture_path, fixture, _ = _build_evidence_tree(
        tmp_path
    )
    fixture["experiments"][0]["cells"][0]["raw_results"][0][
        "execution"
    ]["wall_time_seconds"] = 99.0
    _write_json(fixture_path, fixture)

    with pytest.raises(ValueError, match="execution"):
        _validator()(
            repository_root=repository_root,
            fixture_path=fixture_path,
        )


def test_raw_evidence_validator_compares_payloads_after_only_execution_removal(
    tmp_path: Path,
) -> None:
    repository_root, fixture_path, fixture, raw_payloads = (
        _build_evidence_tree(tmp_path)
    )
    production = raw_payloads["production"]
    production["anchors"][0]["classification"] = "certified-feasible"
    production_record = fixture["experiments"][0]["cells"][0][
        "raw_results"
    ][1]
    production_record["sha256"] = _write_json(
        repository_root / production_record["path"],
        production,
    )
    _write_json(fixture_path, fixture)

    with pytest.raises(ValueError, match="scientific payload"):
        _validator()(
            repository_root=repository_root,
            fixture_path=fixture_path,
        )


def test_raw_evidence_validator_rejects_a_raw_path_outside_repository_root(
    tmp_path: Path,
) -> None:
    repository_root, fixture_path, fixture, raw_payloads = (
        _build_evidence_tree(tmp_path)
    )
    smoke_record = fixture["experiments"][0]["cells"][0]["raw_results"][0]
    smoke_record["path"] = "../outside-repository.json"
    smoke_record["sha256"] = _write_json(
        tmp_path / "outside-repository.json",
        raw_payloads["smoke"],
    )
    _write_json(fixture_path, fixture)

    with pytest.raises(ValueError, match="repository root"):
        _validator()(
            repository_root=repository_root,
            fixture_path=fixture_path,
        )


def test_raw_evidence_validator_requires_every_referenced_raw_file(
    tmp_path: Path,
) -> None:
    repository_root, fixture_path, fixture, _ = _build_evidence_tree(
        tmp_path
    )
    smoke_record = fixture["experiments"][0]["cells"][0]["raw_results"][0]
    (repository_root / smoke_record["path"]).unlink()

    with pytest.raises(ValueError, match="missing"):
        _validator()(
            repository_root=repository_root,
            fixture_path=fixture_path,
        )


def test_raw_evidence_validator_requires_one_smoke_and_one_production_role(
    tmp_path: Path,
) -> None:
    repository_root, fixture_path, fixture, _ = _build_evidence_tree(
        tmp_path
    )
    fixture["experiments"][0]["cells"][0]["raw_results"][1]["role"] = (
        "smoke"
    )
    _write_json(fixture_path, fixture)

    with pytest.raises(ValueError, match="roles"):
        _validator()(
            repository_root=repository_root,
            fixture_path=fixture_path,
        )


def test_raw_evidence_validator_rejects_incomplete_raw_provenance(
    tmp_path: Path,
) -> None:
    repository_root, fixture_path, fixture, raw_payloads = (
        _build_evidence_tree(tmp_path)
    )
    production = raw_payloads["production"]
    del production["source_commit"]
    production_record = fixture["experiments"][0]["cells"][0][
        "raw_results"
    ][1]
    production_record["sha256"] = _write_json(
        repository_root / production_record["path"],
        production,
    )
    _write_json(fixture_path, fixture)

    with pytest.raises(ValueError, match="source_commit"):
        _validator()(
            repository_root=repository_root,
            fixture_path=fixture_path,
        )


@pytest.mark.parametrize(
    "mask",
    ("rings-bridges", "rings-diagonals-bridges"),
)
def test_bdg_system_contains_number_conserving_rows_without_mixed_support(
    mask: str,
) -> None:
    """Characterizes exact NC inclusion independently of fixture outcomes."""
    number_conserving = build_system("number-conserving", mask)
    bdg = build_system("bdg", mask)
    nc_column_indices = [
        index
        for index, label in enumerate(bdg.labels)
        if not label.startswith(("pa", "pc"))
    ]
    pairing_column_indices = [
        index
        for index, label in enumerate(bdg.labels)
        if label.startswith(("pa", "pc"))
    ]

    assert tuple(bdg.labels[index] for index in nc_column_indices) == (
        number_conserving.labels
    )
    assert pairing_column_indices

    projected_nc_rows = []
    pairing_only_row_count = 0
    for row_index, row in enumerate(bdg.rows):
        nc_coefficients = tuple(
            bdg.coefficients[row_index, column_index]
            for column_index in nc_column_indices
        )
        pairing_coefficients = tuple(
            bdg.coefficients[row_index, column_index]
            for column_index in pairing_column_indices
        )
        has_nc_support = any(
            sp.simplify(coefficient) != 0
            for coefficient in nc_coefficients
        )
        has_pairing_support = any(
            sp.simplify(coefficient) != 0
            for coefficient in pairing_coefficients
        )

        assert has_nc_support or has_pairing_support
        assert not (has_nc_support and has_pairing_support)
        if has_nc_support:
            projected_nc_rows.append((row, nc_coefficients))
        else:
            assert all(
                sp.simplify(coefficient) == 0
                for coefficient in nc_coefficients
            )
            pairing_only_row_count += 1

    expected_nc_rows = [
        (
            row,
            tuple(
                number_conserving.coefficients[row_index, column_index]
                for column_index in range(
                    number_conserving.coefficients.cols
                )
            ),
        )
        for row_index, row in enumerate(number_conserving.rows)
    ]
    assert projected_nc_rows == expected_nc_rows
    assert pairing_only_row_count == (
        len(bdg.rows) - len(number_conserving.rows)
    )
