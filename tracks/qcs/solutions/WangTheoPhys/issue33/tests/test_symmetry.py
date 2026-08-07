import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.spatial_plan import plan_spatial_transfer
from vqetape.spatial_programs import (
    SpatialSiteParameters,
    bind_spatial_column,
    execute_spatial_column,
)
from vqetape.spec import TFIMVQESpec
from vqetape.symmetry import (
    compress_boundary,
    expand_boundary,
    forbidden_boundary_norm,
    z2_boundary_sector,
    z2_symmetry_applicability,
)


@pytest.mark.parametrize(
    ("shape", "active", "dense"),
    [
        ((2, 2, 3), 6, 12),
        ((2, 2, 2, 2, 3), 24, 48),
    ],
)
def test_z2_boundary_sector_removes_exactly_half(
    shape,
    active,
    dense,
):
    sector = z2_boundary_sector(shape)

    assert sector.active_count == active
    assert sector.dense_count == dense
    assert sector.active_fraction == 0.5
    assert sector.compression_factor == 2.0
    assert sector.active_positions == tuple(
        sorted(sector.active_positions)
    )
    assert sector.forbidden_positions == tuple(
        sorted(sector.forbidden_positions)
    )
    assert not (
        set(sector.active_positions)
        & set(sector.forbidden_positions)
    )
    assert (
        set(sector.active_positions)
        | set(sector.forbidden_positions)
    ) == set(range(dense))
    assert sector.to_dict()["active_count"] == active


@pytest.mark.parametrize(
    "shape",
    [
        (),
        (2, 3),
        (2, 2, 2, 3),
        (2, 4, 3),
        (2, 2, 4),
    ],
)
def test_z2_boundary_sector_rejects_invalid_shape(shape):
    with pytest.raises(ValueError, match="boundary"):
        z2_boundary_sector(shape)


def test_z2_symmetry_requires_plus_initial_state():
    assert z2_symmetry_applicability(
        TFIMVQESpec(
            nqubits=4,
            depth=1,
            initial_state="plus",
        )
    ) == (True, "supported global-X Z2 sector")

    applicable, reason = z2_symmetry_applicability(
        TFIMVQESpec(
            nqubits=4,
            depth=1,
            initial_state="zero",
        )
    )
    assert not applicable
    assert "plus" in reason


@pytest.mark.parametrize("depth", [1, 2])
def test_dense_spatial_recurrence_preserves_z2_sector(depth):
    spec = TFIMVQESpec(
        nqubits=5,
        depth=depth,
        initial_state="plus",
    )
    theta = jnp.linspace(
        -0.3,
        0.4,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    transfer = plan_spatial_transfer(spec, "greedy")
    sector = z2_boundary_sector(transfer.boundary_shape)
    zeros = jnp.zeros((depth,), dtype=jnp.float32)

    def parameters(site):
        return SpatialSiteParameters(
            left_rzz=(
                theta[:, 0, site - 1]
                if site > 0
                else zeros
            ),
            right_rzz=(
                theta[:, 0, site]
                if site < spec.nqubits - 1
                else zeros
            ),
            rx=theta[:, 1, site],
        )

    boundary = execute_spatial_column(
        transfer.first,
        None,
        bind_spatial_column(
            transfer.first,
            parameters(0),
            spec,
        ),
    )
    np.testing.assert_allclose(
        forbidden_boundary_norm(boundary, sector),
        0,
        atol=2e-6,
    )
    np.testing.assert_allclose(
        expand_boundary(
            compress_boundary(boundary, sector),
            sector,
        ),
        boundary,
        atol=2e-6,
    )

    assert transfer.bulk is not None
    for site in range(1, spec.nqubits - 1):
        boundary = execute_spatial_column(
            transfer.bulk,
            boundary,
            bind_spatial_column(
                transfer.bulk,
                parameters(site),
                spec,
            ),
        )
        np.testing.assert_allclose(
            forbidden_boundary_norm(
                boundary,
                sector,
            ),
            0,
            atol=2e-6,
        )
        np.testing.assert_allclose(
            expand_boundary(
                compress_boundary(boundary, sector),
                sector,
            ),
            boundary,
            atol=2e-6,
        )

    last_tensors = bind_spatial_column(
        transfer.last,
        parameters(spec.nqubits - 1),
        spec,
    )
    dense_energy = execute_spatial_column(
        transfer.last,
        boundary,
        last_tensors,
    )
    compressed_energy = execute_spatial_column(
        transfer.last,
        expand_boundary(
            compress_boundary(boundary, sector),
            sector,
        ),
        last_tensors,
    )
    np.testing.assert_allclose(
        compressed_energy,
        dense_energy,
        atol=2e-6,
    )
