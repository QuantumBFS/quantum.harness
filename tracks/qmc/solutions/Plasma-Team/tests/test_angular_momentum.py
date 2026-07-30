import numpy as np

from chiral_graviton.angular_momentum import (
    angular_momentum_lowering,
    angular_momentum_raising,
    highest_weight_basis,
    l2_operator,
)
from chiral_graviton.basis import FockBasis, SphereSystem


def test_single_particle_l2_is_q_qplus1():
    system = SphereSystem(n_electrons=1, two_q=3)
    for two_m in system.two_m_values:
        basis = FockBasis(system, two_m)
        value = l2_operator(basis).toarray()[0, 0]
        np.testing.assert_allclose(value, 1.5 * 2.5, atol=1e-12)


def test_ladder_operators_are_adjoint():
    system = SphereSystem(n_electrons=2, two_q=5)
    low = FockBasis(system, 0)
    high = FockBasis(system, 2)
    raising = angular_momentum_raising(low, high)
    lowering = angular_momentum_lowering(high, low)
    np.testing.assert_allclose(lowering.toarray(), raising.toarray().T, atol=1e-13)


def test_highest_weight_kernel_has_requested_l2():
    system = SphereSystem(n_electrons=2, two_q=5)
    basis = FockBasis(system, 4)  # M=L=2
    kernel = highest_weight_basis(basis)
    l2 = l2_operator(basis).toarray()
    np.testing.assert_allclose(kernel.T @ l2 @ kernel, 6.0 * np.eye(kernel.shape[1]), atol=1e-10)
