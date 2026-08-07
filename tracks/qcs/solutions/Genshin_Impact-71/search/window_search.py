#!/usr/bin/env python3
"""Independent structural and exact-window search for issue 71 mystery-D.

The only external input consumed by this program is the plain circuit netlist.
All equivalence checks are exhaustive over the 2**10 primary-input assignments.
Negation is treated as free, exactly as in the challenge cost model.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


OPS = {"AND", "OR", "XOR", "NAND", "NOR", "XNOR"}


@dataclass(frozen=True)
class Token:
    name: str
    inv: bool = False

    @classmethod
    def parse(cls, text: str) -> "Token":
        return cls(text[1:], True) if text.startswith("~") else cls(text, False)

    def text(self) -> str:
        return ("~" if self.inv else "") + self.name


@dataclass(frozen=True)
class Gate:
    out: str
    op: str
    left: Token
    right: Token


@dataclass
class Circuit:
    n_inputs: int
    gates: list[Gate]
    outputs: list[Token]

    @property
    def names(self) -> list[str]:
        return [f"x{i}" for i in range(1, self.n_inputs + 1)] + [
            gate.out for gate in self.gates
        ]


def parse_circuit(path: Path) -> Circuit:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines or not lines[0].startswith("INPUTS "):
        raise ValueError("missing INPUTS header")
    n_inputs = int(lines[0].split()[1])
    gates: list[Gate] = []
    outputs: list[Token] | None = None
    defined = {f"x{i}" for i in range(1, n_inputs + 1)}
    for lineno, line in enumerate(lines[1:], start=2):
        if line.startswith("OUTPUTS "):
            if outputs is not None:
                raise ValueError(f"duplicate OUTPUTS at line {lineno}")
            outputs = [Token.parse(item) for item in line.split()[1:]]
            continue
        if outputs is not None:
            raise ValueError(f"gate after OUTPUTS at line {lineno}")
        fields = line.split()
        if len(fields) != 5 or fields[1] != "=" or fields[2] not in OPS:
            raise ValueError(f"bad gate syntax at line {lineno}: {line!r}")
        out, _, op, left_s, right_s = fields
        left, right = Token.parse(left_s), Token.parse(right_s)
        if out in defined:
            raise ValueError(f"redefinition at line {lineno}: {out}")
        if left.name not in defined or right.name not in defined:
            raise ValueError(f"forward/unknown reference at line {lineno}")
        gates.append(Gate(out, op, left, right))
        defined.add(out)
    if outputs is None:
        raise ValueError("missing OUTPUTS footer")
    for token in outputs:
        if token.name not in defined:
            raise ValueError(f"unknown output {token.text()}")
    return Circuit(n_inputs, gates, outputs)


def input_truth_tables(n_inputs: int) -> tuple[int, dict[str, int]]:
    rows = 1 << n_inputs
    mask = (1 << rows) - 1
    tables: dict[str, int] = {}
    for bit in range(n_inputs):
        value = 0
        for row in range(rows):
            if (row >> bit) & 1:
                value |= 1 << row
        tables[f"x{bit + 1}"] = value
    return mask, tables


def apply_gate(op: str, a: int, b: int, mask: int) -> int:
    if op == "AND":
        return a & b
    if op == "OR":
        return a | b
    if op == "XOR":
        return a ^ b
    if op == "NAND":
        return mask ^ (a & b)
    if op == "NOR":
        return mask ^ (a | b)
    if op == "XNOR":
        return mask ^ (a ^ b)
    raise AssertionError(op)


def evaluate(circuit: Circuit) -> tuple[int, dict[str, int], tuple[int, ...]]:
    mask, values = input_truth_tables(circuit.n_inputs)
    for gate in circuit.gates:
        a = values[gate.left.name] ^ (mask if gate.left.inv else 0)
        b = values[gate.right.name] ^ (mask if gate.right.inv else 0)
        values[gate.out] = apply_gate(gate.op, a, b, mask)
    outputs = tuple(
        values[token.name] ^ (mask if token.inv else 0)
        for token in circuit.outputs
    )
    return mask, values, outputs


def canonical(value: int, mask: int) -> tuple[int, bool]:
    """Return phase-canonical truth table and whether value was complemented."""
    inv = mask ^ value
    if inv < value:
        return inv, True
    return value, False


def structural_maps(circuit: Circuit):
    gate_by_out = {gate.out: gate for gate in circuit.gates}
    fanout: dict[str, set[str]] = defaultdict(set)
    for gate in circuit.gates:
        fanout[gate.left.name].add(gate.out)
        fanout[gate.right.name].add(gate.out)
    for index, output in enumerate(circuit.outputs):
        fanout[output.name].add(f"@o{index}")
    return gate_by_out, fanout


def removable_closure(
    circuit: Circuit, roots: Iterable[str]
) -> tuple[set[str], set[str]]:
    """Gates deleted by replacing all roots; returns (removed, descendants).

    A predecessor becomes removable exactly when every one of its fanouts is
    already removable. Output pseudo-fanouts prevent accidental output deletion.
    Descendants cannot be used as divisors because that would create a cycle.
    """
    gate_by_out, fanout = structural_maps(circuit)
    removed = set(roots)
    queue = deque(removed)
    while queue:
        name = queue.popleft()
        gate = gate_by_out.get(name)
        if gate is None:
            continue
        for pred in {gate.left.name, gate.right.name}:
            if pred not in gate_by_out or pred in removed:
                continue
            if fanout[pred] <= removed:
                removed.add(pred)
                queue.append(pred)

    children: dict[str, set[str]] = defaultdict(set)
    for gate in circuit.gates:
        children[gate.left.name].add(gate.out)
        children[gate.right.name].add(gate.out)
    descendants = set(roots)
    queue = deque(roots)
    while queue:
        name = queue.popleft()
        for child in children[name]:
            if child not in descendants:
                descendants.add(child)
                queue.append(child)
    return removed, descendants


def support_sets(circuit: Circuit) -> dict[str, frozenset[str]]:
    supports = {
        f"x{i}": frozenset({f"x{i}"})
        for i in range(1, circuit.n_inputs + 1)
    }
    for gate in circuit.gates:
        supports[gate.out] = supports[gate.left.name] | supports[gate.right.name]
    return supports


def cone(circuit: Circuit, root: str) -> set[str]:
    gate_by_out, _ = structural_maps(circuit)
    seen: set[str] = set()
    todo = [root]
    while todo:
        name = todo.pop()
        gate = gate_by_out.get(name)
        if gate is None or name in seen:
            continue
        seen.add(name)
        todo.extend((gate.left.name, gate.right.name))
    return seen


def analyse(circuit: Circuit, values: dict[str, int], mask: int) -> dict:
    gate_by_out, fanout = structural_maps(circuit)
    supports = support_sets(circuit)
    output_names = [token.name for token in circuit.outputs]
    mffcs = {}
    for gate in circuit.gates:
        removed, descendants = removable_closure(circuit, [gate.out])
        mffcs[gate.out] = len(removed)

    output_cones = {name: cone(circuit, name) for name in output_names}
    overlaps = []
    for i, left in enumerate(output_names):
        for right in output_names[i + 1 :]:
            common = output_cones[left] & output_cones[right]
            if common:
                overlaps.append(
                    {
                        "left": left,
                        "right": right,
                        "common_gates": len(common),
                        "union_gates": len(output_cones[left] | output_cones[right]),
                    }
                )

    # Candidate pairs whose simultaneous replacement exposes more logic than
    # either independent MFFC. These are the useful multi-output windows.
    synergy = []
    gates = [gate.out for gate in circuit.gates]
    for i, left in enumerate(gates):
        left_removed, _ = removable_closure(circuit, [left])
        for right in gates[i + 1 :]:
            if right in cone(circuit, left) or left in cone(circuit, right):
                continue
            right_removed, _ = removable_closure(circuit, [right])
            both, descendants = removable_closure(circuit, [left, right])
            bonus = len(both) - len(left_removed | right_removed)
            if len(both) >= 3 and (bonus > 0 or len(left_removed) + len(right_removed) >= 4):
                synergy.append(
                    {
                        "left": left,
                        "right": right,
                        "removed": len(both),
                        "independent_union": len(left_removed | right_removed),
                        "synergy": bonus,
                        "left_mffc": len(left_removed),
                        "right_mffc": len(right_removed),
                    }
                )
    synergy.sort(
        key=lambda item: (
            item["synergy"],
            item["removed"],
            item["left_mffc"] + item["right_mffc"],
        ),
        reverse=True,
    )

    phase_classes: dict[int, list[str]] = defaultdict(list)
    for name, value in values.items():
        phase_classes[canonical(value, mask)[0]].append(name)
    duplicates = [names for names in phase_classes.values() if len(names) > 1]

    return {
        "n_inputs": circuit.n_inputs,
        "n_gates": len(circuit.gates),
        "n_outputs": len(circuit.outputs),
        "outputs": [token.text() for token in circuit.outputs],
        "gate_type_counts": dict(Counter(gate.op for gate in circuit.gates)),
        "fanout_histogram": dict(
            sorted(Counter(len(fanout[gate.out]) for gate in circuit.gates).items())
        ),
        "support_histogram": dict(
            sorted(Counter(len(supports[gate.out]) for gate in circuit.gates).items())
        ),
        "largest_mffcs": sorted(
            ({"root": name, "size": size} for name, size in mffcs.items()),
            key=lambda item: item["size"],
            reverse=True,
        )[:30],
        "output_cone_sizes": {
            name: len(output_cones[name]) for name in output_names
        },
        "output_cone_overlaps": sorted(
            overlaps, key=lambda item: item["common_gates"], reverse=True
        ),
        "multi_root_candidates": synergy[:100],
        "phase_duplicate_classes": duplicates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("netlist", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    circuit = parse_circuit(args.netlist)
    mask, values, outputs = evaluate(circuit)
    report = analyse(circuit, values, mask)
    digest = hashlib.sha256()
    for table in outputs:
        digest.update(table.to_bytes((mask.bit_length() + 7) // 8, "little"))
    report["semantic_sha256"] = digest.hexdigest()
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
