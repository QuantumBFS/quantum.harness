"""Exact-state primitives for Haar-random brickwork circuit layers."""

import numpy as np


def haar_unitary_4(rng):
    """Sample a 4-by-4 unitary from the Haar measure."""
    z = (rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4))) / np.sqrt(2.0)
    q, r = np.linalg.qr(z)
    diagonal = np.diag(r)
    phases = np.where(np.abs(diagonal) > 0.0, diagonal / np.abs(diagonal), 1.0)
    return np.asarray(q * phases[np.newaxis, :], dtype=np.complex128)


def _haar_vector(dimension, rng):
    state = rng.normal(size=dimension) + 1j * rng.normal(size=dimension)
    state = np.asarray(state, dtype=np.complex128)
    state /= np.linalg.norm(state)
    return state


def global_haar_state(L, rng):
    """Return a normalized Haar-random state over all L qubits."""
    if int(L) < 2:
        raise ValueError("L must be at least two")
    return _haar_vector(1 << int(L), rng)


def product_haar_state(L, rng):
    """Return a tensor product of independent single-qubit Haar states."""
    if int(L) < 2:
        raise ValueError("L must be at least two")
    state = np.array([1.0 + 0.0j], dtype=np.complex128)
    for _ in range(int(L)):
        state = np.kron(state, _haar_vector(2, rng))
    return np.asarray(state, dtype=np.complex128)


def layer_pairs(L, parity):
    """Return the periodic nearest-neighbor pairs for one brickwork layer."""
    L, parity = int(L), int(parity)
    if L < 2 or L % 2 or parity not in (0, 1):
        raise ValueError("L must be even and parity must be zero or one")
    return tuple(
        ((parity + 2 * j) % L, (parity + 2 * j + 1) % L)
        for j in range(L // 2)
    )


def apply_two_qubit_gate_inplace(state, gate, sites, L):
    """Apply a gate in |00>, |01>, |10>, |11> order to the specified sites."""
    q0, q1 = map(int, sites)
    if state.dtype != np.complex128 or state.shape != (1 << int(L),):
        raise ValueError("state must be flat complex128 with length 2**L")
    if np.shape(gate) != (4, 4) or q0 == q1:
        raise ValueError("invalid gate or sites")
    tensor = state.reshape((2,) * int(L))
    moved = np.moveaxis(tensor, (q0, q1), (0, 1))
    acted = np.tensordot(
        np.asarray(gate).reshape(2, 2, 2, 2), moved, axes=((2, 3), (0, 1))
    )
    state[:] = np.moveaxis(acted, (0, 1), (q0, q1)).reshape(-1)


def apply_gate_layer(state, L, parity, rng):
    """Apply independent Haar gates over one periodic brickwork layer."""
    pairs = layer_pairs(L, parity)
    for pair in pairs:
        apply_two_qubit_gate_inplace(state, haar_unitary_4(rng), pair, L)
    return len(pairs)
