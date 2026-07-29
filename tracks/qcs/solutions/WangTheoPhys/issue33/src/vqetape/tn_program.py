"""Contraction-path planning and explicit JAX execution."""

from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Literal

import jax
import jax.numpy as jnp
import opt_einsum as oe
from jax import Array

from vqetape.spec import dtype_bytes
from vqetape.tape import name_residual
from vqetape.tn_template import TensorNetworkTemplate

PathStrategy = Literal["greedy", "random-greedy", "auto-hq"]


@dataclass(frozen=True)
class ContractionStep:
    positions: tuple[int, ...]
    einsum: str
    output_subscript: str
    output_elements: int


@dataclass(frozen=True)
class ContractionTreeNode:
    node_id: int
    leaf_index: int | None
    step_index: int | None
    einsum: str | None
    children: tuple[ContractionTreeNode, ...]
    leaf_indices: tuple[int, ...]
    output_elements: int

    @property
    def is_leaf(self) -> bool:
        return self.leaf_index is not None


@dataclass(frozen=True)
class ContractionProgram:
    template: TensorNetworkTemplate
    strategy: PathStrategy
    path: tuple[tuple[int, ...], ...]
    steps: tuple[ContractionStep, ...]
    tensor_count: int
    input_tensor_elements: int
    flops: int
    largest_intermediate_elements: int
    step_output_bytes: tuple[int, ...]
    root: ContractionTreeNode


def _symbol_dimensions(template: TensorNetworkTemplate) -> dict[str, int]:
    dimensions: dict[str, int] = {}
    for slot in template.slots:
        for index, extent in zip(slot.indices, slot.shape, strict=True):
            symbol = oe.get_symbol(index)
            previous = dimensions.setdefault(symbol, extent)
            if previous != extent:
                raise ValueError(f"inconsistent extent for index {index}")
    return dimensions


def plan_contraction(
    template: TensorNetworkTemplate,
    strategy: PathStrategy,
    explicit_path: tuple[tuple[int, ...], ...] | None = None,
) -> ContractionProgram:
    """Search a path and retain its explicit opt_einsum contraction steps."""

    if strategy not in ("greedy", "random-greedy", "auto-hq"):
        raise ValueError(f"unsupported path strategy: {strategy}")
    if explicit_path is not None:
        operand_count = len(template.slots)
        for positions in explicit_path:
            if len(positions) < 2 or any(
                position < 0 or position >= operand_count
                for position in positions
            ):
                raise ValueError(
                    "explicit contraction path is incompatible with "
                    "the selected tensor topology"
                )
            operand_count -= len(positions) - 1
        if operand_count != 1:
            raise ValueError(
                "explicit contraction path is incompatible with "
                "the selected tensor topology"
            )
    try:
        path, info = oe.contract_path(
            template.equation,
            *template.shapes,
            shapes=True,
            optimize=explicit_path if explicit_path is not None else strategy,
        )
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError(
            "explicit contraction path is incompatible with "
            "the selected tensor topology"
        ) from exc
    explicit_path = tuple(tuple(int(position) for position in item) for item in path)
    expression = oe.contract_expression(
        template.equation,
        *template.shapes,
        optimize=explicit_path,
    )
    dimensions = _symbol_dimensions(template)
    steps: list[ContractionStep] = []
    active_nodes = [
        ContractionTreeNode(
            node_id=index,
            leaf_index=index,
            step_index=None,
            einsum=None,
            children=(),
            leaf_indices=(index,),
            output_elements=prod(template.shapes[index]),
        )
        for index in range(len(template.slots))
    ]
    next_node_id = len(active_nodes)
    for contraction in expression.contraction_list:
        positions, _, einsum, _, _ = contraction
        output_subscript = einsum.split("->", maxsplit=1)[1]
        output_elements = prod(dimensions[symbol] for symbol in output_subscript)
        steps.append(
            ContractionStep(
                positions=tuple(int(position) for position in positions),
                einsum=einsum,
                output_subscript=output_subscript,
                output_elements=output_elements,
            )
        )
        selected_nodes = [
            active_nodes.pop(int(position)) for position in positions
        ]
        leaf_indices = tuple(
            sorted(
                leaf_index
                for node in selected_nodes
                for leaf_index in node.leaf_indices
            )
        )
        active_nodes.append(
            ContractionTreeNode(
                node_id=next_node_id,
                leaf_index=None,
                step_index=len(steps) - 1,
                einsum=einsum,
                children=tuple(selected_nodes),
                leaf_indices=leaf_indices,
                output_elements=output_elements,
            )
        )
        next_node_id += 1
    if len(active_nodes) != 1:
        raise RuntimeError("path did not produce one contraction-tree root")
    scalar_bytes = dtype_bytes(template.spec.dtype)
    return ContractionProgram(
        template=template,
        strategy=strategy,
        path=explicit_path,
        steps=tuple(steps),
        tensor_count=len(template.slots),
        input_tensor_elements=sum(prod(shape) for shape in template.shapes),
        flops=int(info.opt_cost),
        largest_intermediate_elements=int(info.largest_intermediate),
        step_output_bytes=tuple(
            step.output_elements * scalar_bytes for step in steps
        ),
        root=active_nodes[0],
    )


def execute_contraction(
    program: ContractionProgram,
    tensors: tuple[Array, ...],
    remat_steps: frozenset[int] = frozenset(),
    *,
    name_residuals: bool = False,
) -> Array:
    """Execute an opt_einsum contraction list with optional step remat."""

    if len(tensors) != len(program.template.slots):
        raise ValueError("tensor count does not match contraction template")
    if any(
        step < 0 or step >= len(program.steps) for step in remat_steps
    ):
        raise ValueError("remat step index is out of range")

    operands = list(tensors)
    for step_index, step in enumerate(program.steps):
        selected = [operands.pop(position) for position in step.positions]

        def contract_step(*values: Array, equation: str = step.einsum) -> Array:
            return jnp.einsum(equation, *values, optimize=True)

        if step_index in remat_steps:
            contracted = jax.checkpoint(contract_step)(*selected)
        else:
            contracted = contract_step(*selected)
        if name_residuals:
            contracted = name_residual(
                contracted,
                f"contract:{step_index}:elements{step.output_elements}",
            )
        operands.append(contracted)
    if len(operands) != 1:
        raise RuntimeError("contraction program did not produce one output")
    return operands[0]


def subtree_nodes_at_depth(
    program: ContractionProgram,
    depth: int,
) -> tuple[ContractionTreeNode, ...]:
    """Return internal nodes on a root-relative antichain."""

    if depth < 0:
        raise ValueError("depth must be nonnegative")
    frontier = (program.root,)
    for _ in range(depth):
        next_frontier = tuple(
            child
            for node in frontier
            if not node.is_leaf
            for child in node.children
        )
        frontier = next_frontier
        if not frontier:
            break
    return tuple(node for node in frontier if not node.is_leaf)


def execute_tree_contraction(
    program: ContractionProgram,
    tensors: tuple[Array, ...],
    checkpoint_node_ids: frozenset[int],
) -> Array:
    """Execute the contraction tree with checkpointed subtree frontiers."""

    if len(tensors) != len(program.template.slots):
        raise ValueError("tensor count does not match contraction template")

    def evaluate_plain(
        node: ContractionTreeNode,
        leaf_values: dict[int, Array],
    ) -> Array:
        if node.is_leaf:
            assert node.leaf_index is not None
            return leaf_values[node.leaf_index]
        assert node.einsum is not None
        values = tuple(
            evaluate_plain(child, leaf_values) for child in node.children
        )
        return jnp.einsum(node.einsum, *values, optimize=True)

    def evaluate(node: ContractionTreeNode) -> Array:
        if node.is_leaf:
            assert node.leaf_index is not None
            return tensors[node.leaf_index]
        if node.node_id in checkpoint_node_ids:
            leaf_indices = node.leaf_indices

            def evaluate_subtree(*values: Array) -> Array:
                leaf_values = dict(zip(leaf_indices, values, strict=True))
                return evaluate_plain(node, leaf_values)

            return jax.checkpoint(evaluate_subtree)(
                *(tensors[index] for index in leaf_indices)
            )
        assert node.einsum is not None
        values = tuple(evaluate(child) for child in node.children)
        return jnp.einsum(node.einsum, *values, optimize=True)

    return evaluate(program.root)
