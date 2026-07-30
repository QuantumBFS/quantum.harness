"""Packed sorted-coordinate arrays for exact sparse tensor contraction."""

from dataclasses import dataclass
from math import prod
from typing import Any

import numpy as np

from .compact import UINT64_MAX


@dataclass(slots=True)
class PackedTensor:
    """Sparse tensor stored as sorted flat coordinates and uint64 values."""

    name: str
    labels: tuple[str, ...]
    dimensions: tuple[int, ...]
    keys: np.ndarray
    values: np.ndarray
    tree: dict[str, Any]

    def __post_init__(self) -> None:
        if len(self.labels) != len(self.dimensions):
            raise ValueError("labels and dimensions differ in length")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("tensor labels must be unique")
        if self.keys.dtype != np.uint64 or self.values.dtype != np.uint64:
            raise ValueError("packed coordinates and values require uint64")
        if self.keys.ndim != 1 or self.values.ndim != 1:
            raise ValueError("packed coordinates and values must be vectors")
        if self.keys.size != self.values.size:
            raise ValueError("packed coordinates and values differ in length")
        if self.keys.size:
            if np.any(self.values == 0):
                raise ValueError("zero entries must not be stored")
            if np.any(self.keys[1:] <= self.keys[:-1]):
                raise ValueError("packed coordinates must be strictly sorted")
            if int(self.keys[-1]) >= self.dense_cells:
                raise ValueError("packed coordinate is outside tensor dimensions")

    @property
    def rank(self) -> int:
        return len(self.labels)

    @property
    def dense_cells(self) -> int:
        return prod(self.dimensions)

    @property
    def nnz(self) -> int:
        return int(self.keys.size)

    @property
    def nbytes(self) -> int:
        return int(self.keys.nbytes + self.values.nbytes)


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


def build_packed_copy_absorbed_network(n: int) -> list[PackedTensor]:
    """Build the fixed COPY-absorbed factor network in packed coordinates."""
    if n < 1:
        raise ValueError("the algebraic network requires n >= 1")
    if n**n > UINT64_MAX:
        raise OverflowError(
            f"n**n={n**n} exceeds the exact uint64 safety bound"
        )

    tensors: list[PackedTensor] = []
    columns = np.arange(n, dtype=np.int64)
    differences = np.abs(columns[:, None] - columns[None, :])
    unequal = columns[:, None] != columns[None, :]

    for row in range(n):
        label = f"column_{row}"
        name = f"ONE_{row}"
        keys = np.arange(n, dtype=np.uint64)
        values = np.ones(n, dtype=np.uint64)
        tensors.append(
            PackedTensor(
                name=name,
                labels=(label,),
                dimensions=(n,),
                keys=keys,
                values=values,
                tree=_leaf_tree(name, "ONE", (label,), n),
            )
        )

    for row_a in range(n):
        for row_b in range(row_a + 1, n):
            labels = (f"column_{row_a}", f"column_{row_b}")
            allowed = unequal & (differences != row_b - row_a)
            keys = np.flatnonzero(allowed.reshape(-1)).astype(np.uint64)
            values = np.ones(keys.size, dtype=np.uint64)
            name = f"PAIR_{row_a}_{row_b}"
            tensors.append(
                PackedTensor(
                    name=name,
                    labels=labels,
                    dimensions=(n, n),
                    keys=keys,
                    values=values,
                    tree=_leaf_tree(name, "PAIR", labels, int(keys.size)),
                )
            )

    scalar_name = "SCALAR_ONE"
    tensors.append(
        PackedTensor(
            name=scalar_name,
            labels=(),
            dimensions=(),
            keys=np.array([0], dtype=np.uint64),
            values=np.array([1], dtype=np.uint64),
            tree=_leaf_tree(scalar_name, "SCALAR", (), 1),
        )
    )
    return tensors


def with_horizontal_reflection_domain(
    tensors: list[PackedTensor], n: int, row: int
) -> list[PackedTensor]:
    """Select one representative of every free horizontal-reflection orbit."""
    if n < 2:
        raise ValueError("horizontal reflection requires n >= 2")
    if row < 0 or row >= n // 2:
        raise ValueError(f"reflection row must be in [0, {n // 2})")
    if 2 * n**n > UINT64_MAX:
        raise OverflowError("reflection orbit weight exceeds the uint64 bound")
    mirror = n - 1 - row
    target = f"PAIR_{row}_{mirror}"
    result = list(tensors)
    for index, tensor in enumerate(result):
        if tensor.name != target:
            continue
        column_a = tensor.keys // n
        column_b = tensor.keys % n
        representative = column_a < column_b
        keys = tensor.keys[representative].copy()
        values = tensor.values[representative] * np.uint64(2)
        tree = {
            **tensor.tree,
            "tensor_kind": "HORIZONTAL_REFLECTION_DOMAIN",
            "nnz": int(keys.size),
            "symmetry": "row reflection",
            "representative_condition": (
                f"column_{row} < column_{mirror}"
            ),
            "orbit_weight": 2,
        }
        result[index] = PackedTensor(
            name=tensor.name,
            labels=tensor.labels,
            dimensions=tensor.dimensions,
            keys=keys,
            values=values,
            tree=tree,
        )
        return result
    raise AssertionError(f"missing mirror-pair tensor {target}")


def _outside_labels(
    active: list[PackedTensor], left_index: int, right_index: int
) -> set[str]:
    return {
        label
        for index, tensor in enumerate(active)
        if index not in (left_index, right_index)
        for label in tensor.labels
    }


def _signature(
    left: PackedTensor,
    right: PackedTensor,
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


def _coordinate(tensor: PackedTensor, position: int) -> np.ndarray:
    stride = prod(tensor.dimensions[position + 1 :])
    return (tensor.keys // stride) % tensor.dimensions[position]


def _shared_keys(tensor: PackedTensor, shared: list[str]) -> np.ndarray:
    keys = np.zeros(tensor.nnz, dtype=np.uint64)
    for label in shared:
        position = tensor.labels.index(label)
        keys *= tensor.dimensions[position]
        keys += _coordinate(tensor, position)
    return keys


def _matching_rows(
    left: PackedTensor, right: PackedTensor, shared: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    """Return compact row-index vectors for the sparse equality join."""
    uint32_limit = int(np.iinfo(np.uint32).max)
    if left.nnz > uint32_limit or right.nnz > uint32_limit:
        raise OverflowError("packed row indices exceed the uint32 backend")
    left_shared = _shared_keys(left, shared)
    right_shared = _shared_keys(right, shared)
    left_order = np.argsort(left_shared, kind="stable").astype(np.uint32)
    right_order = np.argsort(right_shared, kind="stable").astype(np.uint32)
    left_sorted = left_shared[left_order]
    right_sorted = right_shared[right_order]
    left_unique, left_start, left_count = np.unique(
        left_sorted, return_index=True, return_counts=True
    )
    right_unique, right_start, right_count = np.unique(
        right_sorted, return_index=True, return_counts=True
    )
    _, left_groups, right_groups = np.intersect1d(
        left_unique, right_unique, assume_unique=True, return_indices=True
    )
    pair_count = int(
        np.sum(
            left_count[left_groups].astype(np.uint64)
            * right_count[right_groups].astype(np.uint64),
            dtype=np.uint64,
        )
    )
    left_rows = np.empty(pair_count, dtype=np.uint32)
    right_rows = np.empty(pair_count, dtype=np.uint32)
    cursor = 0
    for left_group, right_group in zip(left_groups, right_groups):
        left_begin = left_start[left_group]
        left_size = left_count[left_group]
        right_begin = right_start[right_group]
        right_size = right_count[right_group]
        block_size = int(left_size * right_size)
        left_block = left_order[left_begin : left_begin + left_size]
        right_block = right_order[right_begin : right_begin + right_size]
        left_rows[cursor : cursor + block_size] = np.repeat(
            left_block, right_size
        )
        right_rows[cursor : cursor + block_size] = np.tile(
            right_block, left_size
        )
        cursor += block_size
    return left_rows, right_rows


def packed_multiply_and_reduce(
    left: PackedTensor,
    right: PackedTensor,
    *,
    outside_labels: set[str],
    name: str,
) -> tuple[PackedTensor, int, list[str]]:
    """Sparse equality join followed by exact coordinate aggregation."""
    shared, keep_labels, eliminated, dimensions = _signature(
        left, right, outside_labels
    )
    left_rows, right_rows = _matching_rows(left, right, shared)
    pair_count = int(left_rows.size)

    output_keys = np.zeros(pair_count, dtype=np.uint64)
    left_positions = {label: index for index, label in enumerate(left.labels)}
    right_positions = {
        label: index for index, label in enumerate(right.labels)
    }
    for label in keep_labels:
        output_keys *= dimensions[label]
        if label in left_positions:
            coordinates = _coordinate(left, left_positions[label])[left_rows]
        else:
            coordinates = _coordinate(right, right_positions[label])[
                right_rows
            ]
        output_keys += coordinates

    output_values = left.values[left_rows] * right.values[right_rows]
    if pair_count:
        order = np.argsort(output_keys, kind="stable")
        sorted_keys = output_keys[order]
        sorted_values = output_values[order]
        starts = np.empty(pair_count, dtype=bool)
        starts[0] = True
        starts[1:] = sorted_keys[1:] != sorted_keys[:-1]
        start_indices = np.flatnonzero(starts)
        result_keys = sorted_keys[start_indices].copy()
        result_values = np.add.reduceat(
            sorted_values, start_indices, dtype=np.uint64
        )
        nonzero = result_values != 0
        result_keys = result_keys[nonzero]
        result_values = result_values[nonzero]
    else:
        result_keys = np.empty(0, dtype=np.uint64)
        result_values = np.empty(0, dtype=np.uint64)

    output_dimensions = tuple(dimensions[label] for label in keep_labels)
    tree = {
        "type": "hyper_contract",
        "name": name,
        "matched_indices": shared,
        "summed_indices": eliminated,
        "output_indices": keep_labels,
        "output_rank": len(keep_labels),
        "output_nnz": int(result_keys.size),
        "left": left.tree,
        "right": right.tree,
    }
    return (
        PackedTensor(
            name=name,
            labels=tuple(keep_labels),
            dimensions=output_dimensions,
            keys=result_keys,
            values=result_values,
            tree=tree,
        ),
        pair_count,
        eliminated,
    )


def _score(
    active: list[PackedTensor], left_index: int, right_index: int
) -> tuple[int, int, int, int, int]:
    left, right = active[left_index], active[right_index]
    outside = _outside_labels(active, left_index, right_index)
    _, keep, _, dimensions = _signature(left, right, outside)
    shared = set(left.labels) & set(right.labels)
    return (
        int(not shared),
        prod(dimensions[label] for label in keep),
        len(keep),
        left_index,
        right_index,
    )


def packed_contraction_plan(
    tensors: list[PackedTensor],
) -> tuple[list[tuple[int, int]], dict[str, Any]]:
    """Build a contraction plan from labels and dimensions, never values."""
    if not tensors:
        raise ValueError("at least one factor is required")
    empty = np.empty(0, dtype=np.uint64)
    active = [
        PackedTensor(
            name=tensor.name,
            labels=tensor.labels,
            dimensions=tensor.dimensions,
            keys=empty,
            values=empty,
            tree={"type": "leaf", "name": tensor.name},
        )
        for tensor in tensors
    ]
    plan: list[tuple[int, int]] = []
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
            raise AssertionError("no packed contraction pair found")
        left_index, right_index = pair
        left, right = active[left_index], active[right_index]
        outside = _outside_labels(active, left_index, right_index)
        shared, keep, eliminated, dimensions = _signature(
            left, right, outside
        )
        tree = {
            "type": "hyper_contract",
            "name": f"hyper_contract_{step}",
            "matched_indices": shared,
            "summed_indices": eliminated,
            "output_indices": keep,
            "output_rank": len(keep),
            "left": left.tree,
            "right": right.tree,
        }
        planned = PackedTensor(
            name=f"hyper_contract_{step}",
            labels=tuple(keep),
            dimensions=tuple(dimensions[label] for label in keep),
            keys=empty,
            values=empty,
            tree=tree,
        )
        plan.append(pair)
        for index in sorted(pair, reverse=True):
            active.pop(index)
        active.append(planned)
        step += 1
    return plan, active[0].tree


def choose_horizontal_reflection_row(
    tensors: list[PackedTensor], n: int
) -> int:
    """Choose the symmetry-domain leaf from contraction-tree topology only."""
    if n < 2:
        raise ValueError("horizontal reflection requires n >= 2")
    _, tree = packed_contraction_plan(tensors)
    candidates = {
        f"PAIR_{row}_{n - 1 - row}": row for row in range(n // 2)
    }
    scores = {row: (-1, -1) for row in candidates.values()}

    def visit(node: dict[str, Any]) -> set[str]:
        if node["type"] == "leaf":
            return {node["name"]}
        leaves = visit(node["left"]) | visit(node["right"])
        step = int(node["name"].rsplit("_", 1)[1])
        score = (int(node["output_rank"]), step)
        for name, row in candidates.items():
            if name in leaves:
                scores[row] = max(scores[row], score)
        return leaves

    visit(tree)
    # Stable tie break: prefer the smaller row index.
    return max(scores, key=lambda row: (scores[row], -row))


def greedy_packed_hyper_contract(
    tensors: list[PackedTensor],
) -> tuple[int, dict[str, Any], dict[str, int]]:
    """Execute the topology-only tree with packed sparse coordinate arrays."""
    active = list(tensors)
    if not active:
        raise ValueError("at least one factor is required")
    sparse_multiply_adds = 0
    max_join_pairs = 0
    max_rank = max(tensor.rank for tensor in active)
    max_nnz = max(tensor.nnz for tensor in active)
    max_dense = max(tensor.dense_cells for tensor in active)
    max_tensor_bytes = max(tensor.nbytes for tensor in active)
    max_live_array_bytes = sum(tensor.nbytes for tensor in active)
    plan, _ = packed_contraction_plan(tensors)

    for step, pair in enumerate(plan):
        left_index, right_index = pair
        outside = _outside_labels(active, left_index, right_index)
        result, operations, _ = packed_multiply_and_reduce(
            active[left_index],
            active[right_index],
            outside_labels=outside,
            name=f"hyper_contract_{step}",
        )
        sparse_multiply_adds += operations
        max_join_pairs = max(max_join_pairs, operations)
        max_rank = max(max_rank, result.rank)
        max_nnz = max(max_nnz, result.nnz)
        max_dense = max(max_dense, result.dense_cells)
        max_tensor_bytes = max(max_tensor_bytes, result.nbytes)
        live_bytes = sum(tensor.nbytes for tensor in active)
        max_live_array_bytes = max(
            max_live_array_bytes, live_bytes + result.nbytes
        )
        for index in sorted(pair, reverse=True):
            active.pop(index)
        active.append(result)

    final = active[0]
    if final.labels:
        raise AssertionError("packed contraction did not produce a scalar")
    scalar = (
        int(final.values[0])
        if final.nnz == 1 and int(final.keys[0]) == 0
        else 0
    )
    return (
        scalar,
        final.tree,
        {
            "contractions": len(plan),
            "sparse_multiply_adds": sparse_multiply_adds,
            "max_join_pairs": max_join_pairs,
            "max_intermediate_rank": max_rank,
            "max_intermediate_nnz": max_nnz,
            "max_intermediate_dense_cells": max_dense,
            "max_tensor_bytes": max_tensor_bytes,
            "max_live_array_bytes": max_live_array_bytes,
        },
    )
