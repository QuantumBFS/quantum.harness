import json
import os
from pathlib import Path

import pytest

from scalable_v1.audit import freeze_manifest, sha256_file, verify_manifest
from scalable_v1.protocol import DEFAULT_PROTOCOL_PATH, load_protocol


def make_files(
    tmp_path: Path, candidate_source: str = "def amplitude(state):\n    return 1.0\n"
) -> tuple[Path, Path, Path, dict[str, Path]]:
    project_root = tmp_path / "project"
    run_dir = project_root / "run"
    run_dir.mkdir(parents=True)
    candidate = project_root / "candidate.py"
    candidate.write_text(candidate_source, encoding="utf-8")
    artifacts = {
        "checkpoint": run_dir / "checkpoint.bin",
        "optimizer_state": run_dir / "optimizer.bin",
        "training_log": run_dir / "training.log",
    }
    for role, path in artifacts.items():
        path.write_bytes(role.encode("utf-8"))
    return project_root, run_dir, candidate, artifacts


def test_clean_manifest_freezes_and_verifies_candidate_artifacts(tmp_path: Path) -> None:
    project_root, run_dir, candidate, artifacts = make_files(tmp_path)
    protocol = load_protocol()

    manifest_path = freeze_manifest(
        run_dir=run_dir,
        project_root=project_root,
        route="occupation_autoregressive",
        attempt="scalable-v1-s01-a01",
        protocol=protocol,
        selected_update=2048,
        training_seed=848,
        source_files=[candidate],
        artifact_files=artifacts,
    )

    manifest_bytes = manifest_path.read_bytes()
    assert manifest_bytes.endswith(b"}\n")
    assert not manifest_bytes.endswith(b"\r\n")
    assert b"NaN" not in manifest_bytes
    assert b"Infinity" not in manifest_bytes
    payload = json.loads(manifest_bytes.decode("utf-8"))
    assert payload["schema_version"] == "challenge-15-frozen-manifest-v1"
    assert payload["route"] == "occupation_autoregressive"
    assert payload["attempt"] == "scalable-v1-s01-a01"
    assert payload["selected_capacity"] == {
        "hidden_width": 128,
        "hidden_layers": 2,
    }
    assert payload["checkpoint_policy"] == "final_update"
    assert payload["human_blind"] is False
    assert payload["oracle_accesses"] == []
    assert len(payload["source_files"]) == 1
    assert {item["role"] for item in payload["artifacts"]} == set(artifacts)

    result = verify_manifest(
        manifest_path,
        project_root=project_root,
        protocol=protocol,
        expected_training_seed=848,
    )
    assert result.valid
    assert result.issues == ()
    assert result.manifest_sha256 == sha256_file(manifest_path)
    assert result.artifact_bytes == sum(path.stat().st_size for path in artifacts.values())


def test_freeze_manifest_preserves_old_target_when_atomic_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, run_dir, candidate, artifacts = make_files(tmp_path)
    manifest_path = run_dir / "training-manifest.json"
    manifest_path.write_bytes(b"old")
    original_entries = {path.name for path in run_dir.iterdir()}

    def fail_replace(source: object, target: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        freeze_manifest(
            run_dir=run_dir,
            project_root=project_root,
            route="occupation_autoregressive",
            attempt="scalable-v1-s01-a01",
            protocol=load_protocol(),
            selected_update=2048,
            training_seed=848,
            source_files=[candidate],
            artifact_files=artifacts,
        )

    assert manifest_path.read_bytes() == b"old"
    assert {path.name for path in run_dir.iterdir()} == original_entries


def test_forbidden_candidate_import_and_artifact_tamper_are_rejected(
    tmp_path: Path,
) -> None:
    project_root, run_dir, candidate, artifacts = make_files(
        tmp_path,
        "from benchmark_v0.fock_ed import fixed_m_basis\n",
    )
    protocol = load_protocol()
    manifest_path = freeze_manifest(
        run_dir=run_dir,
        project_root=project_root,
        route="occupation_autoregressive",
        attempt="scalable-v1-s01-a01",
        protocol=protocol,
        selected_update=2048,
        training_seed=848,
        source_files=[candidate],
        artifact_files=artifacts,
    )

    forbidden = verify_manifest(
        manifest_path, project_root=project_root, protocol=protocol
    )
    assert not forbidden.valid
    assert any("benchmark_v0.fock_ed" in issue for issue in forbidden.issues)

    artifacts["checkpoint"].write_bytes(b"changed")
    tampered = verify_manifest(
        manifest_path, project_root=project_root, protocol=protocol
    )
    assert not tampered.valid
    assert any("artifact hash" in issue for issue in tampered.issues)


def test_manifest_rejects_a_later_valid_protocol_snapshot(tmp_path: Path) -> None:
    project_root, run_dir, candidate, artifacts = make_files(tmp_path)
    original_protocol = load_protocol()
    manifest_path = freeze_manifest(
        run_dir=run_dir,
        project_root=project_root,
        route="occupation_autoregressive",
        attempt="scalable-v1-s01-a01",
        protocol=original_protocol,
        selected_update=2048,
        training_seed=848,
        source_files=[candidate],
        artifact_files=artifacts,
    )
    changed_data = json.loads(DEFAULT_PROTOCOL_PATH.read_text(encoding="utf-8"))
    changed_data["training"]["optimizer_updates"] = 1024
    changed_data["training"]["local_energy_evaluations_per_sector"] = 524288
    changed_path = tmp_path / "changed-protocol.json"
    changed_path.write_text(json.dumps(changed_data), encoding="utf-8")
    changed_protocol = load_protocol(changed_path)

    result = verify_manifest(
        manifest_path, project_root=project_root, protocol=changed_protocol
    )
    assert not result.valid
    assert "protocol hash mismatch" in result.issues
