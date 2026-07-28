from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
import types
from typing import Any

import numpy as np
import pytest

from scalable_v1.audit import freeze_manifest
from scalable_v1.contracts import (
    ConstructionCertificate,
    ResourceMetrics,
    SampleBatch,
)
from scalable_v1.evaluator import (
    FINAL_GATE_NAMES,
    collect_evidence,
    evaluate_candidate,
    validate_run_record,
    write_json_report,
)
from scalable_v1.protocol import ProtocolConfig, load_protocol
from run_scalable_evaluator import load_factory, main


@dataclass
class FakeState:
    label: str
    l: int
    m: int
    energy: float
    l2: float
    sample_calls: list[tuple[int, int]] = field(default_factory=list, init=False)

    def sample(self, n_samples: int, seed: int) -> SampleBatch:
        self.sample_calls.append((n_samples, seed))
        return SampleBatch(np.arange(n_samples), n_samples, 1024, seed)

    def logpsi(self, config_batch: Any) -> np.ndarray:
        return np.zeros(len(config_batch), dtype=complex)

    def local_energy(self, config_batch: Any) -> np.ndarray:
        return np.full(len(config_batch), self.energy, dtype=complex)

    def local_l2(self, config_batch: Any) -> np.ndarray:
        return np.full(len(config_batch), self.l2, dtype=complex)


class FakeCandidate:
    name = "synthetic"
    family = "contract-test"

    def __init__(self) -> None:
        self.ground = FakeState("ground", 0, 0, 1.0, 0.0)
        self.tower = {
            m: FakeState(f"l2_m{m}", 2, m, 1.1, 6.0)
            for m in range(-2, 3)
        }

    def ground_state(self) -> FakeState:
        return self.ground

    def generate_multiplet(self) -> dict[int, FakeState]:
        return dict(self.tower)

    def construction_certificate(self) -> ConstructionCertificate:
        return ConstructionCertificate(True, True, True, 100, "synthetic")

    def resource_metrics(self) -> ResourceMetrics:
        return ResourceMetrics(
            "local",
            1.0e-6,
            1024,
            None,
            512,
            100,
            50.0,
            True,
            1.5,
            1.2,
            "cpu:test",
        )


class FakeDiagnostics:
    def evaluate(
        self,
        candidate: FakeCandidate,
        *,
        seed: int,
        swap_probes: int,
        rotation_probes: int,
    ) -> dict[str, float]:
        assert candidate.name == "synthetic"
        assert seed == 3848
        assert swap_probes == 64
        assert rotation_probes == 32
        return {
            "lll_residual": 0.0,
            "particle_swap_residual": 0.0,
            "finite_rotation_residual": 0.0,
            "tower_ladder_residual": 0.0,
        }


def make_frozen_run(
    tmp_path: Path, *, tamper_checkpoint: bool = False
) -> tuple[Path, Path, Path, Path, ProtocolConfig]:
    project_root = tmp_path / "project"
    run_dir = project_root / "run"
    run_dir.mkdir(parents=True)
    source = project_root / "candidate.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    artifacts = {
        "checkpoint": run_dir / "checkpoint.bin",
        "optimizer_state": run_dir / "optimizer.bin",
        "training_log": run_dir / "training.log",
    }
    for role, path in artifacts.items():
        path.write_bytes(role.encode("utf-8"))

    oracle_path = tmp_path / "oracle.json"
    oracle_path.write_text(
        json.dumps(
            {
                "ground_energy": 1.0,
                "l2_by_m": {str(m): 1.1 for m in range(-2, 3)},
            }
        ),
        encoding="utf-8",
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
        source_files=[source],
        artifact_files=artifacts,
    )
    if tamper_checkpoint:
        artifacts["checkpoint"].write_bytes(b"tampered")
    return project_root, run_dir, manifest_path, oracle_path, protocol


def test_collect_evidence_uses_the_frozen_sampling_schedule() -> None:
    protocol = load_protocol()
    candidate = FakeCandidate()

    evidence = collect_evidence(
        candidate=candidate,
        diagnostics=FakeDiagnostics(),
        protocol=protocol,
        training_seed=848,
    )

    states = [candidate.ground, *(candidate.tower[m] for m in range(-2, 3))]
    for state_index, state in enumerate(states):
        assert state.sample_calls == [
            (8192, 848 + 1000 * state_index + chain)
            for chain in range(8)
        ]
    assert evidence["construction"] == {
        "strict_lll": True,
        "antisymmetric": True,
        "scalable": True,
        "trainable_parameters": 100,
        "statement": "synthetic",
    }
    assert set(evidence["statistics"]["l2_by_m"]) == {
        "-2",
        "-1",
        "0",
        "1",
        "2",
    }
    assert evidence["statistics"]["ground"]["energy"]["mean"] == 1.0
    assert evidence["statistics"]["ground"]["l2"]["mean"] == 0.0
    assert evidence["statistics"]["l2_by_m"]["2"]["energy"]["mean"] == pytest.approx(
        1.1
    )
    assert evidence["statistics"]["l2_by_m"]["2"]["l2"]["mean"] == 6.0
    assert evidence["statistics"]["combined_l2"] == {
        "mean": pytest.approx(1.1),
        "standard_error": 0.0,
    }
    assert evidence["statistics"]["gap"] == {
        "mean": pytest.approx(0.1),
        "standard_error": 0.0,
    }
    assert evidence["resources"]["effective_sample_size"] == 65536.0
    assert evidence["resources"]["device_fingerprint"] == "cpu:test"


@pytest.mark.parametrize(
    "tower",
    [
        {m: FakeState(str(m), 2, m, 1.1, 6.0) for m in range(-2, 2)},
        {str(m): FakeState(str(m), 2, m, 1.1, 6.0) for m in range(-2, 3)},
    ],
)
def test_collect_evidence_rejects_a_nonexact_integer_multiplet(
    tower: dict[Any, FakeState],
) -> None:
    candidate = FakeCandidate()
    candidate.tower = tower

    with pytest.raises(ValueError, match="exact integer M=-2..2 multiplet"):
        collect_evidence(
            candidate=candidate,
            diagnostics=FakeDiagnostics(),
            protocol=load_protocol(),
            training_seed=848,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda candidate: setattr(candidate.ground, "l", 2), "ground state"),
        (lambda candidate: setattr(candidate.ground, "m", 1), "ground state"),
        (lambda candidate: setattr(candidate.ground, "m", False), "ground state"),
        (lambda candidate: setattr(candidate.tower[2], "m", 1), "L=2 state"),
        (lambda candidate: setattr(candidate.tower[1], "m", True), "L=2 state"),
        (lambda candidate: setattr(candidate.tower[-1], "l", 1), "L=2 state"),
        (lambda candidate: setattr(candidate.ground, "label", ""), "labels"),
        (lambda candidate: setattr(candidate.tower[0], "label", ""), "labels"),
        (
            lambda candidate: setattr(
                candidate.tower[-2], "label", candidate.ground.label
            ),
            "labels",
        ),
    ],
)
def test_collect_evidence_rejects_invalid_state_metadata(
    mutation: Any, message: str
) -> None:
    candidate = FakeCandidate()
    mutation(candidate)

    with pytest.raises(ValueError, match=message):
        collect_evidence(
            candidate=candidate,
            diagnostics=FakeDiagnostics(),
            protocol=load_protocol(),
            training_seed=848,
        )


def test_collect_evidence_rejects_an_invalid_sample_batch() -> None:
    candidate = FakeCandidate()

    def bad_sample(n_samples: int, seed: int) -> SampleBatch:
        return SampleBatch(np.arange(n_samples), n_samples, 0, seed)

    candidate.ground.sample = bad_sample  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="frozen burn-in"):
        collect_evidence(
            candidate=candidate,
            diagnostics=FakeDiagnostics(),
            protocol=load_protocol(),
            training_seed=848,
        )


def test_clean_evaluation_reveals_only_after_audit_and_builds_exact_schema(
    tmp_path: Path,
) -> None:
    project_root, _, manifest_path, oracle_path, protocol = make_frozen_run(tmp_path)
    oracle_calls: list[str] = []
    progress: list[str] = []

    def recording_oracle_loader(raw: str) -> dict[str, Any]:
        oracle_calls.append("oracle")
        return json.loads(raw)

    record = evaluate_candidate(
        candidate=FakeCandidate(),
        diagnostics=FakeDiagnostics(),
        protocol=protocol,
        manifest_path=manifest_path,
        project_root=project_root,
        oracle_path=oracle_path,
        training_seed=848,
        oracle_loader=recording_oracle_loader,
        progress=progress.append,
    )

    assert oracle_calls == ["oracle"]
    assert len(progress) == 2
    assert progress[0].startswith("audit:")
    assert progress[1].startswith("reveal:")
    assert set(record) == {
        "schema_version",
        "protocol_sha256",
        "system",
        "candidate",
        "training_seed",
        "blindness",
        "construction",
        "statistics",
        "diagnostics",
        "resources",
        "gates",
        "audit",
        "ed_comparison",
    }
    assert record["schema_version"] == "challenge-15-scalable-v1.0"
    assert record["protocol_sha256"] == protocol.sha256
    assert record["system"] == dict(protocol.physics)
    assert record["candidate"] == {
        "name": "synthetic",
        "family": "contract-test",
    }
    assert record["training_seed"] == 848
    assert record["blindness"] == {
        "human_blind": False,
        "oracle_isolated": True,
    }
    assert set(record["gates"]) == set(FINAL_GATE_NAMES)
    assert len(record["gates"]) == 13
    assert all(value is True for value in record["gates"].values())
    assert record["resources"]["wall_seconds"] > 0.0
    assert record["resources"]["peak_rss_bytes"] >= 1024
    assert record["resources"]["checkpoint_bytes"] >= 512
    assert record["resources"]["effective_sample_size"] == 65536.0
    assert record["resources"]["ess_per_second"] > 0.0
    assert validate_run_record(record) is None


def test_tampered_manifest_stops_before_collection_or_oracle_read(
    tmp_path: Path,
) -> None:
    project_root, _, manifest_path, _, protocol = make_frozen_run(
        tmp_path, tamper_checkpoint=True
    )
    candidate = FakeCandidate()
    oracle_calls: list[str] = []

    def recording_oracle_loader(raw: str) -> dict[str, Any]:
        oracle_calls.append("oracle")
        return json.loads(raw)

    with pytest.raises(ValueError, match="manifest audit failed"):
        evaluate_candidate(
            candidate=candidate,
            diagnostics=FakeDiagnostics(),
            protocol=protocol,
            manifest_path=manifest_path,
            project_root=project_root,
            oracle_path=tmp_path / "missing-oracle.json",
            training_seed=848,
            oracle_loader=recording_oracle_loader,
        )

    assert candidate.ground.sample_calls == []
    assert oracle_calls == []


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda record: record.update(schema_version="wrong"), "schema mismatch"),
        (lambda record: record["gates"].pop("lll_valid"), "gate set mismatch"),
        (lambda record: record["statistics"]["l2_by_m"].pop("2"), "M set mismatch"),
        (
            lambda record: record.update(
                blindness={"human_blind": False, "oracle_isolated": False}
            ),
            "blindness mismatch",
        ),
    ],
)
def test_validate_run_record_rejects_schema_drift(
    tmp_path: Path, mutation: Any, message: str
) -> None:
    project_root, _, manifest_path, oracle_path, protocol = make_frozen_run(tmp_path)
    record = evaluate_candidate(
        candidate=FakeCandidate(),
        diagnostics=FakeDiagnostics(),
        protocol=protocol,
        manifest_path=manifest_path,
        project_root=project_root,
        oracle_path=oracle_path,
        training_seed=848,
    )
    changed = copy.deepcopy(record)
    mutation(changed)

    with pytest.raises(ValueError, match=message):
        validate_run_record(changed)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda record: record["gates"].__setitem__("lll_valid", "true"),
            "gate values must be booleans",
        ),
        (
            lambda record: record["gates"].__setitem__("lll_valid", 1),
            "gate values must be booleans",
        ),
        (
            lambda record: record["gates"].__setitem__("lll_valid", False),
            "scalable_v1_pass semantics",
        ),
        (
            lambda record: record["gates"].__setitem__(
                "scalable_v1_pass", False
            ),
            "scalable_v1_pass semantics",
        ),
    ],
)
def test_validate_run_record_rejects_invalid_gate_values_and_semantics(
    tmp_path: Path, mutation: Any, message: str
) -> None:
    project_root, _, manifest_path, oracle_path, protocol = make_frozen_run(tmp_path)
    record = evaluate_candidate(
        candidate=FakeCandidate(),
        diagnostics=FakeDiagnostics(),
        protocol=protocol,
        manifest_path=manifest_path,
        project_root=project_root,
        oracle_path=oracle_path,
        training_seed=848,
    )
    changed = copy.deepcopy(record)
    mutation(changed)

    with pytest.raises(ValueError, match=message):
        validate_run_record(changed)


def test_write_json_report_is_strict_and_restorable(tmp_path: Path) -> None:
    project_root, _, manifest_path, oracle_path, protocol = make_frozen_run(tmp_path)
    record = evaluate_candidate(
        candidate=FakeCandidate(),
        diagnostics=FakeDiagnostics(),
        protocol=protocol,
        manifest_path=manifest_path,
        project_root=project_root,
        oracle_path=oracle_path,
        training_seed=848,
    )
    output = tmp_path / "nested" / "report.json"

    assert write_json_report(record, output) == output
    assert json.loads(output.read_text(encoding="utf-8")) == record
    assert output.read_bytes().endswith(b"\n")

    invalid = copy.deepcopy(record)
    invalid["resources"]["wall_seconds"] = float("nan")
    with pytest.raises(ValueError):
        write_json_report(invalid, tmp_path / "invalid.json")


def test_write_json_report_preserves_old_target_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, _, manifest_path, oracle_path, protocol = make_frozen_run(tmp_path)
    record = evaluate_candidate(
        candidate=FakeCandidate(),
        diagnostics=FakeDiagnostics(),
        protocol=protocol,
        manifest_path=manifest_path,
        project_root=project_root,
        oracle_path=oracle_path,
        training_seed=848,
    )
    output = tmp_path / "report.json"
    output.write_text("old report\n", encoding="utf-8")
    original_entries = set(tmp_path.iterdir())

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic replace failure"):
        write_json_report(record, output)

    assert output.read_text(encoding="utf-8") == "old report\n"
    assert set(tmp_path.iterdir()) == original_entries


def test_cli_roundtrip_with_an_in_memory_synthetic_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, _, manifest_path, oracle_path, protocol = make_frozen_run(tmp_path)
    module = types.ModuleType("synthetic_scalable_candidate")
    factory_calls: list[tuple[str, int]] = []

    def factory(
        received_protocol: ProtocolConfig, seed: int
    ) -> tuple[FakeCandidate, FakeDiagnostics]:
        factory_calls.append((received_protocol.sha256, seed))
        return FakeCandidate(), FakeDiagnostics()

    module.factory = factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    output = tmp_path / "cli" / "report.json"

    exit_code = main(
        [
            "--candidate",
            "synthetic_scalable_candidate:factory",
            "--manifest",
            str(manifest_path),
            "--oracle",
            str(oracle_path),
            "--output",
            str(output),
            "--project-root",
            str(project_root),
            "--training-seed",
            "848",
        ]
    )

    restored = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert factory_calls == [(protocol.sha256, 848)]
    assert restored["schema_version"] == "challenge-15-scalable-v1.0"
    assert len(restored["protocol_sha256"]) == 64
    assert restored["blindness"]["human_blind"] is False
    assert set(restored["statistics"]["l2_by_m"]) == {
        "-2",
        "-1",
        "0",
        "1",
        "2",
    }
    assert len(restored["gates"]) == 13
    assert restored["resources"]["n8_smoke_complete"] is True
    assert restored["resources"]["effective_sample_size"] == 65536.0
    assert restored["resources"]["ess_per_second"] > 0.0
    assert restored["gates"]["scalable_v1_pass"] is True


def test_load_factory_rejects_a_non_module_factory_specification() -> None:
    with pytest.raises(ValueError, match="module:factory"):
        load_factory("synthetic_scalable_candidate")
