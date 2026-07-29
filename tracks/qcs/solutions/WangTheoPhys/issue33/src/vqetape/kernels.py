"""Exact state-vector oracle kernels for the first VQETape prototype."""

from __future__ import annotations

import jax.numpy as jnp
from jax import Array

from vqetape.spec import TFIMVQESpec


def _complex_dtype(spec: TFIMVQESpec):
    return jnp.complex64 if spec.dtype == "complex64" else jnp.complex128


def _real_dtype(spec: TFIMVQESpec):
    return jnp.float32 if spec.dtype == "complex64" else jnp.float64


def rx_matrix(angle: Array, dtype) -> Array:
    """Return exp(-i angle X / 2) as a rank-2 tensor."""

    half = angle / 2
    cosine = jnp.cos(half)
    sine = -1j * jnp.sin(half)
    return jnp.asarray(
        [[cosine, sine], [sine, cosine]],
        dtype=dtype,
    )


def rzz_matrix(angle: Array, dtype) -> Array:
    """Return exp(-i angle Z⊗Z / 2) as a 4-by-4 matrix."""

    phase_same = jnp.exp(-0.5j * angle)
    phase_different = jnp.exp(0.5j * angle)
    return jnp.diag(
        jnp.asarray(
            [phase_same, phase_different, phase_different, phase_same],
            dtype=dtype,
        )
    )


def rzz_schmidt_factors(angle: Array, dtype) -> tuple[Array, Array]:
    """Return exact rank-2 operator-Schmidt factors for an RZZ gate."""

    half = angle / 2
    identity = jnp.eye(2, dtype=dtype)
    pauli_z = jnp.asarray([[1, 0], [0, -1]], dtype=dtype)
    left = jnp.stack(
        (
            jnp.cos(half) * identity,
            (-1j * jnp.sin(half)) * pauli_z,
        ),
        axis=-1,
    )
    right = jnp.stack((identity, pauli_z), axis=-1)
    return left, right


def initial_state(spec: TFIMVQESpec) -> Array:
    """Construct a normalized product state in computational-basis ordering."""

    dtype = _complex_dtype(spec)
    dimension = 1 << spec.nqubits
    if spec.initial_state == "zero":
        return jnp.zeros((dimension,), dtype=dtype).at[0].set(1)
    amplitude = jnp.asarray(1.0 / jnp.sqrt(dimension), dtype=dtype)
    return jnp.full((dimension,), amplitude, dtype=dtype)


def _apply_one_qubit_matrix(
    state: Array,
    matrix: Array,
    wire: int,
    nqubits: int,
) -> Array:
    tensor = state.reshape((2,) * nqubits)
    moved = jnp.moveaxis(tensor, wire, 0)
    updated = matrix @ moved.reshape(2, -1)
    restored = jnp.moveaxis(updated.reshape((2,) + moved.shape[1:]), 0, wire)
    return restored.reshape(-1)


def _apply_two_qubit_matrix(
    state: Array,
    matrix: Array,
    wire0: int,
    wire1: int,
    nqubits: int,
) -> Array:
    if wire0 == wire1:
        raise ValueError("two-qubit gate requires distinct wires")
    tensor = state.reshape((2,) * nqubits)
    moved = jnp.moveaxis(tensor, (wire0, wire1), (0, 1))
    updated = matrix @ moved.reshape(4, -1)
    restored = jnp.moveaxis(
        updated.reshape((2, 2) + moved.shape[2:]),
        (0, 1),
        (wire0, wire1),
    )
    return restored.reshape(-1)


def apply_rx(state: Array, angle: Array, wire: int, nqubits: int) -> Array:
    """Apply exp(-i angle X / 2)."""

    return _apply_one_qubit_matrix(
        state,
        rx_matrix(angle, state.dtype),
        wire,
        nqubits,
    )


def apply_rzz(
    state: Array,
    angle: Array,
    wire0: int,
    wire1: int,
    nqubits: int,
) -> Array:
    """Apply exp(-i angle Z⊗Z / 2)."""

    return _apply_two_qubit_matrix(
        state,
        rzz_matrix(angle, state.dtype),
        wire0,
        wire1,
        nqubits,
    )


def apply_layer(state: Array, theta_layer: Array, spec: TFIMVQESpec) -> Array:
    """Apply one RZZ-then-RX layer; the last RZZ parameter is padding."""

    for wire in range(spec.nqubits - 1):
        state = apply_rzz(
            state,
            theta_layer[0, wire],
            wire,
            wire + 1,
            spec.nqubits,
        )
    for wire in range(spec.nqubits):
        state = apply_rx(state, theta_layer[1, wire], wire, spec.nqubits)
    return state


def _apply_pauli_x(state: Array, wire: int, nqubits: int) -> Array:
    matrix = jnp.asarray([[0, 1], [1, 0]], dtype=state.dtype)
    return _apply_one_qubit_matrix(state, matrix, wire, nqubits)


def _apply_pauli_z(state: Array, wire: int, nqubits: int) -> Array:
    matrix = jnp.asarray([[1, 0], [0, -1]], dtype=state.dtype)
    return _apply_one_qubit_matrix(state, matrix, wire, nqubits)


def tfim_hamiltonian_action(
    state: Array,
    spec: TFIMVQESpec,
) -> Array:
    """Apply the open-boundary TFIM Hamiltonian to a state."""

    acted_state = jnp.zeros_like(state)
    for wire in range(spec.nqubits - 1):
        acted = _apply_pauli_z(state, wire, spec.nqubits)
        acted = _apply_pauli_z(acted, wire + 1, spec.nqubits)
        acted_state = acted_state - spec.coupling * acted
    for wire in range(spec.nqubits):
        acted = _apply_pauli_x(state, wire, spec.nqubits)
        acted_state = acted_state - spec.field * acted
    return acted_state


def tfim_energy(state: Array, spec: TFIMVQESpec) -> Array:
    """Evaluate the open-boundary TFIM expectation without a dense H matrix."""

    return jnp.asarray(
        jnp.real(
            jnp.vdot(
                state,
                tfim_hamiltonian_action(state, spec),
            )
        ),
        dtype=_real_dtype(spec),
    )


def unrolled_state(theta: Array, spec: TFIMVQESpec) -> Array:
    """Prepare the variational state with a trace-time-unrolled layer loop."""

    state = initial_state(spec)
    for layer in range(spec.depth):
        state = apply_layer(state, theta[layer], spec)
    return state


def unrolled_energy(theta: Array, spec: TFIMVQESpec) -> Array:
    """Reference VQE energy."""

    return tfim_energy(unrolled_state(theta, spec), spec)
