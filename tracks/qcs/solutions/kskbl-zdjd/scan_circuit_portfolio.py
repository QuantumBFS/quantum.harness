#!/usr/bin/env python3
"""Audit and deduplicate historical exact-circuit candidates."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from score_circuits import HERE, SPECS, base_operand, parse


def input_truths(ninputs: int) -> tuple[dict[str, int], int]:
    rows = 1 << ninputs
    universe = (1 << rows) - 1
    values: dict[str, int] = {}
    for index in range(ninputs):
        block = (1 << (1 << index)) - 1
        truth = 0
        step = 1 << (index + 1)
        for start in range(1 << index, rows, step):
            truth |= block << start
        values[f"x{index + 1}"] = truth
    return values, universe


def expected_outputs(instance: str) -> tuple[int, ...]:
    n, width, formula = SPECS[instance]
    truths = [0] * width
    mask = (1 << n) - 1
    for packed in range(1 << (2 * n)):
        result = formula(packed & mask, packed >> n)
        for bit in range(width):
            truths[bit] |= ((result >> bit) & 1) << packed
    return tuple(truths)


def audit(path: Path, expected: tuple[int, ...]):
    circuit = parse(path)
    values, universe = input_truths(circuit.ninputs)

    def get(token: str) -> int:
        value = values[base_operand(token)]
        return universe ^ value if token.startswith("~") else value

    depth = {f"x{index + 1}": 0 for index in range(circuit.ninputs)}
    for wire, op, left, right in circuit.gates:
        a, b = get(left), get(right)
        if op == "AND":
            value = a & b
        elif op == "OR":
            value = a | b
        elif op == "XOR":
            value = a ^ b
        elif op == "NAND":
            value = universe ^ (a & b)
        elif op == "NOR":
            value = universe ^ (a | b)
        else:
            value = universe ^ (a ^ b)
        values[wire] = value
        depth[wire] = 1 + max(
            depth[base_operand(left)], depth[base_operand(right)]
        )

    outputs = tuple(get(output) for output in circuit.outputs)
    correct = outputs == expected
    uses = Counter(
        base_operand(operand)
        for _, _, left, right in circuit.gates
        for operand in (left, right)
    )
    uses.update(base_operand(output) for output in circuit.outputs)
    dead = sum(not uses[wire] for wire, _, _, _ in circuit.gates)
    canonical_truths = sorted(
        min(values[wire], universe ^ values[wire])
        for wire, _, _, _ in circuit.gates
    )
    digest = hashlib.sha256()
    byte_width = 1 << max(0, circuit.ninputs - 3)
    for truth in canonical_truths:
        digest.update(truth.to_bytes(byte_width, "little"))
    return {
        "gates": len(circuit.gates),
        "depth": max(depth[base_operand(output)] for output in circuit.outputs),
        "dead": dead,
        "correct": correct,
        "fingerprint": digest.hexdigest()[:16],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", choices=tuple(SPECS))
    parser.add_argument("--max-gates", type=int, default=170)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    expected = expected_outputs(args.instance)
    prefix = args.instance
    candidates = [HERE / f"{args.instance}.txt"]
    candidates.extend((HERE / "abc-work").glob(f"{prefix}*.txt"))
    if args.instance == "mystery-C":
        candidates.extend((HERE / "abc-work").glob("c-island*.txt"))

    audited = []
    failures = 0
    for path in sorted(set(candidates)):
        try:
            result = audit(path, expected)
        except Exception:
            failures += 1
            continue
        if result["correct"] and result["gates"] <= args.max_gates:
            audited.append((path, result))

    groups: dict[str, list[tuple[Path, dict]]] = {}
    for item in audited:
        groups.setdefault(item[1]["fingerprint"], []).append(item)
    representatives = [
        min(
            group,
            key=lambda item: (
                item[1]["gates"],
                item[1]["dead"],
                item[1]["depth"],
                str(item[0]),
            ),
        )
        for group in groups.values()
    ]
    representatives.sort(
        key=lambda item: (
            item[1]["gates"],
            item[1]["dead"],
            item[1]["depth"],
            str(item[0]),
        )
    )
    print(
        f"scanned={len(set(candidates))}, parse_failures={failures}, "
        f"correct_within_limit={len(audited)}, "
        f"semantic_internal_topologies={len(representatives)}"
    )
    for index, (path, result) in enumerate(
        representatives[: args.limit], 1
    ):
        aliases = len(groups[result["fingerprint"]])
        print(
            f"{index:03d}: gates={result['gates']}, depth={result['depth']}, "
            f"dead={result['dead']}, aliases={aliases}, "
            f"fingerprint={result['fingerprint']}, path={path}"
        )


if __name__ == "__main__":
    main()
