#!/usr/bin/env python3
"""Generate committed test predictions by evaluating the submitted circuits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
from pathlib import Path

from score_circuits import DATASETS, HERE, SPECS, evaluate, parse


def render_predictions(instance: str) -> bytes:
    circuit = parse(HERE / f"{instance}.txt")
    input_path = DATASETS / instance / "test_inputs.csv"
    with input_path.open(newline="", encoding="utf-8") as handle:
        inputs = [row["input"] for row in csv.DictReader(handle)]

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("input", "output"))
    width = SPECS[instance][1]
    for input_bits in inputs:
        packed = sum((bit == "1") << i for i, bit in enumerate(input_bits))
        value = evaluate(circuit, packed)
        output_bits = f"{value:0{width}b}"[::-1]
        writer.writerow((input_bits, output_bits))
    return output.getvalue().encode("utf-8")


def expected_digest(instance: str) -> str:
    return (
        (DATASETS / instance / "commitment.sha256")
        .read_text(encoding="utf-8")
        .split()[0]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify checked-in predictions without rewriting them",
    )
    args = parser.parse_args()

    prediction_root = HERE / "predictions"
    for instance in SPECS:
        payload = render_predictions(instance)
        digest = hashlib.sha256(payload).hexdigest()
        expected = expected_digest(instance)
        if digest != expected:
            raise AssertionError(
                f"{instance}: prediction hash {digest} != commitment {expected}"
            )

        output_path = prediction_root / instance / "test_outputs.csv"
        if args.check:
            if not output_path.exists():
                raise FileNotFoundError(output_path)
            if output_path.read_bytes() != payload:
                raise AssertionError(f"{output_path}: checked-in bytes are stale")
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(payload)

        print(
            f"{instance}: {output_path.relative_to(HERE)}; "
            f"sha256={digest}; commitment=match"
        )


if __name__ == "__main__":
    main()
