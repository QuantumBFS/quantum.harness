from __future__ import annotations

from config import require_jax
from pulses import as_segments


jax, jnp = require_jax()


def matrix_exp_hermitian(hamiltonian, dt: float):
    values, vectors = jnp.linalg.eigh(hamiltonian)
    phases = jnp.exp(-1j * dt * values)
    return (vectors * phases) @ vectors.conj().T


def propagator(theta, system):
    config = system.config
    controls = as_segments(jnp.asarray(theta, dtype=jnp.float64), config)
    unitary = jnp.eye(config.hilbert_dim, dtype=jnp.complex128)
    dt = 1.0 / float(config.segments)
    for segment in range(config.segments):
        hamiltonian = system.drift
        for index, control_h in enumerate(system.control_hamiltonians):
            hamiltonian = hamiltonian + controls[segment, index] * control_h
        unitary = matrix_exp_hermitian(hamiltonian, dt) @ unitary
    return unitary


def unitary_fidelity(unitary, target):
    dim = target.shape[0]
    overlap = jnp.trace(target.conj().T @ unitary)
    return jnp.real(jnp.abs(overlap) ** 2 / (dim * dim))


def unitary_infidelity(unitary, target):
    return jnp.clip(1.0 - unitary_fidelity(unitary, target), 0.0, 1.0)


def gate_fidelity(theta, system):
    return unitary_fidelity(propagator(theta, system), system.target)


def gate_infidelity(theta, system):
    return unitary_infidelity(propagator(theta, system), system.target)
