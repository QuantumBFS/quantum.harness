#!/usr/bin/env python3
"""Build and exhaustively verify exact circuits for Occam's Circuit A-D."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


HERE = Path(__file__).parent


@dataclass
class Circuit:
    ninputs: int
    gates: list[tuple[str, str, str, str]] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)

    def gate(self, op: str, a: str, b: str) -> str:
        wire = f"w{len(self.gates) + 1}"
        self.gates.append((wire, op, a, b))
        return wire

    def half_adder(self, a: str, b: str) -> tuple[str, str]:
        return self.gate("XOR", a, b), self.gate("AND", a, b)

    def full_adder(self, a: str, b: str, carry: str) -> tuple[str, str]:
        t = self.gate("XOR", a, b)
        result = self.gate("XOR", t, carry)
        generate = self.gate("AND", a, b)
        propagate = self.gate("AND", t, carry)
        carry_out = self.gate("OR", generate, propagate)
        return result, carry_out

    def render(self) -> str:
        lines = [f"INPUTS {self.ninputs}"]
        lines.extend(f"{w} = {op} {a} {b}" for w, op, a, b in self.gates)
        lines.append("OUTPUTS " + " ".join(self.outputs))
        return "\n".join(lines) + "\n"

    def evaluate(self, input_bits: list[bool]) -> list[bool]:
        values = {f"x{i + 1}": bit for i, bit in enumerate(input_bits)}

        def operand(token: str) -> bool:
            if token.startswith("~"):
                return not values[token[1:]]
            return values[token]

        operations = {
            "AND": lambda a, b: a and b,
            "OR": lambda a, b: a or b,
            "XOR": lambda a, b: a != b,
            "NAND": lambda a, b: not (a and b),
            "NOR": lambda a, b: not (a or b),
            "XNOR": lambda a, b: a == b,
        }
        for wire, op, a, b in self.gates:
            values[wire] = operations[op](operand(a), operand(b))
        return [operand(token) for token in self.outputs]


def reduce_weighted_bits(
    circuit: Circuit, columns: list[list[str]], output_width: int
) -> list[str]:
    """Add one-bit terms grouped by binary weight, producing one output per column."""
    while len(columns) < output_width + 1:
        columns.append([])
    outputs: list[str] = []
    for weight in range(output_width):
        column = columns[weight]
        while len(column) > 2:
            a, b, carry_in = column.pop(), column.pop(), column.pop()
            result, carry_out = circuit.full_adder(a, b, carry_in)
            column.append(result)
            columns[weight + 1].append(carry_out)
        if len(column) == 2:
            result, carry_out = circuit.half_adder(column[0], column[1])
            outputs.append(result)
            columns[weight + 1].append(carry_out)
        elif len(column) == 1:
            outputs.append(column[0])
        else:
            raise AssertionError(f"constant-zero output required at weight {weight}")
    if columns[output_width]:
        raise AssertionError("arithmetic overflow beyond declared output width")
    return outputs


def build_a() -> Circuit:
    circuit = Circuit(16)
    x = [f"x{i}" for i in range(1, 9)]
    y = [f"x{i}" for i in range(9, 17)]
    result, carry = circuit.half_adder(x[0], y[0])
    outputs = [result]
    for a, b in zip(x[1:], y[1:]):
        result, carry = circuit.full_adder(a, b, carry)
        outputs.append(result)
    outputs.append(carry)
    circuit.outputs = outputs
    return circuit


def build_b() -> Circuit:
    circuit = Circuit(14)
    x = [f"x{i}" for i in range(1, 8)]
    y = [f"x{i}" for i in range(8, 15)]

    difference = [circuit.gate("XOR", x[0], y[0])]
    borrow = circuit.gate("AND", f"~{x[0]}", y[0])
    for a, b in zip(x[1:], y[1:]):
        t = circuit.gate("XOR", a, b)
        difference.append(circuit.gate("XOR", t, borrow))
        borrow_generate = circuit.gate("AND", f"~{a}", b)
        borrow_propagate = circuit.gate("AND", f"~{t}", borrow)
        borrow = circuit.gate("OR", borrow_generate, borrow_propagate)

    # If x<y, convert the modulo-2^7 difference to its two's complement.
    carry = borrow
    outputs: list[str] = []
    for bit in difference:
        selected = circuit.gate("XOR", bit, borrow)
        outputs.append(circuit.gate("XOR", selected, carry))
        carry = circuit.gate("AND", selected, carry)
    circuit.outputs = outputs
    return circuit


def build_c() -> Circuit:
    circuit = Circuit(12)
    x = [f"x{i}" for i in range(1, 7)]
    y = [f"x{i}" for i in range(7, 13)]
    columns = [[] for _ in range(13)]
    for i, a in enumerate(x):
        for j, b in enumerate(y):
            columns[i + j].append(circuit.gate("AND", a, b))
    circuit.outputs = reduce_weighted_bits(circuit, columns, 12)
    return circuit


def build_d() -> Circuit:
    circuit = Circuit(10)
    x = [f"x{i}" for i in range(1, 6)]
    y = [f"x{i}" for i in range(6, 11)]
    columns = [[] for _ in range(12)]

    # For a square, diagonal terms x_i*x_i equal x_i.  Symmetric off-diagonal
    # terms occur twice, so 2*x_i*x_j is placed directly in weight i+j+1.
    for variables in (x, y):
        for i, bit in enumerate(variables):
            columns[2 * i].append(bit)
        for i in range(5):
            for j in range(i + 1, 5):
                columns[i + j + 1].append(
                    circuit.gate("AND", variables[i], variables[j])
                )
    circuit.outputs = reduce_weighted_bits(circuit, columns, 11)
    return circuit


def bits_lsb_first(value: int, width: int) -> list[bool]:
    return [bool((value >> bit) & 1) for bit in range(width)]


def verify_exhaustively(
    name: str,
    circuit: Circuit,
    n: int,
    width: int,
    formula: Callable[[int, int], int],
) -> None:
    tested = 0
    for x in range(2**n):
        for y in range(2**n):
            inputs = bits_lsb_first(x, n) + bits_lsb_first(y, n)
            actual = circuit.evaluate(inputs)
            expected = bits_lsb_first(formula(x, y), width)
            if actual != expected:
                raise AssertionError(
                    f"{name} failed for x={x}, y={y}: {actual} != {expected}"
                )
            tested += 1
    print(
        f"{name}: gates={len(circuit.gates)}, "
        f"exhaustive exact matches={tested}/{tested}"
    )


def main() -> None:
    designs = {
        "mystery-A": (build_a(), 8, 9, lambda x, y: x + y),
        "mystery-B": (build_b(), 7, 7, lambda x, y: abs(x - y)),
        "mystery-C": (build_c(), 6, 12, lambda x, y: x * y),
        "mystery-D": (build_d(), 5, 11, lambda x, y: x**2 + y**2),
    }
    output_directory = HERE / "baselines"
    output_directory.mkdir(exist_ok=True)
    for name, (circuit, n, width, formula) in designs.items():
        path = output_directory / f"{name}-baseline.txt"
        path.write_text(circuit.render(), encoding="utf-8")
        verify_exhaustively(name, circuit, n, width, formula)
        print(f"  wrote {path}")


if __name__ == "__main__":
    main()
