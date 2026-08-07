#!/usr/bin/env python3
"""Audit exact netlists for dead, duplicate, complementary, and constant wires."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from score_circuits import HERE, SPECS, base_operand, parse


def truth_tables(name: str) -> tuple[dict[str, int], int]:
    n, _, _ = SPECS[name]
    circuit = parse(HERE / f"{name}.txt")
    rows = 1 << (2 * n)
    universe = (1 << rows) - 1
    values: dict[str, int] = {}
    for input_index in range(circuit.ninputs):
        table = 0
        for packed in range(rows):
            table |= ((packed >> input_index) & 1) << packed
        values[f"x{input_index + 1}"] = table

    def get(token: str) -> int:
        value = values[base_operand(token)]
        return universe ^ value if token.startswith("~") else value

    for wire, op, a, b in circuit.gates:
        av, bv = get(a), get(b)
        if op == "AND":
            value = av & bv
        elif op == "OR":
            value = av | bv
        elif op == "XOR":
            value = av ^ bv
        elif op == "NAND":
            value = universe ^ (av & bv)
        elif op == "NOR":
            value = universe ^ (av | bv)
        else:
            value = universe ^ (av ^ bv)
        values[wire] = value
    return values, universe


def analyze(name: str) -> None:
    circuit = parse(HERE / f"{name}.txt")
    values, universe = truth_tables(name)
    uses = Counter(
        base_operand(operand)
        for _, _, a, b in circuit.gates
        for operand in (a, b)
    )
    uses.update(base_operand(output) for output in circuit.outputs)
    dead = [wire for wire, _, _, _ in circuit.gates if not uses[wire]]
    constants = [
        wire for wire, _, _, _ in circuit.gates if values[wire] in (0, universe)
    ]

    canonical: dict[int, list[str]] = defaultdict(list)
    for wire, _, _, _ in circuit.gates:
        value = values[wire]
        key = min(value, universe ^ value)
        canonical[key].append(wire)
    polarity_sharing = [group for group in canonical.values() if len(group) > 1]

    depth = {f"x{i}": 0 for i in range(1, circuit.ninputs + 1)}
    for wire, _, a, b in circuit.gates:
        depth[wire] = 1 + max(depth[base_operand(a)], depth[base_operand(b)])
    output_depth = max(depth[base_operand(output)] for output in circuit.outputs)
    gate_types = Counter(op for _, op, _, _ in circuit.gates)
    print(
        f"{name}: gates={len(circuit.gates)}, depth={output_depth}, "
        f"types={dict(sorted(gate_types.items()))}, dead={len(dead)}, "
        f"constants={len(constants)}, duplicate_or_complement_groups={len(polarity_sharing)}"
    )
    if dead:
        print(f"  dead: {dead}")
    if constants:
        print(f"  constants: {constants}")
    if polarity_sharing:
        print(f"  duplicate/complement: {polarity_sharing[:10]}")


def main() -> None:
    for name in SPECS:
        analyze(name)


if __name__ == "__main__":
    main()
