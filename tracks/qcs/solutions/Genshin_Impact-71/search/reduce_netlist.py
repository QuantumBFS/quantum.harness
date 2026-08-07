#!/usr/bin/env python3
"""Strict, self-contained truth-table optimizer for the Occam netlist format.

The input is treated as untrusted data.  Only a tiny line-oriented grammar is
accepted; no input text is evaluated, imported, interpolated, or executed.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


OPS = ("AND", "OR", "XOR", "NAND", "NOR", "XNOR")
OPS_SET = frozenset(OPS)
INPUT_RE = re.compile(r"INPUTS ([1-9][0-9]*)\Z")
GATE_RE = re.compile(
    r"w([1-9][0-9]*) = (AND|OR|XOR|NAND|NOR|XNOR) "
    r"(~?)([xw])([1-9][0-9]*) (~?)([xw])([1-9][0-9]*)\Z"
)
OUTPUT_RE = re.compile(
    r"OUTPUTS( ~?[xw][1-9][0-9]*)+\Z"
)
TOKEN_RE = re.compile(r"(~?)([xw])([1-9][0-9]*)\Z")


@dataclasses.dataclass(frozen=True, slots=True)
class Lit:
    kind: str
    index: int
    inv: bool = False

    def toggled(self) -> "Lit":
        return Lit(self.kind, self.index, not self.inv)

    def text(self) -> str:
        return ("~" if self.inv else "") + self.kind + str(self.index)


@dataclasses.dataclass(frozen=True, slots=True)
class Gate:
    op: str
    a: Lit
    b: Lit


@dataclasses.dataclass(frozen=True, slots=True)
class Circuit:
    ninputs: int
    gates: tuple[Gate, ...]
    outputs: tuple[Lit, ...]


def parse_lit_token(token: str) -> Lit:
    match = TOKEN_RE.fullmatch(token)
    if match is None:
        raise ValueError(f"invalid literal token: {token!r}")
    tilde, kind, index_text = match.groups()
    return Lit(kind, int(index_text), bool(tilde))


def validate_lit(lit: Lit, ninputs: int, max_wire: int, context: str) -> None:
    if lit.kind == "x":
        if not 1 <= lit.index <= ninputs:
            raise ValueError(f"{context}: input index out of range: {lit.text()}")
    elif lit.kind == "w":
        if not 1 <= lit.index <= max_wire:
            raise ValueError(
                f"{context}: wire must already exist (max w{max_wire}): {lit.text()}"
            )
    else:
        raise ValueError(f"{context}: unknown literal kind: {lit.kind!r}")


def parse_circuit(path: Path) -> Circuit:
    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError("input exceeds strict 2 MB size limit")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("netlist must be ASCII") from exc
    # Normalize only the platform newline representation.  Empty lines and
    # surrounding whitespace are deliberately not accepted.
    lines = text.splitlines()
    if not lines:
        raise ValueError("empty netlist")
    if any(len(line) > 4096 for line in lines):
        raise ValueError("line exceeds strict 4096-byte limit")
    first = INPUT_RE.fullmatch(lines[0])
    if first is None:
        raise ValueError("line 1 must be exactly: INPUTS <positive integer>")
    ninputs = int(first.group(1))
    if not 1 <= ninputs <= 20:
        raise ValueError("strict evaluator accepts 1..20 inputs")
    if len(lines) < 2:
        raise ValueError("missing OUTPUTS line")
    if OUTPUT_RE.fullmatch(lines[-1]) is None:
        raise ValueError("last line is not a valid OUTPUTS declaration")
    gates: list[Gate] = []
    for lineno, line in enumerate(lines[1:-1], start=2):
        match = GATE_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"line {lineno}: not a whitelisted gate assignment")
        (
            wire_text,
            op,
            inv_a,
            kind_a,
            index_a,
            inv_b,
            kind_b,
            index_b,
        ) = match.groups()
        wire_index = int(wire_text)
        expected = len(gates) + 1
        if wire_index != expected:
            raise ValueError(
                f"line {lineno}: expected contiguous w{expected}, got w{wire_index}"
            )
        a = Lit(kind_a, int(index_a), bool(inv_a))
        b = Lit(kind_b, int(index_b), bool(inv_b))
        validate_lit(a, ninputs, expected - 1, f"line {lineno}")
        validate_lit(b, ninputs, expected - 1, f"line {lineno}")
        gates.append(Gate(op, a, b))
    output_tokens = lines[-1].split()[1:]
    if not output_tokens:
        raise ValueError("at least one output is required")
    outputs = tuple(parse_lit_token(token) for token in output_tokens)
    for lit in outputs:
        validate_lit(lit, ninputs, len(gates), "OUTPUTS")
    return Circuit(ninputs, tuple(gates), outputs)


def serialize(circuit: Circuit) -> str:
    lines = [f"INPUTS {circuit.ninputs}"]
    for index, gate in enumerate(circuit.gates, start=1):
        if gate.op not in OPS_SET:
            raise AssertionError(f"internal invalid op: {gate.op}")
        validate_lit(gate.a, circuit.ninputs, index - 1, f"internal w{index}")
        validate_lit(gate.b, circuit.ninputs, index - 1, f"internal w{index}")
        lines.append(f"w{index} = {gate.op} {gate.a.text()} {gate.b.text()}")
    for lit in circuit.outputs:
        validate_lit(lit, circuit.ninputs, len(circuit.gates), "internal OUTPUTS")
    lines.append("OUTPUTS " + " ".join(lit.text() for lit in circuit.outputs))
    return "\n".join(lines) + "\n"


def input_truth_tables(ninputs: int) -> tuple[list[int], int]:
    nrows = 1 << ninputs
    mask = (1 << nrows) - 1
    values: list[int] = []
    for input_index in range(ninputs):
        half_period = 1 << input_index
        period = half_period << 1
        block = (1 << half_period) - 1
        value = 0
        for start in range(half_period, nrows, period):
            value |= block << start
        values.append(value)
    return values, mask


def apply_op(op: str, a: int, b: int, mask: int) -> int:
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
    raise AssertionError(f"unknown op: {op}")


def eval_lit(
    lit: Lit, input_values: list[int], wire_values: list[int], mask: int
) -> int:
    value = (
        input_values[lit.index - 1]
        if lit.kind == "x"
        else wire_values[lit.index - 1]
    )
    return mask ^ value if lit.inv else value


def evaluate(circuit: Circuit) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    input_values, mask = input_truth_tables(circuit.ninputs)
    wire_values: list[int] = []
    for gate in circuit.gates:
        a = eval_lit(gate.a, input_values, wire_values, mask)
        b = eval_lit(gate.b, input_values, wire_values, mask)
        wire_values.append(apply_op(gate.op, a, b, mask))
    outputs = tuple(
        eval_lit(lit, input_values, wire_values, mask) for lit in circuit.outputs
    )
    return tuple(wire_values), outputs, mask


def live_wires(circuit: Circuit) -> set[int]:
    live: set[int] = set()
    stack = [lit.index for lit in circuit.outputs if lit.kind == "w"]
    while stack:
        index = stack.pop()
        if index in live:
            continue
        live.add(index)
        gate = circuit.gates[index - 1]
        if gate.a.kind == "w":
            stack.append(gate.a.index)
        if gate.b.kind == "w":
            stack.append(gate.b.index)
    return live


def prune_and_compact(circuit: Circuit) -> Circuit:
    live = live_wires(circuit)
    mapping: dict[int, int] = {}
    new_gates: list[Gate] = []

    def remap(lit: Lit) -> Lit:
        if lit.kind == "x":
            return lit
        return Lit("w", mapping[lit.index], lit.inv)

    for old_index, gate in enumerate(circuit.gates, start=1):
        if old_index not in live:
            continue
        new_index = len(new_gates) + 1
        mapping[old_index] = new_index
        new_gates.append(Gate(gate.op, remap(gate.a), remap(gate.b)))
    new_outputs = tuple(remap(lit) for lit in circuit.outputs)
    return Circuit(circuit.ninputs, tuple(new_gates), new_outputs)


def compose_inv(container_inv: bool, replacement: Lit) -> Lit:
    return Lit(replacement.kind, replacement.index, container_inv ^ replacement.inv)


def substitute_wire(circuit: Circuit, target: int, replacement: Lit) -> Circuit:
    if replacement.kind == "w" and replacement.index >= target:
        raise ValueError("replacement must be topologically earlier than target")

    def sub(lit: Lit) -> Lit:
        if lit.kind == "w" and lit.index == target:
            return compose_inv(lit.inv, replacement)
        return lit

    gates = tuple(Gate(g.op, sub(g.a), sub(g.b)) for g in circuit.gates)
    outputs = tuple(sub(lit) for lit in circuit.outputs)
    return prune_and_compact(Circuit(circuit.ninputs, gates, outputs))


def replace_gate(circuit: Circuit, target: int, replacement: Gate) -> Circuit:
    validate_lit(replacement.a, circuit.ninputs, target - 1, "replacement")
    validate_lit(replacement.b, circuit.ninputs, target - 1, "replacement")
    gates = list(circuit.gates)
    gates[target - 1] = replacement
    return prune_and_compact(
        Circuit(circuit.ninputs, tuple(gates), circuit.outputs)
    )


def source_truth(
    lit: Lit,
    input_values: list[int],
    wire_values: tuple[int, ...],
    mask: int,
) -> int:
    value = (
        input_values[lit.index - 1]
        if lit.kind == "x"
        else wire_values[lit.index - 1]
    )
    return mask ^ value if lit.inv else value


def structural_key(gate: Gate) -> tuple[str, str, str]:
    # All allowed operations are commutative.
    left, right = sorted((gate.a.text(), gate.b.text()))
    return gate.op, left, right


def all_phases(source: Lit) -> tuple[Lit, Lit]:
    plain = Lit(source.kind, source.index, False)
    return plain, plain.toggled()


def find_best_zero_or_one_gate_rewrite(
    circuit: Circuit,
) -> tuple[Circuit, dict[str, object] | None, dict[str, int]]:
    """Exhaustively search zero- and one-gate resubstitution over all prior nodes.

    Every source pair, both input phases, and every whitelisted gate operation is
    considered.  Only full truth-table matches are candidates.
    """

    circuit = prune_and_compact(circuit)
    wire_values, baseline_outputs, mask = evaluate(circuit)
    input_values, _ = input_truth_tables(circuit.ninputs)
    target_functions = set(wire_values)

    # Map exact function to every topologically available source.  This drives
    # exhaustive zero-gate resubstitution.
    available_by_function: dict[int, list[Lit]] = defaultdict(list)
    base_sources = [Lit("x", i) for i in range(1, circuit.ninputs + 1)]
    for source in base_sources:
        value = source_truth(source, input_values, wire_values, mask)
        available_by_function[value].append(source)
        available_by_function[mask ^ value].append(source.toggled())

    # One-gate expression index, populated incrementally so every expression is
    # guaranteed to use wires earlier than the target.  We retain only results
    # equal to some actual node function, avoiding a large untrusted-data-driven
    # memory footprint.
    expr_by_function: dict[int, list[Gate]] = defaultdict(list)
    expr_seen: dict[int, set[tuple[str, str, str]]] = defaultdict(set)
    sources: list[Lit] = list(base_sources)
    best = circuit
    best_info: dict[str, object] | None = None
    stats = {
        "targets": len(circuit.gates),
        "zero_matches": 0,
        "one_gate_function_hits": 0,
        "one_gate_structural_forms": 0,
        "verified_candidates": 0,
    }

    def consider(candidate: Circuit, info: dict[str, object]) -> None:
        nonlocal best, best_info
        if len(candidate.gates) >= len(best.gates):
            return
        _, outputs, _ = evaluate(candidate)
        stats["verified_candidates"] += 1
        if outputs != baseline_outputs:
            raise AssertionError("internal rewrite failed full-domain verification")
        best = candidate
        best_info = info | {
            "before_gates": len(circuit.gates),
            "after_gates": len(candidate.gates),
        }

    def add_new_source(new_source: Lit) -> None:
        # Include self-pairs as identities such as XOR a a; they can matter for
        # constants even though constants are uncommon in these instances.
        previous_plus_self = sources + [new_source]
        phase_new = all_phases(new_source)
        for other in previous_plus_self:
            for a in phase_new:
                for b in all_phases(other):
                    av = source_truth(a, input_values, wire_values, mask)
                    bv = source_truth(b, input_values, wire_values, mask)
                    for op in OPS:
                        result = apply_op(op, av, bv, mask)
                        if result not in target_functions:
                            continue
                        gate = Gate(op, a, b)
                        key = structural_key(gate)
                        if key in expr_seen[result]:
                            continue
                        expr_seen[result].add(key)
                        expr_by_function[result].append(gate)
                        stats["one_gate_structural_forms"] += 1

    # Seed the one-gate index with every unordered pair of inputs exactly once.
    for input_position, new_source in enumerate(base_sources):
        prior = base_sources[: input_position + 1]
        for other in prior:
            for a in all_phases(new_source):
                for b in all_phases(other):
                    av = source_truth(a, input_values, wire_values, mask)
                    bv = source_truth(b, input_values, wire_values, mask)
                    for op in OPS:
                        result = apply_op(op, av, bv, mask)
                        if result not in target_functions:
                            continue
                        gate = Gate(op, a, b)
                        key = structural_key(gate)
                        if key in expr_seen[result]:
                            continue
                        expr_seen[result].add(key)
                        expr_by_function[result].append(gate)
                        stats["one_gate_structural_forms"] += 1

    # At target w_i, indexes contain inputs and wires w_1..w_(i-1).
    for target, target_value in enumerate(wire_values, start=1):
        for replacement in available_by_function.get(target_value, ()):
            stats["zero_matches"] += 1
            candidate = substitute_wire(circuit, target, replacement)
            consider(
                candidate,
                {
                    "kind": "zero_gate_resubstitution",
                    "target": f"w{target}",
                    "replacement": replacement.text(),
                },
            )

        expressions = expr_by_function.get(target_value, ())
        stats["one_gate_function_hits"] += len(expressions)
        original_key = structural_key(circuit.gates[target - 1])
        for gate in expressions:
            if structural_key(gate) == original_key:
                continue
            candidate = replace_gate(circuit, target, gate)
            consider(
                candidate,
                {
                    "kind": "one_gate_resubstitution",
                    "target": f"w{target}",
                    "replacement": (
                        f"{gate.op} {gate.a.text()} {gate.b.text()}"
                    ),
                },
            )

        current_source = Lit("w", target)
        current_value = target_value
        available_by_function[current_value].append(current_source)
        available_by_function[mask ^ current_value].append(
            current_source.toggled()
        )
        # Generate only pairs that include this newly available wire.  Input
        # pairs were seeded above, so each structural pair is covered once.
        for other in sources:
            for a in all_phases(current_source):
                for b in all_phases(other):
                    av = source_truth(a, input_values, wire_values, mask)
                    bv = source_truth(b, input_values, wire_values, mask)
                    for op in OPS:
                        result = apply_op(op, av, bv, mask)
                        if result not in target_functions:
                            continue
                        gate = Gate(op, a, b)
                        key = structural_key(gate)
                        if key in expr_seen[result]:
                            continue
                        expr_seen[result].add(key)
                        expr_by_function[result].append(gate)
                        stats["one_gate_structural_forms"] += 1
        # Self-pair for the new source.
        for a in all_phases(current_source):
            for b in all_phases(current_source):
                av = source_truth(a, input_values, wire_values, mask)
                bv = source_truth(b, input_values, wire_values, mask)
                for op in OPS:
                    result = apply_op(op, av, bv, mask)
                    if result not in target_functions:
                        continue
                    gate = Gate(op, a, b)
                    key = structural_key(gate)
                    if key in expr_seen[result]:
                        continue
                    expr_seen[result].add(key)
                    expr_by_function[result].append(gate)
                    stats["one_gate_structural_forms"] += 1
        sources.append(current_source)

    return best, best_info, stats


def optimize_fixpoint(circuit: Circuit) -> tuple[Circuit, list[dict[str, object]], list[dict[str, int]]]:
    current = prune_and_compact(circuit)
    steps: list[dict[str, object]] = []
    round_stats: list[dict[str, int]] = []
    while True:
        rewritten, info, stats = find_best_zero_or_one_gate_rewrite(current)
        round_stats.append(stats)
        if info is None:
            break
        steps.append(info)
        current = rewritten
    return current, steps, round_stats


def full_domain_verify(reference: Circuit, candidate: Circuit) -> dict[str, object]:
    if reference.ninputs != candidate.ninputs:
        raise AssertionError("input count mismatch")
    _, ref_outputs, _ = evaluate(reference)
    _, cand_outputs, _ = evaluate(candidate)
    if len(ref_outputs) != len(cand_outputs):
        raise AssertionError("output count mismatch")
    equal_each = [a == b for a, b in zip(ref_outputs, cand_outputs)]
    return {
        "rows": 1 << reference.ninputs,
        "outputs": len(ref_outputs),
        "equal_each_output": equal_each,
        "exact": all(equal_each),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.seed != 42:
        raise ValueError("this reproducible search is preregistered to root seed 42")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    for input_path in args.inputs:
        reference = parse_circuit(input_path)
        baseline = prune_and_compact(reference)
        optimized, steps, round_stats = optimize_fixpoint(baseline)
        verification = full_domain_verify(reference, optimized)
        if not verification["exact"]:
            raise AssertionError("candidate is not exactly equivalent")
        output_path = args.out_dir / input_path.name
        output_path.write_text(serialize(optimized), encoding="ascii", newline="\n")
        # Reparse serialized bytes as a second syntax/topology check.
        reparsed = parse_circuit(output_path)
        second_verification = full_domain_verify(reference, reparsed)
        if not second_verification["exact"]:
            raise AssertionError("serialized candidate failed exact equivalence")
        summaries.append(
            {
                "name": input_path.name,
                "seed": args.seed,
                "original_gates": len(reference.gates),
                "initial_live_gates": len(baseline.gates),
                "optimized_gates": len(optimized.gates),
                "saved_gates": len(reference.gates) - len(optimized.gates),
                "steps": steps,
                "round_stats": round_stats,
                "verification": second_verification,
                "output_path": str(output_path),
            }
        )
    report_path = args.out_dir / "report.json"
    report_path.write_text(
        json.dumps(summaries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(summaries, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
