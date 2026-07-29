"""Static bra-operator-ket tensor-network templates for exact VQE terms."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Literal

import jax.numpy as jnp
import opt_einsum as oe
from jax import Array

from vqetape.kernels import rx_matrix, rzz_matrix, rzz_schmidt_factors
from vqetape.spec import (
    GateRepresentation,
    HamiltonianRepresentation,
    TFIMVQESpec,
)
from vqetape.tape import name_residual
from vqetape.tfim_mpo import tfim_mpo_tensors

SlotKind = Literal[
    "initial_ket",
    "initial_bra",
    "ket_rx",
    "bra_rx",
    "ket_rzz",
    "bra_rzz",
    "ket_rzz_left",
    "ket_rzz_right",
    "bra_rzz_left",
    "bra_rzz_right",
    "operator",
    "hamiltonian_mpo_first",
    "hamiltonian_mpo_bulk",
    "hamiltonian_mpo_last",
]


@dataclass(frozen=True)
class ProductPauliTerm:
    coefficient: float
    operators: tuple[Literal["I", "X", "Y", "Z"], ...]

    def __post_init__(self) -> None:
        if not isfinite(self.coefficient):
            raise ValueError("term coefficient must be finite")
        if not self.operators:
            raise ValueError("term must contain at least one operator")
        if any(operator not in ("I", "X", "Y", "Z") for operator in self.operators):
            raise ValueError("unsupported Pauli operator")


@dataclass(frozen=True)
class TensorSlot:
    kind: SlotKind
    indices: tuple[int, ...]
    shape: tuple[int, ...]
    layer: int | None = None
    wire: int | None = None


@dataclass(frozen=True)
class TensorNetworkTemplate:
    spec: TFIMVQESpec
    gate_representation: GateRepresentation
    hamiltonian_representation: HamiltonianRepresentation
    slots: tuple[TensorSlot, ...]
    equation: str
    shapes: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        counts = Counter(
            index for slot in self.slots for index in slot.indices
        )
        if not counts or any(count != 2 for count in counts.values()):
            raise ValueError("expectation tensor network must be closed")
        if not self.equation.endswith("->"):
            raise ValueError("expectation tensor network must have scalar output")
        if self.shapes != tuple(slot.shape for slot in self.slots):
            raise ValueError("template shapes do not match slots")
        if self.gate_representation not in ("dense", "operator_schmidt"):
            raise ValueError(
                "unsupported gate_representation: "
                f"{self.gate_representation}"
            )
        if self.hamiltonian_representation not in ("pauli_sum", "mpo"):
            raise ValueError(
                "unsupported hamiltonian_representation: "
                f"{self.hamiltonian_representation}"
            )


class _IndexAllocator:
    def __init__(self) -> None:
        self._next = 0

    def take(self) -> int:
        value = self._next
        self._next += 1
        return value


def _append_circuit(
    *,
    slots: list[TensorSlot],
    frontier: list[int],
    allocator: _IndexAllocator,
    spec: TFIMVQESpec,
    side: Literal["ket", "bra"],
    gate_representation: GateRepresentation,
) -> None:
    rzz_kind: SlotKind = "ket_rzz" if side == "ket" else "bra_rzz"
    left_kind: SlotKind = (
        "ket_rzz_left" if side == "ket" else "bra_rzz_left"
    )
    right_kind: SlotKind = (
        "ket_rzz_right" if side == "ket" else "bra_rzz_right"
    )
    rx_kind: SlotKind = "ket_rx" if side == "ket" else "bra_rx"
    for layer in range(spec.depth):
        for wire in range(spec.nqubits - 1):
            output0 = allocator.take()
            output1 = allocator.take()
            if gate_representation == "dense":
                slots.append(
                    TensorSlot(
                        kind=rzz_kind,
                        indices=(
                            output0,
                            output1,
                            frontier[wire],
                            frontier[wire + 1],
                        ),
                        shape=(2, 2, 2, 2),
                        layer=layer,
                        wire=wire,
                    )
                )
            else:
                schmidt = allocator.take()
                slots.extend(
                    (
                        TensorSlot(
                            kind=left_kind,
                            indices=(
                                output0,
                                frontier[wire],
                                schmidt,
                            ),
                            shape=(2, 2, 2),
                            layer=layer,
                            wire=wire,
                        ),
                        TensorSlot(
                            kind=right_kind,
                            indices=(
                                output1,
                                frontier[wire + 1],
                                schmidt,
                            ),
                            shape=(2, 2, 2),
                            layer=layer,
                            wire=wire,
                        ),
                    )
                )
            frontier[wire] = output0
            frontier[wire + 1] = output1
        for wire in range(spec.nqubits):
            output = allocator.take()
            slots.append(
                TensorSlot(
                    kind=rx_kind,
                    indices=(output, frontier[wire]),
                    shape=(2, 2),
                    layer=layer,
                    wire=wire,
                )
            )
            frontier[wire] = output


def build_expectation_template(
    spec: TFIMVQESpec,
    *,
    gate_representation: GateRepresentation = "dense",
) -> TensorNetworkTemplate:
    """Build one reusable closed topology for every product-Pauli term."""

    if gate_representation not in ("dense", "operator_schmidt"):
        raise ValueError(
            f"unsupported gate_representation: {gate_representation}"
        )
    allocator, slots, ket_frontier, bra_frontier = _build_circuit_slots(
        spec,
        gate_representation,
    )

    slots.extend(
        TensorSlot(
            "operator",
            (bra_frontier[wire], ket_frontier[wire]),
            (2, 2),
            wire=wire,
        )
        for wire in range(spec.nqubits)
    )

    equation = ",".join(
        "".join(oe.get_symbol(index) for index in slot.indices)
        for slot in slots
    ) + "->"
    return TensorNetworkTemplate(
        spec=spec,
        gate_representation=gate_representation,
        hamiltonian_representation="pauli_sum",
        slots=tuple(slots),
        equation=equation,
        shapes=tuple(slot.shape for slot in slots),
    )


def _build_circuit_slots(
    spec: TFIMVQESpec,
    gate_representation: GateRepresentation,
) -> tuple[_IndexAllocator, list[TensorSlot], list[int], list[int]]:
    allocator = _IndexAllocator()
    slots: list[TensorSlot] = []
    ket_frontier = [allocator.take() for _ in range(spec.nqubits)]
    slots.extend(
        TensorSlot("initial_ket", (index,), (2,), wire=wire)
        for wire, index in enumerate(ket_frontier)
    )
    bra_frontier = [allocator.take() for _ in range(spec.nqubits)]
    slots.extend(
        TensorSlot("initial_bra", (index,), (2,), wire=wire)
        for wire, index in enumerate(bra_frontier)
    )
    _append_circuit(
        slots=slots,
        frontier=ket_frontier,
        allocator=allocator,
        spec=spec,
        side="ket",
        gate_representation=gate_representation,
    )
    _append_circuit(
        slots=slots,
        frontier=bra_frontier,
        allocator=allocator,
        spec=spec,
        side="bra",
        gate_representation=gate_representation,
    )
    return allocator, slots, ket_frontier, bra_frontier


def build_mpo_expectation_template(
    spec: TFIMVQESpec,
    *,
    gate_representation: GateRepresentation = "dense",
) -> TensorNetworkTemplate:
    """Build a closed bra–MPO–ket TFIM expectation topology."""

    if gate_representation not in ("dense", "operator_schmidt"):
        raise ValueError(
            f"unsupported gate_representation: {gate_representation}"
        )
    allocator, slots, ket_frontier, bra_frontier = _build_circuit_slots(
        spec,
        gate_representation,
    )
    mpo_bonds = [allocator.take() for _ in range(spec.nqubits - 1)]
    slots.append(
        TensorSlot(
            "hamiltonian_mpo_first",
            (
                mpo_bonds[0],
                bra_frontier[0],
                ket_frontier[0],
            ),
            (3, 2, 2),
            wire=0,
        )
    )
    for wire in range(1, spec.nqubits - 1):
        slots.append(
            TensorSlot(
                "hamiltonian_mpo_bulk",
                (
                    mpo_bonds[wire - 1],
                    mpo_bonds[wire],
                    bra_frontier[wire],
                    ket_frontier[wire],
                ),
                (3, 3, 2, 2),
                wire=wire,
            )
        )
    slots.append(
        TensorSlot(
            "hamiltonian_mpo_last",
            (
                mpo_bonds[-1],
                bra_frontier[-1],
                ket_frontier[-1],
            ),
            (3, 2, 2),
            wire=spec.nqubits - 1,
        )
    )
    equation = ",".join(
        "".join(oe.get_symbol(index) for index in slot.indices)
        for slot in slots
    ) + "->"
    return TensorNetworkTemplate(
        spec=spec,
        gate_representation=gate_representation,
        hamiltonian_representation="mpo",
        slots=tuple(slots),
        equation=equation,
        shapes=tuple(slot.shape for slot in slots),
    )


def _product_state_vector(spec: TFIMVQESpec) -> Array:
    dtype = jnp.complex64 if spec.dtype == "complex64" else jnp.complex128
    if spec.initial_state == "zero":
        return jnp.asarray([1, 0], dtype=dtype)
    return jnp.asarray([1 / sqrt(2), 1 / sqrt(2)], dtype=dtype)


def _pauli_matrix(name: str, dtype) -> Array:
    matrices = {
        "I": [[1, 0], [0, 1]],
        "X": [[0, 1], [1, 0]],
        "Y": [[0, -1j], [1j, 0]],
        "Z": [[1, 0], [0, -1]],
    }
    return jnp.asarray(matrices[name], dtype=dtype)


def bind_term_tensors(
    template: TensorNetworkTemplate,
    theta: Array,
    term: ProductPauliTerm,
    *,
    name_residuals: bool = False,
) -> tuple[Array, ...]:
    """Bind parameters and one product-Pauli operator to a static template."""

    spec = template.spec
    if template.hamiltonian_representation != "pauli_sum":
        raise ValueError("term tensors require a pauli_sum template")
    if len(term.operators) != spec.nqubits:
        raise ValueError("operator count must match nqubits")
    if tuple(theta.shape) != spec.parameter_shape:
        raise ValueError(
            f"theta shape must be {spec.parameter_shape}, got {tuple(theta.shape)}"
        )
    dtype = jnp.complex64 if spec.dtype == "complex64" else jnp.complex128
    product_state = _product_state_vector(spec)
    tensors: list[Array] = []
    for slot_index, slot in enumerate(template.slots):
        if slot.kind == "operator":
            assert slot.wire is not None
            tensor = _pauli_matrix(term.operators[slot.wire], dtype)
        else:
            tensor = _bind_non_hamiltonian_slot(
                slot,
                theta,
                product_state,
                dtype,
            )
        tensor = _maybe_name_tensor(
            tensor,
            slot,
            slot_index,
            name_residuals,
        )
        tensors.append(tensor)
    return tuple(tensors)


def _bind_non_hamiltonian_slot(
    slot: TensorSlot,
    theta: Array,
    product_state: Array,
    dtype,
) -> Array:
    if slot.kind == "initial_ket":
        return product_state
    if slot.kind == "initial_bra":
        return jnp.conj(product_state)
    if slot.kind in ("ket_rx", "bra_rx"):
        assert slot.layer is not None and slot.wire is not None
        tensor = rx_matrix(theta[slot.layer, 1, slot.wire], dtype)
        return jnp.conj(tensor) if slot.kind == "bra_rx" else tensor
    if slot.kind in ("ket_rzz", "bra_rzz"):
        assert slot.layer is not None and slot.wire is not None
        tensor = rzz_matrix(
            theta[slot.layer, 0, slot.wire],
            dtype,
        ).reshape(2, 2, 2, 2)
        return jnp.conj(tensor) if slot.kind == "bra_rzz" else tensor
    if slot.kind in (
        "ket_rzz_left",
        "ket_rzz_right",
        "bra_rzz_left",
        "bra_rzz_right",
    ):
        assert slot.layer is not None and slot.wire is not None
        left, right = rzz_schmidt_factors(
            theta[slot.layer, 0, slot.wire],
            dtype,
        )
        tensor = left if slot.kind.endswith("_left") else right
        return jnp.conj(tensor) if slot.kind.startswith("bra_") else tensor
    raise ValueError(f"unsupported non-Hamiltonian slot kind: {slot.kind}")


def _maybe_name_tensor(
    tensor: Array,
    slot: TensorSlot,
    slot_index: int,
    enabled: bool,
) -> Array:
    if not enabled:
        return tensor
    location = (
        f"l{slot.layer if slot.layer is not None else 'x'}:"
        f"w{slot.wire if slot.wire is not None else 'x'}"
    )
    return name_residual(
        tensor,
        f"slot:{slot.kind}:{location}:i{slot_index}",
    )


def bind_mpo_tensors(
    template: TensorNetworkTemplate,
    theta: Array,
    *,
    name_residuals: bool = False,
) -> tuple[Array, ...]:
    """Bind one complete circuit and exact TFIM MPO network."""

    spec = template.spec
    if template.hamiltonian_representation != "mpo":
        raise ValueError("MPO tensors require an mpo template")
    if tuple(theta.shape) != spec.parameter_shape:
        raise ValueError(
            f"theta shape must be {spec.parameter_shape}, got {tuple(theta.shape)}"
        )
    dtype = jnp.complex64 if spec.dtype == "complex64" else jnp.complex128
    product_state = _product_state_vector(spec)
    mpo_tensors = tfim_mpo_tensors(spec)
    tensors: list[Array] = []
    for slot_index, slot in enumerate(template.slots):
        if slot.kind.startswith("hamiltonian_mpo_"):
            assert slot.wire is not None
            tensor = mpo_tensors[slot.wire]
        else:
            tensor = _bind_non_hamiltonian_slot(
                slot,
                theta,
                product_state,
                dtype,
            )
        tensor = _maybe_name_tensor(
            tensor,
            slot,
            slot_index,
            name_residuals,
        )
        if tuple(tensor.shape) != slot.shape:
            raise ValueError(
                f"bound tensor shape {tuple(tensor.shape)} "
                f"does not match slot shape {slot.shape}"
            )
        tensors.append(tensor)
    if len(mpo_tensors) != spec.nqubits:
        raise ValueError("MPO tensor count must match nqubits")
    return tuple(tensors)
