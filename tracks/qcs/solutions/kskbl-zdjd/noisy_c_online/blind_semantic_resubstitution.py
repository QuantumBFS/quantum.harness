"""Blind full-domain resubstitution for a learned gate network.

This script reads only the learned network.  It identifies maximum fanout-free
output cones from graph structure and searches semantic fingerprints for a
zero-, one- or two-gate replacement using signals outside each cone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from compile_learned_mdfa import DOMAIN_SIZE, INPUT_BITS, evaluate_network


MASK = (1 << DOMAIN_SIZE) - 1
OPS = ("AND", "OR", "XOR")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-network", type=Path, required=True)
    parser.add_argument("--output-network", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_token(token: str) -> str:
    return token[1:] if token.startswith("~") else token


def apply_op(op: str, left: int, right: int) -> int:
    if op == "AND":
        return left & right
    if op == "OR":
        return left | right
    if op == "XOR":
        return left ^ right
    raise ValueError(f"unsupported operation: {op}")


def semantic_fingerprints(network: dict[str, Any]) -> dict[str, int]:
    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    fingerprints: dict[str, int] = {
        "c0": 0,
        "c1": MASK,
    }
    for bit in range(INPUT_BITS):
        values = ((ids >> bit) & 1).astype(np.uint8)
        fingerprints[f"i{bit}"] = int.from_bytes(
            np.packbits(values, bitorder="little").tobytes(),
            "little",
        )

    def value(token: str) -> int:
        base = fingerprints[source_token(token)]
        return base ^ MASK if token.startswith("~") else base

    for gate in network["gates"]:
        left = value(gate["a"])
        right = value(gate["b"])
        fingerprints[gate["out"]] = apply_op(gate["op"], left, right)
    return fingerprints


def fanout_consumers(network: dict[str, Any]) -> dict[str, set[str]]:
    consumers: dict[str, set[str]] = {}
    for gate in network["gates"]:
        for token in (gate["a"], gate["b"]):
            source = source_token(token)
            consumers.setdefault(source, set()).add(gate["out"])
    for output_index, token in enumerate(network["outputs"]):
        source = source_token(token)
        consumers.setdefault(source, set()).add(f"OUT{output_index}")
    return consumers


def maximum_fanout_free_cone(
    network: dict[str, Any],
    output_index: int,
) -> set[str]:
    gates = {gate["out"]: gate for gate in network["gates"]}
    consumers = fanout_consumers(network)
    output_consumer = f"OUT{output_index}"
    root = source_token(network["outputs"][output_index])
    cone: set[str] = set()
    allowed_consumers = {output_consumer}
    frontier = [root]
    while frontier:
        candidate = frontier.pop()
        if candidate not in gates or candidate in cone:
            continue
        if not consumers.get(candidate, set()) <= allowed_consumers | cone:
            continue
        cone.add(candidate)
        for token in (gates[candidate]["a"], gates[candidate]["b"]):
            frontier.append(source_token(token))

    changed = True
    while changed:
        changed = False
        for wire in tuple(cone):
            gate = gates[wire]
            for token in (gate["a"], gate["b"]):
                candidate = source_token(token)
                if candidate not in gates or candidate in cone:
                    continue
                if consumers.get(candidate, set()) <= cone:
                    cone.add(candidate)
                    changed = True
    return cone


def literal_candidates(
    fingerprints: dict[str, int],
    available_wires: list[str],
) -> list[tuple[str, int]]:
    by_semantic: dict[int, str] = {}
    for wire in available_wires:
        semantic = fingerprints[wire]
        by_semantic.setdefault(semantic, wire)
        by_semantic.setdefault(semantic ^ MASK, f"~{wire}")
    return [
        (token, semantic)
        for semantic, token in sorted(
            by_semantic.items(),
            key=lambda item: item[1],
        )
    ]


def one_gate_candidates(
    literals: list[tuple[str, int]],
) -> dict[str, dict[int, tuple[str, str, str, bool]]]:
    candidates: dict[
        str,
        dict[int, tuple[str, str, str, bool]],
    ] = {op: {} for op in OPS}
    for left_index, (left_token, left_semantic) in enumerate(literals):
        for right_token, right_semantic in literals[left_index:]:
            for op in OPS:
                semantic = apply_op(op, left_semantic, right_semantic)
                candidates[op].setdefault(
                    semantic,
                    (op, left_token, right_token, False),
                )
                candidates[op].setdefault(
                    semantic ^ MASK,
                    (op, left_token, right_token, True),
                )
    return candidates


def find_replacement(
    target: int,
    literals: list[tuple[str, int]],
) -> dict[str, Any] | None:
    for token, semantic in literals:
        if semantic == target:
            return {"kind": "wire", "token": token, "gate_count": 0}

    one_gate = one_gate_candidates(literals)
    for op in OPS:
        expression = one_gate[op].get(target)
        if expression is not None:
            return {
                "kind": "one_gate",
                "first": expression,
                "gate_count": 1,
            }

    for first_op in ("OR", "XOR", "AND"):
        candidates = one_gate[first_op]
        for outer_op in ("AND", "XOR", "OR"):
            for literal_token, literal_semantic in literals:
                if outer_op == "XOR":
                    required = target ^ literal_semantic
                    expression = candidates.get(required)
                    if expression is not None:
                        return {
                            "kind": "two_gate",
                            "first": expression,
                            "outer_op": outer_op,
                            "outer_literal": literal_token,
                            "gate_count": 2,
                        }
                    continue
                if outer_op == "AND":
                    if target & (literal_semantic ^ MASK):
                        continue
                elif outer_op == "OR":
                    if literal_semantic & (target ^ MASK):
                        continue
                for semantic, expression in candidates.items():
                    if apply_op(
                        outer_op,
                        semantic,
                        literal_semantic,
                    ) == target:
                        return {
                            "kind": "two_gate",
                            "first": expression,
                            "outer_op": outer_op,
                            "outer_literal": literal_token,
                            "gate_count": 2,
                        }
    return None


def instantiate_replacement(
    network: dict[str, Any],
    output_index: int,
    cone: set[str],
    replacement: dict[str, Any],
) -> dict[str, Any]:
    retained_gates = [
        gate for gate in network["gates"] if gate["out"] not in cone
    ]
    outputs = list(network["outputs"])
    if replacement["kind"] == "wire":
        outputs[output_index] = replacement["token"]
    else:
        first_op, first_left, first_right, first_inverted = replacement[
            "first"
        ]
        first_output = "r0"
        retained_gates.append(
            {
                "op": first_op,
                "a": first_left,
                "b": first_right,
                "out": first_output,
            }
        )
        first_token = (
            f"~{first_output}" if first_inverted else first_output
        )
        if replacement["kind"] == "one_gate":
            outputs[output_index] = first_token
        else:
            second_output = "r1"
            retained_gates.append(
                {
                    "op": replacement["outer_op"],
                    "a": first_token,
                    "b": replacement["outer_literal"],
                    "out": second_output,
                }
            )
            outputs[output_index] = second_output
    optimized = {
        **network,
        "kind": "learned-blind-semantically-resubstituted-network",
        "gates": retained_gates,
        "outputs": outputs,
    }
    gate_breakdown = Counter(gate["op"] for gate in retained_gates)
    optimized["stats"] = {
        **network.get("stats", {}),
        "pre_resubstitution_gates": len(network["gates"]),
        "two_input_gates": len(retained_gates),
        "gate_breakdown": dict(sorted(gate_breakdown.items())),
        "blind_semantic_resubstitution": True,
    }
    optimized["optimization"] = {
        "output_index": output_index,
        "removed_cone": sorted(cone),
        "removed_gate_count": len(cone),
        "replacement": replacement,
        "replacement_gate_count": replacement["gate_count"],
        "net_gate_reduction": len(cone) - replacement["gate_count"],
        "search_used_only_source_network_semantics": True,
    }
    return optimized


def main() -> None:
    args = parse_args()
    network = json.loads(args.source_network.read_text(encoding="utf-8"))
    fingerprints = semantic_fingerprints(network)
    gate_wires = [gate["out"] for gate in network["gates"]]
    base_wires = [f"i{bit}" for bit in range(INPUT_BITS)] + ["c0", "c1"]
    source_prediction = evaluate_network(network)

    best: tuple[int, dict[str, Any]] | None = None
    search_records = []
    output_cones = sorted(
        (
            (
                output_index,
                output_token,
                maximum_fanout_free_cone(network, output_index),
            )
            for output_index, output_token in enumerate(network["outputs"])
        ),
        key=lambda item: len(item[2]),
        reverse=True,
    )
    for output_index, output_token, cone in output_cones:
        if not cone:
            continue
        if best is not None and len(cone) <= best[0]:
            search_records.append(
                {
                    "output_index": output_index,
                    "cone_gate_count": len(cone),
                    "replacement_gate_count": None,
                    "skipped_after_larger_reduction": True,
                }
            )
            continue
        available = base_wires + [
            wire for wire in gate_wires if wire not in cone
        ]
        literals = literal_candidates(fingerprints, available)
        target = fingerprints[source_token(output_token)]
        if output_token.startswith("~"):
            target ^= MASK
        replacement = find_replacement(target, literals)
        record = {
            "output_index": output_index,
            "cone_gate_count": len(cone),
            "replacement_gate_count": (
                None if replacement is None else replacement["gate_count"]
            ),
        }
        search_records.append(record)
        if replacement is None:
            continue
        reduction = len(cone) - replacement["gate_count"]
        if reduction <= 0:
            continue
        optimized = instantiate_replacement(
            network,
            output_index,
            cone,
            replacement,
        )
        optimized_prediction = evaluate_network(optimized)
        if not np.array_equal(optimized_prediction, source_prediction):
            raise AssertionError("candidate replacement changed semantics")
        if best is None or reduction > best[0]:
            best = (reduction, optimized)

    if best is None:
        raise RuntimeError("no semantics-preserving reduction found")
    reduction, optimized = best
    optimized["provenance"] = {
        "source_network": args.source_network.as_posix(),
        "source_network_sha256": sha256(args.source_network),
        "page_one_network_read": False,
        "rewrite_template_seeded": False,
        "formula_read": False,
    }
    optimized["verification"] = {
        "domain_size": DOMAIN_SIZE,
        "matches_source_network": True,
        "source_gate_count": len(network["gates"]),
        "optimized_gate_count": len(optimized["gates"]),
        "gate_reduction": reduction,
        "search_records": search_records,
    }
    args.output_network.parent.mkdir(parents=True, exist_ok=True)
    args.output_network.write_text(
        json.dumps(optimized, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output_network": args.output_network.as_posix(),
                "source_gates": len(network["gates"]),
                "optimized_gates": len(optimized["gates"]),
                "optimization": optimized["optimization"],
                "search_records": search_records,
                "output_sha256": sha256(args.output_network),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
