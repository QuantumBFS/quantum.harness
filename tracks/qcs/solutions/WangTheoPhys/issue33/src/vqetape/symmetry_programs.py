"""Charge-native sparse contractions for exact Z2 spatial sectors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np
import opt_einsum as oe
from jax import Array
from jax.experimental import sparse

from vqetape.spatial_plan import SpatialColumnProgram
from vqetape.symmetry import Z2BoundarySector

Z2NativeExecutor = Callable[
    [Array | None, tuple[Array, ...]],
    Array,
]


@dataclass(frozen=True)
class Z2NativeContraction:
    """One sparse-boundary contraction and its serialized path."""

    role: str
    equation: str
    path: tuple[tuple[int, ...], ...]
    input_boundary_is_sparse: bool
    output_boundary_is_compressed: bool
    executor: Z2NativeExecutor


def _boundary_coordinates(
    sector: Z2BoundarySector,
) -> np.ndarray:
    positions = np.asarray(
        sector.active_positions,
        dtype=np.int32,
    )
    return np.stack(
        np.unravel_index(
            positions,
            sector.dense_shape,
        ),
        axis=1,
    ).astype(np.int32)


def _unique_output_symbol(equation: str) -> str:
    index = 0
    while True:
        symbol = oe.get_symbol(index)
        if symbol not in equation:
            return symbol
        index += 1


def build_z2_native_contraction(
    program: SpatialColumnProgram,
    sector: Z2BoundarySector,
    *,
    dtype,
    strategy: str = "greedy",
) -> Z2NativeContraction:
    """Build a sparse-input/direct-compressed-output contraction."""

    if (
        program.carry_is_input
        and program.left_boundary_shape
        != sector.dense_shape
    ):
        raise ValueError(
            "native input boundary does not match Z2 sector"
        )
    has_boundary_output = bool(program.right_boundary_shape)
    if (
        has_boundary_output
        and program.right_boundary_shape
        != sector.dense_shape
    ):
        raise ValueError(
            "native output boundary does not match Z2 sector"
        )

    left, output = program.equation.split(
        "->",
        maxsplit=1,
    )
    equation = program.equation
    input_shapes = list(program.input_shapes)
    selector = None
    coordinates = _boundary_coordinates(sector)
    coordinate_array = jnp.asarray(
        coordinates,
        dtype=jnp.int32,
    )
    if has_boundary_output:
        compressed_symbol = _unique_output_symbol(
            program.equation
        )
        selector_subscript = (
            output + compressed_symbol
        )
        equation = (
            left
            + ","
            + selector_subscript
            + "->"
            + compressed_symbol
        )
        selector_coordinates = np.concatenate(
            (
                coordinates,
                np.arange(
                    sector.active_count,
                    dtype=np.int32,
                )[:, None],
            ),
            axis=1,
        )
        selector_shape = (
            *sector.dense_shape,
            sector.active_count,
        )
        selector = sparse.BCOO(
            (
                jnp.ones(
                    (sector.active_count,),
                    dtype=dtype,
                ),
                jnp.asarray(
                    selector_coordinates,
                    dtype=jnp.int32,
                ),
            ),
            shape=selector_shape,
            indices_sorted=True,
            unique_indices=True,
        )
        input_shapes.append(selector_shape)

    path, _ = oe.contract_path(
        equation,
        *input_shapes,
        shapes=True,
        optimize=strategy,
    )
    serialized_path = tuple(
        tuple(int(position) for position in step)
        for step in path
    )

    def dense_equation(*operands):
        return jnp.einsum(
            equation,
            *operands,
            optimize=serialized_path,
        )

    sparse_equation = sparse.sparsify(dense_equation)

    def execute(
        carry: Array | None,
        tensors: tuple[Array, ...],
    ) -> Array:
        expected_tensor_count = len(program.input_shapes) - (
            1 if program.carry_is_input else 0
        )
        if len(tensors) != expected_tensor_count:
            raise ValueError(
                "tensor count does not match native spatial role"
            )
        operands: list[object] = []
        if program.carry_is_input:
            if carry is None:
                raise ValueError(
                    "native spatial role requires compressed carry"
                )
            expected = (sector.active_count,)
            if tuple(carry.shape) != expected:
                raise ValueError(
                    f"compressed carry shape must be {expected}"
                )
            operands.append(
                sparse.BCOO(
                    (carry, coordinate_array),
                    shape=sector.dense_shape,
                    indices_sorted=True,
                    unique_indices=True,
                )
            )
        elif carry is not None:
            raise ValueError(
                "native first role does not accept a carry"
            )
        operands.extend(tensors)
        if selector is not None:
            operands.append(selector)
        return sparse_equation(*operands)

    return Z2NativeContraction(
        role=program.role,
        equation=equation,
        path=serialized_path,
        input_boundary_is_sparse=program.carry_is_input,
        output_boundary_is_compressed=has_boundary_output,
        executor=execute,
    )
