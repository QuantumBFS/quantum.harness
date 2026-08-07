#!/usr/bin/env python3
"""Generate structurally diverse exact 8-bit ripple-adder circuits."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from build_exact_circuits import Circuit


HERE = Path(__file__).parent


def random_adder(seed: int) -> Circuit:
    rng = random.Random(seed)
    circuit = Circuit(16)
    x = [f"x{i}" for i in range(1, 9)]
    y = [f"x{i}" for i in range(9, 17)]
    result, carry = circuit.half_adder(x[0], y[0])
    outputs = [result]
    for a, b in zip(x[1:], y[1:]):
        terms = [a, b, carry]
        rng.shuffle(terms)
        result, carry = circuit.full_adder(*terms)
        outputs.append(result)
    outputs.append(carry)
    circuit.outputs = outputs
    return circuit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--first-seed", type=int, default=1)
    args = parser.parse_args()
    destination = HERE / "abc-work" / "adder-seeds"
    destination.mkdir(parents=True, exist_ok=True)
    for seed in range(args.first_seed, args.first_seed + args.count):
        circuit = random_adder(seed)
        path = destination / f"mystery-A-seed-{seed:03d}.txt"
        path.write_text(circuit.render(), encoding="ascii")
        print(f"{path.name}: gates={len(circuit.gates)}")


if __name__ == "__main__":
    main()
