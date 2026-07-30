"""Independent Boolean-circuit tooling for quantum.harness issue #71.

The parser is intentionally strict.  Third-party netlists are treated as data:
this module never imports or executes code from a submission.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
import re
from typing import Iterable, Sequence


OPS = frozenset({"AND", "OR", "XOR", "NAND", "NOR", "XNOR"})
_TOKEN_RE = re.compile(r"~?(?:x[1-9][0-9]*|w[1-9][0-9]*)\Z")
_WIRE_RE = re.compile(r"w[1-9][0-9]*\Z")


def split_token(token: str) -> tuple[str, bool]:
    """Return (base name, is_negated) after validating a signal token."""
    if not _TOKEN_RE.fullmatch(token):
        raise ValueError(f"invalid signal token: {token!r}")
    return (token[1:], True) if token.startswith("~") else (token, False)


def invert(token: str) -> str:
    """Toggle a free inversion on a signal token."""
    base, negated = split_token(token)
    return base if negated else f"~{base}"


def remap_token(token: str, mapping: dict[str, str]) -> str:
    base, negated = split_token(token)
    mapped = mapping.get(base, base)
    return f"~{mapped}" if negated else mapped


@dataclass(frozen=True)
class Gate:
    output: str
    op: str
    left: str
    right: str


@dataclass(frozen=True)
class Circuit:
    ninputs: int
    gates: tuple[Gate, ...]
    outputs: tuple[str, ...]

    @classmethod
    def parse(cls, path: str | Path) -> "Circuit":
        return cls.parse_text(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def parse_text(cls, text: str) -> "Circuit":
        ninputs: int | None = None
        gates: list[Gate] = []
        outputs: tuple[str, ...] | None = None
        defined: set[str] = set()

        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            fields = line.split()

            if fields[0] == "INPUTS":
                if ninputs is not None or gates or outputs is not None:
                    raise ValueError(f"line {lineno}: misplaced/duplicate INPUTS")
                if len(fields) != 2 or not fields[1].isdigit():
                    raise ValueError(f"line {lineno}: malformed INPUTS")
                ninputs = int(fields[1])
                if ninputs <= 0:
                    raise ValueError(f"line {lineno}: INPUTS must be positive")
                continue

            if ninputs is None:
                raise ValueError(f"line {lineno}: INPUTS must come first")

            if fields[0] == "OUTPUTS":
                if outputs is not None or len(fields) < 2:
                    raise ValueError(f"line {lineno}: malformed/duplicate OUTPUTS")
                parsed = tuple(fields[1:])
                for token in parsed:
                    base, _ = split_token(token)
                    if base.startswith("x"):
                        idx = int(base[1:])
                        if not 1 <= idx <= ninputs:
                            raise ValueError(f"line {lineno}: input out of range: {base}")
                    elif base not in defined:
                        raise ValueError(f"line {lineno}: undefined output wire: {base}")
                outputs = parsed
                continue

            if outputs is not None:
                raise ValueError(f"line {lineno}: gate appears after OUTPUTS")
            if len(fields) != 5 or fields[1] != "=":
                raise ValueError(f"line {lineno}: malformed gate")
            output, op, left, right = fields[0], fields[2], fields[3], fields[4]
            if not _WIRE_RE.fullmatch(output):
                raise ValueError(f"line {lineno}: invalid output wire: {output}")
            if output in defined:
                raise ValueError(f"line {lineno}: duplicate output wire: {output}")
            if op not in OPS:
                raise ValueError(f"line {lineno}: unsupported gate: {op}")
            for token in (left, right):
                base, _ = split_token(token)
                if base.startswith("x"):
                    idx = int(base[1:])
                    if not 1 <= idx <= ninputs:
                        raise ValueError(f"line {lineno}: input out of range: {base}")
                elif base not in defined:
                    raise ValueError(
                        f"line {lineno}: wire used before definition: {base}"
                    )
            gates.append(Gate(output, op, left, right))
            defined.add(output)

        if ninputs is None:
            raise ValueError("missing INPUTS")
        if outputs is None:
            raise ValueError("missing OUTPUTS")
        return cls(ninputs, tuple(gates), outputs)

    def to_text(self) -> str:
        lines = [f"INPUTS {self.ninputs}"]
        lines.extend(
            f"{gate.output} = {gate.op} {gate.left} {gate.right}"
            for gate in self.gates
        )
        lines.append(f"OUTPUTS {' '.join(self.outputs)}")
        return "\n".join(lines) + "\n"

    def write(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_text(), encoding="utf-8", newline="\n")

    def evaluate(self, input_bits: str) -> str:
        if len(input_bits) != self.ninputs or set(input_bits) - {"0", "1"}:
            raise ValueError(
                f"expected {self.ninputs} binary input characters, got {input_bits!r}"
            )
        values: dict[str, bool] = {
            f"x{i + 1}": bit == "1" for i, bit in enumerate(input_bits)
        }

        def value(token: str) -> bool:
            base, negated = split_token(token)
            result = values[base]
            return not result if negated else result

        for gate in self.gates:
            left, right = value(gate.left), value(gate.right)
            values[gate.output] = _apply_bool(gate.op, left, right)
        return "".join("1" if value(token) else "0" for token in self.outputs)

    def truth_tables(self) -> tuple[dict[str, int], tuple[int, ...], int]:
        """Evaluate all wires bit-parallel over the complete primary-input domain.

        Bit k of each returned integer is the value on assignment k.  Assignment
        bits follow x1, x2, ... order, matching the challenge's LSB-first layout.
        """
        assignment_count = 1 << self.ninputs
        mask = (1 << assignment_count) - 1
        values: dict[str, int] = {}
        for input_idx in range(self.ninputs):
            table = 0
            for assignment in range(assignment_count):
                if (assignment >> input_idx) & 1:
                    table |= 1 << assignment
            values[f"x{input_idx + 1}"] = table

        def value(token: str) -> int:
            base, negated = split_token(token)
            table = values[base]
            return table ^ mask if negated else table

        for gate in self.gates:
            values[gate.output] = _apply_table(
                gate.op, value(gate.left), value(gate.right), mask
            )
        return values, tuple(value(token) for token in self.outputs), mask

    def prune_and_renumber(self) -> "Circuit":
        """Remove gates outside every output cone and densely renumber wires."""
        live: set[str] = {
            base for token in self.outputs for base, _ in (split_token(token),)
            if base.startswith("w")
        }
        kept_reversed: list[Gate] = []
        for gate in reversed(self.gates):
            if gate.output not in live:
                continue
            kept_reversed.append(gate)
            for token in (gate.left, gate.right):
                base, _ = split_token(token)
                if base.startswith("w"):
                    live.add(base)
        kept = list(reversed(kept_reversed))
        mapping = {gate.output: f"w{idx}" for idx, gate in enumerate(kept, start=1)}
        rewritten = tuple(
            Gate(
                mapping[gate.output],
                gate.op,
                remap_token(gate.left, mapping),
                remap_token(gate.right, mapping),
            )
            for gate in kept
        )
        outputs = tuple(remap_token(token, mapping) for token in self.outputs)
        return Circuit(self.ninputs, rewritten, outputs)

    def structural_audit(self) -> dict[str, int]:
        values, _, mask = self.truth_tables()
        seen: dict[int, str] = {}
        constants = duplicates = complement_duplicates = 0
        for gate in self.gates:
            table = values[gate.output]
            if table in (0, mask):
                constants += 1
            if table in seen:
                duplicates += 1
            elif (table ^ mask) in seen:
                complement_duplicates += 1
            seen.setdefault(table, gate.output)
        pruned = self.prune_and_renumber()
        return {
            "gates": len(self.gates),
            "dead_gates": len(self.gates) - len(pruned.gates),
            "constant_wires": constants,
            "duplicate_wires": duplicates,
            "complement_duplicate_wires": complement_duplicates,
        }


def _apply_bool(op: str, left: bool, right: bool) -> bool:
    if op == "AND":
        return left and right
    if op == "OR":
        return left or right
    if op == "XOR":
        return left != right
    if op == "NAND":
        return not (left and right)
    if op == "NOR":
        return not (left or right)
    if op == "XNOR":
        return left == right
    raise AssertionError(op)


def _apply_table(op: str, left: int, right: int, mask: int) -> int:
    if op == "AND":
        return left & right
    if op == "OR":
        return left | right
    if op == "XOR":
        return left ^ right
    if op == "NAND":
        return (left & right) ^ mask
    if op == "NOR":
        return (left | right) ^ mask
    if op == "XNOR":
        return (left ^ right) ^ mask
    raise AssertionError(op)


class CircuitBuilder:
    def __init__(self, ninputs: int):
        self.ninputs = ninputs
        self._gates: list[Gate] = []

    def gate(self, op: str, left: str, right: str) -> str:
        if op not in OPS:
            raise ValueError(op)
        split_token(left)
        split_token(right)
        output = f"w{len(self._gates) + 1}"
        self._gates.append(Gate(output, op, left, right))
        return output

    def half_adder(self, left: str, right: str) -> tuple[str, str]:
        total = self.gate("XOR", left, right)
        carry = self.gate("AND", left, right)
        return total, carry

    def full_adder(self, a: str, b: str, carry_in: str) -> tuple[str, str]:
        parity = self.gate("XOR", a, b)
        total = self.gate("XOR", parity, carry_in)
        generate = self.gate("AND", a, b)
        propagate = self.gate("AND", parity, carry_in)
        # The generate and propagate terms are disjoint, so XOR equals OR.
        carry_out = self.gate("XOR", generate, propagate)
        return total, carry_out

    def finish(self, outputs: Iterable[str], prune: bool = True) -> Circuit:
        circuit = Circuit(self.ninputs, tuple(self._gates), tuple(outputs))
        # Round-trip through the strict parser before returning generated text.
        circuit = Circuit.parse_text(circuit.to_text())
        return circuit.prune_and_renumber() if prune else circuit


def build_adder(nbits: int) -> Circuit:
    if nbits < 1:
        raise ValueError("nbits must be positive")
    builder = CircuitBuilder(2 * nbits)
    x = [f"x{i + 1}" for i in range(nbits)]
    y = [f"x{nbits + i + 1}" for i in range(nbits)]
    low_sum, carry = builder.half_adder(x[0], y[0])
    outputs = [low_sum]
    for idx in range(1, nbits):
        total, carry = builder.full_adder(x[idx], y[idx], carry)
        outputs.append(total)
    outputs.append(carry)
    return builder.finish(outputs)


def build_multiplier(nbits: int) -> Circuit:
    """Build a complete unsigned multiplier via column compression."""
    if nbits < 1:
        raise ValueError("nbits must be positive")
    builder = CircuitBuilder(2 * nbits)
    columns: list[list[str]] = [[] for _ in range(2 * nbits + 1)]
    for left_idx in range(nbits):
        for right_idx in range(nbits):
            partial = builder.gate(
                "AND",
                f"x{left_idx + 1}",
                f"x{nbits + right_idx + 1}",
            )
            columns[left_idx + right_idx].append(partial)

    outputs: list[str] = []
    for weight in range(2 * nbits):
        column = columns[weight]
        while len(column) >= 3:
            a, b, c = column.pop(), column.pop(), column.pop()
            total, carry = builder.full_adder(a, b, c)
            column.append(total)
            columns[weight + 1].append(carry)
        if len(column) == 2:
            total, carry = builder.half_adder(column[0], column[1])
            outputs.append(total)
            columns[weight + 1].append(carry)
        elif len(column) == 1:
            outputs.append(column[0])
        else:
            raise AssertionError(f"empty product column {weight}")
    return builder.finish(outputs)


def decode_operands(input_bits: str) -> tuple[int, int]:
    if len(input_bits) % 2:
        raise ValueError("input width must be even")
    nbits = len(input_bits) // 2
    left = sum((bit == "1") << idx for idx, bit in enumerate(input_bits[:nbits]))
    right = sum((bit == "1") << idx for idx, bit in enumerate(input_bits[nbits:]))
    return left, right


def encode_lsb(value: int, width: int) -> str:
    if value < 0 or value >= 1 << width:
        raise ValueError(f"value {value} does not fit in {width} bits")
    return "".join("1" if (value >> idx) & 1 else "0" for idx in range(width))


def arithmetic_output(kind: str, input_bits: str, width: int) -> str:
    left, right = decode_operands(input_bits)
    if kind == "add":
        value = left + right
    elif kind == "mul":
        value = left * right
    elif kind == "absdiff":
        value = abs(left - right)
    elif kind == "sos":
        value = left * left + right * right
    else:
        raise ValueError(f"unknown arithmetic family: {kind}")
    return encode_lsb(value, width)


def verify_formula(circuit: Circuit, kind: str) -> dict[str, int]:
    checked = 1 << circuit.ninputs
    width = len(circuit.outputs)
    failures = 0
    for assignment in range(checked):
        input_bits = encode_lsb(assignment, circuit.ninputs)
        if circuit.evaluate(input_bits) != arithmetic_output(kind, input_bits, width):
            failures += 1
    return {"checked": checked, "failures": failures}


def verify_dataset(circuit: Circuit, csv_path: str | Path) -> dict[str, int | float]:
    rows = 0
    exact = 0
    correct_bits = 0
    total_bits = 0
    with Path(csv_path).open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["input", "output"]:
            raise ValueError(f"unexpected CSV header in {csv_path}: {reader.fieldnames}")
        for row in reader:
            prediction = circuit.evaluate(row["input"])
            expected = row["output"]
            if len(prediction) != len(expected):
                raise ValueError("circuit/dataset output-width mismatch")
            rows += 1
            exact += prediction == expected
            correct_bits += sum(a == b for a, b in zip(prediction, expected))
            total_bits += len(expected)
    return {
        "rows": rows,
        "exact": exact,
        "exact_accuracy": exact / rows,
        "correct_bits": correct_bits,
        "total_bits": total_bits,
        "bit_accuracy": correct_bits / total_bits,
    }


def prediction_bytes(circuit: Circuit, test_inputs_path: str | Path) -> bytes:
    with Path(test_inputs_path).open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        if header != ["input"]:
            raise ValueError(
                f"unexpected test-input header in {test_inputs_path}: {header}"
            )
        lines = ["input,output"]
        for fields in reader:
            if len(fields) != 1:
                raise ValueError(f"malformed test-input row: {fields}")
            input_bits = fields[0]
            lines.append(f"{input_bits},{circuit.evaluate(input_bits)}")
    return ("\n".join(lines) + "\n").encode("ascii")


def write_predictions(
    circuit: Circuit, test_inputs_path: str | Path, output_path: str | Path
) -> str:
    payload = prediction_bytes(circuit, test_inputs_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def read_commitment(path: str | Path) -> str:
    fields = Path(path).read_text(encoding="ascii").split()
    if not fields or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
        raise ValueError(f"malformed SHA-256 commitment: {path}")
    return fields[0].lower()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_truth_tables(left: Circuit, right: Circuit) -> dict[str, int | bool]:
    if left.ninputs != right.ninputs:
        raise ValueError("input-width mismatch")
    if len(left.outputs) != len(right.outputs):
        raise ValueError("output-width mismatch")
    _, left_outputs, _ = left.truth_tables()
    _, right_outputs, _ = right.truth_tables()
    mismatching_outputs = sum(a != b for a, b in zip(left_outputs, right_outputs))
    return {
        "assignments": 1 << left.ninputs,
        "outputs": len(left.outputs),
        "mismatching_outputs": mismatching_outputs,
        "equivalent": mismatching_outputs == 0,
    }
