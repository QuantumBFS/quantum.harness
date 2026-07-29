from dataclasses import FrozenInstanceError
from itertools import product

import numpy as np
import pytest
from scipy.linalg import expm

from qh147.qmc_mapping import couplings, energy_from_bond_sums


def classical_partition(*, beta: float, h: float, m: int, j: float, nsites: int) -> float:
    c = couplings(beta, h, m, j=j)
    total = 0.0
    for spins in product((-1, 1), repeat=nsites * m):
        array = np.asarray(spins, dtype=int).reshape(m, nsites)
        spatial_sum = sum(np.sum(row[:-1] * row[1:]) for row in array)
        temporal_sum = np.sum(array * np.roll(array, -1, axis=0))
        total += np.exp(
            nsites * m * c.log_a + c.ks * spatial_sum + c.kt * temporal_sum
        )
    return total


def one_spin_energy(*, beta: float, h: float, m: int) -> float:
    c = couplings(beta, h, m, j=1.0)
    weighted_sum = 0.0
    weighted_energy = 0.0
    for spins in product((-1, 1), repeat=m):
        array = np.asarray(spins, dtype=int)
        temporal_sum = np.sum(array * np.roll(array, -1))
        weight = np.exp(m * c.log_a + c.kt * temporal_sum)
        weighted_sum += weight
        weighted_energy += weight * energy_from_bond_sums(
            c, spatial_sum=0, temporal_sum=temporal_sum, nsites=1
        )
    return weighted_energy / weighted_sum


def test_one_spin_partition_and_energy_are_exact():
    beta = 0.7
    h = 1.3
    m = 6

    assert classical_partition(beta=beta, h=h, m=m, j=1.0, nsites=1) == pytest.approx(
        2.0 * np.cosh(beta * h), rel=1e-12
    )
    assert one_spin_energy(beta=beta, h=h, m=m) == pytest.approx(
        -h * np.tanh(beta * h), rel=1e-12
    )


def test_classical_couplings_are_immutable():
    c = couplings(0.7, 1.3, 6, j=1.0)

    with pytest.raises(FrozenInstanceError):
        c.ks = 0.0


@pytest.mark.parametrize("m", (2, 4, 6, 8))
def test_two_spin_classical_sum_matches_trotter_transfer_matrix(m):
    beta = 0.4
    j = 1.0
    h = 0.7
    delta_beta = beta / m
    z = np.diag((1.0, -1.0))
    x = np.array(((0.0, 1.0), (1.0, 0.0)))
    h_spatial = -j * np.kron(z, z)
    h_field = -h * (np.kron(x, np.eye(2)) + np.kron(np.eye(2), x))
    transfer = expm(-delta_beta * h_spatial) @ expm(-delta_beta * h_field)

    expected = np.trace(np.linalg.matrix_power(transfer, m))
    actual = classical_partition(beta=beta, h=h, m=m, j=j, nsites=2)

    assert actual == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize(
    ("beta", "h", "m", "j"),
    ((0.0, 1.0, 2, 1.0), (1.0, 0.0, 2, 1.0), (1.0, 1.0, 1, 1.0), (1.0, 1.0, 2, 0.0)),
)
def test_couplings_reject_invalid_inputs(beta, h, m, j):
    with pytest.raises(ValueError):
        couplings(beta, h, m, j=j)


def test_energy_requires_a_positive_site_count():
    c = couplings(0.7, 1.3, 6, j=1.0)

    with pytest.raises(ValueError, match="nsites"):
        energy_from_bond_sums(c, spatial_sum=0, temporal_sum=0, nsites=0)
