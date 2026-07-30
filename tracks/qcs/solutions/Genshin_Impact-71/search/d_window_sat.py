#!/usr/bin/env python3
"""Exact reachable-relation synthesis for two-root windows in mystery-D.

This script consumes only the plain challenge netlist.  It uses PySAT as a CNF
engine, but builds and audits the circuit semantics independently with complete
1024-row truth tables.  The synthesis model permits every challenge gate,
arbitrary free input/output inversions, arbitrary acyclic topology, and
same-source fanins (so constants/projections are not accidentally excluded).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from pysat.solvers import Solver


SEED = 42
MODULE_PATH = Path(r"C:\tmp\occam71_d_window\window_search.py")


def load_base_module():
    spec = importlib.util.spec_from_file_location("dws_exact_base", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dws = load_base_module()


def truth_id(op: str, left_inv: bool, right_inv: bool) -> int:
    result = 0
    for a in (0, 1):
        for b in (0, 1):
            aa = a ^ left_inv
            bb = b ^ right_inv
            if op == "AND":
                out = aa & bb
            elif op == "OR":
                out = aa | bb
            elif op == "XOR":
                out = aa ^ bb
            elif op == "NAND":
                out = 1 ^ (aa & bb)
            elif op == "NOR":
                out = 1 ^ (aa | bb)
            elif op == "XNOR":
                out = 1 ^ (aa ^ bb)
            else:
                raise AssertionError(op)
            result |= out << ((a << 1) | b)
    return result


def gate_library() -> tuple[list[int], dict[int, tuple[str, bool, bool]]]:
    mapping: dict[int, tuple[str, bool, bool]] = {}
    preference = ["AND", "XOR", "OR", "NAND", "NOR", "XNOR"]
    for op in preference:
        for left_inv in (False, True):
            for right_inv in (False, True):
                table = truth_id(op, left_inv, right_inv)
                depends_left = (
                    ((table >> 0) & 1) != ((table >> 2) & 1)
                    or ((table >> 1) & 1) != ((table >> 3) & 1)
                )
                depends_right = (
                    ((table >> 0) & 1) != ((table >> 1) & 1)
                    or ((table >> 2) & 1) != ((table >> 3) & 1)
                )
                if depends_left and depends_right and table not in mapping:
                    mapping[table] = (op, left_inv, right_inv)
    if len(mapping) != 10:
        raise AssertionError(f"expected 10 essential binary functions, got {mapping}")
    return sorted(mapping), mapping


TABLES, TABLE_TO_GATE = gate_library()


class Pool:
    def __init__(self) -> None:
        self.top = 0

    def one(self) -> int:
        self.top += 1
        return self.top

    def many(self, count: int) -> list[int]:
        return [self.one() for _ in range(count)]


def exactly_one(clauses: list[list[int]], variables: Sequence[int]) -> None:
    if not variables:
        clauses.append([])
        return
    clauses.append(list(variables))
    for i, left in enumerate(variables):
        for right in variables[i + 1 :]:
            clauses.append([-left, -right])


def force_selected_mux(
    clauses: list[list[int]],
    selector: int,
    mux: int,
    source: int | bool,
) -> None:
    if isinstance(source, bool):
        clauses.append([-selector, mux if source else -mux])
    else:
        clauses.append([-selector, -source, mux])
        clauses.append([-selector, source, -mux])


@dataclass
class Encoding:
    clauses: list[list[int]]
    pool: Pool
    source_left: list[list[int]]
    source_right: list[list[int]]
    operations: list[list[int]]
    gate_values: list[list[int]]
    output_source: list[list[int]]
    output_invert: list[int]
    boundary_count: int
    examples: list[tuple[tuple[int, ...], tuple[int, ...]]]


def encode_exact(
    examples: list[tuple[tuple[int, ...], tuple[int, ...]]],
    gate_count: int,
) -> Encoding:
    boundary_count = len(examples[0][0])
    output_count = len(examples[0][1])
    row_count = len(examples)
    pool = Pool()
    clauses: list[list[int]] = []

    gate_values = [pool.many(row_count) for _ in range(gate_count)]
    source_left: list[list[int]] = []
    source_right: list[list[int]] = []
    operations: list[list[int]] = []

    for gate_index in range(gate_count):
        source_count = boundary_count + gate_index
        left_sel = pool.many(source_count)
        right_sel = pool.many(source_count)
        op_sel = pool.many(len(TABLES))
        source_left.append(left_sel)
        source_right.append(right_sel)
        operations.append(op_sel)
        exactly_one(clauses, left_sel)
        exactly_one(clauses, right_sel)
        exactly_one(clauses, op_sel)

        # The operation library is closed under swapping inputs, so left <= right
        # is a complete symmetry break. Equality deliberately remains possible.
        for left_index, left_var in enumerate(left_sel):
            for right_index, right_var in enumerate(right_sel):
                if left_index > right_index:
                    clauses.append([-left_var, -right_var])

        for row_index, (boundary_bits, _) in enumerate(examples):
            mux_left = pool.one()
            mux_right = pool.one()
            out_var = gate_values[gate_index][row_index]
            for source_index, selector in enumerate(left_sel):
                source: int | bool
                if source_index < boundary_count:
                    source = bool(boundary_bits[source_index])
                else:
                    source = gate_values[source_index - boundary_count][row_index]
                force_selected_mux(clauses, selector, mux_left, source)
            for source_index, selector in enumerate(right_sel):
                if source_index < boundary_count:
                    source = bool(boundary_bits[source_index])
                else:
                    source = gate_values[source_index - boundary_count][row_index]
                force_selected_mux(clauses, selector, mux_right, source)

            for operation_index, table in enumerate(TABLES):
                op_var = op_sel[operation_index]
                for a in (0, 1):
                    for b in (0, 1):
                        value = (table >> ((a << 1) | b)) & 1
                        # op ∧ (L=a) ∧ (R=b) → (out=value)
                        clause = [
                            -op_var,
                            mux_left if a == 0 else -mux_left,
                            mux_right if b == 0 else -mux_right,
                            out_var if value else -out_var,
                        ]
                        clauses.append(clause)

    output_source: list[list[int]] = []
    output_invert = pool.many(output_count)
    total_sources = boundary_count + gate_count
    for output_index in range(output_count):
        selectors = pool.many(total_sources)
        output_source.append(selectors)
        exactly_one(clauses, selectors)
        invert = output_invert[output_index]
        for row_index, (boundary_bits, target_bits) in enumerate(examples):
            target = target_bits[output_index]
            for source_index, selector in enumerate(selectors):
                if source_index < boundary_count:
                    source_const = boundary_bits[source_index]
                    required_inv = source_const ^ target
                    clauses.append(
                        [-selector, invert if required_inv else -invert]
                    )
                    continue
                source_var = gate_values[source_index - boundary_count][row_index]
                # selector → (source XOR invert = target)
                for source_value in (0, 1):
                    for invert_value in (0, 1):
                        if (source_value ^ invert_value) == target:
                            continue
                        clauses.append(
                            [
                                -selector,
                                source_var if source_value == 0 else -source_var,
                                invert if invert_value == 0 else -invert,
                            ]
                        )

    # In a topological order of an irredundant circuit, the last gate is an
    # output. This removes pure trailing padding without excluding any solution.
    last_source = boundary_count + gate_count - 1
    clauses.append(
        [output_source[index][last_source] for index in range(output_count)]
    )
    return Encoding(
        clauses,
        pool,
        source_left,
        source_right,
        operations,
        gate_values,
        output_source,
        output_invert,
        boundary_count,
        examples,
    )


def model_bool(model_set: set[int], variable: int) -> bool:
    return variable in model_set


def selected(model_set: set[int], variables: Sequence[int]) -> int:
    choices = [index for index, var in enumerate(variables) if var in model_set]
    if len(choices) != 1:
        raise AssertionError(f"not one-hot in model: {choices}")
    return choices[0]


@dataclass(frozen=True)
class SynthGate:
    out: str
    op: str
    left: object
    right: object


def decode(
    encoding: Encoding,
    model: Sequence[int],
    boundary_names: Sequence[str],
    root_names: Sequence[str],
):
    model_set = {literal for literal in model if literal > 0}
    new_names = [f"q{index + 1}" for index in range(len(encoding.source_left))]
    sources = list(boundary_names)
    gates = []
    for gate_index in range(len(encoding.source_left)):
        left_index = selected(model_set, encoding.source_left[gate_index])
        right_index = selected(model_set, encoding.source_right[gate_index])
        operation_index = selected(model_set, encoding.operations[gate_index])
        table = TABLES[operation_index]
        op, left_inv, right_inv = TABLE_TO_GATE[table]
        left_name = sources[left_index]
        right_name = sources[right_index]
        gates.append(
            dws.Gate(
                new_names[gate_index],
                op,
                dws.Token(left_name, left_inv),
                dws.Token(right_name, right_inv),
            )
        )
        sources.append(new_names[gate_index])
    replacements = {}
    for output_index, root in enumerate(root_names):
        source_index = selected(model_set, encoding.output_source[output_index])
        replacements[root] = dws.Token(
            sources[source_index],
            model_bool(model_set, encoding.output_invert[output_index]),
        )
    return gates, replacements


def token_rewrite(token, replacements):
    replacement = replacements.get(token.name)
    if replacement is None:
        return token
    return dws.Token(replacement.name, token.inv ^ replacement.inv)


def splice(
    circuit,
    roots: Sequence[str],
    new_gates,
    replacements,
):
    removed, descendants = dws.removable_closure(circuit, roots)
    gate_index = {gate.out: index for index, gate in enumerate(circuit.gates)}
    boundary = set()
    gate_by_out, _ = dws.structural_maps(circuit)
    for name in removed:
        gate = gate_by_out[name]
        for token in (gate.left, gate.right):
            if token.name not in removed:
                boundary.add(token.name)
    insert_after = max(
        (gate_index[name] for name in boundary if name in gate_index),
        default=-1,
    )
    combined = []
    inserted = False
    for index, gate in enumerate(circuit.gates):
        if not inserted and index > insert_after:
            combined.extend(new_gates)
            inserted = True
        if gate.out in removed:
            continue
        left = token_rewrite(gate.left, replacements)
        right = token_rewrite(gate.right, replacements)
        if left.name in removed or right.name in removed:
            raise AssertionError(
                f"non-root removed gate still referenced: {gate.out} "
                f"{left.text()} {right.text()}"
            )
        combined.append(dws.Gate(gate.out, gate.op, left, right))
    if not inserted:
        combined.extend(new_gates)
    outputs = [token_rewrite(token, replacements) for token in circuit.outputs]

    # Exact dead-code elimination, then deterministic topological renumbering.
    by_out = {gate.out: gate for gate in combined}
    needed = set()
    todo = [token.name for token in outputs]
    while todo:
        name = todo.pop()
        gate = by_out.get(name)
        if gate is None or name in needed:
            continue
        needed.add(name)
        todo.extend((gate.left.name, gate.right.name))
    live = [gate for gate in combined if gate.out in needed]

    rename = {}
    renumbered = []
    for index, gate in enumerate(live, start=1):
        left = dws.Token(rename.get(gate.left.name, gate.left.name), gate.left.inv)
        right = dws.Token(rename.get(gate.right.name, gate.right.name), gate.right.inv)
        out = f"w{index}"
        rename[gate.out] = out
        renumbered.append(dws.Gate(out, gate.op, left, right))
    new_outputs = [
        dws.Token(rename.get(token.name, token.name), token.inv) for token in outputs
    ]
    return dws.Circuit(circuit.n_inputs, renumbered, new_outputs), removed


def serialize(circuit) -> str:
    lines = [f"INPUTS {circuit.n_inputs}"]
    for gate in circuit.gates:
        lines.append(
            f"{gate.out} = {gate.op} {gate.left.text()} {gate.right.text()}"
        )
    lines.append("OUTPUTS " + " ".join(token.text() for token in circuit.outputs))
    return "\n".join(lines) + "\n"


def reachable_examples(circuit, values, roots, removed):
    gate_by_out, _ = dws.structural_maps(circuit)
    boundary = set()
    for name in removed:
        gate = gate_by_out[name]
        for token in (gate.left, gate.right):
            if token.name not in removed:
                boundary.add(token.name)
    gate_index = {gate.out: index for index, gate in enumerate(circuit.gates)}
    boundary_names = sorted(
        boundary,
        key=lambda name: (
            0 if name.startswith("x") else 1,
            int(name[1:]),
        ),
    )
    relation = {}
    for row in range(1 << circuit.n_inputs):
        key = tuple((values[name] >> row) & 1 for name in boundary_names)
        target = tuple((values[name] >> row) & 1 for name in roots)
        prior = relation.setdefault(key, target)
        if prior != target:
            raise AssertionError("window roots are not functions of boundary")
    return boundary_names, sorted(relation.items())


def solve_with_timeout(
    encoding: Encoding,
    timeout_seconds: float,
    solver_preference: Sequence[str],
):
    last_error = None
    solver = None
    chosen = None
    for name in solver_preference:
        try:
            solver = Solver(name=name, bootstrap_with=encoding.clauses)
            chosen = name
            break
        except Exception as exc:
            last_error = repr(exc)
    if solver is None:
        raise RuntimeError(f"no SAT solver available; last error {last_error}")
    try:
        try:
            solver.configure({"seed": SEED})
        except Exception:
            pass
        timer = threading.Timer(timeout_seconds, solver.interrupt)
        timer.daemon = True
        timer.start()
        started = time.monotonic()
        try:
            result = solver.solve_limited(expect_interrupt=True)
        finally:
            elapsed = time.monotonic() - started
            timer.cancel()
        model = solver.get_model() if result is True else None
        stats = solver.accum_stats()
        return result, model, chosen, elapsed, stats
    finally:
        solver.delete()


def exhaustive_compare(reference, candidate):
    _, _, expected = dws.evaluate(reference)
    _, _, actual = dws.evaluate(candidate)
    failures = []
    for row in range(1 << reference.n_inputs):
        for output_index, (left, right) in enumerate(zip(expected, actual)):
            if ((left ^ right) >> row) & 1:
                failures.append((row, output_index))
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("netlist", type=Path)
    parser.add_argument("--roots", nargs=2, required=True)
    parser.add_argument("--gates", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.timeout <= 0 or args.timeout > 540:
        raise ValueError("local pilot timeout must be in (0, 540] seconds")
    random.seed(SEED)
    started_all = time.monotonic()

    circuit = dws.parse_circuit(args.netlist)
    mask, values, original_outputs = dws.evaluate(circuit)
    root_names = tuple(args.roots)
    for root in root_names:
        if root not in {gate.out for gate in circuit.gates}:
            raise ValueError(f"unknown root {root}")
    removed, descendants = dws.removable_closure(circuit, root_names)
    boundary_names, examples = reachable_examples(
        circuit, values, root_names, removed
    )
    print(
        json.dumps(
            {
                "event": "encoding",
                "roots": root_names,
                "removed_gates": len(removed),
                "candidate_gates": args.gates,
                "boundary": boundary_names,
                "reachable_patterns": len(examples),
                "seed": SEED,
            }
        ),
        flush=True,
    )
    encoding_started = time.monotonic()
    encoding = encode_exact(examples, args.gates)
    encoding_elapsed = time.monotonic() - encoding_started
    print(
        json.dumps(
            {
                "event": "cnf",
                "variables": encoding.pool.top,
                "clauses": len(encoding.clauses),
                "encoding_seconds": encoding_elapsed,
            }
        ),
        flush=True,
    )
    result, model, solver_name, solve_elapsed, stats = solve_with_timeout(
        encoding,
        args.timeout,
        ("cadical195", "cadical153", "glucose42", "minisat22"),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "netlist_sha256": hashlib.sha256(args.netlist.read_bytes()).hexdigest(),
        "roots": list(root_names),
        "removed_gates": sorted(
            removed, key=lambda name: int(name[1:])
        ),
        "removed_gate_count": len(removed),
        "requested_gate_count": args.gates,
        "boundary": boundary_names,
        "reachable_patterns": len(examples),
        "full_input_rows": 1 << circuit.n_inputs,
        "full_output_bits_checked": (1 << circuit.n_inputs)
        * len(circuit.outputs),
        "seed": SEED,
        "solver": solver_name,
        "sat_result": result,
        "variables": encoding.pool.top,
        "clauses": len(encoding.clauses),
        "encoding_seconds": encoding_elapsed,
        "solve_seconds": solve_elapsed,
        "solver_stats": stats,
    }

    if result is True and model is not None:
        new_gates, replacements = decode(
            encoding, model, boundary_names, root_names
        )
        candidate, removed_again = splice(
            circuit, root_names, new_gates, replacements
        )
        failures = exhaustive_compare(circuit, candidate)
        candidate_path = args.output_dir / "mystery-D.candidate.txt"
        candidate_path.write_text(serialize(candidate), encoding="utf-8")
        report.update(
            {
                "status": "SAT_VALID" if not failures else "SAT_INVALID",
                "candidate_gate_count": len(candidate.gates),
                "gate_saving": len(circuit.gates) - len(candidate.gates),
                "replacement_gates": [
                    {
                        "out": gate.out,
                        "op": gate.op,
                        "left": gate.left.text(),
                        "right": gate.right.text(),
                    }
                    for gate in new_gates
                ],
                "replacement_outputs": {
                    root: token.text() for root, token in replacements.items()
                },
                "exhaustive_failure_count": len(failures),
                "first_failures": failures[:20],
                "candidate_sha256": hashlib.sha256(
                    candidate_path.read_bytes()
                ).hexdigest(),
                "candidate_path": str(candidate_path),
            }
        )
        if failures:
            raise AssertionError(f"candidate failed exhaustive audit: {failures[:5]}")
    elif result is False:
        report["status"] = "UNSAT"
        report["completeness"] = (
            "No acyclic circuit with the requested number of arbitrary allowed "
            "two-input gates (including same-source fanins), free inversions, "
            "this fixed boundary, and these two roots realizes the full "
            "reachable boundary relation."
        )
    else:
        report["status"] = "TIMEOUT"

    report["total_seconds"] = time.monotonic() - started_all
    report_path = args.output_dir / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
