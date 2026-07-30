"""Combined row-reflection DAG reuse and column-reflection even sectors."""

from math import prod
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from .block_reduction import ExactBlockReducer, NumPyBlockReducer
from .parity import (
    JoinBudgetExceeded,
    ParityTensor,
    _reflect_flat_keys,
    compress_row_reflection_sector,
    expand_row_reflection_sector,
    parity_multiply_and_reduce,
    parity_multiply_and_reduce_streaming,
)
from .symmetric import (
    reflect_leaf_name,
    reflect_row_label,
    symmetric_contraction_plan,
)


def _outside_labels(
    active: list[ParityTensor], left_index: int, right_index: int
) -> set[str]:
    return {
        label
        for index, tensor in enumerate(active)
        if index not in (left_index, right_index)
        for label in tensor.labels
    }


def _coordinate(tensor: ParityTensor, position: int) -> np.ndarray:
    stride = prod(tensor.dimensions[position + 1 :])
    return (tensor.keys // stride) % tensor.dimensions[position]


def _mirror_relabel_tensor(
    source: ParityTensor,
    *,
    n: int,
    target_labels: tuple[str, ...],
    target_dimensions: tuple[int, ...],
    name: str,
    tree: dict[str, Any],
) -> tuple[ParityTensor, bool]:
    mapped_labels = tuple(reflect_row_label(label, n) for label in source.labels)
    if set(mapped_labels) != set(target_labels):
        raise AssertionError("mirror source has incompatible parity labels")
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
        keys = np.minimum(
            keys, _reflect_flat_keys(keys, target_dimensions)
        )
        order = np.argsort(keys, kind="stable")
        keys = keys[order]
        values = source.values[order].copy()
        if keys.size and np.any(keys[1:] == keys[:-1]):
            raise AssertionError("mirror relabeling merged distinct parity orbits")
        shared_buffers = False
    return (
        ParityTensor(
            name=name,
            labels=target_labels,
            dimensions=target_dimensions,
            keys=keys,
            values=values,
            tree=tree,
            storage=source.storage if shared_buffers else None,
            row_reflection_n=source.row_reflection_n,
            row_uncompressed_even_nnz=(
                source.row_uncompressed_even_nnz
            ),
            row_uncompressed_full_nnz=(
                source.row_uncompressed_full_nnz
            ),
        ),
        shared_buffers,
    )


def _unique_array_bytes(tensors: list[ParityTensor]) -> int:
    arrays: dict[int, int] = {}
    for tensor in tensors:
        arrays.setdefault(id(tensor.keys), tensor.keys.nbytes)
        arrays.setdefault(id(tensor.values), tensor.values.nbytes)
    return sum(arrays.values())


class SymmetricParityBudgetExceeded(RuntimeError):
    """Carries the exact partial frontier of a budgeted contraction."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        super().__init__(
            f"step {report['blocked_step']} requires "
            f"{report['required_join_pairs']:,} join pairs; limit is "
            f"{report['max_join_pairs_budget']:,}"
        )


def _row_reflection_invariant(
    leaves: frozenset[str], labels: tuple[str, ...], n: int
) -> bool:
    return (
        leaves
        == frozenset(reflect_leaf_name(name, n) for name in leaves)
        and {reflect_row_label(label, n) for label in labels}
        == set(labels)
    )


def greedy_symmetric_parity_contract(
    tensors: list[ParityTensor],
    n: int,
    *,
    max_join_pairs: int | None = None,
    join_chunk_pairs: int | None = None,
    streaming_temp_directory: Path | None = None,
    streaming_merge_strategy: str = "sorted-runs",
    planner_tie_break: str = "coverage-first",
    row_reflection_blocks: bool = False,
    block_reducer: ExactBlockReducer | None = None,
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    """Execute the symmetry-aware DAG with every tensor in its even sector."""
    if not tensors:
        raise ValueError("at least one factor is required")
    reducer = block_reducer or NumPyBlockReducer()
    active_leaves = [frozenset((tensor.name,)) for tensor in tensors]
    active = [
        (
            compress_row_reflection_sector(tensor, n)
            if row_reflection_blocks
            and _row_reflection_invariant(leaves, tensor.labels, n)
            else tensor
        )
        for tensor, leaves in zip(tensors, active_leaves)
    ]
    plan = symmetric_contraction_plan(
        tensors, n, tie_break=planner_tie_break
    )
    multiply_adds = 0
    largest_completed_join = 0
    streaming_contractions = 0
    streaming_generation_seconds = 0.0
    streaming_run_write_seconds = 0.0
    streaming_merge_seconds = 0.0
    join_preflight_seconds = 0.0
    in_memory_contraction_seconds = 0.0
    row_sector_expansion_seconds = 0.0
    row_sector_compression_seconds = 0.0
    mirror_relabel_seconds = 0.0
    row_sector_compressions = sum(
        tensor.row_reflection_n is not None for tensor in active
    )
    row_sector_expansions = 0
    executed_contractions = 0
    mirror_reuses = 0
    shared_buffer_reuses = 0
    max_rank = max(tensor.rank for tensor in active)
    max_nnz = max(tensor.column_even_nnz for tensor in active)
    max_stored_nnz = max(tensor.nnz for tensor in active)
    max_full_nnz = max(tensor.full_nnz for tensor in active)
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
            in_memory_limit = max_join_pairs
            if join_chunk_pairs is not None:
                in_memory_limit = (
                    join_chunk_pairs
                    if in_memory_limit is None
                    else min(in_memory_limit, join_chunk_pairs)
                )
            grouped_join_min_records = getattr(
                reducer, "grouped_join_min_records", None
            )
            if (
                join_chunk_pairs is not None
                and grouped_join_min_records is not None
            ):
                # CUDA can generate grouped Cartesian products directly.
                # Stop the CPU path before it materializes a contribution
                # array large enough to belong on that GPU path.
                in_memory_limit = (
                    grouped_join_min_records
                    if in_memory_limit is None
                    else min(
                        in_memory_limit, grouped_join_min_records
                    )
                )
            try:
                expansion_started = perf_counter()
                left_operand = expand_row_reflection_sector(left)
                right_operand = expand_row_reflection_sector(right)
                row_sector_expansion_seconds += (
                    perf_counter() - expansion_started
                )
                row_sector_expansions += int(left_operand is not left)
                row_sector_expansions += int(right_operand is not right)
                contraction_started = perf_counter()
                result, operations, _ = parity_multiply_and_reduce(
                    left_operand,
                    right_operand,
                    outside_labels=outside,
                    name=node_name,
                    max_join_pairs=in_memory_limit,
                    block_reducer=reducer,
                )
                in_memory_contraction_seconds += (
                    perf_counter() - contraction_started
                )
            except JoinBudgetExceeded as error:
                join_preflight_seconds += (
                    perf_counter() - contraction_started
                )
                if (
                    join_chunk_pairs is not None
                    and (
                        max_join_pairs is None
                        or error.pair_count <= max_join_pairs
                    )
                ):
                    result, operations, _ = (
                        parity_multiply_and_reduce_streaming(
                            left_operand,
                            right_operand,
                            outside_labels=outside,
                            name=node_name,
                            expected_join_pairs=error.pair_count,
                            join_chunk_pairs=join_chunk_pairs,
                            join_plan=error.join_plan,
                            temp_directory=streaming_temp_directory,
                            merge_strategy=streaming_merge_strategy,
                            block_reducer=reducer,
                        )
                    )
                    streaming_contractions += 1
                else:
                    raise SymmetricParityBudgetExceeded(
                        {
                            "n": n,
                            "status": "join_budget_exceeded",
                            "blocked_step": step_index,
                            "conceptual_contractions": len(plan),
                            "completed_plan_steps": step_index,
                            "executed_contractions": executed_contractions,
                            "mirror_reuses": mirror_reuses,
                            "shared_buffer_reuses": shared_buffer_reuses,
                            "streaming_contractions": (
                                streaming_contractions
                            ),
                            "planner_tie_break": planner_tie_break,
                            "row_reflection_blocks": (
                                row_reflection_blocks
                            ),
                            "row_sector_compressions": (
                                row_sector_compressions
                            ),
                            "row_sector_expansions": (
                                row_sector_expansions
                            ),
                            "symmetry_multiply_adds": multiply_adds,
                            "largest_completed_join_pairs": (
                                largest_completed_join
                            ),
                            "required_join_pairs": error.pair_count,
                            "max_join_pairs_budget": (
                                max_join_pairs
                                if max_join_pairs is not None
                                else error.limit
                            ),
                            "blocked_left_name": left.name,
                            "blocked_left_rank": left.rank,
                            "blocked_left_even_sector_nnz": left.nnz,
                            "blocked_right_name": right.name,
                            "blocked_right_rank": right.rank,
                            "blocked_right_even_sector_nnz": right.nnz,
                            "blocked_output_rank": len(
                                step.output_labels
                            ),
                            "blocked_output_dense_cells": prod(
                                step.output_dimensions
                            ),
                            "active_tensor_count": len(active),
                            "active_even_sector_nnz": sum(
                                tensor.column_even_nnz
                                for tensor in active
                            ),
                            "active_stored_nnz": sum(
                                tensor.nnz for tensor in active
                            ),
                            "active_unique_array_bytes": (
                                _unique_array_bytes(active)
                            ),
                            "max_intermediate_rank": max_rank,
                            "max_intermediate_even_sector_nnz": max_nnz,
                            "max_intermediate_stored_nnz": (
                                max_stored_nnz
                            ),
                            "max_intermediate_full_nnz": max_full_nnz,
                            "max_intermediate_dense_cells": max_dense,
                            "max_tensor_bytes": max_tensor_bytes,
                            "max_live_unique_array_bytes": (
                                max_live_unique_bytes
                            ),
                            **reducer.statistics.as_dict(),
                        }
                    ) from error
            streaming_generation_seconds += float(
                result.tree.get("contribution_generation_seconds", 0.0)
            )
            streaming_run_write_seconds += float(
                result.tree.get("run_write_seconds", 0.0)
            )
            streaming_merge_seconds += float(
                result.tree.get("external_merge_seconds", 0.0)
            )
            multiply_adds += operations
            largest_completed_join = max(
                largest_completed_join, operations
            )
            executed_contractions += 1
        else:
            source = active[step.reuse_source_index]
            union_labels = list(left.labels) + [
                label
                for label in right.labels
                if label not in set(left.labels)
            ]
            tree = {
                "type": "hyper_contract",
                "name": node_name,
                "matched_indices": [
                    label for label in left.labels if label in set(right.labels)
                ],
                "summed_indices": [
                    label
                    for label in union_labels
                    if label not in set(step.output_labels)
                ],
                "output_indices": list(step.output_labels),
                "output_rank": len(step.output_labels),
                "output_nnz": source.nnz,
                "output_full_nnz": source.full_nnz,
                "column_reflection_sector": "even",
                "execution": "row_reflection_reuse",
                "reuse_source": source.name,
                "left": left.tree,
                "right": right.tree,
            }
            mirror_started = perf_counter()
            result, shared = _mirror_relabel_tensor(
                source,
                n=n,
                target_labels=step.output_labels,
                target_dimensions=step.output_dimensions,
                name=node_name,
                tree=tree,
            )
            mirror_relabel_seconds += perf_counter() - mirror_started
            mirror_reuses += 1
            shared_buffer_reuses += int(shared)

        if (
            row_reflection_blocks
            and result.row_reflection_n is None
            and _row_reflection_invariant(
                result_leaves, result.labels, n
            )
        ):
            compression_started = perf_counter()
            result = compress_row_reflection_sector(result, n)
            row_sector_compression_seconds += (
                perf_counter() - compression_started
            )
            row_sector_compressions += 1

        max_rank = max(max_rank, result.rank)
        max_nnz = max(max_nnz, result.column_even_nnz)
        max_stored_nnz = max(max_stored_nnz, result.nnz)
        max_full_nnz = max(max_full_nnz, result.full_nnz)
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
        raise AssertionError("symmetric parity contraction is not scalar")
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
            "streaming_contractions": streaming_contractions,
            "streaming_merge_strategy": streaming_merge_strategy,
            "streaming_generation_seconds": (
                streaming_generation_seconds
            ),
            "streaming_run_write_seconds": (
                streaming_run_write_seconds
            ),
            "streaming_merge_seconds": streaming_merge_seconds,
            "join_preflight_seconds": join_preflight_seconds,
            "in_memory_contraction_seconds": (
                in_memory_contraction_seconds
            ),
            "row_sector_expansion_seconds": (
                row_sector_expansion_seconds
            ),
            "row_sector_compression_seconds": (
                row_sector_compression_seconds
            ),
            "mirror_relabel_seconds": mirror_relabel_seconds,
            "planner_tie_break": planner_tie_break,
            "row_reflection_blocks": row_reflection_blocks,
            "row_sector_compressions": row_sector_compressions,
            "row_sector_expansions": row_sector_expansions,
            "symmetry_multiply_adds": multiply_adds,
            "max_join_pairs": largest_completed_join,
            "max_intermediate_rank": max_rank,
            "max_intermediate_even_sector_nnz": max_nnz,
            "max_intermediate_stored_nnz": max_stored_nnz,
            "max_intermediate_full_nnz": max_full_nnz,
            "max_intermediate_dense_cells": max_dense,
            "max_tensor_bytes": max_tensor_bytes,
            "max_live_unique_array_bytes": max_live_unique_bytes,
            **reducer.statistics.as_dict(),
        },
    )
