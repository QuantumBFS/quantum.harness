"""Generate Sergeev's 158-gate 6x6 multiplier.

The construction follows the column schedule in arXiv:1602.02362.  A pair of
same-weight bits (a, b) is represented as (a, a XOR b).  MDFA blocks preserve
that representation for their two carry bits.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EncodedPair:
    base: str
    xor: str


class CircuitBuilder:
    def __init__(self) -> None:
        self.gates: list[tuple[str, str, str, str]] = []
        self.counts: Counter[str] = Counter()

    def gate(self, op: str, left: str, right: str) -> str:
        name = f"g{len(self.gates) + 1}"
        self.gates.append((name, op, left, right))
        self.counts[op] += 1
        return name

    def xor(self, left: str, right: str) -> str:
        return self.gate("XOR", left, right)

    def and_(self, left: str, right: str) -> str:
        return self.gate("AND", left, right)

    def or_(self, left: str, right: str) -> str:
        return self.gate("OR", left, right)

    def gt(self, left: str, right: str) -> str:
        return self.gate("AND", left, f"~{right}")


def add_ha(builder: CircuitBuilder, a: str, b: str) -> tuple[str, str]:
    """Two-gate half adder: return (sum, carry)."""
    return builder.xor(a, b), builder.and_(a, b)


def add_fa3(
    builder: CircuitBuilder, a: str, b: str, c: str
) -> tuple[str, str]:
    """Five-gate three-input full adder: return (sum, carry)."""
    a_xor_b = builder.xor(a, b)
    b_xor_c = builder.xor(b, c)
    either_differs = builder.or_(a_xor_b, b_xor_c)
    sum_bit = builder.xor(a_xor_b, c)
    carry = builder.xor(either_differs, sum_bit)
    return sum_bit, carry


def add_sfa3(
    builder: CircuitBuilder, z: str, pair: EncodedPair
) -> tuple[str, str]:
    """Four-gate full adder for inputs z, a, b encoded as z, a, a XOR b."""
    sum_bit = builder.xor(z, pair.xor)
    pair_carry = builder.gt(pair.base, pair.xor)
    mixed_carry = builder.and_(z, pair.xor)
    carry = builder.xor(pair_carry, mixed_carry)
    return sum_bit, carry


def add_mdfa(
    builder: CircuitBuilder,
    z: str,
    first: EncodedPair,
    second: EncodedPair,
) -> tuple[str, EncodedPair]:
    """Eight-gate MDFA.

    The five represented inputs have total

        z + a + b + c + d = v + 2*u1 + 2*u2.

    Return v and the encoded carry pair (u1, u1 XOR u2).
    """
    g1 = builder.xor(first.base, z)
    g2 = builder.or_(first.xor, g1)
    g3 = builder.xor(first.xor, z)
    u1 = builder.xor(g2, g3)
    g5 = builder.xor(second.base, g3)
    v = builder.xor(g3, second.xor)
    g7 = builder.gt(g5, second.xor)
    u1_xor_u2 = builder.xor(g2, g7)
    return v, EncodedPair(u1, u1_xor_u2)


def take(items: list[str], count: int) -> list[str]:
    if len(items) < count:
        raise RuntimeError(f"need {count} single bits, only {len(items)} remain")
    selected = items[:count]
    del items[:count]
    return selected


def build_multiplier() -> tuple[CircuitBuilder, list[str], Counter[str]]:
    builder = CircuitBuilder()
    singles: list[list[str]] = [[] for _ in range(12)]
    pairs: list[list[EncodedPair]] = [[] for _ in range(12)]

    # Inputs x1..x6 and x7..x12 are the two unsigned six-bit operands,
    # ordered from least significant to most significant bit.
    for i in range(6):
        for j in range(6):
            product = builder.and_(f"x{i + 1}", f"x{j + 7}")
            singles[i + j].append(product)

    mdfa_count = {3: 1, 4: 1, 5: 2, 6: 2, 7: 2, 8: 1, 9: 1}
    fa3_count = {2: 1, 4: 1, 8: 1}
    ha_count = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}
    block_counts: Counter[str] = Counter(partial_products=36)
    outputs: list[str] = []

    for weight in range(12):
        for _ in range(mdfa_count.get(weight, 0)):
            while len(pairs[weight]) < 2:
                a, b = take(singles[weight], 2)
                pairs[weight].append(EncodedPair(a, builder.xor(a, b)))
                block_counts["encoding_xor"] += 1

            first = pairs[weight].pop(0)
            second = pairs[weight].pop(0)
            (z,) = take(singles[weight], 1)
            value, carry_pair = add_mdfa(builder, z, first, second)
            singles[weight].append(value)
            pairs[weight + 1].append(carry_pair)
            block_counts["mdfa"] += 1

        for _ in range(fa3_count.get(weight, 0)):
            a, b, c = take(singles[weight], 3)
            value, carry = add_fa3(builder, a, b, c)
            singles[weight].append(value)
            singles[weight + 1].append(carry)
            block_counts["fa3"] += 1

        for _ in range(ha_count.get(weight, 0)):
            a, b = take(singles[weight], 2)
            value, carry = add_ha(builder, a, b)
            singles[weight].append(value)
            singles[weight + 1].append(carry)
            block_counts["ha"] += 1

        if weight == 10:
            if len(pairs[weight]) != 1:
                raise RuntimeError("SFA3 column must contain exactly one encoded pair")
            (z,) = take(singles[weight], 1)
            value, carry = add_sfa3(builder, z, pairs[weight].pop())
            singles[weight].append(value)
            singles[weight + 1].append(carry)
            block_counts["sfa3"] += 1

        if len(singles[weight]) != 1 or pairs[weight]:
            raise RuntimeError(
                f"column {weight}: singles={len(singles[weight])}, "
                f"pairs={len(pairs[weight])}"
            )
        outputs.append(singles[weight][0])

    expected_blocks = Counter(
        partial_products=36,
        ha=6,
        fa3=3,
        sfa3=1,
        mdfa=10,
        encoding_xor=11,
    )
    if block_counts != expected_blocks:
        raise RuntimeError(f"unexpected block counts: {block_counts}")
    if len(builder.gates) != 158:
        raise RuntimeError(f"expected 158 gates, got {len(builder.gates)}")
    return builder, outputs, block_counts


def write_circuit(path: Path) -> None:
    builder, outputs, block_counts = build_multiplier()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["INPUTS 12"]
    lines.extend(
        f"{name} = {op} {left} {right}"
        for name, op, left, right in builder.gates
    )
    lines.append("OUTPUTS " + " ".join(outputs))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path}")
    print(f"gates: {len(builder.gates)}")
    print("blocks: " + ", ".join(f"{key}={value}" for key, value in sorted(block_counts.items())))
    print("operators: " + ", ".join(f"{key}={value}" for key, value in sorted(builder.counts.items())))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path("abc-work") / "sergeev-158" / "mystery-C.txt",
    )
    args = parser.parse_args()
    write_circuit(args.output.resolve())


if __name__ == "__main__":
    main()
