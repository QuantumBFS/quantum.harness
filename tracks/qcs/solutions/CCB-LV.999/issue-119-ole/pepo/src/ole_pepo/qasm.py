"""Strict OpenQASM 2 parser for the audited OLE circuit input."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from hashlib import sha256
from pathlib import Path
import math
import re
import struct

import numpy as np


_DECIMAL = r"(?:\d+(?:\.\d*)?|\.\d+)"
_QUBIT = r"q\[(\d+)\]"
_QREG = re.compile(r"^qreg\s+q\[(\d+)\]\s*;$")
_BARRIER = re.compile(rf"^barrier\s+{_QUBIT}(?:,{_QUBIT})*\s*;$")
_PARAMETERIZED_GATE = re.compile(r"^(rx|rz)\(([^()]*)\)\s+q\[(\d+)\]\s*;$")
_FIXED_GATE = re.compile(r"^(s|sdg|sx|sxdg)\s+q\[(\d+)\]\s*;$")
_CZ = re.compile(rf"^cz\s+{_QUBIT},{_QUBIT}\s*;$")
_SIGNED_DECIMAL = re.compile(rf"^[+-]?{_DECIMAL}$")
_PI_ANGLE = re.compile(
    rf"^(?P<sign>[+-]?)(?:(?P<coefficient>{_DECIMAL})\*)?pi"
    rf"(?:/(?P<denominator>{_DECIMAL}))?$"
)


@dataclass(frozen=True, slots=True)
class QASMGate:
    name: str
    qubits: tuple[int, ...]
    angle: float | None
    layer_index: int
    gate_index: int


@dataclass(frozen=True, slots=True)
class OLEProtocol:
    register_size: int
    layers: tuple[tuple[QASMGate, ...], ...]
    active_sites: tuple[int, ...]
    barrier_count: int

    @property
    def gates(self) -> tuple[QASMGate, ...]:
        return tuple(gate for layer in self.layers for gate in layer)


def _angle_bits(angle: float | None) -> str:
    if angle is None:
        return "-"
    return struct.pack(">d", float(angle)).hex()


def canonical_gate_records(protocol: OLEProtocol) -> tuple[str, ...]:
    return tuple(
        (
            f"{gate.layer_index}|{gate.gate_index}|{gate.name}|"
            f"{','.join(map(str, gate.qubits))}|{_angle_bits(gate.angle)}"
        )
        for gate in protocol.gates
    )


def canonical_gate_digest(protocol: OLEProtocol) -> str:
    payload = "\n".join(canonical_gate_records(protocol)) + "\n"
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _unsupported(line_number: int, statement: str) -> ValueError:
    return ValueError(f"unsupported OpenQASM statement at line {line_number}: {statement}")


def _parse_angle(expression: str) -> float:
    compact = expression.strip()
    if _SIGNED_DECIMAL.fullmatch(compact):
        value = float(compact)
        if math.isfinite(value):
            return value
        raise ValueError(f"invalid angle expression: {expression}")

    matched = _PI_ANGLE.fullmatch(compact)
    if matched is None:
        raise ValueError(f"invalid angle expression: {expression}")

    sign = -1.0 if matched.group("sign") == "-" else 1.0
    coefficient = float(matched.group("coefficient") or 1.0)
    denominator = float(matched.group("denominator") or 1.0)
    if denominator == 0.0:
        raise ValueError(f"invalid angle expression: {expression}")
    return sign * coefficient * math.pi / denominator


def _checked_qubits(qubits: tuple[int, ...], register_size: int, line_number: int, statement: str) -> None:
    if any(qubit < 0 or qubit >= register_size for qubit in qubits):
        raise _unsupported(line_number, statement)


def parse_qasm(text: str) -> OLEProtocol:
    """Parse precisely the OpenQASM subset used by the OLE circuit."""
    statements = [
        (line_number, line.split("//", 1)[0].strip())
        for line_number, line in enumerate(text.splitlines(), start=1)
    ]
    statements = [(line_number, line) for line_number, line in statements if line]

    if len(statements) < 3:
        raise ValueError("unsupported OpenQASM: missing required declarations")
    if statements[0][1] != "OPENQASM 2.0;":
        raise _unsupported(*statements[0])
    if statements[1][1] != 'include "qelib1.inc";':
        raise _unsupported(*statements[1])

    qreg_line_number, qreg_statement = statements[2]
    qreg_match = _QREG.fullmatch(qreg_statement)
    if qreg_match is None:
        raise _unsupported(qreg_line_number, qreg_statement)
    register_size = int(qreg_match.group(1))
    if register_size <= 0:
        raise _unsupported(qreg_line_number, qreg_statement)

    layers: list[tuple[QASMGate, ...]] = []
    current_layer: list[QASMGate] = []
    layer_index = 0
    gate_index = 0
    barrier_count = 0

    for line_number, statement in statements[3:]:
        barrier_match = _BARRIER.fullmatch(statement)
        if barrier_match is not None:
            qubits = tuple(int(qubit) for qubit in re.findall(r"q\[(\d+)\]", statement))
            _checked_qubits(qubits, register_size, line_number, statement)
            if current_layer:
                layers.append(tuple(current_layer))
                current_layer = []
            layer_index += 1
            barrier_count += 1
            continue

        parameterized_match = _PARAMETERIZED_GATE.fullmatch(statement)
        if parameterized_match is not None:
            name, expression, qubit_text = parameterized_match.groups()
            qubits = (int(qubit_text),)
            _checked_qubits(qubits, register_size, line_number, statement)
            try:
                angle = _parse_angle(expression)
            except ValueError as error:
                raise _unsupported(line_number, statement) from error
            current_layer.append(QASMGate(name, qubits, angle, layer_index, gate_index))
            gate_index += 1
            continue

        fixed_match = _FIXED_GATE.fullmatch(statement)
        if fixed_match is not None:
            name, qubit_text = fixed_match.groups()
            qubits = (int(qubit_text),)
            _checked_qubits(qubits, register_size, line_number, statement)
            current_layer.append(QASMGate(name, qubits, None, layer_index, gate_index))
            gate_index += 1
            continue

        cz_match = _CZ.fullmatch(statement)
        if cz_match is not None:
            qubits = tuple(int(qubit) for qubit in cz_match.groups())
            if qubits[0] == qubits[1]:
                raise _unsupported(line_number, statement)
            _checked_qubits(qubits, register_size, line_number, statement)
            current_layer.append(QASMGate("cz", qubits, None, layer_index, gate_index))
            gate_index += 1
            continue

        raise _unsupported(line_number, statement)

    if current_layer:
        layers.append(tuple(current_layer))
    if not layers:
        raise ValueError("unsupported OpenQASM: circuit contains no gates")

    active_sites = tuple(sorted({qubit for layer in layers for gate in layer for qubit in gate.qubits}))
    return OLEProtocol(register_size, tuple(layers), active_sites, barrier_count)


def read_validated_qasm(
    path: str | Path, expected_sha256: str, expected_bytes: int
) -> OLEProtocol:
    """Verify immutable input identity before parsing it."""
    raw = Path(path).read_bytes()
    if len(raw) != expected_bytes:
        raise ValueError(
            f"QASM byte length changed: expected {expected_bytes}, got {len(raw)}"
        )
    actual_sha256 = sha256(raw).hexdigest()
    if actual_sha256.lower() != expected_sha256.lower():
        raise ValueError(
            f"QASM SHA256 changed: expected {expected_sha256}, got {actual_sha256}"
        )
    return parse_qasm(raw.decode("utf-8"))


def replace_perturbations(
    protocol: OLEProtocol,
    source_angle: float,
    expected_count: int,
    replacement_angle: float = 0.0,
) -> OLEProtocol:
    """Return a protocol with the audited Rz perturbations replaced."""
    tolerance = 8 * np.finfo(float).eps
    matches = tuple(
        gate.name == "rz"
        and gate.angle is not None
        and np.isclose(gate.angle, source_angle, atol=tolerance, rtol=0)
        for gate in protocol.gates
    )
    replacement_count = sum(matches)
    if replacement_count != expected_count:
        raise ValueError(
            f"expected {expected_count} perturbation gates at angle {source_angle}, "
            f"found {replacement_count}"
        )

    new_layers = tuple(
        tuple(
            replace(gate, angle=replacement_angle)
            if gate.name == "rz"
            and gate.angle is not None
            and np.isclose(gate.angle, source_angle, atol=tolerance, rtol=0)
            else gate
            for gate in layer
        )
        for layer in protocol.layers
    )
    return replace(protocol, layers=new_layers)


def crop_protocol(protocol: OLEProtocol, sites: tuple[int, ...] | list[int] | frozenset[int]) -> OLEProtocol:
    """Keep gates whose complete support is contained in ``sites``."""
    site_set = frozenset(sites)
    keep = lambda gate: all(qubit in site_set for qubit in gate.qubits)
    layers = tuple(
        retained
        for layer in protocol.layers
        if (retained := tuple(gate for gate in layer if keep(gate)))
    )
    occurring_sites = {qubit for layer in layers for gate in layer for qubit in gate.qubits}
    active_sites = tuple(sorted(site for site in site_set if site in occurring_sites))
    return OLEProtocol(
        register_size=protocol.register_size,
        layers=layers,
        active_sites=active_sites,
        barrier_count=protocol.barrier_count,
    )
