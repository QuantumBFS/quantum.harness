"""Exact spatial partitioning and carry-fused column planning."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import prod
from typing import Literal

import opt_einsum as oe

from vqetape.spec import TFIMVQESpec
from vqetape.tn_program import ContractionStep, PathStrategy
from vqetape.tn_template import (
    SlotKind,
    TensorSlot,
    build_mpo_expectation_template,
)

ColumnRole = Literal["first", "bulk", "tail", "last"]


@dataclass(frozen=True)
class SpatialColumnSlot:
    """One site-local tensor needed by a column transition."""

    kind: SlotKind
    layer: int | None
    site_offset: int
    shape: tuple[int, ...]


@dataclass(frozen=True)
class SpatialColumnProgram:
    """One explicit first, bulk, tail, or last contraction program."""

    role: ColumnRole
    width: int
    equation: str
    path: tuple[tuple[int, ...], ...]
    slots: tuple[SpatialColumnSlot, ...]
    input_shapes: tuple[tuple[int, ...], ...]
    carry_is_input: bool
    left_boundary_shape: tuple[int, ...]
    right_boundary_shape: tuple[int, ...]
    flops: int
    largest_intermediate_elements: int
    output_elements: int
    steps: tuple[ContractionStep, ...]


@dataclass(frozen=True)
class SpatialTransferProgram:
    """The reusable blocked programs for one fixed-depth VQE workload."""

    spec: TFIMVQESpec
    strategy: PathStrategy
    first: SpatialColumnProgram
    bulk: SpatialColumnProgram | None
    tail: SpatialColumnProgram | None
    last: SpatialColumnProgram
    block_width: int
    bulk_block_count: int
    tail_width: int
    boundary_shape: tuple[int, ...]
    boundary_dimension: int


def spatial_slot_site(slot: TensorSlot) -> int:
    """Return the physical site that owns a spatially local tensor."""

    if slot.wire is None:
        raise ValueError(f"slot {slot.kind} has no physical location")
    if slot.kind in ("ket_rzz_right", "bra_rzz_right"):
        return slot.wire + 1
    if slot.kind in ("ket_rzz", "bra_rzz"):
        raise ValueError(
            "dense RZZ tensors cannot be spatially partitioned"
        )
    return slot.wire


def _cut_for_index(
    index: int,
    uses: list[tuple[int, int]],
) -> tuple[int, int | None]:
    """Return an index extent and its left cut, if it crosses a cut."""

    sites = sorted({site for site, _ in uses})
    extents = {extent for _, extent in uses}
    if len(extents) != 1:
        raise ValueError(f"inconsistent extent for spatial index {index}")
    extent = extents.pop()
    if len(sites) == 1:
        return extent, None
    if len(sites) != 2 or sites[1] != sites[0] + 1:
        raise ValueError(f"index {index} is not nearest-neighbor local")
    return extent, sites[0]


def _validate_cut_shapes(
    cut_shapes: tuple[tuple[int, ...], ...],
    expected_shape: tuple[int, ...],
) -> None:
    if any(shape != expected_shape for shape in cut_shapes):
        raise ValueError(
            f"inconsistent spatial cut shapes: {cut_shapes}; "
            f"expected {expected_shape}"
        )


def _canonical_pattern(
    operands: tuple[tuple[int, ...], ...],
    output: tuple[int, ...],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    """Remove global symbol identities from a local tensor topology."""

    mapping: dict[int, int] = {}

    def canonical(index: int) -> int:
        if index not in mapping:
            mapping[index] = len(mapping)
        return mapping[index]

    canonical_operands = tuple(
        tuple(canonical(index) for index in operand)
        for operand in operands
    )
    canonical_output = tuple(canonical(index) for index in output)
    return canonical_operands, canonical_output


def _plan_column(
    *,
    role: ColumnRole,
    local_slots: tuple[tuple[TensorSlot, int], ...],
    left_indices: tuple[int, ...],
    right_indices: tuple[int, ...],
    dimensions: dict[int, int],
    strategy: PathStrategy,
    explicit_path: tuple[tuple[int, ...], ...] | None = None,
) -> tuple[SpatialColumnProgram, tuple[object, ...]]:
    carry_is_input = bool(left_indices)
    operand_indices: list[tuple[int, ...]] = []
    input_shapes: list[tuple[int, ...]] = []
    if carry_is_input:
        operand_indices.append(left_indices)
        input_shapes.append(
            tuple(dimensions[index] for index in left_indices)
        )
    for slot, _ in local_slots:
        operand_indices.append(slot.indices)
        input_shapes.append(slot.shape)

    equation = (
        ",".join(
            "".join(oe.get_symbol(index) for index in indices)
            for indices in operand_indices
        )
        + "->"
        + "".join(oe.get_symbol(index) for index in right_indices)
    )
    try:
        path, info = oe.contract_path(
            equation,
            *input_shapes,
            shapes=True,
            optimize=(
                explicit_path
                if explicit_path is not None
                else strategy
            ),
        )
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError(
            f"explicit {role} column path is incompatible"
        ) from exc
    explicit_path = tuple(
        tuple(int(position) for position in item) for item in path
    )
    expression = oe.contract_expression(
        equation,
        *input_shapes,
        optimize=explicit_path,
    )
    symbol_dimensions = {
        oe.get_symbol(index): extent
        for index, extent in dimensions.items()
    }
    steps: list[ContractionStep] = []
    for contraction in expression.contraction_list:
        positions, _, einsum, _, _ = contraction
        output_subscript = einsum.split("->", maxsplit=1)[1]
        step_output_elements = prod(
            symbol_dimensions[symbol] for symbol in output_subscript
        )
        steps.append(
            ContractionStep(
                positions=tuple(
                    int(position) for position in positions
                ),
                einsum=einsum,
                output_subscript=output_subscript,
                output_elements=step_output_elements,
            )
        )

    left_shape = tuple(dimensions[index] for index in left_indices)
    right_shape = tuple(dimensions[index] for index in right_indices)
    column_slots = tuple(
        SpatialColumnSlot(
            slot.kind,
            slot.layer,
            site_offset,
            slot.shape,
        )
        for slot, site_offset in local_slots
    )
    width = (
        max(
            site_offset
            for _, site_offset in local_slots
        )
        + 1
    )
    program = SpatialColumnProgram(
        role=role,
        width=width,
        equation=equation,
        path=explicit_path,
        slots=column_slots,
        input_shapes=tuple(input_shapes),
        carry_is_input=carry_is_input,
        left_boundary_shape=left_shape,
        right_boundary_shape=right_shape,
        flops=int(info.opt_cost),
        largest_intermediate_elements=int(
            info.largest_intermediate
        ),
        output_elements=prod(right_shape),
        steps=tuple(steps),
    )
    signature = (
        tuple(
            (
                slot.kind,
                slot.layer,
                site_offset,
                slot.shape,
            )
            for slot, site_offset in local_slots
        ),
        tuple(input_shapes),
        _canonical_pattern(tuple(operand_indices), right_indices),
    )
    return program, signature


def plan_spatial_transfer(
    spec: TFIMVQESpec,
    strategy: PathStrategy,
    explicit_paths: (
        tuple[tuple[tuple[int, ...], ...], ...] | None
    ) = None,
    *,
    block_width: int = 1,
) -> SpatialTransferProgram:
    """Partition and plan one exact carry-fused blocked recurrence."""

    if strategy not in ("greedy", "random-greedy", "auto-hq"):
        raise ValueError(f"unsupported path strategy: {strategy}")
    if block_width < 1:
        raise ValueError("block_width must be positive")
    interior_count = spec.nqubits - 2
    bulk_block_count, tail_width = divmod(
        interior_count,
        block_width,
    )
    role_ranges: list[tuple[ColumnRole, int, int]] = [
        ("first", 0, 1),
    ]
    if bulk_block_count:
        role_ranges.append(
            ("bulk", 1, 1 + block_width)
        )
    if tail_width:
        tail_start = 1 + bulk_block_count * block_width
        role_ranges.append(
            ("tail", tail_start, tail_start + tail_width)
        )
    role_ranges.append(
        ("last", spec.nqubits - 1, spec.nqubits)
    )
    expected_path_count = len(role_ranges)
    if (
        explicit_paths is not None
        and len(explicit_paths) != expected_path_count
    ):
        raise ValueError(
            f"column paths must contain {expected_path_count} roles"
        )
    template = build_mpo_expectation_template(
        spec,
        gate_representation="operator_schmidt",
    )
    if template.hamiltonian_representation != "mpo":
        raise ValueError("spatial transfer requires an MPO Hamiltonian")

    slots_by_site: dict[int, list[TensorSlot]] = defaultdict(list)
    index_uses: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for slot in template.slots:
        site = spatial_slot_site(slot)
        if site < 0 or site >= spec.nqubits:
            raise ValueError(f"slot {slot.kind} maps outside the chain")
        slots_by_site[site].append(slot)
        for index, extent in zip(
            slot.indices,
            slot.shape,
            strict=True,
        ):
            index_uses[index].append((site, extent))

    cuts: list[list[int]] = [
        [] for _ in range(spec.nqubits - 1)
    ]
    dimensions: dict[int, int] = {}
    for index, uses in index_uses.items():
        extent, cut_site = _cut_for_index(index, uses)
        dimensions[index] = extent
        if cut_site is not None:
            cuts[cut_site].append(index)
    for cut in cuts:
        cut.sort()

    cut_shapes = tuple(
        tuple(dimensions[index] for index in cut) for cut in cuts
    )
    expected_shape = (2,) * (2 * spec.depth) + (3,)
    _validate_cut_shapes(cut_shapes, expected_shape)

    columns: dict[ColumnRole, SpatialColumnProgram] = {}
    signatures: dict[ColumnRole, tuple[object, ...]] = {}
    for path_index, (role, start, stop) in enumerate(
        role_ranges
    ):
        left_indices = (
            tuple(cuts[start - 1]) if start > 0 else ()
        )
        right_indices = (
            tuple(cuts[stop - 1])
            if stop < spec.nqubits
            else ()
        )
        local_slots = tuple(
            (slot, site - start)
            for site in range(start, stop)
            for slot in slots_by_site[site]
        )
        column, signature = _plan_column(
            role=role,
            local_slots=local_slots,
            left_indices=left_indices,
            right_indices=right_indices,
            dimensions=dimensions,
            strategy=strategy,
            explicit_path=(
                None
                if explicit_paths is None
                else explicit_paths[path_index]
            ),
        )
        columns[role] = column
        signatures[role] = signature

    if bulk_block_count > 1:
        bulk = columns["bulk"]
        for block_index in range(1, bulk_block_count):
            start = 1 + block_index * block_width
            stop = start + block_width
            local_slots = tuple(
                (slot, site - start)
                for site in range(start, stop)
                for slot in slots_by_site[site]
            )
            _, signature = _plan_column(
                role="bulk",
                local_slots=local_slots,
                left_indices=tuple(cuts[start - 1]),
                right_indices=tuple(cuts[stop - 1]),
                dimensions=dimensions,
                strategy=strategy,
                explicit_path=bulk.path,
            )
            if signature != signatures["bulk"]:
                raise ValueError(
                    "bulk block topology is not canonical"
                )

    return SpatialTransferProgram(
        spec=spec,
        strategy=strategy,
        first=columns["first"],
        bulk=columns.get("bulk"),
        tail=columns.get("tail"),
        last=columns["last"],
        block_width=block_width,
        bulk_block_count=bulk_block_count,
        tail_width=tail_width,
        boundary_shape=expected_shape,
        boundary_dimension=prod(expected_shape),
    )
