#!/usr/bin/env python3
"""Search exact low-rank functional decompositions of large circuit regions.

For a boundary tensor F(X, Y), rows that induce identical functions of Y are
merged into an interface label H(X).  The original tensor is then represented
exactly as G(H(X), Y).  This is an exact Boolean analogue of a low-bond-rank
tensor factorization.
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import math
from dataclasses import dataclass
from pathlib import Path

from score_circuits import HERE, parse
from tensor_graph_windows import (
    RegionTensor,
    graph_data,
    reachability,
    sample_regions,
)


Edge = tuple[int, bool]


@dataclass(frozen=True)
class Decomposition:
    region: RegionTensor
    left: tuple[int, ...]
    right: tuple[int, ...]
    classes: int
    interface_bits: int
    front_truths: tuple[int, ...]
    back_truths: tuple[int, ...]
    front_cost: int = -1
    back_cost: int = -1

    @property
    def total_cost(self) -> int:
        if self.front_cost < 0 or self.back_cost < 0:
            return math.inf
        return self.front_cost + self.back_cost

    @property
    def saving(self) -> int:
        return self.region.gates - self.total_cost


def toggle(edge: Edge) -> Edge:
    return edge[0], not edge[1]


def remap_truth(truth: int, ninputs: int, order: tuple[int, ...]) -> bytes:
    values = bytearray(1 << ninputs)
    for packed in range(1 << ninputs):
        original = 0
        for position, variable in enumerate(order):
            original |= ((packed >> position) & 1) << variable
        values[packed] = (truth >> original) & 1
    return bytes(values)


def bdd_gate_cost(
    truths: tuple[int, ...],
    ninputs: int,
    orders: tuple[tuple[int, ...], ...] | None = None,
) -> int:
    """Return a legal-gate upper bound from a shared complemented ROBDD."""
    if not truths:
        return 0
    if orders is None:
        natural = tuple(range(ninputs))
        orders = (natural, tuple(reversed(natural)))

    best = math.inf
    for order in orders:
        nodes: list[tuple[int, Edge, Edge]] = []
        costs: list[int] = []
        unique: dict[tuple[int, Edge, Edge], int] = {}
        memo: dict[tuple[int, bytes], Edge] = {}

        def build(level: int, values: bytes) -> Edge:
            key = level, values
            if key in memo:
                return memo[key]
            if not any(values):
                return 0, False
            if all(values):
                return 0, True
            low = build(level + 1, values[0::2])
            high = build(level + 1, values[1::2])
            if low == high:
                memo[key] = low
                return low
            complemented = low[1]
            if complemented:
                low, high = toggle(low), toggle(high)
            node_key = level, low, high
            if node_key not in unique:
                unique[node_key] = len(nodes) + 1
                nodes.append(node_key)
                if low == (0, False) or high == (0, False):
                    cost = (
                        0
                        if {low, high} == {(0, False), (0, True)}
                        else 1
                    )
                elif low == (0, True) or high == (0, True):
                    cost = 1
                elif high == toggle(low):
                    cost = 1
                else:
                    cost = 3
                costs.append(cost)
            result = unique[node_key], complemented
            memo[key] = result
            return result

        for truth in truths:
            build(0, remap_truth(truth, ninputs, order))
        best = min(best, sum(costs))
    return int(best)


def make_decomposition(
    region: RegionTensor,
    left: tuple[int, ...],
    max_interface: int,
) -> Decomposition | None:
    ninputs = len(region.inputs)
    right = tuple(index for index in range(ninputs) if index not in left)
    outputs = tuple(int(value, 16) for value in region.truths)
    noutputs = len(outputs)

    signatures: list[int] = []
    for left_value in range(1 << len(left)):
        signature = 0
        for right_value in range(1 << len(right)):
            packed = 0
            for bit, variable in enumerate(left):
                packed |= ((left_value >> bit) & 1) << variable
            for bit, variable in enumerate(right):
                packed |= ((right_value >> bit) & 1) << variable
            out_value = sum(
                ((truth >> packed) & 1) << output
                for output, truth in enumerate(outputs)
            )
            signature |= out_value << (noutputs * right_value)
        signatures.append(signature)

    distinct = sorted(set(signatures))
    classes = len(distinct)
    interface_bits = max(1, (classes - 1).bit_length())
    if classes <= 1 or interface_bits > max_interface:
        return None
    if len(right) + interface_bits > 6 or len(left) > 6:
        return None

    class_index = {signature: index for index, signature in enumerate(distinct)}
    labels = [class_index[signature] for signature in signatures]
    front_truths = []
    for bit in range(interface_bits):
        truth = sum(
            ((label >> bit) & 1) << packed
            for packed, label in enumerate(labels)
        )
        front_truths.append(truth)

    back_truths = [0] * noutputs
    for label, signature in enumerate(distinct):
        for right_value in range(1 << len(right)):
            out_value = (
                signature >> (noutputs * right_value)
            ) & ((1 << noutputs) - 1)
            packed = label | (right_value << interface_bits)
            for output in range(noutputs):
                back_truths[output] |= ((out_value >> output) & 1) << packed

    # Verify the factorization over every original boundary assignment.
    for packed in range(1 << ninputs):
        left_value = sum(
            ((packed >> variable) & 1) << bit
            for bit, variable in enumerate(left)
        )
        right_value = sum(
            ((packed >> variable) & 1) << bit
            for bit, variable in enumerate(right)
        )
        label = sum(
            ((truth >> left_value) & 1) << bit
            for bit, truth in enumerate(front_truths)
        )
        combined = label | (right_value << interface_bits)
        for output, original in enumerate(outputs):
            assert ((back_truths[output] >> combined) & 1) == (
                (original >> packed) & 1
            )

    front_tuple = tuple(front_truths)
    back_tuple = tuple(back_truths)
    return Decomposition(
        region=region,
        left=left,
        right=right,
        classes=classes,
        interface_bits=interface_bits,
        front_truths=front_tuple,
        back_truths=back_tuple,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--samples", type=int, default=10_000)
    parser.add_argument("--min-gates", type=int, default=12)
    parser.add_argument("--max-gates", type=int, default=22)
    parser.add_argument("--max-inputs", type=int, default=10)
    parser.add_argument("--max-outputs", type=int, default=6)
    parser.add_argument("--max-interface", type=int, default=3)
    parser.add_argument("--seed", type=int, default=71)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--cost-candidates", type=int, default=300)
    args = parser.parse_args()

    source = args.source or (HERE / f"{args.instance}.txt")
    circuit = parse(source)
    producer, consumers, neighbors = graph_data(circuit)
    ancestors, descendants = reachability(circuit, producer, consumers)
    regions = sample_regions(
        circuit,
        neighbors,
        producer,
        consumers,
        args.samples,
        args.min_gates,
        args.max_gates,
        args.max_inputs,
        args.max_outputs,
        args.seed,
        ancestors,
        descendants,
    )

    unique_regions: dict[
        tuple[int, tuple[str, ...]], RegionTensor
    ] = {}
    for region in regions:
        key = len(region.inputs), region.truths
        previous = unique_regions.get(key)
        if previous is None or region.gates > previous.gates:
            unique_regions[key] = region

    decompositions: list[Decomposition] = []
    for region in unique_regions.values():
        ninputs = len(region.inputs)
        for left_size in range(2, min(6, ninputs - 1) + 1):
            for left in itertools.combinations(range(ninputs), left_size):
                decomposition = make_decomposition(
                    region, left, args.max_interface
                )
                if decomposition is not None:
                    decompositions.append(decomposition)

    # Deduplicate identical factor pairs and retain the largest replaceable
    # region for each pair before running the more expensive BDD costing.
    unique_decompositions: dict[
        tuple[int, tuple[int, ...], int, tuple[int, ...]], Decomposition
    ] = {}
    for item in decompositions:
        key = (
            len(item.left),
            item.front_truths,
            len(item.right) + item.interface_bits,
            item.back_truths,
        )
        previous = unique_decompositions.get(key)
        if previous is None or item.region.gates > previous.region.gates:
            unique_decompositions[key] = item
    ranked = sorted(
        unique_decompositions.values(),
        key=lambda item: (
            -item.region.gates,
            item.interface_bits,
            item.classes,
            max(len(item.left), len(item.right) + item.interface_bits),
        ),
    )[: args.cost_candidates]

    cost_cache: dict[tuple[int, tuple[int, ...]], int] = {}

    def factor_cost(ninputs: int, truths: tuple[int, ...]) -> int:
        key = ninputs, truths
        if key not in cost_cache:
            cost_cache[key] = bdd_gate_cost(truths, ninputs)
        return cost_cache[key]

    decompositions = [
        dataclasses.replace(
            item,
            front_cost=factor_cost(len(item.left), item.front_truths),
            back_cost=factor_cost(
                len(item.right) + item.interface_bits, item.back_truths
            ),
        )
        for item in ranked
    ]
    decompositions.sort(
        key=lambda item: (
            -item.saving,
            -item.region.gates,
            item.interface_bits,
            item.total_cost,
        )
    )
    print(
        f"sampled_regions={len(regions)}, "
        f"unique_regions={len(unique_regions)}, "
        f"low_rank_factor_pairs={len(unique_decompositions)}, "
        f"costed={len(decompositions)}"
    )
    for index, item in enumerate(decompositions[: args.limit], 1):
        left_names = ",".join(item.region.inputs[value] for value in item.left)
        right_names = ",".join(
            item.region.inputs[value] for value in item.right
        )
        region_indices = ",".join(
            str(value + 1) for value in sorted(item.region.indices)
        )
        print(
            f"{index:03d}: gates={item.region.gates}, "
            f"bdd={item.total_cost}({item.front_cost}+{item.back_cost}), "
            f"saving={item.saving}, classes={item.classes}, "
            f"bond={item.interface_bits}, "
            f"indices={region_indices}, left={left_names}, right={right_names}, "
            f"outputs={','.join(item.region.outputs)}"
        )


if __name__ == "__main__":
    main()
