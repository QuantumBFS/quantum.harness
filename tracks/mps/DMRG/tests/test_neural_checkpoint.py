from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from vmcrg_ref.artifacts import sha256_bytes
from vmcrg_ref.neural_checkpoint import (
    CheckpointExpectations,
    NeuralCheckpoint,
    load_neural_checkpoint,
    save_neural_checkpoint,
)
from vmcrg_ref.neural_energy import D4EvenLocalMLP


def _fixture() -> tuple[NeuralCheckpoint, CheckpointExpectations]:
    model = D4EvenLocalMLP.random(1, 3, 2026072808, feature_mode="patch")
    model.weight_out[:] = np.array([0.1, -0.03, 0.02])
    rng = np.random.default_rng(2026072809)
    gauge = rng.choice(np.asarray([-1, 1], dtype=np.int8), size=(5, 5, 5))
    hashes = {
        "protocol_sha256": "1" * 64,
        "code_sha256": "2" * 64,
        "operator_basis_sha256": "3" * 64,
        "gauge_reference_sha256": sha256_bytes(gauge.tobytes(order="C")),
        "seed_bundle_sha256": "4" * 64,
    }
    checkpoint = NeuralCheckpoint(
        model=model,
        fixed_linear_bias=np.zeros(13, dtype=np.float64),
        update=17,
        schedule_state={"eta_0": 1.2, "t_0": 250.0, "p": 0.75},
        polyak_state={
            "weight_in_sum": model.weight_in * 3.0,
            "bias_hidden_sum": model.bias_hidden * 3.0,
            "weight_out_sum": model.weight_out * 3.0,
            "sample_count": np.asarray(3, dtype=np.int64),
        },
        rng_states={"neural_training": rng.bit_generator.state},
        bundle_id="formal-1",
        round_index=2,
        predecessor_manifest_sha256="5" * 64,
        stop_state={"terminal_reason": None, "last_update": 17},
        metadata={"classification": "RUNNING"},
        gauge_energies=np.asarray([model.energy(spins) for spins in gauge]),
        **hashes,
    )
    expected = CheckpointExpectations(
        bundle_id="formal-1",
        round_index=2,
        predecessor_manifest_sha256="5" * 64,
        gauge_spins=gauge,
        **hashes,
    )
    return checkpoint, expected


def test_neural_checkpoint_round_trip_and_energy_gauge(tmp_path: Path) -> None:
    checkpoint, expected = _fixture()
    manifest = save_neural_checkpoint(tmp_path / "ckpt", checkpoint)
    restored = load_neural_checkpoint(tmp_path / "ckpt", expected)
    assert len(manifest["checkpoint_sha256"]) == 64
    assert restored.bundle_id == "formal-1"
    assert restored.round_index == 2
    assert restored.update == 17
    np.testing.assert_array_equal(restored.fixed_linear_bias, np.zeros(13))
    np.testing.assert_array_equal(restored.model.weight_in, checkpoint.model.weight_in)
    observed = np.asarray(
        [restored.model.energy(spins) for spins in expected.gauge_spins]
    )
    difference = observed - checkpoint.gauge_energies
    difference -= difference.mean()
    assert np.max(np.abs(difference)) <= 1e-10


def test_checkpoint_rejects_protocol_hash_mismatch(tmp_path: Path) -> None:
    checkpoint, expected = _fixture()
    save_neural_checkpoint(tmp_path / "ckpt", checkpoint)
    with pytest.raises(ValueError, match="protocol hash"):
        load_neural_checkpoint(
            tmp_path / "ckpt",
            replace(expected, protocol_sha256="a" * 64),
        )


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("code_sha256", "a" * 64, "code hash"),
        ("operator_basis_sha256", "b" * 64, "operator basis hash"),
        ("seed_bundle_sha256", "c" * 64, "seed bundle hash"),
        ("predecessor_manifest_sha256", "d" * 64, "predecessor"),
        ("round_index", 3, "round"),
    ],
)
def test_checkpoint_rejects_every_resume_identity_mismatch(
    tmp_path: Path,
    field: str,
    replacement: object,
    message: str,
) -> None:
    checkpoint, expected = _fixture()
    save_neural_checkpoint(tmp_path / "ckpt", checkpoint)
    with pytest.raises(ValueError, match=message):
        load_neural_checkpoint(
            tmp_path / "ckpt",
            replace(expected, **{field: replacement}),
        )


def test_partial_staging_directory_is_not_resumable(tmp_path: Path) -> None:
    _, expected = _fixture()
    (tmp_path / "ckpt.staging").mkdir()
    with pytest.raises(FileNotFoundError):
        load_neural_checkpoint(tmp_path / "ckpt", expected)


def test_checkpoint_rejects_nonzero_linear_branch_and_artifact_tampering(
    tmp_path: Path,
) -> None:
    checkpoint, expected = _fixture()
    with pytest.raises(ValueError, match="zero 13-operator"):
        save_neural_checkpoint(
            tmp_path / "bad",
            replace(checkpoint, fixed_linear_bias=np.eye(1, 13, dtype=np.float64)[0]),
        )
    save_neural_checkpoint(tmp_path / "ckpt", checkpoint)
    with (tmp_path / "ckpt" / "model.npz").open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_neural_checkpoint(tmp_path / "ckpt", expected)


def test_checkpoint_is_content_stable_and_refuses_overwrite(tmp_path: Path) -> None:
    checkpoint, _ = _fixture()
    first = save_neural_checkpoint(tmp_path / "first", checkpoint)
    second = save_neural_checkpoint(tmp_path / "second", checkpoint)
    assert first["checkpoint_sha256"] == second["checkpoint_sha256"]
    with pytest.raises(FileExistsError, match="nonempty"):
        save_neural_checkpoint(tmp_path / "first", checkpoint)


def test_checkpoint_api_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.save_neural_checkpoint is save_neural_checkpoint
    assert vmcrg_ref.load_neural_checkpoint is load_neural_checkpoint
