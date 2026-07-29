#!/usr/bin/env python3
"""Independently parse and exhaustively score the four submitted netlists."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


HERE = Path(__file__).parent
DATASETS = HERE / "package" / "occam-circuit" / "datasets"
ALLOWED = {"AND", "OR", "XOR", "NAND", "NOR", "XNOR"}


@dataclass(frozen=True)
class ParsedCircuit:
    ninputs: int
    gates: list[tuple[str, str, str, str]]
    outputs: list[str]


def base_operand(token: str) -> str:
    return token[1:] if token.startswith("~") else token


def parse(path: Path) -> ParsedCircuit:
    ninputs = 0
    gates: list[tuple[str, str, str, str]] = []
    outputs: list[str] = []
    defined: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        if tokens[0] == "INPUTS":
            if len(tokens) != 2:
                raise ValueError(f"{path}:{line_number}: malformed INPUTS")
            ninputs = int(tokens[1])
            defined.update(f"x{i}" for i in range(1, ninputs + 1))
        elif tokens[0] == "OUTPUTS":
            outputs = tokens[1:]
        else:
            if len(tokens) != 5 or tokens[1] != "=":
                raise ValueError(f"{path}:{line_number}: malformed gate")
            wire, op, a, b = tokens[0], tokens[2], tokens[3], tokens[4]
            if op not in ALLOWED:
                raise ValueError(f"{path}:{line_number}: unsupported operation {op}")
            if wire in defined:
                raise ValueError(f"{path}:{line_number}: duplicate wire {wire}")
            for operand in (a, b):
                if base_operand(operand) not in defined:
                    raise ValueError(
                        f"{path}:{line_number}: undefined operand {operand}"
                    )
            gates.append((wire, op, a, b))
            defined.add(wire)
    if not ninputs or not outputs:
        raise ValueError(f"{path}: missing INPUTS or OUTPUTS")
    for output in outputs:
        if base_operand(output) not in defined:
            raise ValueError(f"{path}: undefined output {output}")
    return ParsedCircuit(ninputs, gates, outputs)


def evaluate(circuit: ParsedCircuit, input_value: int) -> int:
    values = {
        f"x{i + 1}": bool((input_value >> i) & 1)
        for i in range(circuit.ninputs)
    }

    def get(token: str) -> bool:
        return not values[token[1:]] if token.startswith("~") else values[token]

    for wire, op, a, b in circuit.gates:
        av, bv = get(a), get(b)
        if op == "AND":
            value = av and bv
        elif op == "OR":
            value = av or bv
        elif op == "XOR":
            value = av != bv
        elif op == "NAND":
            value = not (av and bv)
        elif op == "NOR":
            value = not (av or bv)
        else:
            value = av == bv
        values[wire] = value
    return sum(get(output) << i for i, output in enumerate(circuit.outputs))


SPECS: dict[str, tuple[int, int, Callable[[int, int], int]]] = {
    "mystery-A": (8, 9, lambda x, y: x + y),
    "mystery-B": (7, 7, lambda x, y: abs(x - y)),
    "mystery-C": (6, 12, lambda x, y: x * y),
    "mystery-D": (5, 11, lambda x, y: x**2 + y**2),
}


def verify_exhaustive(
    name: str, circuit: ParsedCircuit, n: int, formula: Callable[[int, int], int]
) -> int:
    total = 1 << (2 * n)
    for packed in range(total):
        x = packed & ((1 << n) - 1)
        y = packed >> n
        actual = evaluate(circuit, packed)
        expected = formula(x, y)
        if actual != expected:
            raise AssertionError(
                f"{name}: x={x}, y={y}, circuit={actual}, expected={expected}"
            )
    return total


def decode_lsb_first(bits: str) -> int:
    return sum((bit == "1") << i for i, bit in enumerate(bits))


def verify_training(name: str, circuit: ParsedCircuit) -> tuple[int, int]:
    path = DATASETS / name / "train.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    correct = 0
    for row in rows:
        packed = decode_lsb_first(row["input"])
        expected = decode_lsb_first(row["output"])
        correct += evaluate(circuit, packed) == expected
    if correct != len(rows):
        raise AssertionError(f"{name}: training exact={correct}/{len(rows)}")
    return correct, len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instances", nargs="*", choices=sorted(SPECS))
    parser.add_argument(
        "--directory",
        type=Path,
        default=HERE,
        help="directory containing mystery-A.txt through mystery-D.txt",
    )
    parser.add_argument(
        "--suffix",
        default="",
        help="optional filename suffix before .txt, for example -abc",
    )
    args = parser.parse_args()
    instances = args.instances or list(SPECS)
    for name in instances:
        n, width, formula = SPECS[name]
        circuit = parse(args.directory / f"{name}{args.suffix}.txt")
        if len(circuit.outputs) != width:
            raise AssertionError(
                f"{name}: outputs={len(circuit.outputs)}, expected={width}"
            )
        exhaustive = verify_exhaustive(name, circuit, n, formula)
        train_ok, train_total = verify_training(name, circuit)
        print(
            f"{name}: gates={len(circuit.gates)}, "
            f"exhaustive={exhaustive}/{exhaustive}, "
            f"training={train_ok}/{train_total}"
        )


if __name__ == "__main__":
    main()
