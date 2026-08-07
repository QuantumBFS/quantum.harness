#!/usr/bin/env python3
"""Distill one train-selected continuous MPS into a shared ROBDD and netlist."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from tn_common import (
    INSTANCE_SPECS,
    atomic_json,
    load_models,
    predict_scores,
    sha256_file,
)
from tn_truth import enumerate_full_domain


INSTANCES = ("mystery-A", "mystery-B", "mystery-C", "mystery-D")
ORDERS = (
    "blocked_lsb",
    "blocked_msb",
    "interleaved_lsb",
    "interleaved_msb",
)
BONDS = (2, 4, 8, 16)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def selection_key(configuration: dict) -> tuple[float, float, float, int]:
    validation = configuration["validation"]
    return (
        float(validation["exact_accuracy"]),
        float(validation["bit_accuracy"]),
        -float(validation["rmse_pm1"]),
        -int(configuration["bond"]),
    )


def selected_configuration(summary: dict, instance: str) -> dict:
    candidates = [
        item
        for item in summary["all_mps_configurations"]
        if item["instance"] == instance
    ]
    if len(candidates) != 16:
        raise RuntimeError(f"expected 16 configurations for {instance}")
    return max(candidates, key=selection_key)


def cell_for_configuration(mps_root: Path, configuration: dict) -> Path:
    instance_index = INSTANCES.index(configuration["instance"])
    order_index = ORDERS.index(configuration["order"])
    bond_index = BONDS.index(int(configuration["bond"]))
    task_id = instance_index * 16 + order_index * 4 + bond_index
    matches = sorted((mps_root / "cells").glob(f"{task_id:02d}-*"))
    if len(matches) != 1:
        raise RuntimeError(f"could not resolve task {task_id}: {matches}")
    return matches[0]


def build_shared_robdd(
    predictions: np.ndarray, order: list[int]
) -> tuple[list[tuple[int, int, int]], list[int]]:
    """Return nodes (level, low, high) and roots; terminals are IDs 0 and 1."""
    n_sites = len(order)
    if predictions.shape[0] != 2**n_sites:
        raise ValueError("prediction table is not a complete Boolean domain")
    unique: dict[tuple[int, int, int], int] = {}
    nodes: list[tuple[int, int, int]] = []
    roots: list[int] = []
    for output_index in range(predictions.shape[1]):
        original_tensor = predictions[:, output_index].reshape(
            (2,) * n_sites, order="F"
        )
        ordered_tensor = np.transpose(original_tensor, axes=order)
        current = ordered_tensor.reshape(-1).astype(np.int64)
        for level in range(n_sites - 1, -1, -1):
            if current.size % 2:
                raise AssertionError("odd ROBDD frontier")
            next_ids = np.empty(current.size // 2, dtype=np.int64)
            for position, (low, high) in enumerate(
                zip(current[0::2].tolist(), current[1::2].tolist())
            ):
                low_id, high_id = int(low), int(high)
                if low_id == high_id:
                    node_id = low_id
                else:
                    key = (level, low_id, high_id)
                    node_id = unique.get(key, -1)
                    if node_id < 0:
                        node_id = len(nodes) + 2
                        unique[key] = node_id
                        nodes.append(key)
                next_ids[position] = node_id
            current = next_ids
        if current.size != 1:
            raise AssertionError("ROBDD did not reduce to one root")
        roots.append(int(current[0]))
    return nodes, roots


def invert(reference: str) -> str:
    return reference[1:] if reference.startswith("~") else f"~{reference}"


def emit_mux_netlist(
    path: Path,
    n_inputs: int,
    order: list[int],
    nodes: list[tuple[int, int, int]],
    roots: list[int],
) -> dict:
    """Emit simplified AND/OR MUX logic, structurally shared across all roots."""
    gates: list[tuple[str, str, str, str]] = []
    gate_cache: dict[tuple[str, str, str], str] = {}

    def gate(operation: str, left: str, right: str) -> str:
        operands = tuple(sorted((left, right)))
        key = (operation, operands[0], operands[1])
        existing = gate_cache.get(key)
        if existing is not None:
            return existing
        wire = f"w{len(gates) + 1}"
        gates.append((wire, operation, operands[0], operands[1]))
        gate_cache[key] = wire
        return wire

    false_reference = gate("AND", "x1", "~x1")
    references: dict[int, str] = {0: false_reference, 1: invert(false_reference)}
    simplified = Counter()
    for node_id, (level, low_id, high_id) in enumerate(nodes, start=2):
        variable = f"x{order[level] + 1}"
        low = references[low_id]
        high = references[high_id]
        if low_id == 0 and high_id == 1:
            result = variable
            simplified["identity"] += 1
        elif low_id == 1 and high_id == 0:
            result = invert(variable)
            simplified["inversion"] += 1
        elif low_id == 0:
            result = gate("AND", variable, high)
            simplified["low_false"] += 1
        elif high_id == 0:
            result = gate("AND", invert(variable), low)
            simplified["high_false"] += 1
        elif low_id == 1:
            result = gate("OR", invert(variable), high)
            simplified["low_true"] += 1
        elif high_id == 1:
            result = gate("OR", variable, low)
            simplified["high_true"] += 1
        else:
            low_term = gate("AND", invert(variable), low)
            high_term = gate("AND", variable, high)
            result = gate("OR", low_term, high_term)
            simplified["general_mux"] += 1
        references[node_id] = result
    output_references = [references[root] for root in roots]
    lines = [f"INPUTS {n_inputs}"]
    lines.extend(
        f"{wire} = {operation} {left} {right}"
        for wire, operation, left, right in gates
    )
    lines.append(f"OUTPUTS {' '.join(output_references)}")
    payload = ("\n".join(lines) + "\n").encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)
    return {
        "gates": len(gates),
        "outputs": len(output_references),
        "bytes": len(payload),
        "simplification_counts": dict(sorted(simplified.items())),
    }


def token_value(token: str, values: dict[str, int], mask: int) -> int:
    negated = token.startswith("~")
    base = token[1:] if negated else token
    if base not in values:
        raise ValueError(f"undefined token {token!r}")
    return values[base] ^ mask if negated else values[base]


def bit_table(bits: np.ndarray) -> int:
    packed = np.packbits(bits.astype(np.uint8), bitorder="little")
    return int.from_bytes(packed.tobytes(), byteorder="little", signed=False)


def verify_serialized_netlist(
    path: Path, predictions: np.ndarray
) -> dict[str, int | bool]:
    """Strictly parse and bit-parallel simulate the generated serialized file."""
    raw_lines = path.read_text(encoding="ascii").splitlines()
    if not raw_lines or len(raw_lines[0].split()) != 2:
        raise ValueError("malformed INPUTS line")
    input_fields = raw_lines[0].split()
    if input_fields[0] != "INPUTS" or not input_fields[1].isdigit():
        raise ValueError("malformed INPUTS line")
    n_inputs = int(input_fields[1])
    assignment_count = 2**n_inputs
    if predictions.shape[0] != assignment_count:
        raise ValueError("prediction/netlist domain mismatch")
    mask = (1 << assignment_count) - 1
    values: dict[str, int] = {}
    for input_index in range(n_inputs):
        table = 0
        for assignment in range(assignment_count):
            table |= ((assignment >> input_index) & 1) << assignment
        values[f"x{input_index + 1}"] = table
    output_tokens: list[str] | None = None
    gate_count = 0
    for line in raw_lines[1:]:
        fields = line.split()
        if fields and fields[0] == "OUTPUTS":
            if output_tokens is not None or len(fields) < 2:
                raise ValueError("malformed OUTPUTS line")
            output_tokens = fields[1:]
            continue
        if output_tokens is not None:
            raise ValueError("gate after OUTPUTS")
        if len(fields) != 5 or fields[1] != "=":
            raise ValueError(f"malformed gate line: {line!r}")
        wire, operation, left, right = fields[0], fields[2], fields[3], fields[4]
        if wire != f"w{gate_count + 1}" or operation not in {"AND", "OR"}:
            raise ValueError(f"invalid gate line: {line!r}")
        left_value = token_value(left, values, mask)
        right_value = token_value(right, values, mask)
        values[wire] = (
            left_value & right_value
            if operation == "AND"
            else left_value | right_value
        )
        gate_count += 1
    if output_tokens is None or len(output_tokens) != predictions.shape[1]:
        raise ValueError("missing/mismatched outputs")
    mismatch_outputs = 0
    for output_index, token in enumerate(output_tokens):
        actual = token_value(token, values, mask)
        expected = bit_table(predictions[:, output_index])
        mismatch_outputs += actual != expected
    return {
        "assignments": assignment_count,
        "outputs": predictions.shape[1],
        "gates": gate_count,
        "mismatching_output_truth_tables": mismatch_outputs,
        "equivalent_to_thresholded_mps": mismatch_outputs == 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True, choices=INSTANCES)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--mps-root", required=True, type=Path)
    parser.add_argument("--netlist-out", required=True, type=Path)
    parser.add_argument("--report-out", required=True, type=Path)
    args = parser.parse_args()
    summary = load_json(args.summary)
    configuration = selected_configuration(summary, args.instance)
    cell = cell_for_configuration(args.mps_root, configuration)
    saved = load_models(cell / "model.npz")
    model_hash = sha256_file(cell / "model.npz")
    if model_hash != configuration["model_sha256"]:
        raise RuntimeError("selected model hash mismatch")
    order = [int(value) for value in saved.metadata["order_original_axes"]]
    x_bits, y_truth = enumerate_full_domain(args.instance)
    x_ordered = x_bits[:, order]
    scores = np.column_stack(
        [predict_scores(model, x_ordered) for model in saved.models]
    )
    predictions = (scores >= 0.0).astype(np.int8)
    nodes, roots = build_shared_robdd(predictions, order)
    netlist = emit_mux_netlist(
        args.netlist_out, x_bits.shape[1], order, nodes, roots
    )
    netlist_verification = verify_serialized_netlist(
        args.netlist_out, predictions
    )
    if not netlist_verification["equivalent_to_thresholded_mps"]:
        raise RuntimeError("serialized netlist failed full-domain equivalence")
    wrong_rows = np.any(predictions != y_truth, axis=1)
    parameter_count = int(
        sum(core.size for model in saved.models for core in model)
    )
    nodes_by_level = Counter(level for level, _, _ in nodes)
    report = {
        "schema": "occam71-tn-bdd-distillation-v1",
        "instance": args.instance,
        "selection_rule": (
            "train-only validation exact accuracy, then bit accuracy, then "
            "lower RMSE, then smaller bond"
        ),
        "selected_configuration": configuration,
        "source_cell": str(cell),
        "source_model_sha256": model_hash,
        "mps_parameter_count_float64": parameter_count,
        "mps_parameter_bytes_float64": 8 * parameter_count,
        "robdd": {
            "variable_order_original_axes": order,
            "shared_nonterminal_nodes": len(nodes),
            "nodes_by_level": {
                str(level): int(nodes_by_level[level])
                for level in range(len(order))
            },
            "roots": roots,
        },
        "netlist": {
            **netlist,
            "path": str(args.netlist_out),
            "sha256": sha256_file(args.netlist_out),
            "verification": netlist_verification,
        },
        "arithmetic_truth_audit": {
            "rows": int(y_truth.shape[0]),
            "bit_accuracy": float(np.mean(predictions == y_truth)),
            "exact_accuracy": float(np.mean(~wrong_rows)),
            "mismatching_rows": int(np.count_nonzero(wrong_rows)),
        },
        "challenge_candidate": False,
        "rejection_reason": (
            "The distilled circuit exactly implements the thresholded MPS, "
            "but that function has nonzero full-domain mismatches to the "
            "arithmetic target."
        ),
    }
    atomic_json(args.report_out, report)
    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
