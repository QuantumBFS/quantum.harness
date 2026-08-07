#!/usr/bin/env python3
"""Rank convex circuit regions by reachable boundary-state occupancy."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from score_circuits import HERE, base_operand, parse
from semantic_resub import all_truth_tables
from tensor_graph_windows import (
    boundaries,
    graph_data,
    is_convex,
    reachability,
)


@dataclass(frozen=True)
class ReachableRegion:
    indices: tuple[int, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    reachable: int
    possible: int

    @property
    def gates(self) -> int:
        return len(self.indices)

    @property
    def occupancy(self) -> float:
        return self.reachable / self.possible


def reachable_assignments(
    inputs: tuple[str, ...], values: dict[str, int], rows: int
) -> int:
    patterns: set[int] = set()
    for row in range(rows):
        packed = 0
        for index, wire in enumerate(inputs):
            packed |= ((values[wire] >> row) & 1) << index
        patterns.add(packed)
    return len(patterns)


def sample(
    source: Path,
    instance: str,
    samples: int,
    min_gates: int,
    max_gates: int,
    max_inputs: int,
    max_outputs: int,
    seed: int,
) -> list[ReachableRegion]:
    circuit, values, _ = all_truth_tables(instance, source)
    producer, consumers, neighbors = graph_data(circuit)
    ancestors, descendants = reachability(circuit, producer, consumers)
    rows = 1 << circuit.ninputs
    rng = random.Random(seed)
    accepted: dict[frozenset[int], ReachableRegion] = {}

    for _ in range(samples):
        region = frozenset({rng.randrange(len(circuit.gates))})
        target = rng.randint(min_gates, max_gates)
        while len(region) < target:
            frontier = (
                set().union(*(neighbors[index] for index in region)) - set(region)
            )
            if not frontier:
                break
            ranked: list[tuple[float, int]] = []
            for candidate in frontier:
                expanded = frozenset((*region, candidate))
                inputs, outputs = boundaries(
                    circuit, expanded, producer, consumers
                )
                penalty = len(inputs) + len(outputs) + rng.random() * 2.5
                ranked.append((penalty, candidate))
            ranked.sort()
            pool = ranked[: min(4, len(ranked))]
            region = frozenset((*region, rng.choice(pool)[1]))

        if not (min_gates <= len(region) <= max_gates):
            continue
        inputs, outputs = boundaries(circuit, region, producer, consumers)
        if not (2 <= len(inputs) <= max_inputs):
            continue
        if not (2 <= len(outputs) <= max_outputs):
            continue
        if not is_convex(
            circuit,
            region,
            producer,
            consumers,
            ancestors,
            descendants,
        ):
            continue
        ordered_inputs = tuple(
            sorted(inputs, key=lambda token: (not token.startswith("x"), token))
        )
        ordered_outputs = tuple(outputs)
        reachable = reachable_assignments(ordered_inputs, values, rows)
        accepted[region] = ReachableRegion(
            tuple(sorted(index + 1 for index in region)),
            ordered_inputs,
            ordered_outputs,
            reachable,
            1 << len(ordered_inputs),
        )
    return list(accepted.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--samples", type=int, default=50_000)
    parser.add_argument("--min-gates", type=int, default=12)
    parser.add_argument("--max-gates", type=int, default=32)
    parser.add_argument("--max-inputs", type=int, default=9)
    parser.add_argument("--max-outputs", type=int, default=7)
    parser.add_argument("--seed", type=int, default=71)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    source = args.source or (HERE / f"{args.instance}.txt")
    regions = sample(
        source,
        args.instance,
        args.samples,
        args.min_gates,
        args.max_gates,
        args.max_inputs,
        args.max_outputs,
        args.seed,
    )
    ranked = sorted(
        regions,
        key=lambda region: (
            region.occupancy,
            -region.gates,
            len(region.inputs),
            len(region.outputs),
            region.indices,
        ),
    )
    selected = ranked[: args.limit] if args.limit else ranked
    print(f"eligible_regions={len(regions)}, reported={len(selected)}")
    for rank, region in enumerate(selected, 1):
        print(
            f"{rank:03d}: gates={region.gates}, "
            f"reachable={region.reachable}/{region.possible}, "
            f"occupancy={region.occupancy:.4f}, "
            f"inputs={len(region.inputs)}, outputs={len(region.outputs)}, "
            f"indices={','.join(map(str, region.indices))}, "
            f"boundary_in={','.join(region.inputs)}, "
            f"boundary_out={','.join(region.outputs)}"
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps([asdict(region) for region in selected], indent=2),
            encoding="utf-8",
        )
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
