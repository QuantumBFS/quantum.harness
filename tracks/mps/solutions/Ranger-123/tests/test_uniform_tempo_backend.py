from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose

from floquet_if_manybody.backends.uniform_tempo import (
    UniformTempoBackend,
    UniformTempoControls,
    _encode_complex,
    _tensor_cache_key,
)
from floquet_if_manybody.config import BathConfig, ModelConfig


def _write_fake_runner(path: Path, payload: dict[str, object], exit_code: int = 0) -> None:
    script = f"""\
import json
import pathlib
import sys

if {exit_code}:
    print("synthetic Julia failure", file=sys.stderr)
    raise SystemExit({exit_code})
input_path, output_path = sys.argv[1:3]
request = json.loads(pathlib.Path(input_path).read_text())
pathlib.Path({str(Path("captured-request.json"))!r}).write_text(json.dumps(request))
payload = {payload!r}
payload["request_echo"] = request
pathlib.Path(output_path).write_text(json.dumps(payload))
"""
    script = script.replace(
        repr(str(Path("captured-request.json"))),
        repr(str(path.parent / "captured-request.json")),
    )
    path.write_text(script, encoding="utf-8")


def _valid_payload() -> dict[str, object]:
    return {
        "method": "uniform_tempo_floquet_multitime",
        "dt": np.pi / 2,
        "period_steps": 4,
        "bond_dimension": 3,
        "floquet_state": {
            "real": [0.6, 0.0, 0.0, 0.4],
            "imag": [0.0, 0.1, -0.1, 0.0],
            "shape": [2, 2],
        },
        "phase_states": {
            "real": [0.6, 0.0, 0.0, 0.4, 0.4, 0.0, 0.0, 0.6],
            "imag": [0.0] * 8,
            "shape": [2, 2, 2],
        },
        "one_point": [0.2, -0.2],
        "phase_offsets": [0, 2],
        "delay": [0.0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi],
        "correlation": {
            "real": [1.0, 0.5, 0.25, 0.125, 0.0625],
            "imag": [0.0, -0.1, -0.05, -0.025, -0.0125],
            "shape": [5],
        },
        "diagnostics": {
            "trace_error": 1e-8,
            "hermiticity_error": 1e-8,
            "minimum_density_eigenvalue": 0.3,
            "fixed_point_residual": 1e-7,
            "floquet_transfer_residual": 1e-7,
        },
        "julia_version": "1.12.6",
        "uniform_tempo_revision": "b76a018c32e5415989761d902b1b0e95f1a337da",
        "manifest_sha256": "a" * 64,
        "process_tensor_cache_hit": False,
        "transfer_eigenvalues": {
            "real": [],
            "imag": [],
            "shape": [0],
        },
        "transfer_eigenpair_residuals": [],
        "transfer_dimension": 12,
    }


def _backend(tmp_path: Path, payload: dict[str, object]) -> UniformTempoBackend:
    runner = tmp_path / "fake_runner.py"
    _write_fake_runner(runner, payload)
    return UniformTempoBackend(command_prefix=(sys.executable, str(runner)))


def _model() -> ModelConfig:
    return ModelConfig(
        n=3,
        j=0.5,
        drive_amplitude=0.2,
        drive_frequency=1.0,
    )


def test_valid_payload_round_trips_complex_arrays(tmp_path: Path) -> None:
    backend = _backend(tmp_path, _valid_payload())
    result = backend.run_periodic(
        np.array([[0.0, 0.5], [0.5, 0.0]], dtype=complex),
        np.diag([1.0, -1.0]).astype(complex),
        _model(),
        BathConfig(alpha=0.01, cutoff=2.5),
        UniformTempoControls(
            steps_per_period=4,
            tolerance=1e-4,
            phase_samples=2,
            delay_periods=1,
            auto_nc=False,
            memory_cutoff=6,
        ),
    )
    assert result.method == "uniform_tempo_floquet_multitime"
    assert result.phase_states.shape == (2, 2, 2)
    assert_allclose(result.floquet_state, [[0.6, -0.1j], [0.1j, 0.4]])
    assert_allclose(
        result.correlation.total,
        [
            1.0,
            0.5 - 0.1j,
            0.25 - 0.05j,
            0.125 - 0.025j,
            0.0625 - 0.0125j,
        ],
    )
    assert_allclose(
        result.correlation.total,
        result.correlation.connected + result.correlation.coherent,
    )
    assert result.metadata["uniform_tempo_revision"].startswith("b76a018")
    assert result.transfer_eigenvalues.size == 0


def test_backend_round_trips_transfer_poles_and_independent_drive(
    tmp_path: Path,
) -> None:
    payload = _valid_payload()
    payload["transfer_eigenvalues"] = {
        "real": [1.0, 0.8],
        "imag": [0.0, 0.1],
        "shape": [2],
    }
    payload["transfer_eigenpair_residuals"] = [1e-12, 2e-11]
    backend = _backend(tmp_path, payload)
    drive = 2 * np.diag([1.0, -1.0]).astype(complex)
    result = backend.run_periodic(
        np.array([[0.0, 0.5], [0.5, 0.0]], dtype=complex),
        np.diag([1.0, -1.0]).astype(complex),
        _model(),
        BathConfig(alpha=0.01),
        UniformTempoControls(4, 1e-4, 2, 1, pole_count=2),
        drive_operator=drive,
    )
    assert_allclose(result.transfer_eigenvalues, [1.0, 0.8 + 0.1j])
    assert_allclose(result.transfer_eigenpair_residuals, [1e-12, 2e-11])
    request = json.loads((tmp_path / "captured-request.json").read_text())
    assert request["drive"]["real"] == _encode_complex(drive)["real"]
    assert request["controls"]["pole_count"] == 2


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("transfer_eigenpair_residuals", [1e-12], "same length"),
        ("transfer_eigenpair_residuals", [1e-12, -1.0], "nonnegative"),
        (
            "transfer_eigenvalues",
            {"real": [1.0, "nan"], "imag": [0.0, 0.0], "shape": [2]},
            "non-finite",
        ),
    ],
)
def test_invalid_transfer_pole_payload_is_rejected(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    payload = _valid_payload()
    payload["transfer_eigenvalues"] = {
        "real": [1.0, 0.8],
        "imag": [0.0, 0.1],
        "shape": [2],
    }
    payload["transfer_eigenpair_residuals"] = [1e-12, 2e-11]
    payload[field] = value
    backend = _backend(tmp_path, payload)
    with pytest.raises(ValueError, match=message):
        backend.run_periodic(
            np.eye(2, dtype=complex),
            np.diag([1.0, -1.0]).astype(complex),
            _model(),
            BathConfig(alpha=0.01),
            UniformTempoControls(4, 1e-4, 2, 1, pole_count=2),
        )


def test_nonzero_runner_exit_is_reported(tmp_path: Path) -> None:
    runner = tmp_path / "failing.py"
    _write_fake_runner(runner, {}, exit_code=7)
    backend = UniformTempoBackend(command_prefix=(sys.executable, str(runner)))
    with pytest.raises(RuntimeError, match="synthetic Julia failure"):
        backend.run_periodic(
            np.eye(2, dtype=complex),
            np.diag([1.0, -1.0]).astype(complex),
            _model(),
            BathConfig(alpha=0.01),
            UniformTempoControls(4, 1e-4, 2, 1),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.pop("uniform_tempo_revision"), "provenance"),
        (lambda payload: payload.update(method="wrong"), "method"),
        (
            lambda payload: payload["correlation"].update(real=[1.0, 0.5]),
            "shape",
        ),
    ],
)
def test_malformed_payload_is_rejected(
    tmp_path: Path, mutation, message: str
) -> None:
    payload = _valid_payload()
    mutation(payload)
    backend = _backend(tmp_path, payload)
    with pytest.raises(ValueError, match=message):
        backend.run_periodic(
            np.eye(2, dtype=complex),
            np.diag([1.0, -1.0]).astype(complex),
            _model(),
            BathConfig(alpha=0.01),
            UniformTempoControls(4, 1e-4, 2, 1),
        )


def test_controls_require_commensurate_phase_sampling() -> None:
    with pytest.raises(ValueError, match="phase_samples"):
        UniformTempoControls(steps_per_period=6, tolerance=1e-5, phase_samples=4, delay_periods=1)


def test_process_tensor_key_excludes_phase_and_delay_controls() -> None:
    coupling = np.diag([1.0, -1.0]).astype(complex)
    model = _model()
    bath = BathConfig(alpha=0.01, cutoff=2.5)
    coarse = UniformTempoControls(60, 3e-7, 3, 2)
    denser_phase = UniformTempoControls(60, 3e-7, 15, 8)
    assert _tensor_cache_key(coupling, model, bath, coarse) == _tensor_cache_key(
        coupling,
        model,
        bath,
        denser_phase,
    )


def test_backend_passes_content_addressed_tensor_cache(tmp_path: Path) -> None:
    runner = tmp_path / "fake_runner.py"
    _write_fake_runner(runner, _valid_payload())
    backend = UniformTempoBackend(
        command_prefix=(sys.executable, str(runner)),
        tensor_cache_directory=tmp_path / "tensor-cache",
    )
    controls = UniformTempoControls(4, 1e-4, 2, 1)
    backend.run_periodic(
        np.array([[0.0, 0.5], [0.5, 0.0]], dtype=complex),
        np.diag([1.0, -1.0]).astype(complex),
        _model(),
        BathConfig(alpha=0.01, cutoff=2.5),
        controls,
    )
    request = json.loads((tmp_path / "captured-request.json").read_text())
    cache_key = request["controls"]["process_tensor_cache_key"]
    assert len(cache_key) == 64
    assert request["controls"]["process_tensor_cache_path"].endswith(
        f"{cache_key}.jls"
    )
