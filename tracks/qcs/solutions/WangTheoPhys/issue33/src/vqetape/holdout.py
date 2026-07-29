"""Exact longitudinal-field Ising VQE holdout."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any

from jax import Array
import jax.numpy as jnp
import numpy as np

from vqetape.kernels import (
    apply_rx,
    apply_rzz,
    initial_state,
    tfim_hamiltonian_action,
)
from vqetape.spec import TFIMVQESpec


@dataclass(frozen=True)
class LongitudinalIsingSpec:
    """Open Ising chain with transverse and longitudinal fields."""

    nqubits: int
    depth: int
    coupling: float = 1.0
    transverse_field: float = 1.0
    longitudinal_field: float = 0.35
    dtype: str = "complex128"

    def __post_init__(self) -> None:
        if self.nqubits < 2:
            raise ValueError("nqubits must be at least 2")
        if self.depth < 1:
            raise ValueError("depth must be positive")
        for value in (
            self.coupling,
            self.transverse_field,
            self.longitudinal_field,
        ):
            if not isfinite(value):
                raise ValueError(
                    "Hamiltonian coefficients must be finite"
                )
        if self.dtype not in ("complex64", "complex128"):
            raise ValueError(
                f"unsupported dtype: {self.dtype}"
            )

    @property
    def parameter_shape(self) -> tuple[int, int, int]:
        return (self.depth, 3, self.nqubits)

    @property
    def active_parameter_count(self) -> int:
        return self.depth * (3 * self.nqubits - 1)

    def tfim_spec(self) -> TFIMVQESpec:
        return TFIMVQESpec(
            nqubits=self.nqubits,
            depth=self.depth,
            coupling=self.coupling,
            field=self.transverse_field,
            initial_state="plus",
            dtype=self.dtype,  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> LongitudinalIsingSpec:
        return cls(**payload)


def _apply_z(
    state: Array,
    wire: int,
    nqubits: int,
) -> Array:
    tensor = state.reshape((2,) * nqubits)
    signs = jnp.asarray([1, -1], dtype=state.dtype)
    shape = [1] * nqubits
    shape[wire] = 2
    return (tensor * signs.reshape(shape)).reshape(-1)


def _apply_ry(
    state: Array,
    angle: Array,
    wire: int,
    nqubits: int,
) -> Array:
    tensor = state.reshape((2,) * nqubits)
    moved = jnp.moveaxis(tensor, wire, 0)
    half = angle / 2
    matrix = jnp.asarray(
        [
            [jnp.cos(half), -jnp.sin(half)],
            [jnp.sin(half), jnp.cos(half)],
        ],
        dtype=state.dtype,
    )
    updated = matrix @ moved.reshape(2, -1)
    return jnp.moveaxis(
        updated.reshape((2,) + moved.shape[1:]),
        0,
        wire,
    ).reshape(-1)


def longitudinal_ansatz_state(
    parameters: Array,
    spec: LongitudinalIsingSpec,
) -> Array:
    """Prepare the symmetry-breaking RZZ–RY–RX holdout ansatz."""

    if parameters.shape != spec.parameter_shape:
        raise ValueError("holdout parameter shape mismatch")
    tfim_spec = spec.tfim_spec()
    state = initial_state(tfim_spec)
    for layer in range(spec.depth):
        for wire in range(spec.nqubits - 1):
            state = apply_rzz(
                state,
                parameters[layer, 0, wire],
                wire,
                wire + 1,
                spec.nqubits,
            )
        for wire in range(spec.nqubits):
            state = _apply_ry(
                state,
                parameters[layer, 1, wire],
                wire,
                spec.nqubits,
            )
        for wire in range(spec.nqubits):
            state = apply_rx(
                state,
                parameters[layer, 2, wire],
                wire,
                spec.nqubits,
            )
    return state


def longitudinal_hamiltonian_action(
    state: Array,
    spec: LongitudinalIsingSpec,
) -> Array:
    """Apply the exact holdout Hamiltonian."""

    acted = tfim_hamiltonian_action(
        state,
        spec.tfim_spec(),
    )
    for wire in range(spec.nqubits):
        acted = (
            acted
            - spec.longitudinal_field
            * _apply_z(state, wire, spec.nqubits)
        )
    return acted


def longitudinal_energy(
    parameters: Array,
    spec: LongitudinalIsingSpec,
) -> Array:
    """Return exact statevector energy for the holdout."""

    state = longitudinal_ansatz_state(parameters, spec)
    return jnp.real(
        jnp.vdot(
            state,
            longitudinal_hamiltonian_action(state, spec),
        )
    )


def dense_longitudinal_hamiltonian(
    spec: LongitudinalIsingSpec,
) -> np.ndarray:
    """Construct the audited small-system dense Hamiltonian."""

    identity = np.eye(2, dtype=np.complex128)
    pauli_x = np.asarray(
        [[0, 1], [1, 0]],
        dtype=np.complex128,
    )
    pauli_z = np.asarray(
        [[1, 0], [0, -1]],
        dtype=np.complex128,
    )

    def product(operators: dict[int, np.ndarray]):
        result = np.asarray([1.0], dtype=np.complex128)
        for wire in range(spec.nqubits):
            result = np.kron(
                result,
                operators.get(wire, identity),
            )
        return result

    dimension = 1 << spec.nqubits
    hamiltonian = np.zeros(
        (dimension, dimension),
        dtype=np.complex128,
    )
    for wire in range(spec.nqubits - 1):
        hamiltonian -= spec.coupling * product(
            {wire: pauli_z, wire + 1: pauli_z}
        )
    for wire in range(spec.nqubits):
        hamiltonian -= spec.transverse_field * product(
            {wire: pauli_x}
        )
        hamiltonian -= spec.longitudinal_field * product(
            {wire: pauli_z}
        )
    return hamiltonian


def longitudinal_ground_energy(
    spec: LongitudinalIsingSpec,
) -> float:
    """Return exact dense ground energy for the small holdout."""

    return float(
        np.linalg.eigvalsh(
            dense_longitudinal_hamiltonian(spec)
        )[0]
    )


def global_x_commutator_norm(
    spec: LongitudinalIsingSpec,
) -> float:
    """Return Frobenius norm of [H, X⊗...⊗X]."""

    global_x = np.asarray([[1.0]], dtype=np.complex128)
    pauli_x = np.asarray(
        [[0, 1], [1, 0]],
        dtype=np.complex128,
    )
    for _ in range(spec.nqubits):
        global_x = np.kron(global_x, pauli_x)
    hamiltonian = dense_longitudinal_hamiltonian(spec)
    commutator = (
        hamiltonian @ global_x
        - global_x @ hamiltonian
    )
    return float(np.linalg.norm(commutator))


def holdout_z2_applicability(
    spec: LongitudinalIsingSpec,
) -> dict[str, Any]:
    """Explain why TFIM Z2 spatial compression cannot be reused."""

    reasons = []
    if abs(spec.longitudinal_field) > 0:
        reasons.append(
            "longitudinal Z field breaks global-X symmetry"
        )
    reasons.append(
        "RY ansatz generators break global-X symmetry"
    )
    return {
        "applicable": False,
        "reasons": reasons,
        "commutator_norm": global_x_commutator_norm(spec),
    }
