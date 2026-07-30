from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

from flax import serialization
import jax
import numpy as np
import pytest

from challenge15.exact_eval import (
    EXACT_THRESHOLD_PRECISION,
    _scientific_gates,
    classify_exact_layout,
    evaluate_exact_shard,
)
from challenge15.fermions import (
    DeterminantBasis,
    iter_ordered_determinant_blocks,
)
from challenge15.generations import VerifiedGeneration
from challenge15.model import ModelConfig, ProjectedPfaffianNQS
from challenge15.oracle import VerifiedOracle, solve_target_sectors
from challenge15.production_policy import policy_sha256
from challenge15.production_schema import payload_sha256, validate_envelope
from challenge15.spec import SphereSpec


SHA = "a" * 64
RUNTIMES = {
    "training": {"qdeshell": "1" * 64},
    "coordinate": {"qdeshell": "2" * 64},
    "oracle": {"lasg02": "3" * 64},
    "exact": {"lasg02": "4" * 64},
    "reducer": {"lasg02": "5" * 64},
}


@pytest.fixture(scope="module")
def exact_inputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("exact-input")
    spec = SphereSpec(4)
    model = ProjectedPfaffianNQS(
        ModelConfig(rank=2, hidden_width=8, depth=1, token_width=4)
    )
    spinors = np.asarray(
        [
            [1.0, 0.2j],
            [0.7, 0.3 - 0.1j],
            [0.4 + 0.2j, 0.8],
            [0.1 - 0.3j, 0.9],
        ],
        dtype=np.complex128,
    )
    variables = model.init(jax.random.key(615), spec, spinors, target_l=0)
    parameter_bytes = serialization.to_bytes(variables)
    parameter_sha = hashlib.sha256(parameter_bytes).hexdigest()
    seed_root = root / "seed=0"
    (seed_root / "blobs").mkdir(parents=True)
    (seed_root / "blobs" / parameter_sha).write_bytes(parameter_bytes)
    generation_path = (
        seed_root / "generations" / ("b" * 64) / "manifest.json"
    )
    generation_path.parent.mkdir(parents=True)
    common = {
        "policy_sha256": policy_sha256(),
        "source_manifest_sha256": "c" * 64,
        "runtime_attestations": RUNTIMES,
        "base_configuration_sha256": "d" * 64,
        "particles": 4,
    }
    generation_payload = {
        **common,
        "seed": 0,
        "rank": 2,
        "parameter_sha256": parameter_sha,
    }
    generation = VerifiedGeneration(
        path=generation_path,
        payload_sha256=payload_sha256(generation_payload),
        payload=generation_payload,
    )
    oracle_payload = {**common, "artifact": "independent-occupation-oracle"}
    oracle = VerifiedOracle(
        path=root / "oracle.json",
        payload_sha256=payload_sha256(oracle_payload),
        payload=oracle_payload,
        result=solve_target_sectors(spec),
    )
    return oracle, generation


@pytest.fixture(scope="module")
def exact_metrics(exact_inputs):
    oracle, generation = exact_inputs
    root = Path(generation.path).parents[2]
    parameters = serialization.msgpack_restore(
        (root / "blobs" / generation.payload["parameter_sha256"]).read_bytes()
    )
    from challenge15.oracle import evaluate_exact_nqs

    return evaluate_exact_nqs(
        oracle.result.spec,
        parameters,
        oracle.result,
        determinant_block=7,
        carrier_block=2,
        quadrature_block=13,
    )


def _phase_aligned_difference(first, second):
    reference = np.asarray(first, dtype=np.complex128)
    candidate = np.asarray(second, dtype=np.complex128)
    overlap = np.vdot(reference, candidate)
    if overlap:
        candidate = candidate * np.exp(-1j * np.angle(overlap))
    return float(np.max(np.abs(reference - candidate), initial=0.0))


def test_ordered_determinant_blocks_are_static_padded_and_masked():
    basis = DeterminantBasis.with_two_m(SphereSpec(4), 0)
    blocks = tuple(iter_ordered_determinant_blocks(basis, 7))

    assert blocks
    assert all(block.states.shape == (7,) for block in blocks)
    assert all(block.indices.shape == (7,) for block in blocks)
    assert all(block.valid.shape == (7,) for block in blocks)
    assert all(block.valid.dtype == np.bool_ for block in blocks)
    recovered = [
        int(state)
        for block in blocks
        for state, valid in zip(block.states, block.valid, strict=True)
        if valid
    ]
    assert recovered == list(basis.states)
    assert not blocks[-1].valid[-1]


def test_all_block_layouts_preserve_every_exact_metric(tmp_path, exact_inputs):
    oracle, generation = exact_inputs
    results = []
    for determinant_block in (1, 7, 256):
        for carrier_block in (1, 2):
            for quadrature_block in (1, 13, 64):
                destination = (
                    tmp_path
                    / f"d{determinant_block}-c{carrier_block}-q{quadrature_block}"
                )
                destination.mkdir()
                results.append(
                    evaluate_exact_shard(
                        oracle,
                        generation,
                        determinant_block,
                        carrier_block,
                        quadrature_block,
                        destination,
                    )
                )

    reference = results[0]
    for result in results:
        for target_l in (0, 2):
            assert _phase_aligned_difference(
                reference.metrics.normalized_sector_coefficients(target_l),
                result.metrics.normalized_sector_coefficients(target_l),
            ) <= 2e-12
            np.testing.assert_allclose(
                result.metrics.projected_carrier_relative_singular_values(target_l),
                reference.metrics.projected_carrier_relative_singular_values(target_l),
                rtol=2e-11,
                atol=2e-13,
            )
            assert result.metrics.projected_span_rank(target_l) == (
                reference.metrics.projected_span_rank(target_l)
            )
        for field in (
            "energy_l0",
            "energy_l2",
            "h_variance_l0",
            "h_variance_l2",
            "overlap_l0",
            "overlap_l2",
            "l2_residual_l0",
            "l2_residual_l2",
            "quadrature_coefficient_relative_change_l0",
            "quadrature_coefficient_relative_change_l2",
            "quadrature_energy_relative_change_l0",
            "quadrature_energy_relative_change_l2",
        ):
            assert getattr(result.metrics, field) == pytest.approx(
                getattr(reference.metrics, field), rel=2e-11, abs=2e-13
            )
        equivalence = result.canonical_payload["metric_equivalence"]
        assert result.classification == "passed"
        assert equivalence["classification"] == "passed"
        assert equivalence["ambiguous"] is False
        assert equivalence["straddled_gates"] == []
        assert equivalence["passed"] is True


def test_exact_shard_and_receipt_are_separate_strict_envelopes(
    tmp_path, exact_inputs
):
    oracle, generation = exact_inputs
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    first = evaluate_exact_shard(oracle, generation, 7, 2, 13, first_dir)
    second = evaluate_exact_shard(oracle, generation, 7, 2, 13, second_dir)

    assert first.payload_sha256 == second.payload_sha256
    assert first.canonical_payload == second.canonical_payload
    assert first.receipt_payload["identity"] == {
        "stage": "exact",
        "seed": 0,
        "rank": 2,
    }
    assert first.receipt_payload["shard_sha256"] == first.payload_sha256
    assert first.receipt_payload != second.receipt_payload
    assert first.canonical_payload["metric_equivalence"] == {
        "reference_sha256": first.canonical_payload["metric_equivalence"][
            "reference_sha256"
        ],
        "absolute_tolerance": 2e-11,
        "maximum_difference": first.canonical_payload["metric_equivalence"][
            "maximum_difference"
        ],
        "classification": "passed",
        "ambiguous": False,
        "straddled_gates": [],
        "passed": True,
    }
    assert "rank_converged" not in first.canonical_payload["gate_metrics"]
    assert "production_accepted" not in first.canonical_payload["gate_metrics"]
    validate_envelope(first.payload_path, "challenge15.exact-evaluation-shard.v1")
    validate_envelope(first.receipt_path, "challenge15.evaluation-receipt.v1")
    with pytest.raises(FileExistsError):
        evaluate_exact_shard(oracle, generation, 7, 2, 13, first_dir)


def test_layout_threshold_straddle_is_pending(exact_inputs):
    oracle, generation = exact_inputs
    root = Path(generation.path).parents[2]
    parameters = serialization.msgpack_restore(
        (root / "blobs" / generation.payload["parameter_sha256"]).read_bytes()
    )
    from challenge15.oracle import evaluate_exact_nqs

    reference = evaluate_exact_nqs(
        oracle.result.spec,
        parameters,
        oracle.result,
        determinant_block=7,
        carrier_block=2,
        quadrature_block=13,
    )
    low = replace(reference, overlap_l0=0.99 - 5e-14)
    high = replace(reference, overlap_l0=0.99 + 5e-14)

    comparison = classify_exact_layout(low, high, absolute_tolerance=1e-12)

    assert comparison.classification == "pending"
    assert comparison.ambiguous is True
    assert comparison.passed is False
    assert comparison.straddled_gates == ("overlap",)


def test_scientific_gates_use_per_sector_energy_and_reviewed_thresholds(
    exact_inputs, exact_metrics
):
    oracle, _ = exact_inputs
    exact_gap = oracle.result.gap
    energy_limit = min(1e-4, 0.01 * abs(exact_gap))
    singular_l0 = np.array(
        exact_metrics.carrier_gram_relative_singular_values_l0, copy=True
    )
    singular_l2 = np.array(
        exact_metrics.carrier_gram_relative_singular_values_l2, copy=True
    )
    singular_l0[-1] = 0.0
    singular_l2[-1] = 0.0
    metrics = replace(
        exact_metrics,
        energy_l0=oracle.result.energy_l0 + 0.75 * energy_limit,
        energy_l2=oracle.result.energy_l2 + 0.75 * energy_limit,
        l2_residual_l0=5e-11,
        l2_residual_l2=5e-11,
        carrier_gram_singular_values_l0=singular_l0,
        carrier_gram_singular_values_l2=singular_l2,
        carrier_gram_relative_singular_values_l0=singular_l0,
        carrier_gram_relative_singular_values_l2=singular_l2,
        projected_span_rank_l0=int(np.count_nonzero(singular_l0 > 1e-10)),
        projected_span_rank_l2=int(np.count_nonzero(singular_l2 > 1e-10)),
        projected_span_complete_l0=False,
        projected_span_complete_l2=False,
    )

    gates = _scientific_gates(metrics, oracle)

    assert gates["energy"] is True
    assert gates["symmetry"] is True
    assert "rank_converged" not in gates
    assert "production_accepted" not in gates


@pytest.mark.parametrize(
    ("gate", "make_pair"),
    [
        (
            "overlap",
            lambda metrics, oracle, tolerance: (
                replace(metrics, overlap_l0=0.99 + 0.25 * tolerance),
                replace(metrics, overlap_l0=0.99 + 0.40 * tolerance),
            ),
        ),
        (
            "symmetry",
            lambda metrics, oracle, tolerance: (
                replace(metrics, l2_residual_l0=1e-10 - 0.25 * tolerance),
                replace(metrics, l2_residual_l0=1e-10 - 0.40 * tolerance),
            ),
        ),
        (
            "symmetry",
            lambda metrics, oracle, tolerance: (
                replace(
                    metrics,
                    quadrature_coefficient_relative_change_l0=(
                        1e-11 - 0.25 * tolerance
                    ),
                ),
                replace(
                    metrics,
                    quadrature_coefficient_relative_change_l0=(
                        1e-11 - 0.40 * tolerance
                    ),
                ),
            ),
        ),
        (
            "energy",
            lambda metrics, oracle, tolerance: (
                replace(
                    metrics,
                    energy_l0=oracle.result.energy_l0
                    + min(1e-4, 0.01 * abs(oracle.result.gap))
                    - 0.25 * tolerance,
                    energy_l2=oracle.result.energy_l2,
                ),
                replace(
                    metrics,
                    energy_l0=oracle.result.energy_l0
                    + min(1e-4, 0.01 * abs(oracle.result.gap))
                    - 0.40 * tolerance,
                    energy_l2=oracle.result.energy_l2,
                ),
            ),
        ),
        (
            "gap",
            lambda metrics, oracle, tolerance: (
                replace(
                    metrics,
                    energy_l0=oracle.result.energy_l0,
                    energy_l2=oracle.result.energy_l2
                    + 0.01 * abs(oracle.result.gap)
                    - 0.25 * tolerance,
                ),
                replace(
                    metrics,
                    energy_l0=oracle.result.energy_l0,
                    energy_l2=oracle.result.energy_l2
                    + 0.01 * abs(oracle.result.gap)
                    - 0.40 * tolerance,
                ),
            ),
        ),
    ],
)
def test_same_side_threshold_precision_margin_is_pending(
    exact_inputs, exact_metrics, gate, make_pair
):
    oracle, _ = exact_inputs
    tolerance = 1e-12
    reference, candidate = make_pair(
        exact_metrics, oracle, EXACT_THRESHOLD_PRECISION
    )

    comparison = classify_exact_layout(
        reference,
        candidate,
        absolute_tolerance=tolerance,
        oracle=oracle,
    )

    assert comparison.classification == "pending"
    assert gate in comparison.straddled_gates


def test_same_side_singular_rank_margin_is_pending(exact_metrics):
    tolerance = 1e-12

    def near_rank(metrics, offset):
        singular = np.ones_like(
            metrics.carrier_gram_relative_singular_values_l0
        )
        singular[-1] = 1e-10 + offset * EXACT_THRESHOLD_PRECISION
        absolute = singular.copy()
        rank = int(np.count_nonzero(singular > 1e-10))
        return replace(
            metrics,
            carrier_gram_singular_values_l0=absolute,
            carrier_gram_relative_singular_values_l0=singular,
            projected_span_rank_l0=rank,
            projected_span_complete_l0=(
                rank == metrics.projected_span_dimension_l0
            ),
        )

    comparison = classify_exact_layout(
        near_rank(exact_metrics, 0.25),
        near_rank(exact_metrics, 0.40),
        absolute_tolerance=tolerance,
    )

    assert comparison.classification == "pending"
    assert "singular_rank" in comparison.straddled_gates


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_exact_metrics_hard_fail(exact_inputs, value):
    oracle, generation = exact_inputs
    root = Path(generation.path).parents[2]
    parameters = serialization.msgpack_restore(
        (root / "blobs" / generation.payload["parameter_sha256"]).read_bytes()
    )
    from challenge15.oracle import evaluate_exact_nqs

    metrics = evaluate_exact_nqs(
        oracle.result.spec,
        parameters,
        oracle.result,
        determinant_block=7,
        carrier_block=2,
        quadrature_block=13,
    )
    malformed = replace(metrics, energy_l0=value)

    with pytest.raises(ValueError, match="nonfinite"):
        classify_exact_layout(metrics, malformed, absolute_tolerance=1e-12)


def test_malformed_exact_metrics_hard_fail(exact_inputs):
    oracle, generation = exact_inputs
    root = Path(generation.path).parents[2]
    parameters = serialization.msgpack_restore(
        (root / "blobs" / generation.payload["parameter_sha256"]).read_bytes()
    )
    from challenge15.oracle import evaluate_exact_nqs

    metrics = evaluate_exact_nqs(
        oracle.result.spec,
        parameters,
        oracle.result,
        determinant_block=7,
        carrier_block=2,
        quadrature_block=13,
    )
    malformed_values = (
        replace(metrics, norm_l0=0.0),
        replace(metrics, h_variance_l0=-1.0),
        replace(metrics, overlap_l0=1.01),
        replace(metrics, projected_span_rank_l0=-1),
        replace(metrics, projected_span_complete_l0=not metrics.projected_span_complete_l0),
        replace(metrics, quadrature_orders_l0=((0, 1), (1, 2))),
        replace(
            metrics,
            _normalized_sector_coefficients_l0=(
                metrics.normalized_sector_coefficients(0) * 2.0
            ),
        ),
    )

    for malformed in malformed_values:
        with pytest.raises(ValueError, match="malformed"):
            classify_exact_layout(metrics, malformed, absolute_tolerance=1e-12)
