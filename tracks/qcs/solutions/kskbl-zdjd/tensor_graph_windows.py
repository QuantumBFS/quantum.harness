#!/usr/bin/env python3
"""Search non-interval low-boundary tensor-network regions."""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from score_circuits import HERE, base_operand, parse
from tensor_window_search import apply_gate, exact_gate_count


@dataclass(frozen=True)
class RegionTensor:
    indices: frozenset[int]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    truths: tuple[str, ...]

    @property
    def gates(self) -> int:
        return len(self.indices)


def graph_data(circuit):
    producer = {wire: index for index, (wire, _, _, _) in enumerate(circuit.gates)}
    consumers: dict[str, set[int]] = defaultdict(set)
    neighbors: list[set[int]] = [set() for _ in circuit.gates]
    for index, (_, _, a, b) in enumerate(circuit.gates):
        for operand in (a, b):
            base = base_operand(operand)
            consumers[base].add(index)
            if base in producer:
                parent = producer[base]
                neighbors[index].add(parent)
                neighbors[parent].add(index)
    return producer, consumers, neighbors


def reachability(circuit, producer, consumers):
    """Return transitive ancestor/descendant bitsets for the gate DAG."""
    ancestors = [0] * len(circuit.gates)
    for index, (_, _, a, b) in enumerate(circuit.gates):
        bits = 0
        for operand in (a, b):
            parent = producer.get(base_operand(operand))
            if parent is not None:
                bits |= ancestors[parent] | (1 << parent)
        ancestors[index] = bits

    descendants = [0] * len(circuit.gates)
    for index in range(len(circuit.gates) - 1, -1, -1):
        wire = circuit.gates[index][0]
        bits = 0
        for child in consumers[wire]:
            bits |= descendants[child] | (1 << child)
        descendants[index] = bits
    return ancestors, descendants


def boundaries(circuit, indices: frozenset[int], producer, consumers):
    wires = {circuit.gates[index][0] for index in indices}
    inputs: set[str] = set()
    for index in indices:
        _, _, a, b = circuit.gates[index]
        for operand in (a, b):
            base = base_operand(operand)
            if base not in wires:
                inputs.add(base)
    final_outputs = {base_operand(output) for output in circuit.outputs}
    outputs = []
    for index in sorted(indices):
        wire = circuit.gates[index][0]
        if wire in final_outputs or any(user not in indices for user in consumers[wire]):
            outputs.append(wire)
    return inputs, outputs


def is_convex(
    circuit,
    indices: frozenset[int],
    producer,
    consumers,
    ancestors=None,
    descendants=None,
) -> bool:
    """Reject regions whose output leaves and later re-enters the region."""
    if ancestors is not None and descendants is not None:
        region_bits = sum(1 << index for index in indices)
        low, high = min(indices), max(indices)
        for index in range(low + 1, high):
            if index in indices:
                continue
            if ancestors[index] & region_bits and descendants[index] & region_bits:
                return False
        return True

    reachable_outside: set[int] = set()
    stack: list[int] = []
    for index in indices:
        wire = circuit.gates[index][0]
        for user in consumers[wire]:
            if user not in indices:
                stack.append(user)
    while stack:
        index = stack.pop()
        if index in reachable_outside:
            continue
        reachable_outside.add(index)
        wire = circuit.gates[index][0]
        for user in consumers[wire]:
            if user in indices:
                return False
            stack.append(user)
    return True


def contract(
    circuit,
    indices: frozenset[int],
    producer,
    consumers,
    ancestors=None,
    descendants=None,
):
    if not is_convex(
        circuit, indices, producer, consumers, ancestors, descendants
    ):
        return None
    inputs, outputs = boundaries(circuit, indices, producer, consumers)
    ordered_inputs = tuple(
        sorted(inputs, key=lambda token: (not token.startswith("x"), token))
    )
    ordered_outputs = tuple(outputs)
    truth_values = [0] * len(ordered_outputs)
    for packed in range(1 << len(ordered_inputs)):
        values = {
            wire: bool((packed >> index) & 1)
            for index, wire in enumerate(ordered_inputs)
        }

        def get(token: str) -> bool:
            value = values[base_operand(token)]
            return not value if token.startswith("~") else value

        for index, (wire, op, a, b) in enumerate(circuit.gates):
            if index in indices:
                values[wire] = apply_gate(op, get(a), get(b))
        for position, output in enumerate(ordered_outputs):
            truth_values[position] |= int(values[output]) << packed
    digits = max(1, 1 << max(0, len(ordered_inputs) - 2))
    truths = tuple(f"{value:0{digits}X}" for value in truth_values)
    return RegionTensor(indices, ordered_inputs, ordered_outputs, truths)


def sample_regions(
    circuit,
    neighbors,
    producer,
    consumers,
    samples: int,
    min_gates: int,
    max_gates: int,
    max_inputs: int,
    max_outputs: int,
    seed: int,
    ancestors=None,
    descendants=None,
):
    rng = random.Random(seed)
    accepted: dict[frozenset[int], RegionTensor] = {}
    for sample in range(samples):
        region = frozenset({rng.randrange(len(circuit.gates))})
        target = rng.randint(min_gates, max_gates)
        while len(region) < target:
            frontier = set().union(*(neighbors[index] for index in region)) - set(region)
            if not frontier:
                break
            ranked = []
            for candidate in frontier:
                expanded = frozenset((*region, candidate))
                inputs, outputs = boundaries(circuit, expanded, producer, consumers)
                penalty = len(inputs) + len(outputs) + rng.random() * 2.5
                ranked.append((penalty, candidate))
            ranked.sort()
            choice_pool = ranked[: min(4, len(ranked))]
            region = frozenset((*region, rng.choice(choice_pool)[1]))
        if not (min_gates <= len(region) <= max_gates):
            continue
        inputs, outputs = boundaries(circuit, region, producer, consumers)
        if not (2 <= len(inputs) <= max_inputs):
            continue
        if not (1 <= len(outputs) <= max_outputs):
            continue
        tensor = contract(
            circuit, region, producer, consumers, ancestors, descendants
        )
        if tensor is not None:
            accepted[region] = tensor
    return list(accepted.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--samples", type=int, default=20_000)
    parser.add_argument("--min-gates", type=int, default=5)
    parser.add_argument("--max-gates", type=int, default=10)
    parser.add_argument("--max-inputs", type=int, default=6)
    parser.add_argument("--max-outputs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=71)
    parser.add_argument("--run-exact", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=8)
    parser.add_argument("--conflicts", type=int, default=500_000)
    args = parser.parse_args()

    source = args.source or (HERE / f"{args.instance}.txt")
    circuit = parse(source)
    producer, consumers, neighbors = graph_data(circuit)
    ancestors, descendants = reachability(circuit, producer, consumers)
    regions = sample_regions(
        circuit,
        neighbors,
        producer,
        consumers,
        args.samples,
        args.min_gates,
        args.max_gates,
        args.max_inputs,
        args.max_outputs,
        args.seed,
        ancestors,
        descendants,
    )
    unique: dict[tuple[int, tuple[str, ...]], RegionTensor] = {}
    for region in regions:
        key = len(region.inputs), region.truths
        previous = unique.get(key)
        if previous is None or region.gates > previous.gates:
            unique[key] = region
    representatives = sorted(
        unique.values(),
        key=lambda region: (
            -region.gates,
            len(region.inputs),
            len(region.outputs),
            tuple(sorted(region.indices)),
        ),
    )
    representatives = representatives[args.skip :]
    if args.limit:
        representatives = representatives[: args.limit]
    print(
        f"sampled_regions={len(regions)}, unique_tensors={len(unique)}, "
        f"representatives={len(representatives)}"
    )

    abc = (
        HERE
        / "tools"
        / "oss-cad-suite"
        / "oss-cad-suite"
        / "bin"
        / "yosys-abc.exe"
    )
    work = HERE / "abc-work" / "tensor-graph"
    work.mkdir(parents=True, exist_ok=True)
    for index, region in enumerate(representatives, 1):
        prefix = (
            f"{index:03d}: gates={region.gates}, "
            f"indices={','.join(str(value + 1) for value in sorted(region.indices))}, "
            f"inputs={len(region.inputs)}, outputs={len(region.outputs)}"
        )
        if not args.run_exact:
            print(
                f"{prefix}, boundary_in={','.join(region.inputs)}, "
                f"boundary_out={','.join(region.outputs)}"
            )
            continue
        count, detail = exact_gate_count(
            abc,
            region,
            work,
            args.conflicts,
            args.timeout,
            1,
        )
        status = "IMPROVE" if count is not None and count < region.gates else "no"
        print(f"{prefix}, exact={count}, status={status}, detail={detail}")


if __name__ == "__main__":
    main()
