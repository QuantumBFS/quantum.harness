#!/usr/bin/env python3
"""Independent exhaustive audit for an Occam mystery-C candidate.

This strict parser/evaluator imports no search, bridge, reference-netlist, or
eSLIM code.  It checks the candidate directly against z = x*y for all 64*64
assignments and reports dead, constant, duplicate, and complementary gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


GATE_RE = re.compile(
    r"^(w[1-9][0-9]*) = (AND|OR|XOR|NAND|NOR|XNOR) "
    r"(~?(?:x|w)[1-9][0-9]*) (~?(?:x|w)[1-9][0-9]*)$"
)
TOKEN_RE = re.compile(r"^(~)?([xw])([1-9][0-9]*)$")


@dataclass(frozen=True)
class Gate:
    out: str
    op: str
    left: str
    right: str


def parse_token(token: str) -> tuple[bool, str, int]:
    match = TOKEN_RE.fullmatch(token)
    if match is None:
        raise ValueError(f"invalid token {token!r}")
    return bool(match.group(1)), match.group(2), int(match.group(3))


def parse_candidate(path: Path) -> tuple[int, list[Gate], list[str], bytes]:
    raw = path.read_bytes()
    if not raw:
        raise ValueError("empty candidate")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("candidate must be strict ASCII") from exc
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or not lines[0].startswith("INPUTS "):
        raise ValueError("missing INPUTS header")
    fields = lines[0].split()
    if len(fields) != 2 or not fields[1].isdigit():
        raise ValueError("invalid INPUTS header")
    n_inputs = int(fields[1])
    if n_inputs != 12:
        raise ValueError(f"mystery C requires 12 inputs, got {n_inputs}")

    gates: list[Gate] = []
    defined = {f"x{i}" for i in range(1, n_inputs + 1)}
    outputs: list[str] | None = None
    for line_number, line in enumerate(lines[1:], start=2):
        if line.startswith("OUTPUTS "):
            if outputs is not None or line_number != len(lines):
                raise ValueError("OUTPUTS must occur exactly once at EOF")
            outputs = line.split()[1:]
            continue
        if outputs is not None:
            raise ValueError("gate after OUTPUTS")
        match = GATE_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid gate syntax on line {line_number}")
        gate = Gate(*match.groups())
        if gate.out in defined:
            raise ValueError(f"duplicate signal {gate.out}")
        expected_out = f"w{len(gates) + 1}"
        if gate.out != expected_out:
            raise ValueError(
                f"non-canonical wire order: expected {expected_out}, got {gate.out}"
            )
        for token in (gate.left, gate.right):
            _, prefix, index = parse_token(token)
            base = f"{prefix}{index}"
            if base not in defined:
                raise ValueError(f"forward or unknown reference {token}")
        gates.append(gate)
        defined.add(gate.out)

    if outputs is None:
        raise ValueError("missing OUTPUTS")
    if len(outputs) != 12:
        raise ValueError(f"mystery C requires 12 outputs, got {len(outputs)}")
    for token in outputs:
        _, prefix, index = parse_token(token)
        if f"{prefix}{index}" not in defined:
            raise ValueError(f"unknown output {token}")
    return n_inputs, gates, outputs, raw


def read_token(token: str, values: dict[str, int]) -> int:
    inverted, prefix, index = parse_token(token)
    return values[f"{prefix}{index}"] ^ int(inverted)


def apply_gate(op: str, left: int, right: int) -> int:
    if op == "AND":
        return left & right
    if op == "OR":
        return left | right
    if op == "XOR":
        return left ^ right
    if op == "NAND":
        return 1 ^ (left & right)
    if op == "NOR":
        return 1 ^ (left | right)
    if op == "XNOR":
        return 1 ^ (left ^ right)
    raise AssertionError(op)


def exhaustive_audit(
    gates: list[Gate],
    outputs: list[str],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    mismatches: list[dict[str, object]] = []
    truth_tables = {f"x{i}": 0 for i in range(1, 13)}
    truth_tables.update({gate.out: 0 for gate in gates})
    for x in range(64):
        for y in range(64):
            row = x | (y << 6)
            values = {
                **{f"x{i + 1}": (x >> i) & 1 for i in range(6)},
                **{f"x{i + 7}": (y >> i) & 1 for i in range(6)},
            }
            for name, bit in values.items():
                truth_tables[name] |= bit << row
            for gate in gates:
                left = read_token(gate.left, values)
                right = read_token(gate.right, values)
                values[gate.out] = apply_gate(gate.op, left, right)
                truth_tables[gate.out] |= values[gate.out] << row
            actual = sum(
                read_token(token, values) << bit
                for bit, token in enumerate(outputs)
            )
            expected = x * y
            if actual != expected and len(mismatches) < 16:
                mismatches.append(
                    {
                        "x": x,
                        "y": y,
                        "expected": expected,
                        "actual": actual,
                    }
                )
    return mismatches, truth_tables


def structural_audit(
    gates: list[Gate],
    outputs: list[str],
    truth_tables: dict[str, int],
) -> dict[str, object]:
    gate_by_out = {gate.out: gate for gate in gates}
    live: set[str] = set()
    stack = [parse_token(token)[1:] for token in outputs]
    while stack:
        prefix, index = stack.pop()
        name = f"{prefix}{index}"
        if name in live or name.startswith("x"):
            continue
        live.add(name)
        gate = gate_by_out[name]
        for token in (gate.left, gate.right):
            _, child_prefix, child_index = parse_token(token)
            stack.append((child_prefix, child_index))
    dead = sorted(set(gate_by_out) - live, key=lambda name: int(name[1:]))

    mask = (1 << 4096) - 1
    seen: dict[int, str] = {}
    duplicates: list[tuple[str, str]] = []
    complements: list[tuple[str, str]] = []
    constants: list[str] = []
    for gate in gates:
        table = truth_tables[gate.out]
        if table in (0, mask):
            constants.append(gate.out)
        if table in seen:
            duplicates.append((gate.out, seen[table]))
        complement = table ^ mask
        if complement in seen:
            complements.append((gate.out, seen[complement]))
        seen.setdefault(table, gate.out)
    return {
        "dead_gates": dead,
        "constant_gates": constants,
        "duplicate_gate_functions": duplicates,
        "complement_gate_functions": complements,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    n_inputs, gates, outputs, raw = parse_candidate(args.candidate)
    mismatches, truth_tables = exhaustive_audit(gates, outputs)
    structure = structural_audit(gates, outputs, truth_tables)
    report = {
        "candidate": str(args.candidate),
        "candidate_sha256": hashlib.sha256(raw).hexdigest(),
        "inputs": n_inputs,
        "outputs": len(outputs),
        "gates": len(gates),
        "assignments": 4096,
        "output_bits_checked": 4096 * 12,
        "formula": "x*y",
        "equivalent": not mismatches,
        "mismatches": mismatches,
        "structure": structure,
    }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    if mismatches or structure["dead_gates"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
