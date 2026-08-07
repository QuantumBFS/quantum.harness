"""Synthesize a learned Boolean table as a shared reduced ordered BDD."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import numpy as np

from train_boolean_spectrum import DOMAIN_SIZE, INPUT_BITS, evaluate_network


OUTPUT_BITS = 12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-network", type=Path, required=True)
    parser.add_argument("--order-search-trials", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=97_100)
    parser.add_argument("--output-network", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_ordered_ids(order: tuple[int, ...]) -> np.ndarray:
    paths = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    ids = np.zeros(DOMAIN_SIZE, dtype=np.uint16)
    for depth, variable in enumerate(order):
        path_shift = INPUT_BITS - depth - 1
        ids |= ((paths >> path_shift) & 1) << variable
    return ids


def build_shared_bdd(
    truth_table: np.ndarray,
    order: tuple[int, ...],
    *,
    retain_nodes: bool,
) -> tuple[int, list[int], dict[int, dict[str, int]]]:
    ordered_ids = path_ordered_ids(order)
    unique: dict[tuple[int, int, int], int] = {}
    nodes: dict[int, dict[str, int]] = {}
    roots: list[int] = []
    for output_bit in range(OUTPUT_BITS):
        level = truth_table[ordered_ids, output_bit].astype(int).tolist()
        for variable in reversed(order):
            next_level: list[int] = []
            for offset in range(0, len(level), 2):
                low = level[offset]
                high = level[offset + 1]
                if low == high:
                    next_level.append(low)
                    continue
                key = (variable, low, high)
                node_id = unique.get(key)
                if node_id is None:
                    node_id = len(unique) + 2
                    unique[key] = node_id
                    if retain_nodes:
                        nodes[node_id] = {
                            "variable": variable,
                            "low": low,
                            "high": high,
                        }
                next_level.append(node_id)
            level = next_level
        roots.append(level[0])
    return len(unique), roots, nodes


def candidate_orders(
    trials: int,
    seed: int,
) -> list[tuple[int, ...]]:
    generator = random.Random(seed)
    x_bits = tuple(range(6))
    y_bits = tuple(range(6, 12))
    candidates = [
        tuple(range(INPUT_BITS)),
        tuple(reversed(range(INPUT_BITS))),
        tuple(bit for pair in zip(x_bits, y_bits) for bit in pair),
        tuple(
            bit
            for pair in zip(reversed(x_bits), reversed(y_bits))
            for bit in pair
        ),
        tuple(reversed(x_bits)) + tuple(reversed(y_bits)),
        y_bits + x_bits,
    ]
    candidates.extend(
        tuple(generator.sample(range(INPUT_BITS), INPUT_BITS))
        for _ in range(trials)
    )
    return candidates


def optimize_order(
    truth_table: np.ndarray,
    trials: int,
    seed: int,
) -> tuple[tuple[int, ...], int]:
    candidates = candidate_orders(trials, seed)
    best_order = candidates[0]
    best_count, _, _ = build_shared_bdd(
        truth_table,
        best_order,
        retain_nodes=False,
    )
    for order in candidates[1:]:
        count, _, _ = build_shared_bdd(
            truth_table,
            order,
            retain_nodes=False,
        )
        if count < best_count:
            best_order = order
            best_count = count

    improved = True
    while improved:
        improved = False
        for left in range(INPUT_BITS):
            for right in range(left + 1, INPUT_BITS):
                proposal = list(best_order)
                proposal[left], proposal[right] = (
                    proposal[right],
                    proposal[left],
                )
                proposal_order = tuple(proposal)
                count, _, _ = build_shared_bdd(
                    truth_table,
                    proposal_order,
                    retain_nodes=False,
                )
                if count < best_count:
                    best_order = proposal_order
                    best_count = count
                    improved = True
    return best_order, best_count


class GateBuilder:
    def __init__(self) -> None:
        self.gates: list[dict[str, str]] = []
        self.cache: dict[tuple[str, str, str], str] = {}

    def _gate(self, op: str, left: str, right: str) -> str:
        if op == "XOR":
            if left == "c0":
                return right
            if right == "c0":
                return left
            if left == right:
                return "c0"
        elif op == "AND":
            if left == "c0" or right == "c0":
                return "c0"
            if left == "c1":
                return right
            if right == "c1":
                return left
            if left == right:
                return left
        else:
            raise ValueError(f"unsupported gate: {op}")
        first, second = sorted((left, right))
        key = (op, first, second)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        output = f"g{len(self.gates)}"
        self.gates.append(
            {"op": op, "a": first, "b": second, "out": output}
        )
        self.cache[key] = output
        return output

    def xor(self, left: str, right: str) -> str:
        return self._gate("XOR", left, right)

    def and_(self, left: str, right: str) -> str:
        return self._gate("AND", left, right)


def bdd_to_gates(
    order: tuple[int, ...],
    roots: list[int],
    nodes: dict[int, dict[str, int]],
) -> dict[str, Any]:
    builder = GateBuilder()
    signals: dict[int, str] = {0: "c0", 1: "c1"}
    for node_id in sorted(nodes):
        node = nodes[node_id]
        variable = f"i{node['variable']}"
        low = signals[node["low"]]
        high = signals[node["high"]]
        delta = builder.xor(low, high)
        selected_delta = builder.and_(variable, delta)
        signals[node_id] = builder.xor(low, selected_delta)
    outputs = [signals[root] for root in roots]
    gate_breakdown = {
        "AND": sum(gate["op"] == "AND" for gate in builder.gates),
        "XOR": sum(gate["op"] == "XOR" for gate in builder.gates),
    }
    return {
        "kind": "learned-shared-robdd-two-input-gate-network",
        "input_bits": INPUT_BITS,
        "output_bits": OUTPUT_BITS,
        "constants": ["c0", "c1"],
        "variable_order": list(order),
        "bdd_roots": roots,
        "bdd_nodes": [
            {"id": node_id, **nodes[node_id]} for node_id in sorted(nodes)
        ],
        "gates": builder.gates,
        "outputs": outputs,
        "stats": {
            "shared_bdd_nodes": len(nodes),
            "structurally_hashed_two_input_gates": len(builder.gates),
            "gate_breakdown": gate_breakdown,
            "naive_three_gates_per_bdd_node": 3 * len(nodes),
        },
    }


def evaluate_gate_network(network: dict[str, Any]) -> np.ndarray:
    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    signals: dict[str, np.ndarray] = {
        "c0": np.zeros(DOMAIN_SIZE, dtype=np.uint8),
        "c1": np.ones(DOMAIN_SIZE, dtype=np.uint8),
    }
    for bit in range(INPUT_BITS):
        signals[f"i{bit}"] = ((ids >> bit) & 1).astype(np.uint8)
    for gate in network["gates"]:
        left = signals[gate["a"]]
        right = signals[gate["b"]]
        if gate["op"] == "AND":
            signals[gate["out"]] = left & right
        elif gate["op"] == "XOR":
            signals[gate["out"]] = left ^ right
        else:
            raise ValueError(f"unsupported gate: {gate['op']}")
    return np.stack(
        [signals[signal] for signal in network["outputs"]],
        axis=1,
    )


def main() -> None:
    args = parse_args()
    if args.order_search_trials < 0:
        raise ValueError("order-search-trials must be non-negative")
    source = json.loads(args.source_network.read_text(encoding="utf-8"))
    truth_table = evaluate_network(source)
    order, expected_nodes = optimize_order(
        truth_table,
        args.order_search_trials,
        args.seed,
    )
    node_count, roots, nodes = build_shared_bdd(
        truth_table,
        order,
        retain_nodes=True,
    )
    if node_count != expected_nodes:
        raise AssertionError("BDD score changed during retained build")
    network = bdd_to_gates(order, roots, nodes)
    reconstructed = evaluate_gate_network(network)
    if not np.array_equal(reconstructed, truth_table):
        raise AssertionError("BDD gate network does not reproduce source")
    network["provenance"] = {
        "source_network": args.source_network.as_posix(),
        "source_network_sha256": sha256(args.source_network),
        "order_search_trials": args.order_search_trials,
        "seed": args.seed,
        "source_formula_read": False,
        "source_clean_labels_read": False,
    }
    network["verification"] = {
        "domain_size": DOMAIN_SIZE,
        "matches_source_learned_table": True,
    }
    args.output_network.parent.mkdir(parents=True, exist_ok=True)
    args.output_network.write_text(
        json.dumps(network, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output_network": args.output_network.as_posix(),
                "variable_order": list(order),
                **network["stats"],
                "output_sha256": sha256(args.output_network),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
