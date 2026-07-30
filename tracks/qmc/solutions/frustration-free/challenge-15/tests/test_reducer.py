from __future__ import annotations

import hashlib
from pathlib import Path
import shutil

import pytest

from challenge15.artifacts import publish_create_only, publish_production_envelope
from challenge15.production_policy import policy_sha256
from challenge15.production_schema import (
    SCIENTIFIC_NESTED_CONTRACTS,
    canonical_json,
    contract_fixture,
    envelope_for,
    payload_sha256,
    validate_envelope,
)
from challenge15.reducer import (
    _training_equivalence_gate,
    aggregate_coordinate_seed_uncertainty,
    build_identity_map,
    expected_ranks_sha256,
    publish_reduction,
    reduce_size,
    slurm_array_spec,
    validate_size_result_semantics,
)


SHA = "a" * 64
RUNTIMES = {
    "training": {"qdeshell": "1" * 64},
    "coordinate": {"qdeshell": "2" * 64},
    "oracle": {"lasg02": "3" * 64},
    "exact": {"lasg02": "4" * 64},
    "reducer": {"lasg02": "5" * 64},
}
COMMON = {
    "policy_sha256": policy_sha256(),
    "source_manifest_sha256": SHA,
    "runtime_attestations": RUNTIMES,
    "base_configuration_sha256": "b" * 64,
    "particles": 6,
}


def test_pending_training_oom_equivalence_forces_acceptance_pending():
    failed = []
    passed = _training_equivalence_gate(
        {
            "training_metrics": {
                "metric_equivalence": {"classification": "pending"}
            }
        },
        failed,
        rank=1,
        seed=0,
    )

    assert passed is False
    assert failed == [
        {
            "kind": "training",
            "rank": 1,
            "seed": 0,
            "reason": "metric-equivalence-pending",
        }
    ]


def _statistic(estimate: float, error: float = 1e-6) -> dict:
    return {
        "estimate": estimate,
        "standard_error": error,
        "ci_low": estimate - 2 * error,
        "ci_high": estimate + 2 * error,
    }


def _primitive_metrics(offset: float = 0.0, overlap: float = 1.0) -> dict:
    metrics = contract_fixture(
        SCIENTIFIC_NESTED_CONTRACTS[
            "challenge15.exact-evaluation-shard.v1"
        ]["primitive_metrics"]
    )
    metrics.update({
        "energy_by_sector": {
            "L0": _statistic(1.0 + offset),
            "L2": _statistic(2.0 + offset),
        },
        "gap": {
            **_statistic(1.0),
            "monte_carlo_covariance_e0_e2": 0.0,
            "optimizer_induced_covariance_e0_e2": 0.0,
        },
        "overlap_by_sector": {
            "L0": _statistic(overlap),
            "L2": _statistic(overlap),
        },
        "symmetry_residual_by_sector": {"L0": 0.0, "L2": 0.0},
        "per_state_gate_inputs_by_sector": {
            "L0": {"finite": True, "normalized_amplitude_nonzero": True},
            "L2": {"finite": True, "normalized_amplitude_nonzero": True},
        },
        "quadrature_change_by_sector": {
            "L0": {
                "normalized_amplitude": 0.0,
                "energy": 0.0,
                "symmetry": 0.0,
            },
            "L2": {
                "normalized_amplitude": 0.0,
                "energy": 0.0,
                "symmetry": 0.0,
            },
        },
        "projected_span": {
            "singular_values_by_sector": {"L0": [1.0], "L2": [1.0]},
            "numerical_rank_by_sector": {"L0": 1, "L2": 1},
            "dim_m_l_by_sector": {"L0": 1, "L2": 1},
            "completeness_claim_by_sector": {"L0": True, "L2": True},
        },
    })
    return metrics


def _oracle_payload() -> dict:
    nested = SCIENTIFIC_NESTED_CONTRACTS["challenge15.production-oracle.v1"]
    payload = {**COMMON, **{name: contract_fixture(spec) for name, spec in nested.items()}}
    payload["sphere_spec"]["particles"] = 6
    payload["sector_summaries"]["L0"]["lowest_energy_ec"] = 1.0
    payload["sector_summaries"]["L2"]["lowest_energy_ec"] = 2.0
    payload["low_energy_scan"]["ordered_levels"] = [
        {"L": 0, "index": 0, "energy_ec": 1.0},
        {"L": 2, "index": 0, "energy_ec": 2.0},
    ]
    payload["gate_metrics"] = {
        "hilbert_space": True,
        "gauge_rotation": True,
        "hamiltonian": True,
        "production_accepted": True,
    }
    return payload


def _extension_payload(
    seed: int,
    rank: int,
    parent_digest: str | None,
    parent_payload: dict | None,
) -> dict:
    return {
        **COMMON,
        "seed": seed,
        "experiment_id": "experiment",
        "expected_seed_set": [0, 1, 2, 3, 4],
        "previous_rank": None if parent_payload is None else rank // 2,
        "new_rank": rank,
        "parent_generation_sha256": parent_digest,
        "parent_parameter_sha256": (
            None if parent_payload is None else parent_payload["parameter_sha256"]
        ),
        "parent_optimizer_state_sha256": (
            None
            if parent_payload is None
            else parent_payload["optimizer_state_sha256"]
        ),
        "rank_extension_decision_sha256": hashlib.sha256(
            f"decision:{rank}:{seed}".encode()
        ).hexdigest(),
        "embedding_algorithm": "copy-old-append-zero-gates-v1",
        "rank_growth_prng": {
            "algorithm": "threefry2x32",
            "key_sha256": hashlib.sha256(
                f"rank-growth:{rank}:{seed}".encode()
            ).hexdigest(),
        },
        "reason": "initial" if parent_payload is None else "scheduled_initial_ladder",
        "created_by_git_revision": "revision",
    }


def _generation_payload(
    seed: int,
    rank: int,
    parent: str | None,
    extension_sha: str,
) -> dict:
    return {
        **COMMON,
        "seed": seed,
        "rank": rank,
        "attempt_sha256": hashlib.sha256(f"attempt:{rank}:{seed}".encode()).hexdigest(),
        "extension_sha256": extension_sha,
        "parent_generation_sha256": parent,
        "parent_parameter_sha256": (
            None
            if parent is None
            else hashlib.sha256(f"parameter:{rank // 2}:{seed}".encode()).hexdigest()
        ),
        "parent_optimizer_state_sha256": (
            None
            if parent is None
            else hashlib.sha256(f"optimizer:{rank // 2}:{seed}".encode()).hexdigest()
        ),
        "parameter_sha256": hashlib.sha256(f"parameter:{rank}:{seed}".encode()).hexdigest(),
        "optimizer_state_sha256": hashlib.sha256(f"optimizer:{rank}:{seed}".encode()).hexdigest(),
        "terminal_snapshot_sha256": hashlib.sha256(
            f"snapshot:{rank}:{seed}".encode()
        ).hexdigest(),
        "training_metrics": {
            "terminal_step": 10_000,
            "finite": True,
            "loss": 0.0,
            "energy_by_sector": {
                "L0": _statistic(1.0),
                "L2": _statistic(2.0),
            },
            "metric_equivalence": contract_fixture(
                SCIENTIFIC_NESTED_CONTRACTS[
                    "challenge15.training-generation.v1"
                ]["training_metrics"]["metric_equivalence"]
            ),
        },
    }


def _coordinate_payload(seed: int, rank: int, generation_sha: str) -> dict:
    nested = SCIENTIFIC_NESTED_CONTRACTS[
        "challenge15.coordinate-evaluation-shard.v1"
    ]
    payload = {
        **COMMON,
        "seed": seed,
        "rank": rank,
        "generation_sha256": generation_sha,
        "parameter_sha256": hashlib.sha256(
            f"parameter:{rank}:{seed}".encode()
        ).hexdigest(),
        "evaluation_prng_sha256": hashlib.sha256(
            f"evaluation:{rank}:{seed}".encode()
        ).hexdigest(),
        **{name: contract_fixture(spec) for name, spec in nested.items()},
    }
    payload["sampler_configuration"]["chains"] = 4
    payload["sampler_configuration"]["draws"] = 2
    payload["execution_validation"] = {
        "selected_layout": {
            "walker_microbatch": 1,
            "determinant_block": None,
            "carrier_block": 1,
            "quadrature_block": 1,
        },
        "metric_equivalence": {
            "canonical_completed": True,
            "bitwise_equal": True,
            "classification": "passed",
        },
    }
    for sector, estimate in (("L0", 1.0), ("L2", 2.0)):
        diagnostic = payload["sector_diagnostics"][sector]
        diagnostic.update(
            estimate=estimate,
            standard_error=1e-6,
            tau_int=1.0,
            effective_sample_size=2_000.0,
            split_rhat=1.0,
            autocorrelation_converged=True,
            rigid_acceptance=0.5,
            local_acceptance=0.5,
            total_acceptance=0.5,
            confidence_interval={"low": estimate - 2e-6, "high": estimate + 2e-6},
        )
        diagnostic["per_chain"][0].update(
            estimate=estimate,
            standard_error=1e-6,
            tau_int=1.0,
            effective_sample_size=2_000.0,
            split_rhat=1.0,
            rigid_acceptance=0.5,
            local_acceptance=0.5,
            total_acceptance=0.5,
            confidence_interval={"low": estimate - 2e-6, "high": estimate + 2e-6},
        )
    paired = payload["paired_gap_diagnostics"]
    paired.update(
        **_statistic(1.0),
        tau_int_e0=1.0,
        tau_int_e2=1.0,
        tau_int_gap=1.0,
        effective_sample_size=2_000.0,
        split_rhat=1.0,
        autocorrelation_converged=True,
        uncertainty_status="pending",
    )
    within_template = paired["within_seed_inputs"][0]
    paired["within_seed_inputs"] = [
        {
            **within_template,
            "seed": seed,
            "e0": 1.0,
            "e2": 2.0,
            "variance_mc_e0": 1e-12,
            "variance_mc_e2": 1e-12,
            "monte_carlo_covariance_e0_e2": 0.0,
            "variance_mc_gap": 2e-12,
        }
    ]
    paired["between_seed_inputs"].update(
        paired_seed_ids=[seed],
        e0_seed_estimates=[1.0],
        e2_seed_estimates=[2.0],
        paired_seed_count=1,
    )
    payload["gate_metrics"] = {name: False for name in payload["gate_metrics"]}
    return payload


def _exact_payload(
    seed: int,
    rank: int,
    generation_sha: str,
    *,
    overlap: float = 1.0,
) -> dict:
    equivalence = contract_fixture(
        SCIENTIFIC_NESTED_CONTRACTS[
            "challenge15.exact-evaluation-shard.v1"
        ]["metric_equivalence"]
    )
    equivalence.update(
        reference_sha256="c" * 64,
        absolute_tolerance=1e-12,
        maximum_difference=0.0,
        classification="passed",
        ambiguous=False,
        straddled_gates=[],
        passed=True,
    )
    return {
        **COMMON,
        "seed": seed,
        "rank": rank,
        "generation_sha256": generation_sha,
        "oracle_sha256": "",  # bound after the oracle is published
        "parameter_sha256": hashlib.sha256(
            f"parameter:{rank}:{seed}".encode()
        ).hexdigest(),
        "block_layout": {
            "carrier_block": 1,
            "determinant_block": 1,
            "quadrature_block": 1,
        },
        "primitive_metrics": _primitive_metrics(overlap=overlap),
        "metric_equivalence": equivalence,
        "gate_metrics": contract_fixture(
            SCIENTIFIC_NESTED_CONTRACTS[
                "challenge15.exact-evaluation-shard.v1"
            ]["gate_metrics"]
        ),
    }


def _publish(path: Path, schema: str, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    publish_create_only(
        path,
        canonical_json(envelope_for(schema, payload)) + b"\n",
    )
    return path


def _make_valid_inputs(tmp_path: Path, ranks: tuple[int, ...]) -> dict:
    oracle_payload = _oracle_payload()
    oracle_sha = payload_sha256(oracle_payload)
    oracle = _publish(
        tmp_path / "oracle" / f"{oracle_sha}.json",
        "challenge15.production-oracle.v1",
        oracle_payload,
    )
    generation_roots = []
    generation_by_identity = {}
    for seed in range(5):
        root = tmp_path / "training" / f"seed={seed}"
        generation_roots.append(root)
        parent_digest = None
        parent_payload = None
        for rank in ranks:
            extension = _extension_payload(
                seed, rank, parent_digest, parent_payload
            )
            extension_digest = payload_sha256(extension)
            _publish(
                root / "extensions" / f"{extension_digest}.json",
                "challenge15.rank-extension.v1",
                extension,
            )
            payload = _generation_payload(
                seed, rank, parent_digest, extension_digest
            )
            digest = payload_sha256(payload)
            _publish(
                root / "generations" / digest / "manifest.json",
                "challenge15.training-generation.v1",
                payload,
            )
            generation_by_identity[(rank, seed)] = digest
            parent_digest = digest
            parent_payload = payload

    exact_shards = []
    coordinate_shards = []
    for rank in ranks:
        for seed in range(5):
            generation_sha = generation_by_identity[(rank, seed)]
            exact = _exact_payload(seed, rank, generation_sha)
            exact["oracle_sha256"] = oracle_sha
            exact_digest = payload_sha256(exact)
            exact_shards.append(
                _publish(
                    tmp_path / "exact" / f"{exact_digest}.json",
                    "challenge15.exact-evaluation-shard.v1",
                    exact,
                )
            )
            coordinate = _coordinate_payload(seed, rank, generation_sha)
            coordinate_digest = payload_sha256(coordinate)
            coordinate_shards.append(
                _publish(
                    tmp_path / "coordinate" / f"{coordinate_digest}.json",
                    "challenge15.coordinate-evaluation-shard.v1",
                    coordinate,
                )
            )

    identity_payload = build_identity_map(
        stage="reduction",
        expected_ranks=ranks,
        input_sha256_by_identity=generation_by_identity,
        input_path_by_identity={
            identity: f"/inputs/rank={identity[0]}/seed={identity[1]}.json"
            for identity in generation_by_identity
        },
        array_concurrency=1,
        **COMMON,
    )
    identity_map = _publish(
        tmp_path / "identity-map.json",
        "challenge15.identity-map.v1",
        identity_payload,
    )
    return {
        "identity_map": identity_map,
        "oracle": oracle,
        "generation_roots": tuple(generation_roots),
        "exact_shards": tuple(exact_shards),
        "coordinate_shards": tuple(coordinate_shards),
        "prerequisite_terminal_selection": None,
    }


@pytest.fixture
def valid_inputs(tmp_path):
    return _make_valid_inputs(tmp_path, (1, 2, 4))


def _without_rank_seed(inputs, kind: str, rank: int, seed: int):
    changed = dict(inputs)
    key = f"{kind}_shards"
    schema = f"challenge15.{kind}-evaluation-shard.v1"
    changed[key] = tuple(
        path
        for path in changed[key]
        if (
            (payload := validate_envelope(path, schema))["rank"],
            payload["seed"],
        )
        != (rank, seed)
    )
    return changed


def test_missing_expected_identity_is_deterministic_pending(valid_inputs):
    result = reduce_size(
        expected_ranks=(1, 2, 4),
        **_without_rank_seed(valid_inputs, "exact", 4, 3),
    )
    assert result.canonical_payload["production_accepted"] is False
    assert result.canonical_payload["missing_identities"] == [
        {"kind": "exact", "rank": 4, "seed": 3}
    ]


def test_complete_inputs_are_accepted_from_recomputed_primitive_gates(valid_inputs):
    result = reduce_size(expected_ranks=(1, 2, 4), **valid_inputs)
    assert result.canonical_payload["production_accepted"] is True
    assert result.canonical_payload["failed_gates"] == []
    assert result.canonical_payload["seed_gate"] == {
        "passing_seeds": [0, 1, 2, 3, 4],
        "required_count": 4,
        "passed": True,
    }


def test_size_result_recomputes_paired_seed_covariance(valid_inputs):
    payload = dict(
        reduce_size(expected_ranks=(1, 2, 4), **valid_inputs).canonical_payload
    )
    payload["coordinate_uncertainty_by_rank"] = [
        dict(item) for item in payload["coordinate_uncertainty_by_rank"]
    ]
    payload["coordinate_uncertainty_by_rank"][0][
        "optimizer_covariance_e0_e2"
    ] += 1.0

    with pytest.raises(ValueError, match="covariance"):
        validate_size_result_semantics(payload)


def test_reducer_recomputes_exact_five_seed_unbiased_covariance():
    shards = {
        seed: {
            "seed": seed,
            "sector_diagnostics": {
                "L0": {"estimate": float(seed), "standard_error": 0.1},
                "L2": {"estimate": float(2 * seed + 1), "standard_error": 0.2},
            },
            "paired_gap_diagnostics": {
                "uncertainty_status": "pending",
                "within_seed_inputs": [{
                    "seed": seed,
                    "e0": -1000.0,
                    "e2": 1000.0,
                    "variance_mc_e0": 99.0,
                    "variance_mc_e2": 98.0,
                    "monte_carlo_covariance_e0_e2": 97.0,
                    "variance_mc_gap": 3.0,
                }],
            },
        }
        for seed in range(5)
    }

    result = aggregate_coordinate_seed_uncertainty(shards)

    assert result["paired_seed_ids"] == [0, 1, 2, 3, 4]
    assert result["optimizer_variance_e0"] == pytest.approx(2.5)
    assert result["optimizer_variance_e2"] == pytest.approx(10.0)
    assert result["optimizer_covariance_e0_e2"] == pytest.approx(5.0)
    assert result["variance_seed_mean_gap"] == pytest.approx(0.5)
    assert result["within_seed_inputs"][0] == {
        "seed": 0,
        "e0": 0.0,
        "e2": 1.0,
        "variance_mc_e0": pytest.approx(0.01),
        "variance_mc_e2": pytest.approx(0.04),
        "monte_carlo_covariance_e0_e2": 0.0,
        "variance_mc_gap": pytest.approx(0.05),
    }
    assert result["uncertainty_status"] == "accepted"
    with pytest.raises(ValueError, match="exact five"):
        aggregate_coordinate_seed_uncertainty({k: v for k, v in shards.items() if k < 4})


def test_missing_declared_rank_extensions_hard_fail(valid_inputs):
    shutil.rmtree(valid_inputs["generation_roots"][0] / "extensions")

    with pytest.raises(ValueError, match="extension"):
        reduce_size(expected_ranks=(1, 2, 4), **valid_inputs)


@pytest.mark.parametrize("mutation", ["malformed", "duplicate", "unexpected", "stale"])
def test_invalid_input_hard_fails_without_output(
    tmp_path, valid_inputs, mutation
):
    inputs = dict(valid_inputs)
    exact = list(inputs["exact_shards"])
    if mutation == "malformed":
        exact[0].write_text("{")
    elif mutation == "duplicate":
        exact.append(exact[0])
    elif mutation == "unexpected":
        payload = validate_envelope(
            exact[0], "challenge15.exact-evaluation-shard.v1"
        )
        payload["rank"] = 8
        exact.append(
            _publish(
                tmp_path / "unexpected.json",
                "challenge15.exact-evaluation-shard.v1",
                payload,
            )
        )
    else:
        payload = validate_envelope(
            exact[0], "challenge15.exact-evaluation-shard.v1"
        )
        payload["source_manifest_sha256"] = "f" * 64
        exact[0] = _publish(
            tmp_path / "stale.json",
            "challenge15.exact-evaluation-shard.v1",
            payload,
        )
    inputs["exact_shards"] = tuple(exact)
    output_dir = tmp_path / "results"
    receipt_dir = tmp_path / "receipts"
    with pytest.raises(ValueError):
        publish_reduction(
            reduce_size(expected_ranks=(1, 2, 4), **inputs),
            output_dir,
            receipt_dir,
        )
    assert not output_dir.exists()
    assert not receipt_dir.exists()


def test_reduction_paths_are_content_addressed(tmp_path, valid_inputs):
    published = publish_reduction(
        reduce_size(expected_ranks=(1, 2, 4), **valid_inputs),
        tmp_path / "results",
        tmp_path / "receipts",
    )
    assert published.payload_path == (
        tmp_path
        / "results"
        / published.expected_ranks_sha256
        / f"{published.payload_sha256}.json"
    )
    assert published.receipt_path == (
        tmp_path / "receipts" / f"{published.receipt_sha256}.json"
    )


def test_shuffled_inputs_have_identical_canonical_payload_bytes(valid_inputs):
    first = reduce_size(expected_ranks=(1, 2, 4), **valid_inputs)
    shuffled = {
        **valid_inputs,
        "generation_roots": tuple(reversed(valid_inputs["generation_roots"])),
        "exact_shards": tuple(reversed(valid_inputs["exact_shards"])),
        "coordinate_shards": tuple(reversed(valid_inputs["coordinate_shards"])),
    }
    second = reduce_size(expected_ranks=(1, 2, 4), **shuffled)
    assert canonical_json(first.canonical_payload) == canonical_json(
        second.canonical_payload
    )
    assert "hostname" not in first.canonical_payload
    assert first.execution_receipt["canonical_payload_sha256"] == payload_sha256(
        first.canonical_payload
    )


def test_ambiguous_acceptance_threshold_is_pending(valid_inputs):
    exact = list(valid_inputs["exact_shards"])
    payload = validate_envelope(
        exact[-1], "challenge15.exact-evaluation-shard.v1"
    )
    payload["primitive_metrics"]["overlap_by_sector"]["L0"] = _statistic(0.99)
    replacement = exact[-1].with_name(f"{payload_sha256(payload)}.json")
    exact[-1] = _publish(
        replacement,
        "challenge15.exact-evaluation-shard.v1",
        payload,
    )
    result = reduce_size(
        expected_ranks=(1, 2, 4),
        **{**valid_inputs, "exact_shards": tuple(exact)},
    )
    assert result.canonical_payload["production_accepted"] is False
    assert any(
        gate["reason"] == "ambiguous-threshold"
        for gate in result.canonical_payload["failed_gates"]
    )


def test_coordinate_oom_equivalence_pending_forces_identity_pending(valid_inputs):
    coordinate = list(valid_inputs["coordinate_shards"])
    payload = validate_envelope(
        coordinate[-1], "challenge15.coordinate-evaluation-shard.v1"
    )
    payload["execution_validation"]["metric_equivalence"] = {
        "canonical_completed": False,
        "bitwise_equal": False,
        "classification": "pending",
    }
    coordinate[-1] = _publish(
        coordinate[-1].with_name(f"{payload_sha256(payload)}.json"),
        "challenge15.coordinate-evaluation-shard.v1",
        payload,
    )

    result = reduce_size(
        expected_ranks=(1, 2, 4),
        **{**valid_inputs, "coordinate_shards": tuple(coordinate)},
    )

    assert result.canonical_payload["production_accepted"] is False
    assert any(
        gate["reason"] == "metric-equivalence-pending"
        for gate in result.canonical_payload["failed_gates"]
    )


def test_quadrature_gate_is_recomputed_while_seed_uncertainty_stays_pending(valid_inputs):
    exact = list(valid_inputs["exact_shards"])
    exact_payload = validate_envelope(
        exact[-1], "challenge15.exact-evaluation-shard.v1"
    )
    exact_payload["primitive_metrics"]["quadrature_change_by_sector"]["L2"][
        "energy"
    ] = 2e-11
    exact[-1] = _publish(
        exact[-1].with_name(f"{payload_sha256(exact_payload)}.json"),
        "challenge15.exact-evaluation-shard.v1",
        exact_payload,
    )
    result = reduce_size(
        expected_ranks=(1, 2, 4),
        **{
            **valid_inputs,
            "exact_shards": tuple(exact),
            "coordinate_shards": valid_inputs["coordinate_shards"],
        },
    )

    assert result.canonical_payload["production_accepted"] is False
    reasons = {gate["reason"] for gate in result.canonical_payload["failed_gates"]}
    assert "quadrature-L2-energy" in reasons


def test_false_exact_per_state_primitive_cannot_accept(valid_inputs):
    exact = list(valid_inputs["exact_shards"])
    payload = validate_envelope(
        exact[-1], "challenge15.exact-evaluation-shard.v1"
    )
    payload["primitive_metrics"]["per_state_gate_inputs_by_sector"]["L2"][
        "finite"
    ] = False
    exact[-1] = _publish(
        exact[-1].with_name(f"{payload_sha256(payload)}.json"),
        "challenge15.exact-evaluation-shard.v1",
        payload,
    )

    result = reduce_size(
        expected_ranks=(1, 2, 4),
        **{**valid_inputs, "exact_shards": tuple(exact)},
    )

    assert result.canonical_payload["production_accepted"] is False
    assert any(
        gate["reason"] == "per-state-L2-finite"
        for gate in result.canonical_payload["failed_gates"]
    )


def test_metric_equivalence_at_ambiguity_margin_is_pending(valid_inputs):
    exact = list(valid_inputs["exact_shards"])
    payload = validate_envelope(
        exact[-1], "challenge15.exact-evaluation-shard.v1"
    )
    payload["metric_equivalence"]["maximum_difference"] = payload[
        "metric_equivalence"
    ]["absolute_tolerance"]
    exact[-1] = _publish(
        exact[-1].with_name(f"{payload_sha256(payload)}.json"),
        "challenge15.exact-evaluation-shard.v1",
        payload,
    )

    result = reduce_size(
        expected_ranks=(1, 2, 4),
        **{**valid_inputs, "exact_shards": tuple(exact)},
    )

    assert result.canonical_payload["production_accepted"] is False
    assert any(
        gate["reason"] == "metric-equivalence-ambiguous"
        for gate in result.canonical_payload["failed_gates"]
    )


def test_rank_transition_uses_paired_seed_uncertainty(valid_inputs):
    coordinate = list(valid_inputs["coordinate_shards"])
    offsets = (-4e-3, -2e-3, 0.0, 2e-3, 4e-3)
    for index, path in enumerate(coordinate):
        payload = validate_envelope(
            path, "challenge15.coordinate-evaluation-shard.v1"
        )
        if payload["rank"] != 4:
            continue
        offset = offsets[payload["seed"]]
        if offset == 0.0:
            continue
        sector = payload["sector_diagnostics"]["L2"]
        sector["estimate"] += offset
        sector["confidence_interval"] = {
            "low": sector["estimate"] - 2e-6,
            "high": sector["estimate"] + 2e-6,
        }
        paired = payload["paired_gap_diagnostics"]
        paired["estimate"] += offset
        paired["ci_low"] = paired["estimate"] - 2e-6
        paired["ci_high"] = paired["estimate"] + 2e-6
        paired["uncertainty_status"] = "pending"
        paired["within_seed_inputs"][0]["e2"] += offset
        paired["between_seed_inputs"]["e2_seed_estimates"][0] += offset
        replacement = path.with_name(f"{payload_sha256(payload)}.json")
        coordinate[index] = _publish(
            replacement,
            "challenge15.coordinate-evaluation-shard.v1",
            payload,
        )

    result = reduce_size(
        expected_ranks=(1, 2, 4),
        **{**valid_inputs, "coordinate_shards": tuple(coordinate)},
    )

    final_transition = result.canonical_payload["rank_transitions"][-1]
    assert final_transition["paired_gap_standard_error"] == pytest.approx(
        0.001414213562373095
    )
    assert final_transition["passed"] is False


def test_expected_rank_hash_and_dynamic_identity_map_are_ordered():
    assert expected_ranks_sha256((1, 2, 4)) != expected_ranks_sha256((1, 2, 4, 8))
    identities = {
        (rank, seed): hashlib.sha256(f"{rank}:{seed}".encode()).hexdigest()
        for rank in (1, 2, 4, 8)
        for seed in range(5)
    }
    identity_map = build_identity_map(
        stage="exact",
        expected_ranks=(8,),
        input_sha256_by_identity={
            identity: digest for identity, digest in identities.items() if identity[0] == 8
        },
        input_path_by_identity={
            identity: f"/inputs/rank={identity[0]}/seed={identity[1]}.json"
            for identity in identities if identity[0] == 8
        },
        array_concurrency=1,
        **COMMON,
    )
    assert identity_map["task_count"] == 5
    assert [task["array_index"] for task in identity_map["tasks"]] == list(range(5))
    assert identity_map["expected_ranks_sha256"] == expected_ranks_sha256((8,))
    assert slurm_array_spec(identity_map) == "0-4%1"


def test_real_rank_eight_reduction_is_separately_content_addressed(tmp_path):
    shorter_inputs = _make_valid_inputs(tmp_path / "short", (1, 2, 4))
    extended_inputs = _make_valid_inputs(tmp_path / "extended", (1, 2, 4, 8))

    shorter = publish_reduction(
        reduce_size(expected_ranks=(1, 2, 4), **shorter_inputs),
        tmp_path / "results",
        tmp_path / "receipts",
    )
    extended = publish_reduction(
        reduce_size(expected_ranks=(1, 2, 4, 8), **extended_inputs),
        tmp_path / "results",
        tmp_path / "receipts",
    )

    assert shorter.expected_ranks_sha256 != extended.expected_ranks_sha256
    assert shorter.payload_path.is_file()
    assert extended.payload_path.is_file()
    assert shorter.payload_path.parent != extended.payload_path.parent


def test_receipt_bytes_may_change_while_canonical_bytes_do_not(
    monkeypatch, valid_inputs
):
    times = iter(
        (
            "2026-07-29T00:00:00.000000Z",
            "2026-07-29T00:00:01.000000Z",
            "2026-07-29T00:01:00.000000Z",
            "2026-07-29T00:01:02.000000Z",
        )
    )
    monkeypatch.setattr("challenge15.reducer._now", lambda: next(times))

    first = reduce_size(expected_ranks=(1, 2, 4), **valid_inputs)
    second = reduce_size(expected_ranks=(1, 2, 4), **valid_inputs)

    assert canonical_json(first.canonical_payload) == canonical_json(
        second.canonical_payload
    )
    assert canonical_json(first.execution_receipt) != canonical_json(
        second.execution_receipt
    )
