"""Focused SCNet-only guards for the first experiment implementation."""

from __future__ import annotations

import json
import math
import os
from dataclasses import fields, replace
from itertools import combinations
from pathlib import Path

import numpy as np

from reload_qec.artifacts import INPUT_KEYS, LABEL_KEYS
from reload_qec.config import PolicyConfig, ReloadConfig, SimulationRequest
from reload_qec.geometry import Geometry
from reload_qec.graph import GraphDecoder, MatchingGraph
from reload_qec.matrix import generate_matrix
from reload_qec.rng import EventType, counter_u64
from reload_qec.simulate import SimulationBatch, Simulator


def geometry_path() -> Path:
    value = os.environ.get("Q66_INSTANCE_FILE")
    if not value:
        raise RuntimeError("Q66_INSTANCE_FILE is required")
    return Path(value)


def request(policy: PolicyConfig, *, p_loss: float, p: float = 1e-3) -> SimulationRequest:
    return SimulationRequest(
        run_id="core-test",
        instance_file=geometry_path(),
        distance=3,
        rounds=3,
        basis="X",
        shots=64,
        shot_start=10_000,
        shard_size=64,
        master_seed=0x6600AA55,
        p=p,
        p_m=p,
        p_loss=p_loss,
        reload=ReloadConfig(
            delay_rounds=0,
            reset_error_probability=0.0,
            failure_probability=0.0,
        ),
        policy=policy,
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
    )


def simulate(value: SimulationRequest) -> SimulationBatch:
    geometry = Geometry.load(
        value.instance_file,
        distance=value.distance,
        rounds=value.rounds,
        basis=value.basis,
    )
    shot_ids = np.arange(
        value.shot_start, value.shot_start + value.shots, dtype=np.uint64
    )
    return Simulator(value, geometry).simulate(shot_ids)


def assert_batches_equal(left: SimulationBatch, right: SimulationBatch) -> None:
    for field in fields(SimulationBatch):
        left_value = getattr(left, field.name)
        right_value = getattr(right, field.name)
        if isinstance(left_value, np.ndarray):
            np.testing.assert_array_equal(left_value, right_value, err_msg=field.name)
        else:
            assert left_value == right_value, field.name


def test_counter_rng_is_addressed_not_consumed() -> None:
    address = (19, 23, 2, 7, EventType.LOSS, 0)
    assert counter_u64(*address) == counter_u64(*address)
    assert counter_u64(*address) != counter_u64(19, 24, 2, 7, EventType.LOSS, 0)
    assert counter_u64(*address) != counter_u64(
        19, 23, 2, 7, EventType.MEASUREMENT_FLIP, 0
    )


def test_zero_noise_is_failure_free_for_all_policy_families() -> None:
    policies = (
        PolicyConfig("none"),
        PolicyConfig("immediate"),
        PolicyConfig("periodic", interval=3),
        PolicyConfig("threshold", fraction=0.05),
    )
    for policy in policies:
        batch = simulate(replace(request(policy, p_loss=0.0, p=0.0), p_m=0.0))
        assert not np.any(batch.logical_failure)
        assert not np.any(batch.missing_mask)
        assert not np.any(batch.reload_mask)


def test_loss_free_outputs_are_policy_invariant() -> None:
    none = simulate(request(PolicyConfig("none"), p_loss=0.0))
    immediate = simulate(request(PolicyConfig("immediate"), p_loss=0.0))
    assert_batches_equal(none, immediate)


def test_immediate_equals_periodic_one_under_ideal_reload() -> None:
    immediate = simulate(request(PolicyConfig("immediate"), p_loss=0.08))
    periodic = simulate(
        request(PolicyConfig("periodic", interval=1), p_loss=0.08)
    )
    assert_batches_equal(immediate, periodic)


def test_none_is_invariant_to_unused_reload_costs() -> None:
    ideal = request(PolicyConfig("none"), p_loss=0.08)
    costly = replace(
        ideal,
        reload=ReloadConfig(
            delay_rounds=2,
            reset_error_probability=0.01,
            failure_probability=0.01,
        ),
    )
    assert_batches_equal(simulate(ideal), simulate(costly))


def test_none_missing_occupancy_is_pathwise_monotone() -> None:
    batch = simulate(request(PolicyConfig("none"), p_loss=0.08))
    differences = np.diff(batch.missing_mask.astype(np.int8), axis=1)
    assert np.all(differences >= 0)


def test_decoder_input_and_label_files_have_disjoint_payloads() -> None:
    assert set(INPUT_KEYS).isdisjoint(set(LABEL_KEYS) - {"shot_id"})
    forbidden = {
        "logical_observable",
        "decoder_prediction",
        "logical_failure",
        "catastrophic_loss",
        "reload_reset_fault_mask",
    }
    assert forbidden.isdisjoint(INPUT_KEYS)


def test_frozen_discovery_matrix_is_complete_and_paired() -> None:
    families_path = geometry_path().with_name("benchmark_families.json")
    families = json.loads(families_path.read_text(encoding="utf-8"))
    matrix = generate_matrix(
        families,
        instance_file=geometry_path(),
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
        shots=20_000,
        shard_size=4_096,
    )
    assert matrix["group_count"] == 280
    assert matrix["cell_count"] == 2_240
    run_ids = set()
    for group in matrix["groups"]:
        assert len(group["requests"]) == 8
        seeds = {request_value["master_seed"] for request_value in group["requests"]}
        ranges = {
            (request_value["shot_start"], request_value["shots"])
            for request_value in group["requests"]
        }
        assert len(seeds) == 1
        assert ranges == {(0, 20_000)}
        for request_value in group["requests"]:
            parsed = SimulationRequest.from_dict(request_value)
            assert parsed.run_id not in run_ids
            run_ids.add(parsed.run_id)
    assert len(run_ids) == 2_240


def _missing_edge_syndromes(
    edges: tuple, missing_site_ids: frozenset[int], n_checks: int
) -> set[tuple[int, ...]]:
    selected = [edge for edge in edges if edge.site_id in missing_site_ids]
    syndromes: set[tuple[int, ...]] = set()
    for count in range(len(selected) + 1):
        for subset in combinations(selected, count):
            syndrome = [0] * n_checks
            for edge in subset:
                for endpoint in edge.endpoints:
                    syndrome[endpoint] ^= 1
            syndromes.add(tuple(syndrome))
    return syndromes


def _super_stabilizer_invariants(
    edges: tuple, missing_site_ids: frozenset[int], n_checks: int
) -> tuple[tuple[int, ...], ...]:
    boundary = n_checks
    parent = list(range(n_checks + 1))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in edges:
        if edge.site_id not in missing_site_ids:
            continue
        right = edge.endpoints[1] if len(edge.endpoints) == 2 else boundary
        union(edge.endpoints[0], right)

    boundary_root = find(boundary)
    components: dict[int, list[int]] = {}
    for check_index in range(n_checks):
        components.setdefault(find(check_index), []).append(check_index)
    return tuple(
        tuple(component)
        for root, component in sorted(components.items())
        if root != boundary_root
    )


def _has_erased_logical_cycle(
    edges: tuple, missing_site_ids: frozenset[int], n_checks: int
) -> bool:
    selected = [edge for edge in edges if edge.site_id in missing_site_ids]
    for count in range(1, len(selected) + 1):
        for subset in combinations(selected, count):
            syndrome = [0] * n_checks
            logical = 0
            for edge in subset:
                for endpoint in edge.endpoints:
                    syndrome[endpoint] ^= 1
                logical ^= edge.logical
            if logical and not any(syndrome):
                return True
    return False


def test_erasure_contraction_matches_super_stabilizer_quotient() -> None:
    value = request(PolicyConfig("none"), p_loss=0.0)
    geometry = Geometry.load(
        value.instance_file,
        distance=value.distance,
        rounds=value.rounds,
        basis=value.basis,
    )
    edges = geometry.data_edges()
    graph = MatchingGraph(
        geometry,
        p=value.p,
        p_m=value.p_m,
        p_reset=value.reload.reset_error_probability,
    )
    n_checks = len(geometry.relevant_checks)
    n_sites = geometry.n_sites

    for mask_bits in range(1 << len(edges)):
        missing = frozenset(
            edge.site_id
            for edge_index, edge in enumerate(edges)
            if mask_bits & (1 << edge_index)
        )
        syndromes = _missing_edge_syndromes(edges, missing, n_checks)
        invariants = _super_stabilizer_invariants(edges, missing, n_checks)
        for component in invariants:
            product_support: set[int] = set()
            for check_index in component:
                product_support.symmetric_difference_update(
                    geometry.relevant_checks[check_index].support
                )
            assert product_support
            assert product_support.isdisjoint(missing)
        expected_orbit_size = 1 << (n_checks - len(invariants))
        assert len(syndromes) == expected_orbit_size
        for syndrome in syndromes:
            assert all(
                sum(syndrome[index] for index in component) % 2 == 0
                for component in invariants
            )

        erasure_mask = np.zeros((value.rounds, n_sites), dtype=np.uint8)
        for site_id in missing:
            erasure_mask[0, site_id] = 1
        assert graph.is_catastrophic(erasure_mask) == _has_erased_logical_cycle(
            edges, missing, n_checks
        )


def test_all_frozen_geometries_build_and_decode_zero_syndrome() -> None:
    for distance in (3, 5):
        for rounds in (distance, 2 * distance):
            for basis in ("X", "Z"):
                geometry = Geometry.load(
                    geometry_path(),
                    distance=distance,
                    rounds=rounds,
                    basis=basis,
                )
                graph = MatchingGraph(
                    geometry,
                    p=1e-3,
                    p_m=1e-3,
                    p_reset=0.0,
                )
                shots = 2
                detection = np.zeros(
                    (shots, rounds + 1, len(geometry.relevant_checks)),
                    dtype=np.uint8,
                )
                erasure = np.zeros(
                    (shots, rounds, geometry.n_sites), dtype=np.uint8
                )
                reloads = np.zeros(
                    (shots, rounds + 1, geometry.n_sites), dtype=np.uint8
                )
                decoded = GraphDecoder(graph).decode(detection, erasure, reloads)
                assert decoded.prediction.shape == (shots, 1)
                assert not np.any(decoded.prediction)
                assert not np.any(decoded.catastrophic_loss)
                assert decoded.distinct_graphs == 1


def test_parallel_boundary_weights_use_independent_xor_probability() -> None:
    value = request(PolicyConfig("none"), p_loss=0.0)
    geometry = Geometry.load(
        value.instance_file,
        distance=value.distance,
        rounds=value.rounds,
        basis=value.basis,
    )
    graph = MatchingGraph(
        geometry,
        p=value.p,
        p_m=value.p_m,
        p_reset=value.reload.reset_error_probability,
    )
    grouped: dict[tuple[tuple[int, ...], int], list] = {}
    for edge in graph.edges:
        if len(edge.endpoints) == 1:
            grouped.setdefault((edge.endpoints, edge.logical), []).append(edge)
    parallel = {
        key: mechanisms for key, mechanisms in grouped.items() if len(mechanisms) > 1
    }
    assert parallel

    erasure = np.zeros((value.rounds, geometry.n_sites), dtype=np.uint8)
    reloads = np.zeros((value.rounds + 1, geometry.n_sites), dtype=np.uint8)
    observed = {
        (left, frozenset(attributes["fault_ids"])): float(attributes["weight"])
        for left, right, attributes in graph.build(erasure, reloads).edges()
        if right is None
    }
    for (endpoints, logical), mechanisms in parallel.items():
        probability = 0.0
        for mechanism in mechanisms:
            mechanism_probability = 1.0 / (1.0 + math.exp(mechanism.base_weight))
            probability = (
                probability * (1.0 - mechanism_probability)
                + mechanism_probability * (1.0 - probability)
            )
        expected_weight = math.log((1.0 - probability) / probability)
        fault_ids = frozenset({0} if logical else set())
        assert math.isclose(
            observed[(endpoints[0], fault_ids)],
            expected_weight,
            rel_tol=1e-12,
            abs_tol=0.0,
        )
