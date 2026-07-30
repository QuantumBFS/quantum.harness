#!/usr/bin/env python3
"""Shared multi-root zero-suppressed decision diagram experiment for issue #71.

Each output bit is represented by the family of training inputs labelled one.
Unseen assignments are absent and therefore zero by the ZDD convention.  This
is the canonical zero-suppressed completion of the partial table, not a renamed
BDD.  Skipped ZDD variables implicitly require zero; conversion to the challenge
netlist first expands those guards into an ordinary shared BDD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from decision_diagram_learn_v2 import (
    BDDManager,
    INSTANCE_SPECS,
    Sample,
    base_orders,
    compile_bdd,
    evaluate_samples,
    full_domain_audit,
    read_training_csv,
    write_netlist,
)


@dataclass(frozen=True)
class ZDDNode:
    var: int
    low: int
    high: int


class ZDDManager:
    """Canonical ZDD manager: a node with high=0 is suppressed."""

    def __init__(self, order: Sequence[int]) -> None:
        self.order = list(order)
        self.position = {variable: depth for depth, variable in enumerate(order)}
        self.nodes: dict[int, ZDDNode] = {}
        self.unique: dict[ZDDNode, int] = {}
        self.next_id = 2

    def intern(self, var: int, low: int, high: int) -> int:
        if high == 0:
            return low
        node = ZDDNode(var, low, high)
        old = self.unique.get(node)
        if old is not None:
            return old
        node_id = self.next_id
        self.next_id += 1
        self.nodes[node_id] = node
        self.unique[node] = node_id
        return node_id

    def reachable(self, roots: Sequence[int]) -> set[int]:
        todo = [root for root in roots if root >= 2]
        found = set()
        while todo:
            node_id = todo.pop()
            if node_id in found:
                continue
            found.add(node_id)
            node = self.nodes[node_id]
            if node.low >= 2:
                todo.append(node.low)
            if node.high >= 2:
                todo.append(node.high)
        return found

    def evaluate_root(self, root: int, bits: Sequence[int]) -> int:
        depth = 0
        node_id = root
        while node_id >= 2:
            node = self.nodes[node_id]
            node_depth = self.position[node.var]
            if node_depth < depth:
                raise AssertionError("ZDD variable order violation")
            for skipped in range(depth, node_depth):
                if bits[self.order[skipped]]:
                    return 0
            node_id = node.high if bits[node.var] else node.low
            depth = node_depth + 1
        if node_id == 0:
            return 0
        for skipped in range(depth, len(self.order)):
            if bits[self.order[skipped]]:
                return 0
        return 1

    def evaluate(self, roots: Sequence[int], bits: Sequence[int]) -> tuple[int, ...]:
        return tuple(self.evaluate_root(root, bits) for root in roots)


def ordered_code(bits: Sequence[int], order: Sequence[int]) -> int:
    value = 0
    for depth, variable in enumerate(order):
        value |= bits[variable] << depth
    return value


def build_shared_zdd(
    samples: Sequence[Sample],
    order: Sequence[int],
) -> tuple[ZDDManager, list[int]]:
    manager = ZDDManager(order)
    codes = [ordered_code(sample.bits, order) for sample in samples]
    roots = []
    for output_bit in range(len(samples[0].output)):
        positive = tuple(
            sorted(
                {
                    code
                    for code, sample in zip(codes, samples)
                    if sample.output[output_bit] == 1
                }
            )
        )
        memo: dict[tuple[int, tuple[int, ...]], int] = {}

        def build(depth: int, family: tuple[int, ...]) -> int:
            if not family:
                return 0
            if depth == len(order):
                return 1
            key = (depth, family)
            old = memo.get(key)
            if old is not None:
                return old
            low = tuple(code for code in family if ((code >> depth) & 1) == 0)
            high = tuple(code for code in family if ((code >> depth) & 1) == 1)
            result = manager.intern(
                order[depth],
                build(depth + 1, low),
                build(depth + 1, high),
            )
            memo[key] = result
            return result

        roots.append(build(0, positive))
    for sample in samples:
        if manager.evaluate(roots, sample.bits) != sample.output:
            raise AssertionError("ZDD failed to preserve a training row")
    return manager, roots


def expand_zdd_to_bdd(
    zdd: ZDDManager,
    roots: Sequence[int],
) -> tuple[BDDManager, list[int]]:
    """Make every implicit zero-suppressed guard explicit as a BDD node."""
    bdd = BDDManager()
    memo: dict[tuple[int, int], int] = {}

    def expand(node_id: int, start_depth: int) -> int:
        key = (node_id, start_depth)
        old = memo.get(key)
        if old is not None:
            return old
        if node_id == 0:
            result = 0
        elif node_id == 1:
            result = 1
            for depth in range(len(zdd.order) - 1, start_depth - 1, -1):
                result = bdd.intern(zdd.order[depth], result, 0)
        else:
            node = zdd.nodes[node_id]
            node_depth = zdd.position[node.var]
            if node_depth < start_depth:
                raise AssertionError("ZDD variable order violation")
            low = expand(node.low, node_depth + 1)
            high = expand(node.high, node_depth + 1)
            result = bdd.intern(node.var, low, high)
            for depth in range(node_depth - 1, start_depth - 1, -1):
                result = bdd.intern(zdd.order[depth], result, 0)
        memo[key] = result
        return result

    bdd_roots = [expand(root, 0) for root in roots]
    return bdd, bdd_roots


def zdd_score(samples: Sequence[Sample], order: Sequence[int]) -> tuple[int, int]:
    manager, roots = build_shared_zdd(samples, order)
    return len(manager.reachable(roots)), len(manager.nodes)


def choose_order(
    samples: Sequence[Sample],
    n: int,
    *,
    seed: int,
    sift_variables: int,
    adjacent_passes: int,
) -> tuple[list[int], dict[str, object]]:
    rng = random.Random(seed)
    cache: dict[tuple[int, ...], tuple[int, int]] = {}
    trace = []

    def assess(order: Sequence[int], tag: str) -> tuple[int, int]:
        key = tuple(order)
        if key not in cache:
            cache[key] = zdd_score(samples, order)
        reachable, allocated = cache[key]
        trace.append(
            {
                "tag": tag,
                "order": list(order),
                "reachable_zdd_nodes": reachable,
                "allocated_zdd_nodes": allocated,
            }
        )
        print(
            f"[order] {tag} zdd_reachable={reachable} zdd_allocated={allocated}",
            flush=True,
        )
        return reachable, allocated

    bases = base_orders(n)
    scored = [(assess(order, name), name, list(order)) for name, order in bases.items()]
    best_score, base_name, best = min(scored, key=lambda item: (item[0], item[1]))

    variables = list(best)
    rng.shuffle(variables)
    for variable in variables[: min(sift_variables, len(variables))]:
        old_position = best.index(variable)
        without = [item for item in best if item != variable]
        local = (best_score, old_position, list(best))
        positions = list(range(len(best)))
        rng.shuffle(positions)
        for position in positions:
            trial = list(without)
            trial.insert(position, variable)
            score = assess(trial, f"sift-v{variable}-p{position}")
            if (score, position) < (local[0], local[1]):
                local = (score, position, trial)
        best_score, _, best = local

    for pass_id in range(adjacent_passes):
        positions = list(range(len(best) - 1))
        rng.shuffle(positions)
        changed = False
        for position in positions:
            trial = list(best)
            trial[position], trial[position + 1] = trial[position + 1], trial[position]
            score = assess(trial, f"adj-{pass_id}-p{position}")
            if score < best_score:
                best_score = score
                best = trial
                changed = True
        if not changed:
            break
    return best, {
        "seed": seed,
        "base_winner": base_name,
        "selected_order": best,
        "selected_zdd_score": list(best_score),
        "evaluated_orders": len(cache),
        "trace": trace,
    }


def evaluate_zdd_samples(
    manager: ZDDManager,
    roots: Sequence[int],
    samples: Sequence[Sample],
) -> tuple[int, int]:
    rows = 0
    bits = 0
    for sample in samples:
        predicted = manager.evaluate(roots, sample.bits)
        rows += int(predicted == sample.output)
        bits += sum(a == b for a, b in zip(predicted, sample.output))
    return rows, bits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--instance", choices=sorted(INSTANCE_SPECS), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sift-variables", type=int, default=6)
    parser.add_argument("--adjacent-passes", type=int, default=2)
    args = parser.parse_args()

    kind, n, m = INSTANCE_SPECS[args.instance]
    training_path = args.dataset_root / args.instance / "train.csv"
    samples = read_training_csv(training_path, 2 * n, m)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    order, selection = choose_order(
        samples,
        n,
        seed=args.seed,
        sift_variables=args.sift_variables,
        adjacent_passes=args.adjacent_passes,
    )
    zdd, zdd_roots = build_shared_zdd(samples, order)
    train_rows, train_bits = evaluate_zdd_samples(zdd, zdd_roots, samples)
    bdd, bdd_roots = expand_zdd_to_bdd(zdd, zdd_roots)
    bdd_train_rows, bdd_train_bits = evaluate_samples(bdd, bdd_roots, samples)
    if (train_rows, train_bits) != (bdd_train_rows, bdd_train_bits):
        raise AssertionError("ZDD-to-BDD expansion changed training semantics")
    builder, signals = compile_bdd(bdd, bdd_roots, 2 * n)
    audit = full_domain_audit(bdd, bdd_roots, kind=kind, n=n, m=m)
    netlist = args.output_dir / f"{args.instance}.shared-zdd.txt"
    write_netlist(
        netlist,
        builder,
        signals,
        metadata=[
            "shared multi-root zero-suppressed completion of train.csv",
            f"instance={args.instance} seed={args.seed}",
            "order_zero_based=" + ",".join(map(str, order)),
        ],
    )
    report = {
        "schema": "occam71-shared-zdd-v1",
        "instance": args.instance,
        "completion_rule": "unseen assignments are absent from each output on-set",
        "seed": args.seed,
        "training_rows": len(samples),
        "training_exact_rows": train_rows,
        "training_correct_bits": train_bits,
        "training_sha256": hashlib.sha256(training_path.read_bytes()).hexdigest(),
        "order_selection": selection,
        "zdd_reachable_nodes": len(zdd.reachable(zdd_roots)),
        "zdd_allocated_nodes": len(zdd.nodes),
        "expanded_bdd_reachable_nodes": len(bdd.reachable(bdd_roots)),
        "expanded_bdd_allocated_nodes": len(bdd.nodes),
        "gate_count": len(builder.lines),
        "netlist": str(netlist),
        "netlist_sha256": hashlib.sha256(netlist.read_bytes()).hexdigest(),
        "full_domain_audit": audit,
        "elapsed_seconds": time.monotonic() - started,
    }
    report_path = args.output_dir / f"{args.instance}.shared-zdd-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "ascii")
    print(
        f"[done] train={train_rows}/{len(samples)} "
        f"full={audit['exact_rows']}/{audit['total_rows']} "
        f"zdd={report['zdd_reachable_nodes']} "
        f"bdd={report['expanded_bdd_reachable_nodes']} gates={report['gate_count']}",
        flush=True,
    )
    print(f"[artifact] {netlist}", flush=True)
    print(f"[artifact] {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
