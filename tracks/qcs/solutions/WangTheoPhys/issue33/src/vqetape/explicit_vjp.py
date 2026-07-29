"""Explicit reverse programs for serialized tensor contractions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import jax
import jax.numpy as jnp
from jax import Array

from vqetape.ad_analysis import (
    analyze_contraction_steps,
    reverse_einsum_equation,
)
from vqetape.tn_program import ContractionStep

ExplicitContraction = Callable[..., Array]


@dataclass(frozen=True)
class _ForwardRecord:
    output_node_id: int
    selected_node_ids: tuple[int, ...]
    selected_values: tuple[Array, ...]
    equation: str


def build_explicit_contraction_vjp(
    input_shapes: tuple[tuple[int, ...], ...],
    steps: tuple[ContractionStep, ...],
) -> ExplicitContraction:
    """Return a custom-VJP executor for a serialized contraction.

    The forward residual contains only the original leaves. Backward
    reconstructs every intermediate and then executes the algebraic
    transpose einsums in reverse tree order.
    """

    normalized_shapes = tuple(
        tuple(int(extent) for extent in shape)
        for shape in input_shapes
    )
    analyze_contraction_steps(normalized_shapes, steps)
    leaf_count = len(normalized_shapes)

    def execute(
        leaves: tuple[Array, ...],
    ) -> tuple[Array, tuple[_ForwardRecord, ...], int]:
        if len(leaves) != leaf_count:
            raise ValueError(
                f"expected {leaf_count} contraction inputs, "
                f"got {len(leaves)}"
            )
        for index, (value, expected) in enumerate(
            zip(leaves, normalized_shapes, strict=True)
        ):
            if tuple(value.shape) != expected:
                raise ValueError(
                    f"input {index} shape must be {expected}, "
                    f"got {tuple(value.shape)}"
                )

        active: list[tuple[int, Array]] = list(
            enumerate(leaves)
        )
        records: list[_ForwardRecord] = []
        next_node_id = leaf_count
        for step in steps:
            try:
                selected = tuple(
                    active.pop(position)
                    for position in step.positions
                )
            except IndexError as exc:
                raise ValueError(
                    "contraction step position is out of range"
                ) from exc
            selected_node_ids = tuple(
                node_id for node_id, _ in selected
            )
            selected_values = tuple(
                value for _, value in selected
            )
            result = jnp.einsum(
                step.einsum,
                *selected_values,
                optimize=True,
            )
            records.append(
                _ForwardRecord(
                    output_node_id=next_node_id,
                    selected_node_ids=selected_node_ids,
                    selected_values=selected_values,
                    equation=step.einsum,
                )
            )
            active.append((next_node_id, result))
            next_node_id += 1

        if len(active) != 1:
            raise RuntimeError(
                "contraction did not produce one output"
            )
        root_node_id, output = active[0]
        return output, tuple(records), root_node_id

    @jax.custom_vjp
    def contraction(*leaves: Array) -> Array:
        output, _, _ = execute(tuple(leaves))
        return output

    def contraction_fwd(
        *leaves: Array,
    ) -> tuple[Array, tuple[Array, ...]]:
        leaf_tuple = tuple(leaves)
        output, _, _ = execute(leaf_tuple)
        return output, leaf_tuple

    def contraction_bwd(
        leaves: tuple[Array, ...],
        output_cotangent: Array,
    ) -> tuple[Array, ...]:
        _, records, root_node_id = execute(leaves)
        cotangents: dict[int, Array] = {
            root_node_id: output_cotangent
        }

        for record in reversed(records):
            result_cotangent = cotangents.pop(
                record.output_node_id
            )
            for input_index, node_id in enumerate(
                record.selected_node_ids
            ):
                equation = reverse_einsum_equation(
                    record.equation,
                    input_index,
                )
                reverse_inputs = (
                    result_cotangent,
                    *(
                        value
                        for index, value in enumerate(
                            record.selected_values
                        )
                        if index != input_index
                    ),
                )
                # JAX's complex VJP uses the algebraic transpose of a
                # holomorphic einsum. Conjugating the other operands
                # would implement a Hermitian adjoint and disagree with
                # jax.vjp for complex cotangents.
                input_cotangent = jnp.einsum(
                    equation,
                    *reverse_inputs,
                    optimize=True,
                )
                if node_id in cotangents:
                    input_cotangent = (
                        cotangents[node_id]
                        + input_cotangent
                    )
                cotangents[node_id] = input_cotangent

        return tuple(
            cotangents.get(
                leaf_id,
                jnp.zeros_like(leaves[leaf_id]),
            )
            for leaf_id in range(leaf_count)
        )

    contraction.defvjp(
        contraction_fwd,
        contraction_bwd,
    )
    return contraction
