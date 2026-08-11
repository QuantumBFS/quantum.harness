import itertools

import numpy as np
import pytest

from ceffflow.channels import ConfusionChannel, ErasureChannel
from ceffflow.resolution import (
    ExactBranch,
    estimate_degraded_record_rates,
    exact_filter_observation,
    gaussian_particle_filter_observation,
    particle_filter_observation,
)
from ceffflow.self_dual import (
    SelfDualBornCylinder,
    SelfDualGaussianCylinder,
    estimate_coupled_gaussian_self_dual_record_rates,
)


def test_two_gate_filter_matches_explicit_latent_sum():
    cylinder = SelfDualBornCylinder(3)
    channel = ConfusionChannel(0.2)
    initial = cylinder.plus_state()
    observed = (1, -1)
    gates = (("zz", 0), ("x", 0))
    explicit = 0.0
    for signs in itertools.product((-1, 1), repeat=2):
        state = initial
        joint = 1.0
        for gate, sign, symbol in zip(
            gates, signs, observed, strict=True
        ):
            if gate[0] == "zz":
                state, probability = cylinder.update_zz(
                    state, gate[1], sign
                )
            else:
                state, probability = cylinder.update_x(
                    state, gate[1], sign
                )
            joint *= probability * channel.conditional_probability(
                symbol, sign
            )
        explicit += joint

    branches = [ExactBranch(1.0, initial)]
    log_likelihood = 0.0
    for gate, symbol in zip(gates, observed, strict=True):
        branches, increment = exact_filter_observation(
            branches, cylinder, gate, symbol, channel
        )
        log_likelihood += increment
    assert np.isclose(np.exp(log_likelihood), explicit, atol=1e-14)
    assert np.isclose(sum(branch.weight for branch in branches), 1.0)


def test_identity_filter_reproduces_physical_record_blocks():
    settings = dict(
        lengths=[3, 4, 5],
        steps=8,
        burn_in=2,
        block_size=4,
        seed=23,
    )
    physical = estimate_coupled_gaussian_self_dual_record_rates(**settings)
    observed = estimate_degraded_record_rates(
        **settings,
        channel=ConfusionChannel(0.0),
        particles=1,
    )
    assert np.allclose(observed.blocks, physical.blocks, atol=1e-13)


def test_complete_erasure_has_zero_observed_surprisal():
    estimate = estimate_degraded_record_rates(
        [3, 4, 5],
        ErasureChannel(0.0),
        particles=4,
        steps=4,
        burn_in=1,
        block_size=2,
        seed=9,
    )
    assert np.array_equal(estimate.blocks, np.zeros_like(estimate.blocks))


def test_maximal_confusion_has_exact_uniform_record_rate():
    lengths = np.array([3, 4, 5])
    estimate = estimate_degraded_record_rates(
        lengths,
        ConfusionChannel(0.5),
        particles=7,
        steps=6,
        burn_in=3,
        block_size=2,
        seed=19,
    )
    expected = np.broadcast_to(
        2.0 * lengths * np.log(2.0), estimate.blocks.shape
    )
    assert np.array_equal(estimate.blocks, expected)


def test_batched_gaussian_particle_filter_matches_scalar_confusion():
    gaussian = SelfDualGaussianCylinder(3)
    states = []
    for sign in (1, -1, 1, -1):
        state, _ = gaussian.update_zz(
            gaussian.plus_covariance(), 0, sign
        )
        states.append(state)
    uniforms = np.array([0.1, 0.8, 0.4, 0.6])
    channel = ConfusionChannel(0.2)
    scalar, scalar_logp = particle_filter_observation(
        states,
        gaussian,
        ("x", 1),
        1,
        channel,
        sign_uniforms=uniforms,
        resample_uniform=0.37,
    )
    batched, batched_logp = gaussian_particle_filter_observation(
        np.stack(states),
        gaussian,
        ("x", 1),
        1,
        channel,
        sign_uniforms=uniforms,
        resample_uniform=0.37,
    )
    assert np.isclose(batched_logp, scalar_logp, atol=1e-14)
    assert np.allclose(batched, np.stack(scalar), atol=1e-14)


def test_batched_gaussian_particle_filter_matches_scalar_erasure():
    gaussian = SelfDualGaussianCylinder(3)
    states = [
        gaussian.update_x(gaussian.plus_covariance(), 0, sign)[0]
        for sign in (1, -1, -1, 1)
    ]
    uniforms = np.array([0.2, 0.3, 0.7, 0.9])
    channel = ErasureChannel(0.6)
    scalar, scalar_logp = particle_filter_observation(
        states,
        gaussian,
        ("zz", 1),
        0,
        channel,
        sign_uniforms=uniforms,
        resample_uniform=0.81,
    )
    batched, batched_logp = gaussian_particle_filter_observation(
        np.stack(states),
        gaussian,
        ("zz", 1),
        0,
        channel,
        sign_uniforms=uniforms,
        resample_uniform=0.81,
    )
    assert np.isclose(batched_logp, scalar_logp, atol=1e-14)
    assert np.allclose(batched, np.stack(scalar), atol=1e-14)


@pytest.mark.parametrize(
    "channel",
    [ConfusionChannel(0.1), ErasureChannel(0.8)],
)
def test_batched_estimator_matches_scalar_orchestration(channel):
    settings = dict(
        lengths=[3, 4, 5],
        channel=channel,
        particles=8,
        steps=4,
        burn_in=2,
        block_size=2,
        seed=31,
    )
    scalar = estimate_degraded_record_rates(**settings, batched=False)
    batched = estimate_degraded_record_rates(**settings, batched=True)
    assert np.allclose(batched.blocks, scalar.blocks, atol=1e-12)
