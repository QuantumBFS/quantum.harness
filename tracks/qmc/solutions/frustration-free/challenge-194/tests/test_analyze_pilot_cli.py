from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

import long_range_percolation.pilot_analysis as analysis
import long_range_percolation.pilot_extension as extension

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
    monkeypatch.setattr(
        CLI,
        "build_p1_protocol",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("P0 extension required before P1 publication: 1.0")
        ),
    )

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


def test_build_p0_extension_publishes_once_and_rejects_different_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    source = _analysis_document(complete=True)
    source_path = tmp_path / "p0_analysis.json"
    output = tmp_path / "p0_extension_v1_protocol.json"
    source_path.write_bytes(_canonical_bytes(source))
    protocol = {
        "schema_version": extension.EXTENSION_PROTOCOL_SCHEMA,
        "protocol_sha256": "a" * 64,
    }
    evidence_root = (tmp_path / "external-p0").resolve()
    evidence_root.mkdir()
    seen_roots: list[Path] = []
    monkeypatch.setattr(
        CLI,
        "build_p0_extension_protocol",
        lambda _source, root: seen_roots.append(root) or protocol,
    )

    assert (
        CLI.main(
            [
                "build-p0-extension",
                "--analysis",
                str(source_path),
                "--p0-evidence-root",
                str(evidence_root),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    installed = output.read_bytes()
    assert json.loads(capsys.readouterr().out) == {
        "output": str(output.resolve()),
        "protocol_sha256": protocol["protocol_sha256"],
        "publication": "published",
        "status": "ready",
    }

    assert (
        CLI.main(
            [
                "build-p0-extension",
                "--analysis",
                str(source_path),
                "--p0-evidence-root",
                str(evidence_root),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert output.read_bytes() == installed
    assert json.loads(capsys.readouterr().out) == {
        "output": str(output.resolve()),
        "protocol_sha256": protocol["protocol_sha256"],
        "publication": "verified-existing",
        "status": "ready",
    }

    monkeypatch.setattr(
        CLI,
        "build_p0_extension_protocol",
        lambda _source, root: (
            seen_roots.append(root) or {**protocol, "protocol_sha256": "b" * 64}
        ),
    )
    assert (
        CLI.main(
            [
                "build-p0-extension",
                "--analysis",
                str(source_path),
                "--p0-evidence-root",
                str(evidence_root),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert output.read_bytes() == installed
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "installed bytes mismatch" in captured.err
    assert seen_roots == [evidence_root, evidence_root, evidence_root]


def test_build_p0_extension_requires_explicit_evidence_root():
    with pytest.raises(SystemExit):
        CLI._parser().parse_args(
            [
                "build-p0-extension",
                "--analysis",
                "/tmp/p0_analysis.json",
                "--output",
                "/tmp/p0_extension_v1_protocol.json",
            ]
        )


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


def _command_sources(tmp_path: Path, command: str) -> tuple[list[str], Path]:
    output = tmp_path / f"{command}.json"
    documents = {
        "protocol": {"schema_version": extension.EXTENSION_PROTOCOL_SCHEMA},
        "p0": {"schema_version": analysis.ANALYSIS_SCHEMA},
        "extension": {"schema_version": analysis.EXTENSION_ANALYSIS_SCHEMA},
        "combined": {"schema_version": analysis.COMBINED_ANALYSIS_SCHEMA},
    }
    paths: dict[str, Path] = {}
    for name, document in documents.items():
        path = tmp_path / f"{name}.json"
        path.write_bytes(_canonical_bytes(document))
        paths[name] = path
    if command == "analyze-extension":
        return (
            [
                command,
                "--run-spec",
                str(tmp_path / "run_spec.json"),
                "--protocol",
                str(paths["protocol"]),
                "--output",
                str(output),
            ],
            output,
        )
    if command == "combine":
        evidence_root = tmp_path / "p0-root"
        evidence_root.mkdir()
        extension_run_spec = tmp_path / "extension-root/run_spec.json"
        extension_run_spec.parent.mkdir()
        extension_run_spec.write_text("{}\n", encoding="utf-8")
        return (
            [
                command,
                "--p0-analysis",
                str(paths["p0"]),
                "--extension-analysis",
                str(paths["extension"]),
                "--p0-evidence-root",
                str(evidence_root),
                "--extension-run-spec",
                str(extension_run_spec),
                "--extension-protocol",
                str(paths["protocol"]),
                "--output",
                str(output),
            ],
            output,
        )
    return (
        [
            command,
            "--analysis",
            str(paths["combined"]),
            "--p0-analysis",
            str(paths["p0"]),
            "--extension-analysis",
            str(paths["extension"]),
            "--p0-evidence-root",
            str(tmp_path / "p0-root"),
            "--extension-run-spec",
            str(tmp_path / "extension-root/run_spec.json"),
            "--extension-protocol",
            str(paths["protocol"]),
            "--output",
            str(output),
        ],
        output,
    )


def _stub_command(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    marker: str,
    *,
    fail: bool = False,
) -> dict[str, object]:
    schemas = {
        "analyze-extension": analysis.EXTENSION_ANALYSIS_SCHEMA,
        "combine": analysis.COMBINED_ANALYSIS_SCHEMA,
        "select": analysis.COMBINED_BRACKET_SCHEMA,
        "build-p1": analysis.P1_PROTOCOL_SCHEMA,
    }
    hash_fields = {
        "analyze-extension": "analysis_document_sha256",
        "combine": "analysis_document_sha256",
        "select": "bracket_document_sha256",
        "build-p1": "protocol_sha256",
    }
    document = {
        "schema_version": schemas[command],
        hash_fields[command]: marker * 64,
    }

    def result(*_args, **_kwargs):
        if fail:
            raise RuntimeError("scientific refusal")
        return document

    if command == "analyze-extension":
        monkeypatch.setattr(CLI, "aggregate_p0_extension", result)
    elif command == "combine":
        monkeypatch.setattr(CLI, "combine_p0_evidence", result)
    elif command == "select":
        monkeypatch.setattr(CLI, "select_p1_brackets", result)
    else:
        monkeypatch.setattr(
            CLI,
            "select_p1_brackets",
            lambda *_args, **_kwargs: {
                "schema_version": analysis.COMBINED_BRACKET_SCHEMA,
                "requires_p0_extension": False,
            },
        )
        monkeypatch.setattr(CLI, "build_p1_protocol", result)
    return document


@pytest.mark.parametrize(
    "command",
    ("analyze-extension", "combine", "select", "build-p1"),
)
def test_immutable_commands_publish_verify_and_reject_changed_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
):
    arguments, output = _command_sources(tmp_path, command)
    _stub_command(monkeypatch, command, "a")

    assert CLI.main(arguments) == 0
    installed = output.read_bytes()
    assert json.loads(capsys.readouterr().out)["publication"] == "published"

    assert CLI.main(arguments) == 0
    assert output.read_bytes() == installed
    assert json.loads(capsys.readouterr().out)["publication"] == "verified-existing"

    _stub_command(monkeypatch, command, "b")
    assert CLI.main(arguments) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "installed bytes mismatch" in captured.err
    assert output.read_bytes() == installed


@pytest.mark.parametrize(
    ("command", "malformed_name"),
    (
        ("analyze-extension", "protocol"),
        ("combine", "p0"),
        ("select", "combined"),
        ("build-p1", "combined"),
    ),
)
def test_immutable_commands_reject_noncanonical_inputs_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    malformed_name: str,
):
    arguments, output = _command_sources(tmp_path, command)
    (tmp_path / f"{malformed_name}.json").write_text(
        '{\n  "schema_version": "noncanonical"\n}\n',
        encoding="utf-8",
    )
    _stub_command(monkeypatch, command, "a")

    assert CLI.main(arguments) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not canonical JSON" in captured.err
    assert not output.exists()


@pytest.mark.parametrize(
    "command",
    ("analyze-extension", "combine", "select", "build-p1"),
)
def test_immutable_commands_leave_no_output_on_scientific_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
):
    arguments, output = _command_sources(tmp_path, command)
    _stub_command(monkeypatch, command, "a", fail=True)

    assert CLI.main(arguments) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "scientific refusal" in captured.err
    assert not output.exists()


def test_combined_build_leaves_protocol_absent_when_selection_is_unresolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    arguments, output = _command_sources(tmp_path, "build-p1")
    monkeypatch.setattr(
        CLI,
        "select_p1_brackets",
        lambda *_args, **_kwargs: {
            "schema_version": analysis.COMBINED_BRACKET_SCHEMA,
            "requires_p0_extension": True,
        },
    )
    monkeypatch.setattr(
        CLI,
        "build_p1_protocol",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("P0 extension required before P1 publication: 1.0")
        ),
    )

    assert CLI.main(arguments) == 1
    assert capsys.readouterr().out == ""
    assert not output.exists()


@pytest.mark.parametrize("command", ("select", "build-p1"))
@pytest.mark.parametrize("sources", ((), ("p0",), ("extension",)))
def test_combined_commands_fail_closed_without_both_explicit_sources(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
    sources: tuple[str, ...],
):
    _full_arguments, output = _command_sources(tmp_path, command)
    arguments = [
        command,
        "--analysis",
        str(tmp_path / "combined.json"),
        "--output",
        str(output),
    ]
    if "p0" in sources:
        arguments.extend(["--p0-analysis", str(tmp_path / "p0.json")])
    if "extension" in sources:
        arguments.extend(["--extension-analysis", str(tmp_path / "extension.json")])

    assert CLI.main(arguments) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        "requires explicit --p0-analysis, --extension-analysis, "
        "--p0-evidence-root, --extension-run-spec, and --extension-protocol"
        in captured.err
    )
    assert not output.exists()


def test_v1_build_compatibility_is_allowed_only_without_source_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    source = _analysis_document(complete=True)
    analysis_path = tmp_path / "p0.json"
    analysis_path.write_bytes(_canonical_bytes(source))
    output = tmp_path / "p1.json"
    brackets = {"schema_version": analysis.BRACKET_SCHEMA}
    protocol = {
        "schema_version": analysis.P1_PROTOCOL_SCHEMA,
        "protocol_sha256": "a" * 64,
    }
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        CLI,
        "select_p1_brackets",
        lambda _source: calls.append((None, None)) or brackets,
    )
    monkeypatch.setattr(CLI, "build_p1_protocol", lambda *_args, **_kwargs: protocol)
    base = [
        "build-p1",
        "--analysis",
        str(analysis_path),
        "--output",
        str(output),
    ]

    assert CLI.main(base) == 0
    assert calls == [(None, None)]
    capsys.readouterr()

    for extra in (
        ["--p0-analysis", str(analysis_path)],
        [
            "--p0-analysis",
            str(analysis_path),
            "--extension-analysis",
            str(analysis_path),
        ],
    ):
        other_output = tmp_path / f"rejected-{len(extra)}.json"
        arguments = [*base[:-1], str(other_output), *extra]
        assert CLI.main(arguments) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "v1 build-p1 does not accept combined trusted inputs" in captured.err
        assert not other_output.exists()


@pytest.mark.parametrize("command", ("select", "build-p1"))
def test_cli_rejects_resigned_combined_provenance_bypass(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
):
    from test_pilot_analysis import _combined_selector_document

    p0, extension_analysis, combined = _combined_selector_document()
    for field in (
        "source_p0_analysis_document_sha256",
        "source_extension_analysis_document_sha256",
        "p0_run_spec_sha256",
        "p0_progress_sha256",
        "extension_run_spec_sha256",
        "extension_progress_sha256",
        "p0_source_revision",
        "extension_source_revision",
        "observable_columns",
    ):
        combined.pop(field)
    unsigned = dict(combined)
    unsigned.pop("analysis_document_sha256")
    combined["analysis_document_sha256"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()
    for name, document in (
        ("p0", p0),
        ("extension", extension_analysis),
        ("combined", combined),
        ("protocol", {"schema_version": extension.EXTENSION_PROTOCOL_SCHEMA}),
    ):
        (tmp_path / f"{name}.json").write_bytes(_canonical_bytes(document))
    p0_root = tmp_path / "p0-root"
    p0_root.mkdir()
    extension_run_spec = tmp_path / "extension-root/run_spec.json"
    extension_run_spec.parent.mkdir()
    extension_run_spec.write_text("{}\n", encoding="utf-8")
    output = tmp_path / f"{command}.json"

    assert (
        CLI.main(
            [
                command,
                "--analysis",
                str(tmp_path / "combined.json"),
                "--p0-analysis",
                str(tmp_path / "p0.json"),
                "--extension-analysis",
                str(tmp_path / "extension.json"),
                "--p0-evidence-root",
                str(p0_root),
                "--extension-run-spec",
                str(extension_run_spec),
                "--extension-protocol",
                str(tmp_path / "protocol.json"),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "P0 source hashes or revision are not frozen" in captured.err
    assert not output.exists()
