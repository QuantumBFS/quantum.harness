"""Exact hypergraph tensor contraction after algebraically absorbing COPY tensors."""

from math import prod
from typing import Any

from .tensor import SparseTensor


def _outside_labels(
    active: list[SparseTensor], left_index: int, right_index: int
) -> set[str]:
    return {
        label
        for index, tensor in enumerate(active)
        if index not in (left_index, right_index)
        for label in tensor.labels
    }


def multiply_and_reduce(
    left: SparseTensor,
    right: SparseTensor,
    *,
    outside_labels: set[str],
    name: str,
) -> tuple[SparseTensor, int, list[str]]:
    """Multiply shared-index factors and sum indices internal to the pair."""
    right_label_set = set(right.labels)
    shared = [label for label in left.labels if label in right_label_set]
    union_labels = list(left.labels) + [
        label for label in right.labels if label not in set(left.labels)
    ]
    keep_labels = [label for label in union_labels if label in outside_labels]
    eliminated = [label for label in union_labels if label not in outside_labels]
    dimension_by_label = {
        **dict(zip(left.labels, left.dimensions)),
        **dict(zip(right.labels, right.dimensions)),
    }
    for label in shared:
        if left.dimensions[left.labels.index(label)] != right.dimensions[
            right.labels.index(label)
        ]:
            raise ValueError(f"shared label {label} has inconsistent dimensions")
    keep_dimensions = tuple(dimension_by_label[label] for label in keep_labels)

    left_shared_positions = [left.labels.index(label) for label in shared]
    right_shared_positions = [right.labels.index(label) for label in shared]
    right_buckets: dict[tuple[int, ...], list[tuple[tuple[int, ...], int]]] = {}
    for key, value in right.data.items():
        shared_key = tuple(key[position] for position in right_shared_positions)
        right_buckets.setdefault(shared_key, []).append((key, value))

    left_position = {label: position for position, label in enumerate(left.labels)}
    right_position = {
        label: position for position, label in enumerate(right.labels)
    }
    output: dict[tuple[int, ...], int] = {}
    multiply_adds = 0
    for left_key, left_value in left.data.items():
        shared_key = tuple(
            left_key[position] for position in left_shared_positions
        )
        for right_key, right_value in right_buckets.get(shared_key, ()):
            output_key = tuple(
                left_key[left_position[label]]
                if label in left_position
                else right_key[right_position[label]]
                for label in keep_labels
            )
            updated = output.get(output_key, 0) + left_value * right_value
            if updated:
                output[output_key] = updated
            else:
                output.pop(output_key, None)
            multiply_adds += 1

    tree = {
        "type": "hyper_contract",
        "name": name,
        "matched_indices": shared,
        "summed_indices": eliminated,
        "output_indices": keep_labels,
        "output_rank": len(keep_labels),
        "output_nnz": len(output),
        "left": left.tree,
        "right": right.tree,
    }
    return (
        SparseTensor(
            name=name,
            labels=tuple(keep_labels),
            dimensions=keep_dimensions,
            data=output,
            tree=tree,
        ),
        multiply_adds,
        eliminated,
    )


def _score(
    active: list[SparseTensor], left_index: int, right_index: int
) -> tuple[int, int, int, int, int]:
    left, right = active[left_index], active[right_index]
    outside = _outside_labels(active, left_index, right_index)
    union = list(left.labels) + [
        label for label in right.labels if label not in set(left.labels)
    ]
    keep = [label for label in union if label in outside]
    dimensions = {
        **dict(zip(left.labels, left.dimensions)),
        **dict(zip(right.labels, right.dimensions)),
    }
    shared = set(left.labels) & set(right.labels)
    # No tensor values or N-queens state semantics enter this score.
    return (
        int(not shared),
        prod(dimensions[label] for label in keep),
        len(keep),
        left_index,
        right_index,
    )


def greedy_hyper_contract(
    tensors: list[SparseTensor],
) -> tuple[int, dict[str, Any], dict[str, int]]:
    """Execute a topology/dimension-only binary hypergraph contraction tree."""
    active = list(tensors)
    if not active:
        raise ValueError("at least one factor is required")
    total_operations = 0
    max_rank = max(tensor.rank for tensor in active)
    max_nnz = max(len(tensor.data) for tensor in active)
    max_dense = max(tensor.dense_cells for tensor in active)
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
            raise AssertionError("no hypergraph contraction pair found")
        left_index, right_index = pair
        outside = _outside_labels(active, left_index, right_index)
        result, operations, _ = multiply_and_reduce(
            active[left_index],
            active[right_index],
            outside_labels=outside,
            name=f"hyper_contract_{step}",
        )
        total_operations += operations
        max_rank = max(max_rank, result.rank)
        max_nnz = max(max_nnz, len(result.data))
        max_dense = max(max_dense, result.dense_cells)
        for index in sorted(pair, reverse=True):
            active.pop(index)
        active.append(result)
        step += 1
    final = active[0]
    if final.labels:
        raise AssertionError("hypergraph contraction did not produce a scalar")
    return (
        final.data.get((), 0),
        final.tree,
        {
            "contractions": step,
            "multiply_adds": total_operations,
            "max_intermediate_rank": max_rank,
            "max_intermediate_nnz": max_nnz,
            "max_intermediate_dense_cells": max_dense,
        },
    )
