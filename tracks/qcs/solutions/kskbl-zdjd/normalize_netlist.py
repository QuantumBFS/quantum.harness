#!/usr/bin/env python3
"""Rename internal wires to dense official-format w1, w2, ... identifiers."""

from __future__ import annotations

import argparse
from pathlib import Path

from score_circuits import base_operand, parse


def rewrite_operand(token: str, names: dict[str, str]) -> str:
    negated = token.startswith("~")
    base = base_operand(token)
    rewritten = names.get(base, base)
    return f"~{rewritten}" if negated else rewritten


def normalize(source: Path, destination: Path) -> None:
    circuit = parse(source)
    names = {
        wire: f"w{index}"
        for index, (wire, _, _, _) in enumerate(circuit.gates, start=1)
    }
    lines = [f"INPUTS {circuit.ninputs}"]
    for wire, op, left, right in circuit.gates:
        lines.append(
            f"{names[wire]} = {op} "
            f"{rewrite_operand(left, names)} {rewrite_operand(right, names)}"
        )
    outputs = " ".join(rewrite_operand(output, names) for output in circuit.outputs)
    lines.append(f"OUTPUTS {outputs}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{source} -> {destination}: {len(circuit.gates)} gates")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    normalize(args.source.resolve(), args.destination.resolve())


if __name__ == "__main__":
    main()
