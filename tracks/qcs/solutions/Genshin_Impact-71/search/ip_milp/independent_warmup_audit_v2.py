"""Independent exhaustive audit of the warmup MILP minimum-size claims.

This file deliberately does not import SciPy or exact_milp.py.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path


OPS = ("AND", "OR", "XOR", "NAND", "NOR", "XNOR")
MASK = (1 << 16) - 1


def op(name: str, left: int, right: int) -> int:
    if name == "AND":
        return left & right
    if name == "OR":
        return left | right
    if name == "XOR":
        return left ^ right
    if name == "NAND":
        return MASK ^ (left & right)
    if name == "NOR":
        return MASK ^ (left | right)
    if name == "XNOR":
        return MASK ^ (left ^ right)
    raise ValueError(name)


def table(bit: int) -> int:
    return sum(((row >> bit) & 1) << row for row in range(16))


def literal_tables(bases: list[int]) -> list[int]:
    return [value for base in bases for value in (base, MASK ^ base)]


def reachable_with_two_gates(target: int, static_bases: list[int]) -> tuple[bool, int]:
    static_literals = literal_tables(static_bases)
    checked = 0
    for left_index, right_index in itertools.combinations_with_replacement(
        range(len(static_literals)), 2
    ):
        left, right = static_literals[left_index], static_literals[right_index]
        for first_op in OPS:
            first = op(first_op, left, right)
            second_literals = static_literals + [first, MASK ^ first]
            for second_left, second_right in itertools.combinations_with_replacement(
                range(len(second_literals)), 2
            ):
                for second_op in OPS:
                    checked += 1
                    if op(
                        second_op,
                        second_literals[second_left],
                        second_literals[second_right],
                    ) == target:
                        return True, checked
    return False, checked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    x0, x1, y0, y1 = map(table, range(4))
    targets = {
        "add_bit1": x1 ^ y1 ^ (x0 & y0),
        "mul_bit1": (x1 & y0) ^ (x0 & y1),
    }
    records = {}
    for name, target in targets.items():
        reachable, checked = reachable_with_two_gates(
            target, [x0, x1, y0, y1]
        )
        records[name] = {
            "reachable_with_at_most_two_gates": reachable,
            "complete_second_gate_configurations_checked": checked,
        }
        print(name, reachable, checked, flush=True)
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {
        "schema": "issue71-independent-warmup-enumeration-v2",
        "domain_rows": 16,
        "basis": list(OPS),
        "free_literal_phase": True,
        "commutative_port_ordering": True,
        "source_sha256": source_hash,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
