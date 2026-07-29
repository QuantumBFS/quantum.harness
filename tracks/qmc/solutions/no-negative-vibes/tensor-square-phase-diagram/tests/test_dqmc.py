from __future__ import annotations

import numpy as np
import pytest
from scipy.linalg import expm

from tensor_square.algebra import kron_sum
from tensor_square.dqmc import (
    DQMCConfig,
    density_matrix_from_history,
    direct_log_weight,
    make_one_body_model,
    measure_configuration,
    structured_log_weight,
    StabilizedProduct,
    stabilized_density_matrix,
    stabilized_direct_log_weight,
    stabilized_structured_log_weight,
    summarize_measurements,
    wick_product,
)
from tensor_square.fock import basis_states, d_gamma


def test_structured_log_weight_matches_direct_path() -> None:
    rng = np.random.default_rng(7331)
    for m in (2, 3, 4):
        x = np.eye(m)
        for _ in range(4):
            x = expm(rng.normal(scale=0.25, size=(m, m))) @ x
        sign, direct = direct_log_weight(x)
        assert sign > 0.0
        assert structured_log_weight(x) == pytest.approx(direct, abs=2e-10)


def test_wick_q_square_matches_explicit_fock_trace() -> None:
    beta = 0.7
    one_body_h = np.array(
        [
            [0.2, -0.3, 0.0, 0.1],
            [-0.3, -0.1, 0.2, 0.0],
            [0.0, 0.2, 0.4, -0.2],
            [0.1, 0.0, -0.2, -0.3],
        ]
    )
    probe = np.array(
        [
            [0.1, 0.2, 0.0, 0.0],
            [0.2, -0.4, 0.3, 0.0],
            [0.0, 0.3, 0.2, -0.1],
            [0.0, 0.0, -0.1, 0.5],
        ]
    )
    x = expm(-beta * one_body_h)
    rho = np.eye(4) - np.linalg.inv(np.eye(4) + x).T
    basis = basis_states(4)
    h_fock = d_gamma(one_body_h, basis).toarray()
    q_fock = d_gamma(probe, basis).toarray()
    thermal = expm(-beta * h_fock)
    explicit = np.trace(thermal @ q_fock @ q_fock) / np.trace(thermal)
    assert wick_product(probe, probe, rho) == pytest.approx(
        explicit.real, abs=3e-12
    )


def test_noninteracting_measurement_matches_one_body_thermodynamics() -> None:
    config = DQMCConfig(
        m=3,
        beta=1.3,
        dt=0.1,
        t=0.4,
        g_b_over_g_a=0.0,
        g_a=0.0,
        mu=0.2,
        v_asymmetry=0.15,
    )
    model = make_one_body_model(config)
    x = expm(-config.beta * model.k)
    measured = measure_configuration(x, model)
    full_h = kron_sum(model.k)
    occupations = 1.0 / (1.0 + np.exp(config.beta * np.linalg.eigvalsh(full_h)))
    assert measured["density"] == pytest.approx(np.mean(occupations), abs=2e-12)


def test_checkpoint_resume_is_bitwise_reproducible(tmp_path) -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        proposal_scale=0.6,
    )
    uninterrupted = run_chain(
        config,
        seed=991,
        warmup_sweeps=2,
        measurement_sweeps=4,
        measure_every=1,
        progress_every=10,
    )
    checkpoint = tmp_path / "resume.npz"
    run_chain(
        config,
        seed=991,
        warmup_sweeps=2,
        measurement_sweeps=2,
        measure_every=1,
        progress_every=10,
        checkpoint_path=checkpoint,
        checkpoint_every=2,
    )
    resumed = run_chain(
        config,
        seed=991,
        warmup_sweeps=2,
        measurement_sweeps=4,
        measure_every=1,
        progress_every=10,
        checkpoint_path=checkpoint,
        checkpoint_every=2,
    )
    assert resumed["energy_mean"] == uninterrupted["energy_mean"]
    assert resumed["accepted"] == uninterrupted["accepted"]


def test_stabilized_tensor_product_spans_sixty_log_units() -> None:
    logs = np.array([-30.0, -8.0, 7.0, 30.0])
    product = StabilizedProduct(np.eye(4), logs, np.eye(4))
    sign, direct = stabilized_direct_log_weight(product)
    structured = stabilized_structured_log_weight(product)
    assert sign > 0.0
    assert structured == pytest.approx(direct, abs=2e-11)
    rho = stabilized_density_matrix(product)
    expected = np.empty(16)
    singular = np.exp(logs)
    for index, value in enumerate(np.kron(singular, singular)):
        expected[index] = value / (1.0 + value)
    assert np.diag(rho) == pytest.approx(expected, abs=2e-12)
    assert np.all(np.isfinite(rho))


def test_chain_honors_explicit_stabilization_below_default_beta() -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        proposal_scale=0.4,
        stabilize=True,
    )
    summary = run_chain(
        config,
        seed=732,
        warmup_sweeps=0,
        measurement_sweeps=1,
        measure_every=1,
        progress_every=2,
    )
    assert summary["stabilized"] is True


def test_measurement_summary_preserves_audit_extrema() -> None:
    measurements = [
        {
            "direct_sign": 1.0,
            "weight_log_error": 1.0e-12,
            "density": 0.25,
        },
        {
            "direct_sign": -1.0,
            "weight_log_error": 2.0e-4,
            "density": 1.01,
        },
    ]
    summary = summarize_measurements(measurements)
    assert summary["direct_sign_min"] == -1.0
    assert summary["weight_log_error_max"] == 2.0e-4
    assert summary["density_min"] == 0.25
    assert summary["density_max"] == 1.01


def test_checkpoint_rejects_changed_run_fingerprint(tmp_path) -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
    )
    checkpoint = tmp_path / "fingerprint.npz"
    run_chain(
        config,
        seed=81,
        warmup_sweeps=1,
        measurement_sweeps=2,
        measure_every=1,
        progress_every=10,
        checkpoint_path=checkpoint,
        checkpoint_every=1,
        run_fingerprint="run-a",
    )
    with pytest.raises(ValueError, match="fingerprint"):
        run_chain(
            config,
            seed=81,
            warmup_sweeps=1,
            measurement_sweeps=2,
            measure_every=1,
            progress_every=10,
            checkpoint_path=checkpoint,
            checkpoint_every=1,
            run_fingerprint="run-b",
        )
