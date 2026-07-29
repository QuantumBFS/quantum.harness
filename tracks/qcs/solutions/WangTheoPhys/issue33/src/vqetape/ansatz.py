"""Exact ordered gate structures for adaptive VQE ansatz growth."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any, Literal

from jax import Array
import jax.numpy as jnp

from vqetape.kernels import (
    initial_state,
    tfim_energy,
)
from vqetape.spec import TFIMVQESpec

AnsatzOperatorName = Literal["rx", "rzz", "yz", "zy"]


@dataclass(frozen=True, order=True)
class AnsatzOperator:
    """One local Pauli rotation in an ordered ansatz."""

    kind: AnsatzOperatorName
    wire: int

    def __post_init__(self) -> None:
        if self.kind not in ("rx", "rzz", "yz", "zy"):
            raise ValueError(
                f"unsupported ansatz operator: {self.kind}"
            )
        if self.wire < 0:
            raise ValueError("operator wire must be nonnegative")

    @property
    def label(self) -> str:
        if self.kind == "rx":
            return f"rx-{self.wire}"
        return (
            f"{self.kind}-{self.wire}-{self.wire + 1}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "wire": self.wire}

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> AnsatzOperator:
        return cls(**payload)


@dataclass(frozen=True)
class AnsatzStructure:
    """A complete ordered sequence of exact local rotations."""

    nqubits: int
    operators: tuple[AnsatzOperator, ...]

    def __post_init__(self) -> None:
        if self.nqubits < 2:
            raise ValueError("nqubits must be at least 2")
        for operator in self.operators:
            limit = (
                self.nqubits
                if operator.kind == "rx"
                else self.nqubits - 1
            )
            if operator.wire >= limit:
                raise ValueError(
                    f"{operator.label} is outside "
                    f"{self.nqubits}-qubit chain"
                )

    @property
    def parameter_count(self) -> int:
        return len(self.operators)

    @property
    def label(self) -> str:
        digest = sha1(
            "\0".join(
                operator.label
                for operator in self.operators
            ).encode("utf-8")
        ).hexdigest()[:10]
        return (
            f"ordered-n{self.nqubits}-"
            f"p{self.parameter_count}-{digest}"
        )

    def append(
        self,
        operator: AnsatzOperator,
    ) -> AnsatzStructure:
        return AnsatzStructure(
            self.nqubits,
            self.operators + (operator,),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nqubits": self.nqubits,
            "operators": [
                operator.to_dict()
                for operator in self.operators
            ],
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> AnsatzStructure:
        return cls(
            nqubits=int(payload["nqubits"]),
            operators=tuple(
                AnsatzOperator.from_dict(item)
                for item in payload["operators"]
            ),
        )


def fixed_rzz_rx_structure(
    nqubits: int,
    depth: int,
) -> AnsatzStructure:
    """Return the existing layered RZZ-then-RX ansatz as a sequence."""

    if depth < 1:
        raise ValueError("depth must be positive")
    operators: list[AnsatzOperator] = []
    for _ in range(depth):
        operators.extend(
            AnsatzOperator("rzz", wire)
            for wire in range(nqubits - 1)
        )
        operators.extend(
            AnsatzOperator("rx", wire)
            for wire in range(nqubits)
        )
    return AnsatzStructure(nqubits, tuple(operators))


def local_operator_pool(
    nqubits: int,
) -> tuple[AnsatzOperator, ...]:
    """Return the full local global-X-compatible operator pool."""

    if nqubits < 2:
        raise ValueError("nqubits must be at least 2")
    return tuple(
        [
            AnsatzOperator(kind, wire)
            for kind in ("rzz", "yz", "zy")
            for wire in range(nqubits - 1)
        ]
        + [
            AnsatzOperator("rx", wire)
            for wire in range(nqubits)
        ]
    )


def _apply_local_pauli(
    state: Array,
    pauli: Literal["X", "Y", "Z"],
    wire: int,
    nqubits: int,
) -> Array:
    tensor = state.reshape((2,) * nqubits)
    if pauli == "X":
        return jnp.flip(tensor, axis=wire).reshape(-1)
    if pauli == "Z":
        signs = jnp.asarray(
            [1, -1],
            dtype=state.dtype,
        )
        shape = [1] * nqubits
        shape[wire] = 2
        return (tensor * signs.reshape(shape)).reshape(-1)
    matrix = jnp.asarray(
        [[0, -1j], [1j, 0]],
        dtype=state.dtype,
    )
    moved = jnp.moveaxis(tensor, wire, 0)
    updated = matrix @ moved.reshape(2, -1)
    return jnp.moveaxis(
        updated.reshape((2,) + moved.shape[1:]),
        0,
        wire,
    ).reshape(-1)


def apply_ansatz_generator(
    state: Array,
    operator: AnsatzOperator,
    spec: TFIMVQESpec,
) -> Array:
    """Apply the Pauli generator of one supported rotation."""

    if operator.kind == "rx":
        return _apply_local_pauli(
            state,
            "X",
            operator.wire,
            spec.nqubits,
        )
    paulis = {
        "rzz": ("Z", "Z"),
        "yz": ("Y", "Z"),
        "zy": ("Z", "Y"),
    }[operator.kind]
    generated = _apply_local_pauli(
        state,
        paulis[0],
        operator.wire,
        spec.nqubits,
    )
    return _apply_local_pauli(
        generated,
        paulis[1],
        operator.wire + 1,
        spec.nqubits,
    )


def layered_parameters_to_vector(
    theta: Array,
    spec: TFIMVQESpec,
) -> Array:
    """Drop RZZ padding and preserve gate execution order."""

    if theta.shape != spec.parameter_shape:
        raise ValueError("layered parameter shape mismatch")
    pieces = []
    for layer in range(spec.depth):
        pieces.append(theta[layer, 0, :-1])
        pieces.append(theta[layer, 1, :])
    return jnp.concatenate(pieces)


def ordered_ansatz_state(
    parameters: Array,
    structure: AnsatzStructure,
    spec: TFIMVQESpec,
) -> Array:
    """Prepare an exact state from an ordered local gate sequence."""

    if structure.nqubits != spec.nqubits:
        raise ValueError(
            "structure and workload qubit counts differ"
        )
    if parameters.shape != (structure.parameter_count,):
        raise ValueError("ordered parameter shape mismatch")
    state = initial_state(spec)
    for angle, operator in zip(
        parameters,
        structure.operators,
        strict=True,
    ):
        generator_state = apply_ansatz_generator(
            state,
            operator,
            spec,
        )
        state = (
            jnp.cos(angle / 2) * state
            - 1j * jnp.sin(angle / 2) * generator_state
        )
    return state


def ordered_ansatz_energy(
    parameters: Array,
    structure: AnsatzStructure,
    spec: TFIMVQESpec,
) -> Array:
    """Evaluate exact TFIM energy for an ordered ansatz."""

    return tfim_energy(
        ordered_ansatz_state(parameters, structure, spec),
        spec,
    )
