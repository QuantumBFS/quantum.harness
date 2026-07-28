from __future__ import annotations

from dataclasses import dataclass

from config import SystemConfig, require_jax


jax, jnp = require_jax()


@dataclass(frozen=True)
class SystemModel:
    config: SystemConfig
    target: object
    drift: object
    control_hamiltonians: tuple[object, ...]


def pauli_i():
    return jnp.eye(2, dtype=jnp.complex128)


def pauli_x():
    return jnp.array([[0, 1], [1, 0]], dtype=jnp.complex128)


def pauli_y():
    return jnp.array([[0, -1j], [1j, 0]], dtype=jnp.complex128)


def pauli_z():
    return jnp.array([[1, 0], [0, -1]], dtype=jnp.complex128)


def target_gate(name: str):
    gate = name.upper()
    if gate == "X":
        return pauli_x()
    if gate == "CZ":
        return jnp.diag(jnp.array([1, 1, 1, -1], dtype=jnp.complex128))
    raise ValueError(f"unknown target gate: {name}")


def build_system(config: SystemConfig) -> SystemModel:
    if config.name == "one_qubit_x":
        controls = (2.0 * pauli_x(), 2.0 * pauli_y())
        drift = 0.08 * pauli_z()
    elif config.name == "two_qubit_cz":
        xi = jnp.kron(pauli_x(), pauli_i())
        yi = jnp.kron(pauli_y(), pauli_i())
        ix = jnp.kron(pauli_i(), pauli_x())
        iy = jnp.kron(pauli_i(), pauli_y())
        zz = jnp.kron(pauli_z(), pauli_z())
        controls = (0.5 * xi, 0.5 * yi, 0.5 * ix, 0.5 * iy)
        drift = 0.18 * zz
    else:
        raise ValueError(f"unknown system config: {config.name}")
    return SystemModel(
        config=config,
        target=target_gate(config.target),
        drift=drift,
        control_hamiltonians=controls,
    )
