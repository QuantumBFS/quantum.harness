#!/usr/bin/env python3
"""Deterministically generate the four Challenge #71 candidate circuits."""

from __future__ import print_function

import argparse
import hashlib
import json
from collections import namedtuple
from pathlib import Path


SOLUTION_DIR = Path(__file__).resolve().parent
SPECS = (
    ("mystery-A.txt", 8, 9, 64, "addition"),
    ("mystery-B.txt", 7, 7, 128, "absolute_difference"),
    ("mystery-C.txt", 6, 12, 512, "multiplication"),
    ("mystery-D.txt", 5, 11, 1024, "sum_of_squares"),
)

Signal = namedtuple("Signal", "name inverted constant")
ZERO = Signal(None, False, False)
ONE = Signal(None, False, True)


def invert(signal):
    if signal.constant is not None:
        return ONE if not signal.constant else ZERO
    return Signal(signal.name, not signal.inverted, None)


def _are_complements(left, right):
    return (
        left.constant is None
        and right.constant is None
        and left.name == right.name
        and left.inverted != right.inverted
    )


class CircuitBuilder(object):
    """Build a documented fan-in-two netlist with deterministic local folding."""

    def __init__(self, input_count):
        self.input_count = input_count
        self.inputs = [
            Signal("x{}".format(index), False, None)
            for index in range(1, input_count + 1)
        ]
        self.gates = []
        self._gate_cache = {}
        self._materialized_zero = None

    @staticmethod
    def operand(signal):
        if signal.constant is not None:
            raise ValueError("a Boolean constant cannot be emitted as an operand")
        return "{}{}".format("~" if signal.inverted else "", signal.name)

    def _emit(self, operation, left, right):
        if left.constant is not None or right.constant is not None:
            raise ValueError("constants must be folded before gate emission")
        ordered = sorted((left, right), key=self.operand)
        key = (operation, self.operand(ordered[0]), self.operand(ordered[1]))
        cached = self._gate_cache.get(key)
        if cached is not None:
            return cached
        wire = Signal("w{}".format(len(self.gates) + 1), False, None)
        self.gates.append(
            (
                wire.name,
                operation,
                self.operand(ordered[0]),
                self.operand(ordered[1]),
            )
        )
        self._gate_cache[key] = wire
        return wire

    def and_(self, left, right):
        if left == ZERO or right == ZERO:
            return ZERO
        if left == ONE:
            return right
        if right == ONE:
            return left
        if left == right:
            return left
        if _are_complements(left, right):
            return ZERO
        return self._emit("AND", left, right)

    def or_(self, left, right):
        if left == ONE or right == ONE:
            return ONE
        if left == ZERO:
            return right
        if right == ZERO:
            return left
        if left == right:
            return left
        if _are_complements(left, right):
            return ONE
        return self._emit("OR", left, right)

    def xor(self, left, right):
        if left == ZERO:
            return right
        if right == ZERO:
            return left
        if left == ONE:
            return invert(right)
        if right == ONE:
            return invert(left)
        if left == right:
            return ZERO
        if _are_complements(left, right):
            return ONE
        return self._emit("XOR", left, right)

    def materialize(self, signal):
        if signal.constant is None:
            return signal
        if self._materialized_zero is None:
            self._materialized_zero = self._emit(
                "XOR", self.inputs[0], self.inputs[0]
            )
        return invert(self._materialized_zero) if signal.constant else (
            self._materialized_zero
        )

    def render(self, outputs):
        materialized = [self.materialize(output) for output in outputs]
        lines = ["INPUTS {}".format(self.input_count)]
        lines.extend(
            "{} = {} {} {}".format(wire, operation, left, right)
            for wire, operation, left, right in self.gates
        )
        lines.append(
            "OUTPUTS {}".format(
                " ".join(self.operand(output) for output in materialized)
            )
        )
        return "\n".join(lines) + "\n"


def add_unsigned(builder, left, right, width):
    """Return the low ``width`` sum bits and the carry bit."""

    carry = ZERO
    output = []
    for bit in range(width):
        left_bit = left[bit] if bit < len(left) else ZERO
        right_bit = right[bit] if bit < len(right) else ZERO
        propagate = builder.xor(left_bit, right_bit)
        output.append(builder.xor(propagate, carry))
        generate = builder.and_(left_bit, right_bit)
        carry = builder.or_(
            generate, builder.and_(propagate, carry)
        )
    return output, carry


def subtract_unsigned(builder, left, right):
    """Return ``left - right`` modulo 2**n and its final borrow bit."""

    borrow = ZERO
    output = []
    for left_bit, right_bit in zip(left, right):
        difference_without_borrow = builder.xor(left_bit, right_bit)
        output.append(builder.xor(difference_without_borrow, borrow))
        borrow = builder.or_(
            builder.and_(invert(left_bit), right_bit),
            builder.and_(invert(difference_without_borrow), borrow),
        )
    return output, borrow


def absolute_difference(builder, left, right):
    """Return ``abs(left - right)`` using the subtractor's borrow bit."""

    difference, borrow = subtract_unsigned(builder, left, right)
    output = [difference[0]]
    carry = builder.and_(invert(difference[0]), borrow)
    for bit in range(1, len(difference)):
        selected = builder.xor(difference[bit], borrow)
        output.append(builder.xor(selected, carry))
        if bit + 1 < len(difference):
            carry = builder.and_(selected, carry)
    return output


def multiply_unsigned(builder, left, right, width):
    """Return a fixed-width shift-and-add unsigned product."""

    accumulator = [ZERO] * width
    for right_index, right_bit in enumerate(right):
        row = [ZERO] * width
        for left_index, left_bit in enumerate(left):
            position = left_index + right_index
            if position < width:
                row[position] = builder.and_(left_bit, right_bit)
        accumulator, unused_carry = add_unsigned(
            builder, accumulator, row, width
        )
        del unused_carry
    return accumulator


def build_circuit(operand_width, output_width, operation):
    builder = CircuitBuilder(2 * operand_width)
    left = builder.inputs[:operand_width]
    right = builder.inputs[operand_width:]

    if operation == "addition":
        low_bits, carry = add_unsigned(
            builder, left, right, operand_width
        )
        outputs = low_bits + [carry]
    elif operation == "absolute_difference":
        outputs = absolute_difference(builder, left, right)
    elif operation == "multiplication":
        outputs = multiply_unsigned(builder, left, right, output_width)
    elif operation == "sum_of_squares":
        left_square = multiply_unsigned(
            builder, left, left, output_width
        )
        right_square = multiply_unsigned(
            builder, right, right, output_width
        )
        outputs, unused_carry = add_unsigned(
            builder, left_square, right_square, output_width
        )
        del unused_carry
    else:
        raise ValueError("unknown fixed operation {!r}".format(operation))

    if len(outputs) != output_width:
        raise ValueError(
            "{} produced {} outputs, expected {}".format(
                operation, len(outputs), output_width
            )
        )
    return builder, builder.render(outputs)


def generate_all(output_directory):
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    summary = {}
    for (
        filename,
        operand_width,
        output_width,
        gate_limit,
        operation,
    ) in SPECS:
        builder, netlist = build_circuit(
            operand_width, output_width, operation
        )
        gate_count = len(builder.gates)
        if gate_count > gate_limit:
            raise ValueError(
                "{} generated {} gates, exceeding fixed limit {}".format(
                    filename, gate_count, gate_limit
                )
            )
        encoded = netlist.encode("ascii")
        (output_directory / filename).write_bytes(encoded)
        summary[filename] = {
            "gate_count": gate_count,
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(SOLUTION_DIR),
        help="directory receiving mystery-A.txt through mystery-D.txt",
    )
    arguments = parser.parse_args(argv)
    summary = generate_all(arguments.output_dir)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
