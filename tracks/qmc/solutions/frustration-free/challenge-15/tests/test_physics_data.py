from __future__ import annotations

from math import comb, factorial, pi, sqrt
from pathlib import Path

import numpy as np
import pytest
from scipy.special import eval_legendre, lpmv

from challenge15.physics_data import (
    CANONICAL_SECTORS,
    orbital_table,
    pair_channel_indices,
)
from challenge15.projection_data import (
    ProjectionBlock,
    ProjectionGrid,
    StaticProjectionBlocks,
    coordinate_euler_substitutions,
    wigner_d_m0,
)
from challenge15.spec import SphereSpec


SOURCE_ROOT = Path(__file__).parents[1] / "src" / "challenge15"


def _assert_immutable_bytes_backing(array: np.ndarray) -> None:
    assert not array.flags.writeable
    with pytest.raises(ValueError):
        array.setflags(write=True)


@pytest.mark.parametrize("particles", range(2, 9))
def test_orbital_and_channel_tables_equal_existing_definitions(particles):
    spec = SphereSpec(particles)
    table = orbital_table(spec)
    expected_u = np.asarray(
        [(spec.two_q + two_m) // 2 for two_m in spec.two_m_values],
        dtype=np.int64,
    )
    expected_normalizations = np.asarray(
        [
            sqrt(
                (spec.two_q + 1)
                / (4.0 * pi)
                * comb(spec.two_q, int(power_u))
            )
            for power_u in expected_u
        ],
        dtype=np.complex128,
    )

    assert table.normalizations.dtype == np.complex128
    assert table.u_powers.dtype == np.int64
    assert table.v_powers.dtype == np.int64
    np.testing.assert_array_equal(table.normalizations, expected_normalizations)
    np.testing.assert_array_equal(table.u_powers, expected_u)
    np.testing.assert_array_equal(table.v_powers, spec.two_q - expected_u)

    positive, negative = pair_channel_indices(spec)
    assert positive.dtype == np.int64
    assert negative.dtype == np.int64
    np.testing.assert_array_equal(
        np.asarray(spec.two_m_values)[positive],
        -np.asarray(spec.two_m_values)[negative],
    )
    for value in (
        table.normalizations,
        table.u_powers,
        table.v_powers,
        positive,
        negative,
    ):
        _assert_immutable_bytes_backing(value)


def test_canonical_sectors_are_exact_and_immutable():
    assert CANONICAL_SECTORS == (0, 2)
    assert isinstance(CANONICAL_SECTORS, tuple)


@pytest.mark.parametrize("particles", range(2, 9))
@pytest.mark.parametrize("target_l", (0, 2))
def test_projection_data_preserves_exact_rules_and_immutable_blocks(
    particles, target_l
):
    spec = SphereSpec(particles)
    grid = ProjectionGrid.exact(spec, target_l)
    assert grid.n_alpha == 2 * spec.l_max + 1
    assert grid.n_beta == (spec.l_max + target_l + 2) // 2
    for array, dtype in (
        (grid.alpha_nodes, np.float64),
        (grid.alpha_weights, np.complex128),
        (grid.beta_nodes, np.float64),
        (grid.beta_weights, np.complex128),
    ):
        assert array.dtype == dtype
        _assert_immutable_bytes_backing(array)

    block = next(grid.iter_blocks(5))
    assert isinstance(block, ProjectionBlock)
    for array, dtype in (
        (block.alpha_indices, np.int64),
        (block.beta_indices, np.int64),
        (block.alpha_nodes, np.float64),
        (block.beta_nodes, np.float64),
        (block.weights, np.complex128),
    ):
        assert array.dtype == dtype
        _assert_immutable_bytes_backing(array)

    static = grid.static_blocks(5)
    assert isinstance(static, StaticProjectionBlocks)
    for array in (
        static.alpha_nodes,
        static.beta_nodes,
        static.weights,
        static.node_valid,
        static.tree_valid,
    ):
        _assert_immutable_bytes_backing(array)


def test_projection_helpers_preserve_existing_formulas():
    alpha = np.asarray([0.0, 0.3, 1.7], dtype=np.float64)
    beta_nodes = np.asarray([-0.8, 0.1, 1.0], dtype=np.float64)
    rotations = coordinate_euler_substitutions(alpha, beta_nodes)
    beta = np.arccos(beta_nodes)
    expected = np.empty((3, 2, 2), dtype=np.complex128)
    expected[:, 0, 0] = np.cos(beta / 2) * np.exp(-0.5j * alpha)
    expected[:, 0, 1] = np.sin(beta / 2) * np.exp(0.5j * alpha)
    expected[:, 1, 0] = -np.sin(beta / 2) * np.exp(-0.5j * alpha)
    expected[:, 1, 1] = np.cos(beta / 2) * np.exp(0.5j * alpha)
    np.testing.assert_array_equal(rotations, expected)
    assert rotations.dtype == np.complex128
    _assert_immutable_bytes_backing(rotations)

    for target_l in range(5):
        for m in range(-target_l, target_l + 1):
            actual = wigner_d_m0(target_l, m, beta_nodes)
            if m == 0:
                expected_d = eval_legendre(target_l, beta_nodes)
            else:
                magnitude = abs(m)
                expected_d = sqrt(
                    factorial(target_l - magnitude)
                    / factorial(target_l + magnitude)
                ) * lpmv(magnitude, target_l, beta_nodes)
                if m < 0:
                    expected_d = (-1) ** magnitude * expected_d
            np.testing.assert_array_equal(
                actual, np.asarray(expected_d, dtype=np.float64)
            )
            assert actual.dtype == np.float64
            _assert_immutable_bytes_backing(actual)


def test_projector_reexports_moved_projection_data_interfaces():
    from challenge15 import projector

    assert projector.ProjectionBlock is ProjectionBlock
    assert projector.StaticProjectionBlocks is StaticProjectionBlocks
    assert projector.ProjectionGrid is ProjectionGrid
    assert (
        projector.coordinate_euler_substitutions
        is coordinate_euler_substitutions
    )
    assert projector.wigner_d_m0 is wigner_d_m0


def test_backend_neutral_modules_do_not_import_tensor_frameworks():
    for filename in ("physics_data.py", "projection_data.py"):
        text = (SOURCE_ROOT / filename).read_text()
        for framework in ("jax", "torch", "flax", "optax"):
            assert f"import {framework}" not in text
            assert f"from {framework}" not in text
