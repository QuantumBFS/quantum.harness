from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from qcontrol.evidence import (
    REQUIRED_EVIDENCE_FILES,
    validate_deployment,
    validate_evidence_document,
    validate_evidence_directory,
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


def test_tracked_task10a_evidence_is_independently_schema_valid() -> None:
    hashes = validate_evidence_directory(ROOT / "evidence" / "task10a")

    assert set(hashes) == set(REQUIRED_EVIDENCE_FILES)
    assert all(len(value) == 64 for value in hashes.values())


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
    report = shutil.copy(ROOT / "REPORT.md", tmp_path / "REPORT.md")
    report_sha256 = hashlib.sha256(report.read_bytes()).hexdigest()
    evidence = shutil.copytree(
        ROOT / "evidence" / "task10a",
        tmp_path / "evidence" / "task10a",
    )
    evidence_revision = json.loads((evidence / "index.json").read_text())[
        "source_revision"
    ]
    evidence_index_sha256 = hashlib.sha256(
        (evidence / "index.json").read_bytes()
    ).hexdigest()
    archive = tmp_path / f"challenge-113-{REVISION[:7]}.tar.gz"
    archive.write_bytes(b"exact archive bytes")
    archive_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
    metadata = tmp_path.parent / f"{tmp_path.name}-deployment.json"
    _write_json(
        metadata,
        {
            "archive_name": archive.name,
            "archive_sha256": archive_sha256,
            "evidence_index_sha256": evidence_index_sha256,
            "report_sha256": report_sha256,
            "revision": REVISION,
            "schema_version": 1,
        },
    )

    validate_deployment(
        tmp_path,
        archive_path=archive,
        deployment_metadata_path=metadata,
        expected_revision=REVISION,
        expected_archive_sha256=archive_sha256,
        expected_evidence_revision=evidence_revision,
    )
    with pytest.raises(ValueError, match="revision"):
        validate_deployment(
            tmp_path,
            archive_path=archive,
            deployment_metadata_path=metadata,
            expected_revision="d" * 40,
            expected_archive_sha256=archive_sha256,
            expected_evidence_revision=evidence_revision,
        )
    with pytest.raises(ValueError, match="archive"):
        validate_deployment(
            tmp_path,
            archive_path=archive,
            deployment_metadata_path=metadata,
            expected_revision=REVISION,
            expected_archive_sha256="e" * 64,
            expected_evidence_revision=evidence_revision,
        )
    archive.write_bytes(b"mutated archive bytes")
    with pytest.raises(ValueError, match="archive bytes"):
        validate_deployment(
            tmp_path,
            archive_path=archive,
            deployment_metadata_path=metadata,
            expected_revision=REVISION,
            expected_archive_sha256=archive_sha256,
            expected_evidence_revision=evidence_revision,
        )
    archive.write_bytes(b"exact archive bytes")
    report.write_text("stale report\n")
    with pytest.raises(ValueError, match="report"):
        validate_deployment(
            tmp_path,
            archive_path=archive,
            deployment_metadata_path=metadata,
            expected_revision=REVISION,
            expected_archive_sha256=archive_sha256,
            expected_evidence_revision=evidence_revision,
        )


def test_evidence_rejects_coerced_types_and_nonfinite_values() -> None:
    calibration = json.loads(
        (ROOT / "evidence" / "task10a" / "calibration.json").read_text()
    )
    calibration["payload"]["cpu_count"] = True
    with pytest.raises(ValueError, match="JSON type"):
        validate_evidence_document(calibration)
    calibration["payload"]["cpu_count"] = 32
    calibration["payload"]["warm_query_seconds"] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        validate_evidence_document(calibration)


@pytest.mark.integration
def test_documented_clean_production_check_reaches_ready_gate(tmp_path) -> None:
    source = shutil.copytree(
        ROOT,
        tmp_path / "source",
        ignore=shutil.ignore_patterns(
            ".pytest_cache",
            ".venv",
            "__pycache__",
            "results",
        ),
    )
    commit_environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Challenge 113 Test",
        "GIT_AUTHOR_EMAIL": "challenge113@example.invalid",
        "GIT_COMMITTER_NAME": "Challenge 113 Test",
        "GIT_COMMITTER_EMAIL": "challenge113@example.invalid",
    }
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"],
        cwd=source,
        env=commit_environment,
        check=True,
    )
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        text=True,
    ).strip()
    archive = tmp_path / f"challenge-113-{revision[:7]}.tar.gz"
    archive.write_bytes(b"clean production check archive")
    archive_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
    evidence_revision = json.loads(
        (source / "evidence" / "task10a" / "index.json").read_text()
    )["source_revision"]
    metadata = tmp_path / "deployment.json"
    _write_json(
        metadata,
        {
            "archive_name": archive.name,
            "archive_sha256": archive_sha256,
            "evidence_index_sha256": hashlib.sha256(
                (source / "evidence" / "task10a" / "index.json").read_bytes()
            ).hexdigest(),
            "report_sha256": hashlib.sha256(
                (source / "REPORT.md").read_bytes()
            ).hexdigest(),
            "revision": revision,
            "schema_version": 1,
        },
    )
    result = subprocess.run(
        ["bash", "scripts/run_production.sh"],
        cwd=source,
        env={
            **os.environ,
            "CHALLENGE113_ACK_PRODUCTION": "1",
            "CHALLENGE113_ARCHIVE_PATH": str(archive),
            "CHALLENGE113_ARCHIVE_SHA256": archive_sha256,
            "CHALLENGE113_CHECK_ONLY": "1",
            "CHALLENGE113_DEPLOYMENT_METADATA": str(metadata),
            "CHALLENGE113_EVIDENCE_REVISION": evidence_revision,
            "CHALLENGE113_EXPECTED_REVISION": revision,
            "CHALLENGE113_JAX_PLATFORM": "cpu",
            "CHALLENGE113_PRODUCTION_OUTPUT": str(tmp_path / "production"),
        },
        text=True,
        capture_output=True,
        check=True,
    )

    assert '{"production_gate":"ready"}' in result.stdout
    assert (
        subprocess.check_output(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=source,
            text=True,
        )
        == ""
    )
    assert not (source / ".deployment.json").exists()


@pytest.mark.parametrize(
    "name",
    ["run_production.sh", "slurm_pilot.sh", "slurm_production_array.sh"],
)
def test_production_entrypoints_verify_deployment_metadata(name) -> None:
    script = (ROOT / "scripts" / name).read_text()

    assert "verify_deployment.py" in script
    assert "CHALLENGE113_ARCHIVE_SHA256" in script
    assert "CHALLENGE113_ARCHIVE_PATH" in script
    assert "CHALLENGE113_DEPLOYMENT_METADATA" in script
    assert "CHALLENGE113_EVIDENCE_REVISION" in script


def test_readme_clean_gate_supplies_every_required_variable() -> None:
    readme = (ROOT / "README.md").read_text()
    for name in (
        "CHALLENGE113_ACK_PRODUCTION",
        "CHALLENGE113_ARCHIVE_PATH",
        "CHALLENGE113_ARCHIVE_SHA256",
        "CHALLENGE113_CHECK_ONLY",
        "CHALLENGE113_DEPLOYMENT_METADATA",
        "CHALLENGE113_EVIDENCE_REVISION",
        "CHALLENGE113_EXPECTED_REVISION",
        "CHALLENGE113_JAX_PLATFORM",
        "CHALLENGE113_PRODUCTION_OUTPUT",
    ):
        assert f"export {name}=" in readme
    assert "dd16192953c130d738716238525760de73343e09" in readme
