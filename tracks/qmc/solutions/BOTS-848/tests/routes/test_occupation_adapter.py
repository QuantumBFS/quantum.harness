from __future__ import annotations

import importlib
import inspect
import json
import os
from pathlib import Path

import numpy as np
import pytest

from scalable_v1.audit import sha256_file
from scalable_v1.contracts import CandidateAdapter, DiagnosticProvider, StateHandle
from scalable_v1.protocol import load_protocol
from scalable_v1.routes.occupation_autoregressive.constraints import (
    FeasibilityTable,
    occupation_m2,
)
from scalable_v1.routes.occupation_autoregressive.model import AutoregressiveNQS
from scalable_v1.routes.occupation_autoregressive.train import (
    TrainingArtifacts,
    atomic_save_npz,
)


SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_PACKAGE = (
    SOLUTION_ROOT / "scalable_v1" / "routes" / "occupation_autoregressive"
)
RUN_DIR_ENV = "BOTS848_SCALABLE_RUN_DIR"
ATTEMPT = "s02a-a05"
COMPARISON_SHA = "5aa9219f4cd24bc2274f0514b621c2f9b47cead7"
CERTIFICATE_STATEMENT = (
    "Occupation-basis fermionic state: fixed LLL orbitals make strict LLL exact; "
    "bitset occupation makes particle-swap antisymmetry exact; sparse "
    "autoregressive and ladder operations avoid support enumeration."
)


def _a05_modules() -> tuple[object, object]:
    try:
        adapter = importlib.import_module(
            "scalable_v1.routes.occupation_autoregressive.adapter"
        )
        factory = importlib.import_module(
            "scalable_v1.routes.occupation_autoregressive.factory"
        )
    except ModuleNotFoundError as error:
        pytest.fail(f"A05.1 occupation adapter/factory feature missing: {error}")
    return adapter, factory


def _route_sources() -> list[Path]:
    return [
        SOLUTION_ROOT / "train_occupation_autoregressive.py",
        *sorted(ROUTE_PACKAGE.glob("*.py")),
    ]


def _write_frozen_run(
    run_dir: Path,
    *,
    manifest_seed: int = 848,
    checkpoint_seed: int = 848,
    checkpoint_protocol_sha256: str | None = None,
) -> Path:
    _adapter, _factory = _a05_modules()
    training_cli = importlib.import_module("train_occupation_autoregressive")
    freeze_training_run = getattr(training_cli, "freeze_training_run", None)
    assert callable(freeze_training_run), "A05.1 freeze_training_run feature missing"

    protocol = load_protocol()
    capacity = protocol.capacity["routes"]["occupation_autoregressive"]
    model = AutoregressiveNQS.initialize(
        n_electrons=protocol.physics["n_electrons"],
        two_q=protocol.physics["two_q"],
        target_m2=0,
        width=capacity["hidden_width"],
        layers=capacity["hidden_layers"],
        seed=checkpoint_seed,
        max_trainable_parameters=protocol.capacity["max_trainable_parameters"],
    )
    run_dir.mkdir(parents=True)
    checkpoint = atomic_save_npz(
        run_dir / "checkpoint.npz",
        parameters=model.flat_parameters(),
        selected_update=np.asarray(
            protocol.training["optimizer_updates"], dtype=np.int64
        ),
        completed_update=np.asarray(
            protocol.training["optimizer_updates"], dtype=np.int64
        ),
        training_seed=np.asarray(checkpoint_seed, dtype=np.int64),
        selection_rule=np.asarray("final_update"),
        protocol_sha256=np.asarray(
            checkpoint_protocol_sha256 or protocol.sha256
        ),
        comparison_sha=np.asarray(COMPARISON_SHA),
        n_electrons=np.asarray(protocol.physics["n_electrons"], dtype=np.int64),
        two_q=np.asarray(protocol.physics["two_q"], dtype=np.int64),
        target_m2=np.asarray(0, dtype=np.int64),
        width=np.asarray(capacity["hidden_width"], dtype=np.int64),
        layers=np.asarray(capacity["hidden_layers"], dtype=np.int64),
        batch_size_per_sector=np.asarray(
            protocol.training["batch_size_per_sector"], dtype=np.int64
        ),
    )
    optimizer_state = atomic_save_npz(
        run_dir / "optimizer-state.npz",
        update=np.asarray(protocol.training["optimizer_updates"], dtype=np.int64),
        first_moment=np.zeros(model.parameter_count, dtype=np.float64),
        second_moment=np.zeros(model.parameter_count, dtype=np.float64),
        training_seed=np.asarray(checkpoint_seed, dtype=np.int64),
        protocol_sha256=np.asarray(
            checkpoint_protocol_sha256 or protocol.sha256
        ),
    )
    training_log = run_dir / "training.jsonl"
    training_log.write_text(
        json.dumps(
            {
                "update": protocol.training["optimizer_updates"],
                "selected": True,
                "selection_rule": "final_update",
                "training_seed": checkpoint_seed,
                "resource_metrics": {
                    "placement": "remote",
                    "wall_seconds": 2.5,
                    "peak_rss_bytes": 123_456,
                    "peak_vram_bytes": None,
                    "estimator_evaluations": 2
                    * protocol.training["local_energy_evaluations_per_sector"],
                    "effective_sample_size": 0.0,
                    "n8_smoke_complete": False,
                    "n8_to_n6_time_ratio": 0.0,
                    "n8_to_n6_memory_ratio": 0.0,
                    "device_fingerprint": "pytest-compute-fixture",
                },
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    artifacts = TrainingArtifacts(
        checkpoint=checkpoint,
        optimizer_state=optimizer_state,
        training_log=training_log,
        checkpoint_sha256=sha256_file(checkpoint),
        optimizer_state_sha256=sha256_file(optimizer_state),
        training_log_sha256=sha256_file(training_log),
        selected_update=protocol.training["optimizer_updates"],
    )
    return freeze_training_run(
        run_dir=run_dir,
        artifacts=artifacts,
        protocol=protocol,
        training_seed=manifest_seed,
    )


def _load_candidate(monkeypatch: pytest.MonkeyPatch, run_dir: Path) -> object:
    _adapter, factory = _a05_modules()
    monkeypatch.setenv(RUN_DIR_ENV, str(run_dir))
    return factory.load_candidate()


def test_adapter_and_factory_modules_are_installed() -> None:
    adapter, factory = _a05_modules()

    assert getattr(adapter, "OccupationState", None) is not None
    assert getattr(adapter, "OccupationCandidate", None) is not None
    assert callable(getattr(factory, "load_candidate", None))


def test_factory_has_no_path_or_capacity_arguments() -> None:
    _adapter, factory = _a05_modules()

    assert tuple(inspect.signature(factory.load_candidate).parameters) == ()
    assert factory.RUN_DIR_ENV == RUN_DIR_ENV


@pytest.mark.parametrize("value", [None, "", "   "])
def test_factory_rejects_missing_or_empty_environment_path(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> None:
    _adapter, factory = _a05_modules()
    if value is None:
        monkeypatch.delenv(RUN_DIR_ENV, raising=False)
    else:
        monkeypatch.setenv(RUN_DIR_ENV, value)

    with pytest.raises(ValueError, match=RUN_DIR_ENV):
        factory.load_candidate()


def test_factory_rejects_multiple_environment_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _adapter, factory = _a05_modules()
    monkeypatch.setenv(
        RUN_DIR_ENV,
        f"{tmp_path / 'first'}{os.pathsep}{tmp_path / 'second'}",
    )

    with pytest.raises(ValueError, match="exactly one run directory"):
        factory.load_candidate()


def test_factory_loads_protocol_conforming_candidate_and_exact_multiplet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    manifest_path = _write_frozen_run(run_dir)

    candidate = _load_candidate(monkeypatch, run_dir)
    ground = candidate.ground_state()
    multiplet = candidate.generate_multiplet()

    assert isinstance(candidate, CandidateAdapter)
    assert isinstance(candidate, DiagnosticProvider)
    assert isinstance(ground, StateHandle)
    assert set(multiplet) == {-2, -1, 0, 1, 2}
    assert tuple(multiplet) == (-2, -1, 0, 1, 2)
    assert all(isinstance(state, StateHandle) for state in multiplet.values())
    assert candidate.training_seed == 848
    assert candidate.protocol_sha256 == load_protocol().sha256
    assert candidate.manifest_sha256 == sha256_file(manifest_path)
    assert candidate.checkpoint_sha256 == sha256_file(run_dir / "checkpoint.npz")


def test_state_batches_cover_sample_logpsi_sparse_energy_and_l2_without_enumeration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_run(run_dir)

    def forbidden_enumeration(_self: FeasibilityTable) -> tuple[int, ...]:
        raise AssertionError("production adapter enumerated a support")

    monkeypatch.setattr(
        FeasibilityTable,
        "enumerate_support",
        forbidden_enumeration,
    )
    candidate = _load_candidate(monkeypatch, run_dir)
    states = (candidate.ground_state(), candidate.generate_multiplet()[0])
    for state in states:
        batch = state.sample(3, 4848)
        assert batch.configs.shape == (3,)
        assert batch.n_samples == 3
        assert batch.seed == 4848
        assert all(int(config).bit_count() == 6 for config in batch.configs)
        assert all(
            occupation_m2(int(config), 15) == 2 * state.m
            for config in batch.configs
        )
        for values in (
            state.logpsi(batch.configs),
            state.local_energy(batch.configs),
            state.local_l2(batch.configs),
        ):
            assert values.shape == (3,)
            assert values.dtype == np.complex128
            assert np.all(np.isfinite(values.real))
            assert np.all(np.isfinite(values.imag))


def test_state_batch_shape_size_and_sector_validation_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_run(run_dir)
    ground = _load_candidate(monkeypatch, run_dir).ground_state()
    valid = ground.sample(1, 4848).configs

    with pytest.raises(ValueError, match="one-dimensional non-empty batch"):
        ground.logpsi(valid.reshape(1, 1))
    with pytest.raises(ValueError, match="one-dimensional non-empty batch"):
        ground.local_energy(np.asarray([], dtype=object))
    with pytest.raises(ValueError, match="fixed-N fixed-M"):
        ground.local_l2(np.asarray([0], dtype=object))
    with pytest.raises(ValueError, match="n_samples must be positive"):
        ground.sample(0, 4848)
    with pytest.raises(TypeError, match="seed must be an integer"):
        ground.sample(1, True)


def test_candidate_exposes_exact_construction_certificate_and_measured_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_run(run_dir)
    candidate = _load_candidate(monkeypatch, run_dir)

    certificate = candidate.construction_certificate()
    resources = candidate.resource_metrics()

    assert certificate.strict_lll is True
    assert certificate.antisymmetric is True
    assert certificate.scalable is True
    assert certificate.trainable_parameters == candidate.parameter_count
    assert certificate.statement == CERTIFICATE_STATEMENT
    assert resources.placement == "remote"
    assert resources.wall_seconds == 2.5
    assert resources.peak_rss_bytes == 123_456
    assert resources.checkpoint_bytes == (run_dir / "checkpoint.npz").stat().st_size
    assert resources.device_fingerprint == "pytest-compute-fixture"


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        ("artifact", "artifact (byte size|hash) mismatch"),
        ("manifest_seed", "training seed mismatch"),
        ("checkpoint_seed", "checkpoint training seed mismatch"),
        ("protocol", "checkpoint protocol hash mismatch"),
        ("source", "source hash mismatch"),
    ],
)
def test_factory_rejects_tamper_and_all_identity_mismatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
    message: str,
) -> None:
    run_dir = tmp_path / "run"
    if tamper == "manifest_seed":
        _write_frozen_run(run_dir, manifest_seed=1848)
    elif tamper == "checkpoint_seed":
        _write_frozen_run(run_dir, checkpoint_seed=1848)
    elif tamper == "protocol":
        _write_frozen_run(run_dir, checkpoint_protocol_sha256="0" * 64)
    else:
        manifest_path = _write_frozen_run(run_dir)
        if tamper == "artifact":
            with (run_dir / "checkpoint.npz").open("ab") as handle:
                handle.write(b"tamper")
        elif tamper == "source":
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["source_files"][0]["sha256"] = "0" * 64
            manifest_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
    monkeypatch.setenv(RUN_DIR_ENV, str(run_dir))
    _adapter, factory = _a05_modules()

    with pytest.raises(ValueError, match=message):
        factory.load_candidate()


def test_manifest_binds_exact_route_attempt_sources_and_artifact_bytes(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    manifest_path = _write_frozen_run(run_dir)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "challenge-15-frozen-manifest-v1"
    assert payload["route"] == "occupation_autoregressive"
    assert payload["attempt"] == ATTEMPT
    assert payload["training_seed"] == 848
    assert payload["selected_update"] == 2048
    assert payload["checkpoint_policy"] == "final_update"
    assert payload["protocol_sha256"] == load_protocol().sha256
    assert {item["path"] for item in payload["source_files"]} == {
        path.relative_to(SOLUTION_ROOT).as_posix() for path in _route_sources()
    }
    assert {
        item["role"]: (item["path"], item["bytes"])
        for item in payload["artifacts"]
    } == {
        "checkpoint": (
            "checkpoint.npz",
            (run_dir / "checkpoint.npz").stat().st_size,
        ),
        "optimizer_state": (
            "optimizer-state.npz",
            (run_dir / "optimizer-state.npz").stat().st_size,
        ),
        "training_log": (
            "training.jsonl",
            (run_dir / "training.jsonl").stat().st_size,
        ),
    }


@pytest.mark.parametrize(
    "flag",
    [
        "--width",
        "--hidden-width",
        "--layers",
        "--batch-size",
        "--capacity",
        "--checkpoint",
        "--checkpoint-selection",
    ],
)
def test_cli_rejects_capacity_batch_and_checkpoint_selection_overrides(
    flag: str,
) -> None:
    training_cli = importlib.import_module("train_occupation_autoregressive")
    parser = training_cli._parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--smoke-updates",
                "16",
                "--training-seed",
                "848",
                "--run-dir",
                "unused",
                flag,
                "2",
            ]
        )
