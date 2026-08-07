#!/usr/bin/env python3
"""Generate arithmetic circuits selected only by frozen train-only discovery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def build_absdiff(circuit_module, nbits: int):
    """Unsigned |x-y| via ripple subtraction and conditional two's complement."""
    builder = circuit_module.CircuitBuilder(2 * nbits)
    x = [f"x{i + 1}" for i in range(nbits)]
    y = [f"x{nbits + i + 1}" for i in range(nbits)]

    difference = [builder.gate("XOR", x[0], y[0])]
    borrow = builder.gate("AND", circuit_module.invert(x[0]), y[0])
    for idx in range(1, nbits):
        parity = builder.gate("XOR", x[idx], y[idx])
        difference.append(builder.gate("XOR", parity, borrow))
        generate = builder.gate("AND", circuit_module.invert(x[idx]), y[idx])
        propagate = builder.gate("AND", circuit_module.invert(parity), borrow)
        # These terms are disjoint, so XOR equals OR.
        borrow = builder.gate("XOR", generate, propagate)

    # If borrow=1, the modular difference is negative.  Conditionally invert
    # every bit and add one.  Bit zero simplifies back to difference[0].
    outputs = [difference[0]]
    carry = builder.gate("AND", circuit_module.invert(difference[0]), borrow)
    for idx in range(1, nbits):
        conditional = builder.gate("XOR", difference[idx], borrow)
        outputs.append(builder.gate("XOR", conditional, carry))
        if idx + 1 < nbits:
            carry = builder.gate("AND", conditional, carry)
    return builder.finish(outputs)


def build_sum_of_squares(circuit_module, nbits: int):
    """Build x²+y² from diagonal and shared-weight cross products."""
    builder = circuit_module.CircuitBuilder(2 * nbits)
    columns: list[list[str]] = [[] for _ in range(2 * nbits + 2)]
    for offset in (0, nbits):
        bits = [f"x{offset + i + 1}" for i in range(nbits)]
        for idx, bit in enumerate(bits):
            columns[2 * idx].append(bit)
        for left in range(nbits):
            for right in range(left + 1, nbits):
                partial = builder.gate("AND", bits[left], bits[right])
                columns[left + right + 1].append(partial)

    outputs: list[str] = []
    for weight in range(2 * nbits + 1):
        column = columns[weight]
        while len(column) >= 3:
            total, carry = builder.full_adder(
                column.pop(), column.pop(), column.pop()
            )
            column.append(total)
            columns[weight + 1].append(carry)
        if len(column) == 2:
            total, carry = builder.half_adder(column[0], column[1])
            outputs.append(total)
            columns[weight + 1].append(carry)
        elif len(column) == 1:
            outputs.append(column[0])
        else:
            raise AssertionError(f"empty sum-of-squares column {weight}")
    return builder.finish(outputs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery-root", required=True)
    parser.add_argument("--search-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    search_dir = Path(args.search_dir).resolve()
    sys.path.insert(0, str(search_dir))
    import circuit  # type: ignore[import-not-found]

    discovery_root = Path(args.discovery_root).resolve()
    index = json.loads(
        (discovery_root / "discovery-index.json").read_text(encoding="utf-8")
    )
    if index["schema"] != "occam71-train-only-index-v1":
        raise ValueError("unexpected discovery index schema")

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {}
    formula_by_expr = {
        "x_plus_y": "add",
        "x_times_y": "mul",
        "abs_x_minus_y": "absdiff",
        "sum_of_squares": "sos",
    }
    for name, index_entry in sorted(index["instances"].items()):
        manifest = json.loads(
            (discovery_root / name / "discovery.json").read_text(encoding="utf-8")
        )
        selected = manifest["selected"]
        if selected != index_entry["selected"]:
            raise ValueError(f"{name}: index/manifest selection mismatch")
        for key, expected in (
            ("layout", "grouped"),
            ("input_endian", "lsb"),
            ("output_endian", "lsb"),
        ):
            if selected[key] != expected:
                raise ValueError(f"{name}: unsupported {key}={selected[key]}")

        nbits = int(manifest["operand_width"])
        expr_id = selected["expr_id"]
        if expr_id == "x_plus_y":
            generated = circuit.build_adder(nbits)
        elif expr_id == "x_times_y":
            generated = circuit.build_multiplier(nbits)
        elif expr_id == "abs_x_minus_y":
            generated = build_absdiff(circuit, nbits)
        elif expr_id == "sum_of_squares":
            generated = build_sum_of_squares(circuit, nbits)
        else:
            raise ValueError(f"{name}: no arithmetic template for {expr_id}")
        if len(generated.outputs) != int(manifest["output_width"]):
            raise ValueError(f"{name}: generated output width mismatch")

        instance_dir = out / name
        instance_dir.mkdir(parents=True, exist_ok=True)
        template_path = instance_dir / "template.txt"
        generated.write(template_path)
        formula_audit = circuit.verify_formula(
            generated, formula_by_expr[expr_id]
        )
        train_audit = circuit.verify_dataset(generated, manifest["train_path"])
        if formula_audit["failures"] or (
            train_audit["exact"] != train_audit["rows"]
        ):
            raise RuntimeError(f"{name}: generated template failed audit")
        result = {
            "instance": name,
            "discovery_manifest": str(discovery_root / name / "discovery.json"),
            "discovery_train_sha256": manifest["train_sha256"],
            "selected": selected,
            "template": str(template_path),
            "template_sha256": circuit.sha256_file(template_path),
            "gates": len(generated.gates),
            "formula_audit": formula_audit,
            "train_audit": train_audit,
            "structure": generated.structural_audit(),
        }
        (instance_dir / "template-audit.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        results[name] = result
        print(
            f"{name}: {expr_id}, gates={len(generated.gates)}, "
            f"full failures={formula_audit['failures']}",
            flush=True,
        )

    summary = {
        "schema": "occam71-train-symbolic-to-arithmetic-template-v1",
        "root_seed": 42,
        "instances": results,
    }
    (out / "template-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (out / "TEMPLATES_COMPLETE").write_text(
        "success\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
