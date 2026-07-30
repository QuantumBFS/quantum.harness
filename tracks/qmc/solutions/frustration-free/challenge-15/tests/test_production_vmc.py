from __future__ import annotations

import copy
from dataclasses import fields, replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from challenge15.artifacts import publish_production_envelope
from challenge15.cli import _parser
from challenge15.generations import claim_seed_root
from challenge15.production_policy import policy_sha256
from challenge15.production_schema import RankExtension, SeedOwner, payload_sha256
from challenge15.production_vmc import (
    FINAL_ACCEPTANCE_MAX,
    FINAL_ACCEPTANCE_MIN,
    FINAL_ESS_MINIMUM,
    FINAL_RHAT_MAXIMUM,
    ProductionVMCConfig,
    canonical_base_configuration,
    _validate_training_lineage,
    _array_bundle_bytes,
    _array_bundle_from_bytes,
    _paired_gap_payload,
    adam_init,
    adam_update,
    fixed_scientific_schedule,
    final_evaluation_gates,
    flatten_chain_walker_draw,
    independent_chain_keys,
    paired_seed_gap_uncertainty,
    rank_change_uncertainty,
    with_oom_blocks,
    score_covariance_finite_chain,
    update_gates,
    validate_post_adam_state,
    within_seed_gap_uncertainty,
)
from challenge15.vmc import SamplingDiagnostics


EXPECTED_CONFIG = {
    "optimizer": "adam",
    "learning_rate": 0.001,
    "steps": 10000,
    "weight_l0": 0.5,
    "weight_l2": 0.5,
    "chains_per_sector": 32,
    "walkers_per_chain": 32,
    "pilot_sweeps": 500,
    "burn_in_sweeps": 2000,
    "draws_per_update": 16,
    "thinning_sweeps": 2,
    "reequilibration_sweeps_after_update": 4,
    "refresh_log_amplitudes_after_update": True,
    "checkpoint_interval_steps": 100,
    "final_evaluation_chains_per_sector": 32,
    "final_evaluation_burn_in_sweeps": 5000,
    "final_evaluation_draws_per_chain": 4096,
    "final_evaluation_thinning_sweeps": 4,
    "walker_microbatch": 64,
    "carrier_block": 8,
    "quadrature_block": 64,
}

RUNTIMES = {
    "training": {"qdeshell": "1" * 64},
    "coordinate": {"qdeshell": "2" * 64},
    "oracle": {"lasg02": "3" * 64},
    "exact": {"lasg02": "4" * 64},
    "reducer": {"lasg02": "5" * 64},
}


def _claimed_root_fixture(tmp_path):
    config = ProductionVMCConfig()
    owner = SeedOwner(
        seed=0,
        experiment_id="experiment",
        base_configuration_sha256=config.base_configuration_sha256,
        expected_seed_set=(0, 1, 2, 3, 4),
        owner_uuid="11111111-1111-4111-8111-111111111111",
        claimed_at_utc="2026-07-29T00:00:00Z",
        claim_host="host",
        claim_process="pid:1",
        claim_nonce_sha256="a" * 64,
        policy_sha256=policy_sha256(),
        source_manifest_sha256="b" * 64,
        runtime_attestations=RUNTIMES,
    )
    root = tmp_path / "seed=0"
    claim_seed_root(root, owner)
    extension = RankExtension(
        particles=4,
        seed=0,
        experiment_id="experiment",
        base_configuration_sha256=config.base_configuration_sha256,
        policy_sha256=policy_sha256(),
        source_manifest_sha256="b" * 64,
        runtime_attestations=RUNTIMES,
        expected_seed_set=(0, 1, 2, 3, 4),
        previous_rank=None,
        new_rank=1,
        parent_generation_sha256=None,
        parent_parameter_sha256=None,
        parent_optimizer_state_sha256=None,
        rank_extension_decision_sha256="c" * 64,
        embedding_algorithm="copy-old-append-zero-gates-v1",
        rank_growth_prng={"algorithm": "threefry2x32", "key_sha256": "d" * 64},
        reason="initial",
        created_by_git_revision="revision",
    )
    extensions = root / "extensions"
    extensions.mkdir()
    extension_sha = payload_sha256(extension.to_payload())
    publish_production_envelope(
        extensions / f"{extension_sha}.json",
        "challenge15.rank-extension.v1",
        extension,
    )
    return config, owner, extension, root


def test_config_exact_defaults_shapes_and_base_identity():
    config = ProductionVMCConfig()

    assert {field.name for field in fields(config)} == set(EXPECTED_CONFIG)
    assert {field.name: getattr(config, field.name) for field in fields(config)} == EXPECTED_CONFIG
    assert config.walkers_per_sector == 1024
    assert config.training_draws_per_sector == 16384
    assert config.state_shape(4) == (2, 32, 32, 4, 2)
    assert config.log_amplitude_shape == (2, 32, 32)
    assert config.proposal_shape == (2, 32)
    assert replace(config, walker_microbatch=32).base_configuration_sha256 == (
        config.base_configuration_sha256
    )
    assert replace(config, walkers_per_chain=16).base_configuration_sha256 != (
        config.base_configuration_sha256
    )
    canonical = canonical_base_configuration(config)
    assert config.to_payload() == canonical
    assert canonical["schedule_version"] == "fixed-v1"
    assert set(canonical).isdisjoint(
        {"walker_microbatch", "carrier_block", "quadrature_block"}
    )
    assert set(canonical) == (
        set(EXPECTED_CONFIG)
        - {"walker_microbatch", "carrier_block", "quadrature_block"}
        | {"schedule_version"}
    )
    assert payload_sha256(canonical) == config.base_configuration_sha256


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("steps", 0),
        ("chains_per_sector", True),
        ("walker_microbatch", -1),
        ("learning_rate", np.inf),
        ("weight_l0", 0.0),
        ("optimizer", "sgd"),
        ("refresh_log_amplitudes_after_update", 1),
    ],
)
def test_config_rejects_invalid_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(ProductionVMCConfig(), **{field: value})


def test_config_requires_positive_weights_summing_to_one():
    with pytest.raises(ValueError, match="sum to one"):
        replace(ProductionVMCConfig(), weight_l0=0.4, weight_l2=0.5)


def test_vmc_train_cli_requires_an_explicit_extension():
    parser = _parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "vmc-train",
                "--base-config",
                "config.json",
                "--owner",
                "owner.json",
                "--destination",
                "seed-root",
                "--create-only",
            ]
        )


def test_training_lineage_accepts_only_preclaimed_root_without_generations(tmp_path):
    config, owner, extension, root = _claimed_root_fixture(tmp_path)

    validated_root, owner_sha, extension_sha = _validate_training_lineage(
        config, extension, root, owner
    )

    assert validated_root == root
    assert owner_sha == payload_sha256(owner.to_payload())
    assert extension_sha == payload_sha256(extension.to_payload())
    with pytest.raises(FileNotFoundError, match="pre-existing claimed seed root"):
        _validate_training_lineage(config, extension, tmp_path / "absent", owner)


def test_training_lineage_rejects_owner_config_and_generation_namespace_mismatch(
    tmp_path,
):
    config, owner, extension, root = _claimed_root_fixture(tmp_path)

    with pytest.raises(ValueError, match="permanent seed ownership"):
        _validate_training_lineage(
            config,
            extension,
            root,
            replace(
                owner,
                owner_uuid="22222222-2222-4222-8222-222222222222",
            ),
        )
    with pytest.raises(ValueError, match="base configuration"):
        _validate_training_lineage(
            replace(config, walkers_per_chain=16),
            extension,
            root,
            owner,
        )

    malformed_generation = root / "generations" / ("e" * 64)
    malformed_generation.mkdir(parents=True)
    with pytest.raises(ValueError, match="manifest"):
        _validate_training_lineage(config, extension, root, owner)


def test_score_covariance_matches_hand_computed_finite_chain_fixture():
    values = np.asarray([[1.0, 4.0], [2.0, 2.0], [5.0, 1.0]])
    scores = {
        "x": np.asarray(
            [
                [[1 + 2j, 2 - 1j], [0.5j, 3 + 0j]],
                [[2 - 1j, -1 + 2j], [1 + 0j, 4 - 2j]],
                [[-1 + 0.5j, 0.25j], [2 - 1j, -2 + 1j]],
            ],
            dtype=np.complex128,
        )
    }

    estimates, gradient = score_covariance_finite_chain(
        values, scores, weights=(0.5, 0.5)
    )

    expected_by_sector = []
    for sector in range(2):
        score = scores["x"][:, sector]
        potential = values[:, sector]
        covariance = 3 / 2 * (
            np.mean(np.conjugate(score) * potential[:, None], axis=0)
            - np.mean(np.conjugate(score), axis=0) * np.mean(potential)
        )
        expected_by_sector.append(2 * np.real(covariance))
    np.testing.assert_allclose(estimates, [8 / 3, 7 / 3])
    np.testing.assert_allclose(
        gradient["x"], 0.5 * expected_by_sector[0] + 0.5 * expected_by_sector[1]
    )
    assert gradient["x"].shape == (2,)
    assert gradient["x"].dtype == np.float64


def test_score_contract_rejects_wrong_shape_and_nonfinite_or_single_draw():
    with pytest.raises(ValueError, match="at least two"):
        score_covariance_finite_chain(
            np.ones((1, 2)), {"x": np.ones((1, 2, 3), dtype=np.complex128)}
        )
    with pytest.raises(ValueError, match="complex128"):
        score_covariance_finite_chain(
            np.ones((2, 2)), {"x": np.ones((2, 2, 3), dtype=np.complex64)}
        )
    with pytest.raises(ValueError, match="finite"):
        score_covariance_finite_chain(
            np.asarray([[1.0, np.nan], [2.0, 3.0]]),
            {"x": np.ones((2, 2, 3), dtype=np.complex128)},
        )


def test_flatten_order_is_chain_then_walker_then_draw():
    values = np.empty((2, 3, 4), dtype=np.int64)
    for chain in range(2):
        for walker in range(3):
            for draw in range(4):
                values[chain, walker, draw] = 100 * chain + 10 * walker + draw

    flattened = flatten_chain_walker_draw(values)

    np.testing.assert_array_equal(
        flattened,
        [0, 1, 2, 3, 10, 11, 12, 13, 20, 21, 22, 23,
         100, 101, 102, 103, 110, 111, 112, 113, 120, 121, 122, 123],
    )


def test_chain_keys_are_reproducible_unique_and_namespace_separated():
    training = independent_chain_keys(seed=7, chains=4, namespace="training")
    repeated = independent_chain_keys(seed=7, chains=4, namespace="training")
    final_l0 = independent_chain_keys(seed=7, chains=4, namespace="final-L0")
    final_l2 = independent_chain_keys(seed=7, chains=4, namespace="final-L2")

    np.testing.assert_array_equal(jax.random.key_data(training), jax.random.key_data(repeated))
    assert len({tuple(x) for x in np.asarray(jax.random.key_data(training))}) == 4
    assert not np.array_equal(jax.random.key_data(training), jax.random.key_data(final_l0))
    assert not np.array_equal(jax.random.key_data(final_l0), jax.random.key_data(final_l2))


def test_adam_updates_are_real_deterministic_and_resume_exactly():
    parameters = {"x": np.asarray([1.0, -2.0], dtype=np.float64)}
    gradients = [
        {"x": np.asarray([0.5, -0.25], dtype=np.float64)},
        {"x": np.asarray([-0.1, 0.3], dtype=np.float64)},
        {"x": np.asarray([0.2, 0.4], dtype=np.float64)},
    ]

    continuous_parameters = parameters
    continuous_state = adam_init(parameters)
    for gradient in gradients:
        continuous_parameters, continuous_state = adam_update(
            continuous_parameters, gradient, continuous_state, learning_rate=0.001
        )

    resumed_parameters, resumed_state = adam_update(
        parameters, gradients[0], adam_init(parameters), learning_rate=0.001
    )
    checkpoint = (copy.deepcopy(resumed_parameters), copy.deepcopy(resumed_state))
    resumed_parameters, resumed_state = checkpoint
    for gradient in gradients[1:]:
        resumed_parameters, resumed_state = adam_update(
            resumed_parameters, gradient, resumed_state, learning_rate=0.001
        )

    np.testing.assert_array_equal(
        resumed_parameters["x"], continuous_parameters["x"]
    )
    np.testing.assert_array_equal(resumed_state.first_moment["x"], continuous_state.first_moment["x"])
    np.testing.assert_array_equal(resumed_state.second_moment["x"], continuous_state.second_moment["x"])
    assert resumed_state.step == continuous_state.step == 3


def test_post_adam_gate_rejects_any_nonfinite_published_state():
    finite = {"x": np.asarray([1.0])}
    validate_post_adam_state(
        parameters=finite,
        optimizer_state=(finite, finite),
        updates=finite,
        refreshed_amplitudes=np.asarray([1.0 + 0.0j]),
        estimates=np.asarray([1.0, 2.0]),
    )
    for field in (
        "parameters",
        "optimizer_state",
        "updates",
        "refreshed_amplitudes",
        "estimates",
    ):
        values = {
            "parameters": finite,
            "optimizer_state": (finite, finite),
            "updates": finite,
            "refreshed_amplitudes": np.asarray([1.0 + 0.0j]),
            "estimates": np.asarray([1.0, 2.0]),
        }
        values[field] = {"x": np.asarray([np.nan])}
        with pytest.raises(FloatingPointError, match=field):
            validate_post_adam_state(**values)


def test_checkpoint_array_bundles_round_trip_exactly_and_reject_truncation():
    values = (
        np.arange(2 * 3 * 4, dtype=np.float64).reshape(2, 3, 4)
        + 1j
    ).astype(np.complex128)
    encoded = _array_bundle_bytes(values)

    restored = _array_bundle_from_bytes(encoded)

    assert restored.dtype == np.complex128
    np.testing.assert_array_equal(restored, values)
    with pytest.raises(ValueError, match="payload size"):
        _array_bundle_from_bytes(encoded[:-1])


def test_fixed_schedule_has_exact_lifecycle_and_four_reequilibration_sweeps():
    config = replace(
        ProductionVMCConfig(),
        steps=2,
        pilot_sweeps=3,
        burn_in_sweeps=2,
        draws_per_update=2,
        thinning_sweeps=2,
        checkpoint_interval_steps=1,
    )

    schedule = fixed_scientific_schedule(config)

    assert schedule[:5] == (
        ("pilot", -1, 0),
        ("pilot", -1, 1),
        ("pilot", -1, 2),
        ("burn_in", -1, 0),
        ("burn_in", -1, 1),
    )
    for step in range(2):
        events = [event[0] for event in schedule if event[1] == step]
        assert events == [
            "thin", "thin", "retain",
            "thin", "thin", "retain",
            "update", "refresh",
            "reequilibrate", "reequilibrate", "reequilibrate", "reequilibrate",
            "checkpoint",
        ]


def test_oom_retry_changes_only_block_layout():
    config = ProductionVMCConfig()
    retry = with_oom_blocks(
        config, walker_microbatch=16, carrier_block=2, quadrature_block=8
    )

    assert retry.base_configuration_sha256 == config.base_configuration_sha256
    assert retry.walkers_per_sector == config.walkers_per_sector
    assert fixed_scientific_schedule(retry) == fixed_scientific_schedule(config)
    with pytest.raises(TypeError):
        with_oom_blocks(config, walkers_per_chain=16)
    with pytest.raises(ValueError, match="smaller"):
        with_oom_blocks(config, walker_microbatch=config.walker_microbatch)


def test_update_and_final_gates_are_code_owned_and_fail_closed():
    assert update_gates(
        retained_by_sector=(np.asarray([1.0, 2.0]), np.asarray([3.0, 4.0])),
        finite_trees=({"x": jnp.asarray([1.0])},),
        total_acceptance=0.5,
    ).passed
    assert not update_gates(
        retained_by_sector=(np.asarray([1.0]), np.asarray([3.0, 4.0])),
        finite_trees=({"x": jnp.asarray([1.0])},),
        total_acceptance=0.5,
    ).passed

    passing = {
        key: {
            "autocorrelation_converged": True,
            "effective_sample_size": FINAL_ESS_MINIMUM,
            "split_rhat": FINAL_RHAT_MAXIMUM,
            "local_acceptance": FINAL_ACCEPTANCE_MIN,
            "total_acceptance": FINAL_ACCEPTANCE_MAX,
            "estimate": 1.0,
            "standard_error": 0.1,
            "confidence_interval": {"low": 0.8, "high": 1.2},
            "covariance": 0.0,
        }
        for key in ("L0", "L2", "gap")
    }
    assert final_evaluation_gates(passing, chains_per_sector=4).passed
    passing["gap"]["split_rhat"] = np.nextafter(FINAL_RHAT_MAXIMUM, np.inf)
    assert not final_evaluation_gates(passing, chains_per_sector=4).passed
    passing["gap"]["split_rhat"] = 1.0
    passing["gap"]["standard_error"] = -0.1
    assert not final_evaluation_gates(passing, chains_per_sector=4).passed


def test_gap_uncertainty_contracts_and_pending_inputs():
    within = within_seed_gap_uncertainty(0.04, 0.09, independent_sector_chains=True)
    assert within.accepted
    assert within.variance == pytest.approx(0.13)
    assert not within_seed_gap_uncertainty(
        0.04, 0.09, independent_sector_chains=False
    ).accepted

    paired = paired_seed_gap_uncertainty([1.0, 2.0, 4.0], [2.0, 4.0, 7.0])
    covariance = np.cov([1.0, 2.0, 4.0], [2.0, 4.0, 7.0], ddof=1)
    assert paired.accepted
    assert paired.variance == pytest.approx(
        (covariance[0, 0] + covariance[1, 1] - 2 * covariance[0, 1]) / 3
    )
    assert not paired_seed_gap_uncertainty([1.0], [2.0]).accepted
    assert not paired_seed_gap_uncertainty(
        {0: 1.0, 1: 2.0}, {1: 2.0, 2: 3.0}
    ).accepted
    five_seed_e0 = {seed: float(seed) for seed in range(5)}
    five_seed_e2 = {seed: float(seed + 1) for seed in range(5)}
    assert paired_seed_gap_uncertainty(five_seed_e0, five_seed_e2).accepted
    assert not paired_seed_gap_uncertainty(
        {seed: five_seed_e0[seed] for seed in range(4)},
        {seed: five_seed_e2[seed] for seed in range(4)},
    ).accepted

    rank = rank_change_uncertainty([1.0, 3.0, 6.0], [2.0, 5.0, 9.0])
    assert rank.accepted
    assert rank.standard_error == pytest.approx(
        np.sqrt(np.var([1.0, 2.0, 3.0], ddof=1) / 3)
    )


def test_single_seed_coordinate_shard_keeps_five_seed_covariance_pending():
    diagnostics = SamplingDiagnostics(
        estimate=1.0,
        standard_error=0.1,
        integrated_autocorrelation_time=1.0,
        effective_sample_size=2_000.0,
        split_rhat=1.0,
        autocorrelation_converged=True,
    )
    within_seed = within_seed_gap_uncertainty(
        0.04, 0.09, independent_sector_chains=True
    )

    payload = _paired_gap_payload(
        0,
        1.0,
        np.sqrt(0.13),
        diagnostics,
        0.04,
        0.09,
        within_seed,
        2.0,
        3.0,
    )

    assert payload["within_seed_inputs"][0]["seed"] == 0
    assert payload["between_seed_inputs"]["paired_seed_ids"] == [0]
    assert payload["uncertainty_status"] == "pending"
