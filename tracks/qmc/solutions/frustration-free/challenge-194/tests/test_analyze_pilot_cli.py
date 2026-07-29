from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

import long_range_percolation.pilot_analysis as analysis

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_pilot.py"
CLI_SPEC = importlib.util.spec_from_file_location("analyze_pilot_cli", SCRIPT)
assert CLI_SPEC is not None and CLI_SPEC.loader is not None
CLI = importlib.util.module_from_spec(CLI_SPEC)
CLI_SPEC.loader.exec_module(CLI)


def _canonical_bytes(document: object) -> bytes:
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


def _analysis_document(
    *,
    marker: str = "a",
    complete: bool = False,
) -> dict[str, object]:
    estimates: list[dict[str, object]] = []
    if complete:
        for sigma in (0.8, 0.9, 1.0, 1.1):
            for length in (8, 16, 32):
                for kappa in (0.0, 1.0):
                    estimates.append(
                        {
                            "sigma_hex": sigma.hex(),
                            "length": length,
                            "kappa_hex": kappa.hex(),
                            "means": {
                                "q_g": float(length),
                                "four_sector_crossing": kappa,
                            },
                        }
                    )
    document: dict[str, object] = {
        "schema_version": analysis.ANALYSIS_SCHEMA,
        "p0_run_spec_sha256": marker * 64,
        "p0_progress_sha256": "b" * 64,
        "source_revision": "c" * 40,
        "analysis_plan_sha256": "d" * 64,
        "observable_columns": dict(analysis.OBSERVABLE_COLUMNS),
        "estimates": estimates,
    }
    document["analysis_document_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return document


def _extension_brackets(source: dict[str, object]) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": analysis.BRACKET_SCHEMA,
        "source_analysis_document_sha256": source["analysis_document_sha256"],
        "requires_p0_extension": True,
        "brackets": [
            {
                "sigma_hex": (1.0).hex(),
                "status": "requires_p0_extension",
                "reason": "no_nonzero_interval_marked_by_both_estimators",
                "lengths": [16, 32],
            }
        ],
    }
    document["bracket_document_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return document


def test_analyze_command_publishes_once_and_verifies_identical_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    source = _analysis_document(complete=True)
    output = tmp_path / "p0_analysis.json"
    run_spec = tmp_path / "run_spec.json"
    monkeypatch.setattr(CLI, "aggregate_p0", lambda _path: source)

    assert (
        CLI.main(
            [
                "analyze",
                "--run-spec",
                str(run_spec),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    first = output.read_bytes()
    first_result = json.loads(capsys.readouterr().out)
    assert first_result["publication"] == "published"
    assert (
        first_result["analysis_document_sha256"] == source["analysis_document_sha256"]
    )

    assert (
        CLI.main(
            [
                "analyze",
                "--run-spec",
                str(run_spec),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert output.read_bytes() == first
    assert json.loads(capsys.readouterr().out)["publication"] == "verified-existing"

    monkeypatch.setattr(
        CLI, "aggregate_p0", lambda _path: _analysis_document(marker="e")
    )
    assert (
        CLI.main(
            [
                "analyze",
                "--run-spec",
                str(run_spec),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert output.read_bytes() == first
    assert "installed bytes mismatch" in capsys.readouterr().err


def test_build_p1_command_refuses_extension_without_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    source = _analysis_document(complete=True)
    analysis_path = tmp_path / "p0_analysis.json"
    analysis_path.write_bytes(_canonical_bytes(source))
    output = tmp_path / "p1_protocol.json"
    extension = _extension_brackets(source)
    monkeypatch.setattr(CLI, "select_p1_brackets", lambda _source: extension)

    assert (
        CLI.main(
            [
                "build-p1",
                "--analysis",
                str(analysis_path),
                "--output",
                str(output),
            ]
        )
        == 1
    )

    assert not output.exists()
    assert "P0 extension required" in capsys.readouterr().err


def test_verify_command_accepts_bound_canonical_protocol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    source = _analysis_document()
    protocol: dict[str, object] = {
        "schema_version": analysis.P1_PROTOCOL_SCHEMA,
        "source_analysis_document_sha256": source["analysis_document_sha256"],
        "cells": [],
    }
    protocol["protocol_sha256"] = hashlib.sha256(_canonical_bytes(protocol)).hexdigest()
    analysis_path = tmp_path / "p0_analysis.json"
    protocol_path = tmp_path / "p1_protocol.json"
    analysis_path.write_bytes(_canonical_bytes(source))
    protocol_path.write_bytes(_canonical_bytes(protocol))
    monkeypatch.setattr(CLI, "validate_p1_protocol", lambda _source, _protocol: None)

    assert (
        CLI.main(
            [
                "verify",
                "--analysis",
                str(analysis_path),
                "--p1-protocol",
                str(protocol_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "protocol_sha256": protocol["protocol_sha256"],
        "status": "verified",
    }
