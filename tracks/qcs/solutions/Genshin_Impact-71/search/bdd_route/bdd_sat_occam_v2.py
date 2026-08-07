#!/usr/bin/env python3
"""Lexicographic Occam refinement for SAT-learned layered OBDDs.

Stage 1 finds the smallest power-of-two width consistent with the samples.
Stage 2 uses weighted MaxSAT to minimize the number of reachable states over
all layers, including transitions on unobserved branches.  This explicitly
implements the challenge's simplicity bias instead of accepting an arbitrary
SAT completion.
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

from bdd_sat_refine import LayeredEncoding, SATAttempt, attempt_to_json
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


class _WCNFAdapter:
    def __init__(self, formula: object) -> None:
        self.formula = formula

    def add_clause(self, clause: list[int]) -> None:
        self.formula.append(clause)


class ReachableEncoding(LayeredEncoding):
    def __init__(self, samples: Sequence[Sample], order: Sequence[int], bit: int, k: int):
        super().__init__(samples, order, bit, k)
        self.r_base = self.nvars + 1
        self.r_count = self.depths * self.width
        self.nvars = self.r_base + self.r_count - 1

    def rvar(self, depth: int, state: int) -> int:
        return self.r_base + depth * self.width + state

    def make_wcnf(self) -> tuple[object, int, int]:
        from pysat.formula import WCNF

        formula = WCNF()
        base_clauses = self.add_to_solver(_WCNFAdapter(formula))
        hard_clauses = base_clauses

        def hard(clause: list[int]) -> None:
            nonlocal hard_clauses
            formula.append(clause)
            hard_clauses += 1

        hard([self.rvar(0, 0)])

        # Every state actually used by an example is reachable.
        for sample_id in range(self.n_samples):
            for depth in range(self.depths):
                for state in range(self.width):
                    hard(self.mismatch(sample_id, depth, state) + [self.rvar(depth, state)])

        # Both branches of every reachable state count toward the completed
        # total function, even when the training sample omitted that branch.
        for depth in range(len(self.order)):
            for state in range(self.width):
                for branch in (0, 1):
                    for nxt in range(self.width):
                        transition_mismatch = []
                        for bit in range(self.k):
                            variable = self.tvar(depth, state, branch, bit)
                            transition_mismatch.append(
                                -variable if ((nxt >> bit) & 1) else variable
                            )
                        hard(
                            [-self.rvar(depth, state)]
                            + transition_mismatch
                            + [self.rvar(depth + 1, nxt)]
                        )

        # Unit-weight soft clauses exactly minimize sum_d |reachable states_d|.
        for depth in range(self.depths):
            for state in range(self.width):
                formula.append([-self.rvar(depth, state)], weight=1)
        return formula, hard_clauses, self.depths * self.width


@dataclass
class OccamOutput:
    root: int | None
    width: int | None
    reachable_state_cost: int | None
    attempts: list[SATAttempt]
    maxsat_elapsed_seconds: float | None


def _stats(solver: object) -> tuple[int | None, int | None]:
    try:
        values = solver.accum_stats()
    except Exception:
        return None, None
    return values.get("conflicts"), values.get("decisions")


def learn_occam_output(
    samples: Sequence[Sample],
    order: Sequence[int],
    output_bit: int,
    manager: BDDManager,
    *,
    max_width: int,
    conflict_budget: int,
    solver_name: str,
) -> OccamOutput:
    labels = {sample.output[output_bit] for sample in samples}
    if len(labels) == 1:
        # One terminal state is reachable at every conceptual layer, but the
        # reduced BDD contains no internal node.
        return OccamOutput(next(iter(labels)), 1, len(order) + 1, [], 0.0)

    from pysat.examples.rc2 import RC2
    from pysat.solvers import Solver

    attempts: list[SATAttempt] = []
    max_k = int(math.log2(max_width))
    if 1 << max_k != max_width:
        raise ValueError("max_width must be a power of two")
    chosen_k: int | None = None
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
            conflicts, decisions = _stats(solver)
        elapsed = time.monotonic() - started
        attempt = SATAttempt(
            encoding.width,
            "SAT" if status is True else "UNSAT" if status is False else "UNKNOWN",
            encoding.nvars,
            clauses,
            conflicts,
            decisions,
            elapsed,
        )
        attempts.append(attempt)
        print(
            f"[feasible] bit={output_bit} width={encoding.width} "
            f"status={attempt.status} conflicts={conflicts} elapsed={elapsed:.3f}s",
            flush=True,
        )
        if status is True:
            chosen_k = k
            break
    if chosen_k is None:
        return OccamOutput(None, None, None, attempts, None)

    encoding = ReachableEncoding(samples, order, output_bit, chosen_k)
    formula, hard_clauses, soft_clauses = encoding.make_wcnf()
    started = time.monotonic()
    with RC2(
        formula,
        solver=solver_name,
        adapt=True,
        exhaust=True,
        incr=False,
        minz=True,
        trim=0,
        verbose=0,
    ) as optimizer:
        model = optimizer.compute()
        cost = optimizer.cost
    elapsed = time.monotonic() - started
    print(
        f"[maxsat] bit={output_bit} width={encoding.width} cost={cost} "
        f"hard={hard_clauses} soft={soft_clauses} elapsed={elapsed:.3f}s",
        flush=True,
    )
    if model is None:
        return OccamOutput(None, encoding.width, None, attempts, elapsed)
    root = encoding.decode(model, manager)
    one_bit_samples = [
        Sample(sample.bits, (sample.output[output_bit],)) for sample in samples
    ]
    if evaluate_samples(manager, [root], one_bit_samples)[0] != len(samples):
        raise AssertionError("MaxSAT decoded OBDD violates training data")
    return OccamOutput(root, encoding.width, int(cost), attempts, elapsed)


def learn_occam_order(
    samples: Sequence[Sample],
    order: Sequence[int],
    *,
    max_width: int,
    conflict_budget: int,
    solver_name: str,
) -> tuple[BDDManager, list[int], list[OccamOutput]]:
    manager = BDDManager()
    roots: list[int] = []
    results: list[OccamOutput] = []
    for bit in range(len(samples[0].output)):
        print(f"[output] bit={bit}", flush=True)
        result = learn_occam_output(
            samples,
            order,
            bit,
            manager,
            max_width=max_width,
            conflict_budget=conflict_budget,
            solver_name=solver_name,
        )
        results.append(result)
        if result.root is None:
            break
        roots.append(result.root)
    return manager, roots, results


def objective(
    solved: int,
    state_costs: Sequence[int],
    widths: Sequence[int],
    nodes: int,
    gates: int,
) -> tuple[int, int, int, int, int]:
    return (solved, -sum(state_costs), -sum(widths), -nodes, -gates)


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

    sifted, heuristic_selection = choose_order(
        samples,
        n,
        seed=args.seed,
        validation_fraction=0.2,
        sift_variables=args.sift_variables,
        adjacent_passes=args.adjacent_passes,
        progress=False,
    )
    orders = base_orders(n)
    orders["seed42_sift_adjacent"] = sifted
    candidates = []
    seen: set[tuple[int, ...]] = set()
    for name, order in orders.items():
        if tuple(order) not in seen:
            seen.add(tuple(order))
            candidates.append((name, order))

    reports: list[dict[str, object]] = []
    successful = []
    for name, order in candidates:
        print(f"[candidate] name={name} order={order}", flush=True)
        candidate_started = time.monotonic()
        manager, roots, output_results = learn_occam_order(
            samples,
            order,
            max_width=args.max_width,
            conflict_budget=args.conflict_budget,
            solver_name=args.solver,
        )
        solved = len(roots)
        widths = [result.width for result in output_results if result.width is not None]
        costs = [
            result.reachable_state_cost
            for result in output_results
            if result.reachable_state_cost is not None
        ]
        nodes = len(manager.reachable(roots))
        gates = -1
        netlist = None
        if solved == m:
            builder, output_signals = compile_bdd(manager, roots, 2 * n)
            gates = len(builder.lines)
            path = args.output_dir / f"{args.instance}.{name}.occam-bdd.txt"
            write_netlist(
                path,
                builder,
                output_signals,
                metadata=[
                    "minimum-width then minimum-reachable-state OBDD from train.csv only",
                    f"instance={args.instance} seed={args.seed} order_name={name}",
                    "order_zero_based=" + ",".join(map(str, order)),
                ],
            )
            netlist = str(path)
            successful.append(
                (
                    objective(solved, costs, widths, nodes, gates),
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
            "reachable_state_costs": costs,
            "nodes": nodes,
            "gates": gates,
            "netlist": netlist,
            "outputs": [
                {
                    "root": result.root,
                    "width": result.width,
                    "reachable_state_cost": result.reachable_state_cost,
                    "maxsat_elapsed_seconds": result.maxsat_elapsed_seconds,
                    "attempts": [attempt_to_json(item) for item in result.attempts],
                }
                for result in output_results
            ],
            "elapsed_seconds": time.monotonic() - candidate_started,
        }
        reports.append(report)
        (args.output_dir / f"{args.instance}.{name}.occam-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", "ascii"
        )

    summary: dict[str, object] = {
        "schema": "occam71-min-reachable-obdd-v2",
        "instance": args.instance,
        "seed": args.seed,
        "max_width": args.max_width,
        "conflict_budget": args.conflict_budget,
        "solver": args.solver,
        "training_sha256": hashlib.sha256(training_path.read_bytes()).hexdigest(),
        "heuristic_order_selection": heuristic_selection,
        "candidates": reports,
        "elapsed_seconds": time.monotonic() - started,
    }
    if successful:
        selected_objective, name, order, manager, roots = max(
            successful, key=lambda item: item[0]
        )
        builder, output_signals = compile_bdd(manager, roots, 2 * n)
        selected = args.output_dir / f"{args.instance}.selected.occam-bdd.txt"
        write_netlist(
            selected,
            builder,
            output_signals,
            metadata=[
                "train-only selected minimum-reachable-state OBDD",
                f"instance={args.instance} seed={args.seed} order_name={name}",
                "order_zero_based=" + ",".join(map(str, order)),
            ],
        )
        train_rows, train_bits = evaluate_samples(manager, roots, samples)
        audit = full_domain_audit(manager, roots, kind=kind, n=n, m=m)
        summary.update(
            {
                "status": "COMPLETE_CANDIDATE",
                "selected_order_name": name,
                "selected_order": order,
                "selection_objective": list(selected_objective),
                "selected_nodes": len(manager.reachable(roots)),
                "selected_gates": len(builder.lines),
                "selected_netlist": str(selected),
                "training_rows": len(samples),
                "training_exact_rows": train_rows,
                "training_correct_bits": train_bits,
                "full_domain_audit_after_selection": audit,
            }
        )
        exit_status = 0
        print(
            f"[done] selected={name} train={train_rows}/{len(samples)} "
            f"full={audit['exact_rows']}/{audit['total_rows']} "
            f"nodes={summary['selected_nodes']} gates={summary['selected_gates']}",
            flush=True,
        )
    else:
        summary["status"] = "NO_COMPLETE_CANDIDATE_WITHIN_WIDTH_OR_BUDGET"
        exit_status = 3
        print(f"[done] {summary['status']}", flush=True)
    path = args.output_dir / f"{args.instance}.occam-bdd-summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", "ascii")
    print(f"[artifact] {path}", flush=True)
    return exit_status


if __name__ == "__main__":
    raise SystemExit(main())
