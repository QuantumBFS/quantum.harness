import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.programs import build_value_and_grad
from vqetape.spec import ProgramConfig, TFIMVQESpec
from vqetape.tn_vqe import build_tn_value_and_grad


@pytest.mark.parametrize("strategy", ["greedy", "random-greedy"])
@pytest.mark.parametrize(
    "policy",
    ["none", "all", "output-ge-threshold", "term", "objective"],
)
def test_direct_tn_matches_statevector(strategy, policy):
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.linspace(
        -0.2,
        0.3,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec,
        ProgramConfig(control_flow="unrolled", adjoint="default"),
    )
    candidate = build_tn_value_and_grad(
        spec,
        path_strategy=strategy,
        remat_policy=policy,
        threshold_bytes=64 if policy == "output-ge-threshold" else None,
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
        np.zeros(spec.depth),
    )


def test_direct_tn_zero_parameter_energy():
    spec = TFIMVQESpec(nqubits=4, depth=1)
    executable = build_tn_value_and_grad(
        spec,
        path_strategy="greedy",
        remat_policy="none",
    )
    energy, _ = executable(jnp.zeros(spec.parameter_shape))
    np.testing.assert_allclose(np.asarray(energy), -4.0, atol=1e-5)


@pytest.mark.parametrize("subtree_depth", [0, 1, 2])
def test_subtree_remat_gradient_matches_statevector(subtree_depth):
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.linspace(
        -0.2,
        0.3,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec,
        ProgramConfig(control_flow="unrolled", adjoint="default"),
    )
    candidate = build_tn_value_and_grad(
        spec,
        path_strategy="greedy",
        remat_policy="subtree",
        subtree_depth=subtree_depth,
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


@pytest.mark.parametrize(
    "save_names",
    [
        (),
        (
            "contract:6:elements16:real",
            "contract:6:elements16:imag",
        ),
    ],
)
def test_named_tape_gradient_matches_statevector(save_names):
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.linspace(
        -0.2,
        0.3,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec,
        ProgramConfig(control_flow="unrolled", adjoint="default"),
    )
    candidate = build_tn_value_and_grad(
        spec,
        path_strategy="greedy",
        remat_policy="named",
        save_names=save_names,
    )

    ref_energy, ref_gradient = reference(theta)
    energy, gradient = candidate(theta)

    np.testing.assert_allclose(np.asarray(energy), np.asarray(ref_energy), atol=1e-5)
    np.testing.assert_allclose(
        np.asarray(gradient),
        np.asarray(ref_gradient),
        rtol=1e-4,
        atol=1e-5,
    )


@pytest.mark.parametrize(
    "spec",
    [
        TFIMVQESpec(
            nqubits=2,
            depth=1,
            coupling=0.7,
            field=0.3,
            initial_state="zero",
        ),
        TFIMVQESpec(
            nqubits=3,
            depth=1,
            coupling=1.2,
            field=0.4,
            initial_state="plus",
        ),
        TFIMVQESpec(
            nqubits=3,
            depth=2,
            coupling=0.8,
            field=1.1,
            initial_state="plus",
        ),
    ],
)
@pytest.mark.parametrize(
    "gate_representation",
    ["dense", "operator_schmidt"],
)
@pytest.mark.parametrize(
    "hamiltonian_representation",
    ["pauli_sum", "mpo"],
)
def test_direct_tn_matches_statevector_across_workload_matrix(
    spec,
    gate_representation,
    hamiltonian_representation,
):
    theta = jnp.linspace(
        -0.15,
        0.25,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec,
        ProgramConfig(control_flow="unrolled", adjoint="default"),
    )
    candidate = build_tn_value_and_grad(
        spec,
        path_strategy="greedy",
        remat_policy="none",
        gate_representation=gate_representation,
        hamiltonian_representation=hamiltonian_representation,
    )

    ref_energy, ref_gradient = reference(theta)
    energy, gradient = candidate(theta)

    np.testing.assert_allclose(np.asarray(energy), np.asarray(ref_energy), atol=1e-5)
    np.testing.assert_allclose(
        np.asarray(gradient),
        np.asarray(ref_gradient),
        rtol=1e-4,
        atol=1e-5,
    )
    np.testing.assert_array_equal(
        np.asarray(gradient[:, 0, -1]),
        np.zeros(spec.depth),
    )


@pytest.mark.parametrize(
    "gate_representation",
    ["dense", "operator_schmidt"],
)
@pytest.mark.parametrize("policy", ["none", "named"])
def test_representations_match_statevector_full_gradient(
    gate_representation,
    policy,
):
    spec = TFIMVQESpec(
        nqubits=3,
        depth=2,
        coupling=0.8,
        field=1.1,
    )
    theta = jnp.linspace(
        -0.2,
        0.3,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec,
        ProgramConfig("unrolled", "default"),
    )
    candidate = build_tn_value_and_grad(
        spec,
        path_strategy="greedy",
        remat_policy=policy,
        save_names=() if policy == "named" else None,
        gate_representation=gate_representation,
    )

    expected_energy, expected_gradient = reference(theta)
    energy, gradient = candidate(theta)

    np.testing.assert_allclose(
        np.asarray(energy),
        np.asarray(expected_energy),
        atol=1e-5,
    )
    np.testing.assert_allclose(
        np.asarray(gradient),
        np.asarray(expected_gradient),
        rtol=1e-4,
        atol=1e-5,
    )
    np.testing.assert_array_equal(
        np.asarray(gradient[:, 0, -1]),
        np.zeros(spec.depth),
    )


@pytest.mark.parametrize(
    "hamiltonian_representation",
    ["pauli_sum", "mpo"],
)
@pytest.mark.parametrize("policy", ["none", "named"])
def test_hamiltonian_representations_match_statevector_full_gradient(
    hamiltonian_representation,
    policy,
):
    spec = TFIMVQESpec(
        nqubits=3,
        depth=2,
        coupling=0.7,
        field=1.3,
    )
    theta = jnp.linspace(
        -0.2,
        0.3,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec,
        ProgramConfig("unrolled", "default"),
    )
    candidate = build_tn_value_and_grad(
        spec,
        path_strategy="greedy",
        remat_policy=policy,
        save_names=() if policy == "named" else None,
        hamiltonian_representation=hamiltonian_representation,
    )

    expected_energy, expected_gradient = reference(theta)
    energy, gradient = candidate(theta)

    np.testing.assert_allclose(
        np.asarray(energy),
        np.asarray(expected_energy),
        atol=1e-5,
    )
    np.testing.assert_allclose(
        np.asarray(gradient),
        np.asarray(expected_gradient),
        rtol=1e-4,
        atol=1e-5,
    )
    np.testing.assert_array_equal(
        np.asarray(gradient[:, 0, -1]),
        np.zeros(spec.depth),
    )
