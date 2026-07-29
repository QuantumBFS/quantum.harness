#!/usr/bin/env python3
"""Generate structurally diverse, exact 6x6 multiplier seeds."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from build_exact_circuits import Circuit


HERE = Path(__file__).parent


def random_reduction(seed: int) -> Circuit:
    rng = random.Random(seed)
    circuit = Circuit(12)
    x = [f"x{i}" for i in range(1, 7)]
    y = [f"x{i}" for i in range(7, 13)]
    columns = [[] for _ in range(13)]
    partial_products: list[tuple[int, str]] = []
    for i, a in enumerate(x):
        for j, b in enumerate(y):
            partial_products.append((i + j, circuit.gate("AND", a, b)))
    rng.shuffle(partial_products)
    for weight, wire in partial_products:
        columns[weight].append(wire)

    outputs: list[str] = []
    for weight in range(12):
        column = columns[weight]
        while len(column) > 2:
            indices = sorted(rng.sample(range(len(column)), 3), reverse=True)
            terms = [column.pop(index) for index in indices]
            rng.shuffle(terms)
            result, carry = circuit.full_adder(*terms)
            column.append(result)
            columns[weight + 1].append(carry)
            rng.shuffle(column)
            rng.shuffle(columns[weight + 1])
        if len(column) == 2:
            rng.shuffle(column)
            result, carry = circuit.half_adder(column[0], column[1])
            outputs.append(result)
            columns[weight + 1].append(carry)
        elif len(column) == 1:
            outputs.append(column[0])
        else:
            raise AssertionError(f"empty product column {weight}")
    if columns[12]:
        raise AssertionError("overflow beyond 12 product bits")
    circuit.outputs = outputs
    return circuit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--first-seed", type=int, default=1)
    args = parser.parse_args()
    destination = HERE / "abc-work" / "multiplier-seeds"
    destination.mkdir(parents=True, exist_ok=True)
    for seed in range(args.first_seed, args.first_seed + args.count):
        circuit = random_reduction(seed)
        path = destination / f"mystery-C-seed-{seed:03d}.txt"
        path.write_text(circuit.render(), encoding="ascii")
        print(f"{path.name}: gates={len(circuit.gates)}")


if __name__ == "__main__":
    main()
