#!/usr/bin/env python3
"""Independent strict parser and exhaustive auditor for generated BDD netlists."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence

from decision_diagram_learn import INSTANCE_SPECS, bits_for_xy, truth_value


NAME_RE = re.compile(r"(~)?(x[1-9][0-9]*|w[1-9][0-9]*)\Z")
GATE_RE = re.compile(
    r"(w[1-9][0-9]*) = (AND|OR|XOR|NAND|NOR|XNOR) "
    r"(~?(?:x[1-9][0-9]*|w[1-9][0-9]*)) "
    r"(~?(?:x[1-9][0-9]*|w[1-9][0-9]*))\Z"
)


def parse_operand(token: str, values: dict[str, int]) -> int:
    match = NAME_RE.fullmatch(token)
    if match is None:
        raise ValueError(f"invalid operand {token!r}")
    inverted, name = match.groups()
    if name not in values:
        raise ValueError(f"use before definition: {name}")
    value = values[name]
    return 1 - value if inverted else value


def parse_netlist(path: Path) -> tuple[int, list[tuple[str, str, str, str]], list[str]]:
    n_inputs: int | None = None
    gates: list[tuple[str, str, str, str]] = []
    outputs: list[str] | None = None
    defined: set[str] = set()
    with path.open("r", encoding="ascii", newline="") as handle:
        for line_no, raw in enumerate(handle, 1):
            line = raw.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            if n_inputs is None:
                pieces = line.split(" ")
                if len(pieces) != 2 or pieces[0] != "INPUTS" or not pieces[1].isdigit():
                    raise ValueError(f"{path}:{line_no}: expected INPUTS")
                n_inputs = int(pieces[1])
                if n_inputs <= 0:
                    raise ValueError(f"{path}:{line_no}: invalid input count")
                defined.update(f"x{i}" for i in range(1, n_inputs + 1))
                continue
            if line.startswith("OUTPUTS "):
                if outputs is not None:
                    raise ValueError(f"{path}:{line_no}: duplicate OUTPUTS")
                outputs = line.split(" ")[1:]
                if not outputs:
                    raise ValueError(f"{path}:{line_no}: no outputs")
                for operand in outputs:
                    match = NAME_RE.fullmatch(operand)
                    if match is None or match.group(2) not in defined:
                        raise ValueError(f"{path}:{line_no}: invalid output {operand!r}")
                continue
            if outputs is not None:
                raise ValueError(f"{path}:{line_no}: content after OUTPUTS")
            match = GATE_RE.fullmatch(line)
            if match is None:
                raise ValueError(f"{path}:{line_no}: malformed gate")
            wire, op, left, right = match.groups()
            if wire in defined:
                raise ValueError(f"{path}:{line_no}: duplicate wire {wire}")
            for operand in (left, right):
                operand_name = operand[1:] if operand.startswith("~") else operand
                if operand_name not in defined:
                    raise ValueError(f"{path}:{line_no}: use before definition {operand_name}")
            gates.append((wire, op, left, right))
            defined.add(wire)
    if n_inputs is None or outputs is None:
        raise ValueError(f"{path}: incomplete netlist")
    return n_inputs, gates, outputs


def evaluate(
    n_inputs: int,
    gates: Sequence[tuple[str, str, str, str]],
    outputs: Sequence[str],
    bits: Sequence[int],
) -> tuple[int, ...]:
    if len(bits) != n_inputs:
        raise ValueError("wrong input length")
    values = {f"x{i + 1}": bit for i, bit in enumerate(bits)}
    for wire, op, left_text, right_text in gates:
        left = parse_operand(left_text, values)
        right = parse_operand(right_text, values)
        if op == "AND":
            value = left & right
        elif op == "OR":
            value = left | right
        elif op == "XOR":
            value = left ^ right
        elif op == "NAND":
            value = 1 - (left & right)
        elif op == "NOR":
            value = 1 - (left | right)
        elif op == "XNOR":
            value = 1 - (left ^ right)
        else:
            raise AssertionError(op)
        values[wire] = value
    return tuple(parse_operand(output, values) for output in outputs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", choices=sorted(INSTANCE_SPECS), required=True)
    parser.add_argument("--netlist", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    kind, n, m = INSTANCE_SPECS[args.instance]
    n_inputs, gates, outputs = parse_netlist(args.netlist)
    if n_inputs != 2 * n or len(outputs) != m:
        raise ValueError("netlist arity does not match instance")
    total = 1 << (2 * n)
    mask = (1 << n) - 1
    exact = 0
    correct_bits = 0
    failures = []
    for packed in range(total):
        x, y = packed & mask, packed >> n
        bits = bits_for_xy(x, y, n)
        predicted = evaluate(n_inputs, gates, outputs, bits)
        value = truth_value(kind, x, y)
        expected = tuple((value >> bit) & 1 for bit in range(m))
        exact += int(predicted == expected)
        correct_bits += sum(a == b for a, b in zip(predicted, expected))
        if predicted != expected and len(failures) < 8:
            failures.append(
                {
                    "x": x,
                    "y": y,
                    "predicted": "".join(map(str, predicted)),
                    "expected": "".join(map(str, expected)),
                }
            )
    report = {
        "schema": "occam71-independent-netlist-audit-v1",
        "instance": args.instance,
        "gates": len(gates),
        "total_rows": total,
        "exact_rows": exact,
        "row_accuracy": exact / total,
        "correct_bits": correct_bits,
        "total_bits": total * m,
        "bit_accuracy": correct_bits / (total * m),
        "first_failures": failures,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "ascii")
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if exact == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
