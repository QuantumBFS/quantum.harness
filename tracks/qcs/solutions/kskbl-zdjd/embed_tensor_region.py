#!/usr/bin/env python3
"""Safely embed a verified standalone tensor-region replacement."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from score_circuits import (
    HERE,
    SPECS,
    base_operand,
    evaluate,
    parse,
    verify_exhaustive,
)
from tensor_graph_windows import contract, graph_data, reachability


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", choices=tuple(SPECS))
    parser.add_argument("indices", help="comma-separated one-based gate indices")
    parser.add_argument("replacement", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reachable-only",
        action="store_true",
        help=(
            "allow boundary don't-cares; skip complete boundary equivalence "
            "and rely on the mandatory full-domain verification after embedding"
        ),
    )
    args = parser.parse_args()

    source = args.source or (HERE / f"{args.instance}.txt")
    original = parse(source)
    replacement = parse(args.replacement)
    indices = frozenset(
        int(value) - 1 for value in args.indices.split(",") if value
    )
    producer, consumers, _ = graph_data(original)
    ancestors, descendants = reachability(original, producer, consumers)
    region = contract(
        original,
        indices,
        producer,
        consumers,
        ancestors,
        descendants,
    )
    if region is None:
        raise ValueError("region is not topologically convex")
    if replacement.ninputs != len(region.inputs):
        raise ValueError("replacement input count does not match boundary")
    if len(replacement.outputs) != len(region.outputs):
        raise ValueError("replacement output count does not match boundary")
    if any(output.startswith("~") for output in replacement.outputs):
        raise ValueError("complemented replacement outputs are not supported")

    if not args.reachable_only:
        for packed in range(1 << len(region.inputs)):
            expected = sum(
                ((int(truth, 16) >> packed) & 1) << output
                for output, truth in enumerate(region.truths)
            )
            actual = evaluate(replacement, packed)
            if actual != expected:
                raise ValueError(
                    f"boundary mismatch at {packed}: {actual} != {expected}"
                )

    tag = hashlib.sha256(
        (str(args.replacement) + args.indices).encode("utf-8")
    ).hexdigest()[:8]
    input_map = {
        f"x{index + 1}": wire for index, wire in enumerate(region.inputs)
    }
    output_map = {
        base_operand(output): wire
        for output, wire in zip(replacement.outputs, region.outputs)
    }
    wire_map = dict(input_map)
    for index, (wire, _, _, _) in enumerate(replacement.gates, 1):
        wire_map[wire] = output_map.get(wire, f"tr_{tag}_{index}")

    def rename(token: str) -> str:
        complemented = token.startswith("~")
        base = base_operand(token)
        renamed = wire_map[base]
        return f"~{renamed}" if complemented else renamed

    gates = [
        gate for index, gate in enumerate(original.gates) if index not in indices
    ]
    gates.extend(
        (wire_map[wire], op, rename(left), rename(right))
        for wire, op, left, right in replacement.gates
    )

    # Re-topologically sort because a non-contiguous region cannot always be
    # replaced at one original source position.
    primary_inputs = {f"x{index + 1}" for index in range(original.ninputs)}
    pending = {wire: (wire, op, left, right) for wire, op, left, right in gates}
    ordered = []
    available = set(primary_inputs)
    while pending:
        progress = False
        for wire, gate in list(pending.items()):
            _, _, left, right = gate
            if (
                base_operand(left) in available
                and base_operand(right) in available
            ):
                ordered.append(gate)
                available.add(wire)
                del pending[wire]
                progress = True
        if not progress:
            unresolved = ", ".join(sorted(pending)[:10])
            raise ValueError(f"cannot topologically sort: {unresolved}")

    lines = [f"INPUTS {original.ninputs}"]
    lines.extend(
        f"{wire} = {op} {left} {right}"
        for wire, op, left, right in ordered
    )
    lines.append("OUTPUTS " + " ".join(original.outputs))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="ascii")

    candidate = parse(args.output)
    n, _, formula = SPECS[args.instance]
    exhaustive = verify_exhaustive(args.instance, candidate, n, formula)
    boundary_status = (
        "reachable-only"
        if args.reachable_only
        else str(1 << len(region.inputs))
    )
    print(
        f"boundary={boundary_status}, gates={len(candidate.gates)}, "
        f"exhaustive={exhaustive}, output={args.output}"
    )


if __name__ == "__main__":
    main()
