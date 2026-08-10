import math

from xxzcert.itebd import (
    block_two_site_tensor,
    blocked_xxz_cell_operator,
    optimize_itebd,
)


def test_itebd_produces_variational_xxx_tensor():
    result = optimize_itebd(
        1.0,
        bond_dimension=2,
        schedule=((0.1, 20), (0.02, 40), (0.005, 80)),
    )
    assert result.tensor.shape == (4, 2, 4)
    assert block_two_site_tensor(result.tensor).shape == (2, 4, 2)
    assert blocked_xxz_cell_operator(1.0).shape == (16, 16)
    assert 0.25 - math.log(2) - 1e-8 <= result.energy < -0.40
