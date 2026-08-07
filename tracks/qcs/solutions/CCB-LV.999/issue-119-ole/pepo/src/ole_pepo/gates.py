"""Audited QASM gate matrices and their quimb representations."""

from __future__ import annotations

import numpy as np
import quimb.tensor as qtn

from .qasm import OLEProtocol, QASMGate


_FIXED_MATRICES = {
    "s": np.diag([1.0, 1.0j]).astype(np.complex128),
    "sdg": np.diag([1.0, -1.0j]).astype(np.complex128),
    "sx": 0.5
    * np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]], dtype=np.complex128),
    "sxdg": 0.5
    * np.array([[1 - 1j, 1 + 1j], [1 + 1j, 1 - 1j]], dtype=np.complex128),
    "cz": np.diag([1.0, 1.0, 1.0, -1.0]).astype(np.complex128),
}


def gate_matrix(gate: QASMGate) -> np.ndarray:
    """Return a fresh complex matrix for one supported audited QASM gate."""
    if gate.name in {"rx", "rz"}:
        if gate.angle is None:
            raise ValueError(f"parameterized gate {gate.name!r} requires an angle")
        half_angle = gate.angle / 2
        if gate.name == "rx":
            return np.array(
                [
                    [np.cos(half_angle), -1j * np.sin(half_angle)],
                    [-1j * np.sin(half_angle), np.cos(half_angle)],
                ],
                dtype=np.complex128,
            )
        return np.diag(
            [np.exp(-1j * half_angle), np.exp(1j * half_angle)]
        ).astype(np.complex128)

    if gate.name in _FIXED_MATRICES:
        if gate.angle is not None:
            raise ValueError(f"fixed gate {gate.name!r} does not accept an angle")
        return _FIXED_MATRICES[gate.name].copy()

    raise ValueError(f"unsupported gate matrix: {gate.name!r}")


def to_quimb_gate(gate: QASMGate) -> qtn.Gate:
    """Convert a QASM gate while preserving its physical-label order."""
    return qtn.Gate.from_raw(gate_matrix(gate), qubits=gate.qubits)


def quimb_gates(protocol: OLEProtocol) -> tuple[qtn.Gate, ...]:
    """Convert all protocol gates in their original temporal order."""
    return tuple(to_quimb_gate(gate) for gate in protocol.gates)


def interaction_edges(protocol: OLEProtocol) -> tuple[tuple[int, int], ...]:
    """Return the unique CZ interaction edges in canonical endpoint order."""
    edges = {
        tuple(sorted(gate.qubits))
        for gate in protocol.gates
        if gate.name == "cz"
    }
    return tuple(sorted(edges))
