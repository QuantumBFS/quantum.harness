from __future__ import annotations

import numpy as np


SEGMENTS = 12
CONTROLS = 4
RAW_DIM = SEGMENTS * CONTROLS


def target_gate(name: str) -> np.ndarray:
    gate = name.upper()
    if gate == "CZ":
        return np.diag([1, 1, 1, -1]).astype(complex)
    if gate == "I":
        return np.eye(4, dtype=complex)
    raise ValueError(f"unknown two-qubit target gate: {name}")


def gate_infidelity(unitary: np.ndarray, target: np.ndarray) -> float:
    unitary = np.asarray(unitary, dtype=complex)
    target = np.asarray(target, dtype=complex)
    if unitary.shape != target.shape or unitary.ndim != 2 or unitary.shape[0] != unitary.shape[1]:
        raise ValueError("unitary and target must be square matrices with matching shape")
    dim = unitary.shape[0]
    overlap = np.trace(target.conj().T @ unitary)
    fidelity = abs(overlap) ** 2 / (dim * dim)
    return max(0.0, min(1.0, float(1.0 - fidelity.real)))


def su4_basis() -> list[np.ndarray]:
    paulis = [_pauli_i(), _pauli_x(), _pauli_y(), _pauli_z()]
    basis: list[np.ndarray] = []
    for left in paulis:
        for right in paulis:
            item = np.kron(left, right)
            if np.allclose(item, np.eye(4)):
                continue
            basis.append(item / 2.0)
    return basis


def expm_hermitian(generator: np.ndarray, duration: float = 1.0) -> np.ndarray:
    generator = np.asarray(generator, dtype=complex)
    if generator.ndim != 2 or generator.shape[0] != generator.shape[1]:
        raise ValueError("generator must be a square matrix")
    values, vectors = np.linalg.eigh(generator)
    phases = np.exp(-1j * duration * values)
    return (vectors * phases) @ vectors.conj().T


def propagate_error_pulse(
    params: np.ndarray, mixing: np.ndarray, bias: np.ndarray, target: np.ndarray
) -> np.ndarray:
    params = np.asarray(params, dtype=float)
    mixing = np.asarray(mixing, dtype=float)
    bias = np.asarray(bias, dtype=float)
    target = np.asarray(target, dtype=complex)
    if params.shape != (RAW_DIM,):
        raise ValueError(f"params must have shape ({RAW_DIM},)")
    if mixing.shape != (SEGMENTS, CONTROLS, 15):
        raise ValueError(f"mixing must have shape ({SEGMENTS}, {CONTROLS}, 15)")
    if bias.shape != (15,):
        raise ValueError("bias must have shape (15,)")
    basis = su4_basis()
    controls = params.reshape(SEGMENTS, CONTROLS)
    unitary = np.eye(4, dtype=complex)
    for segment in range(SEGMENTS):
        weights = bias / SEGMENTS + controls[segment] @ mixing[segment]
        hamiltonian = sum(weight * basis[index] for index, weight in enumerate(weights))
        unitary = expm_hermitian(hamiltonian) @ unitary
    return target @ unitary


def _pauli_i() -> np.ndarray:
    return np.eye(2, dtype=complex)


def _pauli_x() -> np.ndarray:
    return np.array([[0, 1], [1, 0]], dtype=complex)


def _pauli_y() -> np.ndarray:
    return np.array([[0, -1j], [1j, 0]], dtype=complex)


def _pauli_z() -> np.ndarray:
    return np.array([[1, 0], [0, -1]], dtype=complex)
