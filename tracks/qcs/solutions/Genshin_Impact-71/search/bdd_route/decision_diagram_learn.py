#!/usr/bin/env python3
"""Train-only shared multi-root BDD learner for Occam's Circuit issue #71.

The learner never reads a reference circuit.  For each output bit it builds a
layered prefix acceptor from the labelled examples, then merges bottom-up
states whose observed outgoing transitions are compatible.  Missing
transitions are don't-cares and are completed toward an already observed
transition, which is the smallest deterministic completion at that state.

Variable ordering is selected only from a deterministic seed-42 split of the
official training rows.  Revealed arithmetic semantics are used solely by the
post-training full-domain audit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


INSTANCE_SPECS = {
    "practice-add-n4": ("add", 4, 5),
    "practice-mul-n4": ("mul", 4, 8),
    "mystery-A": ("add", 8, 9),
    "mystery-B": ("absdiff", 7, 7),
    "mystery-C": ("mul", 6, 12),
    "mystery-D": ("sos", 5, 11),
}


@dataclass(frozen=True)
class Sample:
    bits: tuple[int, ...]
    output: tuple[int, ...]


def read_training_csv(path: Path, n_inputs: int, n_outputs: int) -> list[Sample]:
    """Strict parser for the two-column official training format."""
    rows: list[Sample] = []
    seen: dict[tuple[int, ...], tuple[int, ...]] = {}
    with path.open("r", encoding="ascii", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{path}: empty CSV") from exc
        if header != ["input", "output"]:
            raise ValueError(f"{path}: expected header input,output; got {header!r}")
        for line_no, row in enumerate(reader, 2):
            if len(row) != 2:
                raise ValueError(f"{path}:{line_no}: expected exactly two fields")
            ibits, obits = row
            if len(ibits) != n_inputs or set(ibits) - {"0", "1"}:
                raise ValueError(f"{path}:{line_no}: invalid input bit string")
            if len(obits) != n_outputs or set(obits) - {"0", "1"}:
                raise ValueError(f"{path}:{line_no}: invalid output bit string")
            key = tuple(ord(ch) - 48 for ch in ibits)
            value = tuple(ord(ch) - 48 for ch in obits)
            old = seen.get(key)
            if old is not None and old != value:
                raise ValueError(f"{path}:{line_no}: conflicting duplicate input")
            if old is None:
                seen[key] = value
                rows.append(Sample(key, value))
    if not rows:
        raise ValueError(f"{path}: no samples")
    return rows


@dataclass(frozen=True)
class BDDNode:
    var: int
    low: int
    high: int


class BDDManager:
    """Canonical reduced ordered BDD manager shared by all output roots."""

    def __init__(self) -> None:
        self.nodes: dict[int, BDDNode] = {}
        self.unique: dict[BDDNode, int] = {}
        self.next_id = 2  # 0 and 1 are terminals

    def intern(self, var: int, low: int, high: int) -> int:
        if low == high:
            return low
        node = BDDNode(var, low, high)
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
        found: set[int] = set()
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
        node_id = root
        while node_id >= 2:
            node = self.nodes[node_id]
            node_id = node.high if bits[node.var] else node.low
        return node_id

    def evaluate(self, roots: Sequence[int], bits: Sequence[int]) -> tuple[int, ...]:
        return tuple(self.evaluate_root(root, bits) for root in roots)


@dataclass
class _Cluster:
    low: int | None
    high: int | None
    prefixes: list[int]
    support: int

    def compatible(self, pattern: tuple[int | None, int | None]) -> bool:
        low, high = pattern
        return (
            (self.low is None or low is None or self.low == low)
            and (self.high is None or high is None or self.high == high)
        )

    def absorb(
        self,
        pattern: tuple[int | None, int | None],
        prefixes: Sequence[int],
    ) -> None:
        low, high = pattern
        if self.low is None:
            self.low = low
        if self.high is None:
            self.high = high
        self.prefixes.extend(prefixes)
        self.support += len(prefixes)


def _stable_tie(seed: int, output_bit: int, depth: int, values: object) -> int:
    payload = f"{seed}|{output_bit}|{depth}|{values!r}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _cluster_patterns(
    patterns: dict[int, tuple[int | None, int | None]],
    *,
    var: int,
    manager: BDDManager,
    seed: int,
    output_bit: int,
    depth: int,
) -> dict[int, int]:
    """Greedily cover wildcard transition pairs by compatible total pairs.

    Exact pairs are anchors.  One-sided pairs are placed into an anchor that
    preserves all observed transitions while preferring a reduced or already
    shared BDD node.  The procedure is deterministic for the recorded seed.
    """
    by_pattern: dict[tuple[int | None, int | None], list[int]] = {}
    for prefix, pattern in patterns.items():
        if pattern == (None, None):
            raise AssertionError("observed prefix cannot have two missing children")
        by_pattern.setdefault(pattern, []).append(prefix)

    ordered = sorted(
        by_pattern,
        key=lambda p: (
            -int(p[0] is not None) - int(p[1] is not None),
            -len(by_pattern[p]),
            _stable_tie(seed, output_bit, depth, p),
        ),
    )
    clusters: list[_Cluster] = []
    for pattern in ordered:
        prefixes = by_pattern[pattern]
        compatible: list[tuple[tuple[int, int, int, int], int]] = []
        for idx, cluster in enumerate(clusters):
            if not cluster.compatible(pattern):
                continue
            low = cluster.low if cluster.low is not None else pattern[0]
            high = cluster.high if cluster.high is not None else pattern[1]
            if low is None and high is not None:
                low = high
            if high is None and low is not None:
                high = low
            assert low is not None and high is not None
            reduced = int(low == high)
            shared = int(BDDNode(var, low, high) in manager.unique)
            tie = -(_stable_tie(seed, output_bit, depth, (pattern, idx)) & 0x7FFFFFFF)
            compatible.append(((reduced, shared, cluster.support, tie), idx))
        if compatible:
            _, idx = max(compatible)
            clusters[idx].absorb(pattern, prefixes)
        else:
            clusters.append(_Cluster(pattern[0], pattern[1], list(prefixes), len(prefixes)))

    assignment: dict[int, int] = {}
    for cluster in clusters:
        low, high = cluster.low, cluster.high
        if low is None:
            if high is None:
                raise AssertionError("empty cluster")
            low = high
        if high is None:
            high = low
        node_id = manager.intern(var, low, high)
        for prefix in cluster.prefixes:
            assignment[prefix] = node_id
    if assignment.keys() != patterns.keys():
        raise AssertionError("incomplete cluster assignment")
    return assignment


def _ordered_code(bits: Sequence[int], order: Sequence[int]) -> int:
    code = 0
    for depth, var in enumerate(order):
        code |= bits[var] << depth
    return code


def learn_shared_bdd(
    samples: Sequence[Sample],
    order: Sequence[int],
    *,
    seed: int = 42,
) -> tuple[BDDManager, list[int]]:
    n_inputs = len(samples[0].bits)
    n_outputs = len(samples[0].output)
    if sorted(order) != list(range(n_inputs)):
        raise ValueError("order must be a permutation of all input variables")
    manager = BDDManager()
    codes = [_ordered_code(sample.bits, order) for sample in samples]
    roots: list[int] = []
    for output_bit in range(n_outputs):
        state_of_prefix: dict[int, int] = {}
        for sample, code in zip(samples, codes):
            label = sample.output[output_bit]
            old = state_of_prefix.get(code)
            if old is not None and old != label:
                raise ValueError("conflicting duplicate training input")
            state_of_prefix[code] = label
        for depth in range(n_inputs - 1, -1, -1):
            mask = (1 << depth) - 1
            patterns: dict[int, list[int | None]] = {}
            for child_prefix, child_state in state_of_prefix.items():
                parent = child_prefix & mask
                branch = (child_prefix >> depth) & 1
                pair = patterns.setdefault(parent, [None, None])
                old = pair[branch]
                if old is not None and old != child_state:
                    raise AssertionError("nondeterministic prefix transition")
                pair[branch] = child_state
            state_of_prefix = _cluster_patterns(
                {prefix: (pair[0], pair[1]) for prefix, pair in patterns.items()},
                var=order[depth],
                manager=manager,
                seed=seed,
                output_bit=output_bit,
                depth=depth,
            )
        if set(state_of_prefix) != {0}:
            raise AssertionError("root prefix missing")
        roots.append(state_of_prefix[0])
    for sample in samples:
        if manager.evaluate(roots, sample.bits) != sample.output:
            raise AssertionError("learned BDD lost a training constraint")
    return manager, roots


@dataclass(frozen=True)
class Signal:
    ref: str | None
    inverted: bool = False
    const: int | None = None

    @staticmethod
    def constant(value: int) -> "Signal":
        return Signal(None, False, value)

    def negate(self) -> "Signal":
        if self.const is not None:
            return Signal.constant(1 - self.const)
        return Signal(self.ref, not self.inverted)

    def sort_key(self) -> tuple[str, int, int]:
        return (self.ref or "", int(self.inverted), -1 if self.const is None else self.const)

    def render(self) -> str:
        if self.const is not None:
            raise ValueError("constant must be materialized before rendering")
        assert self.ref is not None
        return f"~{self.ref}" if self.inverted else self.ref


class GateBuilder:
    """Phase-aware AND/XOR gate builder with global structural CSE."""

    def __init__(self, n_inputs: int) -> None:
        self.n_inputs = n_inputs
        self.lines: list[tuple[str, str, str, str]] = []
        self.and_cache: dict[tuple[tuple[str, bool], tuple[str, bool]], Signal] = {}
        self.xor_cache: dict[tuple[str, str], Signal] = {}

    def clone(self) -> "GateBuilder":
        other = GateBuilder(self.n_inputs)
        other.lines = list(self.lines)
        other.and_cache = dict(self.and_cache)
        other.xor_cache = dict(self.xor_cache)
        return other

    def _new_wire(self) -> str:
        return f"w{len(self.lines) + 1}"

    @staticmethod
    def _same_base(a: Signal, b: Signal) -> bool:
        return a.const is None and b.const is None and a.ref == b.ref

    def and_(self, a: Signal, b: Signal) -> Signal:
        if a.const is not None:
            return Signal.constant(0) if a.const == 0 else b
        if b.const is not None:
            return Signal.constant(0) if b.const == 0 else a
        if self._same_base(a, b):
            return Signal.constant(0) if a.inverted != b.inverted else a
        if b.sort_key() < a.sort_key():
            a, b = b, a
        assert a.ref is not None and b.ref is not None
        key = ((a.ref, a.inverted), (b.ref, b.inverted))
        old = self.and_cache.get(key)
        if old is not None:
            return old
        wire = self._new_wire()
        self.lines.append((wire, "AND", a.render(), b.render()))
        result = Signal(wire)
        self.and_cache[key] = result
        # The complement is the same scored gate spelled NAND, so no extra key
        # is required; callers carry the free output phase on Signal.
        return result

    def or_(self, a: Signal, b: Signal) -> Signal:
        return self.and_(a.negate(), b.negate()).negate()

    def xor(self, a: Signal, b: Signal) -> Signal:
        if a.const is not None:
            return b if a.const == 0 else b.negate()
        if b.const is not None:
            return a if b.const == 0 else a.negate()
        if self._same_base(a, b):
            return Signal.constant(int(a.inverted != b.inverted))
        phase = a.inverted ^ b.inverted
        assert a.ref is not None and b.ref is not None
        left, right = sorted((a.ref, b.ref))
        key = (left, right)
        old = self.xor_cache.get(key)
        if old is None:
            wire = self._new_wire()
            self.lines.append((wire, "XOR", left, right))
            old = Signal(wire)
            self.xor_cache[key] = old
        return old.negate() if phase else old

    def mux(self, select: Signal, low: Signal, high: Signal) -> Signal:
        if low == high:
            return low
        if low.const == 0 and high.const == 1:
            return select
        if low.const == 1 and high.const == 0:
            return select.negate()
        if low.const == 0:
            return self.and_(select, high)
        if high.const == 0:
            return self.and_(select.negate(), low)
        if low.const == 1:
            return self.or_(select.negate(), high)
        if high.const == 1:
            return self.or_(select, low)
        if self._same_base(low, high) and low.inverted != high.inverted:
            # low XOR select gives low for select=0 and ~low for select=1.
            return self.xor(low, select)

        # Compare two exact three-gate Shannon decompositions under current CSE.
        xor_trial = self.clone()
        delta = xor_trial.xor(low, high)
        changed = xor_trial.and_(select, delta)
        xor_result = xor_trial.xor(low, changed)

        sop_trial = self.clone()
        low_term = sop_trial.and_(select.negate(), low)
        high_term = sop_trial.and_(select, high)
        sop_result = sop_trial.or_(low_term, high_term)

        if len(sop_trial.lines) < len(xor_trial.lines):
            self.lines = sop_trial.lines
            self.and_cache = sop_trial.and_cache
            self.xor_cache = sop_trial.xor_cache
            return sop_result
        self.lines = xor_trial.lines
        self.and_cache = xor_trial.and_cache
        self.xor_cache = xor_trial.xor_cache
        return xor_result

    def materialize_constant(self, value: int) -> Signal:
        base = Signal("x1")
        zero = self.xor(base, base)
        return zero if value == 0 else zero.negate()


def compile_bdd(
    manager: BDDManager,
    roots: Sequence[int],
    n_inputs: int,
) -> tuple[GateBuilder, list[Signal]]:
    builder = GateBuilder(n_inputs)
    memo: dict[int, Signal] = {
        0: Signal.constant(0),
        1: Signal.constant(1),
    }

    def compile_node(node_id: int) -> Signal:
        old = memo.get(node_id)
        if old is not None:
            return old
        node = manager.nodes[node_id]
        low = compile_node(node.low)
        high = compile_node(node.high)
        select = Signal(f"x{node.var + 1}")
        result = builder.mux(select, low, high)
        memo[node_id] = result
        return result

    outputs = [compile_node(root) for root in roots]
    for idx, output in enumerate(outputs):
        if output.const is not None:
            outputs[idx] = builder.materialize_constant(output.const)
    return builder, outputs


def write_netlist(
    path: Path,
    builder: GateBuilder,
    outputs: Sequence[Signal],
    *,
    metadata: Sequence[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as handle:
        for line in metadata:
            safe = line.encode("ascii", "strict").decode("ascii")
            handle.write(f"# {safe}\n")
        handle.write(f"INPUTS {builder.n_inputs}\n")
        for wire, op, left, right in builder.lines:
            handle.write(f"{wire} = {op} {left} {right}\n")
        handle.write("OUTPUTS " + " ".join(output.render() for output in outputs) + "\n")


def base_orders(n: int) -> dict[str, list[int]]:
    return {
        "blocked": list(range(2 * n)),
        "lsb_interleaved": [item for bit in range(n) for item in (bit, n + bit)],
        "msb_interleaved": [
            item for bit in range(n - 1, -1, -1) for item in (bit, n + bit)
        ],
    }


def evaluate_samples(
    manager: BDDManager,
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


@dataclass(frozen=True)
class OrderScore:
    exact_rows: int
    correct_bits: int
    gates: int
    nodes: int

    def objective(self) -> tuple[int, int, int, int]:
        return (self.exact_rows, self.correct_bits, -self.gates, -self.nodes)


def score_order(
    fit: Sequence[Sample],
    validation: Sequence[Sample],
    order: Sequence[int],
    seed: int,
) -> OrderScore:
    manager, roots = learn_shared_bdd(fit, order, seed=seed)
    exact_rows, correct_bits = evaluate_samples(manager, roots, validation)
    builder, _ = compile_bdd(manager, roots, len(order))
    return OrderScore(
        exact_rows,
        correct_bits,
        len(builder.lines),
        len(manager.reachable(roots)),
    )


def choose_order(
    samples: Sequence[Sample],
    n: int,
    *,
    seed: int,
    validation_fraction: float,
    sift_variables: int,
    adjacent_passes: int,
    progress: bool = True,
) -> tuple[list[int], dict[str, object]]:
    rng = random.Random(seed)
    indices = list(range(len(samples)))
    rng.shuffle(indices)
    n_valid = max(1, round(len(samples) * validation_fraction))
    valid_ids = set(indices[:n_valid])
    fit = [sample for idx, sample in enumerate(samples) if idx not in valid_ids]
    validation = [sample for idx, sample in enumerate(samples) if idx in valid_ids]
    cache: dict[tuple[int, ...], OrderScore] = {}
    trace: list[dict[str, object]] = []

    def assess(order: Sequence[int], tag: str) -> OrderScore:
        key = tuple(order)
        score = cache.get(key)
        if score is None:
            score = score_order(fit, validation, order, seed)
            cache[key] = score
        trace.append({"tag": tag, "order": list(order), **score.__dict__})
        if progress:
            print(
                f"[order] {tag} rows={score.exact_rows}/{len(validation)} "
                f"bits={score.correct_bits}/{len(validation) * len(samples[0].output)} "
                f"gates={score.gates} nodes={score.nodes}",
                flush=True,
            )
        return score

    candidates = base_orders(n)
    scored = [(assess(order, name), name, order) for name, order in candidates.items()]
    best_score, best_name, best_order = max(scored, key=lambda item: item[0].objective())
    best_order = list(best_order)

    variables = list(best_order)
    rng.shuffle(variables)
    for var in variables[: min(sift_variables, len(variables))]:
        old_position = best_order.index(var)
        without = [item for item in best_order if item != var]
        local_best = (best_score, old_position, list(best_order))
        positions = list(range(len(best_order)))
        rng.shuffle(positions)
        for position in positions:
            trial = list(without)
            trial.insert(position, var)
            score = assess(trial, f"sift-v{var}-p{position}")
            candidate = (score.objective(), -position)
            incumbent = (local_best[0].objective(), -local_best[1])
            if candidate > incumbent:
                local_best = (score, position, trial)
        best_score, _, best_order = local_best

    for pass_id in range(adjacent_passes):
        positions = list(range(len(best_order) - 1))
        rng.shuffle(positions)
        changed = False
        for position in positions:
            trial = list(best_order)
            trial[position], trial[position + 1] = trial[position + 1], trial[position]
            score = assess(trial, f"adj-{pass_id}-p{position}")
            if score.objective() > best_score.objective():
                best_score = score
                best_order = trial
                changed = True
        if not changed:
            break

    summary = {
        "seed": seed,
        "fit_rows": len(fit),
        "validation_rows": len(validation),
        "selected_from": best_name,
        "selected_order": best_order,
        "selected_score": best_score.__dict__,
        "evaluated_orders": len(cache),
        "trace": trace,
    }
    return best_order, summary


def bits_for_xy(x: int, y: int, n: int) -> tuple[int, ...]:
    return tuple((x >> bit) & 1 for bit in range(n)) + tuple(
        (y >> bit) & 1 for bit in range(n)
    )


def truth_value(kind: str, x: int, y: int) -> int:
    if kind == "add":
        return x + y
    if kind == "mul":
        return x * y
    if kind == "absdiff":
        return abs(x - y)
    if kind == "sos":
        return x * x + y * y
    raise ValueError(f"unknown audit function {kind!r}")


def full_domain_audit(
    manager: BDDManager,
    roots: Sequence[int],
    *,
    kind: str,
    n: int,
    m: int,
) -> dict[str, object]:
    exact_rows = 0
    correct_bits = 0
    first_failures: list[dict[str, object]] = []
    total = 1 << (2 * n)
    mask = (1 << n) - 1
    for packed in range(total):
        x, y = packed & mask, packed >> n
        bits = bits_for_xy(x, y, n)
        predicted_bits = manager.evaluate(roots, bits)
        expected_value = truth_value(kind, x, y)
        expected_bits = tuple((expected_value >> bit) & 1 for bit in range(m))
        exact_rows += int(predicted_bits == expected_bits)
        correct_bits += sum(a == b for a, b in zip(predicted_bits, expected_bits))
        if predicted_bits != expected_bits and len(first_failures) < 8:
            first_failures.append(
                {
                    "x": x,
                    "y": y,
                    "predicted": "".join(map(str, predicted_bits)),
                    "expected": "".join(map(str, expected_bits)),
                }
            )
    return {
        "total_rows": total,
        "exact_rows": exact_rows,
        "row_accuracy": exact_rows / total,
        "correct_bits": correct_bits,
        "total_bits": total * m,
        "bit_accuracy": correct_bits / (total * m),
        "first_failures": first_failures,
    }


def parse_order(text: str, n_inputs: int) -> list[int]:
    values = [int(piece) for piece in text.split(",") if piece]
    if sorted(values) != list(range(n_inputs)):
        raise argparse.ArgumentTypeError("order must list every zero-based input index once")
    return values


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--instance", choices=sorted(INSTANCE_SPECS), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--sift-variables", type=int, default=6)
    parser.add_argument("--adjacent-passes", type=int, default=2)
    parser.add_argument("--fixed-order")
    args = parser.parse_args(argv)

    kind, n, m = INSTANCE_SPECS[args.instance]
    training_path = args.dataset_root / args.instance / "train.csv"
    samples = read_training_csv(training_path, 2 * n, m)
    started = time.monotonic()
    if args.fixed_order:
        order = parse_order(args.fixed_order, 2 * n)
        selection: dict[str, object] = {
            "seed": args.seed,
            "selected_order": order,
            "mode": "fixed",
        }
    else:
        order, selection = choose_order(
            samples,
            n,
            seed=args.seed,
            validation_fraction=args.validation_fraction,
            sift_variables=args.sift_variables,
            adjacent_passes=args.adjacent_passes,
        )
    print(f"[fit] instance={args.instance} rows={len(samples)} order={order}", flush=True)
    manager, roots = learn_shared_bdd(samples, order, seed=args.seed)
    train_rows, train_bits = evaluate_samples(manager, roots, samples)
    builder, outputs = compile_bdd(manager, roots, 2 * n)
    audit = full_domain_audit(manager, roots, kind=kind, n=n, m=m)
    elapsed = time.monotonic() - started

    args.output_dir.mkdir(parents=True, exist_ok=True)
    netlist_path = args.output_dir / f"{args.instance}.bdd.txt"
    write_netlist(
        netlist_path,
        builder,
        outputs,
        metadata=[
            "self-written train-only compatible-state BDD learner",
            f"instance={args.instance} seed={args.seed}",
            "order_zero_based=" + ",".join(map(str, order)),
        ],
    )
    report = {
        "schema": "occam71-bdd-route-v1",
        "instance": args.instance,
        "function_used_only_for_audit": kind,
        "n": n,
        "m": m,
        "training_rows": len(samples),
        "training_exact_rows": train_rows,
        "training_correct_bits": train_bits,
        "order_selection": selection,
        "bdd_reachable_nodes": len(manager.reachable(roots)),
        "bdd_allocated_nodes": len(manager.nodes),
        "gate_count": len(builder.lines),
        "root_ids": roots,
        "full_domain_audit": audit,
        "elapsed_seconds": elapsed,
        "netlist": str(netlist_path),
        "training_sha256": hashlib.sha256(training_path.read_bytes()).hexdigest(),
    }
    report_path = args.output_dir / f"{args.instance}.report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(
        f"[done] train={train_rows}/{len(samples)} "
        f"full={audit['exact_rows']}/{audit['total_rows']} "
        f"nodes={report['bdd_reachable_nodes']} gates={report['gate_count']} "
        f"elapsed={elapsed:.3f}s",
        flush=True,
    )
    print(f"[artifact] {netlist_path}", flush=True)
    print(f"[artifact] {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
