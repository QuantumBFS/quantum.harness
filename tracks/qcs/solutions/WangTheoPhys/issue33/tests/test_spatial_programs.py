import jax
import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.spatial_plan import plan_spatial_transfer
from vqetape.spatial_programs import (
    SpatialSiteParameters,
    bind_spatial_column,
    build_spatial_energy,
    build_spatial_value_and_grad,
    execute_spatial_column,
    modeled_spatial_checkpoint_count,
    spatial_energy_unrolled,
)
from vqetape.spec import SpatialProgramConfig, TFIMVQESpec
from vqetape.tn_vqe import build_tn_energy


@pytest.mark.parametrize("nqubits", [2, 3, 4, 5])
@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize("initial_state", ["zero", "plus"])
def test_sequential_spatial_energy_matches_global_mpo(
    nqubits,
    depth,
    initial_state,
):
    spec = TFIMVQESpec(
        nqubits=nqubits,
        depth=depth,
        coupling=0.7,
        field=0.3,
        initial_state=initial_state,
    )
    theta = jnp.linspace(
        -0.2,
        0.3,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    program = plan_spatial_transfer(spec, "greedy")
    actual = spatial_energy_unrolled(theta, program)
    reference, _, _ = build_tn_energy(
        spec,
        path_strategy="greedy",
        remat_policy="none",
        gate_representation="operator_schmidt",
        hamiltonian_representation="mpo",
    )

    np.testing.assert_allclose(
        np.asarray(actual),
        np.asarray(reference(theta)),
        rtol=1e-5,
        atol=1e-5,
    )


def test_sequential_spatial_energy_supports_complex128():
    with jax.enable_x64():
        spec = TFIMVQESpec(
            nqubits=3,
            depth=1,
            coupling=0.7,
            field=0.3,
            initial_state="plus",
            dtype="complex128",
        )
        theta = jnp.linspace(
            -0.2,
            0.3,
            np.prod(spec.parameter_shape),
            dtype=jnp.float64,
        ).reshape(spec.parameter_shape)
        program = plan_spatial_transfer(spec, "greedy")
        actual = spatial_energy_unrolled(theta, program)
        reference, _, _ = build_tn_energy(
            spec,
            path_strategy="greedy",
            remat_policy="none",
            gate_representation="operator_schmidt",
            hamiltonian_representation="mpo",
        )
        np.testing.assert_allclose(
            np.asarray(actual),
            np.asarray(reference(theta)),
            rtol=1e-10,
            atol=1e-10,
        )


def test_spatial_column_validates_boundary_carry():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    transfer = plan_spatial_transfer(spec, "greedy")
    assert transfer.bulk is not None
    zeros = jnp.zeros((spec.depth,), dtype=jnp.float32)
    parameters = SpatialSiteParameters(zeros, zeros, zeros)
    bulk_tensors = bind_spatial_column(
        transfer.bulk,
        parameters,
        spec,
    )
    first_tensors = bind_spatial_column(
        transfer.first,
        parameters,
        spec,
    )

    with pytest.raises(ValueError, match="requires a boundary carry"):
        execute_spatial_column(transfer.bulk, None, bulk_tensors)
    with pytest.raises(ValueError, match="carry shape"):
        execute_spatial_column(
            transfer.bulk,
            jnp.zeros((2,), dtype=jnp.complex64),
            bulk_tensors,
        )
    with pytest.raises(ValueError, match="does not accept"):
        execute_spatial_column(
            transfer.first,
            jnp.zeros(transfer.boundary_shape, dtype=jnp.complex64),
            first_tensors,
        )


@pytest.mark.parametrize("nqubits", [2, 3, 5])
@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize("adjoint", ["default", "remat"])
def test_spatial_scan_matches_global_mpo_full_gradient(
    nqubits,
    depth,
    adjoint,
):
    spec = TFIMVQESpec(nqubits=nqubits, depth=depth)
    theta = jnp.linspace(
        -0.1,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    config = SpatialProgramConfig("greedy", adjoint, unroll=1)
    energy = build_spatial_energy(spec, config)
    actual_energy, actual_gradient = jax.value_and_grad(energy)(theta)
    reference, _, _ = build_tn_energy(
        spec,
        path_strategy="greedy",
        remat_policy="none",
        hamiltonian_representation="mpo",
    )
    expected_energy, expected_gradient = jax.value_and_grad(reference)(theta)

    np.testing.assert_allclose(
        np.asarray(actual_energy),
        np.asarray(expected_energy),
        atol=1e-5,
    )
    np.testing.assert_allclose(
        np.asarray(actual_gradient),
        np.asarray(expected_gradient),
        rtol=1e-4,
        atol=1e-5,
    )
    np.testing.assert_array_equal(
        np.asarray(actual_gradient[:, 0, -1]),
        np.zeros((depth,), dtype=np.float32),
    )


def test_spatial_scan_supports_unroll_two():
    spec = TFIMVQESpec(nqubits=6, depth=1)
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    unroll_one = build_spatial_energy(
        spec,
        SpatialProgramConfig("greedy", "default", unroll=1),
    )
    unroll_two = build_spatial_energy(
        spec,
        SpatialProgramConfig("greedy", "default", unroll=2),
    )
    value_one = jax.value_and_grad(unroll_one)(theta)
    value_two = jax.value_and_grad(unroll_two)(theta)

    np.testing.assert_allclose(value_two[0], value_one[0], atol=1e-5)
    np.testing.assert_allclose(value_two[1], value_one[1], atol=1e-5)


@pytest.mark.parametrize("nqubits", [4, 5, 6, 8])
@pytest.mark.parametrize("block_width", [1, 2, 3, 4])
@pytest.mark.parametrize("adjoint", ["default", "remat"])
def test_blocked_spatial_gradient_matches_width_one(
    nqubits,
    block_width,
    adjoint,
):
    if block_width > nqubits - 2:
        pytest.skip("block wider than interior")
    spec = TFIMVQESpec(nqubits=nqubits, depth=1)
    theta = jnp.linspace(
        -0.2,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=1,
        ),
    )
    blocked = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            adjoint,
            block_width=block_width,
        ),
    )
    expected = jax.value_and_grad(reference)(theta)
    actual = jax.value_and_grad(blocked)(theta)

    np.testing.assert_allclose(actual[0], expected[0], atol=1e-5)
    np.testing.assert_allclose(
        actual[1],
        expected[1],
        rtol=1e-4,
        atol=1e-5,
    )


def test_blocked_spatial_tail_is_differentiated():
    spec = TFIMVQESpec(nqubits=8, depth=1)
    theta = jnp.linspace(
        -0.3,
        0.3,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    one = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=1,
        ),
    )
    four = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=4,
        ),
    )

    np.testing.assert_allclose(
        jax.value_and_grad(four)(theta)[1],
        jax.value_and_grad(one)(theta)[1],
        rtol=1e-4,
        atol=1e-5,
    )


@pytest.mark.parametrize(
    ("nqubits", "block_width"),
    [(5, 1), (8, 2), (8, 3), (10, 4)],
)
def test_explicit_spatial_adjoint_matches_default(
    nqubits,
    block_width,
):
    spec = TFIMVQESpec(nqubits=nqubits, depth=1)
    theta = jnp.linspace(
        -0.2,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    default = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=block_width,
        ),
    )
    explicit = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "explicit",
            block_width=block_width,
        ),
    )
    expected = jax.value_and_grad(default)(theta)
    actual = jax.value_and_grad(explicit)(theta)

    np.testing.assert_allclose(
        actual[0],
        expected[0],
        atol=1e-5,
    )
    np.testing.assert_allclose(
        actual[1],
        expected[1],
        rtol=1e-4,
        atol=1e-5,
    )


@pytest.mark.parametrize(
    ("nqubits", "depth", "block_width", "adjoint"),
    [
        (5, 1, 1, "default"),
        (8, 1, 2, "remat"),
        (8, 2, 3, "explicit"),
        (10, 1, 4, "default"),
        (8, 1, 1, "segmented"),
    ],
)
def test_z2_reference_spatial_gradient_matches_dense(
    nqubits,
    depth,
    block_width,
    adjoint,
):
    spec = TFIMVQESpec(
        nqubits=nqubits,
        depth=depth,
        initial_state="plus",
    )
    theta = jnp.linspace(
        -0.2,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    kwargs = (
        {"segment_length": 2}
        if adjoint == "segmented"
        else {}
    )
    dense = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            adjoint,
            block_width=block_width,
            **kwargs,
        ),
    )
    compressed = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            adjoint,
            block_width=block_width,
            symmetry="z2-reference",
            **kwargs,
        ),
    )
    expected = jax.value_and_grad(dense)(theta)
    actual = jax.value_and_grad(compressed)(theta)

    np.testing.assert_allclose(
        actual[0],
        expected[0],
        rtol=1e-5,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        actual[1],
        expected[1],
        rtol=1e-4,
        atol=1e-5,
    )


def test_z2_reference_requires_symmetric_initial_state():
    spec = TFIMVQESpec(
        nqubits=5,
        depth=1,
        initial_state="zero",
    )
    with pytest.raises(ValueError, match="plus"):
        build_spatial_energy(
            spec,
            SpatialProgramConfig(
                "greedy",
                "default",
                symmetry="z2-reference",
            ),
        )


def test_z2_reference_scan_carry_is_compressed():
    spec = TFIMVQESpec(nqubits=8, depth=1)
    theta = jnp.zeros(
        spec.parameter_shape,
        dtype=jnp.float32,
    )
    executable = build_spatial_value_and_grad(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            symmetry="z2-reference",
        ),
    )
    text = executable.lower(theta).as_text().lower()

    assert "while" in text
    assert "tensor<6xcomplex<f32>>" in text


def test_z2_reference_supports_complex128():
    with jax.enable_x64():
        spec = TFIMVQESpec(
            nqubits=5,
            depth=1,
            dtype="complex128",
        )
        theta = jnp.linspace(
            -0.2,
            0.2,
            np.prod(spec.parameter_shape),
            dtype=jnp.float64,
        ).reshape(spec.parameter_shape)
        dense = build_spatial_energy(
            spec,
            SpatialProgramConfig(
                "greedy",
                "default",
            ),
        )
        compressed = build_spatial_energy(
            spec,
            SpatialProgramConfig(
                "greedy",
                "default",
                symmetry="z2-reference",
            ),
        )
        expected = jax.value_and_grad(dense)(theta)
        actual = jax.value_and_grad(compressed)(theta)

        np.testing.assert_allclose(
            actual[0],
            expected[0],
            rtol=1e-10,
            atol=1e-10,
        )
        np.testing.assert_allclose(
            actual[1],
            expected[1],
            rtol=1e-9,
            atol=1e-10,
        )


@pytest.mark.parametrize(
    ("nqubits", "depth", "block_width", "adjoint"),
    [
        (5, 1, 1, "default"),
        (8, 1, 2, "remat"),
        (8, 2, 3, "default"),
        (10, 1, 4, "default"),
        (8, 1, 1, "segmented"),
    ],
)
def test_z2_native_spatial_gradient_matches_reference(
    nqubits,
    depth,
    block_width,
    adjoint,
):
    spec = TFIMVQESpec(nqubits=nqubits, depth=depth)
    theta = jnp.linspace(
        -0.2,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    kwargs = (
        {"segment_length": 2}
        if adjoint == "segmented"
        else {}
    )
    reference = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            adjoint,
            block_width=block_width,
            symmetry="z2-reference",
            **kwargs,
        ),
    )
    native = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            adjoint,
            block_width=block_width,
            symmetry="z2-native",
            **kwargs,
        ),
    )
    expected = jax.value_and_grad(reference)(theta)
    actual = jax.value_and_grad(native)(theta)

    np.testing.assert_allclose(
        actual[0],
        expected[0],
        rtol=1e-5,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        actual[1],
        expected[1],
        rtol=1e-4,
        atol=1e-5,
    )


def test_z2_native_rejects_unsupported_explicit_adjoint():
    with pytest.raises(ValueError, match="explicit"):
        build_spatial_energy(
            TFIMVQESpec(nqubits=5, depth=1),
            SpatialProgramConfig(
                "greedy",
                "explicit",
                symmetry="z2-native",
            ),
        )


def test_z2_native_scan_carry_is_compressed():
    spec = TFIMVQESpec(nqubits=8, depth=1)
    theta = jnp.zeros(
        spec.parameter_shape,
        dtype=jnp.float32,
    )
    executable = build_spatial_value_and_grad(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            symmetry="z2-native",
        ),
    )
    text = executable.lower(theta).as_text().lower()

    assert "while" in text
    assert "tensor<6xcomplex<f32>>" in text


def test_z2_native_supports_complex128():
    with jax.enable_x64():
        spec = TFIMVQESpec(
            nqubits=5,
            depth=1,
            dtype="complex128",
        )
        theta = jnp.linspace(
            -0.2,
            0.2,
            np.prod(spec.parameter_shape),
            dtype=jnp.float64,
        ).reshape(spec.parameter_shape)
        reference = build_spatial_energy(
            spec,
            SpatialProgramConfig(
                "greedy",
                "default",
                symmetry="z2-reference",
            ),
        )
        native = build_spatial_energy(
            spec,
            SpatialProgramConfig(
                "greedy",
                "default",
                symmetry="z2-native",
            ),
        )
        expected = jax.value_and_grad(reference)(theta)
        actual = jax.value_and_grad(native)(theta)

        np.testing.assert_allclose(
            actual[0],
            expected[0],
            rtol=1e-10,
            atol=1e-10,
        )
        np.testing.assert_allclose(
            actual[1],
            expected[1],
            rtol=1e-9,
            atol=1e-10,
        )


def test_blocked_spatial_scan_lowers_to_while():
    spec = TFIMVQESpec(nqubits=10, depth=1)
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    executable = build_spatial_value_and_grad(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=2,
            unroll=1,
        ),
    )

    assert "while" in executable.lower(theta).as_text().lower()


def test_spatial_scan_lowers_to_while():
    spec = TFIMVQESpec(nqubits=6, depth=1)
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    executable = build_spatial_value_and_grad(
        spec,
        SpatialProgramConfig("greedy", "default", unroll=1),
    )
    text = executable.lower(theta).as_text()

    assert "while" in text.lower()


def test_spatial_scan_ir_size_is_stable_with_chain_length():
    texts = {}
    for nqubits in (6, 10):
        spec = TFIMVQESpec(nqubits=nqubits, depth=1)
        theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
        executable = build_spatial_value_and_grad(
            spec,
            SpatialProgramConfig("greedy", "default", unroll=1),
        )
        texts[nqubits] = executable.lower(theta).as_text()
        assert "while" in texts[nqubits].lower()

    assert len(texts[10]) < 2 * len(texts[6])


@pytest.mark.parametrize(
    ("nqubits", "segment_length"),
    [(4, 1), (7, 2), (8, 3)],
)
def test_segmented_spatial_adjoint_matches_default(
    nqubits,
    segment_length,
):
    spec = TFIMVQESpec(nqubits=nqubits, depth=1)
    theta = jnp.linspace(
        -0.2,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    default = build_spatial_energy(
        spec,
        SpatialProgramConfig("greedy", "default"),
    )
    segmented = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "segmented",
            segment_length=segment_length,
        ),
    )
    default_value = jax.value_and_grad(default)(theta)
    segmented_value = jax.value_and_grad(segmented)(theta)

    np.testing.assert_allclose(
        np.asarray(segmented_value[0]),
        np.asarray(default_value[0]),
        atol=1e-5,
    )
    np.testing.assert_allclose(
        np.asarray(segmented_value[1]),
        np.asarray(default_value[1]),
        rtol=1e-4,
        atol=1e-5,
    )


def test_segmented_spatial_adjoint_requires_bulk_columns():
    spec = TFIMVQESpec(nqubits=2, depth=1)
    config = SpatialProgramConfig(
        "greedy",
        "segmented",
        segment_length=1,
    )
    with pytest.raises(ValueError, match="bulk"):
        build_spatial_energy(spec, config)


@pytest.mark.parametrize(
    ("nqubits", "block_width", "segment_length"),
    [(10, 2, 2), (14, 3, 2), (15, 4, 2)],
)
def test_blocked_segmented_matches_blocked_default(
    nqubits,
    block_width,
    segment_length,
):
    spec = TFIMVQESpec(nqubits=nqubits, depth=1)
    theta = jnp.linspace(
        -0.2,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    default = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=block_width,
        ),
    )
    segmented = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "segmented",
            block_width=block_width,
            segment_length=segment_length,
        ),
    )
    expected = jax.value_and_grad(default)(theta)
    actual = jax.value_and_grad(segmented)(theta)

    np.testing.assert_allclose(actual[0], expected[0], atol=1e-5)
    np.testing.assert_allclose(
        actual[1],
        expected[1],
        rtol=1e-4,
        atol=1e-5,
    )


def test_modeled_spatial_checkpoint_count():
    spec = TFIMVQESpec(nqubits=8, depth=1)
    assert modeled_spatial_checkpoint_count(
        spec,
        SpatialProgramConfig("greedy", "default"),
    ) == 6
    assert modeled_spatial_checkpoint_count(
        spec,
        SpatialProgramConfig(
            "greedy",
            "segmented",
            segment_length=2,
        ),
    ) == 5
    assert modeled_spatial_checkpoint_count(
        spec,
        SpatialProgramConfig(
            "greedy",
            "segmented",
            segment_length=3,
        ),
    ) == 5
