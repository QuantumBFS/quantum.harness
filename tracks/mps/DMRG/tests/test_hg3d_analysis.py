from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

import spinglass3d.analysis as analysis_module
from scripts.hard_goal_analyze import (
    build_parser as build_analyze_parser,
    main as analyze_main,
)


TRACK_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE_PATHS = (
    "src/spinglass3d/analysis.py",
    "src/spinglass3d/statistics.py",
    "scripts/hard_goal_analyze.py",
)
from spinglass3d.analysis import (
    load_production_summary,
    run_stage8_analysis,
    write_stage8_analysis,
)


def _write_json(path: Path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _runtime_source_inventory() -> dict[str, str]:
    return {
        relative: hashlib.sha256((TRACK_ROOT / relative).read_bytes()).hexdigest()
        for relative in RUNTIME_SOURCE_PATHS
    }


def _sync_protocol(manifest: Path, protocol: dict[str, object]) -> None:
    manifest_payload = json.loads(manifest.read_text(encoding="ascii"))
    protocol_path = manifest.parent / manifest_payload["analysis_protocol"]["path"]
    manifest_payload["analysis_protocol"]["sha256"] = _write_json(
        protocol_path,
        protocol,
    )
    manifest_payload["frozen_source_inventory"] = protocol["source_inventory"]
    _write_json(manifest, manifest_payload)


def _production_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "production"
    protocol = {
        "schema_version": 1,
        "stage": "stage6",
        "variants": [
            {
                "l_min": 9,
                "temperature_window": [1.0, 1.2],
                "polynomial_order": 1,
                "parity": False,
                "parity_order": 0,
                "fixed_omega": 1.0,
                "fixed_omega_p": None,
            }
        ],
        "nonlinear_bounds": {
            "tc": [0.95, 1.25],
            "nu": [0.8, 5.0],
            "omega": [0.2, 2.5],
            "omega_p": [0.2, 3.0],
        },
        "bootstrap": {
            "seed": 808,
            "n_resamples": 6,
            "minimum_success_count": 2,
            "minimum_success_fraction": 0.33,
        },
        "source_inventory": _runtime_source_inventory(),
    }
    protocol_path = root / "stage6-analysis-protocol.json"
    protocol_hash = _write_json(protocol_path, protocol)
    summaries = []
    rng = np.random.default_rng(2026073227)
    temperatures = np.linspace(1.0, 1.2, 7)
    for length in (9, 12, 15, 18):
        x = (temperatures - 1.1) * length ** 0.5
        for sample in range(5):
            shared = rng.normal(0.0, 0.003)
            slope = rng.normal(0.0, 0.001)
            payload = {
                "schema_version": 1,
                "j_id": f"L{length}-J{sample}",
                "length": length,
                "temperatures": temperatures.tolist(),
                "observables": {
                    "xi_over_l": (
                        0.62 + 0.2 * x + length ** -1.0 * (0.3 - 0.04 * x)
                        + shared + slope * x
                    ).tolist(),
                    "binder": (
                        0.47 + 0.14 * x + length ** -1.0 * (-0.2 + 0.03 * x)
                        + 0.7 * shared - slope * x
                    ).tolist(),
                },
            }
            relative = f"summaries/L{length}-J{sample}.json"
            digest = _write_json(root / relative, payload)
            summaries.append({"path": relative, "sha256": digest})
    manifest = {
        "schema_version": 1,
        "stage": "stage7",
        "classification": "PASS",
        "analysis_protocol": {
            "path": "stage6-analysis-protocol.json",
            "sha256": protocol_hash,
        },
        "frozen_source_inventory": protocol["source_inventory"],
        "summaries": summaries,
    }
    manifest_path = root / "production-summary.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def test_loader_binds_protocol_variants_bounds_sources_and_summaries(tmp_path: Path) -> None:
    manifest = _production_fixture(tmp_path)
    loaded = load_production_summary(manifest)
    assert len(loaded.records) == 20
    assert loaded.protocol_sha256 == json.loads(manifest.read_text())["analysis_protocol"][
        "sha256"
    ]
    assert len(loaded.variants) == 1
    assert loaded.variants[0].l_min == 9
    assert loaded.nonlinear_bounds.tc == (0.95, 1.25)
    assert tuple(loaded.source_inventory) == tuple(sorted(RUNTIME_SOURCE_PATHS))

    manifest_payload = json.loads(manifest.read_text(encoding="ascii"))
    protocol_path = manifest.parent / manifest_payload["analysis_protocol"]["path"]
    protocol = json.loads(protocol_path.read_text(encoding="ascii"))
    protocol["source_inventory"][RUNTIME_SOURCE_PATHS[0]] = "0" * 64
    _sync_protocol(manifest, protocol)
    with pytest.raises(ValueError, match="runtime source hash"):
        load_production_summary(manifest)


@pytest.mark.parametrize(
    ("target", "message"),
    (("protocol", "analysis protocol hash"), ("summary", "summary file.*hash")),
)
def test_loader_rejects_tampered_protocol_or_summary_bytes(
    tmp_path: Path,
    target: str,
    message: str,
) -> None:
    manifest = _production_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    descriptor = (
        payload["analysis_protocol"]
        if target == "protocol"
        else payload["summaries"][0]
    )
    artifact = manifest.parent / descriptor["path"]
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(ValueError, match=message):
        load_production_summary(manifest)


def test_loader_rejects_a_variant_that_would_be_silently_normalized(
    tmp_path: Path,
) -> None:
    manifest = _production_fixture(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="ascii"))
    protocol_path = manifest.parent / manifest_payload["analysis_protocol"]["path"]
    protocol = json.loads(protocol_path.read_text(encoding="ascii"))
    protocol["variants"][0]["parity_order"] = 1
    _sync_protocol(manifest, protocol)
    with pytest.raises(ValueError, match="parity_order"):
        load_production_summary(manifest)


@pytest.mark.parametrize(
    ("target", "bad_value"),
    (
        ("temperature", "1.0"),
        ("observable", True),
        pytest.param("temperature", 10**400, id="oversized-integer"),
    ),
)
def test_loader_rejects_non_numeric_or_boolean_stage7_arrays(
    tmp_path: Path,
    target: str,
    bad_value: object,
) -> None:
    manifest = _production_fixture(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="ascii"))
    descriptor = manifest_payload["summaries"][0]
    summary_path = manifest.parent / descriptor["path"]
    summary = json.loads(summary_path.read_text(encoding="ascii"))
    if target == "temperature":
        summary["temperatures"][0] = bad_value
    else:
        summary["observables"]["xi_over_l"][0] = bad_value
    descriptor["sha256"] = _write_json(summary_path, summary)
    _write_json(manifest, manifest_payload)
    with pytest.raises(ValueError, match="finite JSON numbers"):
        load_production_summary(manifest)


def test_stage8_builds_complete_fit_table_and_interval_compatibility(tmp_path: Path) -> None:
    manifest = _production_fixture(tmp_path)
    loaded = load_production_summary(manifest)
    result = run_stage8_analysis(loaded)
    assert tuple(result.fit_table) == ("xi_over_l", "binder", "joint")
    assert result.fit_table["joint"].fit.observable_names == (
        "xi_over_l",
        "binder",
    )
    assert set(result.interval_compatibility) == {
        "xi_vs_binder",
        "xi_vs_joint",
        "binder_vs_joint",
        "all_primary",
    }
    assert tuple(result.crossings) == ("xi_over_l", "binder")
    assert result.protocol_sha256 == loaded.protocol_sha256
    reference = result.fit_table["xi_over_l"]
    replayed = (
        result.fit_table["binder"],
        result.fit_table["joint"],
        result.crossings["xi_over_l"],
        result.crossings["binder"],
    )
    for item in replayed:
        assert item.record_axes == reference.record_axes
        for length, matrix in reference.resample_indices.items():
            np.testing.assert_array_equal(item.resample_indices[length], matrix)
    output = tmp_path / "analysis" / "analysis.json"
    write_stage8_analysis(result, output)
    payload = json.loads(output.read_text(encoding="ascii"))
    assert tuple(payload["fit_table"]) == ("xi_over_l", "binder", "joint")
    assert payload["ordered_variants"][0]["l_min"] == 9
    assert payload["production_summary_sha256"] == loaded.production_summary_sha256


def test_analysis_cli_parser_is_separate_delegate_entrypoint(tmp_path: Path) -> None:
    args = build_analyze_parser().parse_args(
        [
            "--production-summary",
            str(tmp_path / "production-summary.json"),
            "--output",
            str(tmp_path / "analysis"),
        ]
    )
    assert args.production_summary.name == "production-summary.json"
    assert args.output.name == "analysis"


def test_analysis_cli_fails_closed_on_tampered_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest = _production_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    protocol_path = manifest.parent / payload["analysis_protocol"]["path"]
    protocol = json.loads(protocol_path.read_text(encoding="ascii"))
    protocol["source_inventory"][RUNTIME_SOURCE_PATHS[0]] = "0" * 64
    _sync_protocol(manifest, protocol)
    output = tmp_path / "analysis"
    assert analyze_main(
        ["--production-summary", str(manifest), "--output", str(output)]
    ) == 2
    assert "failed closed" in capsys.readouterr().err
    assert not output.exists()


def test_analysis_writer_never_clobbers_a_competing_publisher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = run_stage8_analysis(load_production_summary(_production_fixture(tmp_path)))
    output = tmp_path / "analysis" / "analysis.json"
    original_replace = os.replace
    original_link = os.link

    def racing_replace(source: str | Path, destination: str | Path) -> None:
        Path(destination).write_bytes(b"competitor\n")
        original_replace(source, destination)

    def racing_link(source: str | Path, destination: str | Path) -> None:
        Path(destination).write_bytes(b"competitor\n")
        original_link(source, destination)

    monkeypatch.setattr(analysis_module.os, "replace", racing_replace)
    monkeypatch.setattr(analysis_module.os, "link", racing_link)
    with pytest.raises(FileExistsError):
        write_stage8_analysis(result, output)
    assert output.read_bytes() == b"competitor\n"
