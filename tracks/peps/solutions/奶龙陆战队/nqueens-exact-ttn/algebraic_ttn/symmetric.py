"""Row-reflection-aware contraction DAG with exact mirrored-subtree reuse."""

from dataclasses import dataclass
from math import prod
from typing import Any

import numpy as np

from .packed import PackedTensor, packed_multiply_and_reduce


def reflect_row_label(label: str, n: int) -> str:
    if label.startswith("column_"):
        row = int(label.split("_", 1)[1])
        return f"column_{n - 1 - row}"
    return label


def reflect_leaf_name(name: str, n: int) -> str:
    if name.startswith("ONE_"):
        row = int(name.split("_", 1)[1])
        return f"ONE_{n - 1 - row}"
    if name.startswith("PAIR_"):
        _, row_a, row_b = name.split("_")
        return f"PAIR_{n - 1 - int(row_b)}_{n - 1 - int(row_a)}"
    return name


@dataclass(slots=True)
class _Shape:
    labels: tuple[str, ...]
    dimensions: tuple[int, ...]
    leaves: frozenset[str]


@dataclass(frozen=True, slots=True)
class SymmetryPlanStep:
    left_index: int
    right_index: int
    reuse_source_index: int | None
    output_labels: tuple[str, ...]
    output_dimensions: tuple[int, ...]


def _outside_labels(
    active: list[_Shape] | list[PackedTensor],
    left_index: int,
    right_index: int,
) -> set[str]:
    return {
        label
        for index, tensor in enumerate(active)
        if index not in (left_index, right_index)
        for label in tensor.labels
    }


def _signature(
    left: _Shape | PackedTensor,
    right: _Shape | PackedTensor,
    outside_labels: set[str],
) -> tuple[list[str], tuple[str, ...], tuple[int, ...]]:
    left_labels = set(left.labels)
    shared = [label for label in left.labels if label in set(right.labels)]
    union = list(left.labels) + [
        label for label in right.labels if label not in left_labels
    ]
    keep = tuple(label for label in union if label in outside_labels)
    dimensions = {
        **dict(zip(left.labels, left.dimensions)),
        **dict(zip(right.labels, right.dimensions)),
    }
    return shared, keep, tuple(dimensions[label] for label in keep)


def _reflected_leaves(leaves: frozenset[str], n: int) -> frozenset[str]:
    return frozenset(reflect_leaf_name(name, n) for name in leaves)


def symmetric_contraction_plan(
    tensors: list[PackedTensor],
    n: int,
    *,
    tie_break: str = "coverage-first",
) -> list[SymmetryPlanStep]:
    """Favor mirror-paired subtrees without changing greedy width priorities."""
    if tie_break not in ("coverage-first", "symmetry-first"):
        raise ValueError("unknown symmetric planner tie break")
    active = [
        _Shape(
            labels=tensor.labels,
            dimensions=tensor.dimensions,
            leaves=frozenset((tensor.name,)),
        )
        for tensor in tensors
    ]
    plan: list[SymmetryPlanStep] = []
    while len(active) > 1:
        leaf_to_index = {
            tensor.leaves: index for index, tensor in enumerate(active)
        }
        best = None
        choice = None
        for left_index in range(len(active)):
            left = active[left_index]
            for right_index in range(left_index + 1, len(active)):
                right = active[right_index]
                outside = _outside_labels(active, left_index, right_index)
                shared, keep, output_dimensions = _signature(
                    left, right, outside
                )
                result_leaves = left.leaves | right.leaves
                reflected_result = _reflected_leaves(result_leaves, n)
                reuse_source = leaf_to_index.get(reflected_result)
                reusable = (
                    reuse_source is not None
                    and reuse_source not in (left_index, right_index)
                )
                reflected_left = leaf_to_index.get(
                    _reflected_leaves(left.leaves, n)
                )
                reflected_right = leaf_to_index.get(
                    _reflected_leaves(right.leaves, n)
                )
                mirror_pair_available = (
                    reflected_left is not None
                    and reflected_right is not None
                    and len(
                        {
                            left_index,
                            right_index,
                            reflected_left,
                            reflected_right,
                        }
                    )
                    == 4
                )
                dense_cells = prod(output_dimensions)
                pair_constraints = sum(
                    name.startswith("PAIR_") for name in result_leaves
                )
                # The first three fields are the original value-blind greedy
                # priorities. For equal boundary size, a subtree containing
                # more fixed pair factors has greater topological constraint
                # coverage; values and nonzero patterns remain unread.
                if tie_break == "coverage-first":
                    secondary = (
                        -pair_constraints,
                        int(not reusable),
                        int(not mirror_pair_available),
                    )
                else:
                    secondary = (
                        int(not reusable),
                        int(not mirror_pair_available),
                        -pair_constraints,
                    )
                score = (
                    int(not shared),
                    dense_cells,
                    len(keep),
                    *secondary,
                    left_index,
                    right_index,
                )
                if best is None or score < best:
                    best = score
                    choice = (
                        left_index,
                        right_index,
                        reuse_source if reusable else None,
                        keep,
                        output_dimensions,
                        result_leaves,
                    )
        if choice is None:
            raise AssertionError("symmetric planner found no contraction pair")
        (
            left_index,
            right_index,
            reuse_source,
            keep,
            output_dimensions,
            result_leaves,
        ) = choice
        plan.append(
            SymmetryPlanStep(
                left_index=left_index,
                right_index=right_index,
                reuse_source_index=reuse_source,
                output_labels=keep,
                output_dimensions=output_dimensions,
            )
        )
        for index in sorted((left_index, right_index), reverse=True):
            active.pop(index)
        active.append(
            _Shape(
                labels=keep,
                dimensions=output_dimensions,
                leaves=result_leaves,
            )
        )
    return plan


def _coordinate(tensor: PackedTensor, position: int) -> np.ndarray:
    stride = prod(tensor.dimensions[position + 1 :])
    return (tensor.keys // stride) % tensor.dimensions[position]


def _mirror_relabel_tensor(
    source: PackedTensor,
    *,
    n: int,
    target_labels: tuple[str, ...],
    target_dimensions: tuple[int, ...],
    name: str,
    tree: dict[str, Any],
) -> tuple[PackedTensor, bool]:
    mapped_labels = tuple(reflect_row_label(label, n) for label in source.labels)
    if set(mapped_labels) != set(target_labels):
        raise AssertionError("mirror source has incompatible output labels")
    if mapped_labels == target_labels:
        keys = source.keys
        values = source.values
        shared_buffers = True
    else:
        keys = np.zeros(source.nnz, dtype=np.uint64)
        mapped_positions = {
            reflect_row_label(label, n): position
            for position, label in enumerate(source.labels)
        }
        for label, dimension in zip(target_labels, target_dimensions):
            keys *= dimension
            keys += _coordinate(source, mapped_positions[label])
        order = np.argsort(keys, kind="stable")
        keys = keys[order]
        values = source.values[order].copy()
        shared_buffers = False
    return (
        PackedTensor(
            name=name,
            labels=target_labels,
            dimensions=target_dimensions,
            keys=keys,
            values=values,
            tree=tree,
        ),
        shared_buffers,
    )


def _unique_array_bytes(tensors: list[PackedTensor]) -> int:
    arrays: dict[int, int] = {}
    for tensor in tensors:
        arrays.setdefault(id(tensor.keys), tensor.keys.nbytes)
        arrays.setdefault(id(tensor.values), tensor.values.nbytes)
    return sum(arrays.values())


def greedy_symmetric_packed_contract(
    tensors: list[PackedTensor], n: int
) -> tuple[int, dict[str, Any], dict[str, int]]:
    """Execute a symmetry-tied contraction DAG on exact packed arrays."""
    if not tensors:
        raise ValueError("at least one factor is required")
    active = list(tensors)
    active_leaves = [frozenset((tensor.name,)) for tensor in tensors]
    plan = symmetric_contraction_plan(tensors, n)
    multiply_adds = 0
    executed_contractions = 0
    mirror_reuses = 0
    shared_buffer_reuses = 0
    max_rank = max(tensor.rank for tensor in active)
    max_nnz = max(tensor.nnz for tensor in active)
    max_dense = max(tensor.dense_cells for tensor in active)
    max_tensor_bytes = max(tensor.nbytes for tensor in active)
    max_live_unique_bytes = _unique_array_bytes(active)

    for step_index, step in enumerate(plan):
        left = active[step.left_index]
        right = active[step.right_index]
        result_leaves = (
            active_leaves[step.left_index] | active_leaves[step.right_index]
        )
        node_name = f"hyper_contract_{step_index}"
        if step.reuse_source_index is None:
            outside = _outside_labels(
                active, step.left_index, step.right_index
            )
            result, operations, _ = packed_multiply_and_reduce(
                left,
                right,
                outside_labels=outside,
                name=node_name,
            )
            multiply_adds += operations
            executed_contractions += 1
        else:
            source = active[step.reuse_source_index]
            tree = {
                "type": "hyper_contract",
                "name": node_name,
                "matched_indices": [
                    label for label in left.labels if label in set(right.labels)
                ],
                "summed_indices": [
                    label
                    for label in list(left.labels)
                    + [
                        label
                        for label in right.labels
                        if label not in set(left.labels)
                    ]
                    if label not in set(step.output_labels)
                ],
                "output_indices": list(step.output_labels),
                "output_rank": len(step.output_labels),
                "output_nnz": source.nnz,
                "execution": "row_reflection_reuse",
                "reuse_source": source.name,
                "left": left.tree,
                "right": right.tree,
            }
            result, shared = _mirror_relabel_tensor(
                source,
                n=n,
                target_labels=step.output_labels,
                target_dimensions=step.output_dimensions,
                name=node_name,
                tree=tree,
            )
            mirror_reuses += 1
            shared_buffer_reuses += int(shared)

        max_rank = max(max_rank, result.rank)
        max_nnz = max(max_nnz, result.nnz)
        max_dense = max(max_dense, result.dense_cells)
        max_tensor_bytes = max(max_tensor_bytes, result.nbytes)
        for index in sorted(
            (step.left_index, step.right_index), reverse=True
        ):
            active.pop(index)
            active_leaves.pop(index)
        active.append(result)
        active_leaves.append(result_leaves)
        max_live_unique_bytes = max(
            max_live_unique_bytes, _unique_array_bytes(active)
        )

    final = active[0]
    if final.labels:
        raise AssertionError("symmetric contraction did not produce a scalar")
    scalar = (
        int(final.values[0])
        if final.nnz == 1 and int(final.keys[0]) == 0
        else 0
    )
    return (
        scalar,
        final.tree,
        {
            "conceptual_contractions": len(plan),
            "executed_contractions": executed_contractions,
            "mirror_reuses": mirror_reuses,
            "shared_buffer_reuses": shared_buffer_reuses,
            "sparse_multiply_adds": multiply_adds,
            "max_intermediate_rank": max_rank,
            "max_intermediate_nnz": max_nnz,
            "max_intermediate_dense_cells": max_dense,
            "max_tensor_bytes": max_tensor_bytes,
            "max_live_unique_array_bytes": max_live_unique_bytes,
        },
    )
