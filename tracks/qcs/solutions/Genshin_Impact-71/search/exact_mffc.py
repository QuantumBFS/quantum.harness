#!/usr/bin/env python3
"""Exact 1--3 gate MFFC replacement over strict Occam netlists.

This imports only the independently written strict parser/evaluator in the same
directory.  Competitor code and prose files are never imported or executed.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from reduce_netlist import (
    Circuit,
    Gate,
    Lit,
    apply_op,
    evaluate,
    full_domain_verify,
    input_truth_tables,
    live_wires,
    parse_circuit,
    prune_and_compact,
    serialize,
    validate_lit,
)


@dataclasses.dataclass(frozen=True, slots=True)
class SRef:
    kind: str  # "base" or "local"
    index: int  # zero based
    inv: bool = False

    def toggled(self) -> "SRef":
        return SRef(self.kind, self.index, not self.inv)


@dataclasses.dataclass(frozen=True, slots=True)
class SGate:
    op: str  # canonical exact-synthesis basis: AND or XOR
    a: SRef
    b: SRef


@dataclasses.dataclass(frozen=True, slots=True)
class Synth:
    # `func` is represented exactly by `out`, including out.inv.
    func: int
    gates: tuple[SGate, ...]
    out: SRef
    # Canonical functions/references for gate-produced signals, in local order.
    signals: tuple[tuple[int, SRef], ...]

    @property
    def cost(self) -> int:
        return len(self.gates)


def canonical(value: int, mask: int) -> tuple[int, bool]:
    complement = mask ^ value
    if complement < value:
        return complement, True
    return value, False


def shift_ref(ref: SRef, local_shift: int) -> SRef:
    if ref.kind == "base":
        return ref
    if ref.kind != "local":
        raise AssertionError(f"bad SRef kind: {ref.kind}")
    return SRef("local", ref.index + local_shift, ref.inv)


def shift_gate(gate: SGate, local_shift: int) -> SGate:
    return SGate(
        gate.op,
        shift_ref(gate.a, local_shift),
        shift_ref(gate.b, local_shift),
    )


def synth_signature(synth: Synth) -> tuple[object, ...]:
    return (
        synth.func,
        tuple(
            (
                gate.op,
                gate.a.kind,
                gate.a.index,
                gate.a.inv,
                gate.b.kind,
                gate.b.index,
                gate.b.inv,
            )
            for gate in synth.gates
        ),
        synth.out.kind,
        synth.out.index,
        synth.out.inv,
    )


def combine_disjoint_variants(
    left: Synth, right: Synth, mask: int
) -> Iterable[Synth]:
    """Combine two disjoint synthesized DAGs with one AND/XOR gate."""

    shift = left.cost
    right_gates = tuple(shift_gate(gate, shift) for gate in right.gates)
    right_out = shift_ref(right.out, shift)
    right_signals = tuple(
        (func, shift_ref(ref, shift)) for func, ref in right.signals
    )
    prefix_gates = left.gates + right_gates
    prefix_signals = left.signals + right_signals
    seen_functions: set[int] = set()
    for left_inv in (False, True):
        left_ref = left.out.toggled() if left_inv else left.out
        left_value = mask ^ left.func if left_inv else left.func
        for right_inv in (False, True):
            right_ref = right_out.toggled() if right_inv else right_out
            right_value = mask ^ right.func if right_inv else right.func
            for op in ("AND", "XOR"):
                raw = apply_op(op, left_value, right_value, mask)
                func, output_inverted = canonical(raw, mask)
                if func in seen_functions:
                    continue
                seen_functions.add(func)
                local_index = len(prefix_gates)
                raw_ref = SRef("local", local_index, False)
                out_ref = raw_ref.toggled() if output_inverted else raw_ref
                gate = SGate(op, left_ref, right_ref)
                yield Synth(
                    func,
                    prefix_gates + (gate,),
                    out_ref,
                    prefix_signals + ((func, out_ref),),
                )


def extend_with_existing_variants(
    prefix: Synth,
    other_func: int,
    other_ref: SRef,
    mask: int,
) -> Iterable[Synth]:
    """Append a gate combining prefix.out with an already present signal."""

    seen_functions: set[int] = set()
    for prefix_inv in (False, True):
        prefix_ref = prefix.out.toggled() if prefix_inv else prefix.out
        prefix_value = mask ^ prefix.func if prefix_inv else prefix.func
        for other_inv in (False, True):
            ref = other_ref.toggled() if other_inv else other_ref
            other_value = mask ^ other_func if other_inv else other_func
            for op in ("AND", "XOR"):
                raw = apply_op(op, prefix_value, other_value, mask)
                func, output_inverted = canonical(raw, mask)
                if func in seen_functions:
                    continue
                seen_functions.add(func)
                local_index = prefix.cost
                raw_ref = SRef("local", local_index, False)
                out_ref = raw_ref.toggled() if output_inverted else raw_ref
                gate = SGate(op, prefix_ref, ref)
                yield Synth(
                    func,
                    prefix.gates + (gate,),
                    out_ref,
                    prefix.signals + ((func, out_ref),),
                )


def fanout_counts(circuit: Circuit) -> list[int]:
    counts = [0] * len(circuit.gates)
    for gate in circuit.gates:
        for lit in (gate.a, gate.b):
            if lit.kind == "w":
                counts[lit.index - 1] += 1
    for lit in circuit.outputs:
        if lit.kind == "w":
            counts[lit.index - 1] += 1
    return counts


def mffc_and_cut(
    circuit: Circuit, root: int, reference_counts: list[int]
) -> tuple[set[int], tuple[Lit, ...]]:
    """Return exact MFFC nodes and its unique phase-free boundary signals."""

    remaining = list(reference_counts)
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

    leaves_set: set[tuple[str, int]] = set()
    for wire in removed:
        gate = circuit.gates[wire - 1]
        for lit in (gate.a, gate.b):
            if lit.kind == "x" or lit.index not in removed:
                leaves_set.add((lit.kind, lit.index))
    leaves = tuple(
        Lit(kind, index, False)
        for kind, index in sorted(
            leaves_set, key=lambda item: (item[0] != "x", item[1])
        )
    )
    return removed, leaves


def literal_value(
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


def make_atoms(
    leaves: tuple[Lit, ...],
    input_values: list[int],
    wire_values: tuple[int, ...],
    mask: int,
) -> list[Synth]:
    atoms_by_function: dict[int, Synth] = {}
    for base_index, leaf in enumerate(leaves):
        raw = literal_value(leaf, input_values, wire_values, mask)
        func, inverted = canonical(raw, mask)
        out = SRef("base", base_index, inverted)
        atoms_by_function.setdefault(func, Synth(func, (), out, ()))
    return list(atoms_by_function.values())


def synthesize_up_to_three(
    target_value: int,
    leaves: tuple[Lit, ...],
    input_values: list[int],
    wire_values: tuple[int, ...],
    mask: int,
    max_cost: int,
) -> tuple[Synth | None, dict[str, int]]:
    """Exhaustively synthesize every 1--3 gate SLP topology over `leaves`."""

    target_func, _ = canonical(target_value, mask)
    atoms = make_atoms(leaves, input_values, wire_values, mask)
    atom_functions = {atom.func for atom in atoms}
    stats = {
        "atoms": len(atoms),
        "cost1_functions": 0,
        "cost2_states": 0,
        "cost3_chain_checks": 0,
        "cost3_reuse_checks": 0,
        "cost3_branch_checks": 0,
    }
    if target_func in atom_functions:
        # Normally caught by zero-gate global resubstitution, but retaining this
        # makes the exact cut search logically complete.
        atom = next(atom for atom in atoms if atom.func == target_func)
        return atom, stats
    if max_cost < 1:
        return None, stats

    layer1: dict[int, Synth] = {}
    for left_index, left in enumerate(atoms):
        for right in atoms[: left_index + 1]:
            for synth in combine_disjoint_variants(left, right, mask):
                if synth.func in atom_functions:
                    continue
                layer1.setdefault(synth.func, synth)
    stats["cost1_functions"] = len(layer1)
    if target_func in layer1:
        return layer1[target_func], stats
    if max_cost < 2:
        return None, stats

    # A cost-2 SLP is necessarily g1=f(base,base), g2=f(g1,base).
    # Preserve (g2 function, g1 function), which is the complete semantic state
    # needed for the cost-3 topology that reuses g1.
    layer2: dict[tuple[int, int], Synth] = {}
    cheap_functions = atom_functions | set(layer1)
    for first_func, first in layer1.items():
        for atom in atoms:
            for synth in combine_disjoint_variants(first, atom, mask):
                stats["cost2_states"] += 1
                if synth.func == target_func:
                    return synth, stats
                if synth.func in cheap_functions:
                    continue
                layer2.setdefault((synth.func, first_func), synth)
    if max_cost < 3:
        return None, stats

    # Topology 1: chain, g3=f(g2, base).
    # Topology 2: reconvergent reuse, g3=f(g2, g1).
    for (second_func, first_func), second in layer2.items():
        for atom in atoms:
            for synth in combine_disjoint_variants(second, atom, mask):
                stats["cost3_chain_checks"] += 1
                if synth.func == target_func:
                    return synth, stats
        # In a chain-built cost-2 Synth the first local gate's canonical signal
        # is stored first.  Its reference may carry a free phase.
        first_signal_func, first_signal_ref = second.signals[0]
        if first_signal_func != first_func:
            raise AssertionError("cost-2 semantic-state bookkeeping mismatch")
        for synth in extend_with_existing_variants(
            second, first_signal_func, first_signal_ref, mask
        ):
            stats["cost3_reuse_checks"] += 1
            if synth.func == target_func:
                return synth, stats

    # Topology 3: independent branches, g1=f(base,base),
    # g2=f(base,base), g3=f(g1,g2).
    layer1_items = list(layer1.values())
    for left_index, left in enumerate(layer1_items):
        for right in layer1_items[: left_index + 1]:
            # Identical synthesized branches should be shared and therefore
            # belong to a <=2 gate topology already covered above.
            if synth_signature(left) == synth_signature(right):
                continue
            for synth in combine_disjoint_variants(left, right, mask):
                stats["cost3_branch_checks"] += 1
                if synth.func == target_func:
                    return synth, stats
    return None, stats


def convert_sref(
    ref: SRef, leaves: tuple[Lit, ...], insertion_root: int
) -> Lit:
    if ref.kind == "base":
        leaf = leaves[ref.index]
        return Lit(leaf.kind, leaf.index, leaf.inv ^ ref.inv)
    if ref.kind == "local":
        return Lit("w", insertion_root + ref.index, ref.inv)
    raise AssertionError(f"bad SRef kind: {ref.kind}")


def insert_replacement(
    circuit: Circuit,
    root: int,
    leaves: tuple[Lit, ...],
    synth: Synth,
    target_value: int,
    mask: int,
) -> Circuit:
    if synth.cost < 1:
        raise ValueError("zero-cost synthesis uses the dedicated substitution path")
    target_func, target_is_complement = canonical(target_value, mask)
    if synth.func != target_func:
        raise ValueError("synth function does not match root modulo phase")

    inserted: list[Gate] = []
    for local_index, sgate in enumerate(synth.gates):
        if sgate.op not in ("AND", "XOR"):
            raise AssertionError("unexpected synthesis op")
        a = convert_sref(sgate.a, leaves, root)
        b = convert_sref(sgate.b, leaves, root)
        # At local gate j, only inserted wires w_root..w_(root+j-1)
        # and old wires < root may be referenced.
        validate_lit(a, circuit.ninputs, root + local_index - 1, "synthesis")
        validate_lit(b, circuit.ninputs, root + local_index - 1, "synthesis")
        inserted.append(Gate(sgate.op, a, b))

    replacement_ref = convert_sref(
        synth.out.toggled() if target_is_complement else synth.out,
        leaves,
        root,
    )
    shift = synth.cost - 1

    def remap_old_lit(lit: Lit) -> Lit:
        if lit.kind == "x":
            return lit
        if lit.index < root:
            return lit
        if lit.index == root:
            return Lit(
                replacement_ref.kind,
                replacement_ref.index,
                lit.inv ^ replacement_ref.inv,
            )
        return Lit("w", lit.index + shift, lit.inv)

    prefix = list(circuit.gates[: root - 1])
    suffix = [
        Gate(gate.op, remap_old_lit(gate.a), remap_old_lit(gate.b))
        for gate in circuit.gates[root:]
    ]
    outputs = tuple(remap_old_lit(lit) for lit in circuit.outputs)
    expanded = Circuit(
        circuit.ninputs, tuple(prefix + inserted + suffix), outputs
    )
    return prune_and_compact(expanded)


def search_best_mffc_rewrite(
    circuit: Circuit,
    max_cut_leaves: int,
) -> tuple[Circuit, dict[str, object] | None, dict[str, object]]:
    circuit = prune_and_compact(circuit)
    wire_values, baseline_outputs, mask = evaluate(circuit)
    input_values, _ = input_truth_tables(circuit.ninputs)
    counts = fanout_counts(circuit)
    best = circuit
    best_info: dict[str, object] | None = None
    root_records: list[dict[str, object]] = []
    mffc_hist: Counter[int] = Counter()
    cut_hist: Counter[int] = Counter()
    searched_roots = 0

    for root, target_value in enumerate(wire_values, start=1):
        removed, leaves = mffc_and_cut(circuit, root, counts)
        mffc_size = len(removed)
        cut_size = len(leaves)
        mffc_hist[mffc_size] += 1
        cut_hist[cut_size] += 1
        max_cost = min(3, mffc_size - 1)
        record: dict[str, object] = {
            "root": root,
            "mffc_size": mffc_size,
            "cut_size": cut_size,
            "max_cost": max_cost,
        }
        if max_cost < 1:
            record["status"] = "cannot_save_with_positive_cost"
            root_records.append(record)
            continue
        if cut_size > max_cut_leaves:
            record["status"] = "cut_limit"
            root_records.append(record)
            continue
        searched_roots += 1
        synth, synth_stats = synthesize_up_to_three(
            target_value,
            leaves,
            input_values,
            wire_values,
            mask,
            max_cost,
        )
        record["synth_stats"] = synth_stats
        if synth is None:
            record["status"] = "exhausted_no_match"
            root_records.append(record)
            continue
        if synth.cost == 0:
            # The global zero-gate pass has already proven there are no such
            # matches in these circuits.  Keep this guard for logical clarity.
            record["status"] = "zero_cost_match_deferred"
            root_records.append(record)
            continue
        candidate = insert_replacement(
            circuit, root, leaves, synth, target_value, mask
        )
        _, candidate_outputs, _ = evaluate(candidate)
        if candidate_outputs != baseline_outputs:
            raise AssertionError("MFFC replacement failed full-domain verification")
        saved = len(circuit.gates) - len(candidate.gates)
        if saved < 1:
            raise AssertionError("accepted MFFC synthesis did not save a gate")
        record["status"] = "match"
        record["synth_cost"] = synth.cost
        record["saved_gates"] = saved
        root_records.append(record)
        if len(candidate.gates) < len(best.gates):
            best = candidate
            best_info = {
                "kind": "exact_mffc_cut_replacement",
                "root": f"w{root}",
                "mffc_size": mffc_size,
                "cut_leaves": [lit.text() for lit in leaves],
                "synth_cost": synth.cost,
                "before_gates": len(circuit.gates),
                "after_gates": len(candidate.gates),
                "saved_gates": saved,
            }

    stats: dict[str, object] = {
        "roots": len(circuit.gates),
        "searched_roots": searched_roots,
        "max_cut_leaves": max_cut_leaves,
        "mffc_histogram": dict(sorted(mffc_hist.items())),
        "cut_histogram": dict(sorted(cut_hist.items())),
        "root_records": root_records,
    }
    return best, best_info, stats


def optimize_fixpoint(
    circuit: Circuit, max_cut_leaves: int
) -> tuple[Circuit, list[dict[str, object]], list[dict[str, object]]]:
    current = prune_and_compact(circuit)
    steps: list[dict[str, object]] = []
    rounds: list[dict[str, object]] = []
    while True:
        candidate, info, stats = search_best_mffc_rewrite(
            current, max_cut_leaves
        )
        rounds.append(stats)
        if info is None:
            return current, steps, rounds
        steps.append(info)
        current = candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-cut-leaves", type=int, default=10)
    args = parser.parse_args()
    if args.seed != 42:
        raise ValueError("this deterministic search is preregistered to root seed 42")
    if not 2 <= args.max_cut_leaves <= 16:
        raise ValueError("max cut leaves must be in 2..16")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    for input_path in args.inputs:
        reference = parse_circuit(input_path)
        baseline = prune_and_compact(reference)
        optimized, steps, rounds = optimize_fixpoint(
            baseline, args.max_cut_leaves
        )
        verification = full_domain_verify(reference, optimized)
        if not verification["exact"]:
            raise AssertionError("optimized circuit failed full-domain equivalence")
        output_path = args.out_dir / input_path.name
        output_path.write_text(
            serialize(optimized), encoding="ascii", newline="\n"
        )
        reparsed = parse_circuit(output_path)
        second_verification = full_domain_verify(reference, reparsed)
        if not second_verification["exact"]:
            raise AssertionError("serialized circuit failed exact verification")
        summaries.append(
            {
                "name": input_path.name,
                "seed": args.seed,
                "original_gates": len(reference.gates),
                "initial_live_gates": len(baseline.gates),
                "optimized_gates": len(optimized.gates),
                "saved_gates": len(reference.gates) - len(optimized.gates),
                "steps": steps,
                "rounds": rounds,
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
    # Keep console output concise; the exhaustive per-root audit is in report.
    concise = [
        {
            "name": item["name"],
            "original_gates": item["original_gates"],
            "optimized_gates": item["optimized_gates"],
            "saved_gates": item["saved_gates"],
            "steps": item["steps"],
            "verification": item["verification"],
            "output_path": item["output_path"],
            "report_path": str(report_path),
        }
        for item in summaries
    ]
    print(json.dumps(concise, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
