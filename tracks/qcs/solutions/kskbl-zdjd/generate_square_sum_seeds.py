#!/usr/bin/env python3
"""Generate structurally diverse, exact 5-bit x^2+y^2 circuit seeds."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from build_exact_circuits import Circuit


HERE = Path(__file__).parent


def random_square_sum(seed: int) -> Circuit:
    rng = random.Random(seed)
    circuit = Circuit(10)
    x = [f"x{i}" for i in range(1, 6)]
    y = [f"x{i}" for i in range(6, 11)]
    columns = [[] for _ in range(12)]
    terms: list[tuple[int, str]] = []
    for variables in (x, y):
        for i, bit in enumerate(variables):
            terms.append((2 * i, bit))
        for i in range(5):
            for j in range(i + 1, 5):
                product = circuit.gate("AND", variables[i], variables[j])
                terms.append((i + j + 1, product))
    rng.shuffle(terms)
    for weight, wire in terms:
        columns[weight].append(wire)

    outputs: list[str] = []
    for weight in range(11):
        column = columns[weight]
        while len(column) > 2:
            indices = sorted(rng.sample(range(len(column)), 3), reverse=True)
            selected = [column.pop(index) for index in indices]
            rng.shuffle(selected)
            result, carry = circuit.full_adder(*selected)
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
            raise AssertionError(f"empty square-sum column {weight}")
    if columns[11]:
        raise AssertionError("overflow beyond 11 output bits")
    circuit.outputs = outputs
    return circuit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--first-seed", type=int, default=1)
    args = parser.parse_args()
    destination = HERE / "abc-work" / "square-sum-seeds"
    destination.mkdir(parents=True, exist_ok=True)
    for seed in range(args.first_seed, args.first_seed + args.count):
        circuit = random_square_sum(seed)
        path = destination / f"mystery-D-seed-{seed:03d}.txt"
        path.write_text(circuit.render(), encoding="ascii")
        print(f"{path.name}: gates={len(circuit.gates)}")


if __name__ == "__main__":
    main()
