import numpy as np
import pytest

from qh147.checkpoint import latest_checkpoint, load_checkpoint, save_checkpoint
from qh147.pepo import FinitePEPO


def test_checkpoint_round_trip_preserves_dense_operator_and_metadata(tmp_path):
    pepo = FinitePEPO.identity(2, 2)
    path = tmp_path / "ordinary" / "checkpoints" / "beta-0.025000"
    save_checkpoint(
        path,
        pepo,
        beta=0.025,
        mode="ordinary",
        log_scale=1.5,
        config_sha256="abc",
        diagnostics={"loss": 0.2},
    )

    restored = load_checkpoint(path, expected_config_sha256="abc")

    assert np.array_equal(restored.pepo.to_dense(), pepo.to_dense())
    assert restored.beta == 0.025
    assert restored.mode == "ordinary"
    assert restored.log_scale == 1.5
    assert restored.diagnostics == {"loss": 0.2}


def test_checkpoint_rejects_tensor_corruption(tmp_path):
    path = tmp_path / "beta-0.025000"
    save_checkpoint(
        path,
        FinitePEPO.identity(1, 1),
        beta=0.025,
        mode="ordinary",
        log_scale=0.0,
        config_sha256="abc",
        diagnostics={},
    )
    tensor_path = path / "tensors.npz"
    tensor_path.write_bytes(tensor_path.read_bytes() + b"x")

    with pytest.raises(ValueError, match="tensor hash mismatch"):
        load_checkpoint(path, expected_config_sha256="abc")


def test_latest_checkpoint_ignores_directory_without_completion_marker(tmp_path):
    root = tmp_path / "checkpoints"
    complete = root / "beta-0.025000"
    save_checkpoint(
        complete,
        FinitePEPO.identity(1, 1),
        beta=0.025,
        mode="ordinary",
        log_scale=0.0,
        config_sha256="abc",
        diagnostics={},
    )
    incomplete = root / "beta-0.050000"
    incomplete.mkdir(parents=True)
    (incomplete / "tensors.npz").write_bytes(b"partial")

    latest = latest_checkpoint(root, expected_config_sha256="abc")

    assert latest is not None
    assert latest.beta == 0.025


def test_checkpoint_rejects_configuration_drift(tmp_path):
    path = tmp_path / "beta-0.025000"
    save_checkpoint(
        path,
        FinitePEPO.identity(1, 1),
        beta=0.025,
        mode="ordinary",
        log_scale=0.0,
        config_sha256="abc",
        diagnostics={},
    )

    with pytest.raises(ValueError, match="configuration hash mismatch"):
        load_checkpoint(path, expected_config_sha256="different")


def test_save_refuses_to_overwrite_a_completed_checkpoint(tmp_path):
    path = tmp_path / "beta-0.025000"
    pepo = FinitePEPO.identity(1, 1)
    save_checkpoint(
        path,
        pepo,
        beta=0.025,
        mode="ordinary",
        log_scale=0.0,
        config_sha256="abc",
        diagnostics={},
    )

    with pytest.raises(FileExistsError, match="completed checkpoint"):
        save_checkpoint(
            path,
            pepo,
            beta=0.025,
            mode="ordinary",
            log_scale=0.0,
            config_sha256="abc",
            diagnostics={},
        )
