#!/usr/bin/env python3
"""Enumerate small maximal fanout-free cones for exact local synthesis."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from score_circuits import HERE, SPECS, base_operand, parse


def maximal_fanout_free_cone(circuit, root: str) -> set[str]:
    producers = {wire: (op, a, b) for wire, op, a, b in circuit.gates}
    consumers: dict[str, set[str]] = defaultdict(set)
    for wire, _, a, b in circuit.gates:
        consumers[base_operand(a)].add(wire)
        consumers[base_operand(b)].add(wire)
    for index, output in enumerate(circuit.outputs):
        consumers[base_operand(output)].add(f"$output{index}")

    cone = {root}
    changed = True
    while changed:
        changed = False
        for wire in tuple(cone):
            _, a, b = producers[wire]
            for operand in (a, b):
                candidate = base_operand(operand)
                if candidate not in producers or candidate in cone:
                    continue
                if consumers[candidate] <= cone:
                    cone.add(candidate)
                    changed = True
    return cone


def boundary_of(circuit, cone: set[str]) -> list[str]:
    boundary: set[str] = set()
    for wire, _, a, b in circuit.gates:
        if wire not in cone:
            continue
        for operand in (a, b):
            base = base_operand(operand)
            if base not in cone:
                boundary.add(base)
    return sorted(boundary, key=lambda token: (not token.startswith("x"), token))


def cone_truth(circuit, root: str, cone: set[str], boundary: list[str]) -> int:
    gates = {wire: (op, a, b) for wire, op, a, b in circuit.gates}
    truth = 0
    for packed in range(1 << len(boundary)):
        values = {
            wire: bool((packed >> index) & 1)
            for index, wire in enumerate(boundary)
        }

        def get(token: str) -> bool:
            value = values[base_operand(token)]
            return not value if token.startswith("~") else value

        for wire, _, _, _ in circuit.gates:
            if wire not in cone:
                continue
            op, a, b = gates[wire]
            av, bv = get(a), get(b)
            if op == "AND":
                value = av and bv
            elif op == "OR":
                value = av or bv
            elif op == "XOR":
                value = av != bv
            elif op == "NAND":
                value = not (av and bv)
            elif op == "NOR":
                value = not (av or bv)
            else:
                value = av == bv
            values[wire] = value
        truth |= int(values[root]) << packed
    return truth


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", choices=sorted(SPECS))
    parser.add_argument("--max-boundary", type=int, default=6)
    parser.add_argument("--min-gates", type=int, default=3)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    circuit = parse(args.source or (HERE / f"{args.instance}.txt"))
    output_wires = {base_operand(output) for output in circuit.outputs}
    candidates = []
    for root, _, _, _ in circuit.gates:
        cone = maximal_fanout_free_cone(circuit, root)
        boundary = boundary_of(circuit, cone)
        if len(cone) < args.min_gates or len(boundary) > args.max_boundary:
            continue
        truth = cone_truth(circuit, root, cone, boundary)
        hex_digits = max(1, 1 << max(0, len(boundary) - 2))
        candidates.append(
            (
                len(cone),
                len(boundary),
                root,
                root in output_wires,
                boundary,
                f"{truth:0{hex_digits}X}",
            )
        )

    for size, support, root, is_output, boundary, truth in sorted(
        candidates, reverse=True
    ):
        print(
            f"{root}: gates={size}, boundary={support}, output={is_output}, "
            f"leaves={','.join(boundary)}, truth={truth}"
        )


if __name__ == "__main__":
    main()
