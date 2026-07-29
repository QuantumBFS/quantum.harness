import jax
import jax.numpy as jnp
import numpy as np
import opt_einsum as oe
import pytest
from jax.ad_checkpoint import checkpoint_policies

from vqetape.spec import TFIMVQESpec
from vqetape.tape import profile_saved_residuals
from vqetape.tn_program import (
    execute_contraction,
    execute_tree_contraction,
    plan_contraction,
    subtree_nodes_at_depth,
)
from vqetape.tn_template import (
    ProductPauliTerm,
    bind_term_tensors,
    build_expectation_template,
    build_mpo_expectation_template,
)


@pytest.mark.parametrize("strategy", ["greedy", "random-greedy"])
def test_explicit_program_matches_opt_einsum_expression(strategy):
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_expectation_template(spec)
    theta = jnp.linspace(-0.2, 0.3, np.prod(spec.parameter_shape)).reshape(
        spec.parameter_shape
    )
    tensors = bind_term_tensors(
        template,
        theta,
        ProductPauliTerm(-1.0, ("Z", "Z", "I")),
    )
    program = plan_contraction(template, strategy)
    actual = execute_contraction(program, tensors)
    expected = oe.contract(
        template.equation,
        *tensors,
        optimize=list(program.path),
        backend="jax",
    )
    np.testing.assert_allclose(
        np.asarray(actual),
        np.asarray(expected),
        atol=1e-6,
    )
    assert program.flops > 0
    assert program.largest_intermediate_elements > 0
    assert len(program.step_output_bytes) == len(program.steps)


def test_rematerialized_execution_preserves_value():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    template = build_expectation_template(spec)
    theta = jnp.zeros(spec.parameter_shape)
    tensors = bind_term_tensors(
        template,
        theta,
        ProductPauliTerm(-1.0, ("X", "I", "I")),
    )
    program = plan_contraction(template, "greedy")
    reference = execute_contraction(program, tensors)
    rematerialized = execute_contraction(
        program,
        tensors,
        remat_steps=frozenset(range(len(program.steps))),
    )
    np.testing.assert_allclose(
        np.asarray(rematerialized),
        np.asarray(reference),
        atol=1e-6,
    )


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_subtree_checkpoint_execution_preserves_value(depth):
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_expectation_template(spec)
    theta = jnp.linspace(-0.1, 0.2, np.prod(spec.parameter_shape)).reshape(
        spec.parameter_shape
    )
    tensors = bind_term_tensors(
        template,
        theta,
        ProductPauliTerm(-1.0, ("Z", "Z", "I")),
    )
    program = plan_contraction(template, "greedy")
    nodes = subtree_nodes_at_depth(program, depth)
    assert nodes
    actual = execute_tree_contraction(
        program,
        tensors,
        checkpoint_node_ids=frozenset(node.node_id for node in nodes),
    )
    reference = execute_contraction(program, tensors)
    np.testing.assert_allclose(
        np.asarray(actual),
        np.asarray(reference),
        atol=1e-6,
    )


def test_named_contraction_outputs_appear_in_residual_profile():
    spec = TFIMVQESpec(nqubits=2, depth=1)
    template = build_expectation_template(spec)
    program = plan_contraction(template, "greedy")
    term = ProductPauliTerm(-1.0, ("Z", "Z"))
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)

    def objective(value):
        tensors = bind_term_tensors(
            template,
            value,
            term,
            name_residuals=True,
        )
        return jnp.real(
            execute_contraction(
                program,
                tensors,
                name_residuals=True,
            )
        )

    saved_names = tuple(
        f"contract:{step_index}:elements{step.output_elements}:{component}"
        for step_index, step in enumerate(program.steps)
        for component in ("real", "imag")
    )
    profiled = jax.checkpoint(
        objective,
        policy=checkpoint_policies.save_only_these_names(*saved_names),
    )
    profile = profile_saved_residuals(profiled, theta)

    assert any(
        name.startswith("contract:") for name in profile.bytes_by_name()
    )


def test_contraction_program_reports_representation_size():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    dense = plan_contraction(
        build_expectation_template(
            spec,
            gate_representation="dense",
        ),
        "greedy",
    )
    schmidt = plan_contraction(
        build_expectation_template(
            spec,
            gate_representation="operator_schmidt",
        ),
        "greedy",
    )

    assert dense.tensor_count == len(dense.template.slots)
    assert schmidt.tensor_count == len(schmidt.template.slots)
    assert dense.input_tensor_elements == sum(
        np.prod(shape) for shape in dense.template.shapes
    )
    assert schmidt.input_tensor_elements == sum(
        np.prod(shape) for shape in schmidt.template.shapes
    )
    assert schmidt.tensor_count > dense.tensor_count


def test_dense_path_cannot_be_reused_for_schmidt_topology():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    dense = plan_contraction(
        build_expectation_template(
            spec,
            gate_representation="dense",
        ),
        "greedy",
    )
    with pytest.raises(ValueError, match="incompatible"):
        plan_contraction(
            build_expectation_template(
                spec,
                gate_representation="operator_schmidt",
            ),
            "greedy",
            explicit_path=dense.path,
        )


def test_explicit_path_is_revalidated_against_mpo_topology():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    pauli = plan_contraction(
        build_expectation_template(spec),
        "greedy",
    )
    mpo = plan_contraction(
        build_mpo_expectation_template(spec),
        "greedy",
        explicit_path=pauli.path,
    )

    # A positional contraction schedule can remain valid when two topologies
    # happen to have the same operand count.  It is not a cached Pauli
    # program: opt_einsum has rebuilt all equations, sizes, and costs for MPO.
    assert mpo.path == pauli.path
    assert mpo.template.hamiltonian_representation == "mpo"
    assert mpo.template.equation != pauli.template.equation
    assert mpo.flops != pauli.flops
