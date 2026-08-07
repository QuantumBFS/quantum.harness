from math import prod

import pytest

from vqetape.spatial_plan import (
    _cut_for_index,
    _validate_cut_shapes,
    plan_spatial_transfer,
    spatial_slot_site,
)
from vqetape.spec import TFIMVQESpec
from vqetape.tn_template import (
    TensorSlot,
    build_mpo_expectation_template,
)


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_spatial_partition_has_exact_boundary_dimension(depth):
    spec = TFIMVQESpec(nqubits=4, depth=depth)
    program = plan_spatial_transfer(spec, "greedy")
    expected_shape = (2,) * (2 * depth) + (3,)

    assert program.boundary_shape == expected_shape
    assert program.boundary_dimension == 3 * 4**depth
    assert prod(program.boundary_shape) == program.boundary_dimension
    assert program.first.right_boundary_shape == expected_shape
    assert program.last.left_boundary_shape == expected_shape
    assert program.bulk is not None
    assert program.bulk.left_boundary_shape == expected_shape
    assert program.bulk.right_boundary_shape == expected_shape
    assert program.first.output_elements == program.boundary_dimension
    assert program.bulk.output_elements == program.boundary_dimension
    assert program.last.output_elements == 1
    assert all(
        step.output_elements < program.boundary_dimension**2
        for step in program.bulk.steps
    )


def test_rzz_factor_ownership_uses_physical_site():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    template = build_mpo_expectation_template(
        spec,
        gate_representation="operator_schmidt",
    )
    left = next(
        slot for slot in template.slots if slot.kind == "ket_rzz_left"
    )
    right = next(
        slot for slot in template.slots if slot.kind == "ket_rzz_right"
    )

    assert spatial_slot_site(left) == left.wire
    assert spatial_slot_site(right) == right.wire + 1


def test_two_qubit_program_has_no_bulk_column():
    program = plan_spatial_transfer(
        TFIMVQESpec(nqubits=2, depth=2),
        "greedy",
    )
    assert program.bulk is None


def test_bulk_columns_have_one_canonical_program():
    program = plan_spatial_transfer(
        TFIMVQESpec(nqubits=6, depth=2),
        "greedy",
    )
    assert program.bulk is not None
    assert program.bulk.carry_is_input
    assert program.first.carry_is_input is False
    assert program.last.carry_is_input


@pytest.mark.parametrize(
    ("nqubits", "block_width", "full_blocks", "tail_width"),
    [
        (8, 1, 6, 0),
        (8, 2, 3, 0),
        (8, 4, 1, 2),
        (5, 3, 1, 0),
        (4, 3, 0, 2),
    ],
)
def test_blocked_spatial_plan_partitions_interior(
    nqubits,
    block_width,
    full_blocks,
    tail_width,
):
    program = plan_spatial_transfer(
        TFIMVQESpec(nqubits=nqubits, depth=1),
        "greedy",
        block_width=block_width,
    )

    assert program.block_width == block_width
    assert program.bulk_block_count == full_blocks
    assert program.tail_width == tail_width
    assert (program.bulk.width if program.bulk else 0) == (
        block_width if full_blocks else 0
    )
    assert (program.tail.width if program.tail else 0) == tail_width


def test_block_program_keeps_only_external_boundary():
    program = plan_spatial_transfer(
        TFIMVQESpec(nqubits=8, depth=2),
        "greedy",
        block_width=3,
    )

    assert program.bulk is not None
    assert program.bulk.left_boundary_shape == program.boundary_shape
    assert program.bulk.right_boundary_shape == program.boundary_shape
    assert program.bulk.output_elements == program.boundary_dimension
    assert all(
        step.output_elements < program.boundary_dimension**2
        for step in program.bulk.steps
    )


def test_block_slots_record_site_offsets():
    program = plan_spatial_transfer(
        TFIMVQESpec(nqubits=6, depth=1),
        "greedy",
        block_width=2,
    )

    assert program.bulk is not None
    assert {slot.site_offset for slot in program.bulk.slots} == {0, 1}


def test_explicit_column_paths_are_reused():
    spec = TFIMVQESpec(nqubits=4, depth=1)
    planned = plan_spatial_transfer(spec, "greedy")
    paths = (
        planned.first.path,
        planned.bulk.path,
        planned.last.path,
    )
    reused = plan_spatial_transfer(
        spec,
        "greedy",
        explicit_paths=paths,
    )

    assert reused.first.path == planned.first.path
    assert reused.bulk is not None
    assert planned.bulk is not None
    assert reused.bulk.path == planned.bulk.path
    assert reused.last.path == planned.last.path


def test_explicit_column_paths_require_role_count():
    with pytest.raises(ValueError, match="column paths"):
        plan_spatial_transfer(
            TFIMVQESpec(nqubits=4, depth=1),
            "greedy",
            explicit_paths=(((0, 1),),),
        )


def test_dense_rzz_slot_has_no_spatial_owner():
    slot = TensorSlot(
        "ket_rzz",
        (0, 1, 2, 3),
        (2, 2, 2, 2),
        layer=0,
        wire=0,
    )
    with pytest.raises(ValueError, match="dense RZZ"):
        spatial_slot_site(slot)


def test_spatial_cut_rejects_nonlocal_index():
    with pytest.raises(ValueError, match="nearest-neighbor"):
        _cut_for_index(7, [(0, 2), (2, 2)])


def test_spatial_cut_rejects_inconsistent_extent():
    with pytest.raises(ValueError, match="inconsistent extent"):
        _cut_for_index(7, [(0, 2), (1, 3)])


def test_spatial_cut_rejects_inconsistent_shapes():
    with pytest.raises(ValueError, match="cut shapes"):
        _validate_cut_shapes(((2, 2, 3), (2, 3)), (2, 2, 3))
