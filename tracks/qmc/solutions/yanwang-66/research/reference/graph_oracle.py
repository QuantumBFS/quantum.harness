"""Exhaustive one-round oracle for the circuit-derived matching graph."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymatching


PYMATCHING_WEIGHT_ABS_TOL = 1e-6


@dataclass(frozen=True)
class Edge:
    endpoints: tuple[int, ...]
    logical: int
    weight: float
    name: str


def load_instance(path: Path) -> dict:
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["distance"] == 3 and record["basis"] == "X":
            return record
    raise ValueError("missing d=3 memory-X geometry")


def build_edges(instance: dict) -> tuple[list[Edge], int]:
    relevant_checks = [check for check in instance["checks"] if check["pauli"] == "X"]
    check_index = {check["check_id"]: index for index, check in enumerate(relevant_checks)}
    checks_by_site: dict[int, list[int]] = {}
    for check in relevant_checks:
        detector = check_index[check["check_id"]]
        for site_id in check["support"]:
            checks_by_site.setdefault(site_id, []).append(detector)

    data_sites = [site for site in instance["sites"] if site["role"] == "data"]
    logical_support = set(instance["logical_support"])
    n_checks = len(relevant_checks)
    edges: list[Edge] = []
    for site in data_sites:
        site_id = site["site_id"]
        endpoints = tuple(sorted(checks_by_site.get(site_id, [])))
        if len(endpoints) not in {1, 2}:
            raise AssertionError(f"data site {site_id} has relevant check degree {len(endpoints)}")
        edges.append(
            Edge(
                endpoints=endpoints,
                logical=int(site_id in logical_support),
                weight=1.0 + site_id * 1e-3,
                name=f"data-{site_id}",
            )
        )

    for detector in range(n_checks):
        edges.append(
            Edge(
                endpoints=(detector, detector + n_checks),
                logical=0,
                weight=1.5 + detector * 1e-3,
                name=f"measurement-{detector}",
            )
        )
    return edges, 2 * n_checks


def edge_subset_signature(edges: list[Edge], subset: int) -> tuple[int, int, float]:
    syndrome = 0
    logical = 0
    weight = 0.0
    for index, edge in enumerate(edges):
        if not (subset >> index) & 1:
            continue
        for detector in edge.endpoints:
            syndrome ^= 1 << detector
        logical ^= edge.logical
        weight += edge.weight
    return syndrome, logical, weight


def exhaustive_minima(edges: list[Edge]) -> dict[int, dict[int, float]]:
    minima: dict[int, dict[int, float]] = {}
    for subset in range(1 << len(edges)):
        syndrome, logical, weight = edge_subset_signature(edges, subset)
        by_logical = minima.setdefault(syndrome, {})
        by_logical[logical] = min(weight, by_logical.get(logical, math.inf))
    return minima


def xor_probability(left: float, right: float) -> float:
    return left * (1.0 - right) + right * (1.0 - left)


def merge_parallel_edges(edges: list[Edge]) -> list[Edge]:
    grouped: dict[tuple[tuple[int, ...], int], list[Edge]] = {}
    endpoint_logicals: dict[tuple[int, ...], set[int]] = {}
    for edge in edges:
        grouped.setdefault((edge.endpoints, edge.logical), []).append(edge)
        endpoint_logicals.setdefault(edge.endpoints, set()).add(edge.logical)
    ambiguous = {
        endpoints: logicals
        for endpoints, logicals in endpoint_logicals.items()
        if len(logicals) > 1
    }
    if ambiguous:
        raise AssertionError(
            f"parallel oracle edges have different logical parities: {ambiguous}"
        )

    merged = []
    for (endpoints, logical), mechanisms in grouped.items():
        probability = 0.0
        for mechanism in mechanisms:
            mechanism_probability = 1.0 / (1.0 + math.exp(mechanism.weight))
            probability = xor_probability(probability, mechanism_probability)
        merged.append(
            Edge(
                endpoints=endpoints,
                logical=logical,
                weight=math.log((1.0 - probability) / probability),
                name="+".join(mechanism.name for mechanism in mechanisms),
            )
        )
    return merged


def make_matching(edges: list[Edge]) -> pymatching.Matching:
    matching = pymatching.Matching()
    for edge in edges:
        fault_ids = {0} if edge.logical else set()
        if len(edge.endpoints) == 1:
            matching.add_boundary_edge(edge.endpoints[0], fault_ids=fault_ids, weight=edge.weight)
        else:
            matching.add_edge(*edge.endpoints, fault_ids=fault_ids, weight=edge.weight)
    return matching


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    args = parser.parse_args()

    instance = load_instance(args.instances)
    physical_edges, n_detectors = build_edges(instance)
    edges = merge_parallel_edges(physical_edges)
    minima = exhaustive_minima(edges)
    matching = make_matching(edges)
    checked = 0
    ties = 0

    for syndrome_bits in itertools.product((0, 1), repeat=n_detectors):
        syndrome_mask = sum(bit << index for index, bit in enumerate(syndrome_bits))
        candidates = minima.get(syndrome_mask)
        if not candidates:
            raise AssertionError(f"oracle found no correction for syndrome {syndrome_mask}")
        prediction, weight = matching.decode(np.asarray(syndrome_bits, dtype=np.uint8), return_weight=True)
        best_weight = min(candidates.values())
        if not math.isclose(
            float(weight),
            best_weight,
            rel_tol=0,
            abs_tol=PYMATCHING_WEIGHT_ABS_TOL,
        ):
            raise AssertionError(
                f"syndrome={syndrome_mask}: PyMatching weight {weight} != oracle {best_weight}"
            )
        best_logicals = {
            logical for logical, candidate_weight in candidates.items()
            if math.isclose(candidate_weight, best_weight, rel_tol=0, abs_tol=1e-9)
        }
        if len(best_logicals) == 1:
            observed_logical = int(np.asarray(prediction).reshape(-1)[0])
            if observed_logical not in best_logicals:
                raise AssertionError(
                    f"syndrome={syndrome_mask}: prediction {observed_logical} not in {best_logicals}"
                )
        else:
            ties += 1
        checked += 1

    print(
        json.dumps(
            {
                "checked_syndromes": checked,
                "detectors": n_detectors,
                "edges": len(edges),
                "physical_edges": len(physical_edges),
                "degenerate_ties": ties,
                "passed": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
