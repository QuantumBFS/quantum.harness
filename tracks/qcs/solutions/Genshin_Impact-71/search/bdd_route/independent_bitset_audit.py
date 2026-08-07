#!/usr/bin/env python3
"""Independent strict netlist parser with exhaustive bit-parallel simulation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SPECS = {
    "practice-add-n4": ("add", 4, 5),
    "practice-mul-n4": ("mul", 4, 8),
    "mystery-A": ("add", 8, 9),
    "mystery-B": ("absdiff", 7, 7),
    "mystery-C": ("mul", 6, 12),
    "mystery-D": ("sos", 5, 11),
}
OPERAND = re.compile(r"(~)?(x[1-9][0-9]*|w[1-9][0-9]*)\Z")
GATE = re.compile(
    r"(w[1-9][0-9]*) = (AND|OR|XOR|NAND|NOR|XNOR) "
    r"(~?(?:x[1-9][0-9]*|w[1-9][0-9]*)) "
    r"(~?(?:x[1-9][0-9]*|w[1-9][0-9]*))\Z"
)


def parse(path: Path) -> tuple[int, list[tuple[str, str, str, str]], list[str]]:
    n_inputs = None
    gates = []
    outputs = None
    defined = set()
    with path.open("r", encoding="ascii", newline="") as handle:
        for line_no, raw in enumerate(handle, 1):
            line = raw.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            if n_inputs is None:
                fields = line.split(" ")
                if len(fields) != 2 or fields[0] != "INPUTS" or not fields[1].isdigit():
                    raise ValueError(f"{path}:{line_no}: malformed INPUTS")
                n_inputs = int(fields[1])
                if n_inputs <= 0:
                    raise ValueError(f"{path}:{line_no}: nonpositive INPUTS")
                defined = {f"x{i}" for i in range(1, n_inputs + 1)}
                continue
            if line.startswith("OUTPUTS "):
                if outputs is not None:
                    raise ValueError(f"{path}:{line_no}: duplicate OUTPUTS")
                outputs = line.split(" ")[1:]
                for token in outputs:
                    match = OPERAND.fullmatch(token)
                    if match is None or match.group(2) not in defined:
                        raise ValueError(f"{path}:{line_no}: invalid output")
                continue
            if outputs is not None:
                raise ValueError(f"{path}:{line_no}: content after OUTPUTS")
            match = GATE.fullmatch(line)
            if match is None:
                raise ValueError(f"{path}:{line_no}: malformed gate")
            wire, op, left, right = match.groups()
            if wire in defined:
                raise ValueError(f"{path}:{line_no}: duplicate wire")
            for token in (left, right):
                name = token[1:] if token.startswith("~") else token
                if name not in defined:
                    raise ValueError(f"{path}:{line_no}: use before definition")
            gates.append((wire, op, left, right))
            defined.add(wire)
    if n_inputs is None or outputs is None:
        raise ValueError(f"{path}: incomplete netlist")
    return n_inputs, gates, outputs


def truth_function(kind: str, x: int, y: int) -> int:
    if kind == "add":
        return x + y
    if kind == "mul":
        return x * y
    if kind == "absdiff":
        return abs(x - y)
    if kind == "sos":
        return x * x + y * y
    raise AssertionError(kind)


def operand_value(token: str, values: dict[str, int], domain_mask: int) -> int:
    match = OPERAND.fullmatch(token)
    if match is None:
        raise ValueError("invalid operand")
    inverted, name = match.groups()
    value = values[name]
    return (value ^ domain_mask) if inverted else value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", choices=sorted(SPECS), required=True)
    parser.add_argument("--netlist", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    kind, n, m = SPECS[args.instance]
    n_inputs, gates, outputs = parse(args.netlist)
    if n_inputs != 2 * n or len(outputs) != m:
        raise ValueError("netlist arity mismatch")
    total = 1 << n_inputs
    domain_mask = (1 << total) - 1
    values = {}
    for variable in range(n_inputs):
        truth = 0
        for row in range(total):
            if (row >> variable) & 1:
                truth |= 1 << row
        values[f"x{variable + 1}"] = truth
    for wire, op, left_text, right_text in gates:
        left = operand_value(left_text, values, domain_mask)
        right = operand_value(right_text, values, domain_mask)
        if op == "AND":
            value = left & right
        elif op == "OR":
            value = left | right
        elif op == "XOR":
            value = left ^ right
        elif op == "NAND":
            value = (left & right) ^ domain_mask
        elif op == "NOR":
            value = (left | right) ^ domain_mask
        elif op == "XNOR":
            value = (left ^ right) ^ domain_mask
        else:
            raise AssertionError(op)
        values[wire] = value
    predicted = [operand_value(token, values, domain_mask) for token in outputs]
    expected = [0] * m
    input_mask = (1 << n) - 1
    for row in range(total):
        x, y = row & input_mask, row >> n
        result = truth_function(kind, x, y)
        for bit in range(m):
            if (result >> bit) & 1:
                expected[bit] |= 1 << row
    bad = 0
    bit_errors = 0
    for actual, wanted in zip(predicted, expected):
        difference = actual ^ wanted
        bad |= difference
        bit_errors += difference.bit_count()
    exact = total - bad.bit_count()
    failures = []
    remaining = bad
    while remaining and len(failures) < 8:
        low_bit = remaining & -remaining
        row = low_bit.bit_length() - 1
        x, y = row & input_mask, row >> n
        actual_text = "".join(str((value >> row) & 1) for value in predicted)
        expected_text = "".join(str((value >> row) & 1) for value in expected)
        failures.append(
            {"x": x, "y": y, "predicted": actual_text, "expected": expected_text}
        )
        remaining ^= low_bit
    report = {
        "schema": "occam71-independent-bitset-audit-v1",
        "instance": args.instance,
        "netlist_sha256": hashlib.sha256(args.netlist.read_bytes()).hexdigest(),
        "gates": len(gates),
        "total_rows": total,
        "exact_rows": exact,
        "row_accuracy": exact / total,
        "correct_bits": total * m - bit_errors,
        "total_bits": total * m,
        "bit_accuracy": (total * m - bit_errors) / (total * m),
        "first_failures": failures,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "ascii")
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if exact == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
