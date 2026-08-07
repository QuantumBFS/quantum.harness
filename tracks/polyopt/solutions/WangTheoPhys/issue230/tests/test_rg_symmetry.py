import numpy as np
import pytest

from xxzcert.rg_relaxation import (
    alternating_neel_mps,
    dimer_cat_mps,
    optimize_u1_uniform_mps,
    uniform_mps_energy,
)
from xxzcert.rg_dual_barrier import (
    _strictly_interior_start,
    build_rg_dual_barrier_model,
    rg_barrier_hessian_product,
    rg_barrier_value_gradient,
)
from xxzcert.rg_symmetry import (
    ChargeBasis,
    assemble_charge_blocks,
    infer_virtual_charges,
    mps_rg_charge_bases,
    split_charge_blocks,
    u1_tensor_mask,
)


@pytest.mark.parametrize(
    ("tensor", "expected"),
    [
        (alternating_neel_mps(), (0, 1)),
        (dimer_cat_mps(), (0, 1, -1)),
    ],
)
def test_virtual_charges_are_inferred_from_tensor_selection_rules(
    tensor, expected
):
    assert infer_virtual_charges(tensor) == expected


def test_charge_block_round_trip_and_spectrum():
    basis = ChargeBasis.from_labels((2, 0, 0, -2))
    matrix = np.array(
        [
            [3.0, 0.0, 0.0, 0.0],
            [0.0, 2.0, 0.25, 0.0],
            [0.0, 0.25, 1.0, 0.0],
            [0.0, 0.0, 0.0, 4.0],
        ]
    )
    blocks = split_charge_blocks(matrix, basis)
    rebuilt = assemble_charge_blocks(blocks, basis)
    assert np.array_equal(rebuilt, matrix)
    block_spectrum = np.sort(
        np.concatenate([np.linalg.eigvalsh(block) for block in blocks])
    )
    assert np.allclose(block_spectrum, np.linalg.eigvalsh(matrix))
    assert basis.block_sizes == (1, 2, 1)


def test_cross_sector_entries_are_rejected():
    basis = ChargeBasis.from_labels((1, -1))
    with pytest.raises(ValueError, match="cross-sector"):
        split_charge_blocks(np.array([[1.0, 1e-3], [1e-3, 2.0]]), basis)


@pytest.mark.parametrize("tensor", [alternating_neel_mps(), dimer_cat_mps()])
def test_rg_charge_bases_cover_every_solver_space(tensor):
    bases = mps_rg_charge_bases(tensor)
    bond = tensor.shape[0]
    assert bases.local.size == 4
    assert bases.equality.size == 2 * bond * bond
    assert bases.omega.size == 4 * bond * bond
    assert sum(bases.equality.block_sizes) == bases.equality.size
    assert sum(bases.omega.block_sizes) == bases.omega.size


def test_tensor_violating_u1_selection_rule_is_rejected():
    tensor = alternating_neel_mps()
    tensor[0, 1, 1] = 0.1
    with pytest.raises(ValueError, match="inconsistent"):
        infer_virtual_charges(tensor)


def test_u1_tensor_mask_uses_declared_selection_rule():
    mask = u1_tensor_mask((-1, 0, 0, 1))
    assert mask.shape == (4, 2, 4)
    assert int(mask.sum()) == 8
    tensor = mask.astype(np.complex128)
    assert infer_virtual_charges(tensor) == (0, 1, 1, 2)


def test_u1_mps_optimizer_preserves_charge_and_beats_neel():
    tensor = optimize_u1_uniform_mps(
        1.0, (-1, 0, 0, 1), restarts=1, seed=230, max_iterations=30
    )
    assert infer_virtual_charges(tensor) == (0, 1, 1, 2)
    assert uniform_mps_energy(tensor, 1.0) < -0.25


def test_blocked_and_dense_barrier_evaluations_agree():
    tensor = alternating_neel_mps()
    blocked = build_rg_dual_barrier_model(
        1.0, tensor, depth=5, use_symmetry=True
    )
    dense = build_rg_dual_barrier_model(
        1.0, tensor, depth=5, use_symmetry=False
    )
    blocked_parameters = _strictly_interior_start(blocked)
    start_y, start_matrices = blocked.unpack(blocked_parameters)
    dense_parameters = dense.pack(start_y, start_matrices)
    direction_seed = np.linspace(-1e-4, 1e-4, dense.parameter_count)
    # Keep the comparison direction inside the invariant charge subspace by
    # projecting every dual matrix through the detected sector blocks.
    y, matrices = dense.unpack(direction_seed)
    bases = (
        blocked.charge_bases.local,
        blocked.charge_bases.first,
        blocked.charge_bases.second,
        blocked.charge_bases.first,
        blocked.charge_bases.second,
    )
    projected = []
    for matrix, basis in zip(matrices, bases, strict=True):
        matrix = matrix * np.equal.outer(basis.labels, basis.labels)
        projected.append(
            assemble_charge_blocks(split_charge_blocks(matrix, basis), basis)
        )
    blocked_direction = blocked.pack(y, tuple(projected))
    dense_direction = dense.pack(y, tuple(projected))
    blocked_value, blocked_gradient, _ = rg_barrier_value_gradient(
        blocked, blocked_parameters, 1e-2
    )
    dense_value, dense_gradient, _ = rg_barrier_value_gradient(
        dense, dense_parameters, 1e-2
    )
    assert blocked_value == pytest.approx(dense_value, abs=1e-10)
    assert blocked.parameter_count < dense.parameter_count
    assert blocked_gradient @ blocked_direction == pytest.approx(
        dense_gradient @ dense_direction, abs=1e-10
    )
    step = 1e-6
    forward = rg_barrier_value_gradient(
        blocked,
        blocked_parameters + step * blocked_direction,
        1e-2,
    )[0]
    backward = rg_barrier_value_gradient(
        blocked,
        blocked_parameters - step * blocked_direction,
        1e-2,
    )[0]
    assert (forward - backward) / (2 * step) == pytest.approx(
        blocked_gradient @ blocked_direction, rel=2e-6, abs=1e-8
    )
    blocked_hessian = rg_barrier_hessian_product(
        blocked, blocked_parameters, blocked_direction, 1e-2
    )
    dense_hessian = rg_barrier_hessian_product(
        dense, dense_parameters, dense_direction, 1e-2
    )
    assert blocked_direction @ blocked_hessian == pytest.approx(
        dense_direction @ dense_hessian, abs=1e-9
    )
