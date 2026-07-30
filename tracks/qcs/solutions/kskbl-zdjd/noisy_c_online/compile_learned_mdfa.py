"""Compile learned weighted Boolean terms with a generic MDFA schedule search."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from train_quadratic_discovery import (
    DOMAIN_SIZE,
    INPUT_BITS,
    OUTPUT_BITS,
    coefficients_to_values,
    quadratic_features,
    values_to_bits,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-network", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class EncodedPair:
    base: str
    xor: str


class CircuitBuilder:
    def __init__(self) -> None:
        self.gates: list[dict[str, str]] = []

    def gate(self, op: str, left: str, right: str) -> str:
        output = f"g{len(self.gates)}"
        self.gates.append(
            {"op": op, "a": left, "b": right, "out": output}
        )
        return output

    def xor(self, left: str, right: str) -> str:
        return self.gate("XOR", left, right)

    def and_(self, left: str, right: str) -> str:
        return self.gate("AND", left, right)

    def or_(self, left: str, right: str) -> str:
        return self.gate("OR", left, right)

    def gt(self, left: str, right: str) -> str:
        return self.gate("AND", left, f"~{right}")


def half_adder(
    builder: CircuitBuilder,
    left: str,
    right: str,
) -> tuple[str, str]:
    return builder.xor(left, right), builder.and_(left, right)


def full_adder(
    builder: CircuitBuilder,
    first: str,
    second: str,
    third: str,
) -> tuple[str, str]:
    first_xor_second = builder.xor(first, second)
    second_xor_third = builder.xor(second, third)
    either_differs = builder.or_(first_xor_second, second_xor_third)
    total = builder.xor(first_xor_second, third)
    carry = builder.xor(either_differs, total)
    return total, carry


def special_full_adder(
    builder: CircuitBuilder,
    single: str,
    pair: EncodedPair,
) -> tuple[str, str]:
    total = builder.xor(single, pair.xor)
    pair_carry = builder.gt(pair.base, pair.xor)
    mixed_carry = builder.and_(single, pair.xor)
    carry = builder.xor(pair_carry, mixed_carry)
    return total, carry


def mdfa(
    builder: CircuitBuilder,
    single: str,
    first: EncodedPair,
    second: EncodedPair,
) -> tuple[str, EncodedPair]:
    first_base_xor_single = builder.xor(first.base, single)
    disjunction = builder.or_(first.xor, first_base_xor_single)
    first_xor_single = builder.xor(first.xor, single)
    carry_base = builder.xor(disjunction, first_xor_single)
    second_base_xor = builder.xor(second.base, first_xor_single)
    total = builder.xor(first_xor_single, second.xor)
    carry_difference = builder.gt(second_base_xor, second.xor)
    carry_xor = builder.xor(disjunction, carry_difference)
    return total, EncodedPair(carry_base, carry_xor)


Action = str
CarryState = tuple[int, int]


@lru_cache(maxsize=None)
def local_reductions(
    initial_singles: int,
    initial_pairs: int,
) -> dict[CarryState, tuple[int, tuple[Action, ...]]]:
    """Enumerate minimum-cost ways to leave one output bit in a column."""

    start = (initial_singles, initial_pairs, 0, 0)
    queue: list[tuple[int, tuple[int, int, int, int], tuple[Action, ...]]] = [
        (0, start, ())
    ]
    best = {start: 0}
    outputs: dict[CarryState, tuple[int, tuple[Action, ...]]] = {}
    while queue:
        cost, state, actions = heapq.heappop(queue)
        if cost != best[state]:
            continue
        singles, pairs, next_singles, next_pairs = state
        if singles == 1 and pairs == 0:
            carry = (next_singles, next_pairs)
            previous = outputs.get(carry)
            if previous is None or cost < previous[0]:
                outputs[carry] = (cost, actions)
            continue

        transitions: list[
            tuple[tuple[int, int, int, int], int, Action]
        ] = []
        if singles >= 2:
            transitions.append(
                (
                    (singles - 2, pairs + 1, next_singles, next_pairs),
                    1,
                    "ENCODE",
                )
            )
            transitions.append(
                (
                    (singles - 1, pairs, next_singles + 1, next_pairs),
                    2,
                    "HA",
                )
            )
        if singles >= 3:
            transitions.append(
                (
                    (singles - 2, pairs, next_singles + 1, next_pairs),
                    5,
                    "FA3",
                )
            )
        if singles >= 1 and pairs >= 2:
            transitions.append(
                (
                    (singles, pairs - 2, next_singles, next_pairs + 1),
                    8,
                    "MDFA",
                )
            )
        if singles >= 1 and pairs >= 1:
            transitions.append(
                (
                    (singles, pairs - 1, next_singles + 1, next_pairs),
                    4,
                    "SFA3",
                )
            )

        for next_state, added_cost, action in transitions:
            next_cost = cost + added_cost
            if next_cost < best.get(next_state, 1 << 30):
                best[next_state] = next_cost
                heapq.heappush(
                    queue,
                    (next_cost, next_state, actions + (action,)),
                )
    return outputs


def optimize_schedule(
    base_counts: tuple[int, ...],
) -> tuple[int, list[tuple[Action, ...]]]:
    """Dynamic program over columns; it sees only weighted term counts."""

    states: dict[
        CarryState,
        tuple[int, list[tuple[Action, ...]]],
    ] = {(0, 0): (0, [])}
    for base_count in base_counts:
        next_states: dict[
            CarryState,
            tuple[int, list[tuple[Action, ...]]],
        ] = {}
        for (carry_singles, carry_pairs), (cost, schedule) in states.items():
            options = local_reductions(
                base_count + carry_singles,
                carry_pairs,
            )
            for next_carry, (local_cost, actions) in options.items():
                candidate = (cost + local_cost, schedule + [actions])
                previous = next_states.get(next_carry)
                if previous is None or candidate[0] < previous[0]:
                    next_states[next_carry] = candidate
        states = next_states
    if (0, 0) not in states:
        raise ValueError("no overflow-free compressor schedule exists")
    return states[(0, 0)]


def take(items: list[Any], count: int) -> list[Any]:
    if len(items) < count:
        raise AssertionError(f"need {count} items, found {len(items)}")
    selected = items[:count]
    del items[:count]
    return selected


def feature_signal(
    builder: CircuitBuilder,
    feature: dict[str, Any],
) -> str:
    bits = feature["input_bits"]
    if not bits:
        return "c1"
    if len(bits) == 1:
        return f"i{bits[0]}"
    if len(bits) == 2:
        return builder.and_(f"i{bits[0]}", f"i{bits[1]}")
    raise ValueError("compiler supports degree-two features")


def compile_network(
    coefficient_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    builder = CircuitBuilder()
    singles: list[list[str]] = [[] for _ in range(OUTPUT_BITS + 1)]
    pairs: list[list[EncodedPair]] = [
        [] for _ in range(OUTPUT_BITS + 1)
    ]
    active_features = []
    for row in coefficient_rows:
        coefficient_mod = int(row["coefficient"]) % (1 << OUTPUT_BITS)
        if coefficient_mod == 0:
            continue
        signal = feature_signal(builder, row)
        active_features.append(row)
        for bit in range(OUTPUT_BITS):
            if coefficient_mod & (1 << bit):
                singles[bit].append(signal)

    base_counts = tuple(len(column) for column in singles[:OUTPUT_BITS])
    compressor_cost, schedule = optimize_schedule(base_counts)
    outputs: list[str] = []
    action_counts: Counter[str] = Counter()
    for column, actions in enumerate(schedule):
        for action in actions:
            action_counts[action] += 1
            if action == "ENCODE":
                left, right = take(singles[column], 2)
                pairs[column].append(
                    EncodedPair(left, builder.xor(left, right))
                )
            elif action == "HA":
                left, right = take(singles[column], 2)
                total, carry = half_adder(builder, left, right)
                singles[column].append(total)
                singles[column + 1].append(carry)
            elif action == "FA3":
                first, second, third = take(singles[column], 3)
                total, carry = full_adder(
                    builder,
                    first,
                    second,
                    third,
                )
                singles[column].append(total)
                singles[column + 1].append(carry)
            elif action == "MDFA":
                first, second = take(pairs[column], 2)
                (single,) = take(singles[column], 1)
                total, carry_pair = mdfa(
                    builder,
                    single,
                    first,
                    second,
                )
                singles[column].append(total)
                pairs[column + 1].append(carry_pair)
            elif action == "SFA3":
                (pair,) = take(pairs[column], 1)
                (single,) = take(singles[column], 1)
                total, carry = special_full_adder(
                    builder,
                    single,
                    pair,
                )
                singles[column].append(total)
                singles[column + 1].append(carry)
            else:
                raise ValueError(f"unknown action: {action}")
        if len(singles[column]) != 1 or pairs[column]:
            raise AssertionError(
                f"column {column} did not reduce to one output"
            )
        outputs.append(singles[column][0])
    if singles[OUTPUT_BITS] or pairs[OUTPUT_BITS]:
        raise AssertionError("unexpected arithmetic overflow")

    gate_breakdown = Counter(gate["op"] for gate in builder.gates)
    return {
        "kind": "learned-generic-mdfa-gate-network",
        "input_bits": INPUT_BITS,
        "output_bits": OUTPUT_BITS,
        "active_features": active_features,
        "base_weighted_term_counts": list(base_counts),
        "schedule": [list(actions) for actions in schedule],
        "gates": builder.gates,
        "outputs": outputs,
        "stats": {
            "active_integer_features": len(active_features),
            "partial_feature_gates": len(active_features),
            "compressor_gate_cost": compressor_cost,
            "two_input_gates": len(builder.gates),
            "gate_breakdown": dict(sorted(gate_breakdown.items())),
            "action_counts": dict(sorted(action_counts.items())),
            "schedule_derived_only_from_term_counts": True,
        },
    }


def operand(signals: dict[str, np.ndarray], token: str) -> np.ndarray:
    if token.startswith("~"):
        return 1 ^ signals[token[1:]]
    return signals[token]


def evaluate_network(network: dict[str, Any]) -> np.ndarray:
    ids = np.arange(DOMAIN_SIZE, dtype=np.uint16)
    signals: dict[str, np.ndarray] = {
        "c0": np.zeros(DOMAIN_SIZE, dtype=np.uint8),
        "c1": np.ones(DOMAIN_SIZE, dtype=np.uint8),
    }
    for bit in range(INPUT_BITS):
        signals[f"i{bit}"] = ((ids >> bit) & 1).astype(np.uint8)
    for gate in network["gates"]:
        left = operand(signals, gate["a"])
        right = operand(signals, gate["b"])
        if gate["op"] == "AND":
            result = left & right
        elif gate["op"] == "OR":
            result = left | right
        elif gate["op"] == "XOR":
            result = left ^ right
        else:
            raise ValueError(f"unsupported gate: {gate['op']}")
        signals[gate["out"]] = result
    return np.stack(
        [operand(signals, signal) for signal in network["outputs"]],
        axis=1,
    )


def main() -> None:
    args = parse_args()
    source = json.loads(args.source_run.read_text(encoding="utf-8"))
    coefficient_rows = source["integer_coefficients"]
    network = compile_network(coefficient_rows)
    prediction = evaluate_network(network)
    features, _ = quadratic_features()
    coefficients = np.asarray(
        [row["coefficient"] for row in coefficient_rows],
        dtype=np.int64,
    )
    expected_values = coefficients_to_values(features, coefficients)
    expected_bits = values_to_bits(expected_values)
    if not np.array_equal(prediction, expected_bits):
        raise AssertionError("MDFA network does not reproduce learned rule")
    network["provenance"] = {
        "source_run": args.source_run.as_posix(),
        "source_run_sha256": sha256(args.source_run),
        "target_formula_seeded": False,
        "existing_circuit_seeded": False,
        "compressor_schedule_seeded": False,
    }
    network["verification"] = {
        "domain_size": DOMAIN_SIZE,
        "matches_learned_integer_rule": True,
    }
    args.output_network.parent.mkdir(parents=True, exist_ok=True)
    args.output_network.write_text(
        json.dumps(network, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output_network": args.output_network.as_posix(),
                **network["stats"],
                "output_sha256": sha256(args.output_network),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
