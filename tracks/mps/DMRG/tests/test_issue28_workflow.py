from __future__ import annotations

import json
from pathlib import Path

import pytest

from vmcrg_ref.artifacts import atomic_write_json, sha256_file
from vmcrg_ref.issue28_protocol import load_issue28_protocol
from vmcrg_ref.issue28_workflow import (
    STAGE_ORDER,
    create_stage_manifest,
    read_verified_stage_manifest,
    verify_stage_dependencies,
)


PROTOCOL_PATH = Path("config/issue28_easy_v1.json")


def _write_stage(
    root: Path,
    stage: str,
    *,
    classification: str = "EASY_GOAL_SUCCESS",
    predecessor_sha256: str | None = None,
) -> dict[str, object]:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    stage_root = root / stage
    stage_root.mkdir(parents=True)
    output = stage_root / "result.json"
    atomic_write_json(output, {"stage": stage, "value": 1})
    manifest = create_stage_manifest(
        stage=stage,
        protocol=protocol,
        classification=classification,
        reason="TEST_FIXTURE",
        output_root=stage_root,
        outputs=("result.json",),
        correctness_gates={"fixture": "PASS"},
        scientific_gates={"fixture": "PASS"},
        resources={"backend": "test"},
        predecessor_manifest_sha256=(
            () if predecessor_sha256 is None else (predecessor_sha256,)
        ),
    )
    atomic_write_json(stage_root / "manifest.json", manifest)
    return {
        **manifest,
        "manifest_sha256": sha256_file(stage_root / "manifest.json"),
    }


def test_stage_order_is_frozen() -> None:
    assert STAGE_ORDER == ("B0", "N0", "N1", "N2", "N3", "N4", "N5")


def test_n1_refuses_to_run_without_passing_b0_and_n0(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    with pytest.raises(ValueError, match="B0"):
        verify_stage_dependencies("N1", tmp_path, protocol)

    b0 = _write_stage(tmp_path, "B0")
    with pytest.raises(ValueError, match="N0"):
        verify_stage_dependencies("N1", tmp_path, protocol)

    n0 = _write_stage(
        tmp_path,
        "N0",
        predecessor_sha256=str(b0["manifest_sha256"]),
    )
    dependencies = verify_stage_dependencies("N1", tmp_path, protocol)
    assert [item["stage"] for item in dependencies] == ["B0", "N0"]
    assert dependencies[-1]["manifest_sha256"] == n0["manifest_sha256"]


@pytest.mark.parametrize("classification", ["CORRECTNESS_FAILURE", "PROTOCOL_FAILURE"])
def test_hard_failure_blocks_dependent_compute(
    tmp_path: Path,
    classification: str,
) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    _write_stage(tmp_path, "B0", classification=classification)
    with pytest.raises(ValueError, match=classification):
        verify_stage_dependencies("N0", tmp_path, protocol)


def test_scientific_failure_continues_to_n5_report(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    previous: str | None = None
    for stage in STAGE_ORDER[:-1]:
        record = _write_stage(
            tmp_path,
            stage,
            classification=("SCIENTIFIC_NEGATIVE" if stage == "N4" else "EASY_GOAL_SUCCESS"),
            predecessor_sha256=previous,
        )
        previous = str(record["manifest_sha256"])
    dependencies = verify_stage_dependencies("N5", tmp_path, protocol)
    assert dependencies[-1]["classification"] == "SCIENTIFIC_NEGATIVE"


def test_manifest_verification_rejects_modified_output(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    _write_stage(tmp_path, "B0")
    (tmp_path / "B0" / "result.json").write_text("{}\n", encoding="ascii")
    with pytest.raises(ValueError, match="output hash mismatch"):
        read_verified_stage_manifest(tmp_path / "B0" / "manifest.json", protocol)


def test_manifest_verification_rejects_protocol_mismatch(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    _write_stage(tmp_path, "B0")
    path = tmp_path / "B0" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="ascii"))
    manifest["protocol_sha256"] = "0" * 64
    atomic_write_json(path, manifest)
    with pytest.raises(ValueError, match="protocol hash"):
        read_verified_stage_manifest(path, protocol)


def test_manifest_requires_complete_audit_fields(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    stage_root = tmp_path / "B0"
    stage_root.mkdir()
    atomic_write_json(stage_root / "result.json", {"ok": True})
    manifest = create_stage_manifest(
        stage="B0",
        protocol=protocol,
        classification="SCIENTIFIC_NEGATIVE",
        reason="SMOKE_ONLY",
        output_root=stage_root,
        outputs=("result.json",),
        correctness_gates={"delta": "PASS"},
        scientific_gates={"power": "INSUFFICIENT"},
        resources={"backend": "local", "wall_seconds": 1.0},
    )
    assert manifest["physical"] == {
        "length": 45,
        "coupling": 0.436,
        "block_size": 3,
        "boundary": "periodic",
        "reference_distribution": "uniform_independent_ising_2d",
    }
    assert manifest["basis_sha256"] == protocol.operator_basis_sha256
    assert manifest["pure_linear_bias"] == [0.0] * 13
    assert manifest["protocol_sha256"] == protocol.protocol_sha256
    assert len(manifest["code_sha256"]) == 64
    assert manifest["correctness_gates"] == {"delta": "PASS"}
    assert manifest["scientific_gates"] == {"power": "INSUFFICIENT"}
    assert manifest["outputs"]["result.json"] == sha256_file(stage_root / "result.json")
