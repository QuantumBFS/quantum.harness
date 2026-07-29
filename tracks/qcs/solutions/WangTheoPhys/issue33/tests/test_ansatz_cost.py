import pytest

from vqetape.ansatz import (
    AnsatzOperator,
    AnsatzStructure,
    fixed_rzz_rx_structure,
)
from vqetape.ansatz_cost import (
    AnsatzCostWeights,
    ansatz_cache_key,
    candidate_cost_delta,
    contraction_aware_score,
    cut_entangler_counts,
    spatial_boundary_dimension,
)
from vqetape.ansatz_signals import AnsatzSignal
from vqetape.spec import TFIMVQESpec


def test_spatial_boundary_tracks_maximum_cut_count():
    structure = AnsatzStructure(
        4,
        (
            AnsatzOperator("rzz", 0),
            AnsatzOperator("rzz", 0),
            AnsatzOperator("rzz", 2),
            AnsatzOperator("rx", 1),
        ),
    )

    assert cut_entangler_counts(structure) == (2, 0, 1)
    assert spatial_boundary_dimension(structure) == 3 * 4**2


def test_cost_penalizes_new_maximum_but_not_equalized_cut():
    base = fixed_rzz_rx_structure(4, 1)
    first = candidate_cost_delta(
        base,
        AnsatzOperator("rzz", 0),
    )
    raised = base.append(AnsatzOperator("rzz", 0))
    equalizing = candidate_cost_delta(
        raised,
        AnsatzOperator("rzz", 1),
    )

    assert first.boundary_after == 4 * first.boundary_before
    assert first.delta_log_boundary > 0
    assert equalizing.boundary_after == (
        equalizing.boundary_before
    )
    assert equalizing.delta_log_boundary == 0
    assert equalizing.delta_memory_relative == 0


def test_contraction_score_reduces_costly_signal():
    signal = AnsatzSignal(
        AnsatzOperator("rzz", 0),
        gradient=0.5,
        metric=0.25,
        normalized_signal=1.0,
    )
    cost = candidate_cost_delta(
        fixed_rzz_rx_structure(4, 1),
        signal.operator,
    )

    score = contraction_aware_score(
        signal,
        cost,
        AnsatzCostWeights(),
    )

    assert 0 < score < signal.normalized_signal


def test_cache_key_changes_on_structure_workload_or_device():
    spec = TFIMVQESpec(nqubits=4, depth=1)
    structure = fixed_rzz_rx_structure(4, 1)
    baseline = ansatz_cache_key(
        structure,
        spec,
        jax_version="test",
        devices=("cpu:0:test",),
    )

    assert baseline != ansatz_cache_key(
        structure.append(AnsatzOperator("rx", 0)),
        spec,
        jax_version="test",
        devices=("cpu:0:test",),
    )
    assert baseline != ansatz_cache_key(
        structure,
        TFIMVQESpec(
            nqubits=4,
            depth=1,
            field=0.7,
        ),
        jax_version="test",
        devices=("cpu:0:test",),
    )
    assert baseline != ansatz_cache_key(
        structure,
        spec,
        jax_version="test",
        devices=("gpu:0:test",),
    )


def test_cost_weights_reject_negative_values():
    with pytest.raises(ValueError, match="nonnegative"):
        AnsatzCostWeights(boundary=-1)
