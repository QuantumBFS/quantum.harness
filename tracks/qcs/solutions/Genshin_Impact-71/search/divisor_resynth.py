#!/usr/bin/env python3
"""Exact phase-aware local resynthesis with external divisors.

Security boundary:
* Input netlists are untrusted data, accepted only by a small ASCII grammar.
* No input text is evaluated, imported, interpolated into a command, or run.
* The only synthesized operations are AND/XOR with free literal negation;
  this represents all six challenge gates modulo free input/output phase.

For a root, the atom set is every primary input and every topologically prior
wire outside the root's MFFC.  The search is complete for all connected
straight-line programs of at most three binary gates:

  1 gate:  g1(atom, atom)
  2 gates: g1(atom, atom); g2(g1, atom)
  3 gates: chain g3(g2, atom), reuse g3(g2, g1), or independent
           branches g3(g1, g2).

Semantically redundant self-gates only produce a constant or a phase of their
input and are covered at lower cost.  Candidate circuits are exhaustively
verified over the full input domain, serialized, strictly reparsed, and
verified again.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator, Sequence


OPS = ("AND", "OR", "XOR", "NAND", "NOR", "XNOR")
OPS_SET = frozenset(OPS)
INPUT_RE = re.compile(r"INPUTS ([1-9][0-9]*)\Z")
GATE_RE = re.compile(
    r"w([1-9][0-9]*) = (AND|OR|XOR|NAND|NOR|XNOR) "
    r"(~?)([xw])([1-9][0-9]*) (~?)([xw])([1-9][0-9]*)\Z"
)
OUTPUT_RE = re.compile(r"OUTPUTS( ~?[xw][1-9][0-9]*)+\Z")
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


@dataclasses.dataclass(frozen=True, slots=True)
class Ref:
    kind: str  # "base" or "local"
    index: int  # zero based
    inv: bool = False

    def toggled(self) -> "Ref":
        return Ref(self.kind, self.index, not self.inv)


@dataclasses.dataclass(frozen=True, slots=True)
class PGate:
    op: str  # canonical synthesis basis: AND or XOR
    a: Ref
    b: Ref


@dataclasses.dataclass(frozen=True, slots=True)
class Program:
    # `out` denotes exactly the canonical phase representative `func`.
    func: int
    gates: tuple[PGate, ...]
    out: Ref

    @property
    def cost(self) -> int:
        return len(self.gates)


class DeadlineExceeded(RuntimeError):
    pass


def parse_lit(token: str) -> Lit:
    match = TOKEN_RE.fullmatch(token)
    if match is None:
        raise ValueError(f"invalid literal token: {token!r}")
    inv, kind, index = match.groups()
    return Lit(kind, int(index), bool(inv))


def validate_lit(lit: Lit, ninputs: int, max_wire: int, context: str) -> None:
    if lit.kind == "x":
        if not 1 <= lit.index <= ninputs:
            raise ValueError(f"{context}: input out of range: {lit.text()}")
    elif lit.kind == "w":
        if not 1 <= lit.index <= max_wire:
            raise ValueError(
                f"{context}: non-prior wire {lit.text()} (max w{max_wire})"
            )
    else:
        raise ValueError(f"{context}: invalid literal kind")


def parse_circuit(path: Path) -> Circuit:
    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError("netlist exceeds strict 2 MB limit")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("netlist must be ASCII") from exc
    lines = text.splitlines()
    if not lines or any(len(line) > 4096 for line in lines):
        raise ValueError("empty netlist or overlong line")
    first = INPUT_RE.fullmatch(lines[0])
    if first is None:
        raise ValueError("invalid INPUTS line")
    ninputs = int(first.group(1))
    if not 1 <= ninputs <= 20:
        raise ValueError("strict evaluator accepts 1..20 inputs")
    if len(lines) < 2 or OUTPUT_RE.fullmatch(lines[-1]) is None:
        raise ValueError("invalid or missing OUTPUTS line")
    gates: list[Gate] = []
    for lineno, line in enumerate(lines[1:-1], start=2):
        match = GATE_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"line {lineno}: invalid gate assignment")
        wi, op, ia, ka, xa, ib, kb, xb = match.groups()
        expected = len(gates) + 1
        if int(wi) != expected:
            raise ValueError(
                f"line {lineno}: expected contiguous w{expected}, got w{wi}"
            )
        a = Lit(ka, int(xa), bool(ia))
        b = Lit(kb, int(xb), bool(ib))
        validate_lit(a, ninputs, expected - 1, f"line {lineno}")
        validate_lit(b, ninputs, expected - 1, f"line {lineno}")
        gates.append(Gate(op, a, b))
    outputs = tuple(parse_lit(tok) for tok in lines[-1].split()[1:])
    if not outputs:
        raise ValueError("at least one output is required")
    for output in outputs:
        validate_lit(output, ninputs, len(gates), "OUTPUTS")
    return Circuit(ninputs, tuple(gates), outputs)


def serialize(circuit: Circuit) -> str:
    lines = [f"INPUTS {circuit.ninputs}"]
    for index, gate in enumerate(circuit.gates, start=1):
        if gate.op not in OPS_SET:
            raise AssertionError("invalid internal operation")
        validate_lit(gate.a, circuit.ninputs, index - 1, f"w{index}")
        validate_lit(gate.b, circuit.ninputs, index - 1, f"w{index}")
        lines.append(
            f"w{index} = {gate.op} {gate.a.text()} {gate.b.text()}"
        )
    for output in circuit.outputs:
        validate_lit(output, circuit.ninputs, len(circuit.gates), "OUTPUTS")
    lines.append("OUTPUTS " + " ".join(x.text() for x in circuit.outputs))
    return "\n".join(lines) + "\n"


def input_truth_tables(ninputs: int) -> tuple[list[int], int]:
    rows = 1 << ninputs
    mask = (1 << rows) - 1
    values: list[int] = []
    for bit in range(ninputs):
        half = 1 << bit
        period = half << 1
        block = (1 << half) - 1
        value = 0
        for start in range(half, rows, period):
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
    raise AssertionError(f"invalid operation {op!r}")


def literal_value(
    lit: Lit, inputs: Sequence[int], wires: Sequence[int], mask: int
) -> int:
    value = inputs[lit.index - 1] if lit.kind == "x" else wires[lit.index - 1]
    return mask ^ value if lit.inv else value


def evaluate(circuit: Circuit) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    inputs, mask = input_truth_tables(circuit.ninputs)
    wires: list[int] = []
    for gate in circuit.gates:
        a = literal_value(gate.a, inputs, wires, mask)
        b = literal_value(gate.b, inputs, wires, mask)
        wires.append(apply_op(gate.op, a, b, mask))
    outputs = tuple(
        literal_value(output, inputs, wires, mask)
        for output in circuit.outputs
    )
    return tuple(wires), outputs, mask


def live_wires(circuit: Circuit) -> set[int]:
    live: set[int] = set()
    stack = [x.index for x in circuit.outputs if x.kind == "w"]
    while stack:
        wire = stack.pop()
        if wire in live:
            continue
        live.add(wire)
        gate = circuit.gates[wire - 1]
        if gate.a.kind == "w":
            stack.append(gate.a.index)
        if gate.b.kind == "w":
            stack.append(gate.b.index)
    return live


def prune_and_compact(circuit: Circuit) -> Circuit:
    live = live_wires(circuit)
    mapping: dict[int, int] = {}
    gates: list[Gate] = []

    def remap(lit: Lit) -> Lit:
        if lit.kind == "x":
            return lit
        return Lit("w", mapping[lit.index], lit.inv)

    for old, gate in enumerate(circuit.gates, start=1):
        if old not in live:
            continue
        mapping[old] = len(gates) + 1
        gates.append(Gate(gate.op, remap(gate.a), remap(gate.b)))
    return Circuit(
        circuit.ninputs,
        tuple(gates),
        tuple(remap(output) for output in circuit.outputs),
    )


def canonical(value: int, mask: int) -> tuple[int, bool]:
    complement = mask ^ value
    if complement < value:
        return complement, True
    return value, False


def fanout_counts(circuit: Circuit) -> list[int]:
    counts = [0] * len(circuit.gates)
    for gate in circuit.gates:
        for lit in (gate.a, gate.b):
            if lit.kind == "w":
                counts[lit.index - 1] += 1
    for output in circuit.outputs:
        if output.kind == "w":
            counts[output.index - 1] += 1
    return counts


def mffc(circuit: Circuit, root: int, counts: Sequence[int]) -> set[int]:
    remaining = list(counts)
    removed: set[int] = set()
    stack = [root]
    while stack:
        wire = stack.pop()
        if wire in removed:
            continue
        removed.add(wire)
        gate = circuit.gates[wire - 1]
        for lit in (gate.a, gate.b):
            if lit.kind != "w":
                continue
            remaining[lit.index - 1] -= 1
            if remaining[lit.index - 1] == 0:
                stack.append(lit.index)
    return removed


def shift_ref(ref: Ref, amount: int) -> Ref:
    if ref.kind == "base":
        return ref
    if ref.kind != "local":
        raise AssertionError("invalid program reference")
    return Ref("local", ref.index + amount, ref.inv)


def shift_gate(gate: PGate, amount: int) -> PGate:
    return PGate(gate.op, shift_ref(gate.a, amount), shift_ref(gate.b, amount))


def matching_variant(
    left: int, right: int, target: int, mask: int
) -> tuple[str, bool, bool, bool] | None:
    """Return op, input phases, and output phase for target's phase class."""
    seen: set[int] = set()
    for li in (False, True):
        a = mask ^ left if li else left
        for ri in (False, True):
            b = mask ^ right if ri else right
            for op in ("AND", "XOR"):
                raw = apply_op(op, a, b, mask)
                func, oi = canonical(raw, mask)
                if func in seen:
                    continue
                seen.add(func)
                if func == target:
                    return op, li, ri, oi
    return None


def merge_programs(
    left: Program,
    right: Program,
    target: int,
    mask: int,
) -> Program:
    variant = matching_variant(left.func, right.func, target, mask)
    if variant is None:
        raise AssertionError("requested program merge does not match target")
    op, li, ri, oi = variant
    shift = left.cost
    shifted_right_gates = tuple(shift_gate(x, shift) for x in right.gates)
    right_out = shift_ref(right.out, shift)
    prefix = left.gates + shifted_right_gates
    gate = PGate(
        op,
        left.out.toggled() if li else left.out,
        right_out.toggled() if ri else right_out,
    )
    out = Ref("local", len(prefix), oi)
    return Program(target, prefix + (gate,), out)


def append_existing(
    prefix: Program,
    other_func: int,
    other_ref: Ref,
    target: int,
    mask: int,
) -> Program:
    variant = matching_variant(prefix.func, other_func, target, mask)
    if variant is None:
        raise AssertionError("requested append does not match target")
    op, li, ri, oi = variant
    gate = PGate(
        op,
        prefix.out.toggled() if li else prefix.out,
        other_ref.toggled() if ri else other_ref,
    )
    return Program(
        target,
        prefix.gates + (gate,),
        Ref("local", prefix.cost, oi),
    )


def pair_variants(
    left: Program, right: Program, mask: int
) -> Iterator[Program]:
    """Yield one witness for every output phase class of this pair."""
    seen: set[int] = set()
    for li in (False, True):
        a = mask ^ left.func if li else left.func
        for ri in (False, True):
            b = mask ^ right.func if ri else right.func
            for op in ("AND", "XOR"):
                raw = apply_op(op, a, b, mask)
                func, oi = canonical(raw, mask)
                if func in seen:
                    continue
                seen.add(func)
                # pair_variants is used for atom/atom and prefix/atom, so the
                # right program has cost zero and no local-index shift is needed.
                if right.cost:
                    raise AssertionError("pair_variants right side must be an atom")
                gate = PGate(
                    op,
                    left.out.toggled() if li else left.out,
                    right.out.toggled() if ri else right.out,
                )
                yield Program(
                    func,
                    left.gates + (gate,),
                    Ref("local", left.cost, oi),
                )


class TargetPairIndex:
    """Target-directed exact pair query; avoids quadratic branch enumeration."""

    def __init__(
        self,
        rights: Sequence[Program],
        target: int,
        mask: int,
    ) -> None:
        self.target = target
        self.mask = mask
        self.by_func = {x.func: x for x in rights}
        self.cover: list[list[tuple[int, Program]]] = []
        for desired in (target, mask ^ target):
            candidates: list[tuple[int, Program]] = []
            for program in rights:
                for inv in (False, True):
                    value = mask ^ program.func if inv else program.func
                    if value & desired == desired:
                        candidates.append((value, program))
            self.cover.append(candidates)

    def find(self, left: int) -> Program | None:
        # XOR: phases only change the output phase, so the partner phase class
        # is uniquely determined.
        wanted, _ = canonical(left ^ self.target, self.mask)
        right = self.by_func.get(wanted)
        if right is not None:
            if matching_variant(left, right.func, self.target, self.mask):
                return right
            raise AssertionError("XOR index invariant failed")

        # AND family: U & V must equal target or its complement.  Filter V by
        # the necessary cover relation and test the remaining disjointness.
        for desired_index, desired in enumerate(
            (self.target, self.mask ^ self.target)
        ):
            for left_inv in (False, True):
                u = self.mask ^ left if left_inv else left
                if u & desired != desired:
                    continue
                for v, candidate in self.cover[desired_index]:
                    if u & v == desired:
                        if matching_variant(
                            left, candidate.func, self.target, self.mask
                        ):
                            return candidate
                        raise AssertionError("AND index invariant failed")
        return None

    def cover_sizes(self) -> list[int]:
        return [len(x) for x in self.cover]


def make_atoms(
    circuit: Circuit,
    root: int,
    removed: set[int],
    inputs: Sequence[int],
    wires: Sequence[int],
    mask: int,
) -> tuple[list[Lit], list[Program]]:
    physical: list[Lit] = [
        Lit("x", index) for index in range(1, circuit.ninputs + 1)
    ]
    physical.extend(
        Lit("w", wire)
        for wire in range(1, root)
        if wire not in removed
    )
    base_lits: list[Lit] = []
    atoms_by_func: dict[int, Program] = {}
    for lit in physical:
        raw = literal_value(lit, inputs, wires, mask)
        func, inv = canonical(raw, mask)
        if func in atoms_by_func:
            continue
        base_index = len(base_lits)
        base_lits.append(lit)
        atoms_by_func[func] = Program(
            func, (), Ref("base", base_index, inv)
        )
    return base_lits, list(atoms_by_func.values())


def make_layer1(
    atoms: Sequence[Program],
    target: int,
    mask: int,
    deadline: float,
) -> tuple[dict[int, Program], Program | None, dict[str, int]]:
    atom_funcs = {x.func for x in atoms}
    layer: dict[int, Program] = {}
    stats = {
        "atom_pairs": 0,
        "semantic_variants": 0,
        "dominated_variants": 0,
        "unique_layer1_functions": 0,
    }
    hit: Program | None = None
    for left_index, left in enumerate(atoms):
        if time.monotonic() > deadline:
            raise DeadlineExceeded("deadline while building layer 1")
        for right in atoms[: left_index + 1]:
            stats["atom_pairs"] += 1
            for program in pair_variants(left, right, mask):
                stats["semantic_variants"] += 1
                if program.func == target and hit is None:
                    hit = program
                if program.func in atom_funcs:
                    stats["dominated_variants"] += 1
                    continue
                layer.setdefault(program.func, program)
    stats["unique_layer1_functions"] = len(layer)
    return layer, hit, stats


def synthesize(
    atoms: Sequence[Program],
    target_value: int,
    mask: int,
    max_cost: int,
    deadline: float,
) -> tuple[Program | None, dict[str, object]]:
    target, _ = canonical(target_value, mask)
    atom_by_func = {x.func: x for x in atoms}
    stats: dict[str, object] = {
        "atoms": len(atoms),
        "max_cost": max_cost,
        "target_popcount_canonical": target.bit_count(),
    }
    if target in atom_by_func:
        stats["result_tier"] = 0
        return atom_by_func[target], stats
    if max_cost < 1:
        stats["result_tier"] = None
        return None, stats

    layer1, cost1_hit, layer1_stats = make_layer1(
        atoms, target, mask, deadline
    )
    stats["layer1"] = layer1_stats
    if cost1_hit is not None:
        stats["result_tier"] = 1
        return cost1_hit, stats
    if max_cost < 2:
        stats["result_tier"] = None
        return None, stats

    atom_target_index = TargetPairIndex(atoms, target, mask)
    stats["atom_target_and_cover_sizes"] = atom_target_index.cover_sizes()
    cost2_queries = 0
    for first in layer1.values():
        cost2_queries += 1
        partner = atom_target_index.find(first.func)
        if partner is not None:
            result = merge_programs(first, partner, target, mask)
            if result.cost != 2:
                raise AssertionError("cost-2 construction mismatch")
            stats["cost2_target_queries"] = cost2_queries
            stats["result_tier"] = 2
            return result, stats
    stats["cost2_target_queries"] = cost2_queries
    if max_cost < 3:
        stats["result_tier"] = None
        return None, stats

    # Independent-branch topology, target-directed exact meet-in-the-middle.
    layer1_values = list(layer1.values())
    branch_index = TargetPairIndex(layer1_values, target, mask)
    stats["branch_target_and_cover_sizes"] = branch_index.cover_sizes()
    branch_queries = 0
    for left in layer1_values:
        branch_queries += 1
        right = branch_index.find(left.func)
        if right is None:
            continue
        if left.func == right.func:
            # Sharing the identical semantic signal costs two gates total.
            result = append_existing(
                left, left.func, left.out, target, mask
            )
            if result.cost > 2:
                raise AssertionError("shared branch should cost at most two")
        else:
            result = merge_programs(left, right, target, mask)
        stats["branch_target_queries"] = branch_queries
        stats["result_tier"] = result.cost
        return result, stats
    stats["branch_target_queries"] = branch_queries

    # Chain and reconvergent-reuse topologies.  Enumerate every semantic
    # g2(g1, atom) state.  Each state is queried against all atoms through the
    # exact target index and against its own g1 directly.
    layer2_pairs = 0
    layer2_variants = 0
    chain_queries = 0
    reuse_queries = 0
    for first in layer1_values:
        first_ref = first.out
        for atom in atoms:
            layer2_pairs += 1
            if (layer2_pairs & 4095) == 0 and time.monotonic() > deadline:
                raise DeadlineExceeded("deadline in exact cost-3 enumeration")
            for second in pair_variants(first, atom, mask):
                layer2_variants += 1
                # Defensive catch: the target index above should already have
                # found every cost-2 target.
                if second.func == target:
                    stats["unexpected_direct_cost2"] = True
                    stats["result_tier"] = 2
                    return second, stats

                reuse_queries += 1
                if matching_variant(
                    second.func, first.func, target, mask
                ) is not None:
                    result = append_existing(
                        second, first.func, first_ref, target, mask
                    )
                    stats.update(
                        {
                            "layer2_pairs": layer2_pairs,
                            "layer2_semantic_variants": layer2_variants,
                            "chain_target_queries": chain_queries,
                            "reuse_target_queries": reuse_queries,
                            "result_tier": 3,
                            "result_topology": "reuse",
                        }
                    )
                    return result, stats

                chain_queries += 1
                partner = atom_target_index.find(second.func)
                if partner is not None:
                    result = merge_programs(
                        second, partner, target, mask
                    )
                    stats.update(
                        {
                            "layer2_pairs": layer2_pairs,
                            "layer2_semantic_variants": layer2_variants,
                            "chain_target_queries": chain_queries,
                            "reuse_target_queries": reuse_queries,
                            "result_tier": 3,
                            "result_topology": "chain",
                        }
                    )
                    return result, stats
    stats.update(
        {
            "layer2_pairs": layer2_pairs,
            "layer2_semantic_variants": layer2_variants,
            "chain_target_queries": chain_queries,
            "reuse_target_queries": reuse_queries,
            "result_tier": None,
        }
    )
    return None, stats


def convert_ref(ref: Ref, bases: Sequence[Lit], root: int) -> Lit:
    if ref.kind == "base":
        base = bases[ref.index]
        return Lit(base.kind, base.index, base.inv ^ ref.inv)
    if ref.kind == "local":
        return Lit("w", root + ref.index, ref.inv)
    raise AssertionError("invalid program reference")


def insert_program(
    circuit: Circuit,
    root: int,
    bases: Sequence[Lit],
    program: Program,
    target_value: int,
    mask: int,
) -> Circuit:
    target, target_complemented = canonical(target_value, mask)
    if program.func != target:
        raise AssertionError("program phase class does not match root")

    inserted: list[Gate] = []
    for local_index, gate in enumerate(program.gates):
        a = convert_ref(gate.a, bases, root)
        b = convert_ref(gate.b, bases, root)
        validate_lit(a, circuit.ninputs, root + local_index - 1, "synthesis")
        validate_lit(b, circuit.ninputs, root + local_index - 1, "synthesis")
        inserted.append(Gate(gate.op, a, b))

    replacement_ref = program.out.toggled() if target_complemented else program.out
    replacement = convert_ref(replacement_ref, bases, root)
    shift = program.cost - 1

    def remap(lit: Lit) -> Lit:
        if lit.kind == "x":
            return lit
        if lit.index < root:
            return lit
        if lit.index == root:
            return Lit(
                replacement.kind,
                replacement.index,
                lit.inv ^ replacement.inv,
            )
        return Lit("w", lit.index + shift, lit.inv)

    prefix = list(circuit.gates[: root - 1])
    suffix = [
        Gate(gate.op, remap(gate.a), remap(gate.b))
        for gate in circuit.gates[root:]
    ]
    expanded = Circuit(
        circuit.ninputs,
        tuple(prefix + inserted + suffix),
        tuple(remap(output) for output in circuit.outputs),
    )
    return prune_and_compact(expanded)


def full_domain_equal(reference: Circuit, candidate: Circuit) -> dict[str, object]:
    if reference.ninputs != candidate.ninputs:
        raise AssertionError("input width mismatch")
    _, left, _ = evaluate(reference)
    _, right, _ = evaluate(candidate)
    if len(left) != len(right):
        raise AssertionError("output width mismatch")
    equal = [a == b for a, b in zip(left, right)]
    return {
        "rows": 1 << reference.ninputs,
        "outputs": len(left),
        "equal_each_output": equal,
        "exact": all(equal),
    }


def search_round(
    circuit: Circuit,
    deadline: float,
    root_filter: set[int] | None,
) -> tuple[Circuit, dict[str, object] | None, dict[str, object]]:
    circuit = prune_and_compact(circuit)
    inputs, mask = input_truth_tables(circuit.ninputs)
    wires, baseline_outputs, _ = evaluate(circuit)
    counts = fanout_counts(circuit)
    records: list[dict[str, object]] = []
    best = circuit
    best_info: dict[str, object] | None = None
    mffc_hist: Counter[int] = Counter()

    for root, target_value in enumerate(wires, start=1):
        removed = mffc(circuit, root, counts)
        size = len(removed)
        mffc_hist[size] += 1
        if root_filter is not None and root not in root_filter:
            continue
        max_cost = min(3, size - 1)
        record: dict[str, object] = {
            "root": root,
            "mffc_size": size,
            "max_cost": max_cost,
        }
        if max_cost < 0:
            record["status"] = "impossible"
            records.append(record)
            continue
        bases, atoms = make_atoms(
            circuit, root, removed, inputs, wires, mask
        )
        record["physical_divisors_before_phase_dedup"] = (
            circuit.ninputs + (root - 1) - len(
                [wire for wire in removed if wire < root]
            )
        )
        record["semantic_divisor_phase_classes"] = len(atoms)
        record["excluded_mffc_wires"] = sorted(
            wire for wire in removed if wire < root
        )
        try:
            program, synth_stats = synthesize(
                atoms, target_value, mask, max_cost, deadline
            )
        except DeadlineExceeded as exc:
            record["status"] = "deadline"
            record["error"] = str(exc)
            records.append(record)
            raise
        record["synthesis"] = synth_stats
        if program is None:
            record["status"] = "exhausted_no_match"
            records.append(record)
            continue
        candidate = insert_program(
            circuit, root, bases, program, target_value, mask
        )
        _, outputs, _ = evaluate(candidate)
        if outputs != baseline_outputs:
            raise AssertionError("candidate failed full-domain output verification")
        saved = len(circuit.gates) - len(candidate.gates)
        if saved < 1:
            # This can occur only if the semantic match did not eliminate the
            # expected MFFC due to a bookkeeping error, so fail closed.
            raise AssertionError("matched program did not save a gate")
        record.update(
            {
                "status": "verified_match",
                "program_cost": program.cost,
                "candidate_gates": len(candidate.gates),
                "saved_gates": saved,
            }
        )
        records.append(record)
        if len(candidate.gates) < len(best.gates):
            best = candidate
            best_info = {
                "kind": "phase_aware_external_divisor_resynthesis",
                "root": root,
                "mffc_size": size,
                "program_cost": program.cost,
                "before_gates": len(circuit.gates),
                "after_gates": len(candidate.gates),
                "saved_gates": saved,
                "semantic_divisors": len(atoms),
            }

    return best, best_info, {
        "gate_count": len(circuit.gates),
        "mffc_histogram": dict(sorted(mffc_hist.items())),
        "records": records,
    }


def optimize(
    circuit: Circuit,
    deadline: float,
    root_filter: set[int] | None,
) -> tuple[Circuit, list[dict[str, object]], list[dict[str, object]]]:
    current = prune_and_compact(circuit)
    steps: list[dict[str, object]] = []
    rounds: list[dict[str, object]] = []
    while True:
        candidate, info, report = search_round(
            current, deadline, root_filter
        )
        rounds.append(report)
        if info is None:
            return current, steps, rounds
        steps.append(info)
        current = candidate
        # Explicit root filters refer to the original numbering and therefore
        # are intentionally single-round diagnostic runs.
        if root_filter is not None:
            return current, steps, rounds


def parse_roots(text: str | None) -> set[int] | None:
    if text is None:
        return None
    roots: set[int] = set()
    for token in text.split(","):
        if not token or not token.isascii() or not token.isdigit():
            raise ValueError("--roots must be comma-separated positive integers")
        value = int(token)
        if value < 1:
            raise ValueError("--roots must be positive")
        roots.add(value)
    return roots


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--deadline-seconds", type=int, default=540)
    parser.add_argument("--roots")
    args = parser.parse_args()
    if args.seed != 42:
        raise ValueError("deterministic search is preregistered to seed 42")
    if not 1 <= args.deadline_seconds <= 86400:
        raise ValueError("deadline must be in 1..86400 seconds")
    root_filter = parse_roots(args.roots)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + args.deadline_seconds
    summaries: list[dict[str, object]] = []

    for input_path in args.inputs:
        reference = parse_circuit(input_path)
        initial = prune_and_compact(reference)
        try:
            optimized, steps, rounds = optimize(
                initial, deadline, root_filter
            )
            status = "complete"
        except DeadlineExceeded as exc:
            optimized = initial
            steps = []
            rounds = []
            status = f"deadline: {exc}"
        verification = full_domain_equal(reference, optimized)
        if not verification["exact"]:
            raise AssertionError("optimized circuit is not exactly equivalent")
        output_path = args.out_dir / input_path.name
        output_path.write_text(
            serialize(optimized), encoding="ascii", newline="\n"
        )
        reparsed = parse_circuit(output_path)
        recheck = full_domain_equal(reference, reparsed)
        if not recheck["exact"]:
            raise AssertionError("serialized circuit failed strict recheck")
        summary = {
            "name": input_path.name,
            "seed": args.seed,
            "status": status,
            "root_filter": sorted(root_filter) if root_filter else None,
            "original_gates": len(reference.gates),
            "initial_live_gates": len(initial.gates),
            "optimized_gates": len(optimized.gates),
            "saved_gates": len(reference.gates) - len(optimized.gates),
            "elapsed_seconds": time.monotonic() - started,
            "steps": steps,
            "rounds": rounds,
            "verification": recheck,
            "output_path": str(output_path),
        }
        summaries.append(summary)
        print(json.dumps(summary, indent=2, sort_keys=True))

    report_path = args.out_dir / "report.json"
    report_path.write_text(
        json.dumps(summaries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT {report_path}")


if __name__ == "__main__":
    main()
