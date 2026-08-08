"""Compact contiguous-array backend for exact nonnegative tensor contraction."""

from dataclasses import dataclass
from math import prod
from typing import Any

import numpy as np


UINT64_MAX = int(np.iinfo(np.uint64).max)


@dataclass(slots=True)
class CompactTensor:
    """A dense C-order tensor whose entries are exact unsigned integers."""

    name: str
    labels: tuple[str, ...]
    dimensions: tuple[int, ...]
    data: np.ndarray
    tree: dict[str, Any]

    def __post_init__(self) -> None:
        if len(self.labels) != len(self.dimensions):
            raise ValueError("labels and dimensions differ in length")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("tensor labels must be unique")
        if self.data.dtype != np.uint64:
            raise ValueError("compact tensors require uint64 entries")
        if self.data.shape != self.dimensions:
            raise ValueError("array shape does not match tensor dimensions")
        if not self.data.flags.c_contiguous:
            self.data = np.ascontiguousarray(self.data)

    @property
    def rank(self) -> int:
        return len(self.labels)

    @property
    def dense_cells(self) -> int:
        return prod(self.dimensions)

    @property
    def nnz(self) -> int:
        return int(np.count_nonzero(self.data))


def _leaf_tree(
    name: str, kind: str, labels: tuple[str, ...], nnz: int
) -> dict[str, object]:
    return {
        "type": "leaf",
        "name": name,
        "tensor_kind": kind,
        "indices": list(labels),
        "nnz": nnz,
    }


def build_compact_copy_absorbed_network(n: int) -> list[CompactTensor]:
    """Build the COPY-absorbed N-queens factor network in contiguous arrays."""
    if n < 1:
        raise ValueError("the algebraic network requires n >= 1")
    # Every intermediate entry counts a subset of at most n**n assignments.
    # This proof-level bound prevents silent uint64 overflow.
    if n**n > UINT64_MAX:
        raise OverflowError(
            f"n**n={n**n} exceeds the exact uint64 safety bound"
        )

    tensors: list[CompactTensor] = []
    columns = np.arange(n, dtype=np.int64)
    differences = np.abs(columns[:, None] - columns[None, :])
    unequal = columns[:, None] != columns[None, :]

    for row in range(n):
        label = f"column_{row}"
        name = f"ONE_{row}"
        data = np.ones((n,), dtype=np.uint64)
        tensors.append(
            CompactTensor(
                name=name,
                labels=(label,),
                dimensions=(n,),
                data=data,
                tree=_leaf_tree(name, "ONE", (label,), n),
            )
        )

    for row_a in range(n):
        for row_b in range(row_a + 1, n):
            labels = (f"column_{row_a}", f"column_{row_b}")
            allowed = unequal & (differences != row_b - row_a)
            data = allowed.astype(np.uint64, copy=True)
            name = f"PAIR_{row_a}_{row_b}"
            tensors.append(
                CompactTensor(
                    name=name,
                    labels=labels,
                    dimensions=(n, n),
                    data=data,
                    tree=_leaf_tree(
                        name, "PAIR", labels, int(np.count_nonzero(data))
                    ),
                )
            )

    scalar_name = "SCALAR_ONE"
    scalar = np.array(1, dtype=np.uint64)
    tensors.append(
        CompactTensor(
            name=scalar_name,
            labels=(),
            dimensions=(),
            data=scalar,
            tree=_leaf_tree(scalar_name, "SCALAR", (), 1),
        )
    )
    return tensors


def _outside_labels(
    active: list[CompactTensor], left_index: int, right_index: int
) -> set[str]:
    return {
        label
        for index, tensor in enumerate(active)
        if index not in (left_index, right_index)
        for label in tensor.labels
    }


def _signature(
    left: CompactTensor,
    right: CompactTensor,
    outside_labels: set[str],
) -> tuple[list[str], list[str], list[str], dict[str, int]]:
    left_labels = set(left.labels)
    right_labels = set(right.labels)
    shared = [label for label in left.labels if label in right_labels]
    union_labels = list(left.labels) + [
        label for label in right.labels if label not in left_labels
    ]
    keep_labels = [label for label in union_labels if label in outside_labels]
    eliminated = [label for label in union_labels if label not in outside_labels]
    dimensions = {
        **dict(zip(left.labels, left.dimensions)),
        **dict(zip(right.labels, right.dimensions)),
    }
    for label in shared:
        if left.dimensions[left.labels.index(label)] != right.dimensions[
            right.labels.index(label)
        ]:
            raise ValueError(f"shared label {label} has inconsistent dimensions")
    return shared, keep_labels, eliminated, dimensions


def compact_multiply_and_reduce(
    left: CompactTensor,
    right: CompactTensor,
    *,
    outside_labels: set[str],
    name: str,
) -> tuple[CompactTensor, int, list[str]]:
    """Multiply, align repeated labels, and sum subtree-internal labels."""
    shared, keep_labels, eliminated, dimensions = _signature(
        left, right, outside_labels
    )
    union_labels = list(left.labels) + [
        label for label in right.labels if label not in set(left.labels)
    ]
    subscript = {label: index for index, label in enumerate(union_labels)}
    left_subscript = [subscript[label] for label in left.labels]
    right_subscript = [subscript[label] for label in right.labels]
    output_subscript = [subscript[label] for label in keep_labels]

    result_data = np.einsum(
        left.data,
        left_subscript,
        right.data,
        right_subscript,
        output_subscript,
        optimize=True,
    )
    result_data = np.asarray(result_data, dtype=np.uint64)
    if result_data.ndim and not result_data.flags.c_contiguous:
        result_data = np.ascontiguousarray(result_data)

    output_dimensions = tuple(dimensions[label] for label in keep_labels)
    output_nnz = int(np.count_nonzero(result_data))
    tree = {
        "type": "hyper_contract",
        "name": name,
        "matched_indices": shared,
        "summed_indices": eliminated,
        "output_indices": keep_labels,
        "output_rank": len(keep_labels),
        "output_nnz": output_nnz,
        "left": left.tree,
        "right": right.tree,
    }
    dense_terms = prod(dimensions[label] for label in union_labels)
    return (
        CompactTensor(
            name=name,
            labels=tuple(keep_labels),
            dimensions=output_dimensions,
            data=result_data,
            tree=tree,
        ),
        dense_terms,
        eliminated,
    )


def _score(
    active: list[CompactTensor], left_index: int, right_index: int
) -> tuple[int, int, int, int, int]:
    left, right = active[left_index], active[right_index]
    outside = _outside_labels(active, left_index, right_index)
    _, keep, _, dimensions = _signature(left, right, outside)
    shared = set(left.labels) & set(right.labels)
    # Deliberately value-blind: only incidence, dimensions, and stable indices.
    return (
        int(not shared),
        prod(dimensions[label] for label in keep),
        len(keep),
        left_index,
        right_index,
    )


def greedy_compact_hyper_contract(
    tensors: list[CompactTensor],
) -> tuple[int, dict[str, Any], dict[str, int]]:
    """Execute the same topology-only tree using contiguous uint64 arrays."""
    active = list(tensors)
    if not active:
        raise ValueError("at least one factor is required")
    dense_multiply_adds = 0
    max_rank = max(tensor.rank for tensor in active)
    max_nnz = max(tensor.nnz for tensor in active)
    max_dense = max(tensor.dense_cells for tensor in active)
    max_tensor_bytes = max(tensor.data.nbytes for tensor in active)
    max_live_array_bytes = sum(tensor.data.nbytes for tensor in active)
    step = 0

    while len(active) > 1:
        best = None
        pair = None
        for left_index in range(len(active)):
            for right_index in range(left_index + 1, len(active)):
                score = _score(active, left_index, right_index)
                if best is None or score < best:
                    best, pair = score, (left_index, right_index)
        if pair is None:
            raise AssertionError("no compact contraction pair found")

        left_index, right_index = pair
        outside = _outside_labels(active, left_index, right_index)
        result, operations, _ = compact_multiply_and_reduce(
            active[left_index],
            active[right_index],
            outside_labels=outside,
            name=f"hyper_contract_{step}",
        )
        dense_multiply_adds += operations
        max_rank = max(max_rank, result.rank)
        max_nnz = max(max_nnz, result.nnz)
        max_dense = max(max_dense, result.dense_cells)
        max_tensor_bytes = max(max_tensor_bytes, result.data.nbytes)
        # At this point result and both inputs coexist.
        live_bytes = sum(tensor.data.nbytes for tensor in active)
        max_live_array_bytes = max(
            max_live_array_bytes, live_bytes + result.data.nbytes
        )
        for index in sorted(pair, reverse=True):
            active.pop(index)
        active.append(result)
        step += 1

    final = active[0]
    if final.labels:
        raise AssertionError("compact contraction did not produce a scalar")
    return (
        int(final.data.item()),
        final.tree,
        {
            "contractions": step,
            "dense_multiply_adds": dense_multiply_adds,
            "max_intermediate_rank": max_rank,
            "max_intermediate_nnz": max_nnz,
            "max_intermediate_dense_cells": max_dense,
            "max_tensor_bytes": max_tensor_bytes,
            "max_live_array_bytes": max_live_array_bytes,
        },
    )
