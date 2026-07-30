#!/usr/bin/env python3
"""Prefix-compressed minimum-width/minimum-state OBDD learner.

This is logically equivalent to the sample-wise SAT encoding, but assigns one
state variable to each distinct observed prefix rather than duplicating it for
every sample sharing that prefix.  It is substantially smaller on the large
formal instances while preserving exactly the same train-only hypothesis class
and Occam objective.
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
    compile_bdd,
    evaluate_samples,
    full_domain_audit,
    read_training_csv,
    write_netlist,
)


class _ClauseSink:
    def __init__(self, target: object, weighted: bool = False) -> None:
        self.target = target
        self.weighted = weighted
        self.count = 0

    def hard(self, clause: list[int]) -> None:
        if self.weighted:
            self.target.append(clause)
        else:
            self.target.add_clause(clause)
        self.count += 1


class PrefixEncoding:
    def __init__(self, samples: Sequence[Sample], order: Sequence[int], output_bit: int, k: int):
        self.samples = samples
        self.order = list(order)
        self.output_bit = output_bit
        self.k = k
        self.width = 1 << k
        self.depths = len(order) + 1
        codes = []
        labels: dict[int, int] = {}
        for sample in samples:
            code = 0
            for depth, variable in enumerate(order):
                code |= sample.bits[variable] << depth
            label = sample.output[output_bit]
            old = labels.get(code)
            if old is not None and old != label:
                raise ValueError("conflicting duplicate input")
            labels[code] = label
            codes.append(code)
        self.codes = sorted(set(codes))
        self.labels = labels
        self.prefixes: list[list[int]] = []
        self.prefix_index: list[dict[int, int]] = []
        self.p_offsets: list[int] = []
        next_variable = 1
        for depth in range(self.depths):
            mask = (1 << depth) - 1
            values = sorted({code & mask for code in self.codes})
            self.prefixes.append(values)
            self.prefix_index.append({value: idx for idx, value in enumerate(values)})
            self.p_offsets.append(next_variable)
            next_variable += len(values) * k
        self.t_base = next_variable
        self.t_count = len(order) * self.width * 2 * k
        self.o_base = self.t_base + self.t_count
        self.r_base = self.o_base + self.width
        self.nvars = self.r_base + self.depths * self.width - 1
        distinguished = self.codes[0]
        self.distinguished_prefix = [
            distinguished & ((1 << depth) - 1) for depth in range(self.depths)
        ]

    def pvar(self, depth: int, prefix_index: int, bit: int) -> int:
        return self.p_offsets[depth] + prefix_index * self.k + bit

    def tvar(self, depth: int, state: int, branch: int, bit: int) -> int:
        return self.t_base + ((((depth * self.width + state) * 2 + branch) * self.k) + bit)

    def ovar(self, state: int) -> int:
        return self.o_base + state

    def rvar(self, depth: int, state: int) -> int:
        return self.r_base + depth * self.width + state

    def mismatch(self, depth: int, prefix_index: int, state: int) -> list[int]:
        result = []
        for bit in range(self.k):
            variable = self.pvar(depth, prefix_index, bit)
            result.append(-variable if ((state >> bit) & 1) else variable)
        return result

    def add_base(self, sink: _ClauseSink) -> None:
        # The only depth-0 prefix starts in state zero.
        for bit in range(self.k):
            sink.hard([-self.pvar(0, 0, bit)])

        # Sound layer-wise state-name symmetry breaking.
        for depth in range(1, self.depths):
            prefix = self.distinguished_prefix[depth]
            index = self.prefix_index[depth][prefix]
            for bit in range(self.k):
                sink.hard([-self.pvar(depth, index, bit)])

        # One deterministic transition constraint per distinct observed edge.
        for depth in range(len(self.order)):
            next_mask = (1 << (depth + 1)) - 1
            edges = set()
            for code in self.codes:
                parent = code & ((1 << depth) - 1)
                branch = (code >> depth) & 1
                child = code & next_mask
                edges.add(
                    (
                        self.prefix_index[depth][parent],
                        branch,
                        self.prefix_index[depth + 1][child],
                    )
                )
            for parent, branch, child in sorted(edges):
                for state in range(self.width):
                    prefix = self.mismatch(depth, parent, state)
                    for bit in range(self.k):
                        nxt = self.pvar(depth + 1, child, bit)
                        transition = self.tvar(depth, state, branch, bit)
                        sink.hard(prefix + [-nxt, transition])
                        sink.hard(prefix + [nxt, -transition])

        last = self.depths - 1
        for code, label in sorted(self.labels.items()):
            leaf = self.prefix_index[last][code]
            for state in range(self.width):
                clause = self.mismatch(last, leaf, state)
                clause.append(self.ovar(state) if label else -self.ovar(state))
                sink.hard(clause)

    def make_wcnf(self) -> tuple[object, int, int]:
        from pysat.formula import WCNF

        formula = WCNF()
        sink = _ClauseSink(formula, weighted=True)
        self.add_base(sink)
        sink.hard([self.rvar(0, 0)])

        # Observed prefix states are reachable.
        for depth, prefixes in enumerate(self.prefixes):
            for prefix_index in range(len(prefixes)):
                for state in range(self.width):
                    sink.hard(
                        self.mismatch(depth, prefix_index, state)
                        + [self.rvar(depth, state)]
                    )

        # Complete both observed and missing outgoing branches of every
        # reachable state, then minimize the resulting reachable-state count.
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
                        sink.hard(
                            [-self.rvar(depth, state)]
                            + transition_mismatch
                            + [self.rvar(depth + 1, nxt)]
                        )
        soft_count = self.depths * self.width
        for depth in range(self.depths):
            for state in range(self.width):
                formula.append([-self.rvar(depth, state)], weight=1)
        return formula, sink.count, soft_count

    def decode(self, model: Sequence[int], manager: BDDManager) -> int:
        positive = {literal for literal in model if literal > 0}
        transitions = {}
        for depth in range(len(self.order)):
            for state in range(self.width):
                for branch in (0, 1):
                    nxt = 0
                    for bit in range(self.k):
                        if self.tvar(depth, state, branch, bit) in positive:
                            nxt |= 1 << bit
                    transitions[depth, state, branch] = nxt
        labels = [int(self.ovar(state) in positive) for state in range(self.width)]
        memo = {}

        def build(depth: int, state: int) -> int:
            key = (depth, state)
            if key in memo:
                return memo[key]
            if depth == len(self.order):
                result = labels[state]
            else:
                low = build(depth + 1, transitions[depth, state, 0])
                high = build(depth + 1, transitions[depth, state, 1])
                result = manager.intern(self.order[depth], low, high)
            memo[key] = result
            return result

        return build(0, 0)


@dataclass
class OutputResult:
    root: int | None
    width: int | None
    reachable_cost: int | None
    feasibility: list[dict[str, object]]
    maxsat_seconds: float | None


def learn_output(
    samples: Sequence[Sample],
    order: Sequence[int],
    output_bit: int,
    manager: BDDManager,
    *,
    max_width: int,
    conflict_budget: int,
    solver_name: str,
) -> OutputResult:
    labels = {sample.output[output_bit] for sample in samples}
    if len(labels) == 1:
        return OutputResult(next(iter(labels)), 1, len(order) + 1, [], 0.0)
    from pysat.examples.rc2 import RC2
    from pysat.solvers import Solver

    attempts = []
    max_k = int(math.log2(max_width))
    chosen_k = None
    for k in range(1, max_k + 1):
        encoding = PrefixEncoding(samples, order, output_bit, k)
        started = time.monotonic()
        with Solver(name=solver_name) as solver:
            sink = _ClauseSink(solver)
            encoding.add_base(sink)
            if conflict_budget > 0:
                solver.conf_budget(conflict_budget)
                status = solver.solve_limited(expect_interrupt=True)
            else:
                status = solver.solve()
            stats = solver.accum_stats()
        elapsed = time.monotonic() - started
        record = {
            "width": encoding.width,
            "status": "SAT" if status is True else "UNSAT" if status is False else "UNKNOWN",
            "variables": encoding.nvars,
            "clauses": sink.count,
            "prefix_counts": [len(items) for items in encoding.prefixes],
            "conflicts": stats.get("conflicts"),
            "decisions": stats.get("decisions"),
            "elapsed_seconds": elapsed,
        }
        attempts.append(record)
        print(
            f"[prefix-feasible] bit={output_bit} width={encoding.width} "
            f"status={record['status']} vars={encoding.nvars} clauses={sink.count} "
            f"conflicts={record['conflicts']} elapsed={elapsed:.3f}s",
            flush=True,
        )
        if status is True:
            chosen_k = k
            break
    if chosen_k is None:
        return OutputResult(None, None, None, attempts, None)

    encoding = PrefixEncoding(samples, order, output_bit, chosen_k)
    formula, hard, soft = encoding.make_wcnf()
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
        f"[prefix-maxsat] bit={output_bit} width={encoding.width} cost={cost} "
        f"hard={hard} soft={soft} elapsed={elapsed:.3f}s",
        flush=True,
    )
    if model is None:
        return OutputResult(None, encoding.width, None, attempts, elapsed)
    root = encoding.decode(model, manager)
    one_bit = [Sample(row.bits, (row.output[output_bit],)) for row in samples]
    if evaluate_samples(manager, [root], one_bit)[0] != len(samples):
        raise AssertionError("decoded prefix MaxSAT model violates samples")
    return OutputResult(root, encoding.width, int(cost), attempts, elapsed)


def parse_order(text: str, size: int) -> list[int]:
    values = [int(piece) for piece in text.split(",") if piece]
    if sorted(values) != list(range(size)):
        raise ValueError("fixed order is not a permutation")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--instance", choices=sorted(INSTANCE_SPECS), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fixed-order", required=True)
    parser.add_argument("--fixed-order-name", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-width", type=int, default=16)
    parser.add_argument("--conflict-budget", type=int, default=1_000_000)
    parser.add_argument("--solver", default="cadical195")
    args = parser.parse_args()

    kind, n, m = INSTANCE_SPECS[args.instance]
    order = parse_order(args.fixed_order, 2 * n)
    path = args.dataset_root / args.instance / "train.csv"
    samples = read_training_csv(path, 2 * n, m)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    manager = BDDManager()
    roots = []
    results = []
    for bit in range(m):
        print(f"[output] bit={bit}", flush=True)
        result = learn_output(
            samples,
            order,
            bit,
            manager,
            max_width=args.max_width,
            conflict_budget=args.conflict_budget,
            solver_name=args.solver,
        )
        results.append(result)
        if result.root is None:
            break
        roots.append(result.root)

    report: dict[str, object] = {
        "schema": "occam71-prefix-compressed-obdd-v3",
        "instance": args.instance,
        "seed": args.seed,
        "order_name": args.fixed_order_name,
        "order": order,
        "max_width": args.max_width,
        "conflict_budget": args.conflict_budget,
        "solver": args.solver,
        "training_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "solved_outputs": len(roots),
        "outputs": [
            {
                "root": result.root,
                "width": result.width,
                "reachable_cost": result.reachable_cost,
                "feasibility": result.feasibility,
                "maxsat_seconds": result.maxsat_seconds,
            }
            for result in results
        ],
    }
    if len(roots) == m:
        builder, signals = compile_bdd(manager, roots, 2 * n)
        netlist = args.output_dir / f"{args.instance}.prefix-occam-bdd.txt"
        write_netlist(
            netlist,
            builder,
            signals,
            metadata=[
                "prefix-compressed minimum-width/minimum-state OBDD from train.csv only",
                f"instance={args.instance} seed={args.seed} order_name={args.fixed_order_name}",
                "order_zero_based=" + ",".join(map(str, order)),
            ],
        )
        train_rows, train_bits = evaluate_samples(manager, roots, samples)
        audit = full_domain_audit(manager, roots, kind=kind, n=n, m=m)
        report.update(
            {
                "status": "COMPLETE_CANDIDATE",
                "training_rows": len(samples),
                "training_exact_rows": train_rows,
                "training_correct_bits": train_bits,
                "nodes": len(manager.reachable(roots)),
                "gates": len(builder.lines),
                "netlist": str(netlist),
                "full_domain_audit": audit,
            }
        )
        status = 0
        print(
            f"[done] train={train_rows}/{len(samples)} "
            f"full={audit['exact_rows']}/{audit['total_rows']} "
            f"nodes={report['nodes']} gates={report['gates']}",
            flush=True,
        )
    else:
        report["status"] = "NO_COMPLETE_CANDIDATE_WITHIN_WIDTH_OR_BUDGET"
        status = 3
        print(f"[done] {report['status']} solved={len(roots)}/{m}", flush=True)
    report["elapsed_seconds"] = time.monotonic() - started
    report_path = args.output_dir / f"{args.instance}.prefix-occam-summary.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "ascii")
    print(f"[artifact] {report_path}", flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
