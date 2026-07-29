import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.programs import build_value_and_grad
from vqetape.spec import ProgramConfig, TFIMVQESpec


@pytest.mark.parametrize("unroll", [1, 2, 4])
@pytest.mark.parametrize("adjoint", ["default", "remat"])
def test_scan_program_matches_unrolled(unroll, adjoint):
    spec = TFIMVQESpec(nqubits=4, depth=4)
    theta = jnp.linspace(
        -0.4,
        0.5,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec,
        ProgramConfig(control_flow="unrolled", adjoint="default", unroll=1),
    )
    candidate = build_value_and_grad(
        spec,
        ProgramConfig(control_flow="scan", adjoint=adjoint, unroll=unroll),
    )
    ref_energy, ref_gradient = reference(theta)
    energy, gradient = candidate(theta)
    np.testing.assert_allclose(
        np.asarray(energy),
        np.asarray(ref_energy),
        atol=1e-5,
    )
    np.testing.assert_allclose(
        np.asarray(gradient),
        np.asarray(ref_gradient),
        rtol=1e-4,
        atol=1e-5,
    )


@pytest.mark.parametrize("depth", [3, 4, 7])
@pytest.mark.parametrize("segment_length", [1, 2, 3])
def test_segmented_adjoint_matches_unrolled(depth, segment_length):
    spec = TFIMVQESpec(nqubits=3, depth=depth)
    theta = jnp.linspace(
        -0.2,
        0.4,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec,
        ProgramConfig(control_flow="unrolled", adjoint="default", unroll=1),
    )
    candidate = build_value_and_grad(
        spec,
        ProgramConfig(
            control_flow="scan",
            adjoint="segmented",
            unroll=1,
            segment_length=segment_length,
        ),
    )
    ref_energy, ref_gradient = reference(theta)
    energy, gradient = candidate(theta)
    np.testing.assert_allclose(
        np.asarray(energy),
        np.asarray(ref_energy),
        atol=1e-5,
    )
    np.testing.assert_allclose(
        np.asarray(gradient),
        np.asarray(ref_gradient),
        rtol=1e-4,
        atol=1e-5,
    )
    np.testing.assert_array_equal(
        np.asarray(gradient[:, 0, -1]),
        np.zeros(depth),
    )
