"""Exact matrix-product-operator tensors for the open-boundary TFIM."""

from __future__ import annotations

import jax.numpy as jnp
from jax import Array

from vqetape.spec import TFIMVQESpec


def _dtype(spec: TFIMVQESpec):
    return jnp.complex64 if spec.dtype == "complex64" else jnp.complex128


def _paulis(dtype):
    identity = jnp.eye(2, dtype=dtype)
    pauli_x = jnp.asarray([[0, 1], [1, 0]], dtype=dtype)
    pauli_z = jnp.asarray([[1, 0], [0, -1]], dtype=dtype)
    return identity, pauli_x, pauli_z


def tfim_mpo_tensors(spec: TFIMVQESpec) -> tuple[Array, ...]:
    """Return the exact bond-dimension-3 TFIM MPO."""

    dtype = _dtype(spec)
    identity, pauli_x, pauli_z = _paulis(dtype)
    first = jnp.stack(
        (
            -spec.field * pauli_x,
            -spec.coupling * pauli_z,
            identity,
        ),
        axis=0,
    )
    bulk = jnp.zeros((3, 3, 2, 2), dtype=dtype)
    bulk = bulk.at[0, 0].set(identity)
    bulk = bulk.at[1, 0].set(pauli_z)
    bulk = bulk.at[2, 0].set(-spec.field * pauli_x)
    bulk = bulk.at[2, 1].set(-spec.coupling * pauli_z)
    bulk = bulk.at[2, 2].set(identity)
    last = jnp.stack(
        (
            identity,
            pauli_z,
            -spec.field * pauli_x,
        ),
        axis=0,
    )
    return (first,) + (bulk,) * (spec.nqubits - 2) + (last,)


def _kron_product(operators: list[Array]) -> Array:
    result = operators[0]
    for operator in operators[1:]:
        result = jnp.kron(result, operator)
    return result


def dense_tfim_hamiltonian(spec: TFIMVQESpec) -> Array:
    """Construct a small-system dense TFIM Hamiltonian oracle."""

    dtype = _dtype(spec)
    identity, pauli_x, pauli_z = _paulis(dtype)
    dimension = 1 << spec.nqubits
    hamiltonian = jnp.zeros((dimension, dimension), dtype=dtype)
    for wire in range(spec.nqubits - 1):
        operators = [identity] * spec.nqubits
        operators[wire] = pauli_z
        operators[wire + 1] = pauli_z
        hamiltonian = (
            hamiltonian
            - spec.coupling * _kron_product(operators)
        )
    for wire in range(spec.nqubits):
        operators = [identity] * spec.nqubits
        operators[wire] = pauli_x
        hamiltonian = (
            hamiltonian
            - spec.field * _kron_product(operators)
        )
    return hamiltonian
