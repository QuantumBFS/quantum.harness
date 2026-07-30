from __future__ import annotations

import json

import numpy as np
import pytest
from scipy.linalg import expm

from tensor_square import dqmc
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


def test_quadratic_moments_match_explicit_fock_trace_through_fourth_order() -> None:
    beta = 0.6
    one_body_h = np.array(
        [
            [0.3, -0.2, 0.1],
            [-0.2, -0.4, 0.25],
            [0.1, 0.25, 0.2],
        ]
    )
    probe = np.array(
        [
            [0.2, 0.35, -0.1],
            [0.35, -0.3, 0.15],
            [-0.1, 0.15, 0.45],
        ]
    )
    x = expm(-beta * one_body_h)
    rho = np.eye(3) - np.linalg.inv(np.eye(3) + x).T
    basis = basis_states(3)
    h_fock = d_gamma(one_body_h, basis).toarray()
    q_fock = d_gamma(probe, basis).toarray()
    thermal = expm(-beta * h_fock)
    partition = np.trace(thermal)

    measured = dqmc.quadratic_moments(probe, rho)

    for power, value in enumerate(measured, start=1):
        explicit = np.trace(
            thermal @ np.linalg.matrix_power(q_fock, power)
        ) / partition
        assert value == pytest.approx(explicit.real, abs=3e-12)


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


def test_measurement_reports_normalized_channel_moments() -> None:
    beta = 0.7
    model = dqmc.OneBodyModel(
        m=1,
        k=np.array([[0.3]]),
        channels=(np.array([[1.0]]), np.array([[2.0]])),
        couplings=(1.0, 0.5),
        group_a=(0,),
        group_b=(1,),
        nematic=np.array([[1.0]]),
    )
    x = np.array([[np.exp(-beta * 0.3)]])
    occupation = x.item() ** 2 / (1.0 + x.item() ** 2)

    measured = measure_configuration(x, model)

    assert measured["q_a_mean"] == pytest.approx(2.0 * occupation)
    assert measured["q_a_sq"] == pytest.approx(4.0 * occupation)
    assert measured["q_a_cube"] == pytest.approx(8.0 * occupation)
    assert measured["q_a_fourth"] == pytest.approx(16.0 * occupation)
    assert measured["q_b_mean"] == pytest.approx(4.0 * occupation)
    assert measured["q_b_fourth"] == pytest.approx(256.0 * occupation)
    assert measured["staggered_structure"] == pytest.approx(2.0 * occupation)
    assert measured["near_staggered_structure"] == pytest.approx(
        18.0 * occupation
    )


def test_summary_uses_central_moments_for_binder_ratio() -> None:
    measurements = [
        {
            "q_a_mean": value,
            "q_a_sq": value**2,
            "q_a_cube": value**3,
            "q_a_fourth": value**4,
            "direct_sign": 1.0,
            "weight_log_error": 0.0,
            "density": 0.5,
        }
        for value in (0.0, 1.0, 2.0, 3.0)
    ]

    summary = summarize_measurements(measurements)

    assert summary["q_a_central_sq"] == pytest.approx(1.25)
    assert summary["q_a_central_fourth"] == pytest.approx(2.5625)
    assert summary["q_a_binder"] == pytest.approx(0.45333333333333337)


def test_hs_static_susceptibility_subtracts_contact_term() -> None:
    value = dqmc.static_susceptibility(
        np.array([-2.0, -1.0, 1.0, 2.0]),
        beta=2.0,
        contact=3.0,
        normalization=5.0,
    )
    assert value == pytest.approx(11.0 / 15.0)


def test_hs_order_estimator_uses_each_channel_coupling_and_time_average() -> None:
    config = DQMCConfig(
        m=3,
        beta=0.4,
        dt=0.2,
        t=0.5,
        g_b_over_g_a=0.25,
    )
    model = make_one_body_model(config)
    fields = np.array([[1.0, 2.0], [3.0, 4.0]])

    measured = dqmc.hs_order_estimators(fields, model=model, dt=config.dt)

    assert measured["hs_q_a"] == pytest.approx(
        2.0 / np.sqrt(0.2 / 3.0)
    )
    assert measured["hs_q_b"] == pytest.approx(
        3.0 / np.sqrt(0.05 / 3.0)
    )
    assert measured["response_beta"] == pytest.approx(0.4)
    assert measured["q_a_susceptibility_contact"] == pytest.approx(3.0)
    assert measured["q_b_susceptibility_contact"] == pytest.approx(12.0)
    assert measured["q_a_response_normalization"] == pytest.approx(9.0)
    assert measured["q_b_response_normalization"] == pytest.approx(9.0)


def test_summary_integrates_hs_static_susceptibility() -> None:
    measurements = [
        {
            "hs_q_a": value,
            "response_beta": 2.0,
            "q_a_susceptibility_contact": 3.0,
            "q_a_response_normalization": 5.0,
            "direct_sign": 1.0,
            "weight_log_error": 0.0,
            "density": 0.5,
        }
        for value in (-2.0, -1.0, 1.0, 2.0)
    ]

    summary = summarize_measurements(measurements)

    assert summary["q_a_susceptibility"] == pytest.approx(11.0 / 15.0)


def test_second_moment_correlation_length_clamps_flat_ratio() -> None:
    assert dqmc.second_moment_correlation_length(5.0, 1.0, np.pi / 3.0) == (
        pytest.approx(2.0)
    )
    assert dqmc.second_moment_correlation_length(0.5, 1.0, np.pi / 3.0) == 0.0


def test_summary_builds_correlation_length_from_averaged_structure() -> None:
    measurements = [
        {
            "staggered_structure": 5.0,
            "near_staggered_structure": 1.0,
            "correlation_q_min": np.pi / 3.0,
            "correlation_system_size": 6.0,
            "direct_sign": 1.0,
            "weight_log_error": 0.0,
            "density": 0.5,
        }
        for _ in range(4)
    ]

    summary = summarize_measurements(measurements)

    assert summary["correlation_length_proxy"] == pytest.approx(2.0)
    assert summary["correlation_length_over_m"] == pytest.approx(1.0 / 3.0)


def test_checkpoint_resume_is_bitwise_reproducible(tmp_path) -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        proposal_scale=0.6,
        temporal_block_scale=0.15,
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
    assert resumed["temporal_block_accepted"] == uninterrupted[
        "temporal_block_accepted"
    ]
    assert resumed["temporal_block_proposed"] == uninterrupted[
        "temporal_block_proposed"
    ]
    assert resumed["temporal_reflection_accepted"] == uninterrupted[
        "temporal_reflection_accepted"
    ]
    assert resumed["temporal_reflection_proposed"] == uninterrupted[
        "temporal_reflection_proposed"
    ]


def test_default_sampler_resumes_legacy_checkpoint_and_fingerprint(
    tmp_path,
) -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        proposal_scale=0.6,
    )
    assert "temporal_block_scale" not in config.as_dict()
    uninterrupted = run_chain(
        config,
        seed=1200,
        warmup_sweeps=2,
        measurement_sweeps=4,
        measure_every=1,
        run_fingerprint="legacy-fingerprint",
    )
    checkpoint_path = tmp_path / "legacy.npz"
    run_chain(
        config,
        seed=1200,
        warmup_sweeps=2,
        measurement_sweeps=2,
        measure_every=1,
        checkpoint_path=checkpoint_path,
        checkpoint_every=2,
        run_fingerprint="legacy-fingerprint",
    )
    with np.load(checkpoint_path, allow_pickle=False) as checkpoint:
        assert "temporal_block_scale" not in json.loads(
            str(checkpoint["config_json"].item())
        )
        legacy_payload = {
            name: checkpoint[name]
            for name in checkpoint.files
            if name
            not in {
                "temporal_block_accepted",
                "temporal_block_proposed",
                "temporal_reflection_accepted",
                "temporal_reflection_proposed",
            }
        }
    np.savez_compressed(checkpoint_path, **legacy_payload)

    resumed = run_chain(
        config,
        seed=999,
        warmup_sweeps=2,
        measurement_sweeps=4,
        measure_every=1,
        checkpoint_path=checkpoint_path,
        checkpoint_every=2,
        run_fingerprint="legacy-fingerprint",
    )

    assert resumed["energy_mean"] == uninterrupted["energy_mean"]
    assert resumed["accepted"] == uninterrupted["accepted"]
    assert resumed["temporal_block_accepted"] == 0
    assert resumed["temporal_block_proposed"] == 0


def test_default_sampler_rejects_nonzero_block_checkpoint(tmp_path) -> None:
    from dataclasses import replace

    from tensor_square.dqmc import run_chain

    block_config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        temporal_block_scale=0.1,
    )
    checkpoint_path = tmp_path / "block.npz"
    run_chain(
        block_config,
        seed=1203,
        warmup_sweeps=1,
        measurement_sweeps=2,
        measure_every=1,
        checkpoint_path=checkpoint_path,
        checkpoint_every=1,
    )

    with pytest.raises(ValueError, match="checkpoint config does not match"):
        run_chain(
            replace(block_config, temporal_block_scale=0.0),
            seed=1203,
            warmup_sweeps=1,
            measurement_sweeps=2,
            measure_every=1,
            checkpoint_path=checkpoint_path,
            checkpoint_every=1,
        )


def test_default_sampler_rejects_reflection_checkpoint(tmp_path) -> None:
    from dataclasses import replace

    from tensor_square.dqmc import run_chain

    reflection_config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        temporal_reflection_updates=True,
    )
    checkpoint_path = tmp_path / "reflection.npz"
    run_chain(
        reflection_config,
        seed=1204,
        warmup_sweeps=1,
        measurement_sweeps=2,
        measure_every=1,
        checkpoint_path=checkpoint_path,
        checkpoint_every=1,
    )

    with pytest.raises(ValueError, match="checkpoint config does not match"):
        run_chain(
            replace(reflection_config, temporal_reflection_updates=False),
            seed=1204,
            warmup_sweeps=1,
            measurement_sweeps=2,
            measure_every=1,
            checkpoint_path=checkpoint_path,
            checkpoint_every=1,
        )


def test_reflection_checkpoint_resume_is_bitwise_reproducible(
    tmp_path,
) -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        proposal_scale=0.6,
        temporal_reflection_updates=True,
    )
    uninterrupted = run_chain(
        config,
        seed=1206,
        warmup_sweeps=2,
        measurement_sweeps=4,
        measure_every=1,
    )
    checkpoint_path = tmp_path / "reflection-resume.npz"
    run_chain(
        config,
        seed=1206,
        warmup_sweeps=2,
        measurement_sweeps=2,
        measure_every=1,
        checkpoint_path=checkpoint_path,
        checkpoint_every=2,
    )
    resumed = run_chain(
        config,
        seed=999,
        warmup_sweeps=2,
        measurement_sweeps=4,
        measure_every=1,
        checkpoint_path=checkpoint_path,
        checkpoint_every=2,
    )

    assert resumed["energy_mean"] == uninterrupted["energy_mean"]
    assert resumed["accepted"] == uninterrupted["accepted"]
    assert resumed["temporal_reflection_accepted"] == uninterrupted[
        "temporal_reflection_accepted"
    ]
    assert resumed["temporal_reflection_proposed"] == uninterrupted[
        "temporal_reflection_proposed"
    ]


def test_temporal_channel_block_update_reports_separate_acceptance() -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        proposal_scale=0.4,
        temporal_block_scale=0.1,
    )
    model = make_one_body_model(config)

    summary = run_chain(
        config,
        seed=1201,
        warmup_sweeps=1,
        measurement_sweeps=2,
        measure_every=1,
        progress_every=10,
    )

    assert summary["temporal_block_proposed"] == 3 * len(model.channels)
    assert 0 <= summary["temporal_block_accepted"] <= summary[
        "temporal_block_proposed"
    ]
    assert 0.0 <= summary["temporal_block_acceptance"] <= 1.0


def test_temporal_channel_reflection_reports_separate_acceptance() -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        proposal_scale=0.4,
        temporal_reflection_updates=True,
    )
    model = make_one_body_model(config)

    summary = run_chain(
        config,
        seed=1205,
        warmup_sweeps=1,
        measurement_sweeps=2,
        measure_every=1,
        progress_every=10,
    )

    assert summary["temporal_reflection_proposed"] == 3 * len(model.channels)
    assert 0 <= summary["temporal_reflection_accepted"] <= summary[
        "temporal_reflection_proposed"
    ]
    assert 0.0 <= summary["temporal_reflection_acceptance"] <= 1.0


def test_temporal_channel_block_scale_must_be_a_valid_pcn_scale() -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        temporal_block_scale=1.0,
    )

    with pytest.raises(
        ValueError, match="temporal_block_scale must be in"
    ):
        run_chain(
            config,
            seed=1202,
            warmup_sweeps=1,
            measurement_sweeps=2,
            measure_every=1,
        )


def test_temporal_block_and_reflection_cannot_be_combined() -> None:
    from tensor_square.dqmc import run_chain

    config = DQMCConfig(
        m=3,
        beta=0.2,
        dt=0.1,
        t=0.2,
        g_b_over_g_a=0.5,
        temporal_block_scale=0.1,
        temporal_reflection_updates=True,
    )

    with pytest.raises(ValueError, match="cannot be combined"):
        run_chain(
            config,
            seed=1207,
            warmup_sweeps=1,
            measurement_sweeps=2,
            measure_every=1,
        )


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
