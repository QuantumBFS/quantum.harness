from collections import Counter

import jax.numpy as jnp
import numpy as np
import opt_einsum as oe
import pytest

from vqetape.spec import TFIMVQESpec
from vqetape.tn_template import (
    ProductPauliTerm,
    bind_mpo_tensors,
    bind_term_tensors,
    build_expectation_template,
    build_mpo_expectation_template,
)
from vqetape.tn_vqe import tfim_product_terms


def test_expectation_template_is_closed_scalar_network():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_expectation_template(spec)
    counts = Counter(
        index for slot in template.slots for index in slot.indices
    )
    assert set(counts.values()) == {2}
    assert template.equation.endswith("->")
    assert len(template.slots) == (
        3 * spec.nqubits
        + 2 * spec.depth * (2 * spec.nqubits - 1)
    )


def test_bound_term_matches_declared_shapes():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_expectation_template(spec)
    theta = jnp.zeros(spec.parameter_shape)
    tensors = bind_term_tensors(
        template,
        theta,
        ProductPauliTerm(
            coefficient=-1.0,
            operators=("Z", "Z", "I"),
        ),
    )
    assert tuple(tuple(tensor.shape) for tensor in tensors) == template.shapes


def test_template_scales_with_declared_gate_count():
    spec = TFIMVQESpec(nqubits=5, depth=3)
    template = build_expectation_template(spec)
    assert len(template.slots) == 15 + 2 * 3 * 9


def test_operator_schmidt_template_has_rank_three_factor_slots():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_expectation_template(
        spec,
        gate_representation="operator_schmidt",
    )
    left = [
        slot for slot in template.slots if slot.kind == "ket_rzz_left"
    ]
    right = [
        slot for slot in template.slots if slot.kind == "ket_rzz_right"
    ]
    expected_gate_count = spec.depth * (spec.nqubits - 1)
    assert len(left) == expected_gate_count
    assert len(right) == expected_gate_count
    assert all(slot.shape == (2, 2, 2) for slot in left + right)
    counts = Counter(
        index for slot in template.slots for index in slot.indices
    )
    assert set(counts.values()) == {2}
    assert len(template.slots) == (
        3 * spec.nqubits
        + 2 * spec.depth * (3 * spec.nqubits - 2)
    )


def test_dense_template_remains_default():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    implicit = build_expectation_template(spec)
    explicit = build_expectation_template(
        spec,
        gate_representation="dense",
    )
    assert implicit == explicit
    assert implicit.hamiltonian_representation == "pauli_sum"


@pytest.mark.parametrize(
    "operators",
    [
        ("Z", "Z", "I"),
        ("I", "X", "I"),
    ],
)
def test_dense_and_schmidt_term_contractions_match(operators):
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.linspace(
        -0.2,
        0.3,
        np.prod(spec.parameter_shape),
    ).reshape(spec.parameter_shape)
    term = ProductPauliTerm(-1.0, operators)
    values = []
    for representation in ("dense", "operator_schmidt"):
        template = build_expectation_template(
            spec,
            gate_representation=representation,
        )
        tensors = bind_term_tensors(template, theta, term)
        assert tuple(tensor.shape for tensor in tensors) == template.shapes
        values.append(
            oe.contract(
                template.equation,
                *tensors,
                optimize="greedy",
                backend="jax",
            )
        )
    np.testing.assert_allclose(
        np.asarray(values[0]),
        np.asarray(values[1]),
        rtol=1e-5,
        atol=1e-5,
    )


def test_template_rejects_unknown_gate_representation():
    with pytest.raises(ValueError, match="gate_representation"):
        build_expectation_template(
            TFIMVQESpec(nqubits=3, depth=1),
            gate_representation="sparse",
        )


def test_mpo_expectation_template_is_closed():
    spec = TFIMVQESpec(nqubits=4, depth=2)
    template = build_mpo_expectation_template(spec)
    assert template.hamiltonian_representation == "mpo"
    mpo_slots = [
        slot
        for slot in template.slots
        if slot.kind.startswith("hamiltonian_mpo_")
    ]
    assert [slot.kind for slot in mpo_slots] == [
        "hamiltonian_mpo_first",
        "hamiltonian_mpo_bulk",
        "hamiltonian_mpo_bulk",
        "hamiltonian_mpo_last",
    ]
    assert [slot.shape for slot in mpo_slots] == [
        (3, 2, 2),
        (3, 3, 2, 2),
        (3, 3, 2, 2),
        (3, 2, 2),
    ]
    counts = Counter(
        index for slot in template.slots for index in slot.indices
    )
    assert set(counts.values()) == {2}


def test_bound_mpo_tensors_match_template_shapes():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_mpo_expectation_template(spec)
    theta = jnp.zeros(spec.parameter_shape)
    tensors = bind_mpo_tensors(template, theta)
    assert tuple(tensor.shape for tensor in tensors) == template.shapes


def test_mpo_and_pauli_sum_scalar_contractions_match():
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
    ).reshape(spec.parameter_shape)
    mpo_template = build_mpo_expectation_template(spec)
    mpo_value = oe.contract(
        mpo_template.equation,
        *bind_mpo_tensors(mpo_template, theta),
        optimize="greedy",
        backend="jax",
    )
    term_template = build_expectation_template(spec)
    term_value = sum(
        term.coefficient
        * oe.contract(
            term_template.equation,
            *bind_term_tensors(term_template, theta, term),
            optimize="greedy",
            backend="jax",
        )
        for term in tfim_product_terms(spec)
    )
    np.testing.assert_allclose(
        np.asarray(mpo_value),
        np.asarray(term_value),
        rtol=1e-5,
        atol=1e-5,
    )
