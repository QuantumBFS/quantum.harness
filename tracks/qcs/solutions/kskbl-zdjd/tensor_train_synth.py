#!/usr/bin/env python3
"""Exact tensor-train/decision-diagram synthesis for the 6x6 multiplier.

For a variable ordering, equal suffix tensors are merged exactly.  This is the
canonical deterministic tensor train (a shared complemented-edge ROBDD for all
output bits).  Each local rank-2 selector tensor is compiled into the allowed
AND/XOR gate basis with free edge complementation.
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from score_circuits import HERE


Edge = tuple[int, bool]


@dataclass
class Diagram:
    order: tuple[int, ...]
    nodes: list[tuple[int, Edge, Edge]]
    roots: list[Edge]
    costs: list[int]

    @property
    def gate_cost(self) -> int:
        return sum(self.costs)


def toggle(edge: Edge) -> Edge:
    return edge[0], not edge[1]


def edge_equal(left: Edge, right: Edge) -> bool:
    return left == right


def build_diagram(order: tuple[int, ...]) -> Diagram:
    rows = 1 << 12
    remapped_products = [0] * rows
    for packed in range(rows):
        original = 0
        for position, variable in enumerate(order):
            original |= ((packed >> position) & 1) << variable
        x = original & 63
        y = original >> 6
        remapped_products[packed] = x * y

    nodes: list[tuple[int, Edge, Edge]] = []
    costs: list[int] = []
    unique: dict[tuple[int, Edge, Edge], int] = {}
    memo: dict[tuple[int, bytes], Edge] = {}

    def build(level: int, values: bytes) -> Edge:
        key = (level, values)
        if key in memo:
            return memo[key]
        if not any(values):
            return 0, False
        if all(values):
            return 0, True
        low = build(level + 1, values[0::2])
        high = build(level + 1, values[1::2])
        if edge_equal(low, high):
            memo[key] = low
            return low

        output_complemented = low[1]
        if output_complemented:
            low = toggle(low)
            high = toggle(high)
        node_key = (level, low, high)
        if node_key not in unique:
            node_id = len(nodes) + 1
            unique[node_key] = node_id
            nodes.append(node_key)
            if low == (0, False) or high == (0, False):
                cost = 0 if {low, high} == {(0, False), (0, True)} else 1
            elif low == (0, True) or high == (0, True):
                cost = 1
            elif high == toggle(low):
                cost = 1
            else:
                cost = 3
            costs.append(cost)
        result = unique[node_key], output_complemented
        memo[key] = result
        return result

    roots: list[Edge] = []
    for bit in range(12):
        values = bytes((product >> bit) & 1 for product in remapped_products)
        roots.append(build(0, values))
    return Diagram(order, nodes, roots, costs)


def render(diagram: Diagram) -> str:
    gates: list[tuple[str, str, str, str]] = []
    aliases: dict[int, str] = {}

    def new_gate(op: str, left: str, right: str) -> str:
        wire = f"w{len(gates) + 1}"
        gates.append((wire, op, left, right))
        return wire

    def token(edge: Edge) -> str:
        node, complemented = edge
        if node == 0:
            raise ValueError("constant edge cannot be materialized directly")
        base = aliases[node]
        return f"~{base}" if complemented else base

    for node_id, (level, low, high) in enumerate(diagram.nodes, 1):
        selector = f"x{diagram.order[level] + 1}"
        if low == (0, False) and high == (0, True):
            aliases[node_id] = selector
        elif low == (0, True) and high == (0, False):
            aliases[node_id] = f"~{selector}"
        elif low == (0, False):
            aliases[node_id] = new_gate("AND", selector, token(high))
        elif high == (0, False):
            aliases[node_id] = new_gate("AND", f"~{selector}", token(low))
        elif low == (0, True):
            aliases[node_id] = new_gate("OR", f"~{selector}", token(high))
        elif high == (0, True):
            aliases[node_id] = new_gate("OR", selector, token(low))
        elif high == toggle(low):
            aliases[node_id] = new_gate("XOR", selector, token(low))
        else:
            difference = new_gate("XOR", token(low), token(high))
            selected = new_gate("AND", selector, difference)
            aliases[node_id] = new_gate("XOR", token(low), selected)

    outputs = [token(root) for root in diagram.roots]
    lines = ["INPUTS 12"]
    lines.extend(f"{w} = {op} {a} {b}" for w, op, a, b in gates)
    lines.append("OUTPUTS " + " ".join(outputs))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--random-orders", type=int, default=500)
    parser.add_argument("--hill-restarts", type=int, default=20)
    parser.add_argument("--seed", type=int, default=71)
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "abc-work" / "mystery-C-tensor-train.txt",
    )
    args = parser.parse_args()
    rng = random.Random(args.seed)

    candidates: set[tuple[int, ...]] = {
        tuple(range(12)),
        tuple(reversed(range(12))),
        tuple(value for pair in zip(range(6), range(6, 12)) for value in pair),
        tuple(
            value
            for pair in zip(reversed(range(6)), reversed(range(6, 12)))
            for value in pair
        ),
        tuple(range(6)) + tuple(reversed(range(6, 12))),
        tuple(range(6, 12)) + tuple(range(6)),
    }
    for _ in range(args.random_orders):
        order = list(range(12))
        rng.shuffle(order)
        candidates.add(tuple(order))

    cache: dict[tuple[int, ...], Diagram] = {}

    def evaluate(order: tuple[int, ...]) -> Diagram:
        if order not in cache:
            cache[order] = build_diagram(order)
        return cache[order]

    best = min((evaluate(order) for order in candidates), key=lambda item: item.gate_cost)
    for _ in range(args.hill_restarts):
        current = evaluate(rng.choice(tuple(candidates)))
        improved = True
        while improved:
            improved = False
            neighbors = []
            for left in range(11):
                order = list(current.order)
                order[left], order[left + 1] = order[left + 1], order[left]
                neighbors.append(evaluate(tuple(order)))
            next_diagram = min(neighbors, key=lambda item: item.gate_cost)
            if next_diagram.gate_cost < current.gate_cost:
                current = next_diagram
                improved = True
        if current.gate_cost < best.gate_cost:
            best = current

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(best), encoding="ascii")
    levels = Counter(level for level, _, _ in best.nodes)
    print(f"evaluated_orders={len(cache)}")
    print(f"best_order={','.join(f'x{index + 1}' for index in best.order)}")
    print(f"tensor_states={len(best.nodes)}, compiled_gates={best.gate_cost}")
    print(
        "states_by_level="
        + ",".join(f"{level}:{levels[level]}" for level in sorted(levels))
    )
    print(args.output)


if __name__ == "__main__":
    main()
