"""Verify a Yosys JSON netlist against a learned network on all 4096 inputs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from compile_learned_mdfa import DOMAIN_SIZE, INPUT_BITS, evaluate_network


MASK = (1 << DOMAIN_SIZE) - 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-network", type=Path, required=True)
    parser.add_argument("--yosys-json", type=Path, required=True)
    parser.add_argument("--module", default="learned_network")
    parser.add_argument("--output-summary", type=Path, required=True)
    return parser.parse_args()


def input_fingerprint(bit: int) -> int:
    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    values = ((ids >> bit) & 1).astype(np.uint8)
    return int.from_bytes(
        np.packbits(values, bitorder="little").tobytes(),
        "little",
    )


def read_signal(signals: dict[int, int], token: int | str) -> int | None:
    if token == "0":
        return 0
    if token == "1":
        return MASK
    if isinstance(token, str):
        raise ValueError(f"unsupported constant token: {token}")
    return signals.get(token)


def apply_cell(cell_type: str, left: int, right: int | None) -> int:
    if cell_type == "$_NOT_":
        return left ^ MASK
    if right is None:
        raise ValueError(f"missing binary operand for {cell_type}")
    operations = {
        "$_AND_": left & right,
        "$_NAND_": (left & right) ^ MASK,
        "$_ANDNOT_": left & (right ^ MASK),
        "$_OR_": left | right,
        "$_NOR_": (left | right) ^ MASK,
        "$_ORNOT_": left | (right ^ MASK),
        "$_XOR_": left ^ right,
        "$_XNOR_": (left ^ right) ^ MASK,
    }
    if cell_type not in operations:
        raise ValueError(f"unsupported Yosys cell: {cell_type}")
    return operations[cell_type]


def evaluate_yosys(
    design: dict[str, Any],
    module_name: str,
) -> tuple[list[int], Counter[str]]:
    module = design["modules"][module_name]
    signals: dict[int, int] = {}
    input_bits = module["ports"]["i"]["bits"]
    for bit, token in enumerate(input_bits):
        if not isinstance(token, int):
            raise ValueError("input port contains a constant")
        signals[token] = input_fingerprint(bit)

    pending = dict(module["cells"])
    breakdown: Counter[str] = Counter()
    while pending:
        progressed = False
        for name, cell in tuple(pending.items()):
            cell_type = cell["type"]
            connections = cell["connections"]
            left = read_signal(signals, connections["A"][0])
            right = (
                None
                if cell_type == "$_NOT_"
                else read_signal(signals, connections["B"][0])
            )
            if left is None or (cell_type != "$_NOT_" and right is None):
                continue
            output_token = connections["Y"][0]
            if not isinstance(output_token, int):
                raise ValueError("cell drives a constant")
            signals[output_token] = apply_cell(cell_type, left, right)
            breakdown[cell_type] += 1
            del pending[name]
            progressed = True
        if not progressed:
            unresolved = sorted(
                {cell["type"] for cell in pending.values()}
            )
            raise RuntimeError(f"cannot topologically resolve {unresolved}")

    output_fingerprints = []
    for token in module["ports"]["o"]["bits"]:
        semantic = read_signal(signals, token)
        if semantic is None:
            raise RuntimeError("output signal is unresolved")
        output_fingerprints.append(semantic)
    return output_fingerprints, breakdown


def array_fingerprints(values: np.ndarray) -> list[int]:
    return [
        int.from_bytes(
            np.packbits(values[:, bit], bitorder="little").tobytes(),
            "little",
        )
        for bit in range(values.shape[1])
    ]


def main() -> None:
    args = parse_args()
    source = json.loads(args.source_network.read_text(encoding="utf-8"))
    design = json.loads(args.yosys_json.read_text(encoding="utf-8"))
    yosys_outputs, breakdown = evaluate_yosys(design, args.module)
    source_prediction = evaluate_network(source)
    source_outputs = array_fingerprints(source_prediction)
    if yosys_outputs != source_outputs:
        raise AssertionError("Yosys netlist differs from learned network")

    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    x = ids & 63
    y = (ids >> 6) & 63
    clean_values = x.astype(np.uint32) * y.astype(np.uint32)
    clean_bits = (
        (clean_values[:, None] >> np.arange(12)) & 1
    ).astype(np.uint8)
    if yosys_outputs != array_fingerprints(clean_bits):
        raise AssertionError("Yosys netlist differs from the clean domain")

    counted_cells = sum(
        count
        for cell_type, count in breakdown.items()
        if cell_type != "$_NOT_"
    )
    summary = {
        "kind": "independent-yosys-abc-global-resynthesis",
        "source_network": args.source_network.as_posix(),
        "yosys_json": args.yosys_json.as_posix(),
        "verification": {
            "domain_size": DOMAIN_SIZE,
            "matches_source_network": True,
            "matches_clean_domain": True,
            "all_outputs_exact": True,
        },
        "gate_model": {
            "counted_two_input_families": [
                "AND",
                "NAND",
                "ANDNOT",
                "OR",
                "NOR",
                "ORNOT",
                "XOR",
                "XNOR",
            ],
            "NOT_cost": 0,
        },
        "source_counted_gates": len(source["gates"]),
        "resynthesized_counted_gates": counted_cells,
        "cell_breakdown": dict(sorted(breakdown.items())),
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
