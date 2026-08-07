#!/usr/bin/env python3
"""Translate challenge netlists to/from formats used in Berkeley ABC experiments."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from score_circuits import SPECS, parse


HERE = Path(__file__).parent


def challenge_to_bench(source: Path, destination: Path) -> None:
    circuit = parse(source)
    lines = [f"INPUT(x{i})" for i in range(1, circuit.ninputs + 1)]
    inversions: dict[str, str] = {}

    def materialize(token: str) -> str:
        if not token.startswith("~"):
            return token
        base = token[1:]
        if base not in inversions:
            wire = f"inv_{base}"
            inversions[base] = wire
            lines.append(f"{wire} = NOT({base})")
        return inversions[base]

    for wire, op, a, b in circuit.gates:
        lines.append(f"{wire} = {op}({materialize(a)},{materialize(b)})")
    output_names: list[str] = []
    for index, output in enumerate(circuit.outputs):
        name = f"out{index}"
        lines.append(f"{name} = BUFF({materialize(output)})")
        output_names.append(name)
    lines[0:0] = [f"OUTPUT({name})" for name in output_names]
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")


def toggle(token: str) -> str:
    return token[1:] if token.startswith("~") else f"~{token}"


def mapped_blif_to_challenge(source: Path, destination: Path) -> None:
    inputs: list[str] = []
    output_nets: list[str] = []
    aliases: dict[str, str] = {}
    gates: list[tuple[str, str, str, str]] = []
    op_names = {
        "and2": "AND",
        "or2": "OR",
        "xor2": "XOR",
        "nand2": "NAND",
        "nor2": "NOR",
        "xnor2": "XNOR",
    }

    def resolve(net: str) -> str:
        token = aliases.get(net, net)
        seen = {net}
        while True:
            negated = token.startswith("~")
            base = token[1:] if negated else token
            if base not in aliases:
                return token
            if base in seen:
                raise ValueError(f"alias cycle through {base}")
            seen.add(base)
            replacement = aliases[base]
            token = toggle(replacement) if negated else replacement

    logical_lines: list[str] = []
    pending = ""
    for raw in source.read_text(encoding="ascii").splitlines():
        stripped = raw.strip()
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            continue
        logical_lines.append(pending + stripped)
        pending = ""
    if pending:
        raise ValueError("unterminated BLIF line continuation")

    for raw in logical_lines:
        line = raw.strip()
        if line.startswith(".inputs "):
            inputs = line.split()[1:]
            for index, net in enumerate(inputs):
                target = f"x{index + 1}"
                if net != target:
                    aliases[net] = target
        elif line.startswith(".outputs "):
            output_nets = line.split()[1:]
        elif line.startswith(".gate "):
            tokens = line.split()
            cell = tokens[1]
            pins = dict(token.split("=", 1) for token in tokens[2:])
            output = pins["Y"]
            if cell == "inv":
                aliases[output] = toggle(resolve(pins["A"]))
                continue
            if cell == "buf":
                aliases[output] = resolve(pins["A"])
                continue
            if cell in {"zero", "one"}:
                raise ValueError("challenge format has no constant operands")
            op = op_names[cell]
            a, b = resolve(pins["A"]), resolve(pins["B"])
            wire = f"w{len(gates) + 1}"
            gates.append((wire, op, a, b))
            aliases[output] = wire

    lines = [f"INPUTS {len(inputs)}"]
    lines.extend(f"{wire} = {op} {a} {b}" for wire, op, a, b in gates)
    lines.append("OUTPUTS " + " ".join(resolve(net) for net in output_nets))
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")


def formula_to_pla(instance: str, destination: Path) -> None:
    n, width, formula = SPECS[instance]
    input_names = [f"x{i}" for i in range(1, 2 * n + 1)]
    output_names = [f"out{i}" for i in range(width)]
    lines = [
        f".i {2 * n}",
        f".o {width}",
        ".ilb " + " ".join(input_names),
        ".ob " + " ".join(output_names),
    ]
    mask = (1 << n) - 1
    for packed in range(1 << (2 * n)):
        x, y = packed & mask, packed >> n
        input_bits = "".join("1" if (packed >> bit) & 1 else "0" for bit in range(2 * n))
        value = formula(x, y)
        output_bits = "".join("1" if (value >> bit) & 1 else "0" for bit in range(width))
        lines.append(f"{input_bits} {output_bits}")
    lines.append(".e")
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", choices=["mystery-A", "mystery-B", "mystery-C", "mystery-D"])
    parser.add_argument("--pla", action="store_true")
    parser.add_argument("--mapped", type=Path)
    parser.add_argument("--tag", default="abc")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--bench-output", type=Path)
    args = parser.parse_args()
    source = args.source or (HERE / f"{args.instance}.txt")
    work = HERE / "abc-work"
    work.mkdir(exist_ok=True)
    if args.mapped:
        candidate = work / f"{args.instance}-{args.tag}.txt"
        mapped_blif_to_challenge(args.mapped, candidate)
        print(candidate)
        return
    if args.pla:
        pla = work / f"{args.instance}-truth.pla"
        formula_to_pla(args.instance, pla)
        print(pla)
        return
    bench = args.bench_output or (work / f"{args.instance}.bench")
    challenge_to_bench(source, bench)
    mapped = work / f"{args.instance}-mapped.blif"
    if mapped.exists():
        candidate = work / f"{args.instance}-{args.tag}.txt"
        mapped_blif_to_challenge(mapped, candidate)
        print(candidate)
    else:
        print(bench)


if __name__ == "__main__":
    main()
