import numpy as np
from scipy.linalg import expm

from qh147.model import tfim_dense
from qh147.trotter import dense_trotter_step, second_order_gates


def test_2x2_schedule_contains_each_term_once_at_full_weight():
    gates = second_order_gates(2, 2, j=1.0, h=3.0, delta_beta=0.1)
    bond_weight = sum(g.weight for g in gates if len(g.sites) == 2)
    field_weight = sum(g.weight for g in gates if len(g.sites) == 1)
    assert np.isclose(bond_weight, 4.0)
    assert np.isclose(field_weight, 4.0)


def test_trotter_one_step_has_cubic_local_error():
    hmat = tfim_dense(2, 1, j=1.0, h=0.7)
    errors = []
    for dt in (0.1, 0.05):
        exact = expm(-dt * hmat)
        approx = dense_trotter_step(
            2,
            1,
            j=1.0,
            h=0.7,
            delta_beta=dt,
        )
        errors.append(np.linalg.norm(approx - exact))
    assert errors[0] / errors[1] > 6.0
