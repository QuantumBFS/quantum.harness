#!/usr/bin/env python3
"""Minimum-width layered OBDD learning by SAT for issue #71.

For a fixed variable order and one output bit, examples traverse a deterministic
layered branching program.  Binary state variables encode the state reached by
each example, and shared transition variables enforce determinism.  Widths
1,2,4,... are tried in ascending order.  Candidate order selection uses only
training constraints, BDD size, and extracted gate count; revealed semantics
are consulted only after selection for an exhaustive audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from decision_diagram_learn_v2 import (
    BDDManager,
    INSTANCE_SPECS,
    Sample,
    base_orders,
    choose_order,
    compile_bdd,
    evaluate_samples,
    full_domain_audit,
    read_training_csv,
    write_netlist,
)


@dataclass
class SATAttempt:
    width: int
    status: str
    variables: int
    clauses: int
    conflicts: int | None
    decisions: int | None
    elapsed_seconds: float


@dataclass
class SATOutput:
    root: int | None
    width: int | None
    attempts: list[SATAttempt]


class LayeredEncoding:
    def __init__(self, samples: Sequence[Sample], order: Sequence[int], bit: int, k: int):
        self.samples = samples
        self.order = order
        self.output_bit = bit
        self.k = k
        self.width = 1 << k
        self.n_samples = len(samples)
        self.depths = len(order) + 1
        self.b_base = 1
        self.b_count = self.n_samples * self.depths * k
        self.t_base = self.b_base + self.b_count
        self.t_count = len(order) * self.width * 2 * k
        self.o_base = self.t_base + self.t_count
        self.nvars = self.o_base + self.width - 1

    def bvar(self, sample: int, depth: int, bit: int) -> int:
        return self.b_base + ((sample * self.depths + depth) * self.k + bit)

    def tvar(self, depth: int, state: int, branch: int, bit: int) -> int:
        return self.t_base + ((((depth * self.width + state) * 2 + branch) * self.k) + bit)

    def ovar(self, state: int) -> int:
        return self.o_base + state

    def mismatch(self, sample: int, depth: int, state: int) -> list[int]:
        result = []
        for bit in range(self.k):
            variable = self.bvar(sample, depth, bit)
            result.append(-variable if ((state >> bit) & 1) else variable)
        return result

    def add_to_solver(self, solver: object) -> int:
        clauses = 0

        def add(clause: list[int]) -> None:
            nonlocal clauses
            solver.add_clause(clause)
            clauses += 1

        # Every example begins at state zero.
        for sample in range(self.n_samples):
            for bit in range(self.k):
                add([-self.bvar(sample, 0, bit)])

        # State names are independently permutable at every layer.  Pinning one
        # example to zero at each layer is a sound symmetry break.
        for depth in range(1, self.depths):
            for bit in range(self.k):
                add([-self.bvar(0, depth, bit)])

        # If an example is in q, its next-state bits equal the shared transition
        # delta[depth,q,input].  Two clauses encode each conditional equivalence.
        for sample_id, sample in enumerate(self.samples):
            for depth, variable_index in enumerate(self.order):
                branch = sample.bits[variable_index]
                for state in range(self.width):
                    prefix = self.mismatch(sample_id, depth, state)
                    for bit in range(self.k):
                        nxt = self.bvar(sample_id, depth + 1, bit)
                        transition = self.tvar(depth, state, branch, bit)
                        add(prefix + [-nxt, transition])
                        add(prefix + [nxt, -transition])

        last = self.depths - 1
        for sample_id, sample in enumerate(self.samples):
            label = sample.output[self.output_bit]
            for state in range(self.width):
                clause = self.mismatch(sample_id, last, state)
                clause.append(self.ovar(state) if label else -self.ovar(state))
                add(clause)
        return clauses

    def decode(
        self,
        model: Sequence[int],
        manager: BDDManager,
    ) -> int:
        positive = {literal for literal in model if literal > 0}
        transitions: dict[tuple[int, int, int], int] = {}
        for depth in range(len(self.order)):
            for state in range(self.width):
                for branch in (0, 1):
                    nxt = 0
                    for bit in range(self.k):
                        if self.tvar(depth, state, branch, bit) in positive:
                            nxt |= 1 << bit
                    transitions[depth, state, branch] = nxt
        labels = [int(self.ovar(state) in positive) for state in range(self.width)]
        memo: dict[tuple[int, int], int] = {}

        def build(depth: int, state: int) -> int:
            key = (depth, state)
            old = memo.get(key)
            if old is not None:
                return old
            if depth == len(self.order):
                result = labels[state]
            else:
                low = build(depth + 1, transitions[depth, state, 0])
                high = build(depth + 1, transitions[depth, state, 1])
                result = manager.intern(self.order[depth], low, high)
            memo[key] = result
            return result

        return build(0, 0)


def _solver_stats(solver: object) -> tuple[int | None, int | None]:
    try:
        stats = solver.accum_stats()
    except Exception:
        return None, None
    return stats.get("conflicts"), stats.get("decisions")


def learn_output(
    samples: Sequence[Sample],
    order: Sequence[int],
    output_bit: int,
    manager: BDDManager,
    *,
    max_width: int,
    conflict_budget: int,
    solver_name: str,
) -> SATOutput:
    labels = {sample.output[output_bit] for sample in samples}
    if len(labels) == 1:
        return SATOutput(next(iter(labels)), 1, [])
    attempts: list[SATAttempt] = []
    max_k = int(math.log2(max_width))
    if (1 << max_k) != max_width:
        raise ValueError("max_width must be a power of two")

    from pysat.solvers import Solver

    for k in range(1, max_k + 1):
        encoding = LayeredEncoding(samples, order, output_bit, k)
        started = time.monotonic()
        with Solver(name=solver_name) as solver:
            clauses = encoding.add_to_solver(solver)
            if conflict_budget > 0:
                solver.conf_budget(conflict_budget)
                status = solver.solve_limited(expect_interrupt=True)
            else:
                status = solver.solve()
            conflicts, decisions = _solver_stats(solver)
            elapsed = time.monotonic() - started
            attempts.append(
                SATAttempt(
                    encoding.width,
                    "SAT" if status is True else "UNSAT" if status is False else "UNKNOWN",
                    encoding.nvars,
                    clauses,
                    conflicts,
                    decisions,
                    elapsed,
                )
            )
            print(
                f"[sat] bit={output_bit} width={encoding.width} "
                f"status={attempts[-1].status} vars={encoding.nvars} "
                f"clauses={clauses} conflicts={conflicts} elapsed={elapsed:.3f}s",
                flush=True,
            )
            if status is True:
                model = solver.get_model()
                if model is None:
                    raise AssertionError("SAT solver returned no model")
                root = encoding.decode(model, manager)
                one_bit_samples = [
                    Sample(sample.bits, (sample.output[output_bit],)) for sample in samples
                ]
                if evaluate_samples(manager, [root], one_bit_samples)[0] != len(samples):
                    raise AssertionError("decoded SAT OBDD violates training data")
                return SATOutput(root, encoding.width, attempts)
    return SATOutput(None, None, attempts)


def learn_order(
    samples: Sequence[Sample],
    order: Sequence[int],
    *,
    max_width: int,
    conflict_budget: int,
    solver_name: str,
) -> tuple[BDDManager, list[int], list[SATOutput]]:
    manager = BDDManager()
    roots: list[int] = []
    outputs: list[SATOutput] = []
    for output_bit in range(len(samples[0].output)):
        print(f"[output] bit={output_bit}", flush=True)
        result = learn_output(
            samples,
            order,
            output_bit,
            manager,
            max_width=max_width,
            conflict_budget=conflict_budget,
            solver_name=solver_name,
        )
        outputs.append(result)
        if result.root is None:
            break
        roots.append(result.root)
    return manager, roots, outputs


def attempt_to_json(attempt: SATAttempt) -> dict[str, object]:
    return {
        "width": attempt.width,
        "status": attempt.status,
        "variables": attempt.variables,
        "clauses": attempt.clauses,
        "conflicts": attempt.conflicts,
        "decisions": attempt.decisions,
        "elapsed_seconds": attempt.elapsed_seconds,
    }


def order_objective(
    solved: int,
    widths: Sequence[int],
    nodes: int,
    gates: int,
) -> tuple[int, int, int, int]:
    return (solved, -sum(widths), -nodes, -gates)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--instance", choices=sorted(INSTANCE_SPECS), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-width", type=int, default=16)
    parser.add_argument("--conflict-budget", type=int, default=2_000_000)
    parser.add_argument("--solver", default="cadical195")
    parser.add_argument("--sift-variables", type=int, default=6)
    parser.add_argument("--adjacent-passes", type=int, default=2)
    args = parser.parse_args(argv)

    kind, n, m = INSTANCE_SPECS[args.instance]
    training_path = args.dataset_root / args.instance / "train.csv"
    samples = read_training_csv(training_path, 2 * n, m)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    # Sifting and adjacent swaps operate on a seed-42 train-only holdout score.
    # Its final order joins the three named base orders as a fourth SAT candidate.
    sifted, heuristic_selection = choose_order(
        samples,
        n,
        seed=args.seed,
        validation_fraction=0.2,
        sift_variables=args.sift_variables,
        adjacent_passes=args.adjacent_passes,
        progress=False,
    )
    candidates = base_orders(n)
    candidates["seed42_sift_adjacent"] = sifted
    unique_candidates: list[tuple[str, list[int]]] = []
    seen: set[tuple[int, ...]] = set()
    for name, order in candidates.items():
        key = tuple(order)
        if key not in seen:
            seen.add(key)
            unique_candidates.append((name, order))

    candidate_reports: list[dict[str, object]] = []
    successful: list[
        tuple[tuple[int, int, int, int], str, list[int], BDDManager, list[int]]
    ] = []
    for name, order in unique_candidates:
        print(f"[candidate] name={name} order={order}", flush=True)
        candidate_start = time.monotonic()
        manager, roots, sat_outputs = learn_order(
            samples,
            order,
            max_width=args.max_width,
            conflict_budget=args.conflict_budget,
            solver_name=args.solver,
        )
        solved = len(roots)
        widths = [output.width for output in sat_outputs if output.width is not None]
        nodes = len(manager.reachable(roots))
        gates = -1
        netlist_path: str | None = None
        if solved == m:
            train_exact, _ = evaluate_samples(manager, roots, samples)
            if train_exact != len(samples):
                raise AssertionError("combined SAT BDD violates training data")
            builder, output_signals = compile_bdd(manager, roots, 2 * n)
            gates = len(builder.lines)
            candidate_netlist = args.output_dir / f"{args.instance}.{name}.sat-bdd.txt"
            write_netlist(
                candidate_netlist,
                builder,
                output_signals,
                metadata=[
                    "minimum-width layered OBDD learned by SAT from train.csv only",
                    f"instance={args.instance} seed={args.seed} order_name={name}",
                    "order_zero_based=" + ",".join(map(str, order)),
                ],
            )
            netlist_path = str(candidate_netlist)
            successful.append(
                (
                    order_objective(solved, widths, nodes, gates),
                    name,
                    order,
                    manager,
                    roots,
                )
            )
        report = {
            "name": name,
            "order": order,
            "solved_outputs": solved,
            "widths": widths,
            "nodes": nodes,
            "gates": gates,
            "netlist": netlist_path,
            "output_attempts": [
                {
                    "root": output.root,
                    "width": output.width,
                    "attempts": [attempt_to_json(attempt) for attempt in output.attempts],
                }
                for output in sat_outputs
            ],
            "elapsed_seconds": time.monotonic() - candidate_start,
        }
        candidate_reports.append(report)
        (args.output_dir / f"{args.instance}.{name}.sat-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", "ascii"
        )

    if not successful:
        summary = {
            "schema": "occam71-sat-bdd-v1",
            "instance": args.instance,
            "status": "NO_COMPLETE_CANDIDATE_WITHIN_WIDTH_OR_BUDGET",
            "seed": args.seed,
            "max_width": args.max_width,
            "conflict_budget": args.conflict_budget,
            "solver": args.solver,
            "heuristic_order_selection": heuristic_selection,
            "candidates": candidate_reports,
            "elapsed_seconds": time.monotonic() - started,
            "training_sha256": hashlib.sha256(training_path.read_bytes()).hexdigest(),
        }
        (args.output_dir / f"{args.instance}.sat-bdd-summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", "ascii"
        )
        print(f"[done] {summary['status']}", flush=True)
        return 3

    objective, selected_name, selected_order, manager, roots = max(
        successful, key=lambda item: item[0]
    )
    builder, output_signals = compile_bdd(manager, roots, 2 * n)
    selected_netlist = args.output_dir / f"{args.instance}.selected.sat-bdd.txt"
    write_netlist(
        selected_netlist,
        builder,
        output_signals,
        metadata=[
            "training-only selected minimum-width layered OBDD",
            f"instance={args.instance} seed={args.seed} order_name={selected_name}",
            "order_zero_based=" + ",".join(map(str, selected_order)),
        ],
    )
    train_rows, train_bits = evaluate_samples(manager, roots, samples)
    audit = full_domain_audit(manager, roots, kind=kind, n=n, m=m)
    summary = {
        "schema": "occam71-sat-bdd-v1",
        "instance": args.instance,
        "status": "COMPLETE_CANDIDATE",
        "seed": args.seed,
        "max_width": args.max_width,
        "conflict_budget": args.conflict_budget,
        "solver": args.solver,
        "training_rows": len(samples),
        "training_exact_rows": train_rows,
        "training_correct_bits": train_bits,
        "training_sha256": hashlib.sha256(training_path.read_bytes()).hexdigest(),
        "heuristic_order_selection": heuristic_selection,
        "candidates": candidate_reports,
        "selected_order_name": selected_name,
        "selected_order": selected_order,
        "selection_objective": list(objective),
        "selected_nodes": len(manager.reachable(roots)),
        "selected_gates": len(builder.lines),
        "selected_netlist": str(selected_netlist),
        "full_domain_audit_after_selection": audit,
        "elapsed_seconds": time.monotonic() - started,
    }
    summary_path = args.output_dir / f"{args.instance}.sat-bdd-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", "ascii")
    print(
        f"[done] selected={selected_name} train={train_rows}/{len(samples)} "
        f"full={audit['exact_rows']}/{audit['total_rows']} "
        f"nodes={summary['selected_nodes']} gates={summary['selected_gates']}",
        flush=True,
    )
    print(f"[artifact] {selected_netlist}", flush=True)
    print(f"[artifact] {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
