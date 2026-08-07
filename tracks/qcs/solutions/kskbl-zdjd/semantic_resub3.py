#!/usr/bin/env python3
"""Search complete three-gate chain resubstitutions on reachable states."""

from __future__ import annotations

import argparse
from pathlib import Path

from enumerate_mffcs import maximal_fanout_free_cone
from score_circuits import HERE, SPECS
from semantic_resub import (
    all_truth_tables,
    descendants,
    one_gate_functions,
)


def two_gate_candidates(
    first_value: int,
    first_expression,
    divisor: str,
    divisor_value: int,
    universe: int,
):
    xor = first_value ^ divisor_value
    yield xor, (first_expression, ("XOR", "temp1", divisor))
    yield universe ^ xor, (
        first_expression,
        ("XNOR", "temp1", divisor),
    )
    for first_negated in (False, True):
        left = universe ^ first_value if first_negated else first_value
        left_token = "~temp1" if first_negated else "temp1"
        for divisor_negated in (False, True):
            right = (
                universe ^ divisor_value
                if divisor_negated
                else divisor_value
            )
            right_token = f"~{divisor}" if divisor_negated else divisor
            product = left & right
            yield product, (
                first_expression,
                ("AND", left_token, right_token),
            )
            yield universe ^ product, (
                first_expression,
                ("NAND", left_token, right_token),
            )


def build_final_matcher(
    target: int,
    available: list[str],
    values: dict[str, int],
    universe: int,
):
    xor_divisors: dict[int, str] = {}
    for divisor in available:
        divisor_value = values[divisor]
        xor_divisors.setdefault(divisor_value, divisor)
        xor_divisors.setdefault(universe ^ divisor_value, f"~{divisor}")
    and_constraints = []
    for divisor in available:
        divisor_value = values[divisor]
        for divisor_negated in (False, True):
            mask = (
                universe ^ divisor_value
                if divisor_negated
                else divisor_value
            )
            divisor_token = (
                f"~{divisor}" if divisor_negated else divisor
            )
            for output_negated in (False, True):
                desired = universe ^ target if output_negated else target
                if desired & (universe ^ mask):
                    continue
                and_constraints.append(
                    (
                        mask,
                        desired,
                        "NAND" if output_negated else "AND",
                        divisor_token,
                    )
                )
    return xor_divisors, and_constraints


def final_match(
    value: int,
    target: int,
    universe: int,
    xor_divisors: dict[int, str],
    and_constraints,
):
    divisor = xor_divisors.get(target ^ value)
    if divisor is not None:
        return "XOR", "temp2", divisor
    for mask, desired, op, divisor_token in and_constraints:
        if (value & mask) == desired:
            return op, "temp2", divisor_token
        if ((universe ^ value) & mask) == desired:
            return op, "~temp2", divisor_token
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", choices=tuple(SPECS))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--min-mffc", type=int, default=4)
    args = parser.parse_args()

    source = args.source or (HERE / f"{args.instance}.txt")
    circuit, values, universe = all_truth_tables(args.instance, source)
    inputs = [f"x{index}" for index in range(1, circuit.ninputs + 1)]
    wires = [wire for wire, _, _, _ in circuit.gates]
    tested_roots = 0
    generated = 0

    for root in wires:
        cone = maximal_fanout_free_cone(circuit, root)
        if len(cone) < args.min_mffc:
            continue
        unavailable = cone | descendants(circuit, root)
        available = inputs + [
            wire for wire in wires if wire not in unavailable
        ]
        functions = one_gate_functions(available, values, universe)
        target = values[root]
        xor_divisors, and_constraints = build_final_matcher(
            target, available, values, universe
        )
        tested_roots += 1
        found = False

        for first_value, first_expression in functions.items():
            for divisor in available:
                for second_value, expressions in two_gate_candidates(
                    first_value,
                    first_expression,
                    divisor,
                    values[divisor],
                    universe,
                ):
                    generated += 1
                    final = final_match(
                        second_value,
                        target,
                        universe,
                        xor_divisors,
                        and_constraints,
                    )
                    if final is None:
                        continue
                    print(
                        f"SAVE {len(cone) - 3}: root={root} "
                        f"MFFC={len(cone)} temp1={expressions[0]} "
                        f"temp2={expressions[1]} final={final}"
                    )
                    found = True
                    break
                else:
                    continue
                break
            else:
                continue
            break
        print(f"root={root} MFFC={len(cone)} found={found}")
    print(f"tested_roots={tested_roots} generated={generated}")


if __name__ == "__main__":
    main()
