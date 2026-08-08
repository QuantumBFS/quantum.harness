"""Problem-agnostic sparse tensors and exact binary contraction trees."""

from dataclasses import dataclass
from math import prod
from typing import Any


@dataclass(slots=True)
class SparseTensor:
    name: str
    labels: tuple[str, ...]
    dimensions: tuple[int, ...]
    data: dict[tuple[int, ...], int]
    tree: dict[str, Any]

    def __post_init__(self) -> None:
        if len(self.labels) != len(self.dimensions):
            raise ValueError("labels and dimensions differ in length")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("tensor labels must be unique")
        for key, value in self.data.items():
            if len(key) != len(self.labels):
                raise ValueError("tensor key has the wrong rank")
            if not value:
                raise ValueError("zero entries must not be stored")
            if any(index < 0 or index >= dim for index, dim in zip(key, self.dimensions)):
                raise ValueError("tensor index is outside its dimension")

    @property
    def rank(self) -> int:
        return len(self.labels)

    @property
    def dense_cells(self) -> int:
        return prod(self.dimensions)


def contraction_signature(
    left: SparseTensor, right: SparseTensor
) -> tuple[list[str], list[str], tuple[int, ...]]:
    right_labels = set(right.labels)
    shared = [label for label in left.labels if label in right_labels]
    shared_set = set(shared)
    output_labels = [
        label for label in left.labels if label not in shared_set
    ] + [label for label in right.labels if label not in shared_set]
    dimension_by_label = {
        **dict(zip(left.labels, left.dimensions)),
        **dict(zip(right.labels, right.dimensions)),
    }
    for label in shared:
        if left.dimensions[left.labels.index(label)] != right.dimensions[
            right.labels.index(label)
        ]:
            raise ValueError(f"shared label {label} has inconsistent dimensions")
    output_dimensions = tuple(dimension_by_label[label] for label in output_labels)
    return shared, output_labels, output_dimensions


def contract(
    left: SparseTensor,
    right: SparseTensor,
    *,
    name: str,
) -> tuple[SparseTensor, int]:
    """Contract every shared label using exact integer multiply-adds."""
    shared, output_labels, output_dimensions = contraction_signature(left, right)
    shared_set = set(shared)
    left_shared_positions = [left.labels.index(label) for label in shared]
    right_shared_positions = [right.labels.index(label) for label in shared]
    left_output_positions = [
        position
        for position, label in enumerate(left.labels)
        if label not in shared_set
    ]
    right_output_positions = [
        position
        for position, label in enumerate(right.labels)
        if label not in shared_set
    ]

    right_buckets: dict[tuple[int, ...], list[tuple[tuple[int, ...], int]]] = {}
    for key, value in right.data.items():
        shared_key = tuple(key[position] for position in right_shared_positions)
        right_buckets.setdefault(shared_key, []).append((key, value))

    output: dict[tuple[int, ...], int] = {}
    multiply_adds = 0
    for left_key, left_value in left.data.items():
        shared_key = tuple(
            left_key[position] for position in left_shared_positions
        )
        for right_key, right_value in right_buckets.get(shared_key, ()):
            output_key = tuple(
                left_key[position] for position in left_output_positions
            ) + tuple(right_key[position] for position in right_output_positions)
            updated = output.get(output_key, 0) + left_value * right_value
            if updated:
                output[output_key] = updated
            else:
                output.pop(output_key, None)
            multiply_adds += 1

    tree = {
        "type": "contract",
        "name": name,
        "contracted_indices": shared,
        "output_indices": output_labels,
        "output_rank": len(output_labels),
        "output_nnz": len(output),
        "left": left.tree,
        "right": right.tree,
    }
    return (
        SparseTensor(
            name=name,
            labels=tuple(output_labels),
            dimensions=output_dimensions,
            data=output,
            tree=tree,
        ),
        multiply_adds,
    )


def _pair_score(
    left: SparseTensor, right: SparseTensor, left_index: int, right_index: int
) -> tuple[int, int, int, int, int]:
    shared, output_labels, output_dimensions = contraction_signature(left, right)
    if not shared:
        # Connected networks should not need outer products until forced.
        disconnected_penalty = 1
    else:
        disconnected_penalty = 0
    # The planner deliberately uses only topology and dimensions, not tensor
    # values, solution counts, or any problem-semantic state.
    return (
        disconnected_penalty,
        prod(output_dimensions),
        len(output_labels),
        left_index,
        right_index,
    )


def greedy_contract(
    tensors: list[SparseTensor],
) -> tuple[int, dict[str, Any], dict[str, int]]:
    """Build and execute a topology-only binary contraction tree."""
    if not tensors:
        raise ValueError("at least one tensor is required")
    active = list(tensors)
    step = 0
    total_multiply_adds = 0
    max_rank = max(tensor.rank for tensor in active)
    max_nnz = max(len(tensor.data) for tensor in active)
    max_dense_cells = max(tensor.dense_cells for tensor in active)

    while len(active) > 1:
        best: tuple[int, int, int, int, int] | None = None
        pair: tuple[int, int] | None = None
        for left_index in range(len(active)):
            for right_index in range(left_index + 1, len(active)):
                score = _pair_score(
                    active[left_index],
                    active[right_index],
                    left_index,
                    right_index,
                )
                if best is None or score < best:
                    best = score
                    pair = (left_index, right_index)
        if pair is None:
            raise AssertionError("contraction planner found no pair")
        left_index, right_index = pair
        left, right = active[left_index], active[right_index]
        result, operations = contract(left, right, name=f"contract_{step}")
        total_multiply_adds += operations
        max_rank = max(max_rank, result.rank)
        max_nnz = max(max_nnz, len(result.data))
        max_dense_cells = max(max_dense_cells, result.dense_cells)
        for index in sorted(pair, reverse=True):
            active.pop(index)
        active.append(result)
        step += 1

    final = active[0]
    if final.labels or final.dimensions:
        raise AssertionError("network contraction did not produce a scalar")
    scalar = final.data.get((), 0)
    statistics = {
        "contractions": step,
        "multiply_adds": total_multiply_adds,
        "max_intermediate_rank": max_rank,
        "max_intermediate_nnz": max_nnz,
        "max_intermediate_dense_cells": max_dense_cells,
    }
    return scalar, final.tree, statistics
