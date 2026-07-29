#!/usr/bin/env python3
"""Search exact truth tables for gate-level resubstitutions missed by ABC."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from enumerate_mffcs import maximal_fanout_free_cone
from score_circuits import HERE, SPECS, base_operand, parse


def all_truth_tables(name: str, source: Path):
    n, _, _ = SPECS[name]
    circuit = parse(source)
    rows = 1 << (2 * n)
    universe = (1 << rows) - 1
    values: dict[str, int] = {}
    for index in range(circuit.ninputs):
        value = 0
        for packed in range(rows):
            value |= ((packed >> index) & 1) << packed
        values[f"x{index + 1}"] = value

    def get(token: str) -> int:
        value = values[base_operand(token)]
        return universe ^ value if token.startswith("~") else value

    for wire, op, a, b in circuit.gates:
        av, bv = get(a), get(b)
        if op == "AND":
            value = av & bv
        elif op == "OR":
            value = av | bv
        elif op == "XOR":
            value = av ^ bv
        elif op == "NAND":
            value = universe ^ (av & bv)
        elif op == "NOR":
            value = universe ^ (av | bv)
        else:
            value = universe ^ (av ^ bv)
        values[wire] = value
    return circuit, values, universe


def descendants(circuit, root: str) -> set[str]:
    consumers: dict[str, set[str]] = defaultdict(set)
    for wire, _, a, b in circuit.gates:
        consumers[base_operand(a)].add(wire)
        consumers[base_operand(b)].add(wire)
    result: set[str] = set()
    stack = [root]
    while stack:
        wire = stack.pop()
        for consumer in consumers[wire]:
            if consumer not in result:
                result.add(consumer)
                stack.append(consumer)
    return result


def one_gate_functions(
    available: list[str], values: dict[str, int], universe: int
) -> dict[int, tuple[str, str, str]]:
    """Return one representative expression for every one-gate function."""
    functions: dict[int, tuple[str, str, str]] = {}
    for left_index, left in enumerate(available):
        left_value = values[left]
        for right in available[left_index + 1 :]:
            right_value = values[right]
            xor = left_value ^ right_value
            functions.setdefault(xor, ("XOR", left, right))
            functions.setdefault(universe ^ xor, ("XNOR", left, right))
            for left_negated in (False, True):
                av = universe ^ left_value if left_negated else left_value
                a_token = f"~{left}" if left_negated else left
                for right_negated in (False, True):
                    bv = universe ^ right_value if right_negated else right_value
                    b_token = f"~{right}" if right_negated else right
                    product = av & bv
                    functions.setdefault(product, ("AND", a_token, b_token))
                    functions.setdefault(
                        universe ^ product, ("NAND", a_token, b_token)
                    )
    functions.pop(0, None)
    functions.pop(universe, None)
    return functions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", choices=sorted(SPECS))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--min-mffc", type=int, default=2)
    args = parser.parse_args()
    source = args.source or (HERE / f"{args.instance}.txt")
    circuit, values, universe = all_truth_tables(args.instance, source)
    inputs = [f"x{index}" for index in range(1, circuit.ninputs + 1)]
    wires = [wire for wire, _, _, _ in circuit.gates]

    tested = 0
    for root in wires:
        cone = maximal_fanout_free_cone(circuit, root)
        if len(cone) < args.min_mffc:
            continue
        unavailable = cone | descendants(circuit, root)
        available = inputs + [wire for wire in wires if wire not in unavailable]
        functions = one_gate_functions(available, values, universe)
        tested += 1
        target = values[root]

        if target in functions:
            print(
                f"SAVE {len(cone) - 1}: {root} MFFC={len(cone)} -> "
                f"{functions[target]}"
            )
            continue

        if len(cone) < 3:
            continue
        for divisor in available:
            required = target ^ values[divisor]
            if required in functions:
                print(
                    f"SAVE {len(cone) - 2}: {root} MFFC={len(cone)} -> "
                    f"temp={functions[required]}, then XOR temp {divisor}"
                )
                break
        else:
            found_and = False
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
                        requirements = (
                            (desired, False),
                            (mask ^ desired, True),
                        )
                        for required, temp_negated in requirements:
                            for function, expression in functions.items():
                                if function & mask != required:
                                    continue
                                op = "NAND" if output_negated else "AND"
                                temp_token = "~temp" if temp_negated else "temp"
                                print(
                                    f"SAVE {len(cone) - 2}: {root} "
                                    f"MFFC={len(cone)} -> temp={expression}, "
                                    f"then {op} {temp_token} {divisor_token}"
                                )
                                found_and = True
                                break
                            if found_and:
                                break
                        if found_and:
                            break
                    if found_and:
                        break
                if found_and:
                    break

        if len(cone) < 4:
            continue
        for first_function, first_expression in functions.items():
            second_function = target ^ first_function
            if second_function not in functions:
                continue
            print(
                f"SAVE {len(cone) - 3}: {root} MFFC={len(cone)} -> "
                f"left={first_expression}, right={functions[second_function]}, "
                "then XOR left right"
            )
            break

    print(f"tested_roots={tested}")


if __name__ == "__main__":
    main()
