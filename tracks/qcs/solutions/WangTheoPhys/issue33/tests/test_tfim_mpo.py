import jax
import numpy as np
import opt_einsum as oe
import pytest

from vqetape.spec import TFIMVQESpec
from vqetape.tfim_mpo import dense_tfim_hamiltonian, tfim_mpo_tensors


def _contract_mpo_to_dense(tensors):
    nqubits = len(tensors)
    bonds = [oe.get_symbol(index) for index in range(nqubits - 1)]
    bras = [
        oe.get_symbol(nqubits - 1 + index)
        for index in range(nqubits)
    ]
    kets = [
        oe.get_symbol(2 * nqubits - 1 + index)
        for index in range(nqubits)
    ]
    inputs = [bonds[0] + bras[0] + kets[0]]
    inputs.extend(
        bonds[wire - 1]
        + bonds[wire]
        + bras[wire]
        + kets[wire]
        for wire in range(1, nqubits - 1)
    )
    inputs.append(bonds[-1] + bras[-1] + kets[-1])
    equation = ",".join(inputs) + "->" + "".join(bras + kets)
    contracted = oe.contract(equation, *tensors, backend="jax")
    dimension = 1 << nqubits
    return contracted.reshape(dimension, dimension)


@pytest.mark.parametrize("nqubits", [2, 3, 4])
@pytest.mark.parametrize(
    ("coupling", "field"),
    [
        (1.0, 1.0),
        (0.7, 1.3),
        (0.0, 0.8),
        (1.1, 0.0),
    ],
)
def test_tfim_mpo_reconstructs_dense_hamiltonian(
    nqubits,
    coupling,
    field,
):
    spec = TFIMVQESpec(
        nqubits=nqubits,
        depth=1,
        coupling=coupling,
        field=field,
    )
    tensors = tfim_mpo_tensors(spec)
    actual = _contract_mpo_to_dense(tensors)
    expected = dense_tfim_hamiltonian(spec)
    np.testing.assert_allclose(
        np.asarray(actual),
        np.asarray(expected),
        rtol=1e-6,
        atol=1e-6,
    )
    assert len(tensors) == nqubits
    assert tensors[0].shape == (3, 2, 2)
    assert tensors[-1].shape == (3, 2, 2)
    assert all(
        tensor.shape == (3, 3, 2, 2)
        for tensor in tensors[1:-1]
    )


def test_tfim_mpo_supports_complex128():
    with jax.enable_x64():
        spec = TFIMVQESpec(
            nqubits=3,
            depth=1,
            coupling=0.7,
            field=1.3,
            dtype="complex128",
        )
        np.testing.assert_allclose(
            np.asarray(_contract_mpo_to_dense(tfim_mpo_tensors(spec))),
            np.asarray(dense_tfim_hamiltonian(spec)),
            rtol=1e-12,
            atol=1e-12,
        )
