#!/usr/bin/env python3
"""Independent evaluator for the documented Occam's Circuit language."""

from __future__ import print_function

import argparse
import csv
import io
import json
import re
import resource
import sys
from collections import namedtuple
from pathlib import Path


Operand = namedtuple("Operand", "kind index inverted")
Gate = namedtuple("Gate", "wire operation left right")
Circuit = namedtuple("Circuit", "input_count gates outputs")


class EvaluationError(Exception):
    """A user-facing contract error with no Python traceback."""


def _contract_error(source, line_number, message):
    if line_number is None:
        raise EvaluationError("{}: {}".format(source, message))
    raise EvaluationError("{}:{}: {}".format(source, line_number, message))


def _and(left, right):
    return left and right


def _or(left, right):
    return left or right


def _xor(left, right):
    return left != right


OPERATIONS = {
    "AND": _and,
    "OR": _or,
    "XOR": _xor,
    "NAND": lambda left, right: not _and(left, right),
    "NOR": lambda left, right: not _or(left, right),
    "XNOR": lambda left, right: not _xor(left, right),
}


OPERAND_PATTERN = re.compile(r"^(~)?([xw])([1-9][0-9]*)$")
WIRE_TARGET_PATTERN = re.compile(r"^w([1-9][0-9]*)$")
POSITIVE_DECIMAL_PATTERN = re.compile(r"^[1-9][0-9]*$")
BINARY_PATTERN = re.compile(r"^[01]+$")


def _parse_operand(
    token, input_count, defined_wires, source, line_number
):
    match = OPERAND_PATTERN.match(token)
    if match is None:
        _contract_error(
            source, line_number, "bad operand {!r}".format(token)
        )
    inverted = match.group(1) is not None
    kind = match.group(2)
    index = int(match.group(3))
    if kind == "x" and index > input_count:
        _contract_error(
            source,
            line_number,
            "input x{} out of range 1..{}".format(index, input_count),
        )
    if kind == "w" and index not in defined_wires:
        _contract_error(
            source,
            line_number,
            "wire w{} used before definition".format(index),
        )
    return Operand(kind, index, inverted)


def parse_netlist(text, source="<netlist>"):
    input_count = None
    gates = []
    outputs = None
    defined_wires = set()
    for line_number, original_line in enumerate(text.splitlines(), 1):
        line = original_line.split("#", 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        keyword = tokens[0]

        if outputs is not None:
            if keyword == "OUTPUTS":
                _contract_error(
                    source, line_number, "duplicate OUTPUTS declaration"
                )
            _contract_error(
                source,
                line_number,
                "statements are not allowed after OUTPUTS",
            )

        if input_count is None and keyword != "INPUTS":
            _contract_error(
                source, line_number, "INPUTS must be the first statement"
            )

        if keyword == "INPUTS":
            if input_count is not None:
                _contract_error(
                    source, line_number, "duplicate INPUTS declaration"
                )
            if (
                len(tokens) != 2
                or POSITIVE_DECIMAL_PATTERN.match(tokens[1]) is None
            ):
                _contract_error(
                    source,
                    line_number,
                    "INPUTS requires exactly one positive decimal integer",
                )
            input_count = int(tokens[1])
        elif keyword == "OUTPUTS":
            if len(tokens) < 2:
                _contract_error(
                    source,
                    line_number,
                    "OUTPUTS requires at least one operand",
                )
            outputs = [
                _parse_operand(
                    token,
                    input_count,
                    defined_wires,
                    source,
                    line_number,
                )
                for token in tokens[1:]
            ]
        else:
            if len(tokens) != 5 or tokens[1] != "=":
                _contract_error(
                    source,
                    line_number,
                    "gate statement must be 'wN = OP operand operand'",
                )
            target_match = WIRE_TARGET_PATTERN.match(tokens[0])
            if target_match is None:
                _contract_error(
                    source,
                    line_number,
                    "gate target must be w followed by a positive decimal integer",
                )
            wire = int(target_match.group(1))
            if wire in defined_wires:
                _contract_error(
                    source,
                    line_number,
                    "wire w{} defined twice".format(wire),
                )
            operation = tokens[2]
            if operation not in OPERATIONS:
                _contract_error(
                    source,
                    line_number,
                    "unknown operation {!r}; allowed: {}".format(
                        operation, " ".join(sorted(OPERATIONS))
                    ),
                )
            gates.append(
                Gate(
                    wire,
                    operation,
                    _parse_operand(
                        tokens[3],
                        input_count,
                        defined_wires,
                        source,
                        line_number,
                    ),
                    _parse_operand(
                        tokens[4],
                        input_count,
                        defined_wires,
                        source,
                        line_number,
                    ),
                )
            )
            defined_wires.add(wire)
    if input_count is None:
        _contract_error(source, None, "missing INPUTS declaration")
    if outputs is None:
        _contract_error(source, None, "missing OUTPUTS declaration")
    return Circuit(input_count, gates, outputs)


def parse_dataset(text, circuit, source="<dataset>"):
    reader = csv.reader(io.StringIO(text), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        _contract_error(
            source, 1, "missing header; expected exactly 'input,output'"
        )
    except csv.Error as error:
        _contract_error(source, 1, "invalid CSV: {}".format(error))
    if header != ["input", "output"]:
        _contract_error(
            source, 1, "header must be exactly 'input,output'"
        )

    rows = []
    while True:
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as error:
            _contract_error(
                source,
                reader.line_num,
                "invalid CSV: {}".format(error),
            )
        line_number = reader.line_num
        if not row:
            _contract_error(
                source, line_number, "blank rows are not allowed"
            )
        if len(row) != 2:
            _contract_error(
                source,
                line_number,
                "expected exactly two CSV fields",
            )
        input_bits, output_bits = row
        if BINARY_PATTERN.match(input_bits) is None:
            _contract_error(
                source,
                line_number,
                "input must be a nonempty binary string",
            )
        if BINARY_PATTERN.match(output_bits) is None:
            _contract_error(
                source,
                line_number,
                "output must be a nonempty binary string",
            )
        if len(input_bits) != circuit.input_count:
            _contract_error(
                source,
                line_number,
                "input width {} does not match INPUTS {}".format(
                    len(input_bits), circuit.input_count
                ),
            )
        if len(output_bits) != len(circuit.outputs):
            _contract_error(
                source,
                line_number,
                "output width {} does not match circuit outputs {}".format(
                    len(output_bits), len(circuit.outputs)
                ),
            )
        rows.append((input_bits, output_bits))

    if not rows:
        _contract_error(
            source, None, "dataset must contain at least one sample"
        )
    return rows


def _operand_value(operand, input_bits, wire_values):
    if operand.kind == "x":
        value = input_bits[operand.index - 1] == "1"
    else:
        value = wire_values[operand.index]
    return not value if operand.inverted else value


def evaluate(circuit, rows):
    exact_matches = 0
    correct_bits = 0
    total_bits = 0
    for input_bits, truth in rows:
        wire_values = {}
        for gate in circuit.gates:
            left = _operand_value(gate.left, input_bits, wire_values)
            right = _operand_value(gate.right, input_bits, wire_values)
            wire_values[gate.wire] = OPERATIONS[gate.operation](left, right)
        predicted = "".join(
            "1"
            if _operand_value(output, input_bits, wire_values)
            else "0"
            for output in circuit.outputs
        )
        if predicted == truth:
            exact_matches += 1
        correct_bits += sum(
            predicted_bit == truth_bit
            for predicted_bit, truth_bit in zip(predicted, truth)
        )
        total_bits += len(truth)

    samples = len(rows)
    return {
        "samples": samples,
        "exact_matches": exact_matches,
        "exact_match_accuracy": exact_matches / float(samples),
        "correct_bits": correct_bits,
        "total_bits": total_bits,
        "bit_accuracy": correct_bits / float(total_bits),
        "gate_count": len(circuit.gates),
        "official_free_inversion_gate_count": len(circuit.gates),
    }


def _load_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise EvaluationError("{}: cannot read UTF-8 text: {}".format(path, error))


def _print_text_metrics(metrics):
    print(
        "gates:            {}  (inverters free)".format(
            metrics["official_free_inversion_gate_count"]
        )
    )
    print("samples:          {}".format(metrics["samples"]))
    print(
        "exact-match acc:  {}".format(
            round(metrics["exact_match_accuracy"], 6)
        )
    )
    print("bit accuracy:     {}".format(round(metrics["bit_accuracy"], 6)))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate a documented Occam's Circuit netlist."
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("circuit")
    parser.add_argument("dataset")
    arguments = parser.parse_args(argv)

    try:
        circuit = parse_netlist(
            _load_text(arguments.circuit), source=arguments.circuit
        )
        rows = parse_dataset(
            _load_text(arguments.dataset), circuit, source=arguments.dataset
        )
        metrics = evaluate(circuit, rows)
        metrics["peak_memory_bytes"] = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        )
        metrics["peak_memory_measurement"] = (
            "resource.getrusage(RUSAGE_SELF).ru_maxrss; "
            "Linux KiB converted to bytes"
        )
    except EvaluationError as error:
        print("error: {}".format(error), file=sys.stderr)
        return 2
    if arguments.as_json:
        print(json.dumps(metrics, sort_keys=True))
    else:
        _print_text_metrics(metrics)
    return 0


if __name__ == "__main__":
    sys.exit(main())
