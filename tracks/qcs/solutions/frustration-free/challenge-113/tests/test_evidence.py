from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from qcontrol.evidence import (
    validate_deployment,
)


ROOT = Path(__file__).parents[1]
REVISION = "a" * 40
SHA256 = "b" * 64


def _write_json(path: Path, payload: object) -> str:
    data = (
        json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def test_calibration_uses_canonical_representative_model_seed() -> None:
    path = ROOT / "scripts" / "calibrate_pilot.py"
    spec = importlib.util.spec_from_file_location("calibrate_pilot", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    config = module.representative_config()

    assert config.model_seed == 5
    assert config.trial_seed == 0
    assert config.device.perturbation_seed == 0
    assert config.system.parameter_count == 80
    assert config.search.dimension == 4


def test_slurm_pilot_decouples_model_and_statistical_seeds() -> None:
    script = (ROOT / "scripts" / "slurm_pilot.sh").read_text()

    assert "--model-seed 5" in script
    assert "--perturbation-seed 0" in script
    assert "--seed 0" in script


def test_calibration_writer_creates_canonical_nested_output(tmp_path) -> None:
    path = ROOT / "scripts" / "calibrate_pilot.py"
    spec = importlib.util.spec_from_file_location("calibrate_pilot_writer", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "nested" / "calibration.json"

    module.write_json(output, {"z": 2, "a": 1})

    assert output.read_bytes() == b'{"a":1,"z":2}\n'


def test_deployment_rejects_stale_revision_archive_and_report(tmp_path) -> None:
    report = tmp_path / "REPORT.md"
    report.write_text("measured report\n")
    report_sha256 = hashlib.sha256(report.read_bytes()).hexdigest()
    evidence_revision = "c" * 40
    document = {
        "evidence_type": "report_metadata",
        "inputs": {"uv_lock": SHA256},
        "payload": {"report_sha256": report_sha256},
        "schema_version": 1,
        "source_revision": evidence_revision,
    }
    document_sha256 = _write_json(
        tmp_path / "evidence" / "task10a" / "report_metadata.json",
        document,
    )
    _write_json(
        tmp_path / "evidence" / "task10a" / "index.json",
        {
            "documents": {"report_metadata.json": document_sha256},
            "schema_version": 1,
            "source_revision": evidence_revision,
        },
    )
    _write_json(
        tmp_path / ".deployment.json",
        {
            "archive_name": "challenge-113.tar.gz",
            "archive_sha256": SHA256,
            "revision": REVISION,
            "schema_version": 1,
        },
    )

    validate_deployment(
        tmp_path,
        expected_revision=REVISION,
        expected_archive_sha256=SHA256,
        expected_evidence_revision=evidence_revision,
    )
    with pytest.raises(ValueError, match="revision"):
        validate_deployment(
            tmp_path,
            expected_revision="d" * 40,
            expected_archive_sha256=SHA256,
            expected_evidence_revision=evidence_revision,
        )
    with pytest.raises(ValueError, match="archive"):
        validate_deployment(
            tmp_path,
            expected_revision=REVISION,
            expected_archive_sha256="e" * 64,
            expected_evidence_revision=evidence_revision,
        )
    report.write_text("stale report\n")
    with pytest.raises(ValueError, match="report"):
        validate_deployment(
            tmp_path,
            expected_revision=REVISION,
            expected_archive_sha256=SHA256,
            expected_evidence_revision=evidence_revision,
        )


@pytest.mark.parametrize(
    "name",
    ["run_production.sh", "slurm_pilot.sh", "slurm_production_array.sh"],
)
def test_production_entrypoints_verify_deployment_metadata(name) -> None:
    script = (ROOT / "scripts" / name).read_text()

    assert "verify_deployment.py" in script
    assert "CHALLENGE113_ARCHIVE_SHA256" in script
    assert "CHALLENGE113_EVIDENCE_REVISION" in script
