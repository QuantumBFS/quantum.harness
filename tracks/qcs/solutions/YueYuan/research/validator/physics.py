from __future__ import annotations

import numpy as np


def target_gate(name: str) -> np.ndarray:
    gate = name.upper()
    if gate == "I":
        return np.eye(2, dtype=complex)
    if gate == "X":
        return np.array([[0, 1], [1, 0]], dtype=complex)
    if gate == "Y":
        return np.array([[0, -1j], [1j, 0]], dtype=complex)
    if gate == "Z":
        return np.array([[1, 0], [0, -1]], dtype=complex)
    if gate == "CZ":
        return np.diag([1, 1, 1, -1]).astype(complex)
    if gate == "ISWAP":
        return np.array(
            [[1, 0, 0, 0], [0, 0, 1j, 0], [0, 1j, 0, 0], [0, 0, 0, 1]],
            dtype=complex,
        )
    raise ValueError(f"unknown target gate: {name}")


def gate_infidelity(unitary: np.ndarray, target: np.ndarray) -> float:
    unitary = np.asarray(unitary, dtype=complex)
    target = np.asarray(target, dtype=complex)
    if unitary.shape != target.shape or unitary.ndim != 2 or unitary.shape[0] != unitary.shape[1]:
        raise ValueError("unitary and target must be square matrices with matching shape")
    dim = unitary.shape[0]
    overlap = np.trace(target.conj().T @ unitary)
    fidelity = abs(overlap) ** 2 / (dim * dim)
    return max(0.0, min(1.0, float(1.0 - fidelity.real)))


def expm_hermitian_generator(generator: np.ndarray, duration: float = 1.0) -> np.ndarray:
    generator = np.asarray(generator, dtype=complex)
    values, vectors = np.linalg.eigh(generator)
    phases = np.exp(-1j * duration * values)
    return (vectors * phases) @ vectors.conj().T
