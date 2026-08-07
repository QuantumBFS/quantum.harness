"""U(1)-charge bookkeeping for symmetry-adapted RG relaxations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class ChargeBasis:
    """A deterministic partition of coordinates by integer doubled charge."""

    labels: tuple[int, ...]
    sectors: tuple[int, ...]
    indices: tuple[tuple[int, ...], ...]
    permutation: NDArray[np.int64]

    @classmethod
    def from_labels(cls, labels: tuple[int, ...]) -> "ChargeBasis":
        normalized = tuple(int(label) for label in labels)
        sectors = tuple(sorted(set(normalized)))
        indices = tuple(
            tuple(index for index, label in enumerate(normalized) if label == sector)
            for sector in sectors
        )
        permutation = np.array(
            [index for block in indices for index in block], dtype=np.int64
        )
        return cls(normalized, sectors, indices, permutation)

    @property
    def size(self) -> int:
        return len(self.labels)

    @property
    def block_sizes(self) -> tuple[int, ...]:
        return tuple(len(block) for block in self.indices)


@dataclass(frozen=True)
class RGMPSChargeBases:
    """Charge partitions for every coordinate ordering in the RG dual."""

    local: ChargeBasis
    first: ChargeBasis
    second: ChargeBasis
    omega: ChargeBasis

    @property
    def equality(self) -> ChargeBasis:
        """Backward-compatible name for the first (compressed, spin) space."""
        return self.first


def u1_tensor_mask(
    virtual_charges: tuple[int, ...],
    *,
    physical_charges: tuple[int, int] = (1, -1),
) -> NDArray[np.bool_]:
    """Return allowed ``(left, spin, right)`` entries for U(1) conservation."""
    charges = tuple(int(charge) for charge in virtual_charges)
    if not charges:
        raise ValueError("at least one virtual charge is required")
    return np.array(
        [
            [
                [
                    charges[right] - charges[left]
                    == physical_charges[spin]
                    for right in range(len(charges))
                ]
                for spin in range(len(physical_charges))
            ]
            for left in range(len(charges))
        ],
        dtype=bool,
    )


def infer_virtual_charges(
    tensor: NDArray[np.complex128],
    *,
    physical_charges: tuple[int, int] = (1, -1),
    tolerance: float = 1e-12,
) -> tuple[int, ...]:
    """Infer virtual charges from ``q_right-q_left=q_physical``.

    A separate zero gauge is chosen for each disconnected virtual component.
    The returned labels are exact integers; inconsistent selection rules are
    rejected instead of being projected silently.
    """
    array = np.asarray(tensor)
    if (
        array.ndim != 3
        or array.shape[1] != len(physical_charges)
        or array.shape[0] != array.shape[2]
    ):
        raise ValueError("tensor must have shape (D,2,D)")
    if not np.all(np.isfinite(array)):
        raise ValueError("tensor contains non-finite entries")
    bond = array.shape[0]
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(bond)]
    for left, spin, right in np.argwhere(np.abs(array) > tolerance):
        delta = int(physical_charges[int(spin)])
        adjacency[int(left)].append((int(right), delta))
        adjacency[int(right)].append((int(left), -delta))
    charges: list[int | None] = [None] * bond
    for root in range(bond):
        if charges[root] is not None:
            continue
        charges[root] = 0
        stack = [root]
        while stack:
            current = stack.pop()
            assert charges[current] is not None
            for following, delta in adjacency[current]:
                proposed = int(charges[current]) + delta
                if charges[following] is None:
                    charges[following] = proposed
                    stack.append(following)
                elif charges[following] != proposed:
                    raise ValueError(
                        "tensor has inconsistent U(1) charge selection rules"
                    )
    return tuple(int(charge) for charge in charges)


def split_charge_blocks(
    matrix: NDArray[np.generic],
    basis: ChargeBasis,
    *,
    tolerance: float = 1e-12,
) -> tuple[NDArray[np.generic], ...]:
    """Extract diagonal charge blocks and reject forbidden couplings."""
    array = np.asarray(matrix)
    if array.shape != (basis.size, basis.size):
        raise ValueError("matrix and charge basis dimensions differ")
    allowed = np.equal.outer(basis.labels, basis.labels)
    if np.any(np.abs(array[~allowed]) > tolerance):
        raise ValueError("matrix contains a nonzero cross-sector entry")
    return tuple(
        array[np.ix_(indices, indices)].copy() for indices in basis.indices
    )


def assemble_charge_blocks(
    blocks: tuple[NDArray[np.generic], ...],
    basis: ChargeBasis,
) -> NDArray[np.generic]:
    """Embed charge blocks back into the original coordinate ordering."""
    if len(blocks) != len(basis.indices):
        raise ValueError("charge block count mismatch")
    dtype = np.result_type(*[np.asarray(block).dtype for block in blocks])
    result = np.zeros((basis.size, basis.size), dtype=dtype)
    for block, indices in zip(blocks, basis.indices, strict=True):
        array = np.asarray(block)
        expected = (len(indices), len(indices))
        if array.shape != expected:
            raise ValueError("charge block dimension mismatch")
        result[np.ix_(indices, indices)] = array
    return result


def mps_rg_charge_bases(
    tensor: NDArray[np.complex128],
    *,
    tolerance: float = 1e-12,
) -> RGMPSChargeBases:
    """Build charge bases matching the Kronecker orderings of the RG solver."""
    virtual = infer_virtual_charges(tensor, tolerance=tolerance)
    physical = (1, -1)
    compressed = tuple(
        virtual[right] - virtual[left]
        for left in range(len(virtual))
        for right in range(len(virtual))
    )
    local = tuple(left + right for left in physical for right in physical)
    first = tuple(
        charge + spin for charge in compressed for spin in physical
    )
    second = tuple(
        spin + charge for spin in physical for charge in compressed
    )
    omega = tuple(
        left + charge + right
        for left in physical
        for charge in compressed
        for right in physical
    )
    return RGMPSChargeBases(
        local=ChargeBasis.from_labels(local),
        first=ChargeBasis.from_labels(first),
        second=ChargeBasis.from_labels(second),
        omega=ChargeBasis.from_labels(omega),
    )
