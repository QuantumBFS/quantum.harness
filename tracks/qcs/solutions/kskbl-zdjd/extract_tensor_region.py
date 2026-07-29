#!/usr/bin/env python3
"""Extract a convex tensor region as a standalone challenge netlist."""

from __future__ import annotations

import argparse
from pathlib import Path

from score_circuits import HERE, base_operand, parse
from tensor_graph_windows import contract, graph_data, reachability


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance")
    parser.add_argument("indices", help="comma-separated one-based gate indices")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    circuit = parse(HERE / f"{args.instance}.txt")
    indices = frozenset(
        int(value) - 1 for value in args.indices.split(",") if value
    )
    producer, consumers, _ = graph_data(circuit)
    ancestors, descendants = reachability(circuit, producer, consumers)
    region = contract(
        circuit,
        indices,
        producer,
        consumers,
        ancestors,
        descendants,
    )
    if region is None:
        raise ValueError("region is not topologically convex")

    input_aliases = {
        wire: f"x{index + 1}" for index, wire in enumerate(region.inputs)
    }

    def rename(token: str) -> str:
        complemented = token.startswith("~")
        base = base_operand(token)
        renamed = input_aliases.get(base, base)
        return f"~{renamed}" if complemented else renamed

    lines = [f"INPUTS {len(region.inputs)}"]
    for index in sorted(indices):
        wire, op, left, right = circuit.gates[index]
        lines.append(f"{wire} = {op} {rename(left)} {rename(right)}")
    lines.append("OUTPUTS " + " ".join(region.outputs))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(
        f"gates={region.gates}, inputs={','.join(region.inputs)}, "
        f"outputs={','.join(region.outputs)}, output={args.output}"
    )


if __name__ == "__main__":
    main()
