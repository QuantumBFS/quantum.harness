#!/usr/bin/env python3
"""Validate the four inferred Occam's Circuit arithmetic functions."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).parent / "package" / "occam-circuit" / "datasets"

FORMULAS: dict[str, tuple[str, Callable[[int, int], int]]] = {
    "mystery-A": ("x + y", lambda x, y: x + y),
    "mystery-B": ("abs(x - y)", lambda x, y: abs(x - y)),
    "mystery-C": ("x * y", lambda x, y: x * y),
    "mystery-D": ("x**2 + y**2", lambda x, y: x**2 + y**2),
}


def decode_lsb_first(bits: str) -> int:
    return sum((bit == "1") << position for position, bit in enumerate(bits))


def load_pairs(path: Path) -> list[tuple[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [(row["input"], row["output"]) for row in reader]


def predict(input_bits: str, formula: Callable[[int, int], int], width: int) -> str:
    n = len(input_bits) // 2
    x = decode_lsb_first(input_bits[:n])
    y = decode_lsb_first(input_bits[n:])
    value = formula(x, y)
    if not 0 <= value < 2**width:
        raise ValueError(f"result {value} does not fit in {width} output bits")
    return f"{value:0{width}b}"[::-1]


def verify_training(instance: str, expression: str, formula: Callable[[int, int], int]) -> None:
    pairs = load_pairs(ROOT / instance / "train.csv")
    width = len(pairs[0][1])
    mismatches = [
        (input_bits, expected, predict(input_bits, formula, width))
        for input_bits, expected in pairs
        if predict(input_bits, formula, width) != expected
    ]
    print(
        f"{instance}: f(x,y) = {expression}; "
        f"training exact matches = {len(pairs) - len(mismatches)}/{len(pairs)}"
    )
    if mismatches:
        raise AssertionError(f"{instance} mismatches: {mismatches[:5]}")


def verify_revealed_test(
    instance: str, expression: str, formula: Callable[[int, int], int]
) -> None:
    answers = ROOT / instance / "test_outputs.csv"
    if not answers.exists():
        print(f"{instance}: hidden test outputs not present; test verification skipped")
        return

    commitment = (ROOT / instance / "commitment.sha256").read_text(
        encoding="utf-8"
    ).split()[0]
    actual_hash = hashlib.sha256(answers.read_bytes()).hexdigest()
    if actual_hash != commitment:
        raise AssertionError(
            f"{instance} test-output hash {actual_hash} != commitment {commitment}"
        )

    pairs = load_pairs(answers)
    width = len(pairs[0][1])
    correct = sum(
        predict(input_bits, formula, width) == expected
        for input_bits, expected in pairs
    )
    print(
        f"{instance}: f(x,y) = {expression}; "
        f"hidden-test exact matches = {correct}/{len(pairs)}; hash verified"
    )
    if correct != len(pairs):
        raise AssertionError(f"{instance} is not exact on the revealed test set")


def main() -> None:
    for instance, (expression, formula) in FORMULAS.items():
        verify_training(instance, expression, formula)
    for instance, (expression, formula) in FORMULAS.items():
        verify_revealed_test(instance, expression, formula)


if __name__ == "__main__":
    main()
