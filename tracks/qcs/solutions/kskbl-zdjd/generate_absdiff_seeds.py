#!/usr/bin/env python3
"""Generate structurally diverse exact 7-bit absolute-difference circuits."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from build_exact_circuits import Circuit


HERE = Path(__file__).parent


def negate(token: str) -> str:
    return token[1:] if token.startswith("~") else f"~{token}"


def random_absdiff(seed: int) -> Circuit:
    rng = random.Random(seed)
    circuit = Circuit(14)
    x = [f"x{i}" for i in range(1, 8)]
    y = [f"x{i}" for i in range(8, 15)]

    difference = [circuit.gate("XOR", x[0], y[0])]
    borrow = circuit.gate("AND", f"~{x[0]}", y[0])
    for a, b in zip(x[1:], y[1:]):
        # Full subtraction equals a full adder on (~a, b, borrow):
        # borrow_out is the carry, while difference is the inverted sum.
        terms = [f"~{a}", b, borrow]
        rng.shuffle(terms)
        inverted_difference, borrow = circuit.full_adder(*terms)
        difference.append(f"~{inverted_difference}")

    # Conditional two's complement.  Bit 0 is unchanged by negation.  For each
    # higher bit, carry implies borrow, so borrow XOR carry = borrow AND ~carry.
    outputs = [difference[0]]
    carry = circuit.gate("AND", borrow, negate(difference[0]))
    for bit in difference[1:]:
        flip = circuit.gate("AND", borrow, f"~{carry}")
        outputs.append(circuit.gate("XOR", bit, flip))
        carry = circuit.gate("AND", carry, negate(bit))
    circuit.outputs = outputs
    return circuit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--first-seed", type=int, default=1)
    args = parser.parse_args()
    destination = HERE / "abc-work" / "absdiff-seeds"
    destination.mkdir(parents=True, exist_ok=True)
    for seed in range(args.first_seed, args.first_seed + args.count):
        circuit = random_absdiff(seed)
        path = destination / f"mystery-B-seed-{seed:03d}.txt"
        path.write_text(circuit.render(), encoding="ascii")
        print(f"{path.name}: gates={len(circuit.gates)}")


if __name__ == "__main__":
    main()
