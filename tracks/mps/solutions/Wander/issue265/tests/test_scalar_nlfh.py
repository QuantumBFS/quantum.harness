from __future__ import annotations

import numpy as np
import pytest

from src.scalar_nlfh import (
    ScalarParams,
    conservative_scalar_step,
    normalized_burgers_coefficient,
    scalar_transfer_logz,
    simulate_scalar,
    simulate_scalar_ensemble,
)


def test_normalized_coefficient_has_registered_amplitude_and_parity() -> None:
    up = normalized_burgers_coefficient(g=1.2, mu=0.05, orientation=1)
    down = normalized_burgers_coefficient(g=1.2, mu=0.05, orientation=-1)
    assert up == 0.12
    assert down == -up


def test_scalar_step_is_conservative_and_spin_flip_equivariant() -> None:
    x = np.linspace(-4.0, 4.0, 16, endpoint=False)
    m = 0.1 * np.sin(2 * np.pi * np.arange(x.size) / x.size)
    noise = np.linspace(-1.0, 1.0, x.size)
    params = ScalarParams(D=0.8, g=0.6)
    up = conservative_scalar_step(
        m,
        dx=x[1] - x[0],
        dt=0.001,
        params=params,
        orientation=1,
        noise=noise,
    )
    down = conservative_scalar_step(
        -m,
        dx=x[1] - x[0],
        dt=0.001,
        params=params,
        orientation=-1,
        noise=-noise,
    )
    np.testing.assert_allclose(down, -up, atol=1e-14)
    np.testing.assert_allclose(np.sum(up), np.sum(m), atol=1e-14)


def test_scalar_trajectory_records_center_transfer() -> None:
    x = np.linspace(-4.0, 4.0, 16, endpoint=False)
    t = np.array([0.0, 0.001, 0.002])
    result = simulate_scalar(
        x=x,
        t=t,
        m0=0.05 * np.tanh(x),
        params=ScalarParams(D=0.8, g=0.6),
        orientation=1,
        dt_internal=0.001,
        noise_faces=None,
    )
    assert result.current_output.shape == (3, 16)
    assert result.integrated_current_output[0] == 0.0
    np.testing.assert_allclose(
        result.integrated_current_output[-1],
        np.sum(result.current_origin) * 0.001,
    )


def test_scalar_ensemble_generates_time_resolved_fcs() -> None:
    x = np.linspace(-4.0, 4.0, 16, endpoint=False)
    t = np.array([0.0, 0.001, 0.002])
    ensemble = simulate_scalar_ensemble(
        x=x,
        t=t,
        m0=np.zeros_like(x),
        params=ScalarParams(D=0.8, g=0.6),
        orientation=1,
        dt_internal=0.001,
        n_ensemble=16,
        seed=41,
    )
    gamma = np.array([-0.4, -0.2, 0.0, 0.2, 0.4])
    logz = scalar_transfer_logz(ensemble, gamma)
    np.testing.assert_array_equal(logz[:, 2], 0.0)
    np.testing.assert_allclose(logz[:, :2], np.conj(logz[:, -1:-3:-1]))
    np.testing.assert_allclose(
        ensemble.current_cumulants_time[0], np.zeros(4), atol=1e-15
    )


def test_scalar_step_rejects_advective_cfl_violation() -> None:
    with pytest.raises(ValueError, match="advective"):
        conservative_scalar_step(
            np.full(8, 10.0),
            dx=1.0,
            dt=0.1,
            params=ScalarParams(D=0.1, g=1.0),
            orientation=1,
            noise=None,
        )
