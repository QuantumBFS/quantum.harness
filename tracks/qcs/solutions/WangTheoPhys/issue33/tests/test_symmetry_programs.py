import jax
import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.spatial_plan import plan_spatial_transfer
from vqetape.spatial_programs import (
    SpatialSiteParameters,
    bind_spatial_block,
    bind_spatial_column,
    execute_spatial_column,
)
from vqetape.spec import TFIMVQESpec
from vqetape.symmetry import (
    compress_boundary,
    expand_boundary,
    z2_boundary_sector,
)
from vqetape.symmetry_programs import (
    build_z2_native_contraction,
)


def _parameters(spec):
    values = jnp.linspace(
        -0.2,
        0.3,
        3 * spec.depth,
        dtype=jnp.float32,
    ).reshape(3, spec.depth)
    return SpatialSiteParameters(
        values[0],
        values[1],
        values[2],
    )


def test_z2_native_first_bulk_and_last_match_reference():
    spec = TFIMVQESpec(nqubits=5, depth=1)
    transfer = plan_spatial_transfer(spec, "greedy")
    sector = z2_boundary_sector(transfer.boundary_shape)
    parameters = _parameters(spec)

    first_tensors = bind_spatial_column(
        transfer.first,
        parameters,
        spec,
    )
    native_first = build_z2_native_contraction(
        transfer.first,
        sector,
        dtype=jnp.complex64,
    )
    compressed = native_first.executor(
        None,
        first_tensors,
    )
    dense = execute_spatial_column(
        transfer.first,
        None,
        first_tensors,
    )
    np.testing.assert_allclose(
        compressed,
        compress_boundary(dense, sector),
        atol=1e-6,
    )

    assert transfer.bulk is not None
    bulk_tensors = bind_spatial_column(
        transfer.bulk,
        parameters,
        spec,
    )
    native_bulk = build_z2_native_contraction(
        transfer.bulk,
        sector,
        dtype=jnp.complex64,
    )
    compressed = native_bulk.executor(
        compressed,
        bulk_tensors,
    )
    dense = execute_spatial_column(
        transfer.bulk,
        dense,
        bulk_tensors,
    )
    np.testing.assert_allclose(
        compressed,
        compress_boundary(dense, sector),
        atol=1e-6,
    )

    last_tensors = bind_spatial_column(
        transfer.last,
        parameters,
        spec,
    )
    native_last = build_z2_native_contraction(
        transfer.last,
        sector,
        dtype=jnp.complex64,
    )
    actual_energy = native_last.executor(
        compressed,
        last_tensors,
    )
    expected_energy = execute_spatial_column(
        transfer.last,
        dense,
        last_tensors,
    )
    np.testing.assert_allclose(
        actual_energy,
        expected_energy,
        atol=1e-6,
    )


@pytest.mark.parametrize(
    ("nqubits", "block_width"),
    [(8, 2), (8, 4)],
)
def test_z2_native_block_and_tail_match_reference(
    nqubits,
    block_width,
):
    spec = TFIMVQESpec(nqubits=nqubits, depth=1)
    transfer = plan_spatial_transfer(
        spec,
        "greedy",
        block_width=block_width,
    )
    sector = z2_boundary_sector(transfer.boundary_shape)
    compressed = jnp.linspace(
        0.1,
        0.6,
        sector.active_count,
        dtype=jnp.float32,
    ).astype(jnp.complex64)

    for program in (transfer.bulk, transfer.tail):
        if program is None:
            continue
        packed = jnp.linspace(
            -0.2,
            0.3,
            program.width * 3 * spec.depth,
            dtype=jnp.float32,
        ).reshape(program.width, 3, spec.depth)
        tensors = bind_spatial_block(program, packed, spec)
        native = build_z2_native_contraction(
            program,
            sector,
            dtype=jnp.complex64,
        )
        actual = native.executor(compressed, tensors)
        dense = execute_spatial_column(
            program,
            expand_boundary(compressed, sector),
            tensors,
        )
        expected = compress_boundary(dense, sector)
        np.testing.assert_allclose(
            actual,
            expected,
            rtol=1e-5,
            atol=1e-5,
        )


def test_z2_native_bulk_vjp_matches_expand_gather_reference():
    spec = TFIMVQESpec(nqubits=5, depth=1)
    transfer = plan_spatial_transfer(spec, "greedy")
    assert transfer.bulk is not None
    sector = z2_boundary_sector(transfer.boundary_shape)
    tensors = bind_spatial_column(
        transfer.bulk,
        _parameters(spec),
        spec,
    )
    carry = jnp.linspace(
        0.1,
        0.6,
        sector.active_count,
        dtype=jnp.float32,
    ).astype(jnp.complex64)
    native = build_z2_native_contraction(
        transfer.bulk,
        sector,
        dtype=jnp.complex64,
    )

    def actual_fn(boundary, *values):
        return native.executor(boundary, tuple(values))

    def reference_fn(boundary, *values):
        dense = execute_spatial_column(
            transfer.bulk,
            expand_boundary(boundary, sector),
            tuple(values),
        )
        return compress_boundary(dense, sector)

    actual_value, actual_pullback = jax.vjp(
        actual_fn,
        carry,
        *tensors,
    )
    expected_value, expected_pullback = jax.vjp(
        reference_fn,
        carry,
        *tensors,
    )
    cotangent = jnp.full_like(
        actual_value,
        0.7 + 0.2j,
    )
    np.testing.assert_allclose(
        actual_value,
        expected_value,
        atol=1e-6,
    )
    for actual, expected in zip(
        actual_pullback(cotangent),
        expected_pullback(cotangent),
        strict=True,
    ):
        np.testing.assert_allclose(
            actual,
            expected,
            rtol=1e-5,
            atol=1e-5,
        )


def test_z2_native_transition_has_no_dense_carry_scatter():
    spec = TFIMVQESpec(nqubits=5, depth=1)
    transfer = plan_spatial_transfer(spec, "greedy")
    assert transfer.bulk is not None
    sector = z2_boundary_sector(transfer.boundary_shape)
    tensors = bind_spatial_column(
        transfer.bulk,
        _parameters(spec),
        spec,
    )
    carry = jnp.zeros(
        (sector.active_count,),
        dtype=jnp.complex64,
    )
    native = build_z2_native_contraction(
        transfer.bulk,
        sector,
        dtype=jnp.complex64,
    )
    text = str(
        jax.make_jaxpr(
            lambda boundary, *values: native.executor(
                boundary,
                tuple(values),
            )
        )(carry, *tensors)
    ).lower()

    assert "bcoo_dot_general" in text
    assert "scatter" not in text
    assert "bcoo_todense" not in text
