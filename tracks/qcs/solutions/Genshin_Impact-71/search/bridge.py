"""Strict, data-only bridge between Occam issue-71 netlists and BLIF.

The module is deliberately self-contained.  It never imports or executes a
submitted program: both formats are parsed as bounded, topologically ordered
data.  BLIF is restricted to the combinational subset emitted and consumed by
eSLIM: .model, .inputs, .outputs, zero/one/two-input .names, and .end.

Truth-table entries use BLIF order.  For a two-input node they are
f(0,0), f(0,1), f(1,0), f(1,1), i.e. the first input is the most significant
index bit.  Occam input and output sequences remain positional.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Sequence


OPS = ("AND", "OR", "XOR", "NAND", "NOR", "XNOR")
OPS_SET = frozenset(OPS)
MAX_INPUTS = 20
MAX_GATES = 1_000_000
MAX_LOGICAL_LINE = 1_000_000

_OCCAM_SIGNAL_RE = re.compile(r"~?(?:x[1-9][0-9]*|w[1-9][0-9]*)\Z")
_OCCAM_WIRE_RE = re.compile(r"w[1-9][0-9]*\Z")
_BLIF_NAME_RE = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_.$-]*|[0-9]+)\Z"
)


def _split_occam_signal(token: str) -> tuple[str, bool]:
    if not _OCCAM_SIGNAL_RE.fullmatch(token):
        raise ValueError(f"invalid Occam signal token: {token!r}")
    return (token[1:], True) if token.startswith("~") else (token, False)


def _token(base: str, negated: bool = False) -> str:
    return f"~{base}" if negated else base


def _check_blif_name(name: str, context: str) -> str:
    if not _BLIF_NAME_RE.fullmatch(name):
        raise ValueError(f"invalid BLIF name in {context}: {name!r}")
    return name


def _apply_op(op: str, left: bool, right: bool) -> bool:
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


@dataclass(frozen=True)
class OccamGate:
    output: str
    op: str
    left: str
    right: str


@dataclass(frozen=True)
class OccamCircuit:
    ninputs: int
    gates: tuple[OccamGate, ...]
    outputs: tuple[str, ...]

    @classmethod
    def parse(cls, path: str | Path) -> "OccamCircuit":
        return cls.parse_text(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def parse_text(cls, text: str) -> "OccamCircuit":
        if "\x00" in text:
            raise ValueError("NUL byte in Occam netlist")
        ninputs: int | None = None
        gates: list[OccamGate] = []
        outputs: tuple[str, ...] | None = None
        defined: set[str] = set()

        for lineno, raw in enumerate(text.splitlines(), start=1):
            if len(raw) > MAX_LOGICAL_LINE:
                raise ValueError(f"line {lineno}: line too long")
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            fields = line.split()
            if fields[0] == "INPUTS":
                if ninputs is not None or gates or outputs is not None:
                    raise ValueError(f"line {lineno}: misplaced/duplicate INPUTS")
                if len(fields) != 2 or not fields[1].isdigit():
                    raise ValueError(f"line {lineno}: malformed INPUTS")
                ninputs = int(fields[1])
                if not 1 <= ninputs <= MAX_INPUTS:
                    raise ValueError(
                        f"line {lineno}: INPUTS must be in 1..{MAX_INPUTS}"
                    )
                continue

            if ninputs is None:
                raise ValueError(f"line {lineno}: INPUTS must come first")
            if fields[0] == "OUTPUTS":
                if outputs is not None or len(fields) < 2:
                    raise ValueError(f"line {lineno}: malformed/duplicate OUTPUTS")
                parsed = tuple(fields[1:])
                for signal in parsed:
                    base, _ = _split_occam_signal(signal)
                    if base.startswith("x"):
                        if not 1 <= int(base[1:]) <= ninputs:
                            raise ValueError(
                                f"line {lineno}: input out of range: {base}"
                            )
                    elif base not in defined:
                        raise ValueError(
                            f"line {lineno}: undefined output wire: {base}"
                        )
                outputs = parsed
                continue

            if outputs is not None:
                raise ValueError(f"line {lineno}: gate after OUTPUTS")
            if len(gates) >= MAX_GATES:
                raise ValueError(f"more than {MAX_GATES} gates")
            if len(fields) != 5 or fields[1] != "=":
                raise ValueError(f"line {lineno}: malformed gate")
            output, op, left, right = fields[0], fields[2], fields[3], fields[4]
            if not _OCCAM_WIRE_RE.fullmatch(output):
                raise ValueError(f"line {lineno}: invalid output wire: {output}")
            if output in defined:
                raise ValueError(f"line {lineno}: duplicate output wire: {output}")
            if op not in OPS_SET:
                raise ValueError(f"line {lineno}: unsupported gate: {op}")
            for signal in (left, right):
                base, _ = _split_occam_signal(signal)
                if base.startswith("x"):
                    if not 1 <= int(base[1:]) <= ninputs:
                        raise ValueError(
                            f"line {lineno}: input out of range: {base}"
                        )
                elif base not in defined:
                    raise ValueError(
                        f"line {lineno}: wire used before definition: {base}"
                    )
            gates.append(OccamGate(output, op, left, right))
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
        lines.append("OUTPUTS " + " ".join(self.outputs))
        return "\n".join(lines) + "\n"

    def write(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_text(), encoding="utf-8", newline="\n")

    def evaluate(self, input_bits: str) -> str:
        if len(input_bits) != self.ninputs or set(input_bits) - {"0", "1"}:
            raise ValueError(
                f"expected {self.ninputs} input bits, got {input_bits!r}"
            )
        values: dict[str, bool] = {
            f"x{idx + 1}": bit == "1"
            for idx, bit in enumerate(input_bits)
        }

        def value(signal: str) -> bool:
            base, negated = _split_occam_signal(signal)
            answer = values[base]
            return not answer if negated else answer

        for gate in self.gates:
            values[gate.output] = _apply_op(
                gate.op, value(gate.left), value(gate.right)
            )
        return "".join("1" if value(out) else "0" for out in self.outputs)

    def prune_and_renumber(self) -> "OccamCircuit":
        live = {
            base
            for output in self.outputs
            for base, _ in (_split_occam_signal(output),)
            if base.startswith("w")
        }
        kept_rev: list[OccamGate] = []
        for gate in reversed(self.gates):
            if gate.output not in live:
                continue
            kept_rev.append(gate)
            for signal in (gate.left, gate.right):
                base, _ = _split_occam_signal(signal)
                if base.startswith("w"):
                    live.add(base)
        kept = list(reversed(kept_rev))
        renaming = {
            gate.output: f"w{idx}" for idx, gate in enumerate(kept, start=1)
        }

        def remap(signal: str) -> str:
            base, negated = _split_occam_signal(signal)
            return _token(renaming.get(base, base), negated)

        result = OccamCircuit(
            self.ninputs,
            tuple(
                OccamGate(
                    renaming[gate.output],
                    gate.op,
                    remap(gate.left),
                    remap(gate.right),
                )
                for gate in kept
            ),
            tuple(remap(output) for output in self.outputs),
        )
        return OccamCircuit.parse_text(result.to_text())


@dataclass(frozen=True)
class BlifGate:
    output: str
    inputs: tuple[str, ...]
    table: tuple[int, ...]

    def __post_init__(self) -> None:
        if not 0 <= len(self.inputs) <= 2:
            raise ValueError("BLIF gate fanin must be zero, one, or two")
        if len(self.table) != 1 << len(self.inputs):
            raise ValueError("BLIF truth-table size does not match fanin")
        if any(bit not in (0, 1) for bit in self.table):
            raise ValueError("BLIF truth table must contain only 0/1")


@dataclass(frozen=True)
class BlifNetwork:
    model: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    gates: tuple[BlifGate, ...]

    @classmethod
    def parse(cls, path: str | Path) -> "BlifNetwork":
        return cls.parse_text(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def parse_text(cls, text: str) -> "BlifNetwork":
        logical_lines = _logical_blif_lines(text)
        model: str | None = None
        inputs: tuple[str, ...] | None = None
        outputs: tuple[str, ...] | None = None
        gates: list[BlifGate] = []
        known: set[str] = set()
        current_header: tuple[int, tuple[str, ...], str] | None = None
        current_cubes: list[tuple[str, int, int]] = []
        ended = False

        def finish_gate() -> None:
            nonlocal current_header, current_cubes
            if current_header is None:
                return
            header_line, gate_inputs, gate_output = current_header
            gate = _build_blif_gate(
                header_line, gate_inputs, gate_output, current_cubes
            )
            gates.append(gate)
            known.add(gate_output)
            current_header = None
            current_cubes = []

        for lineno, line in logical_lines:
            if ended:
                raise ValueError(f"line {lineno}: content after .end")
            if line.startswith("."):
                finish_gate()
                fields = line.split()
                directive = fields[0]
                if directive == ".model":
                    if model is not None or len(fields) != 2 or inputs is not None:
                        raise ValueError(f"line {lineno}: malformed/misplaced .model")
                    model = _check_blif_name(fields[1], f"line {lineno}")
                elif directive == ".inputs":
                    if inputs is not None or gates or current_header is not None:
                        raise ValueError(
                            f"line {lineno}: duplicate/misplaced .inputs"
                        )
                    if len(fields) < 2:
                        raise ValueError(f"line {lineno}: empty .inputs")
                    parsed = tuple(
                        _check_blif_name(name, f"line {lineno}")
                        for name in fields[1:]
                    )
                    if len(parsed) > MAX_INPUTS:
                        raise ValueError(
                            f"line {lineno}: more than {MAX_INPUTS} inputs"
                        )
                    if len(set(parsed)) != len(parsed):
                        raise ValueError(f"line {lineno}: duplicate primary input")
                    inputs = parsed
                    known = set(parsed)
                elif directive == ".outputs":
                    if (
                        inputs is None
                        or outputs is not None
                        or gates
                        or current_header is not None
                    ):
                        raise ValueError(
                            f"line {lineno}: duplicate/misplaced .outputs"
                        )
                    if len(fields) < 2:
                        raise ValueError(f"line {lineno}: empty .outputs")
                    outputs = tuple(
                        _check_blif_name(name, f"line {lineno}")
                        for name in fields[1:]
                    )
                elif directive == ".names":
                    if inputs is None or outputs is None:
                        raise ValueError(
                            f"line {lineno}: .inputs/.outputs must precede .names"
                        )
                    if not 2 <= len(fields) <= 4:
                        raise ValueError(
                            f"line {lineno}: .names must have fanin 0..2"
                        )
                    if len(gates) >= MAX_GATES:
                        raise ValueError(f"more than {MAX_GATES} BLIF gates")
                    names = tuple(
                        _check_blif_name(name, f"line {lineno}")
                        for name in fields[1:]
                    )
                    gate_inputs, gate_output = names[:-1], names[-1]
                    if len(set(gate_inputs)) != len(gate_inputs):
                        # Repeated physical inputs are meaningful, but eSLIM's
                        # relation representation expects distinct formal inputs.
                        # Occam-to-BLIF collapses such nodes before writing.
                        raise ValueError(
                            f"line {lineno}: repeated .names formal input"
                        )
                    missing = [name for name in gate_inputs if name not in known]
                    if missing:
                        raise ValueError(
                            f"line {lineno}: non-topological inputs: {missing}"
                        )
                    if gate_output in known:
                        raise ValueError(
                            f"line {lineno}: redefined BLIF signal: {gate_output}"
                        )
                    current_header = (lineno, gate_inputs, gate_output)
                elif directive == ".end":
                    if len(fields) != 1:
                        raise ValueError(f"line {lineno}: malformed .end")
                    if inputs is None or outputs is None:
                        raise ValueError(
                            f"line {lineno}: missing .inputs or .outputs"
                        )
                    ended = True
                else:
                    raise ValueError(
                        f"line {lineno}: unsupported BLIF directive {directive!r}"
                    )
            else:
                if current_header is None:
                    raise ValueError(f"line {lineno}: cube outside .names")
                current_cubes.append((line, lineno, len(current_header[1])))

        finish_gate()
        if not ended:
            raise ValueError("missing .end")
        if model is None:
            raise ValueError("missing .model")
        assert inputs is not None and outputs is not None
        missing_outputs = [name for name in outputs if name not in known]
        if missing_outputs:
            raise ValueError(f"undefined BLIF outputs: {missing_outputs}")
        result = cls(model, inputs, outputs, tuple(gates))
        # Reparse the serializer in tests/clients when an additional audit is
        # desired; construction itself has already checked all invariants.
        return result

    def to_text(self) -> str:
        _check_blif_name(self.model, "model")
        lines = [
            f".model {self.model}",
            ".inputs " + " ".join(self.inputs),
            ".outputs " + " ".join(self.outputs),
        ]
        for gate in self.gates:
            lines.append(".names " + " ".join((*gate.inputs, gate.output)))
            width = len(gate.inputs)
            for index, value in enumerate(gate.table):
                if not value:
                    continue
                if width:
                    lines.append(f"{index:0{width}b} 1")
                else:
                    lines.append("1")
        lines.append(".end")
        return "\n".join(lines) + "\n"

    def write(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_text(), encoding="utf-8", newline="\n")

    def evaluate(self, input_bits: str) -> str:
        if len(input_bits) != len(self.inputs) or set(input_bits) - {"0", "1"}:
            raise ValueError(
                f"expected {len(self.inputs)} input bits, got {input_bits!r}"
            )
        values = {
            name: bit == "1" for name, bit in zip(self.inputs, input_bits)
        }
        for gate in self.gates:
            index = 0
            for name in gate.inputs:
                index = (index << 1) | int(values[name])
            values[gate.output] = bool(gate.table[index])
        return "".join("1" if values[name] else "0" for name in self.outputs)


def _logical_blif_lines(text: str) -> list[tuple[int, str]]:
    if "\x00" in text:
        raise ValueError("NUL byte in BLIF")
    result: list[tuple[int, str]] = []
    pending = ""
    pending_line = 0
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if len(raw) > MAX_LOGICAL_LINE:
            raise ValueError(f"line {lineno}: physical line too long")
        body = raw.split("#", 1)[0].rstrip()
        continued = body.endswith("\\")
        if continued:
            body = body[:-1].rstrip()
        if pending:
            pending = f"{pending} {body.lstrip()}"
        else:
            pending = body.strip()
            pending_line = lineno
        if len(pending) > MAX_LOGICAL_LINE:
            raise ValueError(f"line {pending_line}: logical line too long")
        if not continued:
            if pending:
                result.append((pending_line, pending))
            pending = ""
            pending_line = 0
    if pending:
        raise ValueError(f"line {pending_line}: dangling BLIF continuation")
    return result


def _build_blif_gate(
    header_line: int,
    inputs: tuple[str, ...],
    output: str,
    cube_lines: Sequence[tuple[str, int, int]],
) -> BlifGate:
    plane: int | None = None
    cubes: list[str] = []
    for raw, lineno, fanin in cube_lines:
        fields = raw.split()
        if fanin == 0:
            if len(fields) != 1 or fields[0] not in {"0", "1"}:
                raise ValueError(f"line {lineno}: malformed constant cube")
            pattern = ""
            value = int(fields[0])
        else:
            if (
                len(fields) != 2
                or len(fields[0]) != fanin
                or set(fields[0]) - {"0", "1", "-"}
                or fields[1] not in {"0", "1"}
            ):
                raise ValueError(f"line {lineno}: malformed cube")
            pattern, value = fields[0], int(fields[1])
        if plane is None:
            plane = value
        elif value != plane:
            raise ValueError(
                f"line {lineno}: mixed output planes in .names from "
                f"line {header_line}"
            )
        cubes.append(pattern)

    if plane is None:
        return BlifGate(output, inputs, (0,) * (1 << len(inputs)))
    table = [1 - plane] * (1 << len(inputs))
    for pattern in cubes:
        for index in range(1 << len(inputs)):
            bits = f"{index:0{len(inputs)}b}" if inputs else ""
            if all(pat == "-" or pat == bit for pat, bit in zip(pattern, bits)):
                table[index] = plane
    return BlifGate(output, inputs, tuple(table))


def _gate_table_over_unique_inputs(
    op: str,
    left_base: str,
    left_negated: bool,
    right_base: str,
    right_negated: bool,
    phases: dict[str, bool],
    output_phase: bool,
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    names = (
        (left_base,)
        if left_base == right_base
        else (left_base, right_base)
    )
    values: list[int] = []
    for index in range(1 << len(names)):
        assignment = {
            name: bool((index >> (len(names) - 1 - position)) & 1)
            for position, name in enumerate(names)
        }
        left = (
            assignment[left_base]
            ^ phases.get(left_base, False)
            ^ left_negated
        )
        right = (
            assignment[right_base]
            ^ phases.get(right_base, False)
            ^ right_negated
        )
        output = _apply_op(op, left, right) ^ output_phase
        values.append(int(output))
    return names, tuple(values)


def occam_to_blif(
    circuit: OccamCircuit, model: str = "occam_issue71"
) -> BlifNetwork:
    """Encode free inversions as BLIF node phases whenever possible.

    A wire used as a complemented primary output is represented in the matching
    phase, so the usual case adds no unary output gate.  Only a complemented
    primary-input output or the same signal requested in both polarities needs
    an explicit unary BLIF alias; the reverse bridge removes that alias for free.
    """
    _check_blif_name(model, "model")
    phases: dict[str, bool] = {
        f"x{idx + 1}": False for idx in range(circuit.ninputs)
    }
    output_constraints: dict[str, bool] = {}
    for output in circuit.outputs:
        base, negated = _split_occam_signal(output)
        if base.startswith("w") and base not in output_constraints:
            output_constraints[base] = negated
    for gate in circuit.gates:
        phases[gate.output] = output_constraints.get(gate.output, False)

    occupied = set(phases)
    output_names: list[str] = []
    aliases: list[tuple[str, str, bool]] = []

    def fresh_output_alias(index: int) -> str:
        serial = index
        while True:
            candidate = f"__occam_output_{serial}"
            if candidate not in occupied:
                occupied.add(candidate)
                return candidate
            serial += len(circuit.outputs) + 1

    for index, output in enumerate(circuit.outputs, start=1):
        base, desired_phase = _split_occam_signal(output)
        actual_phase = phases[base]
        if desired_phase == actual_phase:
            output_names.append(base)
        else:
            alias = fresh_output_alias(index)
            output_names.append(alias)
            aliases.append((base, alias, actual_phase ^ desired_phase))

    gates: list[BlifGate] = []
    for gate in circuit.gates:
        left_base, left_negated = _split_occam_signal(gate.left)
        right_base, right_negated = _split_occam_signal(gate.right)
        names, table = _gate_table_over_unique_inputs(
            gate.op,
            left_base,
            left_negated,
            right_base,
            right_negated,
            phases,
            phases[gate.output],
        )
        gates.append(BlifGate(gate.output, names, table))
    for source, alias, invert in aliases:
        gates.append(
            BlifGate(alias, (source,), (1, 0) if invert else (0, 1))
        )

    network = BlifNetwork(
        model,
        tuple(f"x{idx + 1}" for idx in range(circuit.ninputs)),
        tuple(output_names),
        tuple(gates),
    )
    # The strict parser audits ordering, identifiers, and serialized semantics.
    return BlifNetwork.parse_text(network.to_text())


@dataclass(frozen=True)
class _Literal:
    base: str
    negated: bool = False

    def as_token(self) -> str:
        return _token(self.base, self.negated)


@dataclass(frozen=True)
class _Constant:
    value: bool


_Signal = _Literal | _Constant


def _truth_dependencies(
    variables: Sequence[str], table: Sequence[int]
) -> list[int]:
    dependencies: list[int] = []
    width = len(variables)
    for position in range(width):
        mask = 1 << (width - 1 - position)
        if any(
            table[index] != table[index | mask]
            for index in range(1 << width)
            if not index & mask
        ):
            dependencies.append(position)
    return dependencies


def _binary_implementation(
    table: tuple[int, int, int, int]
) -> tuple[str, bool, bool, bool]:
    candidates: list[tuple[int, int, bool, bool, bool, str]] = []
    for op_index, op in enumerate(OPS):
        for left_negated in (False, True):
            for right_negated in (False, True):
                for output_negated in (False, True):
                    candidate = tuple(
                        int(
                            _apply_op(
                                op,
                                bool(left ^ left_negated),
                                bool(right ^ right_negated),
                            )
                            ^ output_negated
                        )
                        for left in (0, 1)
                        for right in (0, 1)
                    )
                    if candidate == table:
                        inversion_count = (
                            int(left_negated)
                            + int(right_negated)
                            + int(output_negated)
                        )
                        candidates.append(
                            (
                                inversion_count,
                                op_index,
                                left_negated,
                                right_negated,
                                output_negated,
                                op,
                            )
                        )
    if not candidates:
        raise AssertionError(f"no one-gate implementation for table {table}")
    _, _, left_negated, right_negated, output_negated, op = min(candidates)
    return op, left_negated, right_negated, output_negated


def _compose_blif_gate(
    gate: BlifGate,
    arguments: Sequence[_Signal],
    occam_gates: list[OccamGate],
) -> _Signal:
    variables: list[str] = []
    for argument in arguments:
        if isinstance(argument, _Literal) and argument.base not in variables:
            variables.append(argument.base)
    if len(variables) > 2:
        raise AssertionError("a two-input BLIF gate cannot depend on >2 signals")

    effective: list[int] = []
    for index in range(1 << len(variables)):
        assignment = {
            name: bool((index >> (len(variables) - 1 - position)) & 1)
            for position, name in enumerate(variables)
        }
        gate_index = 0
        for argument in arguments:
            if isinstance(argument, _Constant):
                value = argument.value
            else:
                value = assignment[argument.base] ^ argument.negated
            gate_index = (gate_index << 1) | int(value)
        effective.append(gate.table[gate_index])

    dependencies = _truth_dependencies(variables, effective)
    if not dependencies:
        return _Constant(bool(effective[0]))
    if len(dependencies) == 1:
        position = dependencies[0]
        mask = 1 << (len(variables) - 1 - position)
        zero_value = bool(effective[0])
        one_value = bool(effective[mask])
        if zero_value == one_value:
            raise AssertionError("dependency analysis inconsistency")
        return _Literal(variables[position], negated=zero_value)
    if len(dependencies) != 2 or len(variables) != 2:
        raise AssertionError("unexpected dependency structure")

    binary_table = tuple(effective)
    if len(binary_table) != 4:
        raise AssertionError("binary table must contain four entries")
    op, left_negated, right_negated, output_negated = (
        _binary_implementation(binary_table)  # type: ignore[arg-type]
    )
    output = f"w{len(occam_gates) + 1}"
    occam_gates.append(
        OccamGate(
            output,
            op,
            _token(variables[0], left_negated),
            _token(variables[1], right_negated),
        )
    )
    return _Literal(output, output_negated)


def blif_to_occam(network: BlifNetwork) -> OccamCircuit:
    """Convert arbitrary fanin-at-most-two .names into the Occam basis.

    Constants are propagated, and projections/inversions are represented as
    aliases/free phases.  Every genuine two-variable Boolean function is
    realized by exactly one allowed gate plus free input/output inversions.
    If a constant survives at a primary output, one shared XOR(x1,x1) gate is
    materialized for all constant-zero/constant-one outputs.
    """
    if not network.inputs:
        raise ValueError("Occam circuits require at least one primary input")
    if len(network.inputs) > MAX_INPUTS:
        raise ValueError(f"more than {MAX_INPUTS} inputs")
    signal_map: dict[str, _Signal] = {
        name: _Literal(f"x{idx + 1}")
        for idx, name in enumerate(network.inputs)
    }
    occam_gates: list[OccamGate] = []
    for gate in network.gates:
        try:
            arguments = [signal_map[name] for name in gate.inputs]
        except KeyError as error:
            raise ValueError(
                f"non-topological BLIF signal: {error.args[0]}"
            ) from None
        if gate.output in signal_map:
            raise ValueError(f"redefined BLIF signal: {gate.output}")
        signal_map[gate.output] = _compose_blif_gate(
            gate, arguments, occam_gates
        )

    output_signals: list[_Signal] = []
    for name in network.outputs:
        if name not in signal_map:
            raise ValueError(f"undefined BLIF output: {name}")
        output_signals.append(signal_map[name])

    constant_zero: _Literal | None = None

    def materialize(signal: _Signal) -> _Literal:
        nonlocal constant_zero
        if isinstance(signal, _Literal):
            return signal
        if constant_zero is None:
            output = f"w{len(occam_gates) + 1}"
            occam_gates.append(OccamGate(output, "XOR", "x1", "x1"))
            constant_zero = _Literal(output)
        return _Literal(constant_zero.base, negated=signal.value)

    outputs = tuple(materialize(signal).as_token() for signal in output_signals)
    circuit = OccamCircuit(
        len(network.inputs), tuple(occam_gates), outputs
    ).prune_and_renumber()
    return OccamCircuit.parse_text(circuit.to_text())


def verify_equivalent(
    occam: OccamCircuit, blif: BlifNetwork
) -> dict[str, int | bool]:
    if occam.ninputs != len(blif.inputs):
        raise ValueError("input-width mismatch")
    if len(occam.outputs) != len(blif.outputs):
        raise ValueError("output-width mismatch")
    if occam.ninputs > MAX_INPUTS:
        raise ValueError(f"refusing exhaustive check above {MAX_INPUTS} inputs")
    mismatches = 0
    for assignment in range(1 << occam.ninputs):
        bits = f"{assignment:0{occam.ninputs}b}"
        if occam.evaluate(bits) != blif.evaluate(bits):
            mismatches += 1
    return {
        "assignments": 1 << occam.ninputs,
        "outputs": len(occam.outputs),
        "mismatching_assignments": mismatches,
        "equivalent": mismatches == 0,
    }


def verify_occam_equivalent(
    left: OccamCircuit, right: OccamCircuit
) -> dict[str, int | bool]:
    if left.ninputs != right.ninputs:
        raise ValueError("input-width mismatch")
    if len(left.outputs) != len(right.outputs):
        raise ValueError("output-width mismatch")
    mismatches = 0
    for assignment in range(1 << left.ninputs):
        bits = f"{assignment:0{left.ninputs}b}"
        if left.evaluate(bits) != right.evaluate(bits):
            mismatches += 1
    return {
        "assignments": 1 << left.ninputs,
        "outputs": len(left.outputs),
        "mismatching_assignments": mismatches,
        "equivalent": mismatches == 0,
    }


def _write_verified_blif(source: Path, destination: Path, model: str) -> None:
    circuit = OccamCircuit.parse(source)
    network = occam_to_blif(circuit, model)
    audit = verify_equivalent(circuit, network)
    if not audit["equivalent"]:
        raise RuntimeError(f"Occam-to-BLIF verification failed: {audit}")
    network.write(destination)


def _write_verified_occam(source: Path, destination: Path) -> None:
    network = BlifNetwork.parse(source)
    circuit = blif_to_occam(network)
    audit = verify_equivalent(circuit, network)
    if not audit["equivalent"]:
        raise RuntimeError(f"BLIF-to-Occam verification failed: {audit}")
    circuit.write(destination)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strict Occam issue-71 netlist / eSLIM BLIF bridge"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    to_blif_parser = subparsers.add_parser("to-blif")
    to_blif_parser.add_argument("source", type=Path)
    to_blif_parser.add_argument("destination", type=Path)
    to_blif_parser.add_argument("--model", default="occam_issue71")
    to_occam_parser = subparsers.add_parser("to-occam")
    to_occam_parser.add_argument("source", type=Path)
    to_occam_parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)

    if args.command == "to-blif":
        _write_verified_blif(args.source, args.destination, args.model)
    elif args.command == "to-occam":
        _write_verified_occam(args.source, args.destination)
    else:
        raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
