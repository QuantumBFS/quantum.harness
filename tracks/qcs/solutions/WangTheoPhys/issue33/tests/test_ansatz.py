import json

import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.ansatz import (
    AnsatzOperator,
    AnsatzStructure,
    fixed_rzz_rx_structure,
    layered_parameters_to_vector,
    local_operator_pool,
    ordered_ansatz_energy,
    ordered_ansatz_state,
)
from vqetape.kernels import (
    unrolled_energy,
    unrolled_state,
)
from vqetape.spec import TFIMVQESpec


def test_ansatz_structure_round_trip_and_append():
    structure = fixed_rzz_rx_structure(4, 1)
    restored = AnsatzStructure.from_dict(
        json.loads(json.dumps(structure.to_dict()))
    )

    assert restored == structure
    assert structure.parameter_count == 7
    assert structure.append(
        AnsatzOperator("rx", 2)
    ).parameter_count == 8
    assert structure.label == restored.label


def test_local_pool_is_complete_and_symmetry_compatible():
    pool = local_operator_pool(4)

    assert [item.label for item in pool] == [
        "rzz-0-1",
        "rzz-1-2",
        "rzz-2-3",
        "yz-0-1",
        "yz-1-2",
        "yz-2-3",
        "zy-0-1",
        "zy-1-2",
        "zy-2-3",
        "rx-0",
        "rx-1",
        "rx-2",
        "rx-3",
    ]


def test_commutator_pool_gates_preserve_global_x_sector():
    spec = TFIMVQESpec(nqubits=4, depth=1)
    structure = AnsatzStructure(
        4,
        (
            AnsatzOperator("yz", 1),
            AnsatzOperator("zy", 2),
        ),
    )
    state = ordered_ansatz_state(
        jnp.asarray([0.3, -0.2]),
        structure,
        spec,
    )
    tensor = state.reshape((2,) * 4)
    global_x_state = jnp.flip(
        tensor,
        axis=(0, 1, 2, 3),
    ).reshape(-1)

    np.testing.assert_allclose(
        global_x_state,
        state,
        rtol=1e-6,
        atol=1e-6,
    )


def test_ordered_fixed_structure_matches_layered_kernel():
    spec = TFIMVQESpec(nqubits=4, depth=2)
    theta = jnp.linspace(
        -0.3,
        0.4,
        np.prod(spec.parameter_shape),
    ).reshape(spec.parameter_shape)
    structure = fixed_rzz_rx_structure(
        spec.nqubits,
        spec.depth,
    )
    parameters = layered_parameters_to_vector(theta, spec)

    np.testing.assert_allclose(
        ordered_ansatz_state(parameters, structure, spec),
        unrolled_state(theta, spec),
        rtol=1e-6,
        atol=1e-6,
    )
    np.testing.assert_allclose(
        ordered_ansatz_energy(parameters, structure, spec),
        unrolled_energy(theta, spec),
        rtol=1e-6,
        atol=1e-6,
    )


def test_structure_rejects_out_of_range_operator():
    with pytest.raises(ValueError, match="outside"):
        AnsatzStructure(
            3,
            (AnsatzOperator("rzz", 2),),
        )


def test_ordered_state_validates_parameter_shape():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    structure = fixed_rzz_rx_structure(3, 1)
    with pytest.raises(ValueError, match="shape"):
        ordered_ansatz_state(
            jnp.zeros((structure.parameter_count + 1,)),
            structure,
            spec,
        )
