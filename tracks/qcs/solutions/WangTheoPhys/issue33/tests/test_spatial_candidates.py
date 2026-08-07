import pytest

from vqetape.spatial_candidates import (
    enumerate_spatial_candidates,
    enumerate_symmetry_candidates,
    rank_spatial_candidates_by_ad_cost,
)
from vqetape.spatial_plan import plan_spatial_transfer
from vqetape.spec import CompileRequest, TFIMVQESpec


def test_spatial_candidates_cover_path_and_adjoint_axes():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=8, depth=1),
        memory_budget_bytes=2 * 1024**3,
        expected_vqe_steps=100,
        warm_repeats=1,
    )
    candidates = enumerate_spatial_candidates(request)

    assert {item.path_strategy for item in candidates} == {
        "greedy",
        "random-greedy",
        "auto-hq",
    }
    assert {item.adjoint for item in candidates} == {
        "default",
        "explicit",
        "remat",
        "segmented",
    }
    assert {item.block_width for item in candidates} == {
        1,
        2,
        3,
        4,
    }
    assert {
        item.segment_length
        for item in candidates
        if item.adjoint == "segmented"
    } == {2}
    assert {
        item.block_width
        for item in candidates
        if item.adjoint == "segmented"
    } == {1}
    assert len(candidates) == 78
    assert len(candidates) == len(set(candidates))
    for strategy in {"greedy", "random-greedy", "auto-hq"}:
        for block_width in {1, 2, 3, 4}:
            matching = [
                item
                for item in candidates
                if item.path_strategy == strategy
                and item.block_width == block_width
            ]
            paths = {item.column_paths for item in matching}
            assert len(paths) == 1
            assert next(iter(paths)) is not None
            costs = set()
            for item in matching:
                planned = plan_spatial_transfer(
                    request.spec,
                    item.path_strategy,
                    explicit_paths=item.column_paths,
                    block_width=item.block_width,
                )
                assert planned.bulk is not None
                costs.add(
                    (
                        planned.first.flops,
                        planned.bulk.flops,
                        (
                            planned.tail.flops
                            if planned.tail is not None
                            else 0
                        ),
                        planned.last.flops,
                    )
                )
                if item.adjoint != "segmented":
                    full_blocks = (
                        request.spec.nqubits - 2
                    ) // item.block_width
                    assert item.unroll in {
                        min(value, full_blocks)
                        for value in (1, 2, 4)
                    }
            assert len(costs) == 1


def test_spatial_candidate_ad_ranking_is_deterministic():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=8, depth=1),
        memory_budget_bytes=2 * 1024**3,
        expected_vqe_steps=100,
        warm_repeats=1,
    )
    candidates = tuple(
        item
        for item in enumerate_spatial_candidates(
            request,
            strategies=("greedy",),
        )
        if item.block_width in (1, 2)
        and item.adjoint == "default"
    )

    first = rank_spatial_candidates_by_ad_cost(
        request,
        candidates,
    )
    second = rank_spatial_candidates_by_ad_cost(
        request,
        candidates,
    )

    assert first == second
    assert {item.config for item in first} == set(candidates)
    assert all(
        item.ad_cost.static_score > 0
        for item in first
    )
    scores = tuple(
        item.ad_cost.static_score for item in first
    )
    assert scores == tuple(sorted(scores))


def test_two_qubit_candidates_omit_bulk_adjoint_schedules():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=2, depth=1),
        memory_budget_bytes=1024**3,
        expected_vqe_steps=10,
    )
    candidates = enumerate_spatial_candidates(request)

    assert len(candidates) == 6
    assert {item.adjoint for item in candidates} == {
        "default",
        "explicit",
    }
    assert {item.unroll for item in candidates} == {1}
    assert all(
        item.column_paths is not None
        and len(item.column_paths) == 2
        for item in candidates
    )


def test_symmetry_candidates_are_fixed_path_triples():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=8, depth=1),
        memory_budget_bytes=2 * 1024**3,
        expected_vqe_steps=100,
        warm_repeats=1,
    )
    candidates = enumerate_symmetry_candidates(
        request,
        strategies=("greedy",),
    )

    assert len(candidates) == 21
    assert {item.symmetry for item in candidates} == {
        "none",
        "z2-reference",
        "z2-native",
    }
    for block_width in (1, 2, 3, 4):
        matching = [
            item
            for item in candidates
            if item.block_width == block_width
        ]
        by_unroll = {
            item.unroll for item in matching
        }
        for unroll in by_unroll:
            triple = [
                item
                for item in matching
                if item.unroll == unroll
            ]
            assert len(triple) == 3
            assert len(
                {item.column_paths for item in triple}
            ) == 1


def test_symmetry_candidates_reject_zero_initial_state():
    request = CompileRequest(
        spec=TFIMVQESpec(
            nqubits=5,
            depth=1,
            initial_state="zero",
        ),
        memory_budget_bytes=1024**3,
        expected_vqe_steps=10,
    )
    with pytest.raises(ValueError, match="plus"):
        enumerate_symmetry_candidates(request)
