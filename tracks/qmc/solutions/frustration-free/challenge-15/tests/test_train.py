from __future__ import annotations

import jax
import numpy as np
import pytest

import challenge15
from challenge15.model import embed_adam_state, embed_rank
from challenge15.spec import SphereSpec
from challenge15.train import (
    RankEvaluation,
    SeedRankEvaluation,
    TrainConfig,
    analyze_rank_convergence,
    analyze_stochastic_rank_convergence,
    train_joint_sectors,
)


def test_training_interfaces_are_publicly_exported():
    assert challenge15.TrainConfig is TrainConfig
    assert challenge15.train_joint_sectors is train_joint_sectors
    assert challenge15.analyze_rank_convergence is analyze_rank_convergence
    assert (
        challenge15.analyze_stochastic_rank_convergence
        is analyze_stochastic_rank_convergence
    )
    assert challenge15.SeedRankEvaluation is SeedRankEvaluation


def test_joint_training_returns_one_parameter_tree_with_paired_provenance():
    result = train_joint_sectors(
        SphereSpec(2),
        TrainConfig(
            steps=1,
            rank=1,
            seed=4,
            batch_size=2,
            hidden_width=4,
            depth=0,
            token_width=2,
            fourier_order=1,
        ),
    )

    assert result.shared_parameters is not None
    assert not hasattr(result, "parameters_l0")
    assert not hasattr(result, "parameters_l2")
    assert len(result.steps) == 1
    assert result.steps[0].sector_order == (0, 2)
    assert result.steps[0].paired_batch_sha256
    assert result.steps[0].prng_before != result.steps[0].prng_after
    assert np.isfinite(result.steps[0].energy_l0)
    assert np.isfinite(result.steps[0].energy_l2)
    assert result.steps[0].acceptance_rate_l0 is None
    assert result.steps[0].acceptance_rate_l2 is None
    assert result.steps[0].diagnostic_parameter_state == "pre_update"


def test_both_sector_losses_have_nonzero_update_signal():
    result = train_joint_sectors(
        SphereSpec(2),
        TrainConfig(
            steps=1,
            rank=1,
            seed=14,
            batch_size=3,
            hidden_width=4,
            depth=0,
            token_width=2,
            fourier_order=1,
        ),
    )

    assert result.steps[0].gradient_norm_l0 > 0
    assert result.steps[0].gradient_norm_l2 > 0


def test_real_adam_moments_survive_rank_embedding_with_new_moments_zero():
    config = TrainConfig(
        steps=1,
        rank=1,
        seed=15,
        batch_size=3,
        hidden_width=4,
        depth=0,
        token_width=2,
        fourier_order=1,
    )
    result = train_joint_sectors(SphereSpec(2), config)
    old_mu = result.optimizer_state[0].mu
    assert any(
        np.any(np.asarray(leaf) != 0) for leaf in jax.tree.leaves(old_mu)
    )
    expanded_parameters = embed_rank(
        result.shared_parameters,
        1,
        2,
        key=jax.random.key(99),
    )

    expanded_state = embed_adam_state(
        result.optimizer_state,
        expanded_parameters,
        old_rank=1,
        new_rank=2,
    )

    for name in ("carrier_tokens", "carrier_gates"):
        np.testing.assert_array_equal(
            expanded_state[0].mu[name][:1],
            old_mu[name],
        )
        np.testing.assert_array_equal(
            expanded_state[0].mu[name][1:],
            np.zeros_like(expanded_state[0].mu[name][1:]),
        )


def test_joint_training_is_byte_deterministic_for_same_seed():
    config = TrainConfig(
        steps=1,
        rank=1,
        seed=7,
        batch_size=2,
        hidden_width=4,
        depth=0,
        token_width=2,
        fourier_order=1,
    )

    first = train_joint_sectors(SphereSpec(2), config)
    second = train_joint_sectors(SphereSpec(2), config)

    assert first.parameter_sha256 == second.parameter_sha256
    assert first.prng_provenance == second.prng_provenance
    assert first.steps == second.steps


def test_train_config_has_no_private_sector_model_option():
    assert "separate_sector_models" not in TrainConfig.__dataclass_fields__


def test_exact_rank_convergence_requires_two_doublings_and_zero_sigma():
    too_short = [
        RankEvaluation(1, 1.0, 1.2, overlap_l0=0.999, overlap_l2=0.999),
        RankEvaluation(2, 1.00001, 1.20001, overlap_l0=0.999, overlap_l2=0.999),
    ]
    assert not analyze_rank_convergence(too_short).accepted

    invalid_exact = [
        RankEvaluation(1, 1.0, 1.2, overlap_l0=0.999, overlap_l2=0.999),
        RankEvaluation(2, 1.00001, 1.20001, overlap_l0=0.999, overlap_l2=0.999),
        RankEvaluation(
            4,
            1.00002,
            1.20002,
            sigma_diff_l0=1e-3,
            sigma_diff_l2=1e-3,
            sigma_diff_gap=1e-3,
            overlap_l0=0.999,
            overlap_l2=0.999,
        ),
    ]
    result = analyze_rank_convergence(invalid_exact)
    assert not result.accepted
    assert not result.transitions
    assert "exact" in result.reason
    assert "zero" in result.reason


def test_rank_convergence_accepts_only_two_exact_passing_doublings():
    evaluations = [
        RankEvaluation(1, 1.0, 1.2, overlap_l0=0.9980, overlap_l2=0.9980),
        RankEvaluation(2, 1.00001, 1.20001, overlap_l0=0.9985, overlap_l2=0.9985),
        RankEvaluation(4, 1.00002, 1.20002, overlap_l0=0.9990, overlap_l2=0.9990),
    ]

    result = analyze_rank_convergence(evaluations)

    assert result.accepted
    assert len(result.transitions) == 2
    assert all(transition.passed for transition in result.transitions)
    assert all(
        transition.energy_l0_bound == transition.delta_energy_l0
        and transition.energy_l2_bound == transition.delta_energy_l2
        and transition.gap_bound == transition.delta_gap
        for transition in result.transitions
    )


def test_stochastic_rank_convergence_requires_identical_paired_seed_sets():
    evaluations = [
        SeedRankEvaluation(rank, seed, 1.0 + rank * 1e-6, 1.2 + rank * 1e-6)
        for rank in (1, 2, 4)
        for seed in (0, 1)
    ]
    assert analyze_stochastic_rank_convergence(evaluations).accepted

    missing_pair = evaluations[:-1]
    result = analyze_stochastic_rank_convergence(missing_pair)
    assert not result.accepted
    assert not result.transitions
    assert "identical paired seed sets" in result.reason


def test_stochastic_rank_convergence_fails_closed_with_one_pair():
    evaluations = [
        SeedRankEvaluation(rank, 0, 1.0 + rank * 1e-6, 1.2 + rank * 1e-6)
        for rank in (1, 2, 4)
    ]

    result = analyze_stochastic_rank_convergence(evaluations)

    assert not result.accepted
    assert "at least two paired seeds" in result.reason


def test_acceptance_tolerances_cannot_be_overridden():
    evaluations = [
        RankEvaluation(1, 1.0, 1.2),
        RankEvaluation(2, 1.0, 1.2),
        RankEvaluation(4, 1.0, 1.2),
    ]

    with pytest.raises(TypeError):
        analyze_rank_convergence(evaluations, energy_tolerance=1.0)


@pytest.mark.parametrize(
    "evaluations",
    [
        [
            RankEvaluation(1, 1.0, 1.2),
            RankEvaluation(3, 1.0, 1.2),
            RankEvaluation(6, 1.0, 1.2),
        ],
        [
            RankEvaluation(1, 1.0, 1.2),
            RankEvaluation(2, 1.0, 1.2),
            RankEvaluation(4, 1.0, 0.9),
        ],
    ],
)
def test_rank_convergence_rejects_non_nested_or_nonpositive_gap(evaluations):
    assert not analyze_rank_convergence(evaluations).accepted
