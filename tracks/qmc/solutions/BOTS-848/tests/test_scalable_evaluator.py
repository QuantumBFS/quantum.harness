from __future__ import annotations

import copy
from dataclasses import dataclass, field
import inspect
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import types
from typing import Any

import numpy as np
import pytest

from scalable_v1.audit import freeze_manifest, verify_manifest
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
from scalable_v1.overlap import (
    EDOverlapOracle,
    FidelityEstimate,
    build_ed_overlap_oracle,
    evaluate_overlaps,
    fidelity_from_log_amplitudes,
    normalized_fidelity,
)
from scalable_v1.protocol import ProtocolConfig, load_protocol
from run_scalable_evaluator import load_factory, main


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
EAGER_ED_MODULE_PREFIXES = (
    "benchmark_v0.ed_oracle",
    "benchmark_v0.fock_ed",
    "benchmark_v0.lll_coulomb",
)


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


@dataclass
class SupportMismatchState(FakeState):
    def sample(self, n_samples: int, seed: int) -> SampleBatch:
        self.sample_calls.append((n_samples, seed))
        return SampleBatch(np.ones(n_samples, dtype=np.int64), n_samples, 1024, seed)

    def logpsi(self, config_batch: Any) -> np.ndarray:
        configs = np.asarray(config_batch)
        result = np.full(configs.shape[0], complex(-np.inf, 0.0))
        result[configs == 1] = 0.0
        return result


@dataclass
class ContinuousFakeState(FakeState):
    def sample(self, n_samples: int, seed: int) -> SampleBatch:
        self.sample_calls.append((n_samples, seed))
        spinors = np.zeros((n_samples, 6, 2), dtype=complex)
        spinors[:, :, 0] = 1.0
        return SampleBatch(spinors, n_samples, 1024, seed)


def make_candidate_with_state_type(state_type: type[FakeState]) -> FakeCandidate:
    candidate = FakeCandidate()
    candidate.ground = state_type("ground", 0, 0, 1.0, 0.0)
    candidate.tower = {
        m: state_type(f"l2_m{m}", 2, m, 1.1, 6.0)
        for m in range(-2, 3)
    }
    return candidate


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


class FakeOverlapOracle:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        basis = tuple(range(4096))
        coefficients = np.full(4096, 1.0 / np.sqrt(4096), dtype=complex)
        coefficients.setflags(write=False)
        self._basis = basis
        self._coefficients = coefficients

    def amplitude(self, label: str, configs: Any) -> np.ndarray:
        self.calls.append((label, len(configs)))
        return np.ones(len(configs), dtype=complex)

    def occupation_basis(self, label: str) -> tuple[int, ...]:
        return self._basis

    def occupation_coefficients(self, label: str) -> np.ndarray:
        return self._coefficients


def build_fake_overlap_oracle(physics: Any) -> FakeOverlapOracle:
    assert physics["n_electrons"] == 6
    assert physics["two_q"] == 15
    return FakeOverlapOracle()


def make_frozen_run(
    tmp_path: Path,
    *,
    tamper_checkpoint: bool = False,
    source_text: str = "VALUE = 1\n",
) -> tuple[Path, Path, Path, Path, ProtocolConfig]:
    project_root = tmp_path / "project"
    run_dir = project_root / "run"
    run_dir.mkdir(parents=True)
    source = project_root / "candidate.py"
    source.write_text(source_text, encoding="utf-8")
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


def _run_clean_interpreter(source: str, *arguments: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", source, *(str(path) for path in arguments)],
        cwd=SOLUTION_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_cli_rejects_tampered_manifest_before_importing_candidate(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "candidate-imported.txt"
    candidate_source = f"""
from pathlib import Path
Path({str(marker)!r}).write_text('imported', encoding='utf-8')

def factory(protocol, seed):
    raise AssertionError('factory executed before manifest audit')
"""
    project_root, _, manifest_path, oracle_path, _ = make_frozen_run(
        tmp_path,
        tamper_checkpoint=True,
        source_text=candidate_source,
    )
    output = tmp_path / "should-not-exist.json"
    source = """
import sys
sys.path.insert(0, sys.argv[1])
from run_scalable_evaluator import main
raise SystemExit(main(sys.argv[2:]))
"""

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            source,
            str(project_root),
            "--candidate",
            "candidate:factory",
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
        ],
        cwd=SOLUTION_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert not marker.exists(), completed.stdout + completed.stderr
    assert "manifest audit failed" in completed.stderr
    assert not output.exists()


def test_manifest_audit_rejects_candidate_reference_to_reveal_only_overlap(
    tmp_path: Path,
) -> None:
    project_root, _, manifest_path, _, protocol = make_frozen_run(
        tmp_path,
        source_text=(
            "from scalable_v1.overlap import build_ed_overlap_oracle\n"
            "VALUE = build_ed_overlap_oracle\n"
        ),
    )

    audit = verify_manifest(
        manifest_path,
        project_root=project_root,
        protocol=protocol,
        expected_training_seed=848,
    )

    assert audit.valid is False
    assert "scalable_v1.overlap" not in protocol.oracle[
        "forbidden_module_prefixes"
    ]
    assert any(
        issue == "forbidden candidate import: scalable_v1.overlap"
        for issue in audit.issues
    )


@pytest.mark.parametrize(
    ("source_text", "expected_issue"),
    [
        (
            "from scalable_v1.evaluator import build_ed_overlap_oracle as leaked\n",
            "forbidden candidate import: scalable_v1.evaluator",
        ),
        (
            "import scalable_v1.evaluator as coordinator\n",
            "forbidden candidate import: scalable_v1.evaluator",
        ),
        (
            "COORDINATOR_MODULE = 'scalable_v1.evaluator'\n",
            "forbidden candidate module reference: scalable_v1.evaluator",
        ),
    ],
)
def test_manifest_audit_rejects_candidate_evaluator_import_and_reference_variants(
    tmp_path: Path,
    source_text: str,
    expected_issue: str,
) -> None:
    project_root, _, manifest_path, _, protocol = make_frozen_run(
        tmp_path,
        source_text=source_text,
    )

    audit = verify_manifest(
        manifest_path,
        project_root=project_root,
        protocol=protocol,
        expected_training_seed=848,
    )

    assert audit.valid is False
    assert "scalable_v1.evaluator" not in protocol.oracle[
        "forbidden_module_prefixes"
    ]
    assert expected_issue in audit.issues


def test_importing_evaluator_does_not_load_ed_implementation_modules() -> None:
    source = f"""
import sys
import scalable_v1.evaluator

prefixes = {EAGER_ED_MODULE_PREFIXES!r}
loaded = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + '.') for prefix in prefixes)
)
assert loaded == [], loaded
"""

    _run_clean_interpreter(source)


def test_failed_manifest_audit_does_not_load_ed_implementation_modules(
    tmp_path: Path,
) -> None:
    source = f"""
import sys
from pathlib import Path

from scalable_v1.evaluator import evaluate_candidate
from scalable_v1.protocol import load_protocol

root = Path(sys.argv[1])
manifest = root / 'invalid-manifest.json'
manifest.write_text('{{"schema_version": "invalid"}}', encoding='utf-8')
try:
    evaluate_candidate(
        candidate=object(),
        diagnostics=object(),
        protocol=load_protocol(),
        manifest_path=manifest,
        project_root=root,
        oracle_path=root / 'missing-oracle.json',
        training_seed=848,
    )
except ValueError as error:
    assert 'manifest audit failed' in str(error), error
else:
    raise AssertionError('invalid manifest unexpectedly passed audit')

prefixes = {EAGER_ED_MODULE_PREFIXES!r}
loaded = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + '.') for prefix in prefixes)
)
assert loaded == [], loaded
"""

    _run_clean_interpreter(source, tmp_path)


def _fixed_m_dimension(n_electrons: int, two_q: int, target_m: int) -> int:
    return sum(
        1
        for occupied in itertools.combinations(range(two_q + 1), n_electrons)
        if sum(-two_q + 2 * orbital for orbital in occupied) == 2 * target_m
    )


def test_real_n6_ed_overlap_oracle_builds_six_normalized_states() -> None:
    oracle = build_ed_overlap_oracle(load_protocol().physics)

    assert set(oracle._states) == {"ground", "-2", "-1", "0", "1", "2"}
    for label, state in oracle._states.items():
        target_m = 0 if label == "ground" else int(label)
        assert len(state.basis) == _fixed_m_dimension(6, 15, target_m)
        assert state.coefficients.shape == (len(state.basis),)
        assert np.all(np.isfinite(state.coefficients))
        assert np.linalg.norm(state.coefficients) == pytest.approx(1.0)
        assert state.coefficients.flags.writeable is False

        configs = np.asarray(state.basis[:4], dtype=np.int64)
        assert oracle.amplitude(label, configs) == pytest.approx(
            state.coefficients[:4]
        )


def test_normalized_fidelity_is_scale_invariant_and_detects_orthogonality() -> None:
    candidate = np.array([1.0 + 2.0j, -3.0j, 0.5 - 0.25j])
    scale = -2.5 + 4.0j

    assert normalized_fidelity(candidate, scale * candidate) == pytest.approx(1.0)
    assert normalized_fidelity(
        np.array([1.0, 1.0]), np.array([1.0, -1.0])
    ) == pytest.approx(0.0, abs=1.0e-15)


@pytest.mark.parametrize(
    ("candidate", "oracle", "message"),
    [
        (np.ones(2), np.ones(3), "same shape"),
        (np.array([]), np.array([]), "nonempty"),
        (np.array([1.0, np.nan]), np.ones(2), "finite"),
        (np.ones(2), np.array([1.0, np.inf]), "finite"),
        (np.zeros(2), np.ones(2), "denominator"),
        (np.ones(2), np.zeros(2), "denominator"),
    ],
)
def test_normalized_fidelity_rejects_invalid_samples(
    candidate: np.ndarray, oracle: np.ndarray, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        normalized_fidelity(candidate, oracle)


def test_fidelity_from_log_amplitudes_uses_full_ratio_and_block_jackknife() -> None:
    candidate_log = np.zeros(4, dtype=complex)
    oracle_log = np.array([0.0, 0.0, 0.0, 1.0j * np.pi])

    estimate = fidelity_from_log_amplitudes(
        candidate_log, oracle_log, block_size=2
    )

    assert estimate.mean == pytest.approx(0.25, abs=1.0e-15)
    assert estimate.standard_error == pytest.approx(0.5)
    assert estimate.method == "candidate_importance_block_jackknife"
    assert estimate.raw_sample_count == 4
    assert estimate.effective_sample_size == 2.0
    assert estimate.to_dict() == {
        "mean": pytest.approx(0.25),
        "standard_error": pytest.approx(0.5),
        "method": "candidate_importance_block_jackknife",
        "raw_sample_count": 4,
        "effective_sample_size": 2.0,
    }
    assert type(estimate.to_dict()["mean"]) is float
    assert type(estimate.to_dict()["standard_error"]) is float
    assert type(estimate.to_dict()["effective_sample_size"]) is float


def test_fidelity_from_log_amplitudes_stabilizes_extreme_complex_ratios() -> None:
    candidate_log = np.array([1000.0 + 0.2j] * 4)
    oracle_log = candidate_log + np.log(3.0) - 0.7j

    estimate = fidelity_from_log_amplitudes(
        candidate_log, oracle_log, block_size=2
    )

    assert estimate.mean == pytest.approx(1.0)
    assert estimate.standard_error == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("candidate_log", "oracle_log", "block_size", "message"),
    [
        (np.zeros(4), np.zeros(5), 2, "same shape"),
        (np.zeros(0), np.zeros(0), 1, "nonempty"),
        (np.array([0.0, np.nan, 0.0, 0.0]), np.zeros(4), 2, "finite"),
        (np.zeros(4), np.zeros(4), 3, "divisible"),
        (np.zeros(4), np.zeros(4), 4, "at least two blocks"),
    ],
)
def test_fidelity_from_log_amplitudes_rejects_invalid_inputs(
    candidate_log: np.ndarray,
    oracle_log: np.ndarray,
    block_size: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        fidelity_from_log_amplitudes(
            candidate_log, oracle_log, block_size=block_size
        )


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ((float("nan"), 0.0, 1.0), "finite"),
        ((0.5, float("inf"), 1.0), "finite"),
        ((0.5, 0.0, float("nan")), "finite"),
        ((-0.1, 0.0, 1.0), "between zero and one"),
        ((1.1, 0.0, 1.0), "between zero and one"),
        ((0.5, -0.1, 1.0), "nonnegative"),
        ((0.5, 0.1, 0.0), "positive"),
    ],
)
def test_fidelity_estimate_rejects_nonfinite_or_out_of_range_values(
    values: tuple[float, float, float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        FidelityEstimate(*values)


def test_ed_overlap_oracle_supports_bitsets_and_batched_spinors() -> None:
    coefficients = np.array([0.6, 0.8j])
    state_data = {
        label: ((1, 2), coefficients)
        for label in ("ground", "-2", "-1", "0", "1", "2")
    }
    oracle = EDOverlapOracle(
        n_electrons=1,
        two_q=1,
        state_data=state_data,
        chunk_size=1,
    )
    coefficients[:] = 0.0

    assert oracle.occupation_basis("ground") == (1, 2)
    exposed_coefficients = oracle.occupation_coefficients("ground")
    assert exposed_coefficients == pytest.approx(np.array([0.6, 0.8j]))
    assert exposed_coefficients.flags.writeable is False
    with pytest.raises(ValueError):
        exposed_coefficients.setflags(write=True)
    assert oracle.amplitude("ground", np.array([1, 2, 1 << 2])) == pytest.approx(
        np.array([0.6, 0.8j, 0.0])
    )

    spinors = np.array(
        [
            [[1.0 + 0.0j, 0.0 + 0.0j]],
            [[0.0 + 0.0j, 1.0 + 0.0j]],
        ]
    )
    normalization = np.sqrt(2.0 / (4.0 * np.pi))
    assert oracle.amplitude("ground", spinors) == pytest.approx(
        np.array([0.8j * normalization, -0.6 * normalization])
    )


@pytest.mark.parametrize(
    ("label", "configs", "message"),
    [
        ("invalid", np.array([1]), "label"),
        ("ground", np.array(1), "shape"),
        ("ground", np.ones((2, 1)), "shape"),
        ("ground", np.array([[[np.nan, 0.0]]]), "finite"),
    ],
)
def test_ed_overlap_oracle_rejects_invalid_labels_and_configurations(
    label: str, configs: np.ndarray, message: str
) -> None:
    state_data = {
        state_label: ((1, 2), np.array([1.0, 0.0]))
        for state_label in ("ground", "-2", "-1", "0", "1", "2")
    }
    oracle = EDOverlapOracle(n_electrons=1, two_q=1, state_data=state_data)

    with pytest.raises(ValueError, match=message):
        oracle.amplitude(label, configs)


def test_evaluate_overlaps_uses_exact_reveal_sampling_schedule() -> None:
    protocol = load_protocol()
    candidate = FakeCandidate()
    oracle = FakeOverlapOracle()

    overlaps = evaluate_overlaps(candidate, protocol, oracle)

    states = [candidate.ground, *(candidate.tower[m] for m in range(-2, 3))]
    for state_index, state in enumerate(states):
        assert state.sample_calls == [
            (512, 3848 + 1000 * state_index + chain)
            for chain in range(8)
        ]
    assert oracle.calls == []
    assert overlaps["ground_fidelity"].mean == 1.0
    assert overlaps["ground_fidelity"].method == "exact_occupation_normalized_overlap"
    assert overlaps["ground_fidelity"].raw_sample_count == 4096
    assert overlaps["ground_fidelity"].effective_sample_size is None
    assert set(overlaps["l2_fidelity_by_m"]) == {"-2", "-1", "0", "1", "2"}
    assert all(
        estimate.mean == 1.0
        for estimate in overlaps["l2_fidelity_by_m"].values()
    )


def test_exact_occupation_overlap_includes_missing_candidate_support() -> None:
    coefficients = np.full(2, 1.0 / np.sqrt(2.0), dtype=complex)
    state_data = {
        label: ((1, 2), coefficients)
        for label in ("ground", "-2", "-1", "0", "1", "2")
    }
    oracle = EDOverlapOracle(n_electrons=1, two_q=1, state_data=state_data)
    candidate = make_candidate_with_state_type(SupportMismatchState)

    overlaps = evaluate_overlaps(candidate, load_protocol(), oracle)

    assert overlaps["ground_fidelity"].mean == pytest.approx(0.5)
    assert (
        overlaps["ground_fidelity"].method
        == "exact_occupation_normalized_overlap"
    )
    assert overlaps["ground_fidelity"].effective_sample_size is None


def test_continuous_overlap_uses_all_chains_and_reports_block_ess() -> None:
    candidate = make_candidate_with_state_type(ContinuousFakeState)
    oracle = FakeOverlapOracle()

    overlaps = evaluate_overlaps(candidate, load_protocol(), oracle)

    states = [candidate.ground, *(candidate.tower[m] for m in range(-2, 3))]
    for state_index, state in enumerate(states):
        assert state.sample_calls == [
            (512, 3848 + 1000 * state_index + chain)
            for chain in range(8)
        ]
    assert oracle.calls == [
        (label, 4096) for label in ("ground", "-2", "-1", "0", "1", "2")
    ]
    estimate = overlaps["ground_fidelity"]
    assert estimate.method == "candidate_importance_block_jackknife"
    assert estimate.raw_sample_count == 4096
    assert estimate.effective_sample_size == pytest.approx(16.0)
    assert estimate.effective_sample_size < estimate.raw_sample_count


def test_evaluate_overlaps_rejects_invalid_sample_metadata() -> None:
    candidate = FakeCandidate()

    def bad_sample(n_samples: int, seed: int) -> SampleBatch:
        return SampleBatch(np.arange(n_samples), n_samples, 0, seed)

    candidate.ground.sample = bad_sample  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="frozen burn-in"):
        evaluate_overlaps(candidate, load_protocol(), FakeOverlapOracle())


def test_evaluate_candidate_defaults_to_the_production_overlap_builder() -> None:
    parameter = inspect.signature(evaluate_candidate).parameters[
        "overlap_oracle_builder"
    ]

    assert parameter.default is build_ed_overlap_oracle


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
    overlap_builder_calls: list[dict[str, Any]] = []
    progress: list[str] = []

    def recording_oracle_loader(raw: str) -> dict[str, Any]:
        oracle_calls.append("oracle")
        return json.loads(raw)

    def recording_overlap_builder(physics: Any) -> FakeOverlapOracle:
        assert progress[-1].startswith("reveal:")
        overlap_builder_calls.append(dict(physics))
        return FakeOverlapOracle()

    record = evaluate_candidate(
        candidate=FakeCandidate(),
        diagnostics=FakeDiagnostics(),
        protocol=protocol,
        manifest_path=manifest_path,
        project_root=project_root,
        oracle_path=oracle_path,
        training_seed=848,
        oracle_loader=recording_oracle_loader,
        overlap_oracle_builder=recording_overlap_builder,
        progress=progress.append,
    )

    assert oracle_calls == ["oracle"]
    assert overlap_builder_calls == [dict(protocol.physics)]
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
    assert set(record["ed_comparison"]) == {
        "ground_absolute_error",
        "excited_absolute_error_by_m",
        "gap_absolute_error",
        "gap_z_score",
        "ground_fidelity",
        "l2_fidelity_by_m",
        "minimum_l2_fidelity",
        "overlap_wall_seconds",
    }
    assert record["ed_comparison"]["ground_fidelity"] == {
        "mean": 1.0,
        "standard_error": 0.0,
        "method": "exact_occupation_normalized_overlap",
        "raw_sample_count": 4096,
        "effective_sample_size": None,
    }
    assert set(record["ed_comparison"]["l2_fidelity_by_m"]) == {
        "-2",
        "-1",
        "0",
        "1",
        "2",
    }
    assert record["ed_comparison"]["minimum_l2_fidelity"] == 1.0
    assert record["ed_comparison"]["overlap_wall_seconds"] > 0.0
    assert validate_run_record(record) is None


def test_tampered_manifest_stops_before_collection_or_oracle_read(
    tmp_path: Path,
) -> None:
    project_root, _, manifest_path, _, protocol = make_frozen_run(
        tmp_path, tamper_checkpoint=True
    )
    candidate = FakeCandidate()
    oracle_calls: list[str] = []
    overlap_builder_calls: list[str] = []

    def recording_oracle_loader(raw: str) -> dict[str, Any]:
        oracle_calls.append("oracle")
        return json.loads(raw)

    def recording_overlap_builder(physics: Any) -> FakeOverlapOracle:
        overlap_builder_calls.append("overlap")
        return FakeOverlapOracle()

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
            overlap_oracle_builder=recording_overlap_builder,
        )

    assert candidate.ground.sample_calls == []
    assert oracle_calls == []
    assert overlap_builder_calls == []


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
        (
            lambda record: record["ed_comparison"].pop("ground_fidelity"),
            "overlap schema mismatch",
        ),
        (
            lambda record: record["ed_comparison"]["l2_fidelity_by_m"].pop("2"),
            "overlap M set mismatch",
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
        overlap_oracle_builder=build_fake_overlap_oracle,
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
        overlap_oracle_builder=build_fake_overlap_oracle,
    )
    changed = copy.deepcopy(record)
    mutation(changed)

    with pytest.raises(ValueError, match=message):
        validate_run_record(changed)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda record: record["ed_comparison"]["ground_fidelity"].__setitem__(
                "mean", 1.1
            ),
            "fidelity mean",
        ),
        (
            lambda record: record["ed_comparison"]["l2_fidelity_by_m"]["0"].__setitem__(
                "standard_error", -0.1
            ),
            "fidelity standard_error",
        ),
        (
            lambda record: record["ed_comparison"]["ground_fidelity"].__setitem__(
                "method", "unknown"
            ),
            "fidelity method",
        ),
        (
            lambda record: record["ed_comparison"]["ground_fidelity"].__setitem__(
                "raw_sample_count", 0
            ),
            "raw sample count",
        ),
        (
            lambda record: record["ed_comparison"]["ground_fidelity"].__setitem__(
                "effective_sample_size", 1.0
            ),
            "exact occupation ESS",
        ),
        (
            lambda record: record["ed_comparison"].__setitem__(
                "minimum_l2_fidelity", float("nan")
            ),
            "minimum L2 fidelity",
        ),
        (
            lambda record: record["ed_comparison"].__setitem__(
                "overlap_wall_seconds", 0.0
            ),
            "overlap wall time",
        ),
    ],
)
def test_validate_run_record_rejects_invalid_overlap_values(
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
        overlap_oracle_builder=build_fake_overlap_oracle,
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
        overlap_oracle_builder=build_fake_overlap_oracle,
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
        overlap_oracle_builder=build_fake_overlap_oracle,
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
    def evaluate_with_fake_overlap(**kwargs: Any) -> dict[str, Any]:
        return evaluate_candidate(
            **kwargs,
            overlap_oracle_builder=build_fake_overlap_oracle,
        )

    monkeypatch.setattr(
        "run_scalable_evaluator.evaluate_candidate",
        evaluate_with_fake_overlap,
    )
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
    assert restored["ed_comparison"]["ground_fidelity"]["mean"] == 1.0
    assert restored["ed_comparison"]["minimum_l2_fidelity"] == 1.0
    assert restored["ed_comparison"]["overlap_wall_seconds"] > 0.0
    assert restored["gates"]["scalable_v1_pass"] is True


def test_load_factory_rejects_a_non_module_factory_specification() -> None:
    with pytest.raises(ValueError, match="module:factory"):
        load_factory("synthetic_scalable_candidate")
