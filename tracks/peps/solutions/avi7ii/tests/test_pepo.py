import numpy as np

from qh147.pepo import FinitePEPO
from qh147.trotter import second_order_gates


def test_identity_pepo_is_dense_identity():
    pepo = FinitePEPO.identity(2, 2)
    assert np.allclose(pepo.to_dense(), np.eye(16))


def test_two_site_gate_matches_dense_matrix():
    pepo = FinitePEPO.identity(2, 1)
    gate = next(
        gate
        for gate in second_order_gates(
            2,
            1,
            j=1.0,
            h=0.0,
            delta_beta=0.1,
        )
        if len(gate.sites) == 2
    )
    pepo.apply_gate(gate, max_bond=4)
    assert np.allclose(pepo.to_dense(), gate.matrix.reshape(4, 4))


def test_adjoint_swaps_operator_legs():
    pepo = FinitePEPO.identity(1, 1)
    tensor = pepo.tn["I0,0"]
    tensor.modify(data=np.array([[1.0, 2.0j], [3.0, 4.0]]))
    assert np.allclose(pepo.adjoint().to_dense(), pepo.to_dense().conj().T)
